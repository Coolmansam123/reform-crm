#!/usr/bin/env python3
"""
Create (or update) the Patient Reactivation automation row in T_SEQUENCES.

Trigger:        patient_stale
Trigger Config: (empty — scan_stale_patients decides which patients match
                  by checking Follow-Up Date; no per-automation filter)
Steps:          send_sms (no wait — scan runs daily; dedupe-per-month
                  already prevents spam)
Variables:      {first_name}, {name}, {phone}, {doctor}
Is Active:      false  (start as a draft — flip in Baserow UI once tested)

Prereq:
  - `Recipient Phone` field must exist on T_SEQUENCE_ENROLLMENTS (run
    setup_add_recipient_phone.py first)
  - send_due_sequence_steps must prefer `Recipient Phone` from the run
    over the Lead ID → T_LEADS lookup (shipped 2026-04-22)

Idempotent — if a row with the same Name exists, PATCH it.

Usage:
    python execution/setup_patient_reactivation_automation.py
"""
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL  = os.getenv("BASEROW_URL")
BT           = os.getenv("BASEROW_API_TOKEN")
T_SEQUENCES  = 824

AUTOMATION_NAME = "Patient Reactivation — 14-day stall"

STEPS = [
    {
        "type": "send_sms",
        "body": (
            "Hi {first_name}, it's been a bit since your last visit at Reform. "
            "We'd love to check in on how you're feeling. Can we help you "
            "schedule a follow-up? Reply here or call (832) 699-3148. — {doctor}"
        ),
    },
]

PAYLOAD = {
    "Name":           AUTOMATION_NAME,
    "Description":    "Fires when a PI patient's Follow-Up Date is 14+ days in the past (in an open stage). Sends a single SMS asking the patient to reschedule. Deduped per-patient-per-month by scan_stale_patients. Variables: {first_name}, {doctor}.",
    "Category":       "patient",
    "Trigger":        "patient_stale",
    "Trigger Config": "",
    "Steps JSON":     json.dumps(STEPS, indent=2),
    "Is Active":      False,  # Draft — flip to true in Baserow UI after a test
}


def _headers():
    return {"Authorization": f"Token {BT}", "Content-Type": "application/json"}


def find_by_name(name: str) -> dict | None:
    url = f"{BASEROW_URL}/api/database/rows/table/{T_SEQUENCES}/?user_field_names=true&size=200"
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    for row in r.json().get("results", []):
        if (row.get("Name") or "").strip() == name:
            return row
    return None


def main():
    if not BASEROW_URL or not BT:
        raise SystemExit("BASEROW_URL or BASEROW_API_TOKEN missing from env")

    print(f"Looking for existing automation named {AUTOMATION_NAME!r}...")
    existing = find_by_name(AUTOMATION_NAME)

    if existing:
        row_id = existing["id"]
        print(f"  Found row #{row_id} — patching with latest config")
        url = f"{BASEROW_URL}/api/database/rows/table/{T_SEQUENCES}/{row_id}/?user_field_names=true"
        r = requests.patch(url, headers=_headers(), json=PAYLOAD, timeout=30)
        r.raise_for_status()
        print(f"  Patched.")
    else:
        print(f"  Not found — creating new row")
        url = f"{BASEROW_URL}/api/database/rows/table/{T_SEQUENCES}/?user_field_names=true"
        r = requests.post(url, headers=_headers(), json=PAYLOAD, timeout=30)
        r.raise_for_status()
        row_id = r.json()["id"]
        print(f"  Created row #{row_id}")

    print()
    print(f"Automation '{AUTOMATION_NAME}' is in Baserow as row #{row_id}.")
    print(f"Is Active = False  (draft). Flip to true in the Baserow UI after testing.")
    print()
    print("How to test:")
    print("  1. Pick a test patient in T_PI_ACTIVE and set their Follow-Up Date to a")
    print("     date > 14 days ago (e.g. 2026-04-01). Make sure Phone is filled.")
    print("  2. Flip the automation's Is Active = true.")
    print("  3. Run `modal run execution/modal_outreach_hub.py::scan_stale_patients`.")
    print("  4. Verify an Automation Run row appears in T_SEQUENCE_ENROLLMENTS with")
    print("     Recipient Phone populated and Status=active, Next Send At ~= now.")
    print("  5. Run `modal run execution/modal_outreach_hub.py::send_due_sequence_steps`.")
    print("  6. Your test phone should receive the SMS.")
    print("  7. If SMS lands correctly, you're done — the daily cron (9am Pacific)")
    print("     will now auto-fire this flow for any real patient that goes stale.")


if __name__ == "__main__":
    main()
