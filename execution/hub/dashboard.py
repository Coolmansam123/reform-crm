"""
Dashboard pages — login, hub overview, calendar, coming soon placeholders.
"""
import json
import os

from .shared import _CSS, _page
from .access import _get_allowed_hubs
from .meetings import meeting_modal_html, meeting_modal_js


# ──────────────────────────────────────────────────────────────────────────────
# LOGIN PAGE
# ──────────────────────────────────────────────────────────────────────────────
def _login_page(error: str = "") -> str:
    if error == "domain":
        err = '<p class="login-err">Access restricted to authorized staff accounts.</p>'
    elif error:
        err = '<p class="login-err">Sign-in failed. Please try again.</p>'
    else:
        err = ''
    return (
        '<!DOCTYPE html><html lang="en">'
        '<head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Login — Reform Hub</title>'
        f'<style>{_CSS}</style>'
        '</head>'
        '<body class="login-body">'
        '<div class="login-wrap"><div class="login-box">'
        '<h1>\u2726 Reform</h1>'
        '<p class="sub">Outreach Hub — Staff Access</p>'
        '<a href="/auth/google" class="google-btn">'
        '<img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" width="20" alt="">'
        'Sign in with Google'
        '</a>'
        f'{err}'
        '</div></div>'
        '</body></html>'
    )


# ──────────────────────────────────────────────────────────────────────────────
# HUB PAGE
# ──────────────────────────────────────────────────────────────────────────────
_HUB_STYLES = """
<style>
@media(min-width:769px){.content{padding:32px 40px}}
.db-topbar{display:flex;gap:24px;align-items:baseline;margin-bottom:24px;padding-bottom:14px;border-bottom:1px solid var(--border)}
.db-kpi{display:flex;flex-direction:column}
.db-kpi-val{font-size:15px;font-weight:700;line-height:1}
.db-kpi-lbl{font-size:10px;color:var(--text3);margin-top:3px}
.db-main{display:grid;grid-template-columns:1fr 380px;gap:28px}
.db-sidebar{display:grid;grid-template-rows:1fr 1fr;gap:16px}
.db-tool-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:32px}
.db-pi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.db-ql-row{display:flex;gap:10px;flex-wrap:wrap}
@media(max-width:900px){.db-main{grid-template-columns:1fr}.db-sidebar{grid-template-rows:auto auto}}
@media(max-width:768px){
  .db-topbar{gap:10px;flex-wrap:wrap}
  .db-kpi{flex:1 1 calc(50% - 5px);min-width:0}
  .db-tool-grid{grid-template-columns:1fr;margin-bottom:20px}
  .db-pi-grid{grid-template-columns:repeat(2,1fr)}
  .db-card{padding:14px 16px}
  .db-card-row{gap:14px}
  .db-ql-row > a{flex:1 1 100%;min-width:0}
}
@media(max-width:500px){
  .db-kpi{flex-basis:100%}
  .db-pi-grid{grid-template-columns:1fr}
}
.db-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px 22px}
.db-card-hd{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;gap:12px}
.db-card-title{font-size:13px;font-weight:700;color:var(--text)}
.db-card-pill{font-size:10px;font-weight:600;padding:2px 8px;border-radius:4px}
.db-card-val{font-size:26px;font-weight:700;line-height:1}
.db-card-sub{font-size:11px;color:var(--text3);margin-top:6px}
.db-card-row{display:flex;gap:20px;margin-top:14px}
.db-card-mini{text-align:center}
.db-card-mini .n{font-size:15px;font-weight:700}
.db-card-mini .l{font-size:10px;color:var(--text3)}
.db-sect{font-size:11px;font-weight:700;text-transform:uppercase;color:var(--text3);margin:0 0 14px;letter-spacing:0.6px}
.db-link{text-decoration:none;display:flex;align-items:center;gap:8px;padding:10px 14px;transition:border-color .12s;flex:1;min-width:0}
.db-link:hover{border-color:var(--text3) !important}
.db-link-icon{font-size:18px;flex-shrink:0}
.db-link-txt{font-size:12px;font-weight:600;color:var(--text)}
.db-link-sub{font-size:9px;color:var(--text3)}
.db-empty{padding:60px 20px;text-align:center}
.db-empty-card{max-width:480px;margin:0 auto;padding:32px 28px}
.db-empty-title{font-size:20px;font-weight:700;margin-bottom:10px;color:var(--text)}
.db-empty-sub{font-size:13px;color:var(--text3);line-height:1.6}
</style>
"""


_HUB_EMPTY_BODY = (
    '<div class="db-empty"><div class="db-card db-empty-card">'
    '<div class="db-empty-title">Welcome to Reform</div>'
    '<div class="db-empty-sub">'
    'No sections are enabled for your account yet.<br>'
    'Contact an admin to request access to specific hubs.'
    '</div>'
    '</div></div>'
)


