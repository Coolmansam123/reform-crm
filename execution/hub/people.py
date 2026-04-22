"""
People (contacts-as-individuals) pages:

- `/people`       — list of all contact people
- `/people/{id}`  — person detail with linked company + activity/history tabs
- `/people/new`   — new contact form (supports ?company_id= prefill)

Uses the same visual language as company_detail (co-* classes) so they feel
like the same product.
"""
from .shared import _page
from .company_detail import _CO_STYLES, STATUS_OPTIONS, ACTIVITY_TYPES, ACTIVITY_OUTCOMES
from .meetings import meeting_modal_html, meeting_modal_js
from .tasks import task_modal_html, task_modal_js
from .sms import sms_modal_html, sms_modal_js


LIFECYCLE_OPTIONS = ["Lead", "Prospect", "Customer", "Past", "Other"]


_PEOPLE_EXTRA_STYLES = """
<style>
.pe-toolbar{display:flex;gap:10px;margin-bottom:16px;align-items:center;flex-wrap:wrap}
.pe-toolbar input,.pe-toolbar select{padding:8px 12px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-size:13px}
.pe-toolbar .pe-search{flex:1;min-width:200px;max-width:420px}
.pe-new-btn{padding:8px 14px;background:#7c3aed;color:#fff;border:none;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer}
.pe-new-btn:hover{background:#6d28d9}
.pe-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.pe-card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px 16px;display:block;text-decoration:none;color:var(--text);transition:border-color .12s}
.pe-card:hover{border-color:var(--text3)}
.pe-name{font-size:14px;font-weight:600;margin-bottom:2px}
.pe-title{font-size:12px;color:var(--text3)}
.pe-company{font-size:11px;color:var(--text2);margin-top:8px}
.pe-stage{display:inline-block;padding:1px 8px;border-radius:4px;font-size:10px;font-weight:600;margin-top:6px}
.pe-lc-lead{background:#3b82f622;color:#3b82f6}
.pe-lc-prospect{background:#ea580c22;color:#ea580c}
.pe-lc-customer{background:#05966922;color:#059669}
.pe-lc-past{background:#9ca3af22;color:#6b7280}
.pe-lc-other{background:#fbbf2422;color:#d97706}
</style>
"""


def _lifecycle_class(stage: str) -> str:
    return {
        "Lead":     "pe-lc-lead",
        "Prospect": "pe-lc-prospect",
        "Customer": "pe-lc-customer",
        "Past":     "pe-lc-past",
        "Other":    "pe-lc-other",
    }.get(stage, "pe-lc-other")


