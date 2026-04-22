#!/usr/bin/env python3
"""
Add attorney-portal-related fields to T_COMPANIES (820):

  - Portal Slug          (text) — URL-safe random string used in /a/{slug}
                                  Non-guessable (16+ chars). Unique per firm.
  - Portal Enabled       (boolean) — admin gates the portal per-firm.
  - Portal View Count    (number) — incremented on each public portal hit.
  - Portal Last Viewed   (date+time) — timestamp of last public hit.

Idempotent.

Usage:
    python execution/setup_attorney_portal_fields.py
"""
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL      = os.getenv("BASEROW_URL")
BASEROW_EMAIL    = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
T_COMPANIES      = 820


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


PORTAL_FIELDS = [
    {"name": "Portal Slug",        "type": "text"},
    {"name": "Portal Enabled",     "type": "boolean"},
    {"name": "Portal View Count",  "type": "number", "number_decimal_places": 0},
    {"name": "Portal Last Viewed", "type": "date", "date_format": "US", "date_include_time": True},
]


def main():
    r = requests.get(f"{BASEROW_URL}/api/database/fields/table/{T_COMPANIES}/",
                     headers=headers(), timeout=30)
    r.raise_for_status()
    existing_names = {f["name"] for f in r.json()}
    for cfg in PORTAL_FIELDS:
        if cfg["name"] in existing_names:
            print(f"  = {cfg['name']} (exists)")
            continue
        r = requests.post(
            f"{BASEROW_URL}/api/database/fields/table/{T_COMPANIES}/",
            headers=headers(), json=cfg, timeout=30,
        )
        if r.status_code == 200:
            print(f"  + {cfg['name']} ({cfg['type']})")
        else:
            print(f"  WARN: '{cfg['name']}' failed: {r.status_code} {r.text[:200]}")
    print("\nDone.")


if __name__ == "__main__":
    main()
