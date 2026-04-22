#!/usr/bin/env python3
"""
Create the `SMS Messages` table in the 'Reform Chiropractic CRM' database
(197). One row per outbound + inbound SMS; threaded by phone number.

Link rows to T_COMPANIES (820) and T_CONTACTS (821) are plain Baserow
link_rows because they live in the same DB. T_LEADS (817) is in DB 203, so
we store `Lead ID` as a plain number (same pattern as `Referred By Company
ID` on T_LEADS).

Idempotent.

Usage:
    python execution/setup_sms_table.py
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
T_CONTACTS       = 821


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
    # Drop default "Notes" / "Active" auto-fields we don't want
    for f in get_fields(tid):
        if f["name"] in {"Notes", "Active"} and not f.get("primary", False):
            if not any(fc["name"] == f["name"] for fc in configs):
                if delete_field(f["id"]): print(f"    - Removed default '{f['name']}'")


SMS_FIELDS = [
    # Primary is `Phone` (renamed from Baserow's default primary below).
    {"name": "Direction", "type": "single_select", "select_options": [
        {"value": "outbound", "color": "blue"},
        {"value": "inbound",  "color": "green"},
    ]},
    {"name": "Body", "type": "long_text"},
    {"name": "Status", "type": "single_select", "select_options": [
        {"value": "queued",      "color": "light-gray"},
        {"value": "sending",     "color": "yellow"},
        {"value": "sent",        "color": "blue"},
        {"value": "delivered",   "color": "green"},
        {"value": "undelivered", "color": "orange"},
        {"value": "failed",      "color": "red"},
        {"value": "received",    "color": "green"},
        {"value": "read",        "color": "dark-green"},
    ]},
    {"name": "Twilio SID", "type": "text"},
    {"name": "From",       "type": "text"},  # our Twilio number for inbound; staff number (virtual) for outbound
    {"name": "Author",     "type": "text"},  # staff email who sent outbound; blank for inbound
    {"name": "Error",      "type": "long_text"},
    # Lead cross-DB: plain integer (matches the `Referred By Company ID` pattern)
    {"name": "Lead ID",    "type": "number", "number_decimal_places": 0},
    # Timestamps
    {"name": "Created", "type": "date", "date_format": "US", "date_include_time": True},
    {"name": "Updated", "type": "date", "date_format": "US", "date_include_time": True},
]


def rename_primary(tid, new_name):
    primary = next((f for f in get_fields(tid) if f.get("primary")), None)
    if primary and primary["name"] != new_name:
        if patch_field(primary["id"], {"name": new_name}):
            print(f"    = Renamed primary field to '{new_name}'")


def main():
    print("=" * 60)
    print("Setting up SMS Messages table in DB 197")
    print("=" * 60)

    tid = get_or_create_table(DATABASE_ID, "SMS Messages")
    rename_primary(tid, "Phone")
    ensure_fields(tid, SMS_FIELDS)

    # Link-row fields (need both target tables in same DB — they are)
    existing_names = {f["name"] for f in get_fields(tid)}
    if "Company" not in existing_names:
        create_field(tid, {"name": "Company", "type": "link_row",
                            "link_row_table_id": T_COMPANIES})
    if "Contact" not in existing_names:
        create_field(tid, {"name": "Contact", "type": "link_row",
                            "link_row_table_id": T_CONTACTS})

    print("\n" + "=" * 60)
    print(f"T_SMS_MESSAGES = {tid}")
    print("=" * 60)
    print("\nPaste into execution/hub/constants.py:")
    print(f"  T_SMS_MESSAGES = {tid}")


if __name__ == "__main__":
    main()
