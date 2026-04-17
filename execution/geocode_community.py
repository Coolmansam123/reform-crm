#!/usr/bin/env python3
"""
Geocode scraped community organizations (if missing coordinates) and filter by radius.

Most results from SerpAPI already have lat/lng from Google Maps.
This script:
  1. Uses pre-configured office coordinates from .env
  2. Geocodes any organizations missing coordinates (via Nominatim, free, 1 req/sec)
  3. Filters to only keep organizations within the configured radius

Input:  .tmp/scraped_community.json
Output: .tmp/community_in_radius.json

Usage:
    python execution/geocode_community.py
"""

import os
import sys
import json
import time

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from dotenv import load_dotenv


def _geocode(geolocator, address: str, retries: int = 3):
    """Geocode an address with retries."""
    for attempt in range(retries):
        try:
            return geolocator.geocode(address, timeout=10)
        except (GeocoderTimedOut, GeocoderServiceError):
            if attempt < retries - 1:
                time.sleep(2)
    return None


def geocode_and_filter(input_path: str, office_address: str, radius_miles: int) -> list:
    """Geocode missing coordinates, then filter organizations by distance from office."""

    geolocator = Nominatim(user_agent="reform_community_outreach_v1")

    # Prefer pre-configured coords (avoids Nominatim dependency)
    office_latlng = os.getenv("ATTORNEY_MAPPER_OFFICE_LAT_LNG", "")
    if office_latlng:
        lat, lng = [float(x.strip()) for x in office_latlng.split(",")]
        office_coords = (lat, lng)
        print(f"Office coordinates (from .env): {office_coords}\n")
    else:
        print(f"Geocoding office: {office_address}")
        office_loc = _geocode(geolocator, office_address)

        if not office_loc:
            parts = office_address.split(",")
            for i in range(len(parts)):
                simplified = ",".join(parts[i:]).strip()
                if simplified:
                    print(f"  Retrying with: {simplified}")
                    office_loc = _geocode(geolocator, simplified)
                    if office_loc:
                        break
                    time.sleep(1.1)

        if not office_loc:
            raise ValueError(
                f"Could not geocode office address: {office_address}\n"
                "Set ATTORNEY_MAPPER_OFFICE_LAT_LNG in .env (e.g. 33.9467,-118.1337)"
            )

        office_coords = (office_loc.latitude, office_loc.longitude)
        print(f"Office coordinates: {office_coords}\n")

    with open(input_path, "r", encoding="utf-8") as f:
        orgs = json.load(f)

    filtered = []
    skipped_no_coords = 0
    skipped_too_far = 0

    for b in orgs:
        lat = b.get("latitude")
        lng = b.get("longitude")

        # Geocode if missing coordinates
        if lat is None or lng is None:
            address = b.get("address", "")
            if not address:
                skipped_no_coords += 1
                continue

            loc = _geocode(geolocator, address)
            if not loc:
                print(f"  Could not geocode: {b['business_name']} ({address})")
                skipped_no_coords += 1
                continue

            b["latitude"] = loc.latitude
            b["longitude"] = loc.longitude
            time.sleep(1.1)  # Nominatim rate limit

        b_coords = (b["latitude"], b["longitude"])
        distance = geodesic(office_coords, b_coords).miles
        b["distance_miles"] = round(distance, 2)

        if distance <= radius_miles:
            filtered.append(b)
            print(f"  [{distance:.1f} mi] [{b['type']:25s}] {b['business_name']}")
        else:
            skipped_too_far += 1

    print(f"\n--- Summary ---")
    print(f"Total scraped:      {len(orgs)}")
    print(f"Within {radius_miles} miles:    {len(filtered)}")
    print(f"Too far:            {skipped_too_far}")
    print(f"No coordinates:     {skipped_no_coords}")

    # Type breakdown
    type_counts = {}
    for b in filtered:
        t = b.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    if type_counts:
        print("\nWithin radius by type:")
        for t, count in sorted(type_counts.items()):
            print(f"  {t}: {count}")

    return filtered


def main():
    load_dotenv()

    office_address = os.getenv("ATTORNEY_MAPPER_OFFICE_ADDRESS")
    radius_miles = int(os.getenv("COMMUNITY_RADIUS_MILES",
                                  os.getenv("ATTORNEY_MAPPER_RADIUS_MILES", 7)))
    input_path = ".tmp/scraped_community.json"

    if not office_address or office_address == "CHANGE_ME":
        print("ERROR: Set ATTORNEY_MAPPER_OFFICE_ADDRESS in .env")
        return

    if not os.path.exists(input_path):
        print(f"ERROR: {input_path} not found. Run scrape_community.py first.")
        return

    filtered = geocode_and_filter(input_path, office_address, radius_miles)

    output_path = ".tmp/community_in_radius.json"
    os.makedirs(".tmp", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(filtered)} organizations to {output_path}")


if __name__ == "__main__":
    main()
