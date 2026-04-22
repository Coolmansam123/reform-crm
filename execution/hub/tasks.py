"""
Tasks page — the signed-in user's open ClickUp tasks, grouped by due date.
ClickUp is the source of truth; this is a read surface + a "+ Add task"
shortcut. Tasks created here get `crm:<kind>:<id>` tags so they can be
reverse-filtered from CRM detail pages.

Also exports `task_modal_html()` + `task_modal_js()` so Company / Person /
Lead detail pages can drop in a "+ Add task" button that pre-fills the CRM
link id. Same pattern as `hub/meetings.py`.
"""
from .shared import _page


# ─── Shared + Add task modal (drop-in for detail pages) ─────────────────────
_ADD_TASK_MODAL_HTML = """
<div class="atk-modal-bg" id="atk-bg" onclick="if(event.target===this)atkClose()">
  <div class="atk-modal">
    <h3>\u2795 Add ClickUp task</h3>
    <label>Title *</label>
    <input type="text" id="atk-name" placeholder="What needs to happen?">
    <label>List *</label>
    <select id="atk-list"><option value="">Loading\u2026</option></select>
    <label>Description</label>
    <textarea id="atk-desc" placeholder="Optional details"></textarea>
    <div class="atk-row">
      <div><label>Due date</label><input type="date" id="atk-due"></div>
      <div><label>Priority</label>
        <select id="atk-pri">
          <option value="">\u2014</option>
          <option value="4">Low</option>
          <option value="3" selected>Normal</option>
          <option value="2">High</option>
          <option value="1">Urgent</option>
        </select>
      </div>
    </div>
    <div class="atk-msg" id="atk-msg"></div>
    <div class="atk-actions">
      <button type="button" onclick="atkClose()">Cancel</button>
      <button type="button" class="primary" onclick="atkSubmit()">Create</button>
    </div>
  </div>
</div>
<style>
.atk-modal-bg{position:fixed;inset:0;background:rgba(0,0,0,0.5);display:none;align-items:center;justify-content:center;z-index:1000;padding:16px}
.atk-modal-bg.open{display:flex}
.atk-modal{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:22px;width:min(520px,96vw);max-height:92vh;overflow-y:auto}
.atk-modal h3{margin:0 0 14px;font-size:17px;font-weight:700}
.atk-modal label{display:block;font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px}
.atk-modal input,.atk-modal textarea,.atk-modal select{width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:13px;font-family:inherit;box-sizing:border-box;margin-bottom:12px}
.atk-modal textarea{resize:vertical;min-height:70px}
.atk-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.atk-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:8px}
.atk-actions button{padding:8px 16px;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer;border:1px solid var(--border);background:transparent;color:var(--text)}
.atk-actions .primary{background:#3b82f6;color:#fff;border-color:#3b82f6}
.atk-actions .primary:hover{background:#2563eb}
.atk-msg{font-size:12px;color:var(--text3);margin-top:4px;min-height:16px}
.atk-msg.err{color:#ef4444}
.atk-msg.ok{color:#059669}
</style>
"""


def task_modal_html() -> str:
    """Drop this into a detail page body once."""
    return _ADD_TASK_MODAL_HTML


