"""
Tickets hub — internal helpdesk ticketing.
List + detail pages. Data loads client-side via /api/tickets*.
"""
from .shared import _page


STATUS_OPTIONS   = ["Open", "In Progress", "Waiting", "Resolved", "Closed"]
PRIORITY_OPTIONS = ["Low", "Normal", "High", "Critical"]
CATEGORY_OPTIONS = ["Software", "Hardware", "Network", "Account", "Other"]
OPEN_STATUSES    = {"Open", "In Progress", "Waiting"}


_TICKETS_STYLES = """
<style>
.tk-toolbar{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap;align-items:center}
.tk-toolbar select,.tk-toolbar input{padding:7px 10px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-size:13px}
.tk-toolbar .grow{flex:1;min-width:180px}
.tk-new-btn{padding:8px 14px;background:#7c3aed;color:#fff;border:none;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer}
.tk-new-btn:hover{background:#6d28d9}
.tk-table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--border);border-radius:10px;overflow:hidden}
.tk-table th,.tk-table td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--border);font-size:13px}
.tk-table th{background:var(--bg2);font-weight:600;color:var(--text3);font-size:11px;text-transform:uppercase;letter-spacing:0.5px}
.tk-table tr:last-child td{border-bottom:0}
.tk-table tr:hover{background:var(--card-hover)}
.tk-row-link{color:inherit;text-decoration:none;display:block}
.tk-pill{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;white-space:nowrap}
.tk-st-open{background:#3b82f622;color:#3b82f6}
.tk-st-inprog{background:#ea580c22;color:#ea580c}
.tk-st-wait{background:#f59e0b22;color:#d97706}
.tk-st-resolved{background:#05966922;color:#059669}
.tk-st-closed{background:#9ca3af22;color:#6b7280}
.tk-pr-low{background:#9ca3af22;color:#6b7280}
.tk-pr-normal{background:#3b82f622;color:#3b82f6}
.tk-pr-high{background:#ea580c22;color:#ea580c}
.tk-pr-crit{background:#ef444422;color:#ef4444}
.tk-empty{padding:60px 20px;text-align:center;color:var(--text3)}
.tk-detail-grid{display:grid;grid-template-columns:1fr 320px;gap:24px}
@media(max-width:900px){.tk-detail-grid{grid-template-columns:1fr}}
.tk-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px 22px;margin-bottom:20px}
.tk-card h3{font-size:14px;font-weight:700;margin:0 0 12px}
.tk-meta-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px;align-items:center;gap:10px}
.tk-meta-row:last-child{border-bottom:0}
.tk-meta-lbl{color:var(--text3);flex-shrink:0}
.tk-meta-val{color:var(--text);font-weight:500;text-align:right}
.tk-meta-val select,.tk-meta-val input{padding:4px 8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);font-size:12px;min-width:140px}
.tk-desc{font-size:13px;line-height:1.6;white-space:pre-wrap;color:var(--text);background:var(--bg2);padding:12px 14px;border-radius:6px;border:1px solid var(--border)}
.tk-thread{display:flex;flex-direction:column;gap:12px;margin-top:10px}
.tk-cmt{padding:10px 14px;border-radius:8px;border:1px solid var(--border);background:var(--bg2)}
.tk-cmt.sys{background:transparent;border-style:dashed;font-size:12px;color:var(--text3);font-style:italic}
.tk-cmt-hd{display:flex;justify-content:space-between;font-size:11px;color:var(--text3);margin-bottom:4px}
.tk-cmt-body{font-size:13px;line-height:1.5;white-space:pre-wrap;color:var(--text)}
.tk-cmt-form{display:flex;flex-direction:column;gap:8px;margin-top:12px}
.tk-cmt-form textarea{padding:8px 10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:13px;font-family:inherit;resize:vertical;min-height:70px}
.tk-cmt-form button{align-self:flex-end;padding:7px 14px;background:#7c3aed;color:#fff;border:none;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer}
.tk-cmt-form button:hover{background:#6d28d9}
.tk-new-modal-bg{position:fixed;inset:0;background:rgba(0,0,0,0.45);display:none;align-items:center;justify-content:center;z-index:1000}
.tk-new-modal-bg.open{display:flex}
.tk-new-modal{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:24px;width:min(500px,90vw);max-height:90vh;overflow-y:auto}
.tk-new-modal h3{margin:0 0 16px;font-size:16px;font-weight:700}
.tk-new-modal label{display:block;font-size:12px;color:var(--text3);margin-bottom:4px;font-weight:600}
.tk-new-modal input,.tk-new-modal select,.tk-new-modal textarea{width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:13px;font-family:inherit;box-sizing:border-box;margin-bottom:14px}
.tk-new-modal textarea{resize:vertical;min-height:90px}
.tk-new-modal-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.tk-new-modal-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:6px}
.tk-back-link{display:inline-block;margin-bottom:14px;font-size:12px;color:var(--text3);text-decoration:none}
.tk-back-link:hover{color:var(--text)}
</style>
"""


