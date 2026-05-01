"""Home dashboard + My Routes dashboard."""

from hub.shared import (
    _mobile_page,
    T_GOR_VENUES, T_GOR_BOXES, T_GOR_ROUTES, T_GOR_ROUTE_STOPS, T_LEADS,
    T_COMPANIES,
)
from hub.guerilla import GFR_EXTRA_HTML, GFR_EXTRA_JS


_HOME_CSS = """
<style>
#home-root[data-state="A"] .only-b,
#home-root[data-state="A"] .only-c { display:none }
#home-root[data-state="B"] .only-a,
#home-root[data-state="B"] .only-c { display:none }
#home-root[data-state="C"] .only-a,
#home-root[data-state="C"] .only-b { display:none }
.qlog-row { display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin-bottom:18px }
.qlog-btn { background:var(--card); border:1px solid var(--border); border-radius:10px;
            padding:12px 6px; font-size:12px; font-weight:600; color:var(--text);
            text-align:center; cursor:pointer; text-decoration:none;
            display:flex; flex-direction:column; align-items:center; gap:4px;
            font-family:inherit; min-height:64px; line-height:1.2 }
.qlog-btn:active { background:rgba(0,74,198,.08) }
.qlog-btn .material-symbols-outlined { font-size:22px; color:#004ac6 }
.qlog-btn[data-active="1"] { background:#004ac6; border-color:#004ac6; color:#fff }
.qlog-btn[data-active="1"] .material-symbols-outlined { color:#fff }
.status-strip { font-size:12px; color:var(--text3); margin-bottom:14px;
                display:flex; gap:6px; flex-wrap:wrap; align-items:center }
.status-strip a { color:var(--text2); text-decoration:none; font-weight:600 }
.status-strip .sep { color:var(--text4) }
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
</style>
"""


