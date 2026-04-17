#!/usr/bin/env python3
"""
Create the Activities table in Baserow for tracking outreach to law firms.

Links to the Law Firms table (768) via a link_row field.
Idempotent: skips table/field creation if they already exist.

Usage:
    python execution/setup_activity_log.py
"""

import os
import sys
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL = os.getenv("BASEROW_URL")
BASEROW_EMAIL = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
DATABASE_ID = 198  # Law Firm Directory database (same as Law Firms table 768)
LAW_FIRMS_TABLE_ID = 768

ACTIVITIES_TABLE_NAME = "Activities"

# Fields to create (in order)
FIELDS = [
    {
        "name": "Date",
        "type": "date",
        "date_format": "US",
        "date_include_time": False,
    },
    {
        "name": "Type",
        "type": "single_select",
        "select_options": [
            {"value": "Call", "color": "blue"},
            {"value": "Email", "color": "light-blue"},
            {"value": "Drop-In", "color": "green"},
            {"value": "Lunch/Meeting", "color": "orange"},
            {"value": "Mail", "color": "dark-gray"},
            {"value": "Other", "color": "light-gray"},
        ],
    },
    {
        "name": "Outcome",
        "type": "single_select",
        "select_options": [
            {"value": "No Answer", "color": "light-gray"},
            {"value": "Left Message", "color": "yellow"},
            {"value": "Spoke With", "color": "green"},
            {"value": "Scheduled Meeting", "color": "blue"},
            {"value": "Declined", "color": "red"},
            {"value": "Follow-Up Needed", "color": "orange"},
        ],
    },
    {
        "name": "Contact Person",
        "type": "text",
    },
    {
        "name": "Summary",
        "type": "long_text",
    },
    {
        "name": "Follow-Up Date",
        "type": "date",
        "date_format": "US",
        "date_include_time": False,
    },
    {
        "name": "Created By",
        "type": "text",
    },
]

# JWT token management
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


def list_tables(database_id):
    """List all tables in the database."""
    r = requests.get(
        f"{BASEROW_URL}/api/database/tables/database/{database_id}/",
        headers=headers(),
    )
    r.raise_for_status()
    return r.json()


def create_table(database_id, name):
    """Create a new table. Returns the table object."""
    r = requests.post(
        f"{BASEROW_URL}/api/database/tables/database/{database_id}/",
        headers=headers(),
        json={"name": name},
    )
    r.raise_for_status()
    return r.json()


def get_fields(table_id):
    """Get all fields for a table."""
    r = requests.get(
        f"{BASEROW_URL}/api/database/fields/table/{table_id}/",
        headers=headers(),
    )
    r.raise_for_status()
    return r.json()


def create_field(table_id, field_config):
    """Create a field on a table."""
    r = requests.post(
        f"{BASEROW_URL}/api/database/fields/table/{table_id}/",
        headers=headers(),
        json=field_config,
    )
    if r.status_code == 200:
        print(f"  Created field '{field_config['name']}' ({field_config['type']})")
        return r.json()
    else:
        print(f"  WARN: Failed to create '{field_config['name']}': {r.status_code} {r.text[:200]}")
        return None


def main():
    print("=" * 60)
    print("ACTIVITY LOG TABLE SETUP")
    print("=" * 60)

    # Check if table already exists
    tables = list_tables(DATABASE_ID)
    existing = next((t for t in tables if t["name"] == ACTIVITIES_TABLE_NAME), None)

    if existing:
        table_id = existing["id"]
        print(f"Table '{ACTIVITIES_TABLE_NAME}' already exists (ID: {table_id})")
    else:
        print(f"Creating table '{ACTIVITIES_TABLE_NAME}'...")
        table = create_table(DATABASE_ID, ACTIVITIES_TABLE_NAME)
        table_id = table["id"]
        print(f"Created table '{ACTIVITIES_TABLE_NAME}' (ID: {table_id})")

    # Get existing fields
    existing_fields = get_fields(table_id)
    existing_names = {f["name"] for f in existing_fields}
    print(f"Existing fields: {existing_names}")

    # Create the link_row field to Law Firms first
    if "Law Firm" not in existing_names:
        print(f"\nCreating link_row field 'Law Firm' -> table {LAW_FIRMS_TABLE_ID}...")
        create_field(table_id, {
            "name": "Law Firm",
            "type": "link_row",
            "link_row_table_id": LAW_FIRMS_TABLE_ID,
        })
    else:
        print("  Field 'Law Firm' already exists, skipping")

    # Create remaining fields
    print(f"\nCreating fields...")
    for field_config in FIELDS:
        if field_config["name"] in existing_names:
            print(f"  Field '{field_config['name']}' already exists, skipping")
            continue
        create_field(table_id, field_config)

    # Clean up default fields that Baserow auto-creates (Name, Notes, Active)
    existing_fields = get_fields(table_id)
    default_fields_to_remove = {"Notes", "Active"}
    for f in existing_fields:
        if f["name"] in default_fields_to_remove and not f.get("primary", False):
            r = requests.delete(
                f"{BASEROW_URL}/api/database/fields/{f['id']}/",
                headers=headers(),
            )
            if r.status_code in (200, 204):
                print(f"  Removed default field '{f['name']}'")

    # Print final schema
    print(f"\n--- Final Schema (Table ID: {table_id}) ---")
    final_fields = get_fields(table_id)
    for f in final_fields:
        extras = ""
        if f["type"] == "single_select":
            opts = [o["value"] for o in f.get("select_options", [])]
            extras = f" [{', '.join(opts)}]"
        elif f["type"] == "link_row":
            extras = f" -> table {f.get('link_row_table_id', '?')}"
        print(f"  {f['name']:20s} {f['type']}{extras}")

    print(f"\nActivities table ID: {table_id}")
    print("Save this ID — it will be needed by the map generator.")
    print("Done!")

    return table_id


if __name__ == "__main__":
    main()
