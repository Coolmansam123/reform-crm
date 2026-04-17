# Community Outreach Platform

Map and track outreach to local community organizations — chambers of commerce, service clubs (Lions, Rotary), BNI chapters, networking mixers, churches, parks & rec departments, community centers, and high schools — within a 7-mile radius. Goal: build community presence, get a seat at events where locals gather, and drive patient referrals through sponsorships, tabling, and partnerships.

**Source of truth:** Baserow (Community Organizations table 797, Community Activities table 798, Drop Boxes table 799) — Database 204

## Prerequisites

- SerpAPI key → `SERPAPI_KEY` in `.env` (same key as other mappers)
- Google Maps API key → `GOOGLE_MAPS_API_KEY` in `.env` (same key as other mappers)
- Office coordinates → `ATTORNEY_MAPPER_OFFICE_LAT_LNG` in `.env` (same as other mappers)
- Office address → `ATTORNEY_MAPPER_OFFICE_ADDRESS` in `.env` (same as other mappers)
- Search radius → `COMMUNITY_RADIUS_MILES` in `.env` (default: 7 — smaller than attorney/guerilla)
- Baserow credentials → `BASEROW_URL`, `BASEROW_EMAIL`, `BASEROW_PASSWORD`, `BASEROW_API_TOKEN` in `.env`
- Drop Boxes table ID → `COMMUNITY_DROP_BOXES_TABLE_ID=799` in `.env`
- Python packages: `pip install serpapi geopy fuzzywuzzy python-Levenshtein requests python-dotenv`

## Pipeline (run steps independently as needed)

### Step 1: Scrape Google Maps for Community Organizations
```
python execution/scrape_community.py
```
Uses SerpAPI to find community organizations near the office. Searches from 5 points (center + 4 cardinal) with 1-2 queries per type.

**Options:**
- `--types chamber lions rotary bni networking church parksrec commcenter highschool` — scrape only specific types (default: all)
- `--radius 10` — override radius in miles

**Cost:** ~20 SerpAPI credits for all types (~1-2 queries × 9 types × 5 points, fewer for single-query types).

Output: `.tmp/scraped_community.json`

### Step 2: Geocode & Filter by Radius
```
python execution/geocode_community.py
```
Fills missing coordinates via Nominatim (free, 1 req/sec) and filters to the configured radius.

Output: `.tmp/community_in_radius.json`

### Step 3: Set Up Baserow Tables (first time only)
```
python execution/setup_community_tables.py
```
Creates 2 tables in Baserow Database 198:
1. **Community Organizations** — local orgs and venues
2. **Community Activities** — outreach log per organization

Idempotent — safe to re-run. Prints table IDs on completion. Add IDs to `.env`:
```
COMMUNITY_VENUES_TABLE_ID=<id>
COMMUNITY_ACTIVITIES_TABLE_ID=<id>
```

### Step 4: Sync to Baserow
```
python execution/sync_community_to_baserow.py
```
Pushes `.tmp/community_in_radius.json` → Baserow Community Organizations table.
- Deduplicates by Google Place ID (if present), then by normalized name+address
- Idempotent: existing records are NOT overwritten (preserves manual edits)
- New organizations are added as "Not Contacted"

### Step 5: Generate Community Outreach Map
```
python execution/generate_community_map.py
```
Reads live from Baserow and generates a standalone HTML map for community outreach tracking.

Output: `.tmp/community_map.html` — open in browser

## Map Features

- **Pins colored by Contact Status** (Outreach View): Dark Gray = Not Contacted, Blue = Contacted, Purple = In Discussion, Green = Active Partner
- **Priority View**: pins color-scaled by Outreach Score (dark green = top score → red = lowest)
- **Outreach Score**: computed per org — `type_priority×10 + rating×10 + log(reviews)×5 + distance_bonus`. Displayed as badge in side panel
- **Top 50 filter**: one-click to show only the 50 highest-scored orgs on the map
- **Activity ring**: colored ring around pin shows recency of last outreach (green ≤14d, orange ≤45d, red >45d)
- **Drop Box indicator**: orange dot on pin when an Active drop box is placed at that org
- **Type layer toggles**: show/hide by organization type
- **Status layer toggles**: filter by contact status
- **SVG type icons** on each pin (briefcase = Chamber, gear = Lions/Rotary/BNI, church = Church, tree = Parks & Rec, building = Community Center, cap = High School)
- Side panel per pin: name, type/status/goal/score badges, address, phone
- **Editable Contact Person + Email**: inline inputs in side panel, save to Baserow on blur
- **Timestamped notes log** with Add button → saves to Baserow instantly
- Contact Status dropdown → live Baserow sync, pin color updates immediately
- **Drop Box section**: history of all drop boxes for that org + inline Log Drop Box form
- Activity log: view + create activities per organization
- Autocomplete search (by name or type)
- **Stats bar**: Visible | Not Contacted | Active Partners | Active Drop Boxes

