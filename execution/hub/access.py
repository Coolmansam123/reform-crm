"""
Access control helpers for the Reform Operations Hub.
Role lookup (cached), hub allowlist, admin checks.
"""
import os

from .constants import T_STAFF


def _has_social_access(user: dict) -> bool:
    """Returns True if user can access the Social Poster Hub.
    Gated by SOCIAL_POSTER_EMAILS env var (comma-separated).
    If var is not set, all authenticated domain users can access."""
    allowed = os.environ.get("SOCIAL_POSTER_EMAILS", "")
    if not allowed:
        return True
    emails = [e.strip().lower() for e in allowed.split(",") if e.strip()]
    return user.get("email", "").lower() in emails


_staff_cache = {"data": None, "ts": 0}

ALL_HUB_KEYS = ["attorney", "guerilla", "community", "pi_cases", "billing",
                "communications", "social", "calendar"]


def _get_staff_record(user: dict) -> dict:
    """Return the full T_STAFF row for user, cached 5 min.
    Returns empty dict if not found."""
    import time
    email = (user.get("email") or "").lower().strip()
    if not email:
        return {}

    br = os.environ.get("BASEROW_URL", "")
    bt = os.environ.get("BASEROW_API_TOKEN", "")
    if br and bt and T_STAFF:
        now = time.time()
        if _staff_cache["data"] is None or (now - _staff_cache["ts"]) > 300:
            try:
                import httpx
                r = httpx.get(
                    f"{br}/api/database/rows/table/{T_STAFF}/?user_field_names=true&size=200",
                    headers={"Authorization": f"Token {bt}"},
                    timeout=10,
                )
                if r.status_code == 200:
                    _staff_cache["data"] = r.json().get("results", [])
                    _staff_cache["ts"] = now
            except Exception:
                pass

        if _staff_cache["data"]:
            for row in _staff_cache["data"]:
                if (row.get("Email") or "").lower().strip() == email:
                    return row

    return {}


def _get_staff_role(user: dict) -> str:
    """Return the user's role from the Staff table ('admin', 'field', 'viewer').
    Falls back to ADMIN_EMAILS env var, then defaults to 'admin'."""
    email = (user.get("email") or "").lower().strip()
    if not email:
        return "admin"

    record = _get_staff_record(user)
    if record:
        if not record.get("Active", True):
            return "viewer"
        role = record.get("Role")
        if isinstance(role, dict):
            role = role.get("value", "")
        return (role or "field").lower()

    # Fallback: ADMIN_EMAILS env var
    allowed = os.environ.get("ADMIN_EMAILS", "")
    if not allowed:
        return "admin"
    emails = [e.strip().lower() for e in allowed.split(",") if e.strip()]
    return "admin" if email in emails else "field"


def _is_admin(user: dict) -> bool:
    """Returns True if user has admin access."""
    return _get_staff_role(user) == "admin"


def _get_allowed_hubs(user: dict) -> list:
    """Return list of hub keys user can access. Admin gets all."""
    role = _get_staff_role(user)
    if role == "admin":
        return list(ALL_HUB_KEYS)
    record = _get_staff_record(user)
    hubs_field = record.get("Allowed Hubs") or []
    return [h["value"] if isinstance(h, dict) else str(h) for h in hubs_field]


def _has_hub_access(user: dict, hub_key: str) -> bool:
    """Check if user can access a specific hub."""
    return hub_key in _get_allowed_hubs(user)
