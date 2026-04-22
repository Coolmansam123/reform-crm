"""
Communications pages — contacts directory and email.

Reads from the unified T_COMPANIES table (Phase 2b — 2026-04-21) rather than
the three legacy venue tables. Category filtering is client-side.
"""
from .shared import (
    _page,
    T_COMPANIES,
    T_PI_ACTIVE, T_PI_BILLED, T_PI_AWAITING, T_PI_CLOSED,
)


def _contacts_page(br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header"><div class="header-left">'
        '<h1>Companies Directory</h1>'
        '<div class="sub">All companies — attorneys, guerilla venues, community orgs. People will get their own page in Phase 3.</div>'
        '</div></div>'
    )
    body = (
        '<div class="panel" style="margin-bottom:0">'
        '<div class="filter-bar" style="gap:10px;flex-wrap:wrap">'
        '<button class="filter-btn on" data-status="active" onclick="setStatus(this)">Active Relationship</button>'
        '<button class="filter-btn" data-status="previous" onclick="setStatus(this)">Previous Relationship</button>'
        '<div style="width:1px;background:var(--border);align-self:stretch;margin:0 4px"></div>'
        '<button class="filter-btn" data-cat="" onclick="setCat(this)" style="opacity:0.7">All</button>'
        '<button class="filter-btn" data-cat="attorney"  onclick="setCat(this)" style="color:#a78bfa">Attorney</button>'
        '<button class="filter-btn" data-cat="guerilla"  onclick="setCat(this)" style="color:#fb923c">Guerilla</button>'
        '<button class="filter-btn" data-cat="community" onclick="setCat(this)" style="color:#34d399">Community</button>'
        '<input class="search-input" id="srch" placeholder="Search name or phone\u2026" oninput="applyFilters()" style="margin-left:auto;width:220px">'
        '<span id="cnt" style="font-size:12px;color:var(--text3);white-space:nowrap"></span>'
        '</div>'
        '<div class="bulk-actions" id="bulk-actions">'
        '<span class="bulk-label"><span id="bulk-count">0</span> selected</span>'
        '<span class="bulk-sep">\u2022</span>'
        '<select id="blk-status">'
        '<option value="">Change status\u2026</option>'
        '<option>Not Contacted</option><option>Contacted</option>'
        '<option>In Discussion</option><option>Active Partner</option>'
        '<option>Blacklisted</option>'
        '</select>'
        '<select id="blk-goal">'
        '<option value="">Change outreach goal\u2026</option>'
        '<option>Referral Partner</option><option>Co-Marketing</option>'
        '<option>Event Presence</option><option>Sponsorship</option>'
        '<option>Both</option>'
        '</select>'
        '<button class="primary" onclick="coBulkApply()">Apply</button>'
        '<button onclick="clearBulk()">Clear</button>'
        '</div>'
        '<div id="tbl"><div class="loading">Loading\u2026</div></div>'
        '</div>'
        '\n<!-- New Company modal -->'
        '<div class="compose-overlay" id="nc-overlay" onclick="if(event.target===this)closeNewContact()">'
        '<div class="compose-box" style="width:480px">'
        '<h3>+ New Company</h3>'
        '<select id="nc-cat" class="compose-input" style="cursor:pointer">'
        '<option value="attorney">Attorney / Law Firm</option>'
        '<option value="guerilla">Guerilla / Business Venue</option>'
        '<option value="community">Community Org</option>'
        '</select>'
        '<input id="nc-name"  class="compose-input" placeholder="Company name *">'
        '<input id="nc-phone" class="compose-input" placeholder="Phone">'
        '<input id="nc-email" class="compose-input" placeholder="Email">'
        '<input id="nc-addr"  class="compose-input" placeholder="Address">'
        '<select id="nc-status" class="compose-input" style="cursor:pointer">'
        '<option value="Not Contacted">Not Contacted</option>'
        '<option value="Contacted">Contacted</option>'
        '<option value="In Discussion">In Discussion</option>'
        '<option value="Active Partner">Active Partner</option>'
        '</select>'
        '<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:4px">'
        '<button class="compose-send" onclick="closeNewContact()" style="background:#1e3a5f;color:var(--text2)">Cancel</button>'
        '<button class="compose-send" onclick="createContact()">Create</button>'
        '</div>'
        '<div id="nc-msg" style="font-size:12px;text-align:right;min-height:18px"></div>'
        '</div></div>'
    )
    js = f"""
// Category display metadata — hub labels/colors for the unified Companies feed
const CAT_LABELS = {{
  attorney:  {{label:'Attorney',  color:'#7c3aed'}},
  guerilla:  {{label:'Guerilla',  color:'#ea580c'}},
  community: {{label:'Community', color:'#059669'}},
  other:     {{label:'Other',     color:'#64748b'}},
}};
const SC = {{'Active Relationship':'#059669','Active Partner':'#059669','Previous Relationship':'#7c3aed','In Discussion':'#d97706','Contacted':'#2563eb','Not Contacted':'#475569','Blacklisted':'#ef4444'}};
let _all = [];
let _activeCat = '';
let _activeStatusFilter = 'active';

// ─── PI case cross-reference (attorney only) ─────────────────────────────────
let _firmCounts = {{}};
function _normName(n) {{ return (n || '').toLowerCase().trim(); }}
function _getFirmName(p) {{
  const raw = p['Law Firm Name ONLY'] || p['Law Firm Name'] || p['Law Firm'] || '';
  if (!raw) return '';
  if (Array.isArray(raw)) return raw.length ? (raw[0].value || String(raw[0])) : '';
  if (typeof raw === 'object' && raw.value) return raw.value;
  return String(raw);
}}
function _lookupFirmCounts(name) {{
  const key = _normName(name);
  if (_firmCounts[key]) return _firmCounts[key];
  for (const [k, v] of Object.entries(_firmCounts)) {{
    const shorter = key.length <= k.length ? key : k;
    const longer  = key.length <= k.length ? k   : key;
    if (shorter.length >= 8 && longer.includes(shorter)) return v;
  }}
  return {{}};
}}
function _effectiveStatus(r) {{
  const baseStatus = r.status;
  if (r.cat !== 'attorney') return baseStatus;
  const fc = _lookupFirmCounts(r.name);
  const hasCurrent = (fc.active || 0) + (fc.billed || 0) + (fc.awaiting || 0) > 0;
  const hasPast    = (fc.settled || 0) > 0;
  if (hasCurrent || baseStatus === 'Active Partner' || baseStatus === 'Active Relationship') return 'Active Partner';
  if (hasPast) return 'Previous Relationship';
  return baseStatus;
}}

async function load() {{
  document.getElementById('tbl').innerHTML = '<div class="loading">Loading\u2026</div>';
  const [companies, piActive, piBilled, piAwaiting, piClosed] = await Promise.all([
    fetchAll({T_COMPANIES}),
    fetchAll({T_PI_ACTIVE}),
    fetchAll({T_PI_BILLED}),
    fetchAll({T_PI_AWAITING}),
    fetchAll({T_PI_CLOSED}),
  ]);
  // Build firm case counts
  _firmCounts = {{}};
  const tally = (rows, key) => rows.forEach(r => {{
    const k = _normName(_getFirmName(r));
    if (k) {{ _firmCounts[k] = _firmCounts[k] || {{active:0,billed:0,awaiting:0,settled:0}}; _firmCounts[k][key]++; }}
  }});
  tally(piActive,'active'); tally(piBilled,'billed'); tally(piAwaiting,'awaiting'); tally(piClosed,'settled');

  _all = companies.map(r => {{
    const cat = sv(r['Category']) || 'other';
    const meta = CAT_LABELS[cat] || CAT_LABELS.other;
    return {{
      id: r.id,
      cat, label: meta.label, color: meta.color,
      name: r['Name'] || '(unnamed)',
      phone: r['Phone'] || '',
      status: sv(r['Contact Status']) || 'Not Contacted',
      followUp: r['Follow-Up Date'] || '',
    }};
  }}).sort((a,b) => a.name.localeCompare(b.name));
  applyFilters();
  stampRefresh();
}}

function setStatus(btn) {{
  document.querySelectorAll('[data-status]').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  _activeStatusFilter = btn.dataset.status;
  applyFilters();
}}

function setCat(btn) {{
  document.querySelectorAll('[data-cat]').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  _activeCat = btn.dataset.cat;
  applyFilters();
}}

function applyFilters() {{
  const q = (document.getElementById('srch').value || '').toLowerCase();
  let rows = _all.map(r => ({{ ...r, effStatus: _effectiveStatus(r) }}));
  if (_activeStatusFilter === 'active') {{
    rows = rows.filter(r => r.effStatus === 'Active Relationship' || r.effStatus === 'Active Partner');
  }} else {{
    rows = rows.filter(r => r.effStatus === 'Previous Relationship');
  }}
  if (_activeCat) rows = rows.filter(r => r.cat === _activeCat);
  if (q) rows = rows.filter(r => r.name.toLowerCase().includes(q) || r.phone.includes(q));
  document.getElementById('cnt').textContent = rows.length + ' contacts';
  if (!rows.length) {{
    document.getElementById('tbl').innerHTML = '<div class="empty">No contacts found</div>';
    return;
  }}
  document.getElementById('tbl').innerHTML =
    '<table class="data-table"><thead><tr>' +
    '<th style="width:28px"><input type="checkbox" class="bulk-all"></th>' +
    '<th>Name</th><th>Category</th><th style="white-space:nowrap">Status</th><th>Phone</th><th class="c">Follow-Up</th><th></th>' +
    '</tr></thead><tbody>' +
    rows.map(r => {{
      const sc = SC[r.effStatus] || '#475569';
      const du = daysUntil(r.followUp);
      let duHtml = '\u2014';
      if (du !== null) {{
        const col = du < 0 ? '#ef4444' : du === 0 ? '#f59e0b' : du <= 7 ? '#10b981' : '#64748b';
        duHtml = '<span style="color:' + col + ';font-weight:600">' + fmt(r.followUp) + '</span>';
      }}
      const nameEsc = esc(r.name);
      const href = '/companies/' + r.id;
      return '<tr style="cursor:pointer" onclick="if(event.target.tagName===\\'BUTTON\\'||event.target.tagName===\\'INPUT\\')return;location.href=\\'' + href + '\\'">' +
        '<td onclick="event.stopPropagation()" style="width:28px"><input type="checkbox" class="bulk-check" data-id="' + r.id + '"></td>' +
        '<td style="font-weight:500"><a href="' + href + '" style="color:inherit;text-decoration:none">' + nameEsc + '</a></td>' +
        '<td><span style="font-size:11px;padding:2px 8px;border-radius:10px;background:' + r.color + '22;color:' + r.color + ';font-weight:600">' + r.label + '</span></td>' +
        '<td><span style="font-size:11px;padding:2px 8px;border-radius:10px;background:' + sc + '22;color:' + sc + ';font-weight:600;white-space:nowrap">' + esc(r.effStatus) + '</span></td>' +
        '<td style="color:var(--text2)">' + esc(r.phone) + '</td>' +
        '<td class="c">' + duHtml + '</td>' +
        '<td><button class="btn btn-ghost" style="padding:2px 10px;font-size:11px" onclick="event.stopPropagation();openCompose(\\'\\',\\'Re: ' + nameEsc.replace(/'/g,"\\\\'") + '\\')" title="Compose">✉</button></td>' +
        '</tr>';
    }}).join('') +
    '</tbody></table>';
  if (typeof initBulkSelection === 'function') initBulkSelection();
}}

async function coBulkApply() {{
  const patch = {{}};
  const s = document.getElementById('blk-status').value;
  const g = document.getElementById('blk-goal').value;
  if (s) patch.contact_status = s;
  if (g) patch.outreach_goal  = g;
  if (!Object.keys(patch).length) {{ bulkToast('Pick a field to change', 'err'); return; }}
  const data = await submitBulkPatch('/api/companies/bulk-patch', patch);
  if (data && data.ok) {{
    clearBulk();
    document.getElementById('blk-status').value = '';
    document.getElementById('blk-goal').value = '';
    if (typeof load === 'function') load();
    else applyFilters();
  }}
}}

function openNewContact() {{
  document.getElementById('nc-name').value  = '';
  document.getElementById('nc-phone').value = '';
  document.getElementById('nc-email').value = '';
  document.getElementById('nc-addr').value  = '';
  document.getElementById('nc-msg').textContent = '';
  document.getElementById('nc-overlay').classList.add('open');
  setTimeout(function(){{ document.getElementById('nc-name').focus(); }}, 50);
}}
function closeNewContact() {{ document.getElementById('nc-overlay').classList.remove('open'); }}

async function createContact() {{
  const name = document.getElementById('nc-name').value.trim();
  const msg  = document.getElementById('nc-msg');
  if (!name) {{ msg.textContent = 'Name is required.'; msg.style.color='#ef4444'; return; }}
  msg.textContent = 'Creating\u2026'; msg.style.color='#94a3b8';
  try {{
    const r = await fetch('/api/contacts', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        category: document.getElementById('nc-cat').value,
        name,
        phone:   document.getElementById('nc-phone').value.trim(),
        email:   document.getElementById('nc-email').value.trim(),
        address: document.getElementById('nc-addr').value.trim(),
        status:  document.getElementById('nc-status').value,
      }}),
    }});
    const d = await r.json();
    if (r.ok) {{
      msg.textContent = 'Created!'; msg.style.color='#10b981';
      setTimeout(function(){{ closeNewContact(); load(); }}, 900);
    }} else {{
      msg.textContent = d.error || 'Error creating contact.'; msg.style.color='#ef4444';
    }}
  }} catch(e) {{
    msg.textContent = 'Network error.'; msg.style.color='#ef4444';
  }}
}}

load();
"""
    return _page('contacts', 'Contacts Directory', header, body, js, br, bt, user=user)


