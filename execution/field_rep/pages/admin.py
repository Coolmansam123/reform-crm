"""Admin page — Routes management + unified Recent Activity feed.

Tabs:
- Routes: lists routes where Status != Completed; each row has Reassign /
  Unassign / Delete actions wired to the existing PATCH/DELETE
  /api/guerilla/routes/{id} endpoints (admin-gated upstream).
- Activity: same unified feed previously at /recent — activities + events
  + leads sorted newest-first with kind badges and By-You KPI.

Tab state persists via URL hash (#routes default, #activity).
"""

from hub.shared import (
    _mobile_page,
    T_GOR_VENUES, T_GOR_ACTS, T_GOR_ROUTES, T_GOR_ROUTE_STOPS,
    T_EVENTS, T_LEADS, T_STAFF,
)
from hub.guerilla import GFR_EXTRA_HTML, GFR_EXTRA_JS


def _mobile_admin_page(br: str, bt: str, user: dict = None) -> str:
    user = user or {}
    user_name = user.get('name', '')
    user_email = (user.get('email', '') or '').strip().lower()
    body = (
        '<div class="mobile-hdr">'
        '<div><div class="mobile-hdr-title">Admin</div>'
        '<div class="mobile-hdr-sub">Routes &amp; recent activity</div></div>'
        '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        '</div>'
        '<div class="mobile-body">'
        # ── Tab strip ────────────────────────────────────────────────
        '<div id="adm-tabs" style="display:flex;gap:0;margin-bottom:14px;border:1px solid var(--border);'
        'border-radius:8px;overflow:hidden">'
        '<button id="adm-tab-routes" onclick="setAdmTab(\'routes\')" '
        'style="flex:1;background:#ea580c;color:#fff;border:none;padding:9px;font-size:13px;'
        'font-weight:600;cursor:pointer">Routes</button>'
        '<button id="adm-tab-activity" onclick="setAdmTab(\'activity\')" '
        'style="flex:1;background:none;color:var(--text2);border:none;padding:9px;font-size:13px;'
        'font-weight:600;cursor:pointer">Activity</button>'
        '</div>'
        # ── Routes tab body ──────────────────────────────────────────
        '<div id="adm-pane-routes">'
        '<div id="adm-routes-stats" style="display:flex;gap:8px;margin-bottom:10px;font-size:11px;color:var(--text3)">'
        '<span id="adm-routes-count">—</span></div>'
        '<div id="adm-routes-list">'
        '<div style="color:var(--text3);padding:20px;text-align:center">Loading…</div>'
        '</div>'
        '</div>'
        # ── Activity tab body ────────────────────────────────────────
        '<div id="adm-pane-activity" style="display:none">'
        '<div class="stats-row" style="margin-bottom:14px">'
        '<div class="stat-chip c-blue"><div class="label">Today</div><div class="value" id="adm-kpi-today">—</div></div>'
        '<div class="stat-chip c-green"><div class="label">This Week</div><div class="value" id="adm-kpi-week">—</div></div>'
        '<div class="stat-chip c-orange"><div class="label">By You</div><div class="value" id="adm-kpi-mine">—</div></div>'
        '</div>'
        '<div id="adm-kind-chips" style="display:flex;gap:6px;overflow-x:auto;padding-bottom:6px;'
        'margin-bottom:8px;-webkit-overflow-scrolling:touch"></div>'
        '<div id="adm-activity-list">'
        '<div style="color:var(--text3);padding:20px;text-align:center">Loading…</div>'
        '</div>'
        '</div>'
        '</div>'
    )
    js = f"""
const MY_NAME  = {repr(user_name)};
const MY_EMAIL = {repr(user_email)};

// ── Tab state ────────────────────────────────────────────────────────
function setAdmTab(t) {{
  var paneR = document.getElementById('adm-pane-routes');
  var paneA = document.getElementById('adm-pane-activity');
  var btnR  = document.getElementById('adm-tab-routes');
  var btnA  = document.getElementById('adm-tab-activity');
  if (t === 'activity') {{
    paneR.style.display = 'none'; paneA.style.display = '';
    btnR.style.background = 'none'; btnR.style.color = 'var(--text2)';
    btnA.style.background = '#ea580c'; btnA.style.color = '#fff';
    if (!_activityLoaded) loadAdmActivity();
  }} else {{
    paneA.style.display = 'none'; paneR.style.display = '';
    btnA.style.background = 'none'; btnA.style.color = 'var(--text2)';
    btnR.style.background = '#ea580c'; btnR.style.color = '#fff';
    if (!_routesLoaded) loadAdmRoutes();
  }}
  if (window.history && window.history.replaceState) {{
    history.replaceState(null, '', window.location.pathname + (t === 'activity' ? '#activity' : ''));
  }}
}}

function svJS(v) {{
  if (!v) return '';
  if (typeof v === 'object' && !Array.isArray(v)) return v.value || '';
  return String(v);
}}

// ─────────────────────────────────────────────────────────────────────
// ROUTES TAB
// ─────────────────────────────────────────────────────────────────────
var _routesLoaded = false;
var _admRoutes = [];
var _admStops  = [];
var _admStaff  = [];

async function loadAdmRoutes() {{
  try {{
    var results = await Promise.all([
      fetchAll({T_GOR_ROUTES}),
      fetchAll({T_GOR_ROUTE_STOPS}),
      fetchAll({T_STAFF}),
    ]);
    _admRoutes = results[0];
    _admStops  = results[1];
    _admStaff  = (results[2] || []).filter(function(s) {{ return s['Active']; }});
    _routesLoaded = true;
    renderAdmRoutes();
  }} catch (e) {{
    var box = document.getElementById('adm-routes-list');
    if (box) {{
      box.innerHTML = '<div style="color:#ef4444;padding:20px;text-align:center">'
                    + 'Failed to load routes. '
                    + '<button onclick="_routesLoaded=false;loadAdmRoutes()" style="margin-left:8px;background:none;color:#3b82f6;'
                    + 'border:1px solid var(--border);border-radius:6px;padding:4px 10px;cursor:pointer">Retry</button></div>';
    }}
  }}
}}

function _routeStops(routeId) {{
  return (_admStops || []).filter(function(s) {{
    var rl = s['Route'] || [];
    return Array.isArray(rl) && rl.some(function(r){{return r.id===routeId;}});
  }});
}}

function _staffOptionsHtml(currentEmail) {{
  var cur = (currentEmail || '').trim().toLowerCase();
  var opts = '<option value="">— Reassign —</option>';
  _admStaff.forEach(function(s) {{
    var em = (s['Email'] || '').trim();
    if (!em) return;
    var nm = s['Name'] || em;
    if (em.toLowerCase() === cur) return;
    opts += '<option value="'+esc(em)+'">'+esc(nm)+' ('+esc(em)+')</option>';
  }});
  return opts;
}}

function renderAdmRoutes() {{
  var box = document.getElementById('adm-routes-list');
  if (!box) return;
  var rows = (_admRoutes || []).filter(function(r) {{
    return svJS(r['Status']) !== 'Completed';
  }});
  // Newest first by Date, with future-dated routes ahead of past
  var today = new Date().toISOString().slice(0, 10);
  rows.sort(function(a, b) {{
    var da = a['Date'] || '', db = b['Date'] || '';
    var afut = da >= today, bfut = db >= today;
    if (afut !== bfut) return afut ? -1 : 1;
    return afut ? da.localeCompare(db) : db.localeCompare(da);
  }});
  document.getElementById('adm-routes-count').textContent =
    rows.length + ' incomplete route' + (rows.length === 1 ? '' : 's');
  if (!rows.length) {{
    box.innerHTML = '<div style="color:var(--text3);padding:30px 10px;text-align:center">'
                  + '<div style="font-size:14px">No incomplete routes ✓</div>'
                  + '<div style="font-size:12px;margin-top:6px">All routes are Completed.</div></div>';
    return;
  }}
  box.innerHTML = rows.map(function(r) {{
    var name = r['Name'] || ('Route #' + r.id);
    var dt = r['Date'] || '';
    var assigned = (r['Assigned To'] || '').trim();
    var status = svJS(r['Status']) || 'Draft';
    var stops = _routeStops(r.id);
    var visited = stops.filter(function(s) {{
      var st = svJS(s['Status']);
      return st === 'Visited' || st === 'Skipped' || st === 'Not Reached';
    }}).length;
    var statusColor = ({{'Draft':'#64748b','Active':'#10b981','Completed':'#3b82f6'}})[status] || '#64748b';
    return '<div style="padding:12px;border:1px solid var(--border);border-radius:10px;margin-bottom:10px;background:var(--card)">'
         + '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:4px">'
         + '<a href="/routes/'+r.id+'" style="font-weight:700;color:var(--text);text-decoration:none">'+esc(name)+'</a>'
         + '<span style="background:'+statusColor+'22;color:'+statusColor+';font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600">'+esc(status)+'</span>'
         + '</div>'
         + '<div style="color:var(--text3);font-size:12px;margin-bottom:8px">'
         + (dt ? esc(dt) + ' · ' : '')
         + visited + '/' + stops.length + ' stops done · '
         + (assigned ? '👤 ' + esc(assigned) : '<span style="color:#f97316">unassigned</span>')
         + '</div>'
         // Reassign select
         + '<div style="display:flex;gap:6px;margin-bottom:6px">'
         + '<select id="adm-reassign-'+r.id+'" '
         + 'style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
         + 'border-radius:6px;padding:7px 8px;font-size:12px">'
         + _staffOptionsHtml(assigned)
         + '</select>'
         + '<button onclick="reassignRoute('+r.id+')" '
         + 'style="background:#3b82f6;color:#fff;border:none;border-radius:6px;padding:7px 12px;'
         + 'font-size:12px;font-weight:600;cursor:pointer">Reassign</button>'
         + '</div>'
         // Unassign + Delete
         + '<div style="display:flex;gap:6px">'
         + '<button onclick="unassignRoute('+r.id+')" '
         + (assigned ? '' : 'disabled ')
         + 'style="flex:1;background:var(--bg);color:var(--text2);border:1px solid var(--border);border-radius:6px;padding:7px;'
         + 'font-size:12px;font-weight:600;cursor:pointer'+(assigned ? '' : ';opacity:.5;cursor:not-allowed')+'">Unassign</button>'
         + '<button onclick="deleteRoute('+r.id+',\\''+esc(name)+'\\')" '
         + 'style="flex:1;background:#fee2e2;color:#b91c1c;border:1px solid #fecaca;border-radius:6px;padding:7px;'
         + 'font-size:12px;font-weight:600;cursor:pointer">Delete</button>'
         + '</div>'
         + '<div id="adm-route-st-'+r.id+'" style="font-size:11px;margin-top:6px;min-height:14px"></div>'
         + '</div>';
  }}).join('');
}}

async function reassignRoute(routeId) {{
  var sel = document.getElementById('adm-reassign-' + routeId);
  if (!sel || !sel.value) {{ alert('Pick a rep first.'); return; }}
  var newEmail = sel.value;
  var st = document.getElementById('adm-route-st-' + routeId);
  if (st) {{ st.style.color = 'var(--text3)'; st.textContent = 'Reassigning…'; }}
  try {{
    var r = await fetch('/api/guerilla/routes/' + routeId, {{
      method: 'PATCH', headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{assigned_to: newEmail}})
    }});
    if (r.ok) {{
      if (st) {{ st.style.color = '#059669'; st.textContent = 'Reassigned to ' + newEmail + ' ✓'; }}
      _routesLoaded = false;
      setTimeout(loadAdmRoutes, 500);
    }} else {{
      var err = await r.json().catch(function(){{return{{}};}});
      if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Error: ' + (err.error || r.status); }}
    }}
  }} catch (e) {{
    if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Network error'; }}
  }}
}}

async function unassignRoute(routeId) {{
  if (!confirm('Unassign this route? It will sit unassigned until reassigned.')) return;
  var st = document.getElementById('adm-route-st-' + routeId);
  if (st) {{ st.style.color = 'var(--text3)'; st.textContent = 'Unassigning…'; }}
  try {{
    var r = await fetch('/api/guerilla/routes/' + routeId, {{
      method: 'PATCH', headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{assigned_to: ''}})
    }});
    if (r.ok) {{
      if (st) {{ st.style.color = '#059669'; st.textContent = 'Unassigned ✓'; }}
      _routesLoaded = false;
      setTimeout(loadAdmRoutes, 500);
    }} else {{
      var err = await r.json().catch(function(){{return{{}};}});
      if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Error: ' + (err.error || r.status); }}
    }}
  }} catch (e) {{
    if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Network error'; }}
  }}
}}

async function deleteRoute(routeId, name) {{
  if (!confirm('Delete "' + name + '"? This removes the route AND all its stops permanently.')) return;
  var st = document.getElementById('adm-route-st-' + routeId);
  if (st) {{ st.style.color = 'var(--text3)'; st.textContent = 'Deleting…'; }}
  try {{
    var r = await fetch('/api/guerilla/routes/' + routeId, {{ method: 'DELETE' }});
    if (r.ok) {{
      if (st) {{ st.style.color = '#059669'; st.textContent = 'Deleted ✓'; }}
      _routesLoaded = false;
      setTimeout(loadAdmRoutes, 500);
    }} else {{
      var err = await r.json().catch(function(){{return{{}};}});
      if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Error: ' + (err.error || r.status); }}
    }}
  }} catch (e) {{
    if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Network error'; }}
  }}
}}

// ─────────────────────────────────────────────────────────────────────
// ACTIVITY TAB (lifted from former /recent page)
// ─────────────────────────────────────────────────────────────────────
var _activityLoaded = false;
var _items = [];
var _filterKind = 'all';

const KIND_LABELS = {{
  'activity': '✍️ Activity',
  'event':    '\U0001f4c5 Event',
  'lead':     '\U0001f3af Lead',
}};
const KIND_COLORS = {{
  'activity': '#3b82f6',
  'event':    '#8b5cf6',
  'lead':     '#ea580c',
}};

function _firstLine(s) {{
  if (!s) return '';
  var i = String(s).indexOf('\\n');
  return i < 0 ? String(s) : String(s).slice(0, i);
}}

function _submittedBy(summary) {{
  if (!summary) return '';
  var m = String(summary).match(/Submitted by:\\s*([^\\n]+)/i);
  return m ? m[1].trim() : '';
}}

function _byMe(who) {{
  if (!who) return false;
  var w = String(who).toLowerCase();
  if (MY_EMAIL && w.indexOf(MY_EMAIL) !== -1) return true;
  if (MY_NAME  && w.indexOf(MY_NAME.toLowerCase()) !== -1) return true;
  return false;
}}

function _actToItem(a) {{
  var sf = svJS(a['Source Form']) || svJS(a['Type']) || 'Activity';
  var biz = (a['Business'] && a['Business'].length) ? (a['Business'][0].value || '') : '';
  var who = a['Created By'] || _submittedBy(a['Summary']);
  return {{
    kind: 'activity', id: a.id, title: sf,
    subtitle: biz || _firstLine(a['Summary']) || '',
    meta: [svJS(a['Outcome']), a['Contact Person']].filter(Boolean).join(' · '),
    date: (a['Created'] || a['Date'] || '').slice(0, 10),
    sortKey: a['Created'] || a['Date'] || '',
    who: who, href: null,
  }};
}}
function _evtToItem(e) {{
  var et = svJS(e['Event Type']) || 'Event';
  var es = svJS(e['Event Status']);
  var biz = (e['Business'] && e['Business'].length) ? (e['Business'][0].value || '') : '';
  var name = e['Name'] || biz || et;
  return {{
    kind: 'event', id: e.id, title: name,
    subtitle: et + (biz && biz !== name ? ' · ' + biz : ''),
    meta: [es, e['Event Date']].filter(Boolean).join(' · '),
    date: (e['Created'] || e['Event Date'] || '').slice(0, 10),
    sortKey: e['Created'] || e['Event Date'] || '',
    who: e['Created By'] || '', href: '/events#' + e.id,
  }};
}}
function _leadToItem(L) {{
  var nm = L['Name'] || '(no name)';
  var st = svJS(L['Status']) || 'New';
  var src = L['Source'] || '';
  return {{
    kind: 'lead', id: L.id, title: nm,
    subtitle: [L['Phone'], svJS(L['Reason'])].filter(Boolean).join(' · '),
    meta: [st, src].filter(Boolean).join(' · '),
    date: (L['Created'] || '').slice(0, 10),
    sortKey: L['Created'] || '',
    who: L['Owner'] || '', href: '/lead#' + L.id,
  }};
}}

function recomputeKpis() {{
  var today = new Date().toISOString().slice(0, 10);
  var weekAgo = new Date(Date.now() - 7*86400000).toISOString().slice(0, 10);
  var kT = 0, kW = 0, kM = 0;
  _items.forEach(function(it) {{
    if (it.date === today) kT++;
    if (it.date >= weekAgo) kW++;
    if (_byMe(it.who)) kM++;
  }});
  document.getElementById('adm-kpi-today').textContent = kT;
  document.getElementById('adm-kpi-week').textContent  = kW;
  document.getElementById('adm-kpi-mine').textContent  = kM;
}}

function renderKindChips() {{
  var box = document.getElementById('adm-kind-chips');
  if (!box) return;
  var entries = [
    {{key:'all',      label:'All',                color:'#64748b'}},
    {{key:'activity', label:KIND_LABELS.activity, color:KIND_COLORS.activity}},
    {{key:'event',    label:KIND_LABELS.event,    color:KIND_COLORS.event}},
    {{key:'lead',     label:KIND_LABELS.lead,     color:KIND_COLORS.lead}},
  ];
  box.innerHTML = entries.map(function(e) {{
    var active = (e.key === _filterKind);
    var bg = active ? e.color : 'var(--bg)';
    var fg = active ? '#fff' : 'var(--text2)';
    return '<button onclick="setKindFilter(\\''+ e.key +'\\')" '
         + 'style="flex:0 0 auto;background:'+bg+';color:'+fg+';border:1px solid '+e.color+';'
         + 'border-radius:14px;padding:5px 12px;font-size:12px;font-weight:600;cursor:pointer;'
         + 'white-space:nowrap;font-family:inherit">'+e.label+'</button>';
  }}).join('');
}}

function setKindFilter(k) {{
  _filterKind = k;
  renderKindChips();
  renderActivityFeed();
}}

function renderActivityFeed() {{
  var body = document.getElementById('adm-activity-list');
  if (!body) return;
  var rows = _items.slice();
  if (_filterKind !== 'all') {{
    rows = rows.filter(function(it) {{ return it.kind === _filterKind; }});
  }}
  rows = rows.slice(0, 30);
  if (!rows.length) {{
    body.innerHTML = '<div class="empty">No matching activity.</div>';
    return;
  }}
  body.innerHTML = rows.map(function(it) {{
    var color = KIND_COLORS[it.kind] || '#64748b';
    var label = KIND_LABELS[it.kind] || it.kind;
    var line = '<span style="background:'+color+'22;color:'+color+';font-size:10px;padding:2px 7px;'
             + 'border-radius:4px;font-weight:700;text-transform:uppercase;letter-spacing:.3px">'
             + esc(label) + '</span>';
    var titleHtml = it.href
      ? '<a href="'+esc(it.href)+'" style="color:var(--text);text-decoration:none">'+esc(it.title)+'</a>'
      : esc(it.title);
    return '<div style="padding:10px 0;border-bottom:1px solid var(--border)">'
         + '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:2px">'
         + '<span style="font-weight:600">' + titleHtml + '</span>'
         + line
         + '</div>'
         + (it.subtitle ? '<div style="color:var(--text2);font-size:12px">'+esc(it.subtitle)+'</div>' : '')
         + '<div style="color:var(--text3);font-size:11px;margin-top:2px">'
         + esc(it.date)
         + (it.meta ? ' · ' + esc(it.meta) : '')
         + (it.who ? ' · ' + esc(it.who) : '')
         + '</div>'
         + '</div>';
  }}).join('');
}}

async function loadAdmActivity() {{
  try {{
    var results = await Promise.all([
      fetchAll({T_GOR_ACTS}),
      fetchAll({T_EVENTS}),
      fetchAll({T_LEADS}),
    ]);
    var acts = results[0], events = results[1], leads = results[2];
    var items = []
      .concat(acts.map(_actToItem))
      .concat(events.map(_evtToItem))
      .concat(leads.map(_leadToItem));
    items.sort(function(a, b) {{
      var c = (b.sortKey || '').localeCompare(a.sortKey || '');
      if (c !== 0) return c;
      return (b.id || 0) - (a.id || 0);
    }});
    _items = items;
    _activityLoaded = true;
    recomputeKpis();
    renderActivityFeed();
  }} catch (e) {{
    var body = document.getElementById('adm-activity-list');
    if (body) {{
      body.innerHTML = '<div style="color:#ef4444;padding:20px;text-align:center">'
                    + 'Failed to load activity. '
                    + '<button onclick="_activityLoaded=false;loadAdmActivity()" style="margin-left:8px;background:none;color:#3b82f6;'
                    + 'border:1px solid var(--border);border-radius:6px;padding:4px 10px;cursor:pointer">Retry</button></div>';
    }}
  }}
}}

// ── Init ─────────────────────────────────────────────────────────────
renderKindChips();
var _initTab = (window.location.hash || '').replace(/^#/, '');
setAdmTab(_initTab === 'activity' ? 'activity' : 'routes');
"""
    script_js = f"const GFR_USER={repr(user_name)};\nconst TOOL = {{venuesT: {T_GOR_VENUES}}};\n" + js
    return _mobile_page('m_admin', 'Admin', body, script_js, br, bt, user=user,
                         extra_html=GFR_EXTRA_HTML, extra_js=GFR_EXTRA_JS)
