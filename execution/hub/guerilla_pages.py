"""
Guerilla Marketing -- Desktop sub-pages (log, events, businesses, boxes, routes).
"""
import os

from .shared import (
    _page, _is_admin,
    T_GOR_VENUES, T_GOR_ACTS, T_GOR_BOXES, T_GOR_ROUTES, T_GOR_ROUTE_STOPS,
    T_EVENTS,
)
from .guerilla import (
    _GFR_CSS, _GFR_HTML, _GFR_FORMS345_HTML, _GFR_FORM2_HTML,
    _GFR_JS, _GFR_FORMS345_JS,
    GFR_EXTRA_HTML, GFR_EXTRA_JS,
)
from .contact_detail import contact_actions_js, contact_detail_html, contact_detail_js


# ===========================================================================
# Gorilla Log Page
# ===========================================================================
def _gorilla_log_page(br: str, bt: str, user: dict = None) -> str:
    _uname = (user or {}).get('name', '')
    header = (
        '<div class="header">'
        '<div class="header-left"><h1>Log Field Activity</h1>'
        '<div class="sub">Guerilla Marketing -- field reports &amp; event intake</div>'
        '</div></div>'
    )
    # Chooser cards inline (no modal wrapper needed -- already on own page)
    body = (
        _GFR_CSS
        + '<div style="max-width:680px;margin:0 auto;padding:8px 0">'
        + '<div class="gfr-chooser-body" style="padding:0">'
        + '<div class="gfr-grid">'
        + '<div class="gfr-card" onclick="openGFRForm(\'Business Outreach Log\')">'
        + '<div class="gfr-card-icon">&#x1f3e2;</div>'
        + '<div class="gfr-card-name">Business Outreach Log</div>'
        + '<div class="gfr-card-desc">Door-to-door visit, massage box placement, and program interest</div>'
        + '<div class="gfr-card-cta">Open &#x2192;</div></div>'
        + '<div class="gfr-card" onclick="openGFRForm(\'External Event\')">'
        + '<div class="gfr-card-icon">&#x1f3aa;</div>'
        + '<div class="gfr-card-name">External Event</div>'
        + '<div class="gfr-card-desc">Pre-event planning and community event demographic intel</div>'
        + '<div class="gfr-card-cta">Open &#x2192;</div></div>'
        + '<div class="gfr-card" onclick="openGFRForm(\'Mobile Massage Service\')">'
        + '<div class="gfr-card-icon">&#x1f486;</div>'
        + '<div class="gfr-card-name">Mobile Massage Service</div>'
        + '<div class="gfr-card-desc">Book a mobile chair or table massage at a company or event</div>'
        + '<div class="gfr-card-cta">Open &#x2192;</div></div>'
        + '<div class="gfr-card" onclick="openGFRForm(\'Lunch and Learn\')">'
        + '<div class="gfr-card-icon">&#x1f37d;&#xfe0f;</div>'
        + '<div class="gfr-card-name">Lunch and Learn</div>'
        + '<div class="gfr-card-desc">Schedule a chiropractic L&amp;L presentation for company staff</div>'
        + '<div class="gfr-card-cta">Open &#x2192;</div></div>'
        + '<div class="gfr-card" onclick="openGFRForm(\'Health Assessment Screening\')">'
        + '<div class="gfr-card-icon">&#x1fa7a;</div>'
        + '<div class="gfr-card-name">Health Assessment Screening</div>'
        + '<div class="gfr-card-desc">Book a chiropractic health screening event for staff</div>'
        + '<div class="gfr-card-cta">Open &#x2192;</div></div>'
        + '</div></div></div>'
        + _GFR_HTML
        + _GFR_FORMS345_HTML
        + _GFR_FORM2_HTML
    )
    js = f"const GFR_USER = {repr(_uname)};\nconst TOOL = {{venuesT: {T_GOR_VENUES}}};\n" + _GFR_JS + _GFR_FORMS345_JS
    return _page('gorilla_log', 'Log Field Activity', header, body, js, br, bt, user=user)


# ===========================================================================
# Gorilla Events
# ===========================================================================
def _gorilla_events_internal_page(br: str, bt: str, user: dict = None) -> str:
    _uname = (user or {}).get('name', '')
    header = (
        '<div class="header">'
        '<div class="header-left"><h1>Internal Events</h1>'
        '<div class="sub">Guerilla Marketing \u2014 field activity by program type</div>'
        '</div></div>'
    )
    body = (
        _GFR_CSS + _GFR_HTML + _GFR_FORMS345_HTML + _GFR_FORM2_HTML
        +
        '<div class="tab-bar" style="display:flex;gap:4px;margin-bottom:18px;flex-wrap:wrap">'
        '<button class="btn tab-btn active-tab" id="tab-bol" onclick="switchTab(\'bol\')" style="background:#ea580c;color:#fff">Interested Follow Up</button>'
        '<button class="btn tab-btn" id="tab-mms" onclick="switchTab(\'mms\')" style="background:var(--bg2);color:var(--text2);border:1px solid var(--border)">Mobile Massage</button>'
        '<button class="btn tab-btn" id="tab-ll"  onclick="switchTab(\'ll\')"  style="background:var(--bg2);color:var(--text2);border:1px solid var(--border)">Lunch &amp; Learn</button>'
        '<button class="btn tab-btn" id="tab-has" onclick="switchTab(\'has\')" style="background:var(--bg2);color:var(--text2);border:1px solid var(--border)">Health Assessment</button>'
        '</div>'
        '<div id="tab-content"></div>'
    )
    js = f"""
const INT_TYPES = {{
  bol: 'Business Outreach Log',
  mms: 'Mobile Massage Service',
  ll:  'Lunch and Learn',
  has: 'Health Assessment Screening'
}};
let _intActs = [];
let _activeTab = 'bol';

function switchTab(t) {{
  _activeTab = t;
  document.querySelectorAll('.tab-btn').forEach(function(b) {{
    if (b.id === 'tab-' + t) {{ b.style.background='#ea580c'; b.style.color='#fff'; b.style.border='none'; }}
    else {{ b.style.background='var(--bg2)'; b.style.color='var(--text2)'; b.style.border='1px solid var(--border)'; }}
  }});
  renderTab();
}}

function renderTab() {{
  var tname = INT_TYPES[_activeTab];
  var rows = _intActs.filter(function(r) {{ return (r['Type'] && r['Type'].value === tname) || r['Type'] === tname; }});
  if (!rows.length) {{
    document.getElementById('tab-content').innerHTML = '<div class="empty">No records for this type yet.</div>';
    return;
  }}
  var html = '<div class="table-wrap"><table class="data-table"><thead><tr>'
    + '<th>Date</th><th>Business</th><th>Contact Person</th><th>Outcome</th>'
    + '<th>Follow-Up</th><th>Summary</th></tr></thead><tbody>';
  rows.sort(function(a,b){{return (b['Date']||'').localeCompare(a['Date']||'');}});
  rows.forEach(function(r) {{
    var biz = '';
    if (r['Business'] && Array.isArray(r['Business'])) biz = esc(r['Business'].map(function(b){{return b.value||'';}}).join(', '));
    var fuDate = r['Follow-Up Date'] || '';
    var du = fuDate ? daysUntil(fuDate) : null;
    var fuBadge = '';
    if (du !== null) {{
      var fc = du < 0 ? '#ef4444' : du === 0 ? '#f59e0b' : '#10b981';
      var fl = du < 0 ? 'Overdue' : du === 0 ? 'Today' : 'In ' + du + 'd';
      fuBadge = '<span style="font-size:10px;background:' + fc + '20;color:' + fc + ';border-radius:4px;padding:2px 6px;margin-left:4px">' + fl + '</span>';
    }}
    var summary = esc((r['Summary'] || '').slice(0, 120)) + ((r['Summary'] || '').length > 120 ? '\u2026' : '');
    html += '<tr>'
      + '<td>' + esc(fmt(r['Date'] || '')) + '</td>'
      + '<td>' + biz + '</td>'
      + '<td>' + esc(r['Contact Person'] || '') + '</td>'
      + '<td>' + esc(sv(r['Outcome']) || '') + '</td>'
      + '<td>' + esc(fmt(fuDate)) + fuBadge + '</td>'
      + '<td style="max-width:260px;white-space:normal;font-size:12px;color:var(--text3)">' + summary + '</td>'
      + '</tr>';
  }});
  html += '</tbody></table></div>';
  document.getElementById('tab-content').innerHTML = html;
  stampRefresh();
}}

async function load() {{
  _intActs = await fetchAll({T_GOR_ACTS});
  renderTab();
}}
load();
"""
    gfr_preamble = f"const GFR_USER = {repr(_uname)};\nconst TOOL = {{venuesT: {T_GOR_VENUES}}};\n"
    js = gfr_preamble + _GFR_JS + '\n' + _GFR_FORMS345_JS + '\n' + js
    return _page('gorilla_events_int', 'Internal Events', header, body, js, br, bt, user=user)