def _people_list_page(br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header"><div class="header-left">'
        '<h1>People</h1>'
        '<div class="sub">Individual contacts \u2014 linked to companies</div>'
        '</div></div>'
    )

    lc_opts = '<option value="">Any stage</option>' + "".join(
        f'<option value="{s}">{s}</option>' for s in LIFECYCLE_OPTIONS
    )

    bulk_lc_opts = '<option value="">Change lifecycle stage\u2026</option>' + "".join(
        f'<option value="{s}">{s}</option>' for s in LIFECYCLE_OPTIONS
    )

    body = (
        _CO_STYLES
        + _PEOPLE_EXTRA_STYLES
        + '<style>.pe-card{position:relative}.pe-chk{position:absolute;top:10px;right:10px;z-index:2}</style>'
        + '<div class="co-wrap">'
        + '<div class="pe-toolbar">'
        + '<input type="text" class="pe-search" id="pe-search" placeholder="Search name, email, phone\u2026">'
        + f'<select id="pe-stage">{lc_opts}</select>'
        + '<span style="flex:1"></span>'
        + '<button class="pe-new-btn" onclick="openNewPerson()">+ New person</button>'
        + '</div>'
        + '<div class="bulk-actions" id="bulk-actions">'
        + '<span class="bulk-label"><span id="bulk-count">0</span> selected</span>'
        + '<span class="bulk-sep">\u2022</span>'
        + f'<select id="blk-lifecycle">{bulk_lc_opts}</select>'
        + '<button class="primary" onclick="peBulkApply()">Apply</button>'
        + '<button onclick="clearBulk()">Clear</button>'
        + '</div>'
        + '<div id="pe-count" style="font-size:12px;color:var(--text3);margin-bottom:10px"></div>'
        + '<div class="pe-grid" id="pe-grid"><div class="co-empty">Loading\u2026</div></div>'
        + _new_person_modal()
        + '</div>'
    )

    js = r"""
let _PEOPLE = [];
let _COMPANIES_INDEX = {};

function sv(v){ if(!v) return ''; if(typeof v==='object') return v.value||''; return String(v); }

async function loadPeople() {
  try {
    const r = await fetch('/api/people');
    if (!r.ok) {
      const msg = r.status === 401 ? 'Please sign in.' : ('Failed to load people (HTTP ' + r.status + '). Try refreshing.');
      document.getElementById('pe-grid').innerHTML = '<div class="co-empty">' + msg + '</div>';
      return;
    }
    _PEOPLE = (await r.json()) || [];
    // Build a quick index of company id -> name for display on cards
    try {
      const r2 = await fetch('/api/data/820');
      if (r2.ok) {
        const rows = await r2.json();
        rows.forEach(function(c){ _COMPANIES_INDEX[c.id] = c.Name; });
      }
    } catch(e) { /* non-fatal */ }
    render();
  } catch(e) {
    document.getElementById('pe-grid').innerHTML = '<div class="co-empty">Network error loading people: ' + esc(String(e)) + '</div>';
  }
}

function lifecycleClass(stage) {
  return ({'Lead':'pe-lc-lead','Prospect':'pe-lc-prospect','Customer':'pe-lc-customer','Past':'pe-lc-past','Other':'pe-lc-other'})[stage] || 'pe-lc-other';
}

function render() {
  const q = (document.getElementById('pe-search').value || '').toLowerCase();
  const stage = document.getElementById('pe-stage').value;
  const filtered = _PEOPLE.filter(function(p) {
    if (stage && sv(p['Lifecycle Stage']) !== stage) return false;
    if (q) {
      const hay = ((p.Name||'') + ' ' + (p.Email||'') + ' ' + (p.Phone||'') + ' ' + (p.Title||'')).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }).sort(function(a,b){ return (a.Name||'').localeCompare(b.Name||''); });

  document.getElementById('pe-count').textContent = filtered.length + ' of ' + _PEOPLE.length + ' people';
  const grid = document.getElementById('pe-grid');
  if (!filtered.length) {
    const msg = _PEOPLE.length === 0
      ? 'No people yet. Click <strong>+ New person</strong> above to add one, or link people to companies from a company detail page.'
      : 'No people match the current filter.';
    grid.innerHTML = '<div class="co-empty" style="padding:48px 20px">' + msg + '</div>';
    return;
  }

  grid.innerHTML = filtered.map(function(p) {
    const pc = (p['Primary Company'] || [])[0];
    const companyName = pc ? (_COMPANIES_INDEX[pc.id] || pc.value || '') : '';
    const stage = sv(p['Lifecycle Stage']) || 'Lead';
    return '<a class="pe-card" href="/people/' + p.id + '">'
      + '<input type="checkbox" class="bulk-check pe-chk" data-id="' + p.id + '" onclick="event.stopPropagation()">'
      + '<div class="pe-name">' + esc(p.Name || '(unnamed)') + '</div>'
      + (p.Title ? '<div class="pe-title">' + esc(p.Title) + '</div>' : '')
      + (companyName ? '<div class="pe-company">\u2198 ' + esc(companyName) + '</div>' : '')
      + '<span class="pe-stage ' + lifecycleClass(stage) + '">' + esc(stage) + '</span>'
      + '</a>';
  }).join('');
  if (typeof initBulkSelection === 'function') initBulkSelection();
}

async function peBulkApply(){
  const patch = {};
  const lc = document.getElementById('blk-lifecycle').value;
  if (lc) patch.lifecycle_stage = lc;
  if (!Object.keys(patch).length){ bulkToast('Pick a field to change', 'err'); return; }
  const data = await submitBulkPatch('/api/people/bulk-patch', patch);
  if (data && data.ok){
    clearBulk();
    document.getElementById('blk-lifecycle').value = '';
    loadPeople();
  }
}

document.getElementById('pe-search').addEventListener('input', render);
document.getElementById('pe-stage').addEventListener('change', render);

let _NP_COMPANIES = [];
function openNewPerson(prefillCompany) {
  document.getElementById('np-overlay').classList.add('open');
  document.getElementById('np-name').value = '';
  document.getElementById('np-title').value = '';
  document.getElementById('np-email').value = '';
  document.getElementById('np-phone').value = '';
  document.getElementById('np-notes').value = '';
  document.getElementById('np-lifecycle').value = 'Lead';
  if (!_NP_COMPANIES.length) _loadCompaniesForNP();
  if (prefillCompany) document.getElementById('np-company').value = prefillCompany;
  setTimeout(function(){ document.getElementById('np-name').focus(); }, 50);
}
function closeNewPerson() { document.getElementById('np-overlay').classList.remove('open'); }

async function _loadCompaniesForNP() {
  const r = await fetch('/api/data/820');
  if (!r.ok) return;
  const rows = await r.json();
  rows.sort(function(a,b){return (a.Name||'').localeCompare(b.Name||'');});
  _NP_COMPANIES = rows;
  document.getElementById('np-company').innerHTML = '<option value="">\u2014 None \u2014</option>'
    + rows.map(function(c){ return '<option value="'+c.id+'">'+esc(c.Name||'')+'</option>'; }).join('');
}

async function submitNewPerson() {
  const name = document.getElementById('np-name').value.trim();
  if (!name) { alert('Name required'); return; }
  const body = {
    name,
    title:     document.getElementById('np-title').value,
    email:     document.getElementById('np-email').value,
    phone:     document.getElementById('np-phone').value,
    notes:     document.getElementById('np-notes').value,
    lifecycle: document.getElementById('np-lifecycle').value,
  };
  const companyId = document.getElementById('np-company').value;
  if (companyId) body.primary_company = parseInt(companyId);
  const r = await fetch('/api/people', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if (!r.ok) { alert('Failed to create'); return; }
  const person = await r.json();
  location.href = '/people/' + person.id;
}

// Support ?company_id= prefill
const params = new URLSearchParams(location.search);
if (params.has('new')) setTimeout(function(){ openNewPerson(params.get('company_id')); }, 100);

loadPeople();
"""
    return _page('people', 'People', header, body, js, br, bt, user=user)


