"""
Cleanup script: Parse "/" in Law Firm Name fields across all PI tables.
- Sets "Law Firm Name" to the LAST firm (current)
- Stores full history in "Case Notes" as "Previous firms: A -> B -> C (current)"
- Skips records that look like notes/phone numbers, not real firm switches
"""
import os, requests, time, sys
from dotenv import load_dotenv

load_dotenv()
BR = os.environ["BASEROW_URL"]
BT = os.environ["BASEROW_API_TOKEN"]
HEADERS = {"Authorization": f"Token {BT}", "Content-Type": "application/json"}

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
    """Filter out entries that are notes/phone numbers, not actual firm switches."""
    parts = [p.strip() for p in firm_str.split("/")]
    # If any part is just a number or very short, probably not a firm switch
    real_parts = [p for p in parts if len(p) > 3 and not p.replace("-", "").replace(" ", "").isdigit()]
    if len(real_parts) < 2:
        return False
    # Skip if slash is inside parentheses like "(4/9 missed appts.)"
    if "(" in firm_str and ")" in firm_str:
        paren_start = firm_str.index("(")
        paren_end = firm_str.index(")")
        slash_pos = firm_str.index("/")
        if paren_start < slash_pos < paren_end:
            return False
    # Skip if parts look like dates (all short numeric fragments)
    short_parts = [p for p in parts if len(p.strip()) <= 2 and p.strip().isdigit()]
    if len(short_parts) >= 2:
        return False
    # Skip "lvm" / phone note patterns
    if "lvm" in firm_str.lower() or "missed appt" in firm_str.lower():
        return False
    return True


def clean_firm_name(name):
    """Strip extra whitespace, emails, phone numbers from firm name."""
    name = name.strip()
    # Remove trailing email patterns
    parts = name.split()
    cleaned = []
    for p in parts:
        if "@" in p:
            continue  # skip emails
        if p.lower() in ("in", "negotiations", "negotiating"):
            break  # stop at negotiation notes
        cleaned.append(p)
    return " ".join(cleaned).strip()


def process():
    total_updated = 0
    total_skipped = 0

    for tid, label in TABLES:
        print(f"\n{'='*60}")
        print(f"Processing {label} (table {tid})")
        print(f"{'='*60}")

        rows = fetch_all(tid)
        slash_rows = [r for r in rows if "/" in str(r.get("Law Firm Name", ""))]
        print(f"  Total rows: {len(rows)}, with '/': {len(slash_rows)}")

        for r in slash_rows:
            raw = str(r.get("Law Firm Name", ""))
            case_label = r.get("Case Label") or "(no label)"
            row_id = r["id"]
            existing_notes = r.get("Case Notes") or ""

            if not is_real_firm_switch(raw):
                print(f"  SKIP (not a real switch): id={row_id} '{raw[:60]}'")
                total_skipped += 1
                continue

            parts = [p.strip() for p in raw.split("/") if p.strip()]
            current_firm = clean_firm_name(parts[-1])
            previous_firms = [clean_firm_name(p) for p in parts[:-1]]

            # Build history note
            history = " -> ".join(previous_firms + [f"{current_firm} (current)"])
            note = f"Firm history: {history}"

            # Don't duplicate if already processed
            if existing_notes and "Firm history:" in existing_notes:
                print(f"  SKIP (already processed): id={row_id} {case_label[:30]}")
                total_skipped += 1
                continue

            # Append to existing notes
            new_notes = f"{existing_notes}\n{note}".strip() if existing_notes else note

            print(f"  UPDATE id={row_id} {case_label[:30]}")
            print(f"    Old: {raw[:80]}")
            print(f"    New firm: {current_firm}")
            print(f"    History: {history}")

            if not DRY_RUN:
                patch_data = {
                    "Law Firm Name": current_firm,
                    "Case Notes": new_notes,
                }
                resp = requests.patch(
                    f"{BR}/api/database/rows/table/{tid}/{row_id}/?user_field_names=true",
                    headers=HEADERS,
                    json=patch_data,
                )
                if resp.status_code == 200:
                    print(f"    ✓ Updated")
                else:
                    print(f"    ✗ Failed: {resp.status_code} {resp.text[:100]}")
                time.sleep(0.15)  # rate limit

            total_updated += 1

    print(f"\n{'='*60}")
    print(f"DONE: {total_updated} updated, {total_skipped} skipped")
    if DRY_RUN:
        print("(DRY RUN — no changes made. Run without --dry-run to apply)")


if __name__ == "__main__":
    process()
