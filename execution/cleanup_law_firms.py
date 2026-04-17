#!/usr/bin/env python3
"""
Clean up the Law Firms table in Baserow and enrich with scraped data.

Steps:
  1. Delete junk/bare rows (no address AND no phone)
  2. Add new fields: Latitude, Longitude, Rating, Reviews, Distance (mi),
     Classification, Google Place ID
  3. Enrich existing firms with scraped data (fuzzy match)
  4. Add new prospect firms from scraped data

Input:  Baserow Law Firms table (768), .tmp/attorneys_in_radius.json,
        .tmp/existing_attorneys.json
Output: Cleaned and enriched Law Firms table in Baserow

Usage:
    python execution/cleanup_law_firms.py
"""

import requests
import os
import sys
import json
import time
from urllib.parse import quote

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fuzzywuzzy import fuzz
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL = os.getenv("BASEROW_URL")
BASEROW_EMAIL = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

LAW_FIRMS_TABLE_ID = 768

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


def read_all_rows(table_id):
    all_rows = []
    page = 1
    while True:
        r = requests.get(
            f"{BASEROW_URL}/api/database/rows/table/{table_id}/?size=200&page={page}&user_field_names=true",
            headers=headers(),
        )
        if r.status_code != 200:
            break
        data = r.json()
        all_rows.extend(data["results"])
        if not data.get("next"):
            break
        page += 1
    return all_rows


def get_field_map(table_id):
    r = requests.get(
        f"{BASEROW_URL}/api/database/fields/table/{table_id}/",
        headers=headers(),
    )
    r.raise_for_status()
    return {f["name"]: f"field_{f['id']}" for f in r.json()}


# ─── Step 1: Delete junk rows ────────────────────────────────────

def find_junk_rows(firms):
    """Identify rows to delete: empty names, bare names with no useful data."""
    junk_ids = []
    keep = []

    for f in firms:
        name = (f.get("Law Firm Name") or "").strip()
        address = (f.get("Law Office Address") or "").strip()
        phone = (f.get("Phone Number") or "").strip()
        email = (f.get("Email Address") or "").strip()

        # Delete if: empty name, or no address AND no phone AND no email
        if not name or (not address and not phone and not email):
            junk_ids.append(f["id"])
        else:
            keep.append(f)

    return junk_ids, keep


def batch_delete(table_id, row_ids, batch_size=200):
    """Delete rows in batches."""
    total = len(row_ids)
    deleted = 0

    for i in range(0, total, batch_size):
        batch = row_ids[i:i + batch_size]
        r = requests.post(
            f"{BASEROW_URL}/api/database/rows/table/{table_id}/batch-delete/",
            headers=headers(),
            json={"items": batch},
        )
        if r.status_code in (200, 204):
            deleted += len(batch)
            print(f"  Deleted {deleted}/{total} rows...")
        else:
            print(f"  ERROR deleting batch {i}: {r.status_code} {r.text[:200]}")

    return deleted


# ─── Step 2: Add new fields ──────────────────────────────────────

NEW_FIELDS = [
    ("Latitude", "text"),
    ("Longitude", "text"),
    ("Rating", "text"),
    ("Reviews", "text"),
    ("Distance (mi)", "text"),
    ("Classification", "single_select"),
    ("Google Place ID", "text"),
    ("Patient Count", "text"),
    ("Active Patients", "number"),
    ("Billed Patients", "number"),
    ("Awaiting Billing", "number"),
    ("Settled Cases", "number"),
    ("Total Cases", "number"),
    ("Google Reviews JSON", "long_text"),
    ("Google Maps URL", "text"),
    ("Yelp Search URL", "text"),
]

CLASSIFICATION_OPTIONS = [
    {"value": "Existing", "color": "green"},
    {"value": "Prospect", "color": "blue"},
    {"value": "Blacklisted", "color": "red"},
]


