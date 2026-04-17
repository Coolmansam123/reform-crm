# Outreach Hub — Reform CRM

## What It Is

A password-protected web CRM hosted at `hub.reformchiropractic.app` (Modal + Cloudflare Worker proxy). Provides live dashboards across every major area of the Reform Chiropractic operation, all backed by Baserow.

**Entry point:** `execution/modal_outreach_hub.py` — Modal FastAPI app (routes + auth + Baserow proxy). All page-render functions live in `execution/hub/` as themed modules (see **Code Structure** below).

**Live URL:** `https://hub.reformchiropractic.app`
**Raw Modal URL:** `https://reformtechops--outreach-hub-web.modal.run`
**Last deployed:** 2026-04-03

---

## Current Pages (Live)

| Route | Description | Status |
|-------|-------------|--------|
| `/login` | Google OAuth sign-in page | Live |
| `/auth/google` | Initiate Google OAuth flow | Live |
| `/auth/google/callback` | OAuth callback — creates session | Live |
| `/logout` | Clear session | Live |
| `POST /api/gmail/send` | Send email via authenticated user's Gmail | Live |
| `GET /api/gmail/threads?contact_email=` | Fetch Gmail threads for a contact | Live |
| `/` | Command Center — combined stats + alerts | Live |
| `/attorney` | PI Attorney pipeline dashboard | Live |
| `/guerilla` | Guerilla Marketing pipeline dashboard | Live |
| `/community` | Community Outreach pipeline dashboard | Live |
| `/attorney/map` | Interactive attorney map | Live |
| `/guerilla/map` | Interactive guerilla map | Live |
| `/community/map` | Interactive community map | Live |
| `/patients` | Patient Rolodex — all PI stages | Live |
| `/patients/active` | Active treatment patients | Live |
| `/patients/billed` | Billed cases | Live |
| `/patients/awaiting` | Awaiting/negotiating | Live |
| `/patients/closed` | Closed cases | Live |
| `/firms` | Law firm overview | Live |
| `/billing/collections` | Outstanding balances + follow-up tracking | Live |
| `/billing/settlements` | Settlement records + financials | Live |
| `/guerilla/log` | Log Field Activity — standalone form page (5 forms) | Live |
| `/guerilla/events/internal` | Internal Events — tabbed by type (BOL, MMS, L&L, HAS) | Live |
| `/guerilla/events/external` | External Events — pipeline by Event Status | Live |
| `/guerilla/businesses` | Businesses Reached — all venues with activity counts | Live |
| `/guerilla/boxes` | Massage Box Tracking — T_GOR_BOXES | Live |
| `/guerilla/routes` | Field Route list — admin view | Live |
| `/guerilla/routes/new` | Route builder — create ordered stop list | Live |
| `/m` | Mobile Hub home — field staff landing page | Live |
| `/m/log` | Mobile Quick Log — 5 GFR form cards | Live |
| `/m/route` | Mobile Today's Route — stop list with check-in | Live |
| `/m/recent` | Mobile Recent Logs — last 20 activity records | Live |
| `GET /api/geocode` | Server-side Nominatim reverse geocode | Live |
| `GET /api/guerilla/routes/today` | Field rep: today's active route + stops | Live |
| `PATCH /api/guerilla/routes/stops/{id}` | Update stop status (Pending/Visited/Skipped) | Live |
| `POST /api/guerilla/routes` | Create route + stops | Live |
| `PATCH /api/guerilla/routes/{id}/status` | Toggle route Draft/Active/Completed | Live |
| `/contacts` | Contacts (placeholder) | Coming Soon |
| `/social` | Social Media (placeholder) | Coming Soon |
| `/social/history` | Social Media History (placeholder) | Coming Soon |
| `/calendar` | Calendar (placeholder) | Coming Soon |

---

## Baserow Tables

### Outreach
| Tool | Venues | Activities | Extra |
|------|--------|------------|-------|
| Attorney | 768 (Law Firms) | 784 | — |
| Guerilla | 790 (Business Venues) | 791 | 800 (Massage Boxes) |
| Community | 797 (Community Orgs) | 798 | — |

