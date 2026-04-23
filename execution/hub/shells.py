"""
Page shells for the Reform Operations Hub.
- `_page`: full desktop page (CSS + nav + compose FAB + theme toggle)
- `_forbidden_page`: 403 for users lacking hub access
- `_mobile_page`: lightweight /m page with bottom nav
- `_tool_page`: shared pipeline dashboard used by attorney / gorilla / community
"""

from .access import _is_admin
from .compose import _COMPOSE_HTML, _COMPOSE_JS
from .constants import (
    T_ATT_ACTS, T_ATT_VENUES, T_COM_ACTS, T_COM_VENUES,
    T_GOR_ACTS, T_GOR_BOXES, T_GOR_VENUES,
)
from .nav import _topnav
from .styles import _CSS, _JS_SHARED


# ─── Page shell ────────────────────────────────────────────────────────────────
def _page(active: str, title: str, header_html: str, body_html: str,
          script_js: str, br: str, bt: str, user: dict = None) -> str:
    shared = _JS_SHARED.format(br=br, bt=bt)
    user = user or {}
    admin = _is_admin(user)
    role_css = '' if admin else '.admin-only{display:none!important}'
    role_js = f'var IS_ADMIN = {"true" if admin else "false"};'
    return (
        '<!DOCTYPE html><html lang="en">'
        '<head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{title} \u2014 Reform Hub</title>'
        f'<style>{_CSS}\n{role_css}</style>'
        '<script>(function(){{'
        'var t=localStorage.getItem("hub-theme");'
        'if(t==="light"){{document.documentElement.setAttribute("data-theme","light");'
        'var ic=document.getElementById("theme-icon");if(ic)ic.textContent="\u2600\ufe0f";}}'
        '}})()</script>'
        '</head><body>'
        + _topnav(active, user)
        + '<div class="main">'
        + header_html
        + '<div class="content">'
        + body_html
        + '</div></div>'
        + _COMPOSE_HTML
        + '<script>'
        'function toggleTheme(){'
        'var d=document.documentElement;'
        'var cur=d.getAttribute("data-theme");'
        'var t=cur==="light"?"dark":"light";'
        'd.setAttribute("data-theme",t==="dark"?"":"light");'
        'var ic=document.getElementById("theme-icon");'
        'if(ic)ic.textContent=t==="light"?"\u2600\ufe0f":"\U0001f319";'
        'localStorage.setItem("hub-theme",t);}'
        'function openDrawer(){'
        'document.getElementById("drawer-nav").classList.add("open");'
        'document.getElementById("drawer-backdrop").classList.add("open");}'
        'function closeDrawer(){'
        'document.getElementById("drawer-nav").classList.remove("open");'
        'document.getElementById("drawer-backdrop").classList.remove("open");}'
        f'</script>'
        + f'<script>{role_js}\n{shared}\n{_COMPOSE_JS}\n{script_js}</script>'
        '</body></html>'
    )

def _forbidden_page(br: str, bt: str, user: dict = None) -> str:
    """403 page shown when user lacks hub access."""
    header = (
        '<div class="header"><div class="header-left">'
        '<h1>Access Restricted</h1>'
        '<div class="sub">You don\'t have permission to view this section</div>'
        '</div></div>'
    )
    body = (
        '<div style="display:flex;flex-direction:column;align-items:center;'
        'justify-content:center;padding:80px 20px;text-align:center">'
        '<div style="font-size:48px;margin-bottom:16px">\U0001f512</div>'
        '<div style="font-size:16px;font-weight:700;margin-bottom:8px;color:var(--text)">'
        'This section is not available to your account</div>'
        '<div style="font-size:13px;color:var(--text3);max-width:400px;line-height:1.6">'
        'Your administrator has not granted you access to this area. '
        'Contact your admin to request access.</div>'
        '<a href="/" style="margin-top:20px;color:#3b82f6;font-size:13px;'
        'font-weight:600;text-decoration:none">\u2190 Back to Dashboard</a>'
        '</div>'
    )
    return _page('', 'Access Restricted', header, body, '', br, bt, user=user)


