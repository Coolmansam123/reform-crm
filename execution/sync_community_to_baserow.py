#!/usr/bin/env python3
"""
Sync scraped community organizations from .tmp/community_in_radius.json to Baserow.

- Reads Community Organizations table to find existing records
- Deduplicates by Google Place ID (if present), then by normalized name+address
- Adds new organizations as "Not Contacted"
- Does NOT overwrite existing records (preserves manual edits: notes, status, goal)

Prerequisites:
  - Run setup_community_tables.py first to create the Baserow table
  - Run scrape_community.py + geocode_community.py to generate the input file

Input:  .tmp/community_in_radius.json
Output: Baserow Community Organizations table (updated in-place)

Usage:
    python execution/sync_community_to_baserow.py
"""

import os
import sys
import json
import time
import requests
from urllib.parse import quote
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

BASEROW_URL = os.getenv("BASEROW_URL")
BASEROW_EMAIL = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")

# ── Update these if setup_community_tables.py printed different IDs ──
COMMUNITY_VENUES_TABLE_ID = int(os.getenv("COMMUNITY_VENUES_TABLE_ID", 0)) or None
# If env var not set, the script will auto-discover the table by name

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

def read_all_rows(table_id):
    all_rows = []
    page = 1
    while True:
        r = requests.get(
            f"{BASEROW_URL}/api/database/rows/table/{table_id}/"
            f"?size=200&page={page}&user_field_names=true",
            headers=headers(),
        )
        if r.status_code != 200:
            print(f"  WARN: Failed to read page {page}: {r.status_code}")
            break
        data = r.json()
        all_rows.extend(data["results"])
        if not data.get("next"):
            break
        page += 1
    return all_rows


def get_field_map(table_id):
    """Returns dict of field_name -> field_NNN key for use in write payloads."""
    r = requests.get(
        f"{BASEROW_URL}/api/database/fields/table/{table_id}/",
        headers=headers(),
    )
    r.raise_for_status()
    return {f["name"]: f"field_{f['id']}" for f in r.json()}


def batch_create_rows(table_id, items):
    """Create rows in batches of 100 using user_field_names for single_select compatibility."""
    total = 0
    for i in range(0, len(items), 100):
        batch = items[i:i + 100]
        r = requests.post(
            f"{BASEROW_URL}/api/database/rows/table/{table_id}/batch/?user_field_names=true",
            headers=headers(),
            json={"items": batch},
        )
        if r.status_code not in (200, 201):
            print(f"  WARN: Batch create failed: {r.status_code} {r.text[:300]}")
        else:
            total += len(batch)
    return total


def find_table_by_name(database_id, name):
    r = requests.get(
        f"{BASEROW_URL}/api/database/tables/database/{database_id}/",
        headers=headers(),
    )
    r.raise_for_status()
    for t in r.json():
        if t["name"] == name:
            return t["id"]
    return None


# ─── Dedup Logic ─────────────────────────────────────────────────────────────

def _norm(s):
    return (s or "").lower().strip()


def build_existing_index(existing_rows):
    """Build lookup sets from existing Baserow rows."""
    by_place_id = {}
    by_name_addr = {}

    for row in existing_rows:
        pid = _norm(row.get("Google Place ID", ""))
        if pid:
            by_place_id[pid] = row["id"]

        key = (_norm(row.get("Name", "")), _norm(row.get("Address", "")))
        by_name_addr[key] = row["id"]

    return by_place_id, by_name_addr


def is_duplicate(org, by_place_id, by_name_addr):
    """Return True if this organization already exists in Baserow."""
    pid = _norm(org.get("place_id", ""))
    if pid and pid in by_place_id:
        return True

    key = (_norm(org.get("business_name", "")), _norm(org.get("address", "")))
    if key in by_name_addr:
        return True

    return False


# ─── Yelp URL Builder ────────────────────────────────────────────────────────

def build_yelp_url(name: str, address: str) -> str:
    """Build a Yelp search URL from organization name and address."""
    city = ""
    if address:
        parts = address.split(",")
        if len(parts) >= 2:
            city = parts[-2].strip()
    query = quote(f"{name} {city}".strip())
    return f"https://www.yelp.com/search?find_desc={query}"


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    input_path = ".tmp/community_in_radius.json"

    if not os.path.exists(input_path):
        print(f"ERROR: {input_path} not found. Run geocode_community.py first.")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        orgs = json.load(f)

    print(f"Loaded {len(orgs)} organizations from {input_path}")

    # Auto-discover table ID if not set
    table_id = COMMUNITY_VENUES_TABLE_ID
    if not table_id:
        print("COMMUNITY_VENUES_TABLE_ID not set — auto-discovering by table name...")
        table_id = find_table_by_name(198, "Community Organizations")
        if not table_id:
            print("ERROR: Could not find 'Community Organizations' table in Database 198.")
            print("Run setup_community_tables.py first.")
            return
        print(f"Found Community Organizations table: ID {table_id}")

    # Get field map for writing
    fid = get_field_map(table_id)
    required_fields = ["Name", "Type", "Address"]
    for f in required_fields:
        if f not in fid:
            print(f"ERROR: Field '{f}' not found in Community Organizations table.")
            print("Run setup_community_tables.py to create required fields.")
            return

    # Load existing rows for dedup check
    print("Reading existing Community Organizations from Baserow...")
    existing_rows = read_all_rows(table_id)
    print(f"Found {len(existing_rows)} existing records")
    by_place_id, by_name_addr = build_existing_index(existing_rows)

    # Identify new organizations
    new_orgs = []
    skipped = 0

    for org in orgs:
        if is_duplicate(org, by_place_id, by_name_addr):
            skipped += 1
            continue
        new_orgs.append(org)

    print(f"\nNew organizations to add: {len(new_orgs)}")
    print(f"Already in Baserow (skipped): {skipped}")

    if not new_orgs:
        print("Nothing to add — Baserow is already up to date.")
        return

    # Build row payloads
    rows_to_create = []
    for org in new_orgs:
        name = org.get("business_name", "")
        address = org.get("address", "")
        yelp_url = build_yelp_url(name, address)

        row = {
            "Name": name,
            "Type": org.get("type", ""),
            "Address": address,
            "Phone": org.get("phone", ""),
            "Website": org.get("website", ""),
            "Latitude": str(org.get("latitude", "") or ""),
            "Longitude": str(org.get("longitude", "") or ""),
            "Rating": str(org.get("rating", "") or ""),
            "Reviews": org.get("reviews", 0) or 0,
            "Distance (mi)": str(org.get("distance_miles", "") or ""),
            "Google Place ID": org.get("place_id", ""),
            "Contact Status": "Not Contacted",
            "Yelp Search URL": yelp_url,
        }

        # Remove empty string fields to avoid Baserow validation errors on URL/email fields
        row = {k: v for k, v in row.items() if v != ""}
        rows_to_create.append(row)

    # Batch create
    print(f"\nCreating {len(rows_to_create)} new records in Baserow...")
    added = batch_create_rows(table_id, rows_to_create)
    print(f"Done! Added {added} organizations to Community Organizations table.")

    # Type breakdown for new records
    type_counts = {}
    for org in new_orgs:
        t = org.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    print("\nNew records by type:")
    for t, count in sorted(type_counts.items()):
        print(f"  {t}: {count}")


if __name__ == "__main__":
    main()
