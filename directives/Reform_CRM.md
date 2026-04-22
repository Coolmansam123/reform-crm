# Reform CRM / Operations Hub

## What It Is

A password-protected web app at `hub.reformchiropractic.app` (Modal + Cloudflare Worker proxy) that acts as Reform Chiropractic's internal operations platform. Lives on top of Baserow; wraps dashboards, a PI pipeline, marketing outreach tools, a HubSpot-style CRM (Companies / People / Activities), an internal helpdesk, and a Google Calendar view — all behind Google Workspace SSO.

**Entry point:** [execution/modal_outreach_hub.py](../execution/modal_outreach_hub.py) — Modal FastAPI app (routes + auth + Baserow proxy). All page-render functions live in [execution/hub/](../execution/hub/) as themed modules (see **Code Structure** below).

**Live URL:** `https://hub.reformchiropractic.app`
**Raw Modal URL:** `https://reformtechops--outreach-hub-web.modal.run`

---

## Access Model

Every page is gated on one of two things:

1. **`_is_admin(user)`** — full access, based on an allowlist in [hub/access.py](../execution/hub/access.py).
2. **`_has_hub_access(user, hub_key)`** — per-hub permission driven by the `Allowed Hubs` multi-select on the `T_STAFF` (815) row for that user.

`ALL_HUB_KEYS` enumerates the valid hub keys: `attorney`, `guerilla`, `community`, `pi_cases`, `billing`, `communications`, `social`, `calendar`, `tickets`. When a new hub is added, the key must be added to `ALL_HUB_KEYS` *and* to the `Allowed Hubs` single_select options on T_STAFF (via Baserow field PATCH).

Non-admins who aren't allow-listed for a hub are redirected to `/` (the dashboard); the dashboard itself strips down to whatever hubs they do have. A view-mode toggle on `/settings` lets the user "see the dashboard as if I only had hub X" — scoped only to admins listed in `VIEW_AS_EMAILS` (currently just `techops@reformchiropractic.com`).

---

## Routes

### Public / auth
| Route | Description |
|---|---|
| `/login` | Google OAuth sign-in |
| `/auth/google` | Initiate OAuth flow |
| `/auth/google/callback` | OAuth callback — creates session |
| `/logout` | Clear session |
| `/settings` | Per-user profile + view-mode toggle (admin only for view mode) |

### Dashboard & calendar
| Route | Description |
|---|---|
| `/` | Command Center — KPI tiles + alerts + calendar widget, scoped by `Allowed Hubs` |
| `/calendar` | Full-bleed month view of the signed-in user's primary Google Calendar; click a day for a slide-out event panel; "+ Add event" schedules on your primary calendar |

### CRM (Companies / People / Activities)
| Route | Description |
|---|---|
| `/companies` | (alias of `/contacts`) Companies Directory — unified across Attorney / Guerilla / Community categories |
| `/companies/{id}` | Company detail — inline-editable profile + Activity / History tabs + linked People sidebar |
| `/people` | People list + `+ New Person` modal with company picker |
| `/people/{id}` | Person detail with Activity timeline |

### Ticketing (internal helpdesk)
| Route | Description |
|---|---|
| `/tickets` | Ticket list — filter by status / priority / assignee |
| `/tickets/{id}` | Ticket detail — inline status/priority/assignee/category edit + comments thread |

### Outreach pipelines
| Route | Description |
|---|---|
| `/attorney`, `/guerilla`, `/community` | Per-tool pipeline dashboards |
| `/attorney/map`, `/guerilla/map`, `/community/map` | Interactive maps (per tool) |

### PI cases & billing
| Route | Description |
|---|---|
| `/patients` | Patient Rolodex — all PI stages |
| `/patients/active`, `/patients/billed`, `/patients/awaiting`, `/patients/closed` | Per-stage views |
| `/firms` | Law firm overview (with firm-history timeline) |
| `/billing/collections` | Outstanding balances + follow-up tracking |
| `/billing/settlements` | Settlement records + financials |

### Guerilla sub-pages
| Route | Description |
|---|---|
| `/guerilla/log` | Standalone GFR form page (5 forms) |
| `/guerilla/events/internal` | Internal Events — tabbed by type (BOL, MMS, L&L, HAS) |
| `/guerilla/events/external` | External Events — pipeline by Event Status |
| `/guerilla/businesses` | Businesses Reached — all venues with activity counts |
| `/guerilla/boxes` | Massage Box Tracking |
| `/guerilla/routes` | Field Route list — admin view |
| `/guerilla/routes/new` | Route builder |

