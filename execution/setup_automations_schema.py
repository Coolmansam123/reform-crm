#!/usr/bin/env python3
"""
Evolve the Sequences schema into unified Automations.

  - Rename tables: `Sequences` \u2192 `Automations`,
                    `Sequence Enrollments` \u2192 `Automation Runs`
  - Add `Trigger` single_select to Automations (manual / new_lead /
    lead_stage_changed / lead_converted / lead_dropped)
  - Add `Trigger Config` text field (holds the parameter for triggers
    that need one \u2014 e.g. `to:Contacted` for lead_stage_changed)

Python constants T_SEQUENCES / T_SEQUENCE_ENROLLMENTS stay the same (they're
just numeric table IDs), so no downstream code changes.

Idempotent.

Usage:
    python execution/setup_automations_schema.py
"""
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL      = os.getenv("BASEROW_URL")
BASEROW_EMAIL    = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
T_SEQUENCES            = 824
T_SEQUENCE_ENROLLMENTS = 825


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


def rename_table(tid, new_name):
    r = requests.patch(f"{BASEROW_URL}/api/database/tables/{tid}/",
                       headers=headers(), json={"name": new_name})
    if r.status_code == 200:
        print(f"  = Table {tid} renamed to '{new_name}'")
    else:
        print(f"  WARN: rename table {tid}: {r.status_code} {r.text[:200]}")


def get_fields(tid):
    r = requests.get(f"{BASEROW_URL}/api/database/fields/table/{tid}/", headers=headers())
    r.raise_for_status(); return r.json()


def create_field(tid, cfg):
    r = requests.post(f"{BASEROW_URL}/api/database/fields/table/{tid}/",
                      headers=headers(), json=cfg)
    if r.status_code == 200:
        print(f"    + {cfg['name']} ({cfg['type']})")
    else:
        print(f"    WARN: '{cfg['name']}' failed: {r.status_code} {r.text[:200]}")


def ensure_fields(tid, configs):
    existing_names = {f["name"] for f in get_fields(tid)}
    for cfg in configs:
        if cfg["name"] in existing_names:
            print(f"    = {cfg['name']} (exists)")
        else:
            create_field(tid, cfg)


AUTOMATION_FIELDS = [
    {"name": "Trigger", "type": "single_select", "select_options": [
        {"value": "manual",               "color": "light-gray"},
        {"value": "new_lead",             "color": "blue"},
        {"value": "lead_stage_changed",   "color": "orange"},
        {"value": "lead_converted",       "color": "green"},
        {"value": "lead_dropped",         "color": "red"},
        {"value": "patient_stale",        "color": "dark-red"},
    ]},
    # e.g. "to:Contacted" for `lead_stage_changed`. Blank for others.
    {"name": "Trigger Config", "type": "text"},
]


def patch_field(fid, patch):
    r = requests.patch(f"{BASEROW_URL}/api/database/fields/{fid}/",
                       headers=headers(), json=patch)
    return r.status_code == 200


def ensure_select_options(tid, field_name, desired):
    fields = get_fields(tid)
    f = next((x for x in fields if x["name"] == field_name), None)
    if not f or f.get("type") != "single_select": return
    existing = {o["value"] for o in f.get("select_options", [])}
    missing = [o for o in desired if o["value"] not in existing]
    if missing:
        merged = list(f.get("select_options", [])) + missing
        if patch_field(f["id"], {"select_options": merged}):
            for o in missing:
                print(f"    + {field_name}: added option '{o['value']}'")


def main():
    print("=" * 60)
    print("Evolving Sequences \u2192 Automations")
    print("=" * 60)

    print("\n1. Rename Baserow tables")
    rename_table(T_SEQUENCES,            "Automations")
    rename_table(T_SEQUENCE_ENROLLMENTS, "Automation Runs")

    print("\n2. Add Trigger + Trigger Config fields")
    ensure_fields(T_SEQUENCES, AUTOMATION_FIELDS)
    # Merge any new Trigger options into existing field
    trigger_cfg = next((f for f in AUTOMATION_FIELDS if f["name"] == "Trigger"), None)
    if trigger_cfg:
        ensure_select_options(T_SEQUENCES, "Trigger", trigger_cfg["select_options"])

    print("\n" + "=" * 60)
    print("Done. Python constants unchanged:")
    print(f"  T_SEQUENCES            = {T_SEQUENCES}   (now labeled 'Automations')")
    print(f"  T_SEQUENCE_ENROLLMENTS = {T_SEQUENCE_ENROLLMENTS}   (now labeled 'Automation Runs')")
    print("=" * 60)


if __name__ == "__main__":
    main()
