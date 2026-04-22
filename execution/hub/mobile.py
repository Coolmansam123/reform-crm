"""
Guerilla Marketing -- Mobile Pages (home, log, route, recent, map).
"""
import os

from .shared import (
    _mobile_page, _is_admin,
    T_GOR_VENUES, T_GOR_ACTS, T_GOR_BOXES,
    T_GOR_ROUTES, T_GOR_ROUTE_STOPS,
    T_COM_VENUES, T_COM_ACTS,
    T_EVENTS, T_LEADS,
)
from .guerilla import GFR_EXTRA_HTML, GFR_EXTRA_JS
from .contact_detail import contact_actions_js


# ===========================================================================
# Mobile Pages
# ===========================================================================
def _mobile_home_page(br: str, bt: str, user: dict = None) -> str:
    import datetime
    user = user or {}
    first = (user.get('name', 'there') or 'there').split()[0]
    today = datetime.date.today()
    day_str = f"{today.strftime('%A')}, {today.strftime('%B')} {today.day}"
    user_name = user.get('name', '')
    body = (
        '<div class="mobile-hdr">'
        '<div><div class="mobile-hdr-title">\u2726 Reform</div>'
        f'<div class="mobile-hdr-sub">{day_str}</div></div>'
        '<div style="display:flex;align-items:center;gap:10px">'
        '<button class="m-theme-btn" onclick="mToggleTheme()" id="m-theme-btn"><span id="m-theme-icon">\U0001f319</span></button>'
        f'<a href="/logout" style="font-size:12px;color:var(--text3);text-decoration:none">Sign out</a>'
        '</div>'
        '</div>'
        '<div class="mobile-body">'
        f'<div class="mobile-greeting"><h2>Hey, {first} \U0001f44b</h2>'
        '<div class="sub">Ready to hit the field?</div></div>'
        '<div class="mobile-cta-grid">'
        '<a href="/routes" class="mobile-cta mobile-cta-orange">'
        '<span class="mobile-cta-icon">\U0001f5fa\ufe0f</span>'
        '<div><div>My Routes</div><div class="mobile-cta-sub">View all assigned routes</div></div>'
        '</a>'
        + ('<a href="/map" class="mobile-cta mobile-cta-blue">'
           '<span class="mobile-cta-icon">\U0001f4cd</span>'
           '<div><div>Route Planner</div><div class="mobile-cta-sub">Full venue map</div></div>'
           '</a>' if _is_admin(user) else '')
        + '</div>'
        '<div class="mobile-section-lbl">Quick Links</div>'
        '<div class="mobile-links">'
        '<a href="/lead" class="mobile-link">\U0001f4cb Capture Lead</a>'
        '<a href="/recent" class="mobile-link">\u23f1\ufe0f Recent Logs</a>'
        + ('<a href="/map" class="mobile-link">\U0001f4cd Full Map</a>' if _is_admin(user) else '')
        + '<a href="https://hub.reformchiropractic.app" class="mobile-link">\U0001f4bb Full Hub</a>'
        '</div>'
        '</div>'
    )
    script_js = f"const GFR_USER={repr(user_name)};\nconst TOOL = {{venuesT: {T_GOR_VENUES}}};\n"
    return _mobile_page('m_home', 'Home', body, script_js, br, bt, user=user,
                         extra_html=GFR_EXTRA_HTML, extra_js=GFR_EXTRA_JS)


