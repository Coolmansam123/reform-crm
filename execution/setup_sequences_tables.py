#!/usr/bin/env python3
"""
Create Email Sequences + Sequence Enrollments tables in 'Reform Chiropractic
CRM' database (197) and add `sequences` to T_STAFF 'Allowed Hubs'.

Sequences store steps as a JSON blob in a long_text field to avoid a third
table; the list of {delay_days, subject, body} objects is small enough.

Idempotent.

Usage:
    python execution/setup_sequences_tables.py
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
T_COMPANIES      = 820
T_STAFF          = 815
NEW_HUB_KEY      = "sequences"


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

def patch_field(fid, patch, label=""):
    r = requests.patch(f"{BASEROW_URL}/api/database/fields/{fid}/", headers=headers(), json=patch)
    if r.status_code != 200: print(f"    WARN patch {label}: {r.status_code} {r.text[:200]}")
    return r.status_code == 200

def get_or_create_table(db_id, name):
    existing = next((t for t in list_tables(db_id) if t["name"] == name), None)
    if existing: print(f"  Table '{name}' already exists (ID: {existing['id']})"); return existing["id"]
    print(f"  Creating table '{name}'...")
    t = create_table(db_id, name); print(f"  Created (ID: {t['id']})"); return t["id"]

def ensure_fields(tid, configs):
    existing_names = {f["name"] for f in get_fields(tid)}
    for cfg in configs:
        if cfg["name"] in existing_names: print(f"    = {cfg['name']} (exists)")
        else: create_field(tid, cfg)
    for f in get_fields(tid):
        if f["name"] in {"Notes", "Active"} and not f.get("primary", False):
            if not any(fc["name"] == f["name"] for fc in configs):
                if delete_field(f["id"]): print(f"    - Removed default '{f['name']}'")

def rename_primary(tid, new_name):
    p = next((f for f in get_fields(tid) if f.get("primary")), None)
    if p and p["name"] != new_name:
        if patch_field(p["id"], {"name": new_name}): print(f"    = Renamed primary to '{new_name}'")


SEQUENCES_FIELDS = [
    {"name": "Description", "type": "long_text"},
    {"name": "Category", "type": "single_select", "select_options": [
        {"value": "attorney",  "color": "purple"},
        {"value": "guerilla",  "color": "orange"},
        {"value": "community", "color": "green"},
        {"value": "patient",   "color": "blue"},
        {"value": "other",     "color": "light-gray"},
    ]},
    # Steps as JSON array: [{"delay_days": 0, "subject": "...", "body": "..."}, ...]
    # Delay is measured from the previous send (first step uses delay_days
    # from enrollment time).
    {"name": "Steps JSON", "type": "long_text"},
    {"name": "Is Active",  "type": "boolean"},
    {"name": "Created",    "type": "date", "date_format": "US", "date_include_time": True},
    {"name": "Updated",    "type": "date", "date_format": "US", "date_include_time": True},
]

ENROLLMENTS_FIELDS = [
    {"name": "Recipient Email", "type": "email"},
    {"name": "Recipient Name",  "type": "text"},
    {"name": "Sender Email",    "type": "text"},  # staff who enrolled + whose Gmail we send from
    {"name": "Status", "type": "single_select", "select_options": [
        {"value": "active",        "color": "blue"},
        {"value": "paused",        "color": "yellow"},
        {"value": "replied",       "color": "dark-blue"},
        {"value": "completed",     "color": "green"},
        {"value": "needs_reauth",  "color": "orange"},
        {"value": "failed",        "color": "red"},
        {"value": "unenrolled",    "color": "light-gray"},
    ]},
    {"name": "Current Step",  "type": "number", "number_decimal_places": 0},
    # Cross-DB ids (T_LEADS is in DB 203)
    {"name": "Lead ID",       "type": "number", "number_decimal_places": 0},
    {"name": "Next Send At",  "type": "date", "date_format": "US", "date_include_time": True},
    {"name": "Last Sent At",  "type": "date", "date_format": "US", "date_include_time": True},
    {"name": "Last Error",    "type": "long_text"},
    {"name": "Created",       "type": "date", "date_format": "US", "date_include_time": True},
    {"name": "Updated",       "type": "date", "date_format": "US", "date_include_time": True},
]


def extend_allowed_hubs(hub_key):
    fields = get_fields(T_STAFF)
    allowed = next((f for f in fields if f["name"] == "Allowed Hubs"), None)
    if not allowed: print("  WARN: T_STAFF has no 'Allowed Hubs' field"); return
    opts = allowed.get("select_options", []) or []
    if any(o["value"] == hub_key for o in opts):
        print(f"  = '{hub_key}' already an Allowed Hubs option"); return
    merged = [{"id": o["id"], "value": o["value"], "color": o.get("color", "light-gray")} for o in opts]
    merged.append({"value": hub_key, "color": "pink"})
    if patch_field(allowed["id"], {"select_options": merged}, "(Allowed Hubs)"):
        print(f"  + Added '{hub_key}' to Allowed Hubs")


def main():
    print("=" * 60)
    print("Setting up Email Sequences + Enrollments in DB 197")
    print("=" * 60)

    print("\n1. Sequences table")
    seq_id = get_or_create_table(DATABASE_ID, "Sequences")
    rename_primary(seq_id, "Name")
    ensure_fields(seq_id, SEQUENCES_FIELDS)

    print("\n2. Sequence Enrollments table")
    enr_id = get_or_create_table(DATABASE_ID, "Sequence Enrollments")
    rename_primary(enr_id, "Name")  # kept as a general display field; content mirrors Recipient Email
    ensure_fields(enr_id, ENROLLMENTS_FIELDS)

    existing_names = {f["name"] for f in get_fields(enr_id)}
    if "Sequence" not in existing_names:
        create_field(enr_id, {"name": "Sequence", "type": "link_row", "link_row_table_id": seq_id})
    if "Company" not in existing_names:
        create_field(enr_id, {"name": "Company", "type": "link_row", "link_row_table_id": T_COMPANIES})

    print("\n3. T_STAFF 'Allowed Hubs' options")
    extend_allowed_hubs(NEW_HUB_KEY)

    print("\n" + "=" * 60)
    print(f"T_SEQUENCES            = {seq_id}")
    print(f"T_SEQUENCE_ENROLLMENTS = {enr_id}")
    print("=" * 60)


if __name__ == "__main__":
    main()
