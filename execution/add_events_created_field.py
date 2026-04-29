"""
Add a Baserow auto-managed Created field to T_EVENTS (816).

Same as add_gor_acts_created_field.py but for the events table. Needed so
the unified Recent Activity feed can sort events chronologically by when
they were logged (T_EVENTS only has Event Date today, which is the future
event date, not when the row was created).

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

TID = 816  # T_EVENTS

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