def add_new_fields(table_id):
    """Add map-related fields to the Law Firms table. Skip if they already exist."""
    h = headers()

    # Get existing field names
    r = requests.get(f"{BASEROW_URL}/api/database/fields/table/{table_id}/", headers=h)
    r.raise_for_status()
    existing_names = {f["name"] for f in r.json()}

    created = []
    for field_name, field_type in NEW_FIELDS:
        if field_name in existing_names:
            print(f"  Field '{field_name}' already exists, skipping")
            continue

        payload = {"name": field_name, "type": field_type}

        # Add select options for Classification
        if field_name == "Classification" and field_type == "single_select":
            payload["select_options"] = CLASSIFICATION_OPTIONS

        r = requests.post(
            f"{BASEROW_URL}/api/database/fields/table/{table_id}/",
            headers=h, json=payload,
        )
        if r.status_code == 200:
            print(f"  Created field '{field_name}' ({field_type})")
            created.append(field_name)
        else:
            print(f"  WARN: Failed to create '{field_name}': {r.status_code} {r.text[:200]}")

    return created


# ─── Step 3: Enrich existing firms ───────────────────────────────

# Very strict matching to prevent false positives like
# "Aratta Law Firm" -> "Lara Law Firm" or "Gor & Associates" -> "Orloff & Associates"
#
# Strategy: compare the DISTINCTIVE part of firm names (strip boilerplate),
# then require a high similarity on the distinctive parts.

GENERIC_WORDS = {"law", "firm", "office", "offices", "group", "the", "of", "apc",
                 "llp", "pc", "pllc", "p.c", "p.c.", "attorneys", "attorney",
                 "lawyer", "lawyers", "personal", "injury", "accident", "car",
                 "&", "and", "a", "|", "-"}


def fuzzy_match(name, candidates):
    """Find best fuzzy match using strict distinctive-name comparison."""
    distinctive = _get_distinctive(name)

    best_score = 0
    best_match = None

    for candidate in candidates:
        c_distinctive = _get_distinctive(candidate["firm_name"])

        # If either name has no distinctive content, skip
        if not distinctive or not c_distinctive:
            continue

        # Compare distinctive parts
        d_ratio = fuzz.ratio(distinctive, c_distinctive)

        # Also check full name ratio as a secondary signal
        full_ratio = fuzz.ratio(name.lower().strip(), candidate["firm_name"].lower().strip())

        # Accept if distinctive parts are very similar (>=85)
        # OR if full names are very similar (>=85)
        score = max(d_ratio, full_ratio)
        if score >= 85 and score > best_score:
            best_score = score
            best_match = candidate

    return best_match


def _get_distinctive(name):
    """Extract the distinctive part of a firm name (remove legal boilerplate)."""
    words = name.lower().strip().split()
    distinctive = [w.strip(".,") for w in words if w.strip(".,") not in GENERIC_WORDS]
    return " ".join(distinctive).strip()


def enrich_existing_firms(table_id, kept_firms, scraped, field_map, select_option_map):
    """Update existing firms with scraped data where there's a fuzzy match."""
    enriched = 0
    matched_scraped = set()  # track which scraped firms we've matched

    for firm in kept_firms:
        name = (firm.get("Law Firm Name") or "").strip()
        if not name:
            continue

        match = fuzzy_match(name, scraped)
        if match:
            matched_scraped.add(match["firm_name"])

            # Build update payload
            update = {}
            if match.get("latitude"):
                update[field_map["Latitude"]] = str(match["latitude"])
            if match.get("longitude"):
                update[field_map["Longitude"]] = str(match["longitude"])
            if match.get("rating"):
                update[field_map["Rating"]] = str(match["rating"])
            if match.get("reviews"):
                update[field_map["Reviews"]] = str(match["reviews"])
            if match.get("distance_miles") is not None:
                update[field_map["Distance (mi)"]] = str(match["distance_miles"])
            if match.get("place_id"):
                update[field_map["Google Place ID"]] = match["place_id"]

            # Fill in missing address/phone/website from scraped data
            if not (firm.get("Law Office Address") or "").strip() and match.get("address"):
                update[field_map["Law Office Address"]] = match["address"]
            if not (firm.get("Phone Number") or "").strip() and match.get("phone"):
                update[field_map["Phone Number"]] = match["phone"]
            if not (firm.get("Website") or "").strip() and match.get("website"):
                update[field_map["Website"]] = match["website"]

            # Classification: Existing
            if "Existing" in select_option_map:
                update[field_map["Classification"]] = select_option_map["Existing"]

            if update:
                r = requests.patch(
                    f"{BASEROW_URL}/api/database/rows/table/{table_id}/{firm['id']}/",
                    headers=headers(), json=update,
                )
                if r.status_code == 200:
                    enriched += 1
                    print(f"  [ENRICHED] {name} <- {match['firm_name']}")
                else:
                    print(f"  WARN: update {name}: {r.status_code} {r.text[:200]}")
        else:
            # No scraped match -- still mark as Existing (they're from the real firm directory)
            if "Existing" in select_option_map:
                r = requests.patch(
                    f"{BASEROW_URL}/api/database/rows/table/{table_id}/{firm['id']}/",
                    headers=headers(),
                    json={field_map["Classification"]: select_option_map["Existing"]},
                )

    return enriched, matched_scraped


