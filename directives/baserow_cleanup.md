# Baserow CRM Cleanup

## Purpose
Clean and standardize data across all three Baserow CRM databases. This is a separate pipeline from the law firm scraper/mapper — it operates on existing Baserow data and does not require any external scraping inputs.

## Quick Reference

```
python execution/baserow_cleanup.py --step N --dry-run   # always dry-run first
python execution/baserow_cleanup.py --step N             # apply
python execution/baserow_cleanup.py                      # run all steps
```

| Step | What it does | Status |
|------|-------------|--------|
| 1 | Deduplicate Law Firm names (table 768) | ✅ Done (Feb 2026) |
| 2 | Create Blacklisted Law Firms table + clean "(BLACK LIST)" from names | ✅ Done (Feb 2026) |
| 3 | Add 70 unknown firms from billing to Law Firms directory | ✅ Done (Feb 2026) |
| 4 | Normalize Law Firm Names in Settlement & Finance (table 781) | ✅ Done (Feb 2026) |
| 5 | Normalize Law Firm Names in Closed Cases (table 772) | ✅ Done (Mar 2026) |
| 6 | Delete duplicate Case Labels in Closed Cases (table 772) | ✅ Done (Mar 2026) |

## Databases & Tables

| Database | App ID | Tables |
|----------|--------|--------|
| Law Firm Directory | 198 | Law Firms (768), Law Firm Contacts (769), Activities (784) |
| Patient & Case Management | 199 | Patients (770), Medical Records (771), Closed Cases (772), Tx Completed - Billed (773), Dropped (774), Active Cases (775), Awaiting (776), Subpoenas (777), Black List (778), Universal Law (779), Need Records (780) |
| Billing & Legal | 200 | Settlement & Finance (781), Billing (782) |

## Cleanup Steps

### Step 1: Deduplicate Law Firm Names (table 768) ✅ DONE
- **Problem**: Duplicate and near-duplicate firm names from data entry and scraping
- **Solution**: Fuzzy match similar names, pick canonical version, delete duplicates
- **Merge plan**: Hardcoded in `MERGE_PLAN` list in `execution/baserow_cleanup.py`
- **Result**: 241 → 220 rows, 21 duplicates removed (Feb 2026)
- **Key decisions**:
  - Exact duplicates (same name): keep lowest ID
  - "The Law Offices of X" vs "X": keep shorter/simpler form unless the full form is clearly the real name
  - Spanish-language variants of English firm names: merge into English canonical
  - Separate firms with similar structure (e.g., "X Law Group" vs "Y Law Group") are NOT duplicates — see False Positive Patterns below

### Step 2: Create Blacklisted Law Firms table ✅ DONE
- **Problem**: Blacklisted firms stored in main Law Firms table with "(BLACK LIST)" suffix in name
- **Solution**: Create dedicated `Blacklisted Law Firms` table (ID=785) in Law Firm Directory (App 198)
- **Fields**: Firm Name, Reason, Notes, Date Added
- **Result**: 3 firms moved — Omega Law Firm PC, Top Notch Law Group, Trillium Law
- **Law Firms table**: "(BLACK LIST)" suffix removed from names, Classification set to Blacklisted
- **Billing**: Noisy entries like "Omega Law Firm, PC ... do not send anything..." normalized to clean name

### Step 3: Add unknown firms from billing ✅ DONE
- **Problem**: 79 firm names in Settlement & Finance had no match in Law Firms directory
- **Solution**: Add all as new Law Firms entries (Classification=Existing, Active=False)
- **Result**: 70 firms added (after deduplication — e.g. Kalfaayan/Kalfayan → Kalfayan Merjanian)
- **Skipped**: 3 non-firm entries (`562-667-0378 lien negotiations`, `HTTP Corp`, `Terry Rendon rendonterri@gmail.com`)
- **To add new ones**: append to `NEW_LAW_FIRMS` list in the script, re-run `--step 3`

### Step 4: Normalize billing firm names ✅ DONE
- **Problem**: 577 unique Law Firm Name values in Settlement & Finance (2903 rows) — noisy free text
- **Solution**: Hard-coded `BILLING_FIRM_MAP` dict maps known variants to canonical names
- **Result**: 783 rows updated, 308 multi-firm slash entries skipped, 1746 already clean or unmapped
- **To add new mappings**: append to `BILLING_FIRM_MAP` in the script, re-run `--step 4` (idempotent)
- **Multi-firm entries**: slash-separated (e.g. `"The JLF Firm/Jacoby & Meyers"`) — left as-is intentionally

### Step 5: Normalize Law Firm Names in Closed Cases (table 772) ✅ DONE
- **Problem**: 297 unique Law Firm Name values in Closed Cases — typos, variant spellings, noisy suffixes
- **Solution**: Hard-coded `CLOSED_CASES_FIRM_MAP` dict in `execution/baserow_cleanup.py`
- **Result**: 160 rows updated (Mar 2026)
- **Key decisions**:
  - All Dayan Houman variants → `Dayan Houman Professional Law Corporation` (owner instruction)
  - `Law Office of Howard B. Kim` ≠ `Law Offices of Howard Kornberg` — different firms, not merged
  - `The Injury Firm` / `The Injury Law Firm` — poor labeling, left as-is
  - Multi-firm slash entries skipped (215 rows)
- **To add new mappings**: append to `CLOSED_CASES_FIRM_MAP`, re-run `--step 5` (idempotent)

