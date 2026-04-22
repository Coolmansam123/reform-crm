#!/usr/bin/env python3
"""
Migrate rows from T_ATT_VENUES (768), T_GOR_VENUES (790), T_COM_VENUES (797)
and Law Firm Contacts (769) into the new unified T_COMPANIES (820) and
T_CONTACTS (821) tables.

Idempotent: checks Legacy Source + Legacy ID on Companies/Contacts before
inserting, so running it twice doesn't duplicate.

DEFAULTS TO DRY RUN. Pass --apply to actually write.

Usage:
    python execution/migrate_venues_to_companies.py           # dry run
    python execution/migrate_venues_to_companies.py --apply   # actually migrate
    python execution/migrate_venues_to_companies.py --apply --source attorney
"""

import argparse
import datetime as dt
import os
import sys
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL      = os.getenv("BASEROW_URL")
BASEROW_EMAIL    = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
BASEROW_TOKEN    = os.getenv("BASEROW_API_TOKEN")

# Source tables
T_ATT_VENUES      = 768
T_GOR_VENUES      = 790
T_COM_VENUES      = 797
T_LAW_FIRM_CONTACTS = 769  # Nascent pre-existing Contacts table (attorney-only, 8 rows)

# Target tables
T_COMPANIES = 820
T_CONTACTS  = 821


# ─── Auth ────────────────────────────────────────────────────────────────────

_jwt_token = None
_jwt_time  = 0

def fresh_token():
    global _jwt_token, _jwt_time
    if _jwt_token is None or (time.time() - _jwt_time) > 480:
        r = requests.post(f"{BASEROW_URL}/api/user/token-auth/", json={
            "email": BASEROW_EMAIL, "password": BASEROW_PASSWORD,
        })
        r.raise_for_status()
        _jwt_token = r.json()["access_token"]
        _jwt_time  = time.time()
    return _jwt_token

def jwt_headers():
    return {"Authorization": f"JWT {fresh_token()}", "Content-Type": "application/json"}

def api_headers():
    return {"Authorization": f"Token {BASEROW_TOKEN}", "Content-Type": "application/json"}


# ─── Baserow helpers ─────────────────────────────────────────────────────────

def fetch_all(table_id: int) -> list:
    """Page through all rows of a table via the row-level API token."""
    rows = []
    url = f"{BASEROW_URL}/api/database/rows/table/{table_id}/?user_field_names=true&size=200"
    while url:
        r = requests.get(url, headers=api_headers())
        r.raise_for_status()
        data = r.json()
        rows.extend(data["results"])
        url = data.get("next")
    return rows

def select_val(v) -> str:
    """Baserow single_select returns {'id', 'value', 'color'} — extract value."""
    if isinstance(v, dict):
        return v.get("value") or ""
    return v or ""

def to_int(v) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None

def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


# ─── Mapping functions ───────────────────────────────────────────────────────

# Contact Status values that differ across the three venues — normalize to the
# unified Companies set.
STATUS_MAP = {
    # Attorney labels
    "Active Relationship": "Active Partner",
    # Guerilla label
    "Partner":             "Active Partner",
    # Community & shared labels pass through
}

def normalize_status(s: str) -> str:
    return STATUS_MAP.get(s, s)

# Outreach Goal normalization
GOAL_MAP = {
    "Referral Partnership": "Referral Partner",  # Community uses this variant
    # Guerilla & Community both use "Both" → "Both"
}

def normalize_goal(s: str) -> str:
    return GOAL_MAP.get(s, s)


