#!/usr/bin/env python3
"""
Enrich Business Venues with Yelp URLs using a two-stage approach.

Stage 1 (FREE - runs by default):
  Constructs a Yelp slug from business name + city, then verifies it via
  direct HTTP. No SerpAPI credits used. Resolved businesses are written to
  Baserow immediately. Unresolved businesses are written to .tmp/yelp_review.csv
  so you can decide which ones are worth a SerpAPI credit.

Stage 2 (PAID - opt-in via --serpapi):
  SerpAPI fallback for businesses that failed Stage 1. Use --limit to cap spend.

Workflow:
  1. Run Stage 1 to get free enrichment + review list
        python execution/enrich_yelp_urls.py
  2. Open .tmp/yelp_review.csv, set Action column to "keep" or "skip"
  3. Run Stage 2 on "keep" businesses only
        python execution/enrich_yelp_urls.py --serpapi --limit 50
  4. Repeat step 3 as credits allow

Usage:
    python execution/enrich_yelp_urls.py                      # Stage 1 only
    python execution/enrich_yelp_urls.py --serpapi            # Stage 1 + 2 (all)
    python execution/enrich_yelp_urls.py --serpapi --limit 50 # Stage 1 + 2 (capped)
    python execution/enrich_yelp_urls.py --force              # Re-process already enriched
"""

import os
import sys
import re
import csv
import time
import argparse
import requests
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

BASEROW_URL = os.getenv("BASEROW_URL")
BASEROW_EMAIL = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

GORILLA_VENUES_TABLE_ID = int(os.getenv("GORILLA_VENUES_TABLE_ID", 0)) or None

REVIEW_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", ".tmp", "yelp_review.csv")

YELP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

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


def auth_headers():
    return {"Authorization": f"JWT {fresh_token()}", "Content-Type": "application/json"}


# ─── Baserow Helpers ─────────────────────────────────────────────────────────

def find_table_by_name(database_id, name):
    r = requests.get(
        f"{BASEROW_URL}/api/database/tables/database/{database_id}/",
        headers=auth_headers(),
    )
    r.raise_for_status()
    for t in r.json():
        if t["name"] == name:
            return t["id"]
    return None


def read_all_rows(table_id):
    all_rows = []
    page = 1
    while True:
        r = requests.get(
            f"{BASEROW_URL}/api/database/rows/table/{table_id}/"
            f"?size=200&page={page}&user_field_names=true",
            headers=auth_headers(),
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


def get_fields(table_id):
    r = requests.get(
        f"{BASEROW_URL}/api/database/fields/table/{table_id}/",
        headers=auth_headers(),
    )
    r.raise_for_status()
    return r.json()


def create_field(table_id, name, field_type, **kwargs):
    payload = {"name": name, "type": field_type, **kwargs}
    r = requests.post(
        f"{BASEROW_URL}/api/database/fields/table/{table_id}/",
        headers=auth_headers(),
        json=payload,
    )
    if r.status_code not in (200, 201):
        print(f"  WARN: Failed to create field '{name}': {r.status_code} {r.text[:200]}")
        return None
    return r.json()


def update_row(table_id, row_id, payload):
    r = requests.patch(
        f"{BASEROW_URL}/api/database/rows/table/{table_id}/{row_id}/?user_field_names=true",
        headers=auth_headers(),
        json=payload,
    )
    if r.status_code not in (200, 201):
        print(f"  WARN: Failed to update row {row_id}: {r.status_code} {r.text[:200]}")
        return False
    return True


def ensure_permanently_closed_field(table_id):
    fields = get_fields(table_id)
    for f in fields:
        if f["name"] == "Permanently Closed":
            return "Permanently Closed"
    print("  Creating 'Permanently Closed' boolean field...")
    result = create_field(table_id, "Permanently Closed", "boolean")
    if result:
        print(f"  Created field ID: {result['id']}")
        return "Permanently Closed"
    return None


# ─── Stage 1: Free Slug Construction ─────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert a string to a Yelp-style URL slug."""
    text = text.lower().strip()
    # Remove common business suffixes
    for suffix in [", inc.", ", inc", ", llc.", ", llc", ", ltd.", ", ltd",
                   " inc.", " inc", " llc.", " llc", " ltd.", " ltd", " co."]:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    # Remove characters Yelp strips from slugs
    text = re.sub(r"[''&@#!]", "", text)
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"[\s\-]+", "-", text)
    return text.strip("-")


def extract_city(address: str) -> str:
    """Pull city name out of a full address string."""
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",")]
    # "123 Main St, Alhambra, CA 90001" → "Alhambra"
    if len(parts) >= 3:
        return parts[-3]
    if len(parts) >= 2:
        return parts[-2]
    return ""


def build_slug_candidates(name: str, city: str) -> list:
    """Generate ordered list of Yelp slug candidates to try."""
    name_slug = slugify(name)
    city_slug = slugify(city) if city else ""

    candidates = []
    if city_slug:
        candidates.append(f"{name_slug}-{city_slug}")
        candidates.append(f"{name_slug}-{city_slug}-2")
        candidates.append(f"{name_slug}-{city_slug}-3")
    candidates.append(name_slug)
    return candidates


