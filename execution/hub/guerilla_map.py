"""
Guerilla Marketing -- Desktop Map Page.
"""
import os

from .shared import (
    _page, _is_admin,
    T_GOR_VENUES, T_GOR_ACTS, T_GOR_BOXES, T_GOR_ROUTES, T_GOR_ROUTE_STOPS,
    T_COM_VENUES, T_COM_ACTS,
)
from .guerilla import (
    _GFR_CSS, _GFR_HTML, _GFR_FORMS345_HTML, _GFR_FORM2_HTML,
    _GFR_JS, _GFR_FORMS345_JS,
    GFR_EXTRA_HTML, GFR_EXTRA_JS,
)


# ===========================================================================
# Gorilla Map Page
# ===========================================================================
def _gorilla_map_page(br: str, bt: str, user: dict = None) -> str:
    gk = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    stages_json = '["Not Contacted","Contacted","In Discussion","Active Partner"]'
    admin = _is_admin(user or {})

    _uname = (user or {}).get('name', '')
    header = ''
    body = (
        '<style>.content{padding:0 !important;}</style>'
        + _GFR_CSS
        + _GFR_HTML
        + _GFR_FORMS345_HTML
        + _GFR_FORM2_HTML
        + '<div id="filter-bar" style="display:flex;align-items:center;gap:3px;padding:4px 10px;'
        'border-bottom:1px solid var(--border);background:var(--bg2)">'
        '<div class="loading" style="font-size:12px">Loading\u2026</div>'
        '</div>'
        '<div id="map-view" style="height:calc(100vh - 88px)">'
        '<div style="display:flex;height:100%;position:relative">'
        '<div id="gmap" style="flex:1;height:100%"></div>'
        '<style>'
        '#map-sidebar{width:380px;overflow-y:auto;background:var(--bg2);'
        'border-left:1px solid var(--border);padding:0;flex-shrink:0;'
        'transform:translateX(100%);opacity:0;position:absolute;right:0;top:0;bottom:0;'
        'transition:transform .25s ease,opacity .2s ease;z-index:10;}'
        '#map-sidebar.open{transform:translateX(0);opacity:1;}'
        '#map-sidebar .sb-content{transition:opacity .15s ease;}'
        '#map-sidebar .sb-content.fading{opacity:0;}'
        '</style>'
        '<div id="map-sidebar">'
        '</div>'
        '</div>'
        '</div>'
    )
    js = f"""
const GK = '{gk}';
// IS_ADMIN is set by page shell
const OFFICE_LAT = 33.9478, OFFICE_LNG = -118.1335;
const VENUES_TID = {T_GOR_VENUES};
const ACTS_TID   = {T_GOR_ACTS};
const ROUTES_TID = {T_GOR_ROUTES};
const STOPS_TID  = {T_GOR_ROUTE_STOPS};
const ACTS_LINK  = 'Business';
const USER_EMAIL = '{(user or {{}}).get("email", "")}';
let _venues = [];
let _stageFilter = '';
let _overdueFilter = false;
let _todayRoute = null;
let _todayStops = [];
let _map = null;
let _markerMap = {{}};
const _stages = {stages_json};
const _activeStatus = 'Active Partner';
const _nameField = 'Name';
const _addrField = 'Address';
const _phoneField = 'Phone';

// --- Baserow write helpers ------------------------------------------------
async function bpatch(tid, id, data) {{
  return fetch(BR + '/api/database/rows/table/' + tid + '/' + id + '/?user_field_names=true', {{
    method: 'PATCH',
    headers: {{'Authorization': 'Token ' + BT, 'Content-Type': 'application/json'}},
    body: JSON.stringify(data)
  }});
}}
async function bpost(tid, data) {{
  return fetch(BR + '/api/database/rows/table/' + tid + '/?user_field_names=true', {{
    method: 'POST',
    headers: {{'Authorization': 'Token ' + BT, 'Content-Type': 'application/json'}},
    body: JSON.stringify(data)
  }});
}}

// --- Filters --------------------------------------------------------------
function buildFilters() {{
  const bar = document.getElementById('filter-bar');
  bar.style.cssText = 'display:flex;align-items:center;gap:3px;padding:6px 12px;flex-wrap:wrap';
  var toggleBtn = {'true' if admin else 'false'}
    ? '<button onclick="toggleViewMode()" id="view-toggle" style="margin-left:auto;padding:3px 9px;font-size:10px;border-radius:10px;border:1px solid var(--border);background:var(--card);color:var(--text3);cursor:pointer;white-space:nowrap">' + (IS_ADMIN ? '&#x1f441; Field View' : '&#x1f512; Admin View') + '</button>'
    : '';
  if (IS_ADMIN) {{
    bar.innerHTML = '<button class="filter-btn on" data-stage="" onclick="setFilter(this)" style="padding:3px 9px;font-size:11px">All</button>'
      + _stages.map(s => '<button class="filter-btn" data-stage="' + s + '" onclick="setFilter(this)" style="padding:3px 9px;font-size:11px">' + s + '</button>').join('')
      + '<button class="filter-btn" id="overdue-btn" onclick="toggleOverdue(this)" style="padding:3px 9px;font-size:11px">Overdue</button>'
      + '<input class="search-input" id="search-box" placeholder="Search\u2026" oninput="applyFilters()" style="min-width:100px;max-width:160px;padding:3px 8px;font-size:11px">'
      + '<span id="count-bar" style="font-size:10px;color:var(--text4);margin-left:auto;white-space:nowrap"></span>'
      + toggleBtn;
  }} else {{
    bar.innerHTML = '<span style="font-size:13px;font-weight:600;color:var(--text)">My Route</span>'
      + '<input class="search-input" id="search-box" placeholder="Search\u2026" oninput="applyFilters()" style="min-width:100px;max-width:160px;padding:3px 8px;font-size:11px;margin-left:8px">'
      + '<span id="count-bar" style="font-size:10px;color:var(--text4);margin-left:auto;white-space:nowrap"></span>'
      + toggleBtn;
  }}
}}

function statusBadge(status) {{
  const map = {{'Not Contacted':'sb-not','Contacted':'sb-cont','In Discussion':'sb-disc'}};
  const cls = status === _activeStatus ? 'sb-act' : (map[status] || 'sb-not');
  return '<span class="status-badge ' + cls + '">' + esc(status || 'Unknown') + '</span>';
}}

function toggleViewMode() {{
  IS_ADMIN = !IS_ADMIN;
  closeSidebar();
  buildFilters();
  applyFilters();
}}

function setFilter(btn) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  _stageFilter = btn.dataset.stage;
  _overdueFilter = false;
  applyFilters();
}}

function toggleOverdue(btn) {{
  _overdueFilter = !_overdueFilter;
  if (_overdueFilter) {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
    _stageFilter = '';
  }} else {{
    btn.classList.remove('on');
    document.querySelector('.filter-btn[data-stage=""]').classList.add('on');
  }}
  applyFilters();
}}

function applyFilters() {{
  const q = (document.getElementById('search-box') ? document.getElementById('search-box').value || '' : '').toLowerCase();
  const todayStr = new Date().toISOString().split('T')[0];
  const filtered = _venues.filter(v => {{
    const name   = (v[_nameField] || '').toLowerCase();
    const status = sv(v['Contact Status']);
    const fu     = v['Follow-Up Date'] || '';
    if (_overdueFilter && (!fu || fu >= todayStr)) return false;
    return (!_stageFilter || status === _stageFilter) && (!q || name.includes(q));
  }});
  const cb = document.getElementById('count-bar');
  if (cb) cb.textContent = filtered.length + ' shown';
  renderMarkers();
}}

// --- Google Maps -----------------------------------------------------------
const _STATUS_COLORS = {{'Not Contacted':'#4285f4','Contacted':'#fbbc04','In Discussion':'#ff9800'}};
function _pinColor(s) {{ return s === _activeStatus ? '#34a853' : (_STATUS_COLORS[s] || '#9e9e9e'); }}
function _pinIcon(color) {{
  return {{ path: google.maps.SymbolPath.CIRCLE, scale: 6,
            fillColor: color, fillOpacity: 1, strokeColor: '#fff', strokeWeight: 1 }};
}}
function _pinIconSelected(color) {{
  return {{ path: google.maps.SymbolPath.CIRCLE, scale: 10,
            fillColor: color, fillOpacity: 1, strokeColor: '#fff', strokeWeight: 2 }};
}}
let _selectedId = null;

function initMap() {{
  if (!GK) {{ document.getElementById('gmap').innerHTML = '<div style="padding:40px;text-align:center;color:var(--text3)">Google Maps API key not configured.</div>'; return; }}
  window._mapReadyCb = function() {{
    _map = new google.maps.Map(document.getElementById('gmap'), {{
      center: {{lat: OFFICE_LAT, lng: OFFICE_LNG}}, zoom: 12,
      mapTypeControl: false, streetViewControl: false, clickableIcons: false,
      styles: [{{featureType:'poi',stylers:[{{visibility:'off'}}]}},
               {{featureType:'transit',stylers:[{{visibility:'off'}}]}},
               {{featureType:'administrative.neighborhood',stylers:[{{visibility:'off'}}]}},
               {{featureType:'administrative.locality',elementType:'labels.icon',stylers:[{{visibility:'off'}}]}}]
    }});
    new google.maps.Marker({{ position: {{lat: OFFICE_LAT, lng: OFFICE_LNG}}, map: _map,
      title: 'Reform Chiropractic',
      icon: {{ url: 'http://maps.google.com/mapfiles/ms/icons/red-dot.png' }}
    }});
    renderMarkers();
  }};
  const s = document.createElement('script');
  s.src = 'https://maps.googleapis.com/maps/api/js?key=' + GK + '&callback=_mapReadyCb';
  s.async = true; document.head.appendChild(s);
}}

function closeSidebar() {{
  document.getElementById('map-sidebar').classList.remove('open');
  if (_selectedId && _markerMap[_selectedId]) {{
    const prev = _venues.find(x => x.id === _selectedId);
    const prevStatus = prev ? sv(prev['Contact Status']) : '';
    _markerMap[_selectedId].setIcon(_pinIcon(_pinColor(prevStatus)));
  }}
  _selectedId = null;
  _currentVenue = null;
}}

function renderMarkers() {{
  if (!_map) return;
  Object.values(_markerMap).forEach(m => m.setMap(null));
  _markerMap = {{}};
  const q = (document.getElementById('search-box') ? document.getElementById('search-box').value || '' : '').toLowerCase();
  const todayStr = new Date().toISOString().split('T')[0];
  _venues.forEach(v => {{
    const lat = parseFloat(v['Latitude']), lng = parseFloat(v['Longitude']);
    if (!lat || !lng) return;
    const status = sv(v['Contact Status']);
    if (_stageFilter && status !== _stageFilter) return;
    if (q && !(v[_nameField] || '').toLowerCase().includes(q)) return;
    if (_overdueFilter) {{
      const fu = v['Follow-Up Date'] || '';
      if (!fu || fu >= todayStr) return;
    }}
    const marker = new google.maps.Marker({{
      position: {{lat, lng}}, map: _map, title: v[_nameField] || '',
      icon: _pinIcon(_pinColor(status))
    }});
    marker.addListener('click', () => showGorDetail(v));
    _markerMap[v.id] = marker;
  }});
}}

// --- Note renderer ---------------------------------------------------------
function renderNotes(text) {{
  if (!text || !text.trim()) return '<div style="color:var(--text3);font-size:12px;padding:4px 0">No notes yet</div>';
  return text.split('\\n---\\n').filter(e => e.trim()).map(entry => {{
    const m = entry.match(/^\\[(\\d{{4}}-\\d{{2}}-\\d{{2}})\\] ([\\s\\S]*)$/);
    if (m) return '<div style="padding:5px 0;border-bottom:1px solid var(--border)">'
      + '<div style="font-size:10px;color:var(--text3);margin-bottom:2px">' + m[1] + '</div>'
      + '<div style="font-size:12px">' + esc(m[2].trim()) + '</div></div>';
    return '<div style="padding:5px 0;border-bottom:1px solid var(--border);font-size:12px">' + esc(entry.trim()) + '</div>';
  }}).join('');
}}

function stageOpts(cur) {{
  return _stages.map(s => '<option value="' + s + '"' + (cur === s ? ' selected' : '') + '>' + s + '</option>').join('');
}}

// --- Gorilla sidebar (3-tab) -----------------------------------------------
function showGorDetail(v) {{
  const sb = document.getElementById('map-sidebar');
  const id = v.id;
  // Reset previous selected pin
  if (_selectedId && _markerMap[_selectedId]) {{
    const prev = _venues.find(x => x.id === _selectedId);
    const prevStatus = prev ? sv(prev['Contact Status']) : '';
    _markerMap[_selectedId].setIcon(_pinIcon(_pinColor(prevStatus)));
  }}
  // Highlight new selected pin
  _selectedId = id;
  _currentVenue = v;
  if (_markerMap[id]) {{
    const color = _pinColor(sv(v['Contact Status']));
    _markerMap[id].setIcon(_pinIconSelected(color));
  }}
  const name     = esc(v[_nameField] || '(unnamed)');
  const status   = sv(v['Contact Status']);
  const phone    = esc(v[_phoneField] || '');
  const addr     = esc(v[_addrField]  || '');
  const website  = v['Website'] || '';
  const rating   = v['Rating'] || '';
  const reviews  = v['Reviews'] || '';
  const dist     = v['Distance (mi)'] || '';
  const _placeId = v['Google Place ID'] || '';
  const gmUrl    = v['Google Maps URL'] || (_placeId ? 'https://www.google.com/maps/place/?q=place_id:' + _placeId : '');
  const yelpUrl  = v['Yelp Search URL'] || '';
  const fu       = v['Follow-Up Date'] || '';
  const classif  = sv(v['Classification'] || v['Type'] || '');
  const notesRaw = v['Notes'] || '';
  const today    = new Date().toISOString().split('T')[0];
  const statColors = {{'Not Contacted':'#4285f4','Contacted':'#fbbc04','In Discussion':'#ff9800','Active Partner':'#34a853'}};
  const statColor  = statColors[status] || '#64748b';

  let html = '';

  // - Header
  html += '<div style="padding:16px 18px 10px">';
  html += '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">';
  html += '<div style="font-size:16px;font-weight:700;line-height:1.3;padding-right:10px">' + name + '</div>';
  html += '<button onclick="closeSidebar()" style="background:none;border:none;color:var(--text3);cursor:pointer;font-size:20px;line-height:1;flex-shrink:0">&times;</button>';
  html += '</div>';

  if (!IS_ADMIN) {{
    // ── FIELD REP SIDEBAR (tabbed, action-focused) ─────────────────────────
    if (classif) html += '<span style="background:#1565C0;color:#fff;font-size:11px;padding:3px 9px;border-radius:5px;margin-bottom:10px;display:inline-block">' + esc(classif) + '</span>';

    // Check In button (primary action)
    html += '<div style="padding:8px 0 10px">';
    html += '<button onclick="openLogEvent()" style="width:100%;background:#3b82f6;color:#fff;border:none;border-radius:7px;padding:11px 12px;font-size:14px;font-weight:600;cursor:pointer">Check In</button>';
    html += '</div>';

    // Tab bar
    html += '<div class="sb-tabs">';
    html += '<div class="sb-tab active" onclick="sbTab(this,\\'info-' + id + '\\')">Info</div>';
    html += '<div class="sb-tab" onclick="sbTab(this,\\'acts-' + id + '\\')">Activity</div>';
    html += '<div class="sb-tab" onclick="sbTab(this,\\'evts-' + id + '\\')">Events</div>';
    html += '<div class="sb-tab" onclick="sbTab(this,\\'boxes-' + id + '\\')">Boxes</div>';
    html += '</div>';

    // Info panel
    html += '<div class="sb-panel active" id="info-' + id + '" style="padding:14px">';
    if (phone) html += '<div style="font-size:13px;margin-bottom:8px">&#128222; <a href="tel:' + phone + '" style="color:var(--text)">' + phone + '</a></div>';
    if (addr)  html += '<div style="font-size:13px;color:var(--text2);margin-bottom:8px">&#128205; ' + addr + '</div>';
    if (dist)  html += '<div style="font-size:11px;color:var(--text3);margin-bottom:8px">' + esc(dist) + ' mi from office</div>';
    html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
    html += '<div class="sb-section-lbl" style="margin-bottom:6px">Notes</div>';
    html += '<div id="sb-notes-' + id + '" style="max-height:100px;overflow-y:auto;background:var(--card);border-radius:7px;padding:8px 10px;border:1px solid var(--border);font-size:12px">' + renderNotes(notesRaw) + '</div>';
    html += '<div style="display:flex;gap:6px;margin-top:6px">';
    html += '<input type="text" id="sb-note-in-' + id + '" placeholder="Add a note\u2026" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:6px 10px;font-size:12px">';
    html += '<button onclick="addNote(' + id + ')" style="background:#e94560;color:#fff;border:none;border-radius:7px;padding:6px 10px;cursor:pointer;font-size:11px;font-weight:600">Add</button>';
    html += '</div><div id="sb-note-st-' + id + '" style="font-size:11px;color:#34a853;margin-top:3px"></div>';
    html += '</div>';

    // Activity panel (last visit only)
    html += '<div class="sb-panel" id="acts-' + id + '" style="padding:14px">';
    html += '<div id="sb-last-visit-' + id + '" style="font-size:12px;color:var(--text3)">Loading\u2026</div>';
    html += '</div>';

    // Events panel (3 schedule buttons, no history)
    html += '<div class="sb-panel" id="evts-' + id + '" style="padding:14px">';
    html += '<div class="sb-section-lbl" style="margin-bottom:8px">Schedule Event</div>';
    html += '<div style="display:grid;gap:8px">';
    html += '<button onclick="openScheduleEvent(\\'Mobile Massage Service\\')" style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:9px 12px;font-size:13px;font-weight:600;cursor:pointer;text-align:left">&#x1f486; Mobile Massage</button>';
    html += '<button onclick="openScheduleEvent(\\'Lunch and Learn\\')" style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:9px 12px;font-size:13px;font-weight:600;cursor:pointer;text-align:left">&#x1f37d;&#xfe0f; Lunch &amp; Learn</button>';
    html += '<button onclick="openScheduleEvent(\\'Health Assessment Screening\\')" style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:9px 12px;font-size:13px;font-weight:600;cursor:pointer;text-align:left">&#x1fa7a; Health Assessment</button>';
    html += '</div></div>';

    // Boxes panel
    html += '<div class="sb-panel" id="boxes-' + id + '" style="padding:14px">';
    html += '<div id="sb-boxes-list-' + id + '"><div class="loading">Loading\u2026</div></div>';
    html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
    html += '<div class="sb-section-lbl" style="margin-bottom:6px">Place New Box</div>';
    html += '<div style="display:grid;gap:6px">';
    html += '<input type="text" id="sb-box-loc-' + id + '" placeholder="Location (e.g. Front desk)" onkeydown="if(event.key===\'Enter\'){{event.preventDefault();placeBoxDesktop(' + id + ');}}" style="background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:6px 10px;font-size:12px">';
    html += '<input type="text" id="sb-box-contact-' + id + '" placeholder="Contact person" onkeydown="if(event.key===\'Enter\'){{event.preventDefault();placeBoxDesktop(' + id + ');}}" style="background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:6px 10px;font-size:12px">';
    html += '<button onclick="placeBoxDesktop(' + id + ')" style="background:#059669;color:#fff;border:none;border-radius:7px;padding:7px 12px;cursor:pointer;font-size:12px;font-weight:600">Place Box</button>';
    html += '<div id="sb-box-st-' + id + '" style="font-size:11px;text-align:center;min-height:14px"></div>';
    html += '</div></div>';

    html += '</div>';  // close header padding div

  }} else {{
  // ── ADMIN SIDEBAR (full featured) ──────────────────────────────────────

  // Classification + status badge
  html += '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px">';
  if (classif) html += '<span style="background:#1565C0;color:#fff;font-size:11px;padding:3px 9px;border-radius:5px">' + esc(classif) + '</span>';
  html += '<span class="sb-status-badge" id="sb-stat-badge-' + id + '" onclick="toggleStatusPicker(' + id + ')" style="color:' + statColor + '">';
  html += '&#x25CF; ' + esc(status || 'Unknown') + '</span>';
  html += '<span id="sb-stat-save-' + id + '" style="font-size:11px;color:#34a853"></span>';
  html += '</div>';
  html += '<select class="sb-inline-select" id="sb-stat-sel-' + id + '" onchange="updateGorStatus(' + id + ',this.value)">' + stageOpts(status) + '</select>';

  // Check In button
  html += '<div style="padding:8px 0 10px">';
  html += '<button onclick="openLogEvent()" style="width:100%;background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:7px;padding:9px 12px;font-size:13px;font-weight:600;cursor:pointer;transition:background .12s">Check In &#x2192;</button>';
  html += '</div>';

  // - Tab bar
  html += '<div class="sb-tabs">';
  html += '<div class="sb-tab active" onclick="sbTab(this,\\'info-' + id + '\\')">Info</div>';
  html += '<div class="sb-tab" onclick="sbTab(this,\\'acts-' + id + '\\')">Activity</div>';
  html += '<div class="sb-tab" onclick="sbTab(this,\\'evts-' + id + '\\')">Events</div>';
  html += '<div class="sb-tab" onclick="sbTab(this,\\'boxes-' + id + '\\')">Boxes</div>';
  html += '</div>';

  // - Info panel
  html += '<div class="sb-panel active" id="info-' + id + '" style="padding:18px">';
  if (phone)   html += '<div style="font-size:13px;margin-bottom:10px">&#128222; <a href="tel:' + phone + '" style="color:var(--text)">' + phone + '</a></div>';
  if (addr)    html += '<div style="font-size:13px;color:var(--text2);margin-bottom:10px">&#128205; ' + addr + '</div>';
  if (website) html += '<div style="font-size:12px;margin-bottom:8px">&#127760; <a href="' + esc(website) + '" target="_blank" style="color:#3b82f6">' + esc(website) + '</a></div>';
  if (gmUrl || yelpUrl) {{
    html += '<div style="display:flex;gap:12px;font-size:12px;margin-bottom:8px">';
    if (gmUrl)   html += '<a href="' + esc(gmUrl)   + '" target="_blank" style="color:#3b82f6">Google Maps &#x2197;</a>';
    if (yelpUrl) html += '<a href="' + esc(yelpUrl) + '" target="_blank" style="color:#f97316">Yelp &#x2197;</a>';
    html += '</div>';
  }}
  if (rating) {{
    const stars = '\u2605'.repeat(Math.min(5, Math.round(parseFloat(rating)||0)));
    html += '<div style="font-size:12px;margin-bottom:8px">' + stars + ' ' + esc(rating) + (reviews ? ' (' + reviews + ' reviews)' : '') + '</div>';
  }}
  if (dist) html += '<div style="font-size:11px;color:var(--text3);margin-bottom:10px">' + esc(dist) + ' mi from office</div>';
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:14px 0">';
  html += '<div class="sb-section-lbl" style="margin-bottom:8px">Follow-Up Date</div>';
  html += '<div style="display:flex;gap:8px;align-items:center;margin-bottom:14px">';
  html += '<input type="date" id="sb-fu-' + id + '" value="' + esc(fu) + '" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:7px 10px;font-size:13px">';
  html += '<button onclick="saveFollowUp(' + id + ')" style="background:#3b82f6;color:#fff;border:none;border-radius:7px;padding:7px 12px;cursor:pointer;font-size:12px;font-weight:600">Save</button>';
  html += '<span id="sb-fu-st-' + id + '" style="font-size:11px;color:#34a853;min-width:20px"></span></div>';
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:14px 0">';
  html += '<div class="sb-section-lbl" style="margin-bottom:8px">Notes</div>';
  html += '<div id="sb-notes-' + id + '" style="max-height:140px;overflow-y:auto;background:var(--card);border-radius:7px;padding:10px 12px;border:1px solid var(--border)">' + renderNotes(notesRaw) + '</div>';
  html += '<div style="display:flex;gap:8px;margin-top:8px">';
  html += '<input type="text" id="sb-note-in-' + id + '" placeholder="Add a note\u2026" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:7px 10px;font-size:13px">';
  html += '<button onclick="addNote(' + id + ')" style="background:#e94560;color:#fff;border:none;border-radius:7px;padding:7px 12px;cursor:pointer;font-size:12px;font-weight:600">Add</button>';
  html += '</div><div id="sb-note-st-' + id + '" style="font-size:11px;color:#34a853;margin-top:4px"></div>';
  html += '</div>';

  // - Activity panel (GFR form trigger + history)
  html += '<div class="sb-panel" id="acts-' + id + '" style="padding:14px">';
  html += '<button onclick="openLogEvent()" style="width:100%;background:#ea580c;color:#fff;border:none;border-radius:10px;padding:12px;font-size:14px;font-weight:700;cursor:pointer;margin-bottom:14px">\u270f\ufe0f Log Activity</button>';
  html += '<div class="sb-section-lbl" style="margin-bottom:8px">History</div>';
  html += '<div id="sb-acts-list-' + id + '"><div class="loading" style="padding:16px">Loading\u2026</div></div>';
  html += '</div>';

  // - Events panel (schedule buttons + history)
  html += '<div class="sb-panel" id="evts-' + id + '" style="padding:18px">';
  html += '<div class="sb-section-lbl" style="margin-bottom:8px">Schedule Event</div>';
  html += '<div style="display:grid;gap:8px;margin-bottom:14px">';
  html += '<button onclick="openScheduleEvent(\\'Mobile Massage Service\\')" style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:9px 12px;font-size:13px;font-weight:600;cursor:pointer;text-align:left">&#x1f486; Mobile Massage</button>';
  html += '<button onclick="openScheduleEvent(\\'Lunch and Learn\\')" style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:9px 12px;font-size:13px;font-weight:600;cursor:pointer;text-align:left">&#x1f37d;&#xfe0f; Lunch &amp; Learn</button>';
  html += '<button onclick="openScheduleEvent(\\'Health Assessment Screening\\')" style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:9px 12px;font-size:13px;font-weight:600;cursor:pointer;text-align:left">&#x1fa7a; Health Assessment</button>';
  html += '</div>';
  html += '<div class="sb-section-lbl" style="margin-bottom:8px">Event History</div>';
  html += '<div id="sb-evts-list-' + id + '"><div class="loading" style="padding:16px">Loading\u2026</div></div>';
  html += '</div>';

  // - Boxes panel (lazy load + place box form)
  html += '<div class="sb-panel" id="boxes-' + id + '" style="padding:18px">';
  html += '<div id="sb-boxes-list-' + id + '"><div class="loading" style="padding:16px">Loading\u2026</div></div>';
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:14px 0">';
  html += '<div class="sb-section-lbl" style="margin-bottom:8px">Place New Box</div>';
  html += '<div style="display:grid;gap:8px">';
  html += '<input type="text" id="sb-box-loc-' + id + '" placeholder="Location (e.g. Front desk, Break room)" onkeydown="if(event.key===\'Enter\'){{event.preventDefault();placeBoxDesktop(' + id + ');}}" style="background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:7px 10px;font-size:13px">';
  html += '<input type="text" id="sb-box-contact-' + id + '" placeholder="Contact person" onkeydown="if(event.key===\'Enter\'){{event.preventDefault();placeBoxDesktop(' + id + ');}}" style="background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:7px 10px;font-size:13px">';
  html += '<button onclick="placeBoxDesktop(' + id + ')" style="background:#059669;color:#fff;border:none;border-radius:7px;padding:7px 12px;cursor:pointer;font-size:12px;font-weight:600">Place Box</button>';
  html += '<div id="sb-box-st-' + id + '" style="font-size:11px;text-align:center;min-height:14px"></div>';
  html += '</div>';
  html += '</div>';

  }}  // end IS_ADMIN else block

  // ── Load last visit for field rep view ────────────────────────────────
  if (!IS_ADMIN) {{
    fetch('/api/data/' + ACTS_TID).then(r => r.json()).then(acts => {{
      const mine = (acts || []).filter(a => {{
        const lf = a['Business'];
        return Array.isArray(lf) ? lf.some(r => r.id === id) : false;
      }}).sort((a,b) => (b['Date']||'').localeCompare(a['Date']||''));
      const el = document.getElementById('sb-last-visit-' + id);
      if (el && mine.length) {{
        const last = mine[0];
        const type = sv(last['Type']) || 'Visit';
        const outcome = sv(last['Outcome']) || '';
        const date = last['Date'] || '';
        el.innerHTML = '<div style="font-size:12px"><strong>' + esc(type) + '</strong>'
          + (outcome ? ' \u2014 ' + esc(outcome) : '') + '</div>'
          + '<div style="font-size:11px;color:var(--text3)">' + esc(date) + '</div>';
      }} else if (el) {{
        el.innerHTML = '<div style="font-size:12px;color:var(--text3)">No visits yet</div>';
      }}
    }});
  }}

  const wasOpen = sb.classList.contains('open');
  if (wasOpen) {{
    // Switching between businesses — fade content
    sb.innerHTML = '<div class="sb-content fading">' + html + '</div>';
    requestAnimationFrame(() => {{
      const c = sb.querySelector('.sb-content');
      if (c) c.classList.remove('fading');
    }});
  }} else {{
    // Opening fresh
    sb.innerHTML = '<div class="sb-content">' + html + '</div>';
    sb.classList.add('open');
  }}
}}

// --- Tab switching ---------------------------------------------------------
function sbTab(el, panelId) {{
  const sb = document.getElementById('map-sidebar');
  sb.querySelectorAll('.sb-tab').forEach(t => t.classList.remove('active'));
  sb.querySelectorAll('.sb-panel').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  document.getElementById(panelId).classList.add('active');
  if (panelId.startsWith('acts-')) loadGorActs(parseInt(panelId.replace('acts-','')));
  if (panelId.startsWith('evts-')) loadGorEvts(parseInt(panelId.replace('evts-','')));
  if (panelId.startsWith('boxes-')) loadGorBoxes(parseInt(panelId.replace('boxes-','')));
}}

async function loadGorBoxes(id) {{
  const el = document.getElementById('sb-boxes-list-' + id);
  if (!el) return;
  el.dataset.loaded = '1';
  // Force fresh fetch: /api/data/{{tid}} has 120s cache but we just wrote data.
  // fetchAll hits that endpoint; the endpoint reads hub_cache which we invalidate
  // server-side on every write, so it's fine.
  const boxes = await fetchAll({T_GOR_BOXES});
  const mine = boxes.filter(b => {{
    const biz = b['Business'];
    return Array.isArray(biz) && biz.some(r => r.id === id);
  }});
  if (!mine.length) {{ el.innerHTML = '<div style="color:var(--text3);font-size:12px;padding:4px 0">No massage boxes placed</div>'; return; }}
  el.innerHTML = mine.map(b => {{
    const st = sv(b['Status']) || '';
    const sc = st === 'Active' ? '#059669' : st === 'Picked Up' ? '#3b82f6' : '#475569';
    const loc = b['Location Notes'] || '';
    const contactP = b['Contact Person'] || '';
    const pickupDays = parseInt(b['Pickup Days']) || 14;
    let timerBadge = '';
    if (st === 'Active' && b['Date Placed']) {{
      const age = -(daysUntil(b['Date Placed']) || 0);
      if (age >= pickupDays * 2) timerBadge = '<span style="background:#ef444420;color:#ef4444;border-radius:4px;padding:2px 6px;font-size:10px;font-weight:600;margin-left:6px">' + age + 'd - Action needed</span>';
      else if (age >= pickupDays) timerBadge = '<span style="background:#f59e0b20;color:#f59e0b;border-radius:4px;padding:2px 6px;font-size:10px;font-weight:600;margin-left:6px">' + age + 'd - Follow up</span>';
      else timerBadge = '<span style="background:#05966920;color:#059669;border-radius:4px;padding:2px 6px;font-size:10px;font-weight:600;margin-left:6px">' + age + 'd</span>';
    }}

    // Data for the inline edit form (JSON-escaped so re-renders work)
    const dataAttrs =
        ' data-box-id="' + b.id + '"'
      + ' data-box-venue="' + id + '"'
      + ' data-box-loc="' + (loc.replace(/"/g, '&quot;')) + '"'
      + ' data-box-contact="' + (contactP.replace(/"/g, '&quot;')) + '"'
      + ' data-box-days="' + pickupDays + '"';

    // Display view
    const displayHTML =
        '<div id="box-view-' + b.id + '">'
      + '<div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px">'
      +   '<span style="background:'+sc+'20;color:'+sc+';border-radius:4px;padding:2px 6px;font-size:11px;font-weight:600">'+esc(st)+'</span>'
      +   timerBadge
      + '</div>'
      + (b['Date Placed'] ? '<div class="sb-act-meta">Placed '+esc(fmt(b['Date Placed'])) + (loc ? ' \u2022 ' + esc(loc) : '') + '</div>' : '')
      + (contactP ? '<div class="sb-act-meta">Contact: '+esc(contactP)+'</div>' : '')
      + '<div class="sb-act-meta">Pickup in ' + pickupDays + 'd</div>'
      + (b['Date Removed'] ? '<div class="sb-act-meta">Removed ' + esc(fmt(b['Date Removed'])) + '</div>' : '')
      + (b['Leads Generated'] ? '<div class="sb-act-meta">'+b['Leads Generated']+' leads</div>' : '')
      // Action row
      + '<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap">'
      +   (st === 'Active'
            ? '<button onclick="pickupBoxFromSidebar(' + b.id + ',' + id + ')" style="background:#3b82f6;color:#fff;border:none;border-radius:5px;padding:4px 10px;font-size:11px;font-weight:600;cursor:pointer">\u2713 Pick Up</button>'
            : '')
      +   '<button onclick="editBoxFromSidebar(' + b.id + ')" style="background:none;border:1px solid var(--border);color:var(--text3);border-radius:5px;padding:4px 10px;font-size:11px;font-weight:600;cursor:pointer">Edit</button>'
      + '</div>'
      + '</div>';

    // Inline edit view (hidden until Edit clicked)
    const editHTML =
        '<div id="box-edit-' + b.id + '" style="display:none"' + dataAttrs + '>'
      + '<div style="display:grid;gap:6px">'
      +   '<input type="text" id="be-loc-' + b.id + '" placeholder="Location" style="background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:5px;padding:5px 8px;font-size:12px">'
      +   '<input type="text" id="be-contact-' + b.id + '" placeholder="Contact person" style="background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:5px;padding:5px 8px;font-size:12px">'
      +   '<div style="display:flex;align-items:center;gap:6px">'
      +     '<span style="font-size:11px;color:var(--text3)">Pickup in</span>'
      +     '<input type="number" id="be-days-' + b.id + '" min="1" max="90" style="width:50px;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:5px;padding:4px 6px;font-size:12px;text-align:center">'
      +     '<span style="font-size:11px;color:var(--text3)">days</span>'
      +   '</div>'
      +   '<div style="display:flex;gap:6px">'
      +     '<button onclick="saveBoxEdit(' + b.id + ',' + id + ')" style="background:#059669;color:#fff;border:none;border-radius:5px;padding:5px 12px;font-size:11px;font-weight:600;cursor:pointer">Save</button>'
      +     '<button onclick="cancelBoxEdit(' + b.id + ')" style="background:none;border:1px solid var(--border);color:var(--text3);border-radius:5px;padding:5px 12px;font-size:11px;font-weight:600;cursor:pointer">Cancel</button>'
      +     '<span id="be-st-' + b.id + '" style="font-size:10px;align-self:center"></span>'
      +   '</div>'
      + '</div>'
      + '</div>';

    return '<div class="sb-act-item">' + displayHTML + editHTML + '</div>';
  }}).join('');
}}

function editBoxFromSidebar(boxId) {{
  const view = document.getElementById('box-view-' + boxId);
  const edit = document.getElementById('box-edit-' + boxId);
  if (!view || !edit) return;
  // Pre-fill from data attributes
  document.getElementById('be-loc-' + boxId).value     = edit.dataset.boxLoc || '';
  document.getElementById('be-contact-' + boxId).value = edit.dataset.boxContact || '';
  document.getElementById('be-days-' + boxId).value    = edit.dataset.boxDays || '14';
  view.style.display = 'none';
  edit.style.display = 'block';
  setTimeout(() => document.getElementById('be-loc-' + boxId).focus(), 30);
}}

function cancelBoxEdit(boxId) {{
  const view = document.getElementById('box-view-' + boxId);
  const edit = document.getElementById('box-edit-' + boxId);
  if (view) view.style.display = 'block';
  if (edit) edit.style.display = 'none';
}}

async function saveBoxEdit(boxId, venueId) {{
  const loc     = document.getElementById('be-loc-' + boxId).value.trim();
  const contact = document.getElementById('be-contact-' + boxId).value.trim();
  const days    = parseInt(document.getElementById('be-days-' + boxId).value, 10) || 14;
  const st      = document.getElementById('be-st-' + boxId);
  if (st) {{ st.style.color='var(--text3)'; st.textContent = 'Saving\u2026'; }}
  try {{
    const r = await fetch('/api/guerilla/boxes/' + boxId, {{
      method: 'PATCH', headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{location: loc, contact_person: contact, pickup_days: days}})
    }});
    const d = await r.json();
    if (d.ok) {{
      const el = document.getElementById('sb-boxes-list-' + venueId);
      if (el) el.dataset.loaded = '';
      loadGorBoxes(venueId);
    }} else {{
      if (st) {{ st.style.color='#ef4444'; st.textContent = 'Error: ' + (d.error||'Unknown'); }}
    }}
  }} catch(e) {{
    if (st) {{ st.style.color='#ef4444'; st.textContent = 'Network error'; }}
  }}
}}

async function pickupBoxFromSidebar(boxId, venueId) {{
  if (!confirm('Mark this box as picked up?')) return;
  try {{
    const r = await fetch('/api/guerilla/boxes/' + boxId + '/pickup', {{method: 'PATCH'}});
    const d = await r.json();
    if (d.ok) {{
      const el = document.getElementById('sb-boxes-list-' + venueId);
      if (el) el.dataset.loaded = '';
      loadGorBoxes(venueId);
    }} else {{
      alert('Pickup failed: ' + (d.error || 'Unknown'));
    }}
  }} catch(e) {{
    alert('Network error during pickup');
  }}
}}

async function placeBoxDesktop(venueId) {{
  const loc = document.getElementById('sb-box-loc-' + venueId).value.trim();
  const contact = document.getElementById('sb-box-contact-' + venueId).value.trim();
  const st = document.getElementById('sb-box-st-' + venueId);
  if (!loc) {{ alert('Please enter the box location.'); return; }}
  if (st) st.textContent = 'Saving\u2026';
  try {{
    const r = await fetch('/api/guerilla/boxes', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{venue_id: venueId, location: loc, contact_person: contact}})
    }});
    const d = await r.json();
    if (d.ok) {{
      if (st) {{ st.style.color = '#059669'; st.textContent = 'Box placed \u2713'; }}
      document.getElementById('sb-box-loc-' + venueId).value = '';
      document.getElementById('sb-box-contact-' + venueId).value = '';
      // Reload boxes
      const el = document.getElementById('sb-boxes-list-' + venueId);
      if (el) el.dataset.loaded = '';
      loadGorBoxes(venueId);
      setTimeout(() => {{ if(st) st.textContent=''; }}, 3000);
    }} else {{
      if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Error: ' + (d.error||'Unknown'); }}
    }}
  }} catch(e) {{
    if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Network error'; }}
  }}
}}

function toggleStatusPicker(id) {{
  const sel = document.getElementById('sb-stat-sel-' + id);
  sel.style.display = sel.style.display === 'block' ? 'none' : 'block';
}}

function toggleEvtMenu(id) {{
  const m = document.getElementById('evt-menu-' + id);
  if (m) m.style.display = m.style.display === 'block' ? 'none' : 'block';
}}
// Close event menu when clicking elsewhere
document.addEventListener('click', function(e) {{
  if (!e.target.closest('[id^="evt-menu"]') && !e.target.closest('[id^="evt-menu-btn"]')) {{
    document.querySelectorAll('[id^="evt-menu-"]').forEach(function(m) {{ if (m.id.indexOf('btn') === -1) m.style.display = 'none'; }});
  }}
}});

async function updateGorStatus(id, val) {{
  const v = _venues.find(x => x.id === id);
  if (v) v['Contact Status'] = {{value: val}};
  if (_markerMap[id]) _markerMap[id].setIcon(_pinIcon(_pinColor(val)));
  const statColors = {{'Not Contacted':'#4285f4','Contacted':'#fbbc04','In Discussion':'#ff9800','Active Partner':'#34a853'}};
  const badge  = document.getElementById('sb-stat-badge-' + id);
  const saveEl = document.getElementById('sb-stat-save-' + id);
  const sel    = document.getElementById('sb-stat-sel-' + id);
  if (badge)  {{ badge.style.color = statColors[val] || '#64748b'; badge.innerHTML = '&#x25CF; ' + esc(val); }}
  if (saveEl) saveEl.textContent = 'Saving\u2026';
  if (sel)    sel.style.display = 'none';
  const r = await bpatch(VENUES_TID, id, {{'Contact Status': {{value: val}}}});
  if (saveEl) {{ saveEl.textContent = r.ok ? '\u2713' : '\u2717'; setTimeout(() => {{ if(saveEl) saveEl.textContent=''; }}, 2000); }}
}}

async function saveFollowUp(id) {{
  const val = (document.getElementById('sb-fu-' + id) || {{}}).value || null;
  const v = _venues.find(x => x.id === id);
  if (v) v['Follow-Up Date'] = val;
  const st = document.getElementById('sb-fu-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  const r = await bpatch(VENUES_TID, id, {{'Follow-Up Date': val || null}});
  if (st) {{ st.textContent = r.ok ? '\u2713' : '\u2717'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
}}

async function addNote(id) {{
  const inputEl = document.getElementById('sb-note-in-' + id);
  const text = (inputEl ? inputEl.value : '').trim();
  if (!text) return;
  const today = new Date().toISOString().split('T')[0];
  const entry = '[' + today + '] ' + text;
  const v = _venues.find(x => x.id === id);
  const existing = (v && v['Notes'] ? v['Notes'].trim() : '');
  const newNotes = existing ? entry + '\\n---\\n' + existing : entry;
  if (v) v['Notes'] = newNotes;
  if (inputEl) inputEl.value = '';
  const logEl = document.getElementById('sb-notes-' + id);
  if (logEl) logEl.innerHTML = renderNotes(newNotes);
  const st = document.getElementById('sb-note-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  const r = await bpatch(VENUES_TID, id, {{'Notes': newNotes}});
  if (st) {{ st.textContent = r.ok ? 'Saved \u2713' : 'Failed \u2717'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
}}

// --- Lazy activity / event loaders -----------------------------------------
async function loadGorActs(id) {{
  const el = document.getElementById('sb-acts-list-' + id);
  if (!el || el.dataset.loaded) return;
  el.dataset.loaded = '1';
  const url = BR + '/api/database/rows/table/' + ACTS_TID
    + '/?user_field_names=true&size=50&order_by=-Date&filter__Business__link_row_has=' + id;
  try {{
    const r = await fetch(url, {{headers: {{'Authorization': 'Token ' + BT}}}});
    const data = await r.json();
    const acts = (data.results || []).filter(a => !sv(a['Event Status']));
    el.innerHTML = acts.length
      ? acts.map(renderGorAct).join('')
      : '<div style="color:var(--text3);font-size:12px;padding:4px 0">No activities yet</div>';
  }} catch(e) {{ el.innerHTML = '<div style="color:var(--text3);font-size:12px">Failed to load</div>'; }}
}}

async function loadGorEvts(id) {{
  const el = document.getElementById('sb-evts-list-' + id);
  if (!el || el.dataset.loaded) return;
  el.dataset.loaded = '1';
  const url = BR + '/api/database/rows/table/' + ACTS_TID
    + '/?user_field_names=true&size=20&order_by=-Date&filter__Business__link_row_has=' + id;
  try {{
    const r = await fetch(url, {{headers: {{'Authorization': 'Token ' + BT}}}});
    const data = await r.json();
    const evts = (data.results || []).filter(a => !!sv(a['Event Status']));
    el.innerHTML = evts.length
      ? evts.map(renderGorEvt).join('')
      : '<div style="color:var(--text3);font-size:12px;padding:4px 0">No events logged for this venue</div>';
  }} catch(e) {{ el.innerHTML = '<div style="color:var(--text3);font-size:12px">Failed to load</div>'; }}
}}

function renderGorAct(a) {{
  const type    = sv(a['Type']) || 'Activity';
  const outcome = sv(a['Outcome']) || '';
  const date    = a['Date'] || '';
  const summary = a['Summary'] || '';
  return '<div class="sb-act-item">'
    + '<div class="sb-act-type">' + esc(type) + (outcome ? ' \u2014 ' + esc(outcome) : '') + '</div>'
    + '<div class="sb-act-meta">' + esc(date) + (summary ? ' \xb7 ' + esc(summary) : '') + '</div>'
    + '</div>';
}}

function renderGorEvt(a) {{
  const evStatus = sv(a['Event Status']) || '';
  const type     = sv(a['Type']) || 'Event';
  const date     = a['Date'] || '';
  const evColors = {{'Prospective':'#3b82f6','Approved':'#10b981','Scheduled':'#8b5cf6','Completed':'#64748b'}};
  const color    = evColors[evStatus] || '#64748b';
  return '<div class="sb-evt-item">'
    + '<div style="display:flex;align-items:center;gap:6px">'
    + '<span style="font-size:12px;font-weight:600">' + esc(type) + '</span>'
    + '<span style="font-size:10px;padding:2px 7px;border-radius:6px;background:' + color + '22;color:' + color + ';font-weight:600">' + esc(evStatus) + '</span>'
    + '</div>'
    + '<div class="sb-act-meta">' + esc(date) + '</div>'
    + '</div>';
}}

async function logGorActivity(id) {{
  const btn = document.getElementById('sb-abtn-' + id);
  const st  = document.getElementById('sb-act-st-' + id);
  if (btn) btn.disabled = true;
  if (st)  st.textContent = 'Saving\u2026';
  const date    = (document.getElementById('sb-adate-'    + id) || {{}}).value || null;
  const type    = (document.getElementById('sb-atype-'    + id) || {{}}).value || 'Other';
  const outcome = (document.getElementById('sb-aoutcome-' + id) || {{}}).value || '';
  const person  = (document.getElementById('sb-aperson-'  + id) || {{}}).value || '';
  const summary = (document.getElementById('sb-asummary-' + id) || {{}}).value || '';
  const fu      = (document.getElementById('sb-afu-'      + id) || {{}}).value || null;
  const payload = {{[ACTS_LINK]: [{{id}}], 'Date': date, 'Type': {{value: type}},
    'Outcome': {{value: outcome}}, 'Contact Person': person, 'Summary': summary, 'Follow-Up Date': fu || null}};
  try {{
    const r = await bpost(ACTS_TID, payload);
    if (r.ok) {{
      const listEl = document.getElementById('sb-acts-list-' + id);
      if (listEl) delete listEl.dataset.loaded;
      if (document.getElementById('sb-asummary-' + id)) document.getElementById('sb-asummary-' + id).value = '';
      if (document.getElementById('sb-aperson-'  + id)) document.getElementById('sb-aperson-'  + id).value = '';
      if (document.getElementById('sb-afu-'      + id)) document.getElementById('sb-afu-'      + id).value = '';
      if (fu) {{ const fuIn = document.getElementById('sb-fu-' + id); if (fuIn) {{ fuIn.value = fu; saveFollowUp(id); }} }}
      if (st) {{ st.textContent = 'Saved \u2713'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
    }} else {{ if (st) st.textContent = 'Failed \u2717'; }}
  }} catch(e) {{ if (st) st.textContent = 'Error: ' + e.message; }}
  if (btn) btn.disabled = false;
}}

async function load() {{
  _venues = await fetchAll(VENUES_TID);
  buildFilters();
  applyFilters();
  if (!_map) initMap(); else renderMarkers();
  stampRefresh();
}}

load();
"""
    # Inject GFR form JS + pre-fill helpers
    gfr_js = f"const GFR_USER = {repr(_uname)};\nconst TOOL = {{venuesT: {T_GOR_VENUES}}};\n"
    gfr_js += _GFR_JS + '\n' + _GFR_FORMS345_JS + '\n'
    gfr_js += """
// ── Map-specific: open External Event form pre-filled with selected venue ──
let _currentVenue = null;
function openLogEvent() {
  if (!_currentVenue) { s2Reset(); document.getElementById('gfr-form-s2').classList.add('open'); return; }
  s2Reset();
  var el;
  el = document.getElementById('s2-event-name'); if (el) el.value = _currentVenue[_nameField] || '';
  el = document.getElementById('s2-addr');       if (el) el.value = _currentVenue[_addrField] || '';
  el = document.getElementById('s2-org-phone');  if (el) el.value = _currentVenue[_phoneField] || '';
  document.getElementById('gfr-form-s2').classList.add('open');
}
function openScheduleEvent(formType) {
  if (!_currentVenue) { openGFRForm(formType); return; }
  openGFRForm(formType);
  var name = _currentVenue[_nameField] || '';
  var addr = _currentVenue[_addrField] || '';
  var phone = _currentVenue[_phoneField] || '';
  setTimeout(function() {
    ['s3','s4','s5'].forEach(function(p) {
      var c = document.getElementById(p + '-company'); if (c && !c.value) c.value = name;
      var a = document.getElementById(p + '-addr');    if (a && !a.value) a.value = addr;
      var ph = document.getElementById(p + '-phone');  if (ph && !ph.value) ph.value = phone;
    });
  }, 50);
}
"""
    js = gfr_js + js
    return _page('gorilla_map', 'Guerilla Marketing Directory', header, body, js, br, bt, user=user)

