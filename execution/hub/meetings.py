"""
Shared meeting-scheduler modal HTML + JS. Dropped into any page that wants
a "+ Schedule meeting" button (company_detail, people detail). Posts to
POST /api/meetings which writes to the user's primary Google Calendar and
auto-logs an Activity on the linked Company/Contact.

Consumer wires it by:
  1) Including `meeting_modal_html()` once in the page body
  2) Including `meeting_modal_js(company_id=..., contact_id=..., prefill_email=...)`
     in the page's JS block
  3) Calling `openMeetingModal()` from a button's onclick
"""


MEETING_MODAL_STYLES = """
<style>
.mt-modal-bg{position:fixed;inset:0;background:rgba(0,0,0,0.5);display:none;align-items:center;justify-content:center;z-index:1000;padding:16px}
.mt-modal-bg.open{display:flex}
.mt-modal{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:22px;width:min(520px,96vw);max-height:92vh;overflow-y:auto}
.mt-modal h3{margin:0 0 14px;font-size:17px;font-weight:700}
.mt-modal label{display:block;font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:0.4px;margin-bottom:4px}
.mt-modal input,.mt-modal textarea,.mt-modal select{width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:13px;font-family:inherit;box-sizing:border-box;margin-bottom:12px}
.mt-modal textarea{resize:vertical;min-height:70px}
.mt-modal-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:500px){.mt-modal-row{grid-template-columns:1fr}}
.mt-modal-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:8px}
.mt-modal-actions button{padding:8px 16px;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer;border:1px solid var(--border);background:transparent;color:var(--text)}
.mt-modal-actions .mt-primary{background:#3b82f6;color:#fff;border-color:#3b82f6}
.mt-modal-actions .mt-primary:hover{background:#2563eb}
.mt-modal .mt-msg{font-size:12px;color:var(--text3);margin-top:8px;min-height:18px}
.mt-modal .mt-msg.err{color:#ef4444}
.mt-modal .mt-msg.ok{color:#059669}
.mt-btn{padding:8px 14px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-size:13px;font-weight:600;cursor:pointer;text-decoration:none;display:inline-block}
.mt-btn:hover{border-color:var(--text3)}
.mt-btn.primary{background:#3b82f6;color:#fff;border-color:#3b82f6}
.mt-btn.primary:hover{background:#2563eb}
</style>
"""


def meeting_modal_html() -> str:
    """HTML for the Schedule Meeting modal. Include once per page."""
    return (
        MEETING_MODAL_STYLES
        + '<div class="mt-modal-bg" id="mt-modal-bg" onclick="if(event.target===this)closeMeetingModal()">'
        + '<div class="mt-modal">'
        + '<h3>\U0001f4c5 Schedule meeting</h3>'
        + '<label>Title</label>'
        + '<input type="text" id="mt-title" placeholder="Intro call with X, Firm visit, etc.">'
        + '<div class="mt-modal-row">'
        + '<div><label>Date</label><input type="date" id="mt-date"></div>'
        + '<div><label>Start time</label><input type="time" id="mt-time"></div>'
        + '</div>'
        + '<div class="mt-modal-row">'
        + '<div><label>Duration</label>'
        + '<select id="mt-duration">'
        + '<option value="15">15 min</option>'
        + '<option value="30" selected>30 min</option>'
        + '<option value="45">45 min</option>'
        + '<option value="60">1 hour</option>'
        + '<option value="90">1.5 hours</option>'
        + '<option value="120">2 hours</option>'
        + '</select></div>'
        + '<div><label>Location (optional)</label><input type="text" id="mt-location" placeholder="Office, Google Meet, etc."></div>'
        + '</div>'
        + '<label>Invitees (comma-separated emails)</label>'
        + '<input type="text" id="mt-attendees" placeholder="name@example.com, other@example.com">'
        + '<label>Notes</label>'
        + '<textarea id="mt-description" placeholder="Agenda, context, or anything else Google Calendar should include"></textarea>'
        + '<div class="mt-msg" id="mt-msg"></div>'
        + '<div class="mt-modal-actions">'
        + '<button type="button" onclick="closeMeetingModal()">Cancel</button>'
        + '<button type="button" class="mt-primary" id="mt-submit" onclick="submitMeeting()">Schedule & send invites</button>'
        + '</div>'
        + '</div></div>'
    )