def map_attorney(row: dict) -> dict:
    """T_ATT_VENUES row → Companies payload.
    Single-select fields pass bare strings (Baserow accepts either the integer
    option ID or the string value when user_field_names=true)."""
    classification = select_val(row.get("Classification"))
    status = normalize_status(select_val(row.get("Contact Status")))
    if classification == "Blacklisted":
        status = "Blacklisted"
    return {
        "Name":                row.get("Law Firm Name") or "",
        "Category":            "attorney",
        "Type":                "Law Firm",
        "Address":             row.get("Law Office Address") or "",
        "Phone":               row.get("Phone Number") or "",
        "Email":               row.get("Email Address") or "",
        "Website":             row.get("Website") or "",
        "Contact Status":      status or None,
        "Active":              bool(row.get("Active", True)),
        "Classification":      classification or None,
        "Fax Number":          row.get("Fax Number") or "",
        "Preferred MRI Facility": row.get("Preferred MRI Facility") or "",
        "Preferred PM Facility":  row.get("Preferred PM Facility") or "",
        "Active Patients":     to_int(row.get("Active Patients")),
        "Billed Patients":     to_int(row.get("Billed Patients")),
        "Awaiting Billing":    to_int(row.get("Awaiting Billing")),
        "Settled Cases":       to_int(row.get("Settled Cases")),
        "Total Cases":         to_int(row.get("Total Cases")),
        "Latitude":            row.get("Latitude") or "",
        "Longitude":           row.get("Longitude") or "",
        "Rating":              row.get("Rating") or "",
        "Reviews":             row.get("Reviews") or "",
        "Distance (mi)":       row.get("Distance (mi)") or "",
        "Google Place ID":     row.get("Google Place ID") or "",
        "Google Reviews JSON": row.get("Google Reviews JSON") or "",
        "Google Maps URL":     row.get("Google Maps URL") or "",
        "Yelp Search URL":     row.get("Yelp Search URL") or "",
        "Notes":               row.get("Notes") or "",
        "Legacy Source":       "attorney_venue",
        "Legacy ID":           row["id"],
        "Created":             now_iso(),
        "Updated":             now_iso(),
    }


def map_guerilla(row: dict) -> dict:
    """T_GOR_VENUES row → Companies payload."""
    return {
        "Name":                row.get("Name") or "",
        "Category":            "guerilla",
        "Type":                select_val(row.get("Type")) or None,
        "Address":             row.get("Address") or "",
        "Phone":               row.get("Phone") or "",
        "Website":             row.get("Website") or "",
        "Contact Status":      normalize_status(select_val(row.get("Contact Status"))) or None,
        "Outreach Goal":       normalize_goal(select_val(row.get("Outreach Goal"))) or None,
        "Active":              not bool(row.get("Permanently Closed", False)),
        "Permanently Closed":  bool(row.get("Permanently Closed", False)),
        "Promo Items":         row.get("Promo Items") or "",
        "Latitude":            row.get("Latitude") or "",
        "Longitude":           row.get("Longitude") or "",
        "Rating":              row.get("Rating") or "",
        "Reviews":             str(row.get("Reviews")) if row.get("Reviews") is not None else "",
        "Distance (mi)":       row.get("Distance (mi)") or "",
        "Google Place ID":     row.get("Google Place ID") or "",
        "Google Reviews JSON": row.get("Google Reviews JSON") or "",
        "Google Maps URL":     row.get("Google Maps URL") or "",
        "Yelp Search URL":     row.get("Yelp Search URL") or "",
        "Legacy Source":       "guerilla_venue",
        "Legacy ID":           row["id"],
        "Created":             now_iso(),
        "Updated":             now_iso(),
    }


def map_community(row: dict) -> dict:
    """T_COM_VENUES row → Companies payload."""
    return {
        "Name":                row.get("Name") or "",
        "Category":            "community",
        "Type":                select_val(row.get("Type")) or None,
        "Address":             row.get("Address") or "",
        "Phone":               row.get("Phone") or "",
        "Email":               row.get("Email") or "",
        "Website":             row.get("Website") or "",
        "Contact Status":      normalize_status(select_val(row.get("Contact Status"))) or None,
        "Outreach Goal":       normalize_goal(select_val(row.get("Outreach Goal"))) or None,
        "Active":              True,
        "Latitude":            row.get("Latitude") or "",
        "Longitude":           row.get("Longitude") or "",
        "Rating":              row.get("Rating") or "",
        "Reviews":             str(row.get("Reviews")) if row.get("Reviews") is not None else "",
        "Distance (mi)":       row.get("Distance (mi)") or "",
        "Google Place ID":     row.get("Google Place ID") or "",
        "Google Maps URL":     row.get("Google Maps URL") or "",
        "Yelp Search URL":     row.get("Yelp Search URL") or "",
        "Notes":               row.get("Notes") or "",
        "Legacy Source":       "community_venue",
        "Legacy ID":           row["id"],
        "Created":             now_iso(),
        "Updated":             now_iso(),
    }