# ─── Step 4: Add prospect firms ──────────────────────────────────

def add_prospects(table_id, scraped, matched_scraped, existing_data, field_map, select_option_map):
    """Add scraped firms not already in Baserow as prospects."""
    blacklist = existing_data.get("blacklist", [])

    prospects = []
    for s in scraped:
        if s["firm_name"] in matched_scraped:
            continue

        # Check blacklist
        sname = s["firm_name"].lower().strip()
        is_blacklisted = False
        for bl in blacklist:
            if fuzz.token_set_ratio(sname, bl.lower()) >= 85:
                is_blacklisted = True
                print(f"  [BLACKLISTED] {s['firm_name']} (matched '{bl}')")
                break
        if is_blacklisted:
            continue

        prospects.append(s)

    # Batch create prospect rows
    items = []
    for s in prospects:
        item = {
            field_map["Law Firm Name"]: s["firm_name"],
            field_map["Law Office Address"]: s.get("address", ""),
            field_map["Phone Number"]: s.get("phone", ""),
            field_map["Website"]: s.get("website", ""),
        }
        if s.get("latitude"):
            item[field_map["Latitude"]] = str(s["latitude"])
        if s.get("longitude"):
            item[field_map["Longitude"]] = str(s["longitude"])
        if s.get("rating"):
            item[field_map["Rating"]] = str(s["rating"])
        if s.get("reviews"):
            item[field_map["Reviews"]] = str(s["reviews"])
        if s.get("distance_miles") is not None:
            item[field_map["Distance (mi)"]] = str(s["distance_miles"])
        if s.get("place_id"):
            item[field_map["Google Place ID"]] = s["place_id"]
        if "Prospect" in select_option_map:
            item[field_map["Classification"]] = select_option_map["Prospect"]
        items.append(item)

    if not items:
        print("  No prospects to add")
        return 0

    added = 0
    batch_size = 50
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        r = requests.post(
            f"{BASEROW_URL}/api/database/rows/table/{table_id}/batch/",
            headers=headers(), json={"items": batch},
        )
        if r.status_code == 200:
            added += len(batch)
            print(f"  Added {added}/{len(items)} prospects...")
        else:
            print(f"  ERROR batch {i}: {r.status_code} {r.text[:300]}")

    return added


# ─── Step 5: Enrich with patient counts ──────────────────────────

