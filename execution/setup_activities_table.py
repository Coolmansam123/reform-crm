#!/usr/bin/env python3
"""
Create a unified `Activities` table in the CRM database (DB 197) replacing the
three legacy per-domain activity tables (T_ATT_ACTS 784, T_GOR_ACTS 791,
T_COM_ACTS 798). The new table has link_rows to both Companies (820) and
Contacts (821) so activities can be attributed to a person when we have one.

Idempotent.

Usage:
    python execution/setup_activities_table.py
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL      = os.getenv("BASEROW_URL")
BASEROW_EMAIL    = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
DATABASE_ID      = 197  # Reform Chiropractic CRM
T_COMPANIES      = 820
T_CONTACTS       = 821


# ─── Auth ────────────────────────────────────────────────────────────────────

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


# ─── Helpers ─────────────────────────────────────────────────────────────────

def list_tables(database_id):
    r = requests.get(
        f"{BASEROW_URL}/api/database/tables/database/{database_id}/",
        headers=headers(),
    )
    r.raise_for_status()
    return r.json()

def create_table(database_id, name):
    r = requests.post(
        f"{BASEROW_URL}/api/database/tables/database/{database_id}/",
        headers=headers(),
        json={"name": name},
    )
    r.raise_for_status()
    return r.json()

def get_fields(table_id):
    r = requests.get(f"{BASEROW_URL}/api/database/fields/table/{table_id}/", headers=headers())
    r.raise_for_status()
    return r.json()

def create_field(table_id, field_config):
    r = requests.post(
        f"{BASEROW_URL}/api/database/fields/table/{table_id}/",
        headers=headers(),
        json=field_config,
    )
    if r.status_code == 200:
        print(f"    + {field_config['name']} ({field_config['type']})")
        return r.json()
    print(f"    WARN: Failed '{field_config['name']}': {r.status_code} {r.text[:200]}")
    return None

def delete_field(field_id):
    r = requests.delete(f"{BASEROW_URL}/api/database/fields/{field_id}/", headers=headers())
    return r.status_code in (200, 204)

def rename_primary(table_id, new_name):
    fields = get_fields(table_id)
    primary = next((f for f in fields if f.get("primary")), None)
    if primary and primary["name"] != new_name:
        r = requests.patch(
            f"{BASEROW_URL}/api/database/fields/{primary['id']}/",
            headers=headers(),
            json={"name": new_name},
        )
        if r.status_code == 200:
            print(f"    = Renamed primary field to '{new_name}'")

def get_or_create_table(db_id, name):
    tables = list_tables(db_id)
    existing = next((t for t in tables if t["name"] == name), None)
    if existing:
        print(f"  Table '{name}' already exists (ID: {existing['id']})")
        return existing["id"], False
    print(f"  Creating table '{name}'...")
    t = create_table(db_id, name)
    print(f"  Created '{name}' (ID: {t['id']})")
    return t["id"], True

def ensure_fields(table_id, fields_config):
    existing = get_fields(table_id)
    existing_names = {f["name"] for f in existing}
    for fc in fields_config:
        if fc["name"] in existing_names:
            print(f"    = {fc['name']} (exists)")
        else:
            create_field(table_id, fc)
    # Remove default fields we aren't using
    existing = get_fields(table_id)
    for f in existing:
        if f["name"] in {"Notes", "Active"} and not f.get("primary", False):
            if not any(fc["name"] == f["name"] for fc in fields_config):
                if delete_field(f["id"]):
                    print(f"    - Removed default '{f['name']}'")


ACTIVITIES_FIELDS = [
    # Primary = Summary (defaults to Baserow's "Name", we'll rename)
    {"name": "Date", "type": "date", "date_format": "US", "date_include_time": False},
    {"name": "Type", "type": "single_select", "select_options": [
        {"value": "Call",      "color": "blue"},
        {"value": "Email",     "color": "orange"},
        {"value": "In Person", "color": "green"},
        {"value": "Drop Off",  "color": "purple"},
        {"value": "Text",      "color": "yellow"},
        {"value": "Other",     "color": "light-gray"},
    ]},
    {"name": "Outcome", "type": "single_select", "select_options": [
        {"value": "Interested",      "color": "green"},
        {"value": "Not Interested",  "color": "red"},
        {"value": "Follow-Up Needed","color": "orange"},
        {"value": "Left Voicemail",  "color": "yellow"},
        {"value": "No Answer",       "color": "light-gray"},
        {"value": "Meeting Scheduled","color": "blue"},
        {"value": "Partnership Begun","color": "dark-green"},
    ]},
    {"name": "Contact Person", "type": "text"},  # freeform fallback when Contact link is empty
    {"name": "Summary",        "type": "long_text"},
    {"name": "Follow-Up Date", "type": "date", "date_format": "US", "date_include_time": False},
    {"name": "Author",         "type": "text"},
    {"name": "Created",        "type": "date", "date_format": "US", "date_include_time": True},

    # Migration metadata
    {"name": "Legacy Source", "type": "single_select", "select_options": [
        {"value": "attorney_act",  "color": "purple"},
        {"value": "guerilla_act",  "color": "orange"},
        {"value": "community_act", "color": "green"},
        {"value": "crm_native",    "color": "light-gray"},
    ]},
    {"name": "Legacy ID", "type": "number", "number_decimal_places": 0},
]


def main():
    print("=" * 60)
    print("Setting up unified Activities table in CRM DB (197)")
    print("=" * 60)

    print("\n1. Activities table")
    acts_id, _ = get_or_create_table(DATABASE_ID, "Activities")
    rename_primary(acts_id, "Summary")
    ensure_fields(acts_id, ACTIVITIES_FIELDS)

    # Link_rows last (must exist before adding)
    existing = get_fields(acts_id)
    existing_names = {f["name"] for f in existing}
    if "Company" not in existing_names:
        create_field(acts_id, {
            "name": "Company",
            "type": "link_row",
            "link_row_table_id": T_COMPANIES,
        })
    if "Contact" not in existing_names:
        create_field(acts_id, {
            "name": "Contact",
            "type": "link_row",
            "link_row_table_id": T_CONTACTS,
        })

    print("\n" + "=" * 60)
    print(f"T_ACTIVITIES = {acts_id}")
    print("=" * 60)
    print("\nPaste into execution/hub/constants.py:")
    print(f"  T_ACTIVITIES = {acts_id}")


if __name__ == "__main__":
    main()
