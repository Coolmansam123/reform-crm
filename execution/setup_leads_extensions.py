#!/usr/bin/env python3
"""
Extend the existing T_LEADS table (817 in DB 203 'Gorilla Marketing') into
a full follow-up pipeline:

  - Rename Status options in place (Scheduled -> Appointment Scheduled,
    Lost -> Dropped) and add a new 'Seen' option between Appointment
    Scheduled and Converted.
  - Add the follow-up fields: Owner, Follow-Up Date, Appointment Date,
    Seen Date, Converted Date, Referred By Company ID, Referred By
    Person ID, Stage Changed At, Created, Updated.
  - Extend the T_STAFF (815) 'Allowed Hubs' multi-select to include the
    new `leads`, `tasks`, `inbox` options (idempotent merge — never
    removes existing options).

Idempotent. Renames-by-ID so existing row values are preserved.

Usage:
    python execution/setup_leads_extensions.py
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL      = os.getenv("BASEROW_URL")
BASEROW_EMAIL    = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")

T_LEADS   = 817   # Gorilla Marketing DB (203)
T_STAFF   = 815

NEW_HUB_KEYS = ["leads", "tasks", "inbox"]


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


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_fields(table_id):
    r = requests.get(f"{BASEROW_URL}/api/database/fields/table/{table_id}/", headers=headers())
    r.raise_for_status()
    return r.json()

def create_field(table_id, field_config):
    r = requests.post(
        f"{BASEROW_URL}/api/database/fields/table/{table_id}/",
        headers=headers(), json=field_config,
    )
    if r.status_code == 200:
        print(f"    + {field_config['name']} ({field_config['type']})")
        return r.json()
    print(f"    WARN: failed '{field_config['name']}': {r.status_code} {r.text[:200]}")
    return None

def patch_field(field_id, patch, label=""):
    r = requests.patch(
        f"{BASEROW_URL}/api/database/fields/{field_id}/",
        headers=headers(), json=patch,
    )
    if r.status_code == 200:
        print(f"    = patched field {field_id} {label}")
    else:
        print(f"    WARN: patch field {field_id} {label} -> {r.status_code} {r.text[:200]}")
    return r


# ─── Status rename + option add ──────────────────────────────────────────────

# Current options (from setup_events_leads_tables.py): New / Contacted /
# Scheduled / Converted / Lost
# Desired options: New / Contacted / Appointment Scheduled / Seen / Converted / Dropped
RENAMES = {
    "Scheduled": "Appointment Scheduled",
    "Lost":      "Dropped",
}
NEW_OPTIONS = [
    {"value": "Seen", "color": "dark-blue"},
]
# Full desired order (new additions ordered between existing preserved ones):
DESIRED_ORDER = ["New", "Contacted", "Appointment Scheduled", "Seen",
                 "Converted", "Dropped"]

def update_status_options():
    print("\n1. T_LEADS 'Status' option rename + extend")
    fields = get_fields(T_LEADS)
    status = next((f for f in fields if f["name"] == "Status"), None)
    if not status:
        print("    WARN: no Status field on T_LEADS — aborting status-rename step")
        return
    existing = status.get("select_options", []) or []
    # Build a map of existing by id; apply renames
    by_value = {o["value"]: o for o in existing}
    updated_opts = []
    for o in existing:
        new_value = RENAMES.get(o["value"], o["value"])
        updated_opts.append({
            "id":    o["id"],
            "value": new_value,
            "color": o.get("color", "light-gray"),
        })
    # Add any wholly new options (those without an existing match after renames)
    current_values = {o["value"] for o in updated_opts}
    for new_opt in NEW_OPTIONS:
        if new_opt["value"] not in current_values:
            updated_opts.append(new_opt)
    # Reorder to match DESIRED_ORDER where possible (kept options first, extras after)
    order_key = {v: i for i, v in enumerate(DESIRED_ORDER)}
    updated_opts.sort(key=lambda o: order_key.get(o["value"], 999))

    patch_field(status["id"], {"select_options": updated_opts}, label="(Status)")


# ─── New fields on T_LEADS ───────────────────────────────────────────────────

NEW_LEADS_FIELDS = [
    {"name": "Owner",                 "type": "text"},
    {"name": "Follow-Up Date",        "type": "date", "date_format": "US", "date_include_time": False},
    {"name": "Appointment Date",      "type": "date", "date_format": "US", "date_include_time": True},
    {"name": "Seen Date",             "type": "date", "date_format": "US", "date_include_time": False},
    {"name": "Converted Date",        "type": "date", "date_format": "US", "date_include_time": False},
    {"name": "Stage Changed At",      "type": "date", "date_format": "US", "date_include_time": True},
    {"name": "Created",               "type": "date", "date_format": "US", "date_include_time": True},
    {"name": "Updated",               "type": "date", "date_format": "US", "date_include_time": True},
    # Referral source IDs as plain numbers — T_LEADS is in DB 203 and
    # cross-DB link_rows to T_COMPANIES/T_CONTACTS (DB 197) are forbidden.
    {"name": "Referred By Company ID", "type": "number", "number_decimal_places": 0},
    {"name": "Referred By Person ID",  "type": "number", "number_decimal_places": 0},
]

def add_new_fields():
    print("\n2. T_LEADS new follow-up fields")
    existing = get_fields(T_LEADS)
    existing_names = {f["name"] for f in existing}
    for cfg in NEW_LEADS_FIELDS:
        if cfg["name"] in existing_names:
            print(f"    = {cfg['name']} (exists)")
        else:
            create_field(T_LEADS, cfg)


# ─── T_STAFF 'Allowed Hubs' merge ───────────────────────────────────────────

def extend_allowed_hubs(hub_keys):
    print("\n3. T_STAFF 'Allowed Hubs' options")
    fields = get_fields(T_STAFF)
    allowed = next((f for f in fields if f["name"] == "Allowed Hubs"), None)
    if not allowed:
        print("    WARN: T_STAFF has no 'Allowed Hubs' field — skipping")
        return
    existing_opts = allowed.get("select_options", []) or []
    existing_vals = {o["value"] for o in existing_opts}
    to_add = [k for k in hub_keys if k not in existing_vals]
    if not to_add:
        print(f"    = All target hub keys already present ({sorted(existing_vals)})")
        return
    # Merge: preserve existing (with ids) + append new ones without ids
    color_map = {"leads": "pink", "tasks": "blue", "inbox": "orange"}
    merged = [
        {"id": o["id"], "value": o["value"], "color": o.get("color", "light-gray")}
        for o in existing_opts
    ] + [
        {"value": k, "color": color_map.get(k, "light-gray")} for k in to_add
    ]
    patch_field(allowed["id"], {"select_options": merged}, label="(Allowed Hubs)")
    print(f"    + Added: {to_add}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Extending T_LEADS (817) for full follow-up pipeline")
    print("=" * 60)

    update_status_options()
    add_new_fields()
    extend_allowed_hubs(NEW_HUB_KEYS)

    print("\n" + "=" * 60)
    print("Done. T_LEADS is now ready for the leads hub.")
    print("=" * 60)


if __name__ == "__main__":
    main()