### Communications
| Route | Description |
|---|---|
| `/communications/email` | Compose + thread view per contact (Gmail) |

### Social
| Route | Description |
|---|---|
| `/social`, `/social/poster`, `/social/history` | Social poster + scheduler |

### APIs (non-exhaustive)
| Method / Path | Purpose |
|---|---|
| `GET /api/data/{tid}` | Cached Baserow passthrough (paginated) |
| `GET /api/dashboard` | Consolidated stats for the Command Center |
| `GET /api/calendar/events` | User's primary Google Calendar. Accepts `?start=ISO&end=ISO&max=N&calendar_id=X` (defaults: now → now+20 events, `calendar_id=primary`) |
| `POST /api/meetings` | Create event on user's primary Google Calendar with `sendUpdates=all`; auto-logs an Activity when `company_id` / `contact_id` provided |
| `POST /api/gmail/send`, `GET /api/gmail/threads?contact_email=` | Gmail send + threads |
| `GET/POST /api/tickets` | List / create tickets |
| `GET/PATCH /api/tickets/{id}` | Fetch / update; auto-appends a system comment for status + assignee changes |
| `GET/POST /api/tickets/{id}/comments` | Thread |
| `GET/PATCH /api/companies/{id}` | Read / update a Company. PATCH also mirrors the write to the matching legacy venue row (see **Bi-directional sync** below) |
| `GET /api/companies/{id}/people`, `GET/POST /api/companies/{id}/activities` | Linked entities + activity feed |
| `GET/POST /api/people` | List / create |
| `GET/PATCH /api/people/{id}` | Read / update |
| `GET/POST /api/people/{id}/activities` | Activity feed for a person |
| `GET/PATCH /api/patients/{stage}/{id}`, `.../firm` | Patient edits (firm edits update `Firm History`) |
| `POST /api/guerilla/log` | Field Report submission |
| `PATCH /api/guerilla/boxes/{id}/pickup` | Transition massage box to Picked Up |
| `POST /api/guerilla/routes`, `PATCH /api/guerilla/routes/{id}/status`, `PATCH /api/guerilla/routes/stops/{id}` | Route / stop writes |
| `GET /api/geocode` | Server-side Nominatim reverse geocode |

Every endpoint runs through `_get_session` (401 on unauthenticated) and the appropriate `_has_hub_access` check (403 on denied); writes call `_invalidate(tid)` on the touched tables so the in-memory cache reflects fresh data.

---

## Baserow Layout

When a new domain comes online, prefer creating a **new database** rather than piling into an existing one. Current databases:

| Database | ID | Purpose |
|---|---|---|
| Reform Chiropractic CRM | 197 | Companies, Contacts, Activities |
| Law Firm Directory | 198 | Attorney venues (legacy) + activities + PI stages |
| Gorilla Marketing | 203 | Guerilla venues (legacy), activities, boxes, routes, stops |
| Community Outreach | 204 | Community venues (legacy) + activities |
| Operations Hub | 206 | Tickets + Ticket Comments (created 2026-04-21) |

### CRM tables (DB 197 — Reform Chiropractic CRM)

| Table | ID | Notes |
|---|---|---|
| Companies | 820 | Unified across categories. `Category` (Attorney / Guerilla / Community). `Legacy Source` + `Legacy ID` stamps every row so writes can mirror back to the per-category legacy venue table. |
| Contacts | 821 | People. `Primary Company` is a link_row → Companies. |
| Activities | 822 | Unified activity log. `Company` + optional `Contact` link_rows. `Kind` is one of `user_activity`, `edit`, `note`, `creation`. `Type` includes `Meeting` (auto-logged from meeting scheduler). |

### Outreach legacy tables

These still exist and are still written by the older hubs (guerilla route-stop flows, GFR log submissions, field-rep tooling via the routes domain). The Companies table shadows them; edits go through the bi-directional sync layer below.

| Tool | Venues | Activities | Extra |
|---|---|---|---|
| Attorney | 768 (Law Firms) | 784 | — |
| Guerilla | 790 (Business Venues) | 791 | 800 (Massage Boxes), 801 (Routes), 802 (Route Stops) |
| Community | 797 (Community Orgs) | 798 | — |