def map_attorney_contact(row: dict, company_id_map: dict) -> dict | None:
    """Law Firm Contact row → Contacts payload. Needs company_id_map to
    link back to the new Company row. Returns None if no linked firm."""
    firm_links = row.get("Law Firm") or []
    legacy_firm_id = firm_links[0]["id"] if firm_links and isinstance(firm_links[0], dict) else None
    new_company_id = company_id_map.get(("attorney_venue", legacy_firm_id)) if legacy_firm_id else None

    phone_parts = []
    if row.get("Direct Line"): phone_parts.append(f"Direct: {row['Direct Line']}")
    if row.get("Office #"):    phone_parts.append(f"Office: {row['Office #']}")
    phone = " / ".join(phone_parts)

    notes_parts = []
    if row.get("Notes"):         notes_parts.append(row["Notes"])
    if row.get("Contact Notes"): notes_parts.append(row["Contact Notes"])
    if row.get("Check In"):      notes_parts.append(f"Check In: {row['Check In']}")
    notes = "\n---\n".join(notes_parts)

    payload: dict[str, Any] = {
        "Name":            row.get("Name") or "",
        "Email":           row.get("Email") or "",
        "Phone":           phone,
        "Title":           row.get("Title") or "",
        "Lifecycle Stage": "Prospect",
        "Notes":           notes,
        "Active":          bool(row.get("Active", True)),
        "Legacy Source":   "law_firm_contact",
        "Legacy ID":       row["id"],
        "Created":         now_iso(),
        "Updated":         now_iso(),
    }
    if new_company_id:
        payload["Primary Company"] = [new_company_id]
    return payload


def map_community_contact_person(row: dict, new_company_id: int) -> dict | None:
    """Community venue 'Contact Person' field → Contacts row (if non-empty)."""
    cp = (row.get("Contact Person") or "").strip()
    if not cp:
        return None
    return {
        "Name":            cp,
        "Email":           row.get("Email") or "",
        "Phone":           row.get("Phone") or "",
        "Title":           "",
        "Lifecycle Stage": "Prospect",
        "Notes":           f"Migrated from community venue: {row.get('Name', '')}",
        "Active":          True,
        "Legacy Source":   "community_contact",
        "Legacy ID":       row["id"],
        "Created":         now_iso(),
        "Updated":         now_iso(),
        "Primary Company": [new_company_id],
    }


# ─── Write helpers ───────────────────────────────────────────────────────────

def post_row(table_id: int, payload: dict) -> dict:
    # Strip None values — Baserow rejects them for some field types
    clean = {k: v for k, v in payload.items() if v is not None and v != ""}
    url = f"{BASEROW_URL}/api/database/rows/table/{table_id}/?user_field_names=true"
    # Retry transient network errors (SSL drops, timeouts). Don't retry 4xx.
    last_err = None
    for attempt in range(4):
        try:
            r = requests.post(url, headers=api_headers(), json=clean, timeout=30)
            if r.status_code in (200, 201):
                return r.json()
            # 4xx is a data issue — no point retrying
            if 400 <= r.status_code < 500:
                print(f"    ERROR posting to table {table_id}: {r.status_code} {r.text[:300]}")
                raise RuntimeError("post_row failed")
            last_err = f"{r.status_code} {r.text[:200]}"
        except requests.exceptions.RequestException as e:
            last_err = str(e)
        if attempt < 3:
            time.sleep(1.5 * (attempt + 1))
    print(f"    ERROR posting to table {table_id} (after retries): {last_err}")
    raise RuntimeError("post_row failed after retries")

def existing_legacy_index(target_table: int) -> dict:
    """Return {(legacy_source, legacy_id): new_id} for rows already migrated."""
    rows = fetch_all(target_table)
    idx = {}
    for r in rows:
        src = select_val(r.get("Legacy Source"))
        lid = r.get("Legacy ID")
        if src and lid:
            idx[(src, int(lid))] = r["id"]
    return idx


# ─── Main ────────────────────────────────────────────────────────────────────

