"""Active route map + stop bottom sheet."""

import os

from hub.shared import (
    _mobile_page, _is_admin,
    T_GOR_VENUES, T_GOR_ACTS, T_GOR_BOXES, T_COMPANIES, T_EVENTS, T_LEADS,
)
from hub.guerilla import GFR_EXTRA_HTML, GFR_EXTRA_JS
from hub.contact_detail import contact_actions_js
from hub.lead_capture_ui import LEAD_CAPTURE_HTML, build_lead_capture_js


def _mobile_route_page(br: str, bt: str, user: dict = None,
                       route_id: int = None) -> str:
    """Renders the full-screen route map. If route_id is given, loads that
    specific route; otherwise loads the caller's active/draft route for today."""
    import datetime
    gk = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    user = user or {}
    today_str = datetime.date.today().isoformat()
    user_email = user.get('email', '')
    user_name = user.get('name', '')
    # Endpoint is chosen server-side so the same JS handles both paths.
    route_endpoint = f"/api/guerilla/routes/{int(route_id)}" if route_id else "/api/guerilla/routes/today"
    body = (
        # Full-screen map for route
        '<div class="m-map-wrap" id="rmap"></div>'
        # "No Active Routes" overlay (shown/hidden by JS)
        '<div id="rt-empty" style="display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:105;text-align:center;pointer-events:none">'
        '<div style="background:var(--bg2);border-radius:16px;padding:28px 36px;box-shadow:0 4px 20px rgba(0,0,0,.3)">'
        '<div style="font-size:18px;font-weight:700;color:var(--text)">No Active Routes</div>'
        '</div></div>'
        # Progress bar overlay at top — pad for iOS notch/Dynamic Island in standalone PWA mode
        '<div id="rt-progress" style="position:fixed;top:0;left:0;right:0;z-index:110;background:var(--bg2);padding:calc(10px + env(safe-area-inset-top)) 16px 10px;border-bottom:1px solid var(--border);display:none">'
        '<div style="display:flex;justify-content:space-between;align-items:center">'
        '<div id="rt-name" style="font-size:14px;font-weight:700"></div>'
        '<a href="/routes" style="font-size:12px;color:var(--text3);text-decoration:none">\u2190 Routes</a>'
        '</div>'
        '<div id="rt-count" style="font-size:12px;color:var(--text3);margin-top:3px"></div>'
        '<div style="margin-top:6px;background:var(--border);border-radius:4px;height:5px;overflow:hidden">'
        '<div id="rt-bar" style="height:100%;background:#ea580c;border-radius:4px;width:0%"></div>'
        '</div>'
        '<div id="rt-actions" style="margin-top:8px;display:none;gap:8px;flex-wrap:wrap">'
        '<a href="#" onclick="openFullDirections();return false" '
        'style="display:inline-block;padding:7px 12px;background:#ea580c;color:#fff;'
        'border-radius:8px;font-size:12px;font-weight:700;text-decoration:none">'
        '\U0001f9ed Open in Google Maps</a>'
        '<a href="#" onclick="openDirectionsSheet();return false" '
        'style="display:inline-block;padding:7px 12px;background:var(--bg3);color:var(--text);'
        'border:1px solid var(--border);border-radius:8px;font-size:12px;font-weight:700;'
        'text-decoration:none;margin-left:6px">'
        '\U0001f4cb Turn-by-turn</a>'
        '</div>'
        '</div>'
        # Stop bottom sheet (tap a marker)
        '<div class="m-sheet-backdrop" id="m-backdrop" onclick="closeRouteSheet()"></div>'
        '<div class="m-sheet" id="m-sheet">'
        '<div class="m-sheet-handle" onclick="closeRouteSheet()"></div>'
        '<div id="m-sheet-body" style="padding:0 0 20px"></div>'
        '</div>'
        # Turn-by-turn directions sheet (tap the button)
        '<div class="m-sheet-backdrop" id="d-backdrop" onclick="closeDirectionsSheet()"></div>'
        '<div class="m-sheet" id="d-sheet">'
        '<div class="m-sheet-handle" onclick="closeDirectionsSheet()"></div>'
        '<div id="d-sheet-body" style="padding:0 0 20px"></div>'
        '</div>'
        # Privacy indicator (location only shared while on route)
        # Lift above the iOS home-indicator safe area when in standalone PWA mode
        '<div id="loc-pill" style="display:none;position:fixed;left:10px;bottom:calc(10px + env(safe-area-inset-bottom));z-index:90;'
        'background:rgba(15,23,42,.72);color:#e2e8f0;border-radius:14px;padding:5px 10px;'
        'font-size:10px;font-weight:600;backdrop-filter:blur(6px)">📍 Location shared while on route</div>'
    )
    route_js = f"""
const RGK = {repr(gk)};
const _GGOR_VENUES = {T_GOR_VENUES};
const _GGOR_ACTS   = {T_GOR_ACTS};
const _GGOR_BOXES  = {T_GOR_BOXES};
const _GOFF_LAT = 33.9478, _GOFF_LNG = -118.1335;
const _STATUS_COLORS = {{'Pending':'#4285f4','In Progress':'#a855f7','Visited':'#059669','Skipped':'#f97316','Not Reached':'#ef4444'}};
const _SENT_COLORS_R = {{Green:'#059669',Yellow:'#f59e0b',Red:'#ef4444'}};
var _routeData = null, _rMap = null, _rMarkers = {{}}, _rPolyline = null, _rOfficeMarker = null;
var _rDirections = null;  // DirectionsRenderer for street-following polyline
var _rLastDirections = null;  // cached DirectionsResult for turn-by-turn sheet
var _rCurrentStop = null;  // currently selected stop (full venue data)
var _userLat = null, _userLng = null, _userMarker = null;
var _allBoxesCache = null;  // cached boxes for pickup badges

function _haversine(lat1, lng1, lat2, lng2) {{
  var R = 3958.8; // miles
  var dLat = (lat2-lat1)*Math.PI/180;
  var dLng = (lng2-lng1)*Math.PI/180;
  var a = Math.sin(dLat/2)*Math.sin(dLat/2)
        + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)
        * Math.sin(dLng/2)*Math.sin(dLng/2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}}

var _promptedStopIds = new Set();  // dedup geofence toasts across position updates
var _geofenceOpen = false;          // suppress new toasts while one is on screen
const _GEOFENCE_RADIUS_MI = 0.031;  // ~50m

if (navigator.geolocation) {{
  navigator.geolocation.watchPosition(function(pos) {{
    _userLat = pos.coords.latitude; _userLng = pos.coords.longitude;
    if (_rMap && _userMarker) _userMarker.setPosition({{lat:_userLat,lng:_userLng}});
    else if (_rMap) {{
      _userMarker = new google.maps.Marker({{position:{{lat:_userLat,lng:_userLng}},map:_rMap,
        icon:{{path:google.maps.SymbolPath.CIRCLE,scale:7,fillColor:'#2563eb',fillOpacity:1,strokeColor:'#fff',strokeWeight:2}},
        title:'You',zIndex:999}});
    }}
    checkGeofence(_userLat, _userLng);
  }}, function(){{}}, {{timeout:10000,enableHighAccuracy:true}});
}}

// ── Auto-check-in prompt ──────────────────────────────────────────────────
// When the rep walks within ~50m of a Pending stop, surface a one-time toast
// asking if they want to check in. Tapping Yes flips the stop to In Progress
// (stamps Arrived At) without opening any form. We dedup per stop so the rep
// isn't pestered every second the GPS updates.
function checkGeofence(lat, lng) {{
  if (_geofenceOpen) return;
  if (!_routeData || !_routeData.stops) return;
  if (typeof lat !== 'number' || typeof lng !== 'number') return;
  for (var i = 0; i < _routeData.stops.length; i++) {{
    var s = _routeData.stops[i];
    if (!s || s.status !== 'Pending') continue;
    if (_promptedStopIds.has(s.stop_id)) continue;
    var sLat = parseFloat(s.lat), sLng = parseFloat(s.lng);
    if (!sLat || !sLng) continue;
    var dist = _haversine(lat, lng, sLat, sLng);
    if (dist <= _GEOFENCE_RADIUS_MI) {{
      _promptedStopIds.add(s.stop_id);
      showGeofencePrompt(s);
      return;  // one at a time
    }}
  }}
}}

function showGeofencePrompt(stop) {{
  _geofenceOpen = true;
  var bg = document.createElement('div');
  bg.id = 'gf-prompt';
  bg.style.cssText = 'position:fixed;left:12px;right:12px;bottom:16px;z-index:1300;'
    + 'background:var(--bg2);border:1px solid var(--border);border-radius:14px;'
    + 'padding:14px 16px;box-shadow:0 6px 24px rgba(0,0,0,.35);font-family:inherit';
  bg.innerHTML =
    '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">'
    + '<span style="font-size:18px">\U0001f4cd</span>'
    + '<div style="flex:1;min-width:0">'
    + '<div style="font-size:14px;font-weight:700;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
    + esc(stop.name || 'this stop') + '</div>'
    + '<div style="font-size:11px;color:var(--text3)">You\\'re here — want to check in?</div>'
    + '</div></div>'
    + '<div style="display:flex;gap:8px">'
    + '<button onclick="dismissGeofence(true,'+stop.stop_id+')" '
    + 'style="flex:1;background:#a855f7;color:#fff;border:none;border-radius:10px;padding:11px;'
    + 'font-size:14px;font-weight:700;cursor:pointer;font-family:inherit">Yes, check in</button>'
    + '<button onclick="dismissGeofence(false,'+stop.stop_id+')" '
    + 'style="width:90px;background:var(--bg);color:var(--text2);border:1px solid var(--border);'
    + 'border-radius:10px;padding:11px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit">Not yet</button>'
    + '</div>';
  document.body.appendChild(bg);
}}

function dismissGeofence(accept, stopId) {{
  var el = document.getElementById('gf-prompt');
  if (el) el.remove();
  _geofenceOpen = false;
  if (accept) routeArrive(stopId);
}}

async function loadRoute() {{
  // Always init map first
  initRouteMap();
  try {{
    var [routeResp, boxes] = await Promise.all([
      fetch({route_endpoint!r}).then(function(r){{return r.json();}}),
      fetchAll(_GGOR_BOXES)
    ]);
    _routeData = routeResp;
    _allBoxesCache = boxes;
    if (!_routeData || !_routeData.route) {{
      document.getElementById('rt-empty').style.display = 'block';
      return;
    }}
    document.getElementById('rt-empty').style.display = 'none';
    updateProgress();
    renderRouteStops();
  }} catch(e) {{
    document.getElementById('rt-empty').style.display = 'block';
  }}
}}

function updateProgress() {{
  if (!_routeData || !_routeData.route) return;
  var stops = _routeData.stops || [];
  var visited = stops.filter(function(s){{return s.status==='Visited';}}).length;
  var skipped = stops.filter(function(s){{return s.status==='Skipped';}}).length;
  var notReached = stops.filter(function(s){{return s.status==='Not Reached';}}).length;
  var total = stops.length;
  var done = visited + skipped + notReached;
  var pct = total ? Math.round(done/total*100) : 0;
  document.getElementById('rt-progress').style.display = 'block';
  document.getElementById('rt-name').textContent = _routeData.route.name || 'Route';
  var summary = visited + ' visited';
  if (skipped) summary += ', ' + skipped + ' skipped';
  if (notReached) summary += ', ' + notReached + ' missed';
  summary += ' of ' + total + ' stops';
  // Total route distance (office → stop 1 → stop 2 → ...)
  var totalDist = 0;
  var prevLat = _GOFF_LAT, prevLng = _GOFF_LNG;
  var anyStop = false;
  stops.forEach(function(s) {{
    var sLat = parseFloat(s.lat), sLng = parseFloat(s.lng);
    if (sLat && sLng) {{
      totalDist += _haversine(prevLat, prevLng, sLat, sLng);
      prevLat = sLat; prevLng = sLng;
      anyStop = true;
    }}
  }});
  if (anyStop) totalDist += _haversine(prevLat, prevLng, _GOFF_LAT, _GOFF_LNG);
  if (totalDist > 0) summary += ' \u2022 ' + totalDist.toFixed(1) + ' mi total';
  document.getElementById('rt-count').textContent = summary;
  document.getElementById('rt-bar').style.width = pct + '%';
  var actionsEl = document.getElementById('rt-actions');
  if (actionsEl) actionsEl.style.display = anyStop ? 'flex' : 'none';
}}

function initRouteMap() {{
  if (_rMap) return;  // already initialized
  if (!RGK) return;
  window._rMapReady = function() {{
    var el = document.getElementById('rmap');
    el.style.height = el.offsetHeight + 'px';
    _rMap = new google.maps.Map(el, {{
      center: {{lat: _GOFF_LAT, lng: _GOFF_LNG}}, zoom: 13,
      mapTypeControl: false, streetViewControl: false,
      styles: [{{featureType:'poi',stylers:[{{visibility:'off'}}]}},
               {{featureType:'transit',stylers:[{{visibility:'off'}}]}}]
    }});
    setTimeout(function(){{ google.maps.event.trigger(_rMap, 'resize'); }}, 100);
    // If route data already loaded, render stops
    if (_routeData && _routeData.route) renderRouteStops();
  }};
  var s = document.createElement('script');
  s.src = 'https://maps.googleapis.com/maps/api/js?key=' + RGK + '&callback=_rMapReady';
  s.async = true; document.head.appendChild(s);
}}

function renderRouteStops() {{
  if (!_rMap || !_routeData || !_routeData.route) return;
  // Clear existing markers/polyline/directions
  Object.values(_rMarkers).forEach(function(m){{ m.setMap(null); }});
  _rMarkers = {{}};
  if (_rOfficeMarker) {{ _rOfficeMarker.setMap(null); _rOfficeMarker = null; }}
  if (_rPolyline) {{ _rPolyline.setMap(null); _rPolyline = null; }}
  if (_rDirections) {{ _rDirections.setMap(null); _rDirections = null; }}
  _rLastDirections = null;
  var stops = _routeData.stops || [];
  var bounds = new google.maps.LatLngBounds();
  var pathCoords = [];

  // Start point: Reform Chiropractic office
  var officePos = {{lat: _GOFF_LAT, lng: _GOFF_LNG}};
  pathCoords.push(officePos);
  bounds.extend(officePos);
  _rOfficeMarker = new google.maps.Marker({{
    position: officePos, map: _rMap,
    label: {{text: '\u2726', color: '#fff', fontWeight: '700', fontSize: '14px'}},
    icon: {{path:google.maps.SymbolPath.CIRCLE, scale:16, fillColor:'#1e3a5f', fillOpacity:1, strokeColor:'#fff', strokeWeight:3}},
    title: 'Reform Chiropractic',
    zIndex: 900
  }});

  stops.forEach(function(stop, i) {{
    var lat = parseFloat(stop.lat), lng = parseFloat(stop.lng);
    if (!lat || !lng) return;
    var pos = {{lat:lat, lng:lng}};
    pathCoords.push(pos);
    bounds.extend(pos);
    var color = _STATUS_COLORS[stop.status] || '#4285f4';
    var marker = new google.maps.Marker({{
      position: pos, map: _rMap,
      label: {{text: String(i+1), color: '#fff', fontWeight: '700', fontSize: '12px'}},
      icon: {{path:google.maps.SymbolPath.CIRCLE, scale:14, fillColor:color, fillOpacity:1, strokeColor:'#fff', strokeWeight:2}},
      title: stop.name || ''
    }});
    (function(s) {{ marker.addListener('click', function() {{ openRouteSheet(s); }}); }})(stop);
    _rMarkers[stop.stop_id] = marker;
  }});
  // Close the loop: return to office at the end of the route.
  if (pathCoords.length > 1) {{
    pathCoords.push(officePos);
    _drawDirectionsOrFallback(pathCoords);
  }}
  if (pathCoords.length) {{
    _rMap.fitBounds(bounds, {{top:70,bottom:80,left:20,right:20}});
  }}
}}

// Draw a road-following polyline via the Directions API. Falls back to a
// simple straight-line Polyline on error or when we exceed Google's
// 25-waypoint cap (origin + destination + up to 23 intermediate waypoints).
function _drawDirectionsOrFallback(pathCoords) {{
  var origin = pathCoords[0];
  var destination = pathCoords[pathCoords.length - 1];
  var mid = pathCoords.slice(1, -1);
  var straightLine = function() {{
    _rPolyline = new google.maps.Polyline({{
      path: pathCoords, geodesic: true,
      strokeColor: '#ea580c', strokeOpacity: 0.7, strokeWeight: 3,
      map: _rMap
    }});
  }};
  if (mid.length > 23) {{
    console.log('[route] >23 waypoints; falling back to straight-line polyline');
    straightLine();
    return;
  }}
  var waypoints = mid.map(function(c) {{
    return {{location: new google.maps.LatLng(c.lat, c.lng), stopover: true}};
  }});
  var ds = new google.maps.DirectionsService();
  _rDirections = new google.maps.DirectionsRenderer({{
    map: _rMap,
    suppressMarkers: true,    // we already draw numbered markers
    preserveViewport: true,   // fitBounds will run on our markers below
    polylineOptions: {{strokeColor: '#ea580c', strokeOpacity: 0.8, strokeWeight: 4}},
  }});
  ds.route({{
    origin: origin, destination: destination, waypoints: waypoints,
    travelMode: google.maps.TravelMode.DRIVING,
    optimizeWaypoints: false,  // respect admin's stop order
  }}, function(res, status) {{
    if (status === 'OK') {{
      _rDirections.setDirections(res);
      _rLastDirections = res;
    }} else {{
      console.log('[route] directions failed (' + status + '); falling back to straight-line');
      if (_rDirections) {{ _rDirections.setMap(null); _rDirections = null; }}
      _rLastDirections = null;
      straightLine();
    }}
  }});
}}

// Hands off the full route to Google Maps for turn-by-turn directions:
// office -> each stop in order -> office. Google's /maps/dir/?api=1 URL
// supports up to 9 intermediate waypoints; if the route has more stops we
// silently truncate to the first 9 (the polyline on the page still shows
// all of them via the Directions API which allows 23).
function openFullDirections() {{
  if (!_routeData || !_routeData.stops || !_routeData.stops.length) return;
  var office = _GOFF_LAT + ',' + _GOFF_LNG;
  var waypoints = _routeData.stops.map(function(s) {{
    var lat = parseFloat(s.lat), lng = parseFloat(s.lng);
    return (lat && lng) ? (lat + ',' + lng) : null;
  }}).filter(Boolean);
  if (!waypoints.length) return;
  if (waypoints.length > 9) {{
    console.log('[route] >9 stops; Google Maps URL truncated to first 9');
    waypoints = waypoints.slice(0, 9);
  }}
  var url = 'https://www.google.com/maps/dir/?api=1'
    + '&origin=' + encodeURIComponent(office)
    + '&destination=' + encodeURIComponent(office)
    + '&waypoints=' + encodeURIComponent(waypoints.join('|'))
    + '&travelmode=driving';
  window.open(url, '_blank');
}}

// Turn-by-turn sheet: each leg (office -> stop 1, stop 1 -> stop 2, ...,
// last stop -> office) is a collapsible header showing distance/duration;
// tapping expands to reveal Google's step-by-step instructions for that leg.
function openDirectionsSheet() {{
  var body = document.getElementById('d-sheet-body');
  var stops = (_routeData && _routeData.stops) || [];
  if (!_rLastDirections || !_rLastDirections.routes || !_rLastDirections.routes[0]) {{
    body.innerHTML = '<div style="padding:24px 18px;color:var(--text3);font-size:13px;text-align:center">'
      + 'Turn-by-turn directions are not available for this route yet.<br><br>'
      + 'This usually means the Directions API fell back to a straight line '
      + '(too many stops, or the API call failed). Use <b>Open in Google Maps</b> '
      + 'for full turn-by-turn.</div>';
  }} else {{
    var legs = _rLastDirections.routes[0].legs || [];
    var html = '<div style="padding:16px 18px 10px;border-bottom:1px solid var(--border)">';
    html += '<div style="font-size:16px;font-weight:700">Turn-by-turn</div>';
    html += '<div style="font-size:12px;color:var(--text3);margin-top:3px">Tap a leg to expand</div>';
    html += '</div>';
    legs.forEach(function(leg, i) {{
      // Leg i goes from stop i-1 (or office) to stop i (or office).
      var fromName = (i === 0) ? 'Reform Office'
        : ((stops[i-1] && stops[i-1].name) || ('Stop ' + i));
      var toName = (i === legs.length - 1) ? 'Reform Office'
        : ((stops[i] && stops[i].name) || ('Stop ' + (i+1)));
      var dist = (leg.distance && leg.distance.text) || '';
      var dur = (leg.duration && leg.duration.text) || '';
      html += '<div style="border-bottom:1px solid var(--border)">';
      html += '<div onclick="toggleLeg(' + i + ')" style="padding:12px 18px;cursor:pointer;display:flex;justify-content:space-between;align-items:center">';
      html += '<div style="flex:1;min-width:0">';
      html += '<div style="font-size:14px;font-weight:600">' + esc(fromName) + ' → ' + esc(toName) + '</div>';
      html += '<div style="font-size:12px;color:var(--text3);margin-top:2px">' + esc(dist) + (dur ? ' · ' + esc(dur) : '') + '</div>';
      html += '</div>';
      html += '<div id="d-chev-' + i + '" style="font-size:14px;color:var(--text3);margin-left:10px">▾</div>';
      html += '</div>';
      html += '<div id="d-steps-' + i + '" style="display:none;padding:0 18px 12px">';
      (leg.steps || []).forEach(function(step, j) {{
        var sDist = (step.distance && step.distance.text) || '';
        html += '<div style="padding:8px 0;border-top:1px solid var(--border);display:flex;gap:10px">';
        html += '<div style="color:var(--text3);font-size:12px;min-width:22px">' + (j+1) + '.</div>';
        html += '<div style="flex:1">';
        // instructions is HTML from Google (e.g. "Turn <b>right</b> onto ...")
        html += '<div style="font-size:13px;line-height:1.4">' + (step.instructions || '') + '</div>';
        if (sDist) html += '<div style="font-size:11px;color:var(--text3);margin-top:3px">' + esc(sDist) + '</div>';
        html += '</div></div>';
      }});
      html += '</div></div>';
    }});
    body.innerHTML = html;
  }}
  document.getElementById('d-sheet').classList.add('open');
  document.getElementById('d-backdrop').classList.add('open');
}}

function closeDirectionsSheet() {{
  document.getElementById('d-sheet').classList.remove('open');
  document.getElementById('d-backdrop').classList.remove('open');
}}

function toggleLeg(idx) {{
  var steps = document.getElementById('d-steps-' + idx);
  var chev = document.getElementById('d-chev-' + idx);
  if (!steps) return;
  if (steps.style.display === 'none') {{
    steps.style.display = 'block';
    if (chev) chev.textContent = '▴';
  }} else {{
    steps.style.display = 'none';
    if (chev) chev.textContent = '▾';
  }}
}}

function closeRouteSheet() {{
  document.getElementById('m-sheet').classList.remove('open');
  document.getElementById('m-backdrop').classList.remove('open');
  _rCurrentStop = null;
}}

function openRouteSheet(stop) {{
  _rCurrentStop = stop;
  document.getElementById('m-sheet').classList.add('open');
  document.getElementById('m-backdrop').classList.add('open');
  document.getElementById('m-sheet-body').innerHTML = renderRouteSheet(stop);
  // Load venue data for tabs
  loadRouteVenueData(stop);
}}

function _getBoxPickupInfo(venueId) {{
  if (!_allBoxesCache) return null;
  var activeBoxes = _allBoxesCache.filter(function(b) {{
    var biz = b['Business'];
    var st = (b['Status'] && b['Status'].value) || b['Status'] || '';
    return st === 'Active' && Array.isArray(biz) && biz.some(function(r){{return r.id===venueId;}});
  }});
  if (!activeBoxes.length) return null;
  var dueCount = 0;
  activeBoxes.forEach(function(b) {{
    if (b['Date Placed']) {{
      var age = -daysUntil(b['Date Placed']);
      var pd = parseInt(b['Pickup Days']) || 14;
      if (age >= pd) dueCount++;
    }}
  }});
  return {{total: activeBoxes.length, due: dueCount}};
}}

function renderRouteSheet(stop) {{
  var name = esc(stop.name || '(unnamed)');
  var addr = stop.address || '';
  var status = stop.status || 'Pending';
  var sc = _STATUS_COLORS[status] || '#4285f4';
  var id = stop.stop_id;

  // Header
  var html = '<div class="m-sheet-sec">';
  html += '<div style="font-size:17px;font-weight:700;margin-bottom:6px">' + name + '</div>';
  html += '<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">';
  html += '<span style="background:'+sc+'20;color:'+sc+';font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600">' + esc(status) + '</span>';
  html += '<span style="font-size:11px;color:var(--text3)">Stop ' + (stop.order||'') + '</span>';
  // Distance from previous stop (or office if first)
  if (stop.lat && stop.lng && _routeData && _routeData.stops) {{
    var idx = _routeData.stops.indexOf(stop);
    var prevLat, prevLng, fromLabel;
    if (idx <= 0) {{
      prevLat = _GOFF_LAT; prevLng = _GOFF_LNG; fromLabel = 'from office';
    }} else {{
      var prev = _routeData.stops[idx-1];
      prevLat = parseFloat(prev.lat); prevLng = parseFloat(prev.lng);
      fromLabel = 'from prev stop';
    }}
    if (prevLat && prevLng) {{
      var dist = _haversine(prevLat, prevLng, parseFloat(stop.lat), parseFloat(stop.lng));
      html += '<span style="font-size:10px;color:var(--text3);background:var(--bg);padding:2px 6px;border-radius:4px">' + dist.toFixed(1) + ' mi ' + fromLabel + '</span>';
    }}
  }}
  // Box pickup badge (server-provided via stop.pending_box for authoritative state)
  if (stop.pending_box) {{
    var pb = stop.pending_box;
    var overdueLbl = pb.overdue_by > 0 ? (' (' + pb.overdue_by + 'd overdue)') : '';
    html += '<span style="background:#f59e0b20;color:#f59e0b;font-size:10px;padding:2px 7px;border-radius:4px;font-weight:600">\U0001f4e6 Box pending pickup' + overdueLbl + '</span>';
  }} else {{
    // Fallback: show count of active boxes if none pending
    var boxInfo = _getBoxPickupInfo(stop.venue_id);
    if (boxInfo && boxInfo.total > 0) {{
      html += '<span style="background:#05966920;color:#059669;font-size:10px;padding:2px 7px;border-radius:4px;font-weight:600">\U0001f4e6 '+boxInfo.total+' active box'+(boxInfo.total>1?'es':'')+'</span>';
    }}
  }}
  html += '</div>';
  // Pending pickup notice (prominent, under header)
  if (stop.pending_box && stop.pending_box.location) {{
    html += '<div style="margin-top:8px;padding:10px 12px;background:#f59e0b15;border:1px solid #f59e0b40;border-radius:8px;font-size:12px;color:#f59e0b"><strong>\U0001f4e6 Pick up the box while you\\'re here.</strong> Location: ' + esc(stop.pending_box.location) + '. It will be marked picked up automatically when you check in.</div>';
  }} else if (stop.pending_box) {{
    html += '<div style="margin-top:8px;padding:10px 12px;background:#f59e0b15;border:1px solid #f59e0b40;border-radius:8px;font-size:12px;color:#f59e0b"><strong>\U0001f4e6 Pick up the box while you\\'re here.</strong> It will be marked picked up automatically when you check in.</div>';
  }}
  html += '</div>';

  // Tab bar
  html += '<div class="m-tabs">';
  html += '<div class="m-tab active" onclick="mSheetTab(this,\\'rp-info-'+id+'\\')">Info</div>';
  html += '<div class="m-tab" onclick="mSheetTab(this,\\'rp-leads-'+id+'\\')">Leads</div>';
  html += '<div class="m-tab" onclick="mSheetTab(this,\\'rp-evts-'+id+'\\')">Events</div>';
  html += '<div class="m-tab" onclick="mSheetTab(this,\\'rp-boxes-'+id+'\\')">Boxes</div>';
  html += '</div>';

  // Info tab
  html += '<div class="m-panel active" id="rp-info-'+id+'" style="padding:12px 16px">';
  // Briefing card \u2014 populated by loadRouteVenueData with last visit, last
  // note, last contact, promised follow-up, open-lead count, sentiment dot.
  html += '<div id="rv-briefing-'+id+'" style="display:none;margin-bottom:10px"></div>';
  if (addr) {{
    var mapsLink = 'https://maps.google.com/?q='+encodeURIComponent(addr);
    html += '<div style="margin-bottom:8px;font-size:13px">\U0001f4cd '+esc(addr)+' <a href="'+mapsLink+'" target="_blank" style="color:#3b82f6;font-size:12px">Navigate \u2197</a></div>';
  }}
  // Action buttons by status. Pending \u2192 Arrive (one tap \u2192 In Progress, sets
  // Arrived At); In Progress \u2192 Check In (opens visit form, marks Visited,
  // sets Departed At + computes Duration Mins).
  if (status === 'Pending') {{
    html += '<div style="padding:4px 0 12px;display:flex;gap:10px">';
    html += '<button onclick="routeArrive('+id+')" style="flex:1;background:#a855f7;color:#fff;border:none;border-radius:10px;padding:14px;font-size:15px;font-weight:700;cursor:pointer">\U0001f4cd Arrive</button>';
    html += '<button onclick="routeSkip('+id+')" style="width:70px;background:var(--bg);color:var(--text2);border:1px solid var(--border);border-radius:10px;padding:14px;font-size:12px;font-weight:600;cursor:pointer">Skip</button>';
    html += '<button onclick="routeNotReached('+id+')" style="width:70px;background:var(--bg);color:#ef4444;border:1px solid #ef444440;border-radius:10px;padding:14px;font-size:11px;font-weight:600;cursor:pointer;line-height:1.2">Didn\\\'t<br>Get To</button>';
    html += '</div>';
  }} else if (status === 'In Progress') {{
    html += '<div style="padding:4px 0 12px;display:flex;gap:10px">';
    html += '<button onclick="routeCheckIn('+id+')" style="flex:1;background:#ea580c;color:#fff;border:none;border-radius:10px;padding:14px;font-size:15px;font-weight:700;cursor:pointer">Check In</button>';
    html += '<button onclick="routeSkip('+id+')" style="width:70px;background:var(--bg);color:var(--text2);border:1px solid var(--border);border-radius:10px;padding:14px;font-size:12px;font-weight:600;cursor:pointer">Skip</button>';
    html += '<button onclick="routeNotReached('+id+')" style="width:70px;background:var(--bg);color:#ef4444;border:1px solid #ef444440;border-radius:10px;padding:14px;font-size:11px;font-weight:600;cursor:pointer;line-height:1.2">Didn\\\'t<br>Get To</button>';
    html += '</div>';
  }} else {{
    html += '<div style="padding:4px 0 12px"><button onclick="routeCheckInForm()" style="width:100%;background:#ea580c;color:#fff;border:none;border-radius:10px;padding:14px;font-size:15px;font-weight:700;cursor:pointer">Check In</button></div>';
  }}
  html += '<div id="rv-info-'+id+'" style="color:var(--text3);font-size:13px">Loading venue details\u2026</div>';
  html += '</div>';

  // Leads tab
  html += '<div class="m-panel" id="rp-leads-'+id+'" style="padding:12px 16px">';
  html += '<div id="rv-leads-'+id+'" style="color:var(--text3);font-size:13px">Loading\u2026</div>';
  html += '</div>';

  // Events tab
  html += '<div class="m-panel" id="rp-evts-'+id+'" style="padding:12px 16px">';
  html += '<div class="m-sheet-lbl">Schedule Event</div>';
  html += '<div style="display:grid;gap:8px;margin-bottom:14px">';
  html += '<button onclick="scheduleRouteEvent(\\'Mobile Massage Service\\')" style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:12px 16px;font-size:14px;font-weight:600;cursor:pointer;min-height:48px;text-align:left">\U0001f486 Mobile Massage</button>';
  html += '<button onclick="scheduleRouteEvent(\\'Lunch and Learn\\')" style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:12px 16px;font-size:14px;font-weight:600;cursor:pointer;min-height:48px;text-align:left">\U0001f37d\ufe0f Lunch & Learn</button>';
  html += '<button onclick="scheduleRouteEvent(\\'Health Assessment Screening\\')" style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:12px 16px;font-size:14px;font-weight:600;cursor:pointer;min-height:48px;text-align:left">\U0001fa7a Health Assessment</button>';
  html += '</div>';
  html += '<div class="m-sheet-lbl">Event History</div>';
  html += '<div id="rv-evts-'+id+'" style="color:var(--text3);font-size:13px">Loading\u2026</div>';
  html += '</div>';

  // Boxes tab
  html += '<div class="m-panel" id="rp-boxes-'+id+'" style="padding:12px 16px">';
  html += '<div id="rv-boxes-'+id+'" style="color:var(--text3);font-size:13px">Loading\u2026</div>';
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:12px 0">';
  html += '<div class="m-sheet-lbl">\U0001f4e6 Place New Box</div>';
  html += '<div style="display:grid;gap:8px">';
  html += '<input type="text" id="rv-box-loc-'+id+'" placeholder="Location (e.g. Front desk)" style="background:var(--bg);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:10px 12px;font-size:14px">';
  html += '<input type="text" id="rv-box-contact-'+id+'" placeholder="Contact person" style="background:var(--bg);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:10px 12px;font-size:14px">';
  html += '<div style="display:flex;align-items:center;gap:8px"><span style="font-size:12px;color:var(--text3);white-space:nowrap">Pickup in</span><input type="number" id="rv-box-days-'+id+'" value="14" min="1" max="90" style="width:60px;background:var(--bg);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:10px 12px;font-size:14px;text-align:center"><span style="font-size:12px;color:var(--text3)">days</span></div>';
  html += '<button onclick="placeRouteBox('+id+')" style="background:#059669;color:#fff;border:none;border-radius:8px;padding:10px 14px;font-size:14px;font-weight:600;cursor:pointer;min-height:44px">Place Box</button>';
  html += '<div id="rv-box-st-'+id+'" style="font-size:12px;text-align:center;min-height:14px"></div>';
  html += '</div></div>';

  return html;
}}

// Tab switching (reuse from mobile map)
function mSheetTab(el, panelId) {{
  document.querySelectorAll('.m-tab').forEach(function(t){{t.classList.remove('active');}});
  document.querySelectorAll('.m-panel').forEach(function(p){{p.classList.remove('active');}});
  el.classList.add('active');
  var panel = document.getElementById(panelId);
  if (panel) panel.classList.add('active');
}}

// Load venue data for the route stop sheet
async function loadRouteVenueData(stop) {{
  // Get venue ID from the stop's venue link
  var venueId = stop.venue_id;
  if (!venueId) return;
  // Load venue details, activities, events, boxes, companies, leads in parallel
  var results = await Promise.all([
    fetchAll(_GGOR_VENUES), fetchAll(_GGOR_ACTS), fetchAll(_GGOR_BOXES),
    fetchAll({T_COMPANIES}), fetchAll({T_LEADS})
  ]);
  var venues = results[0], acts = results[1], boxes = results[2], companies = results[3], leads = results[4];
  var v = venues.find(function(x){{return x.id === venueId;}});
  if (!v) return;
  var id = stop.stop_id;
  var companyId = buildVenueCompanyMap(companies)[venueId];

  // Pull T_ACTIVITIES rows for the linked company so sentiment + photos
  // logged via the company-detail composer show up in this venue's history.
  // T_GOR_ACTS rows (legacy guerilla flow) don't have those fields; merging
  // here lets the briefing card and Visit History render uniformly.
  var compActs = [];
  if (companyId) {{
    try {{
      var car = await fetch('/api/companies/' + companyId + '/activities');
      if (car.ok) compActs = await car.json();
    }} catch (e) {{}}
  }}
  var venueActs = acts.filter(function(a) {{
    var lf = a['Business'];
    return Array.isArray(lf) && lf.some(function(r){{return r.id===venueId;}});
  }});
  var allActs = venueActs.concat(compActs).sort(function(a,b) {{
    var da = a['Date'] || (a['Created']||'').slice(0,10);
    var db = b['Date'] || (b['Created']||'').slice(0,10);
    return (db||'').localeCompare(da||'');
  }});

  // ── Briefing card ───────────────────────────────────────────────────────
  var briefEl = document.getElementById('rv-briefing-' + id);
  if (briefEl) {{
    var brief = '';
    var latest = allActs[0];
    if (latest) {{
      var sent = (latest.Sentiment && latest.Sentiment.value) || latest.Sentiment || '';
      var dot = (sent && _SENT_COLORS_R[sent])
        ? '<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:'+_SENT_COLORS_R[sent]+';margin-right:6px;vertical-align:middle"></span>'
        : '';
      var dStr = latest['Date'] || (latest['Created']||'').slice(0,10);
      var daysAgo = '';
      if (dStr) {{
        var d = new Date(dStr);
        if (!isNaN(d.getTime())) {{
          var diff = Math.floor((new Date() - d) / 86400000);
          daysAgo = diff <= 0 ? 'today' : (diff === 1 ? '1d ago' : diff + 'd ago');
        }}
      }}
      brief += '<div style="font-size:13px;line-height:1.5;color:var(--text2)">';
      if (daysAgo) brief += '<div>'+dot+'<strong>Last visit</strong> · '+esc(daysAgo)+'</div>';
      var noteText = latest.Summary || '';
      if (noteText) {{
        var note = noteText.length > 80 ? noteText.slice(0, 80) + '…' : noteText;
        brief += '<div style="margin-top:4px;font-style:italic;color:var(--text)">"'+esc(note)+'"</div>';
      }}
      var person = latest['Contact Person'] || '';
      if (person) brief += '<div style="margin-top:4px">\U0001f464 '+esc(person)+'</div>';
      brief += '</div>';
    }} else {{
      brief += '<div style="font-size:13px;color:var(--text3);font-style:italic">No prior visits</div>';
    }}
    var fuDateB = v['Follow-Up Date'] || '';
    if (fuDateB) {{
      brief += '<div style="margin-top:4px;font-size:13px;color:var(--text2)">\U0001f4c5 Promised: <strong>'+esc(fuDateB)+'</strong></div>';
    }}
    var vNameLower = (v['Name']||'').trim().toLowerCase();
    var _openSet = ['New','Contacted','Appointment Set','Patient Seen'];
    var openLeads = leads.filter(function(L) {{
      var src = (L['Source']||'').trim().toLowerCase();
      if (!src || src !== vNameLower) return false;
      var st = (L['Status'] && L['Status'].value) || L['Status'] || 'New';
      return _openSet.indexOf(st) !== -1;
    }}).length;
    if (openLeads > 0) {{
      brief += '<div style="margin-top:4px;font-size:13px;color:var(--text2)">\U0001f3af <strong>'+openLeads+'</strong> open lead'+(openLeads>1?'s':'')+'</div>';
    }}
    briefEl.innerHTML =
      '<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:10px 12px">' +
      '<div style="font-size:10px;color:var(--text3);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;font-weight:700">Briefing</div>' +
      brief +
      '</div>';
    briefEl.style.display = 'block';
  }}

  // Fill Info tab
  var infoEl = document.getElementById('rv-info-' + id);
  if (infoEl && v) {{
    var ih = '';
    var phone = v['Phone'] || '';
    var website = v['Website'] || '';
    var fu = v['Follow-Up Date'] || '';
    var notesRaw = v['Notes'] || '';
    var _placeId = v['Google Place ID'] || '';
    var gmUrl = v['Google Maps URL'] || (_placeId ? 'https://www.google.com/maps/place/?q=place_id:' + _placeId : '');
    if (phone) ih += '<div style="margin-bottom:8px">\U0001f4de <a href="tel:'+esc(phone)+'" style="color:var(--text1)">'+esc(phone)+'</a></div>';
    if (website) ih += '<div style="margin-bottom:8px">\U0001f310 <a href="'+esc(website)+'" target="_blank" style="color:#3b82f6">'+esc(website)+'</a></div>';
    if (gmUrl) ih += '<div style="margin-bottom:8px"><a href="'+esc(gmUrl)+'" target="_blank" style="color:#3b82f6;font-size:12px">Google Maps \u2197</a></div>';
    if (companyId) ih += '<div style="margin-bottom:8px"><a href="/company/'+companyId+'" style="color:#3b82f6;font-size:13px;font-weight:600">View full profile \u2192</a></div>';
    ih += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
    ih += '<div class="m-sheet-lbl">Contact Status</div>';
    var stOpts = IS_ADMIN ? ['Not Contacted','Contacted','In Discussion','Active Partner'] : ['Not Contacted','Contacted','In Discussion'];
    var curSt = (v['Contact Status'] && v['Contact Status'].value) || v['Contact Status'] || '';
    ih += '<select onchange="updateRouteVenueStatus('+venueId+',this.value)" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:8px 10px;font-size:14px;margin-bottom:10px"' + (curSt==='Active Partner' && !IS_ADMIN ? ' disabled' : '') + '>';
    stOpts.forEach(function(s) {{ ih += '<option'+(curSt===s?' selected':'')+'>'+s+'</option>'; }});
    ih += '</select>';
    // ── Follow-Up Date ──────────────────────────────────────────────
    ih += '<div class="m-sheet-lbl">\U0001f5d3\ufe0f Follow-Up Date</div>';
    ih += '<div style="display:flex;gap:6px;margin-bottom:4px">';
    ih += '<input type="date" id="rv-fu-'+id+'" value="'+esc(fu)+'" style="flex:1;background:var(--bg);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:8px 10px;font-size:14px">';
    ih += '<button onclick="mRouteSaveFollowUp()" style="background:#3b82f6;color:#fff;border:none;border-radius:8px;padding:8px 14px;font-size:13px;font-weight:600;cursor:pointer;min-width:60px;min-height:40px">Save</button>';
    ih += '</div>';
    ih += '<div id="rv-fu-st-'+id+'" style="font-size:11px;margin-bottom:10px;min-height:14px"></div>';
    // ── Notes (read + add) ──────────────────────────────────────────
    ih += '<div class="m-sheet-lbl">\U0001f4dd Notes</div>';
    ih += '<div id="rv-notes-display-'+id+'" style="max-height:120px;overflow-y:auto;background:var(--card);border-radius:8px;padding:8px 10px;border:1px solid var(--border);font-size:13px;margin-bottom:6px">';
    ih += renderNotesM(notesRaw) + '</div>';
    ih += '<div style="display:flex;gap:6px">';
    ih += '<input type="text" id="rv-note-in-'+id+'" placeholder="Add a note\u2026" style="flex:1;background:var(--bg);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:8px 10px;font-size:14px">';
    ih += '<button onclick="mRouteAddNote()" style="background:#e94560;color:#fff;border:none;border-radius:8px;padding:8px 14px;font-size:13px;font-weight:600;cursor:pointer;min-width:50px;min-height:40px">Add</button>';
    ih += '</div>';
    ih += '<div id="rv-note-st-'+id+'" style="font-size:11px;margin-top:4px;min-height:14px"></div>';
    // ── Visit History (merged from T_GOR_ACTS + T_ACTIVITIES) ──────
    var historyActs = allActs.slice(0, 10);
    ih += '<hr style="border:none;border-top:1px solid var(--border);margin:14px 0 10px">';
    ih += '<div class="m-sheet-lbl">Visit History</div>';
    if (historyActs.length) {{
      ih += historyActs.map(function(a) {{
        var t = (a['Type'] && a['Type'].value) || a['Type'] || '';
        var o = (a['Outcome'] && a['Outcome'].value) || a['Outcome'] || '';
        var d = a['Date'] || (a['Created']||'').slice(0,10);
        var sm = a['Summary'] || '';
        var sentV = (a.Sentiment && a.Sentiment.value) || a.Sentiment || '';
        var photo = (a['Photo URL'] || '').trim();
        var audio = (a['Audio URL'] || '').trim();
        var sDot = (sentV && _SENT_COLORS_R[sentV])
          ? '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:'+_SENT_COLORS_R[sentV]+';margin-right:5px;vertical-align:middle"></span>'
          : '';
        var parts = [];
        if (t) parts.push('<span style="font-weight:600">'+esc(t)+'</span>');
        if (o) parts.push(esc(o));
        var head = sDot + parts.join(' — ');
        var thumb = photo
          ? '<div style="margin-top:4px"><img src="'+esc(photo)+'" onclick="openRoutePhotoLightbox(\\''+esc(photo)+'\\')" style="max-width:110px;max-height:80px;border-radius:6px;border:1px solid var(--border);cursor:pointer;object-fit:cover"></div>'
          : '';
        var player = audio
          ? '<div style="margin-top:4px"><audio controls preload="none" src="'+esc(audio)+'" style="width:100%;height:30px"></audio></div>'
          : '';
        return '<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:13px">'
             + head
             + (sm ? '<div style="font-size:12px;color:var(--text2);margin-top:2px">'+esc(sm)+'</div>' : '')
             + player
             + thumb
             + (d ? '<div style="font-size:11px;color:var(--text3);margin-top:2px">'+esc(d)+'</div>' : '')
             + '</div>';
      }}).join('');
    }} else {{
      ih += '<div style="color:var(--text3);font-size:13px;padding:4px 0">No visits logged yet.</div>';
    }}
    infoEl.innerHTML = ih;
  }}

  // Fill Activity tab — log-new form + history
  var leadsEl = document.getElementById('rv-leads-' + id);
  if (leadsEl) {{
    // Match leads to this business by Source field (T_LEADS has no direct
    // Company link). When a lead is captured via our in-stop form, Source
    // is pre-filled with the referring company/venue name, so this works.
    var vName = (v['Name'] || '').trim().toLowerCase();
    var cName = '';
    if (companyId) {{
      var cRow = companies.find(function(x){{return x.id === companyId;}});
      if (cRow) cName = (cRow.Name || '').trim().toLowerCase();
    }}
    var myLeads = leads.filter(function(L) {{
      var src = (L['Source'] || '').trim().toLowerCase();
      return src && (src === vName || (cName && src === cName));
    }}).sort(function(a,b) {{
      return (b['Created']||'').localeCompare(a['Created']||'');
    }});
    var lh = '<div style="margin-bottom:12px">';
    lh += '<button onclick="openRouteLeadCapture()" style="width:100%;background:#ea580c;color:#fff;border:none;border-radius:8px;padding:12px;font-size:14px;font-weight:700;cursor:pointer;min-height:44px">+ Capture Lead</button>';
    lh += '</div>';
    if (myLeads.length) {{
      var stColors = {{'New':'#3b82f6','Contacted':'#ea580c','Appointment Set':'#7c3aed','Patient Seen':'#0891b2','Converted':'#059669','Dropped':'#9ca3af'}};
      lh += myLeads.map(function(L) {{
        var nm = L['Name'] || '(no name)';
        var ph = L['Phone'] || '';
        var rs = (L['Reason'] && L['Reason'].value) || L['Reason'] || '';
        var st = (L['Status'] && L['Status'].value) || L['Status'] || 'New';
        var dt = (L['Created'] || '').slice(0,10);
        var col = stColors[st] || '#6b7280';
        var line2 = '';
        if (ph) line2 += esc(ph);
        if (rs) line2 += (line2 ? ' • ' : '') + esc(rs);
        return '<div style="padding:10px 0;border-bottom:1px solid var(--border);font-size:13px">'
             + '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px">'
             + '<span style="font-weight:600">'+esc(nm)+'</span>'
             + '<span style="background:'+col+'22;color:'+col+';font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600;white-space:nowrap">'+esc(st)+'</span>'
             + '</div>'
             + (line2 ? '<div style="color:var(--text2);font-size:12px;margin-top:2px">'+line2+'</div>' : '')
             + (dt ? '<div style="color:var(--text3);font-size:11px;margin-top:2px">'+esc(dt)+'</div>' : '')
             + '</div>';
      }}).join('');
    }} else {{
      lh += '<div style="color:var(--text3);padding:6px 0">No leads captured from this business yet.</div>';
    }}
    leadsEl.innerHTML = lh;
  }}

  // Fill Events tab
  var evtsEl = document.getElementById('rv-evts-' + id);
  if (evtsEl) {{
    var myEvts = acts.filter(function(a) {{
      var lf = a['Business'];
      var es = (a['Event Status'] && a['Event Status'].value) || a['Event Status'] || '';
      return es && Array.isArray(lf) && lf.some(function(r){{return r.id===venueId;}});
    }}).sort(function(a,b){{return (b['Date']||'').localeCompare(a['Date']||'');}}).slice(0,10);
    var evColors = {{'Prospective':'#3b82f6','Approved':'#10b981','Scheduled':'#8b5cf6','Completed':'#64748b'}};
    evtsEl.innerHTML = myEvts.length
      ? myEvts.map(function(a) {{
          var es = (a['Event Status'] && a['Event Status'].value) || '';
          var t = (a['Type'] && a['Type'].value) || a['Type'] || '';
          var ec = evColors[es] || '#64748b';
          return '<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:13px">'
            + '<span style="font-weight:600">'+esc(t)+'</span> '
            + '<span style="font-size:10px;padding:2px 6px;border-radius:4px;background:'+ec+'22;color:'+ec+';font-weight:600">'+esc(es)+'</span>'
            + '<div style="font-size:11px;color:var(--text3)">'+esc(a['Date']||'')+'</div></div>';
        }}).join('')
      : '<div style="color:var(--text3)">No events yet</div>';
  }}

  // Fill Boxes tab
  var boxesEl = document.getElementById('rv-boxes-' + id);
  if (boxesEl) {{
    var myBoxes = boxes.filter(function(b) {{
      var biz = b['Business'];
      return Array.isArray(biz) && biz.some(function(r){{return r.id===venueId;}});
    }});
    boxesEl.innerHTML = myBoxes.length
      ? myBoxes.map(function(b) {{
          var st = (b['Status'] && b['Status'].value) || b['Status'] || '';
          var sc = st === 'Active' ? '#059669' : '#475569';
          var loc = b['Location Notes'] || '';
          var pickupDays = parseInt(b['Pickup Days']) || 14;
          var timerBadge = '';
          var pickupBtn = '';
          var daysEdit = '';
          if (st === 'Active' && b['Date Placed']) {{
            var age = -daysUntil(b['Date Placed']);
            if (age >= pickupDays * 2) timerBadge = '<span style="background:#ef444420;color:#ef4444;border-radius:4px;padding:2px 6px;font-size:10px;font-weight:600;margin-left:6px">'+age+'d - Action needed</span>';
            else if (age >= pickupDays) timerBadge = '<span style="background:#f59e0b20;color:#f59e0b;border-radius:4px;padding:2px 6px;font-size:10px;font-weight:600;margin-left:6px">'+age+'d - Follow up</span>';
            else timerBadge = '<span style="background:#05966920;color:#059669;border-radius:4px;padding:2px 6px;font-size:10px;font-weight:600;margin-left:6px">'+age+'d</span>';
            if (IS_ADMIN) {{
              pickupBtn = '<button onclick="pickupBox('+b.id+')" style="margin-top:6px;background:#ea580c;color:#fff;border:none;border-radius:6px;padding:6px 14px;font-size:12px;font-weight:600;cursor:pointer;min-height:36px">Pick Up Box</button>';
              daysEdit = '<div style="margin-top:6px;display:flex;align-items:center;gap:6px">'
                + '<span style="font-size:11px;color:var(--text3)">Pickup in</span>'
                + '<input type="number" value="'+pickupDays+'" min="1" max="90" id="rv-edit-days-'+b.id+'" style="width:50px;background:var(--bg);border:1px solid var(--border);color:var(--text1);border-radius:6px;padding:4px 6px;font-size:12px;text-align:center">'
                + '<span style="font-size:11px;color:var(--text3)">days</span>'
                + '<button onclick="updateBoxDays('+b.id+')" style="background:none;border:1px solid var(--border);color:#3b82f6;border-radius:6px;padding:3px 8px;font-size:11px;font-weight:600;cursor:pointer">Save</button>'
                + '<span id="rv-days-st-'+b.id+'" style="font-size:10px;min-width:30px"></span>'
                + '</div>';
            }}
          }}
          return '<div style="padding:8px 0;border-bottom:1px solid var(--border);font-size:13px">'
            + '<span style="background:'+sc+'20;color:'+sc+';border-radius:4px;padding:2px 6px;font-size:11px;font-weight:600">'+esc(st)+'</span>'
            + timerBadge
            + (b['Date Placed'] ? '<div style="font-size:12px;color:var(--text3);margin-top:3px">Placed '+esc(fmt(b['Date Placed']))+(loc?' \u2022 '+esc(loc):'')+'</div>' : '')
            + pickupBtn
            + daysEdit
            + '</div>';
        }}).join('')
      : '<div style="color:var(--text3)">No massage boxes placed</div>';
  }}
}}

function renderNotesM(text) {{
  if (!text || !text.trim()) return '<div style="color:var(--text3);font-size:13px">No notes yet</div>';
  return text.split('\\n---\\n').filter(function(e){{return e.trim();}}).map(function(entry) {{
    var m = entry.match(/^\\[(\\d{{4}}-\\d{{2}}-\\d{{2}})\\] ([\\s\\S]*)$/);
    if (m) return '<div style="padding:4px 0;border-bottom:1px solid var(--border)"><div style="font-size:10px;color:var(--text3)">'+m[1]+'</div><div style="font-size:13px">'+esc(m[2].trim())+'</div></div>';
    return '<div style="padding:4px 0;font-size:13px">'+esc(entry.trim())+'</div>';
  }}).join('');
}}

async function updateRouteVenueStatus(venueId, val) {{
  await fetch(BR + '/api/database/rows/table/' + _GGOR_VENUES + '/' + venueId + '/?user_field_names=true', {{
    method: 'PATCH', headers: {{'Authorization':'Token '+BT,'Content-Type':'application/json'}},
    body: JSON.stringify({{'Contact Status': {{value: val}}}})
  }});
}}

var _pendingCheckInStopId = null;

function routeArrive(stopId) {{
  // One-tap "I'm here" — flips status to In Progress and stamps Arrived At.
  // The subsequent Check In tap stamps Departed At + computes Duration Mins.
  markRouteStop(stopId, 'In Progress', null);
}}

function openRoutePhotoLightbox(url) {{
  var bg = document.createElement('div');
  bg.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.92);z-index:1200;display:flex;align-items:center;justify-content:center;padding:20px;cursor:pointer';
  bg.onclick = function() {{ bg.remove(); }};
  bg.innerHTML = '<img src="' + url + '" style="max-width:100%;max-height:100%;object-fit:contain">';
  document.body.appendChild(bg);
}}

function routeCheckIn(stopId) {{
  _pendingCheckInStopId = stopId;
  routeCheckInForm();
}}

function routeCheckInForm() {{
  if (!_rCurrentStop) return;
  // Capture the stop BEFORE closing the sheet — closeRouteSheet() nulls
  // _rCurrentStop, and reading .name on null in the setTimeout callback
  // would throw and prevent the form from ever opening.
  var stop = _rCurrentStop;
  closeRouteSheet();
  s2Reset();
  setTimeout(function() {{
    var el;
    el = document.getElementById('s2-event-name'); if (el) el.value = stop.name || '';
    el = document.getElementById('s2-addr');        if (el) el.value = stop.address || '';
    document.getElementById('gfr-form-s2').classList.add('open');
  }}, 150);
}}

function _onFormSubmitSuccess() {{
  if (_pendingCheckInStopId) {{
    markRouteStop(_pendingCheckInStopId, 'Visited', null);
    _pendingCheckInStopId = null;
  }}
}}

function routeSkip(stopId) {{
  var reason = prompt('Why are you skipping this stop?\\n(e.g. closed, no parking, ran out of time)');
  if (reason === null) return;  // cancelled
  if (!reason.trim()) {{ alert('Please provide a reason for skipping.'); return; }}
  markRouteStop(stopId, 'Skipped', null, reason.trim());
}}

function routeNotReached(stopId) {{
  var reason = prompt('Why couldn\\'t you get to this stop?\\n(e.g. too far, traffic, end of day)');
  if (reason === null) return;  // cancelled
  if (!reason.trim()) {{ alert('Please provide a reason.'); return; }}
  markRouteStop(stopId, 'Not Reached', null, reason.trim());
}}

async function markRouteStop(stopId, status, callback, reason) {{
  try {{
    var payload = {{status: status}};
    if (reason) payload.notes = reason;
    // Attach current GPS coords if we have them and the status is Visited
    if (status === 'Visited' && _userLat != null && _userLng != null) {{
      payload.lat = _userLat;
      payload.lng = _userLng;
    }}
    await fetch('/api/guerilla/routes/stops/' + stopId, {{
      method: 'PATCH', headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify(payload)
    }});

    // Auto-pickup box if visiting a stop that has a pending box
    if (status === 'Visited' && _routeData && _routeData.stops) {{
      var thisStop = _routeData.stops.find(function(s){{ return s.stop_id === stopId; }});
      if (thisStop && thisStop.pending_box && thisStop.pending_box.box_id) {{
        try {{
          await fetch('/api/guerilla/boxes/' + thisStop.pending_box.box_id + '/pickup', {{
            method: 'PATCH', headers: {{'Content-Type':'application/json'}},
          }});
        }} catch(e) {{ /* non-fatal */ }}
      }}
    }}
    var r = await fetch({route_endpoint!r});
    _routeData = await r.json();
    updateProgress();
    // Update marker color
    if (_rMarkers[stopId] && _rMap) {{
      var color = _STATUS_COLORS[status] || '#4285f4';
      var stop = (_routeData.stops||[]).find(function(s){{return s.stop_id===stopId;}});
      var idx = stop ? stop.order : '?';
      _rMarkers[stopId].setIcon({{path:google.maps.SymbolPath.CIRCLE,scale:14,fillColor:color,fillOpacity:1,strokeColor:'#fff',strokeWeight:2}});
      _rMarkers[stopId].setLabel({{text:String(idx),color:'#fff',fontWeight:'700',fontSize:'12px'}});
    }}
    closeRouteSheet();
    if (callback) callback();
  }} catch(e) {{
    alert('Could not update stop. Try again.');
  }}
}}

function scheduleRouteEvent(formType) {{
  if (!_rCurrentStop) return;
  // Capture before closeRouteSheet() nulls _rCurrentStop.
  var stop = _rCurrentStop;
  closeRouteSheet();
  openGFRForm(formType);
  var name = stop.name || '';
  var addr = stop.address || '';
  setTimeout(function() {{
    ['s3','s4','s5'].forEach(function(p) {{
      var c = document.getElementById(p + '-company'); if (c && !c.value) c.value = name;
      var a = document.getElementById(p + '-addr');    if (a && !a.value) a.value = addr;
    }});
  }}, 350);
}}

async function placeRouteBox(stopId) {{
  if (!_rCurrentStop) return;
  var loc = document.getElementById('rv-box-loc-' + stopId).value.trim();
  var contact = document.getElementById('rv-box-contact-' + stopId).value.trim();
  var daysEl = document.getElementById('rv-box-days-' + stopId);
  var pickupDays = daysEl ? parseInt(daysEl.value) || 14 : 14;
  var st = document.getElementById('rv-box-st-' + stopId);
  if (!loc) {{ alert('Please enter the box location.'); return; }}
  if (st) st.textContent = 'Saving\u2026';
  try {{
    var r = await fetch('/api/guerilla/boxes', {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{venue_id:_rCurrentStop.venue_id, location:loc, contact_person:contact, pickup_days:pickupDays}})
    }});
    var d = await r.json();
    if (d.ok) {{
      if (st) {{ st.style.color='#059669'; st.textContent='Box placed \u2713'; }}
      document.getElementById('rv-box-loc-'+stopId).value='';
      document.getElementById('rv-box-contact-'+stopId).value='';
      setTimeout(function(){{ if(st) st.textContent=''; }}, 3000);
    }} else {{ if (st) {{ st.style.color='#ef4444'; st.textContent='Error'; }} }}
  }} catch(e) {{ if (st) {{ st.style.color='#ef4444'; st.textContent='Network error'; }} }}
}}

async function pickupBox(boxId) {{
  if (!confirm('Pick up this massage box?')) return;
  try {{
    var r = await fetch('/api/guerilla/boxes/' + boxId + '/pickup', {{
      method:'PATCH', headers:{{'Content-Type':'application/json'}},
      body:'{{}}'
    }});
    var d = await r.json();
    if (d.ok) {{
      alert('Box picked up!');
      if (_rCurrentStop) loadRouteVenueData(_rCurrentStop);
    }}
  }} catch(e) {{ alert('Error picking up box'); }}
}}

async function updateBoxDays(boxId) {{
  var el = document.getElementById('rv-edit-days-' + boxId);
  var st = document.getElementById('rv-days-st-' + boxId);
  if (!el) return;
  var days = parseInt(el.value);
  if (!days || days < 1) {{ alert('Enter a valid number of days.'); return; }}
  if (st) st.textContent = '\u2026';
  try {{
    var r = await fetch('/api/guerilla/boxes/' + boxId + '/days', {{
      method:'PATCH', headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{pickup_days: days}})
    }});
    var d = await r.json();
    if (d.ok) {{
      if (st) {{ st.style.color='#059669'; st.textContent='\u2713'; }}
      setTimeout(function(){{ if(st) st.textContent=''; }}, 2000);
    }} else {{ if (st) {{ st.style.color='#ef4444'; st.textContent='Error'; }} }}
  }} catch(e) {{ if (st) {{ st.style.color='#ef4444'; st.textContent='Error'; }} }}
}}

// ── Field-rep quick-edit handlers (Contact.* backed) ───────────────────────
async function mRouteSaveFollowUp() {{
  var stop = _rCurrentStop; if (!stop || !stop.venue_id) return;
  var venueId = stop.venue_id, id = stop.stop_id;
  var inEl = document.getElementById('rv-fu-' + id);
  var stEl = document.getElementById('rv-fu-st-' + id);
  var val = inEl ? (inEl.value || null) : null;
  if (stEl) {{ stEl.textContent = 'Saving\u2026'; stEl.style.color = 'var(--text3)'; }}
  var res = await Contact.saveFollowUp('gorilla', venueId, val);
  if (stEl) {{
    stEl.textContent = res.ok ? '\u2713 Saved' : '\u2717 Failed';
    stEl.style.color = res.ok ? '#059669' : '#ef4444';
    setTimeout(function() {{ if (stEl) stEl.textContent = ''; }}, 2000);
  }}
}}

async function mRouteAddNote() {{
  var stop = _rCurrentStop; if (!stop || !stop.venue_id) return;
  var venueId = stop.venue_id, id = stop.stop_id;
  var inEl = document.getElementById('rv-note-in-' + id);
  var text = (inEl ? inEl.value : '').trim();
  if (!text) return;
  var stEl = document.getElementById('rv-note-st-' + id);
  if (stEl) {{ stEl.textContent = 'Saving\u2026'; stEl.style.color = 'var(--text3)'; }}
  try {{
    var v = await Contact.fetchVenue('gorilla', venueId);
    var existing = (v && v['Notes']) || '';
    var res = await Contact.addNote('gorilla', venueId, existing, text);
    if (stEl) {{
      stEl.textContent = res.ok ? '\u2713 Added' : '\u2717 Failed';
      stEl.style.color = res.ok ? '#059669' : '#ef4444';
      setTimeout(function() {{ if (stEl) stEl.textContent = ''; }}, 2000);
    }}
    if (res.ok) {{
      if (inEl) inEl.value = '';
      var displayEl = document.getElementById('rv-notes-display-' + id);
      if (displayEl) displayEl.innerHTML = renderNotesM(res.newNotes);
    }}
  }} catch(e) {{
    if (stEl) {{ stEl.textContent = 'Error'; stEl.style.color = '#ef4444'; }}
  }}
}}


// Capture Lead overlay lives in hub/lead_capture_ui.py and is injected
// via extra_js on _mobile_page(). Route-specific launcher below.
function openRouteLeadCapture() {{
  if (!_rCurrentStop) return;
  var name = _rCurrentStop.name || '';
  closeRouteSheet();  // bottom sheet out of the way before the modal opens
  setTimeout(function() {{ openLeadCapture(name); }}, 60);
}}

// ── Live-rep ping (admin map) ────────────────────────────────────────────
// Fires every 30s while the rep has a route loaded AND we have GPS coords.
// Server upserts the rep's T_STAFF row; admin map polls /api/admin/reps/live.
async function _pingRepLocation() {{
  if (!_routeData || !_routeData.stops || !_routeData.stops.length) return;
  if (_userLat == null || _userLng == null) return;
  // Show the privacy pill while pings are firing.
  var pill = document.getElementById('loc-pill');
  if (pill) pill.style.display = 'block';
  try {{
    await fetch('/api/rep/ping', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        lat: _userLat,
        lng: _userLng,
        route_id: _routeData.route_id || null,
      }}),
    }});
  }} catch (e) {{}}
}}
setInterval(_pingRepLocation, 30000);
// First ping after 5s so admins see reps quickly when they open a route.
setTimeout(_pingRepLocation, 5000);

loadRoute();
"""
    admin = _is_admin(user or {})
    script_js = (
        f"const GFR_USER={repr(user_name)};\n"
        f"const TOOL = {{venuesT: {T_GOR_VENUES}}};\n"
        f"const IS_ADMIN = {'true' if admin else 'false'};\n"
        f"const _TOOL_KEY = 'gorilla';\n"
        + contact_actions_js() + "\n"
        + route_js
    )
    return _mobile_page('m_route', 'My Route', body, script_js, br, bt, user=user, wrap_cls='map-mode',
                         extra_html=GFR_EXTRA_HTML + LEAD_CAPTURE_HTML,
                         extra_js=GFR_EXTRA_JS + '\n' + build_lead_capture_js())
