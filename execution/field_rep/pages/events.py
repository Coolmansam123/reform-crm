"""Field-rep events list + detail.

Read-only for non-admin reps; admins get inline edits for Event Status,
Checked In, and Decision Notes via PATCH /api/events/{id}. The page sources
its data from T_EVENTS — the activities table no longer holds events
after the dual-write split.
"""

from hub.shared import (
    _mobile_page, _is_admin,
    T_GOR_VENUES, T_EVENTS, T_LEADS, T_STAFF,
    LEAD_MODAL_HTML, LEAD_MODAL_JS,
)
from hub.guerilla import GFR_EXTRA_HTML, GFR_EXTRA_JS


def _mobile_events_page(br: str, bt: str, user: dict = None, archive: bool = False) -> str:
    user = user or {}
    user_name = user.get('name', '')
    user_email = (user.get('email', '') or '').strip().lower()
    is_admin = _is_admin(user)

    title = 'Archived Events' if archive else 'Events'
    subtitle = 'Past &amp; closed events' if archive else 'Upcoming &amp; recent events'
    toggle_link = (
        '<a href="/events" style="color:var(--primary);font-size:12px;font-weight:600;text-decoration:none">&larr; Back to active</a>'
        if archive else
        '<a href="/events/archive" style="color:var(--primary);font-size:12px;font-weight:600;text-decoration:none">View archive &rarr;</a>'
    )

    # Week-strip + Next-Up hero are active-page-only; FAB lives there too.
    week_strip_slot = '' if archive else '<div id="evt-week-strip" style="margin-bottom:16px"></div>'
    next_up_slot    = '' if archive else '<div id="evt-next-up" style="margin-bottom:16px"></div>'
    fab_html = (
        '' if archive else
        '<button class="fab" onclick="openGFRChooser()" aria-label="Schedule event">'
        '<span class="material-symbols-outlined">add</span></button>'
    )
    list_section_label = 'Past events' if archive else 'Upcoming events'

    modal_html = (
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

    body = (
        '<div class="mobile-hdr">'
        + f'<div><div class="mobile-hdr-title">{title}</div>'
        + f'<div class="mobile-hdr-sub">{subtitle}</div></div>'
        + '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        + '</div>'
        + '<div class="mobile-body">'
        + f'<div style="margin-bottom:14px">{toggle_link}</div>'
        + week_strip_slot
        + next_up_slot
        + '<div class="label-caps" style="margin-bottom:6px">Filter by status</div>'
        + '<div id="evt-status-chips" class="chip-strip" style="margin-bottom:16px"></div>'
        + f'<div id="evt-list-label" class="label-caps" style="margin-bottom:8px">{list_section_label}</div>'
        + '<div id="evt-list" style="display:flex;flex-direction:column;gap:10px">'
        + '<div style="color:var(--text3);padding:20px;text-align:center">Loading…</div>'
        + '</div>'
        + '</div>'
        + fab_html
        + modal_html
        + LEAD_MODAL_HTML
    )

    js = f"""
const USER_EMAIL = {repr(user_email)};
const IS_ADMIN = {'true' if is_admin else 'false'};
const IS_ARCHIVE = {'true' if archive else 'false'};
const GFR_USER = {repr(user_name)};
const TOOL = {{ venuesT: {T_GOR_VENUES}, leadsT: {T_LEADS}, staffT: {T_STAFF} }};
const _EQUIPMENT_FIELDS = [
  ['Massage Chair Needed', 'Massage chair'],
  ['Massage Table Needed', 'Massage table'],
  ['Table Needed',         'Folding table'],
  ['EZ Up Needed',         'EZ Up tent'],
  ['Banner Needed',        'Banner'],
  ['Flyers Needed',        'Flyers'],
  ['Intake Forms Needed',  'Intake forms'],
  ['Tablet Needed',        'Tablet'],
  ['Power Strip Needed',   'Power strip'],
  ['Generator Needed',     'Generator'],
];
var _STAFF_CACHE = null;
const _EVT_STATUSES = ['Prospective','Maybe','Approved','Declined','Scheduled','Completed'];
const _ACTIVE_STATUSES = ['Prospective','Maybe','Approved','Scheduled'];

function _isActiveEvent(e) {{
  var d = e['Event Date'] || '';
  var st = (e['Event Status'] && e['Event Status'].value) || e['Event Status'] || '';
  var today = new Date().toISOString().slice(0, 10);
  var futureOrToday = !d || d >= today;
  var activeStatus = !st || _ACTIVE_STATUSES.indexOf(st) >= 0;
  return futureOrToday && activeStatus;
}}
const _EVT_COLORS = {{
  'Prospective':'#3b82f6','Maybe':'#f59e0b','Approved':'#10b981',
  'Declined':'#ef4444','Scheduled':'#8b5cf6','Completed':'#64748b'
}};

var _events = [];
var _filterStatus = 'All';
var _filterDate = null;     // ISO YYYY-MM-DD when a day chip is selected
var _currentEventId = null;
var _weekAnchor = null;     // Monday of the visible week (Date object)

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

// ── Date helpers ─────────────────────────────────────────────────────
function _dateKey(d) {{
  // Local-time YYYY-MM-DD; avoids the UTC drift you get from toISOString()
  // when the user's tz is west of UTC and it's late at night.
  var y = d.getFullYear(), m = d.getMonth() + 1, day = d.getDate();
  return y + '-' + (m < 10 ? '0' : '') + m + '-' + (day < 10 ? '0' : '') + day;
}}
function _todayKey() {{ return _dateKey(new Date()); }}
function _addDays(d, n) {{ var x = new Date(d); x.setDate(x.getDate() + n); return x; }}
function _startOfWeek(d) {{
  // Sunday-anchored week to match the design system mockup (SUN..SAT).
  var x = new Date(d); x.setHours(0,0,0,0); x.setDate(x.getDate() - x.getDay());
  return x;
}}
const _DOWS = ['SUN','MON','TUE','WED','THU','FRI','SAT'];
const _MONTHS = ['January','February','March','April','May','June',
                 'July','August','September','October','November','December'];

// ── Status pill class mapping (uses .pill primitives in styles.py) ───
function _pillClass(status) {{
  switch (status) {{
    case 'Maybe':       return 'pill pill-warning';
    case 'Approved':    return 'pill pill-routine';
    case 'Scheduled':   return 'pill pill-success';
    case 'Completed':   return 'pill pill-success';
    case 'Declined':    return 'pill pill-overdue';
    default:            return 'pill';  // Prospective + unknown
  }}
}}

function _eventsOnDate(dKey) {{
  return _events.filter(function(e) {{ return (e['Event Date'] || '') === dKey; }});
}}

// ── Week strip ───────────────────────────────────────────────────────
function renderWeekStrip() {{
  var box = document.getElementById('evt-week-strip');
  if (!box) return;
  if (!_weekAnchor) _weekAnchor = _startOfWeek(new Date());
  var today = _todayKey();
  var monthLbl = _MONTHS[_weekAnchor.getMonth()] + ' ' + _weekAnchor.getFullYear();
  // 7-day grid + month header + prev/next chevrons
  var html = '<div class="card" style="padding:12px 14px">';
  html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">';
  html += '<div><div class="headline-sm">' + esc(monthLbl) + '</div>';
  html += '<div class="label-caps" style="margin-top:2px">TODAY IS ' + esc(_DOWS[new Date().getDay()]) + ', ' + esc(_MONTHS[new Date().getMonth()].toUpperCase()) + ' ' + new Date().getDate() + '</div></div>';
  html += '<div style="display:flex;gap:4px">';
  html += '<button onclick="weekShift(-7)" aria-label="Previous week" style="width:30px;height:30px;border:1px solid var(--border);background:var(--card);color:var(--text);border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center"><span class="material-symbols-outlined" style="font-size:18px">chevron_left</span></button>';
  html += '<button onclick="weekShift(7)" aria-label="Next week" style="width:30px;height:30px;border:1px solid var(--border);background:var(--card);color:var(--text);border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center"><span class="material-symbols-outlined" style="font-size:18px">chevron_right</span></button>';
  html += '</div></div>';
  html += '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px">';
  for (var i = 0; i < 7; i++) {{
    var day = _addDays(_weekAnchor, i);
    var key = _dateKey(day);
    var isToday = (key === today);
    var isSelected = (_filterDate === key);
    var hasEvents = _eventsOnDate(key).length > 0;
    var bg, fg, border;
    if (isSelected) {{ bg = 'var(--primary)'; fg = '#fff'; border = 'var(--primary)'; }}
    else if (isToday) {{ bg = 'var(--primary-tint)'; fg = 'var(--primary)'; border = 'var(--primary-tint)'; }}
    else {{ bg = 'transparent'; fg = 'var(--text)'; border = 'transparent'; }}
    html += '<button onclick="setDateFilter(\\''+ key +'\\')" '
         + 'style="display:flex;flex-direction:column;align-items:center;gap:2px;'
         + 'padding:8px 4px;background:'+bg+';border:1px solid '+border+';border-radius:8px;'
         + 'color:'+fg+';cursor:pointer;font-family:inherit">'
         + '<span style="font-size:10px;font-weight:600;letter-spacing:.04em;opacity:.7">'+_DOWS[i]+'</span>'
         + '<span style="font-size:16px;font-weight:700">'+day.getDate()+'</span>'
         + (hasEvents ? '<span style="width:4px;height:4px;border-radius:50%;background:'+(isSelected?'#fff':'var(--primary)')+';margin-top:2px"></span>' : '<span style="height:6px"></span>')
         + '</button>';
  }}
  html += '</div>';
  if (_filterDate) {{
    html += '<div style="margin-top:10px;text-align:center"><a href="#" onclick="setDateFilter(null);return false" style="font-size:12px;color:var(--primary);font-weight:600;text-decoration:none">Show all dates</a></div>';
  }}
  html += '</div>';
  box.innerHTML = html;
}}
function weekShift(days) {{
  if (!_weekAnchor) _weekAnchor = _startOfWeek(new Date());
  _weekAnchor = _addDays(_weekAnchor, days);
  renderWeekStrip();
}}
function setDateFilter(key) {{
  _filterDate = key;
  if (key) {{
    var d = new Date(key + 'T00:00:00');
    _weekAnchor = _startOfWeek(d);
  }}
  renderWeekStrip();
  renderEvents();
}}

// ── Featured "Next Up" hero card ─────────────────────────────────────
function renderNextUp() {{
  var box = document.getElementById('evt-next-up');
  if (!box) return;
  var today = _todayKey();
  var upcoming = _events
    .filter(function(e) {{ return (e['Event Date'] || '') >= today; }})
    .sort(function(a, b) {{ return (a['Event Date']||'').localeCompare(b['Event Date']||''); }});
  var ev = upcoming[0];
  if (!ev) {{ box.innerHTML = ''; return; }}
  var nm = ev['Name'] || '(unnamed)';
  var dt = ev['Event Date'] || '';
  var et = svJS(ev['Event Type']);
  var addr = ev['Venue Address'] || '';
  var sub = [];
  if (et) sub.push(esc(et));
  if (dt) sub.push(esc(dt));
  var subLine = sub.join(' · ');
  var html = '<div class="card card-featured" onclick="openEventModal('+ev.id+')" style="cursor:pointer;padding:18px 20px">';
  html += '<div class="label-caps" style="margin-bottom:8px">Next Up</div>';
  html += '<div style="font-size:18px;font-weight:700;margin-bottom:6px;line-height:1.3">' + esc(nm) + '</div>';
  if (subLine) html += '<div style="font-size:13px;opacity:.85;margin-bottom:8px">' + subLine + '</div>';
  if (addr) html += '<div style="font-size:12px;opacity:.75;display:flex;align-items:center;gap:4px"><span class="material-symbols-outlined" style="font-size:14px">location_on</span>' + esc(addr) + '</div>';
  html += '</div>';
  box.innerHTML = html;
}}

// ── Status chips (uses .chip-strip / .chip primitives in styles.py) ──
function renderStatusChips() {{
  var box = document.getElementById('evt-status-chips');
  if (!box) return;
  var labels = ['All'].concat(_EVT_STATUSES);
  box.innerHTML = labels.map(function(s) {{
    var active = (s === _filterStatus);
    return '<button class="chip' + (active ? ' active' : '') + '" '
         + 'onclick="setStatusFilter(\\''+ esc(s) +'\\')">'+esc(s)+'</button>';
  }}).join('');
}}

function setStatusFilter(s) {{
  _filterStatus = s;
  renderStatusChips();
  renderEvents();
}}

// ── Render list (cards with day-badge + status pill, image-hero variant) ──
function renderEvents() {{
  var box = document.getElementById('evt-list');
  var label = document.getElementById('evt-list-label');
  if (!box) return;
  var rows = _events.slice();
  if (_filterStatus !== 'All') {{
    rows = rows.filter(function(e) {{ return svJS(e['Event Status']) === _filterStatus; }});
  }}
  if (_filterDate) {{
    rows = rows.filter(function(e) {{ return (e['Event Date'] || '') === _filterDate; }});
  }}
  // Section label updates with filter context + count
  if (label) {{
    var base = IS_ARCHIVE ? 'Past events' : 'Upcoming events';
    if (_filterDate) {{
      var d0 = new Date(_filterDate + 'T00:00:00');
      base = _DOWS[d0.getDay()] + ', ' + _MONTHS[d0.getMonth()] + ' ' + d0.getDate();
    }}
    label.innerHTML = esc(base)
      + ' <span style="color:var(--text4);font-weight:600">· '
      + rows.length + ' ' + (rows.length === 1 ? 'event' : 'events') + '</span>';
  }}
  if (!_events.length) {{
    var emptyCta = IS_ARCHIVE
      ? ''
      : '<button onclick="openGFRChooser()" style="background:var(--primary);color:#fff;border:none;border-radius:8px;padding:10px 18px;font-size:13px;font-weight:600;cursor:pointer">+ Schedule your first event</button>';
    box.innerHTML = '<div style="color:var(--text3);padding:30px 10px;text-align:center">'
                  + '<div style="font-size:14px;margin-bottom:10px">No events yet.</div>'
                  + emptyCta + '</div>';
    return;
  }}
  if (!rows.length) {{
    box.innerHTML = '<div style="color:var(--text3);padding:30px 10px;text-align:center">'
                  + '<div style="font-size:14px;margin-bottom:8px">No events match.</div>'
                  + '<a href="#" onclick="setStatusFilter(\\'All\\');setDateFilter(null);return false" '
                  + 'style="color:var(--primary);font-size:13px;font-weight:600;text-decoration:none">Show all</a></div>';
    return;
  }}
  var today = _todayKey();
  box.innerHTML = rows.map(function(e) {{
    var nm = e['Name'] || '(unnamed)';
    var et = svJS(e['Event Type']);
    var es = svJS(e['Event Status']) || 'Prospective';
    var dt = e['Event Date'] || '';
    var addr = e['Venue Address'] || '';
    var leads = e['Lead Count'] || 0;
    var flyer = (e['Flyer URL'] || '').trim();
    var biz = Array.isArray(e['Business'])
      ? e['Business'].map(function(b) {{ return b && (b.value || b.name); }}).filter(Boolean).join(', ')
      : '';
    var isToday = (dt && dt === today);
    var cardCls = 'card' + (isToday ? ' card-active' : '');
    var pillCls = _pillClass(es);
    // Day badge — TODAY pill if happening today, else DOW + DOM
    var dayBadge = '';
    if (isToday) {{
      dayBadge = '<div class="day-badge" style="background:var(--primary);border-color:var(--primary);color:#fff;min-width:64px">'
               + '<div class="dow" style="color:rgba(255,255,255,.85)">TODAY</div></div>';
    }} else if (dt) {{
      var d1 = new Date(dt + 'T00:00:00');
      dayBadge = '<div class="day-badge"><div class="dow">' + _DOWS[d1.getDay()] + '</div>'
               + '<div class="dom">' + d1.getDate() + '</div></div>';
    }}
    var metaBits = [];
    if (et) metaBits.push(esc(et));
    if (biz) metaBits.push(esc(biz));
    else if (addr) metaBits.push(esc(addr));
    var metaLine = metaBits.join(' · ');
    var leadsLine = leads > 0
      ? '<span style="display:inline-flex;align-items:center;gap:4px"><span class="material-symbols-outlined" style="font-size:14px">group</span>' + leads + ' lead' + (leads > 1 ? 's' : '') + '</span>'
      : '';
    var flyerHtml = flyer
      ? '<img src="' + esc(flyer) + '" alt="" style="width:100%;height:120px;object-fit:cover;border-radius:6px;margin-bottom:10px;background:var(--bg);display:block">'
      : '';
    return '<div class="' + cardCls + '" onclick="openEventModal(' + e.id + ')" style="cursor:pointer">'
         + flyerHtml
         + '<div style="display:flex;gap:12px;align-items:flex-start">'
         + dayBadge
         + '<div style="flex:1;min-width:0">'
         + '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:4px">'
         + '<div style="font-size:14px;font-weight:600;color:var(--text);line-height:1.3;min-width:0">' + esc(nm) + '</div>'
         + '<span class="' + pillCls + '">' + esc(es) + '</span>'
         + '</div>'
         + (metaLine ? '<div style="font-size:12px;color:var(--text3);margin-top:4px">' + metaLine + '</div>' : '')
         + (leadsLine ? '<div style="font-size:12px;color:var(--text3);margin-top:8px">' + leadsLine + '</div>' : '')
         + '</div></div></div>';
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
  var biz = Array.isArray(ev['Business'])
    ? ev['Business'].map(function(b) {{ return b && (b.value || b.name); }}).filter(Boolean).join(', ')
    : '';

  var html = '';
  function row(label, val) {{
    if (!val) return '';
    return '<div style="margin-bottom:10px">'
         + '<div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:2px">'+esc(label)+'</div>'
         + '<div style="font-size:14px;color:var(--text)">'+esc(val)+'</div></div>';
  }}
  html += row('Type', et);
  html += row('Date', dt);
  html += row('Business', biz);
  html += row('Organizer', org + (oph ? ' · ' + oph : ''));
  html += row('Venue Address', addr);
  if (ant) html += row('Anticipated Count', ant);
  html += row('Lead Count', String(leads));
  if (notes) html += row('Notes', notes);
  var staffStr = (ev['Staff Attending'] || '').trim();
  if (staffStr) html += row('Staff attending', staffStr);
  // Equipment summary (read-only) — only show items that are checked
  var eqOn = _EQUIPMENT_FIELDS.filter(function(p) {{ return !!ev[p[0]]; }}).map(function(p) {{ return p[1]; }});
  if (eqOn.length) html += row('Equipment', eqOn.join(', '));
  // Leads-from-this-event section (loaded async after open)
  html += '<div id="evt-leads-section" style="margin-top:6px"></div>';

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
         + 'style="width:18px;height:18px;accent-color:#004ac6">'
         + '<label for="evt-edit-checkedin" style="font-size:14px;color:var(--text);cursor:pointer">Checked In</label>'
         + '</div>';
    // Decision Notes
    html += '<div style="margin-bottom:10px">'
         + '<label style="font-size:11px;font-weight:600;color:var(--text3);display:block;margin-bottom:4px">Decision Notes</label>'
         + '<textarea id="evt-edit-decision" rows="3" '
         + 'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
         + 'border-radius:8px;padding:9px 12px;font-size:14px;box-sizing:border-box;font-family:inherit;resize:vertical">'
         + esc(dec) + '</textarea></div>';
    // Equipment checklist (booleans)
    html += '<div style="margin-bottom:10px">'
         + '<label style="font-size:11px;font-weight:600;color:var(--text3);display:block;margin-bottom:6px">Equipment to bring</label>'
         + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px 12px">';
    _EQUIPMENT_FIELDS.forEach(function(pair) {{
      var fld = pair[0], lbl = pair[1];
      var checked = !!ev[fld];
      var dom = 'evt-eq-' + fld.replace(/\\W+/g, '-');
      html += '<label style="display:flex;align-items:center;gap:6px;font-size:13px;color:var(--text);cursor:pointer">'
           + '<input type="checkbox" data-evt-eq="'+esc(fld)+'" id="'+dom+'"'
           + (checked ? ' checked' : '')
           + ' style="width:16px;height:16px;accent-color:#004ac6">'
           + esc(lbl) + '</label>';
    }});
    html += '</div></div>';
    // Staff Attending — checkbox list of T_STAFF (loaded async; placeholder
    // below). Stored as comma-joined emails on the event's Staff Attending
    // field (long_text — see add_event_staff_attending.py for why it's not
    // a link_row).
    html += '<div style="margin-bottom:10px">'
         + '<label style="font-size:11px;font-weight:600;color:var(--text3);display:block;margin-bottom:4px">Staff attending</label>'
         + '<div id="evt-edit-staff" style="background:var(--input-bg);border:1px solid var(--border);'
         + 'border-radius:8px;padding:8px 10px;font-size:13px;color:var(--text3);max-height:180px;overflow-y:auto">'
         + 'Loading staff…</div></div>';
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
  loadEventLeads(id);
  if (IS_ADMIN) loadStaffPicker(ev['Staff Attending'] || '');
}}

async function loadStaffPicker(currentVal) {{
  var box = document.getElementById('evt-edit-staff');
  if (!box) return;
  var selected = new Set(
    String(currentVal || '').split(',').map(function(s) {{ return s.trim().toLowerCase(); }}).filter(Boolean)
  );
  try {{
    if (!_STAFF_CACHE) {{
      _STAFF_CACHE = await fetchAll(TOOL.staffT);
    }}
    var staff = (_STAFF_CACHE || []).filter(function(s) {{
      // Treat missing Active as active so we don't accidentally hide everyone.
      return s.Active !== false && (s.Email || s.Name);
    }});
    staff.sort(function(a, b) {{ return (a.Name || a.Email || '').localeCompare(b.Name || b.Email || ''); }});
    if (!staff.length) {{
      box.innerHTML = '<div style="color:var(--text3);font-size:12px">No staff records found.</div>';
      return;
    }}
    var html = '';
    staff.forEach(function(s) {{
      var em = (s.Email || '').trim();
      if (!em) return;
      var nm = s.Name || em;
      var checked = selected.has(em.toLowerCase());
      var dom = 'evt-st-' + em.replace(/\\W+/g, '-');
      html += '<label style="display:flex;align-items:center;gap:6px;padding:3px 0;font-size:13px;color:var(--text);cursor:pointer">'
           + '<input type="checkbox" data-evt-staff="'+esc(em)+'" id="'+dom+'"'
           + (checked ? ' checked' : '')
           + ' style="width:15px;height:15px;accent-color:#004ac6">'
           + esc(nm) + '</label>';
    }});
    box.innerHTML = html || '<div style="color:var(--text3);font-size:12px">No staff with email addresses.</div>';
  }} catch (e) {{
    box.innerHTML = '<div style="color:#ef4444;font-size:12px">Failed to load staff.</div>';
  }}
}}

async function loadEventLeads(eventId) {{
  var box = document.getElementById('evt-leads-section');
  if (!box) return;
  box.innerHTML = '<div style="font-size:11px;color:var(--text3);padding:6px 0">Loading leads…</div>';
  try {{
    var rows = await fetchAll(TOOL.leadsT);
    var matches = rows.filter(function(L) {{
      var ev = L['Event'];
      if (!Array.isArray(ev)) return false;
      return ev.some(function(e) {{ return e && e.id === eventId; }});
    }});
    if (!matches.length) {{
      box.innerHTML = '<div style="font-size:11px;color:var(--text3);padding:6px 0;border-top:1px solid var(--border);margin-top:6px">No leads from this event yet.</div>';
      return;
    }}
    matches.sort(function(a, b) {{ return (b.Created||'').localeCompare(a.Created||''); }});
    var out = '<div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin:10px 0 4px">Leads from this event</div>';
    matches.forEach(function(L) {{
      var st = (L.Status && L.Status.value) || L.Status || '';
      var nm = L.Name || '(no name)';
      var ph = L.Phone || '';
      out += '<div onclick="openLeadModal(' + L.id + ')" '
          + 'style="padding:6px 0;border-top:1px solid var(--border);cursor:pointer;display:flex;justify-content:space-between;gap:8px;align-items:center">'
          + '<div style="flex:1;min-width:0">'
          + '<div style="font-size:13px;font-weight:600;color:var(--text)">'+esc(nm)+'</div>'
          + (ph ? '<div style="font-size:11px;color:var(--text3)">'+esc(ph)+'</div>' : '')
          + '</div>'
          + (st ? '<span style="font-size:10px;color:var(--text2);background:var(--bg);border:1px solid var(--border);border-radius:4px;padding:2px 6px;white-space:nowrap">'+esc(st)+'</span>' : '')
          + '</div>';
    }});
    box.innerHTML = out;
  }} catch (e) {{
    box.innerHTML = '<div style="font-size:11px;color:#ef4444;padding:6px 0">Failed to load leads.</div>';
  }}
}}

// When a lead is edited via the shared lead modal, refresh the events list
// (Lead Count may have changed) and the leads-from-this-event section if the
// event modal is still open behind it.
window._afterLeadSave = function() {{
  loadEvents();
  if (_currentEventId) loadEventLeads(_currentEventId);
}};

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
  // Equipment booleans
  document.querySelectorAll('[data-evt-eq]').forEach(function(el) {{
    payload[el.getAttribute('data-evt-eq')] = el.checked;
  }});
  // Staff Attending — collect ticked emails into a comma-joined string
  var staffEmails = [];
  document.querySelectorAll('[data-evt-staff]').forEach(function(el) {{
    if (el.checked) staffEmails.push(el.getAttribute('data-evt-staff'));
  }});
  payload['Staff Attending'] = staffEmails.join(', ');
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
    // Active page shows only active+future events. Archive shows the rest
    // (past-dated OR Completed/Declined). Same predicate as the lead-capture
    // event picker so reps see one consistent definition of "active."
    rows = rows.filter(function(e) {{
      return IS_ARCHIVE ? !_isActiveEvent(e) : _isActiveEvent(e);
    }});
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
    if (!IS_ARCHIVE) {{ renderWeekStrip(); renderNextUp(); }}
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
if (!IS_ARCHIVE) {{ renderWeekStrip(); }}
renderStatusChips();
loadEvents();
"""
    return _mobile_page('m_events', 'Events', body, js + LEAD_MODAL_JS,
                         br, bt, user=user,
                         extra_html=GFR_EXTRA_HTML, extra_js=GFR_EXTRA_JS)