def _build_hub_body(allowed: set) -> str:
    """Render the dashboard body gated by the user's Allowed Hubs.
    Admins get the full set via `_get_allowed_hubs`; users with no hubs see
    the empty-state card."""
    if not allowed:
        return _HUB_STYLES + _HUB_EMPTY_BODY

    outreach = allowed & {"attorney", "guerilla", "community"}
    show_pi = "pi_cases" in allowed
    show_sidebar = bool(outreach or show_pi)
    show_calendar = "calendar" in allowed

    # KPI bar — each tile keyed to the hub that populates it
    kpi_tiles = []
    if outreach or show_pi:
        kpi_tiles.append('<div class="db-kpi"><div class="db-kpi-val" id="s-total">--</div><div class="db-kpi-lbl">Total Venues</div></div>')
    if outreach:
        kpi_tiles.append('<div class="db-kpi"><div class="db-kpi-val" id="s-active" style="color:#059669">--</div><div class="db-kpi-lbl">Active Relationships</div></div>')
    if show_pi:
        kpi_tiles.append('<div class="db-kpi"><div class="db-kpi-val" id="s-pipeline" style="color:#7c3aed">--</div><div class="db-kpi-lbl">PI Pipeline</div></div>')
    if outreach or show_pi:
        kpi_tiles.append('<div class="db-kpi"><div class="db-kpi-val" id="s-attention" style="color:#ef4444">--</div><div class="db-kpi-lbl">Needs Attention</div></div>')
    if "tickets" in allowed:
        kpi_tiles.append('<div class="db-kpi"><div class="db-kpi-val" id="s-tickets" style="color:#3b82f6">--</div><div class="db-kpi-lbl">Open Tickets</div></div>')
    if "leads" in allowed:
        kpi_tiles.append('<div class="db-kpi"><div class="db-kpi-val" id="s-leads" style="color:#db2777">--</div><div class="db-kpi-lbl">Open Leads</div></div>')
        kpi_tiles.append('<div class="db-kpi"><div class="db-kpi-val" id="s-leads-overdue" style="color:#ef4444">--</div><div class="db-kpi-lbl">Overdue Follow-ups</div></div>')
    if "tasks" in allowed:
        kpi_tiles.append('<div class="db-kpi"><div class="db-kpi-val" id="s-tasks" style="color:#2563eb">--</div><div class="db-kpi-lbl">My Tasks</div></div>')
    if "inbox" in allowed:
        kpi_tiles.append('<div class="db-kpi"><div class="db-kpi-val" id="s-activity" style="color:#059669">--</div><div class="db-kpi-lbl">Activity this Week</div></div>')
    kpi_bar = f'<div class="db-topbar">{"".join(kpi_tiles)}</div>' if kpi_tiles else ''

    # Outreach cards — one loader per allowed outreach hub; JS fills them in
    outreach_section = ''
    if outreach:
        loaders = '<div class="db-card"><div class="loading">Loading\u2026</div></div>' * len(outreach)
        outreach_section = (
            '<div class="db-sect">Outreach</div>'
            f'<div class="db-tool-grid" id="tool-cards">{loaders}</div>'
        )

    # PI Cases grid
    pi_section = ''
    if show_pi:
        pi_section = (
            '<div class="db-sect">PI Cases</div>'
            '<div class="db-pi-grid">'
            '<div class="db-card"><div class="db-card-hd"><span class="db-card-title">Active</span><span class="db-card-pill" style="background:#7c3aed22;color:#7c3aed">Treatment</span></div><div class="db-card-val" id="pi-active" style="color:#7c3aed">--</div></div>'
            '<div class="db-card"><div class="db-card-hd"><span class="db-card-title">Billed</span><span class="db-card-pill" style="background:#fbbf2422;color:#d97706">Pending</span></div><div class="db-card-val" id="pi-billed" style="color:#d97706">--</div></div>'
            '<div class="db-card"><div class="db-card-hd"><span class="db-card-title">Awaiting</span><span class="db-card-pill" style="background:#ea580c22;color:#ea580c">Negotiation</span></div><div class="db-card-val" id="pi-awaiting" style="color:#ea580c">--</div></div>'
            '<div class="db-card"><div class="db-card-hd"><span class="db-card-title">Closed</span><span class="db-card-pill" style="background:#05966922;color:#059669">Settled</span></div><div class="db-card-val" id="pi-closed" style="color:#059669">--</div></div>'
            '</div>'
        )

    # Sidebar: Priority Alerts + Upcoming (driven by outreach + PI data)
    sidebar = ''
    if show_sidebar:
        sidebar = (
            '<div class="db-sidebar">'
            '<div class="panel" style="margin:0;display:flex;flex-direction:column;overflow:hidden">'
            '<div class="panel-hd"><span class="panel-title">Priority Alerts</span><span class="panel-ct" id="alerts-ct">\u2014</span></div>'
            '<div class="panel-body" id="alerts-body" style="flex:1;overflow-y:auto"><div class="loading">Loading\u2026</div></div>'
            '</div>'
            '<div class="panel" style="margin:0;display:flex;flex-direction:column;overflow:hidden">'
            '<div class="panel-hd"><span class="panel-title">Upcoming This Week</span><span class="panel-ct" id="upcoming-ct">\u2014</span></div>'
            '<div class="panel-body" id="upcoming-body" style="flex:1;overflow-y:auto"><div class="loading">Loading\u2026</div></div>'
            '</div>'
            '</div>'
        )

    main_col = f'<div class="db-main"><div>{kpi_bar}{outreach_section}{pi_section}</div>{sidebar}</div>'

    # Quick Links — each link keyed to the hub that backs it
    ql_items = []
    if "guerilla" in allowed:
        ql_items.append('<a href="/outreach/planner" class="db-card db-link"><div class="db-link-icon">\U0001f5fa\ufe0f</div><div><div class="db-link-txt">Route Planner</div><div class="db-link-sub">Plan outreach routes</div></div></a>')
        ql_items.append('<a href="/outreach/list" class="db-card db-link"><div class="db-link-icon">\U0001f4cb</div><div><div class="db-link-txt">Routes List</div><div class="db-link-sub">All venues by status</div></div></a>')
    if "social" in allowed:
        ql_items.append('<a href="/social/poster" class="db-card db-link"><div class="db-link-icon">\U0001f3a8</div><div><div class="db-link-txt">Social Poster</div><div class="db-link-sub">Create content</div></div></a>')
        ql_items.append('<a href="/social" class="db-card db-link"><div class="db-link-icon">\U0001f4c5</div><div><div class="db-link-txt">Social Schedule</div><div class="db-link-sub">Content queue</div></div></a>')
    if "communications" in allowed:
        ql_items.append('<a href="/contacts" class="db-card db-link"><div class="db-link-icon">\U0001f4e7</div><div><div class="db-link-txt">Communications</div><div class="db-link-sub">Email contacts</div></div></a>')
    if "tickets" in allowed:
        ql_items.append('<a href="/tickets" class="db-card db-link"><div class="db-link-icon">\U0001f3ab</div><div><div class="db-link-txt">Tickets</div><div class="db-link-sub">Helpdesk queue</div></div></a>')
    if "leads" in allowed:
        ql_items.append('<a href="/leads" class="db-card db-link"><div class="db-link-icon">\U0001f4e5</div><div><div class="db-link-txt">Leads</div><div class="db-link-sub">Follow-up pipeline</div></div></a>')
    if "tasks" in allowed:
        ql_items.append('<a href="/tasks" class="db-card db-link"><div class="db-link-icon">\u2705</div><div><div class="db-link-txt">My Tasks</div><div class="db-link-sub">Open ClickUp tasks</div></div></a>')
    if "inbox" in allowed:
        ql_items.append('<a href="/inbox" class="db-card db-link"><div class="db-link-icon">\U0001f4ec</div><div><div class="db-link-txt">Inbox</div><div class="db-link-sub">All activity</div></div></a>')
    ql_section = (
        f'<div style="margin-top:24px"><div class="db-sect">Quick Links</div><div class="db-ql-row">{"".join(ql_items)}</div></div>'
        if ql_items else ''
    )

    cal_section = ''
    if show_calendar:
        cal_section = (
            '<div style="margin-top:24px">'
            '<div class="db-sect">Calendar</div>'
            '<div class="db-card" style="padding:0;overflow:hidden;height:clamp(260px,55vh,440px)" id="db-cal-wrap">'
            '<div class="loading" style="padding:20px">Loading calendar\u2026</div>'
            '</div></div>'
        )

    return _HUB_STYLES + main_col + ql_section + cal_section

