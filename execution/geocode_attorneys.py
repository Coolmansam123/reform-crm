#!/usr/bin/env python3
"""
Geocode scraped attorneys (if missing coordinates) and filter by radius.

Most attorneys from SerpAPI already have lat/lng from Google Maps.
This script:
  1. Geocodes the office address to get the center point
  2. Geocodes any attorneys missing coordinates (via Nominatim, free)
  3. Filters to only keep attorneys within the configured radius

Output: .tmp/attorneys_in_radius.json

Usage:
    python execution/geocode_attorneys.py
"""

import os
import sys
import json

# Fix Windows console encoding for non-ASCII characters
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import time
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from dotenv import load_dotenv


def geocode_and_filter(input_path: str, office_address: str, radius_miles: int) -> list:
    """Geocode missing coordinates, then filter by distance from office."""

    geolocator = Nominatim(user_agent="reform_attorney_mapper_v1")

    # Check for pre-configured office coordinates (avoids Nominatim dependency)
    office_latlng = os.getenv("ATTORNEY_MAPPER_OFFICE_LAT_LNG", "")
    if office_latlng:
        lat, lng = [float(x.strip()) for x in office_latlng.split(",")]
        office_coords = (lat, lng)
        print(f"Office coordinates (from .env): {office_coords}\n")
    else:
        # Geocode the office address (try progressively broader searches)
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
                f"Set ATTORNEY_MAPPER_OFFICE_LAT_LNG in .env (e.g. 33.9467,-118.1337)"
            )

        office_coords = (office_loc.latitude, office_loc.longitude)
        print(f"Office coordinates: {office_coords}\n")

    # Load scraped attorneys
    with open(input_path, "r") as f:
        attorneys = json.load(f)

    filtered = []
    skipped_no_coords = 0
    skipped_too_far = 0

    for attorney in attorneys:
        lat = attorney.get("latitude")
        lng = attorney.get("longitude")

        # Geocode if missing coordinates
        if lat is None or lng is None:
            address = attorney.get("address", "")
            if not address:
                skipped_no_coords += 1
                continue

            loc = _geocode(geolocator, address)
            if not loc:
                print(f"  Could not geocode: {attorney['firm_name']} ({address})")
                skipped_no_coords += 1
                continue

            attorney["latitude"] = loc.latitude
            attorney["longitude"] = loc.longitude
            time.sleep(1.1)  # Nominatim rate limit

        # Calculate distance
        att_coords = (attorney["latitude"], attorney["longitude"])
        distance = geodesic(office_coords, att_coords).miles
        attorney["distance_miles"] = round(distance, 2)

        if distance <= radius_miles:
            filtered.append(attorney)
            print(f"  [{distance:.1f} mi] {attorney['firm_name']}")
        else:
            skipped_too_far += 1

    print(f"\n--- Summary ---")
    print(f"Total scraped:      {len(attorneys)}")
    print(f"Within {radius_miles} miles:   {len(filtered)}")
    print(f"Too far:            {skipped_too_far}")
    print(f"No coordinates:     {skipped_no_coords}")

    return filtered


def _geocode(geolocator, address: str, retries: int = 3):
    """Geocode with retries."""
    for attempt in range(retries):
        try:
            return geolocator.geocode(address, timeout=10)
        except (GeocoderTimedOut, GeocoderServiceError):
            if attempt < retries - 1:
                time.sleep(2)
    return None


def main():
    load_dotenv()

    office_address = os.getenv("ATTORNEY_MAPPER_OFFICE_ADDRESS")
    radius_miles = int(os.getenv("ATTORNEY_MAPPER_RADIUS_MILES", 25))
    input_path = ".tmp/scraped_attorneys.json"

    if not office_address or office_address == "CHANGE_ME":
        print("ERROR: Set ATTORNEY_MAPPER_OFFICE_ADDRESS in .env")
        return

    if not os.path.exists(input_path):
        print(f"ERROR: {input_path} not found. Run scrape_attorneys.py first.")
        return

    filtered = geocode_and_filter(input_path, office_address, radius_miles)

    output_path = ".tmp/attorneys_in_radius.json"
    with open(output_path, "w") as f:
        json.dump(filtered, f, indent=2)

    print(f"\nSaved {len(filtered)} attorneys to {output_path}")


if __name__ == "__main__":
    main()
