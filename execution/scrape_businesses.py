#!/usr/bin/env python3
"""
Scrape Google Maps for local wellness businesses near the office using SerpAPI.

Business types scraped:
  - Gym / Fitness center
  - Yoga / Pilates studio
  - Health food / Supplement store
  - Chiropractor / Wellness clinic

Uses the same multi-point search pattern as scrape_attorneys.py:
  5 search points (center + 4 cardinal) x 2 queries per type = 10 SerpAPI calls/type
  All 4 types = ~40 SerpAPI calls (~20 credits)

Output: .tmp/scraped_businesses.json

Usage:
    python execution/scrape_businesses.py
    python execution/scrape_businesses.py --types gym yoga
    python execution/scrape_businesses.py --radius 10
"""

import os
import sys
import json
import math
import time
import argparse
import serpapi
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ─── Business Type Definitions ───────────────────────────────────────────────

BUSINESS_TYPES = {
    "gym": {
        "label": "Gym",
        "baserow_type": "Gym",
        "queries": ["gym", "fitness center"],
    },
    "yoga": {
        "label": "Yoga Studio",
        "baserow_type": "Yoga Studio",
        "queries": ["yoga studio", "pilates studio"],
    },
    "health": {
        "label": "Health Store",
        "baserow_type": "Health Store",
        "queries": ["health food store", "vitamin supplement store"],
    },
    "wellness": {
        "label": "Wellness Clinic",
        "baserow_type": "Chiropractor/Wellness",
        "queries": ["wellness clinic", "holistic health center"],
    },
}

ALL_TYPES = list(BUSINESS_TYPES.keys())


# ─── Search Helpers ──────────────────────────────────────────────────────────

def _generate_search_points(center_lat: float, center_lng: float, radius_miles: float) -> list:
    """
    Generate 5 search center points: center + 4 cardinal at ~60% of radius.
    Returns list of (lat, lng, label) tuples.
    """
    points = [(center_lat, center_lng, "center")]
    offset_miles = radius_miles * 0.6
    lat_offset = offset_miles / 69.0
    lng_offset = offset_miles / (69.0 * math.cos(math.radians(center_lat)))

    points.append((center_lat + lat_offset, center_lng, "north"))
    points.append((center_lat - lat_offset, center_lng, "south"))
    points.append((center_lat, center_lng + lng_offset, "east"))
    points.append((center_lat, center_lng - lng_offset, "west"))
    return points


def _search_maps(query: str, lat: float, lng: float, api_key: str, business_type: str) -> list:
    """Run a single SerpAPI Google Maps search and return normalized results."""
    client = serpapi.Client(api_key=api_key)
    data = client.search({
        "engine": "google_maps",
        "q": query,
        "ll": f"@{lat},{lng},14z",
        "type": "search",
    })

    results = []
    for r in data.get("local_results", []):
        results.append({
            "business_name": r.get("title", ""),
            "type": business_type,
            "address": r.get("address", ""),
            "phone": r.get("phone", ""),
            "website": r.get("website", ""),
            "rating": r.get("rating", 0),
            "reviews": r.get("reviews", 0),
            "place_id": r.get("place_id", ""),
            "latitude": r.get("gps_coordinates", {}).get("latitude"),
            "longitude": r.get("gps_coordinates", {}).get("longitude"),
        })
    return results


def _deduplicate(businesses: list) -> list:
    """Remove duplicates by place_id, then by normalized name+address."""
    seen_ids = set()
    seen_keys = set()
    unique = []

    for b in businesses:
        pid = b.get("place_id")
        if pid and pid in seen_ids:
            continue
        if pid:
            seen_ids.add(pid)

        key = (b["business_name"].lower().strip(), b["address"].lower().strip())
        if key in seen_keys:
            continue
        seen_keys.add(key)

        unique.append(b)

    return unique


# ─── Main Scrape ─────────────────────────────────────────────────────────────

def scrape_businesses(center_lat: float, center_lng: float,
                      radius_miles: float, api_key: str,
                      types: list) -> list:
    """Scrape all requested business types. Returns combined, deduplicated list."""
    all_results = []
    search_points = _generate_search_points(center_lat, center_lng, radius_miles)

    for type_key in types:
        type_def = BUSINESS_TYPES[type_key]
        queries = type_def["queries"]
        baserow_type = type_def["baserow_type"]
        total_searches = len(search_points) * len(queries)

        print(f"\n── {type_def['label'].upper()} ──")
        print(f"   {len(search_points)} points x {len(queries)} queries = {total_searches} API calls")

        search_num = 0
        type_results = []

        for lat, lng, label in search_points:
            for query in queries:
                search_num += 1
                print(f"  [{search_num}/{total_searches}] '{query}' from {label} ({lat:.4f}, {lng:.4f})")

                try:
                    results = _search_maps(query, lat, lng, api_key, baserow_type)
                    print(f"    Found {len(results)} results")
                    type_results.extend(results)
                except Exception as e:
                    print(f"    Error: {e}")

                time.sleep(1)

        deduped = _deduplicate(type_results)
        print(f"  Unique {type_def['label']}s: {len(deduped)}")
        all_results.extend(deduped)

    # Final dedup across all types (same place might appear in multiple type searches)
    final = _deduplicate(all_results)
    print(f"\nTotal unique businesses across all types: {len(final)}")
    return final


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scrape local wellness businesses via SerpAPI")
    parser.add_argument("--types", nargs="+", choices=ALL_TYPES, default=ALL_TYPES,
                        help="Business types to scrape (default: all)")
    parser.add_argument("--radius", type=int, default=None,
                        help="Override radius in miles")
    args = parser.parse_args()

    load_dotenv()

    api_key = os.getenv("SERPAPI_KEY")
    latlng = os.getenv("ATTORNEY_MAPPER_OFFICE_LAT_LNG", "")
    radius_miles = args.radius or int(os.getenv("ATTORNEY_MAPPER_RADIUS_MILES", 15))

    if not api_key or api_key == "CHANGE_ME":
        print("ERROR: Set SERPAPI_KEY in .env")
        return
    if not latlng:
        print("ERROR: Set ATTORNEY_MAPPER_OFFICE_LAT_LNG in .env")
        return

    lat, lng = [float(x.strip()) for x in latlng.split(",")]

    print(f"Office: ({lat}, {lng})")
    print(f"Radius: {radius_miles} miles")
    print(f"Types:  {', '.join(args.types)}")
    estimated_calls = len(args.types) * 5 * 2
    print(f"Estimated SerpAPI calls: ~{estimated_calls} (~{estimated_calls // 2} credits)\n")

    os.makedirs(".tmp", exist_ok=True)
    businesses = scrape_businesses(lat, lng, radius_miles, api_key, args.types)

    output_path = ".tmp/scraped_businesses.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(businesses, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(businesses)} businesses to {output_path}")

    # Print type breakdown
    type_counts = {}
    for b in businesses:
        t = b.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    print("\nBreakdown by type:")
    for t, count in sorted(type_counts.items()):
        print(f"  {t}: {count}")


if __name__ == "__main__":
    main()
