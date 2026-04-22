"""
Company detail page — `/companies/{id}`.

HubSpot-style detail view for a Company row. Inline-editable profile, linked
people on the right, activity timeline + edit-history tabs in the middle.
Writes go through the server endpoints in modal_outreach_hub.py so every
change auto-logs an edit activity for the History tab.
"""
from .shared import _page
from .meetings import meeting_modal_html, meeting_modal_js
from .tasks import task_modal_html, task_modal_js
from .sms import sms_modal_html, sms_modal_js


STATUS_OPTIONS   = ["Not Contacted", "Contacted", "In Discussion", "Active Partner", "Blacklisted"]
CATEGORY_LABELS  = {
    "attorney":  ("Attorney",  "#7c3aed"),
    "guerilla":  ("Guerilla",  "#ea580c"),
    "community": ("Community", "#059669"),
    "other":     ("Other",     "#64748b"),
}
ACTIVITY_TYPES   = ["Call", "Email", "In Person", "Drop Off", "Text", "Other"]
ACTIVITY_OUTCOMES = ["Interested", "Not Interested", "Follow-Up Needed",
                     "Left Voicemail", "No Answer", "Meeting Scheduled",
                     "Partnership Begun"]


_CO_STYLES = """
<style>
.co-wrap{max-width:1180px;margin:0 auto;padding:18px 20px}
.co-back{display:inline-block;margin-bottom:10px;font-size:12px;color:var(--text3);text-decoration:none}
.co-back:hover{color:var(--text)}
.co-header{display:flex;align-items:flex-start;gap:16px;margin-bottom:18px;flex-wrap:wrap}
.co-avatar{width:56px;height:56px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;color:#fff;flex-shrink:0}
.co-htext{flex:1;min-width:0}
.co-htext h1{margin:0;font-size:22px;font-weight:700;line-height:1.2}
.co-sub{margin-top:6px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.co-pill{padding:2px 10px;border-radius:4px;font-size:11px;font-weight:600}
.co-headtool select,.co-headtool input{padding:5px 10px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-size:12px}
.co-grid{display:grid;grid-template-columns:1fr 320px;gap:20px}
@media(max-width:900px){.co-grid{grid-template-columns:1fr}}
.co-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px 20px;margin-bottom:16px}
.co-card h3{margin:0 0 12px;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:var(--text3)}
.co-field{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-bottom:1px solid var(--border);font-size:13px;align-items:center}
.co-field:last-child{border-bottom:0}
.co-flabel{color:var(--text3);flex-shrink:0}
.co-fval{flex:1;text-align:right}
.co-fval input,.co-fval textarea,.co-fval select{width:100%;padding:4px 8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);font-size:12px;font-family:inherit;text-align:left}
.co-fval textarea{resize:vertical;min-height:60px}
.co-saving{font-size:10px;color:var(--text3);margin-left:6px}
.co-saving.ok{color:#059669}
.co-saving.err{color:#ef4444}
.co-tabs{display:flex;gap:4px;border-bottom:1px solid var(--border);margin-bottom:14px}
.co-tab{padding:9px 16px;cursor:pointer;color:var(--text3);font-size:13px;font-weight:600;border-bottom:2px solid transparent}
.co-tab:hover{color:var(--text)}
.co-tab.active{color:var(--text);border-bottom-color:#3b82f6}
.co-tab-ct{font-size:10px;margin-left:4px;color:var(--text3)}
.co-feed{display:flex;flex-direction:column;gap:10px}
.co-act{padding:12px 14px;border:1px solid var(--border);border-radius:8px;background:var(--card)}
.co-act.sys{background:transparent;border-style:dashed;color:var(--text2);font-size:12px}
.co-act-hd{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;font-size:11px;color:var(--text3)}
.co-act-body{font-size:13px;white-space:pre-wrap;line-height:1.5}
.co-act-meta{font-size:11px;color:var(--text3);margin-top:6px;display:flex;gap:10px;flex-wrap:wrap}
.co-act-pill{padding:1px 6px;border-radius:4px;font-size:10px;font-weight:600}
.co-log-form{padding:14px;border:1px solid var(--border);border-radius:8px;background:var(--bg2);margin-bottom:14px}
.co-log-row{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
@media(max-width:500px){.co-log-row{grid-template-columns:1fr}}
.co-log-form select,.co-log-form input,.co-log-form textarea{width:100%;padding:7px 10px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-size:12px;font-family:inherit;box-sizing:border-box}
.co-log-form textarea{resize:vertical;min-height:60px}
.co-log-form button{padding:7px 14px;background:#3b82f6;color:#fff;border:none;border-radius:6px;font-size:13px;font-weight:600;cursor:pointer}
.co-log-form button:hover{background:#2563eb}
.co-empty{padding:30px;text-align:center;color:var(--text3);font-size:13px}
.co-person{padding:10px 12px;border:1px solid var(--border);border-radius:6px;margin-bottom:8px;display:block;text-decoration:none;color:var(--text)}
.co-person:hover{border-color:var(--text3)}
.co-person-name{font-size:13px;font-weight:600}
.co-person-meta{font-size:11px;color:var(--text3);margin-top:2px}
</style>
"""


