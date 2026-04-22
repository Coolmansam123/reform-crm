"""
ClickUp integration — hub-side wrapper around the ClickUp v2 API.

Reuses patterns from `execution/modal_clickup_reminder.py` (the weekly
reminder cron) but adapted for the Modal web app: async (httpx), email-based
user resolution, in-process caching, and a `create_task` helper that tags the
task with CRM-link metadata (`crm:company:820`, `crm:lead:42`) so we can
reverse-filter later.

ClickUp API peculiarities worth preserving (from the reminder directive):
  - `/team` endpoint returns members with `{id, email, username, color, ...}`
    — email IS present here (unlike Google Chat), so email-based matching
    is reliable. No display-name fuzzy matching needed.
  - Rate limit: 100 req/min per token. Cache `team_members` aggressively.
  - Auth header: `Authorization: {api_key}` (no `Bearer` prefix).
"""
import os
import time
from typing import Optional

import httpx


CLICKUP_BASE = "https://api.clickup.com/api/v2"
CLICKUP_SPACE_ID = os.environ.get("CLICKUP_SPACE_ID", "90142723798")
CLICKUP_DEFAULT_LIST_ID = os.environ.get("CLICKUP_DEFAULT_LIST_ID", "")


# ─── In-process cache (per Modal container) ─────────────────────────────────
_cache: dict = {}
_TTL = {
    "team_id":      3600,   # workspaces rarely change
    "team_members": 600,    # 10 min — member list shifts occasionally
    "user_by_email": 600,
    "space_lists":  300,    # 5 min
}


def _cache_get(key: str):
    entry = _cache.get(key)
    if not entry: return None
    ttl = _TTL.get(key.split(":", 1)[0], 300)
    if (time.time() - entry["ts"]) > ttl: return None
    return entry["data"]


def _cache_put(key: str, data) -> None:
    _cache[key] = {"data": data, "ts": time.time()}


def _headers(api_key: str) -> dict:
    return {"Authorization": api_key}


# ─── Team / member resolution ───────────────────────────────────────────────
async def get_first_team_id(api_key: str, client: httpx.AsyncClient) -> Optional[str]:
    cached = _cache_get("team_id:first")
    if cached: return cached
    r = await client.get(f"{CLICKUP_BASE}/team", headers=_headers(api_key))
    if r.status_code != 200: return None
    teams = r.json().get("teams", [])
    if not teams: return None
    tid = str(teams[0]["id"])
    _cache_put("team_id:first", tid)
    return tid


async def get_team_members(api_key: str, client: httpx.AsyncClient) -> list:
    """Returns `[{id, email, username, color, profilePicture, initials}, ...]`."""
    cached = _cache_get("team_members:first")
    if cached is not None: return cached
    team_id = await get_first_team_id(api_key, client)
    if not team_id: return []
    r = await client.get(f"{CLICKUP_BASE}/team/{team_id}", headers=_headers(api_key))
    if r.status_code != 200: return []
    team = r.json().get("team", {})
    raw = team.get("members", []) or []
    # Members come back as [{"user": {...}}, ...] — flatten.
    members = []
    for m in raw:
        u = m.get("user") if isinstance(m, dict) else None
        if not u: continue
        members.append({
            "id":       u.get("id"),
            "email":    (u.get("email") or "").lower(),
            "username": u.get("username", ""),
            "color":    u.get("color", ""),
            "initials": u.get("initials", ""),
            "profilePicture": u.get("profilePicture", ""),
        })
    _cache_put("team_members:first", members)
    return members


async def resolve_user_by_email(api_key: str, email: str,
                                  client: httpx.AsyncClient) -> Optional[dict]:
    """Match a hub user (identified by Google email) to their ClickUp user."""
    if not email: return None
    email = email.lower().strip()
    cached = _cache_get(f"user_by_email:{email}")
    if cached is not None: return cached
    members = await get_team_members(api_key, client)
    match = next((m for m in members if m.get("email") == email), None)
    _cache_put(f"user_by_email:{email}", match)
    return match


# ─── Task fetchers ──────────────────────────────────────────────────────────
async def get_space_lists(api_key: str, space_id: str,
                           client: httpx.AsyncClient) -> list:
    """Return [{id, name, folder, folder_id}, ...] for every list in the space,
    including nested-in-folder lists. Cached 5 min."""
    cached = _cache_get(f"space_lists_full:{space_id}")
    if cached is not None: return cached
    out = []
    # Folderless lists
    r = await client.get(f"{CLICKUP_BASE}/space/{space_id}/list",
                         headers=_headers(api_key))
    if r.status_code == 200:
        for l in r.json().get("lists", []) or []:
            out.append({"id": str(l["id"]), "name": l.get("name", ""),
                         "folder": "", "folder_id": None})
    # Folders → lists
    r = await client.get(f"{CLICKUP_BASE}/space/{space_id}/folder",
                         headers=_headers(api_key))
    if r.status_code == 200:
        for folder in r.json().get("folders", []) or []:
            fid = folder.get("id")
            fname = folder.get("name", "")
            if not fid: continue
            rr = await client.get(f"{CLICKUP_BASE}/folder/{fid}/list",
                                  headers=_headers(api_key))
            if rr.status_code == 200:
                for l in rr.json().get("lists", []) or []:
                    out.append({"id": str(l["id"]), "name": l.get("name", ""),
                                 "folder": fname, "folder_id": str(fid)})
    _cache_put(f"space_lists_full:{space_id}", out)
    return out


