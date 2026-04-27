"""Company detail page + directory list."""

import os

from hub.shared import (
    _mobile_page,
    T_COMPANIES, T_LEADS, T_ACTIVITIES, T_GOR_BOXES,
)
from hub.guerilla import GFR_EXTRA_HTML, GFR_EXTRA_JS
from hub.lead_capture_ui import LEAD_CAPTURE_HTML, build_lead_capture_js


def _mobile_company_detail_page(br: str, bt: str, company_id: int,
                                 user: dict = None) -> str:
    """Mobile-sized view of a single Company row. Tabs: Info / Leads /
    Events / Boxes (Boxes only when category='guerilla' and the Company has
    a linked venue). Info tab carries a ~180px mini-map pinned on the
    business, a Google-rating row, the meta card, visit history, and the
    existing 'Log activity' flow."""
    user = user or {}
    user_name = user.get('name', '')
    gk = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    body = (
        # Header
        '<div class="mobile-hdr">'
        '<button class="m-hamburger" onclick="goBack()" aria-label="Back" '
        'style="margin-right:10px">←</button>'
        '<div style="flex:1;min-width:0"><div class="mobile-hdr-title" id="cd-name">Loading…</div>'
        '<div class="mobile-hdr-sub" id="cd-sub"></div></div>'
        '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        '</div>'
        '<div class="mobile-body">'
        # Stats strip
        '<div class="stats-row" id="cd-stats" style="margin-bottom:12px"></div>'
        # Tab bar
        '<div class="m-tabs" id="cd-tabs" style="margin-bottom:14px"></div>'
        # Info panel
        '<div class="m-panel active" id="cd-panel-info">'
        '<div id="cd-map-wrap" style="display:none;margin-bottom:14px">'
        '<div id="cd-map" style="height:180px;border-radius:10px;overflow:hidden;border:1px solid var(--border)"></div>'
        '</div>'
        '<div id="cd-rating" style="display:none;margin-bottom:10px"></div>'
        '<div id="cd-meta" style="margin-bottom:16px"></div>'
        '<div class="mobile-section-lbl" style="margin-bottom:8px">Visit History</div>'
        '<div id="cd-visits" style="margin-bottom:16px"><div class="loading">Loading…</div></div>'
        '<button onclick="openLogModal()" '
        'style="width:100%;padding:12px;background:#ea580c;color:#fff;border:none;border-radius:10px;'
        'font-size:14px;font-weight:700;cursor:pointer;font-family:inherit">'
        '+ Log activity</button>'
        '</div>'
        # Leads panel
        '<div class="m-panel" id="cd-panel-leads">'
        '<button id="cd-leads-capture-btn" onclick="openLeadCaptureForCompany()" '
        'style="width:100%;padding:12px;background:#ea580c;color:#fff;border:none;border-radius:10px;'
        'font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;margin-bottom:12px">'
        '+ Capture Lead</button>'
        '<div id="cd-leads"><div class="loading">Loading…</div></div>'
        '</div>'
        # Events panel
        '<div class="m-panel" id="cd-panel-events">'
        '<div class="mobile-section-lbl" style="margin-bottom:8px">Schedule Event</div>'
        '<div style="display:grid;gap:8px;margin-bottom:14px">'
        '<button onclick="scheduleCompanyEvent(\'Mobile Massage Service\')" '
        'style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:12px 16px;font-size:14px;font-weight:600;cursor:pointer;'
        'min-height:48px;text-align:left;font-family:inherit">\U0001f486 Mobile Massage</button>'
        '<button onclick="scheduleCompanyEvent(\'Lunch and Learn\')" '
        'style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:12px 16px;font-size:14px;font-weight:600;cursor:pointer;'
        'min-height:48px;text-align:left;font-family:inherit">\U0001f37d️ Lunch & Learn</button>'
        '<button onclick="scheduleCompanyEvent(\'Health Assessment Screening\')" '
        'style="width:100%;background:var(--card);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:12px 16px;font-size:14px;font-weight:600;cursor:pointer;'
        'min-height:48px;text-align:left;font-family:inherit">\U0001fa7a Health Assessment</button>'
        '</div>'
        '<div class="mobile-section-lbl" style="margin-bottom:8px">Event History</div>'
        '<div id="cd-events"><div class="loading">Loading…</div></div>'
        '</div>'
        # Boxes panel (rendered only for guerilla-linked companies; tab button
        # is also conditional)
        '<div class="m-panel" id="cd-panel-boxes">'
        '<div id="cd-boxes"><div class="loading">Loading…</div></div>'
        '<div id="cd-box-form"></div>'
        '</div>'
        '</div>'  # end mobile-body
        # Log-activity modal (unchanged from previous flat page)
        '<div id="cd-modal-bg" onclick="if(event.target===this)closeLogModal()" '
        'style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:900;'
        'align-items:flex-start;justify-content:center;padding:40px 16px;overflow-y:auto">'
        '<div style="background:var(--bg2);border:1px solid var(--border);border-radius:14px;'
        'width:100%;max-width:480px;padding:20px">'
        '<h3 style="margin:0 0 14px;color:var(--text);font-size:16px">Log activity</h3>'
        '<label style="display:block;font-size:11px;font-weight:700;color:var(--text3);'
        'text-transform:uppercase;margin-bottom:4px;letter-spacing:.4px">Type</label>'
        '<select id="cd-type" style="width:100%;padding:9px;background:var(--bg);border:1px solid var(--border);'
        'color:var(--text);border-radius:6px;font-size:13px;margin-bottom:12px">'
        '<option value="Call">\U0001f4de Call</option>'
        '<option value="Email">✉️ Email</option>'
        '<option value="Drop Off">\U0001f4cd Drop-off</option>'
        '<option value="Text">\U0001f4ac Text</option>'
        '<option value="In Person">\U0001f91d In Person</option>'
        '<option value="Other">Other</option>'
        '</select>'
        '<label style="display:block;font-size:11px;font-weight:700;color:var(--text3);'
        'text-transform:uppercase;margin-bottom:4px;letter-spacing:.4px">Notes *</label>'
        '<textarea id="cd-summary" rows="3" placeholder="What happened?" '
        'style="width:100%;padding:9px;background:var(--bg);border:1px solid var(--border);'
        'color:var(--text);border-radius:6px;font-size:13px;resize:vertical;font-family:inherit;margin-bottom:12px"></textarea>'
        # Sentiment row (Green/Yellow/Red)
        '<label style="display:block;font-size:11px;font-weight:700;color:var(--text3);'
        'text-transform:uppercase;margin-bottom:4px;letter-spacing:.4px">How did it go?</label>'
        '<div id="cd-sentiment-row" style="display:flex;gap:6px;margin-bottom:12px">'
        '<button type="button" data-sent="Green"  onclick="setSentiment(\'Green\')"  '
        'style="flex:1;padding:8px;background:var(--bg);border:1px solid var(--border);'
        'color:var(--text);border-radius:6px;font-size:13px;cursor:pointer;font-family:inherit">🟢 Good</button>'
        '<button type="button" data-sent="Yellow" onclick="setSentiment(\'Yellow\')" '
        'style="flex:1;padding:8px;background:var(--bg);border:1px solid var(--border);'
        'color:var(--text);border-radius:6px;font-size:13px;cursor:pointer;font-family:inherit">🟡 Mixed</button>'
        '<button type="button" data-sent="Red"    onclick="setSentiment(\'Red\')"    '
        'style="flex:1;padding:8px;background:var(--bg);border:1px solid var(--border);'
        'color:var(--text);border-radius:6px;font-size:13px;cursor:pointer;font-family:inherit">🔴 Bad</button>'
        '</div>'
        # Photo capture
        '<label style="display:block;font-size:11px;font-weight:700;color:var(--text3);'
        'text-transform:uppercase;margin-bottom:4px;letter-spacing:.4px">Photo (optional)</label>'
        '<div id="cd-photo-row" style="margin-bottom:12px">'
        '<label for="cd-photo-input" id="cd-photo-pick" '
        'style="display:inline-flex;align-items:center;gap:6px;padding:8px 12px;background:var(--bg);'
        'border:1px solid var(--border);color:var(--text2);border-radius:6px;font-size:13px;cursor:pointer">'
        '📷 Add photo</label>'
        '<input type="file" id="cd-photo-input" accept="image/*" capture="environment" '
        'onchange="onPhotoPicked(event)" style="display:none">'
        '<div id="cd-photo-preview" style="display:none;margin-top:8px;position:relative">'
        '<img id="cd-photo-img" style="max-width:100%;max-height:160px;border-radius:6px;border:1px solid var(--border)">'
        '<button type="button" onclick="clearPhoto()" '
        'style="position:absolute;top:4px;right:4px;background:rgba(0,0,0,.6);color:#fff;border:none;'
        'border-radius:50%;width:24px;height:24px;font-size:14px;cursor:pointer;line-height:1">×</button>'
        '</div>'
        '</div>'
        '<label style="display:block;font-size:11px;font-weight:700;color:var(--text3);'
        'text-transform:uppercase;margin-bottom:4px;letter-spacing:.4px">Next follow-up</label>'
        '<input type="date" id="cd-fu" '
        'style="width:100%;padding:9px;background:var(--bg);border:1px solid var(--border);'
        'color:var(--text);border-radius:6px;font-size:13px;margin-bottom:12px;font-family:inherit">'
        '<label style="display:block;font-size:11px;font-weight:700;color:var(--text3);'
        'text-transform:uppercase;margin-bottom:4px;letter-spacing:.4px">New status (optional)</label>'
        '<select id="cd-status" style="width:100%;padding:9px;background:var(--bg);border:1px solid var(--border);'
        'color:var(--text);border-radius:6px;font-size:13px;margin-bottom:14px">'
        '<option value="">(keep current)</option>'
        '<option value="Not Contacted">Not Contacted</option>'
        '<option value="Contacted">Contacted</option>'
        '<option value="In Discussion">In Discussion</option>'
        '<option value="Active Partner">Active Partner</option>'
        '</select>'
        '<div id="cd-modal-msg" style="font-size:12px;min-height:14px;margin-bottom:8px"></div>'
        '<div style="display:flex;gap:8px;justify-content:flex-end">'
        '<button onclick="closeLogModal()" '
        'style="padding:9px 16px;background:none;border:1px solid var(--border);color:var(--text2);'
        'border-radius:6px;font-size:13px;cursor:pointer;font-family:inherit">Cancel</button>'
        '<button id="cd-modal-send" onclick="submitLog()" '
        'style="padding:9px 20px;background:#059669;border:none;color:#fff;border-radius:6px;'
        'font-size:13px;font-weight:700;cursor:pointer;font-family:inherit">Save</button>'
        '</div>'
        '</div>'
        '</div>'
    )
    js = f"""
const COMPANY_ID = {int(company_id)};
const CGK = {repr(gk)};
const T_LEADS_TID = {int(T_LEADS)};
const T_GOR_BOXES_TID = {int(T_GOR_BOXES)};

let _COMPANY = null;
let _ACTS = [];
let _LEADS_ALL = [];
let _BOXES_ALL = [];
let _cMap = null;
let _cMarker = null;

var CAT_META = {{
  attorney:  {{label: 'Attorney',  color: '#7c3aed'}},
  guerilla:  {{label: 'Guerilla',  color: '#ea580c'}},
  community: {{label: 'Community', color: '#059669'}},
  other:     {{label: 'Other',     color: '#64748b'}},
}};

function esc(s) {{
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}}

function svJS(v) {{
  if (!v) return '';
  if (typeof v === 'object' && !Array.isArray(v)) return v.value || '';
  if (Array.isArray(v) && v.length) return (v[0] && v[0].value) || (v[0] && v[0].name) || String(v[0]);
  return String(v);
}}

function fmtDate(s) {{
  if (!s) return '—';
  s = String(s).slice(0, 10);
  var parts = s.split('-');
  if (parts.length !== 3) return s;
  return parts[1] + '/' + parts[2] + '/' + parts[0].slice(2);
}}

function goBack() {{
  if (document.referrer && document.referrer.indexOf(location.origin) === 0) {{
    history.back();
  }} else {{
    location.href = '/';
  }}
}}

// Minimal fetchAll — companies/activities come from dedicated endpoints,
// leads & boxes are pulled once from the generic table endpoint.
async function fetchAllTid(tid) {{
  try {{
    var r = await fetch('/api/data/' + tid);
    if (!r.ok) return [];
    return await r.json();
  }} catch (e) {{ return []; }}
}}

// ── Tab switching ────────────────────────────────────────────────────────
function cTab(el, panelId) {{
  document.querySelectorAll('#cd-tabs .m-tab').forEach(function(t) {{ t.classList.remove('active'); }});
  document.querySelectorAll('.m-panel').forEach(function(p) {{ p.classList.remove('active'); }});
  el.classList.add('active');
  var panel = document.getElementById(panelId);
  if (panel) panel.classList.add('active');
  // Re-trigger a resize when the Info tab becomes visible so the map
  // re-lays-out if it was hidden at init time.
  if (panelId === 'cd-panel-info' && _cMap && window.google && window.google.maps) {{
    setTimeout(function() {{ google.maps.event.trigger(_cMap, 'resize'); }}, 80);
  }}
}}

function _catInfo(c) {{
  var cat = (svJS(c.Category) || 'other').toLowerCase();
  return CAT_META[cat] || CAT_META.other;
}}

function _isGuerillaWithVenue(c) {{
  var cat = (svJS(c.Category) || '').toLowerCase();
  var src = svJS(c['Legacy Source']);
  return cat === 'guerilla' && src === 'guerilla_venue' && !!c['Legacy ID'];
}}

// ── Render: header + sub ─────────────────────────────────────────────────
function renderHeader() {{
  var c = _COMPANY;
  var name = c.Name || '(unnamed)';
  var meta = _catInfo(c);
  document.title = name + ' — Reform';
  document.getElementById('cd-name').textContent = name;
  document.getElementById('cd-sub').innerHTML =
    '<span style="background:' + meta.color + '22;color:' + meta.color + ';font-size:10px;font-weight:600;padding:2px 8px;border-radius:10px">' +
    esc(meta.label) + '</span>' +
    (svJS(c['Contact Status']) ? '<span style="font-size:11px;color:var(--text3);margin-left:8px">' + esc(svJS(c['Contact Status'])) + '</span>' : '');
}}

// ── Render: tab bar (Boxes is conditional) ───────────────────────────────
function renderTabs() {{
  var c = _COMPANY;
  var showBoxes = _isGuerillaWithVenue(c);
  var html = '';
  html += '<div class="m-tab active" onclick="cTab(this,\\'cd-panel-info\\')">Info</div>';
  html += '<div class="m-tab" onclick="cTab(this,\\'cd-panel-leads\\')">Leads</div>';
  html += '<div class="m-tab" onclick="cTab(this,\\'cd-panel-events\\')">Events</div>';
  if (showBoxes) {{
    html += '<div class="m-tab" onclick="cTab(this,\\'cd-panel-boxes\\')">Boxes</div>';
  }}
  document.getElementById('cd-tabs').innerHTML = html;
}}

// ── Render: stats strip ──────────────────────────────────────────────────
function renderStats() {{
  var c = _COMPANY;
  var nameKey = (c.Name || '').trim().toLowerCase();
  var legacyId = c['Legacy ID'];
  var leadsCt = _LEADS_ALL.filter(function(L) {{
    var src = (L.Source || '').trim().toLowerCase();
    return src && src === nameKey;
  }}).length;
  var eventsCt = (_ACTS || []).filter(function(a) {{ return !!svJS(a['Event Status']); }}).length;
  var boxesCt = 0;
  if (legacyId) {{
    boxesCt = _BOXES_ALL.filter(function(b) {{
      var lf = b.Business;
      return Array.isArray(lf) && lf.some(function(r) {{ return r && r.id === legacyId; }});
    }}).length;
  }}
  var last = '';
  (_ACTS || []).forEach(function(a) {{
    var d = a.Created || a.Date || '';
    if (d && d > last) last = d;
  }});
  var lastChip = '—';
  if (last) {{
    var dt = new Date(last);
    if (!isNaN(dt.getTime())) {{
      var days = Math.floor((new Date() - dt) / 86400000);
      lastChip = days <= 0 ? 'Today' : (days === 1 ? '1d ago' : (days + 'd ago'));
    }}
  }}
  function chip(cls, label, value, muted) {{
    var extra = muted ? ' style="opacity:.55"' : '';
    return '<div class="stat-chip ' + cls + '"' + extra + '>' +
             '<div class="label">' + esc(label) + '</div>' +
             '<div class="value">' + esc(String(value)) + '</div>' +
           '</div>';
  }}
  var html = '';
  html += chip('c-blue', 'Leads', leadsCt, leadsCt === 0);
  html += chip('c-yellow', 'Events', eventsCt, eventsCt === 0);
  if (_isGuerillaWithVenue(c)) {{
    html += chip('c-green', 'Boxes', boxesCt, boxesCt === 0);
  }}
  html += chip('c-blue', 'Last Visit', lastChip, lastChip === '—');
  document.getElementById('cd-stats').innerHTML = html;
}}

// ── Info tab: map + rating + meta + visit history ────────────────────────
function _initCompanyMap(lat, lng) {{
  if (!CGK) return;
  var color = _catInfo(_COMPANY).color;
  function ready() {{
    var el = document.getElementById('cd-map');
    if (!el) return;
    // Seed an explicit height before constructing the Map, or the div
    // collapses to 0 and Google's tiles never render. Same trick route.py
    // uses at line 145.
    el.style.height = el.offsetHeight + 'px';
    _cMap = new google.maps.Map(el, {{
      center: {{lat: lat, lng: lng}}, zoom: 16,
      mapTypeControl: false, streetViewControl: false,
      styles: [{{featureType:'poi',stylers:[{{visibility:'off'}}]}},
               {{featureType:'transit',stylers:[{{visibility:'off'}}]}}]
    }});
    _cMarker = new google.maps.Marker({{
      position: {{lat: lat, lng: lng}}, map: _cMap,
      icon: {{path: google.maps.SymbolPath.CIRCLE, scale: 10, fillColor: color,
              fillOpacity: 1, strokeColor: '#fff', strokeWeight: 2}},
      title: _COMPANY.Name || ''
    }});
  }}
  if (window.google && window.google.maps) {{
    ready();
  }} else {{
    window._cMapReady = ready;
    var s = document.createElement('script');
    s.src = 'https://maps.googleapis.com/maps/api/js?key=' + CGK + '&callback=_cMapReady';
    s.async = true; document.head.appendChild(s);
  }}
}}

function renderInfoTab() {{
  var c = _COMPANY;
  // Map — only if lat+lng on the Company row resolve to numbers
  var lat = parseFloat(c.Latitude);
  var lng = parseFloat(c.Longitude);
  var mapWrap = document.getElementById('cd-map-wrap');
  if (!isNaN(lat) && !isNaN(lng)) {{
    mapWrap.style.display = 'block';
    _initCompanyMap(lat, lng);
  }} else {{
    mapWrap.style.display = 'none';
  }}
  // Rating row
  var rating = c.Rating;
  var reviews = c.Reviews;
  var gmUrl = c['Google Maps URL'] || '';
  var rEl = document.getElementById('cd-rating');
  if (rating) {{
    var rh = '<div style="padding:10px 12px;background:var(--card);border:1px solid var(--border);border-radius:10px;display:flex;align-items:center;gap:8px">' +
             '<span style="font-size:15px">⭐</span>' +
             '<span style="font-size:14px;font-weight:700">' + esc(rating) + '</span>';
    if (reviews) rh += '<span style="font-size:12px;color:var(--text3)">(' + esc(reviews) + ' reviews)</span>';
    if (gmUrl) rh += '<a href="' + esc(gmUrl) + '" target="_blank" style="margin-left:auto;color:#3b82f6;font-size:12px;text-decoration:none">View on Google ↗</a>';
    rh += '</div>';
    rEl.style.display = 'block';
    rEl.innerHTML = rh;
  }} else {{
    rEl.style.display = 'none';
  }}
  // Meta card (preserved from prior layout)
  var phone = c.Phone || '';
  var email = c.Email || '';
  var addr  = c.Address || '';
  var site  = c.Website || '';
  var fu    = c['Follow-Up Date'] || '';
  var notes = c.Notes || '';
  var legacySrc = svJS(c['Legacy Source']);
  var legacyId  = c['Legacy ID'];
  var navUrl, navTarget;
  if (legacySrc === 'guerilla_venue' && legacyId) {{
    navUrl = '/map?venue=' + encodeURIComponent(legacyId);
    navTarget = '_self';
  }} else {{
    navUrl = addr ? 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(addr) : '';
    navTarget = '_blank';
  }}
  var html = '<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px">';
  if (phone) html += '<div style="padding:6px 0;border-bottom:1px solid var(--border)"><a href="tel:' + esc(phone) + '" style="color:#3b82f6;text-decoration:none;font-size:14px;font-weight:600">\U0001f4de ' + esc(phone) + '</a></div>';
  if (email) html += '<div style="padding:6px 0;border-bottom:1px solid var(--border)"><a href="mailto:' + esc(email) + '" style="color:#3b82f6;text-decoration:none;font-size:14px;font-weight:600">✉️ ' + esc(email) + '</a></div>';
  if (addr)  html += '<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:13px;color:var(--text2)">\U0001f4cd ' + esc(addr) + (navUrl ? ' <a href="' + esc(navUrl) + '" target="' + navTarget + '" style="color:#3b82f6;font-size:12px;margin-left:6px">Navigate →</a>' : '') + '</div>';
  if (site)  html += '<div style="padding:6px 0;border-bottom:1px solid var(--border)"><a href="' + esc(site) + '" target="_blank" style="color:#3b82f6;text-decoration:none;font-size:13px">\U0001f310 ' + esc(site) + '</a></div>';
  if (fu)    html += '<div style="padding:6px 0;font-size:13px;color:var(--text2)">\U0001f4c5 Next follow-up: <strong>' + esc(fmtDate(fu)) + '</strong></div>';
  if (notes) html += '<div style="padding:10px 0 0;margin-top:8px;border-top:1px solid var(--border);font-size:12px;color:var(--text3);white-space:pre-wrap">' + esc(notes) + '</div>';
  html += '</div>';
  document.getElementById('cd-meta').innerHTML = html;
  // Visit history (top 10 from the /activities endpoint response)
  var visits = (_ACTS || []).slice(0, 10);
  var vEl = document.getElementById('cd-visits');
  if (!visits.length) {{
    vEl.innerHTML = '<div style="color:var(--text3);font-size:13px;padding:8px 0;text-align:center">No visits logged yet.</div>';
  }} else {{
    var SENT_COLORS_J = {{ Green: '#059669', Yellow: '#f59e0b', Red: '#ef4444' }};
    var vh = '';
    visits.forEach(function(a) {{
      var type  = svJS(a.Type) || '';
      var summ  = a.Summary || '';
      var when  = a.Created || a.Date || '';
      var who   = a.Author || '';
      var sent  = svJS(a.Sentiment) || '';
      var photo = (a['Photo URL'] || '').trim();
      vh += '<div style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px 12px;margin-bottom:6px">';
      vh += '<div style="display:flex;gap:8px;align-items:center;margin-bottom:4px">';
      if (sent && SENT_COLORS_J[sent]) {{
        vh += '<span title="' + esc(sent) + '" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:' + SENT_COLORS_J[sent] + ';flex-shrink:0"></span>';
      }}
      if (type) vh += '<span style="background:#47556920;color:#475569;font-size:10px;font-weight:600;padding:2px 7px;border-radius:6px">' + esc(type) + '</span>';
      vh += '<span style="font-size:10px;color:var(--text3)">' + esc(fmtDate(when)) + (who ? ' · ' + esc(who.split('@')[0]) : '') + '</span>';
      vh += '</div>';
      if (summ) vh += '<div style="font-size:13px;color:var(--text2);white-space:pre-wrap">' + esc(summ) + '</div>';
      if (photo) {{
        vh += '<div style="margin-top:6px"><img src="' + esc(photo) + '" onclick="openPhotoLightbox(\\'' + esc(photo) + '\\')" '
            + 'style="max-width:120px;max-height:90px;border-radius:6px;border:1px solid var(--border);cursor:pointer;object-fit:cover"></div>';
      }}
      vh += '</div>';
    }});
    vEl.innerHTML = vh;
  }}
}}

// ── Leads tab ────────────────────────────────────────────────────────────
function openLeadCaptureForCompany() {{
  var name = (_COMPANY && _COMPANY.Name) || '';
  openLeadCapture(name);  // from lead_capture_ui.py (injected via extra_js)
}}

function renderLeadsTab() {{
  var c = _COMPANY;
  var nameKey = (c.Name || '').trim().toLowerCase();
  var leads = _LEADS_ALL.filter(function(L) {{
    var src = (L.Source || '').trim().toLowerCase();
    return src && src === nameKey;
  }}).sort(function(a,b) {{ return (b.Created||'').localeCompare(a.Created||''); }});
  var el = document.getElementById('cd-leads');
  if (!leads.length) {{
    el.innerHTML = '<div style="color:var(--text3);font-size:13px;padding:8px 0">No leads captured from this business yet.</div>';
    return;
  }}
  var stColors = {{
    'New':'#3b82f6','Contacted':'#ea580c','Appointment Set':'#7c3aed',
    'Patient Seen':'#0891b2','Converted':'#059669','Dropped':'#9ca3af'
  }};
  var html = '';
  leads.forEach(function(L) {{
    var nm = L.Name || '(no name)';
    var ph = L.Phone || '';
    var rs = svJS(L.Reason) || '';
    var st = svJS(L.Status) || 'New';
    var dt = (L.Created || '').slice(0,10);
    var col = stColors[st] || '#6b7280';
    var line2 = '';
    if (ph) line2 += esc(ph);
    if (rs) line2 += (line2 ? ' · ' : '') + esc(rs);
    html += '<div style="padding:10px 0;border-bottom:1px solid var(--border);font-size:13px">';
    html += '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px">';
    html += '<span style="font-weight:600">' + esc(nm) + '</span>';
    html += '<span style="background:' + col + '22;color:' + col + ';font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600;white-space:nowrap">' + esc(st) + '</span>';
    html += '</div>';
    if (line2) html += '<div style="color:var(--text2);font-size:12px;margin-top:2px">' + line2 + '</div>';
    if (dt) html += '<div style="color:var(--text3);font-size:11px;margin-top:2px">' + esc(dt) + '</div>';
    html += '</div>';
  }});
  el.innerHTML = html;
}}

// ── Events tab ───────────────────────────────────────────────────────────
function scheduleCompanyEvent(formType) {{
  if (!_COMPANY) return;
  var name = _COMPANY.Name || '';
  var addr = _COMPANY.Address || '';
  var phone = _COMPANY.Phone || '';
  if (typeof openGFRForm !== 'function') {{
    alert('Event form not ready yet. Please try again in a moment.');
    return;
  }}
  openGFRForm(formType);
  setTimeout(function() {{
    ['s3','s4','s5'].forEach(function(p) {{
      var el = document.getElementById(p + '-company'); if (el && !el.value) el.value = name;
      var ad = document.getElementById(p + '-addr');    if (ad && !ad.value) ad.value = addr;
      var ph = document.getElementById(p + '-phone');   if (ph && !ph.value) ph.value = phone;
    }});
  }}, 350);
}}

function renderEventsTab() {{
  var events = (_ACTS || []).filter(function(a) {{ return !!svJS(a['Event Status']); }})
                            .sort(function(a,b) {{ return (b.Created||'').localeCompare(a.Created||''); }});
  var el = document.getElementById('cd-events');
  if (!events.length) {{
    el.innerHTML = '<div style="color:var(--text3);font-size:13px;padding:8px 0">No events scheduled at this business yet.</div>';
    return;
  }}
  var evColors = {{'Prospective':'#3b82f6','Approved':'#10b981','Scheduled':'#8b5cf6','Completed':'#64748b'}};
  var html = '';
  events.forEach(function(a) {{
    var nm = a.Summary || svJS(a.Type) || 'Event';
    var st = svJS(a['Event Status']) || '';
    var dt = a.Date || (a.Created || '').slice(0,10);
    var col = evColors[st] || '#6b7280';
    html += '<div style="padding:10px 0;border-bottom:1px solid var(--border);font-size:13px">';
    html += '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px">';
    html += '<span style="font-weight:600">' + esc(nm) + '</span>';
    if (st) html += '<span style="background:' + col + '22;color:' + col + ';font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600;white-space:nowrap">' + esc(st) + '</span>';
    html += '</div>';
    if (dt) html += '<div style="color:var(--text3);font-size:11px;margin-top:2px">' + esc(fmtDate(dt)) + '</div>';
    html += '</div>';
  }});
  el.innerHTML = html;
}}

// ── Boxes tab (guerilla only) ────────────────────────────────────────────
function renderBoxesTab() {{
  var c = _COMPANY;
  if (!_isGuerillaWithVenue(c)) return;  // tab button also absent
  var legacyId = c['Legacy ID'];
  var boxes = _BOXES_ALL.filter(function(b) {{
    var lf = b.Business;
    return Array.isArray(lf) && lf.some(function(r) {{ return r && r.id === legacyId; }});
  }}).sort(function(a,b) {{ return (b['Date Placed']||'').localeCompare(a['Date Placed']||''); }});
  var el = document.getElementById('cd-boxes');
  if (!boxes.length) {{
    el.innerHTML = '<div style="color:var(--text3);font-size:13px;padding:8px 0">No boxes placed here yet.</div>';
  }} else {{
    var html = '';
    boxes.forEach(function(b) {{
      var loc = b.Location || '(unspecified)';
      var st = svJS(b.Status) || 'Active';
      var dp = b['Date Placed'] || '';
      var pd = parseInt(b['Pickup Days']) || 14;
      var stColor = st === 'Active' ? '#f59e0b' : (st === 'Picked Up' ? '#059669' : '#9ca3af');
      html += '<div style="padding:10px 0;border-bottom:1px solid var(--border);font-size:13px">';
      html += '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px">';
      html += '<span style="font-weight:600">\U0001f4e6 ' + esc(loc) + '</span>';
      html += '<span style="background:' + stColor + '22;color:' + stColor + ';font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600">' + esc(st) + '</span>';
      html += '</div>';
      if (dp) html += '<div style="color:var(--text3);font-size:11px;margin-top:2px">Placed ' + esc(dp) + ' · pickup in ' + pd + ' days</div>';
      html += '</div>';
    }});
    el.innerHTML = html;
  }}
  var formEl = document.getElementById('cd-box-form');
  formEl.innerHTML =
    '<hr style="border:none;border-top:1px solid var(--border);margin:12px 0">' +
    '<div class="mobile-section-lbl" style="margin-bottom:8px">\U0001f4e6 Place New Box</div>' +
    '<div style="display:grid;gap:8px">' +
      '<input type="text" id="cd-box-loc" placeholder="Location (e.g. Front desk)" style="background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:10px 12px;font-size:14px;font-family:inherit">' +
      '<input type="text" id="cd-box-contact" placeholder="Contact person" style="background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:10px 12px;font-size:14px;font-family:inherit">' +
      '<div style="display:flex;align-items:center;gap:8px">' +
        '<span style="font-size:12px;color:var(--text3);white-space:nowrap">Pickup in</span>' +
        '<input type="number" id="cd-box-days" value="14" min="1" max="90" style="width:60px;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:10px 12px;font-size:14px;text-align:center;font-family:inherit">' +
        '<span style="font-size:12px;color:var(--text3)">days</span>' +
      '</div>' +
      '<button onclick="placeCompanyBox(' + legacyId + ')" style="background:#059669;color:#fff;border:none;border-radius:8px;padding:10px 14px;font-size:14px;font-weight:600;cursor:pointer;min-height:44px;font-family:inherit">Place Box</button>' +
      '<div id="cd-box-st" style="font-size:12px;text-align:center;min-height:14px"></div>' +
    '</div>';
}}

async function placeCompanyBox(venueId) {{
  var loc = document.getElementById('cd-box-loc').value.trim();
  var contact = document.getElementById('cd-box-contact').value.trim();
  var daysEl = document.getElementById('cd-box-days');
  var days = daysEl ? (parseInt(daysEl.value) || 14) : 14;
  var st = document.getElementById('cd-box-st');
  if (!loc) {{ alert('Please enter the box location.'); return; }}
  st.textContent = 'Saving…'; st.style.color = 'var(--text3)';
  try {{
    var r = await fetch('/api/guerilla/boxes', {{
      method: 'POST', headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{venue_id: venueId, location: loc, contact_person: contact, pickup_days: days}})
    }});
    var d = await r.json();
    if (r.ok && d.ok) {{
      st.style.color = '#059669'; st.textContent = 'Box placed ✓';
      document.getElementById('cd-box-loc').value = '';
      document.getElementById('cd-box-contact').value = '';
      // Refresh underlying list so the new row shows up
      _BOXES_ALL = await fetchAllTid(T_GOR_BOXES_TID);
      renderStats();
      renderBoxesTab();
    }} else {{
      st.style.color = '#ef4444'; st.textContent = 'Error: ' + (d.error || 'failed');
    }}
  }} catch(e) {{
    st.style.color = '#ef4444'; st.textContent = 'Network error';
  }}
}}

// ── Load orchestrator ────────────────────────────────────────────────────
async function load() {{
  var [cRes, aRes, leads, boxes] = await Promise.all([
    fetch('/api/companies/' + COMPANY_ID),
    fetch('/api/companies/' + COMPANY_ID + '/activities'),
    fetchAllTid(T_LEADS_TID),
    fetchAllTid(T_GOR_BOXES_TID),
  ]);
  if (!cRes.ok) {{
    document.getElementById('cd-name').textContent = 'Not found';
    document.getElementById('cd-meta').innerHTML = '';
    document.getElementById('cd-visits').innerHTML = '';
    document.getElementById('cd-stats').innerHTML = '';
    return;
  }}
  _COMPANY = await cRes.json();
  _ACTS = aRes.ok ? await aRes.json() : [];
  _LEADS_ALL = leads || [];
  _BOXES_ALL = boxes || [];
  renderHeader();
  renderTabs();
  renderStats();
  renderInfoTab();
  renderLeadsTab();
  renderEventsTab();
  renderBoxesTab();
}}

// ── Photo lightbox ───────────────────────────────────────────────────────
function openPhotoLightbox(url) {{
  var bg = document.createElement('div');
  bg.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.92);z-index:1000;display:flex;align-items:center;justify-content:center;padding:20px;cursor:pointer';
  bg.onclick = function() {{ bg.remove(); }};
  bg.innerHTML = '<img src="' + url + '" style="max-width:100%;max-height:100%;object-fit:contain">';
  document.body.appendChild(bg);
}}

// ── Log-activity modal ───────────────────────────────────────────────────
let _cdSentiment = '';
let _cdPhotoFile = null;
const _SENT_COLORS = {{ Green: '#059669', Yellow: '#f59e0b', Red: '#ef4444' }};

function setSentiment(val) {{
  _cdSentiment = (_cdSentiment === val) ? '' : val;  // tap-again deselects
  document.querySelectorAll('#cd-sentiment-row button').forEach(function(b) {{
    var v = b.getAttribute('data-sent');
    var on = (v === _cdSentiment);
    b.style.background = on ? _SENT_COLORS[v] : 'var(--bg)';
    b.style.color      = on ? '#fff'             : 'var(--text)';
    b.style.borderColor = on ? _SENT_COLORS[v]   : 'var(--border)';
  }});
}}

function onPhotoPicked(e) {{
  var f = e.target.files && e.target.files[0];
  if (!f) return;
  _cdPhotoFile = f;
  var reader = new FileReader();
  reader.onload = function(ev) {{
    document.getElementById('cd-photo-img').src = ev.target.result;
    document.getElementById('cd-photo-preview').style.display = 'block';
    document.getElementById('cd-photo-pick').textContent = '📷 Replace photo';
  }};
  reader.readAsDataURL(f);
}}

function clearPhoto() {{
  _cdPhotoFile = null;
  document.getElementById('cd-photo-input').value = '';
  document.getElementById('cd-photo-preview').style.display = 'none';
  document.getElementById('cd-photo-pick').textContent = '📷 Add photo';
}}

function openLogModal() {{
  document.getElementById('cd-summary').value = '';
  document.getElementById('cd-fu').value = '';
  document.getElementById('cd-type').value = 'Call';
  document.getElementById('cd-status').value = '';
  document.getElementById('cd-modal-msg').textContent = '';
  _cdSentiment = '';
  setSentiment('');  // resets button styles
  clearPhoto();
  document.getElementById('cd-modal-bg').style.display = 'flex';
}}

function closeLogModal() {{
  document.getElementById('cd-modal-bg').style.display = 'none';
}}

async function submitLog() {{
  var summary = document.getElementById('cd-summary').value.trim();
  var type    = document.getElementById('cd-type').value;
  var fu      = document.getElementById('cd-fu').value;
  var status  = document.getElementById('cd-status').value;
  var msg     = document.getElementById('cd-modal-msg');
  var btn     = document.getElementById('cd-modal-send');
  if (!summary) {{
    msg.style.color = '#ef4444';
    msg.textContent = 'Notes are required.';
    return;
  }}
  btn.disabled = true;
  btn.textContent = 'Saving…';
  msg.textContent = '';
  // Upload photo first (if any), grab URL, include in activity payload.
  var photoUrl = '';
  if (_cdPhotoFile) {{
    btn.textContent = 'Uploading photo…';
    var fd = new FormData();
    fd.append('photo', _cdPhotoFile);
    try {{
      var pr = await fetch('/api/companies/' + COMPANY_ID + '/activities/photo', {{
        method: 'POST', body: fd,
      }});
      if (pr.ok) {{
        var pj = await pr.json();
        photoUrl = pj.url || '';
      }} else {{
        msg.style.color = '#ef4444';
        msg.textContent = 'Photo upload failed (HTTP ' + pr.status + ')';
        btn.disabled = false; btn.textContent = 'Save';
        return;
      }}
    }} catch (e) {{
      msg.style.color = '#ef4444';
      msg.textContent = 'Photo upload network error';
      btn.disabled = false; btn.textContent = 'Save';
      return;
    }}
    btn.textContent = 'Saving…';
  }}
  var body = {{ summary: summary, type: type, kind: 'user_activity' }};
  if (fu) body.follow_up = fu;
  if (status) body.new_status = status;
  if (_cdSentiment) body.sentiment = _cdSentiment;
  if (photoUrl) body.photo_url = photoUrl;
  var r = await fetch('/api/companies/' + COMPANY_ID + '/activities', {{
    method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify(body),
  }});
  if (r.ok) {{
    closeLogModal();
    await load();
  }} else {{
    var err = '';
    try {{ err = (await r.json()).error || ''; }} catch(e) {{}}
    msg.style.color = '#ef4444';
    msg.textContent = 'Save failed: ' + (err || ('HTTP ' + r.status));
    btn.disabled = false;
    btn.textContent = 'Save';
  }}
}}

load();
"""
    script_js = (
        f"const GFR_USER = {repr(user_name)};\n"
        f"const TOOL = {{venuesT: {int(T_COMPANIES)}}};\n"
        + js
    )
    return _mobile_page(
        'm_directory', 'Company', body, script_js, br, bt, user=user,
        extra_html=GFR_EXTRA_HTML + LEAD_CAPTURE_HTML,
        extra_js=GFR_EXTRA_JS + '\n' + build_lead_capture_js(),
    )