**Venue fields:** `Contact Status` (single_select), `Follow-Up Date`, `Type`, name field
**Activity fields:** `Date`, `Type`, `Outcome`, `Contact Person`, `Summary`, `Follow-Up Date`, `Event Status` (single_select, External Event only — Prospective/Approved/Scheduled/Completed, field ID 8092)

**Pipeline stages:**
- Attorney: Not Contacted → Contacted → In Discussion → Active Relationship
- Guerilla/Community: Not Contacted → Contacted → In Discussion → Active Partner

### PI Cases
| Table | ID | Description |
|-------|----|-------------|
| Active Treatment | 775 | Currently in treatment |
| Pt. Billed | 773 | Billed, pending resolution |
| Awaiting & Negotiating | 776 | Awaiting settlement |
| CLOSED | 772 | Fully closed cases |
| Finance | 781 | Settlements + collections |

**PI firm-history data model (2026-04-14):**
- `Law Firm Name` (text) — always the **current** firm only
- `Firm History` (long_text, field IDs: 775=8526, 773=8527, 776=8528, 772=8529) — chain of past → current firms
- Format: `OldFirm1 (until YYYY-MM-DD) -> OldFirm2 (until YYYY-MM-DD) -> CurrentFirm (current)`
  - Legacy entries (pre-2026-04-14) have no dates: `OldFirm -> CurrentFirm (current)`
  - Writes made via the hub's `PATCH /api/patients/{stage}/{id}/firm` endpoint add `(until <today>)` to the outgoing firm
- The legacy approach stored this as a `Firm history:` line inside `Case Notes` — all 103 such rows were migrated to the new field by `execution/migrate_firm_history.py`. Hub reads the new field first and falls back to Case Notes for safety.
- To change a patient's lawyer, use the Edit button in the hub patient detail modal (autocompletes from T_ATT_VENUES=768). Do NOT edit `Law Firm Name` directly — it bypasses history tracking.

### Massage Boxes
- Table 800 in Baserow database 203 (Guerilla Marketing)
- Fields: Business (link_row → 790), Date Placed, Date Removed, Location Notes, Status, Leads Generated, Notes
- `.env` key: `GORILLA_MASSAGE_BOXES_TABLE_ID=800`

### Guerilla Routes
- **T_GOR_ROUTES = 801** — Admin-created route definitions
  - Fields: Name (primary/text), Date, Assigned To (email), Status (Draft/Active/Completed)
- **T_GOR_ROUTE_STOPS = 802** — Ordered venue stops per route
  - Fields: Name (primary), Route (link_row → 801), Venue (link_row → 790), Stop Order (number), Status (Pending/Visited/Skipped/Not Reached), Notes (long_text), Completed At (text), Completed By (text), Check-In Lat (number, 7 dp), Check-In Lng (number, 7 dp)
  - **Historic bug:** before 2026-04-14, `Notes`/`Completed At`/`Completed By` were silently dropped because the fields didn't exist — code was PATCHing nonexistent field names. Added via `execution/add_route_stop_fields.py`.
  - **GPS check-ins:** mobile browser captures lat/lng via `watchPosition` and sends them in the PATCH body when marking a stop Visited. Admin view at `/guerilla/routes` renders a "📍 check-in" link per stop that opens Google Maps at those coords.
  - **Activity drill-down on admin view:** activities logged at a stop are matched by `Business.id === stop.venue_id && Date === route.date` and shown inline under the stop. No direct link_row — this is an implicit join.
- **Box pickup on routes:** stops whose venue has an Active massage box past its `Pickup Days` threshold get a pending-pickup badge in three places:
  1. Route builder (`/guerilla/routes/new`) — banner at top + badge on search results and selected stops
  2. Mobile route view (`/m/route`) — badge in the stop sheet + prominent pickup notice
  3. Admin view (`/guerilla/routes`) — badge on stop detail row
  When a field rep marks a stop Visited on mobile, the mobile `markRouteStop` JS follows up with a `PATCH /api/guerilla/boxes/{box_id}/pickup` call to auto-transition the matching box to `Picked Up` status and stamp `Date Removed`. That endpoint was relaxed from admin-only to guerilla-hub-access so field reps can trigger it.