def add_patient_counts(table_id, kept_firms, existing_data, field_map):
    """Add patient counts from parsed PI sheet data to existing firms."""
    relationships = existing_data.get("relationships", [])
    updated = 0

    for firm in kept_firms:
        name = (firm.get("Law Firm Name") or "").strip()
        if not name:
            continue

        distinctive = _get_distinctive(name)
        if not distinctive:
            continue

        # Find matching relationship
        for rel in relationships:
            rel_name = rel["firm_name"]
            aliases = rel.get("aliases", [])
            all_names = [rel_name] + aliases

            matched = False
            for candidate in all_names:
                c_dist = _get_distinctive(candidate)
                if not c_dist:
                    continue
                d_score = fuzz.ratio(distinctive, c_dist)
                f_score = fuzz.ratio(name.lower(), candidate.lower())
                if max(d_score, f_score) >= 85:
                    matched = True
                    break

            if matched:
                count = rel.get("patient_count", 0)
                if count > 0:
                    r = requests.patch(
                        f"{BASEROW_URL}/api/database/rows/table/{table_id}/{firm['id']}/",
                        headers=headers(),
                        json={field_map["Patient Count"]: str(count)},
                    )
                    if r.status_code == 200:
                        updated += 1
                break

    return updated


# ─── Step 6: Enrich case stats ───────────────────────────────────

def enrich_case_stats(table_id, kept_firms, existing_data, field_map):
    """Write Active/Billed/Awaiting/Settled/Total case counts to Baserow from PI sheet data."""
    relationships = existing_data.get("relationships", [])
    updated = 0

    for firm in kept_firms:
        name = (firm.get("Law Firm Name") or "").strip()
        if not name:
            continue

        distinctive = _get_distinctive(name)
        if not distinctive:
            continue

        for rel in relationships:
            rel_name = rel["firm_name"]
            aliases = rel.get("aliases", [])
            all_names = [rel_name] + aliases

            matched = False
            for candidate in all_names:
                c_dist = _get_distinctive(candidate)
                if not c_dist:
                    continue
                d_score = fuzz.ratio(distinctive, c_dist)
                f_score = fuzz.ratio(name.lower(), candidate.lower())
                if max(d_score, f_score) >= 85:
                    matched = True
                    break

            if matched:
                patch = {}
                if "Active Patients" in field_map:
                    patch[field_map["Active Patients"]] = rel.get("active_count", 0)
                if "Billed Patients" in field_map:
                    patch[field_map["Billed Patients"]] = rel.get("billed_count", 0)
                if "Awaiting Billing" in field_map:
                    patch[field_map["Awaiting Billing"]] = rel.get("awaiting_count", 0)
                if "Settled Cases" in field_map:
                    patch[field_map["Settled Cases"]] = rel.get("settled_count", 0)
                if "Total Cases" in field_map:
                    patch[field_map["Total Cases"]] = rel.get("total_count", 0)

                if patch:
                    r = requests.patch(
                        f"{BASEROW_URL}/api/database/rows/table/{table_id}/{firm['id']}/",
                        headers=headers(), json=patch,
                    )
                    if r.status_code == 200:
                        updated += 1
                        total = rel.get("total_count", 0)
                        print(f"  [STATS] {name}: total={total} "
                              f"(active={rel.get('active_count',0)} "
                              f"billed={rel.get('billed_count',0)} "
                              f"awaiting={rel.get('awaiting_count',0)} "
                              f"settled={rel.get('settled_count',0)})")
                    else:
                        print(f"  WARN: stats update {name}: {r.status_code} {r.text[:200]}")
                break

    return updated


# ─── Step 7: Enrich Google Reviews ───────────────────────────────

