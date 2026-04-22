"""
Twilio SMS helpers — async send, webhook signature verify, phone normalization.

Keep dependencies minimal (httpx only, no twilio-python SDK) so the hub
image stays small.

Secret shape (Modal secret name `twilio-api`):
  - TWILIO_ACCOUNT_SID    — starts with `AC...`
  - TWILIO_AUTH_TOKEN     — keep secret
  - TWILIO_FROM_NUMBER    — E.164, e.g. +18325551234

Webhook URL to configure in the Twilio console (Messaging \u2192 phone number
\u2192 "A MESSAGE COMES IN"):
  https://hub.reformchiropractic.app/api/sms/webhook   (POST)
"""
import base64
import hashlib
import hmac
import os
import re
from typing import Optional
from urllib.parse import urlencode

import httpx


TWILIO_API = "https://api.twilio.com/2010-04-01"


def is_configured() -> bool:
    return bool(os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN"))


def normalize_phone(raw: str, default_country: str = "US") -> Optional[str]:
    """Return E.164 (e.g. `+12135551234`) or None if we can't reasonably
    coerce. No external deps — good-enough for US-heavy use; the caller
    should log failures rather than silently dropping."""
    if not raw: return None
    s = raw.strip()
    if s.startswith("+"):
        digits = re.sub(r"\D", "", s[1:])
        return "+" + digits if digits else None
    digits = re.sub(r"\D", "", s)
    if not digits: return None
    if default_country == "US":
        if len(digits) == 10: return "+1" + digits
        if len(digits) == 11 and digits.startswith("1"): return "+" + digits
    # Fallback: if it has enough digits, hope the caller handed us something
    # already globalized (e.g. 442071234567 from the UK); prefix `+`.
    if 7 <= len(digits) <= 15:
        return "+" + digits
    return None


async def send_sms(to_number: str, body: str,
                    from_number: Optional[str] = None,
                    status_callback: Optional[str] = None) -> dict:
    """POST to Twilio /Messages. Returns Twilio's response JSON (or
    `{error, status}`)."""
    if not is_configured():
        return {"error": "twilio_not_configured", "status": 503}
    sid   = os.environ["TWILIO_ACCOUNT_SID"]
    token = os.environ["TWILIO_AUTH_TOKEN"]
    frm   = from_number or os.environ.get("TWILIO_FROM_NUMBER", "")
    if not frm:
        return {"error": "TWILIO_FROM_NUMBER not configured", "status": 503}

    form = {"To": to_number, "From": frm, "Body": body}
    if status_callback: form["StatusCallback"] = status_callback
    url = f"{TWILIO_API}/Accounts/{sid}/Messages.json"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, data=form, auth=(sid, token))
    if r.status_code in (200, 201):
        return r.json()
    try:    detail = r.json()
    except: detail = {"raw": r.text[:400]}
    return {"error": detail, "status": r.status_code}


def verify_webhook_signature(url: str, params: dict, signature: str) -> bool:
    """Verify a Twilio webhook via `X-Twilio-Signature`. `url` is the full
    public URL the webhook hit; `params` is the POSTed form dict."""
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not token or not signature: return False
    # Twilio signs: url + concat of sorted(key+value) from form params
    s = url
    for k in sorted(params.keys()):
        s += k + str(params[k])
    mac = hmac.new(token.encode("utf-8"), s.encode("utf-8"), hashlib.sha1)
    expected = base64.b64encode(mac.digest()).decode("utf-8")
    return hmac.compare_digest(expected, signature)


# ─── Drop-in UI: Send-SMS modal + inline thread ──────────────────────────────
# Same pattern as meetings.py / tasks.py — page includes `sms_modal_html()`
# once and `sms_modal_js(company_id=..., contact_id=..., lead_id=..., phone=...)`
# in its JS block. Opens with `smsOpen()`.

