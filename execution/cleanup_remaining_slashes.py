"""
Handles the 5 remaining PI rows whose 'Law Firm Name' still contains '/'.
Writes directly into the new 'Firm History' field (not Case Notes).
Same parsing rules as cleanup_slash_firms.py but simpler since we skip the
heuristic filter — we'll print each row for inspection first, then ask.

Usage:
  python execution/cleanup_remaining_slashes.py --dry-run
  python execution/cleanup_remaining_slashes.py
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


def is_real_firm_switch(firm_str):
    """Same filter as cleanup_slash_firms.py — avoids dates, phone notes, etc."""
    parts = [p.strip() for p in firm_str.split("/")]
    real_parts = [p for p in parts if len(p) > 2 and not p.replace("-", "").replace(" ", "").isdigit()]
    if len(real_parts) < 2:
        return False
    if "(" in firm_str and ")" in firm_str:
        paren_start = firm_str.index("(")
        paren_end = firm_str.index(")")
        slash_pos = firm_str.index("/")
        if paren_start < slash_pos < paren_end:
            return False
    short_parts = [p for p in parts if len(p.strip()) <= 2 and p.strip().isdigit()]
    if len(short_parts) >= 2:
        return False
    if "lvm" in firm_str.lower() or "missed appt" in firm_str.lower():
        return False
    return True


def clean_firm_name(name):
    name = name.strip()
    parts = name.split()
    cleaned = []
    for p in parts:
        if "@" in p:
            continue
        if p.lower() in ("in", "negotiations", "negotiating"):
            break
        cleaned.append(p)
    return " ".join(cleaned).strip()


def main():
    updated = skipped = 0
    for tid, label in TABLES:
        rows = fetch_all(tid)
        slash_rows = [r for r in rows if "/" in str(r.get("Law Firm Name", ""))]
        if not slash_rows:
            continue
        print(f"\n{label} (table {tid}): {len(slash_rows)} slash rows")
        for r in slash_rows:
            raw = str(r.get("Law Firm Name", ""))
            row_id = r["id"]
            case_label = (r.get("Case Label") or f"id={row_id}")[:40]

            if not is_real_firm_switch(raw):
                print(f"  SKIP (not a real switch) [{case_label}]: {raw[:80]}")
                skipped += 1
                continue

            parts = [p.strip() for p in raw.split("/") if p.strip()]
            current = clean_firm_name(parts[-1])
            previous = [clean_firm_name(p) for p in parts[:-1]]
            history = " -> ".join(previous + [f"{current} (current)"])

            existing_history = (r.get("Firm History") or "").strip()
            if existing_history:
                new_history = existing_history + "\n" + history
            else:
                new_history = history

            print(f"  UPDATE [{case_label}]")
            print(f"    Old: {raw[:80]}")
            print(f"    New firm: {current}")
            print(f"    History: {history}")

            if not DRY_RUN:
                resp = requests.patch(
                    f"{BR}/api/database/rows/table/{tid}/{row_id}/?user_field_names=true",
                    headers=HEADERS,
                    json={"Law Firm Name": current, "Firm History": new_history},
                )
                if resp.status_code == 200:
                    updated += 1
                else:
                    print(f"    FAIL {resp.status_code}: {resp.text[:150]}")
                time.sleep(0.12)
            else:
                updated += 1

    print(f"\nDONE: {updated} updated, {skipped} skipped")
    if DRY_RUN:
        print("(DRY RUN)")


if __name__ == "__main__":
    main()