def _mobile_routes_dashboard_page(br: str, bt: str, user: dict = None) -> str:
    user = user or {}
    user_email = (user.get('email', '') or '').strip().lower()
    body = (
        '<div class="mobile-hdr">'
        '<div><div class="mobile-hdr-title">My Routes</div>'
        '<div class="mobile-hdr-sub">All your assigned routes</div></div>'
        '<div style="display:flex;align-items:center;gap:10px">'
        '<button class="m-theme-btn" onclick="mToggleTheme()" id="m-theme-btn"><span id="m-theme-icon">\U0001f319</span></button>'
        '<a href="/" style="font-size:12px;color:var(--text3);text-decoration:none">\u2190 Home</a>'
        '</div>'
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
  var [routes, stops, venues] = await Promise.all([
    fetchAll({T_GOR_ROUTES}),
    fetchAll({T_GOR_ROUTE_STOPS}),
    fetchAll({T_GOR_VENUES})
  ]);
  // Filter to user's routes
  routes = routes.filter(function(r) {{
    return (r['Assigned To']||'').trim().toLowerCase() === USER_EMAIL;
  }});
  // Build venue lookup
  var venueMap = {{}};
  venues.forEach(function(v) {{ venueMap[v.id] = v; }});

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
    + '<div style="font-size:22px;font-weight:800;color:#ea580c">' + routes.length + '</div>'
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

    var h = '<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:10px">';
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
      h += '<div style="height:4px;background:var(--border);border-radius:2px;overflow:hidden;margin-bottom:6px">';
      h += '<div style="height:100%;width:'+rpct+'%;background:#059669;border-radius:2px"></div></div>';
    }}
    // Expand toggle
    if(total) {{
      h += '<button onclick="toggleStops(this,'+rid+')" style="font-size:11px;color:#3b82f6;background:none;border:none;font-weight:600;cursor:pointer;padding:0">Show stops \u25be</button>';
      h += '<div id="ms-'+rid+'" style="display:none;border-top:1px solid var(--border);padding-top:8px;margin-top:8px">';
      myStops.forEach(function(s, i) {{
        var ss = sv(s['Status'])||'Pending';
        var sColor = ss==='Visited'?'#059669':ss==='Skipped'?'#f97316':ss==='Not Reached'?'#ef4444':'#94a3b8';
        var vl = s['Venue'];
        var vId = Array.isArray(vl)&&vl.length ? vl[0].id : null;
        var vName = vId&&venueMap[vId] ? (venueMap[vId]['Name']||'(unnamed)') : (s['Name']||'(unknown)');
        h += '<div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:12px">';
        h += '<div style="width:20px;height:20px;border-radius:50%;background:'+sColor+';color:#fff;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;flex-shrink:0">'+(i+1)+'</div>';
        h += '<span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+esc(vName)+'</span>';
        h += '<span style="font-size:10px;color:'+sColor+';font-weight:600;flex-shrink:0">'+esc(ss)+'</span>';
        h += '</div>';
      }});
      h += '</div>';
    }}
    h += '</div>';
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

