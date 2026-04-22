"""
Automations — unified trigger + action-chain engine.

What was once "Sequences" (manually-enrolled email drips) is now the same
schema wearing a bigger hat: every automation has a **trigger** (manual
kickoff or a catalyst event like "lead stage changed to Contacted") and a
chain of typed **steps** that fire in order on a timed cadence.

Supported triggers (see `TRIGGERS`):
  - manual                — user clicks "Start automation" on a record
  - new_lead              — a new Lead row is created
  - lead_stage_changed    — Lead Status transitions (config: `to:<stage>`)
  - lead_converted        — Lead Status \u2192 Converted
  - lead_dropped          — Lead Status \u2192 Dropped

Supported step types (see `STEP_TYPES`):
  - send_email    {subject, body}
  - send_sms      {body}            (needs Twilio configured)
  - create_task   {name, description, list_id?}  (ClickUp)
  - update_lead   {field, value}    (only when the subject is a Lead)
  - wait          {}                (no action, just advance the clock)

Tables are T_SEQUENCES (824, labeled `Automations` in Baserow) and
T_SEQUENCE_ENROLLMENTS (825, `Automation Runs`). Constants stay named with
`SEQUENCES` for Python-code stability.
"""
from .shared import _page


TRIGGERS = [
    ("manual",             "Manual kickoff"),
    ("new_lead",           "When a new lead is created"),
    ("lead_stage_changed", "When a lead stage changes"),
    ("lead_converted",     "When a lead converts to patient"),
    ("lead_dropped",       "When a lead is dropped"),
]

STEP_TYPES = [
    ("send_email",  "Send email"),
    ("send_sms",    "Send SMS"),
    ("create_task", "Create ClickUp task"),
    ("update_lead", "Update lead field"),
    ("wait",        "Wait (no action)"),
]