### Step 6: Delete Duplicate Case Labels in Closed Cases (table 772) ✅ DONE
- **Problem**: 530 duplicate Case Label groups (same patient name + DOI appearing twice) — 2233 rows → ~1700 after cleanup
- **Cause**: Appears to be a bulk import that duplicated the table
- **Solution**: For identical pairs keep lowest ID; for differing pairs keep most-complete row; skip genuinely conflicting data
- **Result**: 530 duplicate rows deleted + 1 manual delete (Bhandari, Anmol row 373 — different visit count, kept row 371)
- **Kept separate** (manual review, genuinely different data):
  - `Rodriguez Sr., Martin - 06/17/2018` — rows 114 & 123 (different start dates)
  - `Garcia, Rosa - 04/05/2021` — rows 690 & 841 (different start dates & visits, likely re-opened case)

### Step 7: Standardize Law Firm Name Formatting (TODO)
- Normalize capitalization (e.g., `ACTS LAW` → `Acts Law`, `YERUSHALMI LAW FIRM` → `Yerushalmi Law Firm`)
- Strip trailing punctuation and double spaces
- `Adamson Ahaoot LLP` has a typo — real name is `Adamson Ahdoot LLP`

### Step 8: Patient Name Deduplication (TODO)
- Match patients across tables by name + DOB + case number
- Flag potential duplicates for manual review

### Step 9: Cross-table Integrity (TODO)
- Ensure linked records (Law Firm Contacts → Law Firms) not orphaned after deduplication
- Verify all patient records link to a valid law firm

### Step 10: Field Standardization (TODO)
- Phone numbers: normalize to (XXX) XXX-XXXX format
- Addresses: verify city/state formatting
- Emails: lowercase, trim whitespace

---

## Fuzzy Matching: False Positive Patterns

When using fuzzy matching to find duplicate/similar firm names, these patterns produce **false positives**. Always human-review before applying.

### Pattern 1: Generic suffix match
Firms with different roots but the same generic suffix score 82–92 because partial_ratio inflates on the shared suffix. These are DIFFERENT firms:
- `DK Law Group` ≠ `RK Law Group` (D ≠ R)
- `Mann Law Group` ≠ `Soliman Law Group`
- `AH Law Group` ≠ `Saeedian Law Group`
- `Simon Law Group` ≠ `Soliman Law Group`
- `Thomas Murphy Law Group` ≠ `HYP Law Group`
- `Compass Law Group` ≠ `RK Law Group`

**Trigger words**: `Law Group`, `& Associates`, `Injury Law`, `Law Firm`, `Law Corp`, `Legal Group`

**Rule**: If the only matching content is a generic suffix, it's a false positive. Require the distinctive root (person name or unique word) to match.

### Pattern 2: Partial ratio inflation
When a short string is a substring of a longer one, `partial_ratio` gives 100 even when they're different firms:
- `The Law Group PC` → scores 100 partial against `Alpine Law Group` (contains "Law Group")
- `The Injury Law Group` → scores against `B&D Injury Law Group APLC`

**Rule**: For short names (<4 distinctive tokens), don't rely on partial_ratio. Use full ratio only.

### Pattern 3: Common attorney name overlap
Individual attorney names can fuzzy-match across completely different firms:
- `Cardona Law Firm` → matched `Scott McDonald-McDonald Law Firm` (wrong)
- `Reardon Injury Law PC` → matched `Brown Injury Law` (wrong)

**Rule**: When matching attorney-named firms, require the attorney surname to match.

### Pattern 4: Multi-firm slash entries
Entries like `"The JLF Firm/Jacoby & Meyers"` are NOT duplicates — they represent cases where multiple attorneys were involved. Never deduplicate or normalize these. Leave them as-is.

### Safe matching patterns (high confidence, usually correct)
- Same attorney name, different prefix: `Larry H. Parker` = `The Law Offices of Larry H. Parker` ✅
- Embedded notes stripped: `Barm Law (833) 227-6529 notes...` = `Barm Law` ✅
- Status prefix stripped: `DROPPED - Dayan Houman Law` = `Dayan Houman` ✅
- Clear typo: `Law Offices of Sammer Habbas` = `Law Offices of Samer Habbas` ✅
- Suffix variant: `Karns & Karns Law` = `Karns & Karns` ✅

### Score thresholds (empirical, based on this dataset)
| Score | Reliability | Action |
|-------|------------|--------|
| 95–100 | Almost always correct | Auto-apply after spot check |
| 88–94 | Usually correct | Review for generic suffix false positives |
| 70–87 | High false positive rate | Manual review required, skip unless obvious |
| <70 | Likely different firm | Add as new entry, don't merge |

---

## Self-Annealing Notes
- Add new dedup decisions to `MERGE_PLAN` (Step 1), new firms to `NEW_LAW_FIRMS` (Step 3), new billing mappings to `BILLING_FIRM_MAP` (Step 4)
- Always run `--dry-run` before every live run
- Baserow batch-delete: `POST /api/database/rows/table/{id}/batch-delete/` with `{"items": [id1, id2, ...]}`
- Baserow batch-update: `PATCH /api/database/rows/table/{id}/batch/` with `{"items": [{id, field_NNNN: val}, ...]}`
- Auth: JWT token expires every ~8 minutes; `get_token()` handles auto-refresh
- `BILLING_FIRM_MAP` is idempotent — re-running Step 4 only touches rows that still have the old value

### Critical: field_id vs user_field_names for writes
**Never use `?user_field_names=true` for INSERT or UPDATE operations.** Use raw `field_NNNN` keys instead.

- `user_field_names=true` is safe for **reads** — reliable and convenient
- For **writes**, Baserow may not recognize user field names if a field was recently renamed or created in the same session (timing/propagation issue)
- The first/primary field is especially affected — its internal name may differ from what was requested in a rename
- **Pattern**: always fetch `GET /api/database/fields/table/{id}/` first, build `fid = {f['name']: f'field_{f["id"]}' for f in fields}`, then use `fid['Field Name']` as the key in payloads
