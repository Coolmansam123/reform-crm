"""
PI Cases pages — patient tracking and law firm ROI.
"""
from .shared import (
    _page,
    T_PI_ACTIVE, T_PI_BILLED, T_PI_AWAITING, T_PI_CLOSED, T_PI_FINANCE,
    T_ATT_VENUES,
)


def _patients_page(br: str, bt: str, stage: str = '', user: dict = None) -> str:
    STAGE_META = {
        '':         ('patients',          'Patient Rolodex',        'All PI patients across every stage'),
        'active':   ('patients_active',   'Active Treatment',       'Patients currently in active treatment'),
        'billed':   ('patients_billed',   'Billed Cases',           'Cases billed and pending resolution'),
        'awaiting': ('patients_awaiting', 'Awaiting / Negotiating', 'Cases awaiting settlement or negotiation'),
        'closed':   ('patients_closed',   'Closed Cases',           'Fully closed PI cases'),
    }
    page_key, title, subtitle = STAGE_META.get(stage, STAGE_META[''])
    header = (
        '<div class="header"><div class="header-left">'
        f'<h1>{title}</h1>'
        f'<div class="sub">{subtitle}</div>'
        '</div></div>'
    )

    # ── Overview landing page (no stage filter) ────────────────────────────────
    if not stage:
        body = f"""
<div style="display:flex;gap:14px;margin-bottom:16px;padding:0 18px">
  <a href="/patients/active" style="text-decoration:none;flex:1">
    <div class="stat-chip c-purple" style="cursor:pointer;transition:border-color 0.12s;margin:0" onmouseover="this.style.borderColor='#7c3aed'" onmouseout="this.style.borderColor=''">
      <div class="label">Active Treatment</div><div class="value" id="s-active">—</div>
      <div style="font-size:10px;color:var(--text3);margin-top:4px">View all →</div>
    </div>
  </a>
  <a href="/patients/billed" style="text-decoration:none;flex:1">
    <div class="stat-chip c-yellow" style="cursor:pointer;transition:border-color 0.12s;margin:0" onmouseover="this.style.borderColor='#d97706'" onmouseout="this.style.borderColor=''">
      <div class="label">Billed</div><div class="value" id="s-billed">—</div>
      <div style="font-size:10px;color:var(--text3);margin-top:4px">View all →</div>
    </div>
  </a>
  <a href="/patients/awaiting" style="text-decoration:none;flex:1">
    <div class="stat-chip c-blue" style="cursor:pointer;transition:border-color 0.12s;margin:0" onmouseover="this.style.borderColor='#2563eb'" onmouseout="this.style.borderColor=''">
      <div class="label">Awaiting / Negotiating</div><div class="value" id="s-awaiting">—</div>
      <div style="font-size:10px;color:var(--text3);margin-top:4px">View all →</div>
    </div>
  </a>
  <a href="/patients/closed" style="text-decoration:none;flex:1">
    <div class="stat-chip c-green" style="cursor:pointer;transition:border-color 0.12s;margin:0" onmouseover="this.style.borderColor='#059669'" onmouseout="this.style.borderColor=''">
      <div class="label">Closed</div><div class="value" id="s-closed">—</div>
      <div style="font-size:10px;color:var(--text3);margin-top:4px">View all →</div>
    </div>
  </a>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
  <div class="panel" style="margin:0">
    <div class="panel-hd">
      <span class="panel-title">&#x26a0; Needs Attention</span>
      <span class="panel-meta" id="attn-ct"></span>
    </div>
    <div class="panel-body" id="attn-body"><div class="loading">Loading\u2026</div></div>
  </div>
  <div class="panel" style="margin:0">
    <div class="panel-hd">
      <span class="panel-title">&#x1f4c5; Upcoming Follow-Ups</span>
      <span class="panel-meta" id="fu-ct"></span>
    </div>
    <div class="panel-body" id="fu-body"><div class="loading">Loading\u2026</div></div>
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
  <div class="panel" style="margin:0">
    <div class="panel-hd">
      <span class="panel-title">&#x2696; Top Firms by Active Cases</span>
    </div>
    <div class="panel-body" id="firms-body"><div class="loading">Loading\u2026</div></div>
  </div>
  <div class="panel" style="margin:0">
    <div class="panel-hd">
      <span class="panel-title">&#x1f4ca; Pipeline Snapshot</span>
    </div>
    <div class="panel-body" id="pipeline-body"><div class="loading">Loading\u2026</div></div>
  </div>
</div>
"""
        js = f"""
async function load() {{
  const [activeRows, billedRows, awaitingRows, closedRows] = await Promise.all([
    fetchAll({T_PI_ACTIVE}), fetchAll({T_PI_BILLED}),
    fetchAll({T_PI_AWAITING}), fetchAll({T_PI_CLOSED}),
  ]);

  document.getElementById('s-active').textContent   = activeRows.length;
  document.getElementById('s-billed').textContent   = billedRows.length;
  document.getElementById('s-awaiting').textContent = awaitingRows.length;
  document.getElementById('s-closed').textContent   = closedRows.length;

  function getName(r) {{
    const label = r['Case Label'] || '';
    const m = label.match(/^(.+?)\s*-\s*\d{{1,2}}\/\d{{1,2}}\/\d{{4}}$/);
    if (m) return m[1].trim();
    const np = Array.isArray(r['Patient']) && r['Patient'][0] ? r['Patient'][0].value : '';
    return np || label || '(unnamed)';
  }}
  function getFirm(r) {{
    const raw = r['Law Firm Name ONLY'] || r['Law Firm Name'] || r['Law Firm'] || '';
    if (!raw) return '';
    if (Array.isArray(raw)) return raw.length ? (raw[0].value || String(raw[0])) : '';
    if (typeof raw === 'object' && raw.value !== undefined) return raw.value;
    return String(raw);
  }}
  function getFU(r) {{ return r['Follow-Up Date'] || r['Follow Up Date'] || ''; }}

  // ── Needs Attention (overdue + today) ──
  const today = new Date().setHours(0,0,0,0);
  const attnRows = [];
  for (const [rows, stageLabel, stageColor] of [
    [activeRows,   'Active',   '#a78bfa'],
    [billedRows,   'Billed',   '#fbbf24'],
    [awaitingRows, 'Awaiting', '#60a5fa'],
  ]) {{
    for (const r of rows) {{
      const fu = getFU(r);
      if (!fu) continue;
      const d = daysUntil(fu);
      if (d !== null && d <= 0) attnRows.push({{ name: getName(r), fu, d, stageLabel, stageColor }});
    }}
  }}
  attnRows.sort((a,b) => a.d - b.d);
  document.getElementById('attn-ct').textContent = attnRows.length + ' item' + (attnRows.length !== 1 ? 's' : '');
  document.getElementById('attn-body').innerHTML = attnRows.length ? attnRows.slice(0,12).map(a => `
    <div class="a-row">
      <div class="dot ${{a.d < 0 ? 'dot-r' : 'dot-y'}}"></div>
      <div style="flex:1;min-width:0">
        <div style="font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${{esc(a.name)}}</div>
        <div style="font-size:11px;color:${{a.stageColor}}">${{esc(a.stageLabel)}}</div>
      </div>
      <span class="a-meta" style="color:${{a.d < 0 ? '#ef4444':'#f59e0b'}};flex-shrink:0">${{a.d === 0 ? 'Today' : Math.abs(a.d) + 'd overdue'}}</span>
    </div>`).join('') : '<div class="empty">All caught up \u2713</div>';

  // ── Upcoming Follow-Ups (next 14 days, not overdue) ──
  const upcoming = [];
  for (const [rows, stageLabel, stageColor] of [
    [activeRows,   'Active',   '#a78bfa'],
    [billedRows,   'Billed',   '#fbbf24'],
    [awaitingRows, 'Awaiting', '#60a5fa'],
  ]) {{
    for (const r of rows) {{
      const fu = getFU(r);
      if (!fu) continue;
      const d = daysUntil(fu);
      if (d !== null && d > 0 && d <= 14) upcoming.push({{ name: getName(r), fu, d, stageLabel, stageColor }});
    }}
  }}
  upcoming.sort((a,b) => a.d - b.d);
  document.getElementById('fu-ct').textContent = upcoming.length + ' in 14 days';
  document.getElementById('fu-body').innerHTML = upcoming.length ? upcoming.slice(0,12).map(a => `
    <div class="a-row">
      <div class="dot dot-g"></div>
      <div style="flex:1;min-width:0">
        <div style="font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${{esc(a.name)}}</div>
        <div style="font-size:11px;color:${{a.stageColor}}">${{esc(a.stageLabel)}}</div>
      </div>
      <span class="date-badge" style="flex-shrink:0">${{fmt(a.fu)}}</span>
    </div>`).join('') : '<div class="empty">No upcoming follow-ups</div>';

  // ── Top Firms ──
  const firmCounts = {{}};
  for (const r of activeRows) {{
    const name = getFirm(r);
    if (name) firmCounts[name] = (firmCounts[name] || 0) + 1;
  }}
  const firmList = Object.entries(firmCounts).sort((a,b) => b[1]-a[1]).slice(0,10);
  const maxFirm  = firmList.length ? firmList[0][1] : 1;
  document.getElementById('firms-body').innerHTML = firmList.length
    ? '<div style="padding:4px 16px 8px">' + firmList.map(([name, n]) => `
        <div style="padding:9px 0;border-bottom:1px solid var(--border)">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
            <span style="font-size:12px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:80%">${{esc(name)}}</span>
            <span style="font-size:13px;font-weight:700;color:#a78bfa;flex-shrink:0;margin-left:8px">${{n}}</span>
          </div>
          <div style="height:5px;background:var(--border);border-radius:3px;overflow:hidden">
            <div style="height:5px;background:linear-gradient(90deg,#7c3aed,#a78bfa);border-radius:3px;width:${{Math.round(n/maxFirm*100)}}%"></div>
          </div>
        </div>`).join('') + '</div>'
    : '<div class="empty">No data</div>';

  // ── Pipeline Snapshot ──
  const activeStages = [
    {{ label: 'Active Treatment', n: activeRows.length,   color: '#a78bfa', href: '/patients/active'   }},
    {{ label: 'Billed',           n: billedRows.length,   color: '#fbbf24', href: '/patients/billed'   }},
    {{ label: 'Awaiting',         n: awaitingRows.length, color: '#60a5fa', href: '/patients/awaiting' }},
  ];
  const closedStage = {{ label: 'Closed', n: closedRows.length, color: '#34d399', href: '/patients/closed' }};
  const barTotal  = activeStages.reduce((s,x) => s + x.n, 0);
  const allStages = [...activeStages, closedStage];
  const allTotal  = allStages.reduce((s,x) => s + x.n, 0);
  document.getElementById('pipeline-body').innerHTML =
    '<div style="padding:12px 16px 4px">'
    + `<div style="display:flex;height:10px;border-radius:5px;overflow:hidden;margin-bottom:4px">
        ${{activeStages.map(s => `<div style="width:${{barTotal ? (s.n/barTotal*100).toFixed(1) : 0}}%;background:${{s.color}}" title="${{s.label}}: ${{s.n}}"></div>`).join('')}}
       </div>
       <div style="font-size:10px;color:var(--text3);margin-bottom:14px">Active pipeline only (excludes closed)</div>`
    + allStages.map(s => `
      <a href="${{s.href}}" style="text-decoration:none;display:block">
        <div style="display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid var(--border)">
          <div style="display:flex;align-items:center;gap:10px">
            <div style="width:10px;height:10px;border-radius:50%;background:${{s.color}};flex-shrink:0"></div>
            <span style="font-size:13px;color:var(--text)">${{esc(s.label)}}</span>
          </div>
          <div style="display:flex;align-items:baseline;gap:8px">
            <span style="font-size:15px;font-weight:700;color:${{s.color}}">${{s.n}}</span>
            <span style="font-size:11px;color:var(--text3);width:38px;text-align:right">${{allTotal ? (s.n/allTotal*100).toFixed(1) : 0}}%</span>
          </div>
        </div>
      </a>`).join('')
    + '</div>';

  stampRefresh();
}}
load();
"""
        return _page(page_key, title, header, body, js, br, bt, user=user)

    # ── Sub-page (active / billed / awaiting / closed) ────────────────────────
    body = f"""
<div class="stats-row">
  <div class="stat-chip c-purple"><div class="label">Active Treatment</div><div class="value" id="s-active">—</div></div>
  <div class="stat-chip c-yellow"><div class="label">Billed</div>          <div class="value" id="s-billed">—</div></div>
  <div class="stat-chip c-blue">  <div class="label">Awaiting</div>        <div class="value" id="s-awaiting">—</div></div>
  <div class="stat-chip c-green"> <div class="label">Closed</div>          <div class="value" id="s-closed">—</div></div>
</div>
<div class="panel" style="margin-bottom:0">
  <div class="filter-bar">
    <input class="search-input" id="search-box" placeholder="Search patient…" oninput="applyFilters()">
  </div>
  <div id="count-bar" style="padding:8px 18px;font-size:12px;color:var(--text3)">Loading…</div>
  <div class="rolodex-grid" id="rolodex-grid"><div class="loading">Loading…</div></div>
</div>
<div class="cd-overlay" id="pd-overlay" onclick="if(event.target===this)closePatientDetail()">
  <div class="cd-modal">
    <div class="cd-header">
      <div style="flex:1;min-width:0">
        <div class="cd-title" id="pd-title"></div>
        <div id="pd-subtitle" style="margin-top:4px"></div>
      </div>
      <div class="cd-header-actions">
        <button class="cd-btn-close" onclick="closePatientDetail()">&times;</button>
      </div>
    </div>
    <div class="cd-body" id="pd-body"></div>
  </div>
</div>
"""
    js = f"""
let _patients = [];
let _stageFilter = '{stage}';

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
    const doi    = p._doi || '';
    return `<div class="patient-card" onclick="openPatientDetail(_patients.find(x=>x.id===${{p.id}}))">
      <div class="pc-head">
        <div class="pc-name">${{esc(p._name)}}</div>
        <span class="pc-stage ${{STAGE_CLS[p._stage]}}">${{STAGE_LABEL[p._stage]}}</span>
      </div>
      ${{firm   ? `<div class="pc-row"><span class="pc-lbl">Law Firm</span><span class="pc-val">${{firm}}</span></div>` : ''}}
      ${{visits ? `<div class="pc-row"><span class="pc-lbl">Visits</span><span class="pc-val">${{visits}}</span></div>` : ''}}
      ${{doi    ? `<div class="pc-row"><span class="pc-lbl">DOI</span><span class="pc-val">${{doi}}</span></div>` : ''}}
      ${{fu     ? `<div class="pc-row"><span class="pc-lbl">Follow-Up</span><span class="pc-val" style="color:${{fuColor}}">${{fmt(fu)}}</span></div>` : ''}}
    </div>`;
  }}).join('') : '<div class="empty">No patients match this filter</div>';
}}

let _allFirmNames = [];

async function load() {{
  const [activeRows, billedRows, awaitingRows, closedRows, attRows] = await Promise.all([
    fetchAll({T_PI_ACTIVE}), fetchAll({T_PI_BILLED}),
    fetchAll({T_PI_AWAITING}), fetchAll({T_PI_CLOSED}),
    fetchAll({T_ATT_VENUES}),
  ]);

  document.getElementById('s-active').textContent   = activeRows.length;
  document.getElementById('s-billed').textContent   = billedRows.length;
  document.getElementById('s-awaiting').textContent = awaitingRows.length;
  document.getElementById('s-closed').textContent   = closedRows.length;

  _allFirmNames = Array.from(new Set(
    attRows.map(f => (f['Law Firm Name'] || '').trim()).filter(Boolean)
  )).sort((a, b) => a.localeCompare(b));

  function tag(rows, stage) {{
    return rows.map(r => {{
      const label = r['Case Label'] || '';
      const m = label.match(/^(.+?)\s*-\s*(\d{{1,2}}\/\d{{1,2}}\/\d{{4}})$/);
      const nameFromPatient = Array.isArray(r['Patient']) && r['Patient'][0] ? r['Patient'][0].value : '';
      return {{
        ...r,
        _stage: stage,
        _name:  m ? m[1].trim() : (nameFromPatient || label || '(unnamed)'),
        _doi:   m ? m[2] : '',
      }};
    }});
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

function _getFirmDisplay(p) {{
  const raw = p['Law Firm Name ONLY'] || p['Law Firm Name'] || p['Law Firm'] || '';
  if (!raw) return '';
  if (Array.isArray(raw)) return raw.length ? (raw[0].value || String(raw[0])) : '';
  if (typeof raw === 'object' && raw.value !== undefined) return raw.value;
  return String(raw);
}}

function _getLinkedValue(v) {{
  if (!v) return '';
  if (Array.isArray(v)) return v.length ? (v[0].value || String(v[0])) : '';
  if (typeof v === 'object' && v.value !== undefined) return v.value;
  return String(v);
}}

function _parseFirmHistory(p) {{
  // New structured field first, then fall back to legacy Case Notes parsing
  let source = (p['Firm History'] || '').trim();
  if (!source) {{
    const caseNotes = p['Case Notes'] || '';
    const hMatch = caseNotes.match(/Firm history:\\s*(.+)/);
    if (hMatch) source = hMatch[1];
  }}
  if (!source) return [];
  return source.split('->').map(raw => {{
    const s = raw.trim();
    if (!s) return null;
    const m = s.match(/^(.+?)\\s*\\((until|current)\\s*([^)]*)\\)\\s*$/);
    if (m) {{
      return {{ name: m[1].trim(), isCurrent: m[2] === 'current', untilDate: m[2] === 'until' ? m[3].trim() : '' }};
    }}
    return {{ name: s, isCurrent: false, untilDate: '' }};
  }}).filter(Boolean);
}}

function _buildPatientDetailHTML(p) {{
  const stageCls = STAGE_CLS[p._stage] || '';
  const doi    = p._doi || '';
  const firm   = _getFirmDisplay(p);
  const visits = p['# of Visits'] || '';
  const fu     = p['Follow-Up Date'] || p['Follow Up Date'] || '';
  const phone  = p['Phone'] || p['Cell Phone'] || '';
  const dob    = p['DOB'] || p['Date of Birth'] || '';
  const addr   = p['Address'] || '';
  const atty   = _getLinkedValue(p['Attorney'] || p['Referring Attorney'] || '');
  const ins    = p['Insurance'] || p['Insurance Company'] || '';
  const adj    = p['Adjuster'] || p['Claims Adjuster'] || '';
  const notes  = p['Notes'] || '';
  const caseNotes = p['Case Notes'] || '';

  const firmHistory = _parseFirmHistory(p);
  // If history doesn't end with current firm (e.g. field empty but Law Firm Name
  // has a value), make sure the display still shows the current firm as a node.
  let timelineEntries = firmHistory.slice();
  if (firm && (timelineEntries.length === 0 || !timelineEntries[timelineEntries.length - 1].isCurrent || timelineEntries[timelineEntries.length - 1].name !== firm)) {{
    // Only show a timeline if there's actual history
  }}

  // Editable Law Firm row (button triggers inline editor)
  const firmRowHTML =
    '<div class="pc-row" style="margin:0" id="pd-firm-row">'
    + '<span class="pc-lbl">Law Firm</span>'
    + '<span class="pc-val" style="display:flex;align-items:center;gap:8px">'
    +   '<span id="pd-firm-display">' + esc(firm || '(none)') + '</span>'
    +   '<button onclick="openFirmEditor(' + p.id + ',\\'' + p._stage + '\\')" '
    +     'style="background:none;border:1px solid var(--border);color:var(--text3);'
    +     'font-size:10px;padding:2px 8px;border-radius:4px;cursor:pointer">Edit</button>'
    + '</span></div>';

  const rows = [
    ['DOI',        doi],
    ['Visits',     visits],
    ['Attorney',   atty],
    ['Phone',      phone],
    ['DOB',        dob],
    ['Insurance',  ins],
    ['Adjuster',   adj],
    ['Address',    addr],
  ].filter(([_, v]) => v);

  let html = '<div style="display:grid;gap:7px;margin-bottom:14px">';
  html += firmRowHTML;
  rows.forEach(([lbl, val]) => {{
    html += '<div class="pc-row" style="margin:0"><span class="pc-lbl">' + esc(lbl) + '</span>'
          + '<span class="pc-val">' + esc(String(val)) + '</span></div>';
  }});
  html += '</div>';

  // Firm history timeline
  if (firmHistory.length > 1) {{
    html += '<div id="pd-firm-history-box" style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:12px 14px;margin-bottom:14px">';
    html += '<div style="font-size:10px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:8px">Firm History</div>';
    firmHistory.forEach((entry, i) => {{
      const isCurrent = entry.isCurrent || (i === firmHistory.length - 1);
      const dotColor = isCurrent ? '#059669' : '#94a3b8';
      html += '<div style="display:flex;gap:10px;padding-bottom:' + (i === firmHistory.length - 1 ? '0' : '8') + 'px">';
      html += '<div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0">';
      html += '<div style="width:8px;height:8px;border-radius:50%;background:' + dotColor + ';margin-top:3px"></div>';
      if (i < firmHistory.length - 1) html += '<div style="flex:1;width:2px;background:var(--border);margin-top:2px"></div>';
      html += '</div>';
      let label = esc(entry.name);
      if (isCurrent) {{
        label += ' <span style="font-size:10px;color:#059669">(current)</span>';
      }} else if (entry.untilDate) {{
        label += ' <span style="font-size:10px;color:var(--text3)">(until ' + esc(entry.untilDate) + ')</span>';
      }} else {{
        label += ' <span style="font-size:10px;color:var(--text3)">(previous)</span>';
      }}
      html += '<div style="font-size:12px;color:' + (isCurrent ? 'var(--text)' : 'var(--text3)') + ';'
            + (isCurrent ? 'font-weight:600' : '') + '">' + label + '</div></div>';
    }});
    html += '</div>';
  }}

  if (fu) {{
    const fuDays = daysUntil(fu);
    const fuColor = fuDays !== null && fuDays < 0 ? '#ef4444' : fuDays === 0 ? '#f59e0b' : '#34d399';
    const fuLabel = fuDays === null ? '' : fuDays < 0
      ? Math.abs(fuDays) + 'd overdue'
      : fuDays === 0 ? 'Today' : 'in ' + fuDays + 'd';
    html += '<div style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px 12px;margin-bottom:12px">';
    html += '<div style="font-size:10px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:4px">Follow-Up</div>';
    html += '<div style="font-size:14px;font-weight:600;color:' + fuColor + '">' + esc(fmt(fu));
    if (fuLabel) html += ' <span style="font-size:11px;font-weight:400;color:' + fuColor + '">(' + fuLabel + ')</span>';
    html += '</div></div>';
  }}

  // Case Notes (strip firm history line since it's shown above)
  const cleanCaseNotes = (caseNotes || '').split('\\n').filter(l => !l.startsWith('Firm history:')).join('\\n').trim();
  const allNotes = [notes, cleanCaseNotes].filter(Boolean).join('\\n\\n').trim();
  if (allNotes) {{
    html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
    html += '<div style="font-size:10px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:6px">Notes</div>';
    html += '<div style="font-size:12px;color:var(--text2);line-height:1.6;white-space:pre-wrap">' + esc(allNotes) + '</div>';
  }}

  return html;
}}

function openFirmEditor(patientId, stage) {{
  const p = _patients.find(x => x.id === patientId);
  if (!p) return;
  const row = document.getElementById('pd-firm-row');
  if (!row) return;
  const current = _getFirmDisplay(p);
  const listId = 'firm-options-' + patientId;
  row.innerHTML =
    '<span class="pc-lbl">Law Firm</span>'
    + '<span class="pc-val" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">'
    +   '<input id="pd-firm-input" list="' + listId + '" value="' + esc(current) + '" '
    +     'style="flex:1;min-width:180px;background:var(--bg);border:1px solid var(--border);'
    +     'color:var(--text);padding:4px 8px;border-radius:4px;font-size:13px">'
    +   '<datalist id="' + listId + '">'
    +     _allFirmNames.map(n => '<option value="' + esc(n) + '"></option>').join('')
    +   '</datalist>'
    +   '<button onclick="saveFirmEdit(' + patientId + ',\\'' + stage + '\\')" '
    +     'style="background:#059669;border:none;color:#fff;font-size:11px;'
    +     'padding:4px 10px;border-radius:4px;cursor:pointer;font-weight:600">Save</button>'
    +   '<button onclick="cancelFirmEdit(' + patientId + ')" '
    +     'style="background:none;border:1px solid var(--border);color:var(--text3);'
    +     'font-size:11px;padding:4px 10px;border-radius:4px;cursor:pointer">Cancel</button>'
    + '</span>';
  setTimeout(() => {{
    const inp = document.getElementById('pd-firm-input');
    if (inp) {{ inp.focus(); inp.select(); }}
  }}, 10);
}}

function cancelFirmEdit(patientId) {{
  const p = _patients.find(x => x.id === patientId);
  if (!p) return;
  // Re-render just the detail body
  document.getElementById('pd-body').innerHTML = _buildPatientDetailHTML(p);
}}

async function saveFirmEdit(patientId, stage) {{
  const input = document.getElementById('pd-firm-input');
  if (!input) return;
  const newFirm = input.value.trim();
  if (!newFirm) {{ alert('Firm name required'); return; }}

  const p = _patients.find(x => x.id === patientId);
  if (!p) return;
  const currentFirm = (_getFirmDisplay(p) || '').trim();
  if (newFirm === currentFirm) {{ cancelFirmEdit(patientId); return; }}

  // Disable inputs, show saving state
  const saveBtn = input.parentElement.querySelector('button');
  if (saveBtn) {{ saveBtn.textContent = 'Saving…'; saveBtn.disabled = true; }}
  input.disabled = true;

  try {{
    const resp = await fetch('/api/patients/' + stage + '/' + patientId + '/firm', {{
      method: 'PATCH',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ new_firm: newFirm }}),
    }});
    if (!resp.ok) {{
      const err = await resp.json().catch(() => ({{}}));
      alert('Save failed: ' + (err.error || resp.status));
      if (saveBtn) {{ saveBtn.textContent = 'Save'; saveBtn.disabled = false; }}
      input.disabled = false;
      return;
    }}
    const data = await resp.json();
    // Update local patient record in place
    p['Law Firm Name'] = data['Law Firm Name'];
    p['Firm History']  = data['Firm History'];
    // Clear the old "Law Firm Name ONLY" formula cache since it won't update locally
    delete p['Law Firm Name ONLY'];
    // Re-render the whole modal body
    document.getElementById('pd-body').innerHTML = _buildPatientDetailHTML(p);
    applyFilters();
  }} catch (e) {{
    alert('Save failed: ' + e.message);
    if (saveBtn) {{ saveBtn.textContent = 'Save'; saveBtn.disabled = false; }}
    input.disabled = false;
  }}
}}

function openPatientDetail(p) {{
  if (!p) return;
  document.getElementById('pd-title').textContent = p._name || '(unnamed)';
  const stageCls = STAGE_CLS[p._stage] || '';
  const stageLabel = STAGE_LABEL[p._stage] || '';
  document.getElementById('pd-subtitle').innerHTML = '<span class="pc-stage ' + stageCls + '">' + esc(stageLabel) + '</span>';
  document.getElementById('pd-body').innerHTML = _buildPatientDetailHTML(p);
  document.getElementById('pd-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}}

function closePatientDetail() {{
  document.getElementById('pd-overlay').classList.remove('open');
  document.body.style.overflow = '';
}}

load();
"""
    return _page(page_key, title, header, body, js, br, bt, user=user)


