"""
Attorney Micro-Portal — read-only per-firm status page.

Public URL: /a/{slug}  — no login; the slug IS the auth. Keep slugs
non-guessable (16+ base62 chars) and treat them like link-share tokens.

v1 renders a mobile-first branded page showing the firm's active
Reform patients (Active / Awaiting / Billed / Closed — except we only
show open stages by default), a firm-level summary, and a per-patient
"Request Case Packet" button that fires an email to Reform staff
(NOT a direct PDF download — keep that staff-only per product decision).

This module has no Modal/DB deps; it takes pre-fetched data from the
route handler and returns a full HTML string. The route handler in
modal_outreach_hub.py does: fetch company row by slug → fetch patients
linked to that firm → _portal_page(...) → HTMLResponse.
"""
from datetime import date, datetime
from html import escape as _esc
import secrets


_STAGE_LABELS = {
    "active":   "Active Treatment",
    "awaiting": "Awaiting / Negotiating",
    "billed":   "Billed",
    "closed":   "Closed",
}
_STAGE_COLORS = {
    "active":   "#7c3aed",  # purple
    "awaiting": "#2563eb",  # blue
    "billed":   "#d97706",  # amber
    "closed":   "#059669",  # green
}
# Stages surfaced to attorneys by default. Closed cases are hidden to keep
# the portal focused on actionable work, but they can be shown later via a
# "Show closed" toggle if firms ask.
_OPEN_STAGES = ("active", "awaiting", "billed")


def generate_slug(length: int = 16) -> str:
    """Return a URL-safe random token. base62 via secrets.token_urlsafe.
    `length` in bytes → ~1.33× that many chars of base64."""
    # secrets.token_urlsafe(12) ≈ 16 chars. Default gives ~22.
    return secrets.token_urlsafe(length)


def _sv(v):
    """Extract scalar from Baserow single_select / link_row dict/list shapes."""
    if isinstance(v, dict):
        return v.get("value", "") or v.get("name", "") or ""
    if isinstance(v, list) and v:
        x = v[0]
        if isinstance(x, dict):
            return x.get("value", "") or x.get("name", "") or ""
        return str(x)
    return v or ""


def _fmt_date(s):
    if not s: return "—"
    s = str(s)[:10]
    try:
        y, m, d = s.split("-")
        return f"{int(m)}/{int(d)}/{int(y) % 100:02d}"
    except Exception:
        return s


def _days_since(s):
    if not s: return None
    try:
        s = str(s)[:10]
        y, m, d = s.split("-")
        dt = date(int(y), int(m), int(d))
        return (date.today() - dt).days
    except Exception:
        return None


def _updated_ago(iso: str) -> str:
    if not iso: return "just now"
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        diff = (datetime.now(dt.tzinfo) - dt).total_seconds()
    except Exception:
        return "recently"
    if diff < 60:      return "just now"
    if diff < 3600:    return f"{int(diff // 60)}m ago"
    if diff < 86400:   return f"{int(diff // 3600)}h ago"
    if diff < 86400 * 30: return f"{int(diff // 86400)}d ago"
    return "over a month ago"


