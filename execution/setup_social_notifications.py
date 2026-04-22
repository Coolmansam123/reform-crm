#!/usr/bin/env python3
"""
Create the `Social Notifications` table in DB 197. One row per incoming
comment / reply / mention / DM from any connected social platform. The
Inbox page reads from this; the per-platform pollers write to it.

`Source ID` is a platform-prefixed unique string (e.g. `yt:comment:abc`,
`ig:comment:123`) — it's the dedupe key so pollers can be safely re-run.

Idempotent.

Usage:
    python execution/setup_social_notifications.py
"""
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL      = os.getenv("BASEROW_URL")
BASEROW_EMAIL    = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
DATABASE_ID      = 197

_jwt_token = None
_jwt_time  = 0

def fresh_token():
    global _jwt_token, _jwt_time
    if _jwt_token is None or (time.time() - _jwt_time) > 480:
        r = requests.post(f"{BASEROW_URL}/api/user/token-auth/", json={
            "email": BASEROW_EMAIL, "password": BASEROW_PASSWORD,
        })
        r.raise_for_status()
        _jwt_token = r.json()["access_token"]
        _jwt_time  = time.time()
    return _jwt_token

def headers():
    return {"Authorization": f"JWT {fresh_token()}", "Content-Type": "application/json"}


def list_tables(db_id):
    r = requests.get(f"{BASEROW_URL}/api/database/tables/database/{db_id}/", headers=headers())
    r.raise_for_status(); return r.json()

def create_table(db_id, name):
    r = requests.post(f"{BASEROW_URL}/api/database/tables/database/{db_id}/",
                      headers=headers(), json={"name": name})
    r.raise_for_status(); return r.json()

def get_fields(tid):
    r = requests.get(f"{BASEROW_URL}/api/database/fields/table/{tid}/", headers=headers())
    r.raise_for_status(); return r.json()

def create_field(tid, cfg):
    r = requests.post(f"{BASEROW_URL}/api/database/fields/table/{tid}/",
                      headers=headers(), json=cfg)
    if r.status_code == 200:
        print(f"    + {cfg['name']} ({cfg['type']})"); return r.json()
    print(f"    WARN: '{cfg['name']}' failed: {r.status_code} {r.text[:200]}")

def delete_field(fid):
    r = requests.delete(f"{BASEROW_URL}/api/database/fields/{fid}/", headers=headers())
    return r.status_code in (200, 204)

def patch_field(fid, patch):
    r = requests.patch(f"{BASEROW_URL}/api/database/fields/{fid}/", headers=headers(), json=patch)
    return r.status_code == 200

def get_or_create_table(db_id, name):
    existing = next((t for t in list_tables(db_id) if t["name"] == name), None)
    if existing:
        print(f"  Table '{name}' already exists (ID: {existing['id']})"); return existing["id"]
    print(f"  Creating table '{name}'...")
    t = create_table(db_id, name); print(f"  Created (ID: {t['id']})"); return t["id"]

def ensure_fields(tid, configs):
    existing_names = {f["name"] for f in get_fields(tid)}
    for cfg in configs:
        if cfg["name"] in existing_names:
            print(f"    = {cfg['name']} (exists)")
        else:
            create_field(tid, cfg)
    for f in get_fields(tid):
        if f["name"] in {"Notes", "Active"} and not f.get("primary", False):
            if not any(fc["name"] == f["name"] for fc in configs):
                if delete_field(f["id"]): print(f"    - Removed default '{f['name']}'")


NOTIFICATION_FIELDS = [
    # Primary = `Source ID` (renamed from Baserow's default primary below)
    {"name": "Platform", "type": "single_select", "select_options": [
        {"value": "instagram", "color": "pink"},
        {"value": "facebook",  "color": "blue"},
        {"value": "tiktok",    "color": "dark-gray"},
        {"value": "youtube",   "color": "red"},
    ]},
    {"name": "Kind", "type": "single_select", "select_options": [
        {"value": "comment", "color": "blue"},
        {"value": "reply",   "color": "light-blue"},
        {"value": "mention", "color": "orange"},
        {"value": "dm",      "color": "purple"},
        {"value": "follow",  "color": "green"},
        {"value": "digest",  "color": "dark-gray"},
    ]},
    {"name": "Author Name",   "type": "text"},
    {"name": "Author Handle", "type": "text"},
    {"name": "Body",          "type": "long_text"},
    {"name": "Post URL",      "type": "url"},
    {"name": "Post Caption",  "type": "text"},
    {"name": "Reply URL",     "type": "url"},
    {"name": "Received At",   "type": "date", "date_format": "US", "date_include_time": True},
    {"name": "Status", "type": "single_select", "select_options": [
        {"value": "unread",   "color": "blue"},
        {"value": "read",     "color": "light-gray"},
        {"value": "archived", "color": "dark-gray"},
    ]},
    {"name": "Metadata", "type": "long_text"},  # raw payload JSON
]


def rename_primary(tid, new_name):
    primary = next((f for f in get_fields(tid) if f.get("primary")), None)
    if primary and primary["name"] != new_name:
        if patch_field(primary["id"], {"name": new_name}):
            print(f"    = Renamed primary field to '{new_name}'")


def ensure_select_options(tid, field_name, desired_options):
    """Merge any missing single_select options into an existing field.
    desired_options: list of {"value": str, "color": str}."""
    fields = get_fields(tid)
    field = next((f for f in fields if f["name"] == field_name), None)
    if not field or field.get("type") != "single_select":
        return
    existing_values = {o["value"] for o in field.get("select_options", [])}
    missing = [o for o in desired_options if o["value"] not in existing_values]
    if not missing:
        return
    merged = list(field.get("select_options", [])) + missing
    if patch_field(field["id"], {"select_options": merged}):
        for o in missing:
            print(f"    + {field_name}: added option '{o['value']}'")


def main():
    print("=" * 60)
    print("Setting up Social Notifications table in DB 197")
    print("=" * 60)

    tid = get_or_create_table(DATABASE_ID, "Social Notifications")
    rename_primary(tid, "Source ID")
    ensure_fields(tid, NOTIFICATION_FIELDS)
    # Ensure Kind has every option (merge 'digest' into existing tables)
    kind_cfg = next((f for f in NOTIFICATION_FIELDS if f["name"] == "Kind"), None)
    if kind_cfg:
        ensure_select_options(tid, "Kind", kind_cfg["select_options"])

    print("\n" + "=" * 60)
    print(f"T_SOCIAL_NOTIFICATIONS = {tid}")
    print("=" * 60)
    print("\nPaste into execution/hub/constants.py:")
    print(f"  T_SOCIAL_NOTIFICATIONS = {tid}")


if __name__ == "__main__":
    main()
