#!/usr/bin/env python3
"""
Create Baserow tables for the Gorilla Route Management system.

Creates 2 tables in Database 203 (Gorilla Marketing):
  1. T_GOR_ROUTES       — admin-created route definitions per day/rep
  2. T_GOR_ROUTE_STOPS  — ordered venue stops within each route

Idempotent: skips table/field creation if they already exist.
Prints table IDs at the end — add them to .env and Modal secrets.

Usage:
    python execution/setup_gorilla_routes.py
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL   = os.getenv("BASEROW_URL")
BASEROW_EMAIL = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
DATABASE_ID   = 203  # Gorilla Marketing

T_GOR_VENUES = 790  # existing venues table (link target)

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
    """Create fields that don't already exist."""
    existing = get_fields(table_id)
    existing_names = {f["name"] for f in existing}

    for field_config in fields_config:
        if field_config["name"] in existing_names:
            print(f"    = {field_config['name']} (already exists)")
        else:
            create_field(table_id, field_config)

    # Remove Baserow auto-created default fields we don't need
    existing = get_fields(table_id)
    for f in existing:
        if f["name"] in {"Notes", "Active"} and not f.get("primary", False):
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
        print(f"    {f['name']:30s} {f['type']}{extras}")


# ─── Table Definitions ───────────────────────────────────────────────────────

ROUTES_FIELDS = [
    {"name": "Date",        "type": "date",   "date_format": "US", "date_include_time": False},
    {"name": "Assigned To", "type": "text"},
    {"name": "Status",      "type": "single_select", "select_options": [
        {"value": "Draft",     "color": "light-gray"},
        {"value": "Active",    "color": "green"},
        {"value": "Completed", "color": "blue"},
    ]},
    {"name": "Notes",       "type": "long_text"},
]

# Route Stops fields — link_row to Routes added after routes table is created
ROUTE_STOPS_FIELDS_BASE = [
    {"name": "Stop Order",  "type": "number", "number_decimal_places": 0},
    {"name": "Status",      "type": "single_select", "select_options": [
        {"value": "Pending", "color": "light-gray"},
        {"value": "Visited", "color": "green"},
        {"value": "Skipped", "color": "orange"},
    ]},
    {"name": "Notes",       "type": "long_text"},
]


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("\nGorilla Routes — Baserow Table Setup")
    print("=" * 50)

    # 1. Create T_GOR_ROUTES
    print("\n[1] T_GOR_ROUTES")
    routes_id, _ = get_or_create_table(DATABASE_ID, "T_GOR_ROUTES")
    ensure_fields(routes_id, ROUTES_FIELDS)
    print_schema(routes_id, "T_GOR_ROUTES")

    # 2. Create T_GOR_ROUTE_STOPS
    print("\n[2] T_GOR_ROUTE_STOPS")
    stops_id, _ = get_or_create_table(DATABASE_ID, "T_GOR_ROUTE_STOPS")

    # Add link_row fields — these reference other tables and must be created first
    stops_link_fields = [
        {
            "name": "Route",
            "type": "link_row",
            "link_row_table_id": routes_id,
        },
        {
            "name": "Venue",
            "type": "link_row",
            "link_row_table_id": T_GOR_VENUES,
        },
    ]
    # Merge link fields with base fields
    ensure_fields(stops_id, stops_link_fields + ROUTE_STOPS_FIELDS_BASE)
    print_schema(stops_id, "T_GOR_ROUTE_STOPS")

    # ─── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("DONE. Add these to .env and Modal secrets:\n")
    print(f"  T_GOR_ROUTES={routes_id}")
    print(f"  T_GOR_ROUTE_STOPS={stops_id}")
    print()
    print("Update Modal secrets with:")
    print(f"  modal secret create outreach-hub-secrets ... T_GOR_ROUTES={routes_id} T_GOR_ROUTE_STOPS={stops_id} --force")
    print()
    print("Then redeploy: PYTHONUTF8=1 modal deploy execution/modal_outreach_hub.py")


if __name__ == "__main__":
    main()
