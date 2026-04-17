#!/usr/bin/env python3
"""
Generate a review CSV from scraped/geocoded attorneys for manual review.

After scraping and filtering by radius, this script outputs a human-readable
CSV so someone can review the results and remove entries that shouldn't be
included (e.g., your own practice, generic "Law Office" entries, non-attorneys).

Workflow:
  1. Run scrape + geocode steps
  2. Run this script -> produces .tmp/scraped_review.csv
  3. Open the CSV, delete rows you want to exclude, save it
  4. Run match_and_classify.py (reads from the reviewed CSV)

Input:  .tmp/attorneys_in_radius.json
Output: .tmp/scraped_review.csv

Usage:
    python execution/review_scraped_attorneys.py
"""

import csv
import json


COLUMNS = [
    "Keep (Y/N)",
    "Firm Name",
    "Address",
    "Phone",
    "Website",
    "Rating",
    "Reviews",
    "Distance (mi)",
    "Type",
]


def generate_review_csv(input_path: str, output_path: str):
    """Generate a review CSV from geocoded attorneys."""

    with open(input_path, "r") as f:
        attorneys = json.load(f)

    # Sort by distance for easy review
    attorneys.sort(key=lambda a: a.get("distance_miles", 999))

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)

        for attorney in attorneys:
            writer.writerow([
                "Y",  # Default to keep
                attorney.get("firm_name", ""),
                attorney.get("address", ""),
                attorney.get("phone", ""),
                attorney.get("website", ""),
                attorney.get("rating", ""),
                attorney.get("reviews", ""),
                attorney.get("distance_miles", ""),
                attorney.get("type", ""),
            ])

    print(f"Review CSV generated: {output_path}")
    print(f"  {len(attorneys)} entries (sorted by distance)")
    print()
    print("Next steps:")
    print(f"  1. Open {output_path}")
    print(f"  2. Change 'Keep (Y/N)' to 'N' for entries to exclude")
    print(f"     (e.g., your own practice, non-attorneys, generic entries)")
    print(f"  3. Save the file")
    print(f"  4. Run: python execution/match_and_classify.py")


def main():
    input_path = ".tmp/attorneys_in_radius.json"
    output_path = ".tmp/scraped_review.csv"

    try:
        with open(input_path):
            pass
    except FileNotFoundError:
        print(f"ERROR: {input_path} not found. Run geocode_attorneys.py first.")
        return

    generate_review_csv(input_path, output_path)


if __name__ == "__main__":
    main()
