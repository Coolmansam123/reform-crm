"""Home dashboard + My Routes dashboard."""

import os

from hub.shared import (
    _mobile_page,
    T_GOR_VENUES, T_GOR_BOXES, T_GOR_ROUTES, T_GOR_ROUTE_STOPS, T_LEADS,
    T_COMPANIES, T_EVENTS,
)
from hub.guerilla import GFR_EXTRA_HTML, GFR_EXTRA_JS
from hub.maps import MAP_PALETTE_JS, OFFICE_PIN_JS, map_script_url
from hub.tz import local_today


_HOME_CSS = """
<style>
#home-root[data-state="A"] .only-b,
#home-root[data-state="A"] .only-c { display:none }
#home-root[data-state="B"] .only-a,
#home-root[data-state="B"] .only-c { display:none }
#home-root[data-state="C"] .only-a,
#home-root[data-state="C"] .only-b { display:none }
.qlog-row { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:18px }
.qlog-btn { background:var(--card); border:1px solid var(--border); border-radius:12px;
            padding:14px 6px; font-size:12px; font-weight:600; color:var(--text);
            text-align:center; cursor:pointer; text-decoration:none;
            display:flex; flex-direction:column; align-items:center; gap:6px;
            font-family:inherit; min-height:72px; line-height:1.2 }
.qlog-btn:active { background:rgba(0,74,198,.08) }
.qlog-btn .material-symbols-outlined { font-size:24px; color:#004ac6 }
.qlog-btn[data-active="1"] { background:#004ac6; border-color:#004ac6; color:#fff }
.qlog-btn[data-active="1"] .material-symbols-outlined { color:#fff }

/* KPI strip */
#kpi-strip { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-bottom:18px }
.kpi-card { background:var(--card); border:1px solid var(--border); border-radius:12px;
            padding:12px 8px; text-align:center; text-decoration:none; color:inherit;
            display:block }
.kpi-card:active { background:rgba(0,74,198,.06) }
.kpi-label { font-size:10px; font-weight:600; color:var(--text3);
             letter-spacing:.6px; margin-bottom:4px }
.kpi-val { font-size:22px; font-weight:700; color:var(--text); line-height:1 }

/* Events strip */
#events-strip { margin-bottom:18px }
.strip-hdr { display:flex; align-items:baseline; justify-content:space-between;
             margin-bottom:8px }
.strip-link { font-size:11px; color:var(--text3); text-decoration:none }
#events-rail { display:flex; gap:10px; overflow-x:auto;
               -webkit-overflow-scrolling:touch; scrollbar-width:none;
               padding-bottom:4px }
#events-rail::-webkit-scrollbar { display:none }
.event-card { min-width:180px; padding:12px; border-radius:10px;
              border:1px solid var(--border); background:var(--card);
              text-decoration:none; color:inherit; flex-shrink:0;
              display:flex; flex-direction:column; gap:2px }
.event-when { font-size:10px; font-weight:700; color:#004ac6;
              letter-spacing:.4px; margin-bottom:2px; text-transform:uppercase }
.event-name { font-size:13px; font-weight:600; color:var(--text);
              display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
              overflow:hidden }
.event-where { font-size:11px; color:var(--text3);
               white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
.event-empty { color:var(--text3); font-size:12px; padding:14px;
               border:1px dashed var(--border); border-radius:10px;
               width:100%; text-align:center; flex-shrink:0 }

/* Leaderboard */
#leaderboard-card { background:var(--card); border:1px solid var(--border);
                    border-radius:12px; padding:12px 14px; margin-bottom:18px }
.lb-hdr { display:flex; align-items:baseline; justify-content:space-between;
          margin-bottom:8px }
.lb-metric { font-size:11px; color:var(--text3) }
.lb-row { display:grid; grid-template-columns:24px 1fr auto; gap:10px;
          align-items:center; padding:6px 0; font-size:13px }
.lb-row[data-self="1"] { background:rgba(0,74,198,.08); border-radius:6px;
                         padding:6px 8px; margin:0 -8px }
.lb-rank { color:var(--text3); font-weight:600; text-align:center }
.lb-name { color:var(--text); font-weight:500;
           white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
.lb-val { color:#004ac6; font-weight:700 }
.lb-divider { height:1px; background:var(--border); margin:6px 0 }

/* Worklist count badge */
#wl-ct { background:#fee2e2; color:#b91c1c; padding:2px 9px;
         border-radius:999px; font-size:11px; font-weight:600 }
#wl-ct:empty { display:none }
.hero-c { padding:18px 20px; color:#fff;
          background:linear-gradient(135deg,#004ac6,#0066ee);
          border-radius:12px; border:none }
.hero-c .label-caps { color:rgba(255,255,255,.78) }
.hero-c .h-actions { display:flex; gap:8px; margin-top:14px }
.hero-c .h-actions button { flex:1; border:none; border-radius:8px;
                            padding:11px 10px; font-size:13px; font-weight:700;
                            cursor:pointer; font-family:inherit }
.hero-c .h-primary { background:#fff; color:#004ac6 }
.hero-c .h-secondary { background:rgba(255,255,255,.18); color:#fff }
.recap-card { display:block; text-align:center; padding:10px; font-size:12px;
              color:var(--text3); border:1px dashed var(--border);
              border-radius:10px; text-decoration:none; background:transparent }

/* ── Map card ───────────────────────────────────────────────────────── */
#home-map-card { margin-bottom:18px; border:1px solid var(--border);
                 border-radius:12px; overflow:hidden; background:var(--card) }
#hm-chips { display:flex; gap:6px; padding:10px;
            overflow-x:auto; -webkit-overflow-scrolling:touch;
            scrollbar-width:none }
#hm-chips::-webkit-scrollbar { display:none }
#hm-map { width:100%; height:240px; background:var(--bg); position:relative }
#hm-map-empty { position:absolute; inset:0; display:flex;
                align-items:center; justify-content:center;
                color:var(--text3); font-size:13px; pointer-events:none }
#hm-legend { font-size:11px; color:var(--text3);
             padding:6px 10px; border-top:1px solid var(--border);
             min-height:14px }

/* Desktop: cap content column width and bump map height. */
@media (min-width: 720px) {
  .mobile-body { max-width:520px; margin-left:auto; margin-right:auto }
  #hm-map { height:300px }
}
</style>
"""