def _mobile_home_page(br: str, bt: str, user: dict = None) -> str:
    import datetime
    user = user or {}
    first = (user.get('name', 'there') or 'there').split()[0]
    today = datetime.date.today()
    day_str = f"{today.strftime('%A')}, {today.strftime('%B')} {today.day}"
    user_name = user.get('name', '')
    user_email = (user.get('email', '') or '').strip().lower()

    body = (
        '<div class="mobile-hdr">'
        + '<div><div class="mobile-hdr-title">Reform</div>'
        + f'<div class="mobile-hdr-sub">{day_str}</div></div>'
        + '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        + '</div>'
        + _HOME_CSS
        + '<div class="mobile-body">'
        + '<div id="home-root" data-state="A">'
        # ── Hero slot ──────────────────────────────────────────────────────
        + '<div id="hero-slot" style="margin-bottom:18px">'
        +   '<div class="only-a">'
        +     f'<div style="font-size:22px;font-weight:700;color:var(--text);margin-bottom:2px">Hey, {first}</div>'
        +     '<div style="font-size:13px;color:var(--text3)">Ready to hit the field?</div>'
        +   '</div>'
        +   '<div class="only-b" id="hero-b"></div>'
        +   '<div class="only-c" id="hero-c"></div>'
        + '</div>'
        # ── Status strip (replaces 2x2 KPI grid) ───────────────────────────
        + '<div class="status-strip">'
        +   '<a href="/routes" id="ss-stops">— stops</a>'
        +   '<span class="sep">·</span>'
        +   '<a href="/todo"   id="ss-overdue">— overdue</a>'
        +   '<span class="sep">·</span>'
        +   '<a href="/lead"   id="ss-leads">— leads (7d)</a>'
        + '</div>'
        # ── Quick-log row ──────────────────────────────────────────────────
        + '<div class="qlog-row">'
        +   '<button class="qlog-btn" onclick="quickLog(\'lead\')">'
        +     '<span class="material-symbols-outlined">person_add</span>'
        +     '<span>Log Lead</span></button>'
        +   '<button class="qlog-btn" id="qlog-visit-btn" onclick="quickLog(\'visit\')">'
        +     '<span class="material-symbols-outlined">check_circle</span>'
        +     '<span id="qlog-visit-lbl">Log Visit</span></button>'
        +   '<button class="qlog-btn" onclick="quickLog(\'box\')">'
        +     '<span class="material-symbols-outlined">inventory_2</span>'
        +     '<span>Place Box</span></button>'
        + '</div>'
        # ── Worklist ───────────────────────────────────────────────────────
        + '<div class="label-caps" style="display:flex;align-items:center;gap:6px;margin-bottom:8px">'
        +   '<span class="material-symbols-outlined" style="font-size:14px;color:#ba1a1a">priority_high</span>'
        +   'Worklist<span id="wl-ct" style="margin-left:auto;color:var(--text4);font-weight:600"></span></div>'
        + '<div id="wl-body" style="display:flex;flex-direction:column;gap:10px;margin-bottom:18px">'
        +   '<div class="card" style="color:var(--text3);text-align:center;font-size:13px">Loading…</div>'
        + '</div>'
        # ── Yesterday recap ────────────────────────────────────────────────
        + '<div id="recap-slot"></div>'
        # ── Place-box mini modal ───────────────────────────────────────────
        + '<div id="pb-modal-bg" onclick="if(event.target===this)closePbModal()" '
        + 'style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1100;'
        + 'align-items:flex-start;justify-content:center;padding:30px 14px;overflow-y:auto">'
        +   '<div style="background:var(--bg2);border:1px solid var(--border);border-radius:14px;'
        +   'width:100%;max-width:420px;padding:18px 20px calc(20px + env(safe-area-inset-bottom))">'
        +     '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">'
        +       '<h3 style="margin:0;color:var(--text);font-size:16px;flex:1">Place Box</h3>'
        +       '<button onclick="closePbModal()" style="background:none;border:none;color:var(--text3);'
        +       'font-size:18px;cursor:pointer;padding:4px 8px">×</button>'
        +     '</div>'
        +     '<div id="pb-modal-body"></div>'
        +     '<div id="pb-modal-msg" style="font-size:12px;min-height:14px;margin-top:8px"></div>'
        +     '<div style="display:flex;gap:8px;justify-content:flex-end;margin-top:10px">'
        +       '<button onclick="closePbModal()" '
        +       'style="padding:9px 16px;background:none;border:1px solid var(--border);color:var(--text2);'
        +       'border-radius:6px;font-size:13px;cursor:pointer;font-family:inherit">Cancel</button>'
        +       '<button id="pb-submit" onclick="submitPlaceBox()" '
        +       'style="padding:9px 20px;background:#004ac6;border:none;color:#fff;border-radius:6px;'
        +       'font-size:13px;font-weight:700;cursor:pointer;font-family:inherit">Place</button>'
        +     '</div>'
        +   '</div>'
        + '</div>'
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
        f"const TOOL = {{ venuesT: {T_GOR_VENUES} }};\n"
    )

    js_body = r"""
async function loadHomeDashboard() {
  const [routes, stops, leads, boxes, companies, overdueRaw] = await Promise.all([
    fetchAll(T_GOR_ROUTES),
    fetchAll(T_GOR_ROUTE_STOPS),
    fetchAll(T_LEADS),
    fetchAll(T_GOR_BOXES),
    fetchAll(T_COMPANIES),
    fetch('/api/outreach/due').then(r => r.ok ? r.json() : []).catch(() => [])
  ]);
  // Active Partners have graduated out of the rep's outreach pipeline.
  const overdueResp = (Array.isArray(overdueRaw) ? overdueRaw : [])
    .filter(c => c.status !== 'Active Partner');
  const venueCoMap = buildVenueCompanyMap(companies);

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

  // ── Status strip ─────────────────────────────────────────────────────
  const sevenDaysAgo = new Date(Date.now() - 7*86400000).toISOString().slice(0, 10);
  const recentLeads = leads.filter(l => {
    const d = (l['Created'] || l['Date'] || '').slice(0, 10);
    return d && d >= sevenDaysAgo;
  }).length;
  const overdueCount = Array.isArray(overdueResp) ? overdueResp.length : 0;
  document.getElementById('ss-stops').textContent = todayRoute
    ? (visitedToday + ' of ' + todayStops.length + ' stops')
    : '0 stops today';
  document.getElementById('ss-overdue').textContent = overdueCount + ' overdue';
  document.getElementById('ss-leads').textContent = recentLeads + ' leads (7d)';

  // ── Worklist (merged: overdue boxes + overdue companies + due-soon boxes) ─
  // TODO: navigator.geolocation.getCurrentPosition -> /api/venues/near
  // for proximity-aware "near me" hints. v2.
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
      // box row
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
  // Re-index the box rows so addBoxToTodayRoute(idx) hits the right entry.
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
      // State A: ad-hoc Business Outreach Log
      if (typeof openGFRForm === 'function') openGFRForm('Business Outreach Log');
      else window.location.href = '/companies';
    }
    return;
  }
  if (kind === 'box') {
    if (state === 'C' && window._activeVenueId) {
      openPbModal({ venueId: window._activeVenueId, venueName: window._activeVenueName });
    } else {
      // State A/B: open the GFR chooser (covers Business Outreach Log w/ box-left field)
      if (typeof openGFRChooser === 'function') openGFRChooser();
      else window.location.href = '/companies';
    }
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

// ── Place Box mini-modal ───────────────────────────────────────────────
function openPbModal(opts) {
  const o = opts || {};
  const venueLocked = !!o.venueId;
  const venueDisplay = esc(o.venueName || 'Active venue');
  const body = document.getElementById('pb-modal-body');
  body.innerHTML =
    '<label style="font-size:11px;font-weight:700;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Venue' + (venueLocked ? '' : ' *') + '</label>' +
    (venueLocked
      ? '<div style="padding:9px;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:6px;font-size:13px;margin-bottom:12px">' +
        venueDisplay + ' <span style="color:var(--text3);font-size:11px">(current stop)</span></div>'
      : '<div style="padding:10px;background:var(--bg);border:1px dashed var(--border);color:var(--text3);border-radius:6px;font-size:12px;margin-bottom:12px;text-align:center">' +
        'Open a company page and use its Place Box action.<br><a href="/companies" style="color:#004ac6;font-weight:600;text-decoration:none">→ Browse companies</a></div>'
    ) +
    '<label style="font-size:11px;font-weight:700;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Location (optional)</label>' +
    '<input type="text" id="pb-loc" placeholder="e.g. by the front door" ' +
    'style="width:100%;padding:9px;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:6px;font-size:13px;margin-bottom:12px;font-family:inherit">' +
    '<label style="font-size:11px;font-weight:700;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Pickup days</label>' +
    '<input type="number" id="pb-days" value="14" min="1" max="60" ' +
    'style="width:100%;padding:9px;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:6px;font-size:13px;font-family:inherit">';
  window._pbVenueId = o.venueId || null;
  document.getElementById('pb-modal-msg').textContent = '';
  const btn = document.getElementById('pb-submit');
  btn.disabled = !venueLocked;
  btn.style.opacity = venueLocked ? '1' : '.5';
  document.getElementById('pb-modal-bg').style.display = 'flex';
}
function closePbModal() {
  document.getElementById('pb-modal-bg').style.display = 'none';
}
async function submitPlaceBox() {
  const msg = document.getElementById('pb-modal-msg');
  const btn = document.getElementById('pb-submit');
  msg.textContent = '';
  const venueId = window._pbVenueId;
  if (!venueId) {
    msg.style.color = '#ef4444';
    msg.textContent = 'No venue in scope.';
    return;
  }
  const locEl = document.getElementById('pb-loc');
  const daysEl = document.getElementById('pb-days');
  const loc = locEl ? locEl.value.trim() : '';
  const days = daysEl ? (parseInt(daysEl.value) || 14) : 14;
  btn.disabled = true; btn.textContent = 'Placing…';
  try {
    const r = await fetch('/api/guerilla/boxes', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ venue_id: venueId, location: loc, pickup_days: days })
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      msg.style.color = '#ef4444';
      msg.textContent = 'Failed: ' + (err.error || ('HTTP ' + r.status));
      btn.disabled = false; btn.textContent = 'Place';
      return;
    }
    msg.style.color = '#059669';
    msg.textContent = 'Box placed ✓';
    setTimeout(() => { closePbModal(); loadHomeDashboard(); }, 600);
  } catch (e) {
    msg.style.color = '#ef4444';
    msg.textContent = 'Network error';
    btn.disabled = false; btn.textContent = 'Place';
  }
}

// ── Add a box-pickup stop to today's route (existing behavior, kept) ────
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