**Pipeline stages:**
- Attorney: Not Contacted → Contacted → In Discussion → Active Relationship
- Guerilla / Community: Not Contacted → Contacted → In Discussion → Active Partner

### Bi-directional sync (Companies ↔ legacy venues)

Instead of rewriting every legacy hub to use Companies, the hub mirrors writes in both directions:

- **Forward (`PATCH /api/companies/{id}`):** after writing the Companies row, `_mirror_to_legacy_venue()` looks up the matching legacy venue row via the Company's `Legacy Source` + `Legacy ID` and PATCHes it. Handles per-category field-name translation (e.g. `Name` → `Law Firm Name`) and status reverse-map (`Active Partner` → `Active Relationship` for attorneys, `Active Partner` → `Partner` for guerilla).
- **Reverse:** `guerilla_api.update_venue` mirrors writes back to Companies by looking up the Company with matching `Legacy ID`. Same for `/api/contacts` POST from the Comms hub — creates dual-write to legacy and to Companies.
- **Net effect:** edits from either side (detail pages or legacy hubs) stay in sync; legacy hubs and their external consumers (route planner, field-rep site on Coolify, Events, etc.) keep reading venue tables and see current data.

### Tickets tables (DB 206 — Operations Hub)

| Table | ID | Notes |
|---|---|---|
| Tickets | 818 | `Title`, `Description`, `Status` (Open / In Progress / Waiting / Resolved / Closed), `Priority`, `Category`, `Reporter`, `Assignee`, `Created`, `Updated`, `Resolution Notes`. |
| Ticket Comments | 819 | `Ticket` link_row, `Author`, `Body`, `Kind` (`comment`, `status_change`, `assignment`, `creation`), `Created`. System comments are auto-written on state changes by the PATCH endpoint. |

### PI cases (DB 198 tables)

| Table | ID | Description |
|---|---|---|
| Active Treatment | 775 | Currently in treatment |
| Pt. Billed | 773 | Billed, pending resolution |
| Awaiting & Negotiating | 776 | Awaiting settlement |
| CLOSED | 772 | Fully closed cases |
| Finance | 781 | Settlements + collections |

**Firm-history data model:**
- `Law Firm Name` (text) — always the **current** firm only.
- `Firm History` (long_text, field IDs: 775=8526, 773=8527, 776=8528, 772=8529) — chain of past → current firms.
- Format: `OldFirm1 (until YYYY-MM-DD) -> OldFirm2 (until YYYY-MM-DD) -> CurrentFirm (current)`. Legacy entries (pre-2026-04-14) have no dates: `OldFirm -> CurrentFirm (current)`. Writes made via `PATCH /api/patients/{stage}/{id}/firm` add `(until <today>)` to the outgoing firm.
- To change a patient's lawyer, use the Edit button in the hub patient detail modal (autocompletes from T_ATT_VENUES=768). **Never edit `Law Firm Name` directly** — it bypasses history tracking.

### Staff / roles

| Table | ID | Notes |
|---|---|---|
| T_STAFF | 815 | `Email`, `Name`, `Role`, `Allowed Hubs` (multi-select driving per-hub access). 5-min in-memory cache in `hub/access.py`. |
| T_EVENTS | 816 | Marketing / external events |
| T_LEADS | 817 | Public lead-form submissions |

### Baserow field-format gotchas (bite-marks from past bugs)

1. **Single-select writes** take the **plain string value** (`"Open"`), not the dict form (`{"value": "Open"}`). Dict form returns `ERROR_REQUEST_BODY_VALIDATION`. (`{"value": ...}` / `{"id": ...}` shapes only appear in GET responses.)
2. **Link-row writes** take a plain list of integer IDs (`[123]`), not `[{"id": 123}]`.
3. **Cross-database link_rows are forbidden** (`ERROR_LINK_ROW_TABLE_NOT_IN_SAME_DATABASE`). The unified `Activities` table lives inside DB 197 because that's where Companies and Contacts live.
4. **Silent field drops:** PATCHing a field that doesn't exist on the table returns 200 but writes nothing. The Route Stops table hit this in 2026-04-14 (Notes / Completed At / Completed By) — always confirm field exists before wiring into an endpoint.
5. **Missing import trap:** 401 on a smoke-test curl only proves the auth guard runs, not the handler body. Verify every symbol referenced inside `modal_outreach_hub.py` has a matching import — a `NameError` otherwise only surfaces when a real user hits the page.
6. **Emoji above U+FFFF:** use the 8-digit `\U0001xxxx` form, never surrogate pairs (`\ud83d\udccd`). Python 3 on Modal's Linux runtime rejects surrogates when Starlette encodes the HTML response to UTF-8.

