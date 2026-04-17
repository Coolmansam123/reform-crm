#!/usr/bin/env python3
"""
Pre-filter Business Venues before Yelp enrichment.

Reads all unenriched businesses from Baserow and classifies each as:
  keep  — physical activity / service-based (gym, yoga, pilates, climbing, etc.)
  skip  — product sellers (nutrition shops, grocery stores, supplement retailers, etc.)

Writes .tmp/yelp_review.csv with Action pre-populated.
Any existing manual decisions (keep/skip) in the CSV are preserved.

Run this BEFORE enrich_yelp_urls.py --serpapi to avoid burning credits
on businesses that aren't outreach targets.

Usage:
    python execution/prefilter_businesses.py           # classify + write CSV
    python execution/prefilter_businesses.py --dry-run # print summary, don't write CSV
"""

import os
import sys
import csv
import time
import requests
import argparse
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

BASEROW_URL     = os.getenv("BASEROW_URL")
BASEROW_EMAIL   = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD= os.getenv("BASEROW_PASSWORD")
GORILLA_VENUES_TABLE_ID = int(os.getenv("GORILLA_VENUES_TABLE_ID", 0)) or None

REVIEW_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", ".tmp", "yelp_review.csv")

# ─── Classification Rules ────────────────────────────────────────────────────
#
# Only auto-skip well-known big chain retailers — national/regional brands
# where a partnership doesn't make sense. Small/local health stores stay as
# "keep" so the user can decide — they may be good advertising targets.
#
# Everything else (gyms, studios, local stores, etc.) defaults to keep.

# Exact or partial name matches for big chains → always skip
BIG_CHAIN_NAMES = [
    # National supplement/vitamin chains
    "gnc",
    "vitamin shoppe",
    "the vitamin shoppe",
    "nutrishop",
    "vitamin world",
    "max muscle nutrition",
    # National grocery chains
    "sprouts farmers market",
    "whole foods market",
    "whole foods",
    "trader joe's",
    "trader joes",
    "amazon fresh",
    "lazy acres",
    "mother's market & kitchen",
    # MLM brands
    "herbalife",
    "shaklee",
    "youngevity",
    "4life",
    "omnilife",
    "nature's sunshine",
    "transfer factor",
    # Manufacturers / B2B suppliers (no walk-in customers)
    "jarrow industries",
    "nugen research",
    "nuliv science",
    "beacon manufacturing",
    "orgenetics",
    "megahealth supply",
    "w m health products",
    "ndxusa",
    "immunocorp",
    # MLM nutrition clubs (herbalife front stores)
    "club nutricion",
    "club salud",
    "club viva mejor",
    "club broadway",
    # Grocery stores / markets (not fitness-adjacent)
    "grocery store",
    "grocer(",
    "re_ grocery",
    "food city",
    "village market",
    "island bodega",
    # Corporate offices (not a physical customer-facing location)
    "corporate office",
    # Online-only businesses
    "(online only)",
    "online only",
]

# Type strings that are always kept regardless of name
KEEP_TYPES = {"gym", "yoga studio"}


def classify(row: dict) -> tuple:
    """
    Returns ('keep' | 'skip', reason_string).
    Only auto-skips confirmed big chain retailers. Everything else is keep.
    """
    raw_type = row.get("Type", "") or ""
    type_val = raw_type.get("value", "").lower() if isinstance(raw_type, dict) else raw_type.lower()
    name = (row.get("Business Name") or row.get("Name", "") or "").lower()

    # 1. Type-level KEEP — gyms/studios/chiro are always worth reaching out to
    if type_val in KEEP_TYPES:
        return "keep", f"type={type_val}"

    # 2. Chiropractor offices → skip (competitor, not an outreach target)
    if type_val == "chiropractor" or "chiro" in name:
        return "skip", "chiropractor office"

    # 3. Beauty-related businesses → skip (not fitness outreach targets)
    BEAUTY_KEYWORDS = ["beauty", "salon", "nail", "lash", "brow", "wax", "cosmetic", "skincare", "aestheti"]
    if any(kw in name for kw in BEAUTY_KEYWORDS):
        matched = next(kw for kw in BEAUTY_KEYWORDS if kw in name)
        return "skip", f"beauty-related: '{matched}' in name"

    # 3. Big chain name match → skip
    for chain in BIG_CHAIN_NAMES:
        if chain in name:
            return "skip", f"big chain: '{chain}'"

    # 3. Default: keep — let the user decide on local/small businesses
    return "keep", "default (local/small business)"


# ─── Baserow Helpers ─────────────────────────────────────────────────────────

_jwt_token = None
_jwt_time  = 0

def fresh_token():
    global _jwt_token, _jwt_time
    if _jwt_token is None or (time.time() - _jwt_time) > 480:
        r = requests.post(f"{BASEROW_URL}/api/user/token-auth/",
                          json={"email": BASEROW_EMAIL, "password": BASEROW_PASSWORD})
        r.raise_for_status()
        _jwt_token = r.json()["access_token"]
        _jwt_time  = time.time()
    return _jwt_token

def auth_headers():
    return {"Authorization": f"JWT {fresh_token()}", "Content-Type": "application/json"}

def find_table_by_name(database_id, name):
    r = requests.get(f"{BASEROW_URL}/api/database/tables/database/{database_id}/",
                     headers=auth_headers())
    r.raise_for_status()
    for t in r.json():
        if t["name"] == name:
            return t["id"]
    return None

