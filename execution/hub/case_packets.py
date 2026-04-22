"""
Case Packet generator — PDF summary of a PI patient for the referring attorney.
v1: download-only; email + attorney-facing delivery land in later iterations.
"""
from datetime import date
from html import escape as _esc


def _sv(v):
    """Extract value from Baserow single_select dict or pass through scalars."""
    if isinstance(v, dict):
        return v.get("value", "") or ""
    if isinstance(v, list) and v:
        x = v[0]
        if isinstance(x, dict):
            return x.get("value", "") or x.get("name", "") or ""
        return str(x)
    return v or ""


def _fmt_money(v):
    try: return f"${float(v):,.2f}"
    except Exception: return "—"


def _fmt_date(v):
    if not v: return "—"
    s = str(v)[:10]
    try:
        y, m, d = s.split("-")
        return f"{int(m)}/{int(d)}/{y}"
    except Exception:
        return s


def _match_finance(patient, finance_rows):
    """Return finance rows whose Patient Name matches this patient."""
    name = (patient.get("Name") or "").strip().lower()
    if not name: return []
    out = []
    for r in finance_rows or []:
        rn = (r.get("Patient Name") or r.get("Name") or "").strip().lower()
        if rn and rn == name:
            out.append(r)
    return out


def _firm_from_patient(p):
    return (
        _sv(p.get("Law Firm Name ONLY"))
        or _sv(p.get("Law Firm Name"))
        or _sv(p.get("Law Firm"))
        or _sv(p.get("Attorney"))
        or _sv(p.get("Referring Attorney"))
        or ""
    )


