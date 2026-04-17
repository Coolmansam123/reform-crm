"""
Add missing fields to T_GOR_ROUTE_STOPS (802):
  - Notes          (long_text)  — fixes latent bug (code wrote to nonexistent field)
  - Completed At   (text)       — fixes latent bug
  - Completed By   (text)       — fixes latent bug
  - Check-In Lat   (number, 7 decimals) — new, GPS check-in
  - Check-In Lng   (number, 7 decimals) — new, GPS check-in

Uses JWT auth (email/password from .env) since database tokens can't create fields.
Idempotent — skips fields that already exist.
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

FIELDS_TO_ADD = [
    {"name": "Notes",        "type": "long_text"},
    {"name": "Completed At", "type": "text"},
    {"name": "Completed By", "type": "text"},
    {"name": "Check-In Lat", "type": "number", "number_decimal_places": 7, "number_negative": True},
    {"name": "Check-In Lng", "type": "number", "number_decimal_places": 7, "number_negative": True},
]


def jwt():
    r = requests.post(f"{BR}/api/user/token-auth/", json={"email": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    d = r.json()
    return d.get("access_token") or d.get("token")


def main():
    token = jwt()
    h_jwt = {"Authorization": f"JWT {token}", "Content-Type": "application/json"}

    existing = {f["name"] for f in requests.get(f"{BR}/api/database/fields/table/{TID}/", headers=h_jwt).json()}

    for spec in FIELDS_TO_ADD:
        if spec["name"] in existing:
            print(f"  SKIP {spec['name']} — exists")
            continue
        r = requests.post(f"{BR}/api/database/fields/table/{TID}/", headers=h_jwt, json=spec)
        if r.status_code in (200, 201):
            print(f"  OK   {spec['name']} ({spec['type']})")
        else:
            print(f"  FAIL {spec['name']} — {r.status_code}: {r.text[:200]}")


if __name__ == "__main__":
    main()
