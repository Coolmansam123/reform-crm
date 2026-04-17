"""
Outreach pages — directory and map (shared across attorney, gorilla, community).
"""
from .shared import (
    _page, _TEMPLATES_JS,
    T_ATT_VENUES, T_ATT_ACTS, T_GOR_VENUES, T_GOR_ACTS,
    T_COM_VENUES, T_COM_ACTS,
    T_PI_ACTIVE, T_PI_BILLED, T_PI_AWAITING, T_PI_CLOSED,
)
from .guerilla import (
    _GFR_CSS, _GFR_HTML, _GFR_FORMS345_HTML, _GFR_FORM2_HTML,
    _GFR_JS, _GFR_FORMS345_JS,
)
import os


def _directory_page(tool_key: str, br: str, bt: str, user: dict = None) -> str:
    CONF = {
        'attorney':  {'label': 'PI Attorney',       'color': '#7c3aed', 'tid': T_ATT_VENUES,
                      'actsTid': T_ATT_ACTS,  'actLinkField': 'Law Firm',
                      'nameField': 'Law Firm Name',  'phoneField': 'Phone Number', 'addrField': 'Law Office Address',
                      'activeStatus': 'Active Relationship',
                      'stages': ['Not Contacted','Contacted','In Discussion','Active Relationship']},
        'gorilla':   {'label': 'Guerilla Marketing', 'color': '#ea580c', 'tid': T_GOR_VENUES,
                      'actsTid': T_GOR_ACTS,  'actLinkField': 'Business',
                      'nameField': 'Name',            'phoneField': 'Phone',        'addrField': 'Address',
                      'activeStatus': 'Active Partner',
                      'stages': ['Not Contacted','Contacted','In Discussion','Active Partner']},
        'community': {'label': 'Community',          'color': '#059669', 'tid': T_COM_VENUES,
                      'actsTid': T_COM_ACTS,  'actLinkField': 'Organization',
                      'nameField': 'Name',            'phoneField': 'Phone',        'addrField': 'Address',
                      'activeStatus': 'Active Partner',
                      'stages': ['Not Contacted','Contacted','In Discussion','Active Partner']},
    }
    c = CONF[tool_key]
    active_key = tool_key + '_dir'
    import json as _json
    stages_json = _json.dumps(c['stages'])

    header = (
        f'<div class="header" style="background:linear-gradient(135deg,{c["color"]}22,transparent)">'
        f'<div class="header-left">'
        f'<h1>{c["label"]} — Contact List</h1>'
        f'<div class="sub">All venues with contact details</div>'
        f'</div></div>'
    )
    body = (
        '<div class="panel" style="margin-bottom:0">'
        '<div class="filter-bar" id="filter-bar">'
        '<div class="loading">Loading\u2026</div>'
        '</div>'
        '<div id="count-bar" style="padding:4px 18px 8px;font-size:12px;color:var(--text3)">Loading\u2026</div>'
        '<div class="venue-grid" id="venue-grid"><div class="loading">Loading\u2026</div></div>'
        '</div>'
    )
    body += (
        f'<div class="cd-overlay" id="cd-overlay" onclick="if(event.target===this)closeContactDetail()">'
        f'<div class="cd-modal">'
        f'<div class="cd-header">'
        f'<div style="flex:1;min-width:0"><div class="cd-title" id="cd-title"></div>'
        f'<div id="cd-subtitle" style="margin-top:4px"></div></div>'
        f'<div class="cd-header-actions">'
        f'<button class="cd-btn-email" onclick="showEmailTemplates(_cdVenue,\'{tool_key}\')" title="Email templates">\u2709 Email</button>'
        f'<button class="cd-btn-close" onclick="closeContactDetail()">&times;</button>'
        f'</div></div>'
        f'<div class="cd-body">'
        f'<div class="cd-panel active" id="cd-panel-detail"><div id="cd-detail-body"></div></div>'
        f'<div class="cd-panel" id="cd-panel-tpl"><div id="cd-tpl-body"></div></div>'
        f'</div></div></div>'
    )
    js = f"""
const _stages      = {stages_json};
const _activeStatus = '{c["activeStatus"]}';
const _nameField   = '{c["nameField"]}';
const _phoneField  = '{c["phoneField"]}';
const _addrField   = '{c["addrField"]}';
const _color       = '{c["color"]}';
const VENUES_TID   = {c["tid"]};
const ACTS_TID     = {c["actsTid"]};
const ACTS_LINK    = '{c["actLinkField"]}';
let _venues = [];
let _stageFilter = '';
let _sortMode = 'distance';
let _cdVenue = null;

async function bpatch(tid, id, data) {{
  return fetch(BR+'/api/database/rows/table/'+tid+'/'+id+'/?user_field_names=true',{{
    method:'PATCH',headers:{{'Authorization':'Token '+BT,'Content-Type':'application/json'}},
    body:JSON.stringify(data)}});
}}
async function bpost(tid, data) {{
  return fetch(BR+'/api/database/rows/table/'+tid+'/?user_field_names=true',{{
    method:'POST',headers:{{'Authorization':'Token '+BT,'Content-Type':'application/json'}},
    body:JSON.stringify(data)}});
}}

function stageOpts(cur) {{
  return _stages.map(s => '<option value="'+s+'"'+(cur===s?' selected':'')+'>'+s+'</option>').join('');
}}

function renderNotes(text) {{
  if (!text || !text.trim()) return '<div style="color:var(--text3);font-size:12px;padding:4px 0">No notes yet</div>';
  return text.split('\\n---\\n').filter(e => e.trim()).map(entry => {{
    const m = entry.match(/^\\[(\d{{4}}-\d{{2}}-\d{{2}})\\] ([\s\S]*)$/);
    if (m) return '<div style="padding:5px 0;border-bottom:1px solid var(--border)">'
      + '<div style="font-size:10px;color:var(--text3);margin-bottom:2px">' + m[1] + '</div>'
      + '<div style="font-size:12px">' + esc(m[2].trim()) + '</div></div>';
    return '<div style="padding:5px 0;border-bottom:1px solid var(--border);font-size:12px">' + esc(entry.trim()) + '</div>';
  }}).join('');
}}

function renderAct(a) {{
  const type = a['Type'] ? (typeof a['Type'] === 'object' ? a['Type'].value : a['Type']) : '';
  const outcome = a['Outcome'] ? (typeof a['Outcome'] === 'object' ? a['Outcome'].value : a['Outcome']) : '';
  const date = a['Date'] || '';
  const person = a['Contact Person'] || '';
  const summary = a['Summary'] || '';
  const fu = a['Follow-Up Date'] || '';
  return '<div style="padding:8px 0;border-bottom:1px solid var(--border)">'
    + '<div style="display:flex;justify-content:space-between;margin-bottom:3px">'
    + '<span style="font-size:11px;font-weight:600;background:var(--badge-bg);padding:1px 6px;border-radius:4px">' + esc(type) + '</span>'
    + '<span style="font-size:11px;color:var(--text3)">' + esc(date) + '</span></div>'
    + (outcome ? '<div style="font-size:12px;color:var(--text2)">' + esc(outcome) + '</div>' : '')
    + (person  ? '<div style="font-size:11px;color:var(--text3)">with ' + esc(person) + '</div>' : '')
    + (summary ? '<div style="font-size:12px;margin-top:3px">' + esc(summary) + '</div>' : '')
    + (fu      ? '<div style="font-size:11px;color:#f59e0b;margin-top:2px">Follow-up: ' + esc(fu) + '</div>' : '')
    + '</div>';
}}

function _buildDetailHTML(v) {{
  const id  = v.id;
  const status = sv(v['Contact Status']);
  const phone   = esc(v[_phoneField] || '');
  const addr    = esc(v[_addrField]  || '');
  const website = v['Website'] || '';
  const fu      = v['Follow-Up Date'] || '';
  const notesRaw = v['Notes'] || '';
  let html = '';
  if (phone)   html += '<div style="font-size:13px;margin-bottom:6px">\u260e <a href="tel:'+phone+'" style="color:var(--text)">'+phone+'</a></div>';
  if (addr)    html += '<div style="font-size:12px;color:var(--text2);margin-bottom:6px">\U0001f4cd '+addr+'</div>';
  if (website) html += '<div style="font-size:12px;margin-bottom:10px">\U0001f310 <a href="'+esc(website)+'" target="_blank" style="color:#3b82f6">'+esc(website)+'</a></div>';
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
  html += '<div style="margin-bottom:8px">';
  html += '<div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:4px">Contact Status</div>';
  html += '<div style="display:flex;gap:6px;align-items:center">';
  html += '<select id="cd-status-'+id+'" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 8px;font-size:12px" onchange="updateStatus('+id+',this.value)">'+stageOpts(status)+'</select>';
  html += '<span id="cd-status-st-'+id+'" style="font-size:11px;color:#34a853;min-width:20px"></span></div></div>';
  html += '<div style="margin-bottom:10px">';
  html += '<div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:4px">Follow-Up Date</div>';
  html += '<div style="display:flex;gap:6px;align-items:center">';
  html += '<input type="date" id="cd-fu-'+id+'" value="'+esc(fu)+'" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 8px;font-size:12px">';
  html += '<button onclick="saveFollowUp('+id+')" style="background:#3b82f6;color:#fff;border:none;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:11px;font-weight:600">Save</button>';
  html += '<span id="cd-fu-st-'+id+'" style="font-size:11px;color:#34a853;min-width:20px"></span></div></div>';
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
  html += '<div style="margin-bottom:10px">';
  html += '<div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:6px">Notes</div>';
  html += '<div id="cd-notes-'+id+'" style="max-height:120px;overflow-y:auto;background:var(--card);border-radius:6px;padding:6px 8px;border:1px solid var(--border)">'+renderNotes(notesRaw)+'</div>';
  html += '<div style="display:flex;gap:6px;margin-top:6px">';
  html += '<input type="text" id="cd-note-in-'+id+'" placeholder="Add a note\u2026" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 8px;font-size:12px">';
  html += '<button onclick="addNote('+id+')" style="background:#e94560;color:#fff;border:none;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:11px;font-weight:600">Add</button>';
  html += '</div><div id="cd-note-st-'+id+'" style="font-size:11px;color:#34a853;margin-top:3px;min-height:14px"></div></div>';
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
  html += '<div>';
  html += '<div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:6px">Activities</div>';
  html += '<div id="cd-acts-'+id+'" style="font-size:12px;color:var(--text3)">Loading\u2026</div>';
  html += '</div>';
  return html;
}}

function openContactDetail(v) {{
  _cdVenue = v;
  const id = v.id;
  document.getElementById('cd-title').textContent = v[_nameField] || '(unnamed)';
  document.getElementById('cd-subtitle').innerHTML = statusBadge(sv(v['Contact Status']));
  document.getElementById('cd-detail-body').innerHTML = _buildDetailHTML(v);
  document.getElementById('cd-panel-detail').className = 'cd-panel active';
  document.getElementById('cd-panel-tpl').className    = 'cd-panel';
  document.getElementById('cd-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  fetchAll(ACTS_TID).then(acts => {{
    const mine = acts.filter(a => {{
      const lf = a[ACTS_LINK];
      return Array.isArray(lf) ? lf.some(r => r.id === id) : false;
    }}).sort((a,b) => (b['Date']||'').localeCompare(a['Date']||''));
    const el = document.getElementById('cd-acts-'+id);
    if (el) el.innerHTML = mine.length ? mine.map(renderAct).join('')
      : '<div style="color:var(--text3);padding:4px 0">No activities yet</div>';
  }});
}}

function closeContactDetail() {{
  document.getElementById('cd-overlay').classList.remove('open');
  document.body.style.overflow = '';
  _cdVenue = null;
}}

function showEmailTemplates(v, category) {{
  if (!v) return;
  const name = v[_nameField] || '(unnamed)';
  const tmpls = (_TEMPLATES[category] || []);
  let html = '<button class="cd-back-btn" onclick="_cdBackToDetail()">\u2190 Back to detail</button>';
  html += '<div style="font-size:13px;font-weight:600;margin-bottom:12px">Choose a template for <strong>' + esc(name) + '</strong></div>';
  html += '<div class="tpl-grid">';
  tmpls.forEach(function(t, i) {{
    const preview = t.body.replace(/\{{name\}}/g, name).substring(0, 160) + '\u2026';
    html += '<div class="tpl-card">';
    html += '<div class="tpl-card-name">' + esc(t.name) + '</div>';
    html += '<div class="tpl-card-subj">Subject: ' + esc(t.subject) + '</div>';
    html += '<div class="tpl-card-preview">' + esc(preview) + '</div>';
    html += '<button class="tpl-use-btn" data-tpl-i="'+i+'" data-tpl-cat="'+category+'" onclick="useTemplate(+this.dataset.tplI,this.dataset.tplCat)">Use Template \u2192</button>';
    html += '</div>';
  }});
  html += '</div>';
  document.getElementById('cd-tpl-body').innerHTML = html;
  document.getElementById('cd-panel-detail').className = 'cd-panel';
  document.getElementById('cd-panel-tpl').className    = 'cd-panel active';
}}

function _cdBackToDetail() {{
  document.getElementById('cd-panel-detail').className = 'cd-panel active';
  document.getElementById('cd-panel-tpl').className    = 'cd-panel';
}}

function useTemplate(i, category) {{
  const t = _TEMPLATES[category][i];
  if (!t || !_cdVenue) return;
  const name = _cdVenue[_nameField] || '';
  const body = t.body.replace(/\{{name\}}/g, name);
  document.getElementById('compose-to').value      = (_cdVenue['Email'] || '');
  document.getElementById('compose-subject').value = t.subject;
  document.getElementById('compose-body').value    = body;
  document.getElementById('compose-status').textContent = '';
  closeContactDetail();
  document.getElementById('compose-overlay').classList.add('open');
  setTimeout(function() {{
    var toVal = document.getElementById('compose-to').value;
    document.getElementById(toVal ? 'compose-subject' : 'compose-to').focus();
  }}, 50);
}}

async function updateStatus(id, val) {{
  const v = _venues.find(x => x.id === id);
  if (v) v['Contact Status'] = {{value: val}};
  const st = document.getElementById('cd-status-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  const r = await bpatch(VENUES_TID, id, {{'Contact Status': {{value: val}}}});
  if (st) {{ st.textContent = r.ok ? '\u2713' : '\u2717'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
}}

async function saveFollowUp(id) {{
  const val = (document.getElementById('cd-fu-' + id) || {{}}).value || null;
  const v = _venues.find(x => x.id === id);
  if (v) v['Follow-Up Date'] = val;
  const st = document.getElementById('cd-fu-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  const r = await bpatch(VENUES_TID, id, {{'Follow-Up Date': val || null}});
  if (st) {{ st.textContent = r.ok ? '\u2713' : '\u2717'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
}}

async function addNote(id) {{
  const inputEl = document.getElementById('cd-note-in-' + id);
  const text = (inputEl ? inputEl.value : '').trim();
  if (!text) return;
  const today = new Date().toISOString().split('T')[0];
  const entry = '[' + today + '] ' + text;
  const v = _venues.find(x => x.id === id);
  const existing = (v && v['Notes'] ? v['Notes'].trim() : '');
  const newNotes = existing ? entry + '\\n---\\n' + existing : entry;
  if (v) v['Notes'] = newNotes;
  if (inputEl) inputEl.value = '';
  const logEl = document.getElementById('cd-notes-' + id);
  if (logEl) logEl.innerHTML = renderNotes(newNotes);
  const st = document.getElementById('cd-note-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  const r = await bpatch(VENUES_TID, id, {{'Notes': newNotes}});
  if (st) {{ st.textContent = r.ok ? 'Saved \u2713' : 'Failed \u2717'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
}}

async function logActivity(id) {{
  const btn = document.getElementById('cd-abtn-' + id);
  const st  = document.getElementById('cd-act-st-' + id);
  if (btn) btn.disabled = true;
  if (st) st.textContent = 'Saving\u2026';
  const date    = (document.getElementById('cd-adate-' + id) || {{}}).value || null;
  const type    = (document.getElementById('cd-atype-' + id) || {{}}).value || 'Other';
  const outcome = (document.getElementById('cd-aoutcome-' + id) || {{}}).value || '';
  const person  = (document.getElementById('cd-aperson-' + id) || {{}}).value || '';
  const summary = (document.getElementById('cd-asummary-' + id) || {{}}).value || '';
  const fu      = (document.getElementById('cd-afu-' + id) || {{}}).value || null;
  const payload = {{[ACTS_LINK]: [{{id}}], 'Date': date, 'Type': {{value: type}},
    'Outcome': {{value: outcome}}, 'Contact Person': person, 'Summary': summary, 'Follow-Up Date': fu || null}};
  try {{
    const r = await bpost(ACTS_TID, payload);
    if (r.ok) {{
      const newAct = await r.json();
      const el = document.getElementById('cd-acts-' + id);
      if (el) el.innerHTML = renderAct(newAct) + (el.innerHTML.includes('No activities') ? '' : el.innerHTML);
      if (document.getElementById('cd-asummary-' + id)) document.getElementById('cd-asummary-' + id).value = '';
      if (document.getElementById('cd-aperson-' + id))  document.getElementById('cd-aperson-' + id).value  = '';
      if (document.getElementById('cd-afu-' + id))      document.getElementById('cd-afu-' + id).value      = '';
      if (fu) {{ const fuIn = document.getElementById('cd-fu-' + id); if (fuIn) {{ fuIn.value = fu; saveFollowUp(id); }} }}
      if (st) {{ st.textContent = 'Saved \u2713'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
    }} else {{
      if (st) st.textContent = 'Failed \u2717';
    }}
  }} catch(e) {{ if (st) st.textContent = 'Error: ' + e.message; }}
  if (btn) btn.disabled = false;
}}

function buildFilters() {{
  const bar = document.getElementById('filter-bar');
  bar.innerHTML =
    '<button class="filter-btn stage-btn on" data-stage="" onclick="setFilter(this)">All</button>' +
    _stages.map(s => '<button class="filter-btn stage-btn" data-stage="' + s + '" onclick="setFilter(this)">' + s + '</button>').join('') +
    '<input class="search-input" id="search-box" placeholder="Search name\u2026" oninput="applyFilters()" style="min-width:140px">' +
    '<div style="margin-left:auto;display:flex;gap:4px;align-items:center;flex-shrink:0">' +
    '<span style="font-size:11px;color:var(--text3)">Sort:</span>' +
    '<button id="sort-btn-distance" class="filter-btn sort-btn on" data-mode="distance" onclick="setSortMode(this.dataset.mode)">\U0001f4cd Distance</button>' +
    '<button id="sort-btn-alpha" class="filter-btn sort-btn" data-mode="alpha" onclick="setSortMode(this.dataset.mode)">A\u2013Z</button>' +
    '</div>';
}}

function setFilter(btn) {{
  document.querySelectorAll('.stage-btn').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  _stageFilter = btn.dataset.stage;
  applyFilters();
}}

function setSortMode(mode) {{
  _sortMode = mode;
  document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('on'));
  const active = document.getElementById('sort-btn-' + mode);
  if (active) active.classList.add('on');
  applyFilters();
}}

function statusBadge(status) {{
  const map = {{'Not Contacted':'sb-not','Contacted':'sb-cont','In Discussion':'sb-disc'}};
  const cls = status === _activeStatus ? 'sb-act' : (map[status] || 'sb-not');
  return '<span class="status-badge ' + cls + '">' + esc(status || 'Unknown') + '</span>';
}}

function applyFilters() {{
  const q = ((document.getElementById('search-box') || {{}}).value || '').toLowerCase();
  let filtered = _venues.filter(v => {{
    const name   = (v[_nameField] || '').toLowerCase();
    const status = sv(v['Contact Status']);
    return (!_stageFilter || status === _stageFilter) && (!q || name.includes(q));
  }});
  filtered = filtered.slice().sort((a, b) => {{
    if (_sortMode === 'alpha') return (a[_nameField]||'').localeCompare(b[_nameField]||'');
    const da = parseFloat(a['Distance (mi)']) || Infinity;
    const db = parseFloat(b['Distance (mi)']) || Infinity;
    return da - db;
  }});
  const cb = document.getElementById('count-bar');
  if (cb) cb.textContent = filtered.length + ' shown';
  const grid = document.getElementById('venue-grid');
  if (!filtered.length) {{ grid.innerHTML = '<div class="empty">No venues match this filter</div>'; return; }}
  grid.innerHTML = filtered.map(v => {{
    const name   = esc(v[_nameField] || '(unnamed)');
    const status = sv(v['Contact Status']);
    const phone  = esc(v[_phoneField] || '');
    const addr   = esc(v[_addrField]  || '');
    const fu     = v['Follow-Up Date'];
    const fuDays = daysUntil(fu);
    const fuColor = fuDays !== null && fuDays < 0 ? '#ef4444' : fuDays === 0 ? '#f59e0b' : 'var(--text3)';
    const dist   = v['Distance (mi)'] ? parseFloat(v['Distance (mi)']).toFixed(1) + ' mi' : '';
    return '<div class="venue-card" onclick="openContactDetail(_venues.find(x=>x.id==='+v.id+'))">'
      + '<div class="vc-name">' + name + '</div>'
      + (phone ? '<div class="vc-row"><span class="vc-icon">📞</span><span>' + phone + '</span></div>' : '')
      + (addr  ? '<div class="vc-row"><span class="vc-icon">📍</span><span>' + addr  + '</span></div>' : '')
      + '<div class="vc-foot">' + statusBadge(status)
      + (dist ? '<span style="font-size:11px;color:var(--text3)">' + dist + '</span>' : '')
      + (fu ? '<span style="font-size:11px;color:' + fuColor + '">Follow-up ' + fmt(fu) + '</span>' : '')
      + '</div></div>';
  }}).join('');
}}

async function load() {{
  document.getElementById('venue-grid').innerHTML = '<div class="loading">Loading\u2026</div>';
  _venues = await fetchAll({c["tid"]});
  buildFilters();
  applyFilters();
  stampRefresh();
}}

load();
{_TEMPLATES_JS}
"""
    return _page(active_key, c['label'], header, body, js, br, bt, user=user)


