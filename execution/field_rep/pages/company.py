"""Company detail page + directory list."""

from hub.shared import (
    _mobile_page,
    T_COMPANIES,
)


def _mobile_company_detail_page(br: str, bt: str, company_id: int,
                                 user: dict = None) -> str:
    """Mobile-sized view of a single Company row + its activity feed, with an
    inline 'Log activity' form. POSTs to /api/companies/{id}/activities."""
    user = user or {}
    body = (
        '<div class="mobile-hdr">'
        '<button class="m-hamburger" onclick="goBack()" aria-label="Back" '
        'style="margin-right:10px">←</button>'
        '<div style="flex:1;min-width:0"><div class="mobile-hdr-title" id="cd-name">Loading…</div>'
        '<div class="mobile-hdr-sub" id="cd-sub"></div></div>'
        '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        '</div>'
        '<div class="mobile-body">'
        '<div id="cd-meta" style="margin-bottom:14px"></div>'
        # Quick-log activity button
        '<button onclick="openLogModal()" '
        'style="width:100%;padding:12px;background:#ea580c;color:#fff;border:none;border-radius:10px;'
        'font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;margin-bottom:16px">'
        '+ Log activity</button>'
        # Activity feed
        '<div class="mobile-section-lbl">Recent activity</div>'
        '<div id="cd-feed"><div class="loading">Loading…</div></div>'
        '</div>'
        # Log-activity modal
        '<div id="cd-modal-bg" onclick="if(event.target===this)closeLogModal()" '
        'style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:900;'
        'align-items:flex-start;justify-content:center;padding:40px 16px;overflow-y:auto">'
        '<div style="background:var(--bg2);border:1px solid var(--border);border-radius:14px;'
        'width:100%;max-width:480px;padding:20px">'
        '<h3 style="margin:0 0 14px;color:var(--text);font-size:16px">Log activity</h3>'
        '<label style="display:block;font-size:11px;font-weight:700;color:var(--text3);'
        'text-transform:uppercase;margin-bottom:4px;letter-spacing:.4px">Type</label>'
        '<select id="cd-type" style="width:100%;padding:9px;background:var(--bg);border:1px solid var(--border);'
        'color:var(--text);border-radius:6px;font-size:13px;margin-bottom:12px">'
        '<option value="Call">\U0001f4de Call</option>'
        '<option value="Email">✉️ Email</option>'
        '<option value="Drop Off">\U0001f4cd Drop-off</option>'
        '<option value="Text">\U0001f4ac Text</option>'
        '<option value="In Person">\U0001f91d In Person</option>'
        '<option value="Other">Other</option>'
        '</select>'
        '<label style="display:block;font-size:11px;font-weight:700;color:var(--text3);'
        'text-transform:uppercase;margin-bottom:4px;letter-spacing:.4px">Notes *</label>'
        '<textarea id="cd-summary" rows="3" placeholder="What happened?" '
        'style="width:100%;padding:9px;background:var(--bg);border:1px solid var(--border);'
        'color:var(--text);border-radius:6px;font-size:13px;resize:vertical;font-family:inherit;margin-bottom:12px"></textarea>'
        '<label style="display:block;font-size:11px;font-weight:700;color:var(--text3);'
        'text-transform:uppercase;margin-bottom:4px;letter-spacing:.4px">Next follow-up</label>'
        '<input type="date" id="cd-fu" '
        'style="width:100%;padding:9px;background:var(--bg);border:1px solid var(--border);'
        'color:var(--text);border-radius:6px;font-size:13px;margin-bottom:12px;font-family:inherit">'
        '<label style="display:block;font-size:11px;font-weight:700;color:var(--text3);'
        'text-transform:uppercase;margin-bottom:4px;letter-spacing:.4px">New status (optional)</label>'
        '<select id="cd-status" style="width:100%;padding:9px;background:var(--bg);border:1px solid var(--border);'
        'color:var(--text);border-radius:6px;font-size:13px;margin-bottom:14px">'
        '<option value="">(keep current)</option>'
        '<option value="Not Contacted">Not Contacted</option>'
        '<option value="Contacted">Contacted</option>'
        '<option value="In Discussion">In Discussion</option>'
        '<option value="Active Partner">Active Partner</option>'
        '</select>'
        '<div id="cd-modal-msg" style="font-size:12px;min-height:14px;margin-bottom:8px"></div>'
        '<div style="display:flex;gap:8px;justify-content:flex-end">'
        '<button onclick="closeLogModal()" '
        'style="padding:9px 16px;background:none;border:1px solid var(--border);color:var(--text2);'
        'border-radius:6px;font-size:13px;cursor:pointer;font-family:inherit">Cancel</button>'
        '<button id="cd-modal-send" onclick="submitLog()" '
        'style="padding:9px 20px;background:#059669;border:none;color:#fff;border-radius:6px;'
        'font-size:13px;font-weight:700;cursor:pointer;font-family:inherit">Save</button>'
        '</div>'
        '</div>'
        '</div>'
    )
    js = f"""
const COMPANY_ID = {int(company_id)};
let _COMPANY = null;

var CAT_META = {{
  attorney:  {{label: 'Attorney',  color: '#7c3aed'}},
  guerilla:  {{label: 'Guerilla',  color: '#ea580c'}},
  community: {{label: 'Community', color: '#059669'}},
  other:     {{label: 'Other',     color: '#64748b'}},
}};

function esc(s) {{
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}}

function svJS(v) {{
  if (!v) return '';
  if (typeof v === 'object' && !Array.isArray(v)) return v.value || '';
  if (Array.isArray(v) && v.length) return (v[0] && v[0].value) || (v[0] && v[0].name) || String(v[0]);
  return String(v);
}}

function fmtDate(s) {{
  if (!s) return '—';
  s = String(s).slice(0, 10);
  var parts = s.split('-');
  if (parts.length !== 3) return s;
  return parts[1] + '/' + parts[2] + '/' + parts[0].slice(2);
}}

function goBack() {{
  if (document.referrer && document.referrer.indexOf(location.origin) === 0) {{
    history.back();
  }} else {{
    location.href = '/';
  }}
}}

function renderCompany() {{
  var c = _COMPANY;
  var name = c.Name || '(unnamed)';
  var cat = (svJS(c.Category) || 'other').toLowerCase();
  var meta = CAT_META[cat] || CAT_META.other;
  document.title = name + ' — Reform';
  document.getElementById('cd-name').textContent = name;
  document.getElementById('cd-sub').innerHTML =
    '<span style="background:' + meta.color + '22;color:' + meta.color + ';font-size:10px;font-weight:600;padding:2px 8px;border-radius:10px">' +
    esc(meta.label) + '</span>' +
    (svJS(c['Contact Status']) ? '<span style="font-size:11px;color:var(--text3);margin-left:8px">' + esc(svJS(c['Contact Status'])) + '</span>' : '');

  var phone = c.Phone || '';
  var email = c.Email || '';
  var addr  = c.Address || '';
  var site  = c.Website || '';
  var fu    = c['Follow-Up Date'] || '';
  var notes = c.Notes || '';

  // Prefer the internal map view if we know the underlying guerilla venue id.
  // Falls back to Google Maps for hub-only / community companies without a
  // migrated venue row.
  var legacySrc = svJS(c['Legacy Source']);
  var legacyId  = c['Legacy ID'];
  var navUrl, navTarget;
  if (legacySrc === 'guerilla_venue' && legacyId) {{
    navUrl = '/map?venue=' + encodeURIComponent(legacyId);
    navTarget = '_self';
  }} else {{
    navUrl = addr ? 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(addr) : '';
    navTarget = '_blank';
  }}
  var html = '<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px">';
  if (phone) html += '<div style="padding:6px 0;border-bottom:1px solid var(--border)"><a href="tel:' + esc(phone) + '" style="color:#3b82f6;text-decoration:none;font-size:14px;font-weight:600">\U0001f4de ' + esc(phone) + '</a></div>';
  if (email) html += '<div style="padding:6px 0;border-bottom:1px solid var(--border)"><a href="mailto:' + esc(email) + '" style="color:#3b82f6;text-decoration:none;font-size:14px;font-weight:600">✉️ ' + esc(email) + '</a></div>';
  if (addr)  html += '<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:13px;color:var(--text2)">\U0001f4cd ' + esc(addr) + (navUrl ? ' <a href="' + esc(navUrl) + '" target="' + navTarget + '" style="color:#3b82f6;font-size:12px;margin-left:6px">Navigate →</a>' : '') + '</div>';
  if (site)  html += '<div style="padding:6px 0;border-bottom:1px solid var(--border)"><a href="' + esc(site) + '" target="_blank" style="color:#3b82f6;text-decoration:none;font-size:13px">\U0001f310 ' + esc(site) + '</a></div>';
  if (fu)    html += '<div style="padding:6px 0;font-size:13px;color:var(--text2)">\U0001f4c5 Next follow-up: <strong>' + esc(fmtDate(fu)) + '</strong></div>';
  if (notes) html += '<div style="padding:10px 0 0;margin-top:8px;border-top:1px solid var(--border);font-size:12px;color:var(--text3);white-space:pre-wrap">' + esc(notes) + '</div>';
  html += '</div>';
  document.getElementById('cd-meta').innerHTML = html;
}}

function renderFeed(activities) {{
  if (!activities || !activities.length) {{
    document.getElementById('cd-feed').innerHTML =
      '<div style="text-align:center;padding:24px 0;color:var(--text3);font-size:13px">No activity yet.</div>';
    return;
  }}
  var html = '';
  activities.forEach(function(a) {{
    var kind  = svJS(a.Kind) || 'activity';
    var type  = svJS(a.Type) || '';
    var summ  = a.Summary || '';
    var when  = a.Created || a.Date || '';
    var who   = a.Author || '';
    var typeColor = '#475569';
    html +=
      '<div style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px 12px;margin-bottom:6px">' +
      '<div style="display:flex;gap:8px;align-items:center;margin-bottom:4px">' +
      (type ? '<span style="background:' + typeColor + '20;color:' + typeColor + ';font-size:10px;font-weight:600;padding:2px 7px;border-radius:6px">' + esc(type) + '</span>' : '') +
      '<span style="font-size:10px;color:var(--text3)">' + esc(fmtDate(when)) + (who ? ' · ' + esc(who.split('@')[0]) : '') + '</span>' +
      '</div>' +
      '<div style="font-size:13px;color:var(--text2);white-space:pre-wrap">' + esc(summ) + '</div>' +
      '</div>';
  }});
  document.getElementById('cd-feed').innerHTML = html;
}}

async function load() {{
  var [cRes, aRes] = await Promise.all([
    fetch('/api/companies/' + COMPANY_ID),
    fetch('/api/companies/' + COMPANY_ID + '/activities'),
  ]);
  if (!cRes.ok) {{
    document.getElementById('cd-name').textContent = 'Not found';
    document.getElementById('cd-meta').innerHTML = '';
    document.getElementById('cd-feed').innerHTML = '';
    return;
  }}
  _COMPANY = await cRes.json();
  renderCompany();
  if (aRes.ok) {{
    var acts = await aRes.json();
    renderFeed(acts);
  }}
}}

// ── Log activity modal ──
function openLogModal() {{
  document.getElementById('cd-summary').value = '';
  document.getElementById('cd-fu').value = '';
  document.getElementById('cd-type').value = 'Call';
  document.getElementById('cd-status').value = '';
  document.getElementById('cd-modal-msg').textContent = '';
  document.getElementById('cd-modal-bg').style.display = 'flex';
}}

function closeLogModal() {{
  document.getElementById('cd-modal-bg').style.display = 'none';
}}

async function submitLog() {{
  var summary = document.getElementById('cd-summary').value.trim();
  var type    = document.getElementById('cd-type').value;
  var fu      = document.getElementById('cd-fu').value;
  var status  = document.getElementById('cd-status').value;
  var msg     = document.getElementById('cd-modal-msg');
  var btn     = document.getElementById('cd-modal-send');
  if (!summary) {{
    msg.style.color = '#ef4444';
    msg.textContent = 'Notes are required.';
    return;
  }}
  btn.disabled = true;
  btn.textContent = 'Saving…';
  msg.textContent = '';
  var body = {{ summary: summary, type: type, kind: 'user_activity' }};
  if (fu) body.follow_up = fu;
  if (status) body.new_status = status;
  var r = await fetch('/api/companies/' + COMPANY_ID + '/activities', {{
    method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify(body),
  }});
  if (r.ok) {{
    closeLogModal();
    await load();  // re-render with new activity
  }} else {{
    var err = '';
    try {{ err = (await r.json()).error || ''; }} catch(e) {{}}
    msg.style.color = '#ef4444';
    msg.textContent = 'Save failed: ' + (err || ('HTTP ' + r.status));
    btn.disabled = false;
    btn.textContent = 'Save';
  }}
}}

load();
"""
    return _mobile_page('m_directory', 'Company', body, js, br, bt, user=user)




