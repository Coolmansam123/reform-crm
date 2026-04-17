#!/usr/bin/env python3
"""
Baserow Cleanup Script
======================
Dedicated script for cleaning up Baserow data across all CRM databases.
Runs independently from the law firm mapper/scraper pipeline.

Current operations:
  Step 1: Deduplicate Law Firm names (table 768)
  Step 2: Create Blacklisted Law Firms table + move blacklist entries
  Step 3: Add unknown firms from billing to Law Firms directory
  Step 4: Normalize Law Firm Names in Settlement & Finance (table 781)

Usage:
    python execution/baserow_cleanup.py [--step N] [--dry-run]
"""
import sys, os, json, time, argparse
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
from dotenv import load_dotenv

load_dotenv()
URL = os.getenv('BASEROW_URL')
EMAIL = os.getenv('BASEROW_EMAIL')
PASSWORD = os.getenv('BASEROW_PASSWORD')

LAW_FIRMS_TABLE = 768

# ─── Auth ─────────────────────────────────────────────────────────

_token = None
_token_time = 0

def get_token():
    global _token, _token_time
    if _token is None or (time.time() - _token_time) > 480:
        r = requests.post(f'{URL}/api/user/token-auth/', json={'email': EMAIL, 'password': PASSWORD})
        r.raise_for_status()
        _token = r.json()['access_token']
        _token_time = time.time()
    return _token

def headers():
    return {'Authorization': f'JWT {get_token()}', 'Content-Type': 'application/json'}

# ─── Helpers ──────────────────────────────────────────────────────

def fetch_all_rows(table_id):
    rows = []
    page = 1
    while True:
        r = requests.get(
            f'{URL}/api/database/rows/table/{table_id}/?size=200&page={page}&user_field_names=true',
            headers=headers()
        )
        r.raise_for_status()
        data = r.json()
        rows.extend(data['results'])
        if not data.get('next'):
            break
        page += 1
    return rows

def update_row(table_id, row_id, payload, dry_run=False):
    if dry_run:
        print(f'    [DRY-RUN] PATCH row {row_id}: {payload}')
        return True
    r = requests.patch(
        f'{URL}/api/database/rows/table/{table_id}/{row_id}/?user_field_names=true',
        headers=headers(), json=payload
    )
    if r.status_code == 200:
        return True
    print(f'    WARN: update row {row_id}: {r.status_code} {r.text[:200]}')
    return False

def delete_rows(table_id, row_ids, dry_run=False):
    if not row_ids:
        return 0
    if dry_run:
        print(f'    [DRY-RUN] DELETE rows: {row_ids}')
        return len(row_ids)
    r = requests.post(
        f'{URL}/api/database/rows/table/{table_id}/batch-delete/',
        headers=headers(), json={'items': row_ids}
    )
    if r.status_code in (200, 204):
        return len(row_ids)
    print(f'    WARN: delete rows {row_ids}: {r.status_code} {r.text[:200]}')
    return 0

# ─── Step 1: Deduplicate Law Firm Names ───────────────────────────

# Each entry: (canonical_name, keep_id, [ids_to_delete])
# keep_id = None means pick the lowest ID from the group automatically
# For exact duplicates where all names are the same, set canonical_name = None (use existing name)

MERGE_PLAN = [
    # Exact duplicates - identical names
    ('Braff Law Car Accident Personal Injury Lawyers', 652, [653, 668, 707, 713]),
    ('DK Law - Injury, Accident, and More',            677, [685, 694]),
    ('The Accident Guys',                              678, [695]),
    ('i Abogados de Accidentes',                       715, [716, 723]),

    # Name variants - standardize to canonical
    ('Karns & Karns',                                  47,  [48]),    # drop "Law" suffix
    ('Law Office of Daniel Kim',                       57,  [125]),   # drop "The"
    ("Law Office of Kerry O'Brien",                    59,  [128]),   # drop "The"
    ('Larry H. Parker',                                55,  [129]),   # drop "The Law Offices of"
    ('Law Offices of Daniel F. Jimenez',               64,  [31]),    # keep fuller name, drop bare name
    ('Law Offices of Oscar Sandoval',                  75,  [74]),    # drop middle initial "D."
    ('The Dominguez Firm',                             119, [648, 714]),  # drop Spanish variants
    ('Nelson & Natale',                                90,  [91]),    # drop long descriptor suffix
    ('Law Offices of Samer Habbas & Associates',       78,  [79]),    # fix typo "Sammer" -> "Samer"
    ('The Ceja Firm',                                  117, [29]),    # "Ceja Law Office" -> "The Ceja Firm"
    ('McGee Lerer Ogrin',                              675, [87]),    # rebranded name is canonical
]


def step1_deduplicate_law_firms(dry_run=False):
    print('\n' + '='*60)
    print('STEP 1: Deduplicate Law Firm Names')
    print('='*60)

    rows = fetch_all_rows(LAW_FIRMS_TABLE)
    id_to_row = {r['id']: r for r in rows}
    print(f'Loaded {len(rows)} rows from Law Firms table\n')

    renamed = 0
    deleted = 0
    skipped = 0

    for canonical_name, keep_id, delete_ids in MERGE_PLAN:
        current_name = (id_to_row.get(keep_id, {}).get('Law Firm Name') or '').strip()

        # Check if keep row exists
        if keep_id not in id_to_row:
            print(f'  SKIP: keep row {keep_id} not found (already cleaned?)')
            skipped += 1
            continue

        # Check which delete rows still exist
        existing_deletes = [d for d in delete_ids if d in id_to_row]
        already_gone = [d for d in delete_ids if d not in id_to_row]
        if already_gone:
            print(f'  NOTE: rows {already_gone} already deleted')

        # Rename canonical row if name differs
        if current_name != canonical_name:
            print(f'  RENAME [{keep_id}]: "{current_name}" -> "{canonical_name}"')
            if update_row(LAW_FIRMS_TABLE, keep_id, {'Law Firm Name': canonical_name}, dry_run):
                renamed += 1
        else:
            print(f'  KEEP   [{keep_id}]: "{canonical_name}" (name already correct)')

        # Delete duplicate rows
        if existing_deletes:
            dupe_names = [f"[{d}] '{(id_to_row[d].get('Law Firm Name') or '').strip()}'" for d in existing_deletes]
            print(f'  DELETE {dupe_names}')
            n = delete_rows(LAW_FIRMS_TABLE, existing_deletes, dry_run)
            deleted += n
        print()

    print('-'*60)
    print(f'Renamed:  {renamed} rows')
    print(f'Deleted:  {deleted} rows')
    print(f'Skipped:  {skipped} entries (already cleaned)')
    return renamed, deleted


