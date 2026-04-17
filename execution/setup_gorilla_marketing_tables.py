#!/usr/bin/env python3
"""
Create Baserow tables for the Gorilla Marketing platform.

Creates 3 tables in Database 203 (Gorilla Marketing):
  1. Business Venues     — gyms, yoga studios, health stores, wellness clinics
  2. Business Activities — outreach activity log per business
  3. Influencers         — scaffolded for future influencer collab tracking

Idempotent: skips table/field creation if they already exist.
Prints table IDs at the end — update generate_gorilla_map.py and
sync_businesses_to_baserow.py if IDs differ from defaults.

Usage:
    python execution/setup_gorilla_marketing_tables.py
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
DATABASE_ID = 203  # Gorilla Marketing

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
        print(f"    {f['name']:25s} {f['type']}{extras}")


# ─── Table Definitions ───────────────────────────────────────────────────────

BUSINESS_VENUES_FIELDS = [
    {"name": "Type", "type": "single_select", "select_options": [
        {"value": "Gym", "color": "blue"},
        {"value": "Yoga Studio", "color": "green"},
        {"value": "Health Store", "color": "orange"},
        {"value": "Chiropractor/Wellness", "color": "purple"},
    ]},
    {"name": "Address", "type": "text"},
    {"name": "Phone", "type": "text"},
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
        {"value": "Partner", "color": "green"},
    ]},
    {"name": "Outreach Goal", "type": "single_select", "select_options": [
        {"value": "Referral Partner", "color": "blue"},
        {"value": "Co-Marketing", "color": "purple"},
        {"value": "Both", "color": "green"},
    ]},
    {"name": "Notes", "type": "long_text"},
    {"name": "Google Reviews JSON", "type": "long_text"},
    {"name": "Google Maps URL", "type": "url"},
    {"name": "Yelp Search URL", "type": "url"},
]

BUSINESS_ACTIVITIES_FIELDS = [
    # link_row created separately
    {"name": "Date", "type": "date", "date_format": "US", "date_include_time": False},
    {"name": "Type", "type": "single_select", "select_options": [
        {"value": "Call", "color": "blue"},
        {"value": "Email", "color": "light-blue"},
        {"value": "Drop-In", "color": "green"},
        {"value": "Meeting", "color": "orange"},
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

INFLUENCERS_FIELDS = [
    {"name": "Platform", "type": "single_select", "select_options": [
        {"value": "Instagram", "color": "pink"},
        {"value": "TikTok", "color": "dark-gray"},
        {"value": "YouTube", "color": "red"},
        {"value": "Facebook", "color": "blue"},
        {"value": "Other", "color": "light-gray"},
    ]},
    {"name": "Handle / URL", "type": "url"},
    {"name": "Niche", "type": "single_select", "select_options": [
        {"value": "Fitness", "color": "blue"},
        {"value": "Wellness", "color": "green"},
        {"value": "Nutrition", "color": "orange"},
        {"value": "Lifestyle", "color": "purple"},
        {"value": "Chiro/Health", "color": "light-blue"},
    ]},
    {"name": "Followers", "type": "number", "number_decimal_places": 0},
    {"name": "Engagement Rate", "type": "text"},
    {"name": "Location", "type": "text"},
    {"name": "Contact Status", "type": "single_select", "select_options": [
        {"value": "Not Contacted", "color": "light-blue"},
        {"value": "Contacted", "color": "yellow"},
        {"value": "In Discussion", "color": "orange"},
        {"value": "Active Collab", "color": "green"},
    ]},
    {"name": "Collab Type", "type": "single_select", "select_options": [
        {"value": "Sponsored Post", "color": "blue"},
        {"value": "Giveaway", "color": "orange"},
        {"value": "Ambassador", "color": "green"},
        {"value": "Story Feature", "color": "purple"},
        {"value": "Other", "color": "light-gray"},
    ]},
    {"name": "Email", "type": "email"},
    {"name": "Notes", "type": "long_text"},
]


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 60)
    print("GORILLA MARKETING TABLE SETUP")
    print("=" * 60)

    # ── 1. Business Venues ────────────────────────────────────────
    print("\n[1/3] Business Venues")
    venues_id, _ = get_or_create_table(DATABASE_ID, "Business Venues")
    print("  Creating fields...")
    ensure_fields(venues_id, BUSINESS_VENUES_FIELDS)
    print_schema(venues_id, "Business Venues")

    # ── 2. Business Activities ────────────────────────────────────
    print("\n[2/3] Business Activities")
    activities_id, _ = get_or_create_table(DATABASE_ID, "Business Activities")

    # Create the link_row field first
    existing_names = {f["name"] for f in get_fields(activities_id)}
    if "Business" not in existing_names:
        print("  Creating link_row field 'Business' -> Business Venues...")
        create_field(activities_id, {
            "name": "Business",
            "type": "link_row",
            "link_row_table_id": venues_id,
        })
    else:
        print("    = Business (already exists)")

    print("  Creating fields...")
    ensure_fields(activities_id, BUSINESS_ACTIVITIES_FIELDS)
    print_schema(activities_id, "Business Activities")

    # ── 3. Influencers ────────────────────────────────────────────
    print("\n[3/3] Influencers")
    influencers_id, _ = get_or_create_table(DATABASE_ID, "Influencers")
    print("  Creating fields...")
    ensure_fields(influencers_id, INFLUENCERS_FIELDS)
    print_schema(influencers_id, "Influencers")

    # ── Summary ───────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("DONE — Table IDs:")
    print(f"  Business Venues:     {venues_id}")
    print(f"  Business Activities: {activities_id}")
    print(f"  Influencers:         {influencers_id}")
    print("=" * 60)
    print("\nIf these IDs differ from the defaults in other scripts,")
    print("update the TABLE_IDs constants at the top of:")
    print("  - execution/sync_businesses_to_baserow.py")
    print("  - execution/generate_gorilla_map.py")
    print("  - execution/generate_unified_map.py")


if __name__ == "__main__":
    main()