def _mobile_home_page(br: str, bt: str, user: dict = None) -> str:
    gk      = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    gmap_id = os.environ.get("GOOGLE_MAPS_MAP_ID", "")
    user = user or {}
    first = (user.get('name', 'there') or 'there').split()[0]
    today = local_today()
    day_str = f"{today.strftime('%A')}, {today.strftime('%B')} {today.day}"
    user_name = user.get('name', '')
    user_email = (user.get('email', '') or '').strip().lower()

    body = (
        '<div class="mobile-hdr">'
        + '<div><div class="mobile-hdr-title"><img src="/static/reform-logo.png" alt="Reform" style="height:22px;width:auto;display:block"></div>'
        + f'<div class="mobile-hdr-sub">{day_str}</div></div>'
        + '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        + '</div>'
        + _HOME_CSS
        + '<div class="mobile-body">'
        + '<div id="home-root" data-state="A">'
        # ── Hero slot ──────────────────────────────────────────────────────
        + '<div id="hero-slot" style="margin-bottom:18px">'
        +   '<div class="only-a">'
        +     f'<div style="font-size:26px;font-weight:700;color:var(--text);margin-bottom:4px;letter-spacing:-0.3px">Hey, {first}!</div>'
        +     '<div style="font-size:13px;color:var(--text3)">Ready to hit the field?</div>'
        +   '</div>'
        +   '<div class="only-b" id="hero-b"></div>'
        +   '<div class="only-c" id="hero-c"></div>'
        + '</div>'
        # ── KPI strip (rep-scoped 7d) ──────────────────────────────────────
        + '<div id="kpi-strip">'
        +   '<a href="/lead" class="kpi-card">'
        +     '<div class="kpi-label">LEADS (7D)</div>'
        +     '<div class="kpi-val" id="kpi-leads">—</div></a>'
        +   '<a href="/routes" class="kpi-card">'
        +     '<div class="kpi-label">VISITS (7D)</div>'
        +     '<div class="kpi-val" id="kpi-visits">—</div></a>'
        +   '<a href="/events" class="kpi-card">'
        +     '<div class="kpi-label">EVENTS</div>'
        +     '<div class="kpi-val" id="kpi-events">—</div></a>'
        + '</div>'
        # ── Recent Events strip ────────────────────────────────────────────
        + '<div id="events-strip">'
        +   '<div class="strip-hdr">'
        +     '<span class="label-caps">Upcoming Events</span>'
        +     '<a href="/events" class="strip-link">See all →</a>'
        +   '</div>'
        +   '<div id="events-rail">'
        +     '<div class="event-empty">Loading…</div>'
        +   '</div>'
        + '</div>'
        # ── Quick-log row (3 buttons: Lead / Visit / Event) ────────────────
        + '<div class="qlog-row">'
        +   '<button class="qlog-btn" onclick="quickLog(\'lead\')">'
        +     '<span class="material-symbols-outlined">person_add</span>'
        +     '<span>Log Lead</span></button>'
        +   '<button class="qlog-btn" id="qlog-visit-btn" onclick="quickLog(\'visit\')">'
        +     '<span class="material-symbols-outlined">check_circle</span>'
        +     '<span id="qlog-visit-lbl">Log Visit</span></button>'
        +   '<button class="qlog-btn" onclick="quickLog(\'event\')">'
        +     '<span class="material-symbols-outlined">event</span>'
        +     '<span>Log Event</span></button>'
        + '</div>'
        # ── Map card (anchor) ──────────────────────────────────────────────
        + '<div id="home-map-card">'
        +   '<div id="hm-chips"></div>'
        +   '<div id="hm-map"><div id="hm-map-empty">Loading map…</div></div>'
        +   '<div id="hm-legend"></div>'
        + '</div>'
        # ── Top Performers leaderboard ─────────────────────────────────────
        + '<div id="leaderboard-card">'
        +   '<div class="lb-hdr">'
        +     '<span class="label-caps">Top Performers · 7d</span>'
        +     '<span class="lb-metric">Leads</span>'
        +   '</div>'
        +   '<div id="lb-body">'
        +     '<div style="color:var(--text3);font-size:12px;text-align:center;padding:8px">Loading…</div>'
        +   '</div>'
        + '</div>'
        # ── Worklist ───────────────────────────────────────────────────────
        + '<div class="label-caps" style="display:flex;align-items:center;gap:6px;margin-bottom:8px">'
        +   '<span class="material-symbols-outlined" style="font-size:14px;color:#ba1a1a">priority_high</span>'
        +   '<span>Worklist</span>'
        +   '<span id="wl-ct" style="margin-left:auto"></span></div>'
        + '<div id="wl-body" style="display:flex;flex-direction:column;gap:10px;margin-bottom:18px">'
        +   '<div class="card" style="color:var(--text3);text-align:center;font-size:13px">Loading…</div>'
        + '</div>'
        # ── Yesterday recap ────────────────────────────────────────────────
        + '<div id="recap-slot"></div>'
        + '</div>'  # /home-root
        + '</div>'  # /mobile-body
    )

    # JS: head with constants (interpolated), body with single braces.
    js_head = (
        f"const GFR_USER = {repr(user_name)};\n"
        f"const USER_EMAIL = {repr(user_email)};\n"
        f"const T_GOR_VENUES = {T_GOR_VENUES};\n"
        f"const T_GOR_BOXES = {T_GOR_BOXES};\n"
        f"const T_GOR_ROUTES = {T_GOR_ROUTES};\n"
        f"const T_GOR_ROUTE_STOPS = {T_GOR_ROUTE_STOPS};\n"
        f"const T_LEADS = {T_LEADS};\n"
        f"const T_COMPANIES = {T_COMPANIES};\n"
        f"const T_EVENTS = {T_EVENTS};\n"
        f"const TOOL = {{ venuesT: {T_GOR_VENUES} }};\n"
        f"const HM_GK = {repr(gk)};\n"
        f"const HM_MAP_ID = {repr(gmap_id)};\n"
        f"const HM_SCRIPT_URL = {repr(map_script_url(gk, '_homeMapReadyCb'))};\n"
    )

    js_body = MAP_PALETTE_JS + OFFICE_PIN_JS + r"""
// ═══════════════════════════════════════════════════════════════════════
// Home map — embedded interactive map with toggleable layers.
// Color palettes + office-pin factory come from hub.maps (injected above).
// ═══════════════════════════════════════════════════════════════════════
// Aliases so existing references stay terse.
const _HM_STATUS_COLORS = _MAP_STATUS_COLORS;
const _HM_BOX_COLORS    = _MAP_BOX_COLORS;
const _HM_OVERDUE_COLOR = '#ef4444';

const HM_LAYERS = ['route','boxes','visits','overdue'];
const HM_CHIP_LABELS = {
  route:   { label: 'Route',   dot: '#004ac6' },
  boxes:   { label: 'Boxes',   dot: '#059669' },
  visits:  { label: 'Visits',  dot: '#8b5cf6' },
  overdue: { label: 'Overdue', dot: '#ef4444' },
};
// `overdue` is OFF by default in every state per direction —
// it's more for admins than reps.
const HM_DEFAULTS = {
  A: { route:0, boxes:1, visits:1, overdue:0 },
  B: { route:1, boxes:1, visits:0, overdue:0 },
  C: { route:1, boxes:0, visits:0, overdue:0 },
};

let _hmMap            = null;
let _hmIW             = null;  // shared InfoWindow
let _hmMarkers        = {};    // 'layer:id' -> AdvancedMarkerElement
let _hmLayerData      = { route:[], boxes:[], visits:[], overdue:[] };
let _hmLayerOn        = null;  // {route:1, boxes:1, ...}
let _hmInitialized    = false;
let _hmLastPanStopId  = null;  // auto-pan latch — pans once per arrival

function _hmLoadLayerPrefs() {
  try {
    const raw = localStorage.getItem('hm.layers.' + USER_EMAIL);
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return null;
}
function _hmSaveLayerPrefs(prefs) {
  try { localStorage.setItem('hm.layers.' + USER_EMAIL, JSON.stringify(prefs)); } catch (e) {}
}

// ── Pin factories ──────────────────────────────────────────────────────
function _hmFallbackDot(color) {
  const el = document.createElement('div');
  el.style.cssText = 'width:12px;height:12px;border-radius:50%;background:' + color
    + ';border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.35);box-sizing:content-box';
  return el;
}
function _hmRoutePin(stopOrder, status) {
  const fill = _HM_STATUS_COLORS[status] || '#4285f4';
  if (!(google.maps.marker && google.maps.marker.PinElement)) return _hmFallbackDot(fill);
  const pin = new google.maps.marker.PinElement({
    background: fill, borderColor: '#fff',
    glyph: String(stopOrder || ''), glyphColor: '#fff', scale: 1.15,
  });
  return pin.element;
}
function _hmBoxPin(level) {
  const color = _HM_BOX_COLORS[level] || _HM_BOX_COLORS.ok;
  if (!(google.maps.marker && google.maps.marker.PinElement)) return _hmFallbackDot(color);
  const pin = new google.maps.marker.PinElement({
    background: color, borderColor: '#fff',
    glyphColor: '#fff', glyph: '', scale: 1.0,
  });
  return pin.element;
}
function _hmVisitDot() {
  // Custom HTML — recedes visually so route + boxes stay primary.
  const el = document.createElement('div');
  el.style.cssText = 'width:10px;height:10px;border-radius:50%;background:#8b5cf6'
    + ';border:2px solid #fff;opacity:.6;box-shadow:0 1px 2px rgba(0,0,0,.3)'
    + ';box-sizing:content-box';
  return el;
}
function _hmOverduePin() {
  if (!(google.maps.marker && google.maps.marker.PinElement)) return _hmFallbackDot(_HM_OVERDUE_COLOR);
  const pin = new google.maps.marker.PinElement({
    background: _HM_OVERDUE_COLOR, borderColor: '#7f1d1d',
    glyph: '!', glyphColor: '#fff', scale: 1.1,
  });
  return pin.element;
}

// ── Map init (lazy, idempotent) ────────────────────────────────────────
function hmInit() {
  if (_hmInitialized) return;
  if (!HM_GK) {
    const card = document.getElementById('home-map-card');
    if (card) card.style.display = 'none';
    console.warn('GOOGLE_MAPS_API_KEY not set — home map hidden.');
    return;
  }
  if (!HM_MAP_ID) {
    console.warn('GOOGLE_MAPS_MAP_ID not set — AdvancedMarkers may not render.');
  }
  _hmInitialized = true;
  if (window.google && window.google.maps && window.google.maps.marker) {
    _hmReady();
  } else {
    window._homeMapReadyCb = _hmReady;
    const s = document.createElement('script');
    s.src = HM_SCRIPT_URL;  // built server-side via hub.maps.map_script_url
    s.async = true;
    s.onerror = () => {
      const card = document.getElementById('home-map-card');
      if (card) card.style.display = 'none';
    };
    document.head.appendChild(s);
  }
}

function _hmReady() {
  const el = document.getElementById('hm-map');
  if (!el) return;
  const opts = {
    center: { lat: 33.9478, lng: -118.1335 },  // Reform office (Downey)
    zoom: 11,
    mapTypeControl: false, streetViewControl: false, fullscreenControl: false,
    clickableIcons: false,
  };
  if (HM_MAP_ID) opts.mapId = HM_MAP_ID;
  _hmMap = new google.maps.Map(el, opts);
  _hmIW = new google.maps.InfoWindow();
  // Hide the loading placeholder
  const loading = document.getElementById('hm-map-empty');
  if (loading) loading.style.display = 'none';
  // Office marker (always visible) — navy star variant from hub.maps.
  const officeContent = _mapOfficePinNavy();
  if (officeContent && google.maps.marker && google.maps.marker.AdvancedMarkerElement) {
    new google.maps.marker.AdvancedMarkerElement({
      position: opts.center, map: _hmMap,
      title: 'Reform Chiropractic',
      content: officeContent,
    });
  }
  hmRefreshLayers();
}

// ── Chip rendering / toggle ────────────────────────────────────────────
function hmRenderChips() {
  const wrap = document.getElementById('hm-chips');
  if (!wrap || !_hmLayerOn) return;
  wrap.innerHTML = HM_LAYERS.map(layer => {
    const on = !!_hmLayerOn[layer];
    const meta = HM_CHIP_LABELS[layer];
    const ct = (_hmLayerData[layer] || []).length;
    const borderColor = on ? meta.dot : 'var(--border)';
    const bg = on ? (meta.dot + '1a') : 'var(--card)';
    const color = on ? meta.dot : 'var(--text2)';
    return '<button data-layer="' + layer + '" data-on="' + (on ? 1 : 0) + '"'
      + ' onclick="hmToggleLayer(\'' + layer + '\')"'
      + ' style="display:inline-flex;align-items:center;gap:6px;'
      + 'padding:8px 12px;border-radius:18px;'
      + 'border:1px solid ' + borderColor + ';background:' + bg + ';color:' + color + ';'
      + 'font-size:12px;font-weight:600;font-family:inherit;cursor:pointer;'
      + 'min-width:88px;min-height:36px;white-space:nowrap;flex-shrink:0">'
      + '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + meta.dot + '"></span>'
      + '<span>' + meta.label + '</span>'
      + '<span style="opacity:.7;font-weight:500">' + ct + '</span>'
      + '</button>';
  }).join('');
}

function hmToggleLayer(layer) {
  if (!_hmLayerOn) return;
  _hmLayerOn[layer] = _hmLayerOn[layer] ? 0 : 1;
  _hmSaveLayerPrefs(_hmLayerOn);
  hmRefreshLayers();
}

// ── Layer rendering ────────────────────────────────────────────────────
function hmRefreshLayers() {
  if (!_hmMap) return;
  // Drop existing layer markers
  Object.values(_hmMarkers).forEach(m => { m.map = null; });
  _hmMarkers = {};
  // Stack order (drawn first → behind): overdue, boxes, visits, route
  const order = ['overdue','boxes','visits','route'];
  order.forEach(layer => {
    if (!_hmLayerOn || !_hmLayerOn[layer]) return;
    const items = _hmLayerData[layer] || [];
    items.forEach(item => {
      if (!item || !item.lat || !item.lng) return;
      if (!(google.maps.marker && google.maps.marker.AdvancedMarkerElement)) return;
      let content;
      if      (layer === 'route')   content = _hmRoutePin(item.order, item.status);
      else if (layer === 'boxes')   content = _hmBoxPin(item.level);
      else if (layer === 'visits')  content = _hmVisitDot();
      else if (layer === 'overdue') content = _hmOverduePin();
      const m = new google.maps.marker.AdvancedMarkerElement({
        position: { lat: item.lat, lng: item.lng },
        map: _hmMap, title: item.name || '',
        content,
      });
      m.addListener('gmpClick', () => _hmOpenIW(m, layer, item));
      _hmMarkers[layer + ':' + (item.id != null ? item.id : Math.random())] = m;
    });
  });
  // Legend
  const legend = document.getElementById('hm-legend');
  if (legend) {
    const parts = HM_LAYERS.filter(l => _hmLayerOn[l])
      .map(l => (_hmLayerData[l] || []).length + ' ' + l);
    legend.textContent = parts.length
      ? parts.join(' · ')
      : 'No layers selected — tap a chip above';
  }
  // Re-render chips so the count badges reflect current data
  hmRenderChips();
}

function _hmOpenIW(marker, layer, item) {
  if (!_hmIW) return;
  let subtitle = '';
  let nav = item.nav || '/companies';
  if      (layer === 'route')   subtitle = 'Stop ' + (item.order || '?') + ' · ' + (item.status || 'Pending');
  else if (layer === 'boxes')   subtitle = (item.age != null ? item.age + 'd placed' : '')
                                         + (item.level && item.level !== 'ok' ? ' · ' + item.level : '');
  else if (layer === 'visits')  subtitle = 'Visited ' + (item.date || '');
  else if (layer === 'overdue') subtitle = (item.daysOverdue || 0) + 'd overdue';
  const html = '<div style="font-family:system-ui;max-width:220px">'
    + '<div style="font-weight:700;font-size:13px;margin-bottom:4px">' + esc(item.name || '') + '</div>'
    + '<div style="font-size:11px;color:#666;margin-bottom:6px">' + esc(subtitle) + '</div>'
    + '<a href="' + esc(nav) + '" style="font-size:12px;color:#004ac6;font-weight:600;text-decoration:none">Open →</a>'
    + '</div>';
  _hmIW.setContent(html);
  _hmIW.open({ map: _hmMap, anchor: marker });
}

// Auto-pan: pans to active stop ONCE per arrival; if rep manually pans
// after, subsequent loadHomeDashboard refreshes won't fight them.
function hmAutoPan(activeStop, lat, lng) {
  if (!activeStop) {
    _hmLastPanStopId = null;
    return;
  }
  if (_hmLastPanStopId === activeStop.id) return;
  if (!lat || !lng || !_hmMap) return;
  _hmMap.panTo({ lat: parseFloat(lat), lng: parseFloat(lng) });
  _hmMap.setZoom(16);
  _hmLastPanStopId = activeStop.id;
}

// ═══════════════════════════════════════════════════════════════════════
// Events rail + Top Performers renderers
// ═══════════════════════════════════════════════════════════════════════
function _hmRelDate(iso) {
  // Returns a short relative label: "Today", "Tomorrow", weekday, or "Mon 8".
  if (!iso) return '';
  const d = String(iso).slice(0, 10);
  const t = new Date().toISOString().slice(0, 10);
  const ms = new Date(d).getTime() - new Date(t).getTime();
  const days = Math.round(ms / 86400000);
  if (days === 0) return 'Today';
  if (days === 1) return 'Tomorrow';
  const dt = new Date(d + 'T00:00:00');
  if (days > 1 && days < 7) return dt.toLocaleDateString('en-US', { weekday: 'short' });
  return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
function hmRenderEventsStrip(upcoming) {
  const rail = document.getElementById('events-rail');
  if (!rail) return;
  if (!upcoming || !upcoming.length) {
    rail.innerHTML = '<div class="event-empty">No events in the next 7 days</div>';
    return;
  }
  const sorted = upcoming.slice()
    .sort((a, b) => (a['Event Date'] || '').localeCompare(b['Event Date'] || ''))
    .slice(0, 6);
  rail.innerHTML = sorted.map(e => {
    const when  = _hmRelDate(e['Event Date']);
    const name  = esc(e['Name'] || 'Event');
    const where = esc(e['Venue Address'] || e['Event Type'] || '');
    return '<a class="event-card" href="/events">' +
             '<div class="event-when">' + esc(when) + '</div>' +
             '<div class="event-name">' + name + '</div>' +
             (where ? '<div class="event-where">' + where + '</div>' : '') +
           '</a>';
  }).join('');
}
function hmRenderLeaderboard(lb) {
  const body = document.getElementById('lb-body');
  if (!body) return;
  if (!lb || !Array.isArray(lb.top) || !lb.top.length) {
    body.innerHTML = '<div style="color:var(--text3);font-size:12px;text-align:center;padding:8px">No activity yet this week</div>';
    return;
  }
  const _row = (r) => '<div class="lb-row" data-self="' + (r.is_self ? '1' : '0') + '">' +
                        '<span class="lb-rank">' + r.rank + '</span>' +
                        '<span class="lb-name">' + esc(r.is_self ? 'You' : r.name) + '</span>' +
                        '<span class="lb-val">' + r.leads + '</span>' +
                      '</div>';
  let html = lb.top.map(_row).join('');
  if (lb.self) {
    html += '<div class="lb-divider"></div>' + _row(lb.self);
  }
  body.innerHTML = html;
}

// ═══════════════════════════════════════════════════════════════════════
// Home dashboard — main loader.
// ═══════════════════════════════════════════════════════════════════════
async function loadHomeDashboard() {
  const [routes, stops, leads, boxes, companies, venues, events, overdueRaw, lbResp] = await Promise.all([
    fetchAll(T_GOR_ROUTES),
    fetchAll(T_GOR_ROUTE_STOPS),
    fetchAll(T_LEADS),
    fetchAll(T_GOR_BOXES),
    fetchAll(T_COMPANIES),
    fetchAll(T_GOR_VENUES),
    fetchAll(T_EVENTS),
    fetch('/api/outreach/due').then(r => r.ok ? r.json() : []).catch(() => []),
    fetch('/api/leaderboard?range=7d').then(r => r.ok ? r.json() : null).catch(() => null)
  ]);
  // Active Partners have graduated out of the rep's outreach pipeline.
  const overdueResp = (Array.isArray(overdueRaw) ? overdueRaw : [])
    .filter(c => c.status !== 'Active Partner');
  const venueCoMap = buildVenueCompanyMap(companies);
  // Venue lat/lng lookup for layers that only carry linked Business[] IDs.
  const venueLL = {};
  venues.forEach(v => {
    const lat = parseFloat(v['Latitude']);
    const lng = parseFloat(v['Longitude']);
    if (lat && lng) venueLL[v.id] = { lat, lng, name: v['Name'] || '' };
  });

  const myRoutes = routes.filter(r => (r['Assigned To']||'').trim().toLowerCase() === USER_EMAIL);
  const today = new Date().toISOString().slice(0, 10);

  const todayRoute = myRoutes.find(r => {
    const s = sv(r['Status']) || 'Draft';
    return r['Date'] === today && (s === 'Active' || s === 'Draft');
  });

  const todayStops = todayRoute
    ? stops.filter(s => Array.isArray(s['Route']) && s['Route'].some(x => x.id === todayRoute.id))
    : [];
  const activeStop = todayStops.find(s => sv(s['Status']) === 'In Progress');
  const visitedToday = todayStops.filter(s => {
    const ss = sv(s['Status']);
    return ss === 'Visited' || ss === 'Skipped';
  }).length;
  const PAGE_STATE = !todayRoute ? 'A' : activeStop ? 'C' : 'B';

  // Persist for action handlers (quickLog, markStop, etc.)
  window._pageState = PAGE_STATE;
  window._todayRoute = todayRoute || null;
  window._todayRouteId = todayRoute ? todayRoute.id : null;
  window._activeStop = activeStop || null;

  let activeVenueId = null, activeCompanyId = null, activeVenueName = '';
  if (activeStop) {
    const biz = (activeStop['Business'] || [])[0] || {};
    activeVenueId = biz.id || null;
    activeVenueName = biz.value || '';
    activeCompanyId = activeVenueId ? (venueCoMap[activeVenueId] || null) : null;
  }
  window._activeVenueId = activeVenueId;
  window._activeCompanyId = activeCompanyId;
  window._activeVenueName = activeVenueName;

  document.getElementById('home-root').setAttribute('data-state', PAGE_STATE);

  // ── Hero rendering ───────────────────────────────────────────────────
  if (PAGE_STATE === 'C') {
    const stopName = activeStop['Name'] || activeVenueName || 'Current Stop';
    const arrivedRaw = activeStop['Arrived At'] || '';
    const arrivedTime = arrivedRaw.length >= 16 ? arrivedRaw.slice(11, 16) : '';
    const elapsedMin = computeElapsedMin(arrivedRaw);
    document.getElementById('hero-c').innerHTML =
      '<div class="card hero-c">' +
        '<div class="label-caps">On site now</div>' +
        '<div style="font-size:20px;font-weight:700;line-height:1.25;margin-top:4px">' + esc(stopName) + '</div>' +
        '<div style="font-size:12px;opacity:.85;margin-top:4px">' +
          'Arrived ' + esc(arrivedTime) + ' · <span id="hero-elapsed">' + elapsedMin + 'm</span> elapsed' +
        '</div>' +
        '<div class="h-actions">' +
          '<button class="h-primary"   onclick="markStop(\'Visited\')">Mark Visited</button>' +
          '<button class="h-secondary" onclick="markStop(\'Skipped\')">Skip</button>' +
          '<button class="h-secondary" onclick="goStopNotes()">Notes</button>' +
        '</div>' +
      '</div>';
  } else if (PAGE_STATE === 'B') {
    const rname = esc(todayRoute['Name'] || "Today's Route");
    const sct = todayStops.length;
    document.getElementById('hero-b').innerHTML =
      '<a href="/route" class="mobile-cta mobile-cta-orange" style="display:flex">' +
        '<span class="mobile-cta-icon">🗺️</span>' +
        '<div><div>Start Today\'s Route</div>' +
          '<div class="mobile-cta-sub">' + rname + ' · ' + sct + ' stop' + (sct === 1 ? '' : 's') + '</div>' +
        '</div>' +
      '</a>';
  }

  // Quick-log Visit label/active flip when at a stop
  const visitLbl = document.getElementById('qlog-visit-lbl');
  const visitBtn = document.getElementById('qlog-visit-btn');
  if (visitLbl) visitLbl.textContent = (PAGE_STATE === 'C') ? 'Mark Visited' : 'Log Visit';
  if (visitBtn) visitBtn.setAttribute('data-active', PAGE_STATE === 'C' ? '1' : '0');

  // ── KPI strip (rep-scoped 7d) ────────────────────────────────────────
  const sevenDaysAgo = new Date(Date.now() - 7*86400000).toISOString().slice(0, 10);
  const overdueCount = Array.isArray(overdueResp) ? overdueResp.length : 0;
  const myLeads7d = leads.filter(l => {
    if ((l['Owner'] || '').trim().toLowerCase() !== USER_EMAIL) return false;
    const d = (l['Created'] || l['Date'] || '').slice(0, 10);
    return d && d >= sevenDaysAgo;
  }).length;
  const myVisits7d = stops.filter(s => {
    if ((s['Completed By'] || '').trim().toLowerCase() !== USER_EMAIL) return false;
    if (sv(s['Status']) !== 'Visited') return false;
    const d = (s['Completed At'] || '').slice(0, 10);
    return d && d >= sevenDaysAgo;
  }).length;
  const upcomingEvents = (events || []).filter(e => {
    const status = sv(e['Event Status']);
    if (status && status !== 'Scheduled' && status !== 'Active' && status !== 'Upcoming') return false;
    const d = (e['Event Date'] || '').slice(0, 10);
    return d && d >= today;
  });
  document.getElementById('kpi-leads').textContent  = myLeads7d;
  document.getElementById('kpi-visits').textContent = myVisits7d;
  document.getElementById('kpi-events').textContent = upcomingEvents.length;

  // ── Recent Events rail ───────────────────────────────────────────────
  hmRenderEventsStrip(upcomingEvents);

  // ── Top Performers ───────────────────────────────────────────────────
  hmRenderLeaderboard(lbResp);

  // ── Build map layer data ─────────────────────────────────────────────
  // Route layer: today's stops, ordered, with venue lat/lng fallback
  const routeLayer = todayStops.map(s => {
    const biz = (s['Business'] || [])[0] || {};
    const ll = (s['Check-In Lat'] && s['Check-In Lng'])
      ? { lat: parseFloat(s['Check-In Lat']), lng: parseFloat(s['Check-In Lng']) }
      : (biz.id && venueLL[biz.id]) || {};
    return {
      id:     s.id,
      lat:    ll.lat,
      lng:    ll.lng,
      name:   s['Name'] || biz.value || 'Stop',
      order:  s['Stop Order'] || '',
      status: sv(s['Status']) || 'Pending',
      nav:    '/route',
    };
  }).filter(x => x.lat && x.lng).sort((a, b) => (a.order || 0) - (b.order || 0));

  // Boxes layer: active boxes with overdue alert level
  const boxesLayer = boxes.filter(b => sv(b['Status']) === 'Active' && b['Date Placed']).map(b => {
    const placed = (b['Date Placed'] || '').slice(0, 10);
    const pickupDays = parseInt(b['Pickup Days']) || 14;
    const age = -daysUntil(placed);
    const overdue = age - pickupDays;
    const level = overdue > 0 ? 'action' : (overdue >= -2 ? 'warning' : 'ok');
    const biz = (b['Business'] || [])[0] || {};
    const ll = (biz.id && venueLL[biz.id]) || {};
    const companyId = venueCoMap[biz.id];
    return {
      id:    b.id,
      lat:   ll.lat,
      lng:   ll.lng,
      name:  biz.value || ll.name || 'Unknown venue',
      age, level, placed,
      nav:   companyId ? ('/company/' + companyId) : '/companies',
    };
  }).filter(x => x.lat && x.lng);

  // Recent visits layer: last 7 days of Visited stops, plotted at venue lat/lng
  const visitsLayer = stops.filter(s => {
    if (sv(s['Status']) !== 'Visited') return false;
    const d = (s['Completed At'] || s['Visit Date'] || s['Updated'] || '').slice(0, 10);
    return d && d >= sevenDaysAgo;
  }).map(s => {
    const biz = (s['Business'] || [])[0] || {};
    const ll = (s['Check-In Lat'] && s['Check-In Lng'])
      ? { lat: parseFloat(s['Check-In Lat']), lng: parseFloat(s['Check-In Lng']) }
      : (biz.id && venueLL[biz.id]) || {};
    const companyId = venueCoMap[biz.id];
    const date = (s['Completed At'] || s['Visit Date'] || s['Updated'] || '').slice(0, 10);
    return {
      id:    s.id,
      lat:   ll.lat,
      lng:   ll.lng,
      name:  s['Name'] || biz.value || 'Visit',
      date,
      nav:   companyId ? ('/company/' + companyId) : '/companies',
    };
  }).filter(x => x.lat && x.lng);

  // Overdue layer: from /api/outreach/due (already includes lat/lng)
  const overdueLayer = (Array.isArray(overdueResp) ? overdueResp : []).map(c => ({
    id:           c.id,
    lat:          c.latitude  != null ? parseFloat(c.latitude)  : null,
    lng:          c.longitude != null ? parseFloat(c.longitude) : null,
    name:         c.name || '(unnamed)',
    daysOverdue:  c.days_overdue || 0,
    nav:          '/company/' + c.id,
  })).filter(x => x.lat && x.lng);

  // Initialize map (lazy on first load) and push layer data
  hmInit();
  _hmLayerData = {
    route:   routeLayer,
    boxes:   boxesLayer,
    visits:  visitsLayer,
    overdue: overdueLayer,
  };
  // Initialize toggle state if not set yet (per-state defaults; user-saved prefs win)
  if (!_hmLayerOn) {
    const stored = _hmLoadLayerPrefs();
    _hmLayerOn = stored || Object.assign({}, HM_DEFAULTS[PAGE_STATE] || HM_DEFAULTS.A);
  }
  hmRenderChips();
  hmRefreshLayers();

  // Auto-pan in State C to the active stop (once per arrival)
  if (PAGE_STATE === 'C' && activeStop) {
    let lat = parseFloat(activeStop['Check-In Lat']);
    let lng = parseFloat(activeStop['Check-In Lng']);
    if (!lat || !lng) {
      const ll = activeVenueId ? venueLL[activeVenueId] : null;
      if (ll) { lat = ll.lat; lng = ll.lng; }
    }
    hmAutoPan(activeStop, lat, lng);
  } else {
    hmAutoPan(null);
  }

  // ── Worklist (merged: overdue boxes + overdue companies + due-soon boxes) ─
  const wlItems = [];
  const activeBoxes = boxes.filter(b => sv(b['Status']) === 'Active' && b['Date Placed']);
  activeBoxes.forEach(b => {
    const placed = (b['Date Placed'] || '').slice(0, 10);
    const pickupDays = parseInt(b['Pickup Days']) || 14;
    const age = -daysUntil(placed);
    const overdue = age - pickupDays;
    const biz = (b['Business'] || [])[0] || {};
    let priority;
    if (overdue > 0)         priority = 1000 + overdue;
    else if (overdue === 0)  priority = 800;
    else if (overdue >= -2)  priority = 700 + overdue;
    else                     priority = 100 + (-overdue);
    wlItems.push({
      kind: 'box', priority,
      name: biz.value || 'Unknown venue',
      venueId: biz.id, boxId: b.id,
      overdue, placed, pickupDays
    });
  });
  (Array.isArray(overdueResp) ? overdueResp : []).forEach(c => {
    wlItems.push({
      kind: 'company',
      priority: 900 + (c.days_overdue || 0),
      name: c.name || '(unnamed)',
      companyId: c.id,
      daysOverdue: c.days_overdue || 0
    });
  });
  wlItems.sort((a, b) => b.priority - a.priority);
  const top8 = wlItems.slice(0, 8);
  document.getElementById('wl-ct').textContent = wlItems.length ? '· ' + wlItems.length + ' items' : '';

  if (!top8.length) {
    document.getElementById('wl-body').innerHTML =
      '<div class="card" style="color:var(--text3);text-align:center;font-size:13px">All caught up ✓</div>';
  } else {
    const routeId = window._todayRouteId;
    document.getElementById('wl-body').innerHTML = top8.map((x, i) => {
      if (x.kind === 'company') {
        return '<a href="/company/' + x.companyId + '" class="card card-urgent" ' +
          'style="display:flex;align-items:center;justify-content:space-between;gap:8px;text-decoration:none;color:inherit">' +
          '<span style="font-size:14px;font-weight:600;color:var(--text);min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(x.name) + '</span>' +
          '<span class="pill pill-overdue" style="white-space:nowrap">' + x.daysOverdue + 'd overdue</span>' +
        '</a>';
      }
      let pill, accent = '';
      if (x.overdue > 0)        { pill = '<span class="pill pill-overdue">' + x.overdue + 'd overdue</span>'; accent = ' card-urgent'; }
      else if (x.overdue === 0) { pill = '<span class="pill pill-warning">due today</span>'; accent = ' card-warning'; }
      else if (x.overdue >= -2) { pill = '<span class="pill pill-warning">due in ' + (-x.overdue) + 'd</span>'; accent = ' card-warning'; }
      else                      { pill = '<span class="pill pill-success">' + (-x.overdue) + 'd left</span>'; }
      const btn = (routeId && x.venueId)
        ? '<button id="wl-add-' + i + '" onclick="addBoxToTodayRoute(' + i + ')" ' +
          'style="background:var(--primary);color:#fff;border:none;border-radius:6px;padding:8px 12px;' +
          'font-size:12px;font-weight:600;cursor:pointer;min-height:36px;white-space:nowrap">+ Add</button>'
        : '';
      const companyId = venueCoMap[x.venueId];
      const nameHtml = companyId
        ? '<a href="/company/' + companyId + '" style="font-size:14px;font-weight:600;color:var(--text);' +
          'text-decoration:none;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(x.name) + '</a>'
        : '<div style="font-size:14px;font-weight:600;color:var(--text);' +
          'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(x.name) + '</div>';
      return '<div class="card' + accent + '" style="display:flex;align-items:center;justify-content:space-between;gap:12px">' +
        '<div style="flex:1;min-width:0">' + nameHtml +
          '<div style="margin-top:6px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">' + pill +
          '<span style="font-size:11px;color:var(--text3)">placed ' + esc(fmt(x.placed)) + '</span></div>' +
        '</div>' + btn + '</div>';
    }).join('');
  }
  window._boxRows = top8.map(x => x.kind === 'box' ? x : null);

  // ── Yesterday recap ──────────────────────────────────────────────────
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  const yStops = stops.filter(s => {
    const d = (s['Completed At'] || s['Visit Date'] || s['Updated'] || '').slice(0, 10);
    return d === yesterday && sv(s['Status']) === 'Visited';
  }).length;
  const yLeads = leads.filter(l => {
    const d = (l['Created'] || l['Date'] || '').slice(0, 10);
    const owner = (l['Owner'] || '').toLowerCase();
    return d === yesterday && (!owner || owner === USER_EMAIL);
  }).length;
  const recap = document.getElementById('recap-slot');
  if (yStops || yLeads) {
    recap.innerHTML =
      '<a href="/todo" class="recap-card">Yesterday: ' +
        yStops + ' visit'  + (yStops === 1 ? '' : 's') + ', ' +
        yLeads + ' lead'   + (yLeads === 1 ? '' : 's') + ' logged' +
      '</a>';
  } else {
    recap.innerHTML = '';
  }
}

function computeElapsedMin(arrivedAt) {
  if (!arrivedAt) return 0;
  const t = Date.parse(arrivedAt.replace(' ', 'T'));
  if (isNaN(t)) return 0;
  return Math.max(0, Math.round((Date.now() - t) / 60000));
}

// ── Quick-log dispatcher ────────────────────────────────────────────────
function quickLog(kind) {
  const state = window._pageState || 'A';
  if (kind === 'lead') {
    // TODO: support /lead?new=1&company_id= prefill once lead.py reads the params
    window.location.href = '/lead';
    return;
  }
  if (kind === 'visit') {
    if (state === 'C') {
      markStop('Visited');
    } else if (state === 'B') {
      window.location.href = '/route';
    } else {
      // State A: a drop-by visit goes straight to Business Outreach Log.
      // Events are their own button.
      if (typeof openGFRForm === 'function') openGFRForm('Business Outreach Log');
      else window.location.href = '/companies';
    }
    return;
  }
  if (kind === 'event') {
    // The chooser surfaces External Event / Lunch and Learn / Mobile Massage
    // Service / Health Assessment Screening (and Business Outreach Log).
    if (typeof openGFRChooser === 'function') openGFRChooser();
    else window.location.href = '/companies';
    return;
  }
}

// ── PATCH current stop status (Visited / Skipped) ──────────────────────
async function markStop(status) {
  const stop = window._activeStop;
  if (!stop) { alert('No active stop'); return; }
  try {
    const r = await fetch('/api/guerilla/routes/stops/' + stop.id, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ status })
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      alert('Could not update stop: ' + (err.error || ('HTTP ' + r.status)));
      return;
    }
    await loadHomeDashboard();
  } catch (e) {
    alert('Network error — try again');
  }
}

function goStopNotes() {
  // Notes have a full editor on /route. Punt there.
  window.location.href = '/route';
}

// ── Add a box-pickup stop to today's route (worklist row's "+ Add") ─────
async function addBoxToTodayRoute(idx) {
  const x = (window._boxRows || [])[idx];
  const routeId = window._todayRouteId;
  if (!x || !routeId || !x.venueId) return;
  const btn = document.getElementById('wl-add-' + idx);
  if (btn) { btn.disabled = true; btn.textContent = '…'; }
  try {
    const r = await fetch('/api/guerilla/routes/' + routeId + '/stops', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ venue_id: x.venueId, name: 'Box pickup: ' + x.name })
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      if (btn) { btn.disabled = false; btn.textContent = '+ Add'; }
      alert('Could not add: ' + (err.error || r.status));
      return;
    }
    if (btn) { btn.style.background = '#059669'; btn.textContent = '✓'; }
  } catch (e) {
    if (btn) { btn.disabled = false; btn.textContent = '+ Add'; }
    alert('Network error — try again');
  }
}

// ── Live elapsed-time tick for the State C hero ────────────────────────
setInterval(() => {
  const stop = window._activeStop;
  const el = document.getElementById('hero-elapsed');
  if (!stop || !el) return;
  el.textContent = computeElapsedMin(stop['Arrived At'] || '') + 'm';
}, 30000);

// ── Initial load + freshness loop ──────────────────────────────────────
function _scheduleNextHomeLoad() {
  setTimeout(() => {
    loadHomeDashboard().then(_scheduleNextHomeLoad).catch(() => _scheduleNextHomeLoad());
  }, 30000);
}
loadHomeDashboard()
  .then(_scheduleNextHomeLoad)
  .catch(err => { console.error('Dashboard load failed:', err); _scheduleNextHomeLoad(); });

document.addEventListener('visibilitychange', () => {
  if (!document.hidden) loadHomeDashboard();
});
"""

    script_js = js_head + js_body
    return _mobile_page('m_home', 'Home', body, script_js, br, bt, user=user,
                         extra_html=GFR_EXTRA_HTML, extra_js=GFR_EXTRA_JS)