_SMS_STYLES = """
<style>
.sms-modal-bg{position:fixed;inset:0;background:rgba(0,0,0,0.5);display:none;align-items:center;justify-content:center;z-index:1000;padding:16px}
.sms-modal-bg.open{display:flex}
.sms-modal{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:22px;width:min(540px,96vw);max-height:92vh;display:flex;flex-direction:column}
.sms-modal h3{margin:0 0 14px;font-size:17px;font-weight:700}
.sms-modal label{display:block;font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px}
.sms-modal input,.sms-modal textarea{width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:13px;font-family:inherit;box-sizing:border-box;margin-bottom:12px}
.sms-modal textarea{resize:vertical;min-height:70px}
.sms-thread{flex:1;overflow-y:auto;background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:8px;margin-bottom:14px;max-height:260px;min-height:120px}
.sms-bubble{padding:8px 11px;border-radius:10px;margin:6px 0;max-width:85%;font-size:13px;line-height:1.35;word-wrap:break-word}
.sms-bubble.out{background:#3b82f6;color:#fff;margin-left:auto;border-bottom-right-radius:3px}
.sms-bubble.in{background:var(--card);color:var(--text);border:1px solid var(--border);border-bottom-left-radius:3px}
.sms-meta{font-size:10px;color:var(--text3);margin-top:3px;opacity:.85}
.sms-bubble.out .sms-meta{color:rgba(255,255,255,.8)}
.sms-empty{text-align:center;padding:36px 10px;color:var(--text3);font-size:12px}
.sms-warn{padding:12px 14px;background:#f59e0b11;border:1px solid #f59e0b33;border-radius:8px;color:var(--text);font-size:12px;margin-bottom:12px;line-height:1.5}
.sms-actions{display:flex;gap:10px;justify-content:flex-end}
.sms-actions button{padding:8px 16px;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer;border:1px solid var(--border);background:transparent;color:var(--text)}
.sms-actions .primary{background:#3b82f6;color:#fff;border-color:#3b82f6}
.sms-actions .primary:hover{background:#2563eb}
.sms-msg{font-size:12px;color:var(--text3);margin-top:4px;min-height:16px}
.sms-msg.err{color:#ef4444}
.sms-msg.ok{color:#059669}
</style>
"""


def sms_modal_html() -> str:
    return (
        _SMS_STYLES
        + '<div class="sms-modal-bg" id="sms-bg" onclick="if(event.target===this)smsClose()">'
        + '<div class="sms-modal">'
        + '<h3>\U0001f4ac Send SMS</h3>'
        + '<div id="sms-warn"></div>'
        + '<label>To</label>'
        + '<input type="tel" id="sms-to" placeholder="+18325551234">'
        + '<label>Conversation</label>'
        + '<div class="sms-thread" id="sms-thread"><div class="sms-empty">Loading\u2026</div></div>'
        + '<label>New message</label>'
        + '<textarea id="sms-body" placeholder="Type your text here\u2026" maxlength="1600"></textarea>'
        + '<div class="sms-msg" id="sms-msg"></div>'
        + '<div class="sms-actions">'
        + '<button type="button" onclick="smsClose()">Close</button>'
        + '<button type="button" class="primary" onclick="smsSend()">Send</button>'
        + '</div>'
        + '</div></div>'
    )


