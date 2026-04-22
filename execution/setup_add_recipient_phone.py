#!/usr/bin/env python3
"""
Add the `Recipient Phone` field to T_SEQUENCE_ENROLLMENTS (825).

Background: `scan_stale_patients` in modal_outreach_hub.py writes a
`Recipient Phone` value on each automation run it creates. But that field
never existed in the T_SEQUENCE_ENROLLMENTS schema — the original
ENROLLMENTS_FIELDS in setup_sequences_tables.py didn't include it
(phones were always resolved from Lead ID → T_LEADS). PI patients live
in T_PI_* and have no Lead ID, so we store their phone directly on the
enrollment row.

Idempotent.

Usage:
    python execution/setup_add_recipient_phone.py
"""
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL      = os.getenv("BASEROW_URL")
BASEROW_EMAIL    = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
T_SEQUENCE_ENROLLMENTS = 825


_jwt_token = None
_jwt_time = 0


def fresh_token():
    global _jwt_token, _jwt_time
    if _jwt_token is None or (time.time() - _jwt_time) > 480:
        r = requests.post(f"{BASEROW_URL}/api/user/token-auth/", json={
            "email": BASEROW_EMAIL, "password": BASEROW_PASSWORD,
        })
        r.raise_for_status()
        _jwt_token = r.json()["access_token"]
        _jwt_time = time.time()
    return _jwt_token


def headers():
    return {"Authorization": f"JWT {fresh_token()}", "Content-Type": "application/json"}


def main():
    r = requests.get(f"{BASEROW_URL}/api/database/fields/table/{T_SEQUENCE_ENROLLMENTS}/",
                     headers=headers(), timeout=30)
    r.raise_for_status()
    existing = {f["name"] for f in r.json()}
    if "Recipient Phone" in existing:
        print("  = Recipient Phone (exists) — no change")
        return
    r = requests.post(
        f"{BASEROW_URL}/api/database/fields/table/{T_SEQUENCE_ENROLLMENTS}/",
        headers=headers(),
        json={"name": "Recipient Phone", "type": "phone_number"},
        timeout=30,
    )
    if r.status_code == 200:
        print("  + Recipient Phone (phone_number) added")
    else:
        print(f"  WARN: failed: {r.status_code} {r.text[:200]}")


if __name__ == "__main__":
    main()