def _new_person_modal() -> str:
    lc_opts = "".join(f'<option value="{s}"{" selected" if s == "Lead" else ""}>{s}</option>' for s in LIFECYCLE_OPTIONS)
    return (
        '<div class="compose-overlay" id="np-overlay" onclick="if(event.target===this)closeNewPerson()">'
        '<div class="compose-box" style="width:480px">'
        '<h3>+ New Person</h3>'
        '<input id="np-name"  class="compose-input" placeholder="Full name *">'
        '<input id="np-title" class="compose-input" placeholder="Title (e.g., Paralegal, Owner)">'
        '<input id="np-email" class="compose-input" placeholder="Email">'
        '<input id="np-phone" class="compose-input" placeholder="Phone">'
        '<select id="np-company" class="compose-input"><option value="">\u2014 None \u2014</option></select>'
        f'<select id="np-lifecycle" class="compose-input">{lc_opts}</select>'
        '<textarea id="np-notes" class="compose-input" placeholder="Notes" style="min-height:60px;resize:vertical"></textarea>'
        '<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:4px">'
        '<button class="compose-send" onclick="closeNewPerson()" style="background:#1e3a5f;color:var(--text2)">Cancel</button>'
        '<button class="compose-send" onclick="submitNewPerson()">Create</button>'
        '</div>'
        '</div></div>'
    )