# Shared calendar widget JS — used by both the dashboard (`_hub_page`) and the
# full `/calendar` page (`_calendar_page`). Expects a `<div id="db-cal-wrap">`
# somewhere in the body. Globals `esc` and `fetch` are the only dependencies.
_CAL_WIDGET_JS = """
// Calendar widget: mini month grid + upcoming events list
async function loadCalendarWidget() {
  var wrap = document.getElementById('db-cal-wrap');
  renderCalendarShell(wrap);
  try {
    var r = await fetch('/api/calendar/events');
    if (r.status === 401) {
      setCalendarError(wrap, 'Calendar access expired', 'Sign out to refresh \u2192');
      return;
    }
    if (!r.ok) {
      setCalendarError(wrap, "Couldn't load calendar", 'Sign out to re-authenticate \u2192');
      return;
    }
    var data = await r.json();
    populateCalendarEvents(wrap, data.items || []);
  } catch(e) {
    setCalendarError(wrap, 'Calendar unavailable', '');
  }
}

function renderCalendarShell(wrap) {
  var now = new Date();
  var year = now.getFullYear();
  var month = now.getMonth();
  var monthName = now.toLocaleDateString('en-US', {month:'long', year:'numeric'});
  var firstOfMonth = new Date(year, month, 1);
  var leadingBlanks = firstOfMonth.getDay();
  var daysInMonth   = new Date(year, month + 1, 0).getDate();
  var daysPrevMonth = new Date(year, month, 0).getDate();
  var todayKey = now.toISOString().substring(0, 10);

  var cells = '';
  for (var i = leadingBlanks - 1; i >= 0; i--) {
    var d = daysPrevMonth - i;
    cells += '<div class="cal-day-cell other-month">' + d + '</div>';
  }
  for (var d = 1; d <= daysInMonth; d++) {
    var dateKey = year + '-' + String(month + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
    var cls = 'cal-day-cell';
    if (dateKey === todayKey) cls += ' today';
    cells += '<div class="' + cls + '" data-date="' + dateKey + '">' + d + '</div>';
  }
  var totalCells = leadingBlanks + daysInMonth;
  var trailingBlanks = (7 - (totalCells % 7)) % 7;
  for (var d = 1; d <= trailingBlanks; d++) {
    cells += '<div class="cal-day-cell other-month">' + d + '</div>';
  }

  wrap.innerHTML = ''
    + '<div class="cal-wrap">'
    +   '<div class="cal-month">'
    +     '<div class="cal-month-hdr">'
    +       '<div class="cal-month-title">' + esc(monthName) + '</div>'
    +       '<a href="/calendar" class="cal-month-sub" style="text-decoration:none">Open \u2192</a>'
    +     '</div>'
    +     '<div class="cal-weekdays"><div>S</div><div>M</div><div>T</div><div>W</div><div>T</div><div>F</div><div>S</div></div>'
    +     '<div class="cal-days" id="cal-days">' + cells + '</div>'
    +   '</div>'
    +   '<div class="cal-upcoming" id="cal-upcoming">'
    +     '<div class="cal-empty-msg">Loading events\u2026</div>'
    +   '</div>'
    + '</div>';
}

function populateCalendarEvents(wrap, items) {
  var eventDays = new Set();
  items.forEach(function(ev) {
    var d;
    if (ev.allDay) d = (ev.start || '').substring(0, 10);
    else if (ev.start) d = new Date(ev.start).toISOString().substring(0, 10);
    else return;
    eventDays.add(d);
  });
  eventDays.forEach(function(dateKey) {
    var cell = wrap.querySelector('.cal-day-cell[data-date="' + dateKey + '"]');
    if (cell) cell.classList.add('has-events');
  });

  var upcoming = document.getElementById('cal-upcoming');
  if (!items.length) {
    upcoming.innerHTML = '<div class="cal-empty-msg">No upcoming events</div>';
    return;
  }
  var groups = {};
  var order  = [];
  items.slice(0, 10).forEach(function(ev) {
    var d;
    if (ev.allDay) d = (ev.start || '').substring(0, 10);
    else           d = new Date(ev.start).toISOString().substring(0, 10);
    if (!groups[d]) { groups[d] = []; order.push(d); }
    groups[d].push(ev);
  });
  var today = new Date();
  var todayKey = today.toISOString().substring(0, 10);
  var tomorrow = new Date(today.getTime() + 86400000).toISOString().substring(0, 10);

  var html = '<div class="cal-upcoming-hdr">Upcoming</div>';
  order.forEach(function(d) {
    var dateObj = new Date(d + 'T00:00:00');
    var label;
    if (d === todayKey)      label = 'Today';
    else if (d === tomorrow) label = 'Tomorrow';
    else label = dateObj.toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric'});
    html += '<div class="cal-day"><div class="cal-day-hdr">' + esc(label) + '</div>';
    groups[d].forEach(function(ev) {
      var timeStr;
      if (ev.allDay) timeStr = 'all day';
      else {
        var t = new Date(ev.start);
        timeStr = t.toLocaleTimeString('en-US', {hour:'numeric', minute:'2-digit'});
      }
      html += '<div class="cal-evt">';
      html += '<div class="cal-evt-time">' + esc(timeStr) + '</div>';
      html += '<div class="cal-evt-title">';
      if (ev.link) html += '<a href="' + esc(ev.link) + '" target="_blank" style="color:inherit">' + esc(ev.summary) + '</a>';
      else         html += esc(ev.summary);
      if (ev.location) html += '<div class="cal-evt-loc">' + esc(ev.location) + '</div>';
      html += '</div></div>';
    });
    html += '</div>';
  });
  upcoming.innerHTML = html;
}

function setCalendarError(wrap, title, linkText) {
  var upcoming = document.getElementById('cal-upcoming');
  var linkHtml = linkText ? '<a href="/logout">' + esc(linkText) + '</a>' : '';
  if (upcoming) {
    upcoming.innerHTML = '<div class="cal-empty-msg">' + esc(title) + '<br>' + linkHtml + '</div>';
  } else {
    wrap.innerHTML = '<div class="cal-err"><div>' + esc(title) + '</div>' + linkHtml + '</div>';
  }
}

loadCalendarWidget();
"""


