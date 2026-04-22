#!/usr/bin/env python3
"""
Create the 'Operations Hub' Baserow database (if missing) and the Tickets +
Ticket Comments tables inside it.

Idempotent: skips application/table/field creation if they already exist.
Prints the table IDs at the end — paste into execution/hub/constants.py.

Usage:
    python execution/setup_tickets_tables.py
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL      = os.getenv("BASEROW_URL")
BASEROW_EMAIL    = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
WORKSPACE_ID     = 133  # TechOps's workspace — holds all Reform DBs
DATABASE_NAME    = "Operations Hub"


# ─── JWT Auth ────────────────────────────────────────────────────────────────

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

def list_applications():
    r = requests.get(f"{BASEROW_URL}/api/applications/", headers=headers())
    r.raise_for_status()
    return r.json()

def create_database(workspace_id, name):
    r = requests.post(
        f"{BASEROW_URL}/api/applications/workspace/{workspace_id}/",
        headers=headers(),
        json={"type": "database", "name": name},
    )
    r.raise_for_status()
    return r.json()

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
    print(f"    WARN: Failed to create '{field_config['name']}': {r.status_code} {r.text[:200]}")
    return None

def delete_field(field_id):
    r = requests.delete(
        f"{BASEROW_URL}/api/database/fields/{field_id}/",
        headers=headers(),
    )
    return r.status_code in (200, 204)

def get_or_create_database(workspace_id, name):
    apps = list_applications()
    existing = next((a for a in apps if a["type"] == "database" and a["name"] == name), None)
    if existing:
        print(f"  Database '{name}' already exists (ID: {existing['id']})")
        return existing["id"], False
    print(f"  Creating database '{name}' in workspace {workspace_id}...")
    app = create_database(workspace_id, name)
    print(f"  Created '{name}' (ID: {app['id']})")
    return app["id"], True

def get_or_create_table(db_id, name):
    tables = list_tables(db_id)
    existing = next((t for t in tables if t["name"] == name), None)
    if existing:
        print(f"  Table '{name}' already exists (ID: {existing['id']})")
        return existing["id"], False
    print(f"  Creating table '{name}'...")
    table = create_table(db_id, name)
    print(f"  Created '{name}' (ID: {table['id']})")
    return table["id"], True

def ensure_fields(table_id, fields_config):
    existing = get_fields(table_id)
    existing_names = {f["name"] for f in existing}
    for field_config in fields_config:
        if field_config["name"] in existing_names:
            print(f"    = {field_config['name']} (already exists)")
        else:
            create_field(table_id, field_config)
    # Remove auto-created default fields that we aren't using
    existing = get_fields(table_id)
    for f in existing:
        if f["name"] in {"Notes", "Active"} and not f.get("primary", False):
            if delete_field(f["id"]):
                print(f"    - Removed default field '{f['name']}'")


# ─── Table Schemas ───────────────────────────────────────────────────────────

TICKETS_FIELDS = [
    # Primary-ish — Title serves as the display. Baserow's auto primary field
    # gets renamed below if needed.
    {"name": "Status", "type": "single_select", "select_options": [
        {"value": "Open",        "color": "blue"},
        {"value": "In Progress", "color": "orange"},
        {"value": "Waiting",     "color": "yellow"},
        {"value": "Resolved",    "color": "green"},
        {"value": "Closed",      "color": "light-gray"},
    ]},
    {"name": "Priority", "type": "single_select", "select_options": [
        {"value": "Low",      "color": "light-gray"},
        {"value": "Normal",   "color": "blue"},
        {"value": "High",     "color": "orange"},
        {"value": "Critical", "color": "red"},
    ]},
    {"name": "Category", "type": "single_select", "select_options": [
        {"value": "Software", "color": "blue"},
        {"value": "Hardware", "color": "orange"},
        {"value": "Network",  "color": "purple"},
        {"value": "Account",  "color": "green"},
        {"value": "Other",    "color": "light-gray"},
    ]},
    {"name": "Description",      "type": "long_text"},
    {"name": "Reporter",         "type": "text"},
    {"name": "Assignee",         "type": "text"},
    {"name": "Created",          "type": "date", "date_format": "US", "date_include_time": True},
    {"name": "Updated",          "type": "date", "date_format": "US", "date_include_time": True},
    {"name": "Resolution Notes", "type": "long_text"},
]

COMMENTS_FIELDS = [
    {"name": "Author", "type": "text"},
    {"name": "Body",   "type": "long_text"},
    {"name": "Kind", "type": "single_select", "select_options": [
        {"value": "comment",        "color": "blue"},
        {"value": "status_change",  "color": "orange"},
        {"value": "assignment",     "color": "purple"},
        {"value": "creation",       "color": "green"},
    ]},
    {"name": "Created", "type": "date", "date_format": "US", "date_include_time": True},
]


# ─── Main ────────────────────────────────────────────────────────────────────

def rename_primary_to_title(table_id):
    """Baserow auto-creates a primary 'Name' field on new tables — rename to 'Title'."""
    fields = get_fields(table_id)
    primary = next((f for f in fields if f.get("primary")), None)
    if primary and primary["name"] != "Title":
        r = requests.patch(
            f"{BASEROW_URL}/api/database/fields/{primary['id']}/",
            headers=headers(),
            json={"name": "Title"},
        )
        if r.status_code == 200:
            print(f"    = Renamed primary field to 'Title'")

def main():
    print("=" * 60)
    print(f"Setting up '{DATABASE_NAME}' database + Tickets tables")
    print("=" * 60)

    # ── Database ─────────────────────────────────────────────
    print("\n1. Database")
    db_id, _ = get_or_create_database(WORKSPACE_ID, DATABASE_NAME)

    # ── Tickets ──────────────────────────────────────────────
    print("\n2. Tickets table")
    tickets_id, _ = get_or_create_table(db_id, "Tickets")
    rename_primary_to_title(tickets_id)
    ensure_fields(tickets_id, TICKETS_FIELDS)

    # ── Ticket Comments ──────────────────────────────────────
    print("\n3. Ticket Comments table")
    comments_id, _ = get_or_create_table(db_id, "Ticket Comments")
    ensure_fields(comments_id, COMMENTS_FIELDS)

    # Ticket link_row — must happen after both tables exist
    existing = get_fields(comments_id)
    if not any(f["name"] == "Ticket" for f in existing):
        create_field(comments_id, {
            "name": "Ticket",
            "type": "link_row",
            "link_row_table_id": tickets_id,
        })

    # ── Summary ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"Operations Hub DB = {db_id}")
    print(f"T_TICKETS         = {tickets_id}")
    print(f"T_TICKET_COMMENTS = {comments_id}")
    print("=" * 60)
    print("\nPaste these into execution/hub/constants.py:")
    print(f"  T_TICKETS         = {tickets_id}")
    print(f"  T_TICKET_COMMENTS = {comments_id}")


if __name__ == "__main__":
    main()
