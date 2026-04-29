"""Recent activity — unified feed across activities, events, and leads."""

from hub.shared import (
    _mobile_page,
    T_GOR_VENUES, T_GOR_ACTS, T_EVENTS, T_LEADS,
)
from hub.guerilla import GFR_EXTRA_HTML, GFR_EXTRA_JS


def _mobile_recent_page(br: str, bt: str, user: dict = None) -> str:
    user = user or {}
    user_name = user.get('name', '')
    user_email = (user.get('email', '') or '').strip().lower()
    body = (
        '<div class="mobile-hdr">'
        '<div><div class="mobile-hdr-title">Recent Activity</div>'
        '<div class="mobile-hdr-sub">Latest field-rep logs across activities, events, and leads</div></div>'
        '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        '</div>'
        '<div class="mobile-body">'
        '<div class="stats-row" style="margin-bottom:14px">'
        '<div class="stat-chip c-blue"><div class="label">Today</div><div class="value" id="rec-kpi-today">—</div></div>'
        '<div class="stat-chip c-green"><div class="label">This Week</div><div class="value" id="rec-kpi-week">—</div></div>'
        '<div class="stat-chip c-orange"><div class="label">By You</div><div class="value" id="rec-kpi-mine">—</div></div>'
        '</div>'
        # Kind filter chips
        '<div id="rec-kind-chips" style="display:flex;gap:6px;overflow-x:auto;padding-bottom:6px;'
        'margin-bottom:8px;-webkit-overflow-scrolling:touch"></div>'
        '<div id="recent-body">'
        '<div class="loading">Loading…</div>'
        '</div>'
        '</div>'
    )
    recent_js = f"""
const MY_NAME  = {repr(user_name)};
const MY_EMAIL = {repr(user_email)};
const KIND_LABELS = {{
  'activity': '✍️ Activity',
  'event':    '\U0001f4c5 Event',
  'lead':     '\U0001f3af Lead',
}};
const KIND_COLORS = {{
  'activity': '#3b82f6',
  'event':    '#8b5cf6',
  'lead':     '#ea580c',
}};

var _items = [];        // unified, sorted newest-first
var _filterKind = 'all';

function svJS(v) {{
  if (!v) return '';
  if (typeof v === 'object' && !Array.isArray(v)) return v.value || '';
  return String(v);
}}

function _firstLine(s) {{
  if (!s) return '';
  var i = String(s).indexOf('\\n');
  return i < 0 ? String(s) : String(s).slice(0, i);
}}

// Find "Submitted by: <name>" inside a multi-line summary blob. Activities
// don't have an Owner column so this is the only signal of who logged it.
function _submittedBy(summary) {{
  if (!summary) return '';
  var m = String(summary).match(/Submitted by:\\s*([^\\n]+)/i);
  return m ? m[1].trim() : '';
}}

function _byMe(who) {{
  if (!who) return false;
  var w = String(who).toLowerCase();
  if (MY_EMAIL && w.indexOf(MY_EMAIL) !== -1) return true;
  if (MY_NAME  && w.indexOf(MY_NAME.toLowerCase()) !== -1) return true;
  return false;
}}

// ── Normalize each source into a common item shape ──────────────────
function _actToItem(a) {{
  var sf = svJS(a['Source Form']) || svJS(a['Type']) || 'Activity';
  var biz = (a['Business'] && a['Business'].length) ? (a['Business'][0].value || '') : '';
  var who = a['Created By'] || _submittedBy(a['Summary']);
  return {{
    kind:     'activity',
    id:       a.id,
    title:    sf,
    subtitle: biz || _firstLine(a['Summary']) || '',
    meta:     [svJS(a['Outcome']), a['Contact Person']].filter(Boolean).join(' · '),
    date:     (a['Created'] || a['Date'] || '').slice(0, 10),
    sortKey:  a['Created'] || a['Date'] || '',
    who:      who,
    href:     null,
  }};
}}

function _evtToItem(e) {{
  var et  = svJS(e['Event Type']) || 'Event';
  var es  = svJS(e['Event Status']);
  var biz = (e['Business'] && e['Business'].length) ? (e['Business'][0].value || '') : '';
  var name = e['Name'] || biz || et;
  return {{
    kind:     'event',
    id:       e.id,
    title:    name,
    subtitle: et + (biz && biz !== name ? ' · ' + biz : ''),
    meta:     [es, e['Event Date']].filter(Boolean).join(' · '),
    date:     (e['Created'] || e['Event Date'] || '').slice(0, 10),
    sortKey:  e['Created'] || e['Event Date'] || '',
    who:      e['Created By'] || '',
    href:     '/events#' + e.id,
  }};
}}

function _leadToItem(L) {{
  var nm = L['Name'] || '(no name)';
  var st = svJS(L['Status']) || 'New';
  var src = L['Source'] || '';
  return {{
    kind:     'lead',
    id:       L.id,
    title:    nm,
    subtitle: [L['Phone'], svJS(L['Reason'])].filter(Boolean).join(' · '),
    meta:     [st, src].filter(Boolean).join(' · '),
    date:     (L['Created'] || '').slice(0, 10),
    sortKey:  L['Created'] || '',
    who:      L['Owner'] || '',
    href:     '/lead#' + L.id,
  }};
}}

// ── KPI compute ──────────────────────────────────────────────────────
function recomputeKpis() {{
  var today = new Date().toISOString().slice(0, 10);
  var weekAgo = new Date(Date.now() - 7*86400000).toISOString().slice(0, 10);
  var kT = 0, kW = 0, kM = 0;
  _items.forEach(function(it) {{
    if (it.date === today) kT++;
    if (it.date >= weekAgo) kW++;
    if (_byMe(it.who)) kM++;
  }});
  document.getElementById('rec-kpi-today').textContent = kT;
  document.getElementById('rec-kpi-week').textContent  = kW;
  document.getElementById('rec-kpi-mine').textContent  = kM;
}}

// ── Kind filter chips ────────────────────────────────────────────────
function renderKindChips() {{
  var box = document.getElementById('rec-kind-chips');
  if (!box) return;
  var entries = [
    {{key: 'all',      label: 'All',         color: '#64748b'}},
    {{key: 'activity', label: KIND_LABELS.activity, color: KIND_COLORS.activity}},
    {{key: 'event',    label: KIND_LABELS.event,    color: KIND_COLORS.event}},
    {{key: 'lead',     label: KIND_LABELS.lead,     color: KIND_COLORS.lead}},
  ];
  box.innerHTML = entries.map(function(e) {{
    var active = (e.key === _filterKind);
    var bg = active ? e.color : 'var(--bg)';
    var fg = active ? '#fff' : 'var(--text2)';
    return '<button onclick="setKindFilter(\\''+ e.key +'\\')" '
         + 'style="flex:0 0 auto;background:'+bg+';color:'+fg+';border:1px solid '+e.color+';'
         + 'border-radius:14px;padding:5px 12px;font-size:12px;font-weight:600;cursor:pointer;'
         + 'white-space:nowrap;font-family:inherit">'+e.label+'</button>';
  }}).join('');
}}

function setKindFilter(k) {{
  _filterKind = k;
  renderKindChips();
  renderFeed();
}}

// ── Render the feed ──────────────────────────────────────────────────
function renderFeed() {{
  var body = document.getElementById('recent-body');
  if (!body) return;
  var rows = _items.slice();
  if (_filterKind !== 'all') {{
    rows = rows.filter(function(it) {{ return it.kind === _filterKind; }});
  }}
  rows = rows.slice(0, 30);
  if (!rows.length) {{
    body.innerHTML = '<div class="empty">No matching activity.</div>';
    return;
  }}
  body.innerHTML = rows.map(function(it) {{
    var color = KIND_COLORS[it.kind] || '#64748b';
    var label = KIND_LABELS[it.kind] || it.kind;
    var line = '<span style="background:'+color+'22;color:'+color+';font-size:10px;padding:2px 7px;'
             + 'border-radius:4px;font-weight:700;text-transform:uppercase;letter-spacing:.3px">'
             + esc(label) + '</span>';
    var titleHtml = it.href
      ? '<a href="'+esc(it.href)+'" style="color:var(--text);text-decoration:none">'+esc(it.title)+'</a>'
      : esc(it.title);
    return '<div style="padding:10px 0;border-bottom:1px solid var(--border)">'
         + '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:2px">'
         + '<span style="font-weight:600">' + titleHtml + '</span>'
         + line
         + '</div>'
         + (it.subtitle ? '<div style="color:var(--text2);font-size:12px">'+esc(it.subtitle)+'</div>' : '')
         + '<div style="color:var(--text3);font-size:11px;margin-top:2px">'
         + esc(it.date)
         + (it.meta ? ' · ' + esc(it.meta) : '')
         + (it.who ? ' · ' + esc(it.who) : '')
         + '</div>'
         + '</div>';
  }}).join('');
}}

// ── Load all three sources in parallel ───────────────────────────────
async function loadRecent() {{
  try {{
    var results = await Promise.all([
      fetchAll({T_GOR_ACTS}),
      fetchAll({T_EVENTS}),
      fetchAll({T_LEADS}),
    ]);
    var acts = results[0], events = results[1], leads = results[2];
    var items = []
      .concat(acts.map(_actToItem))
      .concat(events.map(_evtToItem))
      .concat(leads.map(_leadToItem));
    // Sort newest-first by sortKey (Created ISO timestamp), id as tiebreak.
    items.sort(function(a, b) {{
      var c = (b.sortKey || '').localeCompare(a.sortKey || '');
      if (c !== 0) return c;
      return (b.id || 0) - (a.id || 0);
    }});
    _items = items;
    recomputeKpis();
    renderFeed();
  }} catch (e) {{
    var body = document.getElementById('recent-body');
    if (body) {{
      body.innerHTML = '<div style="color:#ef4444;padding:20px;text-align:center">'
                    + 'Failed to load recent activity. '
                    + '<button onclick="loadRecent()" style="margin-left:8px;background:none;color:#3b82f6;'
                    + 'border:1px solid var(--border);border-radius:6px;padding:4px 10px;cursor:pointer">Retry</button></div>';
    }}
  }}
}}

renderKindChips();
loadRecent();
"""
    script_js = f"const GFR_USER={repr(user_name)};\nconst TOOL = {{venuesT: {T_GOR_VENUES}}};\n" + recent_js
    return _mobile_page('m_recent', 'Recent Activity', body, script_js, br, bt, user=user,
                         extra_html=GFR_EXTRA_HTML, extra_js=GFR_EXTRA_JS)