def verify_yelp_slug(slug: str) -> str | None:
    """
    Try fetching yelp.com/biz/{slug} directly.
    Returns the clean /biz/ URL if it resolves, None otherwise.
    Status meanings:
      200 + /biz/ in final URL → found
      301/302 to /biz/ URL    → found (redirect to canonical slug)
      404 / redirect to search → not found
      403 / timeout           → blocked (treat as not found, falls to SerpAPI)
    """
    url = f"https://www.yelp.com/biz/{slug}"
    try:
        r = requests.get(
            url,
            headers=YELP_HEADERS,
            timeout=10,
            allow_redirects=True,
        )
        final_url = r.url
        # Yelp redirects failed lookups to /search or /biz/redirect pages
        if r.status_code == 200 and "/biz/" in final_url and "/search" not in final_url:
            return final_url.split("?")[0]
    except Exception:
        pass
    return None


def stage1_enrich(row: dict) -> tuple:
    """
    Attempt free Yelp URL resolution for a single business.
    Returns (resolved_url_or_None, status_string).
    Statuses: 'found' | 'not_found'
    """
    name = row.get("Business Name") or row.get("Name", "")
    address = row.get("Address", "")
    city = extract_city(address)

    candidates = build_slug_candidates(name, city)
    for slug in candidates:
        url = verify_yelp_slug(slug)
        if url:
            return url, "found"
        time.sleep(0.4)  # gentle rate limiting between attempts

    return None, "not_found"


# ─── Stage 2: SerpAPI Fallback ────────────────────────────────────────────────

def search_yelp_serpapi(name: str, address: str) -> dict | None:
    """Search Yelp via SerpAPI. Returns first organic result or None."""
    city = ""
    if address:
        parts = address.split(",")
        if len(parts) >= 3:
            city = f"{parts[-3].strip()}, {parts[-2].strip()}"
        elif len(parts) >= 2:
            city = parts[-2].strip()

    params = {
        "engine": "yelp",
        "find_desc": name,
        "find_loc": city or "Los Angeles, CA",
        "api_key": SERPAPI_KEY,
    }
    try:
        r = requests.get("https://serpapi.com/search", params=params, timeout=15)
        if r.status_code != 200:
            print(f"  WARN: SerpAPI returned {r.status_code} for '{name}'")
            return None
        data = r.json()
        results = data.get("organic_results", [])
        return results[0] if results else None
    except Exception as e:
        print(f"  WARN: SerpAPI error for '{name}': {e}")
        return None


def is_closed(result: dict) -> bool:
    return "CLOSED" in result.get("name", "").upper()


def extract_biz_url(result: dict) -> str | None:
    for key in ("url", "link", "website"):
        url = result.get(key, "")
        if url and "/biz/" in url:
            return url.split("?")[0]
    return None


# ─── Review CSV ───────────────────────────────────────────────────────────────