**Baserow field-format gotcha:** when POST/PATCHing rows with `user_field_names=true`, link_row fields take a **plain list of integer IDs** (`[123]` not `[{"id": 123}]`), and single_select fields take the **plain string value** (`"Active"` not `{"value": "Active"}`). The `{"id": ...}` / `{"value": ...}` shapes are only in GET responses. Two endpoints were latently broken by this (`create_box`, `pickup_box`) — fixed 2026-04-14. Check any other row-write endpoint in `modal_outreach_hub.py` that touches single_selects or link_rows if you see `ERROR_REQUEST_BODY_VALIDATION`.
- `.env` keys: `T_GOR_ROUTES=801`, `T_GOR_ROUTE_STOPS=802`
- Modal secrets: `T_GOR_ROUTES`, `T_GOR_ROUTE_STOPS`
- Created via: `python execution/setup_gorilla_routes.py`

---

## Design System

```css
/* Dark theme (default) */
--bg: #0d1b2a;        /* page background */
--bg2: #0a1628;       /* sidebar */
--border: #1e3a5f;
--hdr-grad: linear-gradient(135deg, #0f3460, #16213e);

/* Accent colors */
Attorney:  #7c3aed  (purple)
Guerilla:  #ea580c  (orange)
Community: #059669  (green)
Patients:  #2563eb  (blue)
Billing:   #ef4444  (red)

/* Pipeline bars */
Not Contacted: #475569
Contacted:     #2563eb
In Discussion: #d97706
Active:        #059669

/* Alert dots */
Overdue: #ef4444
Today:   #f59e0b
Upcoming: #10b981
```

Light theme support is built in via `[data-theme="light"]` CSS variables and a toggle button.

---

## Code Structure

The hub is split into a thin **entry point** (`modal_outreach_hub.py`) that wires up Modal + FastAPI, and a **`hub/` package** of themed modules that render pages. Each module owns a slice of the UI so you can edit one area without touching everything else.

```
execution/
├── modal_outreach_hub.py         ← Modal app, FastAPI routes, auth, Baserow proxy
└── hub/
    ├── __init__.py               ← empty package marker
    │
    │   ── Infrastructure (the old shared.py, now split) ──
    ├── shared.py                 ← thin facade — re-exports everything below for back-compat
    ├── constants.py              ← table IDs (T_*) + _TEMPLATES_JS email bodies
    ├── access.py                 ← role lookup, hub allowlist, admin checks (5-min staff cache)
    ├── styles.py                 ← _CSS (desktop + mobile + light/dark) + _JS_SHARED template
    ├── nav.py                    ← _topnav — desktop top nav + hamburger drawer
    ├── compose.py                ← _COMPOSE_HTML / _COMPOSE_JS — email FAB overlay
    ├── shells.py                 ← _page / _forbidden_page / _mobile_page / _tool_page
    │
    │   ── Feature pages ──
    ├── dashboard.py              ← _login_page, _hub_page (Command Center), _calendar_page, _coming_soon_page
    ├── outreach.py               ← _directory_page, _map_page (shared across attorney/gorilla/community)
    ├── pi_cases.py               ← _patients_page (rolodex + detail modal), _firms_page
    ├── billing.py                ← _billing_page (collections + settlements)
    ├── comms.py                  ← _contacts_page, _communications_email_page
    ├── events.py                 ← _event_detail_page, _lead_form_page (public), _leads_dashboard_page
    ├── social.py                 ← _social_poster_hub_page, _social_schedule_page
    │
    │   ── Guerilla area ──
    ├── guerilla.py                ← GFR form helpers (_gfr_*) + form JS for field reps
    ├── guerilla_map.py           ← _gorilla_map_page (desktop map)
    ├── guerilla_pages.py         ← log, events internal/external, businesses, boxes, routes list + builder
    ├── route_planner.py          ← _route_planner_page (unified cross-tool map), _outreach_list_page
    │
    │   ── Mobile /m/* ──
    └── mobile.py                 ← _mobile_home_page, _mobile_log_page, _mobile_route_page, _mobile_recent_page, _mobile_map_page
```

