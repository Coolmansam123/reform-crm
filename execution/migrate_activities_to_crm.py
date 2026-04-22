#!/usr/bin/env python3
"""
Migrate rows from T_ATT_ACTS (784), T_GOR_ACTS (791), T_COM_ACTS (798) into the
unified T_ACTIVITIES (822) table in DB 197, resolving the Company link via
Legacy ID mapping.

Idempotent (checks Legacy Source + Legacy ID on T_ACTIVITIES before inserting).

Usage:
    python execution/migrate_activities_to_crm.py          # dry run
    python execution/migrate_activities_to_crm.py --apply  # write
"""

import argparse
import datetime as dt
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL      = os.getenv("BASEROW_URL")
BASEROW_EMAIL    = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
BASEROW_TOKEN    = os.getenv("BASEROW_API_TOKEN")

T_ATT_ACTS   = 784
T_GOR_ACTS   = 791
T_COM_ACTS   = 798
T_COMPANIES  = 820
T_ACTIVITIES = 822

SPECS = [
    {"tid": T_ATT_ACTS, "label": "attorney",  "old_link": "Law Firm",     "legacy_src_company": "attorney_venue",  "legacy_src_act": "attorney_act"},
    {"tid": T_GOR_ACTS, "label": "guerilla",  "old_link": "Business",     "legacy_src_company": "guerilla_venue",  "legacy_src_act": "guerilla_act"},
    {"tid": T_COM_ACTS, "label": "community", "old_link": "Organization", "legacy_src_company": "community_venue", "legacy_src_act": "community_act"},
]


# ─── Auth ────────────────────────────────────────────────────────────────────

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

def api_headers():
    return {"Authorization": f"Token {BASEROW_TOKEN}", "Content-Type": "application/json"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def fetch_all(tid):
    rows = []
    url = f"{BASEROW_URL}/api/database/rows/table/{tid}/?user_field_names=true&size=200"
    while url:
        r = requests.get(url, headers=api_headers(), timeout=30)
        r.raise_for_status()
        d = r.json()
        rows.extend(d["results"])
        url = d.get("next")
    return rows

def select_val(v):
    if isinstance(v, dict): return v.get("value") or ""
    return v or ""

def post_row(tid, payload):
    clean = {k: v for k, v in payload.items() if v is not None and v != ""}
    for attempt in range(4):
        try:
            r = requests.post(
                f"{BASEROW_URL}/api/database/rows/table/{tid}/?user_field_names=true",
                headers=api_headers(), json=clean, timeout=30,
            )
            if r.status_code in (200, 201):
                return r.json()
            if 400 <= r.status_code < 500:
                print(f"    ERROR {r.status_code}: {r.text[:300]}")
                raise RuntimeError("post_row failed")
        except requests.exceptions.RequestException as e:
            if attempt == 3: raise
        time.sleep(1.5 * (attempt + 1))

def build_legacy_to_company_map(legacy_source):
    companies = fetch_all(T_COMPANIES)
    out = {}
    for c in companies:
        src = select_val(c.get("Legacy Source"))
        if src != legacy_source:
            continue
        lid = c.get("Legacy ID")
        if lid is None: continue
        try: out[int(lid)] = c["id"]
        except (TypeError, ValueError): pass
    return out

def existing_legacy_index():
    rows = fetch_all(T_ACTIVITIES)
    out = {}
    for r in rows:
        src = select_val(r.get("Legacy Source"))
        lid = r.get("Legacy ID")
        if src and lid is not None:
            try: out[(src, int(lid))] = r["id"]
            except (TypeError, ValueError): pass
    return out


def map_activity(row, spec, company_id):
    return {
        "Summary":         row.get("Summary") or "",
        "Date":            row.get("Date") or None,
        "Type":            select_val(row.get("Type")) or None,
        "Outcome":         select_val(row.get("Outcome")) or None,
        "Contact Person":  row.get("Contact Person") or "",
        "Follow-Up Date":  row.get("Follow-Up Date") or None,
        "Company":         [company_id] if company_id else None,
        "Legacy Source":   spec["legacy_src_act"],
        "Legacy ID":       row["id"],
        "Created":         dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    dry_run = not args.apply

    print("=" * 60)
    print(f"{'[DRY RUN] ' if dry_run else ''}Migrating activities → T_ACTIVITIES (822)")
    print("=" * 60)

    existing = existing_legacy_index() if not dry_run else {}
    print(f"Already-migrated: {len(existing)}")

    for spec in SPECS:
        print(f"\n-- {spec['label']} activities (table {spec['tid']}) --")
        id_map = build_legacy_to_company_map(spec["legacy_src_company"])
        rows = fetch_all(spec["tid"])
        print(f"   found {len(rows)} activity rows")
        for row in rows:
            key = (spec["legacy_src_act"], row["id"])
            if key in existing:
                print(f"   = already migrated: #{row['id']}")
                continue
            old_links = row.get(spec["old_link"]) or []
            legacy_id = old_links[0].get("id") if old_links and isinstance(old_links[0], dict) else (old_links[0] if old_links else None)
            company_id = id_map.get(int(legacy_id)) if legacy_id else None
            payload = map_activity(row, spec, company_id)
            linked = f"LINKED -> company #{company_id}" if company_id else "UNLINKED"
            summary = (payload["Summary"] or "(no summary)")[:40]
            print(f"   + {row['id']:4d}  {summary:42s}  {linked}")
            if not dry_run:
                post_row(T_ACTIVITIES, payload)

    print("\n" + "=" * 60)
    print(f"{'[DRY RUN] ' if dry_run else ''}Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
