"""
Route Planner — Unified map combining Attorney, Guerilla, and Community venues.
Admin-only view with layers, action queue, and route builder.
"""
import os

from .shared import (
    _page, _is_admin, _TEMPLATES_JS,
    T_ATT_VENUES, T_ATT_ACTS,
    T_GOR_VENUES, T_GOR_ACTS, T_GOR_BOXES, T_GOR_ROUTES, T_GOR_ROUTE_STOPS,
    T_COM_VENUES, T_COM_ACTS,
    T_PI_ACTIVE, T_PI_BILLED, T_PI_AWAITING, T_PI_CLOSED,
)
from .guerilla import (
    _GFR_CSS, _GFR_HTML, _GFR_FORMS345_HTML, _GFR_FORM2_HTML,
    _GFR_JS, _GFR_FORMS345_JS,
    GFR_EXTRA_HTML, GFR_EXTRA_JS,
)


# ===========================================================================
# Route Planner Page
# ===========================================================================
def _route_planner_page(br: str, bt: str, user: dict = None) -> str:
    gk = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    admin = _is_admin(user or {})
    _uname = (user or {}).get('name', '')
    _uemail = (user or {}).get('email', '')

    header = ''
    body = (
        '<style>'
        'html,body{overflow:hidden;height:100%;margin:0;}'
        'body{display:flex;flex-direction:column;}'
        '.main{flex:1;display:flex;flex-direction:column;overflow:hidden;min-height:0;}'
        '.content{padding:0 !important;flex:1;display:flex;flex-direction:column;min-height:0;overflow:hidden;}'
        '#rp-wrap{flex:1;min-height:0;}'
        '#gmap{width:100%;height:100%;}'
        '</style>'
        + _GFR_CSS
        + _GFR_HTML
        + _GFR_FORMS345_HTML
        + _GFR_FORM2_HTML
        + '<style>'
        '#rp-left{width:300px;overflow-y:auto;background:var(--bg2);border-right:1px solid var(--border);padding:0;flex-shrink:0;}'
        '.rp-section{padding:14px 16px;border-bottom:1px solid var(--border);}'
        '.rp-section-title{font-size:11px;font-weight:700;text-transform:uppercase;color:var(--text3);margin-bottom:10px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;}'
        '.rp-check{display:flex;align-items:center;gap:6px;font-size:13px;color:var(--text2);margin-bottom:6px;cursor:pointer;}'
        '.rp-check input[type="checkbox"]{accent-color:#ea580c;}'
        '.rp-action-item{padding:8px 10px;border-radius:6px;cursor:pointer;font-size:12px;margin-bottom:4px;background:var(--card);border:1px solid var(--border);}'
        '.rp-action-item:hover{border-color:var(--text3);}'
        '.rp-stop-item{padding:8px 10px;border-radius:6px;font-size:13px;margin-bottom:4px;background:var(--card);border:1px solid var(--border);display:flex;align-items:center;gap:8px;cursor:grab;}'
        '.rp-stop-item.dragging{opacity:0.4;}'
        '.rp-stop-num{width:22px;height:22px;border-radius:50%;background:#ea580c;color:#fff;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;}'
        '.rp-badge{display:inline-block;font-size:10px;font-weight:600;padding:2px 6px;border-radius:4px;margin-right:4px;}'
        '#map-sidebar{width:380px;overflow-y:auto;overflow-x:hidden;background:var(--bg2);'
        'border-left:1px solid var(--border);padding:0;flex-shrink:0;'
        'transform:translateX(100%);opacity:0;position:absolute;right:0;top:0;bottom:0;'
        'transition:transform .25s ease,opacity .2s ease;z-index:10;}'
        '#map-sidebar.open{transform:translateX(0);opacity:1;}'
        '#map-sidebar .sb-content{transition:opacity .15s ease;}'
        '#map-sidebar .sb-content.fading{opacity:0;}'
        '</style>'
        '<div id="rp-wrap" style="display:flex;position:relative;overflow:hidden;max-width:100vw">'
        # Left panel
        '<div id="rp-left">'
        # Search
        '<div class="rp-section" style="padding:10px 16px">'
        '<input type="text" id="rp-search" placeholder="Search venues\u2026" '
        'oninput="applyFilters()" style="width:100%;background:var(--input-bg);border:1px solid var(--border);'
        'color:var(--text);border-radius:7px;padding:8px 12px;font-size:13px;box-sizing:border-box">'
        '</div>'
        # Layers
        '<div class="rp-section" id="rp-layers">'
        '<div class="rp-section-title" onclick="toggleSection(this)">Layers <span>&#x25BE;</span></div>'
        '<div class="rp-section-body">'
        '<label class="rp-check"><input type="checkbox" data-layer="gorilla" onchange="applyFilters()"><span style="color:#ea580c;font-weight:600">&#x25CF;</span> Guerilla (orange)</label>'
        '<label class="rp-check"><input type="checkbox" checked data-layer="attorney" onchange="applyFilters()"><span style="color:#7c3aed;font-weight:600">&#x25CF;</span> Attorney (purple)</label>'
        '<label class="rp-check"><input type="checkbox" data-layer="community" onchange="applyFilters()"><span style="color:#059669;font-weight:600">&#x25CF;</span> Community (green)</label>'
        '</div></div>'
        # Status Filters
        '<div class="rp-section" id="rp-filters">'
        '<div class="rp-section-title" onclick="toggleSection(this)">Status Filters <span>&#x25BE;</span></div>'
        '<div class="rp-section-body">'
        '<label class="rp-check"><input type="checkbox" data-status="Not Contacted" onchange="applyFilters()"> Not Contacted</label>'
        '<label class="rp-check"><input type="checkbox" data-status="Contacted" onchange="applyFilters()"> Contacted</label>'
        '<label class="rp-check"><input type="checkbox" checked data-status="In Discussion" onchange="applyFilters()"> In Discussion</label>'
        '<label class="rp-check"><input type="checkbox" checked data-status="Active" onchange="applyFilters()"> Active</label>'
        '<label class="rp-check"><input type="checkbox" data-status="Previous" onchange="applyFilters()"> Previous Relationship</label>'
        '<hr style="border:none;border-top:1px solid var(--border);margin:8px 0">'
        '<label class="rp-check"><input type="checkbox" id="rp-overdue-chk" onchange="applyFilters()"> Overdue Follow-Ups</label>'
        '<label class="rp-check"><input type="checkbox" id="rp-box-alert-chk" onchange="applyFilters()"> Box Alerts</label>'
        '</div></div>'
        # Action Needed
        '<div class="rp-section" id="rp-actions">'
        '<div class="rp-section-title" onclick="toggleSection(this)">Action Needed <span id="rp-action-count" style="font-size:10px;background:#ef4444;color:#fff;border-radius:8px;padding:1px 7px;min-width:16px;text-align:center">0</span> <span>&#x25BE;</span></div>'
        '<div class="rp-section-body" id="rp-action-list" style="max-height:240px;overflow-y:auto">'
        '<div style="font-size:12px;color:var(--text3);padding:4px 0">Loading\u2026</div>'
        '</div></div>'
        # Route Builder
        '<div class="rp-section" id="rp-route">'
        '<div class="rp-section-title" onclick="toggleSection(this)">Route Builder <span>&#x25BE;</span></div>'
        '<div class="rp-section-body">'
        '<button id="rp-route-toggle" onclick="toggleRouteMode()" '
        'style="width:100%;padding:8px;border-radius:7px;border:1px solid var(--border);'
        'background:var(--card);color:var(--text);font-size:13px;font-weight:600;cursor:pointer;margin-bottom:10px">'
        'Build Route</button>'
        '<div id="rp-route-form" style="display:none">'
        '<input type="text" id="rp-route-name" placeholder="Route name" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:7px 10px;font-size:12px;margin-bottom:6px;box-sizing:border-box">'
        '<input type="date" id="rp-route-date" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:7px 10px;font-size:12px;margin-bottom:6px;box-sizing:border-box">'
        '<input type="email" id="rp-route-assign" placeholder="Assign to (email)" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:7px 10px;font-size:12px;margin-bottom:10px;box-sizing:border-box">'
        '<div id="rp-stop-list"></div>'
        '<div style="display:flex;gap:6px;margin-top:8px">'
        '<button onclick="saveRoute()" style="flex:1;background:#3b82f6;color:#fff;border:none;border-radius:7px;padding:8px;font-size:12px;font-weight:600;cursor:pointer">Save Route</button>'
        '<button onclick="clearRoute()" style="flex:1;background:var(--card);color:var(--text2);border:1px solid var(--border);border-radius:7px;padding:8px;font-size:12px;cursor:pointer">Clear</button>'
        '</div>'
        '<div id="rp-route-status" style="font-size:11px;text-align:center;margin-top:6px;min-height:16px"></div>'
        '</div></div></div>'
        # Count bar
        '<div style="padding:10px 16px;font-size:11px;color:var(--text3)" id="rp-count-bar">Loading\u2026</div>'
        '</div>'
        # Center map
        '<div id="gmap" style="flex:1;height:100%"></div>'
        # Right sidebar
        '<div id="map-sidebar"></div>'
        '</div>'
    )

    js = f"""
const GK = '{gk}';
// IS_ADMIN is set by page shell
const OFFICE_LAT = 33.9478, OFFICE_LNG = -118.1335;
const USER_EMAIL = '{_uemail}';

const ATT_TID  = {T_ATT_VENUES};
const ATT_ACTS = {T_ATT_ACTS};
const GOR_TID  = {T_GOR_VENUES};
const GOR_ACTS = {T_GOR_ACTS};
const BOX_TID  = {T_GOR_BOXES};
const COM_TID  = {T_COM_VENUES};
const COM_ACTS = {T_COM_ACTS};
const ROUTES_TID = {T_GOR_ROUTES};
const STOPS_TID  = {T_GOR_ROUTE_STOPS};
const PI_ACTIVE  = {T_PI_ACTIVE};
const PI_BILLED  = {T_PI_BILLED};
const PI_AWAITING = {T_PI_AWAITING};
const PI_CLOSED  = {T_PI_CLOSED};

const TOOLS = {{
  attorney:  {{tid:ATT_TID, actsTid:ATT_ACTS, link:'Law Firm',     nameField:'Law Firm Name', phoneField:'Phone Number',  addrField:'Law Office Address', color:'#7c3aed',
               activeStatus:'Active Relationship', stages:['Not Contacted','Contacted','In Discussion','Active Relationship']}},
  gorilla:   {{tid:GOR_TID, actsTid:GOR_ACTS, link:'Business',     nameField:'Name',           phoneField:'Phone',         addrField:'Address',            color:'#ea580c',
               activeStatus:'Active Partner', stages:['Not Contacted','Contacted','In Discussion','Active Partner']}},
  community: {{tid:COM_TID, actsTid:COM_ACTS, link:'Organization', nameField:'Name',           phoneField:'Phone',         addrField:'Address',            color:'#059669',
               activeStatus:'Active Partner', stages:['Not Contacted','Contacted','In Discussion','Active Partner']}}
}};

let _allVenues = [];
let _allBoxes = [];
let _firmCounts = {{}};
let _map = null;
let _markerMap = {{}};
let _selectedId = null;
let _currentVenue = null;
let _routeMode = false;
let _routeStops = [];
let _routeLine = null;
let _deepLinkPending = null;
let _dataReady = false;
let _mapReady = false;

// ─── Baserow write helpers ──────────────────────────────────────────────────
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

function _haversine(lat1, lng1, lat2, lng2) {{
  var R = 3958.8;
  var dLat = (lat2-lat1)*Math.PI/180;
  var dLng = (lng2-lng1)*Math.PI/180;
  var a = Math.sin(dLat/2)*Math.sin(dLat/2)
        + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)
        * Math.sin(dLng/2)*Math.sin(dLng/2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}}

// ─── Section toggle ─────────────────────────────────────────────────────────
function toggleSection(titleEl) {{
  const body = titleEl.parentElement.querySelector('.rp-section-body');
  if (!body) return;
  const hidden = body.style.display === 'none';
  body.style.display = hidden ? '' : 'none';
  const arrow = titleEl.querySelector('span:last-child');
  if (arrow) arrow.innerHTML = hidden ? '&#x25BE;' : '&#x25B8;';
}}

// ─── Firm counts for attorney case block ────────────────────────────────────
function normName(n) {{ return (n || '').toLowerCase().trim(); }}
function _getFirmName(p) {{
  const raw = p['Law Firm Name ONLY'] || p['Law Firm Name'] || p['Law Firm'] || '';
  if (!raw) return '';
  if (Array.isArray(raw)) return raw.length ? (raw[0].value || String(raw[0])) : '';
  if (typeof raw === 'object' && raw.value) return raw.value;
  return String(raw);
}}
function _lookupFirmCounts(name) {{
  const key = normName(name);
  if (_firmCounts[key]) return _firmCounts[key];
  for (const [k, v] of Object.entries(_firmCounts)) {{
    const shorter = key.length <= k.length ? key : k;
    const longer  = key.length <= k.length ? k   : key;
    if (shorter.length >= 8 && longer.includes(shorter)) return v;
  }}
  return {{}};
}}

// ─── Load all venues in parallel ────────────────────────────────────────────
async function loadAllVenues() {{
  const [att, gor, com, boxes] = await Promise.all([
    fetchAll(ATT_TID), fetchAll(GOR_TID), fetchAll(COM_TID), fetchAll(BOX_TID)
  ]);

  // Tag attorney venues
  att.forEach(v => {{
    v._tool = 'attorney';
    v._tid = ATT_TID;
    v._actsTid = ATT_ACTS;
    v._link = TOOLS.attorney.link;
    v._nameField = TOOLS.attorney.nameField;
    v._phoneField = TOOLS.attorney.phoneField;
    v._addrField = TOOLS.attorney.addrField;
  }});
  // Tag guerilla venues
  gor.forEach(v => {{
    v._tool = 'gorilla';
    v._tid = GOR_TID;
    v._actsTid = GOR_ACTS;
    v._link = TOOLS.gorilla.link;
    v._nameField = TOOLS.gorilla.nameField;
    v._phoneField = TOOLS.gorilla.phoneField;
    v._addrField = TOOLS.gorilla.addrField;
  }});
  // Tag community venues
  com.forEach(v => {{
    v._tool = 'community';
    v._tid = COM_TID;
    v._actsTid = COM_ACTS;
    v._link = TOOLS.community.link;
    v._nameField = TOOLS.community.nameField;
    v._phoneField = TOOLS.community.phoneField;
    v._addrField = TOOLS.community.addrField;
  }});

  _allVenues = [].concat(att, gor, com);
  _allBoxes = boxes;

  // Load PI case counts for attorney venues
  Promise.all([fetchAll(PI_ACTIVE), fetchAll(PI_BILLED), fetchAll(PI_AWAITING), fetchAll(PI_CLOSED)]).then(([a,b,w,c]) => {{
    const tally = (rows, key) => rows.forEach(r => {{
      const k = normName(_getFirmName(r));
      if (k) {{ _firmCounts[k] = _firmCounts[k] || {{active:0,billed:0,awaiting:0,settled:0}}; _firmCounts[k][key]++; }}
    }});
    tally(a,'active'); tally(b,'billed'); tally(w,'awaiting'); tally(c,'settled');
    applyFilters();
  }});

  applyFilters();
  buildActionList();
  stampRefresh();

  // Deep-link: parse URL params for venue preselection
  var params = new URLSearchParams(window.location.search);
  var dlTool = params.get('tool');
  var dlVenue = params.get('venue');
  if (dlTool && dlVenue) {{
    _deepLinkPending = {{tool: dlTool, venueId: parseInt(dlVenue)}};
  }}
  _dataReady = true;
  _tryDeepLink();
}}

function _tryDeepLink() {{
  if (!_deepLinkPending || !_dataReady || !_mapReady) return;
  var dl = _deepLinkPending;
  _deepLinkPending = null;
  // Enable ALL layer checkboxes and ALL status filters so venue is guaranteed visible
  document.querySelectorAll('#rp-layers input[data-layer]').forEach(function(cb) {{
    cb.checked = true;
  }});
  document.querySelectorAll('#rp-filters input[data-status]').forEach(function(cb) {{
    cb.checked = true;
  }});
  applyFilters();
  // Find the venue and open its detail
  var venue = _allVenues.find(function(v) {{
    return v.id === dl.venueId && v._tool === dl.tool;
  }});
  if (venue) {{
    showDetail(venue);
    var lat = parseFloat(venue['Latitude']), lng = parseFloat(venue['Longitude']);
    if (_map && lat && lng) {{
      _map.panTo({{lat: lat, lng: lng}});
      _map.setZoom(15);
    }}
  }}
  // Clean URL
  history.replaceState(null, '', '/outreach/planner');
}}

// ─── Google Maps ────────────────────────────────────────────────────────────
function initMap() {{
  if (!GK) {{
    document.getElementById('gmap').innerHTML = '<div style="padding:40px;text-align:center;color:var(--text3)">Google Maps API key not configured.</div>';
    return;
  }}
  window._mapReadyCb = function() {{
    _map = new google.maps.Map(document.getElementById('gmap'), {{
      center: {{lat: OFFICE_LAT, lng: OFFICE_LNG}}, zoom: 12,
      mapTypeControl: false, streetViewControl: false, clickableIcons: false,
      styles: [
        {{featureType:'poi',stylers:[{{visibility:'off'}}]}},
        {{featureType:'transit',stylers:[{{visibility:'off'}}]}},
        {{featureType:'administrative.neighborhood',stylers:[{{visibility:'off'}}]}},
        {{featureType:'administrative.locality',elementType:'labels.icon',stylers:[{{visibility:'off'}}]}}
      ]
    }});
    var _officeMarker = new google.maps.Marker({{
      position: {{lat: OFFICE_LAT, lng: OFFICE_LNG}}, map: _map,
      title: 'Reform Chiropractic (Home Office)',
      icon: {{ url: 'https://maps.google.com/mapfiles/ms/icons/red-dot.png' }}
    }});
    _officeMarker.addListener('click', function() {{
      if (_routeMode) {{
        addRouteStop({{
          _isOffice: true,
          id: 0, _tid: 0, _tool: 'office',
          _nameField: '_name', _addrField: '_addr',
          _name: 'Reform Chiropractic',
          _addr: '3816 E Florence Ave, Bell, CA 90201',
          Latitude: OFFICE_LAT, Longitude: OFFICE_LNG
        }});
      }}
    }});
    _mapReady = true;
    applyFilters();
    _tryDeepLink();
  }};
  const s = document.createElement('script');
  s.src = 'https://maps.googleapis.com/maps/api/js?key=' + GK + '&callback=_mapReadyCb';
  s.async = true;
  s.onerror = function() {{
    document.getElementById('gmap').innerHTML = '<div style="padding:40px;text-align:center;color:var(--text3)">Failed to load Google Maps. Check API key.</div>';
  }};
  document.head.appendChild(s);
}}

// ─── Pin helpers ────────────────────────────────────────────────────────────
function pinColor(v) {{
  const t = TOOLS[v._tool];
  return t ? t.color : '#9e9e9e';
}}
function _pinIcon(color, hasBoxAlert) {{
  return {{
    path: google.maps.SymbolPath.CIRCLE, scale: 7,
    fillColor: color, fillOpacity: 1,
    strokeColor: hasBoxAlert ? '#f59e0b' : '#fff',
    strokeWeight: hasBoxAlert ? 3 : 1
  }};
}}
function _pinIconSelected(color) {{
  return {{
    path: google.maps.SymbolPath.CIRCLE, scale: 14,
    fillColor: '#fff', fillOpacity: 1,
    strokeColor: color, strokeWeight: 4
  }};
}}
function _hasBoxAlert(v) {{
  if (v._tool !== 'gorilla') return false;
  return _allBoxes.some(b => {{
    const biz = b['Business'];
    if (!Array.isArray(biz) || !biz.some(r => r.id === v.id)) return false;
    if (sv(b['Status']) !== 'Active' || !b['Date Placed']) return false;
    const age = -(daysUntil(b['Date Placed']) || 0);
    const pickupDays = parseInt(b['Pickup Days']) || 14;
    return age >= pickupDays;
  }});
}}

// ─── Filter logic ───────────────────────────────────────────────────────────
function getActiveStatuses() {{
  const checked = [];
  document.querySelectorAll('#rp-filters input[data-status]').forEach(cb => {{
    if (cb.checked) checked.push(cb.dataset.status);
  }});
  return checked;
}}
function getActiveLayers() {{
  const checked = [];
  document.querySelectorAll('#rp-layers input[data-layer]').forEach(cb => {{
    if (cb.checked) checked.push(cb.dataset.layer);
  }});
  return checked;
}}
function _activeStatusMatch(v) {{
  // The "Active" checkbox should match tool-specific active status strings
  const t = TOOLS[v._tool];
  return t ? t.activeStatus : '';
}}

function applyFilters() {{
  const q = (document.getElementById('rp-search').value || '').toLowerCase();
  const layers = getActiveLayers();
  const statuses = getActiveStatuses();
  const overdueOnly = document.getElementById('rp-overdue-chk').checked;
  const boxAlertOnly = document.getElementById('rp-box-alert-chk').checked;
  const todayStr = new Date().toISOString().split('T')[0];
  let shown = 0;

  _allVenues.forEach(v => {{
    v._visible = false;
    if (!layers.includes(v._tool)) return;
    const name = (v[v._nameField] || '').toLowerCase();
    if (q && !name.includes(q)) return;
    const status = sv(v['Contact Status']);
    // Map status to checkbox value
    const activeStr = _activeStatusMatch(v);
    let statusMatch = false;
    if (statuses.includes('Active') && status === activeStr) statusMatch = true;
    if (statuses.includes('Not Contacted') && status === 'Not Contacted') statusMatch = true;
    if (statuses.includes('Contacted') && status === 'Contacted') statusMatch = true;
    if (statuses.includes('In Discussion') && status === 'In Discussion') statusMatch = true;
    // Also match unknown/empty as Not Contacted
    if (statuses.includes('Not Contacted') && !status) statusMatch = true;
    // Previous Relationship: attorney firms with only closed cases
    if (statuses.includes('Previous') && v._tool === 'attorney') {{
      const fc = _lookupFirmCounts(v[v._nameField] || '');
      if ((fc.settled || 0) > 0 && !(fc.active || 0) && !(fc.billed || 0) && !(fc.awaiting || 0)) statusMatch = true;
    }}
    if (!statusMatch) return;
    if (overdueOnly) {{
      const fu = v['Follow-Up Date'] || '';
      if (!fu || fu >= todayStr) return;
    }}
    if (boxAlertOnly) {{
      if (!_hasBoxAlert(v)) return;
    }}
    v._visible = true;
    shown++;
  }});

  const cb = document.getElementById('rp-count-bar');
  if (cb) cb.textContent = shown + ' of ' + _allVenues.length + ' venues shown';
  renderMarkers();
}}

// ─── Render markers ─────────────────────────────────────────────────────────
function renderMarkers() {{
  if (!_map) return;
  Object.values(_markerMap).forEach(m => m.setMap(null));
  _markerMap = {{}};
  _allVenues.forEach(v => {{
    if (!v._visible) return;
    const lat = parseFloat(v['Latitude']), lng = parseFloat(v['Longitude']);
    if (!lat || !lng) return;
    const color = pinColor(v);
    const alert = _hasBoxAlert(v);
    const marker = new google.maps.Marker({{
      position: {{lat, lng}}, map: _map,
      title: v[v._nameField] || '',
      icon: _pinIcon(color, alert)
    }});
    marker.addListener('click', () => {{
      if (_routeMode) {{
        addRouteStop(v);
      }} else {{
        showDetail(v);
      }}
    }});
    _markerMap[v.id + '_' + v._tool] = marker;
  }});
}}

// ─── Sidebar ────────────────────────────────────────────────────────────────
function _venueKey(v) {{ return v._isOffice ? 'office' : v.id + '_' + v._tool; }}

function closeSidebar() {{
  const sb = document.getElementById('map-sidebar');
  if (sb) sb.classList.remove('open');
  if (_selectedId && _markerMap[_selectedId]) {{
    const prev = _allVenues.find(x => _venueKey(x) === _selectedId);
    if (prev) _markerMap[_selectedId].setIcon(_pinIcon(pinColor(prev), _hasBoxAlert(prev)));
  }}
  _selectedId = null;
  _currentVenue = null;
}}

function showDetail(v) {{
  const sb = document.getElementById('map-sidebar');
  const key = _venueKey(v);
  const id = v.id;
  const tool = TOOLS[v._tool];

  // Deselect previous
  if (_selectedId && _selectedId !== key && _markerMap[_selectedId]) {{
    const prev = _allVenues.find(x => _venueKey(x) === _selectedId);
    if (prev) _markerMap[_selectedId].setIcon(_pinIcon(pinColor(prev), _hasBoxAlert(prev)));
  }}
  _selectedId = key;
  _currentVenue = v;
  if (_markerMap[key]) _markerMap[key].setIcon(_pinIconSelected(tool.color));

  // Center map on venue
  const lat = parseFloat(v['Latitude']), lng = parseFloat(v['Longitude']);
  if (_map && lat && lng) _map.panTo({{lat, lng}});

  const name     = esc(v[v._nameField] || '(unnamed)');
  const status   = sv(v['Contact Status']);
  const phone    = esc(v[v._phoneField] || '');
  const addr     = esc(v[v._addrField]  || '');
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

  // Build stages dropdown for this tool
  const stageOpts = tool.stages.map(s => '<option value="' + s + '"' + (status === s ? ' selected' : '') + '>' + s + '</option>').join('');

  let html = '';

  // Header
  html += '<div style="padding:16px 18px 10px">';
  html += '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">';
  html += '<div style="font-size:16px;font-weight:700;line-height:1.3;padding-right:10px">' + name + '</div>';
  html += '<button onclick="closeSidebar()" style="background:none;border:none;color:var(--text3);cursor:pointer;font-size:20px;line-height:1;flex-shrink:0">&times;</button>';
  html += '</div>';

  // Tool badge
  html += '<span class="rp-badge" style="background:' + tool.color + '22;color:' + tool.color + '">' + esc(v._tool === 'gorilla' ? 'Guerilla' : v._tool === 'attorney' ? 'Attorney' : 'Community') + '</span>';
  if (classif) html += '<span class="rp-badge" style="background:#1565C0;color:#fff">' + esc(classif) + '</span>';

  // Status badge
  html += '<div style="margin-top:8px;margin-bottom:10px">';
  html += '<span class="sb-status-badge" id="sb-stat-badge-' + key + '" onclick="toggleStatusPicker(\\'' + key + '\\')" style="color:' + tool.color + '">';
  html += '&#x25CF; ' + esc(status || 'Unknown') + '</span>';
  html += '<span id="sb-stat-save-' + key + '" style="font-size:11px;color:#34a853;margin-left:4px"></span>';
  html += '</div>';
  html += '<select class="sb-inline-select" id="sb-stat-sel-' + key + '" onchange="updateStatus(' + id + ',' + v._tid + ',this.value,\\'' + key + '\\')">' + stageOpts + '</select>';

  // Attorney case counts
  if (v._tool === 'attorney') {{
    const _fc = _lookupFirmCounts(v[v._nameField] || '');
    html += '<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:4px;margin:10px 0;'
      + 'background:var(--card);border-radius:8px;padding:10px;text-align:center">'
      + '<div><div style="font-size:16px;font-weight:700;color:#a78bfa">' + (_fc.active||0) + '</div>'
      + '<div style="font-size:10px;color:var(--text3)">Active</div></div>'
      + '<div><div style="font-size:16px;font-weight:700;color:#fbbf24">' + (_fc.billed||0) + '</div>'
      + '<div style="font-size:10px;color:var(--text3)">Billed</div></div>'
      + '<div><div style="font-size:16px;font-weight:700;color:#60a5fa">' + (_fc.awaiting||0) + '</div>'
      + '<div style="font-size:10px;color:var(--text3)">Awaiting</div></div>'
      + '<div><div style="font-size:16px;font-weight:700;color:#34d399">' + (_fc.settled||0) + '</div>'
      + '<div style="font-size:10px;color:var(--text3)">Settled</div></div>'
      + '<div><div style="font-size:16px;font-weight:700">' + ((_fc.active||0)+(_fc.billed||0)+(_fc.awaiting||0)+(_fc.settled||0)) + '</div>'
      + '<div style="font-size:10px;color:var(--text3)">Total</div></div></div>';
    if (_fc.active === 0 && ((_fc.billed||0)+(_fc.awaiting||0)+(_fc.settled||0)) > 0) {{
      html += '<span style="font-size:10px;padding:2px 6px;border-radius:4px;background:#7c3aed22;color:#a78bfa;font-weight:600">Previous Relationship</span>';
    }}
  }}

  // Tab bar
  html += '<div class="sb-tabs">';
  html += '<div class="sb-tab active" onclick="sbTab(this,\\'info-' + key + '\\')">Info</div>';
  html += '<div class="sb-tab" onclick="sbTab(this,\\'acts-' + key + '\\')">Activity</div>';
  html += '<div class="sb-tab" onclick="sbTab(this,\\'evts-' + key + '\\')">Events</div>';
  if (v._tool === 'gorilla') html += '<div class="sb-tab" onclick="sbTab(this,\\'boxes-' + key + '\\')">Boxes</div>';
  html += '</div>';

  // ── Info tab ──
  html += '<div class="sb-panel active" id="info-' + key + '" style="padding:18px">';
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

  // Follow-Up Date
  html += '<div class="sb-section-lbl" style="margin-bottom:8px">Follow-Up Date</div>';
  html += '<div style="display:flex;gap:8px;align-items:center;margin-bottom:14px">';
  html += '<input type="date" id="sb-fu-' + key + '" value="' + esc(fu) + '" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:7px 10px;font-size:13px">';
  html += '<button onclick="saveFollowUp(' + id + ',' + v._tid + ',\\'' + key + '\\')" style="background:#3b82f6;color:#fff;border:none;border-radius:7px;padding:7px 12px;cursor:pointer;font-size:12px;font-weight:600">Save</button>';
  html += '<span id="sb-fu-st-' + key + '" style="font-size:11px;color:#34a853;min-width:20px"></span></div>';
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:14px 0">';

  // Notes
  html += '<div class="sb-section-lbl" style="margin-bottom:8px">Notes</div>';
  html += '<div id="sb-notes-' + key + '" style="max-height:140px;overflow-y:auto;background:var(--card);border-radius:7px;padding:10px 12px;border:1px solid var(--border)">' + renderNotes(notesRaw) + '</div>';
  html += '<div style="display:flex;gap:8px;margin-top:8px">';
  html += '<input type="text" id="sb-note-in-' + key + '" placeholder="Add a note\u2026" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:7px 10px;font-size:13px">';
  html += '<button onclick="addNote(' + id + ',' + v._tid + ',\\'' + key + '\\')" style="background:#e94560;color:#fff;border:none;border-radius:7px;padding:7px 12px;cursor:pointer;font-size:12px;font-weight:600">Add</button>';
  html += '</div><div id="sb-note-st-' + key + '" style="font-size:11px;color:#34a853;margin-top:4px"></div>';
  html += '</div>';

  // ── Activity tab ──
  html += '<div class="sb-panel" id="acts-' + key + '" style="padding:14px">';
  html += '<button onclick="openLogEvent()" style="width:100%;background:#ea580c;color:#fff;border:none;border-radius:10px;padding:12px;font-size:14px;font-weight:700;cursor:pointer;margin-bottom:14px">\u270f\ufe0f Log Activity</button>';
  html += '<div class="sb-section-lbl" style="margin-bottom:8px">History</div>';
  html += '<div id="sb-acts-list-' + key + '"><div class="loading">Loading\u2026</div></div>';
  html += '</div>';

  // ── Events tab ──
  html += '<div class="sb-panel" id="evts-' + key + '" style="padding:18px">';
  html += '<div class="sb-section-lbl" style="margin-bottom:8px">Schedule Event</div>';
  html += '<div style="display:grid;gap:8px;margin-bottom:14px">';
  html += '<button onclick="openScheduleEvent(\\'Mobile Massage Service\\')" style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:9px 12px;font-size:13px;font-weight:600;cursor:pointer;text-align:left">&#x1f486; Mobile Massage</button>';
  html += '<button onclick="openScheduleEvent(\\'Lunch and Learn\\')" style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:9px 12px;font-size:13px;font-weight:600;cursor:pointer;text-align:left">&#x1f37d;&#xfe0f; Lunch &amp; Learn</button>';
  html += '<button onclick="openScheduleEvent(\\'Health Assessment Screening\\')" style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:9px 12px;font-size:13px;font-weight:600;cursor:pointer;text-align:left">&#x1fa7a; Health Assessment</button>';
  html += '</div>';

  // Promo Items section (venue-level, shown/edited inline)
  html += '<div id="promo-section-' + id + '" style="margin-bottom:14px;padding:12px 14px;background:#f59e0b10;border:1px solid #f59e0b30;border-radius:8px">';
  html += '<div class="sb-section-lbl" style="margin-bottom:8px;color:#f59e0b;font-weight:700">\U0001f4cb Bring to Events</div>';
  html += '<div id="promo-view-' + id + '">';
  html += '<div id="promo-display-' + id + '" style="font-size:13px;color:var(--text1);white-space:pre-wrap;margin-bottom:8px;min-height:18px"></div>';
  html += '<button onclick="editVenuePromo(' + id + ')" style="background:var(--bg2);border:1px solid var(--border);color:var(--text1);border-radius:7px;padding:6px 14px;font-size:12px;font-weight:600;cursor:pointer">&#x270e; Edit</button>';
  html += '</div>';
  html += '<div id="promo-edit-' + id + '" style="display:none">';
  html += '<textarea id="promo-input-' + id + '" placeholder="e.g. roller tool for demo, sample oils, brochures" rows="3" style="width:100%;box-sizing:border-box;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:10px 12px;font-size:13px;font-family:inherit;resize:vertical;min-height:64px;margin-bottom:8px"></textarea>';
  html += '<div style="display:flex;gap:6px;align-items:center">';
  html += '<button onclick="saveVenuePromo(' + id + ')" style="background:#059669;color:#fff;border:none;border-radius:7px;padding:8px 14px;font-size:12px;font-weight:700;cursor:pointer">Save</button>';
  html += '<button onclick="cancelVenuePromo(' + id + ')" style="background:var(--bg2);border:1px solid var(--border);color:var(--text1);border-radius:7px;padding:8px 14px;font-size:12px;font-weight:600;cursor:pointer">Cancel</button>';
  html += '<span id="promo-st-' + id + '" style="font-size:11px;color:var(--text3)"></span>';
  html += '</div></div></div>';

  html += '<div class="sb-section-lbl" style="margin-bottom:8px">Event History</div>';
  html += '<div id="sb-evts-list-' + key + '"><div class="loading">Loading\u2026</div></div>';
  html += '</div>';

  // ── Boxes tab (guerilla only) ──
  if (v._tool === 'gorilla') {{
    html += '<div class="sb-panel" id="boxes-' + key + '" style="padding:18px">';
    html += '<div id="sb-boxes-list-' + key + '"><div class="loading">Loading\u2026</div></div>';
    html += '<hr style="border:none;border-top:1px solid var(--border);margin:18px 0">';
    html += '<div class="sb-section-lbl" style="margin-bottom:10px;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:var(--text2)">Place New Box</div>';
    html += '<div style="display:grid;gap:10px">';
    html += '<input type="text" id="sb-box-loc-' + key + '" placeholder="Location (e.g. Front desk, Break room)" onkeydown="if(event.key===\\'Enter\\'){{event.preventDefault();placeBox(\\'' + key + '\\',' + id + ');}}" style="background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:11px 14px;font-size:14px">';
    html += '<input type="text" id="sb-box-contact-' + key + '" placeholder="Contact person" onkeydown="if(event.key===\\'Enter\\'){{event.preventDefault();placeBox(\\'' + key + '\\',' + id + ');}}" style="background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:11px 14px;font-size:14px">';
    html += '<button onclick="placeBox(\\'' + key + '\\',' + id + ')" style="background:#059669;color:#fff;border:none;border-radius:8px;padding:12px 18px;cursor:pointer;font-size:14px;font-weight:700;min-height:44px">Place Box</button>';
    html += '<div id="sb-box-st-' + key + '" style="font-size:12px;text-align:center;min-height:16px"></div>';
    html += '</div></div>';
  }}

  html += '</div>';  // close header padding

  // Render into sidebar
  const wasOpen = sb.classList.contains('open');
  if (wasOpen) {{
    sb.innerHTML = '<div class="sb-content fading">' + html + '</div>';
    requestAnimationFrame(() => {{
      const c = sb.querySelector('.sb-content');
      if (c) c.classList.remove('fading');
    }});
  }} else {{
    sb.innerHTML = '<div class="sb-content">' + html + '</div>';
    sb.classList.add('open');
  }}
}}

// ─── Tab switching ──────────────────────────────────────────────────────────
function sbTab(el, panelId) {{
  const sb = document.getElementById('map-sidebar');
  sb.querySelectorAll('.sb-tab').forEach(t => t.classList.remove('active'));
  sb.querySelectorAll('.sb-panel').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  const panel = document.getElementById(panelId);
  if (panel) panel.classList.add('active');
  if (panelId.startsWith('acts-'))  loadActs(panelId.replace('acts-',''));
  if (panelId.startsWith('evts-'))  loadEvts(panelId.replace('evts-',''));
  if (panelId.startsWith('boxes-')) loadBoxes(panelId.replace('boxes-',''));
}}

// ─── Status picker toggle ───────────────────────────────────────────────────
function toggleStatusPicker(key) {{
  const sel = document.getElementById('sb-stat-sel-' + key);
  if (sel) sel.style.display = sel.style.display === 'block' ? 'none' : 'block';
}}

// ─── Lazy loaders ───────────────────────────────────────────────────────────
async function loadActs(key) {{
  const el = document.getElementById('sb-acts-list-' + key);
  if (!el || el.dataset.loaded) return;
  el.dataset.loaded = '1';
  if (!_currentVenue) return;
  const v = _currentVenue;
  const url = BR + '/api/database/rows/table/' + v._actsTid
    + '/?user_field_names=true&size=50&order_by=-Date&filter__' + v._link + '__link_row_has=' + v.id;
  try {{
    const r = await fetch(url, {{headers: {{'Authorization': 'Token ' + BT}}}});
    const data = await r.json();
    const acts = (data.results || []).filter(a => !sv(a['Event Status']));
    el.innerHTML = acts.length
      ? acts.map(renderAct).join('')
      : '<div style="color:var(--text3);font-size:12px;padding:4px 0">No activities yet</div>';
  }} catch(e) {{ el.innerHTML = '<div style="color:var(--text3);font-size:12px">Failed to load</div>'; }}
}}

async function loadEvts(key) {{
  // Populate the venue-level Promo Items section at the same time
  if (_currentVenue && _currentVenue._tool === 'gorilla') {{
    const display = document.getElementById('promo-display-' + _currentVenue.id);
    if (display) {{
      const promo = (_currentVenue['Promo Items'] || '').trim();
      display.textContent = promo || '(nothing set — click Edit to add items)';
      if (!promo) display.style.color = 'var(--text3)';
      else display.style.color = 'var(--text1)';
    }}
  }}
  const el = document.getElementById('sb-evts-list-' + key);
  if (!el || el.dataset.loaded) return;
  el.dataset.loaded = '1';
  if (!_currentVenue) return;
  const v = _currentVenue;
  const url = BR + '/api/database/rows/table/' + v._actsTid
    + '/?user_field_names=true&size=20&order_by=-Date&filter__' + v._link + '__link_row_has=' + v.id;
  try {{
    const r = await fetch(url, {{headers: {{'Authorization': 'Token ' + BT}}}});
    const data = await r.json();
    const evts = (data.results || []).filter(a => !!sv(a['Event Status']));
    el.innerHTML = evts.length
      ? evts.map(renderEvt).join('')
      : '<div style="color:var(--text3);font-size:12px;padding:4px 0">No events logged</div>';
  }} catch(e) {{ el.innerHTML = '<div style="color:var(--text3);font-size:12px">Failed to load</div>'; }}
}}

async function loadBoxes(key) {{
  const el = document.getElementById('sb-boxes-list-' + key);
  if (!el) return;
  el.dataset.loaded = '1';
  if (!_currentVenue || _currentVenue._tool !== 'gorilla') return;
  const venueId = _currentVenue.id;
  const mine = _allBoxes.filter(b => {{
    const biz = b['Business'];
    return Array.isArray(biz) && biz.some(r => r.id === venueId);
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
      if (age >= pickupDays * 2) timerBadge = '<span style="background:#ef444420;color:#ef4444;border-radius:6px;padding:4px 10px;font-size:12px;font-weight:700;margin-left:8px">' + age + 'd \u2014 Action needed</span>';
      else if (age >= pickupDays) timerBadge = '<span style="background:#f59e0b20;color:#f59e0b;border-radius:6px;padding:4px 10px;font-size:12px;font-weight:700;margin-left:8px">' + age + 'd \u2014 Follow up</span>';
      else timerBadge = '<span style="background:#05966920;color:#059669;border-radius:6px;padding:4px 10px;font-size:12px;font-weight:700;margin-left:8px">' + age + 'd</span>';
    }}

    const dataAttrs =
        ' data-box-loc="' + (loc.replace(/"/g, '&quot;')) + '"'
      + ' data-box-contact="' + (contactP.replace(/"/g, '&quot;')) + '"'
      + ' data-box-days="' + pickupDays + '"';

    const displayHTML =
        '<div id="box-view-' + b.id + '">'
      + '<div style="display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:8px">'
      +   '<span style="background:'+sc+'20;color:'+sc+';border-radius:6px;padding:5px 12px;font-size:13px;font-weight:700">'+esc(st)+'</span>'
      +   timerBadge
      + '</div>'
      + (b['Date Placed'] ? '<div style="font-size:13px;color:var(--text2);margin-bottom:4px"><strong>Placed:</strong> ' + esc(fmt(b['Date Placed'])) + '</div>' : '')
      + (loc ? '<div style="font-size:13px;color:var(--text2);margin-bottom:4px"><strong>Location:</strong> ' + esc(loc) + '</div>' : '')
      + (contactP ? '<div style="font-size:13px;color:var(--text2);margin-bottom:4px"><strong>Contact:</strong> ' + esc(contactP) + '</div>' : '')
      + '<div style="font-size:13px;color:var(--text2);margin-bottom:4px"><strong>Pickup in:</strong> ' + pickupDays + ' days</div>'
      + (b['Date Removed'] ? '<div style="font-size:13px;color:var(--text2);margin-bottom:4px"><strong>Removed:</strong> ' + esc(fmt(b['Date Removed'])) + '</div>' : '')
      + (b['Leads Generated'] ? '<div style="font-size:13px;color:var(--text2);margin-bottom:4px"><strong>Leads:</strong> ' + b['Leads Generated'] + '</div>' : '')
      + '<div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">'
      +   (st === 'Active'
            ? '<button onclick="pickupBoxFromSidebar(' + b.id + ',' + venueId + ')" style="background:#3b82f6;color:#fff;border:none;border-radius:8px;padding:10px 16px;font-size:14px;font-weight:700;cursor:pointer;min-height:40px">\u2713 Pick Up</button>'
            : '')
      +   '<button onclick="editBoxFromSidebar(' + b.id + ')" style="background:var(--bg2);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:10px 16px;font-size:14px;font-weight:600;cursor:pointer;min-height:40px">\u270e Edit</button>'
      + '</div>'
      + '</div>';

    const editHTML =
        '<div id="box-edit-' + b.id + '" style="display:none"' + dataAttrs + '>'
      + '<div style="display:grid;gap:10px">'
      +   '<div><label style="font-size:11px;color:var(--text3);font-weight:600;display:block;margin-bottom:4px">Location</label><input type="text" id="be-loc-' + b.id + '" placeholder="Location" style="width:100%;box-sizing:border-box;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:10px 14px;font-size:14px"></div>'
      +   '<div><label style="font-size:11px;color:var(--text3);font-weight:600;display:block;margin-bottom:4px">Contact person</label><input type="text" id="be-contact-' + b.id + '" placeholder="Contact person" style="width:100%;box-sizing:border-box;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:10px 14px;font-size:14px"></div>'
      +   '<div style="display:flex;align-items:center;gap:8px">'
      +     '<span style="font-size:13px;color:var(--text3)">Pickup in</span>'
      +     '<input type="number" id="be-days-' + b.id + '" min="1" max="90" style="width:70px;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:8px 10px;font-size:14px;text-align:center">'
      +     '<span style="font-size:13px;color:var(--text3)">days</span>'
      +   '</div>'
      +   '<div style="display:flex;gap:8px;margin-top:4px">'
      +     '<button onclick="saveBoxEdit(' + b.id + ',' + venueId + ')" style="background:#059669;color:#fff;border:none;border-radius:8px;padding:10px 18px;font-size:14px;font-weight:700;cursor:pointer;min-height:40px">Save</button>'
      +     '<button onclick="cancelBoxEdit(' + b.id + ')" style="background:var(--bg2);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:10px 18px;font-size:14px;font-weight:600;cursor:pointer;min-height:40px">Cancel</button>'
      +     '<span id="be-st-' + b.id + '" style="font-size:12px;align-self:center"></span>'
      +   '</div>'
      + '</div>'
      + '</div>';

    return '<div class="sb-act-item" style="padding:14px 0;border-bottom:1px solid var(--border)">' + displayHTML + editHTML + '</div>';
  }}).join('');
}}

function editBoxFromSidebar(boxId) {{
  const view = document.getElementById('box-view-' + boxId);
  const edit = document.getElementById('box-edit-' + boxId);
  if (!view || !edit) return;
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
      _allBoxes = await fetchAll(BOX_TID);
      const el = document.getElementById('sb-boxes-list-' + venueId);
      if (el) el.dataset.loaded = '';
      loadBoxes(venueId);
    }} else {{
      if (st) {{ st.style.color='#ef4444'; st.textContent = 'Error: ' + (d.error||'Unknown'); }}
    }}
  }} catch(e) {{
    if (st) {{ st.style.color='#ef4444'; st.textContent = 'Network error'; }}
  }}
}}

function editVenuePromo(venueId) {{
  const view = document.getElementById('promo-view-' + venueId);
  const edit = document.getElementById('promo-edit-' + venueId);
  if (!view || !edit) return;
  const current = (_currentVenue && _currentVenue.id === venueId) ? (_currentVenue['Promo Items'] || '') : '';
  const input = document.getElementById('promo-input-' + venueId);
  if (input) input.value = current;
  view.style.display = 'none';
  edit.style.display = 'block';
  setTimeout(() => {{ if (input) input.focus(); }}, 30);
}}

function cancelVenuePromo(venueId) {{
  const view = document.getElementById('promo-view-' + venueId);
  const edit = document.getElementById('promo-edit-' + venueId);
  if (view) view.style.display = 'block';
  if (edit) edit.style.display = 'none';
}}

async function saveVenuePromo(venueId) {{
  const input = document.getElementById('promo-input-' + venueId);
  const st = document.getElementById('promo-st-' + venueId);
  if (!input) return;
  const newVal = input.value.trim();
  if (st) {{ st.style.color = 'var(--text3)'; st.textContent = 'Saving\u2026'; }}
  try {{
    const r = await fetch('/api/guerilla/venues/' + venueId, {{
      method: 'PATCH', headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{promo_items: newVal}})
    }});
    const d = await r.json();
    if (d.ok) {{
      // Update local venue cache so next open reflects the change
      if (_currentVenue && _currentVenue.id === venueId) _currentVenue['Promo Items'] = newVal;
      const display = document.getElementById('promo-display-' + venueId);
      if (display) {{
        display.textContent = newVal || '(nothing set — click Edit to add items)';
        display.style.color = newVal ? 'var(--text1)' : 'var(--text3)';
      }}
      cancelVenuePromo(venueId);
      if (st) st.textContent = '';
    }} else {{
      if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Error: ' + (d.error||'Unknown'); }}
    }}
  }} catch(e) {{
    if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Network error'; }}
  }}
}}

async function pickupBoxFromSidebar(boxId, venueId) {{
  if (!confirm('Mark this box as picked up?')) return;
  try {{
    const r = await fetch('/api/guerilla/boxes/' + boxId + '/pickup', {{method: 'PATCH'}});
    const d = await r.json();
    if (d.ok) {{
      _allBoxes = await fetchAll(BOX_TID);
      const el = document.getElementById('sb-boxes-list-' + venueId);
      if (el) el.dataset.loaded = '';
      loadBoxes(venueId);
    }} else {{
      alert('Pickup failed: ' + (d.error || 'Unknown'));
    }}
  }} catch(e) {{
    alert('Network error during pickup');
  }}
}}

// ─── Renderers ──────────────────────────────────────────────────────────────
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

function renderAct(a) {{
  const type = a['Type'] ? (typeof a['Type'] === 'object' ? a['Type'].value : a['Type']) : '';
  const outcome = a['Outcome'] ? (typeof a['Outcome'] === 'object' ? a['Outcome'].value : a['Outcome']) : '';
  const date = a['Date'] || '';
  const person = a['Contact Person'] || '';
  const summary = a['Summary'] || '';
  const fu = a['Follow-Up Date'] || '';
  return '<div style="padding:8px 14px;border-bottom:1px solid var(--border)">'
    + '<div style="display:flex;justify-content:space-between;margin-bottom:3px">'
    + '<span style="font-size:11px;font-weight:600;background:var(--badge-bg);padding:1px 6px;border-radius:4px">' + esc(type) + '</span>'
    + '<span style="font-size:11px;color:var(--text3)">' + esc(date) + '</span></div>'
    + (outcome ? '<div style="font-size:12px;color:var(--text2)">' + esc(outcome) + '</div>' : '')
    + (person  ? '<div style="font-size:11px;color:var(--text3)">with ' + esc(person) + '</div>' : '')
    + (summary ? '<div style="font-size:12px;margin-top:3px">' + esc(summary) + '</div>' : '')
    + (fu      ? '<div style="font-size:11px;color:#f59e0b;margin-top:2px">Follow-up: ' + esc(fu) + '</div>' : '')
    + '</div>';
}}

function renderEvt(a) {{
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

// ─── CRUD actions ───────────────────────────────────────────────────────────
async function addNote(id, tid, key) {{
  const inputEl = document.getElementById('sb-note-in-' + key);
  const text = (inputEl ? inputEl.value : '').trim();
  if (!text) return;
  const today = new Date().toISOString().split('T')[0];
  const entry = '[' + today + '] ' + text;
  const v = _allVenues.find(x => _venueKey(x) === key);
  const existing = (v && v['Notes'] ? v['Notes'].trim() : '');
  const newNotes = existing ? entry + '\\n---\\n' + existing : entry;
  if (v) v['Notes'] = newNotes;
  if (inputEl) inputEl.value = '';
  const logEl = document.getElementById('sb-notes-' + key);
  if (logEl) logEl.innerHTML = renderNotes(newNotes);
  const st = document.getElementById('sb-note-st-' + key);
  if (st) st.textContent = 'Saving\u2026';
  const r = await bpatch(tid, id, {{'Notes': newNotes}});
  if (st) {{ st.textContent = r.ok ? 'Saved \u2713' : 'Failed \u2717'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
}}

async function saveFollowUp(id, tid, key) {{
  const val = (document.getElementById('sb-fu-' + key) || {{}}).value || null;
  const v = _allVenues.find(x => _venueKey(x) === key);
  if (v) v['Follow-Up Date'] = val;
  const st = document.getElementById('sb-fu-st-' + key);
  if (st) st.textContent = 'Saving\u2026';
  const r = await bpatch(tid, id, {{'Follow-Up Date': val || null}});
  if (st) {{ st.textContent = r.ok ? '\u2713' : '\u2717'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
  buildActionList();
}}

async function updateStatus(id, tid, val, key) {{
  const v = _allVenues.find(x => _venueKey(x) === key);
  if (v) v['Contact Status'] = {{value: val}};
  const tool = v ? TOOLS[v._tool] : null;
  if (_markerMap[key]) _markerMap[key].setIcon(_pinIconSelected(tool ? tool.color : '#9e9e9e'));
  const badge  = document.getElementById('sb-stat-badge-' + key);
  const saveEl = document.getElementById('sb-stat-save-' + key);
  const sel    = document.getElementById('sb-stat-sel-' + key);
  if (badge && tool)  {{ badge.style.color = tool.color; badge.innerHTML = '&#x25CF; ' + esc(val); }}
  if (saveEl) saveEl.textContent = 'Saving\u2026';
  if (sel)    sel.style.display = 'none';
  const r = await bpatch(tid, id, {{'Contact Status': {{value: val}}}});
  if (saveEl) {{ saveEl.textContent = r.ok ? '\u2713' : '\u2717'; setTimeout(() => {{ if(saveEl) saveEl.textContent=''; }}, 2000); }}
}}

async function placeBox(key, venueId) {{
  const loc = (document.getElementById('sb-box-loc-' + key) || {{}}).value.trim();
  const contact = (document.getElementById('sb-box-contact-' + key) || {{}}).value.trim();
  const st = document.getElementById('sb-box-st-' + key);
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
      const locIn = document.getElementById('sb-box-loc-' + key);
      const conIn = document.getElementById('sb-box-contact-' + key);
      if (locIn) locIn.value = '';
      if (conIn) conIn.value = '';
      // Refresh boxes data
      _allBoxes = await fetchAll(BOX_TID);
      const el = document.getElementById('sb-boxes-list-' + key);
      if (el) {{ delete el.dataset.loaded; loadBoxes(key); }}
      buildActionList();
      setTimeout(() => {{ if(st) st.textContent=''; }}, 3000);
    }} else {{
      if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Error: ' + (d.error||'Unknown'); }}
    }}
  }} catch(e) {{
    if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Network error'; }}
  }}
}}

// ─── Action Needed ──────────────────────────────────────────────────────────
function buildActionList() {{
  const list = document.getElementById('rp-action-list');
  const countEl = document.getElementById('rp-action-count');
  const todayStr = new Date().toISOString().split('T')[0];
  let items = [];

  // Box alerts: gorilla venues with active boxes >= 14 days
  _allVenues.filter(v => v._tool === 'gorilla').forEach(v => {{
    _allBoxes.filter(b => {{
      const biz = b['Business'];
      return Array.isArray(biz) && biz.some(r => r.id === v.id);
    }}).forEach(b => {{
      if (sv(b['Status']) !== 'Active' || !b['Date Placed']) return;
      const age = -(daysUntil(b['Date Placed']) || 0);
      const pickupDays = parseInt(b['Pickup Days']) || 14;
      if (age >= pickupDays * 2) {{
        items.push({{v, priority: 0, reason: 'Box ' + age + 'd \u2014 action needed', color: '#ef4444'}});
      }} else if (age >= pickupDays) {{
        items.push({{v, priority: 2, reason: 'Box ' + age + 'd \u2014 follow up', color: '#f59e0b'}});
      }}
    }});
  }});

  // Overdue follow-ups
  _allVenues.forEach(v => {{
    const fu = v['Follow-Up Date'] || '';
    if (fu && fu < todayStr) {{
      const days = -(daysUntil(fu) || 0);
      items.push({{v, priority: 1, reason: 'Follow-up ' + days + 'd overdue', color: '#ef4444'}});
    }}
  }});

  // Not contacted venues (lower priority informational)
  // (skip for now to keep the list focused on actionable items)

  // Sort: priority 0 first (box 30d+), then 1 (overdue FU), then 2 (box 14d+)
  items.sort((a, b) => a.priority - b.priority);

  // Deduplicate by venue (keep highest priority)
  const seen = new Set();
  items = items.filter(item => {{
    const key = _venueKey(item.v);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }});

  if (countEl) countEl.textContent = items.length;

  if (!items.length) {{
    list.innerHTML = '<div style="font-size:12px;color:var(--text3);padding:4px 0">No actions needed right now.</div>';
    return;
  }}

  list.innerHTML = items.map(item => {{
    const v = item.v;
    const tool = TOOLS[v._tool];
    const name = esc(v[v._nameField] || '(unnamed)');
    const toolLabel = v._tool === 'gorilla' ? 'Guerilla' : v._tool === 'attorney' ? 'Attorney' : 'Community';
    return '<div class="rp-action-item" onclick="focusVenue(\\'' + _venueKey(v) + '\\')">'
      + '<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">'
      + '<span class="rp-badge" style="background:' + tool.color + '22;color:' + tool.color + '">' + toolLabel + '</span>'
      + '<span style="font-weight:600;color:var(--text)">' + name + '</span>'
      + '</div>'
      + '<div style="color:' + item.color + ';font-size:11px">' + item.reason + '</div>'
      + '</div>';
  }}).join('');
}}

function focusVenue(key) {{
  const v = _allVenues.find(x => _venueKey(x) === key);
  if (!v) return;
  const lat = parseFloat(v['Latitude']), lng = parseFloat(v['Longitude']);
  if (_map && lat && lng) {{
    _map.panTo({{lat, lng}});
    _map.setZoom(15);
  }}
  showDetail(v);
}}

// ─── Route Builder ──────────────────────────────────────────────────────────
function toggleRouteMode() {{
  _routeMode = !_routeMode;
  const btn = document.getElementById('rp-route-toggle');
  const form = document.getElementById('rp-route-form');
  if (_routeMode) {{
    btn.style.background = '#ea580c';
    btn.style.color = '#fff';
    btn.style.borderColor = '#ea580c';
    btn.textContent = 'Building Route \u2014 Click Pins to Add';
    form.style.display = 'block';
    // Set today's date by default
    const dateIn = document.getElementById('rp-route-date');
    if (dateIn && !dateIn.value) dateIn.value = new Date().toISOString().split('T')[0];
    const assignIn = document.getElementById('rp-route-assign');
    if (assignIn && !assignIn.value) assignIn.value = USER_EMAIL;
    closeSidebar();
  }} else {{
    btn.style.background = 'var(--card)';
    btn.style.color = 'var(--text)';
    btn.style.borderColor = 'var(--border)';
    btn.textContent = 'Build Route';
    form.style.display = 'none';
  }}
}}

function addRouteStop(v) {{
  const key = _venueKey(v);
  if (_routeStops.find(s => s.key === key)) return;  // already in route
  _routeStops.push({{
    key: key,
    id: v.id,
    tid: v._tid,
    tool: v._tool,
    name: v[v._nameField] || '(unnamed)',
    lat: parseFloat(v['Latitude']),
    lng: parseFloat(v['Longitude']),
    addr: v[v._addrField] || ''
  }});
  renderRouteStops();
}}

function removeRouteStop(key) {{
  _routeStops = _routeStops.filter(s => s.key !== key);
  renderRouteStops();
}}

function renderRouteStops() {{
  const list = document.getElementById('rp-stop-list');
  if (!list) return;
  // Office is always stop #1 (fixed, can't remove)
  var officeHtml = '<div class="rp-stop-item" style="opacity:0.85;cursor:default">'
    + '<div class="rp-stop-num" style="background:#1e3a5f">\u2726</div>'
    + '<div style="flex:1;min-width:0">'
    + '<div style="font-weight:600">Reform Chiropractic</div>'
    + '<div style="font-size:11px;color:var(--text3)">Start Point</div>'
    + '</div></div>';
  if (!_routeStops.length) {{
    list.innerHTML = officeHtml + '<div style="font-size:12px;color:var(--text3);padding:4px 0">Click pins on the map to add stops.</div>';
    drawRouteLine();
    return;
  }}
  list.innerHTML = officeHtml + _routeStops.map((s, i) => {{
    const toolColor = TOOLS[s.tool] ? TOOLS[s.tool].color : '#9e9e9e';
    const dist = _haversine(
      i === 0 ? OFFICE_LAT : (_routeStops[i-1].lat||0),
      i === 0 ? OFFICE_LNG : (_routeStops[i-1].lng||0),
      s.lat||0, s.lng||0
    );
    const distLabel = (s.lat && s.lng) ? ' \u2022 ' + dist.toFixed(1) + ' mi' : '';
    return '<div class="rp-stop-item" draggable="true" data-idx="' + i + '" '
      + 'ondragstart="onStopDragStart(event)" ondragover="onStopDragOver(event)" '
      + 'ondrop="onStopDrop(event)" ondragend="onStopDragEnd(event)">'
      + '<div class="rp-stop-num" style="background:' + toolColor + '">' + (i+1) + '</div>'
      + '<div style="flex:1;min-width:0">'
      + '<div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(s.name) + '</div>'
      + '<div style="font-size:11px;color:var(--text3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(s.addr) + distLabel + '</div>'
      + '</div>'
      + '<button onclick="removeRouteStop(\\'' + s.key + '\\')" style="background:none;border:none;color:var(--text3);cursor:pointer;font-size:16px;flex-shrink:0">&times;</button>'
      + '</div>';
  }}).join('');
  drawRouteLine();
}}

// ─── Drag-to-reorder ────────────────────────────────────────────────────────
let _dragIdx = null;
function onStopDragStart(e) {{
  _dragIdx = parseInt(e.currentTarget.dataset.idx);
  e.currentTarget.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
}}
function onStopDragOver(e) {{
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
}}
function onStopDrop(e) {{
  e.preventDefault();
  const target = parseInt(e.currentTarget.dataset.idx);
  if (_dragIdx === null || _dragIdx === target) return;
  const item = _routeStops.splice(_dragIdx, 1)[0];
  _routeStops.splice(target, 0, item);
  renderRouteStops();
}}
function onStopDragEnd(e) {{
  e.currentTarget.classList.remove('dragging');
  _dragIdx = null;
}}

// ─── Route polyline ─────────────────────────────────────────────────────────
function drawRouteLine() {{
  if (_routeLine) {{ _routeLine.setMap(null); _routeLine = null; }}
  if (!_map || !_routeStops.length) return;
  // Always start from office
  const path = [{{lat: OFFICE_LAT, lng: OFFICE_LNG}}];
  _routeStops.filter(s => s.lat && s.lng).forEach(s => path.push({{lat: s.lat, lng: s.lng}}));
  if (path.length < 2) return;
  _routeLine = new google.maps.Polyline({{
    path: path, geodesic: true,
    strokeColor: '#ea580c', strokeOpacity: 0.8, strokeWeight: 3,
    map: _map
  }});
}}

// ─── Save route ─────────────────────────────────────────────────────────────
async function saveRoute() {{
  const nameIn = document.getElementById('rp-route-name');
  const dateIn = document.getElementById('rp-route-date');
  const assignIn = document.getElementById('rp-route-assign');
  const st = document.getElementById('rp-route-status');
  const name = (nameIn ? nameIn.value.trim() : '') || 'Route ' + (dateIn ? dateIn.value : '');
  const date = dateIn ? dateIn.value : '';
  const assign = assignIn ? assignIn.value.trim() : '';
  if (!_routeStops.length) {{ if (st) st.textContent = 'Add stops first'; return; }}
  if (st) st.textContent = 'Saving\u2026';
  try {{
    // POST route
    const routePayload = {{'Name': name, 'Date': date || null, 'Assigned To': assign}};
    const rr = await fetch('/api/guerilla/routes', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        name: name,
        date: date || null,
        assigned_to: assign,
        stops: _routeStops.map((s, i) => ({{venue_id: s.id, table_id: s.tid, order: i + 1, name: s.name}}))
      }})
    }});
    const rd = await rr.json();
    if (rd.ok || rd.id) {{
      if (st) {{ st.style.color = '#059669'; st.textContent = 'Route saved \u2713'; }}
      setTimeout(() => {{ clearRoute(); }}, 2000);
    }} else {{
      if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Error: ' + (rd.error || 'Unknown'); }}
    }}
  }} catch(e) {{
    if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Network error'; }}
  }}
}}

function clearRoute() {{
  _routeStops = [];
  renderRouteStops();
  const nameIn = document.getElementById('rp-route-name');
  const dateIn = document.getElementById('rp-route-date');
  const assignIn = document.getElementById('rp-route-assign');
  const st = document.getElementById('rp-route-status');
  if (nameIn) nameIn.value = '';
  if (dateIn) dateIn.value = '';
  if (assignIn) assignIn.value = '';
  if (st) st.textContent = '';
  if (_routeMode) toggleRouteMode();
}}

// ─── GFR pre-fill helpers ───────────────────────────────────────────────────
function openLogEvent() {{
  if (!_currentVenue) {{ s2Reset(); document.getElementById('gfr-form-s2').classList.add('open'); return; }}
  s2Reset();
  var el;
  el = document.getElementById('s2-event-name'); if (el) el.value = _currentVenue[_currentVenue._nameField] || '';
  el = document.getElementById('s2-addr');       if (el) el.value = _currentVenue[_currentVenue._addrField] || '';
  el = document.getElementById('s2-org-phone');  if (el) el.value = _currentVenue[_currentVenue._phoneField] || '';
  document.getElementById('gfr-form-s2').classList.add('open');
}}
function openScheduleEvent(formType) {{
  if (!_currentVenue) {{ openGFRForm(formType); return; }}
  openGFRForm(formType);
  var name = _currentVenue[_currentVenue._nameField] || '';
  var addr = _currentVenue[_currentVenue._addrField] || '';
  var phone = _currentVenue[_currentVenue._phoneField] || '';
  setTimeout(function() {{
    ['s3','s4','s5'].forEach(function(p) {{
      var c = document.getElementById(p + '-company'); if (c && !c.value) c.value = name;
      var a = document.getElementById(p + '-addr');    if (a && !a.value) a.value = addr;
      var ph = document.getElementById(p + '-phone');  if (ph && !ph.value) ph.value = phone;
    }});
  }}, 50);
}}

// ─── Init ───────────────────────────────────────────────────────────────────
initMap();
loadAllVenues();
"""

    # Prepend GFR form JS
    gfr_js = f"const GFR_USER = {repr(_uname)};\nconst TOOL = {{venuesT: {T_GOR_VENUES}}};\n"
    gfr_js += _GFR_JS + '\n' + _GFR_FORMS345_JS + '\n'
    js = gfr_js + js

    return _page('route_planner', 'Route Planner', header, body, js, br, bt, user=user)