_AT_STYLES = """
<style>
.at-toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:18px}
.at-toolbar .grow{flex:1;min-width:240px}
.at-toolbar input,.at-toolbar select{padding:7px 10px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-size:13px}
.at-new-btn{padding:8px 14px;background:#3b82f6;color:#fff;border:none;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer}
.at-new-btn:hover{background:#2563eb}
.at-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.at-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px 18px;text-decoration:none;color:var(--text);display:block;transition:border-color .12s}
.at-card:hover{border-color:var(--text3)}
.at-card h3{font-size:15px;font-weight:700;margin:0 0 6px}
.at-card .desc{font-size:12px;color:var(--text3);margin-bottom:10px;min-height:30px;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.at-chips{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
.at-chip{font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600}
.at-chip.trig{background:var(--bg2);color:var(--text2)}
.at-chip.trig.manual{background:#64748b22;color:#64748b}
.at-chip.trig.new_lead{background:#3b82f622;color:#3b82f6}
.at-chip.trig.lead_stage_changed{background:#ea580c22;color:#ea580c}
.at-chip.trig.lead_converted{background:#05966922;color:#059669}
.at-chip.trig.lead_dropped{background:#ef444422;color:#ef4444}
.at-chip.on{background:#05966922;color:#059669}
.at-chip.off{background:#64748b22;color:#64748b}
.at-meta{font-size:11px;color:var(--text3);display:flex;gap:14px}
.at-empty{padding:60px 20px;text-align:center;color:var(--text3);font-size:13px;background:var(--card);border:1px solid var(--border);border-radius:10px}
.at-detail-grid{display:grid;grid-template-columns:1fr 340px;gap:22px}
@media(max-width:900px){.at-detail-grid{grid-template-columns:1fr}}
.at-card-big{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px 22px;margin-bottom:16px}
.at-card-big h3{font-size:14px;font-weight:700;margin:0 0 12px}
.at-fld{margin-bottom:14px}
.at-fld label{display:block;font-size:11px;color:var(--text3);font-weight:600;text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px}
.at-fld input,.at-fld textarea,.at-fld select{width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:13px;font-family:inherit;box-sizing:border-box}
.at-fld textarea{resize:vertical;min-height:60px}
.at-row-2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.at-step{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:14px 16px;margin-bottom:10px;position:relative}
.at-step-hd{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:10px;flex-wrap:wrap}
.at-step-hd strong{font-size:12px;color:var(--text3);text-transform:uppercase;letter-spacing:.4px}
.at-step-ctrl{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.at-step-ctrl .delay{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--text2)}
.at-step-ctrl .delay input{width:60px;padding:4px 6px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);font-size:12px}
.at-step-ctrl select{padding:4px 8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);font-size:12px}
.at-step textarea,.at-step input[type=text]{width:100%;padding:7px 9px;border:1px solid var(--border);border-radius:5px;background:var(--bg);color:var(--text);font-size:13px;font-family:inherit;box-sizing:border-box;margin-bottom:8px}
.at-step textarea{min-height:72px;resize:vertical;font-family:ui-monospace,'Cascadia Code',Menlo,monospace;font-size:12px}
.at-step-rm{position:absolute;top:10px;right:10px;background:transparent;border:none;color:var(--text3);font-size:16px;cursor:pointer;padding:2px 6px;border-radius:4px}
.at-step-rm:hover{background:var(--card);color:#ef4444}
.at-add-step{padding:8px 14px;background:var(--bg2);color:var(--text);border:1px dashed var(--border);border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;width:100%}
.at-add-step:hover{border-color:var(--text3)}
.at-actions{display:flex;gap:10px;justify-content:flex-end}
.at-btn{padding:8px 14px;border:1px solid var(--border);background:var(--card);color:var(--text);border-radius:6px;font-size:13px;font-weight:600;cursor:pointer}
.at-btn.primary{background:#3b82f6;color:#fff;border-color:#3b82f6}
.at-btn.primary:hover{background:#2563eb}
.at-btn.danger{color:#ef4444;border-color:#ef444455}
.at-run-row{display:flex;gap:12px;padding:9px 0;border-bottom:1px solid var(--border);font-size:13px;align-items:center}
.at-run-row:last-child{border-bottom:0}
.at-run-row .who{flex:1;min-width:0}
.at-run-row .who strong{display:block;font-size:13px;color:var(--text)}
.at-run-row .who small{font-size:11px;color:var(--text3)}
.at-run-row .st{font-size:10px;padding:2px 7px;border-radius:10px;font-weight:600;text-transform:uppercase;letter-spacing:.3px}
.at-run-row .st.active{background:#3b82f622;color:#3b82f6}
.at-run-row .st.paused{background:#f59e0b22;color:#d97706}
.at-run-row .st.replied{background:#05966922;color:#059669}
.at-run-row .st.completed{background:#64748b22;color:#64748b}
.at-run-row .st.needs_reauth{background:#ea580c22;color:#ea580c}
.at-run-row .st.failed{background:#ef444422;color:#ef4444}
.at-run-row .st.unenrolled{background:#64748b22;color:#64748b}
.at-run-row .actions button{padding:4px 9px;font-size:11px;background:transparent;border:1px solid var(--border);border-radius:4px;color:var(--text);cursor:pointer;font-weight:600}
.at-run-row .actions button:hover{border-color:var(--text3)}
.at-run-row .prog{font-size:11px;color:var(--text3);white-space:nowrap}
.at-msg{font-size:12px;color:var(--text3);margin-top:4px;min-height:16px}
.at-msg.ok{color:#059669}
.at-msg.err{color:#ef4444}
.at-hint{font-size:11px;color:var(--text3);background:var(--bg2);padding:9px 12px;border-radius:6px;line-height:1.5;margin-bottom:10px}
.at-trigger-cfg{margin-top:8px;display:none}
.at-trigger-cfg.on{display:block}
.at-back-link{display:inline-block;margin-bottom:14px;font-size:12px;color:var(--text3);text-decoration:none}
.at-back-link:hover{color:var(--text)}
</style>
"""