def task_modal_js(company_id: int = 0, contact_id: int = 0, lead_id: int = 0) -> str:
    """Include in the page's JS block. Exposes `atkOpen()`, `atkClose()`, `atkSubmit()`.
    The link ids pre-fill the POST so the new task is CRM-tagged."""
    return f"""
const _ATK_COMPANY = {int(company_id) or 0};
const _ATK_CONTACT = {int(contact_id) or 0};
const _ATK_LEAD    = {int(lead_id) or 0};

let _ATK_LISTS_LOADED = false;

async function _atkLoadLists() {{
  if (_ATK_LISTS_LOADED) return;
  try {{
    const r = await fetch('/api/clickup/lists');
    if (!r.ok) return;
    const data = await r.json();
    const sel = document.getElementById('atk-list');
    const items = data.items || [];
    // Group by folder for readability
    const byFolder = {{}};
    items.forEach(function(l) {{
      const f = l.folder || '(no folder)';
      (byFolder[f] = byFolder[f] || []).push(l);
    }});
    const folders = Object.keys(byFolder).sort();
    let html = '<option value="">Choose a list\u2026</option>';
    folders.forEach(function(f) {{
      html += '<optgroup label="' + f.replace(/"/g,'&quot;') + '">';
      byFolder[f].sort(function(a,b){{ return (a.name||'').localeCompare(b.name||''); }})
        .forEach(function(l) {{
          html += '<option value="' + l.id + '">' + (l.name||'(unnamed)').replace(/</g,'&lt;') + '</option>';
        }});
      html += '</optgroup>';
    }});
    sel.innerHTML = html;
    // Pre-select: last-used (localStorage) > server default > first
    const last = localStorage.getItem('atk_last_list_id') || '';
    const def  = data.default_list_id || '';
    const picks = [last, def];
    for (const pick of picks) {{
      if (pick && sel.querySelector('option[value="' + pick + '"]')) {{
        sel.value = pick; break;
      }}
    }}
    _ATK_LISTS_LOADED = true;
  }} catch(e) {{ /* best effort */ }}
}}

function atkOpen() {{
  document.getElementById('atk-name').value = '';
  document.getElementById('atk-desc').value = '';
  document.getElementById('atk-due').value  = '';
  document.getElementById('atk-pri').value  = '3';
  document.getElementById('atk-msg').textContent = '';
  document.getElementById('atk-msg').className = 'atk-msg';
  document.getElementById('atk-bg').classList.add('open');
  _atkLoadLists();
  setTimeout(function(){{ document.getElementById('atk-name').focus(); }}, 40);
}}
function atkClose() {{ document.getElementById('atk-bg').classList.remove('open'); }}

async function atkSubmit() {{
  const name   = document.getElementById('atk-name').value.trim();
  const listId = document.getElementById('atk-list').value || '';
  const msg    = document.getElementById('atk-msg');
  if (!name)   {{ msg.textContent = 'Title is required.';   msg.className = 'atk-msg err'; return; }}
  if (!listId) {{ msg.textContent = 'Pick a target list.';   msg.className = 'atk-msg err'; return; }}
  msg.textContent = 'Creating\u2026'; msg.className = 'atk-msg';
  localStorage.setItem('atk_last_list_id', listId);
  const payload = {{
    name,
    list_id:     listId,
    description: document.getElementById('atk-desc').value.trim(),
    due_date:    document.getElementById('atk-due').value || null,
    priority:    document.getElementById('atk-pri').value || null,
  }};
  if (_ATK_COMPANY) payload.company_id = _ATK_COMPANY;
  if (_ATK_CONTACT) payload.contact_id = _ATK_CONTACT;
  if (_ATK_LEAD)    payload.lead_id    = _ATK_LEAD;
  try {{
    const r = await fetch('/api/clickup/tasks', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify(payload)}});
    const data = await r.json();
    if (!r.ok) {{
      msg.textContent = 'Failed: ' + (data.error || r.status) + (data.hint ? ' \u2014 ' + data.hint : '');
      msg.className = 'atk-msg err';
      return;
    }}
    msg.innerHTML = 'Created. <a href="' + (data.url||'#') + '" target="_blank" style="color:#3b82f6">Open in ClickUp \u2192</a>';
    msg.className = 'atk-msg ok';
    setTimeout(atkClose, 1100);
  }} catch(e) {{
    msg.textContent = 'Network error: ' + String(e);
    msg.className = 'atk-msg err';
  }}
}}
"""