def _hub_page(br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header">'
        '<div class="header-left">'
        '<h1>Dashboard</h1>'
        '<div class="sub">Reform Chiropractic Operations Hub</div>'
        '</div>'
        '<div class="header-right"></div>'
        '</div>'
    )
    allowed = set(_get_allowed_hubs(user) if user else [])
    body = _build_hub_body(allowed)

    if not allowed:
        return _page('hub', 'Dashboard', header, body, '', br, bt, user=user)

    allowed_json = json.dumps(sorted(allowed))
    cal_js = _CAL_WIDGET_JS if "calendar" in allowed else ''

    js = f"""
const ALLOWED = new Set({allowed_json});
const setText = (id, v) => {{ const el = document.getElementById(id); if (el) el.textContent = v; }};
const setHTML = (id, v) => {{ const el = document.getElementById(id); if (el) el.innerHTML = v; }};

const TOOLS = [
  {{key: 'att', hub: 'attorney',  label: 'PI Attorney',  color: '#7c3aed', activeStatus: 'Active Relationship', badge: 'b-pi',  short: 'PI', href: '/attorney'}},
  {{key: 'gor', hub: 'guerilla',  label: 'Guerilla Mktg', color: '#ea580c', activeStatus: 'Active Partner',      badge: 'b-gor', short: 'G',  href: '/guerilla'}},
  {{key: 'com', hub: 'community', label: 'Community',     color: '#059669', activeStatus: 'Active Partner',      badge: 'b-com', short: 'C',  href: '/community'}},
].filter(t => ALLOWED.has(t.hub));

async function load() {{
  var resp;
  for (var attempt = 0; attempt < 3; attempt++) {{
    try {{
      resp = await fetch('/api/dashboard');
      if (resp.ok) break;
    }} catch(e) {{}}
    if (attempt < 2) await new Promise(ok => setTimeout(ok, 1000 * (attempt + 1)));
  }}
  if (!resp || !resp.ok) return;
  const data = await resp.json();

  const stats = TOOLS.map(tool => {{
    const rows = data[tool.key] || [];
    let active = 0, overdue = 0, today = 0;
    const alerts = [], upcoming = [];
    for (const row of rows) {{
      const status = sv(row.cs);
      const du = daysUntil(row.fu);
      const name = esc(row.n || '(unnamed)');
      if (status === tool.activeStatus) active++;
      if (du !== null && du < 0)  {{ overdue++; alerts.push({{name, du, badge: tool.badge, short: tool.short}}); }}
      if (du === 0)                {{ today++;   alerts.push({{name, du, badge: tool.badge, short: tool.short}}); }}
      if (du !== null && du > 0 && du <= 7) {{ upcoming.push({{name, du, badge: tool.badge, short: tool.short, date: row.fu}}); }}
    }}
    return {{total: rows.length, active, overdue, today, alerts, upcoming, tool}};
  }});

  const totals = stats.reduce((a, s) => ({{
    total: a.total + s.total, active: a.active + s.active,
    overdue: a.overdue + s.overdue, today: a.today + s.today,
  }}), {{total:0, active:0, overdue:0, today:0}});

  let boxAlerts = 0;
  (data.boxes || []).forEach(b => {{
    if (sv(b.s) !== 'Active' || !b.d) return;
    const age = -(daysUntil(b.d) || 0);
    const pickupDays = parseInt(b.p) || 14;
    if (age >= pickupDays) boxAlerts++;
  }});

  setText('s-total', totals.total);
  setText('s-active', totals.active);
  setText('s-attention', totals.overdue + totals.today + boxAlerts);
  const pi = data.pi || {{}};
  setText('s-pipeline', (pi.a || 0) + (pi.b || 0) + (pi.w || 0));

  setText('pi-active',   pi.a || 0);
  setText('pi-billed',   pi.b || 0);
  setText('pi-awaiting', pi.w || 0);
  setText('pi-closed',   pi.c || 0);

  setHTML('tool-cards', stats.map(s => `
    <div class="db-card" style="border-left:3px solid ${{s.tool.color}}">
      <div class="db-card-hd">
        <span class="db-card-title">${{esc(s.tool.label)}}</span>
        <span class="db-card-pill" style="background:${{s.tool.color}}22;color:${{s.tool.color}}">${{s.active}} active</span>
      </div>
      <div class="db-card-row">
        <div class="db-card-mini"><div class="n">${{s.total}}</div><div class="l">Total</div></div>
        <div class="db-card-mini"><div class="n" style="color:#ef4444">${{s.overdue}}</div><div class="l">Overdue</div></div>
        <div class="db-card-mini"><div class="n" style="color:#f59e0b">${{s.today}}</div><div class="l">Today</div></div>
      </div>
      <a href="${{s.tool.href}}" style="display:block;text-align:center;margin-top:10px;font-size:11px;color:${{s.tool.color}};text-decoration:none;font-weight:600">Open Dashboard \u2192</a>
    </div>
  `).join(''));

  const allAlerts = stats.flatMap(s => s.alerts).sort((a,b) => a.du - b.du);
  setText('alerts-ct', allAlerts.length + ' items');
  setHTML('alerts-body', allAlerts.length ? allAlerts.slice(0,10).map(a => `
    <div class="a-row">
      <div class="dot ${{a.du < 0 ? 'dot-r' : 'dot-y'}}"></div>
      <span class="a-name">${{a.name}}</span>
      <span class="badge ${{a.badge}}">${{a.short}}</span>
      <span class="a-meta" style="color:${{a.du < 0 ? '#ef4444' : '#fbbf24'}}">${{a.du === 0 ? 'Today' : Math.abs(a.du) + 'd overdue'}}</span>
    </div>
  `).join('') : '<div class="empty">No overdue or due-today items \u2713</div>');

  const allUpcoming = stats.flatMap(s => s.upcoming).sort((a,b) => a.du - b.du);
  setText('upcoming-ct', allUpcoming.length + ' this week');
  setHTML('upcoming-body', allUpcoming.length ? allUpcoming.slice(0,10).map(a => `
    <div class="a-row">
      <div class="dot dot-g"></div>
      <span class="a-name">${{a.name}}</span>
      <span class="badge ${{a.badge}}">${{a.short}}</span>
      <span class="date-badge">${{fmt(a.date)}}</span>
    </div>
  `).join('') : '<div class="empty">Nothing due this week</div>');

  if (typeof stampRefresh === 'function') stampRefresh();
}}

load();

async function loadOpenTicketCount() {{
  if (!ALLOWED.has('tickets')) return;
  try {{
    const r = await fetch('/api/tickets');
    if (!r.ok) return;
    const rows = await r.json();
    const openSet = new Set(['Open', 'In Progress', 'Waiting']);
    const n = rows.filter(t => {{
      const s = t.Status; const v = (s && typeof s === 'object') ? s.value : s;
      return openSet.has(v);
    }}).length;
    const el = document.getElementById('s-tickets');
    if (el) el.textContent = n;
  }} catch(e) {{}}
}}
loadOpenTicketCount();

async function loadLeadStats() {{
  if (!ALLOWED.has('leads')) return;
  try {{
    const r = await fetch('/api/leads');
    if (!r.ok) return;
    const rows = await r.json();
    const openSet = new Set(['New','Contacted','Appointment Scheduled','Seen']);
    const today = new Date().toISOString().slice(0,10);
    let open = 0, overdue = 0;
    rows.forEach(l => {{
      const st = l.Status; const v = (st && typeof st === 'object') ? st.value : st;
      if (openSet.has(v)) {{
        open++;
        if (l['Follow-Up Date'] && l['Follow-Up Date'] < today) overdue++;
      }}
    }});
    const e1 = document.getElementById('s-leads');          if (e1) e1.textContent = open;
    const e2 = document.getElementById('s-leads-overdue');  if (e2) e2.textContent = overdue;
  }} catch(e) {{}}
}}
loadLeadStats();

async function loadTaskCount() {{
  if (!ALLOWED.has('tasks')) return;
  try {{
    const r = await fetch('/api/clickup/tasks');
    if (!r.ok) return;
    const data = await r.json();
    const n = (data.items || []).length;
    const el = document.getElementById('s-tasks');
    if (el) el.textContent = data.unmatched ? '\u2014' : n;
  }} catch(e) {{}}
}}
loadTaskCount();

async function loadActivityCount() {{
  if (!ALLOWED.has('inbox')) return;
  try {{
    const r = await fetch('/api/activities/stream?since=7d&kind=user_activity&limit=500');
    if (!r.ok) return;
    const data = await r.json();
    const el = document.getElementById('s-activity');
    if (el) el.textContent = (data.items || []).length;
  }} catch(e) {{}}
}}
loadActivityCount();

{cal_js}
"""
    return _page('hub', 'Dashboard', header, body, js, br, bt, user=user)