def _portal_page(firm: dict, patients_by_stage: dict, *, last_updated_iso: str = "") -> str:
    """Render the attorney-facing portal HTML.

    firm              — T_COMPANIES row (must be Category=attorney, Portal Enabled=true)
    patients_by_stage — dict of stage-key → list of PI patient rows (each has `_stage` attr)
    last_updated_iso  — ISO timestamp to show as 'last updated'; caller
                        typically uses max(patient Updated) or current time.
    """
    firm_name = (firm.get("Name") or "Referring Firm").strip()
    updated_label = _updated_ago(last_updated_iso) if last_updated_iso else "just now"

    # Summary counts
    counts = {k: len(patients_by_stage.get(k, [])) for k in _OPEN_STAGES}
    total_open = sum(counts.values())

    summary_cards = ""
    for k in _OPEN_STAGES:
        summary_cards += (
            f'<div class="sum-card" style="border-top:3px solid {_STAGE_COLORS[k]}">'
            f'<div class="sum-count">{counts[k]}</div>'
            f'<div class="sum-label">{_esc(_STAGE_LABELS[k])}</div>'
            f'</div>'
        )

    # Flat list of patients with stage info
    body_cards = ""
    flat_patients = []
    for stage_key in _OPEN_STAGES:
        for p in patients_by_stage.get(stage_key, []):
            p_copy = dict(p)
            p_copy["_stage"] = stage_key
            flat_patients.append(p_copy)

    if not flat_patients:
        body_cards = (
            '<div class="empty">'
            '<h3>No active cases right now</h3>'
            '<p>We\'ll update this page as soon as you refer a patient who is actively receiving care.</p>'
            '</div>'
        )
    else:
        for p in flat_patients:
            pname  = (p.get("Name") or "").strip() or "Unnamed patient"
            stage  = p["_stage"]
            visits = p.get("# of Visits") or p.get("Visits") or "—"
            doi    = _fmt_date(p.get("DOI") or p.get("Date of Injury") or p.get("Date of Accident"))
            fu     = p.get("Follow-Up Date") or p.get("Follow Up Date") or ""
            fu_fmt = _fmt_date(fu)
            fu_days = _days_since(fu)
            fu_color = "var(--text3)"
            if fu_days is not None:
                if fu_days > 14:  fu_color = "#dc2626"   # >14d past follow-up
                elif fu_days > 0: fu_color = "#d97706"   # recently past
                elif fu_days >= -3: fu_color = "#059669" # upcoming in 3d
            stage_label = _STAGE_LABELS[stage]
            stage_color = _STAGE_COLORS[stage]
            js_name = _esc(pname).replace("'", "&#39;")  # safe for inline JS string literal

            body_cards += f"""
<div class="p-card" data-pid="{p.get('id')}">
  <div class="p-hd">
    <div class="p-name">{_esc(pname)}</div>
    <span class="p-stage" style="background:{stage_color}">{_esc(stage_label)}</span>
  </div>
  <div class="p-grid">
    <div class="p-kv"><span class="k">DOI</span><span class="v">{_esc(doi)}</span></div>
    <div class="p-kv"><span class="k">Visits</span><span class="v">{_esc(str(visits))}</span></div>
    <div class="p-kv"><span class="k">Last / Next Follow-Up</span><span class="v" style="color:{fu_color}">{_esc(fu_fmt)}</span></div>
  </div>
  <button class="p-cta" onclick="requestPacket({p.get('id')},'{js_name}',this)">
    Request Case Packet
  </button>
</div>
"""

    footer_year = date.today().year

    return f"""<!DOCTYPE html><html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<title>{_esc(firm_name)} — Case Portal</title>
<style>
:root {{
  --bg:      #fafafa;
  --card:    #ffffff;
  --border:  #e2e8f0;
  --text:    #0f172a;
  --text2:   #334155;
  --text3:   #64748b;
  --brand:   #ea580c;
  --brand-d: #c2410c;
  --shadow:  0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06);
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);line-height:1.5;padding-bottom:40px}}
.wrap{{max-width:920px;margin:0 auto;padding:20px 16px}}
.hdr{{background:linear-gradient(135deg,var(--brand),var(--brand-d));color:#fff;padding:28px 24px;border-radius:14px;margin-bottom:20px;box-shadow:var(--shadow)}}
.hdr-brand{{font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;opacity:.85}}
.hdr-firm{{font-size:22px;font-weight:700;margin-top:4px;line-height:1.2}}
.hdr-sub{{font-size:13px;opacity:.85;margin-top:6px}}
.sum-row{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:18px}}
.sum-card{{background:var(--card);padding:14px 16px;border-radius:10px;border:1px solid var(--border);box-shadow:var(--shadow)}}
.sum-count{{font-size:24px;font-weight:700;color:var(--text)}}
.sum-label{{font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.4px;margin-top:2px}}
.section-hd{{font-size:13px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.5px;margin:20px 0 10px;padding-left:4px}}
.p-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px 18px;margin-bottom:10px;box-shadow:var(--shadow)}}
.p-hd{{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:10px}}
.p-name{{font-size:16px;font-weight:700;color:var(--text);flex:1}}
.p-stage{{color:#fff;font-size:10px;font-weight:700;letter-spacing:.3px;text-transform:uppercase;padding:3px 9px;border-radius:10px;white-space:nowrap;flex-shrink:0}}
.p-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px}}
.p-kv{{display:flex;flex-direction:column}}
.p-kv .k{{font-size:10px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.4px;margin-bottom:2px}}
.p-kv .v{{font-size:13px;color:var(--text2);font-weight:500}}
.p-cta{{width:100%;padding:9px;background:var(--card);border:1px solid var(--brand);color:var(--brand);border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;transition:background .12s,color .12s}}
.p-cta:hover{{background:var(--brand);color:#fff}}
.p-cta:disabled{{opacity:.6;cursor:default}}
.p-cta.sent{{background:#059669;border-color:#059669;color:#fff}}
.empty{{background:var(--card);padding:36px 24px;border-radius:12px;text-align:center;color:var(--text3);border:1px dashed var(--border)}}
.empty h3{{color:var(--text2);font-size:15px;margin-bottom:6px}}
.empty p{{font-size:13px}}
.splash-bg{{position:fixed;inset:0;background:rgba(0,0,0,0.6);display:none;align-items:center;justify-content:center;padding:24px;z-index:900}}
.splash-bg.on{{display:flex}}
.splash-box{{background:#fff;max-width:440px;padding:28px 28px 24px;border-radius:14px}}
.splash-box h3{{font-size:17px;margin-bottom:10px;color:var(--text)}}
.splash-box p{{font-size:13px;color:var(--text2);margin-bottom:14px}}
.splash-box button{{background:var(--brand);color:#fff;border:none;padding:9px 20px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit}}
.footer{{text-align:center;font-size:11px;color:var(--text3);margin-top:30px;padding:0 16px}}
.footer a{{color:var(--text3)}}
@media (max-width:520px) {{
  .sum-row{{grid-template-columns:repeat(3,1fr);gap:6px}}
  .sum-card{{padding:10px 8px}}
  .sum-count{{font-size:18px}}
  .sum-label{{font-size:9px}}
  .p-grid{{grid-template-columns:1fr 1fr;gap:8px}}
  .p-kv:nth-child(3){{grid-column:span 2}}
  .hdr-firm{{font-size:19px}}
}}
</style>
</head>
<body>
<div class="splash-bg" id="splash" onclick="if(event.target===this){{}}">
  <div class="splash-box">
    <h3>Confidential Medical Information</h3>
    <p>This page contains confidential medical and case information about your clients. Please do not share this URL outside your firm.</p>
    <button onclick="dismissSplash()">I understand</button>
  </div>
</div>

<div class="wrap">
  <div class="hdr">
    <div class="hdr-brand">Reform Chiropractic — Case Portal</div>
    <div class="hdr-firm">{_esc(firm_name)}</div>
    <div class="hdr-sub">{total_open} open {'case' if total_open == 1 else 'cases'} · updated {_esc(updated_label)}</div>
  </div>

  <div class="sum-row">
    {summary_cards}
  </div>

  <div class="section-hd">Cases</div>
  {body_cards}

  <div class="footer">
    Reform Chiropractic &middot; (832) 699-3148 &middot; reformchiropractic.com<br>
    &copy; {footer_year} &middot; For referring attorneys only. Do not share this URL.
  </div>
</div>

<script>
const SLUG = {_quote_js(firm.get("Portal Slug") or "")};

function dismissSplash() {{
  document.getElementById('splash').classList.remove('on');
  try {{ localStorage.setItem('portal-ack-' + SLUG, '1'); }} catch(e) {{}}
}}

(function () {{
  try {{
    if (!localStorage.getItem('portal-ack-' + SLUG)) {{
      document.getElementById('splash').classList.add('on');
    }}
  }} catch(e) {{
    document.getElementById('splash').classList.add('on');
  }}
}})();

async function requestPacket(patientId, patientName, btn) {{
  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = 'Requesting…';
  try {{
    const r = await fetch('/a/' + SLUG + '/request-packet', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{patient_id: patientId, patient_name: patientName}}),
    }});
    if (r.ok) {{
      btn.classList.add('sent');
      btn.textContent = '✓ Staff notified';
    }} else {{
      btn.disabled = false;
      btn.textContent = original;
      alert('Could not send request. Please call (832) 699-3148.');
    }}
  }} catch (e) {{
    btn.disabled = false;
    btn.textContent = original;
    alert('Network error. Please call (832) 699-3148.');
  }}
}}
</script>
</body></html>"""


def _quote_js(s: str) -> str:
    """Quote a string safely for embedding inside a JS string literal."""
    return "'" + (s or "").replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"


def _not_found_page() -> str:
    """404 shown when a slug doesn't match or the firm's portal is disabled.
    Keep it generic — don't confirm that the slug WOULD have matched if enabled,
    since that's a small fingerprinting leak."""
    return """<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><title>Not Found</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<style>body{font-family:-apple-system,sans-serif;background:#fafafa;color:#334155;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px;margin:0}
.box{background:#fff;padding:36px 30px;border-radius:12px;border:1px solid #e2e8f0;text-align:center;max-width:440px}
h1{font-size:22px;color:#0f172a;margin-bottom:8px}p{font-size:14px;color:#64748b;line-height:1.6}</style></head>
<body><div class="box">
<h1>Page not found</h1>
<p>This link is either incorrect or no longer active.<br>
If you believe this is an error, please contact Reform Chiropractic at (832) 699-3148.</p>
</div></body></html>"""