_TK_STYLES = """
<style>
.tk2-wrap{padding:0 4px}
.tk2-toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:18px}
.tk2-toolbar .grow{flex:1;min-width:220px}
.tk2-toolbar input{padding:7px 10px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-size:13px}
.tk2-new{padding:8px 14px;background:#3b82f6;color:#fff;border:none;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer}
.tk2-new:hover{background:#2563eb}
.tk2-group{margin-bottom:24px}
.tk2-group-hdr{font-size:11px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px;padding-left:2px}
.tk2-group-hdr.overdue{color:#ef4444}
.tk2-group-hdr.today{color:#f59e0b}
.tk2-group-hdr.week{color:#3b82f6}
.tk2-group-hdr.later{color:var(--text3)}
.tk2-group-hdr.none{color:var(--text3)}
.tk2-item{display:flex;gap:12px;align-items:center;padding:11px 14px;background:var(--card);border:1px solid var(--border);border-radius:8px;margin-bottom:6px;font-size:13px}
.tk2-item:hover{border-color:var(--text3)}
.tk2-check{flex-shrink:0;width:18px;height:18px;border:2px solid var(--text3);border-radius:50%;cursor:pointer;background:transparent;transition:all .12s;padding:0}
.tk2-check:hover{border-color:#059669}
.tk2-check.done{background:#059669;border-color:#059669;position:relative}
.tk2-check.done::after{content:"\u2713";position:absolute;inset:0;color:#fff;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center}
.tk2-name{flex:1;min-width:0;color:var(--text);text-decoration:none;line-height:1.4}
.tk2-name:hover{color:#3b82f6}
.tk2-meta{display:flex;gap:8px;align-items:center;flex-shrink:0;font-size:11px}
.tk2-status{padding:2px 8px;border-radius:3px;font-weight:600;text-transform:uppercase;letter-spacing:.3px;font-size:10px;color:#fff}
.tk2-crmchip{padding:2px 8px;border-radius:10px;background:var(--bg2);color:var(--text2);text-decoration:none;border:1px solid var(--border);font-size:10px;font-weight:500}
.tk2-crmchip:hover{border-color:var(--text3)}
.tk2-due{color:var(--text3);font-variant-numeric:tabular-nums}
.tk2-due.overdue{color:#ef4444;font-weight:600}
.tk2-due.today{color:#f59e0b;font-weight:600}
.tk2-ext{text-decoration:none;color:var(--text3);font-size:11px;padding:4px 6px;border-radius:4px}
.tk2-ext:hover{background:var(--bg2);color:var(--text)}
.tk2-empty{padding:60px 20px;text-align:center;color:var(--text3);font-size:13px;background:var(--card);border:1px solid var(--border);border-radius:8px}
.tk2-unmatched{padding:20px 24px;background:#f59e0b11;border:1px solid #f59e0b33;border-radius:8px;color:var(--text);font-size:13px;line-height:1.5;margin-bottom:16px}
.tk2-modal-bg{position:fixed;inset:0;background:rgba(0,0,0,0.5);display:none;align-items:center;justify-content:center;z-index:1000;padding:16px}
.tk2-modal-bg.open{display:flex}
.tk2-modal{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:22px;width:min(520px,96vw)}
.tk2-modal h3{margin:0 0 14px;font-size:17px;font-weight:700}
.tk2-modal label{display:block;font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px}
.tk2-modal input,.tk2-modal textarea,.tk2-modal select{width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:13px;font-family:inherit;box-sizing:border-box;margin-bottom:12px}
.tk2-modal textarea{resize:vertical;min-height:70px}
.tk2-modal .row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.tk2-modal-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:8px}
.tk2-modal-actions button{padding:8px 16px;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer;border:1px solid var(--border);background:transparent;color:var(--text)}
.tk2-modal-actions .primary{background:#3b82f6;color:#fff;border-color:#3b82f6}
.tk2-modal-actions .primary:hover{background:#2563eb}
.tk2-msg{font-size:12px;color:var(--text3);margin-top:6px;min-height:16px}
.tk2-msg.err{color:#ef4444}
.tk2-msg.ok{color:#059669}
</style>
"""