### Editing map — "where does X live?"

| Want to change… | Edit this file |
|---|---|
| CSS (colors, spacing, responsive breakpoints) | `hub/styles.py` → `_CSS` |
| Shared JS helpers (`fetchAll`, `sv`, `esc`, `fmt`, `daysUntil`, `stampRefresh`) | `hub/styles.py` → `_JS_SHARED` |
| Top nav dropdowns / items / ordering | `hub/nav.py` → `_topnav` |
| Hamburger drawer (mobile-width desktop) | `hub/nav.py` → `_topnav` (`drawer_links` block) |
| Compose email overlay HTML/JS | `hub/compose.py` |
| Page shell (head, theme toggle, scripts) | `hub/shells.py` → `_page` |
| 403 page | `hub/shells.py` → `_forbidden_page` |
| Mobile `/m/*` page shell + bottom nav | `hub/shells.py` → `_mobile_page` |
| Attorney/Guerilla/Community dashboard template | `hub/shells.py` → `_tool_page` |
| Role/hub access rules | `hub/access.py` (`_is_admin`, `_get_allowed_hubs`, `ALL_HUB_KEYS`) |
| Baserow table IDs | `hub/constants.py` |
| Email outreach templates (PI / gorilla / community) | `hub/constants.py` → `_TEMPLATES_JS` |
| Command Center (`/`) | `hub/dashboard.py` → `_hub_page` |
| Login page | `hub/dashboard.py` → `_login_page` |
| Patient rolodex + detail modal (`/patients`) | `hub/pi_cases.py` → `_patients_page` |
| Law firm ROI (`/firms`) | `hub/pi_cases.py` → `_firms_page` |
| Collections / settlements (`/billing/*`) | `hub/billing.py` → `_billing_page` |
| Contact directory / Gmail thread view | `hub/comms.py` |
| Directory page (Contact List) for any outreach tool | `hub/outreach.py` → `_directory_page` |
| Map pages (attorney/gorilla/community desktop) | `hub/outreach.py` → `_map_page` |
| Guerilla desktop sub-pages (log, events, businesses, boxes) | `hub/guerilla_pages.py` |
| Guerilla desktop map | `hub/guerilla_map.py` |
| Route builder / planner (`/outreach/planner`, `/guerilla/routes/new`) | `hub/route_planner.py`, `hub/guerilla_pages.py` |
| GFR field-report forms (shared HTML helpers) | `hub/guerilla.py` |
| Any mobile `/m/*` page | `hub/mobile.py` |
| Event detail / public lead form / leads dashboard | `hub/events.py` |
| Social poster / scheduler | `hub/social.py` |
| FastAPI routes, OAuth, Baserow proxy, session store | `modal_outreach_hub.py` |

### Import conventions

- New code should import **from the specific module** (`from .nav import _topnav`, `from .constants import T_ATT_VENUES`) — it's easier to trace and keeps module dependencies explicit.
- `hub/shared.py` is a **thin facade** that re-exports every public name from the infrastructure modules. Existing callers (`from .shared import _page, T_PI_FINANCE, ...`) keep working unchanged — don't rewrite them just to rewrite them. Only touch import lines when you're editing that file for another reason.
- Dependency direction inside the infrastructure layer (no cycles): `constants` → `access` / `styles` / `compose` (leaves) → `nav` (uses access) → `shells` (uses all of the above). Feature pages depend on `shared` (or any specific module) but not on each other.

### `_JS_SHARED` — helpers embedded in every page

These are injected into every `_page()` and `_mobile_page()` render via `_JS_SHARED.format(br=..., bt=...)`. Available to all page-specific scripts:

- `fetchAll(tid)` — paginated Baserow fetch (200 rows/page), retries twice
- `sv(f)` — extract the `.value` from a Baserow single_select field (falls through for plain strings)
- `daysUntil(ds)` — integer days from today (negative = overdue)
- `fmt(ds)` — format `YYYY-MM-DD` → `Mon D`
- `esc(s)` — HTML-escape for safe innerHTML
- `stampRefresh()` — update the "Updated X:XX" timestamp in `#refresh-stamp`