def _mobile_directory_page(br: str, bt: str, category: str = "",
                            user: dict = None) -> str:
    """Mobile directory listing. `category` in {'', 'attorney', 'guerilla',
    'community'}; empty string means all. Tap a row → /company/{id}."""
    user = user or {}
    title = {
        "attorney":  "Attorney Directory",
        "guerilla":  "Guerilla Directory",
        "community": "Community Directory",
    }.get(category, "All Contacts")
    subtitle = {
        "attorney":  "Law firms & referral partners",
        "guerilla":  "Local businesses & health partners",
        "community": "Community groups & events",
    }.get(category, "Every outreach company")
    body = (
        '<div class="mobile-hdr">'
        f'<div><div class="mobile-hdr-title">{title}</div>'
        f'<div class="mobile-hdr-sub">{subtitle}</div></div>'
        '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        '</div>'
        '<div class="mobile-body">'
        '<div class="stats-row" style="margin-bottom:14px">'
        '<div class="stat-chip c-blue"><div class="label">Total</div><div class="value" id="dir-kpi-total">—</div></div>'
        '<div class="stat-chip c-green"><div class="label">Active</div><div class="value" id="dir-kpi-active">—</div></div>'
        '<div class="stat-chip c-yellow"><div class="label">Needs Contact</div><div class="value" id="dir-kpi-new">—</div></div>'
        '</div>'
        '<input type="search" id="dir-search" placeholder="Search name, address, phone…" oninput="renderDir()" '
        'style="width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:8px;'
        'background:var(--card);color:var(--text);font-size:14px;margin-bottom:10px;font-family:inherit">'
        '<div id="dir-filter" style="display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap"></div>'
        '<div id="dir-summary" style="font-size:12px;color:var(--text3);margin-bottom:8px">Loading…</div>'
        '<div id="dir-list"><div class="loading">Loading…</div></div>'
        '</div>'
    )
    cat_js = repr(category or "")
    js = f"""
var CATEGORY = {cat_js};
var _DIR_ROWS = [];
var _DIR_STATUS = 'prospects';
var _PROSPECT_STATUSES = ['Not Contacted', 'Contacted', 'In Discussion'];

var STATUS_META = {{
  'Not Contacted':  {{color: '#64748b'}},
  'Contacted':      {{color: '#2563eb'}},
  'In Discussion':  {{color: '#ea580c'}},
  'Active Partner': {{color: '#059669'}},
  'Blacklisted':    {{color: '#dc2626'}},
}};

var DIR_CAT_META = {{
  attorney:  {{label: 'Attorney',  color: '#7c3aed'}},
  guerilla:  {{label: 'Guerilla',  color: '#ea580c'}},
  community: {{label: 'Community', color: '#059669'}},
  other:     {{label: 'Other',     color: '#64748b'}},
}};

function esc(s) {{
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}}

function svJS(v) {{
  if (!v) return '';
  if (typeof v === 'object' && !Array.isArray(v)) return v.value || '';
  if (Array.isArray(v) && v.length) return (v[0] && v[0].value) || (v[0] && v[0].name) || String(v[0]);
  return String(v);
}}

function renderStatusFilter() {{
  var counts = {{ all: _DIR_ROWS.length, prospects: 0 }};
  Object.keys(STATUS_META).forEach(function(k) {{ counts[k] = 0; }});
  _DIR_ROWS.forEach(function(c) {{
    var s = svJS(c['Contact Status']) || 'Not Contacted';
    counts[s] = (counts[s] || 0) + 1;
    if (_PROSPECT_STATUSES.indexOf(s) !== -1) counts.prospects += 1;
  }});
  // Prospects first so it reads as the default intent, then all, then real statuses.
  var opts = ['prospects', 'all'].concat(Object.keys(STATUS_META));
  var html = '';
  opts.forEach(function(k) {{
    if (k === 'prospects' && !counts.prospects) return;
    if (k !== 'all' && k !== 'prospects' && !counts[k]) return;
    var active = k === _DIR_STATUS;
    var color;
    var label;
    if (k === 'all')             {{ color = '#0f172a'; label = 'All'; }}
    else if (k === 'prospects')  {{ color = '#2563eb'; label = 'Prospects'; }}
    else                         {{ color = (STATUS_META[k] || {{}}).color || '#64748b'; label = k; }}
    html +=
      '<button onclick="setStatus(\\'' + k + '\\')" ' +
      'style="padding:5px 10px;border-radius:14px;font-size:11px;font-weight:600;cursor:pointer;font-family:inherit;' +
      'border:1px solid ' + (active ? color : 'var(--border)') + ';' +
      'background:' + (active ? color : 'var(--card)') + ';' +
      'color:' + (active ? '#fff' : 'var(--text2)') + '">' +
      esc(label) + ' ' + counts[k] + '</button>';
  }});
  document.getElementById('dir-filter').innerHTML = html;
}}

function setStatus(k) {{
  _DIR_STATUS = k;
  renderStatusFilter();
  renderDir();
}}

function renderDir() {{
  var q = (document.getElementById('dir-search').value || '').toLowerCase().trim();
  var filtered = _DIR_ROWS.filter(function(c) {{
    var s = svJS(c['Contact Status']) || 'Not Contacted';
    if (_DIR_STATUS === 'prospects') {{
      if (_PROSPECT_STATUSES.indexOf(s) === -1) return false;
    }} else if (_DIR_STATUS !== 'all') {{
      if (s !== _DIR_STATUS) return false;
    }}
    if (!q) return true;
    var hay = ((c.Name || '') + ' ' + (c.Address || '') + ' ' + (c.Phone || '')).toLowerCase();
    return hay.indexOf(q) !== -1;
  }});
  filtered.sort(function(a, b) {{
    return (a.Name || '').localeCompare(b.Name || '');
  }});
  document.getElementById('dir-summary').textContent =
    filtered.length + ' compan' + (filtered.length === 1 ? 'y' : 'ies');
  if (!filtered.length) {{
    document.getElementById('dir-list').innerHTML =
      '<div style="text-align:center;padding:30px 0;color:var(--text3);font-size:13px">No matches.</div>';
    return;
  }}
  var html = '';
  filtered.forEach(function(c) {{
    var status = svJS(c['Contact Status']) || 'Not Contacted';
    var sMeta = STATUS_META[status] || {{color: '#64748b'}};
    var catKey = (svJS(c.Category) || 'other').toLowerCase();
    var catMeta = DIR_CAT_META[catKey] || DIR_CAT_META.other;
    // Only show the category pill when no specific category is filtered —
    // it's redundant on /attorney, /guerilla, /community.
    var catPill = CATEGORY ? '' :
      '<span style="background:' + catMeta.color + '22;color:' + catMeta.color +
      ';font-size:10px;font-weight:600;padding:2px 7px;border-radius:8px;white-space:nowrap">' +
      esc(catMeta.label) + '</span>';
    html +=
      '<div onclick="location.href=\\'/company/' + c.id + '\\'" ' +
      'style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:10px 12px;' +
      'margin-bottom:6px;cursor:pointer;display:flex;align-items:center;gap:8px">' +
      '<div style="flex:1;min-width:0">' +
      '<div style="font-size:14px;font-weight:700;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(c.Name || '(unnamed)') + '</div>' +
      (c.Address ? '<div style="font-size:11px;color:var(--text3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(c.Address) + '</div>' : '') +
      '</div>' +
      catPill +
      '<span style="background:' + sMeta.color + '22;color:' + sMeta.color + ';font-size:10px;font-weight:600;padding:2px 8px;border-radius:10px;white-space:nowrap">' + esc(status) + '</span>' +
      '</div>';
  }});
  document.getElementById('dir-list').innerHTML = html;
}}

async function loadDir() {{
  try {{
    var r = await fetch('/api/data/{T_COMPANIES}');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    var rows = await r.json();
    if (CATEGORY) {{
      rows = rows.filter(function(c) {{
        return (svJS(c.Category) || '').toLowerCase() === CATEGORY;
      }});
    }}
    // Exclude Permanently Closed
    rows = rows.filter(function(c) {{ return !c['Permanently Closed']; }});
    _DIR_ROWS = rows;
  }} catch (e) {{
    document.getElementById('dir-summary').textContent = '';
    document.getElementById('dir-list').innerHTML =
      '<div style="text-align:center;padding:30px 0;color:#ef4444;font-size:13px">Failed to load: ' + esc(e.message || 'error') + '</div>';
    return;
  }}
  renderStatusFilter();
  renderDir();
  // KPI strip
  var active = 0, needsContact = 0;
  _DIR_ROWS.forEach(function(c) {{
    var s = svJS(c['Contact Status']);
    if (s === 'Active Partner') active++;
    if (!s || s === 'Not Contacted') needsContact++;
  }});
  document.getElementById('dir-kpi-total').textContent = _DIR_ROWS.length;
  document.getElementById('dir-kpi-active').textContent = active;
  document.getElementById('dir-kpi-new').textContent = needsContact;
}}

loadDir();
"""
    return _mobile_page('m_directory', title, body, js, br, bt, user=user)
