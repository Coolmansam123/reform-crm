"""
Leads follow-up pipeline — list + detail pages.

Backs onto the existing T_LEADS (817) table in the Gorilla Marketing DB.
Public lead-capture forms (hub/events.py) + authenticated field capture
(`/api/leads/capture`) continue to populate the same table; this module
surfaces those rows as a follow-up workflow with stage transitions,
referral-source links, owner assignment, and convert-to-patient.

Kanban-style board is deferred to a follow-up pass.
"""
from .shared import _page, LEAD_STAGES, OPEN_LEAD_STAGES, CLOSED_LEAD_STAGES
from .tasks import task_modal_html, task_modal_js
from .sms import sms_modal_html, sms_modal_js
from .sequences import enroll_modal_html, enroll_modal_js


_LD_STYLES = """
<style>
.ld-toolbar{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap;align-items:center}
.ld-toolbar select,.ld-toolbar input{padding:7px 10px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-size:13px}
.ld-toolbar .grow{flex:1;min-width:200px}
.ld-new-btn{padding:8px 14px;background:#db2777;color:#fff;border:none;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer}
.ld-new-btn:hover{background:#be185d}
.ld-table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--border);border-radius:10px;overflow:hidden}
.ld-table th,.ld-table td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--border);font-size:13px}
.ld-table th{background:var(--bg2);font-weight:600;color:var(--text3);font-size:11px;text-transform:uppercase;letter-spacing:0.5px}
.ld-table tr:last-child td{border-bottom:0}
.ld-table tr:hover{background:var(--card-hover);cursor:pointer}
.ld-row-link{color:inherit;text-decoration:none;display:block}
.ld-pill{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;white-space:nowrap}
.ld-st-new{background:#3b82f622;color:#3b82f6}
.ld-st-contacted{background:#ea580c22;color:#ea580c}
.ld-st-appt{background:#7c3aed22;color:#7c3aed}
.ld-st-seen{background:#0891b222;color:#0891b2}
.ld-st-converted{background:#05966922;color:#059669}
.ld-st-dropped{background:#9ca3af22;color:#6b7280}
.ld-overdue{color:#ef4444;font-weight:600}
.ld-upcoming{color:#f59e0b;font-weight:500}
.ld-ontrack{color:var(--text3)}
.ld-empty{padding:60px 20px;text-align:center;color:var(--text3)}
.ld-detail-grid{display:grid;grid-template-columns:1fr 340px;gap:24px}
@media(max-width:900px){.ld-detail-grid{grid-template-columns:1fr}}
.ld-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px 22px;margin-bottom:20px}
.ld-card h3{font-size:14px;font-weight:700;margin:0 0 12px}
.ld-meta-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px;align-items:center;gap:10px}
.ld-meta-row:last-child{border-bottom:0}
.ld-meta-lbl{color:var(--text3);flex-shrink:0;text-transform:uppercase;font-size:11px;letter-spacing:.4px}
.ld-meta-val{color:var(--text);font-weight:500;text-align:right;flex:1;min-width:0}
.ld-meta-val select,.ld-meta-val input{padding:5px 8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);font-size:12px;min-width:150px}
.ld-ref-chip{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:12px;background:var(--bg2);color:var(--text);font-size:12px;text-decoration:none;border:1px solid var(--border)}
.ld-ref-chip:hover{border-color:var(--text3)}
.ld-action-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
.ld-act-btn{padding:7px 12px;border:1px solid var(--border);background:var(--card);color:var(--text);border-radius:6px;font-size:12px;font-weight:600;cursor:pointer}
.ld-act-btn:hover{border-color:var(--text3)}
.ld-act-btn.primary{background:#db2777;color:#fff;border-color:#db2777}
.ld-act-btn.primary:hover{background:#be185d}
.ld-call-row{padding:10px 0;border-bottom:1px solid var(--border);font-size:12px}
.ld-call-row:last-child{border-bottom:0}
.ld-modal-bg{position:fixed;inset:0;background:rgba(0,0,0,0.45);display:none;align-items:center;justify-content:center;z-index:1000;padding:16px}
.ld-modal-bg.open{display:flex}
.ld-modal{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:24px;width:min(540px,92vw);max-height:92vh;overflow-y:auto}
.ld-modal h3{margin:0 0 16px;font-size:16px;font-weight:700}
.ld-modal label{display:block;font-size:11px;color:var(--text3);margin-bottom:4px;font-weight:600;text-transform:uppercase;letter-spacing:.4px}
.ld-modal input,.ld-modal select,.ld-modal textarea{width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:13px;font-family:inherit;box-sizing:border-box;margin-bottom:14px}
.ld-modal textarea{resize:vertical;min-height:80px}
.ld-modal-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.ld-modal-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:6px}
.ld-back-link{display:inline-block;margin-bottom:14px;font-size:12px;color:var(--text3);text-decoration:none}
.ld-back-link:hover{color:var(--text)}
</style>
"""


