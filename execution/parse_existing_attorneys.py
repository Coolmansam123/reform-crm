#!/usr/bin/env python3
"""
Parse existing attorney relationships from the P.I. Sheet CSV tab exports.

Reads four tab CSVs from .tmp/ to build per-firm case counts:
  - pi_sheet_export_Patients and Info.csv          → active_count
  - pi_sheet_export_Tx Completed - Billed.csv      → billed_count
  - pi_sheet_export_Awaiting & Negotiated.csv      → awaiting_count
  - pi_sheet_export_CLOSED.csv                     → settled_count

Also parses blacklist and referral firm sections from the main Patients and Info tab.

Output: .tmp/existing_attorneys.json with:
  - relationships: unique firms we actively work with, with full case counts
  - blacklist: firms to exclude from all results
  - referral_firms: firms we refer unrepresented patients to

Usage:
    python execution/parse_existing_attorneys.py
"""

import os
import csv
import json
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv
from fuzzywuzzy import fuzz


FUZZY_DEDUP_THRESHOLD = 85  # similarity % to consider same firm

TMP_DIR = Path(__file__).parent.parent / ".tmp"

TAB_CONFIGS = [
    ("pi_sheet_export_Patients and Info.csv",     {"Active"},              "active_count"),
    ("pi_sheet_export_Tx Completed - Billed.csv", {"Tx Completed"},        "billed_count"),
    ("pi_sheet_export_Awaiting & Negotiated.csv", {"Awaiting", "Negotiated"}, "awaiting_count"),
    ("pi_sheet_export_CLOSED.csv",                {"Closed"},              "settled_count"),
]


def parse_tab(csv_path: Path, status_values: set) -> dict:
    """Count patients per law firm for given status values from a tab CSV.
    Returns {firm_name: count}."""
    counts = defaultdict(int)
    if not csv_path.exists():
        print(f"[WARN] Tab CSV not found: {csv_path}")
        return dict(counts)
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 9:
                continue
            status = row[1].strip()
            firm_name = row[8].strip()
            if status in status_values and firm_name:
                counts[firm_name] += 1
    return dict(counts)


def parse_csv(csv_path: str) -> dict:
    """Parse the P.I. Sheet CSV into three categorized lists."""

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = list(csv.reader(f))

    # --- Extract active case firms (Column I = index 8) ---
    raw_firms = []
    for row in reader:
        if len(row) < 9:
            continue
        status = row[1].strip()
        firm_name = row[8].strip()
        if status == "Active" and firm_name:
            phone = row[6].strip() if len(row) > 6 else ""
            address = row[7].strip() if len(row) > 7 else ""
            raw_firms.append({
                "firm_name": firm_name,
                "phone": phone,
                "address": address,
            })

    # Deduplicate firms using fuzzy matching
    relationships = _fuzzy_dedup(raw_firms)

    # --- Extract blacklisted firms ---
    blacklist = []
    in_blacklist = False
    for row in reader:
        cell = row[0].strip() if row else ""
        if cell == "BLACK LIST Law Firms":
            in_blacklist = True
            continue
        if in_blacklist:
            if not cell or cell.startswith("HIGHLIGHT") or cell.startswith("BLACK LIST Patients"):
                break
            if cell.startswith("REPLY:"):
                continue
            blacklist.append(cell)

    # --- Extract referral firms ---
    referral_firms = []
    in_referral = False
    for row in reader:
        cell = row[0].strip() if row else ""
        if cell == "UNREP PT. REFER ORDER":
            in_referral = True
            continue
        if in_referral:
            if not cell or cell in ("New Attorney Performance", "Pending", "Poor", "Fair", "Good"):
                break
            referral_firms.append(cell)

    result = {
        "relationships": relationships,
        "blacklist": blacklist,
        "referral_firms": referral_firms,
    }

    # Print summary
    print(f"Parsed CSV: {csv_path}")
    print(f"  Active relationships: {len(relationships)} unique firms")
    print(f"  Blacklisted firms:    {len(blacklist)}")
    print(f"  Referral firms:       {len(referral_firms)}")
    print()
    print("=== RELATIONSHIPS ===")
    for f in relationships:
        aliases = f.get("aliases", [])
        alias_str = f" (aliases: {', '.join(aliases)})" if aliases else ""
        print(f"  {f['firm_name']}{alias_str}")
    print()
    print("=== BLACKLIST ===")
    for b in blacklist:
        print(f"  {b}")
    print()
    print("=== REFERRAL FIRMS ===")
    for r in referral_firms:
        print(f"  {r}")

    return result


