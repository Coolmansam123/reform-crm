"""Outreach Due list + Outreach Map."""

import os

from hub.shared import (
    _mobile_page,
)


def _mobile_outreach_due_page(br: str, bt: str, user: dict = None) -> str:
    """Cross-category list of companies with past-due Follow-Up Dates.
    Fetches `/api/outreach/due` (server-filtered). Each row shows name,
    category pill, phone (tel:), days overdue. Tap a row → Company detail
    page (shipped in a later iteration)."""
    user = user or {}
    body = (
        '<div class="mobile-hdr">'
        '<div><div class="mobile-hdr-title">Outreach Due</div>'
        '<div class="mobile-hdr-sub">Companies past their follow-up date</div></div>'
        '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        '</div>'
        '<div class="mobile-body">'
        '<div class="stats-row" style="margin-bottom:14px">'
        '<div class="stat-chip c-red"><div class="label">Total Overdue</div><div class="value" id="od-kpi-total">—</div></div>'
        '<div class="stat-chip c-orange"><div class="label">14+ Days</div><div class="value" id="od-kpi-bad">—</div></div>'
        '<div class="stat-chip c-yellow"><div class="label">Worst</div><div class="value" id="od-kpi-worst">—</div></div>'
        '</div>'
        '<div id="od-filter" style="display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap"></div>'
        '<div id="od-summary" style="font-size:12px;color:var(--text3);margin-bottom:10px">Loading…</div>'
        '<div id="od-list"><div class="loading">Loading…</div></div>'
        '</div>'
    )
    js = """
var _OD_ROWS = [];
var _OD_FILTER = 'all';  // 'all' | 'attorney' | 'guerilla' | 'community' | 'other'

var CAT_META = {
  attorney:  {label: 'Attorney',  color: '#7c3aed', icon: '⚖'},
  guerilla:  {label: 'Guerilla',  color: '#ea580c', icon: '\U0001f3cb'},
  community: {label: 'Community', color: '#059669', icon: '\U0001f91d'},
  other:     {label: 'Other',     color: '#64748b', icon: '\U0001f4cd'},
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
    var meta = k === 'all' ? {label: 'All', color: '#0f172a'} : CAT_META[k];
    html +=
      '<button onclick="setFilter(\\'' + k + '\\')" ' +
      'style="padding:6px 12px;border-radius:16px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;' +
      'border:1px solid ' + (active ? meta.color : 'var(--border)') + ';' +
      'background:' + (active ? meta.color : 'var(--card)') + ';' +
      'color:' + (active ? '#fff' : 'var(--text2)') + '">' +
      esc(meta.label) + ' ' + counts[k] + '</button>';
  });
  document.getElementById('od-filter').innerHTML = html;
}

function setFilter(k) {
  _OD_FILTER = k;
  renderFilter();
  renderList();
}

function renderList() {
  var list = _OD_FILTER === 'all'
    ? _OD_ROWS
    : _OD_ROWS.filter(function(r) { return (r.category || 'other') === _OD_FILTER; });

  document.getElementById('od-summary').textContent =
    list.length === 0 ? 'No overdue follow-ups in this filter.' :
    (list.length + ' compan' + (list.length === 1 ? 'y' : 'ies') + ' overdue');

  if (!list.length) {
    document.getElementById('od-list').innerHTML =
      '<div style="text-align:center;padding:40px 16px;color:var(--text3);font-size:13px">' +
      '\U0001f389 No overdue follow-ups.</div>';
    return;
  }

  var html = '';
  list.forEach(function(r) {
    var meta = CAT_META[r.category] || CAT_META.other;
    var color = overdueColor(r.days_overdue);
    var label = r.days_overdue === 0 ? 'Today' :
                r.days_overdue === 1 ? '1d overdue' :
                r.days_overdue + 'd overdue';
    html +=
      '<div onclick="location.href=\\'/company/' + r.id + '\\'" ' +
      'style="background:var(--card);border:1px solid var(--border);border-left:3px solid ' + color +
      ';border-radius:10px;padding:12px 14px;margin-bottom:8px;cursor:pointer">' +
      '<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:6px">' +
      '<div style="flex:1;min-width:0">' +
      '<div style="font-size:14px;font-weight:700;color:var(--text);word-break:break-word">' + esc(r.name) + '</div>' +
      (r.address ? '<div style="font-size:11px;color:var(--text3);margin-top:2px">' + esc(r.address) + '</div>' : '') +
      '</div>' +
      '<span style="background:' + meta.color + '22;color:' + meta.color + ';font-size:10px;' +
      'font-weight:600;padding:2px 8px;border-radius:10px;white-space:nowrap">' + esc(meta.label) + '</span>' +
      '</div>' +
      '<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:6px">' +
      '<span style="font-size:11px;font-weight:600;color:' + color + '">' + esc(label) + '</span>' +
      (r.phone
        ? '<a href="tel:' + esc(r.phone) + '" onclick="event.stopPropagation()" style="font-size:12px;color:#3b82f6;font-weight:600;text-decoration:none">' +
          '\U0001f4de ' + esc(r.phone) + '</a>'
        : '<span style="font-size:11px;color:var(--text3)">no phone</span>') +
      '</div>' +
      '</div>';
  });
  document.getElementById('od-list').innerHTML = html;
}

async function loadOD() {
  try {
    var r = await fetch('/api/outreach/due');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    _OD_ROWS = await r.json();
    // Active Partners have graduated out of the rep's outreach pipeline.
    _OD_ROWS = (_OD_ROWS || []).filter(function(row) {
      return row.status !== 'Active Partner';
    });
  } catch (e) {
    document.getElementById('od-summary').textContent = '';
    document.getElementById('od-list').innerHTML =
      '<div style="text-align:center;padding:40px 16px;color:#ef4444;font-size:13px">' +
      'Failed to load: ' + esc(e.message || 'unknown') + '</div>';
    return;
  }
  renderFilter();
  renderList();
  // KPI strip
  var total = _OD_ROWS.length;
  var bad14 = _OD_ROWS.filter(function(r) { return (r.days_overdue || 0) >= 14; }).length;
  var worst = _OD_ROWS.reduce(function(m, r) { return Math.max(m, r.days_overdue || 0); }, 0);
  document.getElementById('od-kpi-total').textContent = total;
  document.getElementById('od-kpi-bad').textContent = bad14;
  document.getElementById('od-kpi-worst').textContent = worst ? (worst + 'd') : '—';
}

loadOD();
"""
    return _mobile_page('m_outreach', 'Outreach Due', body, js, br, bt, user=user)