# ─── Step 2: Blacklisted Law Firms table ──────────────────────────

LAW_FIRM_DIR_DB = 198   # Law Firm Directory database

# Firms to move to blacklist: (row_id_in_768, clean_name, reason)
BLACKLISTED_FIRMS = [
    (93,  'Omega Law Firm, PC',    'Do not send anything — shady practices, may have transferred cases to JLF'),
    (135, 'Top Notch Law Group',   'Blacklisted'),
    (136, 'Trillium Law',          'Do not send anything — shady practices'),
]


def step2_create_blacklist_table(dry_run=False):
    print('\n' + '='*60)
    print('STEP 2: Create Blacklisted Law Firms Table')
    print('='*60)

    # Check if table already exists in App 198
    r = requests.get(f'{URL}/api/database/tables/database/{LAW_FIRM_DIR_DB}/', headers=headers())
    r.raise_for_status()
    existing = {t['name']: t['id'] for t in r.json()}

    if 'Blacklisted Law Firms' in existing:
        table_id = existing['Blacklisted Law Firms']
        print(f'  Table already exists (ID={table_id}), skipping creation')
    else:
        if dry_run:
            print('  [DRY-RUN] Would create table "Blacklisted Law Firms" in Law Firm Directory')
            table_id = None
        else:
            r = requests.post(
                f'{URL}/api/database/tables/database/{LAW_FIRM_DIR_DB}/',
                headers=headers(), json={'name': 'Blacklisted Law Firms'}
            )
            r.raise_for_status()
            table_id = r.json()['id']
            print(f'  Created table "Blacklisted Law Firms" (ID={table_id})')

    if table_id and not dry_run:
        # Get current fields - use field_id keys for all writes (user_field_names
        # is unreliable for writes when fields were recently created/renamed)
        r = requests.get(f'{URL}/api/database/fields/table/{table_id}/', headers=headers())
        r.raise_for_status()
        fields = r.json()
        existing_names = {f['name'] for f in fields}
        fid = {f['name']: f'field_{f["id"]}' for f in fields}
        primary_fid = f'field_{next(f for f in fields if f.get("primary"))["id"]}'

        # Add Reason and Notes fields if missing
        for fname, ftype in [('Reason', 'long_text'), ('Notes', 'long_text'), ('Date Added', 'text')]:
            if fname not in existing_names:
                r = requests.post(
                    f'{URL}/api/database/fields/table/{table_id}/',
                    headers=headers(), json={'name': fname, 'type': ftype}
                )
                if r.status_code == 200:
                    print(f'  Added field "{fname}"')
                    new_field = r.json()
                    fid[fname] = f'field_{new_field["id"]}'

        # Add blacklisted firms (skip if already there) — read with user_field_names, write with field_id
        r = requests.get(
            f'{URL}/api/database/rows/table/{table_id}/?user_field_names=true',
            headers=headers()
        )
        # Primary field could be named "Name" or "Firm Name" depending on Baserow version
        primary_name = next(f['name'] for f in fields if f.get('primary'))
        existing_rows = {(row.get(primary_name) or '').strip() for row in r.json().get('results', [])}

        import datetime
        today = datetime.date.today().isoformat()
        added = 0
        for _, clean_name, reason in BLACKLISTED_FIRMS:
            if clean_name in existing_rows:
                print(f'  SKIP "{clean_name}" already in blacklist')
                continue
            payload = {primary_fid: clean_name}
            if 'Reason' in fid:    payload[fid['Reason']]     = reason
            if 'Date Added' in fid: payload[fid['Date Added']] = today
            r = requests.post(
                f'{URL}/api/database/rows/table/{table_id}/',
                headers=headers(), json=payload
            )
            if r.status_code == 200:
                print(f'  Added "{clean_name}" to blacklist')
                added += 1
            else:
                print(f'  WARN: {r.status_code} {r.text[:150]}')
        print(f'  Firms added to blacklist: {added}')

    # Clean up Law Firms table: remove "(BLACK LIST)" suffix, set Classification=Blacklisted
    print(f'\n  Cleaning up Law Firms table (removing BLACK LIST suffix)...')
    law_firm_rows = fetch_all_rows(LAW_FIRMS_TABLE)
    id_to_row = {r['id']: r for r in law_firm_rows}

    # Get Classification field options
    r2 = requests.get(f'{URL}/api/database/fields/table/{LAW_FIRMS_TABLE}/', headers=headers())
    r2.raise_for_status()
    blacklisted_option_id = None
    for field in r2.json():
        if field['name'] == 'Classification' and field['type'] == 'single_select':
            for opt in field.get('select_options', []):
                if opt['value'] == 'Blacklisted':
                    blacklisted_option_id = opt['id']

    for row_id, clean_name, _ in BLACKLISTED_FIRMS:
        if row_id not in id_to_row:
            print(f'  SKIP row {row_id} not found')
            continue
        current = (id_to_row[row_id].get('Law Firm Name') or '').strip()
        patch = {'Law Firm Name': clean_name}
        if blacklisted_option_id:
            patch['Classification'] = blacklisted_option_id
        if dry_run:
            print(f'  [DRY-RUN] RENAME [{row_id}] "{current}" -> "{clean_name}" + Classification=Blacklisted')
        else:
            r3 = requests.patch(
                f'{URL}/api/database/rows/table/{LAW_FIRMS_TABLE}/{row_id}/?user_field_names=false',
                headers=headers(), json=patch
            )
            # Use field_id based update for classification
            field_map = {f['name']: f'field_{f["id"]}' for f in r2.json()}
            patch2 = {'Law Firm Name': clean_name}
            if blacklisted_option_id and 'Classification' in field_map:
                patch2[field_map['Classification']] = blacklisted_option_id
            r3 = requests.patch(
                f'{URL}/api/database/rows/table/{LAW_FIRMS_TABLE}/{row_id}/',
                headers=headers(), json=patch2
            )
            if r3.status_code == 200:
                print(f'  RENAMED [{row_id}] "{current}" -> "{clean_name}" + Classification=Blacklisted')
            else:
                print(f'  WARN: {r3.status_code} {r3.text[:150]}')


