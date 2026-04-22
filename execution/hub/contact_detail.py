"""
Contact-detail — shared CRUD actions for the "click a business, edit it" flow.

Used by:
  - `/attorney/directory`, `/guerilla/directory`, `/community/directory`
  - `/guerilla/routes`  (admin dashboard, click a stop's venue name)
  - `/m/route`          (field rep bottom sheet — Notes, Activity, Follow-Up edits)

Each action is namespaced under a single `Contact` global so it doesn't
collide with existing per-page bpatch/bpost/etc. definitions.

The desktop overlay modal (HTML + render) is not in this file yet — Step 3
of the refactor will extract it from outreach.py once Step 2 confirms the
CRUD actions work end-to-end via the directory page.
"""
from .constants import T_COMPANIES, T_ACTIVITIES


# JS block — inject into any page that needs the Contact.* actions.
# Format placeholders are filled in by contact_actions_js() below.
#
# Phase 2b.2 (2026-04-21): all three tools now read/write T_COMPANIES (unified)
# and the single T_ACTIVITIES table. The per-tool `cfg` only differs in display
# labels + status options. All field names are unified: Name/Phone/Address.
_CONTACT_ACTIONS_JS = r"""
/* ── Contact detail — shared CRUD actions ──────────────────────────── */
const _COMPANIES_TID = {companies};
const _ACTIVITIES_TID = {activities};
const _CONTACT_TOOL_CFG = {{
  attorney: {{
    venuesTid: {companies}, actsTid: {activities},
    actsLinkField: 'Company',
    nameField: 'Name', phoneField: 'Phone', addrField: 'Address',
    activeStatus: 'Active Partner',
    stages: ['Not Contacted', 'Contacted', 'In Discussion', 'Active Partner'],
  }},
  gorilla: {{
    venuesTid: {companies}, actsTid: {activities},
    actsLinkField: 'Company',
    nameField: 'Name', phoneField: 'Phone', addrField: 'Address',
    activeStatus: 'Active Partner',
    stages: ['Not Contacted', 'Contacted', 'In Discussion', 'Active Partner'],
  }},
  community: {{
    venuesTid: {companies}, actsTid: {activities},
    actsLinkField: 'Company',
    nameField: 'Name', phoneField: 'Phone', addrField: 'Address',
    activeStatus: 'Active Partner',
    stages: ['Not Contacted', 'Contacted', 'In Discussion', 'Active Partner'],
  }},
}};

window.Contact = {{
  cfg: _CONTACT_TOOL_CFG,

  /* Return YYYY-MM-DD for today (local). */
  today: function() {{
    return new Date().toISOString().split('T')[0];
  }},

  /* Append a new "[YYYY-MM-DD] text" entry to existing notes, joined by \n---\n.
     Returns the new notes string — caller writes it back via saveNotes(). */
  formatNewNote: function(existing, text, date) {{
    var d = date || Contact.today();
    var entry = '[' + d + '] ' + text;
    var prior = (existing || '').trim();
    return prior ? entry + '\n---\n' + prior : entry;
  }},

  /* Raw Baserow calls. Return the fetch Response so callers can check .ok
     and parse JSON as needed. */
  bpatch: async function(tid, id, data) {{
    return fetch(BR + '/api/database/rows/table/' + tid + '/' + id + '/?user_field_names=true', {{
      method: 'PATCH',
      headers: {{'Authorization': 'Token ' + BT, 'Content-Type': 'application/json'}},
      body: JSON.stringify(data),
    }});
  }},
  bpost: async function(tid, data) {{
    return fetch(BR + '/api/database/rows/table/' + tid + '/?user_field_names=true', {{
      method: 'POST',
      headers: {{'Authorization': 'Token ' + BT, 'Content-Type': 'application/json'}},
      body: JSON.stringify(data),
    }});
  }},

  /* Fetch a single venue row by id. Tags the returned row with _tool/_tid/_actsTid/_link
     so downstream renderers can dispatch tool-specific behavior. */
  fetchVenue: async function(tool, venueId) {{
    var cfg = _CONTACT_TOOL_CFG[tool];
    if (!cfg) throw new Error('Unknown tool: ' + tool);
    var r = await fetch(BR + '/api/database/rows/table/' + cfg.venuesTid + '/' + venueId + '/?user_field_names=true', {{
      headers: {{'Authorization': 'Token ' + BT}},
    }});
    if (!r.ok) throw new Error('fetchVenue ' + r.status);
    var v = await r.json();
    v._tool = tool;
    v._tid = cfg.venuesTid;
    v._actsTid = cfg.actsTid;
    v._link = cfg.actsLinkField;
    v._nameField = cfg.nameField;
    return v;
  }},

  /* CRUD actions. Each returns {{ok: bool, ...}} so callers can branch
     on success and update their own local state / UI. */

  saveStatus: async function(tool, venueId, newStatus) {{
    var cfg = _CONTACT_TOOL_CFG[tool];
    var r = await Contact.bpatch(cfg.venuesTid, venueId, {{'Contact Status': newStatus}});
    return {{ok: r.ok}};
  }},

  saveFollowUp: async function(tool, venueId, date) {{
    var cfg = _CONTACT_TOOL_CFG[tool];
    var r = await Contact.bpatch(cfg.venuesTid, venueId, {{'Follow-Up Date': date || null}});
    return {{ok: r.ok}};
  }},

  saveNotes: async function(tool, venueId, newNotes) {{
    var cfg = _CONTACT_TOOL_CFG[tool];
    var r = await Contact.bpatch(cfg.venuesTid, venueId, {{'Notes': newNotes}});
    return {{ok: r.ok}};
  }},

  /* Convenience: format + save a new note in one call.
     Returns {{ok, newNotes}} on success so the caller can update its display. */
  addNote: async function(tool, venueId, existingNotes, text) {{
    var merged = Contact.formatNewNote(existingNotes, text);
    var r = await Contact.saveNotes(tool, venueId, merged);
    return {{ok: r.ok, newNotes: merged}};
  }},

  /* Log a new activity row.
     fields: {{date?, type?, outcome?, person?, summary?, followUp?}}.
     Unspecified fields default sensibly (date = today, empty strings/null).
     `venueId` is a Company row id (unified schema post-Phase-2b.2). */
  logActivity: async function(tool, venueId, fields) {{
    var payload = {{}};
    payload['Company']         = [venueId];
    payload['Date']            = fields.date || Contact.today();
    payload['Type']            = fields.type || null;
    payload['Outcome']         = fields.outcome || null;
    payload['Contact Person']  = fields.person || '';
    payload['Summary']         = fields.summary || '';
    payload['Follow-Up Date']  = fields.followUp || null;
    payload['Created']         = new Date().toISOString();
    var r = await Contact.bpost(_ACTIVITIES_TID, payload);
    if (!r.ok) return {{ok: false}};
    var row = await r.json();
    return {{ok: true, row: row}};
  }},

  /* Fetch all activities for a given Company id.
     Uses Baserow's filter params to pull just this Company's rows. */
  fetchActivities: async function(companyId) {{
    var url = BR + '/api/database/rows/table/' + _ACTIVITIES_TID
      + '/?user_field_names=true&size=200&order_by=-Date,-id'
      + '&filter__field_Company__link_row_has=' + encodeURIComponent(companyId);
    // link_row_has uses field id not name, so fall back to client-side filter
    url = BR + '/api/database/rows/table/' + _ACTIVITIES_TID
      + '/?user_field_names=true&size=200&order_by=-Date,-id';
    var r = await fetch(url, {{headers: {{'Authorization': 'Token ' + BT}}}});
    if (!r.ok) return [];
    var data = await r.json();
    return (data.results || []).filter(function(a) {{
      var links = a.Company || [];
      return links.some(function(l) {{
        return (l && (l.id === companyId || l.id === +companyId));
      }});
    }});
  }},
}};
"""