# ─── Mobile page shell ────────────────────────────────────────────────────────────
def _build_mobile_drawer(active: str, user: dict) -> str:
    """Slide-out drawer for the routes mobile app. Mirrors the hub's tnav-drawer
    pattern but slides in from the left. Admin-only items are gated."""
    admin = _is_admin(user)

    def link(aid: str, label: str, href: str, grp: bool = False) -> str:
        cls_parts = []
        if grp:
            cls_parts.append('tnav-grp-lbl')
        if aid and aid == active:
            cls_parts.append('active')
        cls = f' class="{" ".join(cls_parts)}"' if cls_parts else ''
        return f'<a href="{href}"{cls}>{label}</a>'

    sep = '<div class="tnav-sep"></div>'
    items = (
        link('m_home',         '🏠 Dashboard',         '/',              grp=True)
        + link('m_routes',     '🗺️ Routes',       '/routes',        grp=True)
        + link('m_outreach',   '📞 Outreach Due',       '/outreach',      grp=True)
        + link('m_recent',     '⏱️ Recent Activity',  '/recent',        grp=True)
        + sep
        + (link('m_map',       '📍 Full Venue Map',     '/map') if admin else '')
        + link('m_outreach_map','📍 Outreach Map',      '/outreach/map')
        + sep
        + link('m_lead',       '📋 Capture Lead',       '/lead')
        + link('m_directory',  '📇 All Companies',      '/directory')
        + sep
        + '<a href="https://hub.reformchiropractic.app">💻 Full Hub</a>'
        '<a href="/logout" style="color:var(--text3)">Sign Out</a>'
    )
    return (
        '<div class="m-drawer-backdrop" id="m-drawer-backdrop" onclick="closeMDrawer()"></div>'
        '<div class="m-drawer" id="m-drawer">'
        '<div class="m-drawer-hdr">'
        '<span class="tnav-logo">✦ Reform</span>'
        '<button class="tnav-drawer-close" onclick="closeMDrawer()">✕</button>'
        '</div>'
        + items
        + '</div>'
    )


def _mobile_page(active: str, title: str, body_html: str, script_js: str,
                 br: str, bt: str, user: dict = None, wrap_cls: str = '',
                 extra_html: str = '', extra_js: str = '') -> str:
    """Page shell for the routes mobile app. Hamburger + slide-out drawer. Dark only."""
    shared = _JS_SHARED.format(br=br, bt=bt)
    user = user or {}
    drawer = _build_mobile_drawer(active, user)
    wrap_class = f'mobile-wrap {wrap_cls}'.strip()
    return (
        '<!DOCTYPE html><html lang="en">'
        '<head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">'
        f'<title>{title} — Reform</title>'
        f'<style>{_CSS}</style>'
        '</head><body>'
        + drawer
        + f'<div class="{wrap_class}">'
        + body_html
        + '</div>'
        + extra_html
        + f'<script>{shared}\n{extra_js}\n{script_js}\n'
        'function openMDrawer(){'
        'document.getElementById("m-drawer").classList.add("open");'
        'document.getElementById("m-drawer-backdrop").classList.add("open");}'
        'function closeMDrawer(){'
        'document.getElementById("m-drawer").classList.remove("open");'
        'document.getElementById("m-drawer-backdrop").classList.remove("open");}'
        '</script>'
        '</body></html>'
    )

# ─── Tool Dashboard ───────────────────────────────────────────────────────────
_TOOL_BODY = """
<div class="stats-row" id="stats-row">
  <div class="loading" style="padding:16px">Loading\u2026</div>
</div>

<div class="panel" style="margin-bottom:16px">
  <div class="panel-hd"><span class="panel-title">Pipeline</span></div>
  <div id="pipeline" class="pipeline"><div class="loading">Loading\u2026</div></div>
</div>

<div class="two-col">
  <div class="col-l">
    <div class="panel">
      <div class="panel-hd">
        <span class="panel-title">\U0001f534 Needs Attention</span>
        <span class="panel-ct" id="attn-ct">\u2014</span>
      </div>
      <div class="panel-body" id="attn-body"><div class="loading">Loading\u2026</div></div>
    </div>
  </div>
  <div class="col-r">
    <div class="panel">
      <div class="panel-hd">
        <span class="panel-title">\U0001f4c5 Upcoming Callbacks</span>
        <span class="panel-ct" id="cb-ct">\u2014</span>
      </div>
      <div class="panel-body" id="cb-body"><div class="loading">Loading\u2026</div></div>
    </div>
  </div>
</div>

<div class="two-col">
  <div class="col-l">
    <div class="panel">
      <div class="panel-hd"><span class="panel-title">By Type</span></div>
      <div class="panel-body" id="type-body"><div class="loading">Loading\u2026</div></div>
    </div>
  </div>
  <div class="col-r">
    <div class="panel">
      <div class="panel-hd">
        <span class="panel-title">Recent Activity</span>
        <span class="panel-ct" id="act-ct">\u2014</span>
      </div>
      <div class="panel-body" id="act-body"><div class="loading">Loading\u2026</div></div>
    </div>
  </div>
</div>
"""