def _new_task_modal() -> str:
    return (
        '<div class="tk2-modal-bg" id="tk2-new-bg" onclick="if(event.target===this)tk2CloseNew()">'
        '<div class="tk2-modal">'
        '<h3>\u2795 New ClickUp task</h3>'
        '<label>Title *</label>'
        '<input type="text" id="tk2-name" placeholder="What needs to happen?">'
        '<label>List *</label>'
        '<select id="tk2-list"><option value="">Loading\u2026</option></select>'
        '<label>Description</label>'
        '<textarea id="tk2-desc" placeholder="Optional details or context"></textarea>'
        '<div class="row">'
        '<div><label>Due date</label><input type="date" id="tk2-due"></div>'
        '<div><label>Priority</label>'
        '<select id="tk2-pri">'
        '<option value="">\u2014</option>'
        '<option value="4">Low</option>'
        '<option value="3" selected>Normal</option>'
        '<option value="2">High</option>'
        '<option value="1">Urgent</option>'
        '</select></div>'
        '</div>'
        '<div class="tk2-msg" id="tk2-msg"></div>'
        '<div class="tk2-modal-actions">'
        '<button type="button" onclick="tk2CloseNew()">Cancel</button>'
        '<button type="button" class="primary" onclick="tk2SubmitNew()">Create in ClickUp</button>'
        '</div>'
        '</div></div>'
    )