def _company_detail_page(company_id: int, br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header" id="co-header"><div class="header-left">'
        f'<h1 id="co-hname">Loading…</h1>'
        '<div class="sub" id="co-hsub">&nbsp;</div>'
        '</div></div>'
    )

    status_opts = "".join(f'<option value="{s}">{s}</option>' for s in STATUS_OPTIONS)
    type_opts = '<option value="">Type</option>' + "".join(f'<option value="{t}">{t}</option>' for t in ACTIVITY_TYPES)
    outcome_opts = '<option value="">Outcome</option>' + "".join(f'<option value="{o}">{o}</option>' for o in ACTIVITY_OUTCOMES)

    body = (
        _CO_STYLES
        + '<div class="co-wrap">'
        + '<a href="/contacts" class="co-back">\u2190 All Companies</a>'
        + '<div class="co-header">'
        + '<div class="co-avatar" id="co-avatar">?</div>'
        + '<div class="co-htext">'
        + '<h1 id="co-name-display">Loading\u2026</h1>'
        + '<div class="co-sub" id="co-sub">&nbsp;</div>'
        + '</div>'
        + '<div class="co-headtool" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
        + f'<select id="co-status" onchange="saveField(\'Contact Status\', this.value, this)"><option value="">Status\u2026</option>{status_opts}</select>'
        + '<span class="co-saving" id="co-status-st"></span>'
        + '<button class="mt-btn primary" onclick="openMeetingModal()">\U0001f4c5 Schedule meeting</button>'
        + '<button class="mt-btn" onclick="openLogLead()">\U0001f4e5 Log lead</button>'
        + '<button class="mt-btn" onclick="atkOpen()">\U00002795 Add task</button>'
        + '<button class="mt-btn" onclick="smsOpen(_CO && _CO.Phone)">\U0001f4ac Send SMS</button>'
        + '</div>'
        + '</div>'
        + '<div class="co-grid">'
        + '<div>'
        # About
        + '<div class="co-card">'
        + '<h3>About</h3>'
        + '<div class="co-field"><span class="co-flabel">Name</span><span class="co-fval"><input id="f-Name" onblur="saveField(\'Name\', this.value, this)"></span></div>'
        + '<div class="co-field"><span class="co-flabel">Phone</span><span class="co-fval"><input id="f-Phone" onblur="saveField(\'Phone\', this.value, this)"></span></div>'
        + '<div class="co-field"><span class="co-flabel">Email</span><span class="co-fval"><input id="f-Email" type="email" onblur="saveField(\'Email\', this.value, this)"></span></div>'
        + '<div class="co-field"><span class="co-flabel">Website</span><span class="co-fval"><input id="f-Website" onblur="saveField(\'Website\', this.value, this)"></span></div>'
        + '<div class="co-field"><span class="co-flabel">Address</span><span class="co-fval"><input id="f-Address" onblur="saveField(\'Address\', this.value, this)"></span></div>'
        + '<div class="co-field"><span class="co-flabel">Notes</span><span class="co-fval"><textarea id="f-Notes" onblur="saveField(\'Notes\', this.value, this)"></textarea></span></div>'
        + '</div>'
        # Activity / History tabs
        + '<div class="co-card" style="padding:14px 18px">'
        + '<div class="co-tabs">'
        + '<div class="co-tab active" data-tab="activity" onclick="switchTab(this)">Activity <span class="co-tab-ct" id="tab-ct-activity"></span></div>'
        + '<div class="co-tab" data-tab="history" onclick="switchTab(this)">History <span class="co-tab-ct" id="tab-ct-history"></span></div>'
        + '</div>'
        + '<div id="tab-activity">'
        # Log form
        + '<div class="co-log-form">'
        + '<div class="co-log-row">'
        + f'<select id="log-type">{type_opts}</select>'
        + f'<select id="log-outcome">{outcome_opts}</select>'
        + '</div>'
        + '<textarea id="log-summary" placeholder="What happened? (required)"></textarea>'
        + '<div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;gap:10px;flex-wrap:wrap">'
        + '<input type="date" id="log-follow-up" style="padding:6px 10px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-size:12px" title="Follow-up date">'
        + '<button onclick="logActivity()">+ Log activity</button>'
        + '</div>'
        + '</div>'
        + '<div class="co-feed" id="feed-activity"><div class="co-empty">Loading\u2026</div></div>'
        + '</div>'
        + '<div id="tab-history" style="display:none">'
        + '<div class="co-feed" id="feed-history"><div class="co-empty">Loading\u2026</div></div>'
        + '</div>'
        + '</div>'
        + '</div>'
        # Right column
        + '<div>'
        + '<div class="co-card"><h3>People</h3><div id="people-list"><div class="co-empty">Loading\u2026</div></div></div>'
        + '<div class="co-card">'
        + '<h3>Details</h3>'
        + '<div class="co-field"><span class="co-flabel">Category</span><span class="co-fval" id="meta-category">\u2014</span></div>'
        + '<div class="co-field"><span class="co-flabel">Type</span><span class="co-fval" id="meta-type">\u2014</span></div>'
        + '<div class="co-field"><span class="co-flabel">Outreach Goal</span><span class="co-fval" id="meta-goal">\u2014</span></div>'
        + '<div class="co-field"><span class="co-flabel">Created</span><span class="co-fval" id="meta-created">\u2014</span></div>'
        + '<div class="co-field"><span class="co-flabel">Updated</span><span class="co-fval" id="meta-updated">\u2014</span></div>'
        + '</div>'
        # Attorney portal card - only visible when Category=attorney
        + '<div class="co-card" id="portal-card" style="display:none">'
        + '<h3>\U0001f517 Attorney Portal</h3>'
        + '<p style="font-size:11px;color:var(--text3);margin:0 0 10px;line-height:1.5">'
        +   'Public read-only page for this firm to check their patients case status. No login required.'
        + '</p>'
        + '<div class="co-field"><span class="co-flabel">Enabled</span>'
        +   '<span class="co-fval" style="display:flex;align-items:center;gap:8px">'
        +     '<label style="display:flex;align-items:center;gap:6px;cursor:pointer">'
        +       '<input type="checkbox" id="portal-toggle" onchange="togglePortal()">'
        +       '<span id="portal-toggle-label" style="font-size:12px;color:var(--text3)">Off</span>'
        +     '</label>'
        +   '</span></div>'
        + '<div class="co-field" id="portal-url-row" style="display:none">'
        +   '<span class="co-flabel">Public URL</span>'
        +   '<span class="co-fval" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">'
        +     '<a id="portal-url-link" href="#" target="_blank" rel="noopener" style="font-size:12px;color:var(--brand);word-break:break-all">—</a>'
        +     '<button onclick="copyPortalUrl()" style="background:none;border:1px solid var(--border);color:var(--text3);font-size:10px;padding:2px 8px;border-radius:4px;cursor:pointer">Copy</button>'
        +   '</span></div>'
        + '<div class="co-field" id="portal-stats-row" style="display:none">'
        +   '<span class="co-flabel">Views</span>'
        +   '<span class="co-fval" id="portal-views" style="font-size:12px;color:var(--text3)">0</span>'
        + '</div>'
        + '<div id="portal-actions-row" style="margin-top:10px;display:none">'
        +   '<button onclick="regenerateSlug()" style="background:none;border:1px solid var(--border);color:var(--text3);font-size:11px;padding:4px 10px;border-radius:6px;cursor:pointer">Regenerate URL</button>'
        +   '<span id="portal-msg" style="font-size:11px;color:var(--text3);margin-left:10px"></span>'
        + '</div>'
        + '</div>'
        + '</div>'
        + '</div>'
        + '</div>'
        + meeting_modal_html()
        + task_modal_html()
        + sms_modal_html()
        # Lead-capture modal (opens on "+ Log lead" click, pre-fills Referred By Company)
        + '<div class="mt-modal-bg" id="lg-modal-bg" onclick="if(event.target===this)closeLogLead()">'
        + '<div class="mt-modal">'
        + '<h3>\U0001f4e5 Log lead from this company</h3>'
        + '<label>Name *</label>'
        + '<input type="text" id="lg-name" placeholder="Jane Doe">'
        + '<div class="mt-modal-row">'
        + '<div><label>Phone *</label><input type="text" id="lg-phone" placeholder="(555) 555-1234"></div>'
        + '<div><label>Email</label><input type="email" id="lg-email" placeholder="jane@example.com"></div>'
        + '</div>'
        + '<label>Source note (how did this company refer them?)</label>'
        + '<input type="text" id="lg-source" placeholder="Direct referral, walk-in, online form\u2026">'
        + '<label>Reason / notes</label>'
        + '<textarea id="lg-reason" placeholder="Injury context, what the lead is looking for\u2026"></textarea>'
        + '<div class="mt-msg" id="lg-msg"></div>'
        + '<div class="mt-modal-actions">'
        + '<button type="button" onclick="closeLogLead()">Cancel</button>'
        + '<button type="button" class="mt-primary" onclick="submitLogLead()">Create lead</button>'
        + '</div>'
        + '</div></div>'
    )

    js = r"""
const COMPANY_ID = __COMPANY_ID__;
let _CO = null;
let _ACTS = [];
let _PEOPLE = [];

function sv(v) {
  if (!v) return '';
  if (typeof v === 'object') return v.value || '';
  return String(v);
}
function fmtDateTime(iso) {
  if (!iso) return '\u2014';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString('en-US', {month:'short', day:'numeric', year:'numeric', hour:'numeric', minute:'2-digit'});
}
function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'T00:00:00');
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', {month:'short', day:'numeric'});
}

const CAT_META = {
  attorney:  ['Attorney',  '#7c3aed'],
  guerilla:  ['Guerilla',  '#ea580c'],
  community: ['Community', '#059669'],
  other:     ['Other',     '#64748b'],
};

async function loadCompany() {
  const r = await fetch('/api/companies/' + COMPANY_ID);
  if (!r.ok) {
    document.getElementById('co-name-display').textContent = 'Not found';
    return;
  }
  _CO = await r.json();
  renderCompany();
}

function renderCompany() {
  const c = _CO;
  const name = c.Name || '(unnamed)';
  const cat  = sv(c.Category) || 'other';
  const [catLabel, catColor] = CAT_META[cat] || CAT_META.other;

  document.title = name + ' — Reform Hub';
  document.getElementById('co-name-display').textContent = name;
  document.getElementById('co-hname').textContent = name;
  document.getElementById('co-hsub').textContent = catLabel + ' \u2022 Company';

  const avatar = document.getElementById('co-avatar');
  avatar.textContent = (name.trim()[0] || '?').toUpperCase();
  avatar.style.background = catColor;

  const sub = document.getElementById('co-sub');
  sub.innerHTML = `<span class="co-pill" style="background:${catColor}22;color:${catColor}">${catLabel}</span>`
    + (sv(c['Contact Status']) ? `<span class="co-pill" style="background:var(--bg2);color:var(--text2)">${sv(c['Contact Status'])}</span>` : '');

  document.getElementById('co-status').value = sv(c['Contact Status']) || '';

  // Populate fields
  ['Name','Phone','Email','Website','Address','Notes'].forEach(function(f) {
    const el = document.getElementById('f-' + f);
    if (el) el.value = c[f] || '';
  });

  // Meta
  document.getElementById('meta-category').textContent = catLabel;
  document.getElementById('meta-type').textContent     = sv(c.Type) || '\u2014';
  document.getElementById('meta-goal').textContent     = sv(c['Outreach Goal']) || '\u2014';
  document.getElementById('meta-created').textContent  = fmtDateTime(c.Created);
  document.getElementById('meta-updated').textContent  = fmtDateTime(c.Updated);

  // Attorney Portal card - only visible for attorney-category companies
  const portalCard = document.getElementById('portal-card');
  if (portalCard) {
    if (cat === 'attorney') {
      portalCard.style.display = '';
      const enabled = !!c['Portal Enabled'];
      const slug = (c['Portal Slug'] || '').trim();
      document.getElementById('portal-toggle').checked = enabled;
      document.getElementById('portal-toggle-label').textContent = enabled ? 'On' : 'Off';
      const urlRow    = document.getElementById('portal-url-row');
      const statsRow  = document.getElementById('portal-stats-row');
      const actionRow = document.getElementById('portal-actions-row');
      if (enabled && slug) {
        const url = window.location.origin + '/a/' + slug;
        const link = document.getElementById('portal-url-link');
        link.textContent = url;
        link.href = url;
        urlRow.style.display = '';
        statsRow.style.display = '';
        actionRow.style.display = '';
        const views = c['Portal View Count'] || 0;
        const lastViewed = c['Portal Last Viewed'];
        document.getElementById('portal-views').textContent =
          views + (lastViewed ? ' · last ' + fmtDateTime(lastViewed) : ' · never viewed');
      } else {
        urlRow.style.display = 'none';
        statsRow.style.display = 'none';
        actionRow.style.display = 'none';
      }
    } else {
      portalCard.style.display = 'none';
    }
  }
}

async function togglePortal() {
  const toggle = document.getElementById('portal-toggle');
  const label  = document.getElementById('portal-toggle-label');
  const msg    = document.getElementById('portal-msg');
  const enabling = toggle.checked;
  label.textContent = enabling ? 'On' : 'Off';
  toggle.disabled = true;
  if (msg) msg.textContent = 'saving…';

  // If enabling for the first time and no slug exists, regenerate one first
  if (enabling && !((_CO && _CO['Portal Slug']) || '').trim()) {
    try {
      const rg = await fetch('/api/companies/' + COMPANY_ID + '/portal/regenerate', { method: 'POST' });
      if (!rg.ok) throw new Error('regen failed');
    } catch (e) {
      toggle.checked = false;
      label.textContent = 'Off';
      toggle.disabled = false;
      if (msg) { msg.textContent = 'slug generation failed'; setTimeout(function(){ msg.textContent=''; }, 2500); }
      return;
    }
  }
  const r = await fetch('/api/companies/' + COMPANY_ID, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ 'Portal Enabled': enabling }),
  });
  toggle.disabled = false;
  if (r.ok) {
    _CO = await r.json();
    renderCompany();
    if (msg) { msg.textContent = 'saved'; setTimeout(function(){ msg.textContent=''; }, 1500); }
  } else {
    toggle.checked = !enabling;
    label.textContent = enabling ? 'Off' : 'On';
    if (msg) { msg.textContent = 'save failed'; setTimeout(function(){ msg.textContent=''; }, 2500); }
  }
}

function copyPortalUrl() {
  const link = document.getElementById('portal-url-link');
  if (!link) return;
  navigator.clipboard.writeText(link.href).then(function() {
    const msg = document.getElementById('portal-msg');
    if (msg) { msg.textContent = 'copied!'; setTimeout(function(){ msg.textContent=''; }, 1500); }
  });
}

async function regenerateSlug() {
  if (!confirm('Regenerate the portal URL? The old URL will immediately stop working.')) return;
  const msg = document.getElementById('portal-msg');
  if (msg) msg.textContent = 'regenerating…';
  const r = await fetch('/api/companies/' + COMPANY_ID + '/portal/regenerate', { method: 'POST' });
  if (r.ok) {
    await loadCompany();  // re-fetch _CO with new slug
    if (msg) { msg.textContent = 'new URL ready'; setTimeout(function(){ msg.textContent=''; }, 2000); }
  } else {
    if (msg) { msg.textContent = 'failed'; setTimeout(function(){ msg.textContent=''; }, 2500); }
  }
}

async function saveField(field, value, el) {
  const status = document.getElementById('co-status-st');
  const patch = {}; patch[field] = value;
  const marker = el && el.nextElementSibling && el.nextElementSibling.classList && el.nextElementSibling.classList.contains('co-saving') ? el.nextElementSibling : status;
  if (marker) { marker.textContent = 'saving\u2026'; marker.className = 'co-saving'; }
  const r = await fetch('/api/companies/' + COMPANY_ID, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(patch),
  });
  if (r.ok) {
    if (marker) { marker.textContent = 'saved'; marker.className = 'co-saving ok'; setTimeout(function(){ marker.textContent = ''; }, 1500); }
    _CO = await r.json();
    renderCompany();
    loadActivities();  // refresh to pick up system edit log
  } else {
    if (marker) { marker.textContent = 'failed'; marker.className = 'co-saving err'; }
  }
}

async function loadActivities() {
  const r = await fetch('/api/companies/' + COMPANY_ID + '/activities');
  if (!r.ok) return;
  _ACTS = await r.json();
  renderActivities();
}

function renderActivities() {
  const userActs = _ACTS.filter(a => sv(a.Kind) !== 'edit');
  const editActs = _ACTS.filter(a => sv(a.Kind) === 'edit');
  document.getElementById('tab-ct-activity').textContent = '(' + userActs.length + ')';
  document.getElementById('tab-ct-history').textContent  = '(' + editActs.length + ')';

  const renderRow = (a) => {
    const kind = sv(a.Kind) || 'user_activity';
    const type = sv(a.Type);
    const outcome = sv(a.Outcome);
    const date = a.Date || a.Created;
    const author = a.Author || 'unknown';
    const body = a.Summary || '';
    const followUp = a['Follow-Up Date'];
    const isSys = kind === 'edit' || kind === 'creation';
    return `<div class="co-act ${isSys ? 'sys' : ''}">`
      + `<div class="co-act-hd"><span>${esc(author)}</span><span>${esc(fmtDate(date))}</span></div>`
      + `<div class="co-act-body">${esc(body)}</div>`
      + `<div class="co-act-meta">`
      + (type ? `<span class="co-act-pill" style="background:#3b82f622;color:#3b82f6">${esc(type)}</span>` : '')
      + (outcome ? `<span class="co-act-pill" style="background:#05966922;color:#059669">${esc(outcome)}</span>` : '')
      + (followUp ? `<span>\u23f0 Follow-up ${esc(fmtDate(followUp))}</span>` : '')
      + `</div>`
      + `</div>`;
  };

  document.getElementById('feed-activity').innerHTML = userActs.length
    ? userActs.map(renderRow).join('')
    : '<div class="co-empty">No activities yet \u2014 log one below.</div>';
  document.getElementById('feed-history').innerHTML = editActs.length
    ? editActs.map(renderRow).join('')
    : '<div class="co-empty">No edit history yet.</div>';
}

function switchTab(el) {
  document.querySelectorAll('.co-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  const which = el.dataset.tab;
  document.getElementById('tab-activity').style.display = which === 'activity' ? 'block' : 'none';
  document.getElementById('tab-history').style.display  = which === 'history'  ? 'block' : 'none';
}

async function logActivity() {
  const summary = document.getElementById('log-summary').value.trim();
  if (!summary) { alert('Summary is required'); return; }
  const payload = {
    summary,
    type:     document.getElementById('log-type').value,
    outcome:  document.getElementById('log-outcome').value,
    follow_up: document.getElementById('log-follow-up').value,
    kind:     'user_activity',
  };
  const r = await fetch('/api/companies/' + COMPANY_ID + '/activities', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  });
  if (!r.ok) { alert('Failed to log activity'); return; }
  document.getElementById('log-summary').value = '';
  document.getElementById('log-type').value = '';
  document.getElementById('log-outcome').value = '';
  document.getElementById('log-follow-up').value = '';
  loadActivities();
}

async function loadPeople() {
  const r = await fetch('/api/companies/' + COMPANY_ID + '/people');
  if (!r.ok) return;
  _PEOPLE = await r.json();
  const wrap = document.getElementById('people-list');
  if (!_PEOPLE.length) {
    wrap.innerHTML = '<div class="co-empty">No people linked yet. <a href="/people/new?company_id=' + COMPANY_ID + '" style="color:#3b82f6;text-decoration:none">+ Add one</a></div>';
    return;
  }
  wrap.innerHTML = _PEOPLE.map(p => {
    const title = p.Title || '';
    const email = p.Email || '';
    return `<a class="co-person" href="/people/${p.id}">`
      + `<div class="co-person-name">${esc(p.Name || '(unnamed)')}</div>`
      + `<div class="co-person-meta">${esc(title)}${title && email ? ' \u2022 ' : ''}${esc(email)}</div>`
      + `</a>`;
  }).join('');
}

function openLogLead() {
  document.getElementById('lg-name').value = '';
  document.getElementById('lg-phone').value = '';
  document.getElementById('lg-email').value = '';
  document.getElementById('lg-source').value = '';
  document.getElementById('lg-reason').value = '';
  document.getElementById('lg-msg').textContent = '';
  document.getElementById('lg-msg').className = 'mt-msg';
  document.getElementById('lg-modal-bg').classList.add('open');
  setTimeout(function(){ document.getElementById('lg-name').focus(); }, 40);
}
function closeLogLead() { document.getElementById('lg-modal-bg').classList.remove('open'); }

async function submitLogLead() {
  const name  = document.getElementById('lg-name').value.trim();
  const phone = document.getElementById('lg-phone').value.trim();
  const msg = document.getElementById('lg-msg');
  if (!name || !phone) { msg.textContent = 'Name and phone are required.'; msg.className = 'mt-msg err'; return; }
  msg.textContent = 'Saving\u2026'; msg.className = 'mt-msg';
  const payload = {
    name, phone,
    email:  document.getElementById('lg-email').value.trim(),
    source: (document.getElementById('lg-source').value.trim()
             || ('Referral from ' + (document.getElementById('co-name-display').textContent || 'company'))),
    reason: document.getElementById('lg-reason').value.trim(),
    referred_by_company_id: COMPANY_ID,
  };
  const r = await fetch('/api/leads/crm', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  const data = await r.json();
  if (!r.ok) { msg.innerHTML = 'Failed: ' + (data.error || r.status); msg.className = 'mt-msg err'; return; }
  msg.innerHTML = 'Lead created. <a href="/leads/' + data.id + '" style="color:#3b82f6">Open \u2192</a>';
  msg.className = 'mt-msg ok';
  setTimeout(function(){
    closeLogLead();
    if (typeof loadActivities === 'function') loadActivities();
  }, 1200);
}

loadCompany();
loadActivities();
loadPeople();
""".replace("__COMPANY_ID__", str(company_id)) + meeting_modal_js(company_id=company_id) + task_modal_js(company_id=company_id) + sms_modal_js(company_id=company_id)

    return _page('contacts', 'Company', header, body, js, br, bt, user=user)
