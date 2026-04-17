"""
Dashboard pages — login, hub overview, calendar, coming soon placeholders.
"""
import os

from .shared import _CSS, _page


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
_HUB_BODY = """
<style>
.content{padding:32px 40px !important}
.db-topbar{display:flex;gap:24px;align-items:baseline;margin-bottom:24px;padding-bottom:14px;border-bottom:1px solid var(--border)}
.db-kpi{display:flex;flex-direction:column}
.db-kpi-val{font-size:15px;font-weight:700;line-height:1}
.db-kpi-lbl{font-size:10px;color:var(--text3);margin-top:3px;white-space:nowrap}
.db-main{display:grid;grid-template-columns:1fr 380px;gap:28px}
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
.db-link-txt{font-size:12px;font-weight:600;color:var(--text);white-space:nowrap}
.db-link-sub{font-size:9px;color:var(--text3);white-space:nowrap}
</style>

<!-- Main 2-column layout -->
<div class="db-main">

  <!-- LEFT COLUMN -->
  <div>
    <!-- KPI bar -->
    <div class="db-topbar">
      <div class="db-kpi"><div class="db-kpi-val" id="s-total">--</div><div class="db-kpi-lbl">Total Venues</div></div>
      <div class="db-kpi"><div class="db-kpi-val" id="s-active" style="color:#059669">--</div><div class="db-kpi-lbl">Active Relationships</div></div>
      <div class="db-kpi"><div class="db-kpi-val" id="s-pipeline" style="color:#7c3aed">--</div><div class="db-kpi-lbl">PI Pipeline</div></div>
      <div class="db-kpi"><div class="db-kpi-val" id="s-attention" style="color:#ef4444">--</div><div class="db-kpi-lbl">Needs Attention</div></div>
    </div>

    <!-- Outreach tool cards -->
    <div class="db-sect">Outreach</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:32px" id="tool-cards">
      <div class="db-card"><div class="loading">Loading\u2026</div></div>
      <div class="db-card"><div class="loading">Loading\u2026</div></div>
      <div class="db-card"><div class="loading">Loading\u2026</div></div>
    </div>

    <!-- PI Cases -->
    <div class="db-sect">PI Cases</div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px">
      <div class="db-card">
        <div class="db-card-hd"><span class="db-card-title">Active</span><span class="db-card-pill" style="background:#7c3aed22;color:#7c3aed">Treatment</span></div>
        <div class="db-card-val" id="pi-active" style="color:#7c3aed">--</div>
      </div>
      <div class="db-card">
        <div class="db-card-hd"><span class="db-card-title">Billed</span><span class="db-card-pill" style="background:#fbbf2422;color:#d97706">Pending</span></div>
        <div class="db-card-val" id="pi-billed" style="color:#d97706">--</div>
      </div>
      <div class="db-card">
        <div class="db-card-hd"><span class="db-card-title">Awaiting</span><span class="db-card-pill" style="background:#ea580c22;color:#ea580c">Negotiation</span></div>
        <div class="db-card-val" id="pi-awaiting" style="color:#ea580c">--</div>
      </div>
      <div class="db-card">
        <div class="db-card-hd"><span class="db-card-title">Closed</span><span class="db-card-pill" style="background:#05966922;color:#059669">Settled</span></div>
        <div class="db-card-val" id="pi-closed" style="color:#059669">--</div>
      </div>
    </div>
  </div>

  <!-- RIGHT COLUMN (sidebar) -->
  <div style="display:grid;grid-template-rows:1fr 1fr;gap:16px">
    <!-- Priority Alerts -->
    <div class="panel" style="margin:0;display:flex;flex-direction:column;overflow:hidden">
      <div class="panel-hd">
        <span class="panel-title">Priority Alerts</span>
        <span class="panel-ct" id="alerts-ct">\u2014</span>
      </div>
      <div class="panel-body" id="alerts-body" style="flex:1;overflow-y:auto"><div class="loading">Loading\u2026</div></div>
    </div>

    <!-- Upcoming -->
    <div class="panel" style="margin:0;display:flex;flex-direction:column;overflow:hidden">
      <div class="panel-hd">
        <span class="panel-title">Upcoming This Week</span>
        <span class="panel-ct" id="upcoming-ct">\u2014</span>
      </div>
      <div class="panel-body" id="upcoming-body" style="flex:1;overflow-y:auto"><div class="loading">Loading\u2026</div></div>
    </div>
  </div>

</div>

<!-- Quick Links — horizontal row -->
<div style="margin-top:24px">
  <div class="db-sect">Quick Links</div>
  <div style="display:flex;gap:10px">
    <a href="/outreach/planner" class="db-card db-link">
      <div class="db-link-icon">\U0001f5fa\ufe0f</div>
      <div><div class="db-link-txt">Route Planner</div><div class="db-link-sub">Plan outreach routes</div></div>
    </a>
    <a href="/outreach/list" class="db-card db-link">
      <div class="db-link-icon">\U0001f4cb</div>
      <div><div class="db-link-txt">Routes List</div><div class="db-link-sub">All venues by status</div></div>
    </a>
    <a href="/social/poster" class="db-card db-link">
      <div class="db-link-icon">\U0001f3a8</div>
      <div><div class="db-link-txt">Social Poster</div><div class="db-link-sub">Create content</div></div>
    </a>
    <a href="/social" class="db-card db-link">
      <div class="db-link-icon">\U0001f4c5</div>
      <div><div class="db-link-txt">Social Schedule</div><div class="db-link-sub">Content queue</div></div>
    </a>
    <a href="/contacts" class="db-card db-link">
      <div class="db-link-icon">\U0001f4e7</div>
      <div><div class="db-link-txt">Communications</div><div class="db-link-sub">Email contacts</div></div>
    </a>
  </div>
</div>

<!-- Calendar — full width bottom -->
<div style="margin-top:24px">
  <div class="db-sect">Calendar</div>
  <div class="db-card" style="padding:0;overflow:hidden;height:440px" id="db-cal-wrap">
    <div class="loading" style="padding:20px">Loading calendar\u2026</div>
  </div>
</div>
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
    cal_url = os.environ.get("GOOGLE_CALENDAR_EMBED_URL", "")
    js = f"""
