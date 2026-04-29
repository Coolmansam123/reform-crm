"""
Page shells for the Reform Operations Hub.
- `_page`: full desktop page (CSS + nav + compose FAB + theme toggle)
- `_forbidden_page`: 403 for users lacking hub access
- `_mobile_page`: lightweight /m page with bottom nav
- `_tool_page`: shared pipeline dashboard used by attorney / gorilla / community
"""

from .access import _is_admin
from .compose import _COMPOSE_HTML, _COMPOSE_JS
from .constants import (
    T_ATT_ACTS, T_ATT_VENUES, T_COM_ACTS, T_COM_VENUES,
    T_GOR_ACTS, T_GOR_BOXES, T_GOR_VENUES,
)
from .nav import _topnav
from .styles import _CSS, _JS_SHARED


# ─── Page shell ────────────────────────────────────────────────────────────────
def _page(active: str, title: str, header_html: str, body_html: str,
          script_js: str, br: str, bt: str, user: dict = None) -> str:
    shared = _JS_SHARED.format(br=br, bt=bt)
    user = user or {}
    admin = _is_admin(user)
    role_css = '' if admin else '.admin-only{display:none!important}'
    role_js = f'var IS_ADMIN = {"true" if admin else "false"};'
    return (
        '<!DOCTYPE html><html lang="en">'
        '<head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{title} \u2014 Reform Hub</title>'
        f'<style>{_CSS}\n{role_css}</style>'
        '<script>(function(){{'
        'var t=localStorage.getItem("hub-theme");'
        'if(t==="light"){{document.documentElement.setAttribute("data-theme","light");'
        'var ic=document.getElementById("theme-icon");if(ic)ic.textContent="\u2600\ufe0f";}}'
        '}})()</script>'
        '</head><body>'
        + _topnav(active, user)
        + '<div class="main">'
        + header_html
        + '<div class="content">'
        + body_html
        + '</div></div>'
        + _COMPOSE_HTML
        + '<script>'
        'function toggleTheme(){'
        'var d=document.documentElement;'
        'var cur=d.getAttribute("data-theme");'
        'var t=cur==="light"?"dark":"light";'
        'd.setAttribute("data-theme",t==="dark"?"":"light");'
        'var ic=document.getElementById("theme-icon");'
        'if(ic)ic.textContent=t==="light"?"\u2600\ufe0f":"\U0001f319";'
        'localStorage.setItem("hub-theme",t);}'
        'function openDrawer(){'
        'document.getElementById("drawer-nav").classList.add("open");'
        'document.getElementById("drawer-backdrop").classList.add("open");}'
        'function closeDrawer(){'
        'document.getElementById("drawer-nav").classList.remove("open");'
        'document.getElementById("drawer-backdrop").classList.remove("open");}'
        f'</script>'
        + f'<script>{role_js}\n{shared}\n{_COMPOSE_JS}\n{script_js}</script>'
        '</body></html>'
    )

def _forbidden_page(br: str, bt: str, user: dict = None) -> str:
    """403 page shown when user lacks hub access."""
    header = (
        '<div class="header"><div class="header-left">'
        '<h1>Access Restricted</h1>'
        '<div class="sub">You don\'t have permission to view this section</div>'
        '</div></div>'
    )
    body = (
        '<div style="display:flex;flex-direction:column;align-items:center;'
        'justify-content:center;padding:80px 20px;text-align:center">'
        '<div style="font-size:48px;margin-bottom:16px">\U0001f512</div>'
        '<div style="font-size:16px;font-weight:700;margin-bottom:8px;color:var(--text)">'
        'This section is not available to your account</div>'
        '<div style="font-size:13px;color:var(--text3);max-width:400px;line-height:1.6">'
        'Your administrator has not granted you access to this area. '
        'Contact your admin to request access.</div>'
        '<a href="/" style="margin-top:20px;color:#3b82f6;font-size:13px;'
        'font-weight:600;text-decoration:none">\u2190 Back to Dashboard</a>'
        '</div>'
    )
    return _page('', 'Access Restricted', header, body, '', br, bt, user=user)


# ─── Mobile page shell ────────────────────────────────────────────────────────────
def _build_mobile_drawer(active: str, user: dict) -> str:
    """Slide-out drawer for the routes mobile app. Mirrors the hub's tnav-drawer
    pattern but slides in from the left. Admin-only items are gated."""
    admin = _is_admin(user)

    def link(aid: str, label: str, href: str, grp: bool = False) -> str:
        cls_parts = []
        if grp:
            cls_parts.append('tnav-grp-lbl')
        if aid and aid == active:
            cls_parts.append('active')
        cls = f' class="{" ".join(cls_parts)}"' if cls_parts else ''
        return f'<a href="{href}"{cls}>{label}</a>'

    sep = '<div class="tnav-sep"></div>'
    items = (
        link('m_home',         '🏠 Dashboard',         '/',              grp=True)
        + link('m_routes',     '🗺️ Routes',       '/routes',        grp=True)
        + link('m_outreach',   '📋 To Do',              '/todo',          grp=True)
        + link('m_lead',       '🎯 Leads',              '/lead',          grp=True)
        + link('m_events',     '📅 Events',             '/events',        grp=True)
        + link('m_directory',  '📇 All Companies',      '/directory',     grp=True)
        + (link('m_recent',    '⏱️ Recent Activity',  '/recent',        grp=True) if admin else '')
        + sep
        + '<a href="#" onclick="enableNotifications();return false;">🔔 Enable Notifications</a>'
        + '<a href="https://hub.reformchiropractic.app">💻 Full Hub</a>'
        '<a href="/logout" style="color:var(--text3)">Sign Out</a>'
    )
    return (
        '<div class="m-drawer-backdrop" id="m-drawer-backdrop" onclick="closeMDrawer()"></div>'
        '<div class="m-drawer" id="m-drawer">'
        '<div class="m-drawer-hdr">'
        '<span class="tnav-logo">✦ Reform</span>'
        '<button class="tnav-drawer-close" onclick="closeMDrawer()">✕</button>'
        '</div>'
        + items
        + '</div>'
    )


