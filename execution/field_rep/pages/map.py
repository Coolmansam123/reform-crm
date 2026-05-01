"""Full admin venue map."""

import os

from hub.shared import (
    _mobile_page,
    T_GOR_VENUES, T_GOR_ACTS, T_GOR_BOXES, T_COM_VENUES, T_COM_ACTS,
)
from hub.guerilla import GFR_EXTRA_HTML, GFR_EXTRA_JS


def _mobile_map_page(br: str, bt: str, user: dict = None) -> str:
    gk      = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    gmap_id = os.environ.get("GOOGLE_MAPS_MAP_ID", "")
    user = user or {}
    user_name = user.get('name', '')
    # Pulse keyframe for high-attention pins (overdue boxes). Local to map page.
    map_css = (
        '<style>'
        '@keyframes gpulse {'
        ' 0%{transform:scale(1);opacity:.55}'
        ' 100%{transform:scale(1.7);opacity:0}'
        '}'
        '</style>'
    )
    body = (
        map_css
        # Full-screen map -- breaks out of mobile-wrap via position:fixed
        + '<div class="m-map-wrap" id="gmap">'
        '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text3);font-size:14px">Loading map...</div>'
        '</div>'
        # Filter bar: search + tool pills + status pills (single container)
        '<div class="m-map-filters">'
        '<input type="search" id="m-search" placeholder="\U0001f50d Search" oninput="onMSearch(this.value)" enterkeyhint="search"'
        ' style="padding:5px 10px;border-radius:20px;font-size:12px;border:none;background:var(--bg2);color:var(--text1);box-shadow:0 1px 4px rgba(0,0,0,.4);width:90px">'
        '<button class="m-map-filter-btn on" onclick="setMFilter(this,\'all\')" style="padding:5px 10px;font-size:11px">All</button>'
        '<button class="m-map-filter-btn" onclick="setMFilter(this,\'gorilla\')" style="padding:5px 10px;font-size:11px">\U0001f7e0 Guerilla</button>'
        '<button class="m-map-filter-btn" onclick="setMFilter(this,\'community\')" style="padding:5px 10px;font-size:11px">\U0001f7e2 Community</button>'
        '<div style="width:100%;height:2px"></div>'
        '<button class="m-map-filter-btn m-stat-pill on" onclick="setMStatus(this,\'\')" style="font-size:11px;padding:4px 9px">All</button>'
        '<button class="m-map-filter-btn m-stat-pill" onclick="setMStatus(this,\'Not Contacted\')" style="font-size:11px;padding:4px 9px">New</button>'
        '<button class="m-map-filter-btn m-stat-pill" onclick="setMStatus(this,\'Contacted\')" style="font-size:11px;padding:4px 9px">Contacted</button>'
        '<button class="m-map-filter-btn m-stat-pill" onclick="setMStatus(this,\'In Discussion\')" style="font-size:11px;padding:4px 9px">Discussion</button>'
        '<button class="m-map-filter-btn m-stat-pill" onclick="setMStatus(this,\'Active Partner\')" style="font-size:11px;padding:4px 9px">Active</button>'
        '<button class="m-map-filter-btn m-stat-pill" onclick="setMStatus(this,\'box-alert\')" style="font-size:11px;padding:4px 9px">\U0001f4e6 Boxes Due</button>'
        '</div>'
        # Bottom sheet
        '<div class="m-sheet-backdrop" id="m-backdrop" onclick="closeSheet()"></div>'
        '<div class="m-sheet" id="m-sheet">'
        '<div class="m-sheet-handle" onclick="closeSheet()"></div>'
        '<div id="m-sheet-body" style="padding:0 0 20px"></div>'
        '</div>'
    )
    map_js = f"""
window.onerror = function(msg, url, line) {{
  if (line === 0 || msg === 'Script error.') return true;
  var el = document.getElementById('gmap');
  if (el && !_gMap) el.innerHTML = '<div style="padding:20px;color:#ef4444;font-size:13px;word-break:break-all">JS Error: ' + msg + ' (line ' + line + ')</div>';
}};
const GK = {repr(gk)};
const GMAP_ID = {repr(gmap_id)};
const _GGOR_TID = {T_GOR_VENUES};
const _GCOM_TID = {T_COM_VENUES};
const _GGOR_ACTS = {T_GOR_ACTS};
const _GCOM_ACTS = {T_COM_ACTS};
const _GBOXES   = {T_GOR_BOXES};
const _GOFF_LAT = 33.9478, _GOFF_LNG = -118.1335;
const _GSTATUS_COLORS = {{'Not Contacted':'#4285f4','Contacted':'#fbbc04','In Discussion':'#ff9800','Active Partner':'#34a853','Active Relationship':'#34a853'}};
const _GTOOL_BORDER   = {{'gorilla':'#ea580c','community':'#059669'}};

var _gVenues = [], _gFilter = 'all', _gStatusFilter = '', _gSearch = '', _gMap, _gMarkers = {{}};
var _currentVenueM = null;
var _boxAlerts = {{}};  // venueId -> 'warning' or 'action'

async function bpatch_m(tid, id, data) {{
  return fetch(BR + '/api/database/rows/table/' + tid + '/' + id + '/?user_field_names=true', {{
    method: 'PATCH',
    headers: {{'Authorization': 'Token ' + BT, 'Content-Type': 'application/json'}},
    body: JSON.stringify(data)
  }});
}}

async function loadMapVenues() {{
  try {{
    var res = await Promise.all([fetchAll(_GGOR_TID), fetchAll(_GCOM_TID), fetchAll(_GBOXES)]);
    var gor = res[0], com = res[1], allBoxes = res[2];
    gor.forEach(function(v) {{ v._tid = _GGOR_TID; v._actsTid = _GGOR_ACTS; v._link = 'Business';    v._tool = 'gorilla';   }});
    com.forEach(function(v) {{ v._tid = _GCOM_TID; v._actsTid = _GCOM_ACTS; v._link = 'Organization'; v._tool = 'community'; }});
    _gVenues = gor.concat(com);
    // Pre-compute box alerts for pin indicators
    allBoxes.forEach(function(b) {{
      if (sv(b['Status']) !== 'Active' || !b['Date Placed']) return;
      var biz = b['Business'];
      if (!Array.isArray(biz) || !biz.length) return;
      var vid = biz[0].id;
      var age = -(daysUntil(b['Date Placed']) || 0);
      var pickupDays = parseInt(b['Pickup Days']) || 14;
      var level = age >= pickupDays * 2 ? 'action' : age >= pickupDays ? 'warning' : null;
      if (level && (!_boxAlerts[vid] || level === 'action')) _boxAlerts[vid] = level;
    }});
    initGMap();
  }} catch(e) {{
    document.getElementById('gmap').innerHTML = '<div style="padding:40px;text-align:center;color:#ef4444;font-size:14px">Map load error: ' + e.message + '</div>';
  }}
}}

// Pin factories (AdvancedMarker era).
//   _gPinContent(v, alertLevel) -> HTMLElement
//     Default: PinElement with status fill + tool-type border + status glyph.
//     Alert states (overdue boxes): custom HTML with pulsing ring (see _gPinAlertHtml).
// TODO(v2): extract these to a shared `_map_helpers.py` so the home page V2
// embedded map can reuse the exact same look.
function _gPinContent(v, alertLevel) {{
  const status = sv(v['Contact Status']) || 'Unknown';
  const tool   = v._tool || 'gorilla';
  const fill   = _GSTATUS_COLORS[status] || '#9e9e9e';
  const ring   = _GTOOL_BORDER[tool] || '#666';
  const glyph  = (status === 'Active Partner') ? '★'
              :  (status === 'In Discussion')  ? '?'
              :  (status === 'Contacted')      ? '·'
              :  '';
  if (alertLevel === 'action' || alertLevel === 'warning') {{
    return _gPinAlertHtml(fill, ring, alertLevel, glyph);
  }}
  if (!(google.maps.marker && google.maps.marker.PinElement)) {{
    // marker library failed to load; return a neutral div so we don't crash.
    var fb = document.createElement('div');
    fb.style.cssText = 'width:14px;height:14px;border-radius:50%;background:' + fill + ';border:2px solid ' + ring;
    return fb;
  }}
  const pin = new google.maps.marker.PinElement({{
    background: fill,
    borderColor: ring,
    glyph: glyph,
    glyphColor: '#fff',
    scale: tool === 'gorilla' ? 1.0 : 0.9,
  }});
  return pin.element;
}}

function _gPinAlertHtml(fill, ring, level, glyph) {{
  const pulseColor = level === 'action' ? '#ef4444' : '#f59e0b';
  const wrap = document.createElement('div');
  wrap.style.cssText = 'position:relative;width:34px;height:34px;display:flex;align-items:center;justify-content:center';
  wrap.innerHTML =
    '<span style="position:absolute;inset:0;border-radius:50%;background:' + pulseColor + ';opacity:.45;animation:gpulse 1.6s ease-out infinite"></span>' +
    '<span style="position:relative;width:22px;height:22px;border-radius:50%;background:' + fill + ';border:3px solid ' + ring + ';display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px;font-weight:700;box-shadow:0 1px 4px rgba(0,0,0,.3)">' + (glyph || '') + '</span>';
  return wrap;
}}

function initGMap() {{
  if (!GK) {{
    document.getElementById('gmap').innerHTML = '<div style="padding:40px;text-align:center;color:var(--text3)">Maps API key not configured.</div>';
    return;
  }}
  if (!GMAP_ID) {{
    // AdvancedMarkers require a Map ID. The page still loads, but pins won't render
    // correctly. Surface this loudly so the env-var fix is obvious.
    console.warn('GOOGLE_MAPS_MAP_ID is not set. AdvancedMarkers require a Map ID — create one in Google Cloud Console (Maps Platform → Map Management) and add to .env as GOOGLE_MAPS_MAP_ID.');
  }}
  window._gMapReadyCb = function() {{
    var el = document.getElementById('gmap');
    el.style.height = el.offsetHeight + 'px';
    var mapOpts = {{
      center: {{lat: _GOFF_LAT, lng: _GOFF_LNG}}, zoom: 13,
      mapTypeControl: false, streetViewControl: false,
      // Inline `styles` is ignored once `mapId` is set — Map ID's cloud-based
      // styling supersedes it. Kept here as a TODO: reproduce POI/transit hides
      // in the cloud Map ID style for parity with the legacy look.
      styles: [{{featureType:'poi',stylers:[{{visibility:'off'}}]}},
               {{featureType:'transit',stylers:[{{visibility:'off'}}]}}]
    }};
    if (GMAP_ID) mapOpts.mapId = GMAP_ID;
    _gMap = new google.maps.Map(el, mapOpts);
    // Office marker — AdvancedMarkerElement with a star-glyph PinElement.
    if (google.maps.marker && google.maps.marker.AdvancedMarkerElement && google.maps.marker.PinElement) {{
      var officePin = new google.maps.marker.PinElement({{
        background: '#ea4335', borderColor: '#b31412',
        glyphColor: '#fff', glyph: '★', scale: 1.1,
      }});
      new google.maps.marker.AdvancedMarkerElement({{
        position: {{lat: _GOFF_LAT, lng: _GOFF_LNG}}, map: _gMap,
        title: 'Reform Chiropractic',
        content: officePin.element,
      }});
    }}
    setTimeout(function(){{ google.maps.event.trigger(_gMap, 'resize'); _gMap.setCenter({{lat: _GOFF_LAT, lng: _GOFF_LNG}}); }}, 100);
    renderGMarkers();
    // ── Venue focus mode: /map?venue=<id> centers and opens its sheet ─────
    var qs = new URLSearchParams(location.search);
    var focusId = parseInt(qs.get('venue'), 10);
    if (focusId) {{
      var v = _gVenues.find(function(x) {{ return x.id === focusId; }});
      if (v) {{
        var lat = parseFloat(v['Latitude']), lng = parseFloat(v['Longitude']);
        if (lat && lng) {{
          _gMap.setCenter({{lat: lat, lng: lng}});
          _gMap.setZoom(17);
        }}
        // Hide the filter bar since we're not browsing, and open the sheet.
        var fb = document.querySelector('.m-map-filters');
        if (fb) fb.style.display = 'none';
        openSheet(v);
      }}
    }}
  }};
  var s = document.createElement('script');
  s.src = 'https://maps.googleapis.com/maps/api/js?key=' + GK + '&v=weekly&libraries=marker&callback=_gMapReadyCb';
  s.async = true;
  s.onerror = function() {{
    document.getElementById('gmap').innerHTML = '<div style="padding:40px;text-align:center;color:#ef4444;font-size:14px">Failed to load Google Maps script. Check API key &amp; network.</div>';
  }};
  document.head.appendChild(s);
}}

function renderGMarkers() {{
  if (!_gMap) return;
  Object.values(_gMarkers).forEach(function(m) {{ m.setMap(null); }});
  _gMarkers = {{}};
  _gVenues.forEach(function(v) {{
    if (_gFilter !== 'all' && v._tool !== _gFilter) return;
    if (_gStatusFilter === 'box-alert') {{
      if (!_boxAlerts[v.id]) return;
    }} else if (_gStatusFilter && sv(v['Contact Status']) !== _gStatusFilter) return;
    if (_gSearch && (v['Name']||'').toLowerCase().indexOf(_gSearch) < 0) return;
    var lat = parseFloat(v['Latitude']), lng = parseFloat(v['Longitude']);
    if (!lat || !lng) return;
    var alertLevel = _boxAlerts[v.id];  // 'action' | 'warning' | undefined
    if (!(google.maps.marker && google.maps.marker.AdvancedMarkerElement)) {{
      // Marker library failed to load (likely missing &libraries=marker on the
      // script URL or a CSP rejection). Skip rendering this pin rather than crash.
      return;
    }}
    var marker = new google.maps.marker.AdvancedMarkerElement({{
      position: {{lat: lat, lng: lng}}, map: _gMap,
      title: v['Name'] || '',
      content: _gPinContent(v, alertLevel),
    }});
    (function(venue) {{
      marker.addListener('gmpClick', function() {{ openSheet(venue); }});
    }})(v);
    _gMarkers[v.id + '_' + v._tool] = marker;
  }});
}}

function setMFilter(btn, f) {{
  document.querySelectorAll('.m-map-filter-btn:not(.m-stat-pill)').forEach(function(b) {{ b.classList.remove('on'); }});
  btn.classList.add('on');
  _gFilter = f;
  renderGMarkers();
}}
function setMStatus(btn, s) {{
  document.querySelectorAll('.m-stat-pill').forEach(function(b) {{ b.classList.remove('on'); }});
  btn.classList.add('on');
  _gStatusFilter = s;
  renderGMarkers();
}}
function onMSearch(q) {{
  _gSearch = q.trim().toLowerCase();
  renderGMarkers();
}}

function closeSheet() {{
  document.getElementById('m-sheet').classList.remove('open');
  document.getElementById('m-backdrop').classList.remove('open');
  _currentVenueM = null;
}}

function openSheet(v) {{
  _currentVenueM = v;
  document.getElementById('m-sheet').classList.add('open');
  document.getElementById('m-backdrop').classList.add('open');
  document.getElementById('m-sheet-body').innerHTML = renderSheetSkeleton(v);
  loadSheetActs(v);
  loadSheetEvts(v);
  if (v._tool === 'gorilla') loadSheetBoxes(v.id);
}}

function stageOptsM(v) {{
  var stages = v._tool === 'gorilla'
    ? ['Not Contacted','Contacted','In Discussion','Active Partner']
    : ['Not Contacted','Contacted','In Discussion','Active Partner'];
  var cur = sv(v['Contact Status']);
  return stages.map(function(s) {{
    return '<option value="'+s+'"'+(cur===s?' selected':'')+'>'+esc(s)+'</option>';
  }}).join('');
}}

// -- Notes helpers ----------------------------------------------------------
function renderNotesM(text) {{
  if (!text || !text.trim()) return '<div style="color:var(--text3);font-size:13px;padding:4px 0">No notes yet</div>';
  return text.split('\\n---\\n').filter(function(e){{return e.trim();}}).map(function(entry) {{
    var m = entry.match(/^\\[(\\d{{4}}-\\d{{2}}-\\d{{2}})\\] ([\\s\\S]*)$/);
    if (m) return '<div style="padding:6px 0;border-bottom:1px solid var(--border)">'
      + '<div style="font-size:10px;color:var(--text3);margin-bottom:2px">' + m[1] + '</div>'
      + '<div style="font-size:13px">' + esc(m[2].trim()) + '</div></div>';
    return '<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:13px">' + esc(entry.trim()) + '</div>';
  }}).join('');
}}
async function addNoteM(id, tid) {{
  var inputEl = document.getElementById('m-note-in-' + id);
  var text = (inputEl ? inputEl.value : '').trim();
  if (!text) return;
  var today = new Date().toISOString().split('T')[0];
  var entry = '[' + today + '] ' + text;
  var v = _gVenues.find(function(x){{return x.id === id && x._tid === tid;}});
  var existing = (v && v['Notes'] ? v['Notes'].trim() : '');
  var newNotes = existing ? entry + '\\n---\\n' + existing : entry;
  if (v) v['Notes'] = newNotes;
  if (inputEl) inputEl.value = '';
  var logEl = document.getElementById('m-notes-' + id);
  if (logEl) logEl.innerHTML = renderNotesM(newNotes);
  var st = document.getElementById('m-note-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  var r = await bpatch_m(tid, id, {{'Notes': newNotes}});
  if (st) {{ st.textContent = r.ok ? 'Saved \u2713' : 'Failed \u2717'; setTimeout(function(){{ if(st) st.textContent=''; }}, 2000); }}
}}

// -- Event history helpers --------------------------------------------------
function renderMapEvt(a) {{
  var evStatus = sv(a['Event Status']) || '';
  var type     = sv(a['Type']) || 'Event';
  var date     = a['Date'] || '';
  var evColors = {{'Prospective':'#3b82f6','Approved':'#10b981','Scheduled':'#8b5cf6','Completed':'#64748b'}};
  var color    = evColors[evStatus] || '#64748b';
  return '<div style="padding:8px 0;border-bottom:1px solid var(--border)">'
    + '<div style="display:flex;align-items:center;gap:6px">'
    + '<span style="font-size:13px;font-weight:600">' + esc(type) + '</span>'
    + '<span style="font-size:10px;padding:2px 7px;border-radius:6px;background:' + color + '22;color:' + color + ';font-weight:600">' + esc(evStatus) + '</span>'
    + '</div>'
    + '<div style="font-size:12px;color:var(--text3);margin-top:2px">' + esc(date) + '</div>'
    + '</div>';
}}
async function loadSheetEvts(v) {{
  var acts = await fetchAll(v._actsTid);
  var mine = acts.filter(function(a) {{
    var lf = a[v._link];
    if (!(Array.isArray(lf) && lf.some(function(r){{return r.id===v.id;}}))) return false;
    return !!sv(a['Event Status']);
  }});
  mine.sort(function(a,b){{return (b['Date']||'').localeCompare(a['Date']||'');}});
  var el = document.getElementById('m-evts-' + v.id);
  if (!el) return;
  if (!mine.length) {{ el.innerHTML = '<div style="color:var(--text3)">No events yet</div>'; return; }}
  el.innerHTML = mine.slice(0,20).map(renderMapEvt).join('');
}}

// -- Schedule Event helpers -------------------------------------------------
function toggleEvtMenuM() {{
  var el = document.getElementById('m-evt-menu');
  if (!el) return;
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}}
function openScheduleEventM(formType) {{
  var v = _currentVenueM;
  closeSheet();
  openGFRForm(formType);
  if (!v) return;
  var name = v['Name'] || '';
  var addr = v['Address'] || '';
  var phone = v['Phone'] || '';
  setTimeout(function() {{
    if (formType === 'External Event') {{
      var el;
      el = document.getElementById('s2-event-name'); if (el && !el.value) el.value = name;
      el = document.getElementById('s2-addr');        if (el && !el.value) el.value = addr;
      el = document.getElementById('s2-org-phone');   if (el && !el.value) el.value = phone;
    }} else {{
      ['s3','s4','s5'].forEach(function(p) {{
        var c = document.getElementById(p + '-company'); if (c && !c.value) c.value = name;
        var a = document.getElementById(p + '-addr');    if (a && !a.value) a.value = addr;
        var ph = document.getElementById(p + '-phone');  if (ph && !ph.value) ph.value = phone;
      }});
    }}
  }}, 350);
}}

function renderSheetSkeleton(v) {{
  var name    = esc(v['Name'] || '(unnamed)');
  var status  = sv(v['Contact Status']) || 'Not Contacted';
  var typeVal = sv(v['Classification'] || v['Type'] || '');
  var phone   = v['Phone'] || '';
  var addr    = v['Address'] || '';
  var website = v['Website'] || '';
  var fu      = v['Follow-Up Date'] || '';
  var _placeId = v['Google Place ID'] || '';
  var gmUrl   = v['Google Maps URL'] || (_placeId ? 'https://www.google.com/maps/place/?q=place_id:' + _placeId : '');
  var yelpUrl = v['Yelp Search URL'] || '';
  var rating  = v['Rating'] || '';
  var reviews = v['Reviews'] || '';
  var dist    = v['Distance (mi)'] || '';
  var notesRaw= v['Notes'] || '';
  var id      = v.id;
  var tid     = v._tid;
  var sc = {{'Not Contacted':'#4285f4','Contacted':'#fbbc04','In Discussion':'#ff9800','Active Partner':'#34a853','Active Relationship':'#34a853'}}[status] || '#9e9e9e';
  var toolBadge = v._tool === 'gorilla'
    ? '<span style="background:#ea580c20;color:#ea580c;font-size:10px;padding:2px 6px;border-radius:4px;font-weight:600">\U0001f7e0 Guerilla</span>'
    : '<span style="background:#05966920;color:#059669;font-size:10px;padding:2px 6px;border-radius:4px;font-weight:600">\U0001f7e2 Community</span>';

  // ── Section 1: Header ───────────────────────────────────────────────────
  var html = '<div class="m-sheet-sec">';
  html += '<div style="font-size:17px;font-weight:700;margin-bottom:6px">'+name+'</div>';
  html += '<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">';
  html += '<span style="background:'+sc+'20;color:'+sc+';font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600">'+esc(status)+'</span>';
  if (typeVal) html += '<span style="background:var(--card);color:var(--text2);font-size:11px;padding:2px 8px;border-radius:4px">'+esc(typeVal)+'</span>';
  html += toolBadge + '</div>';
  if (rating) {{
    var stars = '\u2605'.repeat(Math.min(5, Math.round(parseFloat(rating)||0)));
    html += '<div style="font-size:12px;color:var(--text2);margin-top:6px">' + stars + ' ' + esc(rating) + (reviews ? ' (' + reviews + ' reviews)' : '') + '</div>';
  }}
  if (dist) html += '<div style="font-size:11px;color:var(--text3);margin-top:4px">' + esc(dist) + ' mi from office</div>';
  html += '</div>';

  // ── Tab Bar ──────────────────────────────────────────────────────────────
  html += '<div class="m-tabs">';
  html += '<div class="m-tab active" onclick="mSheetTab(this,\\'mp-info-'+id+'\\')">Info</div>';
  html += '<div class="m-tab" onclick="mSheetTab(this,\\'mp-acts-'+id+'\\')">Activity</div>';
  html += '<div class="m-tab" onclick="mSheetTab(this,\\'mp-evts-'+id+'\\')">Events</div>';
  if (v._tool === 'gorilla') html += '<div class="m-tab" onclick="mSheetTab(this,\\'mp-boxes-'+id+'\\')">Boxes</div>';
  html += '</div>';

  // ══ INFO TAB ═══════════════════════════════════════════════════════════
  html += '<div class="m-panel active" id="mp-info-'+id+'" style="padding:12px 16px">';
  // Contact
  if (phone) html += '<div style="margin-bottom:8px"><a href="tel:'+esc(phone)+'" style="color:var(--text1);font-size:14px;text-decoration:none">\U0001f4de '+esc(phone)+'</a></div>';
  if (addr) {{
    var mapsLink = 'https://maps.google.com/?q='+encodeURIComponent(addr);
    html += '<div style="margin-bottom:8px;font-size:13px">\U0001f4cd '+esc(addr)
      +' <a href="'+mapsLink+'" target="_blank" style="color:#3b82f6;font-size:12px">Open \u2197</a></div>';
  }}
  if (website) html += '<div style="font-size:13px;margin-bottom:8px">\U0001f310 <a href="'+esc(website)+'" target="_blank" style="color:#3b82f6">'+esc(website)+'</a></div>';
  if (gmUrl || yelpUrl) {{
    html += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">';
    if (gmUrl) html += '<a href="'+esc(gmUrl)+'" target="_blank" style="display:inline-flex;align-items:center;padding:8px 14px;border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;background:#3b82f620;color:#3b82f6;min-height:44px">Google Maps \u2197</a>';
    if (yelpUrl) html += '<a href="'+esc(yelpUrl)+'" target="_blank" style="display:inline-flex;align-items:center;padding:8px 14px;border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;background:#f9731620;color:#f97316;min-height:44px">Yelp \u2197</a>';
    html += '</div>';
  }}
  // CRM Controls
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
  html += '<div style="margin-bottom:10px"><div class="m-sheet-lbl">Contact Status</div>';
  html += '<select onchange="updateMapStatus('+id+','+tid+',this.value)" '
    + 'style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:8px 10px;font-size:14px">'
    + stageOptsM(v) + '</select></div>';
  html += '<div style="margin-bottom:10px"><div class="m-sheet-lbl">Follow-Up Date</div>';
  html += '<div style="display:flex;gap:8px;align-items:center">';
  html += '<input type="date" id="m-fu-'+id+'" value="'+esc(fu)+'" '
    + 'style="flex:1;background:var(--bg);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:8px 10px;font-size:14px">';
  html += '<button onclick="saveMapFollowUp('+id+','+tid+')" '
    + 'style="background:#3b82f6;color:#fff;border:none;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:600;cursor:pointer;min-height:44px">Save</button>';
  html += '<span id="m-fu-st-'+id+'" style="font-size:12px;color:#34a853;min-width:16px"></span>';
  html += '</div></div>';
  // Notes
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
  html += '<div class="m-sheet-lbl">\U0001f4dd Notes</div>';
  html += '<div id="m-notes-'+id+'" style="max-height:120px;overflow-y:auto;background:var(--card);border-radius:8px;padding:10px 12px;border:1px solid var(--border)">';
  html += renderNotesM(notesRaw);
  html += '</div>';
  html += '<div style="display:flex;gap:8px;margin-top:8px">';
  html += '<input type="text" id="m-note-in-'+id+'" placeholder="Add a note\u2026" '
    + 'style="flex:1;background:var(--bg);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:10px 12px;font-size:14px">';
  html += '<button onclick="addNoteM('+id+','+tid+')" '
    + 'style="background:#e94560;color:#fff;border:none;border-radius:8px;padding:10px 16px;font-size:13px;font-weight:600;cursor:pointer;min-height:44px">Add</button>';
  html += '</div>';
  html += '<div id="m-note-st-'+id+'" style="font-size:12px;color:#34a853;margin-top:4px"></div>';
  html += '</div>';  // end Info tab

  // ══ ACTIVITY TAB ═══════════════════════════════════════════════════════
  html += '<div class="m-panel" id="mp-acts-'+id+'" style="padding:12px 16px">';
  html += '<div id="m-acts-'+id+'" style="font-size:13px;color:var(--text3)">Loading\u2026</div>';
  html += '</div>';

  // ══ EVENTS TAB ═════════════════════════════════════════════════════════
  html += '<div class="m-panel" id="mp-evts-'+id+'" style="padding:12px 16px">';
  // Schedule Event options (always visible)
  html += '<div class="m-sheet-lbl">Schedule Event</div>';
  html += '<div style="display:grid;gap:8px;margin-bottom:14px">';
  html += '<button onclick="openScheduleEventM(\\'Mobile Massage Service\\')" style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:12px 16px;font-size:14px;font-weight:600;cursor:pointer;min-height:48px;text-align:left">\U0001f486 Mobile Massage</button>';
  html += '<button onclick="openScheduleEventM(\\'Lunch and Learn\\')" style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:12px 16px;font-size:14px;font-weight:600;cursor:pointer;min-height:48px;text-align:left">\U0001f37d\ufe0f Lunch & Learn</button>';
  html += '<button onclick="openScheduleEventM(\\'Health Assessment Screening\\')" style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:12px 16px;font-size:14px;font-weight:600;cursor:pointer;min-height:48px;text-align:left">\U0001fa7a Health Assessment</button>';
  html += '</div>';
  // Event History
  html += '<div class="m-sheet-lbl">Event History</div>';
  html += '<div id="m-evts-'+id+'" style="font-size:13px;color:var(--text3)">Loading\u2026</div>';
  html += '</div>';

  // ══ BOXES TAB (gorilla only) ═══════════════════════════════════════════
  if (v._tool === 'gorilla') {{
    html += '<div class="m-panel" id="mp-boxes-'+id+'" style="padding:12px 16px">';
    html += '<div id="m-boxes-'+id+'" style="font-size:13px;color:var(--text3)">Loading\u2026</div>';
    // Place Box form
    html += '<hr style="border:none;border-top:1px solid var(--border);margin:12px 0">';
    html += '<div class="m-sheet-lbl">\U0001f4e6 Place New Box</div>';
    html += '<div style="display:grid;gap:8px">';
    html += '<input type="text" id="m-box-loc-'+id+'" placeholder="Location (e.g. Front desk, Break room)" '
      + 'style="background:var(--bg);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:10px 12px;font-size:14px">';
    html += '<input type="text" id="m-box-contact-'+id+'" placeholder="Contact person" '
      + 'style="background:var(--bg);border:1px solid var(--border);color:var(--text1);border-radius:8px;padding:10px 12px;font-size:14px">';
    html += '<button onclick="placeBoxM('+id+')" '
      + 'style="background:#059669;color:#fff;border:none;border-radius:8px;padding:10px 14px;font-size:14px;font-weight:600;cursor:pointer;min-height:44px">Place Box</button>';
    html += '<div id="m-box-st-'+id+'" style="font-size:12px;text-align:center;min-height:14px"></div>';
    html += '</div>';
    html += '</div>';
  }}

  // ── Dynamic bottom CTA (changes per tab) ─────────────────────────────────
  html += '<div id="m-cta-wrap" style="padding:16px;border-top:1px solid var(--border)">'
    + '<button id="m-cta-btn" onclick="mCtaAction()" '
    + 'style="width:100%;background:#004ac6;color:#fff;border:none;border-radius:10px;padding:14px;font-size:15px;font-weight:700;cursor:pointer">'
    + 'Check In</button></div>';

  return html;
}}

async function updateMapStatus(id, tid, val) {{
  var v = _gVenues.find(function(x) {{ return x.id === id && x._tid === tid; }});
  if (v) v['Contact Status'] = {{value: val}};
  var toolKey = tid === _GGOR_TID ? 'gorilla' : 'community';
  var k = id + '_' + toolKey;
  if (_gMarkers[k] && v) {{
    // AdvancedMarker uses `.content` instead of `.setIcon()`.
    _gMarkers[k].content = _gPinContent(v, _boxAlerts[id]);
  }}
  await bpatch_m(tid, id, {{'Contact Status': {{value: val}}}});
}}

async function saveMapFollowUp(id, tid) {{
  var inp = document.getElementById('m-fu-' + id);
  var val = inp ? inp.value || null : null;
  var v = _gVenues.find(function(x) {{ return x.id === id && x._tid === tid; }});
  if (v) v['Follow-Up Date'] = val;
  var st = document.getElementById('m-fu-st-' + id);
  if (st) st.textContent = '\u2026';
  var r = await bpatch_m(tid, id, {{'Follow-Up Date': val || null}});
  if (st) {{ st.textContent = r.ok ? '\u2713' : '\u2717'; setTimeout(function() {{ if (st) st.textContent = ''; }}, 2000); }}
}}

function renderMapAct(a) {{
  var type    = sv(a['Type']) || '';
  var outcome = sv(a['Outcome']) || '';
  var date    = a['Date'] || '';
  var person  = a['Contact Person'] || '';
  var summary = a['Summary'] || '';
  return '<div style="padding:8px 0;border-bottom:1px solid var(--border)">'
    + '<div style="display:flex;justify-content:space-between;margin-bottom:2px">'
    + '<span style="font-size:11px;font-weight:600;background:var(--card);padding:1px 6px;border-radius:4px">'+esc(type)+'</span>'
    + '<span style="font-size:11px;color:var(--text3)">'+esc(date)+'</span></div>'
    + (outcome ? '<div style="font-size:12px;color:var(--text2)">'+esc(outcome)+'</div>' : '')
    + (person  ? '<div style="font-size:11px;color:var(--text3)">with '+esc(person)+'</div>' : '')
    + (summary ? '<div style="font-size:12px;margin-top:2px">'+esc(summary)+'</div>' : '')
    + '</div>';
}}

async function loadSheetActs(v) {{
  var acts = await fetchAll(v._actsTid);
  var mine = acts.filter(function(a) {{
    var lf = a[v._link];
    return Array.isArray(lf) ? lf.some(function(r) {{ return r.id === v.id; }}) : false;
  }});
  mine.sort(function(a,b) {{ return (b['Date']||'').localeCompare(a['Date']||''); }});
  var el = document.getElementById('m-acts-' + v.id);
  if (!el) return;
  if (!mine.length) {{ el.innerHTML = '<div style="color:var(--text3)">No activities yet</div>'; return; }}
  el.innerHTML = mine.slice(0,20).map(renderMapAct).join('');
}}

async function loadSheetBoxes(venueId) {{
  var boxes = await fetchAll(_GBOXES);
  var mine = boxes.filter(function(b) {{
    var biz = b['Business'];
    return Array.isArray(biz) && biz.some(function(r) {{ return r.id === venueId; }});
  }});
  // Update global box alerts for pin indicators
  var worstLevel = null;
  mine.forEach(function(b) {{
    if (sv(b['Status']) === 'Active' && b['Date Placed']) {{
      var days = daysUntil(b['Date Placed']);
      if (days !== null) {{
        var age = -days;
        var pickupDays = parseInt(b['Pickup Days']) || 14;
        if (age >= pickupDays * 2) worstLevel = 'action';
        else if (age >= pickupDays && worstLevel !== 'action') worstLevel = 'warning';
      }}
    }}
  }});
  if (worstLevel) _boxAlerts[venueId] = worstLevel;
  var el = document.getElementById('m-boxes-' + venueId);
  if (!el) return;
  if (!mine.length) {{ el.innerHTML = '<div style="color:var(--text3)">No massage boxes placed</div>'; return; }}
  el.innerHTML = mine.map(function(b) {{
    var st = sv(b['Status']) || '';
    var sc = st === 'Active' ? '#059669' : '#475569';
    var loc = b['Location Notes'] || '';
    var contactP = b['Contact Person'] || '';
    // Timer badge for active boxes
    var timerBadge = '';
    if (st === 'Active' && b['Date Placed']) {{
      var age = -(daysUntil(b['Date Placed']) || 0);
      var pickupDays = parseInt(b['Pickup Days']) || 14;
      if (age >= pickupDays * 2) timerBadge = '<span style="background:#ef444420;color:#ef4444;border-radius:4px;padding:2px 6px;font-size:10px;font-weight:600;margin-left:6px">' + age + 'd - Action needed</span>';
      else if (age >= pickupDays) timerBadge = '<span style="background:#f59e0b20;color:#f59e0b;border-radius:4px;padding:2px 6px;font-size:10px;font-weight:600;margin-left:6px">' + age + 'd - Follow up</span>';
      else timerBadge = '<span style="background:#05966920;color:#059669;border-radius:4px;padding:2px 6px;font-size:10px;font-weight:600;margin-left:6px">' + age + 'd</span>';
    }}
    return '<div style="padding:8px 0;border-bottom:1px solid var(--border);font-size:13px">'
      + '<div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px">'
      + '<span style="background:'+sc+'20;color:'+sc+';border-radius:4px;padding:2px 6px;font-size:11px;font-weight:600">'+esc(st)+'</span>'
      + timerBadge
      + '</div>'
      + (b['Date Placed'] ? '<div style="font-size:12px;color:var(--text3);margin-top:3px">Placed '+esc(fmt(b['Date Placed'])) + (loc ? ' \u2022 ' + esc(loc) : '') + '</div>' : '')
      + (contactP ? '<div style="font-size:12px;color:var(--text3)">Contact: '+esc(contactP)+'</div>' : '')
      + (b['Leads Generated'] ? '<div style="font-size:12px;color:var(--text2);margin-top:2px">'+b['Leads Generated']+' leads generated</div>' : '')
      + '</div>';
  }}).join('');
}}

function prefillEvent(venueName, venueAddr, venuePhone, e) {{
  if (e) e.stopPropagation();
  closeSheet();
  s2Reset();
  setTimeout(function() {{
    var el;
    el = document.getElementById('s2-event-name'); if (el) el.value = venueName || '';
    el = document.getElementById('s2-addr');        if (el) el.value = venueAddr || '';
    el = document.getElementById('s2-org-phone');   if (el) el.value = venuePhone || '';
    document.getElementById('gfr-form-s2').classList.add('open');
  }}, 100);
}}
function prefillEventCurrent(e) {{
  if (!_currentVenueM) return;
  prefillEvent(_currentVenueM['Name']||'', _currentVenueM['Address']||'', _currentVenueM['Phone']||'', e);
}}

// -- Tab switching ----------------------------------------------------------
var _activeTab = 'info';
function mSheetTab(el, panelId) {{
  document.querySelectorAll('.m-tab').forEach(function(t){{t.classList.remove('active');}});
  document.querySelectorAll('.m-panel').forEach(function(p){{p.classList.remove('active');}});
  el.classList.add('active');
  var panel = document.getElementById(panelId);
  if (panel) panel.classList.add('active');
  // Update bottom CTA based on tab
  var btn = document.getElementById('m-cta-btn');
  if (!btn) return;
  if (panelId.indexOf('mp-evts-') === 0) {{
    _activeTab = 'events';
    btn.textContent = 'Schedule Event';
    btn.style.background = '#2563eb';
  }} else if (panelId.indexOf('mp-acts-') === 0) {{
    _activeTab = 'activity';
    btn.textContent = 'Check In';
    btn.style.background = '#004ac6';
  }} else {{
    _activeTab = 'info';
    btn.textContent = 'Check In';
    btn.style.background = '#004ac6';
  }}
}}
function mCtaAction() {{
  if (_activeTab === 'events') {{
    // Scroll to top of events panel to show schedule options
    var sheet = document.getElementById('m-sheet');
    if (sheet) sheet.scrollTop = 0;
  }} else {{
    prefillEventCurrent(null);
  }}
}}

// -- Place Box form ---------------------------------------------------------
async function placeBoxM(venueId) {{
  var loc = document.getElementById('m-box-loc-' + venueId).value.trim();
  var contact = document.getElementById('m-box-contact-' + venueId).value.trim();
  var st = document.getElementById('m-box-st-' + venueId);
  if (!loc) {{ alert('Please enter the box location.'); return; }}
  if (st) st.textContent = 'Saving\u2026';
  try {{
    var r = await fetch('/api/guerilla/boxes', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{venue_id: venueId, location: loc, contact_person: contact}})
    }});
    var d = await r.json();
    if (d.ok) {{
      if (st) {{ st.style.color = '#059669'; st.textContent = 'Box placed \u2713'; }}
      document.getElementById('m-box-loc-' + venueId).value = '';
      document.getElementById('m-box-contact-' + venueId).value = '';
      loadSheetBoxes(venueId);
      setTimeout(function(){{ if(st) st.textContent=''; }}, 3000);
    }} else {{
      if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Error: ' + (d.error||'Unknown'); }}
    }}
  }} catch(e) {{
    if (st) {{ st.style.color = '#ef4444'; st.textContent = 'Network error'; }}
  }}
}}

loadMapVenues();
"""
    script_js = f"const GFR_USER={repr(user_name)};\nconst TOOL = {{venuesT: {T_GOR_VENUES}}};\n" + map_js
    return _mobile_page('m_map', 'Map', body, script_js, br, bt, user=user, wrap_cls='map-mode',
                         extra_html=GFR_EXTRA_HTML, extra_js=GFR_EXTRA_JS)
