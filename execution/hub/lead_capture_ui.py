"""Shared Capture Lead overlay — HTML + JS bundle used by both the route
stop sheet (execution/field_rep/pages/route.py) and the mobile business
profile page (execution/field_rep/pages/company.py).

Why this module exists: both surfaces render the same modal with the same
field set and POST to the same /api/leads/capture endpoint. Previously the
overlay lived inline in route.py with state coupled to _rCurrentStop. This
module decouples it: callers pass the business name explicitly to
openLeadCapture(prefillCompany) instead of the JS reading a page-specific
variable.

Call path:
  1. Render LEAD_CAPTURE_HTML alongside other extra_html (inside the
     _mobile_page() wrapper — the overlay is position:fixed so it needs
     to escape the mobile-wrap stacking context).
  2. Inject build_lead_capture_js(t_events, t_companies) into extra_js.
  3. Call openLeadCapture(bizName) from a click handler; closeLeadCapture()
     is available for a programmatic close.
"""

from .constants import T_COMPANIES, T_EVENTS


LEAD_CAPTURE_HTML = (
    '<div class="gfr-overlay" id="gfr-form-lead" onclick="if(event.target===this)closeLeadCapture()">'
    '<div class="gfr-modal gfr-form-modal">'
    '<div class="gfr-hdr">'
    '<span class="gfr-hdr-title">\U0001f4cb Capture Lead</span>'
    '<span class="gfr-hdr-user" id="gfr-user-lead"></span>'
    '<button class="gfr-close" onclick="closeLeadCapture()">&#xd7;</button>'
    '</div>'
    '<div class="gfr-form-body">'
    '<div id="lf2-biz-hint" style="font-size:12px;color:var(--text3);margin:10px 0 12px;padding:8px 10px;background:var(--bg);border-radius:7px;border:1px solid var(--border);display:none"></div>'
    '<div class="gfr-field"><label class="gfr-label">Name <span class="req">*</span></label>'
    '<input type="text" class="gfr-input" id="lf2-name" placeholder="Full name"></div>'
    '<div class="gfr-field"><label class="gfr-label">Phone <span class="req">*</span></label>'
    '<input type="tel" class="gfr-input" id="lf2-phone" placeholder="(555) 123-4567"></div>'
    '<div class="gfr-field"><label class="gfr-label">Email</label>'
    '<input type="email" class="gfr-input" id="lf2-email" placeholder="email@example.com"></div>'
    '<div class="gfr-field"><label class="gfr-label">Service Interested <span class="req">*</span></label>'
    '<select class="gfr-select" id="lf2-service">'
    '<option value="">Select a service…</option>'
    '<option>Chiropractic Care</option><option>Massage Therapy</option>'
    '<option>Health Screening</option><option>Injury Rehab</option><option>Other</option>'
    '</select></div>'
    '<div class="gfr-field"><label class="gfr-label">Event / Source</label>'
    '<select class="gfr-select" id="lf2-event">'
    '<option value="">No event (walk-in / field)</option>'
    '</select></div>'
    '<div class="gfr-field"><label class="gfr-label">Referred from company</label>'
    '<input type="text" class="gfr-input" id="lf2-company" list="lf2-company-list" placeholder="Business name">'
    '<datalist id="lf2-company-list"></datalist>'
    '<div id="lf2-company-hint" style="font-size:11px;color:var(--text3);margin-top:4px;min-height:14px"></div>'
    '</div>'
    '<div class="gfr-field"><label class="gfr-label">Notes</label>'
    '<textarea class="gfr-textarea" id="lf2-notes" rows="3" placeholder="Additional details…"></textarea></div>'
    '<div id="lf2-status" style="font-size:12px;margin-top:6px;min-height:14px;text-align:center"></div>'
    '</div>'
    '<div class="gfr-footer">'
    '<span class="gfr-spacer"></span>'
    '<button class="gfr-btn-cancel" onclick="closeLeadCapture()">Cancel</button>'
    '<button class="gfr-btn-submit" id="lf2-submit" onclick="submitLeadCapture()">Submit Lead</button>'
    '</div>'
    '</div></div>'
)


