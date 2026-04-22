"""
Public self-booking page for prospective patients.

`GET /book` renders a branded page with weekday/time-slot pickers. On submit,
`POST /api/book` (defined in modal_outreach_hub.py) creates a T_LEADS row
with Status=Appointment Scheduled and the selected Appointment Date.

v1 does not check calendar availability \u2014 staff reschedule conflicts manually.
v2 can layer in Google FreeBusy via a service account.
"""


def _quote_str(s: str) -> str:
    """Safe JS string literal."""
    return "'" + (s or "").replace("\\", "\\\\").replace("'", "\\'") + "'"


def _booking_page(event_name: str = "Book a Consultation", slug: str = "") -> str:
    """Standalone branded booking page. No auth required.
    `event_name` shows in the header so we can reuse this for specific events
    (e.g. "Back Pain Clinic — Book a Slot")."""
    slug_js = _quote_str(slug)
    return f"""<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{event_name} \u2014 Reform Chiropractic</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,#fff5eb 0%,#fff 50%,#f0f7ff 100%);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}}
.book-card{{background:#fff;border-radius:20px;box-shadow:0 8px 40px rgba(0,0,0,0.08);max-width:560px;width:100%;overflow:hidden}}
.book-header{{background:linear-gradient(135deg,#ea580c,#dc2626);padding:30px 28px;text-align:center;color:#fff}}
.book-header h1{{font-size:14px;font-weight:600;letter-spacing:1px;text-transform:uppercase;opacity:.9;margin-bottom:6px}}
.book-header h2{{font-size:22px;font-weight:700;line-height:1.3}}
.book-body{{padding:26px 28px}}
.book-section{{margin-bottom:22px}}
.book-label{{font-size:12px;font-weight:600;color:#475569;text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px;display:block}}
.book-input{{width:100%;padding:12px 14px;border:1.5px solid #e2e8f0;border-radius:10px;font-size:15px;color:#1e293b;outline:none;transition:border-color .15s}}
.book-input:focus{{border-color:#ea580c}}
.book-input::placeholder{{color:#94a3b8}}
textarea.book-input{{min-height:74px;resize:vertical;font-family:inherit}}
.day-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}
.day-btn{{padding:9px 6px;border:1.5px solid #e2e8f0;border-radius:10px;background:#fff;cursor:pointer;text-align:center;font-family:inherit;transition:all .12s}}
.day-btn:hover{{border-color:#ea580c}}
.day-btn.on{{border-color:#ea580c;background:#fff5eb;color:#c2410c}}
.day-btn .dn{{font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.4px}}
.day-btn .dd{{font-size:19px;font-weight:700;color:#1e293b;margin-top:2px}}
.day-btn .dm{{font-size:10px;color:#94a3b8;margin-top:1px}}
.day-btn.on .dn,.day-btn.on .dm{{color:#c2410c}}
.day-btn.on .dd{{color:#c2410c}}
.slot-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(82px,1fr));gap:6px;max-height:220px;overflow-y:auto;padding:4px;margin:-4px;border-radius:10px}}
.slot-btn{{padding:9px 2px;border:1.5px solid #e2e8f0;border-radius:8px;background:#fff;cursor:pointer;font-size:13px;font-weight:600;color:#334155;font-family:inherit;transition:all .1s}}
.slot-btn:hover{{border-color:#ea580c}}
.slot-btn.on{{border-color:#ea580c;background:#ea580c;color:#fff}}
.slot-empty{{font-size:13px;color:#94a3b8;text-align:center;padding:40px 0}}
.book-submit{{width:100%;padding:14px;background:#ea580c;color:#fff;border:none;border-radius:10px;font-size:16px;font-weight:700;cursor:pointer;transition:background .15s;margin-top:8px}}
.book-submit:hover{{background:#dc2626}}
.book-submit:disabled{{opacity:.5;cursor:not-allowed}}
.book-msg{{text-align:center;font-size:13px;margin-top:10px;min-height:18px}}
.book-footer{{text-align:center;padding:0 28px 22px;font-size:11px;color:#94a3b8}}
.book-success{{text-align:center;padding:46px 28px}}
.book-success-icon{{font-size:48px;margin-bottom:12px}}
.book-success h3{{font-size:20px;font-weight:700;color:#1e293b;margin-bottom:8px}}
.book-success p{{font-size:14px;color:#64748b;line-height:1.6}}
.book-success p strong{{color:#ea580c}}
</style></head>
<body>
<div class="book-card">
  <div class="book-header">
    <h1>\U0001f4c5 Book an Appointment</h1>
    <h2>{event_name}</h2>
  </div>
  <div id="bk-body" class="book-body">
    <div class="book-section">
      <label class="book-label">Pick a day</label>
      <div class="day-grid" id="day-grid"></div>
    </div>
    <div class="book-section">
      <label class="book-label">Pick a time</label>
      <div id="slot-wrap"><div class="slot-empty">Select a day first.</div></div>
    </div>
    <div class="book-section">
      <label class="book-label">Full name *</label>
      <input type="text" id="bk-name" class="book-input" placeholder="Your full name">
    </div>
    <div class="book-section">
      <label class="book-label">Phone *</label>
      <input type="tel" id="bk-phone" class="book-input" placeholder="(555) 555-5555">
    </div>
    <div class="book-section">
      <label class="book-label">Email</label>
      <input type="email" id="bk-email" class="book-input" placeholder="you@example.com">
    </div>
    <div class="book-section">
      <label class="book-label">What brings you in?</label>
      <textarea id="bk-reason" class="book-input" placeholder="Pain description, how you heard about us, or anything else you'd like us to know"></textarea>
    </div>
    <button class="book-submit" id="bk-submit" onclick="submitBooking()">Request appointment</button>
    <div class="book-msg" id="bk-msg"></div>
  </div>
  <div id="bk-success" class="book-success" style="display:none">
    <div class="book-success-icon">\u2705</div>
    <h3>Your request is in!</h3>
    <p>We\u2019ve received your appointment request for <strong id="bk-when"></strong>.<br>
    A member of our team will confirm shortly by phone or email.</p>
  </div>
  <div class="book-footer">\u00a9 Reform Chiropractic \u2022 (832) 699-3148 \u2022 reformchiropractic.com</div>
</div>
<script>
var SLUG = {slug_js};
var _selDate = '';
var _selTime = '';

function buildDays() {{
  var grid = document.getElementById('day-grid');
  var out = [];
  var d = new Date();
  // Start from tomorrow to avoid same-day confusion; skip weekends
  d.setDate(d.getDate() + 1);
  var count = 0;
  while (count < 8) {{
    var dow = d.getDay();
    if (dow !== 0 && dow !== 6) {{
      var iso = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
      out.push({{iso, d: new Date(d)}});
      count++;
    }}
    d.setDate(d.getDate() + 1);
  }}
  grid.innerHTML = out.map(function(o) {{
    var dn = o.d.toLocaleDateString('en-US', {{weekday:'short'}});
    var dm = o.d.toLocaleDateString('en-US', {{month:'short'}});
    return '<button class="day-btn" data-iso="' + o.iso + '" onclick="pickDay(this)">'
      + '<div class="dn">' + dn + '</div>'
      + '<div class="dd">' + o.d.getDate() + '</div>'
      + '<div class="dm">' + dm + '</div></button>';
  }}).join('');
}}

function pickDay(btn) {{
  document.querySelectorAll('.day-btn').forEach(function(b){{ b.classList.remove('on'); }});
  btn.classList.add('on');
  _selDate = btn.dataset.iso;
  _selTime = '';
  renderSlots();
}}

function renderSlots() {{
  var wrap = document.getElementById('slot-wrap');
  if (!_selDate) {{ wrap.innerHTML = '<div class="slot-empty">Select a day first.</div>'; return; }}
  // 9:00 AM \u2014 5:00 PM, 30-min blocks
  var slots = [];
  for (var h = 9; h < 17; h++) {{
    for (var m = 0; m < 60; m += 30) slots.push({{h, m}});
  }}
  wrap.innerHTML = '<div class="slot-grid">' + slots.map(function(s) {{
    var hh12 = ((s.h + 11) % 12) + 1;
    var ap = s.h < 12 ? 'am' : 'pm';
    var label = hh12 + ':' + String(s.m).padStart(2,'0') + ap;
    var val = String(s.h).padStart(2,'0') + ':' + String(s.m).padStart(2,'0');
    return '<button type="button" class="slot-btn" data-val="' + val + '" onclick="pickSlot(this)">' + label + '</button>';
  }}).join('') + '</div>';
}}

function pickSlot(btn) {{
  document.querySelectorAll('.slot-btn').forEach(function(b){{ b.classList.remove('on'); }});
  btn.classList.add('on');
  _selTime = btn.dataset.val;
}}

async function submitBooking() {{
  var name  = document.getElementById('bk-name').value.trim();
  var phone = document.getElementById('bk-phone').value.trim();
  var email = document.getElementById('bk-email').value.trim();
  var reason = document.getElementById('bk-reason').value.trim();
  var msg = document.getElementById('bk-msg');
  if (!_selDate || !_selTime) {{
    msg.style.color = '#ef4444'; msg.textContent = 'Please pick a day and time.'; return;
  }}
  if (!name || !phone) {{
    msg.style.color = '#ef4444'; msg.textContent = 'Name and phone are required.'; return;
  }}
  var btn = document.getElementById('bk-submit');
  btn.disabled = true; btn.textContent = 'Submitting\u2026';
  msg.textContent = '';
  var appointment = _selDate + 'T' + _selTime + ':00';
  try {{
    var r = await fetch('/api/book', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        name, phone, email, reason, appointment, slug: SLUG,
      }}),
    }});
    var d = await r.json();
    if (d.ok) {{
      var dt = new Date(appointment);
      var whenLabel = dt.toLocaleDateString('en-US', {{weekday:'long', month:'long', day:'numeric'}})
        + ' at ' + dt.toLocaleTimeString('en-US', {{hour:'numeric', minute:'2-digit'}});
      document.getElementById('bk-when').textContent = whenLabel;
      document.getElementById('bk-body').style.display = 'none';
      document.getElementById('bk-success').style.display = 'block';
    }} else {{
      msg.style.color = '#ef4444'; msg.textContent = d.error || 'Something went wrong.';
      btn.disabled = false; btn.textContent = 'Request appointment';
    }}
  }} catch(e) {{
    msg.style.color = '#ef4444'; msg.textContent = 'Network error. Please try again.';
    btn.disabled = false; btn.textContent = 'Request appointment';
  }}
}}

buildDays();
</script>
</body></html>"""
