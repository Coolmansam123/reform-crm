"""
Live rep tracking — Phase 2.3.

Reps' phones POST /api/rep/ping every 30s while a route is active. We upsert
their location onto the rep's T_STAFF (815) row (Latest Lat / Lng / Location
Updated At / Active Route ID). Admin map polls /api/admin/reps/live every 15s
to render pins for reps active in the last 5 minutes.

Backend-agnostic handlers (no modal.*, no os.environ reads). Wrappers in
`modal_outreach_hub.py` (admin map + ping) and `field_rep/routes/api.py` (ping
from rep app) pull env, attach session, and call these.
"""
import os
from datetime import datetime as _dt, timedelta as _td

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

from .access import _is_admin
from .constants import T_STAFF


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/rep/ping — rep upserts their current location
# Body: {lat: float, lng: float, route_id?: int}
# ─────────────────────────────────────────────────────────────────────────────
async def update_rep_location(request: Request, br: str, bt: str,
                              user: dict) -> JSONResponse:
    email = (user.get("email") or "").strip().lower()
    if not email:
        return JSONResponse({"ok": False, "error": "no email"}, status_code=400)
    body = await request.json()
    lat = body.get("lat")
    lng = body.get("lng")
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        return JSONResponse({"ok": False, "error": "lat/lng required"}, status_code=400)
    route_id = body.get("route_id")
    headers = {"Authorization": f"Token {bt}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15) as client:
        # Find the rep's T_STAFF row by Email (case-insensitive — search-param is exact)
        sr = await client.get(
            f"{br}/api/database/rows/table/{T_STAFF}/?user_field_names=true&size=200",
            headers={"Authorization": f"Token {bt}"},
        )
        if sr.status_code != 200:
            return JSONResponse({"ok": False, "error": "staff lookup failed"}, status_code=502)
        match = None
        for row in sr.json().get("results", []):
            if (row.get("Email") or "").lower().strip() == email:
                match = row
                break
        if not match:
            # No staff row — silently no-op so reps not in T_STAFF don't error
            return JSONResponse({"ok": True, "no_staff_row": True})
        # Round to 7 decimals (~1cm precision; the field is capped at 7).
        # Browser geolocation returns 14+ decimals which Baserow rejects.
        patch = {
            "Latest Lat": round(float(lat), 7),
            "Latest Lng": round(float(lng), 7),
            "Location Updated At": _dt.utcnow().strftime("%Y-%m-%d %H:%M"),
            "Active Route ID": str(route_id) if route_id is not None else "",
        }
        pr = await client.patch(
            f"{br}/api/database/rows/table/{T_STAFF}/{match['id']}/?user_field_names=true",
            headers=headers,
            json=patch,
        )
        if pr.status_code not in (200, 201):
            return JSONResponse({"ok": False, "error": pr.text[:200]}, status_code=pr.status_code)
    return JSONResponse({"ok": True})


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/admin/reps/live — list reps with location updated <= 5 min ago
# Returns [{email, name, lat, lng, updated_at, route_id, mins_ago}]
# ─────────────────────────────────────────────────────────────────────────────
async def get_active_reps(request: Request, br: str, bt: str,
                          user: dict) -> JSONResponse:
    if not _is_admin(user):
        return JSONResponse({"error": "admin only"}, status_code=403)
    cutoff = _dt.utcnow() - _td(minutes=5)
    async with httpx.AsyncClient(timeout=15) as client:
        sr = await client.get(
            f"{br}/api/database/rows/table/{T_STAFF}/?user_field_names=true&size=200",
            headers={"Authorization": f"Token {bt}"},
        )
    if sr.status_code != 200:
        return JSONResponse({"error": "staff fetch failed"}, status_code=502)
    out: list[dict] = []
    for row in sr.json().get("results", []):
        ts = (row.get("Location Updated At") or "").strip()
        if not ts:
            continue
        try:
            t = _dt.strptime(ts, "%Y-%m-%d %H:%M")
        except Exception:
            continue
        if t < cutoff:
            continue
        lat = row.get("Latest Lat")
        lng = row.get("Latest Lng")
        if lat is None or lng is None:
            continue
        try:
            lat = float(lat); lng = float(lng)
        except Exception:
            continue
        mins_ago = max(0, int((_dt.utcnow() - t).total_seconds() // 60))
        out.append({
            "email":      row.get("Email") or "",
            "name":       row.get("Name") or row.get("Full Name") or row.get("Email") or "",
            "lat":        lat,
            "lng":        lng,
            "updated_at": ts,
            "route_id":   (row.get("Active Route ID") or "").strip(),
            "mins_ago":   mins_ago,
        })
    return JSONResponse(out)


# ─────────────────────────────────────────────────────────────────────────────
# Admin /reps/live page — full-screen map polling /api/admin/reps/live
# ─────────────────────────────────────────────────────────────────────────────
def _rep_tracker_page(br: str, bt: str, user: dict = None) -> str:
    from .shells import _page
    user = user or {}
    gk      = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    gmap_id = os.environ.get("GOOGLE_MAPS_MAP_ID", "")
    body = (
        '<style>.content{padding:0 !important}</style>'
        '<div id="reps-bar" style="display:flex;align-items:center;gap:8px;padding:8px 14px;'
        'border-bottom:1px solid var(--border);background:var(--bg2);font-size:13px">'
        '<span style="font-weight:700">Live Reps</span>'
        '<span id="reps-count" style="font-size:11px;color:var(--text3);background:var(--card);'
        'border:1px solid var(--border);border-radius:10px;padding:2px 8px">—</span>'
        '<span style="margin-left:auto;font-size:11px;color:var(--text3)" id="reps-updated">never</span>'
        '</div>'
        '<div id="reps-view" style="display:flex;height:calc(100vh - 98px);position:relative">'
        '<div id="reps-map" style="flex:1;height:100%"></div>'
        '<div id="reps-side" style="width:300px;background:var(--bg2);border-left:1px solid var(--border);'
        'overflow-y:auto;padding:0">'
        '<div id="reps-list" style="padding:0">'
        '<div style="padding:14px;font-size:12px;color:var(--text3)">Loading…</div>'
        '</div></div></div>'
    )
    js = f"""
const RGK = '{gk}';
const RMAP_ID = '{gmap_id}';
let _rmap = null;
let _rmarkers = {{}};
let _repRows = [];

// AdvancedMarker pin content for live reps. Color encodes recency.
function _repPinContent(color) {{
  var el = document.createElement('div');
  el.style.cssText = 'width:18px;height:18px;border-radius:50%;background:' + color
    + ';border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4);box-sizing:content-box';
  return el;
}}

function initRepMap() {{
  if (_rmap) return;
  if (!RMAP_ID) console.warn('GOOGLE_MAPS_MAP_ID is not set — AdvancedMarkers may not render.');
  var _opts = {{
    center: {{lat: 33.9478, lng: -118.1335}}, zoom: 11,
    mapTypeControl: false, streetViewControl: false,
    styles: [{{featureType:'poi',stylers:[{{visibility:'off'}}]}},
             {{featureType:'transit',stylers:[{{visibility:'off'}}]}}]
  }};
  if (RMAP_ID) _opts.mapId = RMAP_ID;
  _rmap = new google.maps.Map(document.getElementById('reps-map'), _opts);
}}

function _fmtAgo(m) {{
  if (m <= 0) return 'just now';
  if (m === 1) return '1 min ago';
  if (m < 60) return m + ' min ago';
  return Math.floor(m/60) + 'h ago';
}}

function renderRepMarkers(rows) {{
  if (!_rmap) return;
  // Drop markers no longer in the active set
  var seen = {{}};
  rows.forEach(function(r){{ seen[r.email] = true; }});
  Object.keys(_rmarkers).forEach(function(k) {{
    if (!seen[k]) {{ _rmarkers[k].setMap(null); delete _rmarkers[k]; }}
  }});
  // Upsert markers; color by recency (green <2m, yellow <5m)
  rows.forEach(function(r) {{
    var color = r.mins_ago < 2 ? '#059669' : (r.mins_ago < 5 ? '#f59e0b' : '#9ca3af');
    var pos = {{lat: r.lat, lng: r.lng}};
    if (_rmarkers[r.email]) {{
      _rmarkers[r.email].position = pos;
      _rmarkers[r.email].content  = _repPinContent(color);
    }} else if (google.maps.marker && google.maps.marker.AdvancedMarkerElement) {{
      var m = new google.maps.marker.AdvancedMarkerElement({{
        position: pos, map: _rmap,
        content: _repPinContent(color),
        title: r.name + ' — ' + _fmtAgo(r.mins_ago),
      }});
      _rmarkers[r.email] = m;
    }}
  }});
}}

function renderRepList(rows) {{
  var list = document.getElementById('reps-list');
  if (!rows.length) {{
    list.innerHTML = '<div style="padding:14px;font-size:12px;color:var(--text3)">No reps active in the last 5 minutes.</div>';
    return;
  }}
  var html = '';
  rows.sort(function(a,b){{ return a.mins_ago - b.mins_ago; }});
  rows.forEach(function(r) {{
    var color = r.mins_ago < 2 ? '#059669' : (r.mins_ago < 5 ? '#f59e0b' : '#9ca3af');
    html += '<div onclick="zoomRep(\\'' + esc(r.email) + '\\')" '
         + 'style="padding:10px 14px;border-bottom:1px solid var(--border);cursor:pointer">'
         + '<div style="display:flex;align-items:center;gap:8px">'
         + '<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:' + color + '"></span>'
         + '<span style="font-size:13px;font-weight:600;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(r.name || r.email) + '</span>'
         + '</div>'
         + '<div style="font-size:11px;color:var(--text3);margin-top:3px">'
         + esc(_fmtAgo(r.mins_ago)) + (r.route_id ? ' · route #' + esc(r.route_id) : '')
         + '</div>'
         + '</div>';
  }});
  list.innerHTML = html;
}}

function zoomRep(email) {{
  var m = _rmarkers[email];
  if (!m || !_rmap) return;
  _rmap.panTo(m.position);
  _rmap.setZoom(15);
}}

async function pollReps() {{
  try {{
    var r = await fetch('/api/admin/reps/live', {{ cache: 'no-store' }});
    if (!r.ok) return;
    _repRows = await r.json();
    document.getElementById('reps-count').textContent = _repRows.length + ' active';
    document.getElementById('reps-updated').textContent = 'updated ' + (new Date()).toLocaleTimeString();
    renderRepMarkers(_repRows);
    renderRepList(_repRows);
  }} catch (e) {{}}
}}

function _initWhenMapReady() {{
  if (window.google && window.google.maps) {{ initRepMap(); pollReps(); setInterval(pollReps, 15000); return; }}
  var s = document.createElement('script');
  s.src = 'https://maps.googleapis.com/maps/api/js?key=' + RGK + '&v=weekly&libraries=marker&callback=_initWhenMapReady';
  s.async = true;
  window._initWhenMapReady = function() {{ initRepMap(); pollReps(); setInterval(pollReps, 15000); }};
  document.head.appendChild(s);
}}

_initWhenMapReady();
"""
    return _page('reps_live', 'Live Reps', '', body, js, br, bt, user=user)