def build_lead_capture_js(
    t_events: int = T_EVENTS,
    t_companies: int = T_COMPANIES,
) -> str:
    """Returns the JS for the Capture Lead overlay, with the relevant
    Baserow table IDs substituted in. The JS depends on a global ``fetchAll``
    helper and a ``GFR_USER`` string constant — both already provided by the
    _mobile_page shell.

    Public functions exposed to the rest of the page:
      - openLeadCapture(prefillCompany)
      - closeLeadCapture()
      - submitLeadCapture()   (wired to the Submit button onclick)
    """
    return (
        "// ── Capture Lead (shared overlay) ───────────────────────────────────\n"
        "var _LEAD_COMPANIES = {};  // lower-cased company name -> id\n"
        "\n"
        "async function _loadLeadLookups() {\n"
        "  try {\n"
        f"    var evts = await fetchAll({int(t_events)});\n"
        "    evts.sort(function(a,b) { return (b['Event Date']||'').localeCompare(a['Event Date']||''); });\n"
        "    var sel = document.getElementById('lf2-event');\n"
        "    if (sel) {\n"
        "      evts.forEach(function(e) {\n"
        "        var nm = e['Name'] || '(unnamed)';\n"
        "        var dt = e['Event Date'] || '';\n"
        "        var st = e['Event Status'];\n"
        "        if (typeof st === 'object' && st) st = st.value || '';\n"
        "        var opt = document.createElement('option');\n"
        "        opt.value = e.id;\n"
        "        opt.textContent = nm + (dt ? ' (' + dt + ')' : '') + (st ? ' - ' + st : '');\n"
        "        sel.appendChild(opt);\n"
        "      });\n"
        "    }\n"
        "  } catch(e) { /* non-fatal */ }\n"
        "  try {\n"
        f"    var rows = await fetchAll({int(t_companies)});\n"
        "    var dl = document.getElementById('lf2-company-list');\n"
        "    rows.sort(function(a, b) { return (a.Name || '').localeCompare(b.Name || ''); });\n"
        "    rows.forEach(function(c) {\n"
        "      if (!c.Name) return;\n"
        "      _LEAD_COMPANIES[c.Name.trim().toLowerCase()] = c.id;\n"
        "      var opt = document.createElement('option');\n"
        "      opt.value = c.Name;\n"
        "      if (dl) dl.appendChild(opt);\n"
        "    });\n"
        "  } catch(e) { /* non-fatal */ }\n"
        "}\n"
        "\n"
        "function _leadResolveCompanyId(name) {\n"
        "  name = (name || '').trim().toLowerCase();\n"
        "  return name ? (_LEAD_COMPANIES[name] || null) : null;\n"
        "}\n"
        "\n"
        "// Wire the company-name hint (match / no-match) once the element is present\n"
        "(function() {\n"
        "  var tries = 0;\n"
        "  var iv = setInterval(function() {\n"
        "    var inp = document.getElementById('lf2-company');\n"
        "    var hint = document.getElementById('lf2-company-hint');\n"
        "    if (!inp || !hint) { if (++tries > 40) clearInterval(iv); return; }\n"
        "    clearInterval(iv);\n"
        "    inp.addEventListener('input', function() {\n"
        "      var v = inp.value.trim();\n"
        "      if (!v) { hint.textContent = ''; return; }\n"
        "      var id = _leadResolveCompanyId(v);\n"
        "      if (id) {\n"
        "        hint.style.color = '#059669';\n"
        "        hint.textContent = '✓ Match found — this lead will be linked to the company.';\n"
        "      } else {\n"
        "        hint.style.color = 'var(--text3)';\n"
        "        hint.textContent = 'No exact match (saved as free-text source).';\n"
        "      }\n"
        "    });\n"
        "  }, 100);\n"
        "})();\n"
        "\n"
        "// Opens the overlay with fields cleared and the Referred-From pre-filled.\n"
        "// prefillCompany is a plain string (the business name); pass '' to skip prefill.\n"
        "function openLeadCapture(prefillCompany) {\n"
        "  var bizName = String(prefillCompany || '');\n"
        "  ['lf2-name','lf2-phone','lf2-email','lf2-notes'].forEach(function(id) {\n"
        "    var el = document.getElementById(id); if (el) el.value = '';\n"
        "  });\n"
        "  ['lf2-service','lf2-event'].forEach(function(id) {\n"
        "    var el = document.getElementById(id); if (el) el.selectedIndex = 0;\n"
        "  });\n"
        "  var st = document.getElementById('lf2-status'); if (st) st.textContent = '';\n"
        "  var btn = document.getElementById('lf2-submit');\n"
        "  if (btn) { btn.disabled = false; btn.textContent = 'Submit Lead'; }\n"
        "  var compInp = document.getElementById('lf2-company');\n"
        "  if (compInp) {\n"
        "    compInp.value = bizName;\n"
        "    compInp.dispatchEvent(new Event('input'));\n"
        "  }\n"
        "  var hintBar = document.getElementById('lf2-biz-hint');\n"
        "  if (hintBar) {\n"
        "    if (bizName) {\n"
        "      hintBar.style.display = 'block';\n"
        "      hintBar.textContent = 'Capturing a lead from: ' + bizName;\n"
        "    } else {\n"
        "      hintBar.style.display = 'none';\n"
        "      hintBar.textContent = '';\n"
        "    }\n"
        "  }\n"
        "  var userLbl = document.getElementById('gfr-user-lead');\n"
        "  if (userLbl && typeof GFR_USER !== 'undefined') userLbl.textContent = GFR_USER;\n"
        "  setTimeout(function() {\n"
        "    var ov = document.getElementById('gfr-form-lead');\n"
        "    if (ov) ov.classList.add('open');\n"
        "  }, 120);\n"
        "}\n"
        "\n"
        "function closeLeadCapture() {\n"
        "  var el = document.getElementById('gfr-form-lead');\n"
        "  if (el) el.classList.remove('open');\n"
        "}\n"
        "\n"
        "async function submitLeadCapture() {\n"
        "  var name    = (document.getElementById('lf2-name').value    || '').trim();\n"
        "  var phone   = (document.getElementById('lf2-phone').value   || '').trim();\n"
        "  var email   = (document.getElementById('lf2-email').value   || '').trim();\n"
        "  var service = document.getElementById('lf2-service').value;\n"
        "  var eventId = document.getElementById('lf2-event').value;\n"
        "  var notes   = (document.getElementById('lf2-notes').value   || '').trim();\n"
        "  var compNm  = (document.getElementById('lf2-company').value || '').trim();\n"
        "  var st = document.getElementById('lf2-status');\n"
        "  var btn = document.getElementById('lf2-submit');\n"
        "  if (!name || !phone) {\n"
        "    st.style.color = '#ef4444'; st.textContent = 'Name and phone are required'; return;\n"
        "  }\n"
        "  if (!service) {\n"
        "    st.style.color = '#ef4444'; st.textContent = 'Please select a service'; return;\n"
        "  }\n"
        "  btn.disabled = true; btn.textContent = 'Saving…';\n"
        "  st.textContent = '';\n"
        "  try {\n"
        "    var r = await fetch('/api/leads/capture', {\n"
        "      method: 'POST',\n"
        "      headers: {'Content-Type':'application/json'},\n"
        "      body: JSON.stringify({\n"
        "        name: name, phone: phone, email: email,\n"
        "        service: service,\n"
        "        event_id: eventId ? parseInt(eventId) : null,\n"
        "        notes: notes,\n"
        "        company_id: _leadResolveCompanyId(compNm),\n"
        "      })\n"
        "    });\n"
        "    var d = await r.json();\n"
        "    if (d.ok) {\n"
        "      st.style.color = '#059669';\n"
        "      st.textContent = '✓ Lead captured!';\n"
        "      setTimeout(closeLeadCapture, 1100);\n"
        "    } else {\n"
        "      st.style.color = '#ef4444';\n"
        "      st.textContent = 'Failed: ' + (d.error || 'unknown');\n"
        "      btn.disabled = false; btn.textContent = 'Submit Lead';\n"
        "    }\n"
        "  } catch(e) {\n"
        "    st.style.color = '#ef4444';\n"
        "    st.textContent = 'Error: ' + e.message;\n"
        "    btn.disabled = false; btn.textContent = 'Submit Lead';\n"
        "  }\n"
        "}\n"
        "\n"
        "_loadLeadLookups();\n"
    )
