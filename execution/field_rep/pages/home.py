"""Home dashboard + My Routes dashboard."""

from hub.shared import (
    _mobile_page,
    T_GOR_VENUES, T_GOR_BOXES, T_GOR_ROUTES, T_GOR_ROUTE_STOPS, T_LEADS,
    T_COMPANIES,
)
from hub.guerilla import GFR_EXTRA_HTML, GFR_EXTRA_JS


def _mobile_home_page(br: str, bt: str, user: dict = None) -> str:
    import datetime
    user = user or {}
    first = (user.get('name', 'there') or 'there').split()[0]
    today = datetime.date.today()
    day_str = f"{today.strftime('%A')}, {today.strftime('%B')} {today.day}"
    user_name = user.get('name', '')
    body = (
        '<div class="mobile-hdr">'
        + '<div><div class="mobile-hdr-title">Reform</div>'
        + f'<div class="mobile-hdr-sub">{day_str}</div></div>'
        + '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        + '</div>'
        + '<div class="mobile-body">'
        + f'<div style="margin-bottom:18px"><div style="font-size:22px;font-weight:700;color:var(--text);margin-bottom:2px">Hey, {first}</div>'
        + '<div style="font-size:13px;color:var(--text3)">Ready to hit the field?</div></div>'
        # 2x2 stat tile grid
        + '<div class="label-caps" style="margin-bottom:8px">Daily Overview</div>'
        + '<div class="stat-grid" style="margin-bottom:20px">'
        +   '<a href="/routes" class="stat-tile" style="text-decoration:none;cursor:pointer">'
        +     '<div class="stat-label">Today\'s stops</div><div class="stat-value" id="kpi-stops">—</div></a>'
        +   '<a href="/todo" class="stat-tile" style="text-decoration:none;cursor:pointer">'
        +     '<div class="stat-label">Overdue</div><div class="stat-value" id="kpi-overdue" style="color:#ba1a1a">—</div></a>'
        +   '<a href="/lead" class="stat-tile" style="text-decoration:none;cursor:pointer">'
        +     '<div class="stat-label">Leads (7d)</div><div class="stat-value" id="kpi-leads">—</div></a>'
        +   '<a href="/routes" class="stat-tile" style="text-decoration:none;cursor:pointer">'
        +     '<div class="stat-label">Active routes</div><div class="stat-value" id="kpi-routes">—</div></a>'
        + '</div>'
        # Today's route — featured card slot
        + '<div class="label-caps" style="display:flex;align-items:center;gap:6px;margin-bottom:8px">'
        +   '<span class="material-symbols-outlined" style="font-size:14px">map</span>'
        +   'Today\'s route<span id="today-ct" style="margin-left:auto;color:var(--text4);font-weight:600"></span></div>'
        + '<div id="today-body" style="margin-bottom:20px">'
        +   '<div class="card" style="color:var(--text3);text-align:center;font-size:13px">Loading…</div></div>'
        # Needs Attention
        + '<div class="label-caps" style="display:flex;align-items:center;gap:6px;margin-bottom:8px">'
        +   '<span class="material-symbols-outlined" style="font-size:14px;color:#ba1a1a">priority_high</span>'
        +   'Needs attention<span id="attn-ct" style="margin-left:auto;color:var(--text4);font-weight:600"></span></div>'
        + '<div id="attn-body" style="display:flex;flex-direction:column;gap:10px;margin-bottom:20px">'
        +   '<div class="card" style="color:var(--text3);text-align:center;font-size:13px">Loading…</div></div>'
        # Massage Boxes
        + '<div class="label-caps" style="display:flex;align-items:center;gap:6px;margin-bottom:8px">'
        +   '<span class="material-symbols-outlined" style="font-size:14px">inventory_2</span>'
        +   'Massage boxes<span id="box-ct" style="margin-left:auto;color:var(--text4);font-weight:600"></span></div>'
        + '<div id="box-body" style="display:flex;flex-direction:column;gap:10px">'
        +   '<div class="card" style="color:var(--text3);text-align:center;font-size:13px">Loading…</div></div>'
        + '</div>'
    )
    user_email = (user.get('email', '') or '').strip().lower()
    script_js = f"""
const GFR_USER = {repr(user_name)};
const USER_EMAIL = {repr(user_email)};
const TOOL = {{ venuesT: {T_GOR_VENUES} }};

async function loadHomeDashboard() {{
  const [routes, stops, leads, boxes, companies, overdueRaw] = await Promise.all([
    fetchAll({T_GOR_ROUTES}),
    fetchAll({T_GOR_ROUTE_STOPS}),
    fetchAll({T_LEADS}),
    fetchAll({T_GOR_BOXES}),
    fetchAll({T_COMPANIES}),
    fetch('/api/outreach/due').then(r => r.ok ? r.json() : []).catch(() => [])
  ]);
  // Active Partners have graduated out of the rep's outreach pipeline.
  const overdueResp = (Array.isArray(overdueRaw) ? overdueRaw : [])
    .filter(c => c.status !== 'Active Partner');
  const venueCoMap = buildVenueCompanyMap(companies);

  const myRoutes = routes.filter(r => (r['Assigned To']||'').trim().toLowerCase() === USER_EMAIL);
  const today = new Date().toISOString().slice(0, 10);

  // Today's route
  const todayRoute = myRoutes.find(r => {{
    const s = sv(r['Status']) || 'Draft';
    return r['Date'] === today && (s === 'Active' || s === 'Draft');
  }});
  const activeRoutes = myRoutes.filter(r => {{
    const s = sv(r['Status']) || 'Draft';
    return s === 'Active' || s === 'Draft';
  }}).length;

  let todayStops = 0;
  let todayBody = '<div class="card" style="color:var(--text3);text-align:center;font-size:13px;padding:18px">No route assigned today</div>';
  if (todayRoute) {{
    const ts = stops.filter(s => {{
      const rl = s['Route']; return Array.isArray(rl) && rl.some(x => x.id === todayRoute.id);
    }});
    todayStops = ts.length;
    const done = ts.filter(s => sv(s['Status']) === 'Visited' || sv(s['Status']) === 'Skipped').length;
    const name = esc(todayRoute['Name'] || "Today's Route");
    todayBody = `<a href="/route" class="card card-featured" style="display:block;text-decoration:none;color:inherit;cursor:pointer;padding:18px 20px">
      <div class="label-caps" style="margin-bottom:6px">Active route</div>
      <div style="font-size:18px;font-weight:700;margin-bottom:6px;line-height:1.3">${{name}}</div>
      <div style="font-size:13px;opacity:.88">${{done}} of ${{ts.length}} stops done · Tap to continue &rarr;</div></a>`;
    document.getElementById('today-ct').textContent = todayStops + ' stops';
  }} else {{
    document.getElementById('today-ct').textContent = '';
  }}
  document.getElementById('today-body').innerHTML = todayBody;

  // Leads in last 7 days
  const sevenDaysAgo = new Date(Date.now() - 7*86400000).toISOString().slice(0, 10);
  const recentLeads = leads.filter(l => {{
    const d = (l['Created'] || l['Date'] || '').slice(0, 10);
    return d && d >= sevenDaysAgo;
  }}).length;

  // KPI chips
  document.getElementById('kpi-stops').textContent = todayStops;
  document.getElementById('kpi-overdue').textContent = Array.isArray(overdueResp) ? overdueResp.length : 0;
  document.getElementById('kpi-leads').textContent = recentLeads;
  document.getElementById('kpi-routes').textContent = activeRoutes;

  // Needs Attention: top 5 overdue (cards with red left-border)
  const topOverdue = (Array.isArray(overdueResp) ? overdueResp : []).slice(0, 5);
  const overdueTotal = Array.isArray(overdueResp) ? overdueResp.length : 0;
  document.getElementById('attn-ct').textContent = overdueTotal ? '· ' + overdueTotal + ' overdue' : '';
  document.getElementById('attn-body').innerHTML = topOverdue.length ? topOverdue.map(c => `
    <a href="/company/${{c.id}}" class="card card-urgent" style="display:flex;align-items:center;justify-content:space-between;gap:8px;text-decoration:none;color:inherit;cursor:pointer">
      <span style="font-size:14px;font-weight:600;color:var(--text);min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${{esc(c.name)}}</span>
      <span class="pill pill-overdue" style="white-space:nowrap">${{c.days_overdue}}d overdue</span>
    </a>
  `).join('') : '<div class="card" style="color:var(--text3);text-align:center;font-size:13px">All caught up &check;</div>';

  // Massage Boxes: all active, sorted by most overdue first
  const activeBoxes = boxes.filter(b => sv(b['Status']) === 'Active' && b['Date Placed']);
  const rows = activeBoxes.map(b => {{
    const placed = (b['Date Placed'] || '').slice(0, 10);
    const pickupDays = parseInt(b['Pickup Days']) || 14;
    const age = -daysUntil(placed);
    const overdue = age - pickupDays;
    const biz = (b['Business'] || [])[0] || {{}};
    return {{ boxId: b.id, venueId: biz.id, venueName: biz.value || 'Unknown venue',
             placed, age, pickupDays, overdue }};
  }});
  rows.sort((a, b) => b.overdue - a.overdue);
  window._boxRows = rows;

  document.getElementById('box-ct').textContent = rows.length ? '· ' + rows.length + ' active' : '';
  const routeId = todayRoute ? todayRoute.id : null;
  document.getElementById('box-body').innerHTML = rows.length ? rows.map((x, i) => {{
    let pill, cardAccent = '';
    if (x.overdue > 0)        {{ pill = '<span class="pill pill-overdue">' + x.overdue + 'd overdue</span>'; cardAccent = ' card-urgent'; }}
    else if (x.overdue === 0) {{ pill = '<span class="pill pill-warning">due today</span>'; cardAccent = ' card-warning'; }}
    else if (x.overdue >= -2) {{ pill = '<span class="pill pill-warning">due in ' + (-x.overdue) + 'd</span>'; cardAccent = ' card-warning'; }}
    else                      {{ pill = '<span class="pill pill-success">' + (-x.overdue) + 'd left</span>'; }}
    const btn = (routeId && x.venueId)
      ? '<button id="box-add-' + i + '" onclick="addBoxToTodayRoute(' + i + ')" style="background:var(--primary);color:#fff;border:none;border-radius:6px;padding:8px 12px;font-size:12px;font-weight:600;cursor:pointer;min-height:36px;white-space:nowrap">+ Add</button>'
      : '<span style="font-size:11px;color:var(--text4);white-space:nowrap">' + (routeId ? 'no venue' : 'no active route') + '</span>';
    const companyId = venueCoMap[x.venueId];
    const nameHtml = companyId
      ? '<a href="/company/' + companyId + '" style="font-size:14px;font-weight:600;color:var(--text);text-decoration:none;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(x.venueName) + '</a>'
      : '<div style="font-size:14px;font-weight:600;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(x.venueName) + '</div>';
    return '<div class="card' + cardAccent + '" style="display:flex;align-items:center;justify-content:space-between;gap:12px">'
      + '<div style="flex:1;min-width:0">' + nameHtml
      +   '<div style="margin-top:6px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">' + pill + '<span style="font-size:11px;color:var(--text3)">placed ' + esc(fmt(x.placed)) + '</span></div>'
      + '</div>' + btn + '</div>';
  }}).join('') : '<div class="card" style="color:var(--text3);text-align:center;font-size:13px">No active boxes</div>';
  window._todayRouteId = routeId;
}}

async function addBoxToTodayRoute(idx) {{
  const x = (window._boxRows || [])[idx];
  const routeId = window._todayRouteId;
  if (!x || !routeId || !x.venueId) return;
  const btn = document.getElementById('box-add-' + idx);
  if (btn) {{ btn.disabled = true; btn.textContent = '…'; }}
  try {{
    const r = await fetch('/api/guerilla/routes/' + routeId + '/stops', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{venue_id: x.venueId, name: 'Box pickup: ' + x.venueName}})
    }});
    if (!r.ok) {{
      const err = await r.json().catch(() => ({{}}));
      if (btn) {{ btn.disabled = false; btn.textContent = '+ Add'; }}
      alert('Could not add: ' + (err.error || r.status));
      return;
    }}
    if (btn) {{
      btn.style.background = '#059669';
      btn.textContent = '✓ Added';
    }}
  }} catch (e) {{
    if (btn) {{ btn.disabled = false; btn.textContent = '+ Add'; }}
    alert('Network error — try again');
  }}
}}

loadHomeDashboard().catch(err => console.error('Dashboard load failed:', err));
"""
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
        '<span class="mobile-cta-icon">\U0001f5fa\ufe0f</span>'
        '<div><div id="today-cta-title">Start Today\'s Route</div>'
        '<div class="mobile-cta-sub" id="today-cta-sub">Loading\u2026</div></div>'
        '</a>'
        # Stat cards
        '<div id="m-stats" style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:16px">'
        '<div class="loading">Loading\u2026</div></div>'
        # Route list
        '<div id="m-route-list"><div class="loading">Loading\u2026</div></div>'
        # Past routes toggle
        '<div id="m-past-wrapper" style="display:none">'
        '<button id="m-past-toggle" onclick="togglePast()" '
        'style="width:100%;padding:10px;border:1px solid var(--border);background:var(--card);'
        'color:var(--text2);border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;margin-bottom:12px">'
        '\u25b6 Show past routes</button>'
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
    h += '<div style="font-size:11px;color:var(--text3);margin-bottom:8px">'+fmt(row['Date']||'')+' \u2022 '+total+' stops</div>';
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
    btn.innerHTML = '\u25bc Hide past routes';
  }} else {{
    el.style.display = 'none';
    btn.innerHTML = '\u25b6 Show past routes';
  }}
}}

load();
"""
    return _mobile_page('m_routes', 'My Routes', body, js, br, bt, user=user)