def _packet_html(patient: dict, finance_rows: list, stage: str = "") -> str:
    name   = (patient.get("Name") or "").strip() or "Unnamed Patient"
    dob    = _fmt_date(patient.get("DOB") or patient.get("Date of Birth"))
    phone  = patient.get("Phone") or patient.get("Cell Phone") or "—"
    email  = patient.get("Email") or "—"
    doi    = _fmt_date(patient.get("DOI") or patient.get("Date of Injury") or patient.get("Date of Accident"))
    firm   = _firm_from_patient(patient) or "—"
    atty   = _sv(patient.get("Attorney") or patient.get("Referring Attorney")) or "—"
    adj    = patient.get("Adjuster") or patient.get("Claims Adjuster") or "—"
    ins    = patient.get("Insurance") or patient.get("Insurance Company") or "—"
    visits = patient.get("# of Visits") or patient.get("Visits") or "—"
    fu     = _fmt_date(patient.get("Follow-Up Date") or patient.get("Follow Up Date"))
    notes  = (patient.get("Case Notes") or patient.get("Notes") or "").strip()
    stage_label = (stage or "active").replace("_", " ").title()

    fin = _match_finance(patient, finance_rows)
    total_settlement = sum((float(r.get("Settlement Amount") or 0) or 0) for r in fin)
    total_fees       = sum((float(r.get("Attorney Fees")     or 0) or 0) for r in fin)
    total_paid       = sum((float(r.get("Amount Paid")       or 0) or 0) for r in fin)
    total_due        = sum((float(r.get("Amount Due")        or 0) or 0) for r in fin)

    fin_rows_html = ""
    for r in fin:
        fin_rows_html += (
            "<tr>"
            f"<td>{_esc(_sv(r.get('MedPay/PI/Insurance')) or r.get('Type') or '—')}</td>"
            f"<td class='r'>{_fmt_money(r.get('Settlement Amount'))}</td>"
            f"<td class='r'>{_fmt_money(r.get('Attorney Fees'))}</td>"
            f"<td class='r'>{_fmt_money(r.get('Amount Paid'))}</td>"
            f"<td class='r'>{_fmt_money(r.get('Amount Due'))}</td>"
            "</tr>"
        )
    if not fin_rows_html:
        fin_rows_html = (
            "<tr><td colspan='5' style='text-align:center;color:#888'>"
            "No billed charges on record yet."
            "</td></tr>"
        )

    notes_html = ""
    if notes:
        # Strip any internal firm-history lines before showing to attorney
        clean = "\n".join([ln for ln in notes.splitlines() if not ln.strip().startswith("Firm history:")]).strip()
        if clean:
            notes_html = (
                "<div class='section'>"
                "<h3>Case Notes</h3>"
                f"<div class='notes'>{_esc(clean)}</div>"
                "</div>"
            )

    today = date.today().strftime("%B %-d, %Y") if hasattr(date.today(), "strftime") else str(date.today())
    try:
        # Windows strftime doesn't support %-d; fall back to %d and strip leading zero
        today = date.today().strftime("%B %d, %Y").replace(" 0", " ")
    except Exception:
        today = str(date.today())

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Case Packet — {_esc(name)}</title>
<style>
  @page {{ size: Letter; margin: 0.7in 0.75in; }}
  body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; color: #1f2937; font-size: 11pt; line-height: 1.4; }}
  h1 {{ font-size: 18pt; margin: 0 0 2pt 0; color: #111827; letter-spacing: -0.3pt; }}
  h2 {{ font-size: 13pt; margin: 0; color: #111827; }}
  h3 {{ font-size: 11pt; margin: 14pt 0 6pt; color: #374151; border-bottom: 1pt solid #e5e7eb; padding-bottom: 3pt; text-transform: uppercase; letter-spacing: 0.5pt; }}
  .hdr {{ border-bottom: 2pt solid #111827; padding-bottom: 10pt; margin-bottom: 14pt; display: flex; justify-content: space-between; align-items: flex-end; }}
  .hdr-left {{ }}
  .hdr-right {{ text-align: right; font-size: 9pt; color: #6b7280; }}
  .brand {{ color: #111827; font-weight: 700; font-size: 14pt; letter-spacing: -0.3pt; }}
  .subtle {{ color: #6b7280; font-size: 9pt; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8pt 18pt; margin: 10pt 0; }}
  .kv {{ display: flex; flex-direction: column; }}
  .kv .k {{ font-size: 8pt; color: #6b7280; text-transform: uppercase; letter-spacing: 0.4pt; }}
  .kv .v {{ font-size: 11pt; color: #111827; font-weight: 500; }}
  .pill {{ display: inline-block; padding: 2pt 8pt; border-radius: 10pt; font-size: 9pt; font-weight: 600; background: #dbeafe; color: #1e3a8a; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 4pt; font-size: 10pt; }}
  th, td {{ padding: 5pt 8pt; text-align: left; border-bottom: 1pt solid #f3f4f6; }}
  th {{ background: #f9fafb; color: #374151; text-transform: uppercase; font-size: 8pt; letter-spacing: 0.4pt; font-weight: 600; }}
  .r {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tfoot td {{ font-weight: 700; border-top: 1.5pt solid #374151; border-bottom: none; }}
  .notes {{ background: #f9fafb; padding: 10pt 12pt; border-radius: 4pt; white-space: pre-wrap; font-size: 10pt; color: #374151; }}
  .footer {{ margin-top: 24pt; padding-top: 10pt; border-top: 1pt solid #e5e7eb; font-size: 8.5pt; color: #6b7280; text-align: center; }}
</style></head>
<body>
  <div class="hdr">
    <div class="hdr-left">
      <div class="brand">Reform Chiropractic</div>
      <div class="subtle">Personal Injury Case Summary</div>
    </div>
    <div class="hdr-right">
      Generated {today}<br>
      <span class="pill">{_esc(stage_label)}</span>
    </div>
  </div>

  <h1>{_esc(name)}</h1>
  <div class="subtle">Prepared for: {_esc(firm)}</div>

  <div class="section">
    <h3>Patient Information</h3>
    <div class="grid">
      <div class="kv"><span class="k">Date of Birth</span><span class="v">{_esc(dob)}</span></div>
      <div class="kv"><span class="k">Phone</span><span class="v">{_esc(phone)}</span></div>
      <div class="kv"><span class="k">Email</span><span class="v">{_esc(email)}</span></div>
      <div class="kv"><span class="k">Date of Injury</span><span class="v">{_esc(doi)}</span></div>
    </div>
  </div>

  <div class="section">
    <h3>Case Details</h3>
    <div class="grid">
      <div class="kv"><span class="k">Referring Firm</span><span class="v">{_esc(firm)}</span></div>
      <div class="kv"><span class="k">Attorney</span><span class="v">{_esc(atty)}</span></div>
      <div class="kv"><span class="k">Insurance</span><span class="v">{_esc(ins)}</span></div>
      <div class="kv"><span class="k">Adjuster</span><span class="v">{_esc(adj)}</span></div>
      <div class="kv"><span class="k">Visits to Date</span><span class="v">{_esc(str(visits))}</span></div>
      <div class="kv"><span class="k">Next Follow-Up</span><span class="v">{_esc(fu)}</span></div>
    </div>
  </div>

  <div class="section">
    <h3>Financial Summary</h3>
    <table>
      <thead><tr>
        <th>Coverage</th><th class="r">Settlement</th><th class="r">Atty Fees</th><th class="r">Paid</th><th class="r">Balance</th>
      </tr></thead>
      <tbody>{fin_rows_html}</tbody>
      {"<tfoot><tr><td>Total</td>"
       f"<td class='r'>{_fmt_money(total_settlement)}</td>"
       f"<td class='r'>{_fmt_money(total_fees)}</td>"
       f"<td class='r'>{_fmt_money(total_paid)}</td>"
       f"<td class='r'>{_fmt_money(total_due)}</td></tr></tfoot>" if fin else ""}
    </table>
  </div>

  {notes_html}

  <div class="footer">
    Reform Chiropractic &nbsp;·&nbsp; hub.reformchiropractic.app &nbsp;·&nbsp; Personal Injury Care &amp; Documentation<br>
    This document contains confidential medical and case information. Share only with authorized legal counsel.
  </div>
</body></html>"""


def _packet_pdf(patient: dict, finance_rows: list, stage: str = "") -> bytes:
    """Render patient + finance to PDF bytes using weasyprint."""
    from weasyprint import HTML
    html = _packet_html(patient, finance_rows, stage=stage)
    return HTML(string=html).write_pdf()


def _normalize_firm(s: str) -> str:
    """Normalize a firm name for loose matching: strip punctuation + whitespace, lowercase."""
    s = (s or "").strip().lower()
    # Common legal suffixes / punctuation that vary between PI sheet and CRM
    for noise in [",", ".", "'", '"', "  ", "\t"]:
        s = s.replace(noise, " ")
    for suffix in [" llp", " llc", " pllc", " pc", " p c", " inc", " a p c", " apc"]:
        if s.endswith(suffix): s = s[: -len(suffix)]
    return " ".join(s.split())


def _lookup_attorney_contact(firm_name: str,
                              companies: list,
                              contacts: list = None) -> dict:
    """Best-effort lookup of attorney email + firm metadata by firm name.

    Match order:
      1. T_COMPANIES row with Category=attorney AND Name matches (normalized).
         Return its Email if populated, plus company_id for activity logging.
      2. If company row matched but Email empty, scan T_CONTACTS for rows whose
         Primary Company link points to that company_id; return the first
         Email field that's populated.
      3. No match — return empty email but still pass through company_id=None
         so the caller can show the dialog with an empty 'to' field.

    Returns: {
      "company_id": int | None,
      "company_name": str,        # Name from Companies row if matched, else original firm_name
      "email": str,                # Best-guess email, may be ""
      "source": "company"|"contact"|"none",  # Where the email came from
    }
    """
    out = {"company_id": None, "company_name": firm_name or "", "email": "", "source": "none"}
    if not firm_name:
        return out
    target = _normalize_firm(firm_name)
    if not target:
        return out
    # Step 1: match in T_COMPANIES
    matched = None
    for c in companies or []:
        if _sv(c.get("Category")).lower() != "attorney":
            continue
        cname = _normalize_firm(c.get("Name") or "")
        if cname and cname == target:
            matched = c
            break
    if not matched:
        return out
    out["company_id"] = matched.get("id")
    out["company_name"] = (matched.get("Name") or firm_name).strip()
    company_email = (matched.get("Email") or "").strip()
    if company_email:
        out["email"] = company_email
        out["source"] = "company"
        return out
    # Step 2: fall through to linked contacts
    cid = matched.get("id")
    for p in contacts or []:
        primary = p.get("Primary Company") or []
        if isinstance(primary, list):
            ids = []
            for item in primary:
                if isinstance(item, dict) and item.get("id"):
                    ids.append(item["id"])
                elif isinstance(item, int):
                    ids.append(item)
            if cid in ids:
                pemail = (p.get("Email") or "").strip()
                if pemail:
                    out["email"] = pemail
                    out["source"] = "contact"
                    return out
    return out