---

## Auth

Google Workspace OAuth 2.0. Only accounts from `ALLOWED_DOMAIN` (e.g. `reformchiropractic.com`) can log in.

**Flow:** `/login` → "Sign in with Google" → `/auth/google` → Google consent → `/auth/google/callback` → session cookie set → `/`

**Session storage:** Modal Dict `hub-sessions` (keyed by random session ID stored in `hub_session` cookie, HttpOnly, 7-day expiry, `samesite=lax`).

**CSRF protection:** Modal Dict `hub-oauth-states` stores state token with 5-minute TTL.

**Token refresh:** Access tokens refresh automatically on each page load if within 60s of expiry.

**Gmail scopes:** `gmail.send` + `gmail.readonly` — enables compose from hub + thread view per contact.

### Modal Secrets Required

```bash
modal secret create outreach-hub-secrets \
  GOOGLE_CLIENT_ID=<from GCP — use HUB_CLIENT_ID from .env> \
  GOOGLE_CLIENT_SECRET=<from GCP — use HUB_CLIENT_SECRET from .env> \
  ALLOWED_DOMAIN=reformchiropractic.com \
  BASEROW_URL=https://baserow.reformchiropractic.app \
  BASEROW_API_TOKEN=<token — use BASEROW_API_TOKEN from .env> \
  GOOGLE_MAPS_API_KEY=<use GOOGLE_MAPS_API_KEY from .env> \
  --force
```

**Key mapping (.env → Modal secret):**
| `.env` key | Modal secret key |
|---|---|
| `HUB_CLIENT_ID` | `GOOGLE_CLIENT_ID` |
| `HUB_CLIENT_SECRET` | `GOOGLE_CLIENT_SECRET` |
| `HUB_ALLOWED_DOMAIN` | `ALLOWED_DOMAIN` |
| `BASEROW_URL` | `BASEROW_URL` |
| `BASEROW_API_TOKEN` | `BASEROW_API_TOKEN` |
| `GOOGLE_MAPS_API_KEY` | `GOOGLE_MAPS_API_KEY` |
| `GOOGLE_CALENDAR_EMBED_URL` | `GOOGLE_CALENDAR_EMBED_URL` |

**To regenerate from .env (bash):**
```bash
set -a; source .env; set +a
modal secret create outreach-hub-secrets \
  GOOGLE_CLIENT_ID="$HUB_CLIENT_ID" \
  GOOGLE_CLIENT_SECRET="$HUB_CLIENT_SECRET" \
  ALLOWED_DOMAIN="$HUB_ALLOWED_DOMAIN" \
  BASEROW_URL="$BASEROW_URL" \
  BASEROW_API_TOKEN="$BASEROW_API_TOKEN" \
  GOOGLE_MAPS_API_KEY="$GOOGLE_MAPS_API_KEY" \
  GOOGLE_CALENDAR_EMBED_URL="$GOOGLE_CALENDAR_EMBED_URL" \
  --force
```

### Google Cloud Console Setup (one-time)
1. Enable Gmail API
2. OAuth Consent Screen → User Type: **Internal**
   - Scopes: `email`, `profile`, `openid`, `gmail.send`, `gmail.readonly`
3. OAuth 2.0 Client ID → Web application
   - Authorized redirect URIs:
     - `https://hub.reformchiropractic.app/auth/google/callback`
     - `http://localhost:8000/auth/google/callback`

---

## Deploy

```powershell
cd "c:\Users\crazy\Reform Workspace"
$env:PYTHONUTF8="1"
modal deploy execution/modal_outreach_hub.py
```

Custom domain carries over automatically after redeploy.

### Local dev

```bash
cd "c:\Users\crazy\Reform Workspace"
python execution/modal_outreach_hub.py
# → http://localhost:8000/login
```

Requires `fastapi[standard]`, `python-multipart`, `uvicorn`, `python-dotenv`.