async def _get_space_list_ids(api_key: str, space_id: str,
                               client: httpx.AsyncClient) -> list:
    """Thin wrapper — just the IDs, reused by `get_user_tasks`."""
    full = await get_space_lists(api_key, space_id, client)
    return [l["id"] for l in full]


async def get_user_tasks(api_key: str, user_id: int,
                          space_id: str = None,
                          include_closed: bool = False) -> list:
    """Return open tasks assigned to a user, across every list in the space.
    Returns raw ClickUp task dicts (caller slims)."""
    sid = space_id or CLICKUP_SPACE_ID
    all_tasks = []
    async with httpx.AsyncClient(timeout=30) as client:
        list_ids = await _get_space_list_ids(api_key, sid, client)
        params = {
            "assignees[]": str(user_id),
            "subtasks": "true",
            "include_closed": "true" if include_closed else "false",
            "order_by": "due_date",
            "reverse": "false",
        }
        # ClickUp doesn't support multi-list queries — hit each list
        for lid in list_ids:
            r = await client.get(f"{CLICKUP_BASE}/list/{lid}/task",
                                 headers=_headers(api_key), params=params)
            if r.status_code == 200:
                all_tasks.extend(r.json().get("tasks", []) or [])
    # De-dup by id (a subtask may surface in multiple lists)
    seen = set()
    out = []
    for t in all_tasks:
        tid = t.get("id")
        if tid in seen: continue
        seen.add(tid)
        out.append(t)
    return out


def slim_task(t: dict) -> dict:
    """Compact shape for the hub UI."""
    status = t.get("status") or {}
    lst    = t.get("list") or {}
    folder = t.get("folder") or {}
    return {
        "id":        t.get("id", ""),
        "name":      t.get("name", ""),
        "url":       t.get("url", ""),
        "due_date":  t.get("due_date"),       # milliseconds string or None
        "date_created": t.get("date_created"),
        "status":    status.get("status", "") if isinstance(status, dict) else "",
        "status_color": status.get("color", "") if isinstance(status, dict) else "",
        "assignees": [a.get("id") for a in (t.get("assignees") or []) if a.get("id")],
        "tags":      [tg.get("name") for tg in (t.get("tags") or []) if tg.get("name")],
        "list_id":   lst.get("id"),
        "list_name": lst.get("name", ""),
        "folder":    folder.get("name", "") if isinstance(folder, dict) else "",
        "priority":  (t.get("priority") or {}).get("priority") if t.get("priority") else None,
    }


# ─── Task mutations ─────────────────────────────────────────────────────────
async def create_task(api_key: str, list_id: str, *, name: str,
                       description: str = "", assignees: list = None,
                       due_date_ms: int = None, tags: list = None,
                       priority: int = None, status: str = None) -> dict:
    """POST /list/{list_id}/task. Returns ClickUp's response JSON."""
    payload = {"name": name}
    if description: payload["description"] = description
    if assignees:   payload["assignees"] = [int(a) for a in assignees]
    if due_date_ms: payload["due_date"] = int(due_date_ms)
    if tags:        payload["tags"] = list(tags)
    if priority:    payload["priority"] = int(priority)
    if status:      payload["status"] = status
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{CLICKUP_BASE}/list/{list_id}/task",
                              headers={**_headers(api_key), "Content-Type": "application/json"},
                              json=payload)
    if r.status_code not in (200, 201):
        return {"error": r.text[:400], "status": r.status_code}
    return r.json()


async def update_task(api_key: str, task_id: str, patch: dict) -> dict:
    """PUT /task/{task_id}. Fields like `status`, `due_date`, `name`, `description`."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.put(f"{CLICKUP_BASE}/task/{task_id}",
                             headers={**_headers(api_key), "Content-Type": "application/json"},
                             json=patch)
    if r.status_code not in (200, 201):
        return {"error": r.text[:400], "status": r.status_code}
    return r.json()


# ─── CRM linking ────────────────────────────────────────────────────────────
def crm_tag(kind: str, id_: int) -> str:
    """Tag convention: crm:<kind>:<id> → reverse-filter tasks by CRM record."""
    return f"crm:{kind}:{int(id_)}"


def parse_crm_tags(tags: list) -> dict:
    """Extract CRM link ids from a task's tag list.
    Returns {company_id, lead_id, person_id} with int values or None."""
    out = {"company_id": None, "lead_id": None, "person_id": None}
    for t in tags or []:
        if not isinstance(t, str) or not t.startswith("crm:"): continue
        parts = t.split(":")
        if len(parts) != 3: continue
        kind, sid = parts[1], parts[2]
        try: val = int(sid)
        except (TypeError, ValueError): continue
        if kind == "company": out["company_id"] = val
        elif kind == "lead":  out["lead_id"] = val
        elif kind == "person": out["person_id"] = val
    return out
