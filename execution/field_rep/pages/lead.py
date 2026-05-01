"""Leads list + capture/detail modals + legacy log redirect."""

from hub.shared import (
    _mobile_page,
    T_GOR_VENUES, T_EVENTS, T_COMPANIES, T_LEADS,
    LEAD_MODAL_HTML, LEAD_MODAL_JS,
)
from hub.guerilla import GFR_EXTRA_HTML, GFR_EXTRA_JS


def _mobile_lead_capture_page(br: str, bt: str, user: dict = None) -> str:
    user = user or {}
    user_name = user.get('name', '')
    user_email = (user.get('email', '') or '').strip().lower()
    capture_modal_html = (
        '<div id="capture-modal-bg" onclick="if(event.target===this)closeCaptureModal()" '
        'style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1100;'
        'align-items:flex-start;justify-content:center;padding:30px 14px;overflow-y:auto">'
        '<div style="background:var(--bg2);border:1px solid var(--border);border-radius:14px;'
        'width:100%;max-width:480px;padding:18px 20px calc(20px + env(safe-area-inset-bottom))">'
        '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">'
        '<h3 style="margin:0;color:var(--text);font-size:16px;flex:1">Capture Lead</h3>'
        '<button onclick="closeCaptureModal()" style="background:none;border:none;color:var(--text3);'
        'font-size:18px;cursor:pointer;padding:4px 8px">×</button>'
        '</div>'
        '<div id="capture-modal-body">'
        '<div id="lead-form">'
        '<div style="margin-bottom:12px">'
        '<label style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Name *</label>'
        '<input type="text" id="lf-name" placeholder="Full name" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:10px 12px;font-size:14px;box-sizing:border-box">'
        '</div>'
        '<div style="margin-bottom:12px">'
        '<label style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Phone *</label>'
        '<input type="tel" id="lf-phone" placeholder="(555) 123-4567" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:10px 12px;font-size:14px;box-sizing:border-box">'
        '</div>'
        '<div style="margin-bottom:12px">'
        '<label style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Email</label>'
        '<input type="email" id="lf-email" placeholder="email@example.com" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:10px 12px;font-size:14px;box-sizing:border-box">'
        '</div>'
        '<div style="margin-bottom:12px">'
        '<label style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Service Interested *</label>'
        '<select id="lf-service" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:10px 12px;font-size:14px;box-sizing:border-box;appearance:auto">'
        '<option value="">Select a service…</option>'
        '<option value="Chiropractic Care">Chiropractic Care</option>'
        '<option value="Massage Therapy">Massage Therapy</option>'
        '<option value="Health Screening">Health Screening</option>'
        '<option value="Injury Rehab">Injury Rehab</option>'
        '<option value="Other">Other</option>'
        '</select>'
        '</div>'
        '<div style="margin-bottom:12px">'
        '<label style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Event / Source</label>'
        '<select id="lf-event" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:10px 12px;font-size:14px;box-sizing:border-box;appearance:auto">'
        '<option value="">No event (walk-in / field)</option>'
        '</select>'
        '</div>'
        '<div style="margin-bottom:12px">'
        '<label style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Referred from company (optional)</label>'
        '<input type="text" id="lf-company" list="lf-company-list" placeholder="Type to search…" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:10px 12px;font-size:14px;box-sizing:border-box">'
        '<datalist id="lf-company-list"></datalist>'
        '<div id="lf-company-hint" style="font-size:11px;color:var(--text3);margin-top:4px;min-height:14px"></div>'
        '</div>'
        '<div style="margin-bottom:14px">'
        '<label style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;display:block;margin-bottom:4px">Notes</label>'
        '<textarea id="lf-notes" rows="3" placeholder="Additional details…" '
        'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
        'border-radius:8px;padding:10px 12px;font-size:14px;box-sizing:border-box;resize:vertical;font-family:inherit"></textarea>'
        '</div>'
        '<button id="lf-submit" onclick="submitLead()" '
        'style="width:100%;background:#004ac6;color:#fff;border:none;border-radius:8px;'
        'padding:13px;font-size:15px;font-weight:700;cursor:pointer">'
        'Submit Lead</button>'
        '<div id="lf-status" style="text-align:center;margin-top:10px;font-size:13px;min-height:20px"></div>'
        '</div>'
        '</div>'
        '</div>'
        '</div>'
    )
    body = (
        '<div class="mobile-hdr">'
        + '<div><div class="mobile-hdr-title">Leads</div>'
        + '<div class="mobile-hdr-sub">All captured leads</div></div>'
        + '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        + '</div>'
        + '<div class="mobile-body">'
        # 2x stat tiles: total + conversion %
        + '<div class="stat-grid" style="margin-bottom:18px">'
        +   '<div class="stat-tile"><div class="stat-label">Active Leads</div>'
        +     '<div class="stat-value" id="lead-kpi-active">—</div>'
        +     '<div class="stat-sub" id="lead-kpi-total">of — total</div></div>'
        +   '<div class="stat-tile"><div class="stat-label">Conversion</div>'
        +     '<div class="stat-value" id="lead-kpi-conv" style="color:#059669">—</div>'
        +     '<div class="stat-sub" id="lead-kpi-conv-sub">last 30 days</div></div>'
        + '</div>'
        # Search + Mine/All scope chips inline
        + '<div style="position:relative;margin-bottom:12px">'
        +   '<span class="material-symbols-outlined" style="position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--text3);font-size:18px">search</span>'
        +   '<input type="text" id="leads-search" placeholder="Search name, phone, email, source…" '
        +     'oninput="onSearchInput()" '
        +     'style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);'
        +     'border-radius:8px;padding:10px 12px 10px 36px;font-size:14px;box-sizing:border-box">'
        + '</div>'
        + '<div class="chip-strip" style="margin-bottom:14px">'
        +   '<button id="scope-all" class="chip active" onclick="setScope(\'all\')">All leads</button>'
        +   '<button id="scope-mine" class="chip" onclick="setScope(\'mine\')">Mine only</button>'
        + '</div>'
        + '<div class="label-caps" style="margin-bottom:6px">Filter by status</div>'
        + '<div id="leads-status-chips" class="chip-strip" style="margin-bottom:16px"></div>'
        + '<div class="label-caps" id="lead-list-label" style="margin-bottom:8px">Recent leads</div>'
        + '<div id="leads-list" style="display:flex;flex-direction:column;gap:10px">'
        +   '<div class="card" style="color:var(--text3);text-align:center;font-size:13px">Loading…</div>'
        + '</div>'
        + '</div>'
        # ── New Lead FAB (replaces the full-width toolbar button) ────
        + '<button class="fab" onclick="openCaptureModal()" aria-label="New lead">'
        +   '<span class="material-symbols-outlined">add</span></button>'
        + capture_modal_html
        + LEAD_MODAL_HTML
    )
    js = f"""
const USER_EMAIL = {repr(user_email)};
const _STATUSES = ['New','Contacted','Appointment Set','Patient Seen','Converted','Dropped'];
const _STATUS_COLORS = {{'New':'#3b82f6','Contacted':'#ea580c','Appointment Set':'#7c3aed','Patient Seen':'#0891b2','Converted':'#059669','Dropped':'#9ca3af'}};

var _leads = [];        // full cache from fetchAll
var _events = [];
var _COMPANIES_LOOKUP = {{}};
var _filterStatus = 'All';
var _filterScope = 'all';   // 'all' | 'mine'
var _searchQuery = '';
var _searchTimer = null;

function esc(s) {{
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}}

function svJS(v) {{
  if (!v) return '';
  if (typeof v === 'object' && !Array.isArray(v)) return v.value || '';
  return String(v);
}}

// ── Status pill class mapping ───────────────────────────────────────
function _leadPillClass(status) {{
  switch (status) {{
    case 'New':              return 'pill pill-routine';
    case 'Contacted':        return 'pill pill-warning';
    case 'Appointment Set':  return 'pill pill-routine';
    case 'Patient Seen':     return 'pill pill-success';
    case 'Converted':        return 'pill pill-success';
    case 'Dropped':          return 'pill pill-overdue';
    default:                 return 'pill';
  }}
}}

// ── Status chip strip (uses shared .chip primitives) ────────────────
function renderStatusChips() {{
  var box = document.getElementById('leads-status-chips');
  if (!box) return;
  var labels = ['All'].concat(_STATUSES);
  box.innerHTML = labels.map(function(s) {{
    var active = (s === _filterStatus);
    return '<button class="chip' + (active ? ' active' : '') + '" '
         + 'onclick="setStatusFilter(\\''+ esc(s) +'\\')">'+esc(s)+'</button>';
  }}).join('');
}}

function setStatusFilter(s) {{
  _filterStatus = s;
  renderStatusChips();
  applyFilters();
}}

function setScope(scope) {{
  _filterScope = scope;
  var allBtn = document.getElementById('scope-all');
  var mineBtn = document.getElementById('scope-mine');
  if (allBtn)  allBtn.classList.toggle('active', scope === 'all');
  if (mineBtn) mineBtn.classList.toggle('active', scope === 'mine');
  applyFilters();
}}

function onSearchInput() {{
  if (_searchTimer) clearTimeout(_searchTimer);
  _searchTimer = setTimeout(function() {{
    var el = document.getElementById('leads-search');
    _searchQuery = (el ? el.value : '').trim().toLowerCase();
    applyFilters();
  }}, 150);
}}

function clearAllFilters() {{
  _filterStatus = 'All';
  _filterScope = 'all';
  _searchQuery = '';
  var el = document.getElementById('leads-search');
  if (el) el.value = '';
  renderStatusChips();
  setScope('all');  // also re-applies filters
}}

// ── Filter + render ─────────────────────────────────────────────────
function applyFilters() {{
  var rows = _leads.slice();
  if (_filterStatus !== 'All') {{
    rows = rows.filter(function(L) {{ return svJS(L.Status) === _filterStatus; }});
  }}
  if (_filterScope === 'mine' && USER_EMAIL) {{
    rows = rows.filter(function(L) {{
      return (L.Owner || '').trim().toLowerCase() === USER_EMAIL;
    }});
  }}
  if (_searchQuery) {{
    var q = _searchQuery;
    rows = rows.filter(function(L) {{
      return (L.Name || '').toLowerCase().indexOf(q) >= 0
          || (L.Phone || '').toLowerCase().indexOf(q) >= 0
          || (L.Email || '').toLowerCase().indexOf(q) >= 0
          || (L.Source || '').toLowerCase().indexOf(q) >= 0;
    }});
  }}
  renderLeads(rows);
}}

function _initials(name) {{
  var parts = String(name || '').trim().split(/\\s+/).filter(Boolean);
  if (!parts.length) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}}

function renderLeads(rows) {{
  var box = document.getElementById('leads-list');
  var label = document.getElementById('lead-list-label');
  if (!box) return;
  if (label) {{
    label.innerHTML = 'Recent leads <span style="color:var(--text4);font-weight:600">· '
                    + rows.length + ' ' + (rows.length === 1 ? 'lead' : 'leads') + '</span>';
  }}
  if (!_leads.length) {{
    box.innerHTML = '<div class="card" style="color:var(--text3);text-align:center;padding:24px;font-size:13px">'
                  + '<div style="font-size:14px;margin-bottom:10px;color:var(--text2)">No leads yet.</div>'
                  + '<button onclick="openCaptureModal()" style="background:var(--primary);color:#fff;border:none;'
                  + 'border-radius:8px;padding:10px 18px;font-size:13px;font-weight:600;cursor:pointer">'
                  + '+ Capture your first lead</button></div>';
    return;
  }}
  if (!rows.length) {{
    box.innerHTML = '<div class="card" style="color:var(--text3);text-align:center;padding:24px;font-size:13px">'
                  + '<div style="font-size:14px;margin-bottom:8px;color:var(--text2)">No leads match your filters.</div>'
                  + '<a href="#" onclick="clearAllFilters();return false" style="color:var(--primary);font-size:13px;font-weight:600;text-decoration:none">Clear filters</a></div>';
    return;
  }}
  box.innerHTML = rows.map(function(L) {{
    var nm = L['Name'] || '(no name)';
    var ph = L['Phone'] || '';
    var em = L['Email'] || '';
    var rs = svJS(L['Reason']);
    var st = svJS(L['Status']) || 'New';
    var src = L['Source'] || '';
    var dt = (L['Created'] || '').slice(0, 10);
    var col = _STATUS_COLORS[st] || '#6b7280';
    var pillCls = _leadPillClass(st);
    var initials = _initials(nm);
    var contactBits = [];
    if (em) contactBits.push('<span style="display:inline-flex;align-items:center;gap:3px"><span class="material-symbols-outlined" style="font-size:13px">mail</span>' + esc(em) + '</span>');
    if (ph) contactBits.push('<span style="display:inline-flex;align-items:center;gap:3px"><span class="material-symbols-outlined" style="font-size:13px">call</span>' + esc(ph) + '</span>');
    var contactRow = contactBits.join('<span style="color:var(--text4)"> · </span>');
    var subBits = [];
    if (rs) subBits.push(esc(rs));
    if (src) subBits.push(esc(src));
    if (dt) subBits.push(esc(dt));
    var subLine = subBits.join(' · ');
    return '<div class="card" onclick="openLeadModal('+L.id+')" style="cursor:pointer">'
         + '<div style="display:flex;align-items:flex-start;gap:12px">'
         +   '<div style="width:40px;height:40px;border-radius:50%;background:'+col+'22;color:'+col+';display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;flex-shrink:0">'+esc(initials)+'</div>'
         +   '<div style="flex:1;min-width:0">'
         +     '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:2px">'
         +       '<div style="font-size:14px;font-weight:600;color:var(--text);min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+esc(nm)+'</div>'
         +       '<span class="' + pillCls + '">'+esc(st)+'</span>'
         +     '</div>'
         +     (subLine ? '<div style="font-size:12px;color:var(--text3);margin-top:2px">'+subLine+'</div>' : '')
         +     (contactRow ? '<div style="font-size:12px;color:var(--text3);margin-top:6px;display:flex;flex-wrap:wrap;gap:2px">'+contactRow+'</div>' : '')
         +   '</div>'
         + '</div></div>';
  }}).join('');
}}

function renderLeadKPIs() {{
  var totalEl = document.getElementById('lead-kpi-total');
  var activeEl = document.getElementById('lead-kpi-active');
  var convEl = document.getElementById('lead-kpi-conv');
  var convSubEl = document.getElementById('lead-kpi-conv-sub');
  if (!_leads.length) return;
  var openSet = ['New','Contacted','Appointment Set','Patient Seen'];
  var active = _leads.filter(function(L) {{ return openSet.indexOf(svJS(L.Status)) >= 0; }}).length;
  // Conversion last 30d: of leads created in window, what % are Converted
  var thirtyAgo = new Date(Date.now() - 30*86400000).toISOString().slice(0,10);
  var recent = _leads.filter(function(L) {{ return (L.Created || '').slice(0,10) >= thirtyAgo; }});
  var converted = recent.filter(function(L) {{ return svJS(L.Status) === 'Converted'; }}).length;
  var pct = recent.length ? Math.round(100 * converted / recent.length) : 0;
  if (totalEl)   totalEl.textContent = 'of ' + _leads.length + ' total';
  if (activeEl)  activeEl.textContent = active;
  if (convEl)    convEl.textContent = pct + '%';
  if (convSubEl) convSubEl.textContent = converted + ' of ' + recent.length + ' (30d)';
}}

// ── Data load ────────────────────────────────────────────────────────
async function loadLeads() {{
  try {{
    var rows = await fetchAll({T_LEADS});
    rows.sort(function(a, b) {{ return (b.Created || '').localeCompare(a.Created || ''); }});
    _leads = rows;
    renderLeadKPIs();
    applyFilters();
  }} catch (e) {{
    var box = document.getElementById('leads-list');
    if (box) {{
      box.innerHTML = '<div style="color:#ef4444;padding:20px;text-align:center">'
                    + 'Failed to load leads. '
                    + '<button onclick="loadLeads()" style="margin-left:8px;background:none;color:#3b82f6;'
                    + 'border:1px solid var(--border);border-radius:6px;padding:4px 10px;cursor:pointer">Retry</button></div>';
    }}
  }}
}}

async function loadEvents() {{
  _events = await fetchAll({T_EVENTS});
  _events.sort(function(a, b) {{ return (b['Event Date']||'').localeCompare(a['Event Date']||''); }});
  var sel = document.getElementById('lf-event');
  if (!sel) return;
  // Clear any prior options past index 0 (the placeholder)
  while (sel.options.length > 1) sel.remove(1);
  _events.forEach(function(e) {{
    var name = e['Name'] || '(unnamed)';
    var date = e['Event Date'] || '';
    var status = e['Event Status'];
    if (typeof status === 'object' && status) status = status.value || '';
    var opt = document.createElement('option');
    opt.value = e.id;
    opt.textContent = name + (date ? ' (' + date + ')' : '') + (status ? ' - ' + status : '');
    sel.appendChild(opt);
  }});
}}

async function loadCompanies() {{
  try {{
    var rows = await fetchAll({T_COMPANIES});
    var dl = document.getElementById('lf-company-list');
    if (!dl) return;
    dl.innerHTML = '';
    rows.sort(function(a, b) {{ return (a.Name || '').localeCompare(b.Name || ''); }});
    rows.forEach(function(c) {{
      if (!c.Name) return;
      _COMPANIES_LOOKUP[c.Name.trim().toLowerCase()] = c.id;
      var opt = document.createElement('option');
      opt.value = c.Name;
      dl.appendChild(opt);
    }});
  }} catch (e) {{
    // Non-fatal: form still works without company linking
  }}
}}

function resolveCompanyId(input) {{
  var name = (input || '').trim().toLowerCase();
  if (!name) return null;
  return _COMPANIES_LOOKUP[name] || null;
}}

// Wire the company-autocomplete hint once at init.
(function() {{
  var inp = document.getElementById('lf-company');
  var hint = document.getElementById('lf-company-hint');
  if (!inp || !hint) return;
  inp.addEventListener('input', function() {{
    var v = inp.value.trim();
    if (!v) {{ hint.textContent = ''; hint.style.color = 'var(--text3)'; return; }}
    var id = resolveCompanyId(v);
    if (id) {{
      hint.style.color = '#059669';
      hint.textContent = '✓ Match found — this lead will be linked to the company.';
    }} else {{
      hint.style.color = 'var(--text3)';
      hint.textContent = 'No exact match (will be saved as free-text source).';
    }}
  }});
}})();

// ── Capture modal open/close + submit ───────────────────────────────
function openCaptureModal() {{
  resetCaptureForm();
  document.getElementById('capture-modal-bg').style.display = 'flex';
  document.body.style.overflow = 'hidden';
  setTimeout(function() {{
    var nm = document.getElementById('lf-name');
    if (nm) nm.focus();
  }}, 50);
}}

function closeCaptureModal() {{
  document.getElementById('capture-modal-bg').style.display = 'none';
  document.body.style.overflow = '';
}}

function resetCaptureForm() {{
  ['lf-name','lf-phone','lf-email','lf-service','lf-event','lf-company','lf-notes'].forEach(function(id) {{
    var el = document.getElementById(id);
    if (el) el.value = '';
  }});
  var st = document.getElementById('lf-status'); if (st) st.textContent = '';
  var hint = document.getElementById('lf-company-hint'); if (hint) hint.textContent = '';
  var btn = document.getElementById('lf-submit');
  if (btn) {{ btn.disabled = false; btn.textContent = 'Submit Lead'; }}
}}

async function submitLead() {{
  var name = (document.getElementById('lf-name').value || '').trim();
  var phone = (document.getElementById('lf-phone').value || '').trim();
  var email = (document.getElementById('lf-email').value || '').trim();
  var service = document.getElementById('lf-service').value;
  var eventId = document.getElementById('lf-event').value;
  var notes = (document.getElementById('lf-notes').value || '').trim();
  var st = document.getElementById('lf-status');
  var btn = document.getElementById('lf-submit');

  if (!name || !phone) {{
    st.style.color = '#ef4444'; st.textContent = 'Name and phone are required'; return;
  }}
  if (!service) {{
    st.style.color = '#ef4444'; st.textContent = 'Please select a service'; return;
  }}

  btn.disabled = true; btn.textContent = 'Saving…';
  st.textContent = '';

  var companyName = (document.getElementById('lf-company').value || '').trim();
  var companyId   = resolveCompanyId(companyName);
  try {{
    var r = await fetch('/api/leads/capture', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        name: name, phone: phone, email: email, service: service,
        event_id: eventId ? parseInt(eventId) : null,
        notes: notes,
        company_id: companyId || null,
      }})
    }});
    var d = await r.json();
    if (d.ok) {{
      closeCaptureModal();
      // Briefly flash a success message at the top of the list
      var box = document.getElementById('leads-list');
      if (box) {{
        var toast = document.createElement('div');
        toast.textContent = '✅ Lead captured';
        toast.style.cssText = 'background:#05966922;color:#059669;padding:10px;border-radius:8px;'
                            + 'text-align:center;font-weight:600;margin-bottom:10px;font-size:13px';
        box.parentNode.insertBefore(toast, box);
        setTimeout(function() {{ toast.remove(); }}, 2500);
      }}
      await loadLeads();
    }} else {{
      st.style.color = '#ef4444';
      st.textContent = 'Failed: ' + (d.error || 'unknown');
      btn.disabled = false; btn.textContent = 'Submit Lead';
    }}
  }} catch (e) {{
    st.style.color = '#ef4444';
    st.textContent = 'Error: ' + e.message;
    btn.disabled = false; btn.textContent = 'Submit Lead';
  }}
}}

// After a detail-modal save, refresh the list so edits show.
window._afterLeadSave = loadLeads;

// ── Init ────────────────────────────────────────────────────────────
renderStatusChips();
loadLeads();
loadEvents();
loadCompanies();
"""
    script_js = js + LEAD_MODAL_JS
    return _mobile_page('m_lead', 'Leads', body, script_js, br, bt, user=user)




