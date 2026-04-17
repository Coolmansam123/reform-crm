#!/usr/bin/env python3
"""
Add 'Allowed Hubs' multiple_select field to T_STAFF table.

Idempotent: skips if field already exists.

Usage:
    python execution/setup_staff_hubs_field.py
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL      = os.getenv("BASEROW_URL")
BASEROW_EMAIL    = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
T_STAFF          = int(os.getenv("T_STAFF", "815"))

HUB_OPTIONS = [
    {"value": "attorney",       "color": "purple"},
    {"value": "guerilla",       "color": "orange"},
    {"value": "community",      "color": "green"},
    {"value": "pi_cases",       "color": "blue"},
    {"value": "billing",        "color": "red"},
    {"value": "communications", "color": "light-gray"},
    {"value": "social",         "color": "light-blue"},
    {"value": "calendar",       "color": "yellow"},
]

# ─── JWT Auth ────────────────────────────────────────────────────────────────

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


def headers():
    return {"Authorization": f"JWT {fresh_token()}", "Content-Type": "application/json"}


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print(f"T_STAFF table ID: {T_STAFF}")

    # Check existing fields
    r = requests.get(
        f"{BASEROW_URL}/api/database/fields/table/{T_STAFF}/",
        headers=headers(),
    )
    r.raise_for_status()
    existing = {f["name"]: f for f in r.json()}

    if "Allowed Hubs" in existing:
        print("  = Allowed Hubs field already exists, skipping.")
        return

    # Create the field
    print("  + Creating 'Allowed Hubs' (multiple_select)...")
    r = requests.post(
        f"{BASEROW_URL}/api/database/fields/table/{T_STAFF}/",
        headers=headers(),
        json={
            "name": "Allowed Hubs",
            "type": "multiple_select",
            "select_options": HUB_OPTIONS,
        },
    )
    if r.status_code == 200:
        field = r.json()
        print(f"  + Created 'Allowed Hubs' (field ID: {field['id']})")
        print(f"    Options: {[o['value'] for o in HUB_OPTIONS]}")
    else:
        print(f"  ERROR: {r.status_code} {r.text[:300]}")
        return

    print("\nDone! Now go to Baserow and assign hubs to your staff members.")
    print("Admin users automatically get access to all hubs (no assignment needed).")


if __name__ == "__main__":
    main()