def _sequences_list_page(br: str, bt: str, user: dict = None) -> str:
    """(Historical name kept for import stability — this is the Automations list.)"""
    header = (
        '<div class="header">'
        '<div class="header-left">'
        '<h1>Automations</h1>'
        '<div class="sub">Trigger \u2192 timed chain of actions</div>'
        '</div><div class="header-right">'
        '<button class="at-new-btn" onclick="atCreate()">+ New automation</button>'
        '</div></div>'
    )
    trig_opts = '<option value="">All triggers</option>' + "".join(
        f'<option value="{k}">{lbl}</option>' for k, lbl in TRIGGERS
    )
    body = (
        _AT_STYLES
        + '<div class="at-toolbar">'
        + '<input type="text" id="at-search" class="grow" placeholder="Search automations\u2026">'
        + f'<select id="at-trig">{trig_opts}</select>'
        + '</div>'
        + '<div id="at-list"><div class="at-empty">Loading\u2026</div></div>'
    )
    js = r"""
let _ATS = [];

function selVal(v){ if(!v) return ''; if(typeof v==='object') return v.value||''; return String(v); }

function stepsOf(s){
  try { return JSON.parse(s['Steps JSON'] || '[]') || []; } catch(e) { return []; }
}

function trigLabel(t){
  return {manual:'Manual',new_lead:'New lead',lead_stage_changed:'Stage change',
          lead_converted:'Converted',lead_dropped:'Dropped'}[t] || t || 'manual';
}

function render(){
  const q = (document.getElementById('at-search').value || '').toLowerCase();
  const trig = document.getElementById('at-trig').value;
  const rows = _ATS.filter(s => {
    const t = selVal(s.Trigger) || 'manual';
    if (trig && t !== trig) return false;
    if (q) {
      const hay = ((s.Name||'') + ' ' + (s.Description||'')).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }).sort((a,b) => (a.Name||'').localeCompare(b.Name||''));
  const wrap = document.getElementById('at-list');
  if (!rows.length) {
    wrap.innerHTML = '<div class="at-empty">No automations yet \u2014 click <strong>+ New automation</strong> to build one.</div>';
    return;
  }
  wrap.innerHTML = '<div class="at-grid">' + rows.map(s => {
    const trig = selVal(s.Trigger) || 'manual';
    const steps = stepsOf(s);
    const on = s['Is Active'] ? 'on' : 'off';
    const onLbl = s['Is Active'] ? 'Active' : 'Off';
    return '<a class="at-card" href="/sequences/' + s.id + '">'
      + '<div class="at-chips"><span class="at-chip trig ' + esc(trig) + '">' + esc(trigLabel(trig)) + '</span>'
      + '<span class="at-chip ' + on + '">' + onLbl + '</span></div>'
      + '<h3>' + esc(s.Name || '(no name)') + '</h3>'
      + '<div class="desc">' + esc(s.Description || 'No description') + '</div>'
      + '<div class="at-meta"><span>' + steps.length + ' step' + (steps.length===1?'':'s') + '</span></div>'
      + '</a>';
  }).join('') + '</div>';
}

async function load(){
  try {
    const r = await fetch('/api/sequences');
    if (!r.ok) { document.getElementById('at-list').innerHTML = '<div class="at-empty">Failed to load.</div>'; return; }
    _ATS = (await r.json()) || [];
    render();
  } catch(e) {
    document.getElementById('at-list').innerHTML = '<div class="at-empty">Error: ' + esc(String(e)) + '</div>';
  }
}

async function atCreate(){
  const name = prompt('Automation name:');
  if (!name || !name.trim()) return;
  const r = await fetch('/api/sequences', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name: name.trim()})});
  if (!r.ok) { alert('Failed to create'); return; }
  const data = await r.json();
  if (data.id) location.href = '/sequences/' + data.id;
}

document.getElementById('at-search').addEventListener('input', render);
document.getElementById('at-trig').addEventListener('change', render);

load();
"""
    return _page('sequences', 'Automations', header, body, js, br, bt, user=user)