def _tasks_page(br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header">'
        '<div class="header-left">'
        '<h1>\U0001f4cb My Tasks</h1>'
        '<div class="sub">Open ClickUp tasks assigned to you</div>'
        '</div>'
        '<div class="header-right">'
        '<button class="tk2-new" onclick="tk2OpenNew()">+ New task</button>'
        '</div>'
        '</div>'
    )

    body = (
        _TK_STYLES
        + '<div class="tk2-wrap">'
        + '<div class="tk2-toolbar">'
        + '<input type="text" id="tk2-search" class="grow" placeholder="Filter by title or tag\u2026">'
        + '</div>'
        + '<div id="tk2-unmatched"></div>'
        + '<div id="tk2-list"><div class="tk2-empty">Loading your tasks\u2026</div></div>'
        + '</div>'
        + _new_task_modal()
    )

    js = r"""
let _TASKS = [];

function esc2(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function fmtDueMs(ms){
  if (!ms) return {label:'No date', bucket:'none', overdue:false, today:false};
  var d = new Date(parseInt(ms));
  if (isNaN(d.getTime())) return {label:'No date', bucket:'none'};
  var today = new Date(); today.setHours(0,0,0,0);
  var dayOf = new Date(d); dayOf.setHours(0,0,0,0);
  var diffDays = Math.round((dayOf - today) / 86400000);
  var timeStr = d.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'});
  var label;
  if (diffDays < 0)      label = d.toLocaleDateString('en-US',{month:'short',day:'numeric'}) + ' (' + (-diffDays) + 'd late)';
  else if (diffDays===0) label = 'Today ' + timeStr;
  else if (diffDays===1) label = 'Tomorrow ' + timeStr;
  else if (diffDays<=7)  label = d.toLocaleDateString('en-US',{weekday:'short'}) + ' ' + timeStr;
  else                   label = d.toLocaleDateString('en-US',{month:'short',day:'numeric'});
  var bucket;
  if (diffDays < 0)       bucket = 'overdue';
  else if (diffDays === 0) bucket = 'today';
  else if (diffDays <= 7)  bucket = 'week';
  else                     bucket = 'later';
  return {label, bucket, overdue: diffDays<0, today: diffDays===0};
}

function crmChips(t){
  var parts = [];
  var crm = t.crm || {};
  if (crm.company_id) parts.push('<a class="tk2-crmchip" href="/companies/'+crm.company_id+'">\U0001f3e2 Company</a>');
  if (crm.lead_id)    parts.push('<a class="tk2-crmchip" href="/leads/'+crm.lead_id+'">\U0001f4e5 Lead</a>');
  if (crm.person_id)  parts.push('<a class="tk2-crmchip" href="/people/'+crm.person_id+'">\U0001f464 Person</a>');
  return parts.join('');
}

function renderList(){
  var q = (document.getElementById('tk2-search').value || '').toLowerCase();
  var filtered = _TASKS.filter(function(t){
    if (!q) return true;
    var hay = ((t.name||'')+' '+((t.tags||[]).join(' '))).toLowerCase();
    return hay.indexOf(q) !== -1;
  });
  if (!filtered.length){
    document.getElementById('tk2-list').innerHTML = '<div class="tk2-empty">No tasks \u2014 enjoy the quiet. \U0001f331</div>';
    return;
  }
  // Bucket by due date
  var buckets = {overdue:[], today:[], week:[], later:[], none:[]};
  filtered.forEach(function(t){
    var info = fmtDueMs(t.due_date);
    t._due = info;
    buckets[info.bucket].push(t);
  });
  var order = [
    ['overdue','Overdue'],
    ['today','Today'],
    ['week','This week'],
    ['later','Later'],
    ['none','No due date'],
  ];
  var html = '';
  order.forEach(function(pair){
    var key = pair[0], label = pair[1];
    var arr = buckets[key];
    if (!arr.length) return;
    // Sort within bucket: by due_date ascending (non-none), else by created desc
    arr.sort(function(a,b){
      if (key === 'none') return (parseInt(b.date_created||0)) - (parseInt(a.date_created||0));
      return (parseInt(a.due_date||0)) - (parseInt(b.due_date||0));
    });
    html += '<div class="tk2-group">';
    html += '<div class="tk2-group-hdr ' + key + '">' + esc2(label) + '  <span style="color:var(--text4);font-weight:500">'+arr.length+'</span></div>';
    arr.forEach(function(t){
      var stColor = t.status_color || '#6b7280';
      var dueCls = 'tk2-due' + (t._due.overdue ? ' overdue' : t._due.today ? ' today' : '');
      var listChip = t.list_name
        ? '<span class="tk2-crmchip" title="List' + (t.folder ? ' in ' + esc2(t.folder) : '') + '">\U0001f4c1 ' + esc2(t.list_name) + '</span>'
        : '';
      html += '<div class="tk2-item">'
        + '<button class="tk2-check" title="Mark complete" onclick="tk2Complete(\'' + esc2(t.id) + '\', this)"></button>'
        + '<div class="tk2-name">' + esc2(t.name) + '</div>'
        + '<div class="tk2-meta">'
        + listChip
        + crmChips(t)
        + (t.status ? '<span class="tk2-status" style="background:'+stColor+'">'+esc2(t.status)+'</span>' : '')
        + '<span class="' + dueCls + '">' + esc2(t._due.label) + '</span>'
        + (t.url ? '<a class="tk2-ext" href="'+esc2(t.url)+'" target="_blank" title="Open in ClickUp">\u2197</a>' : '')
        + '</div>'
        + '</div>';
    });
    html += '</div>';
  });
  document.getElementById('tk2-list').innerHTML = html;
}

async function loadTasks(){
  try {
    var r = await fetch('/api/clickup/tasks');
    if (!r.ok){
      document.getElementById('tk2-list').innerHTML = '<div class="tk2-empty">Failed to load tasks (' + r.status + ').</div>';
      return;
    }
    var data = await r.json();
    if (data.unmatched){
      document.getElementById('tk2-unmatched').innerHTML =
        '<div class="tk2-unmatched"><strong>No ClickUp match.</strong> ' + esc2(data.hint || '') + '</div>';
    } else {
      document.getElementById('tk2-unmatched').innerHTML = '';
    }
    _TASKS = data.items || [];
    renderList();
  } catch(e){
    document.getElementById('tk2-list').innerHTML = '<div class="tk2-empty">Error: ' + esc2(String(e)) + '</div>';
  }
}

async function tk2Complete(taskId, btn){
  btn.classList.add('done');
  try {
    var r = await fetch('/api/clickup/tasks/' + encodeURIComponent(taskId), {
      method: 'PATCH', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({status: 'complete'}),
    });
    if (r.ok){
      setTimeout(loadTasks, 600);
    } else {
      btn.classList.remove('done');
      alert('Failed to mark complete.');
    }
  } catch(e){
    btn.classList.remove('done');
    alert('Network error');
  }
}

document.getElementById('tk2-search').addEventListener('input', renderList);

let _TK2_LISTS_LOADED = false;
async function _tk2LoadLists(){
  if (_TK2_LISTS_LOADED) return;
  try {
    var r = await fetch('/api/clickup/lists');
    if (!r.ok) return;
    var data = await r.json();
    var items = data.items || [];
    var byFolder = {};
    items.forEach(function(l){ (byFolder[l.folder||'(no folder)'] = byFolder[l.folder||'(no folder)']||[]).push(l); });
    var folders = Object.keys(byFolder).sort();
    var html = '<option value="">Choose a list\u2026</option>';
    folders.forEach(function(f){
      html += '<optgroup label="' + f.replace(/"/g,'&quot;') + '">';
      byFolder[f].sort(function(a,b){return (a.name||'').localeCompare(b.name||'');})
        .forEach(function(l){ html += '<option value="'+l.id+'">'+(l.name||'').replace(/</g,'&lt;')+'</option>'; });
      html += '</optgroup>';
    });
    var sel = document.getElementById('tk2-list');
    sel.innerHTML = html;
    var last = localStorage.getItem('atk_last_list_id') || '';
    var def  = data.default_list_id || '';
    [last, def].forEach(function(p){
      if (p && sel.querySelector('option[value="'+p+'"]') && !sel.value) sel.value = p;
    });
    _TK2_LISTS_LOADED = true;
  } catch(e){}
}

function tk2OpenNew(){
  document.getElementById('tk2-name').value = '';
  document.getElementById('tk2-desc').value = '';
  document.getElementById('tk2-due').value = '';
  document.getElementById('tk2-pri').value = '3';
  document.getElementById('tk2-msg').textContent = '';
  document.getElementById('tk2-msg').className = 'tk2-msg';
  document.getElementById('tk2-new-bg').classList.add('open');
  _tk2LoadLists();
  setTimeout(function(){ document.getElementById('tk2-name').focus(); }, 40);
}
function tk2CloseNew(){ document.getElementById('tk2-new-bg').classList.remove('open'); }

async function tk2SubmitNew(){
  var name   = document.getElementById('tk2-name').value.trim();
  var listId = document.getElementById('tk2-list').value || '';
  var msg    = document.getElementById('tk2-msg');
  if (!name)   { msg.textContent = 'Title is required.'; msg.className = 'tk2-msg err'; return; }
  if (!listId) { msg.textContent = 'Pick a target list.'; msg.className = 'tk2-msg err'; return; }
  msg.textContent = 'Creating\u2026'; msg.className = 'tk2-msg';
  localStorage.setItem('atk_last_list_id', listId);
  var payload = {
    name, list_id: listId,
    description: document.getElementById('tk2-desc').value.trim(),
    due_date: document.getElementById('tk2-due').value || null,
    priority: document.getElementById('tk2-pri').value || null,
  };
  try {
    var r = await fetch('/api/clickup/tasks', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    var data = await r.json();
    if (!r.ok){
      msg.textContent = 'Failed: ' + (data.error || r.status) + (data.hint ? ' \u2014 ' + data.hint : '');
      msg.className = 'tk2-msg err';
      return;
    }
    msg.innerHTML = 'Created. <a href="' + esc2(data.url||'#') + '" target="_blank" style="color:#3b82f6">Open in ClickUp \u2192</a>';
    msg.className = 'tk2-msg ok';
    setTimeout(function(){ tk2CloseNew(); loadTasks(); }, 1200);
  } catch(e){
    msg.textContent = 'Network error: ' + String(e);
    msg.className = 'tk2-msg err';
  }
}

loadTasks();
"""

    return _page('tasks', 'My Tasks', header, body, js, br, bt, user=user)