# ──────────────────────────────────────────────────────────────────────────────
# UNIFIED CONTACT LIST (all tools on one page, filter to load)
# ──────────────────────────────────────────────────────────────────────────────
def _unified_directory_page(br: str, bt: str, user: dict = None) -> str:
    import json as _json
    CONF = {
        'attorney':  {'label': 'PI Attorney',       'color': '#7c3aed', 'tid': T_ATT_VENUES,
                      'actsTid': T_ATT_ACTS,  'actLinkField': 'Law Firm',
                      'nameField': 'Law Firm Name',  'phoneField': 'Phone Number', 'addrField': 'Law Office Address',
                      'activeStatus': 'Active Relationship',
                      'stages': ['Not Contacted','Contacted','In Discussion','Active Relationship']},
        'gorilla':   {'label': 'Guerilla Marketing', 'color': '#ea580c', 'tid': T_GOR_VENUES,
                      'actsTid': T_GOR_ACTS,  'actLinkField': 'Business',
                      'nameField': 'Name',            'phoneField': 'Phone',        'addrField': 'Address',
                      'activeStatus': 'Active Partner',
                      'stages': ['Not Contacted','Contacted','In Discussion','Active Partner']},
        'community': {'label': 'Community',          'color': '#059669', 'tid': T_COM_VENUES,
                      'actsTid': T_COM_ACTS,  'actLinkField': 'Organization',
                      'nameField': 'Name',            'phoneField': 'Phone',        'addrField': 'Address',
                      'activeStatus': 'Active Partner',
                      'stages': ['Not Contacted','Contacted','In Discussion','Active Partner']},
    }
    conf_json = _json.dumps(CONF)

    header = (
        '<div class="header" style="background:linear-gradient(135deg,#1e3a5f22,transparent)">'
        '<div class="header-left">'
        '<h1>Outreach Contacts</h1>'
        '<div class="sub">All outreach venues across tools</div>'
        '</div></div>'
    )

    body = (
        '<div style="display:flex;gap:8px;padding:12px 18px;flex-wrap:wrap">'
        '<button class="filter-btn tool-btn" id="tb-attorney" data-tool="attorney" onclick="selectTool(\'attorney\',this)"'
        ' style="border:1px solid #7c3aed40;color:var(--text2)">'
        '\u2696 PI Attorney</button>'
        '<button class="filter-btn tool-btn" id="tb-gorilla" data-tool="gorilla" onclick="selectTool(\'gorilla\',this)"'
        ' style="border:1px solid #ea580c40;color:var(--text2)">'
        '\U0001f525 Guerilla</button>'
        '<button class="filter-btn tool-btn" id="tb-community" data-tool="community" onclick="selectTool(\'community\',this)"'
        ' style="border:1px solid #05966940;color:var(--text2)">'
        '\U0001f91d Community</button>'
        '</div>'
        '<div class="panel" style="margin-bottom:0">'
        '<div class="filter-bar" id="filter-bar" style="display:none"></div>'
        '<div id="count-bar" style="padding:4px 18px 8px;font-size:12px;color:var(--text3)"></div>'
        '<div class="venue-grid" id="venue-grid">'
        '<div class="empty" style="grid-column:1/-1;text-align:center;padding:60px 0">'
        '<div style="font-size:32px;margin-bottom:12px">\U0001f4cb</div>'
        '<div style="font-size:15px;font-weight:600;color:var(--text);margin-bottom:4px">Select a tool to view contacts</div>'
        '<div style="font-size:13px;color:var(--text3)">Choose PI Attorney, Guerilla, or Community above</div>'
        '</div></div></div>'
    )

    body += (
        '<div class="cd-overlay" id="cd-overlay" onclick="if(event.target===this)closeContactDetail()">'
        '<div class="cd-modal">'
        '<div class="cd-header">'
        '<div style="flex:1;min-width:0"><div class="cd-title" id="cd-title"></div>'
        '<div id="cd-subtitle" style="margin-top:4px"></div></div>'
        '<div class="cd-header-actions">'
        '<button class="cd-btn-email" onclick="showEmailTemplates(_cdVenue,_activeTool)" title="Email templates">\u2709 Email</button>'
        '<button class="cd-btn-close" onclick="closeContactDetail()">&times;</button>'
        '</div></div>'
        '<div class="cd-body">'
        '<div class="cd-panel active" id="cd-panel-detail"><div id="cd-detail-body"></div></div>'
        '<div class="cd-panel" id="cd-panel-tpl"><div id="cd-tpl-body"></div></div>'
        '</div></div></div>'
    )

    js = f"""
const _CONF = {conf_json};
let _activeTool = null;
let _nameField = '', _phoneField = '', _addrField = '', _activeStatus = '';
let _stages = [];
let VENUES_TID = 0, ACTS_TID = 0, ACTS_LINK = '';
let _venues = [];
let _stageFilter = '';
let _sortMode = 'alpha';
let _cdVenue = null;

async function bpatch(tid, id, data) {{
  return fetch(BR+'/api/database/rows/table/'+tid+'/'+id+'/?user_field_names=true',{{
    method:'PATCH',headers:{{'Authorization':'Token '+BT,'Content-Type':'application/json'}},
    body:JSON.stringify(data)}});
}}
async function bpost(tid, data) {{
  return fetch(BR+'/api/database/rows/table/'+tid+'/?user_field_names=true',{{
    method:'POST',headers:{{'Authorization':'Token '+BT,'Content-Type':'application/json'}},
    body:JSON.stringify(data)}});
}}

function selectTool(tool, btn) {{
  document.querySelectorAll('.tool-btn').forEach(function(b){{
    b.classList.remove('on'); b.style.background=''; b.style.color='var(--text2)';
  }});
  btn.classList.add('on');
  var c = _CONF[tool];
  btn.style.background = c.color + '20';
  btn.style.color = c.color;
  _activeTool = tool;
  _nameField = c.nameField; _phoneField = c.phoneField; _addrField = c.addrField;
  _activeStatus = c.activeStatus; _stages = c.stages;
  VENUES_TID = c.tid; ACTS_TID = c.actsTid; ACTS_LINK = c.actLinkField;
  _stageFilter = '';
  loadVenues();
}}

async function loadVenues() {{
  document.getElementById('filter-bar').style.display = 'flex';
  document.getElementById('venue-grid').innerHTML = '<div class="loading">Loading\u2026</div>';
  document.getElementById('count-bar').textContent = 'Loading\u2026';
  _venues = await fetchAll(VENUES_TID);
  buildFilters();
  applyFilters();
  stampRefresh();
}}

function stageOpts(cur) {{
  return _stages.map(function(s){{ return '<option value="'+s+'"'+(cur===s?' selected':'')+'>'+s+'</option>'; }}).join('');
}}

function renderNotes(text) {{
  if (!text || !text.trim()) return '<div style="color:var(--text3);font-size:12px;padding:4px 0">No notes yet</div>';
  return text.split('\\n---\\n').filter(function(e){{return e.trim();}}).map(function(entry) {{
    var m = entry.match(/^\\[(\d{{4}}-\d{{2}}-\d{{2}})\\] ([\\s\\S]*)$/);
    if (m) return '<div style="padding:5px 0;border-bottom:1px solid var(--border)">'
      + '<div style="font-size:10px;color:var(--text3);margin-bottom:2px">' + m[1] + '</div>'
      + '<div style="font-size:12px">' + esc(m[2].trim()) + '</div></div>';
    return '<div style="padding:5px 0;border-bottom:1px solid var(--border);font-size:12px">' + esc(entry.trim()) + '</div>';
  }}).join('');
}}

function renderAct(a) {{
  var type = a['Type'] ? (typeof a['Type'] === 'object' ? a['Type'].value : a['Type']) : '';
  var outcome = a['Outcome'] ? (typeof a['Outcome'] === 'object' ? a['Outcome'].value : a['Outcome']) : '';
  var date = a['Date'] || '';
  var person = a['Contact Person'] || '';
  var summary = a['Summary'] || '';
  var fu = a['Follow-Up Date'] || '';
  return '<div style="padding:8px 0;border-bottom:1px solid var(--border)">'
    + '<div style="display:flex;justify-content:space-between;margin-bottom:3px">'
    + '<span style="font-size:11px;font-weight:600;background:var(--badge-bg);padding:1px 6px;border-radius:4px">' + esc(type) + '</span>'
    + '<span style="font-size:11px;color:var(--text3)">' + esc(date) + '</span></div>'
    + (outcome ? '<div style="font-size:12px;color:var(--text2)">' + esc(outcome) + '</div>' : '')
    + (person  ? '<div style="font-size:11px;color:var(--text3)">with ' + esc(person) + '</div>' : '')
    + (summary ? '<div style="font-size:12px;margin-top:3px">' + esc(summary) + '</div>' : '')
    + (fu      ? '<div style="font-size:11px;color:#f59e0b;margin-top:2px">Follow-up: ' + esc(fu) + '</div>' : '')
    + '</div>';
}}

function _buildDetailHTML(v) {{
  var id  = v.id;
  var status = sv(v['Contact Status']);
  var phone   = esc(v[_phoneField] || '');
  var addr    = esc(v[_addrField]  || '');
  var website = v['Website'] || '';
  var fu      = v['Follow-Up Date'] || '';
  var notesRaw = v['Notes'] || '';
  var html = '';
  if (phone)   html += '<div style="font-size:13px;margin-bottom:6px">\u260e <a href="tel:'+phone+'" style="color:var(--text)">'+phone+'</a></div>';
  if (addr)    html += '<div style="font-size:12px;color:var(--text2);margin-bottom:6px">\U0001f4cd '+addr+'</div>';
  if (website) html += '<div style="font-size:12px;margin-bottom:10px">\U0001f310 <a href="'+esc(website)+'" target="_blank" style="color:#3b82f6">'+esc(website)+'</a></div>';
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
  html += '<div style="margin-bottom:8px">';
  html += '<div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:4px">Contact Status</div>';
  html += '<div style="display:flex;gap:6px;align-items:center">';
  html += '<select id="cd-status-'+id+'" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 8px;font-size:12px" onchange="updateStatus('+id+',this.value)">'+stageOpts(status)+'</select>';
  html += '<span id="cd-status-st-'+id+'" style="font-size:11px;color:#34a853;min-width:20px"></span></div></div>';
  html += '<div style="margin-bottom:10px">';
  html += '<div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:4px">Follow-Up Date</div>';
  html += '<div style="display:flex;gap:6px;align-items:center">';
  html += '<input type="date" id="cd-fu-'+id+'" value="'+esc(fu)+'" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 8px;font-size:12px">';
  html += '<button onclick="saveFollowUp('+id+')" style="background:#3b82f6;color:#fff;border:none;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:11px;font-weight:600">Save</button>';
  html += '<span id="cd-fu-st-'+id+'" style="font-size:11px;color:#34a853;min-width:20px"></span></div></div>';
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
  html += '<div style="margin-bottom:10px">';
  html += '<div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:6px">Notes</div>';
  html += '<div id="cd-notes-'+id+'" style="max-height:120px;overflow-y:auto;background:var(--card);border-radius:6px;padding:6px 8px;border:1px solid var(--border)">'+renderNotes(notesRaw)+'</div>';
  html += '<div style="display:flex;gap:6px;margin-top:6px">';
  html += '<input type="text" id="cd-note-in-'+id+'" placeholder="Add a note\u2026" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 8px;font-size:12px">';
  html += '<button onclick="addNote('+id+')" style="background:#e94560;color:#fff;border:none;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:11px;font-weight:600">Add</button>';
  html += '</div><div id="cd-note-st-'+id+'" style="font-size:11px;color:#34a853;margin-top:3px;min-height:14px"></div></div>';
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
  html += '<div>';
  html += '<div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:6px">Activities</div>';
  html += '<div id="cd-acts-'+id+'" style="font-size:12px;color:var(--text3)">Loading\u2026</div>';
  html += '</div>';
  return html;
}}

function openContactDetail(v) {{
  _cdVenue = v;
  var id = v.id;
  document.getElementById('cd-title').textContent = v[_nameField] || '(unnamed)';
  document.getElementById('cd-subtitle').innerHTML = statusBadge(sv(v['Contact Status']));
  document.getElementById('cd-detail-body').innerHTML = _buildDetailHTML(v);
  document.getElementById('cd-panel-detail').className = 'cd-panel active';
  document.getElementById('cd-panel-tpl').className    = 'cd-panel';
  document.getElementById('cd-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  fetchAll(ACTS_TID).then(function(acts) {{
    var mine = acts.filter(function(a) {{
      var lf = a[ACTS_LINK];
      return Array.isArray(lf) ? lf.some(function(r){{return r.id === id;}}) : false;
    }}).sort(function(a,b){{ return (b['Date']||'').localeCompare(a['Date']||''); }});
    var el = document.getElementById('cd-acts-'+id);
    if (el) el.innerHTML = mine.length ? mine.map(renderAct).join('')
      : '<div style="color:var(--text3);padding:4px 0">No activities yet</div>';
  }});
}}

function closeContactDetail() {{
  document.getElementById('cd-overlay').classList.remove('open');
  document.body.style.overflow = '';
  _cdVenue = null;
}}

function showEmailTemplates(v, category) {{
  if (!v || !category) return;
  var name = v[_nameField] || '(unnamed)';
  var tmpls = (_TEMPLATES[category] || []);
  var html = '<button class="cd-back-btn" onclick="_cdBackToDetail()">\u2190 Back to detail</button>';
  html += '<div style="font-size:13px;font-weight:600;margin-bottom:12px">Choose a template for <strong>' + esc(name) + '</strong></div>';
  html += '<div class="tpl-grid">';
  tmpls.forEach(function(t, i) {{
    var preview = t.body.replace(/\\{{name\\}}/g, name).substring(0, 160) + '\u2026';
    html += '<div class="tpl-card">';
    html += '<div class="tpl-card-name">' + esc(t.name) + '</div>';
    html += '<div class="tpl-card-subj">Subject: ' + esc(t.subject) + '</div>';
    html += '<div class="tpl-card-preview">' + esc(preview) + '</div>';
    html += '<button class="tpl-use-btn" data-tpl-i="'+i+'" data-tpl-cat="'+category+'" onclick="useTemplate(+this.dataset.tplI,this.dataset.tplCat)">Use Template \u2192</button>';
    html += '</div>';
  }});
  html += '</div>';
  document.getElementById('cd-tpl-body').innerHTML = html;
  document.getElementById('cd-panel-detail').className = 'cd-panel';
  document.getElementById('cd-panel-tpl').className    = 'cd-panel active';
}}

function _cdBackToDetail() {{
  document.getElementById('cd-panel-detail').className = 'cd-panel active';
  document.getElementById('cd-panel-tpl').className    = 'cd-panel';
}}

function useTemplate(i, category) {{
  var t = _TEMPLATES[category][i];
  if (!t || !_cdVenue) return;
  var name = _cdVenue[_nameField] || '';
  var body = t.body.replace(/\\{{name\\}}/g, name);
  document.getElementById('compose-to').value      = (_cdVenue['Email'] || '');
  document.getElementById('compose-subject').value = t.subject;
  document.getElementById('compose-body').value    = body;
  document.getElementById('compose-status').textContent = '';
  closeContactDetail();
  document.getElementById('compose-overlay').classList.add('open');
  setTimeout(function() {{
    var toVal = document.getElementById('compose-to').value;
    document.getElementById(toVal ? 'compose-subject' : 'compose-to').focus();
  }}, 50);
}}

async function updateStatus(id, val) {{
  var v = _venues.find(function(x){{return x.id === id;}});
  if (v) v['Contact Status'] = {{value: val}};
  var st = document.getElementById('cd-status-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  var r = await bpatch(VENUES_TID, id, {{'Contact Status': val}});
  if (st) {{ st.textContent = r.ok ? '\u2713' : '\u2717'; setTimeout(function(){{ if(st) st.textContent=''; }}, 2000); }}
}}

async function saveFollowUp(id) {{
  var val = (document.getElementById('cd-fu-' + id) || {{}}).value || null;
  var v = _venues.find(function(x){{return x.id === id;}});
  if (v) v['Follow-Up Date'] = val;
  var st = document.getElementById('cd-fu-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  var r = await bpatch(VENUES_TID, id, {{'Follow-Up Date': val || null}});
  if (st) {{ st.textContent = r.ok ? '\u2713' : '\u2717'; setTimeout(function(){{ if(st) st.textContent=''; }}, 2000); }}
}}

async function addNote(id) {{
  var inputEl = document.getElementById('cd-note-in-' + id);
  var text = (inputEl ? inputEl.value : '').trim();
  if (!text) return;
  var today = new Date().toISOString().split('T')[0];
  var entry = '[' + today + '] ' + text;
  var v = _venues.find(function(x){{return x.id === id;}});
  var existing = (v && v['Notes'] ? v['Notes'].trim() : '');
  var newNotes = existing ? entry + '\\n---\\n' + existing : entry;
  if (v) v['Notes'] = newNotes;
  if (inputEl) inputEl.value = '';
  var logEl = document.getElementById('cd-notes-' + id);
  if (logEl) logEl.innerHTML = renderNotes(newNotes);
  var st = document.getElementById('cd-note-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  var r = await bpatch(VENUES_TID, id, {{'Notes': newNotes}});
  if (st) {{ st.textContent = r.ok ? 'Saved \u2713' : 'Failed \u2717'; setTimeout(function(){{ if(st) st.textContent=''; }}, 2000); }}
}}

function buildFilters() {{
  var bar = document.getElementById('filter-bar');
  bar.innerHTML =
    '<button class="filter-btn stage-btn on" data-stage="" onclick="setFilter(this)">All</button>' +
    _stages.map(function(s){{ return '<button class="filter-btn stage-btn" data-stage="' + s + '" onclick="setFilter(this)">' + s + '</button>'; }}).join('') +
    '<input class="search-input" id="search-box" placeholder="Search name\u2026" oninput="applyFilters()" style="min-width:140px">' +
    '<div style="margin-left:auto;display:flex;gap:4px;align-items:center;flex-shrink:0">' +
    '<span style="font-size:11px;color:var(--text3)">Sort:</span>' +
    '<button id="sort-btn-distance" class="filter-btn sort-btn" data-mode="distance" onclick="setSortMode(this.dataset.mode)">\U0001f4cd Distance</button>' +
    '<button id="sort-btn-alpha" class="filter-btn sort-btn on" data-mode="alpha" onclick="setSortMode(this.dataset.mode)">A\u2013Z</button>' +
    '</div>';
}}

function setFilter(btn) {{
  document.querySelectorAll('.stage-btn').forEach(function(b){{b.classList.remove('on');}});
  btn.classList.add('on');
  _stageFilter = btn.dataset.stage;
  applyFilters();
}}

function setSortMode(mode) {{
  _sortMode = mode;
  document.querySelectorAll('.sort-btn').forEach(function(b){{b.classList.remove('on');}});
  var active = document.getElementById('sort-btn-' + mode);
  if (active) active.classList.add('on');
  applyFilters();
}}

function statusBadge(status) {{
  var map = {{'Not Contacted':'sb-not','Contacted':'sb-cont','In Discussion':'sb-disc'}};
  var cls = status === _activeStatus ? 'sb-act' : (map[status] || 'sb-not');
  return '<span class="status-badge ' + cls + '">' + esc(status || 'Unknown') + '</span>';
}}

function applyFilters() {{
  var q = ((document.getElementById('search-box') || {{}}).value || '').toLowerCase();
  var filtered = _venues.filter(function(v) {{
    var name   = (v[_nameField] || '').toLowerCase();
    var status = sv(v['Contact Status']);
    return (!_stageFilter || status === _stageFilter) && (!q || name.includes(q));
  }});
  filtered = filtered.slice().sort(function(a, b) {{
    if (_sortMode === 'alpha') return (a[_nameField]||'').localeCompare(b[_nameField]||'');
    var da = parseFloat(a['Distance (mi)']) || Infinity;
    var db = parseFloat(b['Distance (mi)']) || Infinity;
    return da - db;
  }});
  var cb = document.getElementById('count-bar');
  if (cb) cb.textContent = filtered.length + ' shown';
  var grid = document.getElementById('venue-grid');
  if (!filtered.length) {{ grid.innerHTML = '<div class="empty">No venues match this filter</div>'; return; }}
  grid.innerHTML = filtered.map(function(v) {{
    var name   = esc(v[_nameField] || '(unnamed)');
    var status = sv(v['Contact Status']);
    var phone  = esc(v[_phoneField] || '');
    var addr   = esc(v[_addrField]  || '');
    var fu     = v['Follow-Up Date'];
    var fuDays = daysUntil(fu);
    var fuColor = fuDays !== null && fuDays < 0 ? '#ef4444' : fuDays === 0 ? '#f59e0b' : 'var(--text3)';
    var dist   = v['Distance (mi)'] ? parseFloat(v['Distance (mi)']).toFixed(1) + ' mi' : '';
    return '<div class="venue-card" onclick="openContactDetail(_venues.find(function(x){{return x.id==='+v.id+'}}))">'
      + '<div class="vc-name">' + name + '</div>'
      + (phone ? '<div class="vc-row"><span class="vc-icon">\U0001f4de</span><span>' + phone + '</span></div>' : '')
      + (addr  ? '<div class="vc-row"><span class="vc-icon">\U0001f4cd</span><span>' + addr  + '</span></div>' : '')
      + '<div class="vc-foot">' + statusBadge(status)
      + (dist ? '<span style="font-size:11px;color:var(--text3)">' + dist + '</span>' : '')
      + (fu ? '<span style="font-size:11px;color:' + fuColor + '">Follow-up ' + fmt(fu) + '</span>' : '')
      + '</div></div>';
  }}).join('');
}}

{_TEMPLATES_JS}
"""
    return _page('outreach_contacts', 'Outreach Contacts', header, body, js, br, bt, user=user)