def contact_actions_js() -> str:
    """Return the Contact.* CRUD actions JS block, ready to inject into a page.
    All tools now share the unified T_COMPANIES and T_ACTIVITIES tables."""
    return _CONTACT_ACTIONS_JS.format(
        companies=T_COMPANIES, activities=T_ACTIVITIES,
    )


# ── Desktop modal markup ─────────────────────────────────────────────────────
# Two-panel overlay (detail + email templates). The email button is wired to
# the page's tool key via {tool_key} substitution; the rest is tool-agnostic.
_CONTACT_DETAIL_HTML_TEMPLATE = (
    '<div class="cd-overlay" id="cd-overlay" onclick="if(event.target===this)closeContactDetail()">'
    '<div class="cd-modal">'
    '<div class="cd-header">'
    '<div style="flex:1;min-width:0"><div class="cd-title" id="cd-title"></div>'
    '<div id="cd-subtitle" style="margin-top:4px"></div></div>'
    '<div class="cd-header-actions">'
    '<a class="cd-btn-email" id="cd-btn-open" href="#" onclick="return openFullProfile()" title="Open full company profile">\u2197 Open full profile</a>'
    '<button class="cd-btn-email" onclick="showEmailTemplates(_cdVenue,\'{tool_key}\')" title="Email templates">\u2709 Email</button>'
    '<button class="cd-btn-close" onclick="closeContactDetail()">&times;</button>'
    '</div></div>'
    '<div class="cd-body">'
    '<div class="cd-panel active" id="cd-panel-detail"><div id="cd-detail-body"></div></div>'
    '<div class="cd-panel" id="cd-panel-tpl"><div id="cd-tpl-body"></div></div>'
    '</div></div></div>'
)