---

## Initial Setup (one-time, already done)

### Modal secret
See **Auth** section above for the full `modal secret create` command with Google OAuth keys.

To rotate Baserow token (no redeploy needed):
```bash
modal secret create outreach-hub-secrets \
  GOOGLE_CLIENT_ID=<existing> \
  GOOGLE_CLIENT_SECRET=<existing> \
  ALLOWED_DOMAIN=reformchiropractic.com \
  BASEROW_URL=https://baserow.reformchiropractic.app \
  BASEROW_API_TOKEN=<new_token> --force
```

### Cloudflare Worker proxy (already configured)

Modal's custom domain requires a paid plan. A Cloudflare Worker proxies instead.

**DNS:** `CNAME hub → reformtechops--outreach-hub-web.modal.run` (Proxied/orange cloud)

**Worker name:** `hub-proxy`, route: `hub.reformchiropractic.app/*`

```javascript
export default {
  async fetch(request) {
    const url = new URL(request.url);
    url.hostname = "reformtechops--outreach-hub-web.modal.run";
    const modifiedRequest = new Request(url.toString(), {
      method: request.method,
      headers: request.headers,
      body: request.method !== "GET" && request.method !== "HEAD" ? request.body : null,
      redirect: "follow",
    });
    return fetch(modifiedRequest);
  },
};
```

Note: `redirect: "follow"` is required — `redirect: "manual"` drops `Set-Cookie` headers from opaque redirects, breaking auth.

---

## CRM Roadmap (Upcoming Pages)

These routes exist as "Coming Soon" stubs and are next to be built out:

| Route | Goal |
|-------|------|
| `/contacts` | Unified contact directory across all outreach tools |
| `/social` | Social media content calendar + post management |
| `/social/history` | Historical post performance and archive |
| `/calendar` | Unified follow-up calendar across all tools |

Other potential additions as the CRM matures:
- Per-record detail pages (patient detail, law firm detail, venue detail)
- Write-back to Baserow (log activities, update follow-up dates directly from hub)
- Notifications / alerts via Slack
- Reporting / exports

---

## Troubleshooting

**Dashboard shows "—" everywhere / no data loads**
- Check browser console for fetch errors
- Verify `BASEROW_API_TOKEN` in Modal secret is correct
- Confirm Baserow is accessible

**Login loop (password accepted but keeps redirecting)**
- Verify `HUB_PASSWORD` secret is set in Modal
- Clear browser cookies for the domain

**All pages show 0 results / data not loading**
- Most likely cause: `BASEROW_API_TOKEN` missing or expired in `outreach-hub-secrets`
- Also happens if the secret was recreated with `--force` and some keys were omitted
- Fix: regenerate the secret from `.env` using the full command in "Modal Secrets Required" above, then redeploy
- Data cache TTL is 120s — after fix, data reappears within 2 minutes

**"Google Maps API key not configured" on map pages**
- `GOOGLE_MAPS_API_KEY` not in `outreach-hub-secrets` Modal secret
- Fix: recreate the secret with `GOOGLE_MAPS_API_KEY="$GOOGLE_MAPS_API_KEY"` included (see key mapping above)

**401 errors on Baserow fetch**
- `modal secret update outreach-hub-secrets BASEROW_API_TOKEN=<new_token>`

**Table IDs changed**
- Update `T_*` constants at top of `execution/modal_outreach_hub.py`
- Redeploy

**Unicode error on deploy (Windows)**
- Always use `$env:PYTHONUTF8="1"` before `modal deploy`

**`UnicodeEncodeError: surrogates not allowed` at runtime (500 on page load)**
- Caused by using surrogate pair escape sequences (e.g. `\ud83d\udccd`) for emoji inside Python f-strings
- Python 3 on Linux (Modal's runtime) rejects surrogates when Starlette encodes the HTML response to UTF-8
- Fix: use full Unicode scalar values instead — e.g. `\U0001f4cd` (📍) and `\U0001f310` (🌐)
- Rule: any emoji above U+FFFF must use `\U0001xxxx` (8-digit) form, never the surrogate pair form
