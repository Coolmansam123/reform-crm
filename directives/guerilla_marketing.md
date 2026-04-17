# Guerilla Marketing Platform

Map and track outreach to local wellness businesses — gyms, yoga studios, health food stores, and chiropractors/wellness clinics — within a configurable radius. Goal: build referral partnerships and co-marketing relationships that drive new patient flow.

**Source of truth:** Baserow (Business Venues table, Business Activities table)

> **Code note:** Internal Python variable names (`T_GOR_*`, `_gorilla_*` functions) and execution script filenames still use "gorilla" from an early misspelling. We are keeping those for consistency. Route paths, user-facing labels, and directives all use the correct spelling "guerilla."

## Prerequisites

- SerpAPI key → `SERPAPI_KEY` in `.env` (same key as attorney mapper)
- Google Maps API key → `GOOGLE_MAPS_API_KEY` in `.env` (same key as attorney mapper)
- Office coordinates → `ATTORNEY_MAPPER_OFFICE_LAT_LNG` in `.env` (same as attorney mapper)
- Office address → `ATTORNEY_MAPPER_OFFICE_ADDRESS` in `.env` (same as attorney mapper)
- Search radius → `ATTORNEY_MAPPER_RADIUS_MILES` in `.env` (default: 15)
- Baserow credentials → `BASEROW_URL`, `BASEROW_EMAIL`, `BASEROW_PASSWORD` in `.env`
- Python packages: `pip install serpapi geopy fuzzywuzzy python-Levenshtein requests python-dotenv`

## Baserow Tables

All 3 tables live in **Database 198** (Law Firm Directory — same as attorney tables).

After running `setup_gorilla_marketing_tables.py`, note the table IDs it prints. Update the `TABLE_IDS` block at the top of `generate_gorilla_map.py` and `sync_businesses_to_baserow.py` if they differ from defaults.

| Table | ID | Purpose |
|-------|-----|---------|
| Business Venues | 790 | Local businesses (guerilla targets) |
| Business Activities | 791 | Outreach log per business |
| Massage Boxes | 800 | Massage box placements + leads |
| Guerilla Routes | 801 | Admin-created route definitions |
| Guerilla Route Stops | 802 | Ordered venue stops per route |
| Influencers | (scaffolded) | Future influencer collab tracking |

## Pipeline (run steps independently as needed)

### Step 1: Scrape Google Maps for Businesses
```
python execution/scrape_businesses.py
```
Uses SerpAPI to find gyms, yoga studios, health stores, and wellness clinics near the office. Searches from 5 points (center + 4 cardinal) with 2 queries per type.

**Options:**
- `--types gym yoga health wellness` — scrape only specific types (default: all 4)
- `--radius 15` — override radius in miles

**Cost:** ~10 SerpAPI credits per type (~40 total for all 4).

Output: `.tmp/scraped_businesses.json`

### Step 2: Geocode & Filter by Radius
```
python execution/geocode_businesses.py
```
Fills missing coordinates via Nominatim (free, 1 req/sec) and filters to the configured radius.

Output: `.tmp/businesses_in_radius.json`

### Step 3: Set Up Baserow Tables (first time only)
```
python execution/setup_gorilla_marketing_tables.py
```
Creates 3 tables in Baserow Database 198:
1. **Business Venues** — local businesses
2. **Business Activities** — outreach log per business
3. **Influencers** — scaffolded for future influencer collab tracking

Idempotent — safe to re-run. Prints table IDs on completion.

### Step 4: Sync to Baserow
```
python execution/sync_businesses_to_baserow.py
```
Pushes `.tmp/businesses_in_radius.json` → Baserow Business Venues table.
- Deduplicates by Google Place ID (if present), then by normalized name+address
- **Filters out competitors**: businesses with chiropractic keywords in their name or website are excluded automatically (logged as "COMPETITOR FILTERED")
- Idempotent: existing records are NOT overwritten (preserves manual edits like notes, contact status)
- New businesses are added as "Not Contacted"

### Step 4b: Enrich Yelp URLs (two-stage, credit-efficient)

**Stage 1 — Free (run first):**
```
python execution/enrich_yelp_urls.py
```
Constructs Yelp slugs from business name + city and verifies via direct HTTP. Zero SerpAPI credits. Resolved businesses are written to Baserow immediately. Unresolved businesses written to `.tmp/yelp_review.csv`.