def _person_detail_page(person_id: int, br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header"><div class="header-left">'
        '<h1 id="pd-hname">Loading\u2026</h1>'
        '<div class="sub" id="pd-hsub">&nbsp;</div>'
        '</div></div>'
    )
    lc_opts = "".join(f'<option value="{s}">{s}</option>' for s in LIFECYCLE_OPTIONS)
    type_opts = '<option value="">Type</option>' + "".join(f'<option value="{t}">{t}</option>' for t in ACTIVITY_TYPES)
    outcome_opts = '<option value="">Outcome</option>' + "".join(f'<option value="{o}">{o}</option>' for o in ACTIVITY_OUTCOMES)

    body = (
        _CO_STYLES
        + _PEOPLE_EXTRA_STYLES
        + '<div class="co-wrap">'
        + '<a href="/people" class="co-back">\u2190 All People</a>'
        + '<div class="co-header">'
        + '<div class="co-avatar" id="pd-avatar" style="background:#7c3aed">?</div>'
        + '<div class="co-htext">'
        + '<h1 id="pd-name-display">Loading\u2026</h1>'
        + '<div class="co-sub" id="pd-sub">&nbsp;</div>'
        + '</div>'
        + '<div class="co-headtool" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
        + f'<select id="pd-lifecycle" onchange="savePerson(\'Lifecycle Stage\', this.value, this)"><option value="">Stage\u2026</option>{lc_opts}</select>'
        + '<span class="co-saving" id="pd-lc-st"></span>'
        + '<button class="mt-btn primary" onclick="openMeetingModal()">\U0001f4c5 Schedule meeting</button>'
        + '<button class="mt-btn" onclick="pdOpenLogLead()">\U0001f4e5 Log lead</button>'
        + '<button class="mt-btn" onclick="atkOpen()">\U00002795 Add task</button>'
        + '<button class="mt-btn" onclick="smsOpen(_P && _P.Phone)">\U0001f4ac Send SMS</button>'
        + '</div>'
        + '</div>'
        + '<div class="co-grid">'
        + '<div>'
        + '<div class="co-card">'
        + '<h3>About</h3>'
        + '<div class="co-field"><span class="co-flabel">Name</span><span class="co-fval"><input id="pf-Name" onblur="savePerson(\'Name\', this.value, this)"></span></div>'
        + '<div class="co-field"><span class="co-flabel">Title</span><span class="co-fval"><input id="pf-Title" onblur="savePerson(\'Title\', this.value, this)"></span></div>'
        + '<div class="co-field"><span class="co-flabel">Email</span><span class="co-fval"><input id="pf-Email" type="email" onblur="savePerson(\'Email\', this.value, this)"></span></div>'
        + '<div class="co-field"><span class="co-flabel">Phone</span><span class="co-fval"><input id="pf-Phone" onblur="savePerson(\'Phone\', this.value, this)"></span></div>'
        + '<div class="co-field"><span class="co-flabel">Notes</span><span class="co-fval"><textarea id="pf-Notes" onblur="savePerson(\'Notes\', this.value, this)"></textarea></span></div>'
        + '</div>'
        + '<div class="co-card" style="padding:14px 18px">'
        + '<div class="co-tabs">'
        + '<div class="co-tab active" data-tab="activity" onclick="pdSwitchTab(this)">Activity <span class="co-tab-ct" id="pd-tab-ct-activity"></span></div>'
        + '<div class="co-tab" data-tab="history" onclick="pdSwitchTab(this)">History <span class="co-tab-ct" id="pd-tab-ct-history"></span></div>'
        + '</div>'
        + '<div id="pd-tab-activity">'
        + '<div class="co-log-form">'
        + '<div class="co-log-row">'
        + f'<select id="pd-log-type">{type_opts}</select>'
        + f'<select id="pd-log-outcome">{outcome_opts}</select>'
        + '</div>'
        + '<textarea id="pd-log-summary" placeholder="What happened? (required)"></textarea>'
        + '<div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;gap:10px;flex-wrap:wrap">'
        + '<input type="date" id="pd-log-follow-up" style="padding:6px 10px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-size:12px">'
        + '<button onclick="pdLogActivity()">+ Log activity</button>'
        + '</div>'
        + '</div>'
        + '<div class="co-feed" id="pd-feed-activity"><div class="co-empty">Loading\u2026</div></div>'
        + '</div>'
        + '<div id="pd-tab-history" style="display:none">'
        + '<div class="co-feed" id="pd-feed-history"><div class="co-empty">Loading\u2026</div></div>'
        + '</div>'
        + '</div>'
        + '</div>'
        + '<div>'
        + '<div class="co-card"><h3>Companies</h3><div id="pd-companies"><div class="co-empty">Loading\u2026</div></div></div>'
        + '<div class="co-card">'
        + '<h3>Details</h3>'
        + '<div class="co-field"><span class="co-flabel">Created</span><span class="co-fval" id="pd-meta-created">\u2014</span></div>'
        + '<div class="co-field"><span class="co-flabel">Updated</span><span class="co-fval" id="pd-meta-updated">\u2014</span></div>'
        + '</div>'
        + '</div>'
        + '</div>'
        + '</div>'
        + meeting_modal_html()
        + task_modal_html()
        + sms_modal_html()
        # Lead-capture modal — pre-fills Referred By Person (and Company if person has a primary)
        + '<div class="mt-modal-bg" id="pd-lg-bg" onclick="if(event.target===this)pdCloseLogLead()">'
        + '<div class="mt-modal">'
        + '<h3>\U0001f4e5 Log lead referred by this person</h3>'
        + '<label>Name *</label>'
        + '<input type="text" id="pd-lg-name">'
        + '<div class="mt-modal-row">'
        + '<div><label>Phone *</label><input type="text" id="pd-lg-phone"></div>'
        + '<div><label>Email</label><input type="email" id="pd-lg-email"></div>'
        + '</div>'
        + '<label>Source note</label>'
        + '<input type="text" id="pd-lg-source" placeholder="Word of mouth, existing-patient referral, etc.">'
        + '<label>Reason / notes</label>'
        + '<textarea id="pd-lg-reason"></textarea>'
        + '<div class="mt-msg" id="pd-lg-msg"></div>'
        + '<div class="mt-modal-actions">'
        + '<button type="button" onclick="pdCloseLogLead()">Cancel</button>'
        + '<button type="button" class="mt-primary" onclick="pdSubmitLogLead()">Create lead</button>'
        + '</div>'
        + '</div></div>'
    )

    js = r"""
const PERSON_ID = __PERSON_ID__;
let _P = null;
let _PACTS = [];

function sv(v){ if(!v) return ''; if(typeof v==='object') return v.value||''; return String(v); }
function fmtDateTime(iso) {
  if (!iso) return '\u2014';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString('en-US', {month:'short', day:'numeric', year:'numeric', hour:'numeric', minute:'2-digit'});
}
function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'T00:00:00');
  return isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-US', {month:'short', day:'numeric'});
}

async function loadPerson() {
  const r = await fetch('/api/people/' + PERSON_ID);
  if (!r.ok) { document.getElementById('pd-name-display').textContent = 'Not found'; return; }
  _P = await r.json();
  renderPerson();
}

function renderPerson() {
  const p = _P;
  const name = p.Name || '(unnamed)';
  // Keep the meeting modal's attendee prefill + linked-company in sync
  _MT_PREFILL = p.Email || '';
  const pc = p['Primary Company'] || [];
  _MT_COMPANY_ID = pc.length ? pc[0].id : 0;
  document.title = name + ' — Reform Hub';
  document.getElementById('pd-name-display').textContent = name;
  document.getElementById('pd-hname').textContent = name;
  document.getElementById('pd-hsub').textContent = (p.Title || 'Person') + ' \u2022 Contact';
  document.getElementById('pd-avatar').textContent = (name.trim()[0] || '?').toUpperCase();
  const stage = sv(p['Lifecycle Stage']);
  document.getElementById('pd-sub').innerHTML =
    (stage ? '<span class="co-pill" style="background:#3b82f622;color:#3b82f6">' + stage + '</span>' : '')
    + (p.Email ? '<span style="font-size:12px;color:var(--text2)">' + esc(p.Email) + '</span>' : '');
  document.getElementById('pd-lifecycle').value = stage || '';

  ['Name','Title','Email','Phone','Notes'].forEach(function(f) {
    const el = document.getElementById('pf-' + f);
    if (el) el.value = p[f] || '';
  });

  document.getElementById('pd-meta-created').textContent = fmtDateTime(p.Created);
  document.getElementById('pd-meta-updated').textContent = fmtDateTime(p.Updated);

  const cowrap = document.getElementById('pd-companies');
  const pc = p['Primary Company'] || [];
  const ls = p['Lead Source Company'] || [];
  const html = [];
  if (pc.length) {
    html.push('<div style="font-size:11px;color:var(--text3);text-transform:uppercase;margin-bottom:4px">Primary</div>');
    pc.forEach(c => {
      html.push('<a class="co-person" href="/companies/' + c.id + '">'
        + '<div class="co-person-name">' + esc(c.value || '') + '</div></a>');
    });
  }
  if (ls.length) {
    html.push('<div style="font-size:11px;color:var(--text3);text-transform:uppercase;margin:10px 0 4px">Lead Source</div>');
    ls.forEach(c => {
      html.push('<a class="co-person" href="/companies/' + c.id + '">'
        + '<div class="co-person-name">' + esc(c.value || '') + '</div></a>');
    });
  }
  cowrap.innerHTML = html.length ? html.join('') : '<div class="co-empty">Not linked to any company yet.</div>';
}

async function savePerson(field, value, el) {
  const marker = (el && el.nextElementSibling && el.nextElementSibling.classList && el.nextElementSibling.classList.contains('co-saving')) ? el.nextElementSibling : document.getElementById('pd-lc-st');
  if (marker) { marker.textContent = 'saving\u2026'; marker.className = 'co-saving'; }
  const patch = {}; patch[field] = value;
  const r = await fetch('/api/people/' + PERSON_ID, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)});
  if (r.ok) {
    if (marker) { marker.textContent = 'saved'; marker.className = 'co-saving ok'; setTimeout(function(){marker.textContent='';},1500); }
    _P = await r.json();
    renderPerson();
    loadActs();
  } else if (marker) { marker.textContent = 'failed'; marker.className = 'co-saving err'; }
}

async function loadActs() {
  const r = await fetch('/api/people/' + PERSON_ID + '/activities');
  if (!r.ok) return;
  _PACTS = await r.json();
  const userActs = _PACTS.filter(a => sv(a.Kind) !== 'edit');
  const editActs = _PACTS.filter(a => sv(a.Kind) === 'edit');
  document.getElementById('pd-tab-ct-activity').textContent = '(' + userActs.length + ')';
  document.getElementById('pd-tab-ct-history').textContent  = '(' + editActs.length + ')';
  const renderRow = (a) => {
    const kind = sv(a.Kind) || 'user_activity';
    const type = sv(a.Type);
    const outcome = sv(a.Outcome);
    const date = a.Date || a.Created;
    const author = a.Author || 'unknown';
    const body = a.Summary || '';
    const fu = a['Follow-Up Date'];
    const isSys = kind === 'edit' || kind === 'creation';
    return '<div class="co-act ' + (isSys ? 'sys' : '') + '">'
      + '<div class="co-act-hd"><span>' + esc(author) + '</span><span>' + esc(fmtDate(date)) + '</span></div>'
      + '<div class="co-act-body">' + esc(body) + '</div>'
      + '<div class="co-act-meta">'
      + (type ? '<span class="co-act-pill" style="background:#3b82f622;color:#3b82f6">' + esc(type) + '</span>' : '')
      + (outcome ? '<span class="co-act-pill" style="background:#05966922;color:#059669">' + esc(outcome) + '</span>' : '')
      + (fu ? '<span>\u23f0 Follow-up ' + esc(fmtDate(fu)) + '</span>' : '')
      + '</div></div>';
  };
  document.getElementById('pd-feed-activity').innerHTML = userActs.length
    ? userActs.map(renderRow).join('')
    : '<div class="co-empty">No activities yet \u2014 log one below.</div>';
  document.getElementById('pd-feed-history').innerHTML = editActs.length
    ? editActs.map(renderRow).join('')
    : '<div class="co-empty">No edit history yet.</div>';
}

function pdSwitchTab(el) {
  document.querySelectorAll('.co-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  const which = el.dataset.tab;
  document.getElementById('pd-tab-activity').style.display = which === 'activity' ? 'block' : 'none';
  document.getElementById('pd-tab-history').style.display  = which === 'history'  ? 'block' : 'none';
}

async function pdLogActivity() {
  const summary = document.getElementById('pd-log-summary').value.trim();
  if (!summary) { alert('Summary is required'); return; }
  const payload = {
    summary,
    type:     document.getElementById('pd-log-type').value,
    outcome:  document.getElementById('pd-log-outcome').value,
    follow_up: document.getElementById('pd-log-follow-up').value,
    kind:     'user_activity',
  };
  // If they have a primary company, link the activity there too
  if (_P && (_P['Primary Company'] || []).length) {
    payload.company_id = _P['Primary Company'][0].id;
  }
  const r = await fetch('/api/people/' + PERSON_ID + '/activities', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  if (!r.ok) { alert('Failed to log'); return; }
  document.getElementById('pd-log-summary').value = '';
  document.getElementById('pd-log-type').value = '';
  document.getElementById('pd-log-outcome').value = '';
  document.getElementById('pd-log-follow-up').value = '';
  loadActs();
}

function pdOpenLogLead() {
  document.getElementById('pd-lg-name').value = '';
  document.getElementById('pd-lg-phone').value = '';
  document.getElementById('pd-lg-email').value = '';
  document.getElementById('pd-lg-source').value = '';
  document.getElementById('pd-lg-reason').value = '';
  document.getElementById('pd-lg-msg').textContent = '';
  document.getElementById('pd-lg-msg').className = 'mt-msg';
  document.getElementById('pd-lg-bg').classList.add('open');
  setTimeout(function(){ document.getElementById('pd-lg-name').focus(); }, 40);
}
function pdCloseLogLead() { document.getElementById('pd-lg-bg').classList.remove('open'); }

async function pdSubmitLogLead() {
  const name  = document.getElementById('pd-lg-name').value.trim();
  const phone = document.getElementById('pd-lg-phone').value.trim();
  const msg = document.getElementById('pd-lg-msg');
  if (!name || !phone) { msg.textContent = 'Name and phone are required.'; msg.className = 'mt-msg err'; return; }
  msg.textContent = 'Saving\u2026'; msg.className = 'mt-msg';
  // Pre-fill Referred By Person; also Company if person has a primary
  const payload = {
    name, phone,
    email:  document.getElementById('pd-lg-email').value.trim(),
    source: (document.getElementById('pd-lg-source').value.trim()
             || ('Referral from ' + (document.getElementById('pd-name-display').textContent || 'person'))),
    reason: document.getElementById('pd-lg-reason').value.trim(),
    referred_by_person_id: PERSON_ID,
  };
  const primaryCoId = (_P && Array.isArray(_P['Primary Company']) && _P['Primary Company'][0])
    ? (_P['Primary Company'][0].id || _P['Primary Company'][0]) : null;
  if (primaryCoId) payload.referred_by_company_id = primaryCoId;

  const r = await fetch('/api/leads/crm', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  const data = await r.json();
  if (!r.ok) { msg.innerHTML = 'Failed: ' + (data.error || r.status); msg.className = 'mt-msg err'; return; }
  msg.innerHTML = 'Lead created. <a href="/leads/' + data.id + '" style="color:#3b82f6">Open \u2192</a>';
  msg.className = 'mt-msg ok';
  setTimeout(function(){
    pdCloseLogLead();
    if (typeof loadActs === 'function') loadActs();
  }, 1200);
}

loadPerson();
loadActs();
""".replace("__PERSON_ID__", str(person_id)) + meeting_modal_js(contact_id=person_id) + task_modal_js(contact_id=person_id) + sms_modal_js(contact_id=person_id)

    return _page('people', 'Person', header, body, js, br, bt, user=user)
