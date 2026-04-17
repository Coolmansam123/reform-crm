#!/usr/bin/env python3
"""
Create Baserow tables for Events and Leads in the Gorilla Marketing database.

Creates 2 tables in Database 203:
  1. T_EVENTS — dedicated event entities with form slugs
  2. T_LEADS  — patient lead database from lead capture forms

Idempotent: skips table/field creation if they already exist.
Prints table IDs at the end — add them to .env and Modal secrets.

Usage:
    python execution/setup_events_leads_tables.py
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL      = os.getenv("BASEROW_URL")
BASEROW_EMAIL    = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
DATABASE_ID      = 203  # Gorilla Marketing

T_GOR_VENUES = 790

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

def list_tables(db_id):
    r = requests.get(f"{BASEROW_URL}/api/database/tables/database/{db_id}/", headers=headers())
    r.raise_for_status()
    return r.json()

def create_table(db_id, name):
    r = requests.post(
        f"{BASEROW_URL}/api/database/tables/database/{db_id}/",
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
    else:
        print(f"    WARN: Failed to create '{field_config['name']}': {r.status_code} {r.text[:200]}")
        return None

def delete_field(field_id):
    r = requests.delete(f"{BASEROW_URL}/api/database/fields/{field_id}/", headers=headers())
    return r.status_code in (200, 204)

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
    # Remove auto-created default fields
    existing = get_fields(table_id)
    for f in existing:
        if f["name"] in {"Notes", "Active"} and not f.get("primary", False):
            if delete_field(f["id"]):
                print(f"    - Removed default field '{f['name']}'")


# ─── Table Schemas ───────────────────────────────────────────────────────────

EVENTS_FIELDS = [
    {"name": "Event Type", "type": "single_select", "select_options": [
        {"value": "External Event",            "color": "blue"},
        {"value": "Mobile Massage Service",    "color": "orange"},
        {"value": "Lunch and Learn",           "color": "green"},
        {"value": "Health Assessment Screening","color": "purple"},
    ]},
    {"name": "Event Status", "type": "single_select", "select_options": [
        {"value": "Prospective", "color": "light-gray"},
        {"value": "Approved",    "color": "blue"},
        {"value": "Scheduled",   "color": "orange"},
        {"value": "Completed",   "color": "green"},
    ]},
    {"name": "Event Date",       "type": "date", "date_format": "US", "date_include_time": False},
    {"name": "Organizer",        "type": "text"},
    {"name": "Organizer Phone",  "type": "text"},
    {"name": "Venue Address",    "type": "text"},
    {"name": "Cost",             "type": "text"},
    {"name": "Duration",         "type": "text"},
    {"name": "Indoor Outdoor",   "type": "single_select", "select_options": [
        {"value": "Indoor",  "color": "blue"},
        {"value": "Outdoor", "color": "green"},
        {"value": "Both",    "color": "orange"},
    ]},
    {"name": "Anticipated Count","type": "number", "number_decimal_places": 0},
    {"name": "Staff Type",       "type": "text"},
    {"name": "Industry",         "type": "text"},
    {"name": "Flyer URL",        "type": "url"},
    {"name": "Form Slug",        "type": "text"},
    {"name": "Checked In",       "type": "boolean"},
    {"name": "Created By",       "type": "text"},
    {"name": "Notes",            "type": "long_text"},
    {"name": "Lead Count",       "type": "number", "number_decimal_places": 0},
]

LEADS_FIELDS = [
    {"name": "Phone",        "type": "phone_number"},
    {"name": "Email",        "type": "email"},
    {"name": "Status",       "type": "single_select", "select_options": [
        {"value": "New",        "color": "blue"},
        {"value": "Contacted",  "color": "orange"},
        {"value": "Scheduled",  "color": "green"},
        {"value": "Converted",  "color": "dark-green"},
        {"value": "Lost",       "color": "red"},
    ]},
    {"name": "Source",       "type": "text"},
    {"name": "Contacted At", "type": "date", "date_format": "US", "date_include_time": False},
    {"name": "Contacted By", "type": "text"},
    {"name": "Notes",        "type": "long_text"},
    {"name": "Reason",       "type": "text"},
    {"name": "Call Status",  "type": "single_select", "select_options": [
        {"value": "Not Called", "color": "light-gray"},
        {"value": "Queued",     "color": "blue"},
        {"value": "Called",     "color": "orange"},
        {"value": "Answered",   "color": "green"},
        {"value": "Voicemail",  "color": "yellow"},
        {"value": "Failed",     "color": "red"},
    ]},
    {"name": "Call Notes",   "type": "long_text"},
]


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Setting up Events & Leads tables")
    print("=" * 60)

    # ── T_EVENTS ─────────────────────────────────────────────
    print("\n1. Events table")
    events_id, created = get_or_create_table(DATABASE_ID, "Events")
    ensure_fields(events_id, EVENTS_FIELDS)

    # Add Business link_row (needs to be done after table exists)
    existing = get_fields(events_id)
    if not any(f["name"] == "Business" for f in existing):
        create_field(events_id, {
            "name": "Business",
            "type": "link_row",
            "link_row_table_id": T_GOR_VENUES,
        })

    # ── T_LEADS ──────────────────────────────────────────────
    print("\n2. Leads table")
    leads_id, created = get_or_create_table(DATABASE_ID, "Leads")
    ensure_fields(leads_id, LEADS_FIELDS)

    # Add Event link_row
    existing = get_fields(leads_id)
    if not any(f["name"] == "Event" for f in existing):
        create_field(leads_id, {
            "name": "Event",
            "type": "link_row",
            "link_row_table_id": events_id,
        })

    # ── Summary ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"T_EVENTS = {events_id}")
    print(f"T_LEADS  = {leads_id}")
    print("=" * 60)
    print("\nAdd these to .env:")
    print(f"  T_EVENTS={events_id}")
    print(f"  T_LEADS={leads_id}")
    print("\nAnd to Modal secrets:")
    print(f"  modal secret create outreach-hub-secrets ... T_EVENTS={events_id} T_LEADS={leads_id} --force")


if __name__ == "__main__":
    main()