def _status_pill_class(status: str) -> str:
    return {
        "Open":        "tk-st-open",
        "In Progress": "tk-st-inprog",
        "Waiting":     "tk-st-wait",
        "Resolved":    "tk-st-resolved",
        "Closed":      "tk-st-closed",
    }.get(status, "tk-st-closed")


def _priority_pill_class(priority: str) -> str:
    return {
        "Low":      "tk-pr-low",
        "Normal":   "tk-pr-normal",
        "High":     "tk-pr-high",
        "Critical": "tk-pr-crit",
    }.get(priority, "tk-pr-normal")


def _new_ticket_modal() -> str:
    cats = "".join(f'<option value="{c}">{c}</option>' for c in CATEGORY_OPTIONS)
    pris = "".join(f'<option value="{p}"{" selected" if p == "Normal" else ""}>{p}</option>' for p in PRIORITY_OPTIONS)
    return (
        '<div class="tk-new-modal-bg" id="tk-new-bg">'
        '<div class="tk-new-modal">'
        '<h3>New ticket</h3>'
        '<label>Title</label>'
        '<input type="text" id="nt-title" placeholder="Short summary of the issue">'
        '<div class="tk-new-modal-row">'
        '<div>'
        '<label>Priority</label>'
        f'<select id="nt-priority">{pris}</select>'
        '</div>'
        '<div>'
        '<label>Category</label>'
        f'<select id="nt-category">{cats}</select>'
        '</div>'
        '</div>'
        '<label>Description</label>'
        '<textarea id="nt-description" placeholder="What happened, what you expected, steps to reproduce, error messages..."></textarea>'
        '<label>Assignee (optional email)</label>'
        '<input type="text" id="nt-assignee" placeholder="someone@reformchiropractic.com">'
        '<div class="tk-new-modal-actions">'
        '<button type="button" class="set-btn" onclick="closeNewTicket()">Cancel</button>'
        '<button type="button" class="tk-new-btn" onclick="submitNewTicket()">Create ticket</button>'
        '</div>'
        '</div>'
        '</div>'
    )