# ─── Step 3: Add unknown firms from billing ───────────────────────

# Canonical firm names to add to Law Firms (768).
# Sourced from billing Settlement & Finance rows with no match in Law Firms.
# Already deduplicated and cleaned.
NEW_LAW_FIRMS = [
    'Aaron Brown',
    'Aghabilaw ACP',
    'Andrew L. Treger, Esq.',
    'Antonio Gallo',
    'Barrington Legal',
    'Bruce M. Kaufman',
    'Budget Legal Inc',
    'Fiore Legal',
    'Feller & Wendt LLC',
    'First Pacific Law',
    'George Khechuman',
    'Golden Gate Legal LLP',
    'Guldijan Fasel Accident Attorneys',
    'Harlan B. Kistler',
    'Hartounian, APLC',
    'Influential Law, APC',
    'Jerome Konell',
    'Jimmy Nguyen Attorney at Law, APC',
    'John P. Rosenberg PLC',
    'Kalfayan Merjanian',
    'Law At Your Side',
    'Law Brothers',
    'Law Office of Andre Ghariban',
    'Law Office of Brent A. Duque, PLC',
    'Law Office of David M Ward',
    'Law Office of Devin Wang',
    'Law Office of Earnest MacMillen',
    'Law Office of Eric Palacios',
    'Law Office of Estivi Ruiz',
    'Law Office of Lior Sadgan',
    'Law Office of Mario De La Rosa',
    'Law Office of Payam Y Poursalimi',
    'Law Office of Randolph Roger Ramirez',
    'Law Office of Robert Vosburg',
    'Law Office of Timothy Denton',
    'Law Office of Vincent J Quigg',
    'Law Office of William J. Toppi',
    'Law Office of Yohan Lee',
    'Law Offices of Arno Mehrabi',
    'Law Offices of Bob B. Khakshooy',
    'Law Offices of Chudacoff Friedman',
    'Law Offices of Deon S. Goldschmidt',
    'Law Offices of Erik K Chen',
    'Law Offices of Esllamboly Hakim',
    'Law Offices of Howard Kornberg',
    'Law Offices of John P. Strouss III',
    'Law Offices of Kamyar Shayan',
    'Law Offices of Martha Dahdah',
    'Law Offices of Shaffer and Gonor',
    'Law Offices of Todd J. Hilts',
    'Lawyer Vince',
    'Lee & Kim',
    'Lenze Moss PLC',
    'Mikhail Law',
    'Moaddel Kremer & Gerome LLP',
    'Morgan & Morgan',
    'Mulvaney Law',
    'Crumity, APC',
    'Prussak Welch & Avila, APC',
    'Samini Block APC',
    'Shah Sheth LLP',
    'Stephan Filip PC',
    'Sweet James',
    'The Law Collective',
    'The Law Office of Arash Khorsandi, PC',
    'The Law Office of Pablo G. Pinasco',
    'The Law Offices of Robert S Fink',
    'The Law Offices of Sara B. Poster',
    'The Lewis Farmer Group',
    'Zuriel A. Cervantes',
]


def step3_add_unknown_firms(dry_run=False):
    print('\n' + '='*60)
    print('STEP 3: Add Unknown Firms to Law Firms Directory')
    print('='*60)

    # Load existing firm names (case-insensitive)
    existing_rows = fetch_all_rows(LAW_FIRMS_TABLE)
    existing_names = {r.get('Law Firm Name', '').strip().lower() for r in existing_rows}
    print(f'  Existing firms: {len(existing_names)}')

    to_add = []
    for name in NEW_LAW_FIRMS:
        if name.lower() in existing_names:
            print(f'  SKIP (exists): "{name}"')
        else:
            to_add.append(name)

    print(f'  New firms to add: {len(to_add)}')
    if not to_add:
        return 0

    # Get Classification field map for "Existing" option
    r = requests.get(f'{URL}/api/database/fields/table/{LAW_FIRMS_TABLE}/', headers=headers())
    r.raise_for_status()
    existing_option_id = None
    field_map = {}
    for field in r.json():
        field_map[field['name']] = f'field_{field["id"]}'
        if field['name'] == 'Classification' and field['type'] == 'single_select':
            for opt in field.get('select_options', []):
                if opt['value'] == 'Existing':
                    existing_option_id = opt['id']

    items = []
    for name in to_add:
        item = {field_map['Law Firm Name']: name, field_map['Active']: False}
        if existing_option_id and 'Classification' in field_map:
            item[field_map['Classification']] = existing_option_id
        items.append(item)

    if dry_run:
        for name in to_add:
            print(f'  [DRY-RUN] ADD "{name}"')
        return len(to_add)

    added = 0
    batch_size = 50
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        r = requests.post(
            f'{URL}/api/database/rows/table/{LAW_FIRMS_TABLE}/batch/',
            headers=headers(), json={'items': batch}
        )
        if r.status_code == 200:
            added += len(batch)
            print(f'  Added {added}/{len(items)} firms...')
        else:
            print(f'  ERROR batch {i}: {r.status_code} {r.text[:200]}')

    print(f'  Done. Added {added} new firms.')
    return added


# ─── Step 4: Normalize billing firm names ─────────────────────────

SETTLEMENT_TABLE = 781

