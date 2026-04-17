"""
One-shot schema change: adds a 'Firm History' long_text field to all 4 PI tables.
Idempotent — skips tables that already have the field.

Note: Baserow database tokens usually cannot create fields. If this fails with
401/403, the user must add the field via the Baserow UI instead (or provide a
JWT). This script also supports BASEROW_JWT env var as a fallback.
"""
import os, requests, sys
from dotenv import load_dotenv

load_dotenv()
BR = os.environ["BASEROW_URL"]
BT = os.environ["BASEROW_API_TOKEN"]
EMAIL = os.environ.get("BASEROW_EMAIL")
PASSWORD = os.environ.get("BASEROW_PASSWORD")


def fetch_jwt():
    r = requests.post(
        f"{BR}/api/user/token-auth/",
        json={"email": EMAIL, "password": PASSWORD},
    )
    r.raise_for_status()
    # Baserow returns {"token": "...", "access_token": "..."} depending on version
    data = r.json()
    return data.get("access_token") or data.get("token")


JWT = fetch_jwt() if EMAIL and PASSWORD else None

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TABLES = [
    (775, "Active"),
    (773, "Billed"),
    (776, "Awaiting"),
    (772, "Closed"),
]

FIELD_NAME = "Firm History"


def auth_headers(use_jwt=False):
    if use_jwt and JWT:
        return {"Authorization": f"JWT {JWT}", "Content-Type": "application/json"}
    return {"Authorization": f"Token {BT}", "Content-Type": "application/json"}


def list_fields(tid):
    r = requests.get(f"{BR}/api/database/fields/table/{tid}/", headers=auth_headers())
    r.raise_for_status()
    return r.json()


def create_field(tid, use_jwt=False):
    body = {"name": FIELD_NAME, "type": "long_text"}
    r = requests.post(
        f"{BR}/api/database/fields/table/{tid}/",
        headers=auth_headers(use_jwt=use_jwt),
        json=body,
    )
    return r


def main():
    for tid, label in TABLES:
        fields = list_fields(tid)
        if any(f["name"] == FIELD_NAME for f in fields):
            print(f"  SKIP {label} ({tid}) — '{FIELD_NAME}' already exists")
            continue

        # Try token first
        r = create_field(tid, use_jwt=False)
        if r.status_code in (200, 201):
            print(f"  OK   {label} ({tid}) — created '{FIELD_NAME}' with token")
            continue

        # Fall back to JWT if provided
        if JWT:
            r2 = create_field(tid, use_jwt=True)
            if r2.status_code in (200, 201):
                print(f"  OK   {label} ({tid}) — created '{FIELD_NAME}' with JWT")
                continue
            print(f"  FAIL {label} ({tid}) — token={r.status_code}, jwt={r2.status_code}: {r2.text[:150]}")
        else:
            print(f"  FAIL {label} ({tid}) — {r.status_code}: {r.text[:150]}")
            print(f"       (no BASEROW_JWT env var — add field via Baserow UI instead)")


if __name__ == "__main__":
    main()
