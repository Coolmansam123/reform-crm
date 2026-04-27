"""
Create T_PUSH_SUBSCRIPTIONS table in DB 197 (Reform Chiropractic CRM) for the
Phase 3 push-notifications feature.

One row per (rep, browser/device) push subscription:
  - Email          (text)       — owner of the subscription
  - Endpoint       (long_text)  — push service URL (Apple/FCM/Mozilla)
  - Keys           (long_text)  — JSON {p256dh, auth}; required by Web Push
  - Created        (text)       — 'YYYY-MM-DD HH:MM' UTC
  - Last Used      (text)       — set after each successful push send
  - Active         (boolean)    — false when send fails 410 Gone (subscription revoked)

Idempotent. Records the table ID in `.tmp/push_table_id.txt` so the migration
output is easy to copy into hub/constants.py without re-running.
"""
import os, time, requests, sys, pathlib
from dotenv import load_dotenv

load_dotenv()
BR = os.environ["BASEROW_URL"]
EMAIL = os.environ["BASEROW_EMAIL"]
PW = os.environ["BASEROW_PASSWORD"]
DB_ID = 197

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def jwt():
    r = requests.post(f"{BR}/api/user/token-auth/", json={"email": EMAIL, "password": PW})
    r.raise_for_status()
    d = r.json()
    return d.get("access_token") or d.get("token")


_TOK = jwt()
H = {"Authorization": f"JWT {_TOK}", "Content-Type": "application/json"}


def list_tables(dbid):
    r = requests.get(f"{BR}/api/database/tables/database/{dbid}/", headers=H)
    r.raise_for_status()
    return r.json()


def create_table(dbid, name):
    r = requests.post(f"{BR}/api/database/tables/database/{dbid}/", headers=H, json={"name": name})
    r.raise_for_status()
    return r.json()


def get_fields(tid):
    r = requests.get(f"{BR}/api/database/fields/table/{tid}/", headers=H)
    r.raise_for_status()
    return r.json()


def create_field(tid, spec):
    r = requests.post(f"{BR}/api/database/fields/table/{tid}/", headers=H, json=spec)
    if r.status_code in (200, 201):
        print(f"    + {spec['name']} ({spec['type']})")
        return True
    print(f"    WARN {spec['name']}: {r.status_code} {r.text[:200]}")
    return False


def rename_primary(tid, new_name):
    fields = get_fields(tid)
    primary = next((f for f in fields if f.get("primary")), None)
    if primary and primary["name"] != new_name:
        r = requests.patch(f"{BR}/api/database/fields/{primary['id']}/", headers=H, json={"name": new_name})
        if r.status_code in (200, 201):
            print(f"    = renamed primary to '{new_name}'")


def delete_field(fid):
    r = requests.delete(f"{BR}/api/database/fields/{fid}/", headers=H)
    return r.status_code in (200, 204)


FIELDS = [
    # Email is primary so the table view shows the rep at a glance.
    {"name": "Endpoint",  "type": "long_text"},
    {"name": "Keys",      "type": "long_text"},
    {"name": "Created",   "type": "text"},
    {"name": "Last Used", "type": "text"},
    {"name": "Active",    "type": "boolean"},
]


def main():
    tables = list_tables(DB_ID)
    existing = next((t for t in tables if t["name"] == "Push Subscriptions"), None)
    if existing:
        tid = existing["id"]
        print(f"  Table 'Push Subscriptions' exists (ID: {tid})")
    else:
        t = create_table(DB_ID, "Push Subscriptions")
        tid = t["id"]
        print(f"  Created 'Push Subscriptions' (ID: {tid})")
    rename_primary(tid, "Email")
    have = {f["name"] for f in get_fields(tid)}
    for spec in FIELDS:
        if spec["name"] in have:
            print(f"    = {spec['name']} (exists)")
        else:
            create_field(tid, spec)
    # Drop default 'Notes' if present.
    for f in get_fields(tid):
        if f["name"] == "Notes" and not f.get("primary", False):
            if delete_field(f["id"]):
                print(f"    - removed default 'Notes'")
    # Persist for the next caller.
    p = pathlib.Path(".tmp")
    p.mkdir(exist_ok=True)
    (p / "push_table_id.txt").write_text(str(tid))
    print(f"\n  Add to hub/constants.py:")
    print(f"      T_PUSH_SUBSCRIPTIONS = {tid}")


if __name__ == "__main__":
    main()
