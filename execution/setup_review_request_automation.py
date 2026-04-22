#!/usr/bin/env python3
"""
Create (or update) the Review-Request automation row in T_SEQUENCES.

Trigger:        lead_stage_changed with Trigger Config `to:Seen`
Steps:          wait 2d -> SMS -> wait 5d -> email
Variables:      {first_name}, {review_url}, {doctor}
Is Active:      false  (start as a draft — flip in Baserow UI once tested)

Prereq: the `{review_url}` and `{doctor}` merge-variables were added to the
step-runner context in execution/modal_outreach_hub.py (2026-04-22). That
change must be deployed for the substitution to work at send time.

Idempotent — if a row with the same Name exists, PATCH it instead of
POSTing a duplicate.

Usage:
    python execution/setup_review_request_automation.py
"""
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL  = os.getenv("BASEROW_URL")
BT           = os.getenv("BASEROW_API_TOKEN")
T_SEQUENCES  = 824

AUTOMATION_NAME = "Review Request — Post-First-Visit"

STEPS = [
    {"type": "wait", "delay_days": 2},
    {
        "type": "send_sms",
        "body": (
            "Hi {first_name}! So glad we got to see you at Reform. "
            "If your visit went well, would you mind leaving us a quick "
            "Google review? {review_url} — {doctor}"
        ),
    },
    {"type": "wait", "delay_days": 5},
    {
        "type": "send_email",
        "subject": "Quick favor from Reform Chiropractic",
        "body": (
            "Hi {first_name},\n\n"
            "If your visit with us went well, a short Google review helps "
            "our practice enormously:\n{review_url}\n\n"
            "Thank you!\n\n"
            "Reform Chiropractic"
        ),
    },
]

PAYLOAD = {
    "Name":          AUTOMATION_NAME,
    "Description":   "Fires 2 days after a lead hits 'Seen'. SMS + 5-day email follow-up asking for a Google review. Uses {first_name}, {review_url}, {doctor} merge vars.",
    "Category":      "patient",
    "Trigger":       "lead_stage_changed",
    "Trigger Config": "to:Seen",
    "Steps JSON":    json.dumps(STEPS, indent=2),
    "Is Active":     False,  # Start as draft — flip in Baserow UI once tested
}


def _headers():
    return {"Authorization": f"Token {BT}", "Content-Type": "application/json"}


def find_by_name(name: str) -> dict | None:
    """Look up an existing automation row by Name (primary field)."""
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
    print(f"Is Active = False  (draft). Flip to true in the Baserow UI when ready.")
    print(f"Trigger Config = to:Seen  (fires when a lead transitions to stage 'Seen').")
    print()
    print("Next steps:")
    print("  1. Ensure GOOGLE_REVIEW_URL is set in the Modal `outreach-hub-secrets` secret")
    print("     and redeploy the hub so send_due_sequence_steps picks it up.")
    print("  2. Test by manually flipping a test lead's Status to 'Seen' in Baserow,")
    print("     then set its Next Send At in Automation Runs to now and run")
    print("     `modal run execution/modal_outreach_hub.py::send_due_sequence_steps`.")
    print("  3. Once SMS + email land correctly, flip Is Active = true.")


if __name__ == "__main__":
    main()