# Verified safe mappings: billing raw value -> canonical Law Firm Name.
# FALSE POSITIVES deliberately excluded (generic suffix matches like
# "X Law Group" -> "Y Law Group" where X != Y).
# Multi-firm slash entries are handled separately (skipped).
BILLING_FIRM_MAP = {
    # ── Noisy entries: embedded notes/phones/emails stripped ──────
    'Arash Law (low settlement) $40 PPV':                        'Arash Law',
    'Arash Law (patient was TOS)':                               'Arash Law',
    'Aratta Law Firm (818) 550-1111 legalchoicela@gmail.com>':   'Aratta Law Firm',
    'Avrek Law Firm (case closed 3/2020) 8/18/22 MR':            'Avrek Law Firm',
    'B&D Injury Law Group APLC disbursements@bdinjurylawgroup.com call in 1 mo in negotiations': 'B&D Injury Law Group APLC',
    'BD & J PC  per Adolfo dropped on 11/21/22; recvd drop letter 2/29/24': 'BD&J PC',
    'BD&J Injury Lawyers 310-887-1818 lvm 9/26/25 Miriam on leave': 'BD&J PC',
    "Barm Law (833) 227-6529 flores.barmlaw2009@gmail.com":       'Barm Law',
    'Barm Law mailed Superbill 7/9/24':                          'Barm Law',
    "Dayan Houman Law  jillc@dhlawca.com  minor's comp  1-800-961-9172": 'Dayan Houman',
    'Eashoo Law reyna@eashoolaw.com':                            'Eashoo Law',
    'Eldessouky Law (David 3/3/23)':                             'Eldessouky Law',
    'JT Legal  6/7/2022 (dismissed due to lack of coverage)':    'JT Legal Group',
    'Jacoby & Meyers Injury Lawyers (paid by Nationwide Insurance)': 'Jacoby & Meyers',
    'Larry H Parker (workers comp case opened and records subpoenaed)': 'Larry H. Parker',
    'Law Offices of Patrick Aguirre  katherine@paguirrelaw.com submitting demand; pending': 'Patrick S Aguirre',
    'Law Offices of Oscar Sandoval deceased (no executor)':       'Law Offices of Oscar Sandoval',
    'Law Offices of Thomas Pierry  (per Eleen case is in litigation 5-1-2024)': 'Law Offices of Thomas Pierry',
    'My Injury Headquarters (Faraz Mobassern)':                  'My Injury Headquarters',
    'Nelson & Natale (Claudia 3/3/23)':                          'Nelson & Natale',
    'Omega Law Firm, PC ... do not send anything, part of shady lawyer BS (may have transferd to JLF)-JD': 'Omega Law Firm, PC',
    'Omega Law Firm, PC...... do not send anything, part of shady lawyer BS (may have transferd to JLF)-JD': 'Omega Law Firm, PC',
    'Orloff & Associates pending':                               'Orloff & Associates',
    'The JLF Firm  (waived by Dr. Sanchez) Luis Davila 1/3/22':  'The JLF Firm',
    'The JLF Firm  discovery (take loss per Dr. Sanchez)':       'The JLF Firm',
    'The JLF Firm  drop letter recvd 4/9/24':                    'The JLF Firm',
    'The JLF Firm (waived by Dr. Sanchez)':                      'The JLF Firm',
    'The JLF Firm - 2/28/23':                                    'The JLF Firm',
    'The JLF Firm - Dropped (pt has 2 cases)':                   'The JLF Firm',
    'The JLF Firm - no record 2/28/23':                          'The JLF Firm',
    'The JLF Firm Superbill to be paid in full this time':       'The JLF Firm',
    'The JLF Firm; recieved drop letter 5.3.24':                 'The JLF Firm',
    'The Law Offices of Gerald L. Marcus, Injury & Accident Attorneys ryan@injury': 'The Law Offices of Gerald L. Marcus, Injury & Accident Attorneys',
    'Trillium Law.... ... do not send anything, part of shady lawyer BS-JD records given to patient on 2.16.2023': 'Trillium Law',

    # ── DROPPED/status prefix stripped ────────────────────────────
    'DROPPED - Dayan Houman Law':                                'Dayan Houman',
    'DROPPED - Lem Garcia Law':                                  'Lem Garcia Law',
    'DROPPED - The Law Offices of Daniel Kim':                   'Law Office of Daniel Kim',
    'DROPPED -The JLF Firm':                                     'The JLF Firm',
    'Droped- Dayan Houman Law':                                  'Dayan Houman',
    'DROPPED - Fiore Legal':                                     'Fiore Legal',

    # ── Clear name variants ────────────────────────────────────────
    'Adrian Law Firm':                                           'The Adrian Law Firm',
    'Adrian Law Firm  APC':                                      'The Adrian Law Firm',
    'Ariel Mossadeh':                                            'Ariel Mossadeh (Mirage Law Group)',
    'B&D Injury Law Group':                                      'B&D Injury Law Group APLC',
    'BD&J Injury Lawyers':                                       'BD&J PC',
    'BD&J Law, PC':                                              'BD&J PC',
    'C&B Law Group':                                             'C&B Law Group LLP',
    'Carpenter & Zuckerman':                                     'Carpenter & Zuckerman Law',
    'Daniel L. Nelson':                                          'Law Office of Daniel L. Nelson & Associates',
    'Dayan Houman Law':                                          'Dayan Houman',
    'Dayan Houman Law - patient deceased':                       'Dayan Houman',
    'Dayan Houman Law Firm':                                     'Dayan Houman',
    'Dixon & Daley':                                             'Dixon & Daley, LLP',
    'Ellis Law':                                                 'Ellis Law Corporation',
    'George Shalboub Bryan dropped 3/19/2019':                  'Law Offices of George J. Shalboub',
    'H.A. Jacskon':                                              'H.A. Jackson',
    'H.Y.P Law Group':                                           'HYP Law Group',
    'Harris Personal Injury Lawyers':                            'Harris Personal Injury Law',
    'Harris Personal Injury Lawyers, Inc.':                      'Harris Personal Injury Law',
    'Hillstone Law Accident & Injury Attorneys':                 'Hillstone Law, PC',
    'Hillstone Law Accident & Injury Attorneys mara@hstonelaw.com': 'Hillstone Law, PC',
    'JT Legal':                                                  'JT Legal Group',
    'Jacoby & Meyers Injury Lawyers':                            'Jacoby & Meyers',
    'Jacoby & Meyers Injury Lawyers & Larry H. Parker':          'Jacoby & Meyers',
    'Javaherian & Ruszecki':                                     'Javaherian & Ruszecki PC',
    'Jonathan J. Moon':                                          'The Law Office of Jonathan J Moon',
    'Karns & Karns Law':                                         'Karns & Karns',
    'Khechumyan Law':                                            'Khechumyan Law Offices',
    'Khechumyan Law, A.P.C.':                                    'Khechumyan Law Offices',
    'Konell Ruggiero LLP':                                       'Konnell Ruggiero  LLP',
    'Konnell Ruggiero LLP':                                      'Konnell Ruggiero  LLP',
    'Larry H Parker':                                            'Larry H. Parker',
    'Larry H parker':                                            'Larry H. Parker',
    'Law Office of  Jacob Emrani & ME Lawyers':                  'Jacob Emrani',
    'Law Office of Jacob Emrani & ME Lawyers':                   'Jacob Emrani',
    'Law Office of Daniel F. Jimenez':                           'Law Offices of Daniel F. Jimenez',
    'Law Office of Howard B. Kim':                               'Law Offices of Howard B. Kim',
    'Law Office of Joseph Poursholimyo':                         'Law Office of Joseph Poursholimy',
    'Law Office of Joseph Rosenblit':                            'The Law Office of Joseph C. Rosenblit',
    'Law Office of Kaveh Keshmiri':                              'Kaveh Keshmiri',
    "Law Office of Kerry 'O Brien":                              "Law Office of Kerry O'Brien",
    "Law Office of Kerry O Brien":                               "Law Office of Kerry O'Brien",
    "Law Office of Kerry P O'Brien":                             "Law Office of Kerry O'Brien",
    'Law Office of Miguel Duarte':                               'Law Offices of Miguel Duarte',
    'Law Office of Oscar D. Sandoval':                           'Law Offices of Oscar Sandoval',
    'Law Office of Peter Shah':                                  'Law Offices of Peter Shah',
    'Law Office of Samer Habbas & Associates':                   'Law Offices of Samer Habbas & Associates',
    'Law Office of Sammer Habbas':                               'Law Offices of Samer Habbas & Associates',
    'Law Office of William Green':                               'Law Offices of William Green',
    'Law Offices of Andy Van Le, Esq':                           'Andy Van Le & Associates',
    'Law Offices of Daniel KIm':                                 'Law Office of Daniel Kim',
    'Law Offices of HA Jackson':                                 'H.A. Jackson',
    'Law Offices of Jake D. Finkel':                             'Law Offices of Jake D Finkle',
    'Law Offices of Orloff & Associates APC':                    'Orloff & Associates',
    'Law Offices of Patrick Aguirre':                            'Patrick S Aguirre',
    'Law Offices of Samer Habbas':                               'Law Offices of Samer Habbas & Associates',
    'Lem Garcia':                                                'Lem Garcia Law',
    'Lem Garcia  626-777-2211':                                  'Lem Garcia Law',
    'Lem Garcia Firm':                                           'Lem Garcia Law',
    'McGee Lerer & Associates':                                  'McGee Lerer Ogrin',
    'McGee, Lerer & Associates':                                 'McGee Lerer Ogrin',
    'McNicholas & McNicholas, LLP.':                             'McNicholas & McNicholas, LLP',
    'Nelson & Natale, LLP':                                      'Nelson & Natale',
    "Nelson & Natalie, LLP":                                     'Nelson & Natale',
    'Oscar Sandoval':                                            'Law Offices of Oscar Sandoval',
    'Perez & Caballero APC':                                     'Perez and Caballero APC',
    'RMD Law':                                                   'RMD Law LLP',
    'RMD Law - Personal Injury Lawyers':                         'RMD Law LLP',
    'Raymond Perez':                                             'Law Offices Of Raymond Perez',
    'Raymond Perez, Esq.':                                       'Law Offices Of Raymond Perez',
    'Scott McDonald':                                            'Scott McDonald-McDonald Law Firm',
    'Sinarez Law':                                               'Sina Rez Law',
    'SoCal Attorney':                                            'SOCAL Attorneys',
    'Stoll, Nussbaum & Pokakov':                                 'Law Office of Stoll, Nussbaum and Polakov',
    'The Arash Law Firm':                                        'Arash Law',
    'The Dominguez Firm LLP':                                    'The Dominguez Firm',
    'The Dominguez Law Firm':                                    'The Dominguez Firm',
    'The JLF FIrm':                                              'The JLF Firm',
    'The JLF firm':                                              'The JLF Firm',
    'The JlF Firm':                                              'The JLF Firm',
    'The Jlf Firm':                                              'The JLF Firm',
    'The JLF Firm - Dropped':                                    'The JLF Firm',
    'The JLF Firm - Non-Compliant':                              'The JLF Firm',
    'The Law Office of Daniel F Jimenez':                        'Law Offices of Daniel F. Jimenez',
    'The Law Office of Jonathan J. Moon':                        'The Law Office of Jonathan J Moon',
    'The Law Office of Oscar D. Sandoval':                       'Law Offices of Oscar Sandoval',
    'The Law Offices of Daniel Kim':                             'Law Office of Daniel Kim',
    'The Law Offices of Daniel Kim (dropped 11/2020)':           'Law Office of Daniel Kim',
    'The Law Offices of Daniel Kim (dropped 2020)':              'Law Office of Daniel Kim',
    'The Law Offices of Gavril Gabriel':                         'Law Offices of Gavril T. Gabriel',
    'The Law Offices of Gavril T. Gabriel':                      'Law Offices of Gavril T. Gabriel',
    'The Law Offices of Jacob Emrani':                           'Jacob Emrani',
    'The Law Offices of Oscar D. Sandoval':                      'Law Offices of Oscar Sandoval',
    'The Law Offices of Raymond Perez':                          'Law Offices Of Raymond Perez',
    'Timothy J. Ryan & Associatees':                             'Timothy J Ryan & Associates',
    'Top Notch Law Group':                                       'Top Notch Law Group',
    'Trillium Law':                                              'Trillium Law',
    'Uvalle Law Firm-The Law Boss':                              'Uvalle Law Firm/The Law Boss',
    'Workman Law':                                               'Workman Law & Litigation, PC',
    'YMPK Law Group':                                            'YMPK Law Group, LLP',
    'Yagoubzadeh Law':                                           'Yagoubzadeh Law Firm',
    'Yagoubzadh Law Firm':                                       'Yagoubzadeh Law Firm',
    'Yerushami Law':                                             'YERUSHALMI LAW FIRM',
    'Yerushami Law Firm':                                        'YERUSHALMI LAW FIRM',
    'Yerushalmi Law Firm':                                       'YERUSHALMI LAW FIRM',
    'Adamson Ahdoot':                                            'Adamson Ahaoot LLP',

    # ── New firms (added in Step 3) ───────────────────────────────
    'DROPPED - Fiore Legal':                                     'Fiore Legal',
    'Jimmy Nguyen  (949) 438-1714':                              'Jimmy Nguyen Attorney at Law, APC',
    'Jimmy Nguyen Attorney at Law, APC':                         'Jimmy Nguyen Attorney at Law, APC',
    'Jimmy Nguyen, Attorney at Law, APC':                        'Jimmy Nguyen Attorney at Law, APC',
    'Guldijan Fasel':                                            'Guldijan Fasel Accident Attorneys',
    'Guldijian Fasel Accident Attorneys':                        'Guldijan Fasel Accident Attorneys',
    'Guldijan Fasel Accident Attorneys':                         'Guldijan Fasel Accident Attorneys',
    'Kalfaayan Merjanian, LLP':                                  'Kalfayan Merjanian',
    'Hartounian APLC':                                           'Hartounian, APLC',
    'Morgan & Morgan diana.khosrovyan@forthepeople.com':         'Morgan & Morgan',
    'Samini Block':                                              'Samini Block APC',
    'Stephan Philip PC':                                         'Stephan Filip PC',
    'The Law Office of Arash Khorsandi PC':                      'The Law Office of Arash Khorsandi, PC',
    'The Law Office of Arash Khorsandi, Pc':                     'The Law Office of Arash Khorsandi, PC',
    'The Law Office of Pablo G Pinasco 213-699-4878':            'The Law Office of Pablo G. Pinasco',
    'Law Offices of John P. Strouss III 800-484-5161':           'Law Offices of John P. Strouss III',
    'Law office of Martha Dahdah':                               'Law Offices of Martha Dahdah',
}