def read_all_rows(table_id):
    all_rows, page = [], 1
    while True:
        r = requests.get(
            f"{BASEROW_URL}/api/database/rows/table/{table_id}/"
            f"?size=200&page={page}&user_field_names=true",
            headers=auth_headers(),
        )
        if r.status_code != 200:
            break
        data = r.json()
        all_rows.extend(data["results"])
        if not data.get("next"):
            break
        page += 1
    return all_rows


# ─── CSV Helpers ──────────────────────────────────────────────────────────────

def load_existing_manual_decisions() -> dict:
    """
    Load only genuine manual decisions — rows where the user changed Action
    away from the Auto Classification. Auto-generated decisions are not preserved
    so that updated patterns always take effect.
    """
    if not os.path.exists(REVIEW_CSV_PATH):
        return {}
    decisions = {}
    try:
        with open(REVIEW_CSV_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                action = row.get("Action", "").strip().lower()
                auto   = row.get("Auto Classification", "").strip().lower()
                # Only preserve if user explicitly changed from auto classification
                if action in ("keep", "skip") and action != auto:
                    decisions[str(row["Row ID"])] = action
    except Exception:
        pass
    return decisions


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print classification summary without writing CSV")
    args = parser.parse_args()

    # Resolve table
    table_id = GORILLA_VENUES_TABLE_ID
    if not table_id:
        print("GORILLA_VENUES_TABLE_ID not set — auto-discovering...")
        table_id = find_table_by_name(203, "Business Venues")
        if not table_id:
            print("ERROR: Could not find 'Business Venues' table.")
            return
        print(f"Found Business Venues table: {table_id}")

    print("Reading Business Venues from Baserow...")
    rows = read_all_rows(table_id)
    print(f"Loaded {len(rows)} businesses\n")

    # Preserve any manual decisions the user has already made
    manual = load_existing_manual_decisions()
    if manual:
        print(f"Preserving {len(manual)} existing manual decisions from review CSV\n")

    # Classify each business
    results = []
    keep_count = skip_count = manual_override_count = 0

    for row in rows:
        current_url = row.get("Yelp Search URL", "") or ""
        if "/biz/" in current_url:
            continue  # already enriched, skip

        row_id   = str(row["id"])
        name     = row.get("Business Name") or row.get("Name", "")
        raw_type = row.get("Type", "") or ""
        type_str = raw_type.get("value", "") if isinstance(raw_type, dict) else raw_type

        auto_action, reason = classify(row)

        # Manual decisions override auto-classification, but only if the
        # previous auto decision was "keep" (i.e. user explicitly changed to skip).
        # We don't carry forward old auto-skip decisions — those get re-evaluated.
        if row_id in manual and auto_action == "keep" and manual[row_id] == "skip":
            final_action = "skip"
            manual_override_count += 1
        elif row_id in manual and auto_action == "skip" and manual[row_id] == "keep":
            final_action = "keep"
            manual_override_count += 1
        else:
            final_action = auto_action

        if final_action == "keep":
            keep_count += 1
        else:
            skip_count += 1

        results.append({
            "row_id":      row_id,
            "name":        name,
            "type":        type_str,
            "address":     row.get("Address", ""),
            "auto_action": auto_action,
            "action":      final_action,
            "reason":      reason,
        })

    # Print summary
    total = len(results)
    print(f"{'─' * 55}")
    print(f"Pre-filter results: {total} businesses need enrichment")
    print(f"  Auto KEEP:  {keep_count}  (will use SerpAPI credits)")
    print(f"  Auto SKIP:  {skip_count}  (will not be searched)")
    print(f"  Manual overrides preserved: {manual_override_count}")
    print(f"{'─' * 55}\n")

    # Show skip breakdown by type
    skip_rows = [r for r in results if r["action"] == "skip"]
    if skip_rows:
        from collections import Counter
        reasons = Counter(r["reason"] for r in skip_rows)
        print("Skip reasons:")
        for reason, count in reasons.most_common():
            print(f"  {count:3d}  {reason}")
        print()

    # Show a sample of what's being kept and skipped
    keeps = [r for r in results if r["action"] == "keep"][:10]
    skips = [r for r in results if r["action"] == "skip"][:10]

    print("Sample KEEP (first 10):")
    for r in keeps:
        print(f"  ✓ [{r['type']}] {r['name']}")
    print()
    print("Sample SKIP (first 10):")
    for r in skips:
        print(f"  ✗ [{r['type']}] {r['name']}  ← {r['reason']}")
    print()

    if args.dry_run:
        print("Dry run — CSV not written. Remove --dry-run to write .tmp/yelp_review.csv")
        return

    # Write CSV
    os.makedirs(os.path.dirname(REVIEW_CSV_PATH), exist_ok=True)
    with open(REVIEW_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Row ID", "Business Name", "Type", "Address", "Action", "Auto Classification", "Reason"
        ])
        writer.writeheader()
        for r in results:
            writer.writerow({
                "Row ID":              r["row_id"],
                "Business Name":       r["name"],
                "Type":                r["type"],
                "Address":             r["address"],
                "Action":              r["action"],
                "Auto Classification": r["auto_action"],
                "Reason":              r["reason"],
            })

    print(f"Written → .tmp/yelp_review.csv  ({total} rows)")
    print()
    print("Next steps:")
    print("  1. Open .tmp/yelp_review.csv and review — change Action to 'skip' or 'keep' as needed")
    print(f"  2. Run SerpAPI enrichment on keeps ({keep_count} businesses = {keep_count} credits):")
    print(f"     python execution/enrich_yelp_urls.py --serpapi --limit 50")


if __name__ == "__main__":
    main()