const TOOLS = [
  {{key: 'att', label: 'PI Attorney',  color: '#7c3aed', activeStatus: 'Active Relationship', badge: 'b-pi',  short: 'PI', href: '/attorney'}},
  {{key: 'gor', label: 'Guerilla Mktg', color: '#ea580c', activeStatus: 'Active Partner',      badge: 'b-gor', short: 'G',  href: '/guerilla'}},
  {{key: 'com', label: 'Community',      color: '#059669', activeStatus: 'Active Partner',      badge: 'b-com', short: 'C',  href: '/community'}},
];

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

  // Box alerts
  let boxAlerts = 0;
  (data.boxes || []).forEach(b => {{
    if (sv(b.s) !== 'Active' || !b.d) return;
    const age = -(daysUntil(b.d) || 0);
    const pickupDays = parseInt(b.p) || 14;
    if (age >= pickupDays) boxAlerts++;
  }});

  document.getElementById('s-total').textContent = totals.total;
  document.getElementById('s-active').textContent = totals.active;
  document.getElementById('s-attention').textContent = totals.overdue + totals.today + boxAlerts;
  document.getElementById('s-pipeline').textContent = (data.pi.a || 0) + (data.pi.b || 0) + (data.pi.w || 0);

  // PI counts
  document.getElementById('pi-active').textContent   = data.pi.a || 0;
  document.getElementById('pi-billed').textContent   = data.pi.b || 0;
  document.getElementById('pi-awaiting').textContent = data.pi.w || 0;
  document.getElementById('pi-closed').textContent   = data.pi.c || 0;

  // Tool cards
  document.getElementById('tool-cards').innerHTML = stats.map(s => `
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
  `).join('');

  // Alerts
  const allAlerts = stats.flatMap(s => s.alerts).sort((a,b) => a.du - b.du);
  document.getElementById('alerts-ct').textContent = allAlerts.length + ' items';
  document.getElementById('alerts-body').innerHTML = allAlerts.length ? allAlerts.slice(0,10).map(a => `
    <div class="a-row">
      <div class="dot ${{a.du < 0 ? 'dot-r' : 'dot-y'}}"></div>
      <span class="a-name">${{a.name}}</span>
      <span class="badge ${{a.badge}}">${{a.short}}</span>
      <span class="a-meta" style="color:${{a.du < 0 ? '#ef4444' : '#fbbf24'}}">${{a.du === 0 ? 'Today' : Math.abs(a.du) + 'd overdue'}}</span>
    </div>
  `).join('') : '<div class="empty">No overdue or due-today items \u2713</div>';

  // Upcoming
  const allUpcoming = stats.flatMap(s => s.upcoming).sort((a,b) => a.du - b.du);
  document.getElementById('upcoming-ct').textContent = allUpcoming.length + ' this week';
  document.getElementById('upcoming-body').innerHTML = allUpcoming.length ? allUpcoming.slice(0,10).map(a => `
    <div class="a-row">
      <div class="dot dot-g"></div>
      <span class="a-name">${{a.name}}</span>
      <span class="badge ${{a.badge}}">${{a.short}}</span>
      <span class="date-badge">${{fmt(a.date)}}</span>
    </div>
  `).join('') : '<div class="empty">Nothing due this week</div>';

  stampRefresh();
}}

