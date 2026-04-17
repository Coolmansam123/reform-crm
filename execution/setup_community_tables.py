#!/usr/bin/env python3
"""
Create Baserow tables for the Community Outreach platform.

Creates 3 tables in Database 204 (Community Outreach):
  1. Community Organizations — chambers, clubs, churches, schools, etc.
  2. Community Activities    — outreach activity log per organization
  3. Drop Boxes              — massage/drop box placement tracking

Idempotent: skips table/field creation if they already exist.
Prints table IDs at the end — update generate_community_map.py and
sync_community_to_baserow.py if IDs differ from defaults.

Usage:
    python execution/setup_community_tables.py
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL = os.getenv("BASEROW_URL")
BASEROW_EMAIL = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
DATABASE_ID = 204  # Community Outreach

# ─── JWT Auth ────────────────────────────────────────────────────────────────

_jwt_token = None
_jwt_time = 0


def fresh_token():
    global _jwt_token, _jwt_time
    if _jwt_token is None or (time.time() - _jwt_time) > 480:
        r = requests.post(f"{BASEROW_URL}/api/user/token-auth/", json={
            "email": BASEROW_EMAIL, "password": BASEROW_PASSWORD,
        })
        r.raise_for_status()
        _jwt_token = r.json()["access_token"]
        _jwt_time = time.time()
    return _jwt_token


def headers():
    return {"Authorization": f"JWT {fresh_token()}", "Content-Type": "application/json"}


# ─── Baserow Helpers ─────────────────────────────────────────────────────────

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
    r = requests.get(
        f"{BASEROW_URL}/api/database/fields/table/{table_id}/",
        headers=headers(),
    )
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
    else:
        print(f"    WARN: Failed to create '{field_config['name']}': {r.status_code} {r.text[:200]}")
        return None


def delete_field(field_id):
    r = requests.delete(
        f"{BASEROW_URL}/api/database/fields/{field_id}/",
        headers=headers(),
    )
    return r.status_code in (200, 204)


def get_or_create_table(database_id, name):
    """Return (table_id, created). Creates table if it doesn't exist."""
    tables = list_tables(database_id)
    existing = next((t for t in tables if t["name"] == name), None)
    if existing:
        print(f"  Table '{name}' already exists (ID: {existing['id']})")
        return existing["id"], False
    else:
        print(f"  Creating table '{name}'...")
        table = create_table(database_id, name)
        print(f"  Created '{name}' (ID: {table['id']})")
        return table["id"], True


def ensure_fields(table_id, fields_config):
    """Create fields that don't already exist. Returns dict of name→field_id."""
    existing = get_fields(table_id)
    existing_names = {f["name"] for f in existing}

    for field_config in fields_config:
        if field_config["name"] in existing_names:
            print(f"    = {field_config['name']} (already exists)")
        else:
            create_field(table_id, field_config)

    # Remove Baserow auto-created default fields we don't need,
    # but only if they're not part of our intended schema.
    intended_names = {fc["name"] for fc in fields_config}
    existing = get_fields(table_id)
    for f in existing:
        if f["name"] in {"Notes", "Active"} and not f.get("primary", False) and f["name"] not in intended_names:
            if delete_field(f["id"]):
                print(f"    - Removed default field '{f['name']}'")

    return {f["name"]: f["id"] for f in get_fields(table_id)}


def print_schema(table_id, label):
    fields = get_fields(table_id)
    print(f"\n  Schema for {label} (Table {table_id}):")
    for f in fields:
        extras = ""
        if f["type"] == "single_select":
            opts = [o["value"] for o in f.get("select_options", [])]
            extras = f" [{', '.join(opts)}]"
        elif f["type"] == "link_row":
            extras = f" -> table {f.get('link_row_table_id', '?')}"
        print(f"    {f['name']:25s} {f['type']}{extras}")


# ─── Table Definitions ───────────────────────────────────────────────────────

COMMUNITY_ORGS_FIELDS = [
    {"name": "Type", "type": "single_select", "select_options": [
        {"value": "Chamber of Commerce", "color": "blue"},
        {"value": "Lions Club", "color": "yellow"},
        {"value": "Rotary Club", "color": "light-blue"},
        {"value": "BNI Chapter", "color": "red"},
        {"value": "Networking Mixer", "color": "orange"},
        {"value": "Church", "color": "brown"},
        {"value": "Parks & Rec", "color": "green"},
        {"value": "Community Center", "color": "pink"},
        {"value": "High School", "color": "purple"},
        {"value": "Other", "color": "light-gray"},
    ]},
    {"name": "Address", "type": "text"},
    {"name": "Phone", "type": "text"},
    {"name": "Contact Person", "type": "text"},
    {"name": "Email", "type": "email"},
    {"name": "Website", "type": "url"},
    {"name": "Latitude", "type": "text"},
    {"name": "Longitude", "type": "text"},
    {"name": "Rating", "type": "text"},
    {"name": "Reviews", "type": "number", "number_decimal_places": 0},
    {"name": "Distance (mi)", "type": "text"},
    {"name": "Google Place ID", "type": "text"},
    {"name": "Contact Status", "type": "single_select", "select_options": [
        {"value": "Not Contacted", "color": "light-blue"},
        {"value": "Contacted", "color": "yellow"},
        {"value": "In Discussion", "color": "orange"},
        {"value": "Active Partner", "color": "green"},
    ]},
    {"name": "Outreach Goal", "type": "single_select", "select_options": [
        {"value": "Event Presence", "color": "blue"},
        {"value": "Referral Partnership", "color": "green"},
        {"value": "Sponsorship", "color": "orange"},
        {"value": "Both", "color": "purple"},
    ]},
    {"name": "Notes", "type": "long_text"},
    {"name": "Google Maps URL", "type": "url"},
    {"name": "Yelp Search URL", "type": "url"},
]