def step4_normalize_billing_names(dry_run=False):
    print('\n' + '='*60)
    print('STEP 4: Normalize Law Firm Names in Settlement & Finance')
    print('='*60)

    rows = fetch_all_rows(SETTLEMENT_TABLE)
    print(f'  Loaded {len(rows)} rows from Settlement & Finance\n')

    batch = []
    skipped_multi = 0
    already_correct = 0
    no_map = 0

    for row in rows:
        raw = (row.get('Law Firm Name') or '').strip()
        if not raw:
            continue

        # Skip multi-firm slash entries
        if '/' in raw:
            skipped_multi += 1
            continue

        canonical = BILLING_FIRM_MAP.get(raw)
        if canonical is None:
            no_map += 1
            continue

        if raw == canonical:
            already_correct += 1
            continue

        batch.append({'id': row['id'], 'Law Firm Name': canonical})
        if dry_run:
            print(f'  [{row["id"]}] "{raw}"\n       -> "{canonical}"')

    print(f'  Rows to update:      {len(batch)}')
    print(f'  Skipped (multi-firm): {skipped_multi}')
    print(f'  Already correct:     {already_correct}')
    print(f'  No mapping found:    {no_map}')

    if not batch or dry_run:
        return len(batch)

    # Batch update in chunks of 200
    updated = 0
    chunk = 200
    for i in range(0, len(batch), chunk):
        items = batch[i:i+chunk]
        r = requests.patch(
            f'{URL}/api/database/rows/table/{SETTLEMENT_TABLE}/batch/?user_field_names=true',
            headers=headers(), json={'items': items}
        )
        if r.status_code == 200:
            updated += len(items)
            print(f'  Updated {updated}/{len(batch)} rows...')
        else:
            print(f'  ERROR chunk {i}: {r.status_code} {r.text[:200]}')

    print(f'  Done. {updated} rows updated.')
    return updated