def _status_pill_class(status: str) -> str:
    return {
        "New":                  "ld-st-new",
        "Contacted":            "ld-st-contacted",
        "Appointment Scheduled":"ld-st-appt",
        "Seen":                 "ld-st-seen",
        "Converted":            "ld-st-converted",
        "Dropped":              "ld-st-dropped",
    }.get(status, "ld-st-new")


def _new_lead_modal() -> str:
    return (
        '<div class="ld-modal-bg" id="ld-new-bg">'
        '<div class="ld-modal">'
        '<h3>New lead</h3>'
        '<label>Name *</label>'
        '<input type="text" id="nl-name" placeholder="Jane Doe">'
        '<div class="ld-modal-row">'
        '<div><label>Phone *</label><input type="text" id="nl-phone" placeholder="(555) 555-1234"></div>'
        '<div><label>Email</label><input type="email" id="nl-email" placeholder="jane@example.com"></div>'
        '</div>'
        '<label>Source (where did they come from?)</label>'
        '<input type="text" id="nl-source" placeholder="Referral from Duque &amp; Price, Instagram, etc.">'
        '<label>Reason for visit / notes</label>'
        '<textarea id="nl-reason" placeholder="Pain description, injury context, or any other detail"></textarea>'
        '<label>Owner (staff email — follows up)</label>'
        '<input type="text" id="nl-owner" placeholder="defaults to you">'
        '<div class="ld-modal-actions">'
        '<button type="button" class="ld-act-btn" onclick="closeNewLead()">Cancel</button>'
        '<button type="button" class="ld-act-btn primary" onclick="submitNewLead()">Create lead</button>'
        '</div>'
        '</div></div>'
    )