def _gorilla_events_external_page(br: str, bt: str, user: dict = None) -> str:
    _uname = (user or {}).get('name', '')
    header = (
        '<div class="header">'
        '<div class="header-left"><h1>External Events</h1>'
        '<div class="sub">Guerilla Marketing \u2014 event pipeline by status</div>'
        '</div></div>'
    )
    body = (
        _GFR_CSS + _GFR_HTML + _GFR_FORMS345_HTML + _GFR_FORM2_HTML
        +
        '<div class="tab-bar" style="display:flex;gap:4px;margin-bottom:18px;flex-wrap:wrap">'
        '<button class="btn tab-btn active-tab" id="tab-all"         onclick="switchTab(\'all\')"         style="background:#ea580c;color:#fff">All</button>'
        '<button class="btn tab-btn" id="tab-Prospective" onclick="switchTab(\'Prospective\')" style="background:var(--bg2);color:var(--text2);border:1px solid var(--border)">Prospective</button>'
        '<button class="btn tab-btn" id="tab-Approved"    onclick="switchTab(\'Approved\')"    style="background:var(--bg2);color:var(--text2);border:1px solid var(--border)">Approved</button>'
        '<button class="btn tab-btn" id="tab-Scheduled"   onclick="switchTab(\'Scheduled\')"   style="background:var(--bg2);color:var(--text2);border:1px solid var(--border)">Scheduled</button>'
        '<button class="btn tab-btn" id="tab-Completed"   onclick="switchTab(\'Completed\')"   style="background:var(--bg2);color:var(--text2);border:1px solid var(--border)">Completed</button>'
        '</div>'
        '<div id="tab-content"></div>'
    )
    js = f"""
const STATUS_COLORS = {{
  Prospective: '#475569',
  Approved:    '#2563eb',
  Scheduled:   '#d97706',
  Completed:   '#059669',
}};
let _extEvents = [];
let _extTab = 'all';

function switchTab(t) {{
  _extTab = t;
  document.querySelectorAll('.tab-btn').forEach(function(b) {{
    if (b.id === 'tab-' + t) {{ b.style.background='#ea580c'; b.style.color='#fff'; b.style.border='none'; }}
    else {{ b.style.background='var(--bg2)'; b.style.color='var(--text2)'; b.style.border='1px solid var(--border)'; }}
  }});
  renderTab();
}}

function renderTab() {{
  var rows = _extEvents;
  if (_extTab !== 'all') {{
    rows = rows.filter(function(r) {{
      var st = r['Event Status'] ? (r['Event Status'].value || r['Event Status']) : '';
      return st === _extTab;
    }});
  }}
  if (!rows.length) {{
    document.getElementById('tab-content').innerHTML = '<div class="empty">No events in this stage.</div>';
    return;
  }}
  var html = '<div class="table-wrap"><table class="data-table"><thead><tr>'
    + '<th>Event Name</th><th>Status</th><th>Type</th><th>Organizer</th>'
    + '<th>Cost</th><th>Event Date</th><th>Address</th><th>Flyer</th><th></th></tr></thead><tbody>';
  rows.sort(function(a,b){{return (b['Date']||'').localeCompare(a['Date']||'');}});
  rows.forEach(function(r) {{
    var summary = r['Summary'] || '';
    var evtStatus = r['Event Status'] ? (r['Event Status'].value || r['Event Status']) : 'Prospective';
    var sc = STATUS_COLORS[evtStatus] || '#475569';
    var badge = '<span style="font-size:11px;background:'+sc+'20;color:'+sc+';border-radius:4px;padding:2px 7px;font-weight:600">'+esc(evtStatus)+'</span>';
    // parse key fields from summary text
    function extractField(label) {{
      var re = new RegExp(label + ': ([^\\\\n]+)');
      var m = summary.match(re);
      return m ? m[1].trim() : '';
    }}
    var evtName = extractField('Event Name') || esc(r['Name'] || '');
    var evtType = extractField('Type of Event') || extractField('Event Type');
    var organizer = extractField('Organizer');
    var cost = extractField('Cost');
    var addr = extractField('Venue Address');
    var flyerUrl = extractField('Event Flyer');
    var flyerCell = flyerUrl
      ? '<a href="'+esc(flyerUrl)+'" target="_blank" style="color:#ea580c">View</a>'
      : '\u2014';
    // Find matching T_EVENTS row
    var evLink = '';
    var matchedEv = _eventRows.find(function(e) {{
      return (e['Name']||'').toLowerCase().trim() === (evtName||'').toLowerCase().trim();
    }});
    if (matchedEv) {{
      evLink = '<a href="/events/'+matchedEv.id+'" style="color:#3b82f6;font-size:11px;font-weight:600;text-decoration:none">View \u2192</a>';
    }}
    html += '<tr>'
      + '<td style="font-weight:600">' + evtName + '</td>'
      + '<td>' + badge + '</td>'
      + '<td>' + esc(evtType) + '</td>'
      + '<td>' + esc(organizer) + '</td>'
      + '<td>' + esc(cost) + '</td>'
      + '<td>' + esc(fmt(r['Date'] || '')) + '</td>'
      + '<td style="font-size:12px;color:var(--text3)">' + esc(addr) + '</td>'
      + '<td>' + flyerCell + '</td>'
      + '<td>' + evLink + '</td>'
      + '</tr>';
  }});
  html += '</tbody></table></div>';
  document.getElementById('tab-content').innerHTML = html;
  stampRefresh();
}}

var _eventRows = [];
async function load() {{
  var [all, evRows] = await Promise.all([
    fetchAll({T_GOR_ACTS}),
    {T_EVENTS} ? fetchAll({T_EVENTS}) : Promise.resolve([]),
  ]);
  _eventRows = evRows;
  _extEvents = all.filter(function(r) {{
    var t = r['Type'] ? (r['Type'].value || r['Type']) : '';
    return t === 'External Event';
  }});
  renderTab();
}}
load();
"""
    gfr_preamble = f"const GFR_USER = {repr(_uname)};\nconst TOOL = {{venuesT: {T_GOR_VENUES}}};\n"
    js = gfr_preamble + _GFR_JS + '\n' + _GFR_FORMS345_JS + '\n' + js
    return _page('gorilla_events_ext', 'External Events', header, body, js, br, bt, user=user)


