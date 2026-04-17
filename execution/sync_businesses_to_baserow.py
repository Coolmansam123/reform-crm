#!/usr/bin/env python3
"""
Sync scraped businesses from .tmp/businesses_in_radius.json to Baserow.

- Reads Business Venues table to find existing records
- Deduplicates by Google Place ID (if present), then by normalized name+address
- Adds new businesses as "Not Contacted"
- Does NOT overwrite existing records (preserves manual edits: notes, status, goal)

Prerequisites:
  - Run setup_gorilla_marketing_tables.py first to create the Baserow table
  - Run scrape_businesses.py + geocode_businesses.py to generate the input file

Input:  .tmp/businesses_in_radius.json
Output: Baserow Business Venues table (updated in-place)

Usage:
    python execution/sync_businesses_to_baserow.py
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

# ── Update these if setup_gorilla_marketing_tables.py printed different IDs ──
BUSINESS_VENUES_TABLE_ID = int(os.getenv("GORILLA_VENUES_TABLE_ID", 0)) or None
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


def create_row(table_id, payload):
    r = requests.post(
        f"{BASEROW_URL}/api/database/rows/table/{table_id}/",
        headers=headers(),
        json=payload,
    )
    if r.status_code not in (200, 201):
        print(f"  WARN: Failed to create row: {r.status_code} {r.text[:200]}")
    return r


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


def is_duplicate(business, by_place_id, by_name_addr):
    """Return True if this business already exists in Baserow."""
    pid = _norm(business.get("place_id", ""))
    if pid and pid in by_place_id:
        return True

    key = (_norm(business.get("business_name", "")), _norm(business.get("address", "")))
    if key in by_name_addr:
        return True

    return False


# ─── Yelp URL Builder ────────────────────────────────────────────────────────

def build_yelp_url(name: str, address: str) -> str:
    """Build a Yelp search URL from business name and address."""
    city = ""
    if address:
        parts = address.split(",")
        if len(parts) >= 2:
            city = parts[-2].strip()
    query = quote(f"{name} {city}".strip())
    return f"https://www.yelp.com/search?find_desc={query}"


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    input_path = ".tmp/businesses_in_radius.json"

    if not os.path.exists(input_path):
        print(f"ERROR: {input_path} not found. Run geocode_businesses.py first.")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        businesses = json.load(f)

    print(f"Loaded {len(businesses)} businesses from {input_path}")

    # Auto-discover table ID if not set
    table_id = BUSINESS_VENUES_TABLE_ID
    if not table_id:
        print("GORILLA_VENUES_TABLE_ID not set — auto-discovering by table name...")
        table_id = find_table_by_name(203, "Business Venues")
        if not table_id:
            print("ERROR: Could not find 'Business Venues' table in Database 203.")
            print("Run setup_gorilla_marketing_tables.py first.")
            return
        print(f"Found Business Venues table: ID {table_id}")

    # Get field map for writing
    fid = get_field_map(table_id)
    required_fields = ["Name", "Type", "Address"]
    for f in required_fields:
        if f not in fid:
            print(f"ERROR: Field '{f}' not found in Business Venues table.")
            print("Run setup_gorilla_marketing_tables.py to create required fields.")
            return

    # Load existing rows for dedup check
    print("Reading existing Business Venues from Baserow...")
    existing_rows = read_all_rows(table_id)
    print(f"Found {len(existing_rows)} existing records")
    by_place_id, by_name_addr = build_existing_index(existing_rows)

    # Identify new businesses (filter out competitors offering chiropractic services)
    COMPETITOR_KEYWORDS = [
        "chiropractic", "chiropractor", "spinal adjustment", "spinal decompression",
        "chiro ", "chiro-",
    ]

    def _is_competitor(biz):
        """Return True if the business appears to offer chiropractic care."""
        name = (biz.get("business_name") or "").lower()
        # Reform itself should never be in the pipeline
        if "reform" in name and "chiropractic" in name:
            return True
        # Check name and website for chiropractic keywords
        text = name + " " + (biz.get("website") or "").lower()
        return any(kw in text for kw in COMPETITOR_KEYWORDS)

    new_businesses = []
    skipped = 0
    competitors_filtered = 0

    for b in businesses:
        if is_duplicate(b, by_place_id, by_name_addr):
            skipped += 1
            continue
        if _is_competitor(b):
            competitors_filtered += 1
            print(f"  COMPETITOR FILTERED: {b.get('business_name', '')} ({b.get('address', '')})")
            continue
        new_businesses.append(b)

    print(f"\nNew businesses to add: {len(new_businesses)}")
    print(f"Already in Baserow (skipped): {skipped}")
    if competitors_filtered:
        print(f"Competitors filtered out: {competitors_filtered}")

    if not new_businesses:
        print("Nothing to add — Baserow is already up to date.")
        return

    # Build row payloads
    rows_to_create = []
    for b in new_businesses:
        name = b.get("business_name", "")
        address = b.get("address", "")
        yelp_url = build_yelp_url(name, address)

        row = {
            "Name": name,
            "Type": b.get("type", ""),
            "Address": address,
            "Phone": b.get("phone", ""),
            "Website": b.get("website", ""),
            "Latitude": str(b.get("latitude", "") or ""),
            "Longitude": str(b.get("longitude", "") or ""),
            "Rating": str(b.get("rating", "") or ""),
            "Reviews": b.get("reviews", 0) or 0,
            "Distance (mi)": str(b.get("distance_miles", "") or ""),
            "Google Place ID": b.get("place_id", ""),
            "Contact Status": "Not Contacted",
            "Yelp Search URL": yelp_url,
        }

        # Remove empty string fields to avoid Baserow validation errors on URL fields
        row = {k: v for k, v in row.items() if v != ""}
        rows_to_create.append(row)

    # Batch create
    print(f"\nCreating {len(rows_to_create)} new records in Baserow...")
    added = batch_create_rows(table_id, rows_to_create)
    print(f"Done! Added {added} businesses to Business Venues table.")

    # Type breakdown for new records
    type_counts = {}
    for b in new_businesses:
        t = b.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    print("\nNew records by type:")
    for t, count in sorted(type_counts.items()):
        print(f"  {t}: {count}")


if __name__ == "__main__":
    main()