# ──────────────────────────────────────────────────────────────────────────────
# CALENDAR PAGE — full-page month view with slide-out day panel
# ──────────────────────────────────────────────────────────────────────────────
_FULL_CAL_JS = r"""
let _CF_VIEW = new Date();  // first day of the currently-shown month
_CF_VIEW.setDate(1);
let _CF_EVENTS_BY_DAY = {};  // 'YYYY-MM-DD' -> [eventObj, ...]
let _CF_SELECTED = null;     // 'YYYY-MM-DD' of day slid-out

function _cfMonthLabel(d) {
  return d.toLocaleDateString('en-US', {month:'long', year:'numeric'});
}
function _cfKey(d) {
  return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
}
function _cfFmtTime(iso, allDay) {
  if (allDay) return 'all day';
  try {
    const t = new Date(iso);
    return t.toLocaleTimeString('en-US', {hour:'numeric', minute:'2-digit'});
  } catch(e) { return ''; }
}

async function loadCalendarFull() {
  const wrap = document.getElementById('cf-month');
  if (!wrap) return;
  renderFullMonthShell();
  const year = _CF_VIEW.getFullYear();
  const month = _CF_VIEW.getMonth();
  // Fetch a generous window: 7 days before month start to 14 days after month end
  // (covers leading/trailing cells + any multi-week events).
  const start = new Date(year, month, -7);
  const end   = new Date(year, month + 1, 14);
  const startIso = start.toISOString();
  const endIso   = end.toISOString();

  try {
    const r = await fetch('/api/calendar/events?start=' + encodeURIComponent(startIso)
                          + '&end=' + encodeURIComponent(endIso) + '&max=500');
    if (r.status === 401) {
      document.getElementById('cf-month').innerHTML =
        '<div class="cal-err"><div>Calendar access expired</div><a href="/logout">Sign out to refresh &rarr;</a></div>';
      return;
    }
    if (!r.ok) {
      document.getElementById('cf-month').innerHTML =
        '<div class="cal-err"><div>Couldn\'t load calendar</div><a href="/logout">Re-authenticate &rarr;</a></div>';
      return;
    }
    const data = await r.json();
    bucketEvents(data.items || []);
    paintCells();
  } catch(e) {
    document.getElementById('cf-month').innerHTML =
      '<div class="cal-err"><div>Calendar unavailable</div></div>';
  }
}

function bucketEvents(items) {
  _CF_EVENTS_BY_DAY = {};
  items.forEach(function(ev) {
    let d;
    if (ev.allDay) d = (ev.start || '').substring(0, 10);
    else if (ev.start) {
      const dt = new Date(ev.start);
      d = dt.getFullYear() + '-' + String(dt.getMonth()+1).padStart(2,'0') + '-' + String(dt.getDate()).padStart(2,'0');
    }
    else return;
    if (!_CF_EVENTS_BY_DAY[d]) _CF_EVENTS_BY_DAY[d] = [];
    _CF_EVENTS_BY_DAY[d].push(ev);
  });
  // Sort each day by start time
  Object.values(_CF_EVENTS_BY_DAY).forEach(arr =>
    arr.sort((a,b) => (a.start||'').localeCompare(b.start||'')));
}

function renderFullMonthShell() {
  const v = _CF_VIEW;
  const year  = v.getFullYear();
  const month = v.getMonth();
  const firstOfMonth = new Date(year, month, 1);
  const leadingBlanks = firstOfMonth.getDay();
  const daysInMonth   = new Date(year, month + 1, 0).getDate();
  const todayKey = _cfKey(new Date());

  let cells = '';
  // leading cells from prev month
  for (let i = leadingBlanks - 1; i >= 0; i--) {
    const d = new Date(year, month, -i);
    const key = _cfKey(d);
    cells += `<div class="cf-cell other-month" data-date="${key}" onclick="selectDay('${key}')">
      <div class="cf-daynum">${d.getDate()}</div><div class="cf-chips" id="cf-${key}"></div></div>`;
  }
  for (let d = 1; d <= daysInMonth; d++) {
    const date = new Date(year, month, d);
    const key = _cfKey(date);
    const isToday = (key === todayKey);
    cells += `<div class="cf-cell${isToday ? ' today' : ''}" data-date="${key}" onclick="selectDay('${key}')">
      <div class="cf-daynum">${d}</div><div class="cf-chips" id="cf-${key}"></div></div>`;
  }
  const totalCells = leadingBlanks + daysInMonth;
  const trailingBlanks = (7 - (totalCells % 7)) % 7;
  for (let d = 1; d <= trailingBlanks; d++) {
    const date = new Date(year, month + 1, d);
    const key = _cfKey(date);
    cells += `<div class="cf-cell other-month" data-date="${key}" onclick="selectDay('${key}')">
      <div class="cf-daynum">${d}</div><div class="cf-chips" id="cf-${key}"></div></div>`;
  }

  document.getElementById('cf-title').textContent = _cfMonthLabel(v);
  document.getElementById('cf-month').innerHTML = `
    <div class="cf-weekdays"><div>Sun</div><div>Mon</div><div>Tue</div><div>Wed</div><div>Thu</div><div>Fri</div><div>Sat</div></div>
    <div class="cf-grid">${cells}</div>`;
}

function paintCells() {
  Object.keys(_CF_EVENTS_BY_DAY).forEach(function(key) {
    const slot = document.getElementById('cf-' + key);
    if (!slot) return;
    const evs = _CF_EVENTS_BY_DAY[key];
    const max = 3;
    const shown = evs.slice(0, max);
    let html = '';
    shown.forEach(function(ev) {
      const t = _cfFmtTime(ev.start, ev.allDay);
      const cls = ev.allDay ? 'cf-chip allday' : 'cf-chip';
      html += `<div class="${cls}" title="${escHtml(ev.summary)}"><span class="cf-chip-t">${escHtml(t)}</span> ${escHtml(ev.summary)}</div>`;
    });
    if (evs.length > max) {
      html += `<div class="cf-more">+${evs.length - max} more</div>`;
    }
    slot.innerHTML = html;
    slot.parentElement.classList.add('has-events');
  });
}

function escHtml(s) {
  return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function gotoPrevMonth() {
  _CF_VIEW = new Date(_CF_VIEW.getFullYear(), _CF_VIEW.getMonth() - 1, 1);
  loadCalendarFull();
}
function gotoNextMonth() {
  _CF_VIEW = new Date(_CF_VIEW.getFullYear(), _CF_VIEW.getMonth() + 1, 1);
  loadCalendarFull();
}
function gotoToday() {
  _CF_VIEW = new Date(); _CF_VIEW.setDate(1);
  loadCalendarFull();
}

function selectDay(key) {
  _CF_SELECTED = key;
  document.querySelectorAll('.cf-cell.selected').forEach(c => c.classList.remove('selected'));
  const cell = document.querySelector('.cf-cell[data-date="' + key + '"]');
  if (cell) cell.classList.add('selected');

  const panel = document.getElementById('cf-panel');
  const dateObj = new Date(key + 'T00:00:00');
  const dateLabel = dateObj.toLocaleDateString('en-US', {weekday:'long', month:'long', day:'numeric', year:'numeric'});
  document.getElementById('cf-panel-date').textContent = dateLabel;

  const list = document.getElementById('cf-panel-list');
  const evs = _CF_EVENTS_BY_DAY[key] || [];
  if (!evs.length) {
    list.innerHTML = `<div class="cf-panel-empty">No events this day.<br><button class="mt-btn primary" style="margin-top:14px" onclick="openMeetingModalForDay('${key}')">+ Schedule one</button></div>`;
  } else {
    list.innerHTML = evs.map(ev => {
      const t = _cfFmtTime(ev.start, ev.allDay);
      const loc = ev.location ? `<div class="cf-panel-loc">${escHtml(ev.location)}</div>` : '';
      const link = ev.link ? `<a href="${escHtml(ev.link)}" target="_blank" class="cf-panel-link">Open in Google Calendar &rarr;</a>` : '';
      const desc = ev.description ? `<div class="cf-panel-desc">${escHtml(ev.description).replace(/\n/g,'<br>')}</div>` : '';
      return `<div class="cf-panel-evt">
        <div class="cf-panel-t">${escHtml(t)}</div>
        <div class="cf-panel-title">${escHtml(ev.summary)}</div>
        ${loc}${desc}${link}
      </div>`;
    }).join('');
  }

  panel.classList.add('open');
}

function closeDayPanel() {
  document.getElementById('cf-panel').classList.remove('open');
  document.querySelectorAll('.cf-cell.selected').forEach(c => c.classList.remove('selected'));
  _CF_SELECTED = null;
}

// Prefill the meeting modal's date field when scheduling from a specific day.
function openMeetingModalForDay(key) {
  openMeetingModal();
  setTimeout(() => {
    const d = document.getElementById('mt-date');
    if (d) d.value = key;
  }, 60);
}

// After meeting modal saves, refresh the calendar so the new event shows up.
// The modal's submit-success path calls `loadActivities()` if defined.
function loadActivities() { loadCalendarFull(); }

document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape' && _CF_SELECTED) closeDayPanel();
});

loadCalendarFull();
"""