def contact_detail_html(tool_key: str) -> str:
    """Return the desktop contact-detail modal markup, wired for `tool_key`."""
    return _CONTACT_DETAIL_HTML_TEMPLATE.format(tool_key=tool_key)


# ── Desktop modal render + handler JS ─────────────────────────────────────────
# Plain triple-quoted string: not an f-string, not a format template, so JS
# object literals need no brace doubling. Page-level requirement: declare a
# `_TOOL_KEY` global (and optionally `window._onContactUpdate = function(v)` to
# sync the caller's own in-memory state after an edit). All other per-tool
# config (tables, field names, stages, active status) is looked up via
# `Contact.cfg[_TOOL_KEY]` — so pages don't need to redeclare a bunch of
# per-tool consts when they reuse the modal.
_CONTACT_DETAIL_JS = r"""
/* ── Contact detail — modal render + edit handlers ─────────────────── */
let _cdVenue = null;

function _cdCfg() { return Contact.cfg[_TOOL_KEY] || {}; }

function stageOpts(cur) {
  return (_cdCfg().stages || []).map(function(s) {
    return '<option value="' + s + '"' + (cur === s ? ' selected' : '') + '>' + s + '</option>';
  }).join('');
}

function statusBadge(status) {
  var map = {'Not Contacted':'sb-not','Contacted':'sb-cont','In Discussion':'sb-disc'};
  var cls = status === _cdCfg().activeStatus ? 'sb-act' : (map[status] || 'sb-not');
  return '<span class="status-badge ' + cls + '">' + esc(status || 'Unknown') + '</span>';
}

function renderNotes(text) {
  if (!text || !text.trim()) return '<div style="color:var(--text3);font-size:12px;padding:4px 0">No notes yet</div>';
  return text.split('\n---\n').filter(function(e) { return e.trim(); }).map(function(entry) {
    var m = entry.match(/^\[(\d{4}-\d{2}-\d{2})\] ([\s\S]*)$/);
    if (m) return '<div style="padding:5px 0;border-bottom:1px solid var(--border)">'
      + '<div style="font-size:10px;color:var(--text3);margin-bottom:2px">' + m[1] + '</div>'
      + '<div style="font-size:12px">' + esc(m[2].trim()) + '</div></div>';
    return '<div style="padding:5px 0;border-bottom:1px solid var(--border);font-size:12px">' + esc(entry.trim()) + '</div>';
  }).join('');
}

function renderAct(a) {
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
}

function _buildDetailHTML(v) {
  var id  = v.id;
  var cfg = _cdCfg();
  var status   = sv(v['Contact Status']);
  var phone    = esc(v[cfg.phoneField] || '');
  var addr     = esc(v[cfg.addrField]  || '');
  var website  = v['Website'] || '';
  var fu       = v['Follow-Up Date'] || '';
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
}

function openContactDetail(v) {
  _cdVenue = v;
  var id = v.id;
  var cfg = _cdCfg();
  document.getElementById('cd-title').textContent = v[cfg.nameField] || '(unnamed)';
  document.getElementById('cd-subtitle').innerHTML = statusBadge(sv(v['Contact Status']));
  document.getElementById('cd-detail-body').innerHTML = _buildDetailHTML(v);
  document.getElementById('cd-panel-detail').className = 'cd-panel active';
  document.getElementById('cd-panel-tpl').className    = 'cd-panel';
  document.getElementById('cd-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  fetchAll(cfg.actsTid).then(function(acts) {
    var mine = acts.filter(function(a) {
      var lf = a[cfg.actsLinkField];
      return Array.isArray(lf) ? lf.some(function(r) { return r.id === id; }) : false;
    }).sort(function(a, b) { return (b['Date']||'').localeCompare(a['Date']||''); });
    var el = document.getElementById('cd-acts-'+id);
    if (el) el.innerHTML = mine.length ? mine.map(renderAct).join('')
      : '<div style="color:var(--text3);padding:4px 0">No activities yet</div>';
  });
}

function closeContactDetail() {
  document.getElementById('cd-overlay').classList.remove('open');
  document.body.style.overflow = '';
  _cdVenue = null;
}

function openFullProfile() {
  // Modal is lightweight — navigate to the full /companies/{id} page for
  // inline editing, Activity + History tabs, linked People, Log Lead, and
  // Schedule Meeting. _cdVenue is a T_COMPANIES row, so .id maps directly.
  if (_cdVenue && _cdVenue.id) {
    window.location.href = '/companies/' + _cdVenue.id;
  }
  return false;
}

function showEmailTemplates(v, category) {
  if (!v) return;
  var cfg = _cdCfg();
  var name = v[cfg.nameField] || '(unnamed)';
  var tmpls = (window._TEMPLATES && window._TEMPLATES[category]) || [];
  var html = '<button class="cd-back-btn" onclick="_cdBackToDetail()">\u2190 Back to detail</button>';
  html += '<div style="font-size:13px;font-weight:600;margin-bottom:12px">Choose a template for <strong>' + esc(name) + '</strong></div>';
  html += '<div class="tpl-grid">';
  tmpls.forEach(function(t, i) {
    var preview = t.body.replace(/\{name\}/g, name).substring(0, 160) + '\u2026';
    html += '<div class="tpl-card">';
    html += '<div class="tpl-card-name">' + esc(t.name) + '</div>';
    html += '<div class="tpl-card-subj">Subject: ' + esc(t.subject) + '</div>';
    html += '<div class="tpl-card-preview">' + esc(preview) + '</div>';
    html += '<button class="tpl-use-btn" data-tpl-i="'+i+'" data-tpl-cat="'+category+'" onclick="useTemplate(+this.dataset.tplI,this.dataset.tplCat)">Use Template \u2192</button>';
    html += '</div>';
  });
  html += '</div>';
  document.getElementById('cd-tpl-body').innerHTML = html;
  document.getElementById('cd-panel-detail').className = 'cd-panel';
  document.getElementById('cd-panel-tpl').className    = 'cd-panel active';
}

function _cdBackToDetail() {
  document.getElementById('cd-panel-detail').className = 'cd-panel active';
  document.getElementById('cd-panel-tpl').className    = 'cd-panel';
}

function useTemplate(i, category) {
  var t = (window._TEMPLATES && window._TEMPLATES[category] || [])[i];
  if (!t || !_cdVenue) return;
  var cfg = _cdCfg();
  var name = _cdVenue[cfg.nameField] || '';
  var body = t.body.replace(/\{name\}/g, name);
  document.getElementById('compose-to').value      = (_cdVenue['Email'] || '');
  document.getElementById('compose-subject').value = t.subject;
  document.getElementById('compose-body').value    = body;
  document.getElementById('compose-status').textContent = '';
  closeContactDetail();
  document.getElementById('compose-overlay').classList.add('open');
  setTimeout(function() {
    var toVal = document.getElementById('compose-to').value;
    document.getElementById(toVal ? 'compose-subject' : 'compose-to').focus();
  }, 50);
}

async function updateStatus(id, val) {
  if (_cdVenue && _cdVenue.id === id) _cdVenue['Contact Status'] = {value: val};
  var st = document.getElementById('cd-status-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  var res = await Contact.saveStatus(_TOOL_KEY, id, val);
  if (st) { st.textContent = res.ok ? '\u2713' : '\u2717'; setTimeout(function() { if(st) st.textContent=''; }, 2000); }
  if (res.ok && window._onContactUpdate && _cdVenue) window._onContactUpdate(_cdVenue);
}

async function saveFollowUp(id) {
  var val = (document.getElementById('cd-fu-' + id) || {}).value || null;
  if (_cdVenue && _cdVenue.id === id) _cdVenue['Follow-Up Date'] = val;
  var st = document.getElementById('cd-fu-st-' + id);
  if (st) st.textContent = 'Saving\u2026';
  var res = await Contact.saveFollowUp(_TOOL_KEY, id, val);
  if (st) { st.textContent = res.ok ? '\u2713' : '\u2717'; setTimeout(function() { if(st) st.textContent=''; }, 2000); }
  if (res.ok && window._onContactUpdate && _cdVenue) window._onContactUpdate(_cdVenue);
}

async function addNote(id) {
  var inputEl = document.getElementById('cd-note-in-' + id);
  var text = (inputEl ? inputEl.value : '').trim();
  if (!text) return;
  var existing = (_cdVenue && _cdVenue['Notes'] ? _cdVenue['Notes'].trim() : '');
  var res = await Contact.addNote(_TOOL_KEY, id, existing, text);
  if (_cdVenue && _cdVenue.id === id) _cdVenue['Notes'] = res.newNotes;
  if (inputEl) inputEl.value = '';
  var logEl = document.getElementById('cd-notes-' + id);
  if (logEl) logEl.innerHTML = renderNotes(res.newNotes);
  var st = document.getElementById('cd-note-st-' + id);
  if (st) { st.textContent = res.ok ? 'Saved \u2713' : 'Failed \u2717'; setTimeout(function() { if(st) st.textContent=''; }, 2000); }
  if (res.ok && window._onContactUpdate && _cdVenue) window._onContactUpdate(_cdVenue);
}
"""


def contact_detail_js() -> str:
    """Return the contact-detail modal render + handler JS block.

    Page-level requirements before including this:
      - A `_TOOL_KEY` JS global naming the tool ('attorney' | 'gorilla' | 'community').
      - `contact_actions_js()` must have been included earlier on the page
        (provides `Contact.*`).
      - `esc`, `sv`, `fetchAll`, `BR`, `BT` from `_JS_SHARED` (already loaded
        on every page via `_page()`).
      - `_TEMPLATES` from `_COMPOSE_JS` (already loaded on every page).

    Optional: `window._onContactUpdate = function(venue) { ... }` — invoked
    after every successful edit so the page can sync its own state.
    """
    return _CONTACT_DETAIL_JS
