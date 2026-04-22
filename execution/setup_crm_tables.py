#!/usr/bin/env python3
"""
Create the CRM-layer Companies + Contacts tables in the 'Reform Chiropractic
CRM' database (197). These are the unified entities that replace the three
domain-specific venue tables (T_ATT_VENUES, T_GOR_VENUES, T_COM_VENUES) in a
later migration step.

Idempotent: skips table/field creation if they already exist.
Prints the table IDs at the end — paste into execution/hub/constants.py.

Usage:
    python execution/setup_crm_tables.py
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
    print(f"    WARN: Failed '{field_config['name']}': {r.status_code} {r.text[:200]}")
    return None

def delete_field(field_id):
    r = requests.delete(
        f"{BASEROW_URL}/api/database/fields/{field_id}/",
        headers=headers(),
    )
    return r.status_code in (200, 204)

def rename_primary(table_id, new_name):
    """Rename the primary field (auto-created as 'Name') if it differs."""
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
    table = create_table(db_id, name)
    print(f"  Created '{name}' (ID: {table['id']})")
    return table["id"], True

def ensure_fields(table_id, fields_config):
    existing = get_fields(table_id)
    existing_names = {f["name"] for f in existing}
    for field_config in fields_config:
        if field_config["name"] in existing_names:
            print(f"    = {field_config['name']} (exists)")
        else:
            create_field(table_id, field_config)
    # Remove default auto-fields we don't use
    existing = get_fields(table_id)
    for f in existing:
        if f["name"] in {"Notes", "Active"} and not f.get("primary", False):
            # Only remove if we didn't intentionally add it (check against config)
            if not any(fc["name"] == f["name"] for fc in fields_config):
                if delete_field(f["id"]):
                    print(f"    - Removed default '{f['name']}'")


# ─── COMPANIES superset schema ───────────────────────────────────────────────
# Merges fields from T_ATT_VENUES (768), T_GOR_VENUES (790), T_COM_VENUES (797).
# Primary field renamed to 'Name' (it's already 'Name' by Baserow default).
#
# Category drives which hub a Company belongs to. Type options are a flat union
# of all three venue types — the UI filters Type options by Category at edit
# time (enforced in code, not at the schema level).
#
# Active + Permanently Closed are both present: Active covers "still pursuing"
# (preserved from attorney), Permanently Closed covers "venue has shut down"
# (preserved from guerilla). Both default to sensible values.

COMPANIES_FIELDS = [
    {"name": "Category", "type": "single_select", "select_options": [
        {"value": "attorney",  "color": "purple"},
        {"value": "guerilla",  "color": "orange"},
        {"value": "community", "color": "green"},
        {"value": "other",     "color": "light-gray"},
    ]},
    # Business type — union of options from all three domains
    {"name": "Type", "type": "single_select", "select_options": [
        # Guerilla
        {"value": "Gym",                    "color": "orange"},
        {"value": "Yoga Studio",            "color": "orange"},
        {"value": "Health Store",           "color": "orange"},
        {"value": "Wellness Center",        "color": "orange"},
        {"value": "Chiropractor",           "color": "orange"},
        # Community
        {"value": "Chamber of Commerce",    "color": "green"},
        {"value": "Lions Club",             "color": "green"},
        {"value": "Rotary Club",            "color": "green"},
        {"value": "BNI Chapter",            "color": "green"},
        {"value": "Networking Mixer",       "color": "green"},
        {"value": "Church",                 "color": "green"},
        {"value": "Parks & Rec",            "color": "green"},
        {"value": "Community Center",       "color": "green"},
        {"value": "High School",            "color": "green"},
        # Attorney (no explicit Type today — leave empty for migrated rows)
        {"value": "Law Firm",               "color": "purple"},
        # Generic
        {"value": "Other",                  "color": "light-gray"},
    ]},
    {"name": "Address",      "type": "text"},
    {"name": "Phone",        "type": "text"},
    {"name": "Email",        "type": "text"},
    {"name": "Website",      "type": "url"},

    {"name": "Contact Status", "type": "single_select", "select_options": [
        {"value": "Not Contacted",  "color": "light-gray"},
        {"value": "Contacted",      "color": "blue"},
        {"value": "In Discussion",  "color": "orange"},
        {"value": "Active Partner", "color": "green"},
        {"value": "Blacklisted",    "color": "red"},
    ]},
    {"name": "Outreach Goal", "type": "single_select", "select_options": [
        {"value": "Referral Partner", "color": "blue"},
        {"value": "Co-Marketing",     "color": "orange"},
        {"value": "Event Presence",   "color": "purple"},
        {"value": "Sponsorship",      "color": "yellow"},
        {"value": "Both",             "color": "green"},
    ]},
    {"name": "Active",             "type": "boolean"},
    {"name": "Permanently Closed", "type": "boolean"},

    # Attorney-specific
    {"name": "Classification", "type": "single_select", "select_options": [
        {"value": "Existing",    "color": "green"},
        {"value": "Prospect",    "color": "blue"},
        {"value": "Blacklisted", "color": "red"},
    ]},
    {"name": "Fax Number",              "type": "text"},
    {"name": "Preferred MRI Facility",  "type": "text"},
    {"name": "Preferred PM Facility",   "type": "text"},
    {"name": "Active Patients",         "type": "number", "number_decimal_places": 0},
    {"name": "Billed Patients",         "type": "number", "number_decimal_places": 0},
    {"name": "Awaiting Billing",        "type": "number", "number_decimal_places": 0},
    {"name": "Settled Cases",           "type": "number", "number_decimal_places": 0},
    {"name": "Total Cases",             "type": "number", "number_decimal_places": 0},

    # Guerilla-specific
    {"name": "Promo Items", "type": "long_text"},

    # Google Places metadata (common across all three)
    {"name": "Latitude",           "type": "text"},
    {"name": "Longitude",          "type": "text"},
    {"name": "Rating",             "type": "text"},
    {"name": "Reviews",            "type": "text"},  # text for compat with attorney
    {"name": "Distance (mi)",      "type": "text"},
    {"name": "Google Place ID",    "type": "text"},
    {"name": "Google Reviews JSON","type": "long_text"},
    {"name": "Google Maps URL",    "type": "url"},
    {"name": "Yelp Search URL",    "type": "url"},

    # Freeform notes
    {"name": "Notes", "type": "long_text"},

    # Migration metadata — track provenance for rollback
    {"name": "Legacy Source", "type": "single_select", "select_options": [
        {"value": "attorney_venue",  "color": "purple"},
        {"value": "guerilla_venue",  "color": "orange"},
        {"value": "community_venue", "color": "green"},
        {"value": "crm_native",      "color": "light-gray"},
    ]},
    {"name": "Legacy ID", "type": "number", "number_decimal_places": 0},

    # Timestamps
    {"name": "Created", "type": "date", "date_format": "US", "date_include_time": True},
    {"name": "Updated", "type": "date", "date_format": "US", "date_include_time": True},
]


# ─── CONTACTS schema ─────────────────────────────────────────────────────────
# Individual people, linked to Companies. Primary Company = where they work
# (or "unaffiliated" if unknown). Lead Source Company = who referred them /
# where the lead came from, separate from employment.
#
# Primary Company + Lead Source Company are two separate link_row fields to
# the same Companies table. Baserow supports this.

CONTACTS_FIELDS = [
    {"name": "Email",      "type": "email"},
    {"name": "Phone",      "type": "text"},
    {"name": "Title",      "type": "text"},
    {"name": "Lifecycle Stage", "type": "single_select", "select_options": [
        {"value": "Lead",     "color": "blue"},
        {"value": "Prospect", "color": "orange"},
        {"value": "Customer", "color": "green"},
        {"value": "Past",     "color": "light-gray"},
        {"value": "Other",    "color": "yellow"},
    ]},
    {"name": "Notes",   "type": "long_text"},
    {"name": "Active",  "type": "boolean"},

    # Migration metadata
    {"name": "Legacy Source", "type": "single_select", "select_options": [
        {"value": "law_firm_contact",   "color": "purple"},
        {"value": "community_contact",  "color": "green"},
        {"value": "crm_native",         "color": "light-gray"},
    ]},
    {"name": "Legacy ID", "type": "number", "number_decimal_places": 0},

    # Timestamps
    {"name": "Created", "type": "date", "date_format": "US", "date_include_time": True},
    {"name": "Updated", "type": "date", "date_format": "US", "date_include_time": True},
]


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Setting up CRM Companies + Contacts tables in DB 197")
    print("=" * 60)

    # ── Companies ────────────────────────────────────────────
    print("\n1. Companies table")
    companies_id, _ = get_or_create_table(DATABASE_ID, "Companies")
    rename_primary(companies_id, "Name")
    ensure_fields(companies_id, COMPANIES_FIELDS)

    # ── Contacts ─────────────────────────────────────────────
    print("\n2. Contacts table")
    contacts_id, _ = get_or_create_table(DATABASE_ID, "Contacts")
    rename_primary(contacts_id, "Name")
    ensure_fields(contacts_id, CONTACTS_FIELDS)

    # Link rows (after both tables exist)
    existing = get_fields(contacts_id)
    existing_names = {f["name"] for f in existing}
    if "Primary Company" not in existing_names:
        create_field(contacts_id, {
            "name": "Primary Company",
            "type": "link_row",
            "link_row_table_id": companies_id,
        })
    if "Lead Source Company" not in existing_names:
        create_field(contacts_id, {
            "name": "Lead Source Company",
            "type": "link_row",
            "link_row_table_id": companies_id,
        })

    # ── Summary ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"T_COMPANIES = {companies_id}")
    print(f"T_CONTACTS  = {contacts_id}")
    print("=" * 60)
    print("\nPaste into execution/hub/constants.py:")
    print(f"  T_COMPANIES = {companies_id}")
    print(f"  T_CONTACTS  = {contacts_id}")


if __name__ == "__main__":
    main()