def _sequence_detail_page(seq_id: int, br: str, bt: str, user: dict = None) -> str:
    """(Historical name — this is the Automation editor.)"""
    header = (
        '<div class="header"><div class="header-left">'
        f'<h1 id="at-title">Automation #{seq_id}</h1>'
        '<div class="sub" id="at-sub">Loading\u2026</div>'
        '</div></div>'
    )
    trig_opts = "".join(f'<option value="{k}">{lbl}</option>' for k, lbl in TRIGGERS)
    type_opts = "".join(f'<option value="{k}">{lbl}</option>' for k, lbl in STEP_TYPES)

    body = (
        _AT_STYLES
        + '<a href="/sequences" class="at-back-link">\u2190 All automations</a>'
        + '<div class="at-detail-grid">'
        # Left column: configuration + steps
        + '<div>'
        + '<div class="at-card-big">'
        + '<h3>Automation</h3>'
        + '<div class="at-fld"><label>Name</label><input type="text" id="at-name"></div>'
        + '<div class="at-fld"><label>Description</label><textarea id="at-desc"></textarea></div>'
        + '<div class="at-fld at-row-2">'
        + '<div><label>Category</label>'
        + '<select id="at-cat">'
        + '<option value="attorney">Attorney</option><option value="guerilla">Guerilla</option>'
        + '<option value="community">Community</option><option value="patient">Patient</option>'
        + '<option value="other">Other</option>'
        + '</select></div>'
        + '<div><label>Status</label>'
        + '<select id="at-active"><option value="true">Active (firing)</option><option value="false">Off</option></select>'
        + '</div></div>'
        + '<div class="at-fld"><label>Trigger</label>'
        + f'<select id="at-trigger" onchange="atTriggerChange()">{trig_opts}</select>'
        + '<div class="at-trigger-cfg" id="at-trig-stage">'
        + '<label style="margin-top:10px">Fires when status changes to</label>'
        + '<select id="at-trig-stage-val"><option value="New">New</option><option value="Contacted">Contacted</option>'
        + '<option value="Appointment Scheduled">Appointment Scheduled</option><option value="Seen">Seen</option>'
        + '<option value="Converted">Converted</option><option value="Dropped">Dropped</option></select>'
        + '</div></div>'
        + '<div class="at-actions"><button class="at-btn primary" onclick="atSave()">Save</button>'
        + '<button class="at-btn danger" onclick="atDelete()">Delete</button></div>'
        + '<div class="at-msg" id="at-save-msg"></div>'
        + '</div>'
        + '<div class="at-card-big">'
        + '<h3>Steps</h3>'
        + '<div class="at-hint">Text-type steps (<code>send_email</code>, <code>send_sms</code>, <code>create_task</code>) support merge fields: <code>{first_name}</code>, <code>{name}</code>, <code>{email}</code>, <code>{phone}</code>, <code>{company}</code>, <code>{sender_name}</code>. Delay is days from the previous step (step 1 = from trigger fire).</div>'
        + '<div id="at-steps"></div>'
        + '<button class="at-add-step" onclick="atAddStep()">+ Add step</button>'
        + '</div></div>'
        # Right column: runs
        + '<div>'
        + '<div class="at-card-big">'
        + '<h3>Runs <span id="at-run-ct" style="font-size:11px;color:var(--text3);font-weight:500"></span></h3>'
        + '<div id="at-run-list"><div class="at-empty" style="padding:20px;font-size:12px">Loading\u2026</div></div>'
        + '</div></div>'
        + '</div>'
    )

    js = r"""
const SEQ_ID = __SEQ_ID__;
let _SEQ = null;
let _STEPS = [];

const TYPE_OPTS = __TYPE_OPTS__;

function selVal(v){ if(!v) return ''; if(typeof v==='object') return v.value||''; return String(v); }

async function load(){
  const r = await fetch('/api/sequences/' + SEQ_ID);
  if (!r.ok) { document.getElementById('at-sub').textContent = 'Not found'; return; }
  _SEQ = await r.json();
  document.getElementById('at-title').textContent = _SEQ.Name || ('Automation #' + SEQ_ID);
  const trig = selVal(_SEQ.Trigger) || 'manual';
  document.getElementById('at-sub').textContent = 'Trigger: ' + trig.replace(/_/g,' ');
  document.getElementById('at-name').value = _SEQ.Name || '';
  document.getElementById('at-desc').value = _SEQ.Description || '';
  document.getElementById('at-cat').value  = selVal(_SEQ.Category) || 'other';
  document.getElementById('at-active').value = _SEQ['Is Active'] ? 'true' : 'false';
  document.getElementById('at-trigger').value = trig;
  // Parse trigger config (e.g. "to:Contacted")
  const cfg = _SEQ['Trigger Config'] || '';
  if (cfg.startsWith('to:')) document.getElementById('at-trig-stage-val').value = cfg.slice(3);
  atTriggerChange();
  try { _STEPS = JSON.parse(_SEQ['Steps JSON'] || '[]') || []; } catch(e) { _STEPS = []; }
  renderSteps();
}

function atTriggerChange(){
  const t = document.getElementById('at-trigger').value;
  document.getElementById('at-trig-stage').classList.toggle('on', t === 'lead_stage_changed');
}

function stepBodyHTML(i, st){
  const type = st.type || 'send_email';
  let html = '';
  if (type === 'send_email'){
    html += '<input type="text" placeholder="Subject line" value="' + esc(st.subject||'') + '" oninput="atEditStep(' + i + ', \'subject\', this.value)">';
    html += '<textarea placeholder="Email body (plain text; merge fields in {curly_braces})" oninput="atEditStep(' + i + ', \'body\', this.value)">' + esc(st.body||'') + '</textarea>';
  } else if (type === 'send_sms') {
    html += '<textarea placeholder="SMS body (160 chars fits in one message)" maxlength="1600" oninput="atEditStep(' + i + ', \'body\', this.value)">' + esc(st.body||'') + '</textarea>';
  } else if (type === 'create_task') {
    html += '<input type="text" placeholder="Task name (supports merge fields)" value="' + esc(st.name||'') + '" oninput="atEditStep(' + i + ', \'name\', this.value)">';
    html += '<textarea placeholder="Task description (optional)" oninput="atEditStep(' + i + ', \'description\', this.value)">' + esc(st.description||'') + '</textarea>';
    html += '<input type="text" placeholder="ClickUp list ID (optional \u2014 uses default)" value="' + esc(st.list_id||'') + '" oninput="atEditStep(' + i + ', \'list_id\', this.value)">';
  } else if (type === 'update_lead') {
    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:6px">';
    html += '<select onchange="atEditStep(' + i + ', \'field\', this.value)">'
      + '<option value="Status"' + (st.field==='Status'?' selected':'') + '>Status</option>'
      + '<option value="Owner"' + (st.field==='Owner'?' selected':'') + '>Owner</option>'
      + '<option value="Follow-Up Date"' + (st.field==='Follow-Up Date'?' selected':'') + '>Follow-Up Date</option>'
      + '</select>';
    html += '<input type="text" placeholder="Value" value="' + esc(st.value||'') + '" oninput="atEditStep(' + i + ', \'value\', this.value)">';
    html += '</div>';
  } else if (type === 'wait') {
    html += '<div style="font-size:12px;color:var(--text3);padding:4px 0">Wait with no action.</div>';
  }
  return html;
}

function renderSteps(){
  const wrap = document.getElementById('at-steps');
  if (!_STEPS.length) {
    wrap.innerHTML = '<div class="at-empty" style="padding:18px;font-size:12px">No steps yet. Click "+ Add step" to draft one.</div>';
    return;
  }
  wrap.innerHTML = _STEPS.map((st, i) => {
    const type = st.type || 'send_email';
    const typeOpts = TYPE_OPTS.map(o => '<option value="' + o[0] + '"' + (o[0]===type?' selected':'') + '>' + o[1] + '</option>').join('');
    return '<div class="at-step">'
      + '<button class="at-step-rm" onclick="atRemoveStep(' + i + ')" title="Remove">\u2715</button>'
      + '<div class="at-step-hd"><strong>Step ' + (i+1) + '</strong>'
      + '<div class="at-step-ctrl">'
      + '<select onchange="atEditStepType(' + i + ', this.value)">' + typeOpts + '</select>'
      + '<span class="delay">after <input type="number" min="0" max="365" value="' + (st.delay_days||0) + '" onchange="atEditStep(' + i + ', \'delay_days\', parseInt(this.value)||0)"> days</span>'
      + '</div></div>'
      + stepBodyHTML(i, st)
      + '</div>';
  }).join('');
}

function atEditStep(i, key, val){ _STEPS[i][key] = val; }
function atEditStepType(i, newType){
  const existing = _STEPS[i];
  _STEPS[i] = {type: newType, delay_days: existing.delay_days || 0};
  renderSteps();
}
function atRemoveStep(i){ _STEPS.splice(i, 1); renderSteps(); }
function atAddStep(){ _STEPS.push({type: 'send_email', delay_days: _STEPS.length ? 3 : 0, subject: '', body: ''}); renderSteps(); }

async function atSave(){
  const msg = document.getElementById('at-save-msg');
  msg.textContent = 'Saving\u2026'; msg.className = 'at-msg';
  const trigger = document.getElementById('at-trigger').value;
  let trigger_config = '';
  if (trigger === 'lead_stage_changed') trigger_config = 'to:' + document.getElementById('at-trig-stage-val').value;
  const payload = {
    name:           document.getElementById('at-name').value.trim(),
    description:    document.getElementById('at-desc').value.trim(),
    category:       document.getElementById('at-cat').value,
    is_active:      document.getElementById('at-active').value === 'true',
    trigger,
    trigger_config,
    steps:          _STEPS,
  };
  const r = await fetch('/api/sequences/' + SEQ_ID, {method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  if (!r.ok) { msg.textContent = 'Failed to save'; msg.className = 'at-msg err'; return; }
  msg.textContent = 'Saved'; msg.className = 'at-msg ok';
  setTimeout(function(){ msg.textContent = ''; }, 2000);
  load();
}

async function atDelete(){
  if (!confirm('Delete this automation? In-flight runs will be marked unenrolled.')) return;
  const r = await fetch('/api/sequences/' + SEQ_ID, {method:'DELETE'});
  if (!r.ok) { alert('Failed to delete'); return; }
  location.href = '/sequences';
}

function fmtDateTime(iso){
  if (!iso) return '\u2014';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
}

async function loadRuns(){
  const r = await fetch('/api/sequences/' + SEQ_ID + '/enrollments');
  if (!r.ok) return;
  const rows = await r.json();
  document.getElementById('at-run-ct').textContent = rows.length ? ('\u00b7 ' + rows.length) : '';
  const wrap = document.getElementById('at-run-list');
  if (!rows.length) { wrap.innerHTML = '<div class="at-empty" style="padding:20px;font-size:12px">No runs yet.</div>'; return; }
  rows.sort(function(a,b){ return (b.Created||'').localeCompare(a.Created||''); });
  wrap.innerHTML = rows.map(function(e){
    const st = selVal(e.Status) || 'active';
    const step = (e['Current Step'] || 0) + 1;
    const total = _STEPS.length || 1;
    return '<div class="at-run-row">'
      + '<div class="who"><strong>' + esc(e['Recipient Name'] || e['Recipient Email'] || '(unknown)') + '</strong>'
      + '<small>' + esc(e['Recipient Email']||'') + ' \u00b7 via ' + esc(e['Sender Email']||'auto') + '</small></div>'
      + '<div class="prog">Step ' + step + '/' + total
      + (e['Next Send At'] ? ' \u00b7 next ' + fmtDateTime(e['Next Send At']) : '')
      + '</div>'
      + '<span class="st ' + st + '">' + esc(st.replace('_',' ')) + '</span>'
      + '<div class="actions">'
      + (st === 'active' ? '<button onclick="atPauseRun(' + e.id + ')">Pause</button>' : '')
      + (st === 'paused' ? '<button onclick="atResumeRun(' + e.id + ')">Resume</button>' : '')
      + '<button onclick="atStopRun(' + e.id + ')">\u2715</button>'
      + '</div></div>';
  }).join('');
}

async function _patchRun(id, patch){
  const r = await fetch('/api/enrollments/' + id, {method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(patch)});
  if (r.ok) loadRuns();
}
function atPauseRun(id){ _patchRun(id, {status: 'paused'}); }
function atResumeRun(id){ _patchRun(id, {status: 'active'}); }
function atStopRun(id){ if (confirm('Stop this run?')) _patchRun(id, {status: 'unenrolled'}); }

load().then(loadRuns);
""".replace("__SEQ_ID__", str(seq_id)).replace(
    "__TYPE_OPTS__",
    "[" + ",".join(f'["{k}","{lbl}"]' for k, lbl in STEP_TYPES) + "]"
)

    return _page('sequences', 'Automation', header, body, js, br, bt, user=user)


