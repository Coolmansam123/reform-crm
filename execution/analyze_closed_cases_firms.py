#!/usr/bin/env python3
"""
Analyze Law Firm Names in Closed Cases (table 772)
===================================================
Fetches all unique law firm name values from the Closed Cases table,
runs fuzzy matching to find near-duplicates, and prints a proposed
merge plan for human review.

Usage:
    python execution/analyze_closed_cases_firms.py
    python execution/analyze_closed_cases_firms.py --threshold 85
    python execution/analyze_closed_cases_firms.py --show-all     # show all unique names too
"""
import sys, os, argparse
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
from dotenv import load_dotenv

load_dotenv()
URL = os.getenv('BASEROW_URL')
EMAIL = os.getenv('BASEROW_EMAIL')
PASSWORD = os.getenv('BASEROW_PASSWORD')

CLOSED_CASES_TABLE = 772

# ─── Auth ──────────────────────────────────────────────────────────

import time
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

# ─── Fetch ─────────────────────────────────────────────────────────

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

# ─── Fuzzy match ───────────────────────────────────────────────────

def fuzzy_match(names, threshold=88):
    """
    Returns list of (score, name_a, name_b) pairs above threshold.
    Uses both token_sort_ratio (handles word reordering) and
    partial_ratio (handles substring matches), takes the max.
    Applies false-positive filters from the directive.
    """
    try:
        from rapidfuzz import fuzz
    except ImportError:
        try:
            from fuzzywuzzy import fuzz
        except ImportError:
            print("ERROR: Install rapidfuzz:  pip install rapidfuzz")
            sys.exit(1)

    # Generic suffixes that inflate scores across different firms
    GENERIC_SUFFIXES = [
        'law group', '& associates', 'injury law', 'law firm',
        'law corp', 'legal group', 'law office', 'law offices',
        'attorneys', 'accident attorneys', 'injury lawyers',
    ]

    def is_generic_suffix_match(a, b):
        """True if the only overlapping content is a generic suffix."""
        a_lower, b_lower = a.lower(), b.lower()
        for suffix in GENERIC_SUFFIXES:
            if a_lower.endswith(suffix) and b_lower.endswith(suffix):
                # Get the distinctive root (everything before the suffix)
                root_a = a_lower[: a_lower.rfind(suffix)].strip().rstrip(',').strip()
                root_b = b_lower[: b_lower.rfind(suffix)].strip().rstrip(',').strip()
                # If roots are different (not one containing the other), it's a false positive
                if root_a and root_b and root_a != root_b:
                    if root_a not in root_b and root_b not in root_a:
                        return True
        return False

    sorted_names = sorted(names)
    matches = []
    seen = set()

    for i, a in enumerate(sorted_names):
        for b in sorted_names[i+1:]:
            key = (a, b)
            if key in seen:
                continue
            seen.add(key)

            # Skip multi-firm slash entries
            if '/' in a or '/' in b:
                continue

            score_sort = fuzz.token_sort_ratio(a, b)
            score_partial = fuzz.partial_ratio(a, b)

            # For short names, don't rely on partial_ratio (false positive risk)
            a_tokens = len(a.split())
            b_tokens = len(b.split())
            if a_tokens < 4 or b_tokens < 4:
                score = score_sort
            else:
                score = max(score_sort, score_partial)

            if score < threshold:
                continue

            # Filter generic suffix false positives
            if is_generic_suffix_match(a, b):
                continue

            matches.append((score, a, b))

    return sorted(matches, key=lambda x: -x[0])


# ─── Main ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Analyze Closed Cases law firm names')
    parser.add_argument('--threshold', type=int, default=88,
                        help='Minimum fuzzy score to flag (default: 88)')
    parser.add_argument('--show-all', action='store_true',
                        help='Print all unique firm names before matches')
    args = parser.parse_args()

    print(f'Fetching Closed Cases rows (table {CLOSED_CASES_TABLE})...')
    rows = fetch_all_rows(CLOSED_CASES_TABLE)
    print(f'Loaded {len(rows)} rows\n')

    # Collect all unique non-empty law firm names
    name_counts = {}
    for row in rows:
        name = (row.get('Law Firm Name') or '').strip()
        if not name:
            continue
        # Skip multi-firm slash entries
        if '/' in name:
            continue
        name_counts[name] = name_counts.get(name, 0) + 1

    names = sorted(name_counts.keys())
    print(f'Unique law firm name values: {len(names)}')

    if args.show_all:
        print('\n── All unique names ──────────────────────────────────────')
        for n in names:
            print(f'  [{name_counts[n]:3d}x]  {n}')

    print(f'\n── Fuzzy matches (threshold >= {args.threshold}) ──────────────────')
    matches = fuzzy_match(names, threshold=args.threshold)

    if not matches:
        print('  No matches found at this threshold.')
    else:
        print(f'  Found {len(matches)} potential pairs:\n')
        for score, a, b in matches:
            count_a = name_counts[a]
            count_b = name_counts[b]
            print(f'  [{int(score):3d}]  "{a}" ({count_a}x)  <->  "{b}" ({count_b}x)')

    print(f'\nDone. Review the pairs above and decide which to merge.')
    print('Then add a CLOSED_CASES_MERGE_MAP to baserow_cleanup.py (Step 5).')


if __name__ == '__main__':
    main()
