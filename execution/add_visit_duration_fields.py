"""
Add visit-duration tracking fields to T_GOR_ROUTE_STOPS (802):
  - Arrived At     (text)   — set when status flips to 'In Progress' (rep tapped Arrive)
  - Departed At    (text)   — set when status flips to Visited / Skipped / Not Reached
  - Duration Mins  (number) — computed at departure: minutes between Arrived and Departed

Datetimes stored as 'YYYY-MM-DD HH:MM' strings (matches existing 'Completed At'
pattern from add_route_stop_fields.py — text fields avoid Baserow's date-API quirks).

JWT auth (email/password from .env). Idempotent.
"""
import os, requests, sys
from dotenv import load_dotenv

load_dotenv()
BR = os.environ["BASEROW_URL"]
EMAIL = os.environ["BASEROW_EMAIL"]
PASSWORD = os.environ["BASEROW_PASSWORD"]

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TID = 802

FIELDS = [
    {"name": "Arrived At",    "type": "text"},
    {"name": "Departed At",   "type": "text"},
    {"name": "Duration Mins", "type": "number", "number_decimal_places": 0, "number_negative": False},
]


def jwt():
    r = requests.post(f"{BR}/api/user/token-auth/", json={"email": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    d = r.json()
    return d.get("access_token") or d.get("token")


def main():
    token = jwt()
    h = {"Authorization": f"JWT {token}", "Content-Type": "application/json"}

    existing = {f["name"] for f in requests.get(f"{BR}/api/database/fields/table/{TID}/", headers=h).json()}

    for spec in FIELDS:
        if spec["name"] in existing:
            print(f"  SKIP {spec['name']} — exists")
            continue
        r = requests.post(f"{BR}/api/database/fields/table/{TID}/", headers=h, json=spec)
        if r.status_code in (200, 201):
            print(f"  OK   {spec['name']} ({spec['type']})")
        else:
            print(f"  FAIL {spec['name']} — {r.status_code}: {r.text[:200]}")


if __name__ == "__main__":
    main()