**Review step:** Open `.tmp/yelp_review.csv`. Set `Action = skip` for businesses you don't want (irrelevant, clearly closed, wrong category, etc.). Default is `keep`.

**Stage 2 — SerpAPI fallback (opt-in, after review):**
```
python execution/enrich_yelp_urls.py --serpapi --limit 50
```
Only processes rows marked `keep` in the review CSV. Use `--limit` to cap credits per session. Skips rows marked `skip`.

**Cost:** Stage 1 = 0 credits. Stage 2 = 1 credit per business (only for unresolved + kept ones).

### Step 5: Generate Guerilla Marketing Map
```
python execution/generate_gorilla_map.py
```
Reads live from Baserow and generates a standalone HTML map for guerilla marketing outreach.

Output: `.tmp/guerilla_map.html` — open in browser

## Map Features

- **Pins colored by Contact Status**: Dark Gray = Not Contacted, Blue = Contacted, Purple = In Discussion, Green = Partner
- **Activity ring**: colored ring around pin shows recency of last outreach (green ≤14d, orange ≤45d, red >45d)
- **Type layer toggles**: show/hide by business type (Gym, Yoga Studio, Health Store, Chiropractor/Wellness)
- **Status layer toggles**: filter by contact status
- **SVG type icons** on each pin (barbell, yoga pose, cross, wellness symbol)
- Side panel per pin: name, type/status/goal badges, address, phone, website, rating/reviews, distance
- **Timestamped notes log** with Add button → saves to Baserow instantly
- Contact Status dropdown → live Baserow sync, pin color updates immediately
- Activity log: view + create activities per business
- Autocomplete search (by name or type)

## Baserow Schema

### Business Venues Table
| Field | Type | Options |
|-------|------|---------|
| Business Name | text | Primary |
| Type | single_select | Gym, Yoga Studio, Health Store, Chiropractor/Wellness |
| Address | text | |
| Phone | text | |
| Website | text | |
| Latitude | text | |
| Longitude | text | |
| Rating | text | Google rating 1–5 |
| Reviews | number | Google review count |
| Distance (mi) | text | Miles from office |
| Google Place ID | text | Google Maps identifier |
| Contact Status | single_select | Not Contacted, Contacted, In Discussion, Partner |
| Outreach Goal | single_select | Referral Partner, Co-Marketing, Both |
| Notes | long_text | Free-form, editable from map |
| Google Reviews JSON | long_text | Cached from Places API |
| Google Maps URL | text | |
| Yelp Search URL | text | |

### Business Activities Table
| Field | Type | Options |
|-------|------|---------|
| Business | link_row → Business Venues | |
| Date | date | |
| Type | single_select | Call, Email, Drop-In, Meeting, Mail, Other |
| Outcome | single_select | No Answer, Left Message, Spoke With, Scheduled Meeting, Declined, Follow-Up Needed |
| Contact Person | text | |
| Summary | long_text | |
| Follow-Up Date | date | |
| Created By | text | |

### Influencers Table (scaffolded — no scraping yet)
| Field | Type | Options |
|-------|------|---------|
| Influencer Name | text | Primary |
| Platform | single_select | Instagram, TikTok, YouTube, Facebook, Other |
| Handle / URL | text | |
| Niche | single_select | Fitness, Wellness, Nutrition, Lifestyle, Chiro/Health |
| Followers | number | |
| Engagement Rate | text | e.g. "4.2%" |
| Location | text | City/region |
| Contact Status | single_select | Not Contacted, Contacted, In Discussion, Active Collab |
| Collab Type | single_select | Sponsored Post, Giveaway, Ambassador, Story Feature, Other |
| Email | text | |
| Notes | long_text | |

## Re-running

**After finding new businesses:**
1. Run Steps 1 → 2 → 4 → 5

**To just refresh the map** (after editing data in Baserow):
1. Run Step 5 only (`python execution/generate_gorilla_map.py`)

**New radius or area:**
1. Update `ATTORNEY_MAPPER_RADIUS_MILES` in `.env`
2. Run Steps 1 → 2 → 4 → 5

## Edge Cases (Pipeline)