# ──────────────────────────────────────────────────────────────────────────────
# LAW FIRM ROI
# ──────────────────────────────────────────────────────────────────────────────
def _firms_page(br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header"><div class="header-left">'
        '<h1>Law Firm ROI</h1>'
        '<div class="sub">Case volume and relationship status by firm</div>'
        '</div></div>'
    )
    body = """
<div class="stats-row">
  <div class="stat-chip">         <div class="label">Total Firms</div>             <div class="value" id="s-firms">—</div></div>
  <div class="stat-chip c-green"> <div class="label">Active Relationships</div>   <div class="value" id="s-rels">—</div></div>
  <div class="stat-chip c-purple"><div class="label">Previous Relationships</div> <div class="value" id="s-prev">—</div></div>
  <div class="stat-chip c-blue">  <div class="label">Active Cases</div>           <div class="value" id="s-cases">—</div></div>
  <div class="stat-chip c-yellow"><div class="label">Total Settled</div>          <div class="value" id="s-settled">—</div></div>
</div>
<div class="panel">
  <div class="panel-hd"><span class="panel-title">Firms by Case Volume</span></div>
  <div class="panel-body" id="firms-body"><div class="loading">Loading…</div></div>
</div>
"""
    js = f"""
async function load() {{
  const [firms, actRows, bilRows, awRows, clRows] = await Promise.all([
    fetchAll({T_ATT_VENUES}),
    fetchAll({T_PI_ACTIVE}),
    fetchAll({T_PI_BILLED}),
    fetchAll({T_PI_AWAITING}),
    fetchAll({T_PI_CLOSED}),
  ]);

  function normName(n) {{ return (n || '').toLowerCase().trim(); }}
  function getFirmName(p) {{
    const raw = p['Law Firm Name ONLY'] || p['Law Firm Name'] || p['Law Firm'] || '';
    if (!raw) return '';
    if (Array.isArray(raw)) return raw.length ? (raw[0].value || String(raw[0])) : '';
    if (typeof raw === 'object' && raw.value) return raw.value;
    return String(raw);
  }}

  const counts = {{}};
  function tally(rows, key) {{
    for (const r of rows) {{
      const k = normName(getFirmName(r));
      if (!k) continue;
      counts[k] = counts[k] || {{active:0, billed:0, awaiting:0, settled:0}};
      counts[k][key]++;
    }}
  }}
  tally(actRows, 'active');
  tally(bilRows, 'billed');
  tally(awRows,  'awaiting');
  tally(clRows,  'settled');

  function lookupCounts(name) {{
    const key = normName(name);
    if (counts[key]) return counts[key];
    for (const [k, v] of Object.entries(counts)) {{
      const shorter = key.length <= k.length ? key : k;
      const longer  = key.length <= k.length ? k   : key;
      if (shorter.length >= 8 && longer.includes(shorter)) return v;
    }}
    return null;
  }}

  const enriched = firms.map(f => {{
    const name = f['Law Firm Name'] || '(unnamed)';
    const c = lookupCounts(name) || {{active:0, billed:0, awaiting:0, settled:0}};
    const total = c.active + c.billed + c.awaiting + c.settled;
    const prevRel = total > 0 && c.active === 0;
    return {{
      name: esc(name),
      status: sv(f['Contact Status']),
      active: c.active, billed: c.billed, awaiting: c.awaiting, settled: c.settled,
      total, prevRel,
    }};
  }}).sort((a,b) => b.total - a.total || a.name.localeCompare(b.name));

  document.getElementById('s-firms').textContent   = firms.length;
  document.getElementById('s-rels').textContent    = enriched.filter(f => f.status === 'Active Relationship').length;
  document.getElementById('s-prev').textContent    = enriched.filter(f => f.prevRel).length;
  document.getElementById('s-cases').textContent   = enriched.reduce((s,f) => s + f.active, 0);
  document.getElementById('s-settled').textContent = enriched.reduce((s,f) => s + f.settled, 0);

  const SC = {{'Active Relationship':'#059669','In Discussion':'#d97706','Contacted':'#2563eb','Not Contacted':'#475569'}};
  document.getElementById('firms-body').innerHTML = enriched.length ? `
    <table class="data-table"><thead><tr>
      <th>Firm</th><th class="c">Active</th><th class="c">Billed</th>
      <th class="c">Awaiting</th><th class="c">Settled</th><th class="c">Total</th><th>Status</th>
    </tr></thead><tbody>
    ${{enriched.map(f => `<tr>
      <td style="font-weight:500">${{f.name}}</td>
      <td class="c" style="color:#a78bfa">${{f.active||'—'}}</td>
      <td class="c" style="color:#fbbf24">${{f.billed||'—'}}</td>
      <td class="c" style="color:#60a5fa">${{f.awaiting||'—'}}</td>
      <td class="c" style="color:#34d399">${{f.settled||'—'}}</td>
      <td class="c" style="font-weight:700">${{f.total||'—'}}</td>
      <td>${{f.prevRel
        ? '<span style="font-size:11px;padding:2px 8px;border-radius:8px;background:#7c3aed22;color:#a78bfa;font-weight:600">Previous Relationship</span>'
        : '<span style="font-size:11px;padding:2px 8px;border-radius:8px;background:' + (SC[f.status]||'#475569') + '22;color:' + (SC[f.status]||'#64748b') + ';font-weight:600">' + esc(f.status||'Unknown') + '</span>'
      }}</td>
    </tr>`).join('')}}
    </tbody></table>
  ` : '<div class="empty">No firm data</div>';
  stampRefresh();
}}
load();
"""
    return _page('firms', 'Law Firm ROI', header, body, js, br, bt, user=user)
