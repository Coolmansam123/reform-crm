# Mobile Hub — Build Directive

## What This Is

A stripped-down, field-staff-first mobile version of the Reform Operations Hub (`hub.reformchiropractic.app/m`). Designed for employees out in the field on their phones — quick logging, route navigation, and venue lookup. Not a responsive version of the desktop hub; it's a separate experience with its own pages, layout, and navigation.

**Live URL:** `hub.reformchiropractic.app/m`
**Auto-redirect:** Mobile user-agents hitting `/` are redirected to `/m` automatically.

> **Code note:** Internal Python variable names (`T_GOR_*`, `_gorilla_*` functions) and execution script filenames still use "gorilla" from an early misspelling. We are keeping those for consistency. Route paths, user-facing labels, and directives all use the correct spelling "guerilla."

---

## Architecture

Everything lives in a single file: `execution/modal_outreach_hub.py`

- Mobile page functions: `_mobile_page()` (shared shell), `_mobile_home_page()`, `_mobile_log_page()`, `_mobile_map_page()`, `_mobile_route_page()`, `_mobile_recent_page()`
- CSS: All mobile styles are in the `_CSS` block (search for `.mobile-` and `.m-` prefixes)
- Routes are registered in both the Modal `web()` function and local dev `__main__` block
- Mobile pages share the same `/api/data/{tid}` and `/api/guerilla/log` endpoints as desktop

### Key Distinction: Desktop vs Mobile

| Aspect | Desktop (`/`) | Mobile (`/m`) |
|--------|--------------|---------------|
| Purpose | Full CRM dashboard for office work | Field tool for staff on the go |
| Nav | Top nav bar with dropdowns + hamburger fallback at <=768px | Fixed bottom nav (5 tabs) |
| Pages | ~25+ pages (directories, billing, comms, social, calendar) | 5 pages (Home, Log, Map, Route, Recent) |
| Theme | Dark/light toggle in top nav | Dark/light toggle in page headers (🌙/☀️) |
| Layout | Sidebar + content panels | Single-column, touch-optimized |

---

## Pages

### 1. Home (`/m`)
- Greeting with user's first name + current date
- Two CTA cards: "Log Activity" → `/m/log`, "My Route" → `/m/route`
- Quick links: Map, Recent Logs, Businesses, Community, Full Hub
- Theme toggle + Sign out in header

### 2. Log (`/m/log`)
- 5 Guerilla Field Report form cards in single column
- Tapping a card opens the GFR modal overlay (shared with desktop)
- Forms: Business Outreach Log, External Event, Mobile Massage Service, Lunch & Learn, Health Assessment Screening
- See `directives/guerilla_marketing.md` for full form specs

### 3. Map (`/m/map`)
- Full-screen Google Maps (uses `GOOGLE_MAPS_API_KEY`)
- Both Guerilla (orange stroke) and Community (green stroke) venue pins
- Pin color = contact status (blue=Not Contacted, yellow=Contacted, orange=In Discussion, green=Active Partner)
- Filter pill buttons overlaid at top: All / Guerilla / Community
- Tapping a pin opens a bottom sheet (82vh drawer) with:
  - Venue name, status badge, type badge, tool badge (Guerilla/Community)
  - Contact info: phone (tap-to-call), address (tap to open Maps), website
  - CRM controls: Contact Status dropdown (live Baserow update + pin recolor), Follow-Up Date input + Save
  - Massage Boxes section (Guerilla only): shows active/removed boxes with placement dates + leads
  - Recent Activity: last 10 activities async-loaded
  - "Log Field Visit" CTA (Guerilla only): opens GFR Form 1 with business name pre-filled
- CSS class `map-mode` on `.mobile-wrap` makes background transparent so the fixed map renders properly
- Center point: Reform Chiropractic office (33.9478, -118.1335)

### 4. Route (`/m/route`)
- Shows today's assigned route from Baserow (`T_GOR_ROUTES` = 801, `T_GOR_ROUTE_STOPS` = 802)
- Stop cards with distance badges (Haversine formula)
- "Check In & Log" button per stop → opens GFR Form 1 pre-filled
- "Skip" button to mark a stop as skipped