def _leads_list_page(br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header">'
        '<div class="header-left">'
        '<h1>Leads</h1>'
        '<div class="sub">Prospective patient follow-up pipeline</div>'
        '</div>'
        '<div class="header-right"></div>'
        '</div>'
    )

    status_opts = '<option value="open">Open (all stages)</option>' + "".join(
        f'<option value="{s}">{s}</option>' for s in LEAD_STAGES
    ) + '<option value="">All (incl. closed)</option>'

    bulk_stage_opts = '<option value="">Change stage\u2026</option>' + "".join(
        f'<option value="{s}">{s}</option>' for s in LEAD_STAGES
    )

    body = (
        _LD_STYLES
        + '<div class="ld-toolbar">'
        + '<input type="text" id="flt-search" class="grow" placeholder="Search name, phone, email, source\u2026">'
        + f'<select id="flt-status">{status_opts}</select>'
        + '<select id="flt-owner"><option value="">Any owner</option></select>'
        + '<label style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--text3)"><input type="checkbox" id="flt-overdue"> Overdue only</label>'
        + '<button class="ld-new-btn" onclick="openNewLead()">+ New lead</button>'
        + '</div>'
        + '<div class="bulk-actions" id="bulk-actions">'
        + '<span class="bulk-label"><span id="bulk-count">0</span> selected</span>'
        + '<span class="bulk-sep">\u2022</span>'
        + f'<select id="blk-status">{bulk_stage_opts}</select>'
        + '<input type="text" id="blk-owner" placeholder="Owner email">'
        + '<input type="date" id="blk-fu" title="Follow-Up Date">'
        + '<button class="primary" onclick="ldBulkApply()">Apply</button>'
        + '<button onclick="clearBulk()">Clear</button>'
        + '</div>'
        + '<div id="ld-list"><div class="ld-empty">Loading leads\u2026</div></div>'
        + _new_lead_modal()
    )

    js = r"""
let _LEADS = [];
const OPEN_SET = new Set(__OPEN_STAGES__);

function selectVal(v){ if (!v) return ''; if (typeof v === 'object') return v.value || ''; return String(v); }

function fmtDate(iso){ if (!iso) return '\u2014'; const d = new Date(iso); if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US',{month:'short',day:'numeric'}); }

function daysUntil(iso){ if (!iso) return null; const today = new Date(); today.setHours(0,0,0,0);
  const d = new Date(iso); d.setHours(0,0,0,0); return Math.round((d-today)/86400000); }

function followUpCell(iso){
  if (!iso) return '<span class="ld-ontrack">\u2014</span>';
  const d = daysUntil(iso);
  const label = fmtDate(iso);
  if (d === null) return '<span class="ld-ontrack">' + esc(label) + '</span>';
  if (d < 0)     return '<span class="ld-overdue">' + esc(label) + ' (' + (-d) + 'd late)</span>';
  if (d === 0)  return '<span class="ld-upcoming">Today</span>';
  if (d <= 3)   return '<span class="ld-upcoming">' + esc(label) + '</span>';
  return '<span class="ld-ontrack">' + esc(label) + '</span>';
}

function pillClass(s){
  return ({ 'New':'ld-st-new','Contacted':'ld-st-contacted','Appointment Scheduled':'ld-st-appt',
    'Seen':'ld-st-seen','Converted':'ld-st-converted','Dropped':'ld-st-dropped' })[s] || 'ld-st-new';
}

function renderList(){
  const search = (document.getElementById('flt-search').value || '').toLowerCase();
  const fStatus = document.getElementById('flt-status').value;
  const fOwner  = document.getElementById('flt-owner').value;
  const overdueOnly = document.getElementById('flt-overdue').checked;
  const todayIso = new Date().toISOString().slice(0,10);

  const rows = _LEADS.filter(l => {
    const status = selectVal(l.Status) || 'New';
    if (fStatus === 'open') { if (!OPEN_SET.has(status)) return false; }
    else if (fStatus && status !== fStatus) return false;
    if (fOwner && (l.Owner || '') !== fOwner) return false;
    if (overdueOnly) {
      if (!l['Follow-Up Date']) return false;
      if (l['Follow-Up Date'] >= todayIso) return false;
      if (!OPEN_SET.has(status)) return false;
    }
    if (search) {
      const hay = ((l.Name||'')+' '+(l.Phone||'')+' '+(l.Email||'')+' '+(l.Source||'')+' '+(l.Owner||'')).toLowerCase();
      if (!hay.includes(search)) return false;
    }
    return true;
  }).sort((a,b) => {
    // overdue > today > upcoming > no-date; then newest created
    const fa = a['Follow-Up Date'], fb = b['Follow-Up Date'];
    if (fa && fb) return fa.localeCompare(fb);
    if (fa) return -1;
    if (fb) return 1;
    return (b.Created || '').localeCompare(a.Created || '');
  });

  const wrap = document.getElementById('ld-list');
  if (!rows.length) {
    wrap.innerHTML = '<div class="ld-empty">No leads match \u2014 try clearing filters, or create a new one.</div>';
    return;
  }

  const headerRow = '<tr><th style="width:28px"><input type="checkbox" class="bulk-all"></th><th>Name</th><th>Phone</th><th>Status</th><th>Source</th><th>Owner</th><th>Follow-up</th></tr>';
  const body = rows.map(l => {
    const st = selectVal(l.Status) || 'New';
    const phone = l.Phone || '\u2014';
    return '<tr>'
      + '<td onclick="event.stopPropagation()" style="width:28px"><input type="checkbox" class="bulk-check" data-id="' + l.id + '"></td>'
      + '<td onclick="location.href=\'/leads/' + l.id + '\'"><a class="ld-row-link" href="/leads/' + l.id + '"><strong>' + esc(l.Name || '(no name)') + '</strong></a></td>'
      + '<td onclick="location.href=\'/leads/' + l.id + '\'">' + esc(phone) + '</td>'
      + '<td onclick="location.href=\'/leads/' + l.id + '\'"><span class="ld-pill ' + pillClass(st) + '">' + esc(st) + '</span></td>'
      + '<td onclick="location.href=\'/leads/' + l.id + '\'">' + esc(l.Source || '\u2014') + '</td>'
      + '<td onclick="location.href=\'/leads/' + l.id + '\'">' + esc(l.Owner || '\u2014') + '</td>'
      + '<td onclick="location.href=\'/leads/' + l.id + '\'">' + followUpCell(l['Follow-Up Date']) + '</td>'
      + '</tr>';
  }).join('');
  wrap.innerHTML = '<table class="ld-table"><thead>' + headerRow + '</thead><tbody>' + body + '</tbody></table>';
  if (typeof initBulkSelection === 'function') initBulkSelection();
}

async function ldBulkApply(){
  const patch = {};
  const s  = document.getElementById('blk-status').value;
  const ow = document.getElementById('blk-owner').value.trim();
  const fu = document.getElementById('blk-fu').value;
  if (s)  patch.status = s;
  if (ow) patch.owner  = ow;
  if (fu) patch.follow_up_date = fu;
  if (!Object.keys(patch).length){ bulkToast('Pick a field to change', 'err'); return; }
  const data = await submitBulkPatch('/api/leads/bulk-patch', patch);
  if (data && data.ok){
    clearBulk();
    document.getElementById('blk-status').value = '';
    document.getElementById('blk-owner').value = '';
    document.getElementById('blk-fu').value = '';
    loadLeads();
  }
}

async function loadLeads(){
  try {
    const r = await fetch('/api/leads');
    if (!r.ok) {
      document.getElementById('ld-list').innerHTML = '<div class="ld-empty">Failed to load leads.</div>';
      return;
    }
    _LEADS = (await r.json()) || [];
    const owners = Array.from(new Set(_LEADS.map(l => l.Owner).filter(Boolean))).sort();
    const sel = document.getElementById('flt-owner');
    sel.innerHTML = '<option value="">Any owner</option>' + owners.map(o => '<option value="'+esc(o)+'">'+esc(o)+'</option>').join('');
    renderList();
  } catch(e) {
    document.getElementById('ld-list').innerHTML = '<div class="ld-empty">Error: ' + esc(String(e)) + '</div>';
  }
}

document.getElementById('flt-search').addEventListener('input', renderList);
document.getElementById('flt-status').addEventListener('change', renderList);
document.getElementById('flt-owner').addEventListener('change', renderList);
document.getElementById('flt-overdue').addEventListener('change', renderList);

function openNewLead(){ document.getElementById('ld-new-bg').classList.add('open'); document.getElementById('nl-name').focus(); }
function closeNewLead(){ document.getElementById('ld-new-bg').classList.remove('open'); }

async function submitNewLead(){
  const name  = document.getElementById('nl-name').value.trim();
  const phone = document.getElementById('nl-phone').value.trim();
  if (!name || !phone) { alert('Name and phone are required'); return; }
  const payload = {
    name, phone,
    email:  document.getElementById('nl-email').value.trim(),
    source: document.getElementById('nl-source').value.trim(),
    reason: document.getElementById('nl-reason').value.trim(),
    owner:  document.getElementById('nl-owner').value.trim(),
  };
  const r = await fetch('/api/leads/crm', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  if (!r.ok) { const t = await r.text(); alert('Failed to create lead: ' + t); return; }
  const data = await r.json();
  if (data.id) location.href = '/leads/' + data.id;
  else { closeNewLead(); loadLeads(); }
}

loadLeads();
""".replace("__OPEN_STAGES__", str(sorted(OPEN_LEAD_STAGES)).replace("'", '"'))

    return _page('leads', 'Leads', header, body, js, br, bt, user=user)