# ──────────────────────────────────────────────────────────────────────────────
# MAP DIRECTORY (shared template for Attorney / Gorilla / Community)
# ──────────────────────────────────────────────────────────────────────────────
def _map_page(tool_key: str, br: str, bt: str, user: dict = None) -> str:
    gk = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    CONF = {
        'attorney':  {'label': 'PI Attorney',       'color': '#7c3aed', 'tid': T_ATT_VENUES,
                      'actsTid': T_ATT_ACTS,   'actLinkField': 'Law Firm',
                      'nameField': 'Law Firm Name', 'activeStatus': 'Active Relationship',
                      'addrField': 'Law Office Address', 'phoneField': 'Phone Number',
                      'stages': ['Not Contacted','Contacted','In Discussion','Active Relationship']},
        'gorilla':   {'label': 'Guerilla Marketing', 'color': '#ea580c', 'tid': T_GOR_VENUES,
                      'actsTid': T_GOR_ACTS,   'actLinkField': 'Business',
                      'nameField': 'Name', 'activeStatus': 'Active Partner',
                      'addrField': 'Address', 'phoneField': 'Phone',
                      'stages': ['Not Contacted','Contacted','In Discussion','Active Partner']},
        'community': {'label': 'Community',          'color': '#059669', 'tid': T_COM_VENUES,
                      'actsTid': T_COM_ACTS,   'actLinkField': 'Organization',
                      'nameField': 'Name', 'activeStatus': 'Active Partner',
                      'addrField': 'Address', 'phoneField': 'Phone',
                      'stages': ['Not Contacted','Contacted','In Discussion','Active Partner']},
    }
    c = CONF[tool_key]
    map_key = tool_key + '_map'

    # Case-count block + patient cross-reference JS (attorney only)
    if tool_key == 'attorney':
        cases_block = (
            "<div style='display:grid;grid-template-columns:repeat(5,1fr);gap:4px;margin:10px 0;"
            "background:var(--card);border-radius:8px;padding:10px;text-align:center'>"
            "<div><div style='font-size:16px;font-weight:700;color:#a78bfa'>${_fc.active||0}</div>"
            "<div style='font-size:10px;color:var(--text3)'>Active</div></div>"
            "<div><div style='font-size:16px;font-weight:700;color:#fbbf24'>${_fc.billed||0}</div>"
            "<div style='font-size:10px;color:var(--text3)'>Billed</div></div>"
            "<div><div style='font-size:16px;font-weight:700;color:#60a5fa'>${_fc.awaiting||0}</div>"
            "<div style='font-size:10px;color:var(--text3)'>Awaiting</div></div>"
            "<div><div style='font-size:16px;font-weight:700;color:#34d399'>${_fc.settled||0}</div>"
            "<div style='font-size:10px;color:var(--text3)'>Settled</div></div>"
            "<div><div style='font-size:16px;font-weight:700'>${(_fc.active||0)+(_fc.billed||0)+(_fc.awaiting||0)+(_fc.settled||0)}</div>"
            "<div style='font-size:10px;color:var(--text3)'>Total</div></div>"
            "</div><hr style='border:none;border-top:1px solid var(--border);margin:8px 0'>"
        )
        firm_counts_globals = f"""
let _firmCounts = {{}};
function normName(n) {{ return (n || '').toLowerCase().trim(); }}
function _getFirmName(p) {{
  const raw = p['Law Firm Name ONLY'] || p['Law Firm Name'] || p['Law Firm'] || '';
  if (!raw) return '';
  if (Array.isArray(raw)) return raw.length ? (raw[0].value || String(raw[0])) : '';
  if (typeof raw === 'object' && raw.value) return raw.value;
  return String(raw);
}}
function _lookupFirmCounts(name) {{
  const key = normName(name);
  if (_firmCounts[key]) return _firmCounts[key];
  for (const [k, v] of Object.entries(_firmCounts)) {{
    const shorter = key.length <= k.length ? key : k;
    const longer  = key.length <= k.length ? k   : key;
    if (shorter.length >= 8 && longer.includes(shorter)) return v;
  }}
  return {{}};
}}"""
        firm_counts_load = f"""
  Promise.all([fetchAll({T_PI_ACTIVE}),fetchAll({T_PI_BILLED}),fetchAll({T_PI_AWAITING}),fetchAll({T_PI_CLOSED})]).then(([a,b,w,c]) => {{
    const tally = (rows, key) => rows.forEach(r => {{ const k = normName(_getFirmName(r)); if (k) {{ _firmCounts[k] = _firmCounts[k] || {{active:0,billed:0,awaiting:0,settled:0}}; _firmCounts[k][key]++; }} }});
    tally(a,'active'); tally(b,'billed'); tally(w,'awaiting'); tally(c,'settled');
  }});"""
        fc_init = "const _fc = _lookupFirmCounts(v[_nameField]||'');"
        prev_rel_badge = """if (_fc.active === 0 && (_fc.billed+_fc.awaiting+_fc.settled) > 0) html += ' <span style="font-size:10px;padding:2px 6px;border-radius:4px;background:#7c3aed22;color:#a78bfa;font-weight:600">Previous Relationship</span>';"""
    else:
        cases_block = ""
        firm_counts_globals = ""
        firm_counts_load = ""
        fc_init = ""
        prev_rel_badge = ""

    # Log Event button — opens External Event form pre-filled
    log_visit_btn_js = (
        """html += '<button onclick="openLogEvent()" """
        """style="width:100%;background:var(--bg2);color:var(--text);border:1px solid var(--border);"""
        """border-radius:7px;padding:9px 12px;font-size:13px;font-weight:600;cursor:pointer;margin-bottom:6px">"""
        """Log Event &#x2192;</button>';"""
    )

    # Removed — External Event is now the default Log Event action for all tools
    external_event_btn_js = ''

    _uname = (user or {}).get('name', '')
    header = ''
    body = (
        _GFR_CSS + _GFR_HTML + _GFR_FORMS345_HTML + _GFR_FORM2_HTML
        + '<style>.content{padding:0 !important;}'
        '#map-sidebar{width:380px;overflow-y:auto;overflow-x:hidden;background:var(--bg2);'
        'border-left:1px solid var(--border);padding:0;flex-shrink:0;'
        'transform:translateX(100%);opacity:0;position:absolute;right:0;top:0;bottom:0;'
        'transition:transform .25s ease,opacity .2s ease;z-index:10;}'
        '#map-sidebar.open{transform:translateX(0);opacity:1;}'
        '#map-sidebar .sb-content{transition:opacity .15s ease;}'
        '#map-sidebar .sb-content.fading{opacity:0;}'
        '</style>'
        '<div id="filter-bar" style="display:flex;align-items:center;gap:6px;padding:6px 14px;'
        'background:var(--bg2);border-bottom:1px solid var(--border);flex-wrap:wrap">'
        '<div class="loading">Loading\u2026</div>'
        '</div>'
        '<div id="map-view" style="height:calc(100vh - 88px);position:relative">'
        '<div id="gmap" style="width:100%;height:100%"></div>'
        '<div id="map-sidebar"></div>'
        '</div>'
    )
    stages_json = str(c['stages']).replace("'", '"')
    js = f"""
const GK = '{gk}';
const OFFICE_LAT = 33.9478, OFFICE_LNG = -118.1335;
const VENUES_TID = {c['tid']};
const ACTS_TID = {c['actsTid']};
const ACTS_LINK = '{c['actLinkField']}';
let _venues = [];
let _stageFilter = '';
let _map = null;
let _markerMap = {{}};
let _selectedId = null;
let _currentVenue = null;
const _stages = {stages_json};
const _activeStatus = '{c["activeStatus"]}';
const _nameField = '{c["nameField"]}';
const _addrField = '{c["addrField"]}';
const _phoneField = '{c["phoneField"]}';
{firm_counts_globals}

// ─── Baserow write helpers ───────────────────────────────────────────────────
async function bpatch(tid, id, data) {{
  return fetch(BR + '/api/database/rows/table/' + tid + '/' + id + '/?user_field_names=true', {{
    method: 'PATCH',
    headers: {{'Authorization': 'Token ' + BT, 'Content-Type': 'application/json'}},
    body: JSON.stringify(data)
  }});
}}
async function bpost(tid, data) {{
  return fetch(BR + '/api/database/rows/table/' + tid + '/?user_field_names=true', {{
    method: 'POST',
    headers: {{'Authorization': 'Token ' + BT, 'Content-Type': 'application/json'}},
    body: JSON.stringify(data)
  }});
}}

// ─── Filters ─────────────────────────────────────────────────────────────────
function buildFilters() {{
  const bar = document.getElementById('filter-bar');
  bar.innerHTML = '<button class="filter-btn on" data-stage="" onclick="setFilter(this)" style="padding:3px 9px;font-size:11px">All</button>'
    + _stages.map(s => '<button class="filter-btn" data-stage="' + s + '" onclick="setFilter(this)" style="padding:3px 9px;font-size:11px">' + s + '</button>').join('')
    + '<input class="search-input" id="search-box" placeholder="Search name\u2026" oninput="applyFilters()" style="min-width:100px;max-width:160px;padding:3px 8px;font-size:11px">'
    + '<span id="count-bar" style="margin-left:auto;font-size:11px;color:var(--text3)">Loading\u2026</span>';
}}

function statusBadge(status) {{
  const map = {{'Not Contacted':'sb-not','Contacted':'sb-cont','In Discussion':'sb-disc'}};
  const cls = status === _activeStatus ? 'sb-act' : (map[status] || 'sb-not');
  return '<span class="status-badge ' + cls + '">' + esc(status || 'Unknown') + '</span>';
}}

function setFilter(btn) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  _stageFilter = btn.dataset.stage;
  applyFilters();
}}

function applyFilters() {{
  const q = (document.getElementById('search-box') ? document.getElementById('search-box').value || '' : '').toLowerCase();
  const filtered = _venues.filter(v => {{
    const name = (v[_nameField] || '').toLowerCase();
    const status = sv(v['Contact Status']);
    return (!_stageFilter || status === _stageFilter) && (!q || name.includes(q));
  }});
  const cb = document.getElementById('count-bar');
  if (cb) cb.textContent = filtered.length + ' shown';
  renderMarkers();
}}

// ─── Google Maps ─────────────────────────────────────────────────────────────
const _STATUS_COLORS = {{'Not Contacted':'#4285f4','Contacted':'#fbbc04','In Discussion':'#ff9800'}};
function _pinColor(s) {{ return s === _activeStatus ? '#34a853' : (_STATUS_COLORS[s] || '#9e9e9e'); }}
function _pinIcon(color) {{
  return {{ path: google.maps.SymbolPath.CIRCLE, scale: 6,
            fillColor: color, fillOpacity: 1, strokeColor: '#fff', strokeWeight: 1 }};
}}
function _pinIconSelected(color) {{
  return {{ path: google.maps.SymbolPath.CIRCLE, scale: 10,
            fillColor: color, fillOpacity: 1, strokeColor: '#fff', strokeWeight: 2 }};
}}

function initMap() {{
  if (!GK) {{ document.getElementById('gmap').innerHTML = '<div style="padding:40px;text-align:center;color:var(--text3)">Google Maps API key not configured.</div>'; return; }}
  window._mapReadyCb = function() {{
    _map = new google.maps.Map(document.getElementById('gmap'), {{
      center: {{lat: OFFICE_LAT, lng: OFFICE_LNG}}, zoom: 12,
      mapTypeControl: false, streetViewControl: false, clickableIcons: false,
      styles: [{{featureType:'poi',stylers:[{{visibility:'off'}}]}},
               {{featureType:'transit',stylers:[{{visibility:'off'}}]}},
               {{featureType:'administrative.neighborhood',stylers:[{{visibility:'off'}}]}},
               {{featureType:'administrative.locality',elementType:'labels.icon',stylers:[{{visibility:'off'}}]}}]
    }});
    new google.maps.Marker({{ position: {{lat: OFFICE_LAT, lng: OFFICE_LNG}}, map: _map,
      title: 'Reform Chiropractic',
      icon: {{ url: 'http://maps.google.com/mapfiles/ms/icons/red-dot.png' }}
    }});
    renderMarkers();
  }};
  const s = document.createElement('script');
  s.src = 'https://maps.googleapis.com/maps/api/js?key=' + GK + '&callback=_mapReadyCb';
  s.async = true; document.head.appendChild(s);
}}

function renderMarkers() {{
  if (!_map) return;
  Object.values(_markerMap).forEach(m => m.setMap(null));
  _markerMap = {{}};
  const q = (document.getElementById('search-box') ? document.getElementById('search-box').value || '' : '').toLowerCase();
  _venues.forEach(v => {{
    const lat = parseFloat(v['Latitude']), lng = parseFloat(v['Longitude']);
    if (!lat || !lng) return;
    const status = sv(v['Contact Status']);
    if (_stageFilter && status !== _stageFilter) return;
    if (q && !(v[_nameField] || '').toLowerCase().includes(q)) return;
    const marker = new google.maps.Marker({{
      position: {{lat, lng}}, map: _map, title: v[_nameField] || '',
      icon: _pinIcon(_pinColor(status))
    }});
    marker.addListener('click', () => showMapDetail(v));
    _markerMap[v.id] = marker;
  }});
}}

function closeSidebar() {{
  const sb = document.getElementById('map-sidebar');
  if (sb) sb.classList.remove('open');
  if (_selectedId && _markerMap[_selectedId]) {{
    const v = _venues.find(x => x.id === _selectedId);
    const s = v ? sv(v['Contact Status']) : '';
    _markerMap[_selectedId].setIcon(_pinIcon(_pinColor(s)));
  }}
  _selectedId = null;
  _currentVenue = null;
}}

// ─── Rich sidebar ────────────────────────────────────────────────────────────
function renderNotes(text) {{
  if (!text || !text.trim()) return '<div style="color:var(--text3);font-size:12px;padding:4px 0">No notes yet</div>';
  return text.split('\\n---\\n').filter(e => e.trim()).map(entry => {{
    const m = entry.match(/^\\[(\\d{{4}}-\\d{{2}}-\\d{{2}})\\] ([\\s\\S]*)$/);
    if (m) return '<div style="padding:5px 0;border-bottom:1px solid var(--border)">'
      + '<div style="font-size:10px;color:var(--text3);margin-bottom:2px">' + m[1] + '</div>'
      + '<div style="font-size:12px">' + esc(m[2].trim()) + '</div></div>';
    return '<div style="padding:5px 0;border-bottom:1px solid var(--border);font-size:12px">' + esc(entry.trim()) + '</div>';
  }}).join('');
}}

function renderAct(a) {{
  const type = a['Type'] ? (typeof a['Type'] === 'object' ? a['Type'].value : a['Type']) : '';
  const outcome = a['Outcome'] ? (typeof a['Outcome'] === 'object' ? a['Outcome'].value : a['Outcome']) : '';
  const date = a['Date'] || '';
  const person = a['Contact Person'] || '';
  const summary = a['Summary'] || '';
  const fu = a['Follow-Up Date'] || '';
  return '<div style="padding:8px 0;border-bottom:1px solid var(--border)">'
    + '<div style="display:flex;justify-content:space-between;margin-bottom:3px">'
    + '<span style="font-size:11px;font-weight:600;background:var(--badge-bg);padding:1px 6px;border-radius:4px">' + esc(type) + '</span>'
    + '<span style="font-size:11px;color:var(--text3)">' + esc(date) + '</span></div>'
    + (outcome ? '<div style="font-size:12px;color:var(--text2)">' + esc(outcome) + '</div>' : '')
    + (person  ? '<div style="font-size:11px;color:var(--text3)">with ' + esc(person) + '</div>' : '')
    + (summary ? '<div style="font-size:12px;margin-top:3px">' + esc(summary) + '</div>' : '')
    + (fu      ? '<div style="font-size:11px;color:#f59e0b;margin-top:2px">Follow-up: ' + esc(fu) + '</div>' : '')
    + '</div>';
}}

function stageOpts(cur) {{
  return _stages.map(s => '<option value="' + s + '"' + (cur === s ? ' selected' : '') + '>' + s + '</option>').join('');
}}

async function showMapDetail(v) {{
  const sb = document.getElementById('map-sidebar');
  const id = v.id;
  // Deselect previous pin
  if (_selectedId && _selectedId !== id && _markerMap[_selectedId]) {{
    const prev = _venues.find(x => x.id === _selectedId);
    const ps = prev ? sv(prev['Contact Status']) : '';
    _markerMap[_selectedId].setIcon(_pinIcon(_pinColor(ps)));
  }}
  // Highlight new pin
  _selectedId = id;
  _currentVenue = v;
  const curStatus = sv(v['Contact Status']);
  if (_markerMap[id]) _markerMap[id].setIcon(_pinIconSelected(_pinColor(curStatus)));

  {fc_init}
  const name    = esc(v[_nameField] || '(unnamed)');
  const status  = curStatus;
  const phone   = esc(v[_phoneField] || '');
  const addr    = esc(v[_addrField]  || '');
  const website = v['Website'] || '';
  const rating  = v['Rating'] || '';
  const reviews = v['Reviews'] || '';
  const dist    = v['Distance (mi)'] || '';
  const _placeId = v['Google Place ID'] || '';
  const gmUrl   = v['Google Maps URL'] || (_placeId ? 'https://www.google.com/maps/place/?q=place_id:' + _placeId : '');
  const yelpUrl = v['Yelp Search URL'] || '';
  const fu      = v['Follow-Up Date'] || '';
  const classif = sv(v['Classification'] || v['Type'] || '');
  const notesRaw = v['Notes'] || '';

  let html = '<div style="padding:16px 18px 10px">';
  html += '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">';
  html += '<div style="font-size:16px;font-weight:700;line-height:1.3;padding-right:8px">' + name + '</div>';
  html += '<button onclick="closeSidebar()" style="background:none;border:none;color:var(--text3);cursor:pointer;font-size:18px;line-height:1;flex-shrink:0">&times;</button>';
  html += '</div>';
  if (classif) html += '<span style="background:#1565C0;color:#fff;font-size:10px;padding:2px 7px;border-radius:4px;margin-right:4px">' + esc(classif) + '</span>';
  html += statusBadge(status);
  {prev_rel_badge}
  html += `{cases_block}`;
  html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
  html += '<div style="padding:0 0 10px">';
  if (phone) html += '<div style="font-size:13px;margin-bottom:10px">&#128222; <a href="tel:' + phone + '" style="color:var(--text)">' + phone + '</a></div>';
  if (addr)  html += '<div style="font-size:12px;color:var(--text2);margin-bottom:10px">&#128205; ' + addr + '</div>';
  if (website) html += '<div style="font-size:12px;margin-bottom:10px;word-break:break-all">&#127760; <a href="' + esc(website) + '" target="_blank" style="color:#3b82f6">' + esc(website) + '</a></div>';
  if (gmUrl || yelpUrl) {{
    html += '<div style="display:flex;gap:10px;font-size:12px;margin-bottom:10px">';
    if (gmUrl)   html += '<a href="' + esc(gmUrl)   + '" target="_blank" style="color:#3b82f6">Google Maps &#x2197;</a>';
    if (yelpUrl) html += '<a href="' + esc(yelpUrl) + '" target="_blank" style="color:#f97316">Yelp &#x2197;</a>';
    html += '</div>';
  }}
  if (rating) {{
    const stars = '\u2605'.repeat(Math.min(5, Math.round(parseFloat(rating)||0)));
    html += '<div style="font-size:12px;margin-bottom:10px">' + stars + ' ' + esc(rating) + (reviews ? ' (' + reviews + ' reviews)' : '') + '</div>';
  }}
  if (dist) html += '<div style="font-size:11px;color:var(--text3);margin-bottom:10px">' + esc(dist) + ' mi from office</div>';
  html += '</div>';

  html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
  html += '<div style="margin-bottom:10px"><div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:4px">Contact Status</div>';
  html += '<div style="display:flex;gap:6px;align-items:center">';
  html += '<select id="sb-status-' + id + '" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:7px 10px;font-size:12px" onchange="updateStatus(' + id + ',this.value)">' + stageOpts(status) + '</select>';
  html += '<span id="sb-status-st-' + id + '" style="font-size:11px;color:#34a853;min-width:30px"></span></div></div>';

  html += '<div style="margin-bottom:10px"><div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:4px">Follow-Up Date</div>';
  html += '<div style="display:flex;gap:6px;align-items:center">';
  html += '<input type="date" id="sb-fu-' + id + '" value="' + esc(fu) + '" style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:7px 10px;font-size:12px">';
  html += '<button onclick="saveFollowUp(' + id + ')" style="background:#3b82f6;color:#fff;border:none;border-radius:7px;padding:7px 10px;cursor:pointer;font-size:11px;font-weight:600">Save</button>';
  html += '<span id="sb-fu-st-' + id + '" style="font-size:11px;color:#34a853;min-width:20px"></span></div></div>';

  html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
  {log_visit_btn_js}
  {external_event_btn_js}

  html += '<div style="padding:18px"><div style="margin-bottom:10px"><div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:6px">Notes</div>';
  html += '<div id="sb-notes-' + id + '" style="max-height:120px;overflow-y:auto;background:var(--card);border-radius:7px;padding:8px 10px;border:1px solid var(--border);font-size:12px">' + renderNotes(notesRaw) + '</div>';
  html += '<div style="display:flex;gap:6px;margin-top:6px">';
  html += '<input type="text" id="sb-note-in-' + id + '" placeholder="Add a note..." style="flex:1;background:var(--input-bg);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:7px 10px;font-size:12px">';
  html += '<button onclick="addNote(' + id + ')" style="background:#e94560;color:#fff;border:none;border-radius:7px;padding:7px 10px;cursor:pointer;font-size:11px;font-weight:600">Add</button>';
  html += '</div><div id="sb-note-st-' + id + '" style="font-size:11px;color:#34a853;margin-top:3px"></div></div>';

  html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
  html += '<div id="sb-act-section-' + id + '"><div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;margin-bottom:6px">Activities</div>';
  html += '<div id="sb-acts-' + id + '" style="font-size:12px;color:var(--text3)">Loading activities\u2026</div>';
  html += '</div>';
  html += '</div>';  // close info panel padding wrapper

  const wasOpen = sb.classList.contains('open');
  if (wasOpen) {{
    sb.innerHTML = '<div class="sb-content fading">' + html + '</div>';
    requestAnimationFrame(() => {{
      const c = sb.querySelector('.sb-content');
      if (c) c.classList.remove('fading');
    }});
  }} else {{
    sb.innerHTML = '<div class="sb-content">' + html + '</div>';
    sb.classList.add('open');
  }}

  // Fetch activities async
  fetchAll(ACTS_TID).then(acts => {{
    const mine = acts.filter(a => {{
      const lf = a[ACTS_LINK];
      return Array.isArray(lf) ? lf.some(r => r.id === id) : false;
    }}).sort((a,b) => (b['Date']||'').localeCompare(a['Date']||''));
    const el = document.getElementById('sb-acts-' + id);
    if (el) el.innerHTML = mine.length
      ? mine.map(renderAct).join('')
      : '<div style="color:var(--text3);padding:4px 0">No activities yet</div>';
  }});
}}

async function updateStatus(id, val) {{
  const v = _venues.find(x => x.id === id);
  if (v) v['Contact Status'] = {{value: val}};
  if (_markerMap[id]) _markerMap[id].setIcon(id === _selectedId ? _pinIconSelected(_pinColor(val)) : _pinIcon(_pinColor(val)));
  const st = document.getElementById('sb-status-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  const r = await bpatch(VENUES_TID, id, {{'Contact Status': {{value: val}}}});
  if (st) {{ st.textContent = r.ok ? '\u2713' : '\u2717'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
}}

async function saveFollowUp(id) {{
  const val = (document.getElementById('sb-fu-' + id) || {{}}).value || null;
  const v = _venues.find(x => x.id === id);
  if (v) v['Follow-Up Date'] = val;
  const st = document.getElementById('sb-fu-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  const r = await bpatch(VENUES_TID, id, {{'Follow-Up Date': val || null}});
  if (st) {{ st.textContent = r.ok ? '\u2713' : '\u2717'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
}}

async function addNote(id) {{
  const inputEl = document.getElementById('sb-note-in-' + id);
  const text = (inputEl ? inputEl.value : '').trim();
  if (!text) return;
  const today = new Date().toISOString().split('T')[0];
  const entry = '[' + today + '] ' + text;
  const v = _venues.find(x => x.id === id);
  const existing = (v && v['Notes'] ? v['Notes'].trim() : '');
  const newNotes = existing ? entry + '\\n---\\n' + existing : entry;
  if (v) v['Notes'] = newNotes;
  if (inputEl) inputEl.value = '';
  const logEl = document.getElementById('sb-notes-' + id);
  if (logEl) logEl.innerHTML = renderNotes(newNotes);
  const st = document.getElementById('sb-note-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  const r = await bpatch(VENUES_TID, id, {{'Notes': newNotes}});
  if (st) {{ st.textContent = r.ok ? 'Saved \u2713' : 'Failed \u2717'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
}}

async function logActivity(id) {{
  const btn = document.getElementById('sb-abtn-' + id);
  const st  = document.getElementById('sb-act-st-' + id);
  if (btn) btn.disabled = true;
  if (st) st.textContent = 'Saving\u2026';
  const date    = (document.getElementById('sb-adate-' + id) || {{}}).value || null;
  const type    = (document.getElementById('sb-atype-' + id) || {{}}).value || 'Other';
  const outcome = (document.getElementById('sb-aoutcome-' + id) || {{}}).value || '';
  const person  = (document.getElementById('sb-aperson-' + id) || {{}}).value || '';
  const summary = (document.getElementById('sb-asummary-' + id) || {{}}).value || '';
  const fu      = (document.getElementById('sb-afu-' + id) || {{}}).value || null;
  const payload = {{[ACTS_LINK]: [{{id}}], 'Date': date, 'Type': {{value: type}},
    'Outcome': {{value: outcome}}, 'Contact Person': person, 'Summary': summary, 'Follow-Up Date': fu || null}};
  try {{
    const r = await bpost(ACTS_TID, payload);
    if (r.ok) {{
      const newAct = await r.json();
      const el = document.getElementById('sb-acts-' + id);
      if (el) el.innerHTML = renderAct(newAct) + (el.innerHTML === '<div style="color:var(--text3);padding:4px 0">No activities yet</div>' ? '' : el.innerHTML);
      if (document.getElementById('sb-asummary-' + id)) document.getElementById('sb-asummary-' + id).value = '';
      if (document.getElementById('sb-aperson-' + id))  document.getElementById('sb-aperson-' + id).value  = '';
      if (document.getElementById('sb-afu-' + id))      document.getElementById('sb-afu-' + id).value      = '';
      if (fu) {{ const fuIn = document.getElementById('sb-fu-' + id); if (fuIn) {{ fuIn.value = fu; saveFollowUp(id); }} }}
      if (st) {{ st.textContent = 'Saved \u2713'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
    }} else {{
      if (st) st.textContent = 'Failed \u2717';
    }}
  }} catch(e) {{ if (st) st.textContent = 'Error: ' + e.message; }}
  if (btn) btn.disabled = false;
}}

async function load() {{
  _venues = await fetchAll(VENUES_TID);
  {firm_counts_load}
  buildFilters();
  applyFilters();
  if (!_map) initMap(); else renderMarkers();
  stampRefresh();
}}

load();
"""
    # Prepend GFR form JS + pre-fill helpers
    gfr_js = f"const GFR_USER = {repr(_uname)};\nconst TOOL = {{venuesT: {T_GOR_VENUES}}};\n"
    gfr_js += _GFR_JS + '\n' + _GFR_FORMS345_JS + '\n'
    gfr_js += """
// ── Open External Event form pre-filled with selected venue ──────────────
function openLogEvent() {
  if (!_currentVenue) { s2Reset(); document.getElementById('gfr-form-s2').classList.add('open'); return; }
  s2Reset();
  var el;
  el = document.getElementById('s2-event-name'); if (el) el.value = _currentVenue[_nameField] || '';
  el = document.getElementById('s2-addr');       if (el) el.value = _currentVenue[_addrField] || '';
  el = document.getElementById('s2-org-phone');  if (el) el.value = _currentVenue[_phoneField] || '';
  document.getElementById('gfr-form-s2').classList.add('open');
}
function openScheduleEvent(formType) {
  if (!_currentVenue) { openGFRForm(formType); return; }
  openGFRForm(formType);
  var name = _currentVenue[_nameField] || '';
  var addr = _currentVenue[_addrField] || '';
  var phone = _currentVenue[_phoneField] || '';
  setTimeout(function() {
    ['s3','s4','s5'].forEach(function(p) {
      var c = document.getElementById(p + '-company'); if (c && !c.value) c.value = name;
      var a = document.getElementById(p + '-addr');    if (a && !a.value) a.value = addr;
      var ph = document.getElementById(p + '-phone');  if (ph && !ph.value) ph.value = phone;
    });
  }, 50);
}
"""
    js = gfr_js + js
    return _page(map_key, f'{c["label"]} Directory', header, body, js, br, bt, user=user)
