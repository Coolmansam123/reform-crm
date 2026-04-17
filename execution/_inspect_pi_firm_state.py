"""
Read-only diagnostic: inspect PI tables for firm-related fields and current state.
- Lists all fields in the 4 PI tables (looking for Law Firm Name, Case Notes, Firm History if exists)
- Counts rows with "/" still in Law Firm Name
- Counts rows with "Firm history:" line in Case Notes
- Counts rows with existing "Firm History" field populated (if field exists)
"""
import os, requests, sys
from dotenv import load_dotenv

load_dotenv()
BR = os.environ["BASEROW_URL"]
BT = os.environ["BASEROW_API_TOKEN"]
H = {"Authorization": f"Token {BT}"}

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TABLES = [
    (775, "Active"),
    (773, "Billed"),
    (776, "Awaiting"),
    (772, "Closed"),
]


def list_fields(tid):
    r = requests.get(f"{BR}/api/database/fields/table/{tid}/", headers=H)
    r.raise_for_status()
    return r.json()


def fetch_all(tid):
    rows, page = [], 1
    while True:
        r = requests.get(
            f"{BR}/api/database/rows/table/{tid}/?size=200&user_field_names=true&page={page}",
            headers=H,
        )
        data = r.json()
        rows.extend(data.get("results", []))
        if not data.get("next"):
            break
        page += 1
    return rows


def main():
    for tid, label in TABLES:
        print(f"\n{'='*70}\n{label} (table {tid})\n{'='*70}")
        fields = list_fields(tid)
        firm_related = [f for f in fields if "firm" in f["name"].lower() or "law" in f["name"].lower() or "attorney" in f["name"].lower() or f["name"].lower() == "case notes"]
        print(f"  Firm-related fields ({len(firm_related)}):")
        for f in firm_related:
            print(f"    - {f['name']:30s} type={f['type']:15s} id={f['id']}")

        rows = fetch_all(tid)
        slash_count = sum(1 for r in rows if "/" in str(r.get("Law Firm Name", "")))
        history_note_count = sum(1 for r in rows if "Firm history:" in str(r.get("Case Notes") or ""))
        firm_history_field_exists = any(f["name"] == "Firm History" for f in fields)
        firm_history_populated = 0
        if firm_history_field_exists:
            firm_history_populated = sum(1 for r in rows if r.get("Firm History"))

        print(f"  Total rows: {len(rows)}")
        print(f"  Rows with '/' in Law Firm Name: {slash_count}")
        print(f"  Rows with 'Firm history:' in Case Notes: {history_note_count}")
        print(f"  'Firm History' field exists: {firm_history_field_exists}")
        if firm_history_field_exists:
            print(f"  Rows with Firm History populated: {firm_history_populated}")


if __name__ == "__main__":
    main()