def enrich_google_reviews(table_id, kept_firms, field_map):
    """Fetch up to 3 Google Place reviews for firms with a Place ID. Skips already enriched."""
    if not GOOGLE_MAPS_API_KEY:
        print("  WARN: GOOGLE_MAPS_API_KEY not set — skipping reviews enrichment")
        return 0

    enriched = 0
    skipped = 0

    for firm in kept_firms:
        place_id = (firm.get("Google Place ID") or "").strip()
        if not place_id:
            continue

        # Skip if already enriched
        if (firm.get("Google Reviews JSON") or "").strip():
            skipped += 1
            continue

        name = (firm.get("Law Firm Name") or "").strip()

        url = (
            "https://maps.googleapis.com/maps/api/place/details/json"
            f"?place_id={place_id}&fields=reviews,url&key={GOOGLE_MAPS_API_KEY}"
        )
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
        except Exception as e:
            print(f"  WARN: Places API error for {name}: {e}")
            continue

        if data.get("status") != "OK":
            print(f"  WARN: Places API status '{data.get('status')}' for {name}")
            continue

        result = data.get("result", {})
        raw_reviews = result.get("reviews", [])[:3]
        reviews = [
            {
                "author_name": rv.get("author_name", ""),
                "rating": rv.get("rating", 0),
                "text": rv.get("text", ""),
                "relative_time_description": rv.get("relative_time_description", ""),
            }
            for rv in raw_reviews
        ]

        patch = {}
        if "Google Reviews JSON" in field_map:
            patch[field_map["Google Reviews JSON"]] = json.dumps(reviews)
        maps_url = result.get("url", "")
        if maps_url and "Google Maps URL" in field_map:
            patch[field_map["Google Maps URL"]] = maps_url

        if patch:
            r = requests.patch(
                f"{BASEROW_URL}/api/database/rows/table/{table_id}/{firm['id']}/",
                headers=headers(), json=patch,
            )
            if r.status_code == 200:
                enriched += 1
                print(f"  [REVIEWS] {name}: {len(reviews)} review(s) stored")
            else:
                print(f"  WARN: reviews update {name}: {r.status_code} {r.text[:200]}")

        time.sleep(0.1)  # avoid hammering Places API

    print(f"  Reviews enriched: {enriched} | already had reviews: {skipped}")
    return enriched


# ─── Step 8: Enrich Yelp URLs ─────────────────────────────────────

def enrich_yelp_urls(table_id, kept_firms, field_map):
    """Construct and store a Yelp search URL for each firm. Skips already populated."""
    if "Yelp Search URL" not in field_map:
        print("  WARN: Yelp Search URL field not in field_map — skipping")
        return 0

    updated = 0
    skipped = 0

    for firm in kept_firms:
        if (firm.get("Yelp Search URL") or "").strip():
            skipped += 1
            continue

        name = (firm.get("Law Firm Name") or "").strip()
        if not name:
            continue

        # Extract city from address: "123 Main St, Los Angeles, CA 90001" → "Los Angeles"
        address = (firm.get("Law Office Address") or "").strip()
        city = ""
        if address:
            parts = [p.strip() for p in address.split(",")]
            # Walk backwards: skip zip/state, take first non-zip, non-state part
            for part in reversed(parts):
                part = part.strip()
                # Skip if it looks like "CA 90001" or just "CA"
                tokens = part.split()
                if len(tokens) <= 2 and any(len(t) == 2 and t.isupper() for t in tokens):
                    continue
                if part:
                    city = part
                    break

        location = f"{city}, CA" if city else "California"
        yelp_url = f"https://www.yelp.com/search?find_desc={quote(name)}&find_loc={quote(location)}"

        r = requests.patch(
            f"{BASEROW_URL}/api/database/rows/table/{table_id}/{firm['id']}/",
            headers=headers(),
            json={field_map["Yelp Search URL"]: yelp_url},
        )
        if r.status_code == 200:
            updated += 1
        else:
            print(f"  WARN: Yelp URL update {name}: {r.status_code} {r.text[:200]}")

    print(f"  Yelp URLs written: {updated} | already had URL: {skipped}")
    return updated


