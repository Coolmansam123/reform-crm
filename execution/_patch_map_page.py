#!/usr/bin/env python3
"""Patch 5: Insert _map_page() before the PATIENT PIPELINE comment block."""
import pathlib

f = pathlib.Path("execution/modal_outreach_hub.py")
src = f.read_text(encoding="utf-8")

TARGET = "# PATIENT PIPELINE"
idx = src.find(TARGET)
assert idx != -1, "PATIENT PIPELINE anchor not found"

line_start = src.rfind('\n', 0, idx) + 1
sep_start  = src.rfind('\n', 0, line_start - 1) + 1

MAP_PAGE = """\
# ──────────────────────────────────────────────────────────────────────────────
# MAP DIRECTORY (shared template for Attorney / Gorilla / Community)
# ──────────────────────────────────────────────────────────────────────────────
def _map_page(tool_key: str, br: str, bt: str) -> str:
    CONF = {
        'attorney':  {'label': 'PI Attorney',       'color': '#7c3aed', 'tid': T_ATT_VENUES, 'nameField': 'Law Firm Name',
                      'activeStatus': 'Active Relationship',
                      'stages': ['Not Contacted','Contacted','In Discussion','Active Relationship']},
        'gorilla':   {'label': 'Gorilla Marketing', 'color': '#ea580c', 'tid': T_GOR_VENUES, 'nameField': 'Name',
                      'activeStatus': 'Active Partner',
                      'stages': ['Not Contacted','Contacted','In Discussion','Active Partner']},
        'community': {'label': 'Community',          'color': '#059669', 'tid': T_COM_VENUES, 'nameField': 'Name',
                      'activeStatus': 'Active Partner',
                      'stages': ['Not Contacted','Contacted','In Discussion','Active Partner']},
    }
    c = CONF[tool_key]
    map_key = tool_key + '_map'
    header = (
        f'<div class="header"><div class="header-left">'
        f'<h1>{c["label"]} Directory</h1>'
        f'<div class="sub">All venues \u2014 filter by stage or search</div>'
        f'</div><div class="header-right">'
        f'<span id="refresh-stamp" style="font-size:12px;color:rgba(255,255,255,0.5)"></span>'
        f'<button class="btn btn-ghost" onclick="load()">&#x21bb; Refresh</button>'
        f'</div></div>'
    )
    body = (
        '<div class="panel" style="margin-bottom:0">'
        '<div class="filter-bar" id="filter-bar"><div class="loading">Loading\u2026</div></div>'
        '<div id="count-bar" style="padding:8px 18px;font-size:12px;color:var(--text3)">Loading\u2026</div>'
        '<div class="venue-grid" id="venue-grid"><div class="loading">Loading\u2026</div></div>'
        '</div>'
    )
    stages_json = str(c['stages']).replace("'", '"')
    js = f\"\"\"
let _venues = [];
let _stageFilter = '';
const _stages = {stages_json};
const _activeStatus = '{c["activeStatus"]}';
const _nameField = '{c["nameField"]}';

function buildFilters() {{
  const bar = document.getElementById('filter-bar');
  bar.innerHTML = '<button class="filter-btn on" data-stage="" onclick="setFilter(this)">All</button>'
    + _stages.map(s => `<button class="filter-btn" data-stage="${{s}}" onclick="setFilter(this)">${{s}}</button>`).join('')
    + '<input class="search-input" id="search-box" placeholder="Search name\u2026" oninput="applyFilters()">';
}}

function statusBadge(status) {{
  const map = {{'Not Contacted':'sb-not','Contacted':'sb-cont','In Discussion':'sb-disc'}};
  const cls = status === _activeStatus ? 'sb-act' : (map[status] || 'sb-not');
  return `<span class="status-badge ${{cls}}">${{esc(status || 'Unknown')}}</span>`;
}}

function setFilter(btn) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  _stageFilter = btn.dataset.stage;
  applyFilters();
}}

function applyFilters() {{
  const q = (document.getElementById('search-box').value || '').toLowerCase();
  const filtered = _venues.filter(v => {{
    const name = (v[_nameField] || '').toLowerCase();
    const status = sv(v['Contact Status']);
    return (!_stageFilter || status === _stageFilter) && (!q || name.includes(q));
  }});
  document.getElementById('count-bar').textContent = filtered.length + ' venues shown';
  document.getElementById('venue-grid').innerHTML = filtered.length ? filtered.map(v => {{
    const name = esc(v[_nameField] || '(unnamed)');
    const status = sv(v['Contact Status']);
    const type = esc(sv(v['Type']) || '');
    const phone = esc(v['Phone'] || v['Main Phone'] || '');
    const addr = esc(v['Address'] || v['Street Address'] || '');
    const fu = v['Follow-Up Date'];
    const fuDays = daysUntil(fu);
    const fuColor = fuDays !== null && fuDays < 0 ? '#ef4444' : fuDays === 0 ? '#f59e0b' : 'var(--text3)';
    return `<div class="venue-card">
      <div class="vc-name">${{name}}</div>
      ${{type ? `<div class="vc-type">${{type}}</div>` : ''}}
      ${{phone ? `<div class="vc-row"><span class="vc-icon">\U0001f4de</span><span>${{phone}}</span></div>` : ''}}
      ${{addr ? `<div class="vc-row"><span class="vc-icon">\U0001f4cd</span><span>${{addr}}</span></div>` : ''}}
      <div class="vc-foot">
        ${{statusBadge(status)}}
        ${{fu ? `<span style="font-size:11px;color:${{fuColor}}">Follow-up ${{fmt(fu)}}</span>` : ''}}
      </div>
    </div>`;
  }}).join('') : '<div class="empty">No venues match this filter</div>';
}}

async function load() {{
  _venues = await fetchAll({c['tid']});
  buildFilters();
  applyFilters();
  stampRefresh();
}}

load();
\"\"\"
    return _page(map_key, f'{c["label"]} Directory', header, body, js, br, bt)


"""

src = src[:sep_start] + MAP_PAGE + src[sep_start:]
assert 'def _map_page(' in src
f.write_text(src, encoding="utf-8")
print(f"Batch 5 done. File is now {len(src)} chars.")