def _mobile_outreach_map_page(br: str, bt: str, user: dict = None) -> str:
    """Full-screen Google Map plotting overdue-follow-up companies near the
    rep's current location. Tap a pin → InfoWindow → "Details" link opens
    the mobile company detail page."""
    import os as _os
    gk = _os.environ.get("GOOGLE_MAPS_API_KEY", "")
    user = user or {}
    body = (
        '<div class="mobile-hdr">'
        '<div><div class="mobile-hdr-title">Outreach Map</div>'
        '<div class="mobile-hdr-sub">Overdue follow-ups near you</div></div>'
        '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        '</div>'
        '<div id="om-map" style="height:calc(100vh - 120px);width:100%;background:var(--bg2)"></div>'
        '<div id="om-msg" style="text-align:center;padding:8px;font-size:12px;color:var(--text3);min-height:14px"></div>'
    )
    js = f"""
const GK = {repr(gk)};
const OFFICE = {{lat: 33.9478, lng: -118.1335}};  // Downey
let _OM_MAP = null;
let _OM_ROWS = [];
let _OM_MARKERS = [];

var CAT_COLOR = {{
  attorney: '#7c3aed',
  guerilla: '#ea580c',
  community: '#059669',
  other: '#64748b',
}};

function esc(s) {{
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}}

async function loadOM() {{
  try {{
    var r = await fetch('/api/outreach/due');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    _OM_ROWS = await r.json();
    // Active Partners have graduated out of the rep's outreach pipeline.
    _OM_ROWS = (_OM_ROWS || []).filter(function(row) {{
      return row.status !== 'Active Partner';
    }});
  }} catch (e) {{
    document.getElementById('om-msg').textContent = 'Failed to load: ' + (e.message || 'unknown');
    return;
  }}
  if (!GK) {{
    document.getElementById('om-msg').textContent = 'Maps API key not configured.';
    return;
  }}
  // Lazy-load Maps JS
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
  var center = OFFICE;
  _OM_MAP = new google.maps.Map(document.getElementById('om-map'), {{
    center: center,
    zoom: 11,
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: false,
  }});
  plotRows();
  // Try to center on rep's live location — non-blocking.
  if (navigator.geolocation) {{
    navigator.geolocation.getCurrentPosition(function(pos) {{
      var here = {{lat: pos.coords.latitude, lng: pos.coords.longitude}};
      _OM_MAP.panTo(here);
      _OM_MAP.setZoom(13);
      new google.maps.Marker({{
        position: here, map: _OM_MAP,
        icon: {{
          path: google.maps.SymbolPath.CIRCLE,
          scale: 8, fillColor: '#3b82f6', fillOpacity: 1,
          strokeColor: '#fff', strokeWeight: 2,
        }},
        title: 'You are here',
      }});
    }}, function() {{}}, {{timeout: 5000}});
  }}
}}

function plotRows() {{
  _OM_MARKERS.forEach(function(m) {{ m.setMap(null); }});
  _OM_MARKERS = [];
  var bounds = new google.maps.LatLngBounds();
  var plotted = 0;
  _OM_ROWS.forEach(function(r) {{
    var lat = parseFloat(r.latitude); var lng = parseFloat(r.longitude);
    if (!lat || !lng || isNaN(lat) || isNaN(lng)) return;
    var color = CAT_COLOR[r.category] || CAT_COLOR.other;
    var marker = new google.maps.Marker({{
      position: {{lat: lat, lng: lng}},
      map: _OM_MAP,
      icon: {{
        path: google.maps.SymbolPath.BACKWARD_CLOSED_ARROW,
        scale: 5, fillColor: color, fillOpacity: 0.95,
        strokeColor: '#fff', strokeWeight: 1.5,
      }},
      title: r.name,
    }});
    var iw = new google.maps.InfoWindow({{
      content: '<div style="font-family:system-ui;max-width:200px">' +
               '<div style="font-weight:700;font-size:13px;margin-bottom:4px">' + esc(r.name) + '</div>' +
               '<div style="font-size:11px;color:#64748b;margin-bottom:6px">' + r.days_overdue + 'd overdue</div>' +
               (r.phone ? '<a href="tel:' + esc(r.phone) + '" style="font-size:12px;color:#3b82f6;text-decoration:none;display:block;margin-bottom:3px">\U0001f4de ' + esc(r.phone) + '</a>' : '') +
               '<a href="/company/' + r.id + '" style="font-size:12px;color:#ea580c;font-weight:600;text-decoration:none">View details →</a>' +
               '</div>',
    }});
    marker.addListener('click', function() {{ iw.open(_OM_MAP, marker); }});
    _OM_MARKERS.push(marker);
    bounds.extend(marker.getPosition());
    plotted++;
  }});
  document.getElementById('om-msg').textContent =
    plotted + ' pin' + (plotted === 1 ? '' : 's') + ' (of ' + _OM_ROWS.length + ' overdue companies) have coordinates';
  if (plotted > 0) {{
    _OM_MAP.fitBounds(bounds, 40);
    if (_OM_MAP.getZoom() > 14) _OM_MAP.setZoom(14);
  }}
}}

loadOM();
"""
    return _mobile_page('m_outreach_map', 'Outreach Map', body, js, br, bt, user=user)