### 5. Recent (`/m/recent`)
- Last 20 activity records for the logged-in user
- Pulls from `T_GOR_ACTS` (791)
- Shows type, business name, date, outcome

---

## Baserow Tables (referenced by mobile)

| Table | ID | Usage |
|-------|-----|-------|
| Guerilla Venues | 790 | Map pins, venue search, Form 1 linking |
| Guerilla Activities | 791 | Activity logging, recent page |
| Community Venues | 797 | Map pins (community) |
| Community Activities | 798 | Activity logging |
| Community Drop Boxes | 799 | Box tracking |
| Guerilla Massage Boxes | 800 | Box tracking in map sheet |
| Guerilla Routes | 801 | Route page |
| Guerilla Route Stops | 802 | Route page stops |

---

## Navigation

- **Bottom nav bar**: Fixed 60px bar at bottom with 5 tabs (Home, Log, Map, Route, Recent)
- Active tab highlighted in orange (`#ea580c`)
- Each tab has emoji icon + label
- Pages also have `← Home` links in headers for quick back-navigation
- "Full Hub" link on home page to switch to desktop version
- Desktop has a 📱 button in top nav and hamburger drawer to switch to mobile

### Mobile Detection & Redirect

User-agent detection in both Modal `web()` and local dev handlers:
- Keywords checked: `iphone`, `android`, `mobile`, `ipod`
- Root `/` redirects to `/m` for mobile users
- No redirect on direct `/m` access from desktop (allows testing)

---

## Theme Support

- Dark mode (default): Navy blue background (`--bg: #0d1b2a`)
- Light mode: Clean white/slate (`--bg: #f1f5f9`)
- Toggle button (🌙/☀️) in header of every mobile page
- Persists via `localStorage` key `hub-theme` (shared with desktop)
- CSS uses same `[data-theme="light"]` system as desktop

---

## CSS Conventions

All mobile-specific classes use two prefixes:
- `.mobile-*` — layout components (wrap, hdr, body, bnav, cta, link, etc.)
- `.m-*` — map-specific components (map-wrap, map-filters, sheet, sheet-backdrop, etc.)

Key layout rules:
- `.mobile-wrap` — flex column, min-height 100vh, `var(--bg)` background
- `.mobile-wrap.map-mode` — transparent background for map page
- `.mobile-body` — flex:1, padding-bottom:80px (clears bottom nav)
- `.mobile-bnav` — fixed bottom, z-index 800
- `.m-map-wrap` — fixed position, z-index 100, bottom:60px (above bottom nav)
- Touch targets: min 44px height on buttons, 16px font on inputs (prevents iOS zoom)

---

## Deployment

```bash
cd "c:\Users\crazy\Reform Workspace"
PYTHONUTF8=1 modal deploy execution/modal_outreach_hub.py
```

Mobile routes are part of the same Modal app as desktop. No separate deployment needed.

---

## Known Issues / TODO

- [ ] GFR Form 2 (External Event) — modal not yet built; backend endpoint ready
- [ ] Form reset on re-open (stale values may persist)
- [ ] "Reports This Week" stat chip on `/m` home page
- [ ] GPS-based route ordering (currently Haversine from office, not from user location)
- [ ] Offline support / PWA capabilities (future)

---

## Edge Cases & Learnings

- **Map z-index**: The map div is `position:fixed` inside `.mobile-wrap`. Without `map-mode` class (transparent background), the wrap's opaque background covers the map. Always use `wrap_cls='map-mode'` for the map page.
- **Bottom sheet padding**: Sheet needs `padding-bottom:80px` to clear the bottom nav bar when scrolled to the end.
- **Modal routes**: Mobile `/m/*` routes must be registered in BOTH the Modal `web()` FastAPI app AND the local dev `__main__` block. Missing routes in Modal = 404 on production.
- **iOS zoom prevention**: Inputs must be >=16px font-size to prevent Safari auto-zoom on focus.