def _mobile_page(active: str, title: str, body_html: str, script_js: str,
                 br: str, bt: str, user: dict = None, wrap_cls: str = '',
                 extra_html: str = '', extra_js: str = '') -> str:
    """Page shell for the routes mobile app. Hamburger + slide-out drawer. Light only (outdoor use)."""
    shared = _JS_SHARED.format(br=br, bt=bt)
    user = user or {}
    drawer = _build_mobile_drawer(active, user)
    wrap_class = f'mobile-wrap {wrap_cls}'.strip()
    return (
        '<!DOCTYPE html><html lang="en" data-theme="light">'
        '<head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,viewport-fit=cover">'
        # ── PWA: manifest + iOS standalone hints + service-worker scope ──
        '<link rel="manifest" href="/manifest.json">'
        '<meta name="theme-color" content="#ea580c">'
        '<meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
        '<meta name="apple-mobile-web-app-title" content="Reform">'
        '<link rel="apple-touch-icon" href="/static/icon-192.png">'
        f'<title>{title} — Reform</title>'
        f'<style>{_CSS}</style>'
        '</head><body>'
        + drawer
        + f'<div class="{wrap_class}">'
        + body_html
        + '</div>'
        + extra_html
        + f'<script>{shared}\n{extra_js}\n{script_js}\n'
        'function openMDrawer(){'
        'document.getElementById("m-drawer").classList.add("open");'
        'document.getElementById("m-drawer-backdrop").classList.add("open");}'
        'function closeMDrawer(){'
        'document.getElementById("m-drawer").classList.remove("open");'
        'document.getElementById("m-drawer-backdrop").classList.remove("open");}'
        # ── Phone auto-format ──────────────────────────────────────────────
        # Any input[type=tel] gets formatted to (XXX)XXX-XXXX as the rep types.
        # Uses event delegation so dynamically-added phone inputs (modals,
        # forms) pick this up without per-field wiring.
        'function formatPhone(input){'
        'var d=(input.value||"").replace(/\\D/g,"").slice(0,10);'
        'var f=d;'
        'if(d.length>6) f="("+d.slice(0,3)+")"+d.slice(3,6)+"-"+d.slice(6);'
        'else if(d.length>3) f="("+d.slice(0,3)+")"+d.slice(3);'
        'else if(d.length>0) f="("+d;'
        'input.value=f;}'
        'document.addEventListener("input",function(e){'
        'var t=e.target;'
        'if(t&&t.tagName==="INPUT"&&t.type==="tel") formatPhone(t);'
        '},true);'
        # ── Push notifications: register sw, expose enableNotifications() ──
        'if ("serviceWorker" in navigator) {'
        '  navigator.serviceWorker.register("/sw.js").catch(function(e){console.warn("sw register failed",e);});'
        '}'
        'function _b64urlToUint8(b64) {'
        '  var pad = "=".repeat((4 - b64.length % 4) % 4);'
        '  var s = (b64 + pad).replace(/-/g,"+").replace(/_/g,"/");'
        '  var raw = atob(s); var arr = new Uint8Array(raw.length);'
        '  for (var i=0;i<raw.length;i++) arr[i]=raw.charCodeAt(i);'
        '  return arr;'
        '}'
        'async function enableNotifications() {'
        '  try {'
        '    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {'
        '      alert("Push not supported on this browser. iOS users: Add to Home Screen first."); return;'
        '    }'
        '    var perm = await Notification.requestPermission();'
        '    if (perm !== "granted") { alert("Notifications blocked."); return; }'
        '    var keyResp = await fetch("/api/push/vapid-public-key");'
        '    if (!keyResp.ok) { alert("Push not configured (no VAPID key)"); return; }'
        '    var keyData = await keyResp.json();'
        '    var reg = await navigator.serviceWorker.ready;'
        '    var sub = await reg.pushManager.subscribe({'
        '      userVisibleOnly: true,'
        '      applicationServerKey: _b64urlToUint8(keyData.key),'
        '    });'
        '    var subJson = sub.toJSON();'
        '    var r = await fetch("/api/push/subscribe", {'
        '      method: "POST", headers: {"Content-Type":"application/json"},'
        '      body: JSON.stringify({endpoint: subJson.endpoint, keys: subJson.keys}),'
        '    });'
        '    if (r.ok) alert("Notifications enabled \\u2713"); else alert("Subscribe failed (" + r.status + ")");'
        '  } catch (e) { alert("Could not enable notifications: " + (e.message || e)); }'
        '}'
        '</script>'
        '</body></html>'
    )