def _calendar_page(br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header">'
        '<div class="header-left">'
        '<h1>\U0001f4c5 Calendar</h1>'
        '<div class="sub">Month view of your Google Calendar</div>'
        '</div>'
        '<div class="header-right">'
        '<button class="mt-btn primary" onclick="openMeetingModal()">+ Add event</button>'
        '</div>'
        '</div>'
    )
    body = (
        '<div class="cf-page">'
          '<div class="cf-toolbar">'
            '<div class="cf-nav">'
              '<button class="cf-navbtn" onclick="gotoPrevMonth()" aria-label="Previous month">&lsaquo;</button>'
              '<button class="cf-todaybtn" onclick="gotoToday()">Today</button>'
              '<button class="cf-navbtn" onclick="gotoNextMonth()" aria-label="Next month">&rsaquo;</button>'
            '</div>'
            '<div class="cf-title" id="cf-title">\u2026</div>'
            '<div style="width:92px"></div>'  # spacer to center title
          '</div>'
          '<div class="db-card cf-card">'
            '<div id="cf-month"><div class="loading" style="padding:20px">Loading calendar\u2026</div></div>'
          '</div>'
          '<div class="cf-panel" id="cf-panel">'
            '<div class="cf-panel-hdr">'
              '<div class="cf-panel-date" id="cf-panel-date">\u2014</div>'
              '<button class="cf-panel-close" onclick="closeDayPanel()" aria-label="Close">\u00d7</button>'
            '</div>'
            '<div class="cf-panel-body" id="cf-panel-list"></div>'
            '<div class="cf-panel-foot">'
              '<button class="mt-btn primary" style="width:100%" onclick="openMeetingModalForDay(_CF_SELECTED)">+ Schedule on this day</button>'
            '</div>'
          '</div>'
        '</div>'
        + meeting_modal_html()
    )
    js = _FULL_CAL_JS + "\n" + meeting_modal_js()
    return _page('calendar', 'Calendar', header, body, js, br, bt, user=user)


# ──────────────────────────────────────────────────────────────────────────────
# COMING SOON PLACEHOLDER
# ──────────────────────────────────────────────────────────────────────────────
def _coming_soon_page(active_key: str, title: str, br: str, bt: str, user: dict = None) -> str:
    header = (
        f'<div class="header"><div class="header-left">'
        f'<h1>{title}</h1><div class="sub">Coming soon</div>'
        f'</div></div>'
    )
    body = '<div class="empty" style="padding:60px;font-size:15px">\U0001f6a7 This section is under construction</div>'
    return _page(active_key, title, header, body, '', br, bt, user=user)
