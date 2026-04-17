#!/usr/bin/env python3
"""Patch 6: Replace _patients_page() with rolodex version."""
import pathlib

f = pathlib.Path("execution/modal_outreach_hub.py")
src = f.read_text(encoding="utf-8")

# Slice out everything from the PATIENT PIPELINE comment block
# up to (but not including) the LAW FIRM ROI comment block.
START_MARKER = "# PATIENT PIPELINE"
END_MARKER   = "# LAW FIRM ROI"

si = src.find(START_MARKER)
ei = src.find(END_MARKER)
assert si != -1 and ei != -1, "markers not found"

# Walk back from START_MARKER to the separator line above it
line_start = src.rfind('\n', 0, si) + 1
sep_start  = src.rfind('\n', 0, line_start - 1) + 1

# Walk back from END_MARKER to its separator line
ei_line  = src.rfind('\n', 0, ei) + 1
ei_sep   = src.rfind('\n', 0, ei_line - 1) + 1

NEW_PATIENTS = """\
# ──────────────────────────────────────────────────────────────────────────────
# PATIENT ROLODEX
# ──────────────────────────────────────────────────────────────────────────────
def _patients_page(br: str, bt: str) -> str:
    header = (
        '<div class="header"><div class="header-left">'
        '<h1>Patient Rolodex</h1>'
        '<div class="sub">All PI patients across every stage</div>'
        '</div><div class="header-right">'
        '<span id="refresh-stamp" style="font-size:12px;color:rgba(255,255,255,0.5)"></span>'
        '<button class="btn btn-ghost" onclick="load()">&#x21bb; Refresh</button>'
        '</div></div>'
    )
    body = f\"\"\"
<div class="stats-row">
  <div class="stat-chip c-purple"><div class="label">Active Treatment</div><div class="value" id="s-active">\u2014</div></div>
  <div class="stat-chip c-yellow"><div class="label">Billed</div>          <div class="value" id="s-billed">\u2014</div></div>
  <div class="stat-chip c-blue">  <div class="label">Awaiting</div>        <div class="value" id="s-awaiting">\u2014</div></div>
  <div class="stat-chip c-green"> <div class="label">Closed</div>          <div class="value" id="s-closed">\u2014</div></div>
</div>
<div class="panel" style="margin-bottom:0">
  <div class="filter-bar">
    <button class="filter-btn on" data-stage="" onclick="setFilter(this)">All</button>
    <button class="filter-btn" data-stage="active"   onclick="setFilter(this)">Active</button>
    <button class="filter-btn" data-stage="billed"   onclick="setFilter(this)">Billed</button>
    <button class="filter-btn" data-stage="awaiting" onclick="setFilter(this)">Awaiting</button>
    <button class="filter-btn" data-stage="closed"   onclick="setFilter(this)">Closed</button>
    <input class="search-input" id="search-box" placeholder="Search patient\u2026" oninput="applyFilters()">
  </div>
  <div id="count-bar" style="padding:8px 18px;font-size:12px;color:var(--text3)">Loading\u2026</div>
  <div class="rolodex-grid" id="rolodex-grid"><div class="loading">Loading\u2026</div></div>
</div>
\"\"\"
    js = f\"\"\"
let _patients = [];
let _stageFilter = '';

const STAGE_LABEL = {{
  active:   'Active Treatment',
  billed:   'Billed',
  awaiting: 'Awaiting / Negotiating',
  closed:   'Closed',
}};
const STAGE_CLS = {{
  active: 'stage-active', billed: 'stage-billed',
  awaiting: 'stage-awaiting', closed: 'stage-closed',
}};

function setFilter(btn) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  _stageFilter = btn.dataset.stage;
  applyFilters();
}}

function applyFilters() {{
  const q = (document.getElementById('search-box').value || '').toLowerCase();
  const filtered = _patients.filter(p => {{
    const stageOk  = !_stageFilter || p._stage === _stageFilter;
    const searchOk = !q || (p._name || '').toLowerCase().includes(q);
    return stageOk && searchOk;
  }});
  document.getElementById('count-bar').textContent = filtered.length + ' patients shown';
  document.getElementById('rolodex-grid').innerHTML = filtered.length ? filtered.map(p => {{
    const firm   = esc(sv(p['Law Firm Name ONLY'] || p['Law Firm Name'] || p['Law Firm'] || ''));
    const visits = p['# of Visits'] || '';
    const fu     = p['Follow-Up Date'] || p['Follow Up Date'];
    const fuDays = daysUntil(fu);
    const fuColor = fuDays !== null && fuDays < 0 ? '#ef4444' : fuDays === 0 ? '#f59e0b' : 'var(--text3)';
    return `<div class="patient-card">
      <div class="pc-head">
        <div class="pc-name">${{esc(p._name)}}</div>
        <span class="pc-stage ${{STAGE_CLS[p._stage]}}">${{STAGE_LABEL[p._stage]}}</span>
      </div>
      ${{firm   ? `<div class="pc-row"><span class="pc-lbl">Law Firm</span><span class="pc-val">${{firm}}</span></div>` : ''}}
      ${{visits ? `<div class="pc-row"><span class="pc-lbl">Visits</span><span class="pc-val">${{visits}}</span></div>` : ''}}
      ${{fu     ? `<div class="pc-row"><span class="pc-lbl">Follow-Up</span><span class="pc-val" style="color:${{fuColor}}">${{fmt(fu)}}</span></div>` : ''}}
    </div>`;
  }}).join('') : '<div class="empty">No patients match this filter</div>';
}}

async function load() {{
  const [activeRows, billedRows, awaitingRows, closedRows] = await Promise.all([
    fetchAll({T_PI_ACTIVE}), fetchAll({T_PI_BILLED}),
    fetchAll({T_PI_AWAITING}), fetchAll({T_PI_CLOSED}),
  ]);

  document.getElementById('s-active').textContent   = activeRows.length;
  document.getElementById('s-billed').textContent   = billedRows.length;
  document.getElementById('s-awaiting').textContent = awaitingRows.length;
  document.getElementById('s-closed').textContent   = closedRows.length;

  function tag(rows, stage) {{
    return rows.map(r => ({{
      ...r,
      _stage: stage,
      _name:  r['Patient Name'] || r['Name'] || '(unnamed)',
    }}));
  }}
  _patients = [
    ...tag(activeRows,   'active'),
    ...tag(billedRows,   'billed'),
    ...tag(awaitingRows, 'awaiting'),
    ...tag(closedRows,   'closed'),
  ].sort((a, b) => a._name.localeCompare(b._name));

  applyFilters();
  stampRefresh();
}}

load();
\"\"\"
    return _page('patients', 'Patient Rolodex', header, body, js, br, bt)


"""

src = src[:sep_start] + NEW_PATIENTS + src[ei_sep:]
assert 'Patient Rolodex' in src
assert 'def _firms_page(' in src
f.write_text(src, encoding="utf-8")
print(f"Batch 6 done. File is now {len(src)} chars.")