# ─── Main ─────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("LAW FIRMS TABLE CLEANUP")
    print("=" * 60)

    # Load scraped data
    with open(".tmp/attorneys_in_radius.json") as f:
        scraped = json.load(f)
    print(f"Loaded {len(scraped)} scraped attorneys")

    with open(".tmp/existing_attorneys.json") as f:
        existing_data = json.load(f)
    print(f"Loaded existing relationships data")

    # Read current Law Firms table
    print(f"\n--- Reading Law Firms table ---")
    firms = read_all_rows(LAW_FIRMS_TABLE_ID)
    print(f"Current rows: {len(firms)}")

    # Step 1: Find and delete junk (skip if already done)
    print(f"\n--- Step 1: Purge junk rows ---")
    junk_ids, kept = find_junk_rows(firms)
    if junk_ids:
        print(f"Rows to delete (no name or no contact info): {len(junk_ids)}")
        print(f"Rows to keep: {len(kept)}")
        deleted = batch_delete(LAW_FIRMS_TABLE_ID, junk_ids)
        print(f"Deleted: {deleted}")
    else:
        print(f"No junk rows found, all {len(firms)} rows are clean")
        kept = firms

    # Step 2: Add new fields (idempotent -- skips existing)
    print(f"\n--- Step 2: Add new fields ---")
    add_new_fields(LAW_FIRMS_TABLE_ID)

    # Get updated field map (including new fields)
    field_map = get_field_map(LAW_FIRMS_TABLE_ID)

    # Get select option IDs for Classification field
    r = requests.get(
        f"{BASEROW_URL}/api/database/fields/table/{LAW_FIRMS_TABLE_ID}/",
        headers=headers(),
    )
    r.raise_for_status()
    select_option_map = {}
    for field in r.json():
        if field["name"] == "Classification" and field["type"] == "single_select":
            for opt in field.get("select_options", []):
                select_option_map[opt["value"]] = opt["id"]
            break
    print(f"Classification options: {select_option_map}")

    # Step 3: Enrich existing firms with scraped data
    print(f"\n--- Step 3: Enrich existing firms ---")
    enriched, matched_scraped = enrich_existing_firms(
        LAW_FIRMS_TABLE_ID, kept, scraped, field_map, select_option_map
    )
    print(f"Enriched: {enriched} firms")

    # Step 4: Add patient counts
    print(f"\n--- Step 4: Add patient counts ---")
    pc_updated = add_patient_counts(LAW_FIRMS_TABLE_ID, kept, existing_data, field_map)
    print(f"Patient counts added: {pc_updated}")

    # Step 5: Add prospect firms
    print(f"\n--- Step 5: Add prospect firms ---")
    added = add_prospects(
        LAW_FIRMS_TABLE_ID, scraped, matched_scraped, existing_data,
        field_map, select_option_map
    )
    print(f"Prospects added: {added}")

    # Refresh kept list to include any new fields on existing rows
    kept = read_all_rows(LAW_FIRMS_TABLE_ID)

    # Step 6: Enrich case stats
    print(f"\n--- Step 6: Enrich case stats ---")
    stats_updated = enrich_case_stats(LAW_FIRMS_TABLE_ID, kept, existing_data, field_map)
    print(f"Case stats updated: {stats_updated}")

    # Step 7: Enrich Google Reviews
    print(f"\n--- Step 7: Enrich Google Reviews ---")
    reviews_enriched = enrich_google_reviews(LAW_FIRMS_TABLE_ID, kept, field_map)
    print(f"Reviews enriched: {reviews_enriched}")

    # Step 8: Enrich Yelp URLs
    print(f"\n--- Step 8: Enrich Yelp URLs ---")
    yelp_updated = enrich_yelp_urls(LAW_FIRMS_TABLE_ID, kept, field_map)
    print(f"Yelp URLs written: {yelp_updated}")

    # Final summary
    final_firms = read_all_rows(LAW_FIRMS_TABLE_ID)
    existing_count = sum(1 for f in final_firms if (f.get("Classification") or {}).get("value") == "Existing")
    prospect_count = sum(1 for f in final_firms if (f.get("Classification") or {}).get("value") == "Prospect")
    with_coords = sum(1 for f in final_firms if (f.get("Latitude") or "").strip())

    print(f"\n{'=' * 60}")
    print(f"CLEANUP COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total firms:     {len(final_firms)}")
    print(f"  Existing:      {existing_count}")
    print(f"  Prospects:     {prospect_count}")
    print(f"  Unclassified:  {len(final_firms) - existing_count - prospect_count}")
    print(f"  With coords:   {with_coords} (map-ready)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
