"""
Add `Sentiment` single_select field to T_ACTIVITIES (822).

Used by the Phase 1 sentiment-tag feature: reps tag each activity Green/Yellow/Red
to capture how the visit went. Briefing card + visit history render a colored
dot per row.

JWT auth (email/password from .env) — Baserow database tokens can't create fields.
Idempotent.
"""
import os, requests, sys
from dotenv import load_dotenv

load_dotenv()
BR = os.environ["BASEROW_URL"]
EMAIL = os.environ["BASEROW_EMAIL"]
PASSWORD = os.environ["BASEROW_PASSWORD"]

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TID = 822

FIELD = {
    "name": "Sentiment",
    "type": "single_select",
    "select_options": [
        {"value": "Green",  "color": "green"},
        {"value": "Yellow", "color": "yellow"},
        {"value": "Red",    "color": "red"},
    ],
}


def jwt():
    r = requests.post(f"{BR}/api/user/token-auth/", json={"email": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    d = r.json()
    return d.get("access_token") or d.get("token")


def main():
    token = jwt()
    h = {"Authorization": f"JWT {token}", "Content-Type": "application/json"}

    existing = {f["name"] for f in requests.get(f"{BR}/api/database/fields/table/{TID}/", headers=h).json()}

    if FIELD["name"] in existing:
        print(f"  SKIP {FIELD['name']} on {TID} — exists")
        return

    r = requests.post(f"{BR}/api/database/fields/table/{TID}/", headers=h, json=FIELD)
    if r.status_code in (200, 201):
        print(f"  OK   {FIELD['name']} on {TID} (single_select: Green/Yellow/Red)")
    else:
        print(f"  FAIL {FIELD['name']} on {TID} — {r.status_code}: {r.text[:200]}")


if __name__ == "__main__":
    main()