def _mobile_directory_page(br: str, bt: str, category: str = "",
                            user: dict = None) -> str:
    """Mobile directory listing. `category` in {'', 'attorney', 'guerilla',
    'community'}; empty string means all. Tap a row → /company/{id}."""
    user = user or {}
    title = {
        "attorney":  "Attorney Directory",
        "guerilla":  "Guerilla Directory",
        "community": "Community Directory",
    }.get(category, "All Contacts")
    subtitle = {
        "attorney":  "Law firms & referral partners",
        "guerilla":  "Local businesses & health partners",
        "community": "Community groups & events",
    }.get(category, "Every outreach company")
    body = (
        '<div class="mobile-hdr">'
        f'<div><div class="mobile-hdr-title">{title}</div>'
        f'<div class="mobile-hdr-sub">{subtitle}</div></div>'
        '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        '</div>'
        '<div class="mobile-body">'
        '<div class="stats-row" style="margin-bottom:14px">'
        '<div class="stat-chip c-blue"><div class="label">Total</div><div class="value" id="dir-kpi-total">—</div></div>'
        '<div class="stat-chip c-green"><div class="label">Active</div><div class="value" id="dir-kpi-active">—</div></div>'
        '<div class="stat-chip c-yellow"><div class="label">Needs Contact</div><div class="value" id="dir-kpi-new">—</div></div>'
        '</div>'
        '<input type="search" id="dir-search" placeholder="Search name, address, phone…" oninput="renderDir()" '
        'style="width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:8px;'
        'background:var(--card);color:var(--text);font-size:14px;margin-bottom:10px;font-family:inherit">'
        '<div id="dir-filter" style="display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap"></div>'
        '<div id="dir-summary" style="font-size:12px;color:var(--text3);margin-bottom:8px">Loading…</div>'
        '<div id="dir-list"><div class="loading">Loading…</div></div>'
        '</div>'
    )
    cat_js = repr(category or "")
    js = f"""
var CATEGORY = {cat_js};
var _DIR_ROWS = [];
var _DIR_STATUS = 'prospects';
var _PROSPECT_STATUSES = ['Not Contacted', 'Contacted', 'In Discussion'];

var STATUS_META = {{
  'Not Contacted':  {{color: '#64748b'}},
  'Contacted':      {{color: '#2563eb'}},
  'In Discussion':  {{color: '#ea580c'}},
  'Active Partner': {{color: '#059669'}},
  'Blacklisted':    {{color: '#dc2626'}},
}};

var DIR_CAT_META = {{
  attorney:  {{label: 'Attorney',  color: '#7c3aed'}},
  guerilla:  {{label: 'Guerilla',  color: '#ea580c'}},
  community: {{label: 'Community', color: '#059669'}},
  other:     {{label: 'Other',     color: '#64748b'}},
}};

function esc(s) {{
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}}

function svJS(v) {{
  if (!v) return '';
  if (typeof v === 'object' && !Array.isArray(v)) return v.value || '';
  if (Array.isArray(v) && v.length) return (v[0] && v[0].value) || (v[0] && v[0].name) || String(v[0]);
  return String(v);
}}

function renderStatusFilter() {{
  var counts = {{ all: _DIR_ROWS.length, prospects: 0 }};
  Object.keys(STATUS_META).forEach(function(k) {{ counts[k] = 0; }});
  _DIR_ROWS.forEach(function(c) {{
    var s = svJS(c['Contact Status']) || 'Not Contacted';
    counts[s] = (counts[s] || 0) + 1;
    if (_PROSPECT_STATUSES.indexOf(s) !== -1) counts.prospects += 1;
  }});
  // Prospects first so it reads as the default intent, then all, then real statuses.
  var opts = ['prospects', 'all'].concat(Object.keys(STATUS_META));
  var html = '';
  opts.forEach(function(k) {{
    if (k === 'prospects' && !counts.prospects) return;
    if (k !== 'all' && k !== 'prospects' && !counts[k]) return;
    var active = k === _DIR_STATUS;
    var color;
    var label;
    if (k === 'all')             {{ color = '#0f172a'; label = 'All'; }}
    else if (k === 'prospects')  {{ color = '#2563eb'; label = 'Prospects'; }}
    else                         {{ color = (STATUS_META[k] || {{}}).color || '#64748b'; label = k; }}
    html +=
      '<button onclick="setStatus(\\'' + k + '\\')" ' +
      'style="padding:5px 10px;border-radius:14px;font-size:11px;font-weight:600;cursor:pointer;font-family:inherit;' +
      'border:1px solid ' + (active ? color : 'var(--border)') + ';' +
      'background:' + (active ? color : 'var(--card)') + ';' +
      'color:' + (active ? '#fff' : 'var(--text2)') + '">' +
      esc(label) + ' ' + counts[k] + '</button>';
  }});
  document.getElementById('dir-filter').innerHTML = html;
}}

function setStatus(k) {{
  _DIR_STATUS = k;
  renderStatusFilter();
  renderDir();
}}

function renderDir() {{
  var q = (document.getElementById('dir-search').value || '').toLowerCase().trim();
  var filtered = _DIR_ROWS.filter(function(c) {{
    var s = svJS(c['Contact Status']) || 'Not Contacted';
    if (_DIR_STATUS === 'prospects') {{
      if (_PROSPECT_STATUSES.indexOf(s) === -1) return false;
    }} else if (_DIR_STATUS !== 'all') {{
      if (s !== _DIR_STATUS) return false;
    }}
    if (!q) return true;
    var hay = ((c.Name || '') + ' ' + (c.Address || '') + ' ' + (c.Phone || '')).toLowerCase();
    return hay.indexOf(q) !== -1;
  }});
  filtered.sort(function(a, b) {{
    return (a.Name || '').localeCompare(b.Name || '');
  }});
  document.getElementById('dir-summary').textContent =
    filtered.length + ' compan' + (filtered.length === 1 ? 'y' : 'ies');
  if (!filtered.length) {{
    document.getElementById('dir-list').innerHTML =
      '<div style="text-align:center;padding:30px 0;color:var(--text3);font-size:13px">No matches.</div>';
    return;
  }}
  var html = '';
  filtered.forEach(function(c) {{
    var status = svJS(c['Contact Status']) || 'Not Contacted';
    var sMeta = STATUS_META[status] || {{color: '#64748b'}};
    var catKey = (svJS(c.Category) || 'other').toLowerCase();
    var catMeta = DIR_CAT_META[catKey] || DIR_CAT_META.other;
    // Only show the category pill when no specific category is filtered —
    // it's redundant on /attorney, /guerilla, /community.
    var catPill = CATEGORY ? '' :
      '<span style="background:' + catMeta.color + '22;color:' + catMeta.color +
      ';font-size:10px;font-weight:600;padding:2px 7px;border-radius:8px;white-space:nowrap">' +
      esc(catMeta.label) + '</span>';
    html +=
      '<div onclick="location.href=\\'/company/' + c.id + '\\'" ' +
      'style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:10px 12px;' +
      'margin-bottom:6px;cursor:pointer;display:flex;align-items:center;gap:8px">' +
      '<div style="flex:1;min-width:0">' +
      '<div style="font-size:14px;font-weight:700;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(c.Name || '(unnamed)') + '</div>' +
      (c.Address ? '<div style="font-size:11px;color:var(--text3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(c.Address) + '</div>' : '') +
      '</div>' +
      catPill +
      '<span style="background:' + sMeta.color + '22;color:' + sMeta.color + ';font-size:10px;font-weight:600;padding:2px 8px;border-radius:10px;white-space:nowrap">' + esc(status) + '</span>' +
      '</div>';
  }});
  document.getElementById('dir-list').innerHTML = html;
}}

async function loadDir() {{
  try {{
    var r = await fetch('/api/data/{T_COMPANIES}');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    var rows = await r.json();
    if (CATEGORY) {{
      rows = rows.filter(function(c) {{
        return (svJS(c.Category) || '').toLowerCase() === CATEGORY;
      }});
    }}
    // Exclude Permanently Closed
    rows = rows.filter(function(c) {{ return !c['Permanently Closed']; }});
    _DIR_ROWS = rows;
  }} catch (e) {{
    document.getElementById('dir-summary').textContent = '';
    document.getElementById('dir-list').innerHTML =
      '<div style="text-align:center;padding:30px 0;color:#ef4444;font-size:13px">Failed to load: ' + esc(e.message || 'error') + '</div>';
    return;
  }}
  renderStatusFilter();
  renderDir();
  // KPI strip
  var active = 0, needsContact = 0;
  _DIR_ROWS.forEach(function(c) {{
    var s = svJS(c['Contact Status']);
    if (s === 'Active Partner') active++;
    if (!s || s === 'Not Contacted') needsContact++;
  }});
  document.getElementById('dir-kpi-total').textContent = _DIR_ROWS.length;
  document.getElementById('dir-kpi-active').textContent = active;
  document.getElementById('dir-kpi-new').textContent = needsContact;
}}

loadDir();
"""
    return _mobile_page('m_directory', title, body, js, br, bt, user=user)