def _tickets_list_page(br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header"><div class="header-left">'
        '<h1>Tickets</h1>'
        '<div class="sub">Internal helpdesk</div>'
        '</div></div>'
    )

    status_opts = '<option value="">All open</option>' + "".join(
        f'<option value="{s}">{s}</option>' for s in STATUS_OPTIONS
    )
    priority_opts = '<option value="">Any priority</option>' + "".join(
        f'<option value="{p}">{p}</option>' for p in PRIORITY_OPTIONS
    )

    # Bulk-actions bar — the select/input values map to the UI keys on
    # /api/tickets/bulk-patch (status, priority, assignee, category).
    bulk_status_opts = '<option value="">Status\u2026</option>' + "".join(f'<option value="{s}">{s}</option>' for s in STATUS_OPTIONS)
    bulk_priority_opts = '<option value="">Priority\u2026</option>' + "".join(f'<option value="{p}">{p}</option>' for p in PRIORITY_OPTIONS)
    bulk_category_opts = '<option value="">Category\u2026</option>' + "".join(f'<option value="{c}">{c}</option>' for c in CATEGORY_OPTIONS)

    body = (
        _TICKETS_STYLES
        + '<div class="tk-toolbar">'
        + '<input type="text" id="flt-search" class="grow" placeholder="Search tickets\u2026">'
        + f'<select id="flt-status">{status_opts}</select>'
        + f'<select id="flt-priority">{priority_opts}</select>'
        + '<select id="flt-assignee"><option value="">Any assignee</option></select>'
        + '<button class="tk-new-btn" onclick="openNewTicket()">+ New ticket</button>'
        + '</div>'
        + '<div class="bulk-actions" id="bulk-actions">'
        + '<span class="bulk-label"><span id="bulk-count">0</span> selected</span>'
        + '<span class="bulk-sep">\u2022</span>'
        + f'<select id="blk-status">{bulk_status_opts}</select>'
        + f'<select id="blk-priority">{bulk_priority_opts}</select>'
        + f'<select id="blk-category">{bulk_category_opts}</select>'
        + '<input type="text" id="blk-assignee" placeholder="Assignee email (blank to unassign)">'
        + '<button class="primary" onclick="tkBulkApply()">Apply</button>'
        + '<button onclick="clearBulk()">Clear</button>'
        + '</div>'
        + '<div id="tk-list"><div class="tk-empty">Loading tickets\u2026</div></div>'
        + _new_ticket_modal()
    )

    js = r"""
let _TICKETS = [];

function pillClass(kind, value) {
  if (kind === 'status') return ({
    'Open': 'tk-st-open', 'In Progress': 'tk-st-inprog', 'Waiting': 'tk-st-wait',
    'Resolved': 'tk-st-resolved', 'Closed': 'tk-st-closed'
  })[value] || 'tk-st-closed';
  return ({'Low':'tk-pr-low','Normal':'tk-pr-normal','High':'tk-pr-high','Critical':'tk-pr-crit'})[value] || 'tk-pr-normal';
}

function fmtDate(iso) {
  if (!iso) return '\u2014';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', {month:'short', day:'numeric'}) + ' ' + d.toLocaleTimeString('en-US', {hour:'numeric', minute:'2-digit'});
}

function selectVal(v) {
  if (!v) return '';
  if (typeof v === 'object') return v.value || '';
  return String(v);
}

function renderList() {
  const search = (document.getElementById('flt-search').value || '').toLowerCase();
  const fStatus = document.getElementById('flt-status').value;
  const fPri = document.getElementById('flt-priority').value;
  const fAssignee = document.getElementById('flt-assignee').value;

  const rows = _TICKETS.filter(t => {
    const status = selectVal(t.Status);
    if (!fStatus && (status === 'Closed' || status === 'Resolved')) return false;
    if (fStatus && status !== fStatus) return false;
    if (fPri && selectVal(t.Priority) !== fPri) return false;
    if (fAssignee && (t.Assignee || '') !== fAssignee) return false;
    if (search) {
      const hay = ((t.Title || '') + ' ' + (t.Description || '') + ' ' + (t.Reporter || '')).toLowerCase();
      if (!hay.includes(search)) return false;
    }
    return true;
  }).sort((a,b) => (b.Created || '').localeCompare(a.Created || ''));

  const wrap = document.getElementById('tk-list');
  if (!rows.length) {
    wrap.innerHTML = '<div class="tk-empty">No tickets match \u2014 try clearing filters, or create a new one.</div>';
    return;
  }

  const headerRow = '<tr><th style="width:28px"><input type="checkbox" class="bulk-all"></th><th>#</th><th>Title</th><th>Status</th><th>Priority</th><th>Assignee</th><th>Reporter</th><th>Updated</th></tr>';
  const body = rows.map(t => {
    const st = selectVal(t.Status) || 'Open';
    const pr = selectVal(t.Priority) || 'Normal';
    return `<tr><td onclick="event.stopPropagation()"><input type="checkbox" class="bulk-check" data-id="${t.id}"></td>`
      + `<td><a class="tk-row-link" href="/tickets/${t.id}">#${t.id}</a></td>`
      + `<td><a class="tk-row-link" href="/tickets/${t.id}">${esc(t.Title || '(untitled)')}</a></td>`
      + `<td><span class="tk-pill ${pillClass('status', st)}">${esc(st)}</span></td>`
      + `<td><span class="tk-pill ${pillClass('priority', pr)}">${esc(pr)}</span></td>`
      + `<td>${esc(t.Assignee || '\u2014')}</td>`
      + `<td>${esc(t.Reporter || '\u2014')}</td>`
      + `<td>${fmtDate(t.Updated || t.Created)}</td></tr>`;
  }).join('');
  wrap.innerHTML = '<table class="tk-table"><thead>' + headerRow + '</thead><tbody>' + body + '</tbody></table>';
  if (typeof initBulkSelection === 'function') initBulkSelection();
}

async function tkBulkApply() {
  const patch = {};
  const s = document.getElementById('blk-status').value;
  const p = document.getElementById('blk-priority').value;
  const c = document.getElementById('blk-category').value;
  const a = document.getElementById('blk-assignee').value;
  if (s) patch.status   = s;
  if (p) patch.priority = p;
  if (c) patch.category = c;
  // Assignee: we treat the field as edit-intent only if the user typed
  // something; an empty value in the input without a status/priority/cat
  // change means they didn't intend to unassign everyone.
  if (document.activeElement && document.activeElement.id === 'blk-assignee') {
    patch.assignee = a;
  } else if (a.trim()) {
    patch.assignee = a.trim();
  }
  if (!Object.keys(patch).length) { bulkToast('Pick a field to change', 'err'); return; }
  const data = await submitBulkPatch('/api/tickets/bulk-patch', patch);
  if (data && data.ok) {
    clearBulk();
    document.getElementById('blk-status').value = '';
    document.getElementById('blk-priority').value = '';
    document.getElementById('blk-category').value = '';
    document.getElementById('blk-assignee').value = '';
    loadTickets();
  }
}

async function loadTickets() {
  try {
    const r = await fetch('/api/tickets');
    if (!r.ok) {
      document.getElementById('tk-list').innerHTML = '<div class="tk-empty">Failed to load tickets.</div>';
      return;
    }
    _TICKETS = (await r.json()) || [];
    // Populate assignee filter with distinct values
    const assignees = Array.from(new Set(_TICKETS.map(t => t.Assignee).filter(Boolean))).sort();
    const sel = document.getElementById('flt-assignee');
    sel.innerHTML = '<option value="">Any assignee</option>' + assignees.map(a => `<option value="${esc(a)}">${esc(a)}</option>`).join('');
    renderList();
  } catch(e) {
    document.getElementById('tk-list').innerHTML = '<div class="tk-empty">Error loading tickets: ' + esc(String(e)) + '</div>';
  }
}

document.getElementById('flt-search').addEventListener('input', renderList);
document.getElementById('flt-status').addEventListener('change', renderList);
document.getElementById('flt-priority').addEventListener('change', renderList);
document.getElementById('flt-assignee').addEventListener('change', renderList);

function openNewTicket(){ document.getElementById('tk-new-bg').classList.add('open'); document.getElementById('nt-title').focus(); }
function closeNewTicket(){ document.getElementById('tk-new-bg').classList.remove('open'); }

async function submitNewTicket() {
  const title = document.getElementById('nt-title').value.trim();
  if (!title) { alert('Title is required'); return; }
  const payload = {
    title,
    description: document.getElementById('nt-description').value,
    priority:    document.getElementById('nt-priority').value,
    category:    document.getElementById('nt-category').value,
    assignee:    document.getElementById('nt-assignee').value.trim(),
  };
  const r = await fetch('/api/tickets', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  if (!r.ok) { alert('Failed to create ticket: ' + r.status); return; }
  const data = await r.json();
  if (data.id) location.href = '/tickets/' + data.id;
  else { closeNewTicket(); loadTickets(); }
}

loadTickets();
"""

    return _page('tickets', 'Tickets', header, body, js, br, bt, user=user)


