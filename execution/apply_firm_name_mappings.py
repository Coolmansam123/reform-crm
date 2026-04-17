#!/usr/bin/env python3
"""
Apply firm name mappings from .tmp/firm_name_mapping.xlsx to Baserow patient records.

Reads Column A (old name) and Column D (true name or 'x') from the spreadsheet.
- If Column D is a name: updates Law Firm Name in all matching patient records
- If Column D is 'x': deletes those patient records from Baserow

Usage:
    cd "c:\\Users\\crazy\\Reform Workspace"
    python execution/apply_firm_name_mappings.py
"""

import os
import sys
import time
import requests
import openpyxl

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

BASEROW_URL = os.getenv("BASEROW_URL")
BASEROW_EMAIL = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")

TABLE_IDS = {
    "PI Active": 775,
    "PI Billed": 773,
    "PI Awaiting": 776,
    "PI Closed": 772,
}

XLSX_PATH = ".tmp/firm_name_mapping.xlsx"
FIELD = "Law Firm Name"
BATCH_SIZE = 100  # Baserow batch update limit


# ─── Auth ─────────────────────────────────────────────────────────────────────

_token = None
_token_time = 0

def fresh_token():
    global _token, _token_time
    if _token is None or (time.time() - _token_time) > 480:
        r = requests.post(f"{BASEROW_URL}/api/user/token-auth/",
            json={"email": BASEROW_EMAIL, "password": BASEROW_PASSWORD})
        r.raise_for_status()
        _token = r.json()["access_token"]
        _token_time = time.time()
    return _token

def hdrs():
    return {"Authorization": f"JWT {fresh_token()}", "Content-Type": "application/json"}


# ─── Data helpers ─────────────────────────────────────────────────────────────

def fetch_all(table_id):
    rows = []
    page = 1
    while True:
        r = requests.get(
            f"{BASEROW_URL}/api/database/rows/table/{table_id}/"
            f"?size=200&page={page}&user_field_names=true",
            headers=hdrs(),
        )
        r.raise_for_status()
        data = r.json()
        rows.extend(data["results"])
        if not data.get("next"):
            break
        page += 1
    return rows


def batch_update(table_id, items):
    """items = list of {id, Law Firm Name} dicts"""
    for i in range(0, len(items), BATCH_SIZE):
        chunk = items[i:i + BATCH_SIZE]
        r = requests.patch(
            f"{BASEROW_URL}/api/database/rows/table/{table_id}/batch/?user_field_names=true",
            headers=hdrs(),
            json={"items": chunk},
        )
        if r.status_code not in (200, 204):
            print(f"  [WARN] Batch update chunk failed: {r.status_code} {r.text[:200]}")
        else:
            print(f"  [OK] Updated {len(chunk)} rows in table {table_id}")


def delete_row(table_id, row_id):
    r = requests.delete(
        f"{BASEROW_URL}/api/database/rows/table/{table_id}/{row_id}/",
        headers=hdrs(),
    )
    if r.status_code not in (200, 204):
        print(f"  [WARN] Delete row {row_id} failed: {r.status_code}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    # Load mappings from Excel
    wb = openpyxl.load_workbook(XLSX_PATH)
    ws = wb.active

    updates = {}   # old_name_lower -> canonical_name
    deletes = set()  # old_name_lower -> delete records

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # skip header
        old_name = row[0]
        true_name = row[3] if len(row) > 3 else None
        if not old_name or not true_name:
            continue
        key = old_name.strip().lower()
        val = str(true_name).strip()
        if val.lower() == "x":
            deletes.add(key)
        else:
            updates[key] = val

    print(f"Loaded {len(updates)} rename mappings and {len(deletes)} delete mappings")
    print()

    # Fetch all patient rows
    all_rows = {}
    for table_name, table_id in TABLE_IDS.items():
        print(f"Fetching {table_name} (table {table_id})...")
        rows = fetch_all(table_id)
        all_rows[table_id] = rows
        print(f"  {len(rows)} rows loaded")

    print()

    total_updated = 0
    total_deleted = 0

    for table_name, table_id in TABLE_IDS.items():
        rows = all_rows[table_id]
        to_update = []
        to_delete = []

        for row in rows:
            name = (row.get(FIELD) or "").strip()
            name_lower = name.lower()
            if not name_lower:
                continue
            if name_lower in deletes:
                to_delete.append(row["id"])
            elif name_lower in updates:
                canonical = updates[name_lower]
                if name != canonical:  # only update if actually different
                    to_update.append({"id": row["id"], FIELD: canonical})

        print(f"{table_name}: {len(to_update)} to rename, {len(to_delete)} to delete")

        if to_update:
            batch_update(table_id, to_update)
            total_updated += len(to_update)

        if to_delete:
            for rid in to_delete:
                print(f"  Deleting row {rid}...")
                delete_row(table_id, rid)
                total_deleted += 1

    print()
    print("=" * 50)
    print(f"Done. {total_updated} records renamed, {total_deleted} records deleted.")


if __name__ == "__main__":
    main()