# ─── Step 5: Normalize Law Firm Names in Closed Cases ─────────────

CLOSED_CASES_TABLE = 772

# All Dayan Houman variants → new canonical name per owner instruction
# All JLF typos, Kerry O'Brien variants, etc.
CLOSED_CASES_FIRM_MAP = {
    # ── Dayan Houman → new canonical ──────────────────────────────
    'Dayan Houman':                                              'Dayan Houman Professional Law Corporation',
    'Dayan Houman Law':                                          'Dayan Houman Professional Law Corporation',
    'Dayan Houman Law Firm':                                     'Dayan Houman Professional Law Corporation',
    "Dayan Houman Law  jillc@dhlawca.com  minor's comp  1-800-961-9172": 'Dayan Houman Professional Law Corporation',
    'Dayan Houman Law - patient deceased':                       'Dayan Houman Professional Law Corporation',
    'DROPPED - Dayan Houman Law':                                'Dayan Houman Professional Law Corporation',
    'Droped- Dayan Houman Law':                                  'Dayan Houman Professional Law Corporation',

    # ── JLF Firm typos ────────────────────────────────────────────
    'The JLF FIrm':                                              'The JLF Firm',
    'The JLF firm':                                              'The JLF Firm',
    'The JlF Firm':                                              'The JLF Firm',
    'The Jlf Firm':                                              'The JLF Firm',
    'The JLF Firm - Dropped':                                    'The JLF Firm',
    'The JLF Firm - Non-Compliant':                              'The JLF Firm',

    # ── Jacoby & Meyers ───────────────────────────────────────────
    'Jacoby & Meyers Injury Lawyers (paid by Nationwide Insurance)': 'Jacoby & Meyers Injury Lawyers',

    # ── Jacob Emrani (double space / "The Law Offices of" variants) ──
    'Law Office of  Jacob Emrani & ME Lawyers':                  'Law Office of Jacob Emrani & ME Lawyers',
    'The Law Offices of Jacob Emrani':                           'Law Office of Jacob Emrani & ME Lawyers',

    # ── Oscar Sandoval ────────────────────────────────────────────
    'Law Office of Oscar D. Sandoval':                           'Law Offices of Oscar Sandoval',
    'The Law Office of Oscar D. Sandoval':                       'Law Offices of Oscar Sandoval',
    'Law Offices of Oscar Sandoval deceased (no executor)':      'Law Offices of Oscar Sandoval',
    'Oscar Sandoval':                                            'Law Offices of Oscar Sandoval',

    # ── Gerald Marcus (email appended) ────────────────────────────
    'The Law Offices of Gerald L. Marcus, Injury & Accident Attorneys ryan@injury': 'The Law Offices of Gerald L. Marcus, Injury & Accident Attorneys',

    # ── Jimmy Nguyen ──────────────────────────────────────────────
    'Jimmy Nguyen Attorney at Law, APC':                         'Jimmy Nguyen, Attorney at Law, APC',

    # ── Samer Habbas ──────────────────────────────────────────────
    'Law Office of Samer Habbas & Associates':                   'Law Offices of Samer Habbas & Associates',
    'Law Office of Sammer Habbas':                               'Law Offices of Samer Habbas & Associates',
    'Law Offices of Samer Habbas':                               'Law Offices of Samer Habbas & Associates',

    # ── Konnell Ruggiero (typo) ───────────────────────────────────
    'Konell Ruggiero LLP':                                       'Konnell Ruggiero LLP',

    # ── Hartounian ────────────────────────────────────────────────
    'Hartounian APLC':                                           'Hartounian, APLC',

    # ── Larry H. Parker ───────────────────────────────────────────
    'Larry H Parker':                                            'Larry H. Parker',
    'Larry H Parker (workers comp case opened and records subpoenaed)': 'Larry H. Parker',

    # ── Kerry O'Brien ─────────────────────────────────────────────
    "Law Office of Kerry 'O Brien":                              "Law Office of Kerry O'Brien",
    "Law Office of Kerry O Brien":                               "Law Office of Kerry O'Brien",
    "Law Office of Kerry P O'Brien":                             "Law Office of Kerry O'Brien",

    # ── Timothy Ryan (typo) ───────────────────────────────────────
    'Timothy J. Ryan & Associatees':                             'Timothy J Ryan & Associates',

    # ── Daniel Kim (capitalization) ───────────────────────────────
    'Law Offices of Daniel KIm':                                 'The Law Offices of Daniel Kim',

    # ── Devin Wang ────────────────────────────────────────────────
    'Law Office of Devin Wang':                                  'Law Offices of Devin V. Wang',
    'Devin Wang Law Offices':                                    'Law Offices of Devin V. Wang',

    # ── Power Legal Group ─────────────────────────────────────────
    'Power Legal Group':                                         'Power Legal Group, PC',

    # ── Gilbert & Stern ───────────────────────────────────────────
    'Gilbert & Stern':                                           'Gilbert & Stern LLP',

    # ── Harris Personal Injury ────────────────────────────────────
    'Harris Personal Injury Lawyers':                            'Harris Personal Injury Law',

    # ── Arash Law (notes appended) ────────────────────────────────
    'Arash Law (low settlement) $40 PPV':                        'Arash Law',
    'Arash Law (patient was TOS)':                               'Arash Law',

    # ── H.A. Jackson (typo) ───────────────────────────────────────
    'H.A. Jacskon':                                              'H.A. Jackson',

    # ── Khechumyan ────────────────────────────────────────────────
    'Khechumyan Law':                                            'Khechumyan Law Offices',
    'Khechumyan Law, A.P.C.':                                    'Khechumyan Law Offices',

    # ── Hillstone Law ─────────────────────────────────────────────
    'Hillstone Law Accident & Injury Attorneys':                 'Hillstone Law, PC',

    # ── JT Legal ──────────────────────────────────────────────────
    'JT Legal':                                                  'JT Legal Group',

    # ── McGee Lerer ───────────────────────────────────────────────
    'McGee Lerer & Associates':                                  'McGee Lerer Ogrin',
    'McGee, Lerer & Associates':                                 'McGee Lerer Ogrin',

    # ── Nelson & Natale ───────────────────────────────────────────
    "Nelson & Natalie, LLP":                                     'Nelson & Natale',

    # ── My Injury Headquarters ────────────────────────────────────
    'My Injury Headquarters (Faraz Mobassern)':                  'My Injury Headquarters',

    # ── Guldijan Fasel ────────────────────────────────────────────
    'Guldian Fasel Accident Attorneys':                          'Guldijan Fasel Accident Attorneys',
    'Guldijian Fasel Accident Attorneys':                        'Guldijan Fasel Accident Attorneys',

    # ── Yagoubzadeh ───────────────────────────────────────────────
    'Yagoubzadeh Law':                                           'Yagoubzadeh Law Firm',
    'Yagoubzadh Law Firm':                                       'Yagoubzadeh Law Firm',

    # ── Yerushalmi ────────────────────────────────────────────────
    'Yerushami Law':                                             'YERUSHALMI LAW FIRM',
    'Yerushami Law Firm':                                        'YERUSHALMI LAW FIRM',
    'Yerushalmi Law Firm':                                       'YERUSHALMI LAW FIRM',

    # ── Adamson Ahdoot (real spelling) ────────────────────────────
    'Adamson Ahdoot':                                            'Adamson Ahdoot LLP',

    # ── Crumity APC (note prefix stripped) ───────────────────────
    'Nathalie D. Lopez with Crumity, APC.':                      'Crumity, APC',

    # ── Ceja Firm ─────────────────────────────────────────────────
    'Ceja Law Office':                                           'The Ceja Firm',

    # ── Kalfayan ──────────────────────────────────────────────────
    'Kalfaayan Merjanian, LLP':                                  'Kalfayan Merjanian',

    # ── Samini Block ──────────────────────────────────────────────
    'Samini Block':                                              'Samini Block APC',

    # ── Stephan Filip (typo) ──────────────────────────────────────
    'Stephan Philip PC':                                         'Stephan Filip PC',

    # ── Daniel F. Jimenez ─────────────────────────────────────────
    'Law Office of Daniel F. Jimenez':                           'Law Offices of Daniel F. Jimenez',

    # ── BD&J ──────────────────────────────────────────────────────
    'BD&J Injury Lawyers':                                       'BD&J PC',

    # ── AH Law Group ──────────────────────────────────────────────
    'AH Law Group':                                              'AH Law Group, APC',
}