def _mobile_routes_dashboard_page(br: str, bt: str, user: dict = None) -> str:
    user = user or {}
    user_email = (user.get('email', '') or '').strip().lower()
    body = (
        '<div class="mobile-hdr">'
        '<div><div class="mobile-hdr-title">My Routes</div>'
        '<div class="mobile-hdr-sub">All your assigned routes</div></div>'
        '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        '</div>'
        '<div class="mobile-body">'
        # Today's route CTA
        '<a href="/route" id="today-cta" class="mobile-cta mobile-cta-orange" style="margin-bottom:16px;display:none">'
        '<span class="mobile-cta-icon">\U0001f5fa️</span>'
        '<div><div id="today-cta-title">Start Today\'s Route</div>'
        '<div class="mobile-cta-sub" id="today-cta-sub">Loading…</div></div>'
        '</a>'
        # Stat cards
        '<div id="m-stats" style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:16px">'
        '<div class="loading">Loading…</div></div>'
        # Route list
        '<div id="m-route-list"><div class="loading">Loading…</div></div>'
        # Past routes toggle
        '<div id="m-past-wrapper" style="display:none">'
        '<button id="m-past-toggle" onclick="togglePast()" '
        'style="width:100%;padding:10px;border:1px solid var(--border);background:var(--card);'
        'color:var(--text2);border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;margin-bottom:12px">'
        '▶ Show past routes</button>'
        '<div id="m-past-routes" style="display:none"></div>'
        '</div>'
        '</div>'
    )
    js = f"""
var USER_EMAIL = {user_email!r};

async function load() {{
  var [routes, stops, venues, companies] = await Promise.all([
    fetchAll({T_GOR_ROUTES}),
    fetchAll({T_GOR_ROUTE_STOPS}),
    fetchAll({T_GOR_VENUES}),
    fetchAll({T_COMPANIES})
  ]);
  // Filter to user's routes
  routes = routes.filter(function(r) {{
    return (r['Assigned To']||'').trim().toLowerCase() === USER_EMAIL;
  }});
  // Build venue lookup
  var venueMap = {{}};
  venues.forEach(function(v) {{ venueMap[v.id] = v; }});
  var venueCoMap = buildVenueCompanyMap(companies);

  // Today's route CTA
  var today = new Date().toISOString().split('T')[0];
  var todayRoute = routes.find(function(r) {{
    var s = sv(r['Status']) || 'Draft';
    return r['Date'] === today && (s === 'Active' || s === 'Draft');
  }});
  var cta = document.getElementById('today-cta');
  if (todayRoute) {{
    var tStops = stops.filter(function(s) {{
      var rl = s['Route']; return Array.isArray(rl) && rl.some(function(x){{return x.id===todayRoute.id;}});
    }});
    document.getElementById('today-cta-title').textContent = todayRoute['Name'] || "Today's Route";
    document.getElementById('today-cta-sub').textContent = tStops.length + ' stops assigned';
    cta.style.display = 'flex';
  }} else {{
    document.getElementById('today-cta-title').textContent = 'No route today';
    document.getElementById('today-cta-sub').textContent = 'Check back when one is assigned';
    cta.style.display = 'flex';
    cta.style.opacity = '0.5';
    cta.onclick = function(e) {{ e.preventDefault(); }};
  }}

  // Compute stats
  var totalStops = 0, visited = 0, skipped = 0, missed = 0, pending = 0;
  routes.forEach(function(r) {{
    var rid = r.id;
    stops.filter(function(s) {{
      var rl = s['Route']; return Array.isArray(rl) && rl.some(function(x){{return x.id===rid;}});
    }}).forEach(function(s) {{
      totalStops++;
      var ss = sv(s['Status']) || 'Pending';
      if (ss==='Visited') visited++;
      else if (ss==='Skipped') skipped++;
      else if (ss==='Not Reached') missed++;
      else pending++;
    }});
  }});
  var pct = totalStops ? Math.round(visited/totalStops*100) : 0;
  var missedTotal = skipped + missed;
  var pctColor = pct >= 80 ? '#059669' : pct >= 50 ? '#d97706' : '#ef4444';

  document.getElementById('m-stats').innerHTML =
    '<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center">'
    + '<div style="font-size:22px;font-weight:800;color:#004ac6">' + routes.length + '</div>'
    + '<div style="font-size:10px;color:var(--text3);text-transform:uppercase">Routes</div></div>'
    + '<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center">'
    + '<div style="font-size:22px;font-weight:800;color:#059669">' + visited + '<span style="font-size:12px;color:var(--text3)">/' + totalStops + '</span></div>'
    + '<div style="font-size:10px;color:var(--text3);text-transform:uppercase">Visited</div></div>'
    + '<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center">'
    + '<div style="font-size:22px;font-weight:800;color:' + pctColor + '">' + pct + '%</div>'
    + '<div style="font-size:10px;color:var(--text3);text-transform:uppercase">Complete</div></div>'
    + '<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center">'
    + '<div style="font-size:22px;font-weight:800;color:' + (missedTotal > 0 ? '#ef4444' : '#059669') + '">' + missedTotal + '</div>'
    + '<div style="font-size:10px;color:var(--text3);text-transform:uppercase">Missed</div></div>';

  // Split into upcoming vs past
  var upcoming = routes.filter(function(r) {{
    var d = r['Date'] || '';
    var st = sv(r['Status']) || 'Draft';
    return d >= today || st === 'Active' || st === 'Draft';
  }}).sort(function(a,b) {{ return (a['Date']||'').localeCompare(b['Date']||''); }});
  var past = routes.filter(function(r) {{
    var d = r['Date'] || '';
    var st = sv(r['Status']) || 'Draft';
    return d < today && st !== 'Active' && st !== 'Draft';
  }}).sort(function(a,b) {{ return (b['Date']||'').localeCompare(a['Date']||''); }});

  function renderCard(row) {{
    var rid = row.id;
    var status = sv(row['Status']) || 'Draft';
    var sc = status==='Active'?'#059669':status==='Completed'?'#2563eb':'#475569';
    var myStops = stops.filter(function(s) {{
      var rl = s['Route']; return Array.isArray(rl) && rl.some(function(x){{return x.id===rid;}});
    }}).sort(function(a,b) {{ return (a['Stop Order']||0)-(b['Stop Order']||0); }});
    var v=0,sk=0,nr=0,p=0;
    myStops.forEach(function(s) {{
      var ss = sv(s['Status'])||'Pending';
      if(ss==='Visited')v++; else if(ss==='Skipped')sk++; else if(ss==='Not Reached')nr++; else p++;
    }});
    var total = myStops.length;
    var rpct = total ? Math.round(v/total*100) : 0;

    var h = '<a href="/routes/'+rid+'" style="display:block;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:10px;text-decoration:none;color:inherit">';
    h += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">';
    h += '<div style="font-size:14px;font-weight:700">'+esc(row['Name']||'(unnamed)')+'</div>';
    h += '<span style="font-size:10px;background:'+sc+'20;color:'+sc+';border-radius:4px;padding:2px 7px;font-weight:600">'+esc(status)+'</span>';
    h += '</div>';
    h += '<div style="font-size:11px;color:var(--text3);margin-bottom:8px">'+fmt(row['Date']||'')+' • '+total+' stops</div>';
    // Stats
    h += '<div style="display:flex;gap:10px;font-size:11px;font-weight:600;margin-bottom:6px">';
    if(v) h += '<span style="color:#059669">'+v+' visited</span>';
    if(sk) h += '<span style="color:#f97316">'+sk+' skipped</span>';
    if(nr) h += '<span style="color:#ef4444">'+nr+' missed</span>';
    if(p) h += '<span style="color:#94a3b8">'+p+' pending</span>';
    h += '</div>';
    // Progress bar
    if(total) {{
      h += '<div style="height:4px;background:var(--border);border-radius:2px;overflow:hidden">';
      h += '<div style="height:100%;width:'+rpct+'%;background:#059669;border-radius:2px"></div></div>';
    }}
    h += '</a>';
    return h;
  }}

  // Render
  if (!upcoming.length && !past.length) {{
    document.getElementById('m-route-list').innerHTML = '<div style="text-align:center;padding:30px 0;color:var(--text3);font-size:13px">No routes assigned yet.</div>';
  }} else {{
    document.getElementById('m-route-list').innerHTML = upcoming.length
      ? upcoming.map(renderCard).join('')
      : '<div style="text-align:center;padding:20px 0;color:var(--text3);font-size:13px">No upcoming routes.</div>';
    if (past.length) {{
      document.getElementById('m-past-wrapper').style.display = 'block';
      document.getElementById('m-past-routes').innerHTML = past.map(renderCard).join('');
    }}
  }}
  stampRefresh();
}}

function togglePast() {{
  var el = document.getElementById('m-past-routes');
  var btn = document.getElementById('m-past-toggle');
  if (el.style.display === 'none') {{
    el.style.display = 'block';
    btn.innerHTML = '▼ Hide past routes';
  }} else {{
    el.style.display = 'none';
    btn.innerHTML = '▶ Show past routes';
  }}
}}

load();
"""
    return _mobile_page('m_routes', 'My Routes', body, js, br, bt, user=user)