# ===========================================================================
# Gorilla Businesses & Boxes
# ===========================================================================
def _gorilla_businesses_page(br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header">'
        '<div class="header-left"><h1>Businesses Reached</h1>'
        '<div class="sub">Guerilla Marketing \u2014 all business venues</div>'
        '</div></div>'
    )
    body = (
        '<div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap" id="filter-bar">'
        '<button class="btn tab-btn" id="f-all"    onclick="setFilter(\'all\')"    style="background:#ea580c;color:#fff">All</button>'
        '<button class="btn tab-btn" id="f-active" onclick="setFilter(\'Active Partner\')"    style="background:var(--bg2);color:var(--text2);border:1px solid var(--border)">Active Partners</button>'
        '<button class="btn tab-btn" id="f-disc"   onclick="setFilter(\'In Discussion\')"    style="background:var(--bg2);color:var(--text2);border:1px solid var(--border)">In Discussion</button>'
        '<button class="btn tab-btn" id="f-cont"   onclick="setFilter(\'Contacted\')"        style="background:var(--bg2);color:var(--text2);border:1px solid var(--border)">Contacted</button>'
        '<button class="btn tab-btn" id="f-nc"     onclick="setFilter(\'Not Contacted\')"    style="background:var(--bg2);color:var(--text2);border:1px solid var(--border)">Not Contacted</button>'
        '</div>'
        '<div id="biz-content"></div>'
    )
    js = f"""
const STAGE_COLORS = {{
  'Not Contacted': '#475569',
  'Contacted':     '#2563eb',
  'In Discussion': '#d97706',
  'Active Partner':'#059669',
}};
let _venues = [], _acts = [], _activeFilter = 'all';

function setFilter(f) {{
  _activeFilter = f;
  var btns = {{ 'all':'f-all','Active Partner':'f-active','In Discussion':'f-disc','Contacted':'f-cont','Not Contacted':'f-nc' }};
  Object.keys(btns).forEach(function(k) {{
    var b = document.getElementById(btns[k]);
    if (k === f) {{ b.style.background='#ea580c'; b.style.color='#fff'; b.style.border='none'; }}
    else {{ b.style.background='var(--bg2)'; b.style.color='var(--text2)'; b.style.border='1px solid var(--border)'; }}
  }});
  render();
}}

function render() {{
  var rows = _venues;
  if (_activeFilter !== 'all') {{
    rows = rows.filter(function(r) {{ return sv(r['Contact Status']) === _activeFilter; }});
  }}
  if (!rows.length) {{
    document.getElementById('biz-content').innerHTML = '<div class="empty">No businesses in this stage.</div>';
    return;
  }}
  // Build activity count map
  var actCountMap = {{}}, actDateMap = {{}};
  _acts.forEach(function(a) {{
    var biz = a['Business'];
    var ids = Array.isArray(biz) ? biz.map(function(b){{return b.id;}}) : [];
    ids.forEach(function(id) {{
      actCountMap[id] = (actCountMap[id] || 0) + 1;
      if (!actDateMap[id] || (a['Date'] || '') > actDateMap[id]) actDateMap[id] = a['Date'] || '';
    }});
  }});
  var html = '<div class="table-wrap"><table class="data-table"><thead><tr>'
    + '<th>Business</th><th>Type</th><th>Status</th><th>Address</th>'
    + '<th>Activities</th><th>Last Activity</th></tr></thead><tbody>';
  rows.sort(function(a,b){{return (a['Name']||'').localeCompare(b['Name']||'');}});
  rows.forEach(function(r) {{
    var status = sv(r['Contact Status']) || 'Not Contacted';
    var sc = STAGE_COLORS[status] || '#475569';
    var badge = '<span style="font-size:11px;background:'+sc+'20;color:'+sc+';border-radius:4px;padding:2px 7px;font-weight:600">'+esc(status)+'</span>';
    var cnt = actCountMap[r['id']] || 0;
    var lastAct = actDateMap[r['id']] ? fmt(actDateMap[r['id']]) : '\u2014';
    html += '<tr>'
      + '<td style="font-weight:600">' + esc(r['Name'] || '') + '</td>'
      + '<td>' + esc(sv(r['Type']) || '') + '</td>'
      + '<td>' + badge + '</td>'
      + '<td style="font-size:12px;color:var(--text3)">' + esc(r['Address'] || '') + '</td>'
      + '<td style="text-align:center">' + cnt + '</td>'
      + '<td>' + lastAct + '</td>'
      + '</tr>';
  }});
  html += '</tbody></table></div>';
  document.getElementById('biz-content').innerHTML = html;
  stampRefresh();
}}

async function load() {{
  [_venues, _acts] = await Promise.all([fetchAll({T_GOR_VENUES}), fetchAll({T_GOR_ACTS})]);
  render();
}}
load();
"""
    return _page('gorilla_businesses', 'Businesses Reached', header, body, js, br, bt, user=user)


def _gorilla_boxes_page(br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header">'
        '<div class="header-left"><h1>Massage Box Tracking</h1>'
        '<div class="sub">Guerilla Marketing \u2014 referral box placements</div>'
        '</div></div>'
    )
    body = '<div id="boxes-summary" style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap"></div><div id="boxes-content"></div>'
    js = f"""
async function load() {{
  var boxes = await fetchAll({T_GOR_BOXES});
  var active = boxes.filter(function(b){{ return sv(b['Status'])==='Active'; }});
  var totalLeads = boxes.reduce(function(s,b){{ return s + (parseInt(b['Leads Generated'])||0); }}, 0);

  document.getElementById('boxes-summary').innerHTML =
    '<div class="stat-card"><div class="stat-val">'+boxes.length+'</div><div class="stat-label">Total Boxes</div></div>'
    +'<div class="stat-card"><div class="stat-val">'+active.length+'</div><div class="stat-label">Active Boxes</div></div>'
    +'<div class="stat-card"><div class="stat-val">'+totalLeads+'</div><div class="stat-label">Total Leads</div></div>';

  if (!boxes.length) {{
    document.getElementById('boxes-content').innerHTML = '<div class="empty">No massage boxes tracked yet.</div>';
    stampRefresh();
    return;
  }}
  var html = '<div class="table-wrap"><table class="data-table"><thead><tr>'
    + '<th>Box / Name</th><th>Business</th><th>Status</th><th>Date Placed</th>'
    + '<th>Date Removed</th><th>Leads</th><th>Location Notes</th></tr></thead><tbody>';
  boxes.sort(function(a,b){{
    var sa = sv(a['Status'])||''; var sb = sv(b['Status'])||'';
    if (sa==='Active'&&sb!=='Active') return -1;
    if (sb==='Active'&&sa!=='Active') return 1;
    return (b['Date Placed']||'').localeCompare(a['Date Placed']||'');
  }});
  boxes.forEach(function(b) {{
    var status = sv(b['Status']) || '';
    var sc = status === 'Active' ? '#059669' : '#475569';
    var badge = '<span style="font-size:11px;background:'+sc+'20;color:'+sc+';border-radius:4px;padding:2px 7px;font-weight:600">'+esc(status||'\u2014')+'</span>';
    var biz = b['Business'];
    var bizName = Array.isArray(biz) ? esc(biz.map(function(x){{return x.value||'';}}).join(', ')) : '';
    var leads = b['Leads Generated'] || 0;
    html += '<tr>'
      + '<td style="font-weight:600">' + esc(b['Name'] || b['id'] || '') + '</td>'
      + '<td>' + bizName + '</td>'
      + '<td>' + badge + '</td>'
      + '<td>' + esc(fmt(b['Date Placed'] || '')) + '</td>'
      + '<td>' + esc(fmt(b['Date Removed'] || '')) + '</td>'
      + '<td style="text-align:center">' + leads + '</td>'
      + '<td style="font-size:12px;color:var(--text3)">' + esc(b['Location Notes'] || '') + '</td>'
      + '</tr>';
  }});
  html += '</tbody></table></div>';
  document.getElementById('boxes-content').innerHTML = html;
  stampRefresh();
}}
load();
"""
    return _page('gorilla_boxes', 'Massage Box Tracking', header, body, js, br, bt, user=user)


