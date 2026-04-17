#!/usr/bin/env python3
"""
Scrape Google Maps for local community organizations near the office using SerpAPI.

Organization types scraped:
  - Chamber of Commerce
  - Lions Club
  - Rotary Club
  - BNI Chapter (Business Networking International)
  - Networking Mixer / professional networking event
  - Church / community church
  - Parks & Rec department
  - Community Center
  - High School

Uses the same multi-point search pattern as scrape_businesses.py:
  5 search points (center + 4 cardinal) x 1-2 queries per type

Output: .tmp/scraped_community.json

Usage:
    python execution/scrape_community.py
    python execution/scrape_community.py --types chamber church highschool
    python execution/scrape_community.py --radius 7
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


# ─── Organization Type Definitions ────────────────────────────────────────────

ORG_TYPES = {
    "chamber": {
        "label": "Chamber of Commerce",
        "baserow_type": "Chamber of Commerce",
        "queries": ["chamber of commerce"],
    },
    "lions": {
        "label": "Lions Club",
        "baserow_type": "Lions Club",
        "queries": ["lions club"],
    },
    "rotary": {
        "label": "Rotary Club",
        "baserow_type": "Rotary Club",
        "queries": ["rotary club"],
    },
    "bni": {
        "label": "BNI Chapter",
        "baserow_type": "BNI Chapter",
        "queries": ["BNI business networking international"],
    },
    "networking": {
        "label": "Networking Mixer",
        "baserow_type": "Networking Mixer",
        "queries": ["business networking mixer", "professional networking event"],
    },
    "church": {
        "label": "Church",
        "baserow_type": "Church",
        "queries": ["church", "community church"],
    },
    "parksrec": {
        "label": "Parks & Rec",
        "baserow_type": "Parks & Rec",
        "queries": ["parks and recreation", "parks and rec department"],
    },
    "commcenter": {
        "label": "Community Center",
        "baserow_type": "Community Center",
        "queries": ["community center"],
    },
    "highschool": {
        "label": "High School",
        "baserow_type": "High School",
        "queries": ["high school"],
    },
}

ALL_TYPES = list(ORG_TYPES.keys())


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


def _search_maps(query: str, lat: float, lng: float, api_key: str, org_type: str) -> list:
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
            "type": org_type,
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


def _deduplicate(orgs: list) -> list:
    """Remove duplicates by place_id, then by normalized name+address."""
    seen_ids = set()
    seen_keys = set()
    unique = []

    for b in orgs:
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

def scrape_community(center_lat: float, center_lng: float,
                     radius_miles: float, api_key: str,
                     types: list) -> list:
    """Scrape all requested org types. Returns combined, deduplicated list."""
    all_results = []
    search_points = _generate_search_points(center_lat, center_lng, radius_miles)

    for type_key in types:
        type_def = ORG_TYPES[type_key]
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

    # Final dedup across all types (same place may appear in multiple searches)
    final = _deduplicate(all_results)
    print(f"\nTotal unique organizations across all types: {len(final)}")
    return final


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scrape local community organizations via SerpAPI")
    parser.add_argument("--types", nargs="+", choices=ALL_TYPES, default=ALL_TYPES,
                        help="Organization types to scrape (default: all)")
    parser.add_argument("--radius", type=int, default=None,
                        help="Override radius in miles")
    args = parser.parse_args()

    load_dotenv()

    api_key = os.getenv("SERPAPI_KEY")
    latlng = os.getenv("ATTORNEY_MAPPER_OFFICE_LAT_LNG", "")
    radius_miles = args.radius or int(os.getenv("COMMUNITY_RADIUS_MILES",
                                                 os.getenv("ATTORNEY_MAPPER_RADIUS_MILES", 7)))

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
    estimated_calls = sum(len(ORG_TYPES[t]["queries"]) for t in args.types) * 5
    print(f"Estimated SerpAPI calls: ~{estimated_calls} (~{estimated_calls // 2} credits)\n")

    os.makedirs(".tmp", exist_ok=True)
    orgs = scrape_community(lat, lng, radius_miles, api_key, args.types)

    output_path = ".tmp/scraped_community.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(orgs, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(orgs)} organizations to {output_path}")

    # Print type breakdown
    type_counts = {}
    for b in orgs:
        t = b.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    print("\nBreakdown by type:")
    for t, count in sorted(type_counts.items()):
        print(f"  {t}: {count}")


if __name__ == "__main__":
    main()