function toggleStops(btn, rid) {{
  var el = document.getElementById('ms-'+rid);
  if (el.style.display === 'none') {{
    el.style.display = 'block';
    btn.innerHTML = 'Hide stops \u25b4';
  }} else {{
    el.style.display = 'none';
    btn.innerHTML = 'Show stops \u25be';
  }}
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


def _mobile_lead_capture_page(br: str, bt: str, user: dict = None) -> str:
    user = user or {}
    user_name = user.get('name', '')
    user_email = (user.get('email', '') or '').strip()
    body = (
        '<div class="mobile-hdr">'
        '<div><div class="mobile-hdr-title">Capture Lead</div>'
        '<div class="mobile-hdr-sub">Log a new potential patient</div></div>'
        '<div style="display:flex;align-items:center;gap:10px">'
        '<button class="m-theme-btn" onclick="mToggleTheme()" id="m-theme-btn"><span id="m-theme-icon">\U0001f319</span></button>'
        '<a href="/" style="font-size:12px;color:var(--text3);text-decoration:none">\u2190 Home</a>'
        '</div>'
        '</div>'
        '<div class="mobile-body">'
        '<div id="lead-form" style="padding:4px 0">'
        # Name
        '<div style="margin-bottom:14px">'
        '<label style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Name *</label>'
        '<input type="text" id="lf-name" placeholder="Full name" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:10px 12px;font-size:14px;box-sizing:border-box">'
        '</div>'
        # Phone
        '<div style="margin-bottom:14px">'
        '<label style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Phone *</label>'
        '<input type="tel" id="lf-phone" placeholder="(555) 123-4567" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:10px 12px;font-size:14px;box-sizing:border-box">'
        '</div>'
        # Email
        '<div style="margin-bottom:14px">'
        '<label style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Email</label>'
        '<input type="email" id="lf-email" placeholder="email@example.com" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:10px 12px;font-size:14px;box-sizing:border-box">'
        '</div>'
        # Service Interested
        '<div style="margin-bottom:14px">'
        '<label style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Service Interested *</label>'
        '<select id="lf-service" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:10px 12px;font-size:14px;box-sizing:border-box;appearance:auto">'
        '<option value="">Select a service\u2026</option>'
        '<option value="Chiropractic Care">Chiropractic Care</option>'
        '<option value="Massage Therapy">Massage Therapy</option>'
        '<option value="Health Screening">Health Screening</option>'
        '<option value="Injury Rehab">Injury Rehab</option>'
        '<option value="Other">Other</option>'
        '</select>'
        '</div>'
        # Event (dropdown loaded from API)
        '<div style="margin-bottom:14px">'
        '<label style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Event / Source</label>'
        '<select id="lf-event" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:10px 12px;font-size:14px;box-sizing:border-box;appearance:auto">'
        '<option value="">No event (walk-in / field)</option>'
        '</select>'
        '</div>'
        # Notes
        '<div style="margin-bottom:18px">'
        '<label style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Notes</label>'
        '<textarea id="lf-notes" rows="3" placeholder="Additional details\u2026" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:10px 12px;font-size:14px;box-sizing:border-box;resize:vertical;font-family:inherit"></textarea>'
        '</div>'
        # Submit
        '<button id="lf-submit" onclick="submitLead()" '
        'style="width:100%;background:#ea580c;color:#fff;border:none;border-radius:8px;'
        'padding:14px;font-size:15px;font-weight:700;cursor:pointer">'
        'Submit Lead</button>'
        '<div id="lf-status" style="text-align:center;margin-top:10px;font-size:13px;min-height:20px"></div>'
        '</div>'
        # Success view (hidden initially)
        '<div id="lead-success" style="display:none;text-align:center;padding:40px 0">'
        '<div style="font-size:40px;margin-bottom:12px">\u2705</div>'
        '<div style="font-size:18px;font-weight:700;color:var(--text);margin-bottom:6px">Lead Captured!</div>'
        '<div style="font-size:13px;color:var(--text3);margin-bottom:20px">The lead has been saved successfully.</div>'
        '<button onclick="resetForm()" '
        'style="background:#ea580c;color:#fff;border:none;border-radius:8px;'
        'padding:12px 24px;font-size:14px;font-weight:600;cursor:pointer">'
        'Capture Another</button>'
        '</div>'
        '</div>'
    )
    js = f"""
var _events = [];

async function loadEvents() {{
  _events = await fetchAll({T_EVENTS});
  // Sort by date descending, show recent first
  _events.sort(function(a,b) {{ return (b['Event Date']||'').localeCompare(a['Event Date']||''); }});
  var sel = document.getElementById('lf-event');
  _events.forEach(function(e) {{
    var name = e['Name'] || '(unnamed)';
    var date = e['Event Date'] || '';
    var status = e['Event Status'];
    if (typeof status === 'object' && status) status = status.value || '';
    var opt = document.createElement('option');
    opt.value = e.id;
    opt.textContent = name + (date ? ' (' + date + ')' : '') + (status ? ' - ' + status : '');
    sel.appendChild(opt);
  }});
}}

async function submitLead() {{
  var name = (document.getElementById('lf-name').value || '').trim();
  var phone = (document.getElementById('lf-phone').value || '').trim();
  var email = (document.getElementById('lf-email').value || '').trim();
  var service = document.getElementById('lf-service').value;
  var eventId = document.getElementById('lf-event').value;
  var notes = (document.getElementById('lf-notes').value || '').trim();
  var st = document.getElementById('lf-status');
  var btn = document.getElementById('lf-submit');

  if (!name || !phone) {{
    st.style.color = '#ef4444';
    st.textContent = 'Name and phone are required';
    return;
  }}
  if (!service) {{
    st.style.color = '#ef4444';
    st.textContent = 'Please select a service';
    return;
  }}

  btn.disabled = true;
  btn.textContent = 'Saving\u2026';
  st.textContent = '';

  try {{
    var r = await fetch('/api/leads/capture', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        name: name,
        phone: phone,
        email: email,
        service: service,
        event_id: eventId ? parseInt(eventId) : null,
        notes: notes
      }})
    }});
    var d = await r.json();
    if (d.ok) {{
      document.getElementById('lead-form').style.display = 'none';
      document.getElementById('lead-success').style.display = 'block';
    }} else {{
      st.style.color = '#ef4444';
      st.textContent = 'Failed: ' + (d.error || 'unknown');
    }}
  }} catch(e) {{
    st.style.color = '#ef4444';
    st.textContent = 'Error: ' + e.message;
  }}
  btn.disabled = false;
  btn.textContent = 'Submit Lead';
}}

function resetForm() {{
  document.getElementById('lf-name').value = '';
  document.getElementById('lf-phone').value = '';
  document.getElementById('lf-email').value = '';
  document.getElementById('lf-service').value = '';
  document.getElementById('lf-event').value = '';
  document.getElementById('lf-notes').value = '';
  document.getElementById('lf-status').textContent = '';
  document.getElementById('lead-form').style.display = 'block';
  document.getElementById('lead-success').style.display = 'none';
  document.getElementById('lf-name').focus();
}}

loadEvents();
"""
    return _mobile_page('m_lead', 'Capture Lead', body, js, br, bt, user=user)


def _mobile_log_page(br: str, bt: str, user: dict = None) -> str:
    user = user or {}
    user_name = user.get('name', '')
    body = (
        '<div class="mobile-hdr">'
        '<div><div class="mobile-hdr-title">Log Activity</div>'
        '<div class="mobile-hdr-sub">Select a form to get started</div></div>'
        '<div style="display:flex;align-items:center;gap:10px">'
        '<button class="m-theme-btn" onclick="mToggleTheme()" id="m-theme-btn"><span id="m-theme-icon">\U0001f319</span></button>'
        '<a href="/" style="font-size:12px;color:var(--text3);text-decoration:none">\u2190 Home</a>'
        '</div>'
        '</div>'
        '<div class="mobile-body">'
        # Cards (single-column on mobile via CSS)
        '<div class="gfr-grid" style="margin-top:4px">'
        '<div class="gfr-card" onclick="openGFRForm(\'Business Outreach Log\')">'
        '<div class="gfr-card-icon">\U0001f3e2</div>'
        '<div class="gfr-card-name">Business Outreach Log</div>'
        '<div class="gfr-card-desc">Door-to-door visit, massage box placement, and program interest</div>'
        '<div class="gfr-card-cta">Open \u2192</div></div>'
        '<div class="gfr-card" onclick="openGFRForm(\'External Event\')">'
        '<div class="gfr-card-icon">\U0001f3aa</div>'
        '<div class="gfr-card-name">External Event</div>'
        '<div class="gfr-card-desc">Pre-event planning and community event demographic intel</div>'
        '<div class="gfr-card-cta">Open \u2192</div></div>'
        '<div class="gfr-card" onclick="openGFRForm(\'Mobile Massage Service\')">'
        '<div class="gfr-card-icon">\U0001f486</div>'
        '<div class="gfr-card-name">Mobile Massage Service</div>'
        '<div class="gfr-card-desc">Book a mobile chair or table massage at a company or event</div>'
        '<div class="gfr-card-cta">Open \u2192</div></div>'
        '<div class="gfr-card" onclick="openGFRForm(\'Lunch and Learn\')">'
        '<div class="gfr-card-icon">\U0001f37d\ufe0f</div>'
        '<div class="gfr-card-name">Lunch and Learn</div>'
        '<div class="gfr-card-desc">Schedule a chiropractic L&amp;L presentation for company staff</div>'
        '<div class="gfr-card-cta">Open \u2192</div></div>'
        '<div class="gfr-card" onclick="openGFRForm(\'Health Assessment Screening\')">'
        '<div class="gfr-card-icon">\U0001fa7a</div>'
        '<div class="gfr-card-name">Health Assessment Screening</div>'
        '<div class="gfr-card-desc">Book a chiropractic health screening event for staff</div>'
        '<div class="gfr-card-cta">Open \u2192</div></div>'
        '</div>'
        '</div>'
    )
    script_js = f"const GFR_USER={repr(user_name)};\nconst TOOL = {{venuesT: {T_GOR_VENUES}}};\n"
    return _mobile_page('m_log', 'Log Activity', body, script_js, br, bt, user=user,
                         extra_html=GFR_EXTRA_HTML, extra_js=GFR_EXTRA_JS)


def _mobile_route_page(br: str, bt: str, user: dict = None) -> str:
    import datetime
    gk = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    user = user or {}
    today_str = datetime.date.today().isoformat()
    user_email = user.get('email', '')
    user_name = user.get('name', '')
    body = (
        # Full-screen map for route
        '<div class="m-map-wrap" id="rmap"></div>'
        # "No Active Routes" overlay (shown/hidden by JS)
        '<div id="rt-empty" style="display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:105;text-align:center;pointer-events:none">'
        '<div style="background:var(--bg2);border-radius:16px;padding:28px 36px;box-shadow:0 4px 20px rgba(0,0,0,.3)">'
        '<div style="font-size:18px;font-weight:700;color:var(--text)">No Active Routes</div>'
        '</div></div>'
        # Progress bar overlay at top
        '<div id="rt-progress" style="position:fixed;top:0;left:0;right:0;z-index:110;background:var(--bg2);padding:10px 16px;border-bottom:1px solid var(--border);display:none">'
        '<div style="display:flex;justify-content:space-between;align-items:center">'
        '<div id="rt-name" style="font-size:14px;font-weight:700"></div>'
        '<a href="/" style="font-size:12px;color:var(--text3);text-decoration:none">\u2190 Home</a>'
        '</div>'
        '<div id="rt-count" style="font-size:12px;color:var(--text3);margin-top:3px"></div>'
        '<div style="margin-top:6px;background:var(--border);border-radius:4px;height:5px;overflow:hidden">'
        '<div id="rt-bar" style="height:100%;background:#ea580c;border-radius:4px;width:0%"></div>'
        '</div>'
        '</div>'
        # Bottom sheet (same pattern as mobile map)
        '<div class="m-sheet-backdrop" id="m-backdrop" onclick="closeRouteSheet()"></div>'
        '<div class="m-sheet" id="m-sheet">'
        '<div class="m-sheet-handle" onclick="closeRouteSheet()"></div>'
        '<div id="m-sheet-body" style="padding:0 0 20px"></div>'
        '</div>'
    )
    route_js = f"""
const RGK = {repr(gk)};
const _GGOR_VENUES = {T_GOR_VENUES};
const _GGOR_ACTS   = {T_GOR_ACTS};
const _GGOR_BOXES  = {T_GOR_BOXES};
const _GOFF_LAT = 33.9478, _GOFF_LNG = -118.1335;
const _STATUS_COLORS = {{'Pending':'#4285f4','Visited':'#059669','Skipped':'#f97316','Not Reached':'#ef4444'}};
var _routeData = null, _rMap = null, _rMarkers = {{}}, _rPolyline = null, _rOfficeMarker = null;
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

if (navigator.geolocation) {{
  navigator.geolocation.watchPosition(function(pos) {{
    _userLat = pos.coords.latitude; _userLng = pos.coords.longitude;
    if (_rMap && _userMarker) _userMarker.setPosition({{lat:_userLat,lng:_userLng}});
    else if (_rMap) {{
      _userMarker = new google.maps.Marker({{position:{{lat:_userLat,lng:_userLng}},map:_rMap,
        icon:{{path:google.maps.SymbolPath.CIRCLE,scale:7,fillColor:'#2563eb',fillOpacity:1,strokeColor:'#fff',strokeWeight:2}},
        title:'You',zIndex:999}});
    }}
  }}, function(){{}}, {{timeout:10000,enableHighAccuracy:true}});
}}

async function loadRoute() {{
  // Always init map first
  initRouteMap();
  try {{
    var [routeResp, boxes] = await Promise.all([
      fetch('/api/guerilla/routes/today').then(function(r){{return r.json();}}),
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
  stops.forEach(function(s) {{
    var sLat = parseFloat(s.lat), sLng = parseFloat(s.lng);
    if (sLat && sLng) {{
      totalDist += _haversine(prevLat, prevLng, sLat, sLng);
      prevLat = sLat; prevLng = sLng;
    }}
  }});
  if (totalDist > 0) summary += ' \u2022 ' + totalDist.toFixed(1) + ' mi total';
  document.getElementById('rt-count').textContent = summary;
  document.getElementById('rt-bar').style.width = pct + '%';
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
  // Clear existing markers/polyline
  Object.values(_rMarkers).forEach(function(m){{ m.setMap(null); }});
  _rMarkers = {{}};
  if (_rOfficeMarker) {{ _rOfficeMarker.setMap(null); _rOfficeMarker = null; }}
  if (_rPolyline) {{ _rPolyline.setMap(null); _rPolyline = null; }}
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
  if (pathCoords.length > 1) {{
    _rPolyline = new google.maps.Polyline({{
      path: pathCoords, geodesic: true,
      strokeColor: '#ea580c', strokeOpacity: 0.7, strokeWeight: 3,
      map: _rMap
    }});
  }}
  if (pathCoords.length) {{
    _rMap.fitBounds(bounds, {{top:70,bottom:80,left:20,right:20}});
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
  html += '<div class="m-tab" onclick="mSheetTab(this,\\'rp-acts-'+id+'\\')">Activity</div>';
  html += '<div class="m-tab" onclick="mSheetTab(this,\\'rp-evts-'+id+'\\')">Events</div>';
  html += '<div class="m-tab" onclick="mSheetTab(this,\\'rp-boxes-'+id+'\\')">Boxes</div>';
  html += '</div>';

  // Info tab
  html += '<div class="m-panel active" id="rp-info-'+id+'" style="padding:12px 16px">';
  if (addr) {{
    var mapsLink = 'https://maps.google.com/?q='+encodeURIComponent(addr);
    html += '<div style="margin-bottom:8px;font-size:13px">\U0001f4cd '+esc(addr)+' <a href="'+mapsLink+'" target="_blank" style="color:#3b82f6;font-size:12px">Navigate \u2197</a></div>';
  }}
  html += '<div id="rv-info-'+id+'" style="color:var(--text3);font-size:13px">Loading venue details\u2026</div>';
  html += '</div>';

  // Activity tab
  html += '<div class="m-panel" id="rp-acts-'+id+'" style="padding:12px 16px">';
  html += '<div id="rv-acts-'+id+'" style="color:var(--text3);font-size:13px">Loading\u2026</div>';
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

  // Check In / Skip / Didn't Get To buttons
  if (status === 'Pending') {{
    html += '<div style="padding:16px;display:flex;gap:10px">';
    html += '<button onclick="routeCheckIn('+id+')" style="flex:1;background:#ea580c;color:#fff;border:none;border-radius:10px;padding:14px;font-size:15px;font-weight:700;cursor:pointer">Check In</button>';
    html += '<button onclick="routeSkip('+id+')" style="width:70px;background:var(--bg);color:var(--text2);border:1px solid var(--border);border-radius:10px;padding:14px;font-size:12px;font-weight:600;cursor:pointer">Skip</button>';
    html += '<button onclick="routeNotReached('+id+')" style="width:70px;background:var(--bg);color:#ef4444;border:1px solid #ef444440;border-radius:10px;padding:14px;font-size:11px;font-weight:600;cursor:pointer;line-height:1.2">Didn\\\'t<br>Get To</button>';
    html += '</div>';
  }} else {{
    html += '<div style="padding:16px"><button onclick="routeCheckInForm()" style="width:100%;background:#ea580c;color:#fff;border:none;border-radius:10px;padding:14px;font-size:15px;font-weight:700;cursor:pointer">Check In</button></div>';
  }}

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
  // Load venue details, activities, events, boxes in parallel
  var results = await Promise.all([fetchAll(_GGOR_VENUES), fetchAll(_GGOR_ACTS), fetchAll(_GGOR_BOXES)]);
  var venues = results[0], acts = results[1], boxes = results[2];
  var v = venues.find(function(x){{return x.id === venueId;}});
  if (!v) return;
  var id = stop.stop_id;

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
    infoEl.innerHTML = ih;
  }}

  // Fill Activity tab — log-new form + history
  var actsEl = document.getElementById('rv-acts-' + id);
  if (actsEl) {{
    var myActs = acts.filter(function(a) {{
      var lf = a['Business'];
      return Array.isArray(lf) && lf.some(function(r){{return r.id===venueId;}});
    }}).sort(function(a,b){{return (b['Date']||'').localeCompare(a['Date']||'');}}).slice(0,10);
    // Log-new-activity form (collapsed by default)
    var ah = '<div style="margin-bottom:12px">';
    ah += '<button onclick="mRouteToggleLogForm()" style="width:100%;background:#ea580c20;color:#ea580c;border:1px solid #ea580c40;border-radius:8px;padding:10px;font-size:13px;font-weight:600;cursor:pointer;min-height:44px">+ Log new activity</button>';
    ah += '<div id="rv-act-form-'+id+'" style="display:none;margin-top:10px;background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px">';
    ah += '<select id="rv-act-type-'+id+'" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text1);border-radius:6px;padding:8px 10px;font-size:14px;margin-bottom:6px">';
    ah += '<option value="">Type\u2026</option><option>Email</option><option>Phone</option><option>In-Person</option><option>Text</option><option>Other</option>';
    ah += '</select>';
    ah += '<select id="rv-act-out-'+id+'" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text1);border-radius:6px;padding:8px 10px;font-size:14px;margin-bottom:6px">';
    ah += '<option value="">Outcome\u2026</option><option>Positive</option><option>Neutral</option><option>Negative</option><option>Left message</option><option>No answer</option>';
    ah += '</select>';
    ah += '<input type="text" id="rv-act-sum-'+id+'" placeholder="Brief summary\u2026" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text1);border-radius:6px;padding:8px 10px;font-size:14px;margin-bottom:8px;box-sizing:border-box">';
    ah += '<button onclick="mRouteLogActivity()" style="width:100%;background:#ea580c;color:#fff;border:none;border-radius:6px;padding:10px;font-size:14px;font-weight:600;cursor:pointer;min-height:44px">Save Activity</button>';
    ah += '<div id="rv-act-st-'+id+'" style="font-size:11px;margin-top:6px;text-align:center;min-height:14px"></div>';
    ah += '</div></div>';
    // History list — wrapped so the log-activity handler can prepend to it
    var histHtml = myActs.length
      ? myActs.map(function(a) {{
          var t = (a['Type'] && a['Type'].value) || a['Type'] || '';
          var o = (a['Outcome'] && a['Outcome'].value) || a['Outcome'] || '';
          var d = a['Date'] || '';
          return '<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:13px">'
            + '<span style="font-weight:600">'+esc(t)+'</span>'
            + (o ? ' \u2014 '+esc(o) : '')
            + '<div style="font-size:11px;color:var(--text3)">'+esc(d)+'</div></div>';
        }}).join('')
      : '<div style="color:var(--text3)">No activities yet</div>';
    actsEl.innerHTML = ah + '<div id="rv-acts-list-'+id+'">' + histHtml + '</div>';
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

function routeCheckIn(stopId) {{
  _pendingCheckInStopId = stopId;
  routeCheckInForm();
}}

function routeCheckInForm() {{
  if (!_rCurrentStop) return;
  closeRouteSheet();
  s2Reset();
  setTimeout(function() {{
    var el;
    el = document.getElementById('s2-event-name'); if (el) el.value = _rCurrentStop.name || '';
    el = document.getElementById('s2-addr');        if (el) el.value = _rCurrentStop.address || '';
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
    var r = await fetch('/api/guerilla/routes/today');
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
  closeRouteSheet();
  openGFRForm(formType);
  var name = _rCurrentStop.name || '';
  var addr = _rCurrentStop.address || '';
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

async function mRouteLogActivity() {{
  var stop = _rCurrentStop; if (!stop || !stop.venue_id) return;
  var venueId = stop.venue_id, id = stop.stop_id;
  var typeEl = document.getElementById('rv-act-type-' + id);
  var outEl  = document.getElementById('rv-act-out-' + id);
  var sumEl  = document.getElementById('rv-act-sum-' + id);
  var stEl   = document.getElementById('rv-act-st-' + id);
  var formEl = document.getElementById('rv-act-form-' + id);
  var listEl = document.getElementById('rv-acts-list-' + id);
  var type    = typeEl ? typeEl.value : '';
  var outcome = outEl  ? outEl.value  : '';
  var summary = sumEl  ? sumEl.value.trim()  : '';
  if (!type) {{ if (stEl) {{ stEl.textContent = 'Pick a type first'; stEl.style.color = '#ef4444'; }} return; }}
  if (stEl) {{ stEl.textContent = 'Saving\u2026'; stEl.style.color = 'var(--text3)'; }}
  var res = await Contact.logActivity('gorilla', venueId, {{type: type, outcome: outcome, summary: summary}});
  if (stEl) {{
    stEl.textContent = res.ok ? '\u2713 Logged' : '\u2717 Failed';
    stEl.style.color = res.ok ? '#059669' : '#ef4444';
    setTimeout(function() {{ if (stEl) stEl.textContent = ''; }}, 2000);
  }}
  if (res.ok) {{
    if (typeEl) typeEl.value = '';
    if (outEl) outEl.value = '';
    if (sumEl) sumEl.value = '';
    if (formEl) formEl.style.display = 'none';
    if (listEl) {{
      var d = (res.row && res.row['Date']) || new Date().toISOString().split('T')[0];
      var html = '<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:13px">'
        + '<span style="font-weight:600">'+esc(type)+'</span>'
        + (outcome ? ' \u2014 '+esc(outcome) : '')
        + (summary ? '<div style="font-size:12px;color:var(--text2);margin-top:2px">'+esc(summary)+'</div>' : '')
        + '<div style="font-size:11px;color:var(--text3)">'+esc(d)+'</div></div>';
      if (listEl.innerHTML.indexOf('No activities yet') !== -1) listEl.innerHTML = '';
      listEl.innerHTML = html + listEl.innerHTML;
    }}
  }}
}}

function mRouteToggleLogForm() {{
  var stop = _rCurrentStop; if (!stop) return;
  var el = document.getElementById('rv-act-form-' + stop.stop_id);
  if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
}}

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
                         extra_html=GFR_EXTRA_HTML, extra_js=GFR_EXTRA_JS)


def _mobile_recent_page(br: str, bt: str, user: dict = None) -> str:
    user = user or {}
    user_name = user.get('name', '')
    body = (
        '<div class="mobile-hdr">'
        '<div><div class="mobile-hdr-title">Recent Activity</div>'
        '<div class="mobile-hdr-sub">Your last 20 field logs</div></div>'
        '<div style="display:flex;align-items:center;gap:10px">'
        '<button class="m-theme-btn" onclick="mToggleTheme()" id="m-theme-btn"><span id="m-theme-icon">\U0001f319</span></button>'
        '<a href="/" style="font-size:12px;color:var(--text3);text-decoration:none">\u2190 Home</a>'
        '</div>'
        '</div>'
        '<div class="mobile-body" id="recent-body">'
        '<div class="loading">Loading\u2026</div>'
        '</div>'
    )
    recent_js = f"""
const MY_NAME = {repr(user_name)};
const GFR_TYPES = ['Business Outreach Log','External Event','Mobile Massage Service','Lunch and Learn','Health Assessment Screening'];

async function loadRecent() {{
  var acts = await fetchAll({T_GOR_ACTS});
  // Filter to GFR types, sort newest first
  var mine = acts.filter(function(r) {{
    var t = r['Type'] ? (r['Type'].value || r['Type']) : '';
    return GFR_TYPES.indexOf(t) >= 0;
  }});
  mine.sort(function(a,b){{return (b['Date']||'').localeCompare(a['Date']||'');}});
  mine = mine.slice(0,20);
  var body = document.getElementById('recent-body');
  if (!mine.length) {{
    body.innerHTML = '<div class="empty">No field activity logged yet.</div>';
    return;
  }}
  body.innerHTML = mine.map(function(r) {{
    var t = r['Type'] ? (r['Type'].value || r['Type']) : 'Activity';
    var biz = r['Business'] && r['Business'].length ? esc(r['Business'][0].value||'\u2014') : '\u2014';
    var contact = esc(r['Contact Person']||'');
    var outcome = r['Outcome'] ? (r['Outcome'].value || r['Outcome']) : '';
    return '<div class="mobile-act-item">'
      + '<span class="mobile-act-type">' + esc(t) + '</span>'
      + '<div class="mobile-act-biz">' + biz + '</div>'
      + '<div class="mobile-act-meta">'
      + (contact ? contact + ' \u00b7 ' : '')
      + esc(fmt(r['Date']||''))
      + (outcome ? ' \u00b7 ' + esc(outcome) : '')
      + '</div></div>';
  }}).join('');
}}

loadRecent();
"""
    script_js = f"const GFR_USER={repr(user_name)};\nconst TOOL = {{venuesT: {T_GOR_VENUES}}};\n" + recent_js
    return _mobile_page('m_recent', 'Recent Activity', body, script_js, br, bt, user=user,
                         extra_html=GFR_EXTRA_HTML, extra_js=GFR_EXTRA_JS)


def _mobile_map_page(br: str, bt: str, user: dict = None) -> str:
    gk = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    user = user or {}
    user_name = user.get('name', '')
    body = (
        # Full-screen map -- breaks out of mobile-wrap via position:fixed
        '<div class="m-map-wrap" id="gmap">'
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
const _GGOR_TID = {T_GOR_VENUES};
const _GCOM_TID = {T_COM_VENUES};
const _GGOR_ACTS = {T_GOR_ACTS};
const _GCOM_ACTS = {T_COM_ACTS};
const _GBOXES   = {T_GOR_BOXES};
const _GOFF_LAT = 33.9478, _GOFF_LNG = -118.1335;
const _GSTATUS_COLORS = {{'Not Contacted':'#4285f4','Contacted':'#fbbc04','In Discussion':'#ff9800','Active Partner':'#34a853','Active Relationship':'#34a853'}};

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

function _gPinIcon(color, tool) {{
  return {{
    path: google.maps.SymbolPath.CIRCLE,
    scale: tool === 'gorilla' ? 9 : 8,
    fillColor: color, fillOpacity: 1,
    strokeColor: tool === 'gorilla' ? '#ea580c' : '#059669',
    strokeWeight: 2
  }};
}}

function initGMap() {{
  if (!GK) {{
    document.getElementById('gmap').innerHTML = '<div style="padding:40px;text-align:center;color:var(--text3)">Maps API key not configured.</div>';
    return;
  }}
  window._gMapReadyCb = function() {{
    var el = document.getElementById('gmap');
    el.style.height = el.offsetHeight + 'px';
    _gMap = new google.maps.Map(el, {{
      center: {{lat: _GOFF_LAT, lng: _GOFF_LNG}}, zoom: 13,
      mapTypeControl: false, streetViewControl: false,
      styles: [{{featureType:'poi',stylers:[{{visibility:'off'}}]}},
               {{featureType:'transit',stylers:[{{visibility:'off'}}]}}]
    }});
    new google.maps.Marker({{
      position: {{lat: _GOFF_LAT, lng: _GOFF_LNG}}, map: _gMap,
      title: 'Reform Chiropractic',
      icon: {{url: 'https://maps.google.com/mapfiles/ms/icons/red-dot.png'}}
    }});
    setTimeout(function(){{ google.maps.event.trigger(_gMap, 'resize'); _gMap.setCenter({{lat: _GOFF_LAT, lng: _GOFF_LNG}}); }}, 100);
    renderGMarkers();
  }};
  var s = document.createElement('script');
  s.src = 'https://maps.googleapis.com/maps/api/js?key=' + GK + '&callback=_gMapReadyCb';
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
    var status = sv(v['Contact Status']);
    var color  = _GSTATUS_COLORS[status] || '#9e9e9e';
    // Override stroke for box alerts
    var alertLevel = _boxAlerts[v.id];
    var strokeColor = alertLevel === 'action' ? '#ef4444' : alertLevel === 'warning' ? '#f59e0b' : (v._tool === 'gorilla' ? '#ea580c' : '#059669');
    var marker = new google.maps.Marker({{
      position: {{lat: lat, lng: lng}}, map: _gMap,
      title: v['Name'] || '',
      icon: {{path:google.maps.SymbolPath.CIRCLE, scale:v._tool==='gorilla'?9:8, fillColor:color, fillOpacity:1, strokeColor:strokeColor, strokeWeight:alertLevel?3:2}}
    }});
    (function(venue) {{
      marker.addListener('click', function() {{ openSheet(venue); }});
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
    + 'style="width:100%;background:#ea580c;color:#fff;border:none;border-radius:10px;padding:14px;font-size:15px;font-weight:700;cursor:pointer">'
    + 'Check In</button></div>';

  return html;
}}

async function updateMapStatus(id, tid, val) {{
  var v = _gVenues.find(function(x) {{ return x.id === id && x._tid === tid; }});
  if (v) v['Contact Status'] = {{value: val}};
  var toolKey = tid === _GGOR_TID ? 'gorilla' : 'community';
  var k = id + '_' + toolKey;
  if (_gMarkers[k]) {{
    var color = _GSTATUS_COLORS[val] || '#9e9e9e';
    _gMarkers[k].setIcon(_gPinIcon(color, toolKey));
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
    btn.style.background = '#ea580c';
  }} else {{
    _activeTab = 'info';
    btn.textContent = 'Check In';
    btn.style.background = '#ea580c';
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