## Baserow Schema

### Community Organizations Table (Table 797, Database 204)
| Field | Type | Options |
|-------|------|---------|
| Name | text | Primary |
| Type | single_select | Chamber of Commerce, Lions Club, Rotary Club, BNI Chapter, Networking Mixer, Church, Parks & Rec, Community Center, High School, Other |
| Address | text | |
| Phone | text | |
| Contact Person | text | Primary contact name, editable from map |
| Email | email | Editable from map |
| Website | url | |
| Latitude | text | |
| Longitude | text | |
| Rating | text | Google rating 1–5 |
| Reviews | number | Google review count |
| Distance (mi) | text | Miles from office |
| Google Place ID | text | Google Maps identifier |
| Contact Status | single_select | Not Contacted, Contacted, In Discussion, Active Partner |
| Outreach Goal | single_select | Event Presence, Referral Partnership, Sponsorship, Both |
| Notes | long_text | Timestamped log, editable from map |
| Google Maps URL | url | |
| Yelp Search URL | url | |

### Community Activities Table (Table 798, Database 204)
| Field | Type | Options |
|-------|------|---------|
| Organization | link_row → Community Organizations | |
| Date | date | |
| Type | single_select | Call, Email, Drop-In, Meeting, Event, Mail, Other |
| Outcome | single_select | No Answer, Left Message, Spoke With, Scheduled Meeting, Declined, Follow-Up Needed |
| Contact Person | text | |
| Summary | long_text | |
| Follow-Up Date | date | |
| Created By | text | |

### Drop Boxes Table (Table 799, Database 204)
| Field | Type | Options |
|-------|------|---------|
| Name | text | Primary (auto) |
| Organization | link_row → Community Organizations | |
| Date Placed | date | |
| Date Removed | date | |
| Location Notes | text | e.g. "Front desk", "Waiting room" |
| Status | single_select | Active, Picked Up, Lost |
| Leads Generated | number | Count of leads attributed to this box |
| Notes | long_text | |

## Contact Status Flow

| Status | Meaning |
|--------|---------|
| Not Contacted | In outreach queue — haven't reached out yet |
| Contacted | Reached out, awaiting response |
| In Discussion | Engaged, actively exploring a partnership |
| Active Partner | Ongoing relationship — we're participating in their events or they're sending us referrals |

## Outreach Goals

| Goal | Use When |
|------|----------|
| Event Presence | We want a table or speaking slot at their events |
| Referral Partnership | We want them to refer community members to us |
| Sponsorship | We want to sponsor their events or programs |
| Both | Multiple goals |

## Re-running

**After finding new organizations:**
1. Run Steps 1 → 2 → 4 → 5

**To just refresh the map** (after editing data in Baserow):
1. Run Step 5 only (`python execution/generate_community_map.py`)

**New radius or area:**
1. Update `COMMUNITY_RADIUS_MILES` in `.env`
2. Run Steps 1 → 2 → 4 → 5

## Edge Cases

- **SerpAPI credits:** ~20 calls for all types. Run `--types` flag to scrape individual types if budget-conscious.
- **Duplicate organizations:** Deduplicated first by Google Place ID, then by normalized name+address.
- **CORS:** HTML uses Baserow API token directly. Works from `file://` on most browsers. Serve via `python -m http.server 8000` from `.tmp/` if needed.
- **Baserow table IDs:** Printed after running `setup_community_tables.py`. Add to `.env` as `COMMUNITY_VENUES_TABLE_ID` and `COMMUNITY_ACTIVITIES_TABLE_ID`. Scripts auto-discover by table name if env vars not set.
- **Missing email fields:** SerpAPI Google Maps results don't return email addresses. Enrich manually in Baserow or via a follow-up web search for each org.
- **Networking mixers:** Search returns event-hosting venues, not individual events. Use the Notes and Activity Log to track specific event dates.

## Files

| File | Purpose |
|------|---------|
| `execution/scrape_community.py` | SerpAPI scraper for community organizations |
| `execution/geocode_community.py` | Add coordinates + filter by radius |
| `execution/setup_community_tables.py` | Create Baserow tables (run once) |
| `execution/sync_community_to_baserow.py` | Sync scraped organizations → Baserow |
| `execution/generate_community_map.py` | Generate standalone community outreach HTML map |
| `.tmp/scraped_community.json` | Raw SerpAPI results |
| `.tmp/community_in_radius.json` | Geocoded + radius-filtered organizations |
| `.tmp/community_map.html` | Community outreach map output |