# ──────────────────────────────────────────────────────────────────────────────
# COMMUNICATIONS — EMAIL HUB
# ──────────────────────────────────────────────────────────────────────────────
def _communications_email_page(br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header"><div class="header-left">'
        '<h1>\u2709 Email</h1>'
        '<div class="sub">Compose emails and search conversation threads</div>'
        '</div></div>'
    )
    body = """
<style>
.email-toolbar{display:flex;gap:12px;margin-bottom:20px;align-items:stretch}
.email-compose-btn{background:#2563eb;color:#fff;border:none;border-radius:10px;padding:14px 24px;font-size:14px;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:8px;white-space:nowrap;transition:background .12s}
.email-compose-btn:hover{background:#1d4ed8}
.email-search-wrap{flex:1;position:relative}
.email-search-wrap input{width:100%;padding:12px 14px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:13px;outline:none}
.email-search-wrap input:focus{border-color:#2563eb}
.email-search-ac{display:none;position:absolute;top:100%;left:0;right:0;background:var(--bg2);border:1px solid var(--border);border-top:none;border-radius:0 0 10px 10px;max-height:200px;overflow-y:auto;z-index:10}
.email-search-ac.open{display:block}
.email-search-ac .compose-ac-item{padding:8px 14px}
.thread-item{padding:14px 18px;border-bottom:1px solid var(--border);cursor:pointer;transition:background .1s}
.thread-item:hover{background:rgba(255,255,255,0.03)}
.thread-item.expanded{background:rgba(37,99,235,0.06)}
.thread-subject{font-size:13px;font-weight:600;color:var(--text)}
.thread-from{font-size:12px;color:var(--text2)}
.thread-date{font-size:11px;color:var(--text3);white-space:nowrap}
.thread-snippet{font-size:12px;color:var(--text3);margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.thread-count{font-size:10px;color:var(--text3);background:var(--bg);padding:1px 6px;border-radius:8px;margin-left:8px}
.thread-msgs{border-left:3px solid #2563eb;margin:0 18px 0 18px;display:none}
.thread-msgs.open{display:block}
.thread-msg{padding:14px 16px;border-bottom:1px solid var(--border)}
.thread-msg:last-child{border-bottom:none}
.thread-msg-hd{display:flex;justify-content:space-between;margin-bottom:6px}
.thread-msg-from{font-size:12px;font-weight:600;color:var(--text)}
.thread-msg-date{font-size:11px;color:var(--text3)}
.thread-msg-body{font-size:12px;color:var(--text2);line-height:1.6;white-space:pre-wrap;word-break:break-word;max-height:300px;overflow-y:auto}
</style>

<div class="email-toolbar">
  <button class="email-compose-btn" onclick="openCompose()">\u2709 Compose</button>
  <div class="email-search-wrap">
    <input id="thread-search" placeholder="Search by name or email\u2026" autocomplete="off" data-1p-ignore data-bwignore="true"
      onkeydown="if(event.key==='Enter'){_doSearch();document.getElementById('email-search-ac').classList.remove('open')}">
    <div id="email-search-ac" class="email-search-ac"></div>
  </div>
</div>
<div class="panel" style="margin-bottom:0">
  <div class="panel-hd"><span class="panel-title" id="thread-hd">Recent Threads</span><span class="panel-ct" id="thread-ct"></span></div>
  <div class="panel-body" id="thread-results" style="min-height:200px;max-height:calc(100vh - 280px);overflow-y:auto">
    <div class="loading" style="padding:24px">Loading recent threads\u2026</div>
  </div>
</div>
"""
    js = """
var _emailAC = null;
async function _loadEmailAC() {
  if (_emailAC) return _emailAC;
  try { var r = await fetch('/api/contacts/autocomplete'); if (r.ok) _emailAC = await r.json(); else _emailAC = []; }
  catch(e) { _emailAC = []; }
  return _emailAC;
}

// Search autocomplete
(function(){
  var inp = document.getElementById('thread-search');
  var acEl = document.getElementById('email-search-ac');
  if (!inp) return;
  inp.addEventListener('input', function() {
    var q = inp.value.trim().toLowerCase();
    if (q.length < 1) { acEl.classList.remove('open'); return; }
    _loadEmailAC().then(function(contacts) {
      var matches = contacts.filter(function(c) {
        return c.n.toLowerCase().includes(q) || (c.e && c.e.toLowerCase().includes(q));
      }).slice(0, 6);
      if (!matches.length) { acEl.classList.remove('open'); return; }
      acEl.innerHTML = matches.map(function(c, i) {
        return '<div class="compose-ac-item" onmousedown="_pickSearch(\\'' + (c.e||'').replace(/'/g,"\\\\'") + '\\')">'
          + '<span class="compose-ac-name">' + esc(c.n) + '</span>'
          + (c.e ? '<span class="compose-ac-email">' + esc(c.e) + '</span>' : '')
          + '</div>';
      }).join('');
      acEl.classList.add('open');
    });
  });
  inp.addEventListener('blur', function(){ setTimeout(function(){ acEl.classList.remove('open'); }, 150); });
})();

function _pickSearch(email) {
  document.getElementById('thread-search').value = email;
  document.getElementById('email-search-ac').classList.remove('open');
  _doSearch();
}

function _doSearch() {
  var q = (document.getElementById('thread-search').value || '').trim();
  if (!q) { loadRecent(); return; }
  document.getElementById('thread-hd').textContent = 'Threads with ' + q;
  _loadThreads('?contact_email=' + encodeURIComponent(q));
}

function _loadThreads(query) {
  var res = document.getElementById('thread-results');
  res.innerHTML = '<div class="loading" style="padding:24px">Loading\\u2026</div>';
  fetch('/api/gmail/threads' + (query || ''))
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var threads = data.threads || [];
      document.getElementById('thread-ct').textContent = threads.length + ' threads';
      if (!threads.length) {
        res.innerHTML = '<div class="empty" style="padding:24px">No threads found</div>';
        return;
      }
      _threadMeta = {};
      res.innerHTML = threads.map(function(t) {
        var subj = esc(t.subject || '(no subject)');
        var snippet = esc(t.snippet || '');
        var rawFrom = t.from || '';
        var from = esc(rawFrom.replace(/<[^>]+>/g, '').trim());
        var fromEmail = (rawFrom.match(/<([^>]+)>/) || [])[1] || rawFrom.replace(/.*<|>.*/g,'').trim();
        var d = t.date || '';
        try { d = new Date(d).toLocaleDateString('en-US', {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}); } catch(e){}
        _threadMeta[t.id] = {subject: t.subject || '', from: fromEmail};
        return '<div class="thread-item" onclick="_toggleThread(this,\\'' + t.id + '\\')">'
          + '<div style="display:flex;justify-content:space-between;align-items:center">'
          + '<div style="min-width:0;flex:1">'
          + '<div style="display:flex;align-items:center;gap:6px"><span class="thread-subject">' + subj + '</span>'
          + (t.messageCount > 1 ? '<span class="thread-count">' + t.messageCount + '</span>' : '') + '</div>'
          + '<div class="thread-from">' + from + '</div>'
          + '</div>'
          + '<span class="thread-date">' + esc(d) + '</span>'
          + '</div>'
          + '<div class="thread-snippet">' + snippet + '</div>'
          + '</div>'
          + '<div class="thread-msgs" id="msgs-' + t.id + '"></div>';
      }).join('');
    })
    .catch(function(e) { res.innerHTML = '<div class="empty" style="padding:24px;color:#ef4444">Error loading threads</div>'; });
}

function _toggleThread(el, tid) {
  var msgEl = document.getElementById('msgs-' + tid);
  if (msgEl.classList.contains('open')) {
    msgEl.classList.remove('open');
    el.classList.remove('expanded');
    return;
  }
  // Close others
  document.querySelectorAll('.thread-msgs.open').forEach(function(m) { m.classList.remove('open'); });
  document.querySelectorAll('.thread-item.expanded').forEach(function(m) { m.classList.remove('expanded'); });
  el.classList.add('expanded');
  msgEl.classList.add('open');
  if (msgEl.dataset.loaded) return;
  msgEl.innerHTML = '<div class="loading" style="padding:14px">Loading messages\\u2026</div>';
  fetch('/api/gmail/thread/' + tid)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var msgs = data.messages || [];
      msgEl.dataset.loaded = '1';
      var lastFrom = '';
      var html = msgs.map(function(m) {
        var rawF = m.from || '';
        var from = esc(rawF.replace(/<[^>]+>/g, '').trim());
        lastFrom = (rawF.match(/<([^>]+)>/) || [])[1] || rawF.replace(/.*<|>.*/g,'').trim();
        var d = m.date || '';
        try { d = new Date(d).toLocaleDateString('en-US', {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}); } catch(e){}
        var body = esc(m.body || '(no text content)');
        return '<div class="thread-msg">'
          + '<div class="thread-msg-hd"><span class="thread-msg-from">' + from + '</span><span class="thread-msg-date">' + esc(d) + '</span></div>'
          + '<div class="thread-msg-body">' + body + '</div>'
          + '</div>';
      }).join('');
      var meta = _threadMeta[tid] || {};
      var replyTo = lastFrom || meta.from || '';
      var replySubj = meta.subject || '';
      if (replySubj && !replySubj.startsWith('Re:')) replySubj = 'Re: ' + replySubj;
      html += '<div style="padding:10px 16px">'
        + '<button style="background:#3b82f6;color:#fff;border:none;border-radius:6px;padding:6px 16px;font-size:12px;font-weight:600;cursor:pointer" '
        + 'onclick="event.stopPropagation();openCompose(\\'' + replyTo.replace(/'/g,"\\\\'") + '\\',\\'' + replySubj.replace(/'/g,"\\\\'") + '\\',\\'' + tid + '\\')">'
        + '\\u21a9 Reply</button></div>';
      msgEl.innerHTML = html;
    })
    .catch(function(e) { msgEl.innerHTML = '<div class="empty" style="padding:14px;color:#ef4444">Error loading messages</div>'; });
}

var _threadMeta = {};
function loadRecent() {
  document.getElementById('thread-hd').textContent = 'Recent Threads';
  _loadThreads('');
}

loadRecent();
"""
    return _page('communications_email', 'Email', header, body, js, br, bt, user=user)
