# Attorney Relationship Mapper

Map plaintiff injury attorneys within a configurable radius, classify them as existing relationships or prospects, sync to Baserow, and visualize on an interactive Google Maps web app with live note-taking, contact tracking, and activity logging.

**Source of truth:** Baserow (Law Firms table 768, Activities table 784)

## Prerequisites

- SerpAPI key (free tier: 100 searches/month) → set `SERPAPI_KEY` in `.env`
- Google Maps API key → set `GOOGLE_MAPS_API_KEY` in `.env` (enable Maps JavaScript API)
- Office address → set `ATTORNEY_MAPPER_OFFICE_ADDRESS` in `.env`
- Office coordinates → set `ATTORNEY_MAPPER_OFFICE_LAT_LNG` in `.env` (e.g. `33.9478,-118.1335`)
- Search radius → set `ATTORNEY_MAPPER_RADIUS_MILES` in `.env` (default: 15)
- Fresh CSV export of the P.I. Sheet → save to `.tmp/== P.I. Sheet == - Patients and Info.csv`
- Baserow credentials → `BASEROW_URL`, `BASEROW_EMAIL`, `BASEROW_PASSWORD`, `BASEROW_API_TOKEN` in `.env`
- Python packages: `pip install serpapi geopy fuzzywuzzy python-Levenshtein requests python-dotenv`

## Pipeline (run in order)

### Step 1: Parse Existing Relationships
```
python execution/parse_existing_attorneys.py
```
Reads the P.I. Sheet CSV and extracts three lists:
- **Relationships** — unique firms from active patient cases (fuzzy-deduped)
- **Blacklist** — firms to exclude from all results
- **Referral firms** — firms for unrepresented patients

Output: `.tmp/existing_attorneys.json`

### Step 2: Scrape Google for Attorneys
```
python execution/scrape_attorneys.py
```
Runs 5 search queries via SerpAPI (Google Maps engine):
- personal injury attorney, lawyer, accident attorney, injury law firm, plaintiff attorney

Returns structured data with GPS coordinates from Google Maps.

Output: `.tmp/scraped_attorneys.json`

**Cost:** ~5 SerpAPI credits per run.

### Step 3: Geocode & Filter by Radius
```
python execution/geocode_attorneys.py
```
- Uses pre-configured office coordinates from `.env` (falls back to Nominatim geocoding)
- Geocodes any attorneys missing lat/lng (via free Nominatim)
- Filters to only keep attorneys within the configured radius
- Rate limited: 1 req/sec for Nominatim

Output: `.tmp/attorneys_in_radius.json`

### Step 4: Clean & Sync to Baserow
```
python execution/cleanup_law_firms.py
```
Cleans up the Law Firms table (Baserow table 768) and enriches with scraped data:
1. **Purges junk rows** — removes firms with no name, or no address/phone/email
2. **Adds map fields** — Latitude, Longitude, Rating, Reviews, Distance, Classification, Google Place ID, Patient Count, Notes, Contact Status
3. **Enriches existing firms** — fuzzy-matches Baserow firms against scraped data to add coordinates, ratings, websites (strict matching: compares distinctive name parts at >=85% threshold to prevent false positives)
4. **Adds patient counts** — from parsed PI sheet relationships
5. **Adds prospect firms** — scraped firms not already in Baserow (checks blacklist first)
6. **Enriches case stats** — writes Active Patients, Billed Patients, Awaiting Billing, Settled Cases, Total Cases per firm from extended PI sheet parser output
7. **Enriches Google Reviews** — fetches up to 3 review snippets via Places API for firms with a Google Place ID; stores as JSON + Google Maps URL
8. **Enriches Yelp URLs** — constructs a Yelp search URL from firm name + city; no API needed

**Contact Status categories:**
- `Not Contacted` — prospects in the outreach queue
- `Contacted` — prospects already reached out to
- `In Discussion` — prospects who responded
- `Active Relationship` — existing firms we work with

This script is idempotent for field creation (skips existing fields) but will re-delete junk rows and re-enrich on each run. Reset enrichment data before re-running if needed.

### Step 4b: Set Up Activity Log Table (first time only)
```
python execution/setup_activity_log.py
```
Creates the Activities table (ID 784) in the Law Firm Directory database (198) with a link_row to Law Firms. Idempotent — safe to re-run.

### Step 5: Generate Interactive Map
```
python execution/generate_attorney_map.py
```
Reads all firms with coordinates from Baserow and generates a versioned HTML file.

Output: `.tmp/attorney_map_v{N}.html` — open in browser (current: v5)

**Data sources (all live from Baserow — no CSV dependency):**
- Law Firms (768): name, address, contact info, GPS, rating, notes, contact status
- Active Cases (775): counted per firm → At a Glance "Active" stat
- Tx Completed - Billed (773): counted per firm → At a Glance "Billed" stat
- Awaiting (776): counted per firm → At a Glance "Awaiting" stat
- Closed Cases (772): counted + detailed list → At a Glance "Settled" stat + Settled Cases section
- Activities (784): loaded live from map JS per firm click → Activity Log section

