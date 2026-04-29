"""
Add a Baserow auto-managed Created field to T_GOR_ACTS (791).

Field type `created_on` is read-only and Baserow stamps every new row with
the actual insertion time. Eliminates the need to populate `Created` in
code on each write.

Existing rows have no recorded creation time and will show whatever Baserow
backfills (typically blank or "now"); the visit-history sort still falls
back to row id for those, so legacy ordering is preserved.

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

TID = 791  # T_GOR_ACTS

FIELD_NAME = "Created"


def jwt():
    r = requests.post(f"{BR}/api/user/token-auth/", json={"email": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    d = r.json()
    return d.get("access_token") or d.get("token")


def main():
    token = jwt()
    h = {"Authorization": f"JWT {token}", "Content-Type": "application/json"}

    existing = {f["name"] for f in requests.get(f"{BR}/api/database/fields/table/{TID}/", headers=h).json()}

    if FIELD_NAME in existing:
        print(f"  SKIP {FIELD_NAME} — exists")
        return

    spec = {
        "name": FIELD_NAME,
        "type": "created_on",
        "date_format": "ISO",
        "date_include_time": True,
        "date_time_format": "24",
    }
    r = requests.post(f"{BR}/api/database/fields/table/{TID}/", headers=h, json=spec)
    if r.status_code in (200, 201):
        print(f"  OK   {FIELD_NAME} (created_on, ISO, with time)")
    else:
        print(f"  FAIL {FIELD_NAME} — {r.status_code}: {r.text[:300]}")


if __name__ == "__main__":
    main()
