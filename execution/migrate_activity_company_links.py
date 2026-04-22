#!/usr/bin/env python3
"""
Phase 2b.2 — activity link_row migration.

Creates a new `Company` link_row field on each of T_ATT_ACTS (784), T_GOR_ACTS
(791), T_COM_ACTS (798) pointing to T_COMPANIES (820). Backfills the new field
on every existing activity row by looking up its legacy venue-link target and
finding the Company with matching `Legacy Source`/`Legacy ID`.

Idempotent:
- Field creation: skipped if a `Company` field already exists.
- Backfill: skipped for rows whose `Company` link is already populated.

Usage:
    python execution/migrate_activity_company_links.py            # dry run
    python execution/migrate_activity_company_links.py --apply    # write
"""

import argparse
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL      = os.getenv("BASEROW_URL")
BASEROW_EMAIL    = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
BASEROW_TOKEN    = os.getenv("BASEROW_API_TOKEN")

T_ATT_ACTS   = 784
T_GOR_ACTS   = 791
T_COM_ACTS   = 798
T_COMPANIES  = 820

# Mapping from activity table → (old venue link field name, legacy_source value)
ACTIVITY_SPECS = [
    {"tid": T_ATT_ACTS, "label": "attorney activities",  "old_link_field": "Law Firm",     "legacy_source": "attorney_venue"},
    {"tid": T_GOR_ACTS, "label": "guerilla activities",  "old_link_field": "Business",     "legacy_source": "guerilla_venue"},
    {"tid": T_COM_ACTS, "label": "community activities", "old_link_field": "Organization", "legacy_source": "community_venue"},
]


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


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_fields(table_id):
    r = requests.get(
        f"{BASEROW_URL}/api/database/fields/table/{table_id}/",
        headers=jwt_headers(),
    )
    r.raise_for_status()
    return r.json()

def create_field(table_id, name, field_type, **extra):
    body = {"name": name, "type": field_type, **extra}
    r = requests.post(
        f"{BASEROW_URL}/api/database/fields/table/{table_id}/",
        headers=jwt_headers(),
        json=body,
    )
    if r.status_code == 200:
        return r.json()
    print(f"    ERROR creating '{name}': {r.status_code} {r.text[:300]}")
    return None

def fetch_all(table_id):
    rows = []
    url = f"{BASEROW_URL}/api/database/rows/table/{table_id}/?user_field_names=true&size=200"
    while url:
        r = requests.get(url, headers=api_headers(), timeout=30)
        r.raise_for_status()
        data = r.json()
        rows.extend(data["results"])
        url = data.get("next")
    return rows

def patch_row(table_id, row_id, fields):
    last_err = None
    url = f"{BASEROW_URL}/api/database/rows/table/{table_id}/{row_id}/?user_field_names=true"
    for attempt in range(4):
        try:
            r = requests.patch(url, headers=api_headers(), json=fields, timeout=30)
            if r.status_code == 200:
                return True
            if 400 <= r.status_code < 500:
                last_err = f"{r.status_code} {r.text[:200]}"
                break
            last_err = f"{r.status_code} {r.text[:200]}"
        except requests.exceptions.RequestException as e:
            last_err = str(e)
        if attempt < 3:
            time.sleep(1.5 * (attempt + 1))
    print(f"    ERROR patching row {row_id}: {last_err}")
    return False


# ─── Main ────────────────────────────────────────────────────────────────────

def ensure_company_field(spec):
    """Create `Company` link_row on the activity table if not already present."""
    fields = get_fields(spec["tid"])
    existing = next((f for f in fields if f["name"] == "Company"), None)
    if existing:
        print(f"  Table {spec['tid']} ({spec['label']}): 'Company' field already exists (id={existing['id']})")
        return existing
    print(f"  Table {spec['tid']} ({spec['label']}): creating 'Company' link_row → T_COMPANIES...")
    new = create_field(spec["tid"], "Company", "link_row", link_row_table_id=T_COMPANIES)
    if new:
        print(f"    + created (id={new['id']})")
    return new


def build_legacy_to_company_map(legacy_source):
    """Return {legacy_id (int) -> company_id (int)} for one legacy source."""
    companies = fetch_all(T_COMPANIES)
    out = {}
    for c in companies:
        src = c.get("Legacy Source")
        if isinstance(src, dict): src = src.get("value")
        if src != legacy_source:
            continue
        lid = c.get("Legacy ID")
        if lid is None:
            continue
        try:
            out[int(lid)] = c["id"]
        except (ValueError, TypeError):
            pass
    return out


def backfill_links(spec, dry_run):
    print(f"\n  Backfilling {spec['label']} (table {spec['tid']})...")
    id_map = build_legacy_to_company_map(spec["legacy_source"])
    print(f"    id_map has {len(id_map)} entries")

    rows = fetch_all(spec["tid"])
    print(f"    found {len(rows)} activity rows")

    ok = miss = skip = 0
    for row in rows:
        # If Company link already populated, skip
        existing_co = row.get("Company") or []
        if existing_co:
            skip += 1
            continue
        # Look at the old venue link
        old_links = row.get(spec["old_link_field"]) or []
        if not old_links:
            miss += 1
            continue
        legacy_id = old_links[0].get("id") if isinstance(old_links[0], dict) else old_links[0]
        company_id = id_map.get(int(legacy_id)) if legacy_id else None
        if not company_id:
            miss += 1
            continue
        if dry_run:
            ok += 1
        else:
            success = patch_row(spec["tid"], row["id"], {"Company": [company_id]})
            if success:
                ok += 1
            else:
                miss += 1
    print(f"    {'would link' if dry_run else 'linked'}: {ok}  |  already linked: {skip}  |  unmapped/orphan: {miss}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Actually write (default: dry run)")
    args = ap.parse_args()
    dry_run = not args.apply

    print("=" * 60)
    print(f"{'[DRY RUN] ' if dry_run else ''}Activity link_row migration → T_COMPANIES")
    print("=" * 60)

    # Step 1: ensure Company link_row exists on each activity table
    print("\nStep 1: Ensure 'Company' link_row field on each activity table")
    if dry_run:
        print("  (dry run: skipping field creation)")
    else:
        for spec in ACTIVITY_SPECS:
            ensure_company_field(spec)

    # Step 2: backfill existing activities with Company link
    print("\nStep 2: Backfill existing activity rows")
    for spec in ACTIVITY_SPECS:
        backfill_links(spec, dry_run)

    print("\n" + "=" * 60)
    print(f"{'[DRY RUN] ' if dry_run else ''}Done.")
    if dry_run:
        print("Re-run with --apply to actually create fields + write links.")
    print("=" * 60)


if __name__ == "__main__":
    main()
