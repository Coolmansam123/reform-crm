# Reform CRM — Next Features Plan

Scope: four clinic-specific features to add on top of the existing CRM + one outstanding infra
task (TikTok credentials). Each section is self-contained so they can ship in any order, but the
recommended build order mirrors the ROI ranking below.

Build order recommendation:
1. Case-Packet Generator (biggest cash-flow lever; bounded scope)
2. Review-Request Automation (trivial add on existing automation engine)
3. Patient Reactivation (reuses automation engine + leads pipeline)
4. Attorney Micro-Portal (net-new surface; read-only so low risk)
5. TikTok Secrets Population (infra housekeeping — can happen anytime the creds are ready)

---

## 1. Attorney Case-Packet Generator

**Goal.** One-click PDF that summarizes a PI patient for the referring attorney:
treatment timeline, bills, narrative, contact info. Cuts down on "what's the update on X?"
calls and accelerates settlement.

**Reused primitives.**
- T_PI_ACTIVE (775), T_PI_BILLED (773), T_PI_CLOSED (772) — patient rows with case data
- T_PI_FINANCE (781) — billed charges / CPT codes / totals per patient
- Firm History field on patient rows (already shipped 2026-04-14 — see memory)
- Gmail send infra in `send_due_sequence_steps` (refresh_token per staff in `hub-sessions`)
- Existing `_log_activity()` helper so every generated packet shows up on the patient's timeline

**What to build.**
- `execution/hub/case_packets.py` — new module
  - `_packet_html(patient_id, br, bt)` renders full packet as HTML (date range, visit count,
    narrative, bill summary table, per-CPT breakdown, doctor contact block, firm banner)
  - `_packet_pdf(patient_id, br, bt)` wraps HTML → PDF using `weasyprint` (already in Modal image
    for the existing invoice flow — verify; if not, add `playwright` as a fallback since it's
    lighter to install than wkhtmltopdf)
- New API endpoints in `modal_outreach_hub.py`:
  - `GET /api/pi/{id}/packet.pdf` — renders + returns PDF bytes (inline `Content-Type: application/pdf`)
  - `POST /api/pi/{id}/packet/email` — body `{to, cc, subject, note}` → generates PDF, attaches,
    sends via user's Gmail refresh_token, logs an Activity row of kind `case_packet_sent` on the
    referring firm Company + the patient row
- UI: new "Case Packet" button on patient detail page:
  - "Download" → hits `packet.pdf`
  - "Email to Attorney" → modal with pre-filled `to:` = primary contact on Referring Attorney Company,
    pre-filled `subject:` = `Case Update — {patient_name} — {firm_name}`, editable note body

**Verification.**
1. `/patients/{id}` shows the Case Packet button for any patient with a Referring Attorney Company.
2. Clicking "Download" renders a PDF whose narrative + totals match what's in T_PI_FINANCE for that patient.
3. "Email to Attorney" sends a real email from the logged-in staff's Gmail with the PDF attached;
   the email appears in the user's Sent folder and an Activity row appears on both the firm and the patient.
4. An attorney Company's detail page shows the most recent case packets sent under its Activity tab.

**Edge cases.**
- Patient has no Referring Attorney Company → disable the "Email" button, "Download" still works
- Patient's bills table is empty → packet still renders but with "No billed charges yet"
- Firm has no primary contact → fallback to showing the button but require manual `to:` entry

---

## 2. Review-Request Automation

**Goal.** After a patient hits `Seen` (lead converted + first visit done), auto-send an SMS + email
asking for a Google review. PI referrals are influenced heavily by Google rating; this is the
single cheapest lever.

**Reused primitives.**
- Automations engine (`poll_social_inbox`… no wait, `send_due_sequence_steps`) — already dispatches
  `send_email` / `send_sms` / `wait` step types
- Trigger infrastructure `_fire_trigger()` already fires on lead stage transitions
- T_SEQUENCES / T_AUTOMATIONS (824) supports `lead_stage_changed` trigger with config `to:Seen`