def _tool_page(tool_key: str, br: str, bt: str, user: dict = None) -> str:
    CFG = {
        'attorney': {
            'label':        'PI Attorney',
            'color':        '#7c3aed',
            'venues_t':     T_ATT_VENUES,
            'acts_t':       T_ATT_ACTS,
            'boxes_t':      0,
            'name_field':   'Law Firm Name',
            'link_field':   'Law Firm',
            'active_status':'Active Relationship',
            'stages':       ['Not Contacted','Contacted','In Discussion','Active Relationship'],
            'stage_colors': ['#475569','#2563eb','#d97706','#059669'],
            'active_key':   'hub',
        },
        'gorilla': {
            'label':        'Guerilla Marketing',
            'color':        '#ea580c',
            'venues_t':     T_GOR_VENUES,
            'acts_t':       T_GOR_ACTS,
            'boxes_t':      T_GOR_BOXES,
            'name_field':   'Name',
            'link_field':   'Business',
            'active_status':'Active Partner',
            'stages':       ['Not Contacted','Contacted','In Discussion','Active Partner'],
            'stage_colors': ['#475569','#2563eb','#d97706','#059669'],
        },
        'community': {
            'label':        'Community Outreach',
            'color':        '#059669',
            'venues_t':     T_COM_VENUES,
            'acts_t':       T_COM_ACTS,
            'boxes_t':      0,
            'name_field':   'Name',
            'link_field':   'Organization',
            'active_status':'Active Partner',
            'stages':       ['Not Contacted','Contacted','In Discussion','Active Partner'],
            'stage_colors': ['#475569','#2563eb','#d97706','#059669'],
        },
    }
    c = CFG[tool_key]

    import json as _json
    stages_json      = _json.dumps(c['stages'])
    stage_colors_json = _json.dumps(c['stage_colors'])

    header = (
        f'<div class="header">'
        f'<div class="header-left">'
        f'<h1>{c["label"]}</h1>'
        f'<div class="sub">Pipeline &amp; outreach dashboard</div>'
        f'</div>'
        f'</div>'
    )

    js = f"""
const TOOL = {{
  venuesT:      {c['venues_t']},
  actsT:        {c['acts_t']},
  boxesT:       {c['boxes_t']},
  nameField:    '{c['name_field']}',
  linkField:    '{c['link_field']}',
  activeStatus: '{c['active_status']}',
  color:        '{c['color']}',
  stages:       {stages_json},
  stageColors:  {stage_colors_json},
}};

async function load() {{
  const [venues, acts] = await Promise.all([
    fetchAll(TOOL.venuesT),
    fetchAll(TOOL.actsT),
  ]);
  const boxes = TOOL.boxesT ? await fetchAll(TOOL.boxesT) : [];
  const activeBoxes = boxes.filter(b => sv(b['Status']) === 'Active').length;

  // Stats
  let active=0, overdue=0, todayCount=0, weekCount=0;
  const attnItems=[], cbItems=[];
  const typeCounts = {{}};

  for (const row of venues) {{
    const status = sv(row['Contact Status']);
    const du = daysUntil(row['Follow-Up Date']);
    const name = esc(row[TOOL.nameField] || '(unnamed)');
    const type = sv(row['Type']) || 'Other';

    if (status === TOOL.activeStatus) active++;
    typeCounts[type] = (typeCounts[type] || 0) + 1;

    if (du !== null && du < 0)  {{ overdue++;    attnItems.push({{name, du, status}}); }}
    if (du === 0)               {{ todayCount++; attnItems.push({{name, du, status}}); }}
    if (du !== null && du > 0 && du <= 14) {{ weekCount++; cbItems.push({{name, du, date: row['Follow-Up Date'], status}}); }}
  }}

  attnItems.sort((a,b) => a.du - b.du);
  cbItems.sort((a,b) => a.du - b.du);

  // Stats chips
  let statsHtml = `
    <div class="stat-chip">          <div class="label">Total</div>         <div class="value">${{venues.length}}</div></div>
    <div class="stat-chip c-green">  <div class="label">Active</div>        <div class="value">${{active}}</div></div>
    <div class="stat-chip c-red">    <div class="label">Overdue</div>       <div class="value">${{overdue}}</div></div>
    <div class="stat-chip c-yellow"> <div class="label">Due This Week</div> <div class="value">${{weekCount}}</div></div>
  `;
  if (TOOL.boxesT) {{
    statsHtml += `<div class="stat-chip c-orange"><div class="label">Active Boxes</div><div class="value">${{activeBoxes}}</div></div>`;
  }}
  document.getElementById('stats-row').innerHTML = statsHtml;

  // Pipeline
  const stageCounts = {{}};
  TOOL.stages.forEach(s => stageCounts[s] = 0);
  venues.forEach(row => {{
    const s = sv(row['Contact Status']) || 'Not Contacted';
    if (stageCounts[s] !== undefined) stageCounts[s]++;
    else stageCounts['Not Contacted'] = (stageCounts['Not Contacted'] || 0) + 1;
  }});
  const total = venues.length || 1;
  document.getElementById('pipeline').innerHTML = TOOL.stages.map((stage, i) => {{
    const n = stageCounts[stage] || 0;
    const pct = Math.round(n / total * 100);
    return `<div class="pipe-row">
      <span class="pipe-label">${{esc(stage)}}</span>
      <div class="pipe-bar"><div class="pipe-fill" style="width:${{pct}}%;background:${{TOOL.stageColors[i]}}"></div></div>
      <span class="pipe-n">${{n}}</span>
      <span class="pipe-pct">${{pct}}%</span>
    </div>`;
  }}).join('');

  // Needs Attention
  document.getElementById('attn-ct').textContent = attnItems.length + ' items';
  document.getElementById('attn-body').innerHTML = attnItems.length ? attnItems.map(a => `
    <div class="a-row">
      <div class="dot ${{a.du < 0 ? 'dot-r' : 'dot-y'}}"></div>
      <span class="a-name">${{a.name}}</span>
      <span class="a-meta" style="color:${{a.du < 0 ? '#ef4444':'#fbbf24'}}">${{a.du === 0 ? 'Today' : Math.abs(a.du) + 'd overdue'}}</span>
    </div>
  `).join('') : '<div class="empty">All caught up \u2713</div>';

  // Upcoming Callbacks
  document.getElementById('cb-ct').textContent = cbItems.length + ' in 14 days';
  document.getElementById('cb-body').innerHTML = cbItems.length ? cbItems.map(a => `
    <div class="a-row">
      <div class="dot dot-g"></div>
      <span class="a-name">${{a.name}}</span>
      <span class="date-badge">${{fmt(a.date)}}</span>
      <span class="a-meta">in ${{a.du}}d</span>
    </div>
  `).join('') : '<div class="empty">No upcoming callbacks</div>';

  // By Type
  const typeEntries = Object.entries(typeCounts).sort((a,b) => b[1]-a[1]);
  document.getElementById('type-body').innerHTML = typeEntries.length ? typeEntries.map(([t,n]) => `
    <div class="type-row">
      <span class="type-name">${{esc(t)}}</span>
      <span class="type-n">${{n}}</span>
    </div>
  `).join('') : '<div class="empty">No data</div>';

  // Recent Activity
  const sorted = [...acts].sort((a,b) => (b['Date']||'').localeCompare(a['Date']||'')).slice(0,15);
  document.getElementById('act-ct').textContent = acts.length + ' total';
  document.getElementById('act-body').innerHTML = sorted.length ? sorted.map(a => {{
    // Link field contains array of linked rows
    const links = a[TOOL.linkField] || [];
    const linkedName = links.length ? esc(links[0]['value'] || links[0]['display_value'] || '') : '\u2014';
    return `<div class="act-row">
      <span class="act-date">${{fmt(a['Date'])}}</span>
      <div class="act-body">
        <div class="act-name">${{linkedName}}</div>
        <div class="act-type">${{esc(sv(a['Type']))}}${{a['Outcome'] ? ' \u00b7 ' + esc(sv(a['Outcome'])) : ''}}</div>
      </div>
    </div>`;
  }}).join('') : '<div class="empty">No activities logged</div>';

  stampRefresh();
}}

load();
"""
    return _page(tool_key, c['label'], header, _TOOL_BODY, js, br, bt, user=user)