def step5_normalize_closed_cases_firms(dry_run=False):
    print('\n' + '='*60)
    print('STEP 5: Normalize Law Firm Names in Closed Cases (table 772)')
    print('='*60)

    rows = fetch_all_rows(CLOSED_CASES_TABLE)
    print(f'  Loaded {len(rows)} rows from Closed Cases\n')

    batch = []
    skipped_multi = 0
    already_correct = 0
    no_map = 0

    for row in rows:
        raw = (row.get('Law Firm Name') or '').strip()
        if not raw:
            continue
        if '/' in raw:
            skipped_multi += 1
            continue

        canonical = CLOSED_CASES_FIRM_MAP.get(raw)
        if canonical is None:
            no_map += 1
            continue
        if raw == canonical:
            already_correct += 1
            continue

        batch.append({'id': row['id'], 'Law Firm Name': canonical})
        if dry_run:
            print(f'  [{row["id"]}] "{raw}"\n       -> "{canonical}"')

    print(f'  Rows to update:       {len(batch)}')
    print(f'  Skipped (multi-firm): {skipped_multi}')
    print(f'  Already correct:      {already_correct}')
    print(f'  No mapping found:     {no_map}')

    if not batch or dry_run:
        return len(batch)

    updated = 0
    chunk = 200
    for i in range(0, len(batch), chunk):
        items = batch[i:i+chunk]
        r = requests.patch(
            f'{URL}/api/database/rows/table/{CLOSED_CASES_TABLE}/batch/?user_field_names=true',
            headers=headers(), json={'items': items}
        )
        if r.status_code == 200:
            updated += len(items)
            print(f'  Updated {updated}/{len(batch)} rows...')
        else:
            print(f'  ERROR chunk {i}: {r.status_code} {r.text[:200]}')

    print(f'  Done. {updated} rows updated.')
    return updated