---

## Code Structure

Thin entry point (`modal_outreach_hub.py`) wires Modal + FastAPI; themed modules under `hub/` render pages.

```
execution/
├── modal_outreach_hub.py         ← Modal app, FastAPI routes, auth, Baserow proxy, sync layer
└── hub/
    ├── __init__.py
    │
    │   ── Infrastructure ──
    ├── shared.py                 ← thin facade — re-exports everything below for back-compat
    ├── constants.py              ← table IDs (T_*) + _TEMPLATES_JS email bodies
    ├── access.py                 ← _is_admin, _has_hub_access, _get_allowed_hubs, ALL_HUB_KEYS, _can_view_as
    ├── styles.py                 ← _CSS (desktop + mobile + light/dark) + _JS_SHARED template
    ├── nav.py                    ← _topnav — desktop top nav + hamburger drawer
    ├── compose.py                ← _COMPOSE_HTML / _COMPOSE_JS — email FAB overlay
    ├── shells.py                 ← _page / _forbidden_page / _tool_page
    │
    │   ── Feature pages ──
    ├── dashboard.py              ← _login_page, _hub_page, _calendar_page, _coming_soon_page
    ├── settings.py               ← _settings_page (profile + view-mode toggle)
    ├── outreach.py               ← _directory_page, _unified_directory_page, _map_page
    ├── pi_cases.py               ← _patients_page (rolodex + detail modal), _firms_page
    ├── billing.py                ← _billing_page
    ├── comms.py                  ← Companies Directory, _communications_email_page
    ├── contact_detail.py         ← legacy contact detail (now reads T_COMPANIES + T_ACTIVITIES)
    ├── company_detail.py         ← _company_detail_page (HubSpot-style; tabs, inline edit, linked People sidebar)
    ├── people.py                 ← _people_list_page, _person_detail_page
    ├── meetings.py               ← shared meeting_modal_html() + meeting_modal_js() for any page with "+ Schedule meeting"
    ├── tickets.py                ← _tickets_list_page, _ticket_detail_page
    ├── events.py                 ← _event_detail_page, _lead_form_page (public), _leads_dashboard_page
    ├── social.py                 ← _social_poster_hub_page, _social_schedule_page
    │
    │   ── Guerilla area ──
    ├── guerilla.py                ← GFR form helpers
    ├── guerilla_api.py            ← venue CRUD (reverse-syncs to Companies)
    ├── guerilla_map.py             ← _gorilla_map_page
    ├── guerilla_pages.py          ← log, events, businesses, boxes, routes
    └── route_planner.py           ← unified cross-tool map, outreach list
```

### Where does X live?

| Want to change… | Edit this file |
|---|---|
| CSS (colors, spacing, responsive) | `hub/styles.py` → `_CSS` |
| Shared JS helpers (`fetchAll`, `sv`, `esc`, `fmt`, `daysUntil`) | `hub/styles.py` → `_JS_SHARED` |
| Top nav / dropdowns | `hub/nav.py` → `_topnav` |
| Page shell | `hub/shells.py` → `_page` |
| Role / hub access rules | `hub/access.py` |
| Baserow table IDs | `hub/constants.py` |
| Command Center (`/`) | `hub/dashboard.py` → `_hub_page` |
| Calendar (`/calendar`) | `hub/dashboard.py` → `_calendar_page` + `_FULL_CAL_JS` |
| Meeting scheduler modal (reused on Company / Person / Calendar pages) | `hub/meetings.py` |
| Company detail (`/companies/{id}`) | `hub/company_detail.py` |
| People (`/people`, `/people/{id}`) | `hub/people.py` |
| Ticket pages | `hub/tickets.py` |
| Settings page | `hub/settings.py` |
| PI patient rolodex (`/patients`) | `hub/pi_cases.py` |
| Law firm ROI (`/firms`) | `hub/pi_cases.py` → `_firms_page` |
| Collections / settlements | `hub/billing.py` |
| Gmail thread view | `hub/comms.py` |
| Guerilla desktop sub-pages | `hub/guerilla_pages.py` |
| Venue create/update (forward + reverse sync) | `hub/guerilla_api.py`, `modal_outreach_hub.py` (`_mirror_to_legacy_venue`) |
| FastAPI routes, OAuth, Baserow proxy, session store | `modal_outreach_hub.py` |

