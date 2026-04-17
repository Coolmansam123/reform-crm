#!/usr/bin/env python3
"""
Scrape Google for plaintiff injury attorneys near a given address using SerpAPI.

Uses SerpAPI's Google Maps engine with multiple search center points to cover
the full radius. Each search returns results with GPS coordinates.

Output: .tmp/scraped_attorneys.json

Usage:
    python execution/scrape_attorneys.py
"""

import os
import json
import math
import time
import serpapi
from dotenv import load_dotenv


# Search queries — 2 variations for moderate coverage
QUERY_TEMPLATES = [
    "personal injury attorney",
    "personal injury lawyer",
]

# Keywords that indicate a defense attorney (exclude these)
DEFENSE_KEYWORDS = [
    "defense",
    "insurance defense",
    "corporate defense",
    "defense attorney",
    "defense lawyer",
    "defendant",
]


def _generate_search_points(center_lat: float, center_lng: float, radius_miles: float) -> list:
    """
    Generate search center points to cover the radius.
    Uses center + 4 cardinal points at ~60% of the radius for good overlap.
    Returns list of (lat, lng, label) tuples.
    """
    points = [(center_lat, center_lng, "center")]

    # Offset in degrees (~60% of radius for overlap between search areas)
    offset_miles = radius_miles * 0.6
    lat_offset = offset_miles / 69.0  # ~69 miles per degree latitude
    lng_offset = offset_miles / (69.0 * math.cos(math.radians(center_lat)))

    points.append((center_lat + lat_offset, center_lng, "north"))
    points.append((center_lat - lat_offset, center_lng, "south"))
    points.append((center_lat, center_lng + lng_offset, "east"))
    points.append((center_lat, center_lng - lng_offset, "west"))

    return points


def scrape_attorneys(center_lat: float, center_lng: float,
                     radius_miles: float, api_key: str) -> list:
    """
    Scrape Google Maps for injury attorneys across the search radius.
    Searches from multiple center points with multiple query variations.
    """
    all_results = []
    search_points = _generate_search_points(center_lat, center_lng, radius_miles)
    total_searches = len(search_points) * len(QUERY_TEMPLATES)

    print(f"Search plan: {len(search_points)} points x {len(QUERY_TEMPLATES)} queries = {total_searches} API calls\n")

    search_num = 0
    for lat, lng, label in search_points:
        for query in QUERY_TEMPLATES:
            search_num += 1
            print(f"[{search_num}/{total_searches}] '{query}' from {label} ({lat:.4f}, {lng:.4f})")

            try:
                results = _search_maps(query, lat, lng, api_key)
                print(f"  Found {len(results)} results")
                all_results.extend(results)
            except Exception as e:
                print(f"  Error: {e}")

            time.sleep(1)

    # Deduplicate
    unique = _deduplicate(all_results)
    print(f"\nTotal unique attorneys found: {len(unique)}")

    return unique


def _search_maps(query: str, lat: float, lng: float, api_key: str) -> list:
    """Run a single SerpAPI Google Maps search and parse results."""
    attorneys = []

    client = serpapi.Client(api_key=api_key)
    data = client.search({
        "engine": "google_maps",
        "q": query,
        "ll": f"@{lat},{lng},14z",  # lat,lng,zoom — 14z covers ~5-8 mile area
        "type": "search",
    })

    local_results = data.get("local_results", [])

    for result in local_results:
        title = result.get("title", "")

        if _is_defense(title):
            print(f"    [SKIP defense] {title}")
            continue

        attorney = {
            "firm_name": title,
            "address": result.get("address", ""),
            "phone": result.get("phone", ""),
            "website": result.get("website", ""),
            "rating": result.get("rating", 0),
            "reviews": result.get("reviews", 0),
            "place_id": result.get("place_id", ""),
            "latitude": result.get("gps_coordinates", {}).get("latitude"),
            "longitude": result.get("gps_coordinates", {}).get("longitude"),
            "type": result.get("type", ""),
        }
        attorneys.append(attorney)

    return attorneys


def _is_defense(name: str) -> bool:
    """Check if a firm name suggests it's a defense attorney."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in DEFENSE_KEYWORDS)


def _deduplicate(attorneys: list) -> list:
    """Remove duplicates by place_id, then by normalized name+address."""
    seen_ids = set()
    seen_keys = set()
    unique = []

    for attorney in attorneys:
        pid = attorney.get("place_id")
        if pid and pid in seen_ids:
            continue
        if pid:
            seen_ids.add(pid)

        key = (attorney["firm_name"].lower().strip(), attorney["address"].lower().strip())
        if key in seen_keys:
            continue
        seen_keys.add(key)

        unique.append(attorney)

    return unique


def main():
    load_dotenv()

    api_key = os.getenv("SERPAPI_KEY")
    latlng = os.getenv("ATTORNEY_MAPPER_OFFICE_LAT_LNG", "")
    radius_miles = int(os.getenv("ATTORNEY_MAPPER_RADIUS_MILES", 15))

    if not api_key or api_key == "CHANGE_ME":
        print("ERROR: Set SERPAPI_KEY in .env")
        return
    if not latlng:
        print("ERROR: Set ATTORNEY_MAPPER_OFFICE_LAT_LNG in .env")
        return

    lat, lng = [float(x.strip()) for x in latlng.split(",")]

    print(f"Office: ({lat}, {lng})")
    print(f"Radius: {radius_miles} miles\n")

    attorneys = scrape_attorneys(lat, lng, radius_miles, api_key)

    output_path = ".tmp/scraped_attorneys.json"
    with open(output_path, "w") as f:
        json.dump(attorneys, f, indent=2)

    print(f"\nSaved {len(attorneys)} attorneys to {output_path}")


if __name__ == "__main__":
    main()