def _mobile_log_page(br: str, bt: str, user: dict = None) -> str:
    user = user or {}
    user_name = user.get('name', '')
    body = (
        '<div class="mobile-hdr">'
        '<div><div class="mobile-hdr-title">Log Activity</div>'
        '<div class="mobile-hdr-sub">Select a form to get started</div></div>'
        '<button class="m-hamburger" onclick="openMDrawer()" aria-label="Menu">☰</button>'
        '</div>'
        '<div class="mobile-body">'
        # Cards (single-column on mobile via CSS)
        '<div class="gfr-grid" style="margin-top:4px">'
        '<div class="gfr-card" onclick="openGFRForm(\'Business Outreach Log\')">'
        '<div class="gfr-card-icon">\U0001f3e2</div>'
        '<div class="gfr-card-name">Business Outreach Log</div>'
        '<div class="gfr-card-desc">Door-to-door visit, massage box placement, and program interest</div>'
        '<div class="gfr-card-cta">Open →</div></div>'
        '<div class="gfr-card" onclick="openGFRForm(\'External Event\')">'
        '<div class="gfr-card-icon">\U0001f3aa</div>'
        '<div class="gfr-card-name">External Event</div>'
        '<div class="gfr-card-desc">Pre-event planning and community event demographic intel</div>'
        '<div class="gfr-card-cta">Open →</div></div>'
        '<div class="gfr-card" onclick="openGFRForm(\'Mobile Massage Service\')">'
        '<div class="gfr-card-icon">\U0001f486</div>'
        '<div class="gfr-card-name">Mobile Massage Service</div>'
        '<div class="gfr-card-desc">Book a mobile chair or table massage at a company or event</div>'
        '<div class="gfr-card-cta">Open →</div></div>'
        '<div class="gfr-card" onclick="openGFRForm(\'Lunch and Learn\')">'
        '<div class="gfr-card-icon">\U0001f37d️</div>'
        '<div class="gfr-card-name">Lunch and Learn</div>'
        '<div class="gfr-card-desc">Schedule a chiropractic L&amp;L presentation for company staff</div>'
        '<div class="gfr-card-cta">Open →</div></div>'
        '<div class="gfr-card" onclick="openGFRForm(\'Health Assessment Screening\')">'
        '<div class="gfr-card-icon">\U0001fa7a</div>'
        '<div class="gfr-card-name">Health Assessment Screening</div>'
        '<div class="gfr-card-desc">Book a chiropractic health screening event for staff</div>'
        '<div class="gfr-card-cta">Open →</div></div>'
        '</div>'
        '</div>'
    )
    script_js = f"const GFR_USER={repr(user_name)};\nconst TOOL = {{venuesT: {T_GOR_VENUES}}};\n"
    return _mobile_page('m_log', 'Log Activity', body, script_js, br, bt, user=user,
                         extra_html=GFR_EXTRA_HTML, extra_js=GFR_EXTRA_JS)