# ─── Lead detail modal (shared across mobile pages) ──────────────────────────
# Host pages drop LEAD_MODAL_HTML into their body and concat LEAD_MODAL_JS onto
# their script body. After save, the modal calls window._afterLeadSave() if
# defined, so each host can wire its own list/refresh.
LEAD_MODAL_HTML = (
    '<div id="lead-modal-bg" onclick="if(event.target===this)closeLeadModal()" '
    'style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1100;'
    'align-items:flex-start;justify-content:center;padding:30px 14px;overflow-y:auto">'
    '<div style="background:var(--bg2);border:1px solid var(--border);border-radius:14px;'
    'width:100%;max-width:480px;padding:18px 20px calc(20px + env(safe-area-inset-bottom))">'
    '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">'
    '<h3 style="margin:0;color:var(--text);font-size:16px;flex:1">Lead</h3>'
    '<button onclick="closeLeadModal()" style="background:none;border:none;color:var(--text3);'
    'font-size:18px;cursor:pointer;padding:4px 8px">×</button>'
    '</div>'
    '<div id="lead-modal-body" style="font-size:13px;color:var(--text2)">Loading…</div>'
    '<div id="lead-modal-msg" style="font-size:12px;min-height:16px;margin-top:8px"></div>'
    '<div style="display:flex;gap:8px;justify-content:flex-end;margin-top:10px">'
    '<button onclick="closeLeadModal()" '
    'style="padding:9px 16px;background:none;border:1px solid var(--border);color:var(--text2);'
    'border-radius:6px;font-size:13px;cursor:pointer;font-family:inherit">Cancel</button>'
    '<button id="lead-modal-save" onclick="saveLeadModal()" '
    'style="padding:9px 20px;background:#059669;border:none;color:#fff;border-radius:6px;'
    'font-size:13px;font-weight:700;cursor:pointer;font-family:inherit">Save</button>'
    '</div>'
    '</div>'
    '</div>'
)

# Plain string (single braces) — host pages concat AFTER their f-string JS
# bodies so they don't need to escape every `{` to `{{`.
LEAD_MODAL_JS = r"""
// ── Lead detail modal (shared) ──────────────────────────────────────────
let _leadModalId = null;

async function openLeadModal(leadId) {
  _leadModalId = leadId;
  document.getElementById('lead-modal-msg').textContent = '';
  document.getElementById('lead-modal-body').textContent = 'Loading…';
  document.getElementById('lead-modal-bg').style.display = 'flex';
  document.body.style.overflow = 'hidden';
  try {
    var r = await fetch('/api/leads/' + leadId);
    if (!r.ok) {
      document.getElementById('lead-modal-body').innerHTML =
        '<div style="color:#ef4444">Failed to load lead (HTTP ' + r.status + ')</div>';
      return;
    }
    var L = await r.json();
    var stages = ['New','Contacted','Appointment Set','Patient Seen','Converted','Dropped'];
    var st = (L.Status && L.Status.value) || L.Status || 'New';
    var rs = (L.Reason && L.Reason.value) || L.Reason || '';
    function row(label, html) {
      return '<div style="margin-bottom:10px">'
        + '<label style="display:block;font-size:10px;font-weight:700;color:var(--text3);'
        + 'text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px">' + esc(label) + '</label>'
        + html + '</div>';
    }
    var inputCss = 'width:100%;padding:9px;background:var(--bg);border:1px solid var(--border);'
                 + 'color:var(--text);border-radius:6px;font-size:13px;font-family:inherit';
    var stageOpts = stages.map(function(s){
      return '<option value="' + esc(s) + '"' + (s === st ? ' selected' : '') + '>' + esc(s) + '</option>';
    }).join('');
    var html = ''
      + row('Name', '<input type="text" id="lm-name" style="' + inputCss + '" value="' + esc(L.Name || '') + '">')
      + row('Phone', '<input type="tel" id="lm-phone" style="' + inputCss + '" value="' + esc(L.Phone || '') + '">')
      + row('Email', '<input type="email" id="lm-email" style="' + inputCss + '" value="' + esc(L.Email || '') + '">')
      + row('Status', '<select id="lm-status" style="' + inputCss + '">' + stageOpts + '</select>')
      + row('Reason / Service', '<input type="text" id="lm-reason" style="' + inputCss + '" value="' + esc(rs) + '">')
      + row('Source', '<input type="text" id="lm-source" style="' + inputCss + ';opacity:.7" value="' + esc(L.Source || '') + '" readonly>')
      + row('Follow-Up Date', '<input type="date" id="lm-fu" style="' + inputCss + '" value="' + esc((L['Follow-Up Date'] || '').slice(0,10)) + '">')
      + row('Notes', '<textarea id="lm-notes" rows="3" style="' + inputCss + ';resize:vertical">' + esc(L.Notes || '') + '</textarea>')
      + '<div style="font-size:11px;color:var(--text3);margin-top:6px">Created: ' + esc((L.Created || '').slice(0,10) || '—')
      + (L.Owner ? ' · Owner: ' + esc(L.Owner) : '') + '</div>';
    document.getElementById('lead-modal-body').innerHTML = html;
    var phEl = document.getElementById('lm-phone');
    if (phEl && typeof formatPhone === 'function') formatPhone(phEl);
  } catch (e) {
    document.getElementById('lead-modal-body').innerHTML =
      '<div style="color:#ef4444">Network error: ' + esc(e.message || e) + '</div>';
  }
}

function closeLeadModal() {
  document.getElementById('lead-modal-bg').style.display = 'none';
  document.body.style.overflow = '';
  _leadModalId = null;
}

async function saveLeadModal() {
  if (!_leadModalId) return;
  var msg = document.getElementById('lead-modal-msg');
  var btn = document.getElementById('lead-modal-save');
  msg.textContent = '';
  btn.disabled = true; btn.textContent = 'Saving…';
  var get = function(id) { var el = document.getElementById(id); return el ? el.value.trim() : ''; };
  var payload = {
    'Name':   get('lm-name'),
    'Phone':  get('lm-phone'),
    'Email':  get('lm-email'),
    'Status': get('lm-status'),
    'Reason': get('lm-reason'),
    'Notes':  get('lm-notes'),
  };
  var fu = get('lm-fu');
  payload['Follow-Up Date'] = fu || null;
  try {
    var r = await fetch('/api/leads/' + _leadModalId, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      var err = '';
      try { err = (await r.json()).error || ''; } catch (e) {}
      msg.style.color = '#ef4444';
      msg.textContent = 'Save failed: ' + (err || ('HTTP ' + r.status));
      btn.disabled = false; btn.textContent = 'Save';
      return;
    }
    msg.style.color = '#059669';
    msg.textContent = 'Saved ✓';
    setTimeout(function() {
      closeLeadModal();
      if (typeof window._afterLeadSave === 'function') window._afterLeadSave();
    }, 600);
  } catch (e) {
    msg.style.color = '#ef4444';
    msg.textContent = 'Network error';
    btn.disabled = false; btn.textContent = 'Save';
  }
}
"""