# ─── Step 6: Delete duplicate Case Labels ─────────────────────────

# Comparison fields for deciding which row to keep.
# We keep the row with more data. If truly identical, keep lower ID.
COMPARE_FIELDS = [
    'Status', 'DOI', 'Start Date', 'Case Manager', 'Law Firm Name',
    'Notes', 'Case Notes', '# of Visits', 'Last Visit Date', 'Date Dropped',
]


def _data_score(row):
    """Count non-empty field values — higher = more complete record."""
    return sum(1 for f in COMPARE_FIELDS if (row.get(f) or '').strip())


def step6_delete_duplicate_case_labels(dry_run=False):
    print('\n' + '='*60)
    print('STEP 6: Delete Duplicate Case Labels in Closed Cases (table 772)')
    print('='*60)

    rows = fetch_all_rows(CLOSED_CASES_TABLE)
    id_to_row = {r['id']: r for r in rows}
    print(f'  Loaded {len(rows)} rows\n')

    from collections import defaultdict
    label_groups = defaultdict(list)
    for row in rows:
        label = (row.get('Case Label') or '').strip()
        if label:
            label_groups[label].append(row['id'])

    dupes = [(label, sorted(ids)) for label, ids in label_groups.items() if len(ids) > 1]
    print(f'  Duplicate Case Label groups: {len(dupes)}')

    to_delete = []
    needs_review = []

    for label, ids in dupes:
        group_rows = [id_to_row[i] for i in ids]

        # Check if all rows are identical across compare fields
        def rows_match(a, b):
            for f in COMPARE_FIELDS:
                va = (a.get(f) or '').strip()
                vb = (b.get(f) or '').strip()
                if va != vb:
                    return False
            return True

        all_identical = all(rows_match(group_rows[0], group_rows[j]) for j in range(1, len(group_rows)))

        if all_identical:
            # Keep lowest ID, delete the rest
            keep_id = ids[0]
            delete_ids = ids[1:]
            to_delete.extend(delete_ids)
            if dry_run:
                print(f'  DELETE {delete_ids}  (keep {keep_id})  "{label}"')
        else:
            # Rows differ — keep the one with more data, flag for awareness
            best = max(group_rows, key=_data_score)
            delete_ids = [r['id'] for r in group_rows if r['id'] != best['id']]

            # Flag genuinely conflicting data (different dates or visit counts)
            diffs = []
            for f in ['DOI', 'Start Date', '# of Visits']:
                vals = list({(r.get(f) or '').strip() for r in group_rows} - {''})
                if len(vals) > 1:
                    diffs.append(f'{f}: {vals}')

            if diffs:
                needs_review.append((label, ids, diffs))
                print(f'  REVIEW  ids={ids}  "{label}" — conflicting: {", ".join(diffs)}')
            else:
                to_delete.extend(delete_ids)
                if dry_run:
                    print(f'  DELETE {delete_ids}  (keep {best["id"]}, most complete)  "{label}"')

    print(f'\n  Safe to delete:   {len(to_delete)} rows')
    print(f'  Needs review:     {len(needs_review)} groups')

    if needs_review:
        print('\n  Groups needing manual review (different DOI/dates/visits):')
        for label, ids, diffs in needs_review:
            print(f'    {ids}  "{label}"')
            for d in diffs:
                print(f'      {d}')

    if not to_delete or dry_run:
        return len(to_delete)

    # Batch delete in chunks of 200
    deleted = 0
    chunk = 200
    for i in range(0, len(to_delete), chunk):
        batch = to_delete[i:i+chunk]
        r = requests.post(
            f'{URL}/api/database/rows/table/{CLOSED_CASES_TABLE}/batch-delete/',
            headers=headers(), json={'items': batch}
        )
        if r.status_code in (200, 204):
            deleted += len(batch)
            print(f'  Deleted {deleted}/{len(to_delete)} rows...')
        else:
            print(f'  ERROR chunk {i}: {r.status_code} {r.text[:200]}')

    print(f'  Done. {deleted} duplicate rows deleted.')
    return deleted


# ─── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Baserow CRM Cleanup')
    parser.add_argument('--step', type=int, help='Run only a specific step')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    args = parser.parse_args()

    if args.dry_run:
        print('[DRY-RUN MODE - no changes will be written]\n')

    run_all = args.step is None

    if run_all or args.step == 1:
        step1_deduplicate_law_firms(dry_run=args.dry_run)

    if run_all or args.step == 2:
        step2_create_blacklist_table(dry_run=args.dry_run)

    if run_all or args.step == 3:
        step3_add_unknown_firms(dry_run=args.dry_run)

    if run_all or args.step == 4:
        step4_normalize_billing_names(dry_run=args.dry_run)

    if run_all or args.step == 5:
        step5_normalize_closed_cases_firms(dry_run=args.dry_run)

    if run_all or args.step == 6:
        step6_delete_duplicate_case_labels(dry_run=args.dry_run)

    print('\nDone.')


if __name__ == '__main__':
    main()