load();

// Mini calendar
(function() {{
  var calUrl = '{cal_url}';
  var wrap = document.getElementById('db-cal-wrap');
  if (calUrl) {{
    wrap.innerHTML = '<iframe src="' + calUrl + '&mode=WEEK&showTabs=0&showTitle=0&showNav=0&showPrint=0&showCalendars=0&dates=20260101/20261231" '
      + 'style="width:100%;height:100%;border:none" frameborder="0" scrolling="no"></iframe>';
  }} else {{
    wrap.innerHTML = '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:var(--text3);font-size:12px">'
      + '<div style="font-size:28px;margin-bottom:8px">\U0001f4c5</div>'
      + '<div>Calendar not configured</div>'
      + '<a href="/calendar" style="color:#ea580c;font-size:11px;margin-top:4px">Set up calendar \u2192</a></div>';
  }}
}})();
"""
    return _page('hub', 'Dashboard', header, _HUB_BODY, js, br, bt, user=user)


# ──────────────────────────────────────────────────────────────────────────────
# CALENDAR PAGE
# ──────────────────────────────────────────────────────────────────────────────
def _calendar_page(br: str, bt: str, user: dict = None) -> str:
    embed_url = os.environ.get("GOOGLE_CALENDAR_EMBED_URL", "")
    header = (
        '<div class="header"><div class="header-left">'
        '<h1>\U0001f4c5 Calendar</h1>'
        '<div class="sub">Follow-up and scheduling calendar</div>'
        '</div></div>'
    )
    if embed_url:
        body = (
            '<div style="padding:16px 18px;height:calc(100vh - 120px)">'
            f'<iframe src="{embed_url}" style="width:100%;height:100%;border:none;border-radius:10px" '
            'frameborder="0" scrolling="no"></iframe>'
            '</div>'
        )
    else:
        body = (
            '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;'
            'padding:80px 20px;text-align:center">'
            '<div style="font-size:48px;margin-bottom:16px">\U0001f4c5</div>'
            '<div style="font-size:16px;font-weight:700;margin-bottom:8px">Calendar Not Configured</div>'
            '<div style="font-size:13px;color:var(--text3);max-width:440px;line-height:1.6">'
            'Add <code style="background:var(--card);padding:2px 6px;border-radius:4px;font-size:12px">GOOGLE_CALENDAR_EMBED_URL</code> '
            'to the <code style="background:var(--card);padding:2px 6px;border-radius:4px;font-size:12px">outreach-hub-secrets</code> Modal secret.<br><br>'
            'Get the embed URL from Google Calendar: open the calendar, click \u22ef \u2192 Settings \u2192 '
            'scroll to &ldquo;Integrate calendar&rdquo; \u2192 copy the <strong>Public URL to this calendar</strong> or <strong>Embed code</strong> src.</div>'
            '</div>'
        )
    return _page('calendar', 'Calendar', header, body, '', br, bt, user=user)


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
