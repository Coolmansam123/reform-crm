"""Outreach Due list + Outreach Map."""

import os

from hub.shared import (
    _mobile_page,
)


def _mobile_outreach_due_page(br: str, bt: str, user: dict = None) -> str:
    """To Do dashboard — combines two action-required lists for a rep:

    1. Overdue Follow-Ups: companies past their `Follow-Up Date`
       (`/api/outreach/due`).
    2. Skipped / Not Reached: route stops the rep didn't get to in the
       last 30 days (`/api/outreach/skipped`).

    Each row shows a `+ Add to route` button when the rep has an active
    guerilla route assigned today AND the row resolves to a venue id —
    posts to `POST /api/guerilla/routes/{route_id}/stops` (same path the
    home-page Boxes Due panel uses)."""
    user = user or {}
    body = (
        '<div class="mobile-hdr">'
        + '<div><div class="mobile-hdr-title">To Do</div>'
        + '<div class="mobile-hdr-sub">Follow-ups due + stops you skipped</div></div>'
        + '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        + '</div>'
        + '<div class="mobile-body">'
        # Daily Overview stat tiles (3 across — natural fit for 3 KPIs)
        + '<div class="label-caps" style="margin-bottom:8px">Daily Overview</div>'
        + '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:18px">'
        +   '<div class="stat-tile"><div class="stat-label">Total</div><div class="stat-value" id="td-kpi-total">—</div></div>'
        +   '<div class="stat-tile"><div class="stat-label">Skipped</div><div class="stat-value" id="td-kpi-skipped" style="color:#d97706">—</div></div>'
        +   '<div class="stat-tile"><div class="stat-label">Worst</div><div class="stat-value" id="td-kpi-worst" style="color:#ba1a1a">—</div></div>'
        + '</div>'
        + '<div id="td-route-banner" style="display:none;margin-bottom:16px"></div>'
        + '<div class="label-caps" id="td-fu-hdr" style="margin-bottom:8px">Overdue Follow-Ups</div>'
        + '<div id="td-filter" class="chip-strip" style="margin-bottom:14px"></div>'
        + '<div id="td-fu-list" style="display:flex;flex-direction:column;gap:10px;margin-bottom:24px">'
        +   '<div class="card" style="color:var(--text3);text-align:center;font-size:13px">Loading…</div></div>'
        + '<div class="label-caps" id="td-sk-hdr" style="margin-bottom:8px">Skipped Stops</div>'
        + '<div id="td-sk-list" style="display:flex;flex-direction:column;gap:10px">'
        +   '<div class="card" style="color:var(--text3);text-align:center;font-size:13px">Loading…</div></div>'
        + '</div>'
    )
    js = """
var _OD_ROWS = [];           // overdue follow-ups
var _SK_ROWS = [];           // skipped/not-reached stops
var _OD_FILTER = 'all';      // category filter on follow-ups only
var _ACTIVE_ROUTE_ID = null; // populated from /api/guerilla/routes/today
var _ADDED_VENUES = {};      // venueId -> true once a stop has been queued

var CAT_META = {
  attorney:  {label: 'Attorney',  color: '#7c3aed'},
  guerilla:  {label: 'Guerilla',  color: '#ea580c'},
  community: {label: 'Community', color: '#059669'},
  other:     {label: 'Other',     color: '#64748b'},
};

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function overdueColor(days) {
  if (days >= 30) return '#dc2626';
  if (days >= 14) return '#ea580c';
  if (days >= 7)  return '#d97706';
  return '#64748b';
}

function renderFilter() {
  var counts = {all: _OD_ROWS.length, attorney: 0, guerilla: 0, community: 0, other: 0};
  _OD_ROWS.forEach(function(r) {
    var c = r.category in counts ? r.category : 'other';
    counts[c] = (counts[c] || 0) + 1;
  });
  var cats = ['all', 'attorney', 'guerilla', 'community', 'other'];
  var html = '';
  cats.forEach(function(k) {
    if (k !== 'all' && !counts[k]) return;
    var active = k === _OD_FILTER;
    var label = k === 'all' ? 'All' : (CAT_META[k] || {label: k}).label;
    html +=
      '<button class="chip' + (active ? ' active' : '') + '" ' +
      'onclick="setFilter(\\'' + k + '\\')">' +
      esc(label) + ' · ' + counts[k] + '</button>';
  });
  document.getElementById('td-filter').innerHTML = html;
}

function setFilter(k) {
  _OD_FILTER = k;
  renderFilter();
  renderOD();
}

// Build the right-hand action button for a row: Add-to-route when we have
// both an active route and a venue id; otherwise an inline status hint.
function _actionBtn(venueId) {
  if (!venueId) {
    return '<span style="font-size:11px;color:var(--text4)">no venue</span>';
  }
  if (!_ACTIVE_ROUTE_ID) {
    return '<span style="font-size:11px;color:var(--text4)">no active route</span>';
  }
  if (_ADDED_VENUES[venueId]) {
    return '<button disabled style="background:#059669;color:#fff;border:none;border-radius:6px;' +
           'padding:8px 12px;font-size:12px;font-weight:600;min-height:36px;white-space:nowrap;opacity:.85">' +
           '\\u2713 Added</button>';
  }
  return '<button onclick="event.stopPropagation();addToRoute(' + venueId + ',this)" ' +
         'style="background:var(--primary);color:#fff;border:none;border-radius:6px;padding:8px 12px;' +
         'font-size:12px;font-weight:600;cursor:pointer;min-height:36px;white-space:nowrap;display:inline-flex;align-items:center;gap:4px;font-family:inherit">' +
         '<span class="material-symbols-outlined" style="font-size:14px">add_road</span>Add to route</button>';
}

async function addToRoute(venueId, btn) {
  if (!_ACTIVE_ROUTE_ID || !venueId) return;
  // Look up the row so we can build a sensible stop label without piping
  // free-text through the inline onclick attribute.
  var row = null;
  for (var i = 0; i < _OD_ROWS.length; i++) {
    if (_OD_ROWS[i].venue_id === venueId) { row = _OD_ROWS[i]; break; }
  }
  if (!row) {
    for (var j = 0; j < _SK_ROWS.length; j++) {
      if (_SK_ROWS[j].venue_id === venueId) { row = _SK_ROWS[j]; break; }
    }
  }
  var label;
  if (row && row.name)         label = 'Follow-up: ' + row.name;
  else if (row && row.venue_name) label = 'Re-visit: ' + row.venue_name;
  else                            label = 'Venue ' + venueId;

  if (btn) { btn.disabled = true; btn.textContent = '\\u2026'; }
  try {
    var r = await fetch('/api/guerilla/routes/' + _ACTIVE_ROUTE_ID + '/stops', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({venue_id: venueId, name: label})
    });
    if (!r.ok) {
      var err = await r.json().catch(function() { return {}; });
      if (btn) { btn.disabled = false; btn.textContent = '+ Add to route'; }
      alert('Could not add: ' + (err.error || r.status));
      return;
    }
    _ADDED_VENUES[venueId] = true;
    renderOD();
    renderSK();
  } catch (e) {
    if (btn) { btn.disabled = false; btn.textContent = '+ Add to route'; }
    alert('Network error \\u2014 try again');
  }
}

function renderOD() {
  var list = _OD_FILTER === 'all'
    ? _OD_ROWS
    : _OD_ROWS.filter(function(r) { return (r.category || 'other') === _OD_FILTER; });

  var hdr = document.getElementById('td-fu-hdr');
  if (hdr) hdr.innerHTML = 'Overdue Follow-Ups <span style="color:var(--text4);font-weight:600">· ' + list.length + '</span>';

  if (!list.length) {
    document.getElementById('td-fu-list').innerHTML =
      '<div class="card" style="color:var(--text3);text-align:center;font-size:13px">' +
      'No overdue follow-ups in this filter.</div>';
    return;
  }

  var html = '';
  list.forEach(function(r) {
    // Card severity by days overdue: 14+ → urgent (red), 7+ → warning (amber), else default
    var cardCls = 'card';
    var pillCls = 'pill';
    if (r.days_overdue >= 14)      { cardCls += ' card-urgent';  pillCls = 'pill pill-overdue'; }
    else if (r.days_overdue >= 7)  { cardCls += ' card-warning'; pillCls = 'pill pill-warning'; }
    var meta = CAT_META[r.category] || CAT_META.other;
    var label = r.days_overdue === 0 ? 'Due today' :
                r.days_overdue === 1 ? '1d overdue' :
                r.days_overdue + 'd overdue';
    html +=
      '<div class="' + cardCls + '" onclick="location.href=\\'/company/' + r.id + '\\'" style="cursor:pointer">' +
      '<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:6px">' +
      '<div style="flex:1;min-width:0">' +
      '<div style="font-size:14px;font-weight:600;color:var(--text);word-break:break-word">' + esc(r.name) + '</div>' +
      (r.address ? '<div style="font-size:11px;color:var(--text3);margin-top:3px;display:flex;align-items:center;gap:3px"><span class="material-symbols-outlined" style="font-size:13px">location_on</span>' + esc(r.address) + '</div>' : '') +
      '</div>' +
      '<span style="background:' + meta.color + '22;color:' + meta.color + ';font-size:10px;' +
      'font-weight:700;padding:2px 8px;border-radius:9999px;white-space:nowrap;text-transform:uppercase;letter-spacing:.04em">' + esc(meta.label) + '</span>' +
      '</div>' +
      '<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:8px">' +
      '<span class="' + pillCls + '">' + esc(label) + '</span>' +
      _actionBtn(r.venue_id) +
      '</div>' +
      '</div>';
  });
  document.getElementById('td-fu-list').innerHTML = html;
}

function renderSK() {
  var hdr = document.getElementById('td-sk-hdr');
  if (hdr) hdr.innerHTML = 'Skipped Stops <span style="color:var(--text4);font-weight:600">· ' + _SK_ROWS.length + '</span>';

  if (!_SK_ROWS.length) {
    document.getElementById('td-sk-list').innerHTML =
      '<div class="card" style="color:var(--text3);text-align:center;font-size:13px">' +
      'No skipped stops in the last 30 days.</div>';
    return;
  }

  var html = '';
  _SK_ROWS.forEach(function(r) {
    // Not Reached → urgent; Skipped → warning
    var cardCls = r.status === 'Not Reached' ? 'card card-urgent' : 'card card-warning';
    var pillCls = r.status === 'Not Reached' ? 'pill pill-overdue' : 'pill pill-warning';
    var ago = r.days_ago === 0 ? 'today' :
              r.days_ago === 1 ? '1d ago' :
              r.days_ago + 'd ago';
    var click = r.company_id
      ? 'onclick="location.href=\\'/company/' + r.company_id + '\\'" '
      : '';
    var cursor = r.company_id ? 'cursor:pointer' : '';
    html +=
      '<div class="' + cardCls + '" ' + click + 'style="' + cursor + '">' +
      '<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:6px">' +
      '<div style="flex:1;min-width:0">' +
      '<div style="font-size:14px;font-weight:600;color:var(--text);word-break:break-word">' + esc(r.venue_name) + '</div>' +
      (r.reason ? '<div style="font-size:11px;color:var(--text3);margin-top:3px;font-style:italic">\\u201c' + esc(r.reason) + '\\u201d</div>' : '') +
      '</div>' +
      '<span class="' + pillCls + '" style="white-space:nowrap">' + esc(r.status) + '</span>' +
      '</div>' +
      '<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:8px">' +
      '<span style="font-size:11px;color:var(--text3)">skipped ' + esc(ago) + '</span>' +
      _actionBtn(r.venue_id) +
      '</div>' +
      '</div>';
  });
  document.getElementById('td-sk-list').innerHTML = html;
}

function renderKPIs() {
  var total = _OD_ROWS.length + _SK_ROWS.length;
  var skipped = _SK_ROWS.length;
  var worst = _OD_ROWS.reduce(function(m, r) { return Math.max(m, r.days_overdue || 0); }, 0);
  document.getElementById('td-kpi-total').textContent = total;
  document.getElementById('td-kpi-skipped').textContent = skipped;
  document.getElementById('td-kpi-worst').textContent = worst ? (worst + 'd') : '\\u2014';
}

function renderRouteBanner() {
  var el = document.getElementById('td-route-banner');
  if (!el) return;
  el.style.display = 'block';
  if (_ACTIVE_ROUTE_ID) {
    el.className = 'card card-success';
    el.style.cssText = '';
    el.innerHTML = '<div style="display:flex;align-items:center;gap:8px;font-size:13px;color:var(--text)"><span class="material-symbols-outlined" style="font-size:18px;color:#059669">check_circle</span>Active route detected \\u2014 tap "Add to route" to queue stops</div>';
  } else {
    el.className = 'card';
    el.style.cssText = '';
    el.innerHTML = '<div style="display:flex;align-items:center;gap:8px;font-size:13px;color:var(--text3)"><span class="material-symbols-outlined" style="font-size:18px">info</span>No active route today \\u2014 tap a row to open the company</div>';
  }
}

async function loadAll() {
  try {
    var [duResp, skResp, rtResp] = await Promise.all([
      fetch('/api/outreach/due'),
      fetch('/api/outreach/skipped'),
      fetch('/api/guerilla/routes/today'),
    ]);
    _OD_ROWS = duResp.ok ? (await duResp.json()) : [];
    _OD_ROWS = (_OD_ROWS || []).filter(function(row) { return row.status !== 'Active Partner'; });
    _SK_ROWS = skResp.ok ? (await skResp.json()) : [];
    if (rtResp.ok) {
      var rt = await rtResp.json();
      _ACTIVE_ROUTE_ID = (rt && rt.route && rt.route.id) || null;
    }
  } catch (e) {
    document.getElementById('td-fu-list').innerHTML =
      '<div style="text-align:center;padding:30px 16px;color:#ef4444;font-size:13px">' +
      'Failed to load: ' + esc(e.message || 'unknown') + '</div>';
    document.getElementById('td-sk-list').innerHTML = '';
    return;
  }
  renderRouteBanner();
  renderFilter();
  renderOD();
  renderSK();
  renderKPIs();
}

loadAll();
"""
    return _mobile_page('m_outreach', 'To Do', body, js, br, bt, user=user)