def migrate_companies(dry_run: bool, sources: set[str]) -> dict:
    """Migrate venue rows → Companies. Returns map {(legacy_source, legacy_id): new_company_id}."""
    print("\n" + "=" * 60)
    print(f"{'[DRY RUN] ' if dry_run else ''}Migrating companies...")
    print("=" * 60)

    existing = existing_legacy_index(T_COMPANIES) if not dry_run else {}
    id_map: dict = dict(existing)

    if "attorney" in sources:
        print("\n-- Attorney venues -> Companies --")
        rows = fetch_all(T_ATT_VENUES)
        print(f"   found {len(rows)} rows")
        for row in rows:
            key = ("attorney_venue", row["id"])
            if key in existing:
                print(f"   = already migrated: #{row['id']} {row.get('Law Firm Name', '')}")
                continue
            payload = map_attorney(row)
            print(f"   + {row['id']:4d}  {payload['Name'][:48]:48s}  status={select_val(payload.get('Contact Status'))}")
            if not dry_run:
                new = post_row(T_COMPANIES, payload)
                id_map[key] = new["id"]

    if "guerilla" in sources:
        print("\n-- Guerilla venues -> Companies --")
        rows = fetch_all(T_GOR_VENUES)
        print(f"   found {len(rows)} rows")
        for row in rows:
            key = ("guerilla_venue", row["id"])
            if key in existing:
                print(f"   = already migrated: #{row['id']} {row.get('Name', '')}")
                continue
            payload = map_guerilla(row)
            print(f"   + {row['id']:4d}  {payload['Name'][:48]:48s}  type={select_val(payload.get('Type'))}")
            if not dry_run:
                new = post_row(T_COMPANIES, payload)
                id_map[key] = new["id"]

    if "community" in sources:
        print("\n-- Community venues -> Companies --")
        rows = fetch_all(T_COM_VENUES)
        print(f"   found {len(rows)} rows")
        for row in rows:
            key = ("community_venue", row["id"])
            if key in existing:
                print(f"   = already migrated: #{row['id']} {row.get('Name', '')}")
                continue
            payload = map_community(row)
            print(f"   + {row['id']:4d}  {payload['Name'][:48]:48s}  type={select_val(payload.get('Type'))}")
            if not dry_run:
                new = post_row(T_COMPANIES, payload)
                id_map[key] = new["id"]

    return id_map


def migrate_contacts(dry_run: bool, sources: set[str], company_id_map: dict):
    print("\n" + "=" * 60)
    print(f"{'[DRY RUN] ' if dry_run else ''}Migrating contacts...")
    print("=" * 60)

    existing = existing_legacy_index(T_CONTACTS) if not dry_run else {}

    if "attorney" in sources:
        print("\n-- Law Firm Contacts -> Contacts --")
        rows = fetch_all(T_LAW_FIRM_CONTACTS)
        print(f"   found {len(rows)} rows")
        for row in rows:
            key = ("law_firm_contact", row["id"])
            if key in existing:
                print(f"   = already migrated: #{row['id']} {row.get('Name', '')}")
                continue
            payload = map_attorney_contact(row, company_id_map)
            linked = "LINKED" if payload and payload.get("Primary Company") else "UNLINKED"
            if payload:
                print(f"   + {row['id']:4d}  {payload['Name'][:40]:40s}  {linked}")
                if not dry_run:
                    post_row(T_CONTACTS, payload)

    if "community" in sources:
        print("\n-- Community 'Contact Person' field -> Contacts --")
        rows = fetch_all(T_COM_VENUES)
        created = 0
        for row in rows:
            cp = (row.get("Contact Person") or "").strip()
            if not cp:
                continue
            company_key = ("community_venue", row["id"])
            new_company_id = company_id_map.get(company_key)
            if not new_company_id:
                print(f"   ! SKIP '{cp}' — parent community venue #{row['id']} not in id_map")
                continue
            key = ("community_contact", row["id"])
            if key in existing:
                print(f"   = already migrated: #{row['id']} {cp}")
                continue
            payload = map_community_contact_person(row, new_company_id)
            if payload:
                print(f"   + {row['id']:4d}  {cp[:40]:40s}  LINKED -> company #{new_company_id}")
                if not dry_run:
                    post_row(T_CONTACTS, payload)
                created += 1
        print(f"   created {created} contact rows from Contact Person fields")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Actually write (default: dry run)")
    ap.add_argument("--source", choices=["attorney", "guerilla", "community", "all"],
                    default="all", help="Limit migration to one source")
    ap.add_argument("--skip-contacts", action="store_true", help="Companies only, no Contacts")
    args = ap.parse_args()

    dry_run = not args.apply
    sources = {"attorney", "guerilla", "community"} if args.source == "all" else {args.source}

    mode = "DRY RUN" if dry_run else "APPLY"
    print(f"Mode: {mode}")
    print(f"Sources: {sorted(sources)}")
    print(f"Skip contacts: {args.skip_contacts}")

    id_map = migrate_companies(dry_run, sources)

    if not args.skip_contacts:
        migrate_contacts(dry_run, sources, id_map)

    print("\n" + "=" * 60)
    print(f"{'[DRY RUN] ' if dry_run else ''}Done.")
    if dry_run:
        print("Re-run with --apply to actually write.")
    print("=" * 60)


if __name__ == "__main__":
    main()