**Map features:**
- **Dual view modes** — toggle between Outreach View and Relationship View (button in controls bar)
- **Autocomplete search** — dropdown filters firms as you type, shows name/address/distance with highlighted matches. Click a result to zoom and open details.
- **Side panel** on pin click with:
  - **At a Glance** — case stat grid: Active | Billed | Awaiting | Settled | Total cases (all derived live from patient management tables 775/773/776/772)
  - **Google Reviews** — up to 3 review snippets (stars, author, relative time, text) + "See all on Google ↗" link
  - **Yelp** — "View on Yelp ↗" search link
  - Contact info (address, phone, fax, email, website)
  - Details (distance, Google rating/review count, patient referral count, preferred MRI/PM facilities)
  - Contact Status dropdown (saves to Baserow instantly, pin color updates live)
  - Notes textarea (auto-saves to Baserow after 1.5s typing pause or on blur)
  - **Activity Log** — view all outreach activities for this firm, sorted newest first
  - **Log Activity form** — inline form to record calls, emails, drop-ins, meetings with date, type, outcome, contact person, summary, and optional follow-up date. Saves to Baserow Activities table instantly.
- **Layer toggles** — show/hide each Contact Status category independently
- **Radius circle** — visual overlay for the configured search radius
- **Live stats bar** — counts update in real-time; shows status counts in Outreach View, case-volume distribution in Relationship View

**Outreach View (default):**
- Pins colored by Contact Status: green (Active), blue (Not Contacted), yellow (Contacted), orange (In Discussion), red (Office)
- Stats bar shows pipeline counts per status
- Use to work through prospect outreach waves

**Relationship View:**
- Active Relationship pins color-scaled by Total Cases (5 green shades)
- All other firms grayed out (still visible, clickable, filterable)
- Case volume legend appears in controls bar
- Stats bar shows case-volume distribution across active relationships
- Use to assess relationship depth and identify high-value vs. low-volume firms

**Active Relationship pin color scale (by Total Cases):**
- 0-2 cases: light green `#a8d5b5`
- 3-5 cases: medium green `#6abf82`
- 6-10 cases: standard green `#34a853`
- 11-20 cases: dark green `#1e8a3f`
- 20+ cases: very dark green `#0d5c2a`

**Outreach workflow:** Switch to Outreach View, filter to "Not Contacted", work through prospects, change each to "Contacted" as you reach out. Log each activity (call, email, drop-in). Pin turns yellow, stats update, activity history builds up. Repeat in waves.

### Legacy: Step 5 (CSV Export)
```
python execution/generate_map_layers.py
```
Splits classified data into two CSVs for manual Google My Maps import (superseded by the interactive map above):
- `.tmp/map_existing_relationships.csv` → green pins
- `.tmp/map_prospects.csv` → blue pins

## Baserow Schema (Law Firms Table — ID 768)

| Field | Type | Purpose |
|-------|------|---------|
| Law Firm Name | text | Primary identifier |
| Law Office Address | text | Street address |
| Phone Number | text | Main phone |
| Fax Number | text | Fax |
| Email Address | text | Contact email |
| Website | text | Firm website URL |
| Preferred MRI Facility | text | From Law Firm Info tab |
| Preferred PM Facility | text | From Law Firm Info tab |
| Latitude | text | GPS latitude (from SerpAPI) |
| Longitude | text | GPS longitude (from SerpAPI) |
| Rating | text | Google rating (1-5) |
| Reviews | text | Google review count |
| Distance (mi) | text | Miles from office |
| Classification | single_select | Existing / Prospect / Blacklisted |
| Contact Status | single_select | Not Contacted / Contacted / In Discussion / Active Relationship |
| Google Place ID | text | Google Maps place identifier |
| Patient Count | text | Number of patients referred (existing firms) |
| Notes | long_text | Free-form notes (editable from map) |
| Active Patients | number | Patients with Active status in PI sheet |
| Billed Patients | number | Patients on Tx Completed - Billed tab |
| Awaiting Billing | number | Patients on Awaiting & Negotiated tab |
| Settled Cases | number | Patients on CLOSED tab |
| Total Cases | number | Sum of all 4 case counts |
| Google Reviews JSON | long_text | JSON array: [{author_name, rating, text, relative_time_description}] up to 3 |
| Google Maps URL | text | Direct Google Maps listing URL (from Places API) |
| Yelp Search URL | text | Yelp search URL constructed from firm name + city |

## Baserow Schema (Activities Table — ID 784, Database 198)

| Field | Type | Purpose |
|-------|------|---------|
| Name | text | Auto-generated primary field |
| Law Firm | link_row (→ 768) | Links activity to a law firm |
| Date | date | When the activity happened |
| Type | single_select | Call / Email / Drop-In / Lunch/Meeting / Mail / Other |
| Outcome | single_select | No Answer / Left Message / Spoke With / Scheduled Meeting / Declined / Follow-Up Needed |
| Contact Person | text | Who you spoke with |
| Summary | long_text | What happened / key takeaways |
| Follow-Up Date | date | When to follow up (optional) |
| Created By | text | Who logged this activity |