def sms_modal_js(company_id: int = 0, contact_id: int = 0,
                  lead_id: int = 0, phone: str = "") -> str:
    # JSON-safe literals
    import json as _json
    return f"""
const _SMS_COMPANY = {int(company_id) or 0};
const _SMS_CONTACT = {int(contact_id) or 0};
const _SMS_LEAD    = {int(lead_id) or 0};
const _SMS_PHONE   = {_json.dumps(phone or '')};

function _smsFmt(iso) {{
  if (!iso) return '';
  try {{
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleString('en-US',{{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}});
  }} catch(e) {{ return ''; }}
}}

async function _smsLoadThread() {{
  const wrap = document.getElementById('sms-thread');
  const p = new URLSearchParams();
  if (_SMS_COMPANY) p.set('company_id', _SMS_COMPANY);
  else if (_SMS_CONTACT) p.set('contact_id', _SMS_CONTACT);
  else if (_SMS_LEAD)    p.set('lead_id',    _SMS_LEAD);
  else if (document.getElementById('sms-to').value.trim()) p.set('phone', document.getElementById('sms-to').value.trim());
  else {{
    wrap.innerHTML = '<div class="sms-empty">Enter a phone number to load history.</div>'; return;
  }}
  try {{
    const r = await fetch('/api/sms/thread?' + p.toString());
    if (r.status === 503) {{
      wrap.innerHTML = '<div class="sms-empty">Twilio not configured yet.</div>';
      return;
    }}
    if (!r.ok) {{ wrap.innerHTML = '<div class="sms-empty">Failed to load thread.</div>'; return; }}
    const data = await r.json();
    if (!data.configured) {{
      document.getElementById('sms-warn').innerHTML =
        '<div class="sms-warn">Twilio is not configured yet \u2014 sending will fail until the <code>twilio-api</code> Modal secret is attached to the hub.</div>';
    }} else {{
      document.getElementById('sms-warn').innerHTML = '';
    }}
    const items = data.items || [];
    if (!items.length) {{ wrap.innerHTML = '<div class="sms-empty">No messages yet \u2014 send the first one below.</div>'; return; }}
    wrap.innerHTML = items.map(function(m) {{
      const dir = (m.Direction && (m.Direction.value || m.Direction)) || 'outbound';
      const cls = dir === 'inbound' ? 'in' : 'out';
      const author = m.Author ? (m.Author + ' \u00b7 ') : '';
      return '<div class="sms-bubble ' + cls + '">'
        + esc(m.Body || '')
        + '<div class="sms-meta">' + author + _smsFmt(m.Created) + '</div>'
        + '</div>';
    }}).join('');
    wrap.scrollTop = wrap.scrollHeight;
  }} catch(e) {{
    wrap.innerHTML = '<div class="sms-empty">Error: ' + esc(String(e)) + '</div>';
  }}
}}

function smsOpen(prefillPhone) {{
  document.getElementById('sms-body').value = '';
  document.getElementById('sms-msg').textContent = '';
  document.getElementById('sms-msg').className = 'sms-msg';
  const to = document.getElementById('sms-to');
  if (prefillPhone) to.value = prefillPhone;
  else if (_SMS_PHONE && !to.value) to.value = _SMS_PHONE;
  document.getElementById('sms-bg').classList.add('open');
  _smsLoadThread();
  setTimeout(function(){{ document.getElementById('sms-body').focus(); }}, 40);
}}

function smsClose() {{ document.getElementById('sms-bg').classList.remove('open'); }}

async function smsSend() {{
  const to   = document.getElementById('sms-to').value.trim();
  const body = document.getElementById('sms-body').value.trim();
  const msg  = document.getElementById('sms-msg');
  if (!to || !body) {{
    msg.textContent = 'Phone and body are required.'; msg.className = 'sms-msg err'; return;
  }}
  msg.textContent = 'Sending\u2026'; msg.className = 'sms-msg';
  const payload = {{to, body}};
  if (_SMS_COMPANY) payload.company_id = _SMS_COMPANY;
  if (_SMS_CONTACT) payload.contact_id = _SMS_CONTACT;
  if (_SMS_LEAD)    payload.lead_id    = _SMS_LEAD;
  try {{
    const r = await fetch('/api/sms/send', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(payload),
    }});
    const data = await r.json();
    if (!r.ok) {{
      msg.textContent = 'Failed: ' + (data.error || r.status) + (data.hint ? ' \u2014 ' + data.hint : '');
      msg.className = 'sms-msg err';
      return;
    }}
    msg.textContent = 'Sent!'; msg.className = 'sms-msg ok';
    document.getElementById('sms-body').value = '';
    _smsLoadThread();
  }} catch(e) {{
    msg.textContent = 'Network error: ' + String(e);
    msg.className = 'sms-msg err';
  }}
}}

// Reload thread when the user types a phone into the `To` field (debounced)
(function() {{
  let _smsDeb = null;
  const to = document.getElementById('sms-to');
  if (to) to.addEventListener('input', function() {{
    if (_SMS_COMPANY || _SMS_CONTACT || _SMS_LEAD) return;  // scoped already
    clearTimeout(_smsDeb);
    _smsDeb = setTimeout(_smsLoadThread, 400);
  }});
}})();
"""
