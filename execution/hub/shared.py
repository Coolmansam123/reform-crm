"""
Shared infrastructure for the Reform Operations Hub.

This module is a thin facade — the real implementations live in sibling
modules, split out so no single file becomes a bottleneck:

  constants.py  — table IDs + email outreach templates
  access.py     — role lookup, hub allowlist, admin checks
  styles.py     — _CSS string + _JS_SHARED template
  nav.py        — _topnav (desktop + hamburger drawer)
  compose.py    — _COMPOSE_HTML / _COMPOSE_JS (email FAB)
  shells.py     — _page / _forbidden_page / _mobile_page / _tool_page

New code should import from the specific module. Existing callers keep
working via the re-exports below.

UI NOTE: All interactive elements (modals, overlays, sidebars, dropdowns) should
use CSS transitions for open/close rather than abrupt display:none toggling.
Pattern: use opacity + visibility + transform for smooth fade/slide animations.
See guerilla.py .gfr-overlay and #map-sidebar for reference implementations.
"""

from .access import (
    ALL_HUB_KEYS,
    _can_view_as,
    _get_allowed_hubs,
    _get_real_allowed_hubs,
    _get_staff_role,
    _has_hub_access,
    _has_social_access,
    _is_admin,
)
from .compose import _COMPOSE_HTML, _COMPOSE_JS
from .constants import (
    T_ATT_ACTS,
    T_ATT_VENUES,
    T_COM_ACTS,
    T_COM_VENUES,
    T_EVENTS,
    T_GOR_ACTS,
    T_GOR_BOXES,
    T_GOR_ROUTE_STOPS,
    T_GOR_ROUTES,
    T_GOR_VENUES,
    T_LEADS,
    T_PI_ACTIVE,
    T_PI_AWAITING,
    T_PI_BILLED,
    T_PI_CLOSED,
    T_PI_FINANCE,
    T_STAFF,
    T_TICKETS,
    T_TICKET_COMMENTS,
    T_COMPANIES,
    T_CONTACTS,
    T_ACTIVITIES,
    T_SMS_MESSAGES,
    T_SEQUENCES,
    T_SEQUENCE_ENROLLMENTS,
    T_SOCIAL_NOTIFICATIONS,
    LEAD_STAGES,
    OPEN_LEAD_STAGES,
    CLOSED_LEAD_STAGES,
    _TEMPLATES_JS,
)
from .nav import _topnav
from .shells import _forbidden_page, _mobile_page, _page, _tool_page
from .styles import _CSS, _JS_SHARED

__all__ = [
    # constants
    "T_ATT_VENUES", "T_ATT_ACTS", "T_GOR_VENUES", "T_GOR_ACTS", "T_GOR_BOXES",
    "T_COM_VENUES", "T_COM_ACTS", "T_GOR_ROUTES", "T_GOR_ROUTE_STOPS",
    "T_PI_ACTIVE", "T_PI_BILLED", "T_PI_AWAITING", "T_PI_CLOSED", "T_PI_FINANCE",
    "T_STAFF", "T_EVENTS", "T_LEADS", "T_TICKETS", "T_TICKET_COMMENTS",
    "T_COMPANIES", "T_CONTACTS", "T_ACTIVITIES", "T_SMS_MESSAGES",
    "T_SEQUENCES", "T_SEQUENCE_ENROLLMENTS", "T_SOCIAL_NOTIFICATIONS",
    "LEAD_STAGES", "OPEN_LEAD_STAGES", "CLOSED_LEAD_STAGES",
    "_TEMPLATES_JS",
    # access
    "ALL_HUB_KEYS", "_can_view_as", "_get_staff_role",
    "_get_real_allowed_hubs",
    "_has_social_access", "_is_admin", "_get_allowed_hubs", "_has_hub_access",
    # styles
    "_CSS", "_JS_SHARED",
    # nav
    "_topnav",
    # compose
    "_COMPOSE_HTML", "_COMPOSE_JS",
    # shells
    "_page", "_forbidden_page", "_mobile_page", "_tool_page",
]