## Data Source (P.I. Sheet)

The PI sheet is exported as separate tab CSVs to `.tmp/` with prefix `pi_sheet_export_`. All tabs share the same column structure: col B = Status, col I = Law Firm Name ONLY.

| Tab CSV | Status values used | Maps to |
|---|---|---|
| `pi_sheet_export_Patients and Info.csv` | `Active` | Active Patients + blacklist/referral sections |
| `pi_sheet_export_Tx Completed - Billed.csv` | `Tx Completed` | Billed Patients |
| `pi_sheet_export_Awaiting & Negotiated.csv` | `Awaiting`, `Negotiated` | Awaiting Billing |
| `pi_sheet_export_CLOSED.csv` | `Closed` | Settled Cases |

The parser (`parse_existing_attorneys.py`) fuzzy-deduplicates firm names across all tabs and aggregates counts per canonical firm name. Blacklist and referral firm sections are parsed from the Patients and Info tab only (after their respective section markers).

## Edge Cases

- **Fuzzy match false positives**: The cleanup script strips generic legal words ("law", "firm", "office", etc.) and compares distinctive name parts at >=85% threshold. This prevents matches like "Aratta Law Firm" → "Lara Law Firm". If false positives still occur, manually fix in Baserow and clear the enrichment fields.
- **Defense attorneys**: Filtered by keyword ("defense", "insurance defense", etc.) but review output manually
- **Geocoding failures**: Attorneys without addresses are skipped; Nominatim may fail on PO boxes
- **Stale data**: Re-export all P.I. Sheet tab CSVs to `.tmp/` before each run to get current relationships
- **Google Places reviews quota**: Places Details API costs ~$17/1,000 requests. For ~200 firms = ~$3. Reviews are cached in Baserow — `enrich_google_reviews()` skips firms already enriched.
- **Places API not enabled**: If reviews enrichment returns 403, enable "Places API" in Google Cloud Console (same project as Maps JavaScript API — no new key needed)
- **Yelp URL is a search, not a direct page**: The Yelp URL takes the user to a search results page for the firm. It's not a direct business profile link but is ToS-compliant and free.
- **CORS**: The map HTML calls Baserow API directly using the database token. Works from `file://` on most browsers. If CORS issues occur, serve via `python -m http.server 8000` from the `.tmp/` directory.

## Re-running

**When relationships change** (new patients, new firms):
1. Re-export all PI Sheet tab CSVs to `.tmp/`
2. Run Steps 1 → 4 → 5

**For a full refresh** (new attorneys in the area):
1. Run all 5 steps in order

**To just regenerate the map** (after editing data in Baserow):
1. Run Step 5 only

## Files

| File | Purpose |
|------|---------|
| `execution/parse_existing_attorneys.py` | Parse P.I. Sheet CSV into structured data |
| `execution/scrape_attorneys.py` | SerpAPI scraper for Google Maps results |
| `execution/geocode_attorneys.py` | Add coordinates + filter by radius |
| `execution/match_and_classify.py` | Cross-reference and classify (legacy) |
| `execution/generate_map_layers.py` | Output CSVs for Google My Maps (legacy) |
| `execution/cleanup_law_firms.py` | Clean Baserow, enrich with scraped data, add prospects |
| `execution/setup_activity_log.py` | Create Activities table in Baserow (run once) |
| `execution/generate_attorney_map.py` | Generate interactive Google Maps HTML |
| `.tmp/attorney_map_v1.html` | Map v1 (original, no activity log) |
| `.tmp/attorney_map_v2.html` | Map v2 (with activity log) |
| `.tmp/attorney_map_v3.html` | Map v3 (at-a-glance panel: case stats, Google reviews, Yelp link, color-scaled pins) |

## Prerequisites

- **Places API** must be enabled in Google Cloud Console (same project as Maps JavaScript API):
  Console → APIs & Services → Library → "Places API" → Enable
- All PI Sheet tab CSVs exported to `.tmp/` with `pi_sheet_export_` prefix

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025 | Initial map with contact status, notes, search, layer toggles |
| v2 | 2026-02-16 | Added Activity Log (Baserow table 784): view/create activities per firm from map side panel. Activity types: Call, Email, Drop-In, Lunch/Meeting, Mail, Other. Outcomes: No Answer, Left Message, Spoke With, Scheduled Meeting, Declined, Follow-Up Needed. Baserow is now source of truth. |
| v3 | 2026-02-23 | At-a-glance panel: case stats grid (Active/Billed/Awaiting/Settled/Total from PI sheet tabs), Google Reviews (up to 3 snippets via Places API + "See all on Google" link), Yelp search link. Dual view modes: Outreach View (color by status) and Relationship View (Active Relationship pins color-scaled by total case count, 5 green shades; other firms grayed). Case-volume legend and mode-aware stats bar. New Baserow fields: Active Patients, Billed Patients, Awaiting Billing, Settled Cases, Total Cases, Google Reviews JSON, Google Maps URL, Yelp Search URL. |
