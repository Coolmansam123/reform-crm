"""
Add live-location fields to T_STAFF (815) for the Phase 2.3 admin live-rep map:
  - Latest Lat           (number, 7 decimals, signed)
  - Latest Lng           (number, 7 decimals, signed)
  - Location Updated At  (text, 'YYYY-MM-DD HH:MM' UTC)
  - Active Route ID      (text — current route the rep is on, '' when inactive)

Reps' phones POST /api/rep/ping every 30s while a route is open; admin map
polls /api/admin/reps/live and renders a pin per rep with location updated
in the last 5 min.

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

TID = 815

FIELDS = [
    {"name": "Latest Lat",          "type": "number", "number_decimal_places": 7, "number_negative": True},
    {"name": "Latest Lng",          "type": "number", "number_decimal_places": 7, "number_negative": True},
    {"name": "Location Updated At", "type": "text"},
    {"name": "Active Route ID",     "type": "text"},
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