# ─── "Start automation" modal (lead detail) ──────────────────────────────────
_ENROLL_MODAL_HTML = """
<div class="enr-modal-bg" id="enr-bg" onclick="if(event.target===this)enrClose()">
  <div class="enr-modal">
    <h3>\u26a1 Start automation</h3>
    <label>Automation</label>
    <select id="enr-seq"><option value="">Loading\u2026</option></select>
    <label>Recipient email</label>
    <input type="email" id="enr-email">
    <label>Recipient name</label>
    <input type="text" id="enr-name">
    <div class="enr-msg" id="enr-msg"></div>
    <div class="enr-actions">
      <button type="button" onclick="enrClose()">Cancel</button>
      <button type="button" class="primary" onclick="enrSubmit()">Start</button>
    </div>
  </div>
</div>
<style>
.enr-modal-bg{position:fixed;inset:0;background:rgba(0,0,0,0.5);display:none;align-items:center;justify-content:center;z-index:1000;padding:16px}
.enr-modal-bg.open{display:flex}
.enr-modal{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:22px;width:min(500px,96vw)}
.enr-modal h3{margin:0 0 14px;font-size:17px;font-weight:700}
.enr-modal label{display:block;font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px}
.enr-modal input,.enr-modal select{width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:13px;font-family:inherit;box-sizing:border-box;margin-bottom:12px}
.enr-msg{font-size:12px;color:var(--text3);margin-top:4px;min-height:16px}
.enr-msg.ok{color:#059669}
.enr-msg.err{color:#ef4444}
.enr-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:8px}
.enr-actions button{padding:8px 16px;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer;border:1px solid var(--border);background:transparent;color:var(--text)}
.enr-actions .primary{background:#3b82f6;color:#fff;border-color:#3b82f6}
.enr-actions .primary:hover{background:#2563eb}
</style>
"""