- **SerpAPI credits:** ~40 calls for all 4 types. Run `--types` flag to scrape individual types if budget-conscious.
- **Duplicate businesses:** Deduplicated first by Google Place ID, then by normalized name+address. Chain locations (e.g. "Planet Fitness - Alhambra", "Planet Fitness - Pasadena") are kept as separate entries.
- **CORS:** HTML uses Baserow API token directly. Works from `file://` on most browsers. Serve via `python -m http.server 8000` from `.tmp/` if needed.
- **Baserow table IDs:** Printed after running `setup_gorilla_marketing_tables.py`. Update the `TABLE_IDS` constants in the sync and map generator scripts if they differ from defaults.
- **Influencer table:** Schema is scaffolded but no scraping pipeline exists yet. Add records manually in Baserow or build a scraping script when ready.

---

## Guerilla Field Reports

5 real field activity forms integrated into the hub as modal overlays, used for logging outreach activity from both the desktop guerilla section and the mobile hub.

### The 5 Forms (All Fields Confirmed)

#### Form 1: Business Outreach Log
*Door-to-door visit log. Records contact info, massage box placement, interest in 3 programs.*

**Basic Info**
- Employee Name → auto-populated from session user
- Business Name (required) — search/link T_GOR_VENUES (790)
- Point of Contact Name (required)
- Contact Phone Number (required, tel)
- Contact Email Address (required, email)
- Business Address (required)

**Massage Box**
- Did You Leave a Massage Box? (required, radio: Yes / No)

**Available Programs** *(3 sub-sections)*
For each of **Lunch & Learn**, **Health Assessment Screening**, **Mobile Massage Service (Employees & Patrons)**:
- Program description shown as info block
- Interested in Program? (dropdown)
- Follow Up Date (date)
- Program Booking Requested? (radio: Yes / No)
- Notes (textarea)

**Gifted Consultation(s) & Massage(s)**
- Number of Consultations Gifted (number)
- Number of Massages Gifted (number)

---

#### Form 2: External Event
*Pre-event planning + demographic intel when attending a community event.*

**Basic Info**
- Name of Event (required)
- Type of Event (required, text — e.g. Health Fair, 5k, Flea Market)
- Event Organizer (required)
- Event Organizer Phone Number (optional, tel)
- Cost of Event (required)
- Event Date & Time (required — date + HH + MM + AM/PM)
- Event Duration (optional — e.g. "1 hour, 90 mins")
- Event Flyer Upload (optional, file — upload to Bunny CDN LA region, store URL in Summary)

**About Event Venue**
- Venue Address (required)
- Indoor or outdoors? (required, dropdown)
- Is there access to electricity? (required, dropdown)

**Participant Details**
- Is your staff white collar or blue collar? (radio: White collar / Blue collar / Mixed)
- Do you offer healthcare insurance to your employees? (radio: Yes / No)
- What is your company's industry? (text)

---

#### Form 3: Mobile Massage Service
*Service booking form when a company wants to schedule mobile chair/table massage.*

**Basic Info**
- Point of Contact Name (required)
- Contact Phone Number (required, tel)
- Contact Email Address (required, email)
- Company Name (required)

**About Your Venue**
- Venue Address (required)
- Indoor or outdoors? (required, dropdown)
- Is there access to electricity? (required, dropdown)

**Participant Details**
- Are participants customers/patrons or company staff? (required, radio: Customers & patrons / Company staff / Customers, patrons, & staff)
- Number of anticipated customers/patrons/staff serviced (required, number)
- What is your company's industry? (required)
- What product(s) or service(s) do you offer? (required, textarea)

**Requested Service, Date, & Time**
- Duration of massage per participant (required, radio: 10 min $20 / 15 min $30 / 30 min $60)
- Preferred type of massage? (required, radio: Chair massage / Table massage / No preference)
- Date & Time Requested (required — date + HH + MM + AM/PM)

---

#### Form 4: Lunch and Learn
*Service booking form when a company wants to schedule an L&L presentation.*

**Basic Info**
- Point of Contact Name (required)
- Contact Phone Number (required, tel)
- Contact Email Address (required, email)
- Company Name (required)

**About Your Venue**
- Venue Address (required)
- Indoor or outdoors? (required, dropdown)
- Is there access to electricity? (required, dropdown)
- Is there a conference room or space that can seat all attending staff? (required, dropdown)
- Is there enough tables or surfaces to lay out the food? (required, dropdown)
- Is there a projector or large TV screen to display the presentation? (required, dropdown)

