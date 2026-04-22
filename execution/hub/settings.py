"""
Per-user settings page. Profile info for all users; view-as toggle
(override Allowed Hubs for testing) gated to emails in VIEW_AS_EMAILS.
"""
from .access import (
    ALL_HUB_KEYS, _can_view_as, _get_real_allowed_hubs, _get_staff_role,
)
from .shared import _page


_HUB_LABELS = {
    "attorney":       "PI Attorney",
    "guerilla":       "Guerilla Mktg",
    "community":      "Community",
    "pi_cases":       "PI Cases",
    "billing":        "Billing",
    "communications": "Communications",
    "social":         "Social Media",
    "calendar":       "Calendar",
}


_SETTINGS_STYLES = """
<style>
.set-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px 22px;margin-bottom:20px;max-width:680px}
.set-card h2{font-size:14px;font-weight:700;margin:0 0 14px;letter-spacing:0.3px}
.set-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px}
.set-row:last-child{border-bottom:0}
.set-lbl{color:var(--text3)}
.set-val{color:var(--text);font-weight:500}
.set-hint{font-size:12px;color:var(--text3);margin-bottom:14px;line-height:1.5}
.set-status{padding:10px 12px;border-radius:6px;background:var(--card2,rgba(124,58,237,0.08));border:1px solid rgba(124,58,237,0.25);font-size:12px;margin-bottom:14px}
.set-chk-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px 16px;margin-bottom:16px}
@media(max-width:500px){.set-chk-grid{grid-template-columns:1fr}}
.set-chk{display:flex;align-items:center;gap:8px;padding:6px 10px;border:1px solid var(--border);border-radius:6px;cursor:pointer;font-size:13px;user-select:none}
.set-chk:hover{border-color:var(--text3)}
.set-chk input{cursor:pointer}
.set-btn-row{display:flex;gap:10px}
.set-btn{padding:9px 18px;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer;border:1px solid var(--border);background:transparent;color:var(--text)}
.set-btn-primary{background:#7c3aed;color:#fff;border-color:#7c3aed}
.set-btn-primary:hover{background:#6d28d9}
.set-btn:hover{border-color:var(--text3)}
</style>
"""


def _settings_page(br: str, bt: str, user: dict = None) -> str:
    user = user or {}
    email = user.get("email", "")
    name = user.get("name", "")
    role = _get_staff_role(user) if email else "unknown"
    real_hubs = _get_real_allowed_hubs(user) if email else []
    override = user.get("view_as_hubs")

    header = (
        '<div class="header"><div class="header-left">'
        '<h1>Settings</h1>'
        '<div class="sub">Your account preferences</div>'
        '</div></div>'
    )

    dash = "\u2014"
    real_hub_labels = ", ".join(_HUB_LABELS.get(h, h) for h in real_hubs) or "(none)"
    profile_card = (
        '<div class="set-card">'
        '<h2>Profile</h2>'
        f'<div class="set-row"><span class="set-lbl">Name</span><span class="set-val">{name or dash}</span></div>'
        f'<div class="set-row"><span class="set-lbl">Email</span><span class="set-val">{email or dash}</span></div>'
        f'<div class="set-row"><span class="set-lbl">Role</span><span class="set-val">{role}</span></div>'
        f'<div class="set-row"><span class="set-lbl">Allowed Hubs</span><span class="set-val">{real_hub_labels}</span></div>'
        '</div>'
    )

    view_as_card = ""
    if _can_view_as(user):
        if override is None:
            status = 'Currently viewing with your real permissions (<strong>admin / all hubs</strong>).'
            checked_set = set(ALL_HUB_KEYS)
        else:
            shown = ", ".join(_HUB_LABELS.get(h, h) for h in override) or "(empty \u2014 field rep with no hubs)"
            status = f'Currently viewing as a user with: <strong>{shown}</strong>'
            checked_set = set(override)

        checkboxes = ""
        for hub in ALL_HUB_KEYS:
            checked = "checked" if hub in checked_set else ""
            label = _HUB_LABELS.get(hub, hub)
            checkboxes += (
                '<label class="set-chk">'
                f'<input type="checkbox" name="hubs" value="{hub}" {checked}>'
                f'<span>{label}</span>'
                '</label>'
            )

        view_as_card = (
            '<div class="set-card">'
            '<h2>View Mode (Testing)</h2>'
            '<div class="set-hint">Override your Allowed Hubs so you can see the dashboard and routes exactly as a limited-permission user would. Only visible to you. Reset anytime.</div>'
            f'<div class="set-status">{status}</div>'
            '<form id="view-as-form" onsubmit="applyViewAs(event)">'
            f'<div class="set-chk-grid">{checkboxes}</div>'
            '<div class="set-btn-row">'
            '<button type="submit" class="set-btn set-btn-primary">Apply view mode</button>'
            '<button type="button" class="set-btn" onclick="resetViewAs()">Reset to admin</button>'
            '</div>'
            '</form>'
            '</div>'
        )

    body = _SETTINGS_STYLES + profile_card + view_as_card

    js = """
async function applyViewAs(e) {
  e.preventDefault();
  const form = document.getElementById('view-as-form');
  const hubs = Array.from(form.querySelectorAll('input[name="hubs"]:checked')).map(el => el.value);
  const resp = await fetch('/api/settings/view-as', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({hubs})
  });
  if (resp.ok) location.reload();
  else alert('Failed to apply view mode');
}
async function resetViewAs() {
  const resp = await fetch('/api/settings/view-as/clear', {method: 'POST'});
  if (resp.ok) location.reload();
  else alert('Failed to reset');
}
"""

    return _page('settings', 'Settings', header, body, js, br, bt, user=user)