**What to build.**
- No code. This is **configuration** — create one Automation row in Baserow:
  - Name: "Review Request — Post-First-Visit"
  - Trigger: `lead_stage_changed`
  - Trigger Config: `to:Seen`
  - Steps (JSON):
    ```json
    [
      {"type":"wait","delay_days":2},
      {"type":"send_sms","body":"Hi {name}! So glad we got to see you at Reform. If your visit went well, would you mind leaving us a quick Google review? {review_url} — Dr. {doctor}"},
      {"type":"wait","delay_days":5},
      {"type":"send_email","subject":"Quick favor from Reform Chiropractic","body":"Hi {name},\\n\\nIf your visit with us went well, a short Google review helps our practice enormously: {review_url}.\\n\\nThank you!\\n\\nReform Chiropractic"}
    ]
    ```
- Small code touch: extend the automation step-runner's variable substitution to include
  `{review_url}` (env var `GOOGLE_REVIEW_URL` → `https://g.page/r/...`) and `{doctor}` (lookup on
  the patient's assigned practitioner field, fallback `"the team"`).

**Verification.**
1. Manually flip a test lead to stage `Seen`; confirm a row appears in Automation Runs with status
   `active` and `Next Send At` = now + 2 days.
2. Fast-forward by setting `Next Send At` to now; run `send_due_sequence_steps` manually; confirm
   the SMS lands on the phone and appears in SMS Messages table.
3. After 5 more days, the email fires; confirms the run advances to `completed`.

---

## 3. Patient Reactivation

**Goal.** Any PI patient with no Activity in 14 days drops into a follow-up automation. Prevents
cases going cold without anyone noticing. Particularly valuable for Awaiting-settlement patients
who stop responding.

**Reused primitives.**
- T_ACTIVITIES (822) linked to Company (patient's firm) — we can derive "last activity on this patient"
  by scanning activities whose `Subject Type = patient` and `Subject ID = {pid}` (add those fields
  to T_ACTIVITIES if not already there — check before expanding)
- `poll_social_inbox` scheduler pattern — new scheduled function `scan_stale_patients` runs once daily
- Automation trigger `lead_stage_changed` already works; need a new trigger `patient_stale` for this flow

**What to build.**
- `execution/hub/reactivation.py` OR just add to `modal_outreach_hub.py`:
  - Scheduled function `scan_stale_patients` (modal.Cron daily 9am Pacific):
    - For each row in T_PI_ACTIVE: find newest Activity row where `Patient ID = id`.
    - If newest > 14 days ago AND patient is not Status=Closed → `_fire_trigger("patient_stale", "patient", pid, ..., config_match="")`
    - Dedupe: write `hub_cache["reactivation-fired:{pid}:{YYYY-MM}"] = true` to avoid re-firing
      the same patient within a month
- Extend `_fire_trigger` to accept `patient_stale` as a valid trigger key
- Extend the Automation schema's `Trigger` single_select with `patient_stale` option
  (update `setup_automations_schema.py` to add the option idempotently)
- Seed one Automation row:
  - Name: "Patient Reactivation — 14-day stall"
  - Trigger: `patient_stale`
  - Steps: `create_task` (ClickUp task for the patient's doctor, title "Reach out to {patient_name} — no activity in 14 days") + `wait 3 days` + `send_sms` follow-up nudge to patient

**Verification.**
1. Artificially age a test patient's last activity to 15 days ago, run `scan_stale_patients` manually.
2. Confirm ClickUp task appears, assigned to the patient's doctor, with the patient's link in the description.
3. Confirm the dedupe cache key prevents re-firing on a second manual run in the same month.

---

## 4. Attorney Micro-Portal

**Goal.** Read-only URL per referring firm showing their active patients' treatment status + last
note. Saves inbound "what's the update on X" calls; strengthens the referral relationship; zero
authentication needed for attorneys (URL is the auth).

**Reused primitives.**
- T_COMPANIES (820) — attorney firms are rows with `Category=Attorney`
- T_PI_ACTIVE / T_PI_BILLED / T_PI_AWAITING / T_PI_CLOSED — patient rows link to their firm
- `_page()` shell renders without hub nav if we pass a custom shell
- Public `/book` pattern (booking.py) already demonstrates a public, non-authenticated route

**What to build.**
- Add `Portal Slug` field on T_COMPANIES (short URL-safe string, e.g. "duque-price", unique) —
  idempotent schema script; auto-generate from Company name on save if blank
- Add `Portal Enabled` boolean field on T_COMPANIES (default false; admin toggles per firm)
- `execution/hub/attorney_portal.py`:
  - `_portal_page(slug, br, bt)` renders a branded page (Reform header, firm name, date of last update)
  - Lists patients where `Referring Attorney = firm_id` AND Status ∈ {Active, Awaiting, Billed, Closed}
  - Each patient row: name, case status pill, last 3 treatment-related activities (de-identified if
    possible — show activity kind + date, hide clinical notes unless we add a "shareable" flag)
  - "Request case packet" button on each row → emails staff (doesn't grant download to attorney directly)
- Route: `GET /a/{slug}` (gated by `Portal Enabled`, 404 otherwise; no auth)
- Admin toggle: on `/companies/{id}` detail for attorney firms, add a "Portal" section with enable
  toggle + copyable URL

**Verification.**
1. Enable portal on a test firm; visit `/a/{slug}` in incognito — loads without login.
2. Only that firm's patients appear; disabling the portal returns 404.
3. URL is guessable only if you know the slug — no sensitive IDs in the URL.

**Open questions for the user before building.**
- Privacy comfort: is showing last-visit dates + activity kinds OK, or do we need to de-identify
  (e.g. patient initials only)? Affects what we can show in the UI.
- Should the portal include a "case packet download" button for the attorney themselves, or does
  that stay staff-only (matching feature #1)?

---

## 5. TikTok Secrets Population (infra housekeeping)

**Goal.** Make the already-deployed TikTok engagement-digest poller actually emit rows.

**Current state.** Code in `poll_social_inbox` is deployed and runs every 15 min. The
`tiktok-secrets` Modal secret has the right variable names (`TIKTOK_CLIENT_KEY`,
`TIKTOK_CLIENT_SECRET`, `TIKTOK_ACCESS_TOKEN`, `TIKTOK_REFRESH_TOKEN`) but all values are empty strings.

**What to do.**
1. At https://developers.tiktok.com → Reform Chiropractic app → Settings → copy `client_key` and `client_secret`.
2. Generate a `refresh_token` once via TikTok's authorization-code flow:
   - Scopes needed for engagement digest: `user.info.basic`, `video.list`
   - Redirect URI must match whatever is registered on the TikTok app (if no redirect is registered, register a hub URL first, e.g. `https://hub.reformchiropractic.app/oauth/tiktok/callback`)
   - Write a one-off `execution/setup_tiktok_oauth.py` that takes the code from the redirect URL,
     calls `POST https://open.tiktokapis.com/v2/oauth/token/` with `grant_type=authorization_code`,
     prints the `refresh_token` (valid 365 days) for pasting into the Modal secret
3. Paste `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN` into the `tiktok-secrets`
   Modal secret via the dashboard. `TIKTOK_ACCESS_TOKEN` can stay empty — the poller refreshes
   on every run.
4. No redeploy needed — scheduled function picks up new env on next invocation.
5. First poll seeds baseline snapshots in `hub_cache["tt-video-snap"]`; second poll (15 min later)
   starts emitting digest rows.

**Verification.**
1. `modal run execution/modal_outreach_hub.py::poll_social_inbox` after secrets are populated;
   log should print `connected=3` (FB + IG + TT) and no error lines for TT.
2. Wait 15+ min, re-run; if any TikTok video gained views/likes/comments, a `tt:digest:{video_id}:{date}`
   row should appear in the Social Notifications table and show up under the "Engagement" kind
   in `/social/inbox`.

**Why this is last.** Purely infrastructure — no new user-facing code. Can be done by anyone
with access to the Modal dashboard + TikTok developer portal in 15 minutes.

---

## Estimated effort (rough)

| Feature | Design | Code | Total |
|---|---|---|---|
| 1. Case-Packet Generator | 1 day | 3 days | ~4 days |
| 2. Review-Request Automation | — | half day | half day |
| 3. Patient Reactivation | half day | 1 day | 1.5 days |
| 4. Attorney Micro-Portal | 1 day | 2 days | 3 days |
| 5. TikTok Secrets | — | 30 min | 30 min |

Total ≈ 9 working days if done sequentially. The Review-Request + TikTok items can be knocked out
in a single short session whenever there's capacity.