def _lead_detail_page(lead_id: int, br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header"><div class="header-left">'
        f'<h1 id="ld-name-h">Lead #{lead_id}</h1>'
        '<div class="sub" id="ld-sub">Loading\u2026</div>'
        '</div></div>'
    )

    status_opts = "".join(f'<option value="{s}">{s}</option>' for s in LEAD_STAGES)
    call_status_opts = "".join(f'<option value="{c}">{c}</option>' for c in
        ["Not Called", "Queued", "Called", "Answered", "Voicemail", "Failed"])

    body = (
        _LD_STYLES
        + '<a href="/leads" class="ld-back-link">\u2190 All leads</a>'
        + '<div class="ld-detail-grid">'
        # Left column
        + '<div>'
        + '<div class="ld-card">'
        + '<h3>Contact</h3>'
        + '<div class="ld-meta-row"><span class="ld-meta-lbl">Name</span><span class="ld-meta-val"><input type="text" id="ld-name" onblur="saveField(\'name\', this.value)"></span></div>'
        + '<div class="ld-meta-row"><span class="ld-meta-lbl">Phone</span><span class="ld-meta-val"><input type="text" id="ld-phone" onblur="saveField(\'phone\', this.value)"></span></div>'
        + '<div class="ld-meta-row"><span class="ld-meta-lbl">Email</span><span class="ld-meta-val"><input type="email" id="ld-email" onblur="saveField(\'email\', this.value)"></span></div>'
        + '<div class="ld-meta-row"><span class="ld-meta-lbl">Source</span><span class="ld-meta-val"><input type="text" id="ld-source" onblur="saveField(\'source\', this.value)"></span></div>'
        + '<div class="ld-meta-row"><span class="ld-meta-lbl">Reason</span><span class="ld-meta-val"><input type="text" id="ld-reason" onblur="saveField(\'reason\', this.value)"></span></div>'
        + '<div class="ld-meta-row"><span class="ld-meta-lbl">Referred by</span><span class="ld-meta-val" id="ld-refs">\u2014</span></div>'
        + '</div>'
        + '<div class="ld-card">'
        + '<h3>Notes</h3>'
        + '<textarea id="ld-notes" style="width:100%;min-height:100px;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-family:inherit;font-size:13px;resize:vertical" onblur="saveField(\'notes\', this.value)"></textarea>'
        + '</div>'
        + '<div class="ld-card">'
        + '<h3>Call log</h3>'
        + '<div class="ld-meta-row"><span class="ld-meta-lbl">Call status</span>'
        + f'<span class="ld-meta-val"><select id="ld-cstatus" onchange="saveField(\'call_status\', this.value)">{call_status_opts}</select></span></div>'
        + '<textarea id="ld-cnotes" style="width:100%;min-height:70px;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-family:inherit;font-size:13px;resize:vertical;margin-top:10px" placeholder="Call notes (script, objections, next step)" onblur="saveField(\'call_notes\', this.value)"></textarea>'
        + '</div>'
        + '</div>'
        # Right sidebar
        + '<div>'
        + '<div class="ld-card">'
        + '<h3>Pipeline</h3>'
        + '<div class="ld-meta-row"><span class="ld-meta-lbl">Stage</span>'
        + f'<span class="ld-meta-val"><select id="ld-status" onchange="saveField(\'status\', this.value)">{status_opts}</select></span></div>'
        + '<div class="ld-meta-row"><span class="ld-meta-lbl">Owner</span><span class="ld-meta-val"><input type="text" id="ld-owner" onblur="saveField(\'owner\', this.value)" placeholder="staff email"></span></div>'
        + '<div class="ld-meta-row"><span class="ld-meta-lbl">Follow-up</span><span class="ld-meta-val"><input type="date" id="ld-fu" onchange="saveField(\'follow_up_date\', this.value)"></span></div>'
        + '<div class="ld-meta-row"><span class="ld-meta-lbl">Appointment</span><span class="ld-meta-val" id="ld-appt">\u2014</span></div>'
        + '<div class="ld-meta-row"><span class="ld-meta-lbl">Seen</span><span class="ld-meta-val" id="ld-seen">\u2014</span></div>'
        + '<div class="ld-meta-row"><span class="ld-meta-lbl">Converted</span><span class="ld-meta-val" id="ld-conv">\u2014</span></div>'
        + '<div class="ld-meta-row"><span class="ld-meta-lbl">Created</span><span class="ld-meta-val" id="ld-created">\u2014</span></div>'
        + '<div class="ld-action-row">'
        + '<button class="ld-act-btn primary" onclick="convertToPatient()">\u2714 Convert to Patient</button>'
        + '<button class="ld-act-btn" onclick="atkOpen()">\U00002795 Add task</button>'
        + '<button class="ld-act-btn" onclick="smsOpen(_LEAD && _LEAD.Phone)">\U0001f4ac Send SMS</button>'
        + '<button class="ld-act-btn" onclick="enrOpen(_LEAD && _LEAD.Email, _LEAD && _LEAD.Name)">\u26a1 Start automation</button>'
        + '</div>'
        + '</div>'
        + '</div>'
        + '</div>'
        + task_modal_html()
        + sms_modal_html()
        + enroll_modal_html()
    )

    js = r"""
const LEAD_ID = __LEAD_ID__;
let _LEAD = null;

function selectVal(v){ if (!v) return ''; if (typeof v === 'object') return v.value || ''; return String(v); }

function fmtDate(iso, withTime){
  if (!iso) return '\u2014';
  const d = new Date(iso); if (isNaN(d.getTime())) return iso;
  const opts = withTime
    ? {month:'short', day:'numeric', year:'numeric', hour:'numeric', minute:'2-digit'}
    : {month:'short', day:'numeric', year:'numeric'};
  return d.toLocaleDateString('en-US', opts);
}

function setRefChips(lead){
  const parts = [];
  if (lead._refCompany) parts.push('<a class="ld-ref-chip" href="/companies/' + lead._refCompany.id + '">\U0001f3e2 ' + esc(lead._refCompany.name || 'Company #' + lead._refCompany.id) + '</a>');
  if (lead._refPerson)  parts.push('<a class="ld-ref-chip" href="/people/'    + lead._refPerson.id  + '">\U0001f464 ' + esc(lead._refPerson.name  || 'Person #'  + lead._refPerson.id)  + '</a>');
  document.getElementById('ld-refs').innerHTML = parts.length ? parts.join(' ') : '<span style="color:var(--text3)">\u2014</span>';
}

async function loadLead(){
  const r = await fetch('/api/leads/' + LEAD_ID);
  if (!r.ok) { document.getElementById('ld-sub').textContent = 'Lead not found'; return; }
  _LEAD = await r.json();
  document.getElementById('ld-name-h').textContent = _LEAD.Name || ('Lead #' + LEAD_ID);
  document.getElementById('ld-sub').textContent    = (_LEAD.Phone || '') + (_LEAD.Email ? '  \u2022  ' + _LEAD.Email : '');
  document.getElementById('ld-name').value   = _LEAD.Name   || '';
  document.getElementById('ld-phone').value  = _LEAD.Phone  || '';
  document.getElementById('ld-email').value  = _LEAD.Email  || '';
  document.getElementById('ld-source').value = _LEAD.Source || '';
  document.getElementById('ld-reason').value = _LEAD.Reason || '';
  document.getElementById('ld-notes').value  = _LEAD.Notes  || '';
  document.getElementById('ld-cnotes').value = _LEAD['Call Notes'] || '';
  document.getElementById('ld-cstatus').value = selectVal(_LEAD['Call Status']) || 'Not Called';
  document.getElementById('ld-status').value = selectVal(_LEAD.Status) || 'New';
  document.getElementById('ld-owner').value  = _LEAD.Owner || '';
  document.getElementById('ld-fu').value     = _LEAD['Follow-Up Date']   || '';
  document.getElementById('ld-appt').textContent    = fmtDate(_LEAD['Appointment Date'], true);
  document.getElementById('ld-seen').textContent    = fmtDate(_LEAD['Seen Date']);
  document.getElementById('ld-conv').textContent    = fmtDate(_LEAD['Converted Date']);
  document.getElementById('ld-created').textContent = fmtDate(_LEAD.Created, true);
  setRefChips(_LEAD);
}

async function saveField(field, value){
  const payload = {}; payload[field] = value;
  const r = await fetch('/api/leads/' + LEAD_ID, {method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  if (!r.ok) { alert('Failed to save ' + field); return; }
  await loadLead();
}

async function convertToPatient(){
  if (!_LEAD) return;
  const go = confirm('Create a patient record from this lead?\n\nName: ' + (_LEAD.Name || '') + '\nPhone: ' + (_LEAD.Phone || ''));
  if (!go) return;
  const r = await fetch('/api/leads/' + LEAD_ID + '/convert', {method:'POST', headers:{'Content-Type':'application/json'}, body: '{}'});
  if (!r.ok) { const t = await r.text(); alert('Conversion failed: ' + t); return; }
  const d = await r.json();
  if (d.patient_id) {
    alert('Converted. New patient id: ' + d.patient_id);
    await loadLead();
  }
}

loadLead();
""".replace("__LEAD_ID__", str(lead_id)) + task_modal_js(lead_id=lead_id) + sms_modal_js(lead_id=lead_id) + enroll_modal_js(lead_id=lead_id)

    return _page('leads', 'Lead', header, body, js, br, bt, user=user)