def enroll_modal_html() -> str:
    return _ENROLL_MODAL_HTML


def enroll_modal_js(lead_id: int = 0, company_id: int = 0,
                     prefill_email: str = "", prefill_name: str = "") -> str:
    import json as _json
    return f"""
const _ENR_LEAD    = {int(lead_id) or 0};
const _ENR_COMPANY = {int(company_id) or 0};
const _ENR_EMAIL   = {_json.dumps(prefill_email or "")};
const _ENR_NAME    = {_json.dumps(prefill_name or "")};
let _ENR_LOADED = false;

async function _enrLoadSeqs() {{
  if (_ENR_LOADED) return;
  try {{
    const r = await fetch('/api/sequences');
    if (!r.ok) return;
    const seqs = (await r.json()) || [];
    // Only manual-trigger automations can be started by button click.
    const manual = seqs.filter(s => {{
      const t = (s.Trigger && (s.Trigger.value || s.Trigger)) || 'manual';
      return s['Is Active'] && t === 'manual';
    }});
    const sel = document.getElementById('enr-seq');
    if (!manual.length) {{
      sel.innerHTML = '<option value="">(No active manual-trigger automations)</option>';
      _ENR_LOADED = true; return;
    }}
    sel.innerHTML = '<option value="">Choose one\u2026</option>' + manual.map(function(s) {{
      const cat = (s.Category && (s.Category.value || s.Category)) || '';
      return '<option value="' + s.id + '">' + (s.Name || '').replace(/</g,'&lt;') + (cat ? ' (' + cat + ')' : '') + '</option>';
    }}).join('');
    _ENR_LOADED = true;
  }} catch(e) {{}}
}}

function enrOpen(prefillEmail, prefillName) {{
  document.getElementById('enr-email').value = prefillEmail || _ENR_EMAIL || '';
  document.getElementById('enr-name').value  = prefillName  || _ENR_NAME  || '';
  document.getElementById('enr-msg').textContent = '';
  document.getElementById('enr-msg').className   = 'enr-msg';
  document.getElementById('enr-bg').classList.add('open');
  _enrLoadSeqs();
  setTimeout(function(){{ document.getElementById('enr-seq').focus(); }}, 40);
}}

function enrClose() {{ document.getElementById('enr-bg').classList.remove('open'); }}

async function enrSubmit() {{
  const seqId = document.getElementById('enr-seq').value;
  const email = document.getElementById('enr-email').value.trim();
  const name  = document.getElementById('enr-name').value.trim();
  const msg   = document.getElementById('enr-msg');
  if (!seqId) {{ msg.textContent = 'Pick an automation.'; msg.className = 'enr-msg err'; return; }}
  msg.textContent = 'Starting\u2026'; msg.className = 'enr-msg';
  const recipient = {{email, name}};
  if (_ENR_LEAD)    recipient.lead_id    = _ENR_LEAD;
  if (_ENR_COMPANY) recipient.company_id = _ENR_COMPANY;
  try {{
    const r = await fetch('/api/sequences/' + seqId + '/enroll', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{recipients: [recipient]}}),
    }});
    const data = await r.json();
    if (!r.ok) {{ msg.textContent = 'Failed: ' + (data.error || r.status); msg.className = 'enr-msg err'; return; }}
    msg.textContent = 'Started. First step scheduled.'; msg.className = 'enr-msg ok';
    setTimeout(enrClose, 1400);
  }} catch(e) {{
    msg.textContent = 'Network error: ' + String(e); msg.className = 'enr-msg err';
  }}
}}
"""