# ===========================================================================
# Gorilla Routes
# ===========================================================================
def _gorilla_routes_page(br: str, bt: str, user: dict = None) -> str:
    is_admin = _is_admin(user or {})
    user_email = (user or {}).get("email", "").strip().lower()
    _contact_actions = contact_actions_js()
    _contact_detail  = contact_detail_js()
    page_title = "Field Routes" if is_admin else "My Routes"
    page_sub   = "Outreach route management" if is_admin else "Routes assigned to you"
    create_btn = (
        '<a href="/guerilla/routes/new" class="btn" '
        'style="background:#ea580c;color:#fff;font-size:12px;padding:6px 14px;border-radius:6px;text-decoration:none;font-weight:600">'
        '+ New Route</a>'
    ) if is_admin else ''
    header = (
        '<div class="header">'
        f'<div class="header-left"><h1>{page_title}</h1>'
        f'<div class="sub">{page_sub}</div></div>'
        f'<div class="header-right">{create_btn}</div>'
        '</div>'
    )
    body = """
<style>
.rd-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}
@media(max-width:700px){.rd-stats{grid-template-columns:repeat(2,1fr)}}
.rd-stat-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px;text-align:center}
.rd-stat-val{font-size:26px;font-weight:800}
.rd-stat-lbl{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:0.5px;margin-top:2px}
.rd-stat-sub{font-size:10px;color:var(--text3);margin-top:4px}
.rd-cols{display:grid;grid-template-columns:1fr 340px;gap:16px;margin-bottom:20px}
.rd-cols.rep-view{grid-template-columns:1fr}
.rd-cols.rep-view .admin-only{display:none!important}
@media(max-width:900px){.rd-cols{grid-template-columns:1fr}}
.rd-section-hdr{font-size:14px;font-weight:700;color:var(--text);margin-bottom:12px;display:flex;justify-content:space-between;align-items:center}
.route-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px 20px;margin-bottom:12px}
.route-hd{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.route-name{font-size:14px;font-weight:700;color:var(--text)}
.route-meta{font-size:12px;color:var(--text3);margin-bottom:10px}
.route-stats{display:flex;gap:14px;margin-bottom:8px}
.route-stat{font-size:12px;font-weight:600;display:flex;align-items:center;gap:4px}
.route-stat .dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.route-stops-detail{display:none;border-top:1px solid var(--border);padding-top:10px;margin-top:10px}
.route-stops-detail.open{display:block}
.route-stop-row{display:flex;align-items:center;gap:10px;padding:5px 0;font-size:12px;border-bottom:1px solid var(--border)}
.route-stop-row:last-child{border-bottom:none}
.route-stop-num{width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#fff;flex-shrink:0}
.route-toggle{font-size:11px;color:#3b82f6;cursor:pointer;border:none;background:none;font-weight:600}
.route-toggle:hover{text-decoration:underline}
.summary-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px 20px;margin-bottom:12px}
.summary-row{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--border)}
.summary-row:last-child{border-bottom:none}
.summary-avatar{width:32px;height:32px;border-radius:50%;background:#ea580c20;color:#ea580c;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;flex-shrink:0}
.summary-name{font-size:13px;font-weight:600;color:var(--text)}
.summary-stats{display:flex;gap:10px;font-size:11px;color:var(--text3);flex-wrap:wrap}
.summary-stats span{display:flex;align-items:center;gap:3px}
.missed-stop-row{display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--border);font-size:13px}
.missed-stop-row:last-child{border-bottom:none}
.missed-alert{background:linear-gradient(135deg,#ef444410,#f9731610);border:1px solid #ef444430;border-radius:10px;padding:16px 20px;margin-bottom:12px}
.past-routes-toggle{font-size:12px;color:#3b82f6;cursor:pointer;border:none;background:none;font-weight:600;padding:0}
.past-routes-toggle:hover{text-decoration:underline}
</style>

<!-- Stat cards -->
<div class="rd-stats" id="rd-stats"><div class="loading">Loading\u2026</div></div>

<!-- Two column layout: routes + field summary -->
<div class="rd-cols">
  <div>
    <div class="rd-section-hdr">
      <span>Active & Upcoming Routes</span>
    </div>
    <div id="routes-upcoming"><div class="loading">Loading\u2026</div></div>
    <div id="routes-past-wrapper" style="display:none">
      <button class="past-routes-toggle" onclick="togglePast(this)" style="margin:8px 0 12px">\u25b6 Show past routes</button>
      <div id="routes-past" style="display:none"></div>
    </div>
  </div>
  <div class="admin-only">
    <div class="rd-section-hdr">Field Rep Performance</div>
    <div id="summary-content"><div class="loading">Loading\u2026</div></div>
  </div>
</div>

<!-- Missed stops panel (admin only) -->
<div id="missed-content" class="admin-only"></div>
"""
    body += contact_detail_html('gorilla')
    js = f"""
const _TOOL_KEY = 'gorilla';
{_contact_actions}
{_contact_detail}

var _stops = [];
var _allRoutes = [];
var _acts = [];
var _pendingBoxByVenue = {{}};
var IS_ADMIN_VIEW = {str(is_admin).lower()};
var USER_EMAIL = {user_email!r};

// Apply rep-view layout for non-admins
if (!IS_ADMIN_VIEW) {{
  var cols = document.querySelector('.rd-cols');
  if (cols) cols.classList.add('rep-view');
}}

function togglePast(btn) {{
  var el = document.getElementById('routes-past');
  if (el.style.display === 'none') {{
    el.style.display = 'block';
    btn.innerHTML = '\u25bc Hide past routes';
  }} else {{
    el.style.display = 'none';
    btn.innerHTML = '\u25b6 Show past routes';
  }}
}}

async function load() {{
  if (!{T_GOR_ROUTES}) {{
    document.getElementById('routes-upcoming').innerHTML = '<div class="empty">Routes tables not configured.</div>';
    return;
  }}
  var [routes, stops, acts, boxes] = await Promise.all([
    fetchAll({T_GOR_ROUTES}),
    fetchAll({T_GOR_ROUTE_STOPS}),
    fetchAll({T_GOR_ACTS}),
    fetchAll({T_GOR_BOXES}),
  ]);
  _stops = stops;
  _allRoutes = routes;
  _acts = acts;

  // Build pending-box map
  boxes.forEach(function(b) {{
    var st = (b['Status'] && b['Status'].value) || b['Status'] || '';
    if (st !== 'Active' || !b['Date Placed']) return;
    var age = -(daysUntil(b['Date Placed']) || 0);
    var pd = parseInt(b['Pickup Days']) || 14;
    if (age < pd) return;
    var biz = b['Business'];
    if (!Array.isArray(biz) || !biz.length) return;
    var vid = biz[0].id;
    var info = _pendingBoxByVenue[vid];
    if (!info || age > info.age) {{
      _pendingBoxByVenue[vid] = {{age: age, overdue_by: age - pd, location: b['Location Notes']||''}};
    }}
  }});

  // Filter routes: field reps only see their own; admin sees all
  if (!IS_ADMIN_VIEW) {{
    routes = routes.filter(function(r) {{
      return (r['Assigned To']||'').trim().toLowerCase() === USER_EMAIL;
    }});
    _allRoutes = routes;
  }}

  // ── Compute global stats ──────────────────────────────────────
  var totalRoutes = routes.length;
  var activeRoutes = routes.filter(function(r){{ return sv(r['Status']) === 'Active'; }}).length;
  var draftRoutes = routes.filter(function(r){{ return sv(r['Status']) === 'Draft'; }}).length;
  var completedRoutes = routes.filter(function(r){{ return sv(r['Status']) === 'Completed'; }}).length;
  var totalStops = 0, visitedStops = 0, skippedStops = 0, missedStops = 0, pendingStops = 0;
  _stops.forEach(function(s) {{
    // Only count stops belonging to visible routes
    var rLink = s['Route'];
    var routeId = (Array.isArray(rLink) && rLink.length) ? rLink[0].id : null;
    if (!routeId || !_allRoutes.some(function(r){{return r.id===routeId;}})) return;
    totalStops++;
    var ss = sv(s['Status']) || 'Pending';
    if (ss==='Visited') visitedStops++;
    else if (ss==='Skipped') skippedStops++;
    else if (ss==='Not Reached') missedStops++;
    else pendingStops++;
  }});
  var completionPct = totalStops ? Math.round(visitedStops/totalStops*100) : 0;
  var missedTotal = skippedStops + missedStops;

  // Stat cards
  var statsHtml = '';
  statsHtml += '<div class="rd-stat-card">';
  statsHtml += '<div class="rd-stat-val" style="color:#ea580c">' + totalRoutes + '</div>';
  statsHtml += '<div class="rd-stat-lbl">Total Routes</div>';
  statsHtml += '<div class="rd-stat-sub">' + activeRoutes + ' active \u2022 ' + draftRoutes + ' draft \u2022 ' + completedRoutes + ' done</div>';
  statsHtml += '</div>';
  statsHtml += '<div class="rd-stat-card">';
  statsHtml += '<div class="rd-stat-val" style="color:#059669">' + visitedStops + '<span style="font-size:14px;color:var(--text3)">/' + totalStops + '</span></div>';
  statsHtml += '<div class="rd-stat-lbl">Stops Visited</div>';
  statsHtml += '<div class="rd-stat-sub">' + pendingStops + ' pending</div>';
  statsHtml += '</div>';
  statsHtml += '<div class="rd-stat-card">';
  var cColor = completionPct >= 80 ? '#059669' : completionPct >= 50 ? '#d97706' : '#ef4444';
  statsHtml += '<div class="rd-stat-val" style="color:' + cColor + '">' + completionPct + '%</div>';
  statsHtml += '<div class="rd-stat-lbl">Completion Rate</div>';
  statsHtml += '<div style="margin-top:6px;height:4px;background:var(--border);border-radius:2px;overflow:hidden">';
  statsHtml += '<div style="height:100%;width:'+completionPct+'%;background:'+cColor+';border-radius:2px"></div></div>';
  statsHtml += '</div>';
  statsHtml += '<div class="rd-stat-card">';
  statsHtml += '<div class="rd-stat-val" style="color:' + (missedTotal > 0 ? '#ef4444' : '#059669') + '">' + missedTotal + '</div>';
  statsHtml += '<div class="rd-stat-lbl">Missed Stops</div>';
  statsHtml += '<div class="rd-stat-sub">' + skippedStops + ' skipped \u2022 ' + missedStops + ' not reached</div>';
  statsHtml += '</div>';
  document.getElementById('rd-stats').innerHTML = statsHtml;

  // ── Split routes into upcoming vs past ────────────────────────
  var today = new Date().toISOString().split('T')[0];
  var upcoming = routes.filter(function(r) {{
    var d = r['Date'] || '';
    var st = sv(r['Status']) || 'Draft';
    return d >= today || st === 'Active' || st === 'Draft';
  }});
  var past = routes.filter(function(r) {{
    var d = r['Date'] || '';
    var st = sv(r['Status']) || 'Draft';
    return d < today && st !== 'Active' && st !== 'Draft';
  }});
  // Sort upcoming: soonest first
  upcoming.sort(function(a,b) {{ return (a['Date']||'').localeCompare(b['Date']||''); }});
  // Sort past: most recent first
  past.sort(function(a,b) {{ return (b['Date']||'').localeCompare(a['Date']||''); }});

  if (!upcoming.length && !past.length) {{
    var emptyMsg = IS_ADMIN_VIEW
      ? '<div class="empty">No routes yet. <a href="/guerilla/routes/new" style="color:#ea580c">Create the first one \u2192</a></div>'
      : '<div class="empty">No routes assigned to you yet.</div>';
    document.getElementById('routes-upcoming').innerHTML = emptyMsg;
  }} else {{
    document.getElementById('routes-upcoming').innerHTML = upcoming.length
      ? upcoming.map(renderRouteCard).join('')
      : '<div style="color:var(--text3);font-size:13px;padding:12px 0">No upcoming routes.</div>';
    if (past.length) {{
      document.getElementById('routes-past-wrapper').style.display = 'block';
      document.getElementById('routes-past').innerHTML = past.map(renderRouteCard).join('');
    }}
  }}

  renderFieldSummary();
  renderMissedStops();
  stampRefresh();
}}

function renderRouteCard(row) {{
  var rid = row.id;
  var status = sv(row['Status']) || 'Draft';
  var sc = status === 'Active' ? '#059669' : status === 'Completed' ? '#2563eb' : '#475569';
  var badge = '<span style="font-size:11px;background:'+sc+'20;color:'+sc+';border-radius:4px;padding:2px 7px;font-weight:600">'+esc(status)+'</span>';
  var btnLabel = status === 'Active' ? 'Draft' : 'Activate';

  var myStops = _stops.filter(function(s) {{
    var r = s['Route']; return Array.isArray(r) && r.some(function(x){{return x.id===rid;}});
  }}).sort(function(a,b) {{ return (a['Stop Order']||0) - (b['Stop Order']||0); }});
  var visited=0, skipped=0, notReached=0, pending=0;
  myStops.forEach(function(s) {{
    var ss = sv(s['Status']) || 'Pending';
    if (ss==='Visited') visited++;
    else if (ss==='Skipped') skipped++;
    else if (ss==='Not Reached') notReached++;
    else pending++;
  }});
  var total = myStops.length;
  var pct = total ? Math.round(visited/total*100) : 0;

  var html = '<div class="route-card">';
  html += '<div class="route-hd"><div><span class="route-name" style="cursor:pointer;text-decoration:underline dotted" onclick="toggleDetailFromName('+rid+')">'+esc(row['Name']||'(unnamed)')+'</span> '+badge+'</div>';
  html += '<div style="display:flex;gap:6px;align-items:center">';
  html += '<button class="btn btn-ghost" style="padding:4px 10px;font-size:11px" onclick="setStatus('+rid+',this)">'+btnLabel+'</button>';
  html += '</div></div>';
  html += '<div class="route-meta">'+esc(fmt(row['Date']||''))+' \u2022 '+esc(row['Assigned To']||'unassigned')+' \u2022 '+total+' stops</div>';

  html += '<div class="route-stats">';
  if (visited) html += '<div class="route-stat"><div class="dot" style="background:#059669"></div>'+visited+' Visited</div>';
  if (skipped) html += '<div class="route-stat"><div class="dot" style="background:#f97316"></div>'+skipped+' Skipped</div>';
  if (notReached) html += '<div class="route-stat"><div class="dot" style="background:#ef4444"></div>'+notReached+' Not Reached</div>';
  if (pending) html += '<div class="route-stat"><div class="dot" style="background:#94a3b8"></div>'+pending+' Pending</div>';
  if (total) {{
    html += '<div style="flex:1"></div>';
    html += '<div class="route-stat" style="color:'+sc+'">'+pct+'%</div>';
  }}
  html += '</div>';

  if (total) {{
    html += '<div style="height:4px;background:var(--border);border-radius:2px;overflow:hidden;margin-bottom:4px">';
    html += '<div style="height:100%;width:'+pct+'%;background:#059669;border-radius:2px"></div>';
    html += '</div>';
  }}

  if (total) {{
    html += '<button class="route-toggle" onclick="toggleDetail(this,'+rid+')">Show stops \u25be</button>';
    html += '<div class="route-stops-detail" id="rd-'+rid+'">';
    var routeDate = (row['Date']||'').substring(0,10);
    myStops.forEach(function(s, i) {{
      var ss = sv(s['Status']) || 'Pending';
      var sColor = ss==='Visited'?'#059669':ss==='Skipped'?'#f97316':ss==='Not Reached'?'#ef4444':'#94a3b8';
      var venueLink = s['Venue'];
      var vId = Array.isArray(venueLink) && venueLink.length ? venueLink[0].id : null;
      var vName = (venueLink && venueLink.length && venueLink[0].value) || s['Name'] || '(unknown)';
      var sNotes = s['Notes'] || '';
      var sTime = s['Completed At'] || '';
      var sBy = s['Completed By'] || '';
      var sLat = s['Check-In Lat'];
      var sLng = s['Check-In Lng'];
      var pendingBox = _pendingBoxByVenue[vId];

      html += '<div class="route-stop-row" style="flex-wrap:wrap">';
      html += '<div class="route-stop-num" style="background:'+sColor+'">'+(i+1)+'</div>';
      var nameHtml = vId ? '<span style="cursor:pointer;text-decoration:underline dotted var(--text3);text-underline-offset:3px" onclick="Contact.fetchVenue(\\'gorilla\\','+vId+').then(openContactDetail)">'+esc(vName)+'</span>' : esc(vName);
      html += '<span style="flex:1;font-weight:500;min-width:0">'+nameHtml;
      if (pendingBox) {{
        var od = pendingBox.overdue_by > 0 ? (' '+pendingBox.overdue_by+'d overdue') : '';
        html += ' <span style="background:#f59e0b20;color:#f59e0b;font-size:9px;padding:1px 5px;border-radius:3px;font-weight:600;margin-left:4px">\U0001f4e6 pickup' + od + '</span>';
      }}
      html += '</span>';
      html += '<span style="font-size:11px;color:'+sColor+';font-weight:600">'+esc(ss)+'</span>';
      if (vId && IS_ADMIN_VIEW) {{
        html += ' <a href="/outreach/planner?tool=gorilla&venue='+vId+'" style="font-size:11px;color:#3b82f6;text-decoration:none;margin-left:4px" title="View on map">\U0001f5fa Map</a>';
      }}

      var metaParts = [];
      if (sTime) metaParts.push('\u23f1 ' + esc(sTime));
      if (sBy) metaParts.push('\U0001f464 ' + esc(sBy));
      if (sLat && sLng) {{
        var gmapsUrl = 'https://www.google.com/maps?q=' + sLat + ',' + sLng;
        metaParts.push('<a href="'+gmapsUrl+'" target="_blank" style="color:#3b82f6;text-decoration:none">\U0001f4cd check-in</a>');
      }}
      if (sNotes) metaParts.push('\u270f\ufe0f ' + esc(sNotes));
      if (metaParts.length) {{
        html += '<div style="width:100%;padding-left:32px;font-size:11px;color:var(--text3);margin-top:4px">' + metaParts.join(' \u2022 ') + '</div>';
      }}

      if (vId && routeDate) {{
        var stopActs = _acts.filter(function(a) {{
          if ((a['Date']||'').substring(0,10) !== routeDate) return false;
          var biz = a['Business'];
          return Array.isArray(biz) && biz.some(function(r){{return r.id===vId;}});
        }});
        if (stopActs.length) {{
          html += '<div style="width:100%;padding-left:32px;margin-top:6px;padding-top:6px;border-top:1px dashed var(--border)">';
          stopActs.forEach(function(a) {{
            var aType = sv(a['Type']) || 'Activity';
            var aSummary = a['Summary'] || '';
            var aContact = a['Contact Person'] || '';
            var aOutcome = sv(a['Outcome']) || '';
            html += '<div style="margin-bottom:4px;font-size:11px">';
            html += '<span style="background:#ea580c20;color:#ea580c;padding:1px 6px;border-radius:3px;font-weight:600;font-size:9px">'+esc(aType)+'</span>';
            if (aOutcome) html += ' <span style="color:var(--text3)">'+esc(aOutcome)+'</span>';
            if (aContact) html += ' <span style="color:var(--text2)">\u2014 '+esc(aContact)+'</span>';
            if (aSummary) {{
              var summaryShort = aSummary.length > 150 ? aSummary.substring(0,150)+'\u2026' : aSummary;
              html += '<div style="color:var(--text3);margin-left:0;margin-top:2px;white-space:pre-wrap">'+esc(summaryShort)+'</div>';
            }}
            html += '</div>';
          }});
          html += '</div>';
        }}
      }}

      html += '</div>';
    }});
    html += '</div>';
  }}

  // Edit Route panel (admin-only, collapsible — was the old route-detail modal)
  if (IS_ADMIN_VIEW) {{
    html += '<div class="route-edit-wrap" style="border-top:1px solid var(--border);margin-top:12px;padding-top:10px">';
    html += '<button class="route-toggle" onclick="toggleEdit(this,'+rid+')" style="color:var(--text3)">\u2699\ufe0f Edit route \u25be</button>';
    html += '<div class="route-edit-body" id="re-'+rid+'" style="display:none;margin-top:10px">';
    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">';
    html += '<div><label style="font-size:10px;color:var(--text3)">Name</label>';
    html += '<input type="text" id="re-name-'+rid+'" value="'+esc(row['Name']||'')+'" style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 8px;font-size:12px;box-sizing:border-box"></div>';
    html += '<div><label style="font-size:10px;color:var(--text3)">Date</label>';
    html += '<input type="date" id="re-date-'+rid+'" value="'+esc(row['Date']||'')+'" style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 8px;font-size:12px;box-sizing:border-box"></div>';
    html += '</div>';
    html += '<div style="margin-bottom:10px"><label style="font-size:10px;color:var(--text3)">Assigned To</label>';
    html += '<input type="email" id="re-assignee-'+rid+'" value="'+esc(row['Assigned To']||'')+'" style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 8px;font-size:12px;box-sizing:border-box"></div>';
    html += '<div style="display:flex;gap:8px;align-items:center">';
    html += '<button onclick="saveRouteEdit('+rid+')" style="background:#3b82f6;color:#fff;border:none;border-radius:6px;padding:6px 14px;cursor:pointer;font-size:12px;font-weight:600">Save Changes</button>';
    html += '<span id="re-save-st-'+rid+'" style="font-size:11px;color:#34a853"></span>';
    html += '<button onclick="deleteRoute('+rid+')" style="margin-left:auto;background:none;color:#ef4444;border:1px solid #ef444440;border-radius:6px;padding:6px 14px;cursor:pointer;font-size:12px;font-weight:600">Delete Route</button>';
    html += '</div>';
    html += '</div></div>';
  }}

  html += '</div>';
  return html;
}}

function toggleEdit(btn, rid) {{
  var el = document.getElementById('re-'+rid);
  if (!el) return;
  var open = el.style.display !== 'none';
  el.style.display = open ? 'none' : 'block';
  btn.innerHTML = open ? '\u2699\ufe0f Edit route \u25be' : '\u2699\ufe0f Edit route \u25b4';
}}

function toggleDetail(btn, rid) {{
  var el = document.getElementById('rd-'+rid);
  if (el.classList.contains('open')) {{
    el.classList.remove('open');
    btn.textContent = 'Show stops \u25be';
  }} else {{
    el.classList.add('open');
    btn.textContent = 'Hide stops \u25b4';
  }}
}}

async function setStatus(routeId, btn) {{
  var cur = btn.textContent.trim();
  var newStatus = cur === 'Activate' ? 'Active' : 'Draft';
  btn.disabled = true;
  try {{
    var r = await fetch('/api/guerilla/routes/' + routeId + '/status', {{
      method: 'PATCH', headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{status: newStatus}})
    }});
    var d = await r.json();
    if (d.ok) load();
    else alert('Failed: ' + (d.error||'unknown'));
  }} catch(e) {{ alert('Error: '+e); btn.disabled=false; }}
}}

// ── Field Summary ────────────────────────────────────────────────
function renderFieldSummary() {{
  if (!{T_GOR_ROUTES}) return;
  var personStats = {{}};
  _allRoutes.forEach(function(route) {{
    var assignee = route['Assigned To'] || 'Unassigned';
    if (!personStats[assignee]) personStats[assignee] = {{routes:0, visited:0, skipped:0, notReached:0, pending:0, total:0}};
    personStats[assignee].routes++;
    var rid = route.id;
    var myStops = _stops.filter(function(s) {{
      var r = s['Route']; return Array.isArray(r) && r.some(function(x){{return x.id===rid;}});
    }});
    myStops.forEach(function(s) {{
      var ss = sv(s['Status']) || 'Pending';
      personStats[assignee].total++;
      if (ss==='Visited') personStats[assignee].visited++;
      else if (ss==='Skipped') personStats[assignee].skipped++;
      else if (ss==='Not Reached') personStats[assignee].notReached++;
      else personStats[assignee].pending++;
    }});
  }});

  var html = '';
  var people = Object.keys(personStats).sort();
  if (!people.length) {{ html = '<div class="summary-card"><div style="color:var(--text3);font-size:13px;padding:8px 0">No route data yet.</div></div>'; }}
  people.forEach(function(email) {{
    var p = personStats[email];
    var pct = p.total ? Math.round(p.visited/p.total*100) : 0;
    var initials = email.split('@')[0].substring(0,2).toUpperCase();
    html += '<div class="summary-card">';
    html += '<div class="summary-row" style="border-bottom:none">';
    html += '<div class="summary-avatar">' + initials + '</div>';
    html += '<div style="flex:1;min-width:0">';
    html += '<div class="summary-name">' + esc(email) + '</div>';
    html += '<div class="summary-stats">';
    html += '<span>' + p.routes + ' routes</span>';
    html += '<span><div class="dot" style="background:#059669;width:6px;height:6px;border-radius:50%"></div>' + p.visited + '</span>';
    html += '<span><div class="dot" style="background:#f97316;width:6px;height:6px;border-radius:50%"></div>' + p.skipped + '</span>';
    html += '<span><div class="dot" style="background:#ef4444;width:6px;height:6px;border-radius:50%"></div>' + p.notReached + '</span>';
    html += '<span><div class="dot" style="background:#94a3b8;width:6px;height:6px;border-radius:50%"></div>' + p.pending + '</span>';
    html += '</div>';
    html += '<div style="margin-top:4px;height:4px;background:var(--border);border-radius:2px;overflow:hidden">';
    html += '<div style="height:100%;width:'+pct+'%;background:#059669;border-radius:2px"></div>';
    html += '</div>';
    html += '</div>';
    html += '<div style="font-size:18px;font-weight:700;color:'+(pct>=80?'#059669':pct>=50?'#d97706':'#ef4444')+'">'+pct+'%</div>';
    html += '</div></div>';
  }});
  document.getElementById('summary-content').innerHTML = html;
}}

// ── Missed Stops ─────────────────────────────────────────────────
function renderMissedStops() {{
  var missedStops = _stops.filter(function(s) {{
    var ss = sv(s['Status']) || 'Pending';
    var rLink = s['Route'];
    var routeId = (Array.isArray(rLink) && rLink.length) ? rLink[0].id : null;
    return (ss === 'Not Reached' || ss === 'Skipped') && routeId && _allRoutes.some(function(r){{return r.id===routeId;}});
  }});
  if (!missedStops.length) {{
    document.getElementById('missed-content').innerHTML = '';
    return;
  }}
  var byRoute = {{}};
  missedStops.forEach(function(s) {{
    var rLink = s['Route'];
    var routeId = (Array.isArray(rLink) && rLink.length) ? rLink[0].id : 0;
    if (!byRoute[routeId]) byRoute[routeId] = [];
    byRoute[routeId].push(s);
  }});
  var html = '<div class="rd-section-hdr" style="color:#ef4444">\u26a0 Missed Stops</div>';
  Object.keys(byRoute).forEach(function(rid) {{
    var ridInt = parseInt(rid);
    var route = _allRoutes.find(function(r){{return r.id===ridInt;}});
    var routeName = route ? (route['Name']||'(unnamed)') : 'Unknown Route';
    var routeDate = route ? fmt(route['Date']||'') : '';
    var assignee = route ? (route['Assigned To']||'') : '';
    html += '<div class="missed-alert">';
    html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">';
    html += '<div><div style="font-size:14px;font-weight:700">'+esc(routeName)+'</div>';
    html += '<div style="font-size:11px;color:var(--text3)">'+esc(routeDate)+' \u2022 '+esc(assignee)+'</div></div>';
    html += '<span style="font-size:12px;font-weight:600;color:#ef4444">'+byRoute[rid].length+' missed</span>';
    html += '</div>';
    byRoute[rid].forEach(function(s) {{
      var ss = sv(s['Status']) || 'Pending';
      var sColor = ss==='Skipped' ? '#f97316' : '#ef4444';
      var venueLink = s['Venue'];
      var vId = Array.isArray(venueLink) && venueLink.length ? venueLink[0].id : null;
      var vName = (venueLink && venueLink.length && venueLink[0].value) || s['Name'] || '(unknown)';
      var notes = s['Notes'] || '';
      html += '<div class="missed-stop-row">';
      html += '<div class="route-stop-num" style="background:'+sColor+'">' + (s['Stop Order']||'?') + '</div>';
      html += '<div style="flex:1;min-width:0">';
      var missedNameHtml = vId ? '<span style="cursor:pointer;text-decoration:underline dotted var(--text3);text-underline-offset:3px" onclick="Contact.fetchVenue(\\'gorilla\\','+vId+').then(openContactDetail)">'+esc(vName)+'</span>' : esc(vName);
      html += '<div style="font-weight:600">'+missedNameHtml+'</div>';
      if (notes) html += '<div style="font-size:11px;color:var(--text3);margin-top:2px">Reason: '+esc(notes)+'</div>';
      html += '</div>';
      html += '<span style="font-size:11px;color:'+sColor+';font-weight:600">'+esc(ss)+'</span>';
      html += '</div>';
    }});
    html += '</div>';
  }});
  document.getElementById('missed-content').innerHTML = html;
}}

// ── Route Detail Modal ───────────────────────────────────────────
function toggleDetailFromName(rid) {{
  // Clicking a route name (dotted-underline) scrolls its card into view
  // and expands the stops drawer if it is collapsed.
  var card = document.getElementById('rd-' + rid);
  if (!card) return;
  var btn = card.previousElementSibling; // the 'Show stops' toggle button
  if (!card.classList.contains('open') && btn) toggleDetail(btn, rid);
  card.scrollIntoView({{behavior:'smooth', block:'center'}});
}}

async function saveRouteEdit(routeId) {{
  var st = document.getElementById('re-save-st-' + routeId);
  if (st) st.textContent = 'Saving\u2026';
  var payload = {{
    name: (document.getElementById('re-name-' + routeId)||{{}}).value || '',
    date: (document.getElementById('re-date-' + routeId)||{{}}).value || '',
    assigned_to: (document.getElementById('re-assignee-' + routeId)||{{}}).value || ''
  }};
  try {{
    var r = await fetch('/api/guerilla/routes/' + routeId, {{
      method: 'PATCH', headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify(payload)
    }});
    var d = await r.json();
    if (d.ok) {{
      if (st) st.textContent = 'Saved \u2713';
      setTimeout(function(){{ load(); }}, 600);
    }} else {{
      if (st) st.textContent = 'Failed: ' + (d.error||'unknown');
    }}
  }} catch(e) {{ if (st) st.textContent = 'Error: ' + e.message; }}
}}

async function deleteRoute(routeId) {{
  if (!confirm('Delete this route and all its stops? This cannot be undone.')) return;
  try {{
    var r = await fetch('/api/guerilla/routes/' + routeId, {{
      method: 'DELETE'
    }});
    var d = await r.json();
    if (d.ok) {{
      load();
    }} else {{
      alert('Failed to delete: ' + (d.error||'unknown'));
    }}
  }} catch(e) {{ alert('Error: ' + e.message); }}
}}

load();
"""
    return _page('gorilla_routes', 'Field Routes', header, body, js, br, bt, user=user)