### Import conventions

- New code should import **from the specific module** (`from .constants import T_COMPANIES`, `from .meetings import meeting_modal_html`) — easier to trace, keeps deps explicit.
- `hub/shared.py` is a thin facade that re-exports every public name; existing callers keep working unchanged.
- Dependency direction inside infrastructure (no cycles): `constants` → `access` / `styles` / `compose` → `nav` → `shells`. Feature pages depend on `shared` (or specific modules) but not on each other.

### Pattern for adding a new hub

1. Create tables (new DB if the domain is distinct) — use `execution/setup_tickets_tables.py` or `execution/setup_crm_tables.py` as a template (JWT auth via `BASEROW_EMAIL` / `BASEROW_PASSWORD`, workspace ID 133).
2. Add table IDs to `hub/constants.py` and re-export via `hub/shared.py`.
3. Add the hub key to `ALL_HUB_KEYS` in `hub/access.py`.
4. Add the hub key as a `value` on the T_STAFF `Allowed Hubs` multi-select field (Baserow field PATCH).
5. Write the page module in `hub/<name>.py`.
6. Register routes in `modal_outreach_hub.py`, gated by `_has_hub_access(user, '<key>')`.
7. Add a nav entry in `hub/nav.py` + `GROUP_MAP` entry for active-highlighting.
8. Optionally wire a KPI tile / quick link in `hub/dashboard.py` `_build_hub_body`.

---

## Design System

```css
/* Dark theme (default) */
--bg: #0d1b2a;          /* page background */
--bg2: #0a1628;         /* sidebar */
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
Overdue:  #ef4444
Today:    #f59e0b
Upcoming: #10b981
```

Light theme via `[data-theme="light"]` CSS variables + a toggle in the top nav.

---

## Auth

Google Workspace OAuth 2.0. Only accounts from `ALLOWED_DOMAIN` (`reformchiropractic.com`) can log in.

**Flow:** `/login` → Google consent → `/auth/google/callback` → session cookie → `/`.

**Session storage:** Modal Dict `hub-sessions`, keyed by random session ID in `hub_session` cookie (HttpOnly, 7-day, `samesite=lax`).

**CSRF:** Modal Dict `hub-oauth-states` with 5-minute TTL.

**Token refresh:** Access tokens refresh automatically on each page load if within 60s of expiry.

**OAuth scopes:** `openid email profile https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/calendar.events`.

> If you upgrade calendar scope from `.readonly` to `.events` (already done), existing users must sign out and back in once to grant the new permission.

### Modal Secrets Required

```bash
modal secret create outreach-hub-secrets \
  GOOGLE_CLIENT_ID=<HUB_CLIENT_ID from .env> \
  GOOGLE_CLIENT_SECRET=<HUB_CLIENT_SECRET from .env> \
  ALLOWED_DOMAIN=reformchiropractic.com \
  BASEROW_URL=https://baserow.reformchiropractic.app \
  BASEROW_API_TOKEN=<BASEROW_API_TOKEN from .env> \
  GOOGLE_MAPS_API_KEY=<GOOGLE_MAPS_API_KEY from .env> \
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

> `GOOGLE_CALENDAR_EMBED_URL` / `CALENDAR_ID` are no longer consulted — the calendar reads each user's `primary` calendar, writes to `primary` too. A `?calendar_id=X` query override is supported in `/api/calendar/events` if you ever want a shared-calendar view.

### Google Cloud Console Setup (one-time)
1. Enable Gmail API + Calendar API.
2. OAuth Consent Screen → User Type: **Internal**.
3. OAuth 2.0 Client ID → Web application.
   - Authorized redirect URIs:
     - `https://hub.reformchiropractic.app/auth/google/callback`
     - `http://localhost:8000/auth/google/callback`

### ClickUp Integration (already configured)

Modal secret `clickup-api` contains `CLICKUP_API_KEY`. Optional env var `CLICKUP_DEFAULT_LIST_ID` sets a fallback list for `+ Add task` modals; users pick a list per-task via the list dropdown (persisted in browser localStorage).