# ─── Log Activity modal (shared across mobile pages) ─────────────────────────
# Used by both the company profile page and the route stop's Check-In flow.
# Submits to /api/companies/{id}/activities — host page provides company_id
# either via a top-level `COMPANY_ID` const (company profile) or by passing
# `{company_id, business_name}` to openLogModal() (route Check-In). After
# save the modal calls window._afterLogActivitySave() if defined.
LOG_ACTIVITY_MODAL_HTML = (
    '<div id="cd-modal-bg" onclick="if(event.target===this)closeLogModal()" '
    'style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:900;'
    'align-items:flex-start;justify-content:center;padding:40px 16px;overflow-y:auto">'
    '<div style="background:var(--bg2);border:1px solid var(--border);border-radius:14px;'
    'width:100%;max-width:480px;padding:20px">'
    '<h3 id="cd-modal-title" style="margin:0 0 14px;color:var(--text);font-size:16px">Log activity</h3>'
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
    'text-transform:uppercase;margin-bottom:4px;letter-spacing:.4px">How did it go?</label>'
    '<div id="cd-sentiment-row" style="display:flex;gap:6px;margin-bottom:12px">'
    '<button type="button" data-sent="Green"  onclick="setSentiment(\'Green\')"  '
    'style="flex:1;padding:8px;background:var(--bg);border:1px solid var(--border);'
    'color:var(--text);border-radius:6px;font-size:13px;cursor:pointer;font-family:inherit">🟢 Good</button>'
    '<button type="button" data-sent="Yellow" onclick="setSentiment(\'Yellow\')" '
    'style="flex:1;padding:8px;background:var(--bg);border:1px solid var(--border);'
    'color:var(--text);border-radius:6px;font-size:13px;cursor:pointer;font-family:inherit">🟡 Mixed</button>'
    '<button type="button" data-sent="Red"    onclick="setSentiment(\'Red\')"    '
    'style="flex:1;padding:8px;background:var(--bg);border:1px solid var(--border);'
    'color:var(--text);border-radius:6px;font-size:13px;cursor:pointer;font-family:inherit">🔴 Bad</button>'
    '</div>'
    '<label style="display:block;font-size:11px;font-weight:700;color:var(--text3);'
    'text-transform:uppercase;margin-bottom:4px;letter-spacing:.4px">Voice note (optional)</label>'
    '<div id="cd-voice-row" style="margin-bottom:12px">'
    '<button type="button" id="cd-voice-btn" onclick="toggleVoiceNote()" '
    'style="display:inline-flex;align-items:center;gap:6px;padding:8px 12px;background:var(--bg);'
    'border:1px solid var(--border);color:var(--text2);border-radius:6px;font-size:13px;cursor:pointer;font-family:inherit">'
    '🎤 Record</button>'
    '<span id="cd-voice-st" style="margin-left:8px;font-size:11px;color:var(--text3)"></span>'
    '<div id="cd-voice-preview" style="display:none;margin-top:8px">'
    '<audio id="cd-voice-audio" controls style="width:100%;height:36px"></audio>'
    '<button type="button" onclick="clearVoiceNote()" '
    'style="margin-top:4px;padding:4px 10px;background:none;border:1px solid var(--border);'
    'color:var(--text3);border-radius:6px;font-size:11px;cursor:pointer">Discard</button>'
    '</div>'
    '</div>'
    '<label style="display:block;font-size:11px;font-weight:700;color:var(--text3);'
    'text-transform:uppercase;margin-bottom:4px;letter-spacing:.4px">Photo (optional)</label>'
    '<div id="cd-photo-row" style="margin-bottom:12px">'
    '<label for="cd-photo-input" id="cd-photo-pick" '
    'style="display:inline-flex;align-items:center;gap:6px;padding:8px 12px;background:var(--bg);'
    'border:1px solid var(--border);color:var(--text2);border-radius:6px;font-size:13px;cursor:pointer">'
    '📷 Add photo</label>'
    '<input type="file" id="cd-photo-input" accept="image/*" capture="environment" '
    'onchange="onPhotoPicked(event)" style="display:none">'
    '<div id="cd-photo-preview" style="display:none;margin-top:8px;position:relative">'
    '<img id="cd-photo-img" style="max-width:100%;max-height:160px;border-radius:6px;border:1px solid var(--border)">'
    '<button type="button" onclick="clearPhoto()" '
    'style="position:absolute;top:4px;right:4px;background:rgba(0,0,0,.6);color:#fff;border:none;'
    'border-radius:50%;width:24px;height:24px;font-size:14px;cursor:pointer;line-height:1">×</button>'
    '</div>'
    '</div>'
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

LOG_ACTIVITY_MODAL_JS = r"""
// ── Log Activity modal (shared) ──────────────────────────────────────────
// Voice notes (MediaRecorder + Whisper)
let _cdVoiceRecorder = null;
let _cdVoiceChunks = [];
let _cdVoiceBlob = null;
let _cdVoiceUrl = '';
let _cdVoiceTranscript = '';
let _cdVoiceTimer = null;
let _cdVoiceStartedAt = 0;
const _CD_VOICE_MAX_MS = 90000;

let _cdSentiment = '';
let _cdPhotoFile = null;
let _logModalCompanyId = null;
const _SENT_COLORS = { Green: '#059669', Yellow: '#f59e0b', Red: '#ef4444' };

async function toggleVoiceNote() {
  var btn = document.getElementById('cd-voice-btn');
  var st  = document.getElementById('cd-voice-st');
  if (_cdVoiceRecorder && _cdVoiceRecorder.state === 'recording') {
    _cdVoiceRecorder.stop();
    return;
  }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    alert('Mic recording is not supported on this device/browser.');
    return;
  }
  try {
    var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    var mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus'
              : MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm'
              : MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : '';
    _cdVoiceRecorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    _cdVoiceChunks = [];
    _cdVoiceRecorder.ondataavailable = function(e) {
      if (e.data && e.data.size > 0) _cdVoiceChunks.push(e.data);
    };
    _cdVoiceRecorder.onstop = async function() {
      stream.getTracks().forEach(function(t) { t.stop(); });
      if (_cdVoiceTimer) { clearInterval(_cdVoiceTimer); _cdVoiceTimer = null; }
      _cdVoiceBlob = new Blob(_cdVoiceChunks, { type: mime || 'audio/webm' });
      btn.textContent = '🎤 Record again';
      btn.style.background = 'var(--bg)';
      btn.style.color = 'var(--text2)';
      st.textContent = 'Transcribing…';
      var fd = new FormData();
      var ext = (mime && mime.indexOf('mp4') !== -1) ? 'mp4' : 'webm';
      fd.append('audio', _cdVoiceBlob, 'recording.' + ext);
      try {
        var r = await fetch('/api/activities/transcribe', { method: 'POST', body: fd });
        if (!r.ok) {
          st.textContent = 'Transcription failed (HTTP ' + r.status + ')';
          st.style.color = '#ef4444';
          return;
        }
        var d = await r.json();
        _cdVoiceUrl = d.audio_url || '';
        _cdVoiceTranscript = d.transcript || '';
        if (_cdVoiceUrl) {
          var audioEl = document.getElementById('cd-voice-audio');
          audioEl.src = _cdVoiceUrl;
          document.getElementById('cd-voice-preview').style.display = 'block';
        }
        if (_cdVoiceTranscript) {
          var ta = document.getElementById('cd-summary');
          if (ta.value.trim()) {
            ta.value = ta.value.trimEnd() + '\n\n' + _cdVoiceTranscript;
          } else {
            ta.value = _cdVoiceTranscript;
          }
          st.style.color = '#059669';
          st.textContent = '✓ Transcribed';
        } else if (d.error) {
          st.style.color = '#ef4444';
          st.textContent = d.error;
        } else {
          st.style.color = '#f59e0b';
          st.textContent = 'No transcript returned';
        }
      } catch (e) {
        st.style.color = '#ef4444';
        st.textContent = 'Network error';
      }
    };
    _cdVoiceRecorder.start();
    _cdVoiceStartedAt = Date.now();
    btn.textContent = '⏹ Stop';
    btn.style.background = '#ef4444';
    btn.style.color = '#fff';
    st.style.color = 'var(--text3)';
    st.textContent = '0:00';
    _cdVoiceTimer = setInterval(function() {
      var s = Math.floor((Date.now() - _cdVoiceStartedAt) / 1000);
      st.textContent = Math.floor(s/60) + ':' + String(s%60).padStart(2,'0');
      if (Date.now() - _cdVoiceStartedAt >= _CD_VOICE_MAX_MS && _cdVoiceRecorder.state === 'recording') {
        _cdVoiceRecorder.stop();
      }
    }, 250);
  } catch (e) {
    alert('Could not access mic: ' + (e.message || e));
  }
}

function clearVoiceNote() {
  _cdVoiceBlob = null; _cdVoiceUrl = ''; _cdVoiceTranscript = '';
  document.getElementById('cd-voice-preview').style.display = 'none';
  document.getElementById('cd-voice-audio').src = '';
  document.getElementById('cd-voice-btn').textContent = '🎤 Record';
  document.getElementById('cd-voice-st').textContent = '';
}

function setSentiment(val) {
  _cdSentiment = (_cdSentiment === val) ? '' : val;
  document.querySelectorAll('#cd-sentiment-row button').forEach(function(b) {
    var v = b.getAttribute('data-sent');
    var on = (v === _cdSentiment);
    b.style.background = on ? _SENT_COLORS[v] : 'var(--bg)';
    b.style.color      = on ? '#fff'           : 'var(--text)';
    b.style.borderColor = on ? _SENT_COLORS[v] : 'var(--border)';
  });
}

function onPhotoPicked(e) {
  var f = e.target.files && e.target.files[0];
  if (!f) return;
  _cdPhotoFile = f;
  var reader = new FileReader();
  reader.onload = function(ev) {
    document.getElementById('cd-photo-img').src = ev.target.result;
    document.getElementById('cd-photo-preview').style.display = 'block';
    document.getElementById('cd-photo-pick').textContent = '📷 Replace photo';
  };
  reader.readAsDataURL(f);
}

function clearPhoto() {
  _cdPhotoFile = null;
  document.getElementById('cd-photo-input').value = '';
  document.getElementById('cd-photo-preview').style.display = 'none';
  document.getElementById('cd-photo-pick').textContent = '📷 Add photo';
}

function openLogModal(opts) {
  var o = opts || {};
  // Resolve target company id: explicit opts.company_id wins, else fall back
  // to the host page's COMPANY_ID const (company profile case).
  if (o.company_id != null) {
    _logModalCompanyId = o.company_id;
  } else if (typeof COMPANY_ID !== 'undefined') {
    _logModalCompanyId = COMPANY_ID;
  } else {
    _logModalCompanyId = null;
  }
  // Update modal title with the business name when supplied (route Check-In)
  var titleEl = document.getElementById('cd-modal-title');
  if (titleEl) {
    titleEl.textContent = o.business_name ? ('Log activity — ' + o.business_name) : 'Log activity';
  }
  document.getElementById('cd-summary').value = '';
  document.getElementById('cd-fu').value = '';
  document.getElementById('cd-type').value = 'Call';
  document.getElementById('cd-status').value = '';
  document.getElementById('cd-modal-msg').textContent = '';
  _cdSentiment = '';
  setSentiment('');
  clearPhoto();
  clearVoiceNote();
  document.getElementById('cd-modal-bg').style.display = 'flex';
}

function closeLogModal() {
  document.getElementById('cd-modal-bg').style.display = 'none';
}

async function submitLog() {
  var summary = document.getElementById('cd-summary').value.trim();
  var type    = document.getElementById('cd-type').value;
  var fu      = document.getElementById('cd-fu').value;
  var status  = document.getElementById('cd-status').value;
  var msg     = document.getElementById('cd-modal-msg');
  var btn     = document.getElementById('cd-modal-send');
  if (!summary) {
    msg.style.color = '#ef4444';
    msg.textContent = 'Notes are required.';
    return;
  }
  var cid = _logModalCompanyId;
  if (cid == null) {
    msg.style.color = '#ef4444';
    msg.textContent = 'No company in scope.';
    return;
  }
  btn.disabled = true;
  btn.textContent = 'Saving…';
  msg.textContent = '';
  var photoUrl = '';
  if (_cdPhotoFile) {
    btn.textContent = 'Uploading photo…';
    var fd = new FormData();
    fd.append('photo', _cdPhotoFile);
    try {
      var pr = await fetch('/api/companies/' + cid + '/activities/photo', {
        method: 'POST', body: fd,
      });
      if (pr.ok) {
        var pj = await pr.json();
        photoUrl = pj.url || '';
      } else {
        msg.style.color = '#ef4444';
        msg.textContent = 'Photo upload failed (HTTP ' + pr.status + ')';
        btn.disabled = false; btn.textContent = 'Save';
        return;
      }
    } catch (e) {
      msg.style.color = '#ef4444';
      msg.textContent = 'Photo upload network error';
      btn.disabled = false; btn.textContent = 'Save';
      return;
    }
    btn.textContent = 'Saving…';
  }
  var body = { summary: summary, type: type, kind: 'user_activity' };
  if (fu) body.follow_up = fu;
  if (status) body.new_status = status;
  if (_cdSentiment) body.sentiment = _cdSentiment;
  if (photoUrl) body.photo_url = photoUrl;
  if (_cdVoiceUrl) body.audio_url = _cdVoiceUrl;
  if (_cdVoiceTranscript) body.transcript = _cdVoiceTranscript;
  var r = await fetch('/api/companies/' + cid + '/activities', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (r.ok) {
    closeLogModal();
    if (typeof window._afterLogActivitySave === 'function') window._afterLogActivitySave();
  } else {
    var err = '';
    try { err = (await r.json()).error || ''; } catch(e) {}
    msg.style.color = '#ef4444';
    msg.textContent = 'Save failed: ' + (err || ('HTTP ' + r.status));
    btn.disabled = false;
    btn.textContent = 'Save';
  }
}
"""


# ─── Tool Dashboard ───────────────────────────────────────────────────────────
_TOOL_BODY = """
<div class="stats-row" id="stats-row">
  <div class="loading" style="padding:16px">Loading\u2026</div>
</div>

<div class="panel" style="margin-bottom:16px">
  <div class="panel-hd"><span class="panel-title">Pipeline</span></div>
  <div id="pipeline" class="pipeline"><div class="loading">Loading\u2026</div></div>
</div>

<div class="two-col">
  <div class="col-l">
    <div class="panel">
      <div class="panel-hd">
        <span class="panel-title">\U0001f534 Needs Attention</span>
        <span class="panel-ct" id="attn-ct">\u2014</span>
      </div>
      <div class="panel-body" id="attn-body"><div class="loading">Loading\u2026</div></div>
    </div>
  </div>
  <div class="col-r">
    <div class="panel">
      <div class="panel-hd">
        <span class="panel-title">\U0001f4c5 Upcoming Callbacks</span>
        <span class="panel-ct" id="cb-ct">\u2014</span>
      </div>
      <div class="panel-body" id="cb-body"><div class="loading">Loading\u2026</div></div>
    </div>
  </div>
</div>

<div class="two-col">
  <div class="col-l">
    <div class="panel">
      <div class="panel-hd"><span class="panel-title">By Type</span></div>
      <div class="panel-body" id="type-body"><div class="loading">Loading\u2026</div></div>
    </div>
  </div>
  <div class="col-r">
    <div class="panel">
      <div class="panel-hd">
        <span class="panel-title">Recent Activity</span>
        <span class="panel-ct" id="act-ct">\u2014</span>
      </div>
      <div class="panel-body" id="act-body"><div class="loading">Loading\u2026</div></div>
    </div>
  </div>
</div>
"""

def _tool_page(tool_key: str, br: str, bt: str, user: dict = None) -> str:
    CFG = {
        'attorney': {
            'label':        'PI Attorney',
            'color':        '#7c3aed',
            'venues_t':     T_ATT_VENUES,
            'acts_t':       T_ATT_ACTS,
            'boxes_t':      0,
            'name_field':   'Law Firm Name',
            'link_field':   'Law Firm',
            'active_status':'Active Relationship',
            'stages':       ['Not Contacted','Contacted','In Discussion','Active Relationship'],
            'stage_colors': ['#475569','#2563eb','#d97706','#059669'],
            'active_key':   'hub',
        },
        'gorilla': {
            'label':        'Guerilla Marketing',
            'color':        '#ea580c',
            'venues_t':     T_GOR_VENUES,
            'acts_t':       T_GOR_ACTS,
            'boxes_t':      T_GOR_BOXES,
            'name_field':   'Name',
            'link_field':   'Business',
            'active_status':'Active Partner',
            'stages':       ['Not Contacted','Contacted','In Discussion','Active Partner'],
            'stage_colors': ['#475569','#2563eb','#d97706','#059669'],
        },
        'community': {
            'label':        'Community Outreach',
            'color':        '#059669',
            'venues_t':     T_COM_VENUES,
            'acts_t':       T_COM_ACTS,
            'boxes_t':      0,
            'name_field':   'Name',
            'link_field':   'Organization',
            'active_status':'Active Partner',
            'stages':       ['Not Contacted','Contacted','In Discussion','Active Partner'],
            'stage_colors': ['#475569','#2563eb','#d97706','#059669'],
        },
    }
    c = CFG[tool_key]

    import json as _json
    stages_json      = _json.dumps(c['stages'])
    stage_colors_json = _json.dumps(c['stage_colors'])

    header = (
        f'<div class="header">'
        f'<div class="header-left">'
        f'<h1>{c["label"]}</h1>'
        f'<div class="sub">Pipeline &amp; outreach dashboard</div>'
        f'</div>'
        f'</div>'
    )

    js = f"""
const TOOL = {{
  venuesT:      {c['venues_t']},
  actsT:        {c['acts_t']},
  boxesT:       {c['boxes_t']},
  nameField:    '{c['name_field']}',
  linkField:    '{c['link_field']}',
  activeStatus: '{c['active_status']}',
  color:        '{c['color']}',
  stages:       {stages_json},
  stageColors:  {stage_colors_json},
}};

async function load() {{
  const [venues, acts] = await Promise.all([
    fetchAll(TOOL.venuesT),
    fetchAll(TOOL.actsT),
  ]);
  const boxes = TOOL.boxesT ? await fetchAll(TOOL.boxesT) : [];
  const activeBoxes = boxes.filter(b => sv(b['Status']) === 'Active').length;

  // Stats
  let active=0, overdue=0, todayCount=0, weekCount=0;
  const attnItems=[], cbItems=[];
  const typeCounts = {{}};

  for (const row of venues) {{
    const status = sv(row['Contact Status']);
    const du = daysUntil(row['Follow-Up Date']);
    const name = esc(row[TOOL.nameField] || '(unnamed)');
    const type = sv(row['Type']) || 'Other';

    if (status === TOOL.activeStatus) active++;
    typeCounts[type] = (typeCounts[type] || 0) + 1;

    if (du !== null && du < 0)  {{ overdue++;    attnItems.push({{name, du, status}}); }}
    if (du === 0)               {{ todayCount++; attnItems.push({{name, du, status}}); }}
    if (du !== null && du > 0 && du <= 14) {{ weekCount++; cbItems.push({{name, du, date: row['Follow-Up Date'], status}}); }}
  }}

  attnItems.sort((a,b) => a.du - b.du);
  cbItems.sort((a,b) => a.du - b.du);

  // Stats chips
  let statsHtml = `
    <div class="stat-chip">          <div class="label">Total</div>         <div class="value">${{venues.length}}</div></div>
    <div class="stat-chip c-green">  <div class="label">Active</div>        <div class="value">${{active}}</div></div>
    <div class="stat-chip c-red">    <div class="label">Overdue</div>       <div class="value">${{overdue}}</div></div>
    <div class="stat-chip c-yellow"> <div class="label">Due This Week</div> <div class="value">${{weekCount}}</div></div>
  `;
  if (TOOL.boxesT) {{
    statsHtml += `<div class="stat-chip c-orange"><div class="label">Active Boxes</div><div class="value">${{activeBoxes}}</div></div>`;
  }}
  document.getElementById('stats-row').innerHTML = statsHtml;

  // Pipeline
  const stageCounts = {{}};
  TOOL.stages.forEach(s => stageCounts[s] = 0);
  venues.forEach(row => {{
    const s = sv(row['Contact Status']) || 'Not Contacted';
    if (stageCounts[s] !== undefined) stageCounts[s]++;
    else stageCounts['Not Contacted'] = (stageCounts['Not Contacted'] || 0) + 1;
  }});
  const total = venues.length || 1;
  document.getElementById('pipeline').innerHTML = TOOL.stages.map((stage, i) => {{
    const n = stageCounts[stage] || 0;
    const pct = Math.round(n / total * 100);
    return `<div class="pipe-row">
      <span class="pipe-label">${{esc(stage)}}</span>
      <div class="pipe-bar"><div class="pipe-fill" style="width:${{pct}}%;background:${{TOOL.stageColors[i]}}"></div></div>
      <span class="pipe-n">${{n}}</span>
      <span class="pipe-pct">${{pct}}%</span>
    </div>`;
  }}).join('');

  // Needs Attention
  document.getElementById('attn-ct').textContent = attnItems.length + ' items';
  document.getElementById('attn-body').innerHTML = attnItems.length ? attnItems.map(a => `
    <div class="a-row">
      <div class="dot ${{a.du < 0 ? 'dot-r' : 'dot-y'}}"></div>
      <span class="a-name">${{a.name}}</span>
      <span class="a-meta" style="color:${{a.du < 0 ? '#ef4444':'#fbbf24'}}">${{a.du === 0 ? 'Today' : Math.abs(a.du) + 'd overdue'}}</span>
    </div>
  `).join('') : '<div class="empty">All caught up \u2713</div>';

  // Upcoming Callbacks
  document.getElementById('cb-ct').textContent = cbItems.length + ' in 14 days';
  document.getElementById('cb-body').innerHTML = cbItems.length ? cbItems.map(a => `
    <div class="a-row">
      <div class="dot dot-g"></div>
      <span class="a-name">${{a.name}}</span>
      <span class="date-badge">${{fmt(a.date)}}</span>
      <span class="a-meta">in ${{a.du}}d</span>
    </div>
  `).join('') : '<div class="empty">No upcoming callbacks</div>';

  // By Type
  const typeEntries = Object.entries(typeCounts).sort((a,b) => b[1]-a[1]);
  document.getElementById('type-body').innerHTML = typeEntries.length ? typeEntries.map(([t,n]) => `
    <div class="type-row">
      <span class="type-name">${{esc(t)}}</span>
      <span class="type-n">${{n}}</span>
    </div>
  `).join('') : '<div class="empty">No data</div>';

  // Recent Activity
  const sorted = [...acts].sort((a,b) => (b['Date']||'').localeCompare(a['Date']||'')).slice(0,15);
  document.getElementById('act-ct').textContent = acts.length + ' total';
  document.getElementById('act-body').innerHTML = sorted.length ? sorted.map(a => {{
    // Link field contains array of linked rows
    const links = a[TOOL.linkField] || [];
    const linkedName = links.length ? esc(links[0]['value'] || links[0]['display_value'] || '') : '\u2014';
    return `<div class="act-row">
      <span class="act-date">${{fmt(a['Date'])}}</span>
      <div class="act-body">
        <div class="act-name">${{linkedName}}</div>
        <div class="act-type">${{esc(sv(a['Type']))}}${{a['Outcome'] ? ' \u00b7 ' + esc(sv(a['Outcome'])) : ''}}</div>
      </div>
    </div>`;
  }}).join('') : '<div class="empty">No activities logged</div>';

  stampRefresh();
}}

load();
"""
    return _page(tool_key, c['label'], header, _TOOL_BODY, js, br, bt, user=user)