def meeting_modal_js(company_id: int = 0, contact_id: int = 0, prefill_email: str = "") -> str:
    """JS for the modal. Pass company_id and/or contact_id so the meeting gets
    linked to the right entity. prefill_email fills the invitees input."""
    return f"""
let _MT_COMPANY_ID = {company_id or 0};
let _MT_CONTACT_ID = {contact_id or 0};
let _MT_PREFILL = {repr(prefill_email or '')};

function openMeetingModal() {{
  const today = new Date();
  today.setMinutes(today.getMinutes() - today.getTimezoneOffset());
  document.getElementById('mt-date').value = today.toISOString().split('T')[0];
  // Round start time up to next 30-min block
  const h = today.getHours();
  const m = today.getMinutes();
  const rounded = m < 30 ? 30 : 60;
  const startH = rounded === 60 ? (h + 1) % 24 : h;
  const startM = rounded === 60 ? 0 : 30;
  document.getElementById('mt-time').value = String(startH).padStart(2,'0') + ':' + String(startM).padStart(2,'0');
  document.getElementById('mt-title').value = '';
  document.getElementById('mt-location').value = '';
  document.getElementById('mt-description').value = '';
  document.getElementById('mt-attendees').value = _MT_PREFILL;
  document.getElementById('mt-duration').value = '30';
  document.getElementById('mt-msg').textContent = '';
  document.getElementById('mt-msg').className = 'mt-msg';
  document.getElementById('mt-submit').disabled = false;
  document.getElementById('mt-modal-bg').classList.add('open');
  setTimeout(() => document.getElementById('mt-title').focus(), 50);
}}

function closeMeetingModal() {{
  document.getElementById('mt-modal-bg').classList.remove('open');
}}

async function submitMeeting() {{
  const title    = document.getElementById('mt-title').value.trim();
  const date     = document.getElementById('mt-date').value;
  const time     = document.getElementById('mt-time').value;
  const duration = parseInt(document.getElementById('mt-duration').value, 10);
  const location = document.getElementById('mt-location').value.trim();
  const desc     = document.getElementById('mt-description').value.trim();
  const attendees = document.getElementById('mt-attendees').value
    .split(/[,;]+/).map(s => s.trim()).filter(Boolean);
  const msg = document.getElementById('mt-msg');

  if (!title || !date || !time) {{
    msg.textContent = 'Title, date, and start time are required.';
    msg.className = 'mt-msg err';
    return;
  }}

  // Build ISO strings anchored to the browser's timezone. Google will
  // interpret with the `timeZone` param we send on start/end.
  const startLocal = date + 'T' + time + ':00';
  const startD = new Date(startLocal);
  const endD   = new Date(startD.getTime() + duration * 60000);
  const pad = n => String(n).padStart(2, '0');
  const fmt = d => d.getFullYear() + '-' + pad(d.getMonth()+1) + '-' + pad(d.getDate())
    + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':00';

  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/Los_Angeles';

  const payload = {{
    title, attendees, location, description: desc,
    start: fmt(startD),
    end:   fmt(endD),
    tz,
  }};
  if (_MT_COMPANY_ID) payload.company_id = _MT_COMPANY_ID;
  if (_MT_CONTACT_ID) payload.contact_id = _MT_CONTACT_ID;

  document.getElementById('mt-submit').disabled = true;
  msg.textContent = 'Scheduling\u2026';
  msg.className = 'mt-msg';

  try {{
    const r = await fetch('/api/meetings', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(payload),
    }});
    const data = await r.json();
    if (!r.ok) {{
      const hint = data.hint ? ' \u2014 ' + data.hint : '';
      msg.textContent = 'Failed: ' + (data.error || r.status) + hint;
      msg.className = 'mt-msg err';
      document.getElementById('mt-submit').disabled = false;
      return;
    }}
    msg.innerHTML = 'Scheduled! <a href="' + data.htmlLink + '" target="_blank" style="color:#3b82f6">Open in Calendar \u2192</a>';
    msg.className = 'mt-msg ok';
    // Refresh activity feed if the page exposed either loader
    setTimeout(() => {{
      if (typeof loadActivities === 'function') loadActivities();
      if (typeof loadActs === 'function') loadActs();
      closeMeetingModal();
    }}, 1200);
  }} catch(e) {{
    msg.textContent = 'Network error: ' + String(e);
    msg.className = 'mt-msg err';
    document.getElementById('mt-submit').disabled = false;
  }}
}}
"""
