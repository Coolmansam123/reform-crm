#!/usr/bin/env python3
"""
Delete empty rows from Baserow PI tables.
Dry-run by default. Pass --delete to actually delete.
"""
import sys
import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BASEROW_URL", "https://baserow.reformchiropractic.app")
TOKEN    = os.getenv("BASEROW_API_TOKEN")

TABLES = {
    "Active Cases (775)":       775,
    "Billed (773)":             773,
    "Awaiting (776)":           776,
    "Closed Cases (772)":       772,
    "Finance/Billing (781)":    781,
}

DRY_RUN = "--delete" not in sys.argv

def fetch_all(table_id: int) -> list:
    rows, page = [], 1
    while True:
        r = requests.get(
            f"{BASE_URL}/api/database/rows/table/{table_id}/",
            headers={"Authorization": f"Token {TOKEN}"},
            params={"user_field_names": "true", "size": 200, "page": page},
        )
        r.raise_for_status()
        data = r.json()
        rows.extend(data["results"])
        if not data["next"]:
            break
        page += 1
    return rows

def is_empty(row: dict) -> bool:
    """Row is empty if all identity fields are blank."""
    case_label     = (row.get("Case Label")    or "").strip()
    finance_label  = (row.get("Finance Label") or "").strip()
    patient_name   = (row.get("Patient Name")  or "").strip()
    patient_link   = row.get("Patient") or []
    return not case_label and not finance_label and not patient_name and not patient_link

def delete_row(table_id: int, row_id: int):
    r = requests.delete(
        f"{BASE_URL}/api/database/rows/table/{table_id}/{row_id}/",
        headers={"Authorization": f"Token {TOKEN}"},
    )
    r.raise_for_status()

total_deleted = 0

for name, tid in TABLES.items():
    print(f"\n-- {name} --")
    try:
        rows = fetch_all(tid)
    except Exception as e:
        print(f"  ERROR fetching: {e}")
        continue

    empty = [r for r in rows if is_empty(r)]
    print(f"  Total rows: {len(rows)} | Empty rows found: {len(empty)}")

    for row in empty:
        rid = row["id"]
        label = row.get("Case Label", "") or "(no label)"
        print(f"  {'[DELETE]' if not DRY_RUN else '[dry-run]'} row {rid}: {label!r}")
        if not DRY_RUN:
            try:
                delete_row(tid, rid)
                total_deleted += 1
            except Exception as e:
                print(f"    ERROR deleting row {rid}: {e}")

if DRY_RUN:
    print(f"\nDry run complete. Re-run with --delete to actually remove these rows.")
else:
    print(f"\nDone. Deleted {total_deleted} empty rows.")
