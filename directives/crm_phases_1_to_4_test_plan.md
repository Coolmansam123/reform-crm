# CRM Phases 1-4 — Test Plan

Shipped 2026-04-22. All four features deployed to production hub.
Run these tests before announcing any of them to staff.

## Precheck (run once, top of session)

- [ ] You can log in at https://hub.reformchiropractic.app and see your own user email top-right
- [ ] Your phone is reachable (SMS tests)
- [ ] Your personal Gmail is accessible (email tests)
- [ ] Know a real PI patient you can safely mark as a test case, or create a dummy one in T_PI_ACTIVE

---

## Phase 1 — Case Packet email-to-attorney

**What's new:** "✉️ Email to Attorney" button next to the existing "Download Case Packet" on the PI patient detail modal.

### Regression check (download still works)
1. Open Patients → any PI patient → detail modal
2. Click **"📄 Download Case Packet"**
3. PDF opens in a new tab, renders the patient's info + financial table
4. **Pass criteria:** PDF loads without error and the patient's name/visits/firm match Baserow.

### New flow: email composer
5. On the same patient, click **"✉️ Email to Attorney"** (new button, right of Download).
6. The compose overlay opens. Verify:
   - **Subject** is prefilled: `Case Update — {patient name} — {firm name}`
   - **To** is prefilled if that firm has `Email` on its T_COMPANIES row, OR if a linked contact has an Email. Hint text below shows where it came from.
   - If no match: To is empty and hint says `No email on file for {firm} — please enter one`.