### Twilio SMS Setup (pending — endpoints deployed, secret TBD)

SMS send + inbound webhook are wired at `/api/sms/send`, `/api/sms/webhook`, `/api/sms/thread`. Until the Twilio secret is attached, every endpoint returns 503 with a friendly hint and the UI shows a "not configured" banner in the Send SMS modal.

When you're ready to go live:

1. Create a Twilio account + provision a phone number.
2. Create the Modal secret:
   ```bash
   modal secret create twilio-api \
     TWILIO_ACCOUNT_SID=AC... \
     TWILIO_AUTH_TOKEN=... \
     TWILIO_FROM_NUMBER=+18325551234
   ```
3. Attach it to the hub app by adding `modal.Secret.from_name("twilio-api")` to the `secrets=[...]` list on the `@app.function` decorator in `execution/modal_outreach_hub.py` (`bunny-secrets` / `clickup-api` neighbors).
4. Redeploy: `$env:PYTHONUTF8="1"; modal deploy execution/modal_outreach_hub.py`.
5. In the Twilio console, configure the phone number's **A MESSAGE COMES IN** webhook:
   - URL: `https://hub.reformchiropractic.app/api/sms/webhook`
   - Method: `HTTP POST`
6. (Optional) For local testing without signature verification, set `TWILIO_SKIP_SIGNATURE=1` in the secret.

**Schema:** `T_SMS_MESSAGES=823` in DB 197 (CRM). Fields: Phone (primary), Direction, Body, Status, Twilio SID, From, Author, Error, Lead ID, Company link_row, Contact link_row, Created, Updated. Inbound webhook auto-links to any existing Company / Contact / Lead by phone suffix match (last 10 digits).

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

## Cloudflare Worker proxy (already configured)

Modal's custom domain requires a paid plan; a Cloudflare Worker proxies instead.

**DNS:** `CNAME hub → reformtechops--outreach-hub-web.modal.run` (Proxied / orange cloud)

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

> `redirect: "follow"` is required — `redirect: "manual"` drops `Set-Cookie` headers from opaque redirects, breaking auth.

---

## Field-rep site (separate surface)

Field reps no longer live inside this hub. Mobile `/m/*` routes were removed; field reps access their tooling via `routes.reformchiropractic.app` (a separate Coolify-hosted site that reads the guerilla venue / route / stop tables directly). If a rep is added to `Allowed Hubs` on T_STAFF they can also see a stripped-back version of the hub dashboard. Testing the rep-only view is done via the view-mode toggle on `/settings`.

---

## Troubleshooting

**Dashboard shows "—" everywhere / no data loads**
- Check browser console for fetch errors.
- Verify `BASEROW_API_TOKEN` in Modal secret is correct.
- Confirm Baserow is accessible.

**Login loop / login rejected**
- Verify `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` match the current GCP OAuth client.
- Clear browser cookies for the domain.

**Calendar page: "Calendar access expired"**
- Scope upgraded from `calendar.readonly` → `calendar.events`. Sign out and back in once to re-consent.

**All pages show 0 results / data not loading**
- Most likely: `BASEROW_API_TOKEN` missing or expired in `outreach-hub-secrets`. Regenerate the secret from `.env` using the full command above, then redeploy. Data cache TTL is 120s — after fix, data reappears within 2 minutes.

**"Google Maps API key not configured" on map pages**
- `GOOGLE_MAPS_API_KEY` not in `outreach-hub-secrets`. Recreate secret with `GOOGLE_MAPS_API_KEY` included.

**401 errors on Baserow fetch**
- `modal secret update outreach-hub-secrets BASEROW_API_TOKEN=<new_token>` (or recreate — Modal secrets don't support per-key update).

**Table IDs changed**
- Update `T_*` constants in `hub/constants.py`; redeploy.

**Unicode error on deploy (Windows)**
- Always use `$env:PYTHONUTF8="1"` before `modal deploy`.

**`UnicodeEncodeError: surrogates not allowed` at runtime (500 on page load)**
- Using surrogate-pair escapes for emoji inside Python strings. Use full Unicode scalar values instead — e.g. `\U0001f4cd` (📍), `\U0001f310` (🌐). Any emoji above U+FFFF must use the 8-digit form.
