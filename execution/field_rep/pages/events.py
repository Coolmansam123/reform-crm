"""Field-rep events list + detail.

Read-only for non-admin reps; admins get inline edits for Event Status,
Checked In, and Decision Notes via PATCH /api/events/{id}. The page sources
its data from T_EVENTS — the activities table no longer holds events
after the dual-write split.
"""

from hub.shared import (
    _mobile_page, _is_admin,
    T_GOR_VENUES, T_EVENTS,
)
from hub.guerilla import GFR_EXTRA_HTML, GFR_EXTRA_JS


def _mobile_events_page(br: str, bt: str, user: dict = None) -> str:
    user = user or {}
    user_name = user.get('name', '')
    user_email = (user.get('email', '') or '').strip().lower()
    is_admin = _is_admin(user)

    body = (
        '<div class="mobile-hdr">'
        '<div><div class="mobile-hdr-title">Events</div>'
        '<div class="mobile-hdr-sub">Upcoming &amp; recent events</div></div>'
        '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        '</div>'
        '<div class="mobile-body">'
        # Schedule Event CTA — opens the same GFR chooser the route stop uses
        '<button onclick="openGFRChooser()" '
        'style="width:100%;background:#ea580c;color:#fff;border:none;border-radius:8px;'
        'padding:12px;font-size:15px;font-weight:700;cursor:pointer;min-height:44px;margin-bottom:10px">'
        '+ Schedule Event</button>'
        # Status chip strip
        '<div id="evt-status-chips" style="display:flex;gap:6px;overflow-x:auto;padding-bottom:6px;'
        'margin-bottom:10px;-webkit-overflow-scrolling:touch"></div>'
        # List container
        '<div id="evt-list" style="font-size:13px">'
        '<div style="color:var(--text3);padding:20px;text-align:center">Loading…</div>'
        '</div>'
        '</div>'
        # Detail modal
        '<div id="evt-modal-bg" onclick="if(event.target===this)closeEventModal()" '
        'style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1100;'
        'align-items:flex-start;justify-content:center;padding:30px 14px;overflow-y:auto">'
        '<div style="background:var(--bg2);border:1px solid var(--border);border-radius:14px;'
        'width:100%;max-width:520px;padding:18px 20px calc(20px + env(safe-area-inset-bottom))">'
        '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">'
        '<h3 id="evt-modal-title" style="margin:0;color:var(--text);font-size:16px;flex:1">Event</h3>'
        '<button onclick="closeEventModal()" style="background:none;border:none;color:var(--text3);'
        'font-size:18px;cursor:pointer;padding:4px 8px">×</button>'
        '</div>'
        '<div id="evt-modal-body"></div>'
        '<div id="evt-modal-status" style="text-align:center;margin-top:10px;font-size:13px;min-height:20px"></div>'
        '</div>'
        '</div>'
    )

    js = f"""
const USER_EMAIL = {repr(user_email)};
const IS_ADMIN = {'true' if is_admin else 'false'};
const GFR_USER = {repr(user_name)};
const TOOL = {{ venuesT: {T_GOR_VENUES} }};
const _EVT_STATUSES = ['Prospective','Maybe','Approved','Declined','Scheduled','Completed'];
const _EVT_COLORS = {{
  'Prospective':'#3b82f6','Maybe':'#f59e0b','Approved':'#10b981',
  'Declined':'#ef4444','Scheduled':'#8b5cf6','Completed':'#64748b'
}};

var _events = [];
var _filterStatus = 'All';
var _currentEventId = null;

function esc(s) {{
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}}

function svJS(v) {{
  if (!v) return '';
  if (typeof v === 'object' && !Array.isArray(v)) return v.value || '';
  return String(v);
}}

// ── Status chips ─────────────────────────────────────────────────────
function renderStatusChips() {{
  var box = document.getElementById('evt-status-chips');
  if (!box) return;
  var labels = ['All'].concat(_EVT_STATUSES);
  box.innerHTML = labels.map(function(s) {{
    var active = (s === _filterStatus);
    var color = (s === 'All') ? '#ea580c' : (_EVT_COLORS[s] || '#6b7280');
    var bg = active ? color : 'var(--bg)';
    var fg = active ? '#fff' : 'var(--text2)';
    return '<button onclick="setStatusFilter(\\''+ esc(s) +'\\')" '
         + 'style="flex:0 0 auto;background:'+bg+';color:'+fg+';border:1px solid '+color+';'
         + 'border-radius:14px;padding:5px 12px;font-size:12px;font-weight:600;cursor:pointer;'
         + 'white-space:nowrap;font-family:inherit">'+esc(s)+'</button>';
  }}).join('');
}}

function setStatusFilter(s) {{
  _filterStatus = s;
  renderStatusChips();
  renderEvents();
}}

// ── Render list ──────────────────────────────────────────────────────
function renderEvents() {{
  var box = document.getElementById('evt-list');
  if (!box) return;
  var rows = _events.slice();
  if (_filterStatus !== 'All') {{
    rows = rows.filter(function(e) {{ return svJS(e['Event Status']) === _filterStatus; }});
  }}
  if (!_events.length) {{
    box.innerHTML = '<div style="color:var(--text3);padding:30px 10px;text-align:center">'
                  + '<div style="font-size:14px;margin-bottom:10px">No events yet.</div>'
                  + '<button onclick="openGFRChooser()" style="background:#ea580c;color:#fff;border:none;'
                  + 'border-radius:8px;padding:10px 18px;font-size:13px;font-weight:600;cursor:pointer">'
                  + '+ Schedule your first event</button></div>';
    return;
  }}
  if (!rows.length) {{
    box.innerHTML = '<div style="color:var(--text3);padding:30px 10px;text-align:center">'
                  + '<div style="font-size:14px;margin-bottom:8px">No events match this filter.</div>'
                  + '<a href="javascript:setStatusFilter(\\'All\\')" style="color:#3b82f6;font-size:13px">Show all</a></div>';
    return;
  }}
  box.innerHTML = rows.map(function(e) {{
    var nm = e['Name'] || '(unnamed)';
    var et = svJS(e['Event Type']);
    var es = svJS(e['Event Status']) || 'Prospective';
    var dt = e['Event Date'] || '';
    var leads = e['Lead Count'] || 0;
    var col = _EVT_COLORS[es] || '#6b7280';
    var line2bits = [];
    if (et) line2bits.push(esc(et));
    if (dt) line2bits.push(esc(dt));
    var line2 = line2bits.join(' · ');
    var line3 = leads > 0 ? (leads + ' lead' + (leads > 1 ? 's' : '')) : '';
    return '<div onclick="openEventModal('+e.id+')" '
         + 'style="padding:10px 0;border-bottom:1px solid var(--border);cursor:pointer">'
         + '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px">'
         + '<span style="font-weight:600">'+esc(nm)+'</span>'
         + '<span style="background:'+col+'22;color:'+col+';font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600;white-space:nowrap">'+esc(es)+'</span>'
         + '</div>'
         + (line2 ? '<div style="color:var(--text2);font-size:12px;margin-top:2px">'+line2+'</div>' : '')
         + (line3 ? '<div style="color:var(--text3);font-size:11px;margin-top:2px">'+line3+'</div>' : '')
         + '</div>';
  }}).join('');
}}

// ── Detail modal ─────────────────────────────────────────────────────
function openEventModal(id) {{
  var ev = _events.find(function(e){{return e.id === id;}});
  if (!ev) return;
  _currentEventId = id;
  var title = ev['Name'] || '(unnamed)';
  document.getElementById('evt-modal-title').textContent = title;
  var body = document.getElementById('evt-modal-body');
  var et = svJS(ev['Event Type']);
  var es = svJS(ev['Event Status']) || 'Prospective';
  var dt = ev['Event Date'] || '';
  var org = ev['Organizer'] || '';
  var oph = ev['Organizer Phone'] || '';
  var addr = ev['Venue Address'] || '';
  var ant = ev['Anticipated Count'] || '';
  var leads = ev['Lead Count'] || 0;
  var notes = ev['Notes'] || '';
  var dec = ev['Decision Notes'] || '';
  var checkedIn = !!ev['Checked In'];
  var slug = ev['Form Slug'] || '';

  var html = '';
  function row(label, val) {{
    if (!val) return '';
    return '<div style="margin-bottom:10px">'
         + '<div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:2px">'+esc(label)+'</div>'
         + '<div style="font-size:14px;color:var(--text)">'+esc(val)+'</div></div>';
  }}
  html += row('Type', et);
  html += row('Date', dt);
  html += row('Organizer', org + (oph ? ' · ' + oph : ''));
  html += row('Venue Address', addr);
  if (ant) html += row('Anticipated Count', ant);
  html += row('Lead Count', String(leads));
  if (notes) html += row('Notes', notes);

  if (IS_ADMIN) {{
    // Editable fields for admins
    html += '<hr style="border:none;border-top:1px solid var(--border);margin:12px 0">';
    html += '<div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:6px">Admin actions</div>';
    // Event Status select
    html += '<div style="margin-bottom:10px">'
         + '<label style="font-size:11px;font-weight:600;color:var(--text3);display:block;margin-bottom:4px">Event Status</label>'
         + '<select id="evt-edit-status" style="width:100%;background:var(--input-bg);border:1px solid var(--border);'
         + 'color:var(--text);border-radius:8px;padding:9px 12px;font-size:14px">';
    _EVT_STATUSES.forEach(function(s) {{
      html += '<option value="'+esc(s)+'"'+(s===es?' selected':'')+'>'+esc(s)+'</option>';
    }});
    html += '</select></div>';
    // Checked In checkbox
    html += '<div style="margin-bottom:10px;display:flex;align-items:center;gap:8px">'
         + '<input type="checkbox" id="evt-edit-checkedin"'+(checkedIn?' checked':'')+' '
         + 'style="width:18px;height:18px;accent-color:#ea580c">'
         + '<label for="evt-edit-checkedin" style="font-size:14px;color:var(--text);cursor:pointer">Checked In</label>'
         + '</div>';
    // Decision Notes
    html += '<div style="margin-bottom:10px">'
         + '<label style="font-size:11px;font-weight:600;color:var(--text3);display:block;margin-bottom:4px">Decision Notes</label>'
         + '<textarea id="evt-edit-decision" rows="3" '
         + 'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
         + 'border-radius:8px;padding:9px 12px;font-size:14px;box-sizing:border-box;font-family:inherit;resize:vertical">'
         + esc(dec) + '</textarea></div>';
    // Save button
    html += '<button onclick="saveEvent()" '
         + 'style="width:100%;background:#059669;color:#fff;border:none;border-radius:8px;'
         + 'padding:11px;font-size:14px;font-weight:700;cursor:pointer;min-height:42px">'
         + 'Save changes</button>';
  }}

  if (slug) {{
    html += '<hr style="border:none;border-top:1px solid var(--border);margin:12px 0">';
    html += '<div style="font-size:11px;color:var(--text3)">Public lead-capture form: <code style="color:var(--text2)">/lead-form/'+esc(slug)+'</code></div>';
  }}

  body.innerHTML = html;
  document.getElementById('evt-modal-status').textContent = '';
  var bg = document.getElementById('evt-modal-bg');
  bg.style.display = 'flex';
}}

function closeEventModal() {{
  document.getElementById('evt-modal-bg').style.display = 'none';
  _currentEventId = null;
  // Drop the deep-link hash so reopening doesn't auto-pop the same event
  if (window.location.hash) history.replaceState(null, '', window.location.pathname);
}}

async function saveEvent() {{
  if (!_currentEventId || !IS_ADMIN) return;
  var st = document.getElementById('evt-modal-status');
  st.style.color = 'var(--text3)';
  st.textContent = 'Saving…';
  var payload = {{
    'Event Status': document.getElementById('evt-edit-status').value,
    'Checked In': document.getElementById('evt-edit-checkedin').checked,
    'Decision Notes': document.getElementById('evt-edit-decision').value
  }};
  try {{
    var r = await fetch('/api/events/' + _currentEventId, {{
      method: 'PATCH',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(payload)
    }});
    if (r.ok) {{
      st.style.color = '#059669';
      st.textContent = 'Saved ✓';
      await loadEvents();
      setTimeout(closeEventModal, 600);
    }} else {{
      var err = await r.json().catch(function(){{return{{}};}});
      st.style.color = '#ef4444';
      st.textContent = 'Error: ' + (err.error || r.status);
    }}
  }} catch (e) {{
    st.style.color = '#ef4444';
    st.textContent = 'Network error';
  }}
}}

// ── Data load ────────────────────────────────────────────────────────
async function loadEvents() {{
  try {{
    var rows = await fetchAll({T_EVENTS});
    // Sort: future-dated first (ascending), then past (descending). Within
    // same-date, group by status (active before completed).
    var today = new Date().toISOString().slice(0, 10);
    rows.sort(function(a, b) {{
      var da = a['Event Date'] || '';
      var db = b['Event Date'] || '';
      var afut = da >= today, bfut = db >= today;
      if (afut !== bfut) return afut ? -1 : 1;
      return afut ? da.localeCompare(db) : db.localeCompare(da);
    }});
    _events = rows;
    renderEvents();
    // If URL has a hash like #123, deep-link into that event detail.
    var hash = (window.location.hash || '').replace(/^#/, '');
    var deepId = parseInt(hash, 10);
    if (deepId && _events.some(function(e){{return e.id === deepId;}})) {{
      openEventModal(deepId);
    }}
  }} catch (e) {{
    var box = document.getElementById('evt-list');
    if (box) {{
      box.innerHTML = '<div style="color:#ef4444;padding:20px;text-align:center">'
                    + 'Failed to load events. '
                    + '<button onclick="loadEvents()" style="margin-left:8px;background:none;color:#3b82f6;'
                    + 'border:1px solid var(--border);border-radius:6px;padding:4px 10px;cursor:pointer">Retry</button></div>';
    }}
  }}
}}

// After a GFR submit, refresh the events list. _gfrSuccess fires this hook.
window._afterCompanyDataChange = loadEvents;

// ── Init ─────────────────────────────────────────────────────────────
renderStatusChips();
loadEvents();
"""
    return _mobile_page('m_events', 'Events', body, js, br, bt, user=user,
                         extra_html=GFR_EXTRA_HTML, extra_js=GFR_EXTRA_JS)