# ===========================================================================
# Outreach List — unified action list for all three outreach tools
# ===========================================================================
def _outreach_list_page(br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header"><div class="header-left">'
        '<h1>Outreach Directory</h1>'
        '<div class="sub">All outreach venues across Attorney, Guerilla, and Community</div>'
        '</div></div>'
    )
    body = """
<style>
.ol-filters{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
.ol-pill{font-size:12px;padding:5px 12px;border-radius:6px;border:1px solid var(--border);
  background:var(--card);color:var(--text2);cursor:pointer;font-weight:500;transition:all .12s;user-select:none}
.ol-pill.active{background:#ea580c;color:#fff;border-color:#ea580c}
.ol-pill:hover{border-color:var(--text3)}
.ol-search{background:var(--input-bg);border:1px solid var(--border);color:var(--text);
  border-radius:7px;padding:7px 12px;font-size:13px;width:220px}
.ol-stat{text-align:center;padding:14px 0}
.ol-stat .val{font-size:22px;font-weight:700}
.ol-stat .lbl{font-size:10px;color:var(--text3);text-transform:uppercase;margin-top:2px}
.ol-tbl{width:100%;border-collapse:collapse;font-size:13px}
.ol-tbl th{text-align:left;font-size:11px;font-weight:600;text-transform:uppercase;color:var(--text3);
  padding:8px 10px;border-bottom:1px solid var(--border);cursor:pointer;user-select:none;white-space:nowrap}
.ol-tbl th:hover{color:var(--text)}
.ol-tbl td{padding:9px 10px;border-bottom:1px solid var(--border);vertical-align:middle}
.ol-tbl tr:hover{background:var(--card-hover)}
.ol-badge{display:inline-block;font-size:10px;font-weight:600;padding:2px 7px;border-radius:4px}
.ol-overdue{color:#ef4444;font-weight:600}
.ol-soon{color:#f59e0b}
.ol-ok{color:var(--text3)}
.ol-empty{text-align:center;padding:40px;color:var(--text3);font-size:13px}
#ol-table-wrap{overflow-x:auto}
</style>

<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:18px">
  <div class="stat-chip c-purple" style="margin:0"><div class="label">Attorney</div><div class="value" id="s-att">--</div></div>
  <div class="stat-chip c-orange" style="margin:0"><div class="label">Guerilla</div><div class="value" id="s-gor">--</div></div>
  <div class="stat-chip c-green" style="margin:0"><div class="label">Community</div><div class="value" id="s-com">--</div></div>
  <div class="stat-chip c-yellow" style="margin:0"><div class="label">Active Boxes</div><div class="value" id="s-boxes">--</div></div>
  <div class="stat-chip c-red" style="margin:0"><div class="label">Overdue</div><div class="value" id="s-overdue">--</div></div>
  <div class="stat-chip c-blue" style="margin:0"><div class="label">Showing</div><div class="value" id="s-showing">--</div></div>
</div>

<div class="ol-filters">
  <span class="ol-pill active" data-layer="all" onclick="setLayer(this)">All</span>
  <span class="ol-pill" data-layer="attorney" onclick="setLayer(this)" style="border-left:3px solid #7c3aed">Attorney</span>
  <span class="ol-pill" data-layer="gorilla" onclick="setLayer(this)" style="border-left:3px solid #ea580c">Guerilla</span>
  <span class="ol-pill" data-layer="community" onclick="setLayer(this)" style="border-left:3px solid #059669">Community</span>
  <div style="width:1px;height:20px;background:var(--border);margin:0 4px"></div>
  <span class="ol-pill active" data-status="Active" onclick="toggleStatus(this)">Active</span>
  <span class="ol-pill active" data-status="In Discussion" onclick="toggleStatus(this)">In Discussion</span>
  <span class="ol-pill" data-status="Contacted" onclick="toggleStatus(this)">Contacted</span>
  <span class="ol-pill" data-status="Not Contacted" onclick="toggleStatus(this)">Not Contacted</span>
  <span class="ol-pill" data-status="Previous" onclick="toggleStatus(this)">Previous</span>
  <span class="ol-pill" data-status="overdue" onclick="toggleStatus(this)">Overdue Only</span>
  <span class="ol-pill" data-status="boxalert" onclick="toggleStatus(this)">Box Alerts</span>
  <div style="flex:1"></div>
  <input type="text" class="ol-search" id="ol-search" placeholder="Search venues\u2026" oninput="applyFilters()">
</div>

<div id="ol-table-wrap">
  <table class="ol-tbl" id="ol-tbl">
    <thead><tr>
      <th onclick="sortBy('name')">Name <span id="sort-name"></span></th>
      <th onclick="sortBy('tool')" style="width:90px">Tool <span id="sort-tool"></span></th>
      <th onclick="sortBy('status')" style="width:120px">Status <span id="sort-status"></span></th>
      <th onclick="sortBy('followup')" style="width:110px">Follow-Up <span id="sort-followup"></span></th>
      <th onclick="sortBy('lastact')" style="width:110px">Last Activity <span id="sort-lastact"></span></th>
      <th onclick="sortBy('box')" style="width:100px">Box <span id="sort-box"></span></th>
      <th style="width:60px"></th>
    </tr></thead>
    <tbody id="ol-tbody"></tbody>
  </table>
</div>
<div id="ol-empty" class="ol-empty" style="display:none">No venues match your filters.</div>
<div id="ol-loading" class="ol-empty">Loading venues\u2026</div>

<!-- Contact detail modal -->
<div class="cd-overlay" id="cd-overlay" onclick="if(event.target===this)closeContactDetail()">
<div class="cd-modal">
<div class="cd-header">
<div style="flex:1;min-width:0"><div class="cd-title" id="cd-title"></div>
<div id="cd-subtitle" style="margin-top:4px"></div></div>
<div class="cd-header-actions">
<button class="cd-btn-email" onclick="showEmailTemplates(_cdVenue,_cdTool)" title="Email templates">\u2709 Email</button>
<button class="cd-btn-close" onclick="closeContactDetail()">&times;</button>
</div></div>
<div class="cd-body">
<div class="cd-panel active" id="cd-panel-detail"><div id="cd-detail-body"></div></div>
<div class="cd-panel" id="cd-panel-tpl"><div id="cd-tpl-body"></div></div>
</div></div></div>
"""

    js = f"""
const ATT_TID  = {T_ATT_VENUES};
const GOR_TID  = {T_GOR_VENUES};
const COM_TID  = {T_COM_VENUES};
const ATT_ACTS = {T_ATT_ACTS};
const GOR_ACTS = {T_GOR_ACTS};
const COM_ACTS = {T_COM_ACTS};
const BOX_TID  = {T_GOR_BOXES};
const PI_ACTIVE  = {T_PI_ACTIVE};
const PI_BILLED  = {T_PI_BILLED};
const PI_AWAITING = {T_PI_AWAITING};
const PI_CLOSED  = {T_PI_CLOSED};

const TOOL_CFG = {{
  attorney:  {{tid:ATT_TID, actsTid:ATT_ACTS, nameField:'Law Firm Name', phoneField:'Phone Number', addrField:'Law Office Address',
               color:'#7c3aed', label:'Attorney', activeStatus:'Active Relationship'}},
  gorilla:   {{tid:GOR_TID, actsTid:GOR_ACTS, nameField:'Name', phoneField:'Phone', addrField:'Address',
               color:'#ea580c', label:'Guerilla', activeStatus:'Active Partner'}},
  community: {{tid:COM_TID, actsTid:COM_ACTS, nameField:'Name', phoneField:'Phone', addrField:'Address',
               color:'#059669', label:'Community', activeStatus:'Active Partner'}}
}};

let _all = [];
let _allBoxes = [];
let _firmCounts = {{}};
let _filtered = [];
let _sortCol = 'followup';
let _sortAsc = true;
let _layer = 'all';
let _statuses = new Set(['Active','In Discussion']);

function setLayer(el) {{
  document.querySelectorAll('.ol-pill[data-layer]').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  _layer = el.dataset.layer;
  applyFilters();
}}

function toggleStatus(el) {{
  const s = el.dataset.status;
  if (el.classList.contains('active')) {{
    el.classList.remove('active');
    _statuses.delete(s);
  }} else {{
    el.classList.add('active');
    _statuses.add(s);
  }}
  applyFilters();
}}

function _normName(n) {{ return (n || '').toLowerCase().trim(); }}
function _getFirmName(p) {{
  const raw = p['Law Firm Name ONLY'] || p['Law Firm Name'] || p['Law Firm'] || '';
  if (!raw) return '';
  if (Array.isArray(raw)) return raw.length ? (raw[0].value || String(raw[0])) : '';
  if (typeof raw === 'object' && raw.value) return raw.value;
  return String(raw);
}}
function _lookupFirm(name) {{
  const key = _normName(name);
  if (_firmCounts[key]) return _firmCounts[key];
  for (const [k, v] of Object.entries(_firmCounts)) {{
    const shorter = key.length <= k.length ? key : k;
    const longer  = key.length <= k.length ? k   : key;
    if (shorter.length >= 8 && longer.includes(shorter)) return v;
  }}
  return {{}};
}}
function _isPreviousAttorney(v) {{
  if (v._tool !== 'attorney') return false;
  const fc = _lookupFirm(v[v._nameField] || '');
  return (fc.settled || 0) > 0 && !(fc.active || 0) && !(fc.billed || 0) && !(fc.awaiting || 0);
}}

function _statusMatch(v) {{
  const status = sv(v['Contact Status']);
  const cfg = TOOL_CFG[v._tool];

  // For attorneys marked "Active Relationship", check if truly active via case data
  if (v._tool === 'attorney' && status === cfg.activeStatus) {{
    if (_isPreviousAttorney(v)) {{
      // Only show under "Previous" filter, not "Active"
      return _statuses.has('Previous');
    }}
    return _statuses.has('Active');
  }}

  if (_statuses.has('Active') && status === cfg.activeStatus) return true;
  if (_statuses.has('In Discussion') && status === 'In Discussion') return true;
  if (_statuses.has('Contacted') && status === 'Contacted') return true;
  if (_statuses.has('Not Contacted') && (status === 'Not Contacted' || !status)) return true;
  // Previous for attorneys with only closed cases (any contact status)
  if (_statuses.has('Previous') && _isPreviousAttorney(v)) return true;
  return false;
}}

function _isOverdue(v) {{
  const fu = v['Follow-Up Date'] || '';
  if (!fu) return false;
  const d = daysUntil(fu);
  return d !== null && d < 0;
}}

function _boxInfo(v) {{
  // Returns {{count, oldest, alertLevel}} for guerilla venues
  if (v._tool !== 'gorilla') return null;
  const mine = _allBoxes.filter(b => {{
    const biz = b['Business'];
    if (!Array.isArray(biz)) return false;
    return biz.some(r => r.id === v.id);
  }}).filter(b => sv(b['Status']) === 'Active' && b['Date Placed']);
  if (!mine.length) return null;
  let oldest = 0;
  let worstLevel = 'green';
  mine.forEach(b => {{
    const age = -(daysUntil(b['Date Placed']) || 0);
    if (age > oldest) oldest = age;
    const pickupDays = parseInt(b['Pickup Days']) || 14;
    if (age >= pickupDays * 2 && worstLevel !== 'red') worstLevel = 'red';
    else if (age >= pickupDays && worstLevel === 'green') worstLevel = 'amber';
  }});
  return {{count: mine.length, age: oldest, level: worstLevel}};
}}

function applyFilters() {{
  const q = (document.getElementById('ol-search').value || '').toLowerCase();
  const overdueOnly = _statuses.has('overdue');
  const boxAlertOnly = _statuses.has('boxalert');

  _filtered = _all.filter(v => {{
    // Hide blacklisted venues
    var vName = (v[v._nameField] || '').toUpperCase();
    if (vName.includes('(BLACK LIST)') || vName.includes('(BLACKLIST)')) return false;
    if (_layer !== 'all' && v._tool !== _layer) return false;
    if (boxAlertOnly) {{
      const bi = _boxInfo(v);
      if (!bi || bi.level === 'green') return false;
    }} else if (!_statusMatch(v) && !overdueOnly) return false;
    if (overdueOnly && !_isOverdue(v)) return false;
    if (q) {{
      const name = (v[v._nameField] || '').toLowerCase();
      const addr = (v[v._addrField] || '').toLowerCase();
      if (!name.includes(q) && !addr.includes(q)) return false;
    }}
    return true;
  }});

  doSort();
  render();
  updateStats();
}}

function sortBy(col) {{
  if (_sortCol === col) _sortAsc = !_sortAsc;
  else {{ _sortCol = col; _sortAsc = true; }}
  // Update arrows
  ['name','tool','status','followup','lastact','box'].forEach(c => {{
    const el = document.getElementById('sort-' + c);
    if (el) el.textContent = c === _sortCol ? (_sortAsc ? '\\u25B2' : '\\u25BC') : '';
  }});
  doSort();
  render();
}}

function doSort() {{
  _filtered.sort((a, b) => {{
    let va, vb;
    switch (_sortCol) {{
      case 'name':
        va = (a[a._nameField] || '').toLowerCase();
        vb = (b[b._nameField] || '').toLowerCase();
        break;
      case 'tool':
        va = a._tool; vb = b._tool; break;
      case 'status':
        va = sv(a['Contact Status']); vb = sv(b['Contact Status']); break;
      case 'followup':
        va = a['Follow-Up Date'] || 'z'; vb = b['Follow-Up Date'] || 'z'; break;
      case 'lastact':
        va = a._lastAct || ''; vb = b._lastAct || ''; break;
      case 'box':
        const ba = _boxInfo(a), bb = _boxInfo(b);
        va = ba ? ba.age : -1; vb = bb ? bb.age : -1; break;
      default:
        va = ''; vb = '';
    }}
    if (va < vb) return _sortAsc ? -1 : 1;
    if (va > vb) return _sortAsc ? 1 : -1;
    return 0;
  }});
}}

function render() {{
  const tbody = document.getElementById('ol-tbody');
  const empty = document.getElementById('ol-empty');
  const loading = document.getElementById('ol-loading');
  if (loading) loading.style.display = 'none';

  if (!_filtered.length) {{
    tbody.innerHTML = '';
    empty.style.display = '';
    return;
  }}
  empty.style.display = 'none';

  // Render max 200 rows for performance
  const rows = _filtered.slice(0, 200);
  let html = '';
  const today = new Date().toISOString().split('T')[0];

  rows.forEach((v, i) => {{
    const cfg = TOOL_CFG[v._tool];
    const name = esc(v[v._nameField] || '(unnamed)');
    const status = sv(v['Contact Status']) || 'Not Contacted';
    const fu = v['Follow-Up Date'] || '';
    const lastAct = v._lastAct || '';

    // Status display
    let statusLabel = status;
    if (status === cfg.activeStatus) statusLabel = _isPreviousAttorney(v) ? 'Previous' : 'Active';

    // Follow-up styling
    let fuHtml = '';
    if (fu) {{
      const d = daysUntil(fu);
      if (d !== null && d < 0) fuHtml = '<span class="ol-overdue">' + fmt(fu) + ' (' + Math.abs(d) + 'd)</span>';
      else if (d !== null && d <= 7) fuHtml = '<span class="ol-soon">' + fmt(fu) + '</span>';
      else fuHtml = '<span class="ol-ok">' + fmt(fu) + '</span>';
    }}

    // Box column
    let boxHtml = '';
    const bi = _boxInfo(v);
    if (bi) {{
      const bc = bi.level === 'red' ? '#ef4444' : bi.level === 'amber' ? '#f59e0b' : '#34a853';
      boxHtml = '<span class="ol-badge" style="background:' + bc + '18;color:' + bc + '">'
        + bi.count + ' box' + (bi.count > 1 ? 'es' : '') + ' &middot; ' + bi.age + 'd</span>';
    }} else if (v._tool === 'gorilla') {{
      boxHtml = '<span class="ol-ok">None</span>';
    }}

    html += '<tr>'
      + '<td style="font-weight:600"><a href="#" onclick="openContactDetail(_filtered['+i+']);return false" style="color:var(--text);text-decoration:underline dotted">' + name + '</a></td>'
      + '<td><span class="ol-badge" style="background:' + cfg.color + '18;color:' + cfg.color + '">' + cfg.label + '</span></td>'
      + '<td><span class="ol-badge" style="background:var(--card);border:1px solid var(--border)">' + esc(statusLabel) + '</span></td>'
      + '<td>' + fuHtml + '</td>'
      + '<td class="ol-ok">' + (lastAct ? fmt(lastAct) : '') + '</td>'
      + '<td>' + boxHtml + '</td>'
      + '<td>' + ((v[v._addrField] || v['Latitude']) ? '<a href="/outreach/planner?tool='+v._tool+'&venue='+v.id+'" style="font-size:11px;color:#ea580c;text-decoration:none">Map</a>' : '') + '</td>'
      + '</tr>';
  }});

  tbody.innerHTML = html;
  if (_filtered.length > 200) {{
    tbody.innerHTML += '<tr><td colspan="7" style="text-align:center;color:var(--text3);font-size:12px;padding:12px">Showing 200 of ' + _filtered.length + ' — use filters to narrow results</td></tr>';
  }}
}}

function updateStats() {{
  const att = _all.filter(v => v._tool === 'attorney').length;
  const gor = _all.filter(v => v._tool === 'gorilla').length;
  const com = _all.filter(v => v._tool === 'community').length;
  const overdue = _all.filter(v => _isOverdue(v)).length;
  const activeBoxes = _allBoxes.filter(b => sv(b['Status']) === 'Active').length;
  document.getElementById('s-att').textContent = att;
  document.getElementById('s-gor').textContent = gor;
  document.getElementById('s-com').textContent = com;
  document.getElementById('s-boxes').textContent = activeBoxes;
  document.getElementById('s-overdue').textContent = overdue;
  document.getElementById('s-showing').textContent = _filtered.length;
}}

async function load() {{
  // Load all three venue tables + boxes in parallel
  const [att, gor, com, boxes] = await Promise.all([
    fetchAll(ATT_TID), fetchAll(GOR_TID), fetchAll(COM_TID), fetchAll(BOX_TID)
  ]);

  // Tag venues
  att.forEach(v => {{ v._tool = 'attorney';  v._nameField = 'Law Firm Name'; v._addrField = 'Law Office Address'; }});
  gor.forEach(v => {{ v._tool = 'gorilla';   v._nameField = 'Name';          v._addrField = 'Address'; }});
  com.forEach(v => {{ v._tool = 'community'; v._nameField = 'Name';          v._addrField = 'Address'; }});

  _all = [].concat(att, gor, com);
  _allBoxes = boxes;

  // Load PI case counts for attorney firm classification
  Promise.all([fetchAll(PI_ACTIVE), fetchAll(PI_BILLED), fetchAll(PI_AWAITING), fetchAll(PI_CLOSED)]).then(([a,b,w,c]) => {{
    const tally = (rows, key) => rows.forEach(r => {{
      const k = _normName(_getFirmName(r));
      if (k) {{ _firmCounts[k] = _firmCounts[k] || {{active:0,billed:0,awaiting:0,settled:0}}; _firmCounts[k][key]++; }}
    }});
    tally(a,'active'); tally(b,'billed'); tally(w,'awaiting'); tally(c,'settled');
    applyFilters();  // Re-filter now that we know which attorneys are truly active
  }});

  // Load last activity dates in background (lightweight — just need dates)
  Promise.all([fetchAll(ATT_ACTS), fetchAll(GOR_ACTS), fetchAll(COM_ACTS)]).then(([aActs, gActs, cActs]) => {{
    // Build map: tool+venueId -> most recent date
    const actMap = {{}};
    function mapActs(acts, linkField) {{
      acts.forEach(a => {{
        const d = a['Date'] || '';
        const links = a[linkField];
        if (!d || !Array.isArray(links)) return;
        links.forEach(lnk => {{
          const k = lnk.id;
          if (!actMap[k] || d > actMap[k]) actMap[k] = d;
        }});
      }});
    }}
    mapActs(aActs, 'Law Firm');
    mapActs(gActs, 'Business');
    mapActs(cActs, 'Organization');

    _all.forEach(v => {{ v._lastAct = actMap[v.id] || ''; }});
    render();  // Re-render with activity dates
  }});

  // Initial render with just venue data
  applyFilters();
  stampRefresh();
}}

// Default sort by follow-up ascending
_sortCol = 'followup';
_sortAsc = true;
document.getElementById('sort-followup').textContent = '\\u25B2';

// ── Contact Detail Modal ─────────────────────────────────────────────────
let _cdVenue = null;
let _cdTool = null;
let _cdNameField = '', _cdPhoneField = '', _cdAddrField = '', _cdActiveStatus = '';
let _cdStages = [];
let _cdVenuesTid = 0, _cdActsTid = 0, _cdActsLink = '';

function _setCdContext(v) {{
  var tool = v._tool;
  _cdTool = tool;
  var cfg = TOOL_CFG[tool];
  if (!cfg) return;
  _cdNameField = cfg.nameField; _cdPhoneField = cfg.phoneField; _cdAddrField = cfg.addrField;
  _cdActiveStatus = cfg.activeStatus;
  _cdStages = ['Not Contacted','Contacted','In Discussion', cfg.activeStatus];
  _cdVenuesTid = cfg.tid; _cdActsTid = cfg.actsTid; _cdActsLink = tool === 'attorney' ? 'Law Firm' : tool === 'gorilla' ? 'Business' : 'Organization';
}}

function _cdStageOpts(cur) {{
  return _cdStages.map(function(s){{ return '<option value="'+s+'"'+(cur===s?' selected':'')+'>'+s+'</option>'; }}).join('');
}}

function _cdStatusBadge(status) {{
  var map = {{'Not Contacted':'sb-not','Contacted':'sb-cont','In Discussion':'sb-disc'}};
  var cls = status === _cdActiveStatus ? 'sb-act' : (map[status] || 'sb-not');
  return '<span class="status-badge ' + cls + '">' + esc(status || 'Unknown') + '</span>';
}}

async function _cdBpatch(tid, id, data) {{
  return fetch(BR+'/api/database/rows/table/'+tid+'/'+id+'/?user_field_names=true',{{
    method:'PATCH',headers:{{'Authorization':'Token '+BT,'Content-Type':'application/json'}},
    body:JSON.stringify(data)}});
}}

function _cdRenderNotes(text) {{
  if (!text || !text.trim()) return '<div style="color:var(--text3);font-size:12px;padding:4px 0">No notes yet</div>';
  return text.split('\\n---\\n').filter(function(e){{return e.trim();}}).map(function(entry) {{
    var m = entry.match(/^\\[(\d{{4}}-\d{{2}}-\d{{2}})\\] ([\\s\\S]*)$/);
    if (m) return '<div style="padding:5px 0;border-bottom:1px solid var(--border)">'
      + '<div style="font-size:10px;color:var(--text3);margin-bottom:2px">' + m[1] + '</div>'
      + '<div style="font-size:12px">' + esc(m[2].trim()) + '</div></div>';
    return '<div style="padding:5px 0;border-bottom:1px solid var(--border);font-size:12px">' + esc(entry.trim()) + '</div>';
  }}).join('');
}}

function _cdRenderAct(a) {{
  var type = a['Type'] ? (typeof a['Type'] === 'object' ? a['Type'].value : a['Type']) : '';
  var outcome = a['Outcome'] ? (typeof a['Outcome'] === 'object' ? a['Outcome'].value : a['Outcome']) : '';
  var date = a['Date'] || '';
  var person = a['Contact Person'] || '';
  var summary = a['Summary'] || '';
  var fu = a['Follow-Up Date'] || '';
  return '<div style="padding:8px 0;border-bottom:1px solid var(--border)">'
    + '<div style="display:flex;justify-content:space-between;margin-bottom:3px">'
    + '<span style="font-size:11px;font-weight:600;background:var(--badge-bg);padding:1px 6px;border-radius:4px">' + esc(type) + '</span>'
    + '<span style="font-size:11px;color:var(--text3)">' + esc(date) + '</span></div>'
    + (outcome ? '<div style="font-size:12px;color:var(--text2)">' + esc(outcome) + '</div>' : '')
    + (person  ? '<div style="font-size:11px;color:var(--text3)">with ' + esc(person) + '</div>' : '')
    + (summary ? '<div style="font-size:12px;margin-top:3px">' + esc(summary) + '</div>' : '')
    + (fu      ? '<div style="font-size:11px;color:#f59e0b;margin-top:2px">Follow-up: ' + esc(fu) + '</div>' : '')
    + '</div>';
}}

function _cdBuildDetail(v) {{
  var id = v.id;
  var status = sv(v['Contact Status']);
  var phone = esc(v[_cdPhoneField] || '');
  var addr = esc(v[_cdAddrField] || '');
  var website = v['Website'] || '';
  var fu = v['Follow-Up Date'] || '';
  var notesRaw = v['Notes'] || '';
  var html = '';
  if (phone) html += '<div style="font-size:13px;margin-bottom:6px">\u260e <a href="tel:'+phone+'" style="color:var(--text)">'+phone+'</a></div>';
  if (addr)  html += '<div style="font-size:12px;color:var(--text2);margin-bottom:6px">\U0001f4cd '+addr+'</div>';
  if (website) html += '<div style="font-size:12px;margin-bottom:10px">\U0001f310 <a href="'+esc(website)+'" target="_blank" style="color:#3b82f6">'+esc(website)+'</a></div>';
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
  html += '<div style="margin-bottom:8px"><div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:4px">Contact Status</div>';
  html += '<div style="display:flex;gap:6px;align-items:center">';
  html += '<select id="cd-status-'+id+'" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 8px;font-size:12px" onchange="cdUpdateStatus('+id+',this.value)">'+_cdStageOpts(status)+'</select>';
  html += '<span id="cd-status-st-'+id+'" style="font-size:11px;color:#34a853;min-width:20px"></span></div></div>';
  html += '<div style="margin-bottom:10px"><div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:4px">Follow-Up Date</div>';
  html += '<div style="display:flex;gap:6px;align-items:center">';
  html += '<input type="date" id="cd-fu-'+id+'" value="'+esc(fu)+'" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 8px;font-size:12px">';
  html += '<button onclick="cdSaveFollowUp('+id+')" style="background:#3b82f6;color:#fff;border:none;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:11px;font-weight:600">Save</button>';
  html += '<span id="cd-fu-st-'+id+'" style="font-size:11px;color:#34a853;min-width:20px"></span></div></div>';
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
  html += '<div style="margin-bottom:10px"><div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:6px">Notes</div>';
  html += '<div id="cd-notes-'+id+'" style="max-height:120px;overflow-y:auto;background:var(--card);border-radius:6px;padding:6px 8px;border:1px solid var(--border)">'+_cdRenderNotes(notesRaw)+'</div>';
  html += '<div style="display:flex;gap:6px;margin-top:6px">';
  html += '<input type="text" id="cd-note-in-'+id+'" placeholder="Add a note\u2026" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 8px;font-size:12px">';
  html += '<button onclick="cdAddNote('+id+')" style="background:#e94560;color:#fff;border:none;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:11px;font-weight:600">Add</button>';
  html += '</div><div id="cd-note-st-'+id+'" style="font-size:11px;color:#34a853;margin-top:3px;min-height:14px"></div></div>';
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
  html += '<div><div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:6px">Activities</div>';
  html += '<div id="cd-acts-'+id+'" style="font-size:12px;color:var(--text3)">Loading\u2026</div></div>';
  return html;
}}

function openContactDetail(v) {{
  _setCdContext(v);
  _cdVenue = v;
  var id = v.id;
  document.getElementById('cd-title').textContent = v[_cdNameField] || '(unnamed)';
  document.getElementById('cd-subtitle').innerHTML = _cdStatusBadge(sv(v['Contact Status']));
  document.getElementById('cd-detail-body').innerHTML = _cdBuildDetail(v);
  document.getElementById('cd-panel-detail').className = 'cd-panel active';
  document.getElementById('cd-panel-tpl').className = 'cd-panel';
  document.getElementById('cd-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  fetchAll(_cdActsTid).then(function(acts) {{
    var mine = acts.filter(function(a) {{
      var lf = a[_cdActsLink];
      return Array.isArray(lf) ? lf.some(function(r){{return r.id === id;}}) : false;
    }}).sort(function(a,b){{ return (b['Date']||'').localeCompare(a['Date']||''); }});
    var el = document.getElementById('cd-acts-'+id);
    if (el) el.innerHTML = mine.length ? mine.map(_cdRenderAct).join('')
      : '<div style="color:var(--text3);padding:4px 0">No activities yet</div>';
  }});
}}

function closeContactDetail() {{
  document.getElementById('cd-overlay').classList.remove('open');
  document.body.style.overflow = '';
  _cdVenue = null;
}}

async function cdUpdateStatus(id, val) {{
  var st = document.getElementById('cd-status-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  var r = await _cdBpatch(_cdVenuesTid, id, {{'Contact Status': val}});
  if (st) {{ st.textContent = r.ok ? '\u2713' : '\u2717'; setTimeout(function(){{ if(st) st.textContent=''; }}, 2000); }}
  // Update local data
  var v = _all.find(function(x){{return x.id===id && x._tool===_cdTool;}});
  if (v) v['Contact Status'] = {{value: val}};
}}

async function cdSaveFollowUp(id) {{
  var val = (document.getElementById('cd-fu-' + id) || {{}}).value || null;
  var st = document.getElementById('cd-fu-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  var r = await _cdBpatch(_cdVenuesTid, id, {{'Follow-Up Date': val || null}});
  if (st) {{ st.textContent = r.ok ? '\u2713' : '\u2717'; setTimeout(function(){{ if(st) st.textContent=''; }}, 2000); }}
  var v = _all.find(function(x){{return x.id===id && x._tool===_cdTool;}});
  if (v) v['Follow-Up Date'] = val;
}}

async function cdAddNote(id) {{
  var inputEl = document.getElementById('cd-note-in-' + id);
  var text = (inputEl ? inputEl.value : '').trim();
  if (!text) return;
  var today = new Date().toISOString().split('T')[0];
  var entry = '[' + today + '] ' + text;
  var v = _all.find(function(x){{return x.id===id && x._tool===_cdTool;}});
  var existing = (v && v['Notes'] ? v['Notes'].trim() : '');
  var newNotes = existing ? entry + '\\n---\\n' + existing : entry;
  if (v) v['Notes'] = newNotes;
  if (inputEl) inputEl.value = '';
  var logEl = document.getElementById('cd-notes-' + id);
  if (logEl) logEl.innerHTML = _cdRenderNotes(newNotes);
  var st = document.getElementById('cd-note-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  var r = await _cdBpatch(_cdVenuesTid, id, {{'Notes': newNotes}});
  if (st) {{ st.textContent = r.ok ? 'Saved \u2713' : 'Failed \u2717'; setTimeout(function(){{ if(st) st.textContent=''; }}, 2000); }}
}}

function showEmailTemplates(v, category) {{
  if (!v || !category) return;
  var nameField = TOOL_CFG[category] ? TOOL_CFG[category].nameField : 'Name';
  var name = v[nameField] || '(unnamed)';
  var tmpls = (_TEMPLATES[category] || []);
  var html = '<button class="cd-back-btn" onclick="_cdBackToDetail()">\u2190 Back to detail</button>';
  html += '<div style="font-size:13px;font-weight:600;margin-bottom:12px">Choose a template for <strong>' + esc(name) + '</strong></div>';
  html += '<div class="tpl-grid">';
  tmpls.forEach(function(t, i) {{
    var preview = t.body.replace(/\\{{name\\}}/g, name).substring(0, 160) + '\u2026';
    html += '<div class="tpl-card"><div class="tpl-card-name">' + esc(t.name) + '</div>';
    html += '<div class="tpl-card-subj">Subject: ' + esc(t.subject) + '</div>';
    html += '<div class="tpl-card-preview">' + esc(preview) + '</div>';
    html += '<button class="tpl-use-btn" data-tpl-i="'+i+'" data-tpl-cat="'+category+'" onclick="useTemplate(+this.dataset.tplI,this.dataset.tplCat)">Use Template \u2192</button></div>';
  }});
  html += '</div>';
  document.getElementById('cd-tpl-body').innerHTML = html;
  document.getElementById('cd-panel-detail').className = 'cd-panel';
  document.getElementById('cd-panel-tpl').className = 'cd-panel active';
}}

function _cdBackToDetail() {{
  document.getElementById('cd-panel-detail').className = 'cd-panel active';
  document.getElementById('cd-panel-tpl').className = 'cd-panel';
}}

function useTemplate(i, category) {{
  var t = _TEMPLATES[category][i];
  if (!t || !_cdVenue) return;
  var nameField = TOOL_CFG[category] ? TOOL_CFG[category].nameField : 'Name';
  var name = _cdVenue[nameField] || '';
  var body = t.body.replace(/\\{{name\\}}/g, name);
  document.getElementById('compose-to').value = (_cdVenue['Email'] || '');
  document.getElementById('compose-subject').value = t.subject;
  document.getElementById('compose-body').value = body;
  document.getElementById('compose-status').textContent = '';
  closeContactDetail();
  document.getElementById('compose-overlay').classList.add('open');
  setTimeout(function() {{
    var toVal = document.getElementById('compose-to').value;
    document.getElementById(toVal ? 'compose-subject' : 'compose-to').focus();
  }}, 50);
}}

{_TEMPLATES_JS}

load();
"""

    return _page('outreach_list', 'Outreach Directory', header, body, js, br, bt, user=user)