7. Edit the **To** field to your own email (so the real attorney doesn't get a test message).
8. Type a short note in the Note field.
9. Click **Send**.
10. Overlay shows `✓ Sent.` and auto-closes after ~1 second.

### Verify delivery + audit trail
11. Check your Gmail **Sent** folder (from the address you logged in with). Should contain the test email **with the PDF attached** (filename like `Reform_CasePacket_{patient}_2026-04-22.pdf`).
12. Check your own inbox — email arrives.
13. Open the **CRM → the attorney firm's company page**. In the Activity feed, you should see a new entry:
    - **Kind:** `user_activity`
    - **Type:** `Case Packet Sent`
    - **Summary:** `{your name} emailed case packet for {patient} to {your email}`

### Edge cases
- [ ] Patient with **no firm set** → overlay still opens, To is empty, subject omits firm. Still sendable.
- [ ] Firm name doesn't match any Company row → overlay still opens, To is empty, hint says "No email on file".
- [ ] Click Send with an invalid `To` (e.g. no `@`) → error message below button, overlay stays open.

### Rollback
If something is broken: the feature is behind the button — just don't click it. No automatic triggers.

---

## Phase 2 — Review-Request Automation

**What's new:** Automation in Baserow row #3 (T_SEQUENCES). Fires when a lead transitions to `Seen`. 2-day wait → SMS → 5-day wait → email. Currently **draft (Is Active = false)**.

### Setup for testing
1. Open Baserow → `Reform Chiropractic CRM` database → **Automations** table.
2. Find row: `Review Request — Post-First-Visit`.
3. Confirm:
   - `Trigger` = `lead_stage_changed`
   - `Trigger Config` = `to:Seen`
   - `Steps JSON` contains 4 steps: wait 2 → send_sms → wait 5 → send_email
   - `Is Active` = **false**
4. Flip `Is Active` to **true**.

### Test — manual trigger (skip the 2-day wait)
5. Pick a test lead in T_LEADS (or create one): set `Name`, `Phone` (**use your own number**), `Email` (your email), and `Owner` (e.g. `Dr. Cisneros`).
6. Change that lead's `Status` to `Seen` in Baserow. This fires `_fire_trigger("lead_stage_changed", config_match="to:Seen")`.
7. Go to the **Automation Runs** table. A new row should appear:
   - `Recipient Name/Email/Phone` match your test lead
   - `Sequence` links to the Review Request automation
   - `Status` = `active`
   - `Next Send At` ≈ now + 2 days (because step 0 is a `wait 2` step)
   - `Current Step` = 1 (because the wait advances immediately)
8. **Fast-forward:** edit that run's `Next Send At` to **right now** (or a minute ago).
9. Run the step runner manually:
   ```powershell
   cd "c:\Users\crazy\Reform Workspace"
   $env:PYTHONUTF8="1"
   modal run execution/modal_outreach_hub.py::send_due_sequence_steps
   ```
10. **Pass criteria:** You receive the SMS on your phone within ~30 seconds. Message text should have real values (not literal `{first_name}` strings):
    > Hi {first name}! So glad we got to see you at Reform. If your visit went well, would you mind leaving us a quick Google review? https://g.page/r/CQa_gQAJ77iMEAE/review — {owner or "the team"}

### Verify email leg (optional, 5 days later OR fast-forward)
11. Edit the same run's `Next Send At` to now again → runner sends the email.
12. Check your inbox for the Review Request email. Body should have the real review URL inline.

### Rollback
Flip `Is Active` back to **false** in Baserow. Scheduler immediately stops enrolling new leads. Existing runs complete or can be set to `unenrolled` manually.

---

## Phase 3 — Patient Reactivation

**What's new:** Daily 9am Pacific cron `scan_stale_patients`. Finds PI patients with `Follow-Up Date > 14 days ago` and fires a `patient_stale` trigger. Automation row #4 (`Patient Reactivation — 14-day stall`) is draft-inactive.

### Setup
1. Open Baserow → `Reform Chiropractic CRM` → **Automations**.
2. Find row `Patient Reactivation — 14-day stall`. Confirm:
   - `Trigger` = `patient_stale`
   - Steps = 1 step, send_sms only
   - `Is Active` = **false**
3. Flip `Is Active` to **true**.

### Test
4. Pick a test patient in `T_PI_ACTIVE` (775). Update:
   - `Follow-Up Date` → a date **at least 15 days ago** (e.g. `2026-04-01`)
   - `Phone` → **your own phone number** (you'll get the SMS)
   - `Name` → something recognizable like `Test Stale Patient`
5. Manually run the scanner:
   ```powershell
   modal run execution/modal_outreach_hub.py::scan_stale_patients
   ```
6. Output should log something like `[stale-patients] scanned=N stale=1 runs_created=1`.
7. Open the **Automation Runs** table. Verify the new row:
   - `Recipient Name` = your test patient's name
   - `Recipient Phone` = **populated** (new field)
   - `Sequence` links to Patient Reactivation
   - `Status` = `active`, `Next Send At` ≈ now
8. Run the step runner:
   ```powershell
   modal run execution/modal_outreach_hub.py::send_due_sequence_steps
   ```
9. **Pass criteria:** SMS arrives on your phone. Message should have real values.

### Idempotence check
10. Run `scan_stale_patients` again immediately. Output should say `stale=0` (same patient already fired this month — dedupe key in hub_cache).
11. **Pass criteria:** No duplicate enrollment created.

### Rollback
Flip `Is Active` back to **false**. Scan still runs daily but finds no matching automation → does nothing.

---

## Phase 4 — Attorney Micro-Portal

**What's new:** Public URL per attorney firm at `/a/{slug}`. Shows that firm's Reform patients + status + "Request Case Packet" button. No login. Admin enables per-firm in the CRM.

### Setup — enable portal on a test firm
1. Open the CRM → **Companies** → pick an **attorney-category** firm that has a few PI patients.
2. In the right column, scroll to the new **"🔗 Attorney Portal"** card (only appears for attorney companies).
3. Flip the **Enabled** toggle to On.
4. A public URL appears, like `https://hub.reformchiropractic.app/a/Xy7abc123_KlmNo`. Copy it.

### Test — attorney view
5. Open the URL in an **incognito window** (to simulate an attorney with no Reform session).
6. **Pass criteria:**
   - Splash overlay appears once: "Confidential Medical Information". Dismiss it.
   - Firm name shown in header.
   - Summary row shows counts by stage (Active / Awaiting / Billed).
   - Patient cards list the firm's patients only — no patients from any other firm.
   - Each card shows: full patient name, stage pill, DOI, visit count, follow-up date.
   - Mobile-responsive: resize browser to phone width — layout stays readable.

### Test — request case packet button
7. On a patient card, click **"Request Case Packet"**.
8. Button changes to `✓ Staff notified`. No email is sent to the attorney.
9. Back in the CRM, open that firm's company detail page. In the Activity feed, a new entry:
   - **Type:** `Case Packet Requested`
   - **Summary:** `Attorney-portal visitor requested a case packet for '{patient name}' (patient id: N). Follow up via /patients to send.`
   - **Author:** `attorney-portal`

### Test — view analytics
10. Refresh the incognito portal page twice.
11. Back in the CRM → the firm's company detail → the "Attorney Portal" card: `Views` counter should have incremented. `Last viewed` timestamp updates.

### Test — disable + re-enable
12. Flip the **Enabled** toggle off.
13. Refresh the incognito URL → **404 "Page not found"**.
14. Flip back on. Refresh → portal loads again (same slug).

### Test — regenerate URL
15. Click **Regenerate URL**. Confirm the dialog.
16. Old URL in the incognito window → 404 on refresh.
17. The card shows the new URL. Load it in incognito → portal loads.

### Edge cases
- [ ] Firm with no patients at all → portal loads, shows `No active cases right now`.
- [ ] Firm name mismatch between Company `Name` and patient's `Law Firm Name ONLY` → the patient won't appear in the portal. Normalizer handles punctuation/LLP/LLC suffixes but can miss creative variants. Fix by making names match in Baserow.
- [ ] Request-packet button spammed 3× quickly → second+ clicks return `429 slow down` (rate limit = 1 per 20s per slug).

### Rollback
Flip **Enabled** off on affected firms. Portal 404s instantly. No data migration needed.

---

## Summary: Expected results across all 4 phases

| Feature | State after testing | Confidence to flip live |
|---|---|---|
| Case Packet email | Always-on (no flag). Regression tested. | High — tested end-to-end. |
| Review Request automation | Baserow Is Active | Medium — keep in draft until first test SMS received. |
| Patient Reactivation | Baserow Is Active | Medium — verify dedupe + phone lookup with one test run. |
| Attorney Portal | Per-firm toggle | High — enable on one test firm first. |

## Known issues / follow-ups

- Attorney portal firm match is normalized text comparison — long-term fix is a link_row between patient rows and T_COMPANIES.
- Packet-request button logs a CRM activity but doesn't push a notification. v1.1 could fire an email to techops via an automation trigger.
- Review Request automation uses `{first_name}`, `{review_url}`, `{doctor}` — if a lead has no `Owner`, `{doctor}` falls back to `"the team"`.