def _gorilla_routes_new_page(br: str, bt: str, user: dict = None) -> str:
    from .tz import local_today
    today_str = local_today().isoformat()
    user = user or {}
    user_email = user.get('email', '')
    header = (
        '<div class="header">'
        '<div class="header-left"><h1>New Field Route</h1>'
        '<div class="sub">Create an ordered stop list for a field rep</div></div>'
        '</div>'
    )
    body = f"""
<div style="max-width:720px">
  <div class="card" style="margin-bottom:20px">
    <div class="card-title" style="margin-bottom:16px">Route Details</div>
    <div class="gfr-two" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
      <div>
        <label class="gfr-label">Route Name</label>
        <input class="gfr-input" id="rn-name" type="text" placeholder="e.g. Wednesday East Side Run" required>
      </div>
      <div>
        <label class="gfr-label">Date</label>
        <input class="gfr-input" id="rn-date" type="date" value="{today_str}" required>
      </div>
    </div>
    <div style="margin-bottom:12px">
      <label class="gfr-label">Assign To (email)</label>
      <input class="gfr-input" id="rn-assignee" type="email" value="{user_email}" placeholder="fieldstaff@reformchiropractic.com">
    </div>
    <div>
      <label class="gfr-label">Status</label>
      <select class="gfr-input" id="rn-status" style="background:var(--bg2);color:var(--text1)">
        <option value="Draft">Draft</option>
        <option value="Active">Active</option>
      </select>
    </div>
  </div>
  <div class="card" style="margin-bottom:20px">
    <div class="card-title" style="margin-bottom:12px">Add Stops</div>
    <div id="rn-pending-banner" style="display:none;margin-bottom:12px;padding:10px 14px;background:#f59e0b15;border:1px solid #f59e0b40;border-radius:6px;font-size:13px;color:#f59e0b">
      &#x1f4e6; <span id="rn-pending-count"></span>.
      <button type="button" onclick="showPendingOnly()" style="background:none;border:none;color:#f59e0b;font-size:12px;font-weight:600;text-decoration:underline;cursor:pointer;padding:0;margin-left:6px">Show pending pickups</button>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <input class="gfr-input" id="rn-venue-search" type="text" placeholder="Search businesses..." style="flex:1" oninput="searchVenues(this.value)">
    </div>
    <div id="rn-venue-results" style="margin-bottom:16px"></div>
    <div style="font-size:13px;color:var(--text3);margin-bottom:8px">Stop List</div>
    <div id="rn-stop-list" style="display:flex;flex-direction:column;gap:8px">
      <div id="rn-empty-stops" style="color:var(--text4);font-size:13px;padding:12px;text-align:center;border:1px dashed var(--border);border-radius:6px">
        No stops added yet. Search for a business above.
      </div>
    </div>
  </div>
  <div style="display:flex;gap:12px;align-items:center">
    <button class="btn btn-orange" onclick="submitRoute()" id="rn-submit-btn">Create Route</button>
    <a href="/guerilla/routes" class="btn btn-ghost">Cancel</a>
    <span id="rn-status-msg" style="font-size:13px;color:var(--text3)"></span>
  </div>
</div>
"""
    js = f"""
var _rnStops = [];   // {{venue_id, name, address}}
var _rnNextOrder = 1;
var _pendingBoxByVenue = {{}};  // venue_id -> {{age, overdue_by, location}}

// Load pending-pickup boxes on page open so search results can flag them
(async function loadPendingBoxes() {{
  var boxes = await fetchAll({T_GOR_BOXES});
  boxes.forEach(function(b) {{
    var st = (b['Status'] && b['Status'].value) || b['Status'] || '';
    if (st !== 'Active' || !b['Date Placed']) return;
    var age = -(daysUntil(b['Date Placed']) || 0);
    var pd = parseInt(b['Pickup Days']) || 14;
    if (age < pd) return;
    var biz = b['Business'];
    if (!Array.isArray(biz) || !biz.length) return;
    var vid = biz[0].id;
    var info = _pendingBoxByVenue[vid];
    if (!info || age > info.age) {{
      _pendingBoxByVenue[vid] = {{
        age: age, overdue_by: age - pd,
        location: b['Location Notes'] || ''
      }};
    }}
  }});
  // Also show a "Pending pickups" helper list at top
  var pendingVenueIds = Object.keys(_pendingBoxByVenue);
  if (pendingVenueIds.length) {{
    document.getElementById('rn-pending-count').textContent = pendingVenueIds.length + ' venue' + (pendingVenueIds.length>1?'s have':' has') + ' boxes pending pickup';
    document.getElementById('rn-pending-banner').style.display = 'block';
  }}
}})();

function _pendingBoxBadge(venueId) {{
  var info = _pendingBoxByVenue[venueId];
  if (!info) return '';
  var overdueLbl = info.overdue_by > 0 ? (' ('+info.overdue_by+'d overdue)') : '';
  return '<span style="background:#f59e0b20;color:#f59e0b;font-size:10px;padding:2px 6px;border-radius:4px;font-weight:600;margin-left:6px">\U0001f4e6 pending pickup'+overdueLbl+'</span>';
}}

function showPendingOnly() {{
  var ids = Object.keys(_pendingBoxByVenue);
  if (!ids.length) return;
  fetchAll({T_GOR_VENUES}).then(function(all) {{
    var matches = all.filter(function(v) {{ return _pendingBoxByVenue[v.id]; }});
    _renderVenueResults(matches);
  }});
}}

function _renderVenueResults(matches) {{
  if (!matches.length) {{
    document.getElementById('rn-venue-results').innerHTML = '<div style="font-size:13px;color:var(--text3);padding:6px">No matches.</div>';
    return;
  }}
  var html = '<div style="border:1px solid var(--border);border-radius:6px;overflow:hidden">';
  matches.forEach(function(v) {{
    html += '<div style="padding:8px 12px;cursor:pointer;border-bottom:1px solid var(--border);font-size:13px" '
      + "onmouseenter=\\\"this.style.background='var(--bg2)'\\\" onmouseleave=\\\"this.style.background=''\\\" "
      + 'onclick="addStop('+v['id']+','+JSON.stringify(esc(v['Name']||''))+','+JSON.stringify(esc(v['Address']||''))+')">'
      + '<strong>'+esc(v['Name']||'')+'</strong>'
      + _pendingBoxBadge(v['id'])
      + (v['Address'] ? '<div style="color:var(--text3);font-size:12px;margin-top:2px">'+esc(v['Address'])+'</div>' : '')
      + '</div>';
  }});
  html += '</div>';
  document.getElementById('rn-venue-results').innerHTML = html;
}}

async function searchVenues(q) {{
  if (q.length < 2) {{ document.getElementById('rn-venue-results').innerHTML = ''; return; }}
  var all = await fetchAll({T_GOR_VENUES});
  var ql = q.toLowerCase();
  var matches = all.filter(function(v) {{
    return (v['Name']||'').toLowerCase().includes(ql) || (v['Address']||'').toLowerCase().includes(ql);
  }}).slice(0, 10);
  _renderVenueResults(matches);
}}

function addStop(venueId, name, address) {{
  if (_rnStops.find(function(s){{ return s.venue_id === venueId; }})) {{
    alert(name + ' is already in the list.'); return;
  }}
  _rnStops.push({{venue_id: venueId, name: name, address: address, order: _rnNextOrder++}});
  document.getElementById('rn-venue-search').value = '';
  document.getElementById('rn-venue-results').innerHTML = '';
  renderStops();
}}

function removeStop(venueId) {{
  _rnStops = _rnStops.filter(function(s){{ return s.venue_id !== venueId; }});
  _rnStops.forEach(function(s,i){{ s.order = i+1; }});
  _rnNextOrder = _rnStops.length + 1;
  renderStops();
}}

function renderStops() {{
  var el = document.getElementById('rn-stop-list');
  if (!_rnStops.length) {{
    el.innerHTML = '<div id="rn-empty-stops" style="color:var(--text4);font-size:13px;padding:12px;text-align:center;border:1px dashed var(--border);border-radius:6px">No stops added yet.</div>';
    return;
  }}
  var html = '';
  _rnStops.forEach(function(s) {{
    var boxBadge = _pendingBoxBadge(s.venue_id);
    html += '<div style="display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--bg2);border:1px solid var(--border);border-radius:6px">'
      + '<span style="font-size:18px;font-weight:700;color:#ea580c;min-width:28px">'+s.order+'</span>'
      + '<div style="flex:1"><div style="font-weight:600;font-size:13px">'+s.name + boxBadge + '</div>'
      + (s.address ? '<div style="font-size:12px;color:var(--text3)">'+s.address+'</div>' : '')
      + '</div>'
      + '<button class="btn btn-ghost" style="padding:4px 10px;font-size:12px" onclick="removeStop('+s.venue_id+')">Remove</button>'
      + '</div>';
  }});
  el.innerHTML = html;
}}

async function submitRoute() {{
  var name = document.getElementById('rn-name').value.trim();
  var date = document.getElementById('rn-date').value;
  var assignee = document.getElementById('rn-assignee').value.trim();
  var status = document.getElementById('rn-status').value;
  if (!name) {{ alert('Route Name is required.'); return; }}
  if (!date) {{ alert('Date is required.'); return; }}
  var btn = document.getElementById('rn-submit-btn');
  btn.disabled = true; btn.textContent = 'Saving\u2026';
  document.getElementById('rn-status-msg').textContent = '';
  try {{
    var r = await fetch('/api/guerilla/routes', {{
      method: 'POST', headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{
        name: name, date: date, assigned_to: assignee, status: status,
        stops: _rnStops.map(function(s){{ return {{venue_id: s.venue_id}}; }})
      }})
    }});
    var d = await r.json();
    if (d.ok) {{
      window.location.href = '/guerilla/routes';
    }} else {{
      document.getElementById('rn-status-msg').textContent = 'Error: ' + (d.error||'unknown');
      btn.disabled = false; btn.textContent = 'Create Route';
    }}
  }} catch(e) {{
    document.getElementById('rn-status-msg').textContent = 'Network error: ' + e;
    btn.disabled = false; btn.textContent = 'Create Route';
  }}
}}
"""
    return _page('gorilla_routes', 'New Field Route', header, body, js, br, bt, user=user)