def enrich_case_counts(relationships: list) -> None:
    """
    Reads all 4 PI sheet tab CSVs and adds case counts to each relationship in-place.
    Sets: active_count, billed_count, awaiting_count, settled_count, total_count.
    """
    # Build count dicts for each tab
    tab_counts = {}
    for filename, status_values, field_name in TAB_CONFIGS:
        tab_counts[field_name] = parse_tab(TMP_DIR / filename, status_values)
        total = sum(tab_counts[field_name].values())
        print(f"  {field_name}: {total} patients across {len(tab_counts[field_name])} firms")

    print()

    for firm in relationships:
        all_names = {firm["firm_name"]} | set(firm.get("aliases", []))

        active   = sum(tab_counts["active_count"].get(n, 0) for n in all_names)
        billed   = sum(tab_counts["billed_count"].get(n, 0) for n in all_names)
        awaiting = sum(tab_counts["awaiting_count"].get(n, 0) for n in all_names)
        settled  = sum(tab_counts["settled_count"].get(n, 0) for n in all_names)

        firm["active_count"]   = active
        firm["billed_count"]   = billed
        firm["awaiting_count"] = awaiting
        firm["settled_count"]  = settled
        firm["total_count"]    = active + billed + awaiting + settled


def _fuzzy_dedup(firms: list) -> list:
    """
    Deduplicate firms by fuzzy matching on name.
    Groups similar names together; keeps the most common spelling as canonical.
    Merges phone/address from all occurrences.
    """
    groups = []  # list of lists of firm dicts

    for firm in firms:
        matched_group = None
        for group in groups:
            canonical = group[0]["firm_name"]
            name_a = firm["firm_name"].lower()
            name_b = canonical.lower()

            score = fuzz.ratio(name_a, name_b)
            if score >= FUZZY_DEDUP_THRESHOLD:
                matched_group = group
                break

            token_score = fuzz.token_set_ratio(name_a, name_b)
            if token_score >= 85:
                matched_group = group
                break

        if matched_group is not None:
            matched_group.append(firm)
        else:
            groups.append([firm])

    # Build deduplicated list
    deduped = []
    for group in groups:
        name_counts = defaultdict(int)
        for f in group:
            name_counts[f["firm_name"]] += 1
        canonical_name = max(name_counts, key=name_counts.get)

        aliases = list({f["firm_name"] for f in group if f["firm_name"] != canonical_name})
        phones = list({f["phone"] for f in group if f["phone"]})
        addresses = list({f["address"] for f in group if f["address"]})

        entry = {
            "firm_name": canonical_name,
            "aliases": aliases,
            "phones": phones,
            "addresses": addresses,
            "patient_count": len(group),
        }
        deduped.append(entry)

    deduped.sort(key=lambda x: x["patient_count"], reverse=True)
    return deduped


def main():
    load_dotenv()
    csv_path = os.getenv(
        "ATTORNEY_MAPPER_CSV_FILE",
        str(TMP_DIR / "pi_sheet_export_Patients and Info.csv")
    )

    # Fall back to old-format CSV if new tab export doesn't exist
    if not os.path.exists(csv_path):
        legacy_path = str(TMP_DIR / "== P.I. Sheet == - Patients and Info.csv")
        if os.path.exists(legacy_path):
            csv_path = legacy_path
            print(f"[INFO] Using legacy CSV: {csv_path}")
        else:
            print(f"ERROR: CSV file not found: {csv_path}")
            print("Export the PI Sheet tabs from Google Sheets as CSV and place them in .tmp/")
            return

    result = parse_csv(csv_path)

    print("\n=== CASE COUNT ENRICHMENT ===")
    enrich_case_counts(result["relationships"])

    # Print enriched summary
    print("=== CASE COUNTS PER FIRM ===")
    for f in result["relationships"]:
        print(f"  {f['firm_name']}: "
              f"active={f.get('active_count', 0)} "
              f"billed={f.get('billed_count', 0)} "
              f"awaiting={f.get('awaiting_count', 0)} "
              f"settled={f.get('settled_count', 0)} "
              f"total={f.get('total_count', 0)}")

    output_path = str(TMP_DIR / "existing_attorneys.json")
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