**Participant Details**
- Number of anticipated staff attending (required, number)
- Do any attending staff have dietary restrictions? (required, radio: Yes / No)
- Is your staff white collar or blue collar? (required, radio)
- Do you offer healthcare insurance to your employees? (required, radio: Yes / No)
- What is your company's industry? (required)
- What product(s) or service(s) do you offer? (required, textarea)

**Requested Date & Time**
- Date & Time Requested (required — date + HH + MM + AM/PM)

---

#### Form 5: Health Assessment Screening
*Service booking form when a company wants to schedule a chiropractic health screening.*

**Basic Info**
- Point of Contact Name (required)
- Contact Phone Number (required, tel)
- Contact Email Address (required, email)
- Company Name (required)

**About Your Venue**
- Venue Address (required)
- Indoor or outdoors? (required, dropdown)
- Is there access to electricity? (required, dropdown)

**Participant Details**
- Number of anticipated staff attending (required, number)
- Is your staff white collar or blue collar? (required, radio)
- Do you offer healthcare insurance to your employees? (required, radio: Yes / No)
- What is your company's industry? (required)
- What product(s) or service(s) do you offer? (required, textarea)

**Requested Date & Time**
- Date & Time Requested (required — date + HH + MM + AM/PM)

---

### Baserow Data Mapping (Field Reports)

**All submissions → T_GOR_ACTS (791)**

| Field | Value |
|-------|-------|
| `Type` | Form name string (e.g. "Business Outreach Log") |
| `Date` | Today / event date / requested date |
| `Contact Person` | Point of contact name |
| `Follow-Up Date` | If specified in form |
| `Business` | `[{id: venueId}]` — linked to T_GOR_VENUES (790) if matched/created |
| `Summary` | Structured text dump of all form-specific fields |
| `Outcome` | "Booking Requested" for forms 3–5; "Visit Logged" for form 1 |

**Venue enrichment:** Forms 1, 3, 4, 5 → create or update record in T_GOR_VENUES (790) with Company Name, Address, Contact Person, Phone, Email.

**Baserow Type field:** The `Type` single_select in T_GOR_ACTS (791) needs these 5 option values: Business Outreach Log, External Event, Mobile Massage Service, Lunch and Learn, Health Assessment Screening. If the API rejects an unknown option value, fall back to `"Other"` and prepend form type to Summary.

---

### UX Architecture (Field Reports)

**Entry points:**
- Desktop: `/guerilla` dashboard → orange "Log Field Activity" button → Form Chooser Modal
- Desktop: `/guerilla/log` → standalone page with 5 cards + recent submissions feed
- Mobile: `/m/log` → 5 form cards in single column

**Form Modals:**
- Full-screen overlay with dark backdrop, scrollable body
- Header: orange bar + form type name + logged-in user name + × close
- Section headers match the original forms (Basic Info / About Your Venue / Participant Details / etc.)
- Footer: HIPAA compliance badge + Cancel + Submit buttons
- On submit → `POST /api/guerilla/log` → success shows "Submitted ✓" + "Log Another" or "Close"

---

### Field Reports Build Status

| Stage | Status |
|-------|--------|
| Stage 1 — Backend Endpoint (`POST /api/guerilla/log`) | Complete |
| Stage 2 — Chooser + Form 1 (Business Outreach Log) | Complete |
| Stage 3 — Forms 3, 4, 5 (Service Booking Forms) | Complete |
| Stage 4 — Form 2 (External Event) — modal UI | Not started |
| Stage 5 — `/guerilla/log` Page + Nav Link | Complete |
| Stage 6 — Polish (form reset, stat chips, directive update) | Not started |

---

## Files

| File | Purpose |
|------|---------|
| `execution/scrape_businesses.py` | SerpAPI scraper for gyms, yoga, health, wellness |
| `execution/geocode_businesses.py` | Add coordinates + filter by radius |
| `execution/setup_gorilla_marketing_tables.py` | Create Baserow tables (run once) |
| `execution/sync_businesses_to_baserow.py` | Sync scraped businesses → Baserow |
| `execution/generate_gorilla_map.py` | Generate standalone guerilla marketing HTML map |
| `execution/setup_gorilla_routes.py` | Create route tables in Baserow |
| `execution/modal_outreach_hub.py` | Hub app — guerilla dashboard, forms, map, routes |
| `.tmp/scraped_businesses.json` | Raw SerpAPI results |
| `.tmp/businesses_in_radius.json` | Geocoded + radius-filtered businesses |
| `.tmp/guerilla_map.html` | Guerilla marketing map output |