DROP_BOXES_FIELDS = [
    # link_row "Organization" created separately
    {"name": "Date Placed", "type": "date", "date_format": "US", "date_include_time": False},
    {"name": "Date Removed", "type": "date", "date_format": "US", "date_include_time": False},
    {"name": "Location Notes", "type": "text"},
    {"name": "Status", "type": "single_select", "select_options": [
        {"value": "Active", "color": "green"},
        {"value": "Picked Up", "color": "blue"},
        {"value": "Lost", "color": "red"},
    ]},
    {"name": "Leads Generated", "type": "number", "number_decimal_places": 0},
    {"name": "Notes", "type": "long_text"},
]

COMMUNITY_ACTIVITIES_FIELDS = [
    # link_row created separately
    {"name": "Date", "type": "date", "date_format": "US", "date_include_time": False},
    {"name": "Type", "type": "single_select", "select_options": [
        {"value": "Call", "color": "blue"},
        {"value": "Email", "color": "light-blue"},
        {"value": "Drop-In", "color": "green"},
        {"value": "Meeting", "color": "orange"},
        {"value": "Event", "color": "purple"},
        {"value": "Mail", "color": "dark-gray"},
        {"value": "Other", "color": "light-gray"},
    ]},
    {"name": "Outcome", "type": "single_select", "select_options": [
        {"value": "No Answer", "color": "light-gray"},
        {"value": "Left Message", "color": "yellow"},
        {"value": "Spoke With", "color": "green"},
        {"value": "Scheduled Meeting", "color": "blue"},
        {"value": "Declined", "color": "red"},
        {"value": "Follow-Up Needed", "color": "orange"},
    ]},
    {"name": "Contact Person", "type": "text"},
    {"name": "Summary", "type": "long_text"},
    {"name": "Follow-Up Date", "type": "date", "date_format": "US", "date_include_time": False},
    {"name": "Created By", "type": "text"},
]


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 60)
    print("COMMUNITY OUTREACH TABLE SETUP")
    print("=" * 60)

    # ── 1. Community Organizations ────────────────────────────────
    print("\n[1/3] Community Organizations")
    orgs_id, _ = get_or_create_table(DATABASE_ID, "Community Organizations")
    print("  Creating fields...")
    ensure_fields(orgs_id, COMMUNITY_ORGS_FIELDS)
    print_schema(orgs_id, "Community Organizations")

    # ── 2. Community Activities ───────────────────────────────────
    print("\n[2/3] Community Activities")
    activities_id, _ = get_or_create_table(DATABASE_ID, "Community Activities")

    existing_names = {f["name"] for f in get_fields(activities_id)}
    if "Organization" not in existing_names:
        print("  Creating link_row field 'Organization' -> Community Organizations...")
        create_field(activities_id, {
            "name": "Organization",
            "type": "link_row",
            "link_row_table_id": orgs_id,
        })
    else:
        print("    = Organization (already exists)")

    print("  Creating fields...")
    ensure_fields(activities_id, COMMUNITY_ACTIVITIES_FIELDS)
    print_schema(activities_id, "Community Activities")

    # ── 3. Drop Boxes ─────────────────────────────────────────────
    print("\n[3/3] Drop Boxes")
    dropboxes_id, _ = get_or_create_table(DATABASE_ID, "Drop Boxes")

    existing_names = {f["name"] for f in get_fields(dropboxes_id)}
    if "Organization" not in existing_names:
        print("  Creating link_row field 'Organization' -> Community Organizations...")
        create_field(dropboxes_id, {
            "name": "Organization",
            "type": "link_row",
            "link_row_table_id": orgs_id,
        })
    else:
        print("    = Organization (already exists)")

    print("  Creating fields...")
    ensure_fields(dropboxes_id, DROP_BOXES_FIELDS)
    print_schema(dropboxes_id, "Drop Boxes")

    # ── Summary ───────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("DONE — Table IDs:")
    print(f"  Community Organizations: {orgs_id}")
    print(f"  Community Activities:    {activities_id}")
    print(f"  Drop Boxes:              {dropboxes_id}")
    print("=" * 60)
    print("\nAdd these to your .env file:")
    print(f"  COMMUNITY_VENUES_TABLE_ID={orgs_id}")
    print(f"  COMMUNITY_ACTIVITIES_TABLE_ID={activities_id}")
    print(f"  COMMUNITY_DROP_BOXES_TABLE_ID={dropboxes_id}")
    print("\nIf these IDs differ from the defaults in other scripts,")
    print("update the TABLE_ID constants at the top of:")
    print("  - execution/sync_community_to_baserow.py")
    print("  - execution/generate_community_map.py")


if __name__ == "__main__":
    main()
