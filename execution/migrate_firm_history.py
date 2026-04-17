"""
Migration: Case Notes 'Firm history:' line -> dedicated 'Firm History' field.

For each PI row:
  - If Case Notes has a line starting with 'Firm history:', extract the chain
    (e.g. 'A -> B -> C (current)').
  - Write the chain (minus the 'Firm history:' prefix) to the new 'Firm History'
    field.
  - Remove that line from Case Notes.
  - Leave 'Law Firm Name' alone (already contains the current firm post-cleanup).

Skips rows where 'Firm History' is already populated (idempotent).

Usage:
  python execution/migrate_firm_history.py --dry-run
  python execution/migrate_firm_history.py
"""
import os, requests, sys, time
from dotenv import load_dotenv

load_dotenv()
BR = os.environ["BASEROW_URL"]
BT = os.environ["BASEROW_API_TOKEN"]
HEADERS = {"Authorization": f"Token {BT}", "Content-Type": "application/json"}

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DRY_RUN = "--dry-run" in sys.argv

TABLES = [
    (775, "Active"),
    (773, "Billed"),
    (776, "Awaiting"),
    (772, "Closed"),
]


def fetch_all(tid):
    rows, page = [], 1
    while True:
        r = requests.get(
            f"{BR}/api/database/rows/table/{tid}/?size=200&user_field_names=true&page={page}",
            headers={"Authorization": f"Token {BT}"},
        )
        data = r.json()
        rows.extend(data.get("results", []))
        if not data.get("next"):
            break
        page += 1
    return rows


def extract_history(case_notes: str) -> tuple[str, str]:
    """
    Returns (history_chain, case_notes_without_history_line).
    If no history line found, returns ('', original_case_notes).
    """
    if not case_notes:
        return "", case_notes or ""
    lines = case_notes.split("\n")
    kept = []
    history = ""
    for line in lines:
        s = line.strip()
        if s.lower().startswith("firm history:"):
            history = s[len("firm history:"):].strip()
        else:
            kept.append(line)
    # Collapse extra blank lines that may remain
    new_notes = "\n".join(kept).strip()
    return history, new_notes


def process():
    total = {"updated": 0, "skipped_no_history": 0, "skipped_already": 0, "failed": 0}

    for tid, label in TABLES:
        print(f"\n{'='*60}\n{label} (table {tid})\n{'='*60}")
        rows = fetch_all(tid)

        for r in rows:
            row_id = r["id"]
            case_notes = r.get("Case Notes") or ""
            existing_history = (r.get("Firm History") or "").strip()

            if existing_history:
                total["skipped_already"] += 1
                continue

            history, new_notes = extract_history(case_notes)
            if not history:
                total["skipped_no_history"] += 1
                continue

            label_str = (r.get("Case Label") or r.get("Name") or f"id={row_id}")[:40]
            print(f"  MIGRATE {label_str}")
            print(f"    History: {history}")

            if not DRY_RUN:
                resp = requests.patch(
                    f"{BR}/api/database/rows/table/{tid}/{row_id}/?user_field_names=true",
                    headers=HEADERS,
                    json={"Firm History": history, "Case Notes": new_notes},
                )
                if resp.status_code == 200:
                    total["updated"] += 1
                else:
                    total["failed"] += 1
                    print(f"    FAIL {resp.status_code}: {resp.text[:150]}")
                time.sleep(0.12)
            else:
                total["updated"] += 1

    print(f"\n{'='*60}")
    print(f"DONE: {total}")
    if DRY_RUN:
        print("(DRY RUN — nothing changed. Re-run without --dry-run to apply.)")


if __name__ == "__main__":
    process()