def _mobile_outreach_map_page(br: str, bt: str, user: dict = None) -> str:
    """Full-screen Google Map showing today's route stops with a live-GPS
    marker. Tap a stop → InfoWindow with name/address/status and a link to
    the company detail. Replaces the prior "overdue follow-ups" map since
    planning now lives in the hub and reps want a route overview."""
    import os as _os
    from hub.shared import T_COMPANIES as _TC
    gk = _os.environ.get("GOOGLE_MAPS_API_KEY", "")
    user = user or {}
    body = (
        '<div class="mobile-hdr">'
        '<div><div class="mobile-hdr-title">Route Map</div>'
        '<div class="mobile-hdr-sub" id="om-sub">Your route at a glance</div></div>'
        '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        '</div>'
        '<div id="om-map" style="height:calc(100vh - 120px);width:100%;background:var(--bg2)"></div>'
        '<div id="om-msg" style="text-align:center;padding:8px;font-size:12px;color:var(--text3);min-height:14px"></div>'
    )
    js = f"""
const GK = {repr(gk)};
const OFFICE = {{lat: 33.9478, lng: -118.1335}};  // Downey
const _STATUS_COLORS = {{'Pending':'#4285f4','Visited':'#059669','Skipped':'#f97316','Not Reached':'#ef4444'}};
let _OM_MAP = null;
let _OM_ROUTE = null;
let _OM_STOPS = [];
let _OM_MARKERS = [];
let _OM_USER_MARKER = null;
let _OM_VENUE_TO_CO = {{}};

function esc(s) {{
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}}

async function loadOM() {{
  try {{
    var [routeResp, companies] = await Promise.all([
      fetch('/api/guerilla/routes/today').then(function(r) {{ return r.ok ? r.json() : {{route: null, stops: []}}; }}),
      fetchAll({_TC}),
    ]);
    _OM_ROUTE = routeResp.route;
    _OM_STOPS = routeResp.stops || [];
    _OM_VENUE_TO_CO = buildVenueCompanyMap(companies);
  }} catch (e) {{
    document.getElementById('om-msg').textContent = 'Failed to load: ' + (e.message || 'unknown');
    return;
  }}
  if (!GK) {{
    document.getElementById('om-msg').textContent = 'Maps API key not configured.';
    return;
  }}
  if (window.google && window.google.maps) {{
    _omReady();
  }} else {{
    window._omReady = _omReady;
    var s = document.createElement('script');
    s.src = 'https://maps.googleapis.com/maps/api/js?key=' + GK + '&callback=_omReady';
    s.async = true;
    document.head.appendChild(s);
  }}
}}

function _omReady() {{
  _OM_MAP = new google.maps.Map(document.getElementById('om-map'), {{
    center: OFFICE,
    zoom: 11,
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: false,
  }});
  // Office marker so reps can see their starting point.
  new google.maps.Marker({{
    position: OFFICE, map: _OM_MAP,
    title: 'Reform Chiropractic',
    icon: {{path: google.maps.SymbolPath.CIRCLE, scale: 14, fillColor: '#1e3a5f',
            fillOpacity: 1, strokeColor: '#fff', strokeWeight: 3}},
    label: {{text: '✦', color: '#fff', fontWeight: '700', fontSize: '14px'}},
    zIndex: 800,
  }});
  plotStops();
  // Live GPS — kept for admin visibility into where reps are in the field.
  if (navigator.geolocation) {{
    navigator.geolocation.watchPosition(function(pos) {{
      var here = {{lat: pos.coords.latitude, lng: pos.coords.longitude}};
      if (_OM_USER_MARKER) {{
        _OM_USER_MARKER.setPosition(here);
      }} else {{
        _OM_USER_MARKER = new google.maps.Marker({{
          position: here, map: _OM_MAP,
          icon: {{path: google.maps.SymbolPath.CIRCLE, scale: 8, fillColor: '#3b82f6',
                  fillOpacity: 1, strokeColor: '#fff', strokeWeight: 2}},
          title: 'You are here',
          zIndex: 1000,
        }});
        // On first fix, if we had no route to frame the map, center on the rep.
        if (!_OM_STOPS.length) {{
          _OM_MAP.panTo(here);
          _OM_MAP.setZoom(13);
        }}
      }}
    }}, function() {{}}, {{timeout: 10000, enableHighAccuracy: true}});
  }}
}}

function plotStops() {{
  _OM_MARKERS.forEach(function(m) {{ m.setMap(null); }});
  _OM_MARKERS = [];
  if (!_OM_STOPS.length) {{
    var sub = document.getElementById('om-sub');
    if (sub) sub.textContent = 'No route assigned today';
    document.getElementById('om-msg').textContent = 'No route scheduled — admin can assign one from the hub.';
    return;
  }}
  var bounds = new google.maps.LatLngBounds();
  bounds.extend(OFFICE);
  var plotted = 0;
  _OM_STOPS.forEach(function(stop, i) {{
    var lat = parseFloat(stop.lat), lng = parseFloat(stop.lng);
    if (!lat || !lng || isNaN(lat) || isNaN(lng)) return;
    var color = _STATUS_COLORS[stop.status] || '#4285f4';
    var marker = new google.maps.Marker({{
      position: {{lat: lat, lng: lng}}, map: _OM_MAP,
      label: {{text: String(i + 1), color: '#fff', fontWeight: '700', fontSize: '12px'}},
      icon: {{path: google.maps.SymbolPath.CIRCLE, scale: 14, fillColor: color,
              fillOpacity: 1, strokeColor: '#fff', strokeWeight: 2}},
      title: stop.name || '',
    }});
    var companyId = _OM_VENUE_TO_CO[stop.venue_id];
    var profileLink = companyId
      ? '<a href="/company/' + companyId + '" style="font-size:12px;color:#004ac6;font-weight:600;text-decoration:none">View full profile →</a>'
      : '';
    var iw = new google.maps.InfoWindow({{
      content: '<div style="font-family:system-ui;max-width:220px">' +
               '<div style="font-weight:700;font-size:13px;margin-bottom:4px">' + esc(stop.name || '(unnamed)') + '</div>' +
               (stop.address ? '<div style="font-size:11px;color:#64748b;margin-bottom:6px">' + esc(stop.address) + '</div>' : '') +
               '<div style="font-size:11px;color:' + color + ';font-weight:600;margin-bottom:6px">Stop ' + (i + 1) + ' • ' + esc(stop.status || 'Pending') + '</div>' +
               profileLink +
               '</div>',
    }});
    marker.addListener('click', function() {{ iw.open(_OM_MAP, marker); }});
    _OM_MARKERS.push(marker);
    bounds.extend(marker.getPosition());
    plotted++;
  }});
  var sub = document.getElementById('om-sub');
  if (sub && _OM_ROUTE) sub.textContent = (_OM_ROUTE.name || 'Your route') + ' • ' + plotted + ' stop' + (plotted === 1 ? '' : 's');
  document.getElementById('om-msg').textContent = '';
  if (plotted > 0) {{
    _OM_MAP.fitBounds(bounds, 60);
    if (_OM_MAP.getZoom() > 14) _OM_MAP.setZoom(14);
  }}
}}

loadOM();
"""
    return _mobile_page('m_outreach_map', 'Route Map', body, js, br, bt, user=user)