def _ticket_detail_page(ticket_id: int, br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header"><div class="header-left">'
        f'<h1 id="tk-title-h">Ticket #{ticket_id}</h1>'
        '<div class="sub" id="tk-sub">Loading\u2026</div>'
        '</div></div>'
    )

    status_opts = "".join(f'<option value="{s}">{s}</option>' for s in STATUS_OPTIONS)
    priority_opts = "".join(f'<option value="{p}">{p}</option>' for p in PRIORITY_OPTIONS)
    category_opts = "".join(f'<option value="{c}">{c}</option>' for c in CATEGORY_OPTIONS)

    body = (
        _TICKETS_STYLES
        + '<a href="/tickets" class="tk-back-link">\u2190 All tickets</a>'
        + '<div class="tk-detail-grid">'
        # Left column
        + '<div>'
        + '<div class="tk-card">'
        + '<h3>Description</h3>'
        + '<div class="tk-desc" id="tk-description">\u2014</div>'
        + '</div>'
        + '<div class="tk-card">'
        + '<h3>Activity</h3>'
        + '<div class="tk-thread" id="tk-thread"><div class="tk-empty">Loading\u2026</div></div>'
        + '<form class="tk-cmt-form" onsubmit="postComment(event)">'
        + '<textarea id="tk-new-cmt" placeholder="Add a comment\u2026" required></textarea>'
        + '<button type="submit">Post comment</button>'
        + '</form>'
        + '</div>'
        + '</div>'
        # Right sidebar
        + '<div>'
        + '<div class="tk-card">'
        + '<h3>Details</h3>'
        + '<div class="tk-meta-row"><span class="tk-meta-lbl">Status</span>'
        + f'<span class="tk-meta-val"><select id="tk-status" onchange="saveField(\'status\', this.value)">{status_opts}</select></span></div>'
        + '<div class="tk-meta-row"><span class="tk-meta-lbl">Priority</span>'
        + f'<span class="tk-meta-val"><select id="tk-priority" onchange="saveField(\'priority\', this.value)">{priority_opts}</select></span></div>'
        + '<div class="tk-meta-row"><span class="tk-meta-lbl">Category</span>'
        + f'<span class="tk-meta-val"><select id="tk-category" onchange="saveField(\'category\', this.value)">{category_opts}</select></span></div>'
        + '<div class="tk-meta-row"><span class="tk-meta-lbl">Assignee</span>'
        + '<span class="tk-meta-val"><input type="text" id="tk-assignee" onblur="saveField(\'assignee\', this.value)" placeholder="unassigned"></span></div>'
        + '<div class="tk-meta-row"><span class="tk-meta-lbl">Reporter</span><span class="tk-meta-val" id="tk-reporter">\u2014</span></div>'
        + '<div class="tk-meta-row"><span class="tk-meta-lbl">Created</span><span class="tk-meta-val" id="tk-created">\u2014</span></div>'
        + '<div class="tk-meta-row"><span class="tk-meta-lbl">Updated</span><span class="tk-meta-val" id="tk-updated">\u2014</span></div>'
        + '</div>'
        + '</div>'
        + '</div>'
    )

    js = r"""
const TICKET_ID = __TICKET_ID__;
let _TICKET = null;

function selectVal(v) {
  if (!v) return '';
  if (typeof v === 'object') return v.value || '';
  return String(v);
}
function fmtDate(iso) {
  if (!iso) return '\u2014';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString('en-US', {month:'short', day:'numeric', year:'numeric', hour:'numeric', minute:'2-digit'});
}

async function loadTicket() {
  const r = await fetch('/api/tickets/' + TICKET_ID);
  if (!r.ok) {
    document.getElementById('tk-sub').textContent = 'Ticket not found';
    return;
  }
  _TICKET = await r.json();
  document.getElementById('tk-title-h').textContent = _TICKET.Title || ('Ticket #' + TICKET_ID);
  document.getElementById('tk-sub').textContent = '#' + TICKET_ID;
  document.getElementById('tk-description').textContent = _TICKET.Description || '(no description)';
  document.getElementById('tk-status').value    = selectVal(_TICKET.Status)   || 'Open';
  document.getElementById('tk-priority').value  = selectVal(_TICKET.Priority) || 'Normal';
  document.getElementById('tk-category').value  = selectVal(_TICKET.Category) || 'Software';
  document.getElementById('tk-assignee').value  = _TICKET.Assignee || '';
  document.getElementById('tk-reporter').textContent = _TICKET.Reporter || '\u2014';
  document.getElementById('tk-created').textContent  = fmtDate(_TICKET.Created);
  document.getElementById('tk-updated').textContent  = fmtDate(_TICKET.Updated);
}

async function saveField(field, value) {
  const payload = {};
  payload[field] = value;
  const r = await fetch('/api/tickets/' + TICKET_ID, {method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  if (!r.ok) { alert('Failed to save ' + field); return; }
  await loadTicket();
  await loadComments();
}

async function loadComments() {
  const r = await fetch('/api/tickets/' + TICKET_ID + '/comments');
  if (!r.ok) {
    document.getElementById('tk-thread').innerHTML = '<div class="tk-empty">Failed to load activity.</div>';
    return;
  }
  const rows = (await r.json()) || [];
  rows.sort((a,b) => (a.Created || '').localeCompare(b.Created || ''));
  if (!rows.length) {
    document.getElementById('tk-thread').innerHTML = '<div class="tk-empty">No activity yet.</div>';
    return;
  }
  document.getElementById('tk-thread').innerHTML = rows.map(c => {
    const kind = selectVal(c.Kind) || 'comment';
    const when = fmtDate(c.Created);
    const who = c.Author || 'unknown';
    const isSys = kind !== 'comment';
    return `<div class="tk-cmt ${isSys ? 'sys' : ''}">`
      + `<div class="tk-cmt-hd"><span>${esc(who)}</span><span>${esc(when)}</span></div>`
      + `<div class="tk-cmt-body">${esc(c.Body || '')}</div>`
      + `</div>`;
  }).join('');
}

async function postComment(e) {
  e.preventDefault();
  const ta = document.getElementById('tk-new-cmt');
  const body = ta.value.trim();
  if (!body) return;
  const r = await fetch('/api/tickets/' + TICKET_ID + '/comments', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({body})});
  if (!r.ok) { alert('Failed to post comment'); return; }
  ta.value = '';
  await loadComments();
}

loadTicket();
loadComments();
""".replace("__TICKET_ID__", str(ticket_id))

    return _page('tickets', 'Ticket', header, body, js, br, bt, user=user)