def write_review_csv(unresolved: list):
    """
    Write .tmp/yelp_review.csv with unresolved businesses.
    Columns: Row ID, Business Name, Type, Address, Action
    Action values: 'keep' (run SerpAPI on next pass) | 'skip' (exclude)
    """
    os.makedirs(os.path.dirname(REVIEW_CSV_PATH), exist_ok=True)

    # Preserve any existing Action decisions the user has made
    existing = {}
    if os.path.exists(REVIEW_CSV_PATH):
        try:
            with open(REVIEW_CSV_PATH, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("Action") in ("keep", "skip"):
                        existing[str(row["Row ID"])] = row["Action"]
        except Exception:
            pass

    with open(REVIEW_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Row ID", "Business Name", "Type", "Address", "Action"])
        writer.writeheader()
        for row in unresolved:
            row_id = str(row["id"])
            name = row.get("Business Name") or row.get("Name", "")
            writer.writerow({
                "Row ID": row_id,
                "Business Name": name,
                "Type": row.get("Type", {}).get("value", "") if isinstance(row.get("Type"), dict) else row.get("Type", ""),
                "Address": row.get("Address", ""),
                "Action": existing.get(row_id, "keep"),  # default: keep (user can change to skip)
            })

    print(f"\n  Review list written → .tmp/yelp_review.csv ({len(unresolved)} businesses)")
    print("  Open the CSV, set Action = 'skip' for businesses you don't want,")
    print("  then re-run with --serpapi [--limit N] to enrich the 'keep' ones.\n")


def load_review_csv_keeps() -> set:
    """Return set of Row IDs the user has marked 'keep' in the review CSV."""
    if not os.path.exists(REVIEW_CSV_PATH):
        return set()
    keeps = set()
    try:
        with open(REVIEW_CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Action", "keep").strip().lower() != "skip":
                    keeps.add(str(row["Row ID"]))
    except Exception:
        pass
    return keeps


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Two-stage Yelp URL enrichment")
    parser.add_argument("--serpapi", action="store_true",
                        help="Enable Stage 2: SerpAPI fallback for unresolved businesses")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max SerpAPI calls to make in Stage 2 (0 = all kept businesses)")
    parser.add_argument("--force", action="store_true",
                        help="Re-process businesses that already have a /biz/ URL")
    args = parser.parse_args()

    # Resolve table ID
    table_id = GORILLA_VENUES_TABLE_ID
    if not table_id:
        print("GORILLA_VENUES_TABLE_ID not set — auto-discovering...")
        table_id = find_table_by_name(203, "Business Venues")
        if not table_id:
            print("ERROR: Could not find 'Business Venues' table in Database 203.")
            print("Run setup_gorilla_marketing_tables.py first.")
            return
        print(f"Found Business Venues table: {table_id}")

    perm_closed_field = ensure_permanently_closed_field(table_id)
    if not perm_closed_field:
        print("ERROR: Could not create/find 'Permanently Closed' field")
        return

    print("Reading Business Venues from Baserow...")
    rows = read_all_rows(table_id)
    print(f"Loaded {len(rows)} businesses")

    # Split into needs-work vs already-done
    to_process = []
    already_enriched = 0
    for row in rows:
        current_url = row.get("Yelp Search URL", "") or ""
        if not args.force and "/biz/" in current_url:
            already_enriched += 1
            continue
        to_process.append(row)

    print(f"Already enriched (skipped): {already_enriched}")
    print(f"Needs enrichment: {len(to_process)}")

    if not to_process:
        print("\nNothing to process.")
        return

    # ── Stage 1: Free slug construction ──────────────────────────────────────
    print(f"\n{'─' * 50}")
    print(f"STAGE 1 — Free URL construction ({len(to_process)} businesses)\n")

    stage1_resolved = 0
    unresolved = []

    for i, row in enumerate(to_process, 1):
        name = row.get("Business Name") or row.get("Name", "")
        print(f"[{i}/{len(to_process)}] {name}", end="  ", flush=True)

        url, status = stage1_enrich(row)

        if status == "found":
            print(f"→ {url}")
            update_row(table_id, row["id"], {"Yelp Search URL": url})
            stage1_resolved += 1
        else:
            print("→ not resolved")
            unresolved.append(row)

        time.sleep(0.3)

    print(f"\nStage 1 complete: {stage1_resolved} resolved free, {len(unresolved)} unresolved")

    # Always write review CSV for unresolved businesses
    if unresolved:
        write_review_csv(unresolved)

    # ── Stage 2: SerpAPI fallback ─────────────────────────────────────────────
    if not args.serpapi:
        print("Stage 2 skipped (pass --serpapi to enable).")
        print(f"Credits needed if you run all: {len(unresolved)}")
        return

    if not SERPAPI_KEY:
        print("ERROR: SERPAPI_KEY not set in .env — cannot run Stage 2")
        return

    # Only process rows the user hasn't marked 'skip' in review CSV
    keep_ids = load_review_csv_keeps()
    if keep_ids:
        serpapi_queue = [r for r in unresolved if str(r["id"]) in keep_ids]
        skipped = len(unresolved) - len(serpapi_queue)
        if skipped:
            print(f"Skipping {skipped} businesses marked 'skip' in review CSV")
    else:
        serpapi_queue = unresolved

    if args.limit:
        serpapi_queue = serpapi_queue[:args.limit]

    print(f"\n{'─' * 50}")
    print(f"STAGE 2 — SerpAPI fallback ({len(serpapi_queue)} businesses)\n")

    if not serpapi_queue:
        print("Nothing to process in Stage 2.")
        return

    stage2_updated = 0
    closed_found = []
    not_found = []

    for i, row in enumerate(serpapi_queue, 1):
        name = row.get("Business Name") or row.get("Name", "")
        address = row.get("Address", "")
        row_id = row["id"]

        print(f"[{i}/{len(serpapi_queue)}] {name}")

        result = search_yelp_serpapi(name, address)

        if not result:
            print("  → No results")
            not_found.append(name)
            time.sleep(1)
            continue

        biz_url = extract_biz_url(result)
        closed = is_closed(result)

        if closed:
            print(f"  → CLOSED: {result.get('name', '')}")
            closed_found.append(name)

        payload = {}
        if biz_url:
            payload["Yelp Search URL"] = biz_url
            print(f"  → {biz_url}")
        else:
            print(f"  → No /biz/ URL in result")

        if closed:
            payload[perm_closed_field] = True

        if payload:
            if update_row(table_id, row_id, payload):
                stage2_updated += 1

        time.sleep(1)

    # Summary
    print(f"\n{'─' * 50}")
    print("Summary:")
    print(f"  Stage 1 (free):      {stage1_resolved} resolved")
    print(f"  Stage 2 (SerpAPI):   {stage2_updated} resolved  ({len(serpapi_queue)} credits used)")
    print(f"  Closed detected:     {len(closed_found)}")
    print(f"  Not found:           {len(not_found)}")
    print(f"  Still unresolved:    {len(unresolved) - len(serpapi_queue)}")

    if closed_found:
        print("\nPermanently Closed:")
        for n in closed_found:
            print(f"  ✗ {n}")

    if not_found:
        print("\nNo results found:")
        for n in not_found:
            print(f"  ? {n}")


if __name__ == "__main__":
    main()
