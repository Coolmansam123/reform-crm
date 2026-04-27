#!/usr/bin/env python3
"""
Outreach Hub — Modal FastAPI app.
Google OAuth-protected dashboard for PI Attorney, Guerilla Marketing, Community Outreach.

Deploy:
    $env:PYTHONUTF8="1"
    modal deploy execution/modal_outreach_hub.py

Requires Modal secret "outreach-hub-secrets":
    GOOGLE_CLIENT_ID=<from GCP>
    GOOGLE_CLIENT_SECRET=<from GCP>
    ALLOWED_DOMAIN=reformchiropractic.com
    BASEROW_URL=https://baserow.reformchiropractic.app
    BASEROW_API_TOKEN=<token>
"""

import os
import secrets
import time
from datetime import datetime, timezone, date
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
import modal

# Ensure hub package is importable at deploy time
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent))

from hub.shared import (
    _tool_page, _has_social_access, ALL_HUB_KEYS, _can_view_as,
    _has_hub_access, _is_admin, _get_allowed_hubs, _forbidden_page,
    T_ATT_VENUES, T_ATT_ACTS, T_GOR_VENUES, T_GOR_ACTS, T_GOR_BOXES,
    T_COM_VENUES, T_COM_ACTS, T_GOR_ROUTES, T_GOR_ROUTE_STOPS,
    T_PI_ACTIVE, T_PI_BILLED, T_PI_AWAITING, T_PI_CLOSED, T_PI_FINANCE,
    T_STAFF, T_EVENTS, T_LEADS, T_TICKETS, T_TICKET_COMMENTS,
    T_COMPANIES, T_CONTACTS, T_ACTIVITIES, T_SMS_MESSAGES,
    T_SEQUENCES, T_SEQUENCE_ENROLLMENTS, T_SOCIAL_NOTIFICATIONS,
    LEAD_STAGES, OPEN_LEAD_STAGES, CLOSED_LEAD_STAGES,
)
from hub.guerilla_map import _gorilla_map_page
from hub.route_planner import _route_planner_page, _outreach_list_page
from hub.guerilla_pages import (
    _gorilla_log_page,
    _gorilla_events_internal_page, _gorilla_events_external_page,
    _gorilla_businesses_page, _gorilla_boxes_page,
    _gorilla_routes_page, _gorilla_routes_new_page,
)
from hub.dashboard import _login_page, _hub_page, _calendar_page, _coming_soon_page
from hub.settings import _settings_page
from hub.tickets import _tickets_list_page, _ticket_detail_page
from hub.leads import _leads_list_page, _lead_detail_page
from hub.tasks import _tasks_page
from hub.inbox import _inbox_page
from hub.sequences import _sequences_list_page, _sequence_detail_page
from hub import clickup as _cu
from hub import sms as _sms
from hub.company_detail import _company_detail_page
from hub.people import _people_list_page, _person_detail_page
from hub.outreach import _directory_page, _unified_directory_page, _map_page
from hub.pi_cases import _patients_page, _firms_page
from hub.billing import _billing_page
from hub.comms import _contacts_page, _communications_email_page
from hub.social import _social_schedule_page, _social_monitor_page, _social_inbox_page
from hub.events import _event_detail_page, _lead_form_page, _leads_dashboard_page, _events_index_page
from hub import guerilla_api

app = modal.App("outreach-hub")
image = (
    modal.Image.debian_slim()
    .apt_install("libpango-1.0-0", "libpangoft2-1.0-0", "libcairo2", "libfontconfig1")
    .pip_install("fastapi[standard]", "python-multipart", "httpx", "weasyprint", "openai==1.59.*", "pywebpush==2.0.*")
    .add_local_python_source("hub")
)

# ─── Session / OAuth state stores ──────────────────────────────────────────────
hub_sessions     = modal.Dict.from_name("hub-sessions",     create_if_missing=True)
hub_oauth_states = modal.Dict.from_name("hub-oauth-states", create_if_missing=True)
hub_cache        = modal.Dict.from_name("hub-cache",        create_if_missing=True)

CACHE_TTL = 120  # seconds — all tables cached for 2 minutes

# ─── Table cache helpers ───────────────────────────────────────────────────────
async def _fetch_table_all(br: str, bt: str, tid: int) -> list:
    """Fetch all rows for a table using parallel page requests."""
    import asyncio
    headers = {"Authorization": f"Token {bt}"}
    base_url = f"{br}/api/database/rows/table/{tid}/?size=200&user_field_names=true&page="
    async with __import__("httpx").AsyncClient(timeout=30) as client:
        r1 = await client.get(base_url + "1", headers=headers)
        if not r1.is_success:
            return []
        d1 = r1.json()
        rows = list(d1.get("results", []))
        if not d1.get("next"):
            return rows
        total_pages = (d1.get("count", 0) + 199) // 200
        resps = await asyncio.gather(*[
            client.get(base_url + str(p), headers=headers)
            for p in range(2, total_pages + 1)
        ])
        for resp in resps:
            if resp.is_success:
                rows.extend(resp.json().get("results", []))
    return rows

async def _cached_table(tid: int, br: str, bt: str) -> list:
    key = f"table:{tid}"
    try:
        cached = hub_cache.get(key)
        if cached and (time.time() - cached.get("ts", 0)) < CACHE_TTL:
            return cached["data"]
    except Exception:
        pass
    rows = await _fetch_table_all(br, bt, tid)
    try:
        hub_cache[key] = {"data": rows, "ts": time.time()}
    except Exception:
        pass
    return rows

# ─── Auth ──────────────────────────────────────────────────────────────────────
SESSION_COOKIE = "hub_session"

def _get_session(req) -> dict | None:
    sid = req.cookies.get(SESSION_COOKIE)
    if not sid:
        return None
    return hub_sessions.get(sid)

def _ok(req) -> bool:
    return _get_session(req) is not None

def _get_user(req) -> dict:
    return _get_session(req) or {}


# ──────────────────────────────────────────────────────────────────────────────
# BACKGROUND CACHE WARMER — keeps dashboard tables always fresh
# ──────────────────────────────────────────────────────────────────────────────
_WARM_TABLES = [
    T_ATT_VENUES, T_GOR_VENUES, T_COM_VENUES,
    T_PI_ACTIVE, T_PI_BILLED, T_PI_AWAITING, T_PI_CLOSED,
    T_GOR_BOXES, T_GOR_ROUTES, T_GOR_ROUTE_STOPS, T_GOR_ACTS,
]

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("outreach-hub-secrets")],
    schedule=modal.Period(seconds=90),
    timeout=120,
)
async def warm_cache():
    import asyncio
    br = os.environ.get("BASEROW_URL", "")
    bt = os.environ.get("BASEROW_API_TOKEN", "")
    if not br or not bt:
        return
    results = await asyncio.gather(*[
        _fetch_table_all(br, bt, tid) for tid in _WARM_TABLES
    ])
    for tid, rows in zip(_WARM_TABLES, results):
        try:
            hub_cache[f"table:{tid}"] = {"data": rows, "ts": time.time()}
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# EMAIL-SEQUENCE SENDER — runs every 15 min, sends due steps
# ──────────────────────────────────────────────────────────────────────────────
@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("outreach-hub-secrets"),
        modal.Secret.from_name("review-secrets"),
    ],
    schedule=modal.Period(minutes=15),
    timeout=300,
)
async def send_due_sequence_steps():
    """Automation scheduler. Finds active Runs whose `Next Send At` has
    passed, executes the current step by type (send_email / send_sms /
    create_task / update_lead / wait), then advances the Run. Backward-
    compatible: steps missing a `type` default to `send_email`."""
    import base64
    import email as _emaillib
    import json as _json
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    from hub import sms as _sms_mod
    from hub import clickup as _cu_mod

    br = os.environ.get("BASEROW_URL", "")
    bt = os.environ.get("BASEROW_API_TOKEN", "")
    if not br or not bt or not T_SEQUENCES or not T_SEQUENCE_ENROLLMENTS:
        return

    # Index session refresh tokens by email (for send_email steps)
    senders = {}
    try:
        for _sid, sess in hub_sessions.items():
            em = (sess.get("email") or "").lower()
            rt = sess.get("refresh_token", "")
            if em and rt:
                senders[em] = {
                    "refresh_token": rt,
                    "name":          sess.get("name", ""),
                }
    except Exception as e:
        print(f"[automations] failed to iterate sessions: {e}")
        return

    autos = await _fetch_table_all(br, bt, T_SEQUENCES)
    runs = await _fetch_table_all(br, bt, T_SEQUENCE_ENROLLMENTS)
    auto_by_id = {a["id"]: a for a in autos}

    def _sel(v):
        if isinstance(v, dict): return v.get("value", "") or ""
        return v or ""
    def _links(v):
        return [x.get("id") if isinstance(x, dict) else x for x in (v or [])]

    now = _dt.now(_tz.utc)
    now_iso = now.isoformat()

    def _iso_now():
        return _dt.now(_tz.utc).isoformat()

    due = [
        e for e in runs
        if _sel(e.get("Status")) == "active"
        and (e.get("Next Send At") or "") <= now_iso
    ]
    if not due:
        return

    gid = os.environ.get("GOOGLE_CLIENT_ID", "")
    gsecret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    cu_key  = os.environ.get("CLICKUP_API_KEY", "")

    async def _refresh_token(refresh_token: str) -> str:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post("https://oauth2.googleapis.com/token", data={
                "client_id":     gid,
                "client_secret": gsecret,
                "refresh_token": refresh_token,
                "grant_type":    "refresh_token",
            })
        return r.json().get("access_token", "") if r.status_code == 200 else ""

    async def _gmail_send(access_token: str, to_email: str,
                           from_email: str, subject: str, body: str,
                           cc_email: str = "",
                           attachment: tuple = None) -> dict:
        """Send via Gmail API. Optional cc + binary attachment (filename, bytes)."""
        msg = _emaillib.message.EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = from_email, to_email, subject
        if cc_email:
            msg["Cc"] = cc_email
        msg.set_content(body)
        if attachment:
            fname, data = attachment
            maintype, subtype = "application", "pdf"
            if not fname.lower().endswith(".pdf"):
                maintype, subtype = "application", "octet-stream"
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=fname)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"raw": raw},
            )
        if r.status_code in (200, 201):
            return {"ok": True, "id": r.json().get("id", "")}
        try: detail = r.json()
        except: detail = {"raw": r.text[:300]}
        return {"ok": False, "status": r.status_code, "error": detail}

    def _render(tpl: str, ctx: dict) -> str:
        out = tpl or ""
        for k, v in ctx.items():
            out = out.replace("{" + k + "}", str(v or ""))
        return out

    async def _patch_run(client, rid: int, patch: dict):
        await client.patch(
            f"{br}/api/database/rows/table/{T_SEQUENCE_ENROLLMENTS}/{rid}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
            json={**patch, "Updated": _iso_now()},
        )

    sent = failed = waited = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for run in due:
            auto_ids = _links(run.get("Sequence"))
            if not auto_ids: continue
            auto = auto_by_id.get(auto_ids[0])
            if not auto:
                await _patch_run(client, run["id"], {"Status": "failed", "Last Error": "automation not found"})
                failed += 1; continue
            if not auto.get("Is Active"):
                continue  # globally paused — leave for later

            try: steps = _json.loads(auto.get("Steps JSON") or "[]") or []
            except Exception: steps = []
            cur = int(run.get("Current Step") or 0)
            if cur >= len(steps):
                await _patch_run(client, run["id"], {"Status": "completed"})
                continue

            step = steps[cur]
            stype = (step.get("type") or "send_email").lower()

            # Build merge context once; each action uses subset
            r_email = (run.get("Recipient Email") or "").strip()
            r_name  = (run.get("Recipient Name")  or "").strip()
            first   = r_name.split(" ", 1)[0] if r_name else ""
            # Phone: prefer the value stored directly on the run (used by
            # scan_stale_patients for PI patients who aren't in T_LEADS),
            # fall back to resolving via Lead ID → T_LEADS for lead flows.
            r_phone = (run.get("Recipient Phone") or "").strip()
            r_doctor = ""
            lead_id = run.get("Lead ID") or 0
            if lead_id and T_LEADS:
                try:
                    lr = await client.get(
                        f"{br}/api/database/rows/table/{T_LEADS}/{int(lead_id)}/?user_field_names=true",
                        headers={"Authorization": f"Token {bt}"},
                    )
                    if lr.status_code == 200:
                        lead_row = lr.json()
                        if not r_phone:
                            r_phone = lead_row.get("Phone", "") or ""
                        r_doctor = (lead_row.get("Owner", "") or "").strip()
                except Exception: pass
            company_name = ""
            co_ids = _links(run.get("Company"))
            if co_ids:
                try:
                    cr = await client.get(
                        f"{br}/api/database/rows/table/{T_COMPANIES}/{co_ids[0]}/?user_field_names=true",
                        headers={"Authorization": f"Token {bt}"},
                    )
                    if cr.status_code == 200: company_name = cr.json().get("Name", "")
                except Exception: pass

            sender_email = (run.get("Sender Email") or "").lower()
            sender = senders.get(sender_email) if sender_email else None
            ctx = {
                "first_name":   first,
                "name":         r_name,
                "email":        r_email,
                "phone":        r_phone,
                "company":      company_name,
                "sender_name":  sender["name"] if sender else "",
                "sender_email": sender_email,
                "doctor":       r_doctor or "the team",
                "review_url":   os.environ.get("GOOGLE_REVIEW_URL", ""),
            }

            action_ok = False
            error = ""

            try:
                if stype == "wait":
                    action_ok = True
                    waited += 1

                elif stype == "send_email":
                    subj = _render(step.get("subject", ""), ctx)
                    body = _render(step.get("body", ""), ctx)
                    if not r_email or not subj:
                        error = "missing email or subject"
                    elif not sender:
                        error = f"no Gmail session for sender {sender_email or '(unset)'}"
                    else:
                        access = await _refresh_token(sender["refresh_token"])
                        if not access:
                            error = "refresh_token failed — sender needs to sign in again"
                        else:
                            result = await _gmail_send(access, r_email, sender_email, subj, body)
                            if result.get("ok"): action_ok = True
                            else:
                                st = result.get("status", 0)
                                prefix = "needs_reauth: " if st in (401, 403) else ""
                                error = f"{prefix}gmail {st}: {str(result.get('error'))[:200]}"

                elif stype == "send_sms":
                    body = _render(step.get("body", ""), ctx)
                    if not _sms_mod.is_configured():
                        error = "twilio not configured"
                    elif not r_phone:
                        error = "no recipient phone on run"
                    elif not body:
                        error = "missing SMS body"
                    else:
                        e164 = _sms_mod.normalize_phone(r_phone)
                        if not e164:
                            error = f"invalid phone {r_phone}"
                        else:
                            tw = await _sms_mod.send_sms(e164, body)
                            if tw.get("error"): error = f"twilio: {str(tw.get('error'))[:200]}"
                            else:
                                action_ok = True
                                # Log SMS row
                                if T_SMS_MESSAGES:
                                    try:
                                        await client.post(
                                            f"{br}/api/database/rows/table/{T_SMS_MESSAGES}/?user_field_names=true",
                                            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
                                            json={
                                                "Phone": e164, "Direction": "outbound",
                                                "Body": body, "Status": tw.get("status") or "sent",
                                                "Twilio SID": tw.get("sid", ""),
                                                "From": os.environ.get("TWILIO_FROM_NUMBER", ""),
                                                "Author": sender_email or "automation",
                                                "Lead ID": int(lead_id) if lead_id else None,
                                                "Created": _iso_now(), "Updated": _iso_now(),
                                            },
                                        )
                                    except Exception: pass

                elif stype == "create_task":
                    if not cu_key:
                        error = "clickup not configured"
                    else:
                        list_id = (step.get("list_id") or _cu_mod.CLICKUP_DEFAULT_LIST_ID or "").strip()
                        if not list_id:
                            error = "no ClickUp list_id on step and no CLICKUP_DEFAULT_LIST_ID"
                        else:
                            task_name = _render(step.get("name", ""), ctx) or f"Automation task — {r_name or r_email}"
                            desc      = _render(step.get("description", ""), ctx)
                            tags = []
                            if lead_id:          tags.append(_cu_mod.crm_tag("lead", int(lead_id)))
                            if co_ids:           tags.append(_cu_mod.crm_tag("company", co_ids[0]))
                            # Assignee = sender if they exist in ClickUp
                            assignees = []
                            if sender_email:
                                try:
                                    uinfo = await _cu_mod.resolve_user_by_email(cu_key, sender_email, client)
                                    if uinfo and uinfo.get("id"): assignees = [int(uinfo["id"])]
                                except Exception: pass
                            result = await _cu_mod.create_task(
                                cu_key, list_id, name=task_name, description=desc,
                                assignees=assignees, tags=tags or None,
                            )
                            if result.get("error"): error = f"clickup: {str(result.get('error'))[:200]}"
                            else: action_ok = True

                elif stype == "update_lead":
                    field = (step.get("field") or "").strip()
                    value = step.get("value")
                    if not lead_id:         error = "no lead on run"
                    elif not field:         error = "missing field"
                    elif not T_LEADS:       error = "leads table not configured"
                    else:
                        try:
                            await client.patch(
                                f"{br}/api/database/rows/table/{T_LEADS}/{int(lead_id)}/?user_field_names=true",
                                headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
                                json={field: value, "Updated": _iso_now()},
                            )
                            try: hub_cache.pop(f"table:{T_LEADS}", None)
                            except Exception: pass
                            action_ok = True
                        except Exception as e:
                            error = f"patch: {str(e)[:200]}"

                else:
                    error = f"unknown step type '{stype}'"

            except Exception as e:
                error = f"exception: {str(e)[:200]}"

            if not action_ok:
                status = "needs_reauth" if "needs_reauth" in error else "failed"
                await _patch_run(client, run["id"], {"Status": status, "Last Error": error[:500]})
                failed += 1
                continue

            # Advance
            new_cur = cur + 1
            patch = {"Current Step": new_cur, "Last Sent At": _iso_now(), "Last Error": ""}
            if new_cur >= len(steps):
                patch["Status"] = "completed"
                patch["Next Send At"] = None
            else:
                delay = int(steps[new_cur].get("delay_days", 0) or 0)
                patch["Next Send At"] = (_dt.now(_tz.utc) + _td(days=delay)).isoformat()
            await _patch_run(client, run["id"], patch)
            if stype != "wait": sent += 1

    try: hub_cache.pop(f"table:{T_SEQUENCE_ENROLLMENTS}", None)
    except Exception: pass
    print(f"[automations] acted={sent} waited={waited} failed={failed} due={len(due)}")


# ──────────────────────────────────────────────────────────────────────────────
# STALE PATIENT SCANNER — fires `patient_stale` trigger daily 9am Pacific
# ──────────────────────────────────────────────────────────────────────────────
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("outreach-hub-secrets")],
    schedule=modal.Cron("0 16 * * *"),  # 16:00 UTC = 9am PT (8am PDT)
    timeout=300,
)
async def scan_stale_patients():
    """Find PI patients with a Follow-Up Date more than 14 days in the past
    (and still in an open stage). For each active `patient_stale` automation,
    create an Automation Run. Deduped per-patient per-month via hub-cache so
    a patient only drops into the flow once in any 30-day window."""
    import httpx
    import json as _json
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz, date as _date

    br = os.environ.get("BASEROW_URL", "")
    bt = os.environ.get("BASEROW_API_TOKEN", "")
    if not br or not bt or not T_SEQUENCES or not T_SEQUENCE_ENROLLMENTS:
        print("[stale-patients] missing config; skipping")
        return

    STALE_DAYS = 14
    today = _date.today()
    month_key = today.strftime("%Y-%m")

    # Load automations with Trigger=patient_stale + Is Active
    autos = await _fetch_table_all(br, bt, T_SEQUENCES)
    def _sel(v):
        if isinstance(v, dict): return v.get("value", "") or ""
        return v or ""
    matches = [a for a in (autos or [])
               if a.get("Is Active") and _sel(a.get("Trigger")) == "patient_stale"]
    if not matches:
        print("[stale-patients] no active patient_stale automations; skipping scan")
        return

    # Scan Active + Awaiting + Billed (skip Closed by design)
    patients = []
    for tid, stage in [(T_PI_ACTIVE, "active"), (T_PI_AWAITING, "awaiting"), (T_PI_BILLED, "billed")]:
        rows = await _fetch_table_all(br, bt, tid) or []
        for r in rows:
            r["_stage"] = stage
        patients.extend(rows)

    stale = []
    for p in patients:
        fu = (p.get("Follow-Up Date") or p.get("Follow Up Date") or "").strip()
        if not fu: continue
        try:
            fu_date = _dt.fromisoformat(fu.replace("Z", "+00:00")).date() if "T" in fu else _dt.strptime(fu[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        if (today - fu_date).days < STALE_DAYS: continue
        pid = p.get("id")
        dedupe_key = f"reactivation-fired:{pid}:{month_key}"
        try:
            if hub_cache.get(dedupe_key): continue
        except Exception:
            pass
        stale.append(p)

    if not stale:
        print(f"[stale-patients] scanned={len(patients)} stale=0")
        return

    # For each stale patient × each matching automation → create an Automation Run
    headers_json = {"Authorization": f"Token {bt}", "Content-Type": "application/json"}
    now_iso = _dt.now(_tz.utc).isoformat()
    created = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for p in stale:
            pid = p.get("id")
            name = (p.get("Name") or "").strip() or f"Patient {pid}"
            email = (p.get("Email") or "").strip()
            phone = (p.get("Phone") or p.get("Cell Phone") or "").strip()
            for auto in matches:
                try: steps = _json.loads(auto.get("Steps JSON") or "[]") or []
                except Exception: steps = []
                if not steps: continue
                first_delay = int(steps[0].get("delay_days", 0) or 0)
                next_at = (_dt.now(_tz.utc) + _td(days=first_delay)).isoformat()
                row = {
                    "Name":            email or name,
                    "Recipient Email": email,
                    "Recipient Name":  name,
                    "Recipient Phone": phone,
                    "Sender Email":    os.environ.get("AUTOMATION_DEFAULT_SENDER", ""),
                    "Sequence":        [auto["id"]],
                    "Status":          "active",
                    "Current Step":    0,
                    "Next Send At":    next_at,
                    "Created":         now_iso,
                    "Updated":         now_iso,
                }
                try:
                    r = await client.post(
                        f"{br}/api/database/rows/table/{T_SEQUENCE_ENROLLMENTS}/?user_field_names=true",
                        headers=headers_json,
                        json={k: v for k, v in row.items() if v not in (None, "")},
                    )
                    if r.is_success: created += 1
                    else: print(f"[stale-patients] insert failed: {r.status_code} {r.text[:180]}")
                except Exception as e:
                    print(f"[stale-patients] insert err: {e}")
            try: hub_cache[f"reactivation-fired:{pid}:{month_key}"] = True
            except Exception: pass

    try: hub_cache.pop(f"table:{T_SEQUENCE_ENROLLMENTS}", None)
    except Exception: pass
    print(f"[stale-patients] scanned={len(patients)} stale={len(stale)} runs_created={created}")


# ──────────────────────────────────────────────────────────────────────────────
# OVERDUE FOLLOW-UP PUSH — daily 8am PT, push reps a count of stale leads
# ──────────────────────────────────────────────────────────────────────────────
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("outreach-hub-secrets")],
    schedule=modal.Cron("0 16 * * *"),  # 16:00 UTC = 8am PST / 9am PDT
    timeout=300,
)
async def notify_overdue_followups():
    """For each lead whose Status is still in an open stage and whose Created
    date is >3 days old, push a summary to the lead's Owner. One push per
    rep per day with count of stale leads."""
    from collections import defaultdict
    from datetime import date as _date, timedelta as _td

    br = os.environ.get("BASEROW_URL", "")
    bt = os.environ.get("BASEROW_API_TOKEN", "")
    if not br or not bt:
        print("[overdue-push] missing baserow config; skipping")
        return
    pub = os.environ.get("VAPID_PUBLIC_KEY", "")
    priv = os.environ.get("VAPID_PRIVATE_KEY", "")
    sub = os.environ.get("VAPID_SUBJECT", "mailto:techops@reformchiropractic.com")
    if not (pub and priv):
        print("[overdue-push] VAPID not configured; skipping")
        return

    leads = await _fetch_table_all(br, bt, T_LEADS)
    cutoff = _date.today() - _td(days=3)
    OPEN = {"New", "Contacted", "Appointment Scheduled", "Seen"}

    def _sv(v):
        if isinstance(v, dict): return (v.get("value") or v.get("name") or "")
        return v or ""

    by_owner: dict[str, int] = defaultdict(int)
    for L in leads or []:
        owner = (L.get("Owner") or "").strip().lower()
        if not owner: continue
        status = _sv(L.get("Status"))
        if status not in OPEN: continue
        created = (L.get("Created") or L.get("Date") or "")[:10]
        try:
            y, m, d = created.split("-")
            cd = _date(int(y), int(m), int(d))
        except Exception:
            continue
        if cd <= cutoff:
            by_owner[owner] += 1

    from hub.push import send_push_to_email
    sent_total = 0
    for owner, count in by_owner.items():
        title = "Reform — overdue follow-ups"
        body = f"{count} lead{'s' if count != 1 else ''} need a follow-up today."
        result = await send_push_to_email(
            br, bt, owner, title, body,
            url="/outreach",
            vapid_private_key_b64url=priv,
            vapid_public_key_b64url=pub,
            vapid_subject=sub,
        )
        sent_total += result.get("sent", 0)
    print(f"[overdue-push] reps_with_stale={len(by_owner)} pushes_sent={sent_total}")


# ──────────────────────────────────────────────────────────────────────────────
# SOCIAL INBOX POLLER — Facebook + Instagram comments/mentions/DMs every 15 min
# ──────────────────────────────────────────────────────────────────────────────
@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("outreach-hub-secrets"),
        modal.Secret.from_name("meta-secrets"),
        modal.Secret.from_name("tiktok-secrets"),
    ],
    schedule=modal.Period(minutes=15),
    timeout=300,
)
async def poll_social_inbox():
    """Poll Facebook Page + Instagram Business Account for new comments,
    mentions, and page messages (DMs). Upserts into T_SOCIAL_NOTIFICATIONS
    keyed on `Source ID` so re-runs are idempotent."""
    import httpx
    import json as _json

    br = os.environ.get("BASEROW_URL", "")
    bt = os.environ.get("BASEROW_API_TOKEN", "")
    page_id   = os.environ.get("META_PAGE_ID", "")
    page_tok  = os.environ.get("META_PAGE_TOKEN", "")
    ig_id     = os.environ.get("INSTAGRAM_ACCOUNT_ID", "")
    if not br or not bt or not T_SOCIAL_NOTIFICATIONS or not page_tok:
        print("[social-inbox] missing creds; skipping")
        return
    GRAPH = "https://graph.facebook.com/v22.0"
    headers = {"Authorization": f"Token {bt}"}

    # Existing Source IDs so we only POST net-new rows
    existing = set()
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            url = f"{br}/api/database/rows/table/{T_SOCIAL_NOTIFICATIONS}/?user_field_names=true&size=200"
            while url:
                r = await c.get(url, headers=headers)
                if not r.is_success: break
                j = r.json()
                for row in j.get("results", []):
                    sid = row.get("Source ID") or ""
                    if sid: existing.add(sid)
                url = j.get("next")
    except Exception as e:
        print(f"[social-inbox] preload failed: {e}")

    new_rows = []
    pages_connected = []
    if page_id: pages_connected.append({"platform": "facebook",  "id": page_id})
    if ig_id:   pages_connected.append({"platform": "instagram", "id": ig_id})
    tt_client_key    = os.environ.get("TIKTOK_CLIENT_KEY", "")
    tt_client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "")
    tt_refresh_token = os.environ.get("TIKTOK_REFRESH_TOKEN", "")
    if tt_client_key and tt_refresh_token:
        pages_connected.append({"platform": "tiktok", "id": "self"})

    async with httpx.AsyncClient(timeout=45) as c:
        # ── Facebook Page comments on recent posts ────────────────────────────
        if page_id:
            try:
                r = await c.get(
                    f"{GRAPH}/{page_id}/feed",
                    params={
                        "fields": "id,message,permalink_url,comments.limit(25){id,from,message,created_time,permalink_url}",
                        "limit": 25,
                        "access_token": page_tok,
                    },
                )
                if r.is_success:
                    for post in r.json().get("data", []):
                        post_url = post.get("permalink_url", "")
                        cap = (post.get("message") or "")[:120]
                        for cm in (post.get("comments") or {}).get("data", []):
                            sid = f"fb:comment:{cm.get('id')}"
                            if sid in existing: continue
                            frm = cm.get("from") or {}
                            new_rows.append({
                                "Source ID": sid,
                                "Platform": "facebook",
                                "Kind": "comment",
                                "Author Name": frm.get("name", ""),
                                "Author Handle": str(frm.get("id", "")),
                                "Body": cm.get("message", "") or "",
                                "Post URL": post_url,
                                "Post Caption": cap,
                                "Reply URL": cm.get("permalink_url", "") or post_url,
                                "Received At": cm.get("created_time", ""),
                                "Status": "unread",
                                "Metadata": _json.dumps(cm)[:4000],
                            })
                else:
                    print(f"[social-inbox] FB feed fetch failed: {r.status_code} {r.text[:200]}")
            except Exception as e:
                print(f"[social-inbox] FB feed error: {e}")

            # Page messages (DMs) — needs pages_messaging scope; skip silently if scope missing
            try:
                r = await c.get(
                    f"{GRAPH}/{page_id}/conversations",
                    params={
                        "fields": "id,messages.limit(5){id,from,message,created_time}",
                        "limit": 15,
                        "access_token": page_tok,
                    },
                )
                if r.is_success:
                    for conv in r.json().get("data", []):
                        for msg in (conv.get("messages") or {}).get("data", []):
                            frm = msg.get("from") or {}
                            if str(frm.get("id", "")) == str(page_id):
                                continue  # our own outgoing message
                            sid = f"fb:dm:{msg.get('id')}"
                            if sid in existing: continue
                            new_rows.append({
                                "Source ID": sid,
                                "Platform": "facebook",
                                "Kind": "dm",
                                "Author Name": frm.get("name", ""),
                                "Author Handle": frm.get("email", "") or str(frm.get("id", "")),
                                "Body": msg.get("message", "") or "",
                                "Post URL": "",
                                "Post Caption": "",
                                "Reply URL": f"https://www.facebook.com/messages/t/{frm.get('id', '')}",
                                "Received At": msg.get("created_time", ""),
                                "Status": "unread",
                                "Metadata": _json.dumps(msg)[:4000],
                            })
                else:
                    # Common: scope missing → 403 with useful message. Just log.
                    print(f"[social-inbox] FB DMs skipped: {r.status_code} {r.text[:180]}")
            except Exception as e:
                print(f"[social-inbox] FB DMs error: {e}")

        # ── Instagram Business comments on recent media ───────────────────────
        if ig_id:
            try:
                r = await c.get(
                    f"{GRAPH}/{ig_id}/media",
                    params={
                        "fields": "id,caption,permalink,timestamp,comments.limit(25){id,username,text,timestamp,replies.limit(10){id,username,text,timestamp}}",
                        "limit": 15,
                        "access_token": page_tok,
                    },
                )
                if r.is_success:
                    for post in r.json().get("data", []):
                        post_url = post.get("permalink", "")
                        cap = (post.get("caption") or "")[:120]
                        for cm in (post.get("comments") or {}).get("data", []):
                            sid = f"ig:comment:{cm.get('id')}"
                            if sid not in existing:
                                new_rows.append({
                                    "Source ID": sid,
                                    "Platform": "instagram",
                                    "Kind": "comment",
                                    "Author Name": cm.get("username", ""),
                                    "Author Handle": cm.get("username", ""),
                                    "Body": cm.get("text", "") or "",
                                    "Post URL": post_url,
                                    "Post Caption": cap,
                                    "Reply URL": post_url,
                                    "Received At": cm.get("timestamp", ""),
                                    "Status": "unread",
                                    "Metadata": _json.dumps(cm)[:4000],
                                })
                            for rp in (cm.get("replies") or {}).get("data", []):
                                rsid = f"ig:reply:{rp.get('id')}"
                                if rsid in existing: continue
                                new_rows.append({
                                    "Source ID": rsid,
                                    "Platform": "instagram",
                                    "Kind": "reply",
                                    "Author Name": rp.get("username", ""),
                                    "Author Handle": rp.get("username", ""),
                                    "Body": rp.get("text", "") or "",
                                    "Post URL": post_url,
                                    "Post Caption": cap,
                                    "Reply URL": post_url,
                                    "Received At": rp.get("timestamp", ""),
                                    "Status": "unread",
                                    "Metadata": _json.dumps(rp)[:4000],
                                })
                else:
                    print(f"[social-inbox] IG media fetch failed: {r.status_code} {r.text[:200]}")
            except Exception as e:
                print(f"[social-inbox] IG media error: {e}")

            # IG mentions (tags of our account)
            try:
                r = await c.get(
                    f"{GRAPH}/{ig_id}/tags",
                    params={
                        "fields": "id,caption,username,media_type,permalink,timestamp",
                        "limit": 25,
                        "access_token": page_tok,
                    },
                )
                if r.is_success:
                    for tg in r.json().get("data", []):
                        sid = f"ig:mention:{tg.get('id')}"
                        if sid in existing: continue
                        new_rows.append({
                            "Source ID": sid,
                            "Platform": "instagram",
                            "Kind": "mention",
                            "Author Name": tg.get("username", ""),
                            "Author Handle": tg.get("username", ""),
                            "Body": tg.get("caption", "") or "",
                            "Post URL": tg.get("permalink", ""),
                            "Post Caption": "",
                            "Reply URL": tg.get("permalink", ""),
                            "Received At": tg.get("timestamp", ""),
                            "Status": "unread",
                            "Metadata": _json.dumps(tg)[:4000],
                        })
                else:
                    print(f"[social-inbox] IG mentions skipped: {r.status_code} {r.text[:180]}")
            except Exception as e:
                print(f"[social-inbox] IG mentions error: {e}")

        # ── TikTok engagement digest (videos we posted) ────────────────────────
        if tt_client_key and tt_client_secret and tt_refresh_token:
            try:
                tok_resp = await c.post(
                    "https://open.tiktokapis.com/v2/oauth/token/",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={
                        "client_key": tt_client_key,
                        "client_secret": tt_client_secret,
                        "grant_type": "refresh_token",
                        "refresh_token": tt_refresh_token,
                    },
                )
                if tok_resp.is_success:
                    tt_access = (tok_resp.json().get("data") or {}).get("access_token") or tok_resp.json().get("access_token")
                else:
                    tt_access = None
                    print(f"[social-inbox] TT token refresh failed: {tok_resp.status_code} {tok_resp.text[:180]}")

                if tt_access:
                    list_resp = await c.post(
                        "https://open.tiktokapis.com/v2/video/list/",
                        headers={"Authorization": f"Bearer {tt_access}",
                                 "Content-Type": "application/json; charset=UTF-8"},
                        params={"fields": "id,title,video_description,create_time,share_url,view_count,like_count,comment_count,share_count,cover_image_url"},
                        json={"max_count": 20},
                    )
                    if list_resp.is_success:
                        videos = (list_resp.json().get("data") or {}).get("videos") or []
                        try: prev_snap = hub_cache.get("tt-video-snap") or {}
                        except Exception: prev_snap = {}
                        new_snap = {}
                        today_key = datetime.now(timezone.utc).strftime("%Y%m%d")
                        for v in videos:
                            vid = str(v.get("id", ""))
                            if not vid: continue
                            cur = {
                                "v": int(v.get("view_count", 0) or 0),
                                "l": int(v.get("like_count", 0) or 0),
                                "c": int(v.get("comment_count", 0) or 0),
                                "s": int(v.get("share_count", 0) or 0),
                            }
                            new_snap[vid] = cur
                            prev = prev_snap.get(vid)
                            if not prev:
                                continue  # first time we've seen this video; baseline only
                            dv = cur["v"] - prev.get("v", 0)
                            dl = cur["l"] - prev.get("l", 0)
                            dc = cur["c"] - prev.get("c", 0)
                            ds = cur["s"] - prev.get("s", 0)
                            if max(dv, dl, dc, ds) <= 0:
                                continue
                            sid = f"tt:digest:{vid}:{today_key}"
                            if sid in existing: continue  # already emitted a digest today
                            parts = []
                            if dv > 0: parts.append(f"+{dv} views")
                            if dl > 0: parts.append(f"+{dl} likes")
                            if dc > 0: parts.append(f"+{dc} comments")
                            if ds > 0: parts.append(f"+{ds} shares")
                            body = "Engagement since last check: " + ", ".join(parts)
                            total_body = (
                                body
                                + f"  \u2022  Total: {cur['v']:,} views / {cur['l']:,} likes / {cur['c']:,} comments"
                            )
                            new_rows.append({
                                "Source ID": sid,
                                "Platform": "tiktok",
                                "Kind": "digest",
                                "Author Name": "TikTok",
                                "Author Handle": "engagement",
                                "Body": total_body,
                                "Post URL": v.get("share_url", "") or "",
                                "Post Caption": (v.get("title") or v.get("video_description") or "")[:120],
                                "Reply URL": v.get("share_url", "") or "",
                                "Received At": datetime.now(timezone.utc).isoformat(),
                                "Status": "unread",
                                "Metadata": _json.dumps({"video_id": vid, "current": cur, "previous": prev})[:4000],
                            })
                        try: hub_cache["tt-video-snap"] = new_snap
                        except Exception: pass
                    else:
                        print(f"[social-inbox] TT video list failed: {list_resp.status_code} {list_resp.text[:180]}")
            except Exception as e:
                print(f"[social-inbox] TT error: {e}")

        # ── Upsert new rows ───────────────────────────────────────────────────
        for row in new_rows:
            try:
                rr = await c.post(
                    f"{br}/api/database/rows/table/{T_SOCIAL_NOTIFICATIONS}/?user_field_names=true",
                    headers=headers, json=row,
                )
                if not rr.is_success:
                    print(f"[social-inbox] insert failed: {rr.status_code} {rr.text[:200]}")
            except Exception as e:
                print(f"[social-inbox] insert error: {e}")

    try:
        hub_cache["social-poll-status"] = {
            "last_poll": datetime.now(timezone.utc).isoformat(),
            "pages": pages_connected,
            "inserted": len(new_rows),
        }
        hub_cache.pop(f"table:{T_SOCIAL_NOTIFICATIONS}", None)
    except Exception:
        pass
    print(f"[social-inbox] done; inserted={len(new_rows)} connected={len(pages_connected)}")


# ──────────────────────────────────────────────────────────────────────────────
# MODAL APP
# ──────────────────────────────────────────────────────────────────────────────
@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("outreach-hub-secrets"),
        modal.Secret.from_name("bunny-secrets"),
        modal.Secret.from_name("clickup-api"),
        modal.Secret.from_name("meta-secrets"),
        modal.Secret.from_name("tiktok-secrets"),
        modal.Secret.from_name("field-rep-sync"),
    ],
    min_containers=1,
)
@modal.asgi_app()
def web():
    import httpx
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

    fapp = FastAPI()

    def _env():
        return {
            "br":     os.environ.get("BASEROW_URL", "https://baserow.reformchiropractic.app"),
            "bt":     os.environ.get("BASEROW_API_TOKEN", ""),
            "gid":    os.environ.get("GOOGLE_CLIENT_ID", ""),
            "gsec":   os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "domain": os.environ.get("ALLOWED_DOMAIN", ""),
        }

    def _redirect_uri(request: Request) -> str:
        host = request.headers.get("host", "localhost:8000")
        if "localhost" in host or "127.0.0.1" in host:
            return f"http://{host}/auth/google/callback"
        return "https://hub.reformchiropractic.app/auth/google/callback"

    async def _refresh_if_needed(sid: str, session: dict, env: dict) -> str:
        if time.time() < session.get("expires_at", 0) - 60:
            return session["access_token"]
        async with httpx.AsyncClient() as client:
            r = await client.post("https://oauth2.googleapis.com/token", data={
                "client_id":     env["gid"],
                "client_secret": env["gsec"],
                "refresh_token": session.get("refresh_token", ""),
                "grant_type":    "refresh_token",
            })
            data = r.json()
        if "access_token" not in data:
            return session.get("access_token", "")
        session["access_token"] = data["access_token"]
        session["expires_at"] = time.time() + data.get("expires_in", 3600)
        hub_sessions[sid] = session
        return session["access_token"]

    # ── Login / OAuth ──────────────────────────────────────────────────────────
    @fapp.get("/login", response_class=HTMLResponse)
    async def login_get(request: Request, error: str = ""):
        if _ok(request):
            return RedirectResponse(url="/")
        return HTMLResponse(_login_page(error))

    @fapp.get("/auth/google", response_class=HTMLResponse)
    async def auth_google(request: Request):
        env = _env()
        state = secrets.token_urlsafe(32)
        hub_oauth_states[state] = time.time()
        params = urlencode({
            "client_id":     env["gid"],
            "redirect_uri":  _redirect_uri(request),
            "response_type": "code",
            "scope":         "openid email profile https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/calendar.events",
            "access_type":   "offline",
            "prompt":        "consent",
            "state":         state,
        })
        google_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
        # Use client-side redirect so browser navigates to Google directly
        # (Cloudflare Worker's redirect:follow would proxy Google's page otherwise)
        return HTMLResponse(
            f'<html><head></head><body>'
            f'<script>window.location.href={repr(google_url)};</script>'
            f'<noscript><meta http-equiv="refresh" content="0;url={google_url}"></noscript>'
            f'</body></html>'
        )

    @fapp.get("/auth/google/callback")
    async def auth_callback(request: Request, code: str = "", state: str = "", error: str = ""):
        if error or not code:
            return RedirectResponse("/login?error=1")
        stored_time = hub_oauth_states.get(state)
        if not stored_time or (time.time() - stored_time) > 300:
            return RedirectResponse("/login?error=1")
        del hub_oauth_states[state]

        env = _env()
        async with httpx.AsyncClient() as client:
            token_resp = await client.post("https://oauth2.googleapis.com/token", data={
                "code":          code,
                "client_id":     env["gid"],
                "client_secret": env["gsec"],
                "redirect_uri":  _redirect_uri(request),
                "grant_type":    "authorization_code",
            })
            tokens = token_resp.json()
            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {tokens.get('access_token','')}"}
            )
            user = userinfo_resp.json()

        email = user.get("email", "")
        allowed = env["domain"]
        if allowed and not email.endswith(f"@{allowed}"):
            return RedirectResponse("/login?error=domain")

        sid = secrets.token_urlsafe(32)
        hub_sessions[sid] = {
            "email":         email,
            "name":          user.get("name", email),
            "picture":       user.get("picture", ""),
            "access_token":  tokens.get("access_token", ""),
            "refresh_token": tokens.get("refresh_token", ""),
            "expires_at":    time.time() + tokens.get("expires_in", 3600),
        }

        # Auto-register in Staff table if not already there
        try:
            staff_tid = T_STAFF
            if staff_tid:
                async with httpx.AsyncClient(timeout=10) as sc:
                    sr = await sc.get(
                        f"{env['br']}/api/database/rows/table/{staff_tid}/"
                        f"?user_field_names=true&search={email}&size=5",
                        headers={"Authorization": f"Token {env['bt']}"},
                    )
                    found = False
                    if sr.status_code == 200:
                        for row in sr.json().get("results", []):
                            if (row.get("Email") or "").lower().strip() == email.lower():
                                found = True
                                break
                    if not found:
                        await sc.post(
                            f"{env['br']}/api/database/rows/table/{staff_tid}/"
                            f"?user_field_names=true",
                            headers={"Authorization": f"Token {env['bt']}",
                                     "Content-Type": "application/json"},
                            json={
                                "Name": user.get("name", email),
                                "Email": email,
                                "Role": "field",
                                "Active": True,
                            },
                        )
        except Exception:
            pass  # Don't block login if staff registration fails

        resp = HTMLResponse('<html><head><meta http-equiv="refresh" content="0;url=/"></head></html>')
        resp.set_cookie(SESSION_COOKIE, sid, httponly=True, max_age=86400 * 7, samesite="lax")
        return resp

    @fapp.get("/logout")
    async def logout(request: Request):
        sid = request.cookies.get(SESSION_COOKIE)
        if sid:
            try:
                del hub_sessions[sid]
            except KeyError:
                pass
        resp = HTMLResponse('<html><head><meta http-equiv="refresh" content="0;url=/login"></head></html>')
        resp.delete_cookie(SESSION_COOKIE)
        return resp

    # ── Table data proxy (cached) ───────────────────────────────────────────────
    @fapp.get("/api/data/{tid}")
    async def table_data(tid: int, request: Request):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        env = _env()
        rows = await _cached_table(tid, env["br"], env["bt"])
        return JSONResponse(rows)

    # ── Edit patient firm (writes Law Firm Name + Firm History) ────────────────
    _STAGE_TO_PI_TID = {
        "active":   T_PI_ACTIVE,
        "billed":   T_PI_BILLED,
        "awaiting": T_PI_AWAITING,
        "closed":   T_PI_CLOSED,
    }

    @fapp.patch("/api/patients/{stage}/{row_id}/firm")
    async def edit_patient_firm(stage: str, row_id: int, request: Request):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        tid = _STAGE_TO_PI_TID.get(stage)
        if not tid:
            return JSONResponse({"error": f"invalid stage: {stage}"}, status_code=400)

        body = await request.json()
        new_firm = (body.get("new_firm") or "").strip()
        if not new_firm:
            return JSONResponse({"error": "new_firm required"}, status_code=400)

        env = _env()
        br, bt = env["br"], env["bt"]

        # Fetch current row to read old firm + existing history
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{br}/api/database/rows/table/{tid}/{row_id}/?user_field_names=true",
                headers={"Authorization": f"Token {bt}"},
            )
            if r.status_code != 200:
                return JSONResponse({"error": f"fetch failed: {r.status_code}"}, status_code=r.status_code)
            row = r.json()

        old_firm = (row.get("Law Firm Name") or "").strip()
        existing_history = (row.get("Firm History") or "").strip()

        if new_firm == old_firm:
            return JSONResponse({"error": "no change"}, status_code=400)

        # Build new history chain. Existing format: "A -> B -> C (current)".
        # Strip (current) from the existing chain, append old_firm with today's
        # date marker, then append new firm as current.
        import datetime
        today = datetime.date.today().isoformat()

        def strip_current(chain: str) -> str:
            # Remove trailing " (current)" from the last segment if present
            if chain.endswith("(current)"):
                return chain[:-len("(current)")].strip()
            return chain

        parts = []
        if existing_history:
            parts.append(strip_current(existing_history))
        if old_firm:
            parts.append(f"{old_firm} (until {today})")
        parts.append(f"{new_firm} (current)")
        new_history = " -> ".join(p for p in parts if p)

        # Write to Baserow
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.patch(
                f"{br}/api/database/rows/table/{tid}/{row_id}/?user_field_names=true",
                headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
                json={"Law Firm Name": new_firm, "Firm History": new_history},
            )
            if r.status_code != 200:
                return JSONResponse(
                    {"error": f"update failed: {r.status_code}", "detail": r.text[:300]},
                    status_code=r.status_code,
                )
            updated = r.json()

        # Invalidate cache so next read reflects the change
        try:
            hub_cache.pop(f"table:{tid}", None)
        except Exception:
            pass

        return JSONResponse({
            "ok": True,
            "row": updated,
            "Law Firm Name": new_firm,
            "Firm History": new_history,
        })

    # ── Case Packet PDF (per patient) ──────────────────────────────────────────
    @fapp.get("/api/patients/{stage}/{row_id}/packet.pdf")
    async def patient_packet_pdf(stage: str, row_id: int, request: Request):
        from fastapi.responses import Response as _Resp
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        user = _get_user(request)
        if not _has_hub_access(user, "pi_cases"):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        tid = _STAGE_TO_PI_TID.get(stage)
        if not tid:
            return JSONResponse({"error": f"invalid stage: {stage}"}, status_code=400)
        env = _env()
        br, bt = env["br"], env["bt"]
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{br}/api/database/rows/table/{tid}/{row_id}/?user_field_names=true",
                headers={"Authorization": f"Token {bt}"},
            )
            if r.status_code != 200:
                return JSONResponse({"error": "patient not found"}, status_code=404)
            patient = r.json()
        finance_rows = []
        if T_PI_FINANCE:
            try:
                finance_rows = await _cached_table(T_PI_FINANCE, br, bt)
            except Exception:
                finance_rows = []
        from hub.case_packets import _packet_pdf
        try:
            pdf_bytes = _packet_pdf(patient, finance_rows, stage=stage)
        except Exception as e:
            return JSONResponse({"error": f"render failed: {e}"}, status_code=500)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in (patient.get("Name") or "patient"))
        filename = f"Reform_CasePacket_{safe_name}_{date.today().isoformat()}.pdf"
        return _Resp(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    # ── Case Packet compose prefill ────────────────────────────────────────────
    # Returns best-guess attorney email + subject so the UI can pre-fill the
    # compose dialog before the staff member edits/sends.
    @fapp.get("/api/patients/{stage}/{row_id}/packet/prefill")
    async def patient_packet_prefill(stage: str, row_id: int, request: Request):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        user = _get_user(request)
        if not _has_hub_access(user, "pi_cases"):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        tid = _STAGE_TO_PI_TID.get(stage)
        if not tid:
            return JSONResponse({"error": f"invalid stage: {stage}"}, status_code=400)
        env = _env()
        br, bt = env["br"], env["bt"]
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{br}/api/database/rows/table/{tid}/{row_id}/?user_field_names=true",
                headers={"Authorization": f"Token {bt}"},
            )
            if r.status_code != 200:
                return JSONResponse({"error": "patient not found"}, status_code=404)
            patient = r.json()
        from hub.case_packets import _firm_from_patient, _lookup_attorney_contact
        firm_name = _firm_from_patient(patient)
        companies, contacts = [], []
        if T_COMPANIES:
            try: companies = await _cached_table(T_COMPANIES, br, bt)
            except Exception: companies = []
        if T_CONTACTS:
            try: contacts = await _cached_table(T_CONTACTS, br, bt)
            except Exception: contacts = []
        lookup = _lookup_attorney_contact(firm_name, companies, contacts)
        pt_name = (patient.get("Name") or "the patient").strip()
        subject = f"Case Update — {pt_name}"
        if lookup["company_name"]:
            subject = f"Case Update — {pt_name} — {lookup['company_name']}"
        return JSONResponse({
            "to":            lookup["email"],
            "cc":            "",
            "subject":       subject,
            "firm_name":     lookup["company_name"] or firm_name,
            "email_source":  lookup["source"],       # "company" | "contact" | "none"
            "company_id":    lookup["company_id"],   # for activity logging on send
            "patient_name":  pt_name,
        })

    # ── Case Packet email send ────────────────────────────────────────────────
    # Generates the PDF, sends via the logged-in staff's Gmail refresh_token,
    # and logs an Activity row on the firm's Company (if matched).
    @fapp.post("/api/patients/{stage}/{row_id}/packet/email")
    async def patient_packet_email(stage: str, row_id: int, request: Request):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        user = _get_user(request)
        if not _has_hub_access(user, "pi_cases"):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        session = _get_session(request)
        refresh_token = (session or {}).get("refresh_token", "")
        if not refresh_token:
            return JSONResponse(
                {"error": "your hub session has no Gmail refresh_token — sign out and sign in with Google again"},
                status_code=400,
            )
        tid = _STAGE_TO_PI_TID.get(stage)
        if not tid:
            return JSONResponse({"error": f"invalid stage: {stage}"}, status_code=400)
        body = await request.json()
        to_email = (body.get("to") or "").strip()
        cc_email = (body.get("cc") or "").strip()
        subject  = (body.get("subject") or "").strip() or "Case Update — Reform Chiropractic"
        note     = (body.get("note") or "").strip()
        if not to_email or "@" not in to_email:
            return JSONResponse({"error": "valid 'to' address required"}, status_code=400)

        env = _env()
        br, bt = env["br"], env["bt"]

        # Fetch patient + finance for PDF render
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{br}/api/database/rows/table/{tid}/{row_id}/?user_field_names=true",
                headers={"Authorization": f"Token {bt}"},
            )
            if r.status_code != 200:
                return JSONResponse({"error": "patient not found"}, status_code=404)
            patient = r.json()
        finance_rows = []
        if T_PI_FINANCE:
            try: finance_rows = await _cached_table(T_PI_FINANCE, br, bt)
            except Exception: finance_rows = []

        from hub.case_packets import _packet_pdf, _firm_from_patient
        try:
            pdf_bytes = _packet_pdf(patient, finance_rows, stage=stage)
        except Exception as e:
            return JSONResponse({"error": f"render failed: {e}"}, status_code=500)

        # Refresh Gmail token + send
        from hub.gmail_send import refresh_access_token, send_email
        gid = os.environ.get("GOOGLE_CLIENT_ID", "")
        gsecret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        access_token = await refresh_access_token(refresh_token, gid, gsecret)
        if not access_token:
            return JSONResponse({"error": "Gmail token refresh failed"}, status_code=500)

        pt_name = (patient.get("Name") or "patient").strip()
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in pt_name)
        filename = f"Reform_CasePacket_{safe_name}_{date.today().isoformat()}.pdf"
        from_email = session.get("email", "techops@reformchiropractic.com")
        result = await send_email(
            access_token=access_token,
            to_email=to_email,
            from_email=from_email,
            subject=subject,
            body=note or f"Please find attached the case packet for {pt_name}.",
            cc_email=cc_email,
            attachment=(filename, pdf_bytes),
        )
        if not result.get("ok"):
            return JSONResponse(
                {"error": "send failed", "detail": result.get("error")},
                status_code=502,
            )

        # Log activity on the firm's Company if matched
        firm_name = _firm_from_patient(patient)
        company_id = None
        if firm_name and T_COMPANIES:
            try:
                from hub.case_packets import _lookup_attorney_contact
                companies = await _cached_table(T_COMPANIES, br, bt)
                lookup = _lookup_attorney_contact(firm_name, companies, [])
                company_id = lookup.get("company_id")
            except Exception:
                company_id = None
        if company_id:
            try:
                await _log_activity(
                    env,
                    company_id=company_id,
                    kind="user_activity",
                    type_="Case Packet Sent",
                    summary=f"{session.get('name') or from_email} emailed case packet for {pt_name} to {to_email}"
                            + (f" (cc {cc_email})" if cc_email else ""),
                    author=from_email,
                )
            except Exception:
                pass  # Send succeeded; don't bounce the request on log failure

        return JSONResponse({"ok": True, "message_id": result.get("id", "")})

    # ── Contact autocomplete (for compose modal) ───────────────────────────────
    @fapp.get("/api/contacts/autocomplete")
    async def contacts_autocomplete(request: Request):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        if not T_COMPANIES:
            return JSONResponse([])
        env = _env()
        rows = await _cached_table(T_COMPANIES, env["br"], env["bt"])
        contacts = []
        for r in rows:
            n = r.get("Name") or ""
            e = r.get("Email") or ""
            if n: contacts.append({"n": n, "e": e})
        contacts.sort(key=lambda c: c["n"].lower())
        return JSONResponse(contacts)

    # ── Dashboard batch endpoint (single request for all dashboard data) ──────
    @fapp.get("/api/dashboard")
    async def dashboard_batch(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        import asyncio
        env = _env()
        br, bt = env["br"], env["bt"]
        hubs = _get_allowed_hubs(session)

        # Only fetch tables the user has access to
        att = gor = com = boxes = []
        pi_act = pi_bil = pi_aw = pi_cl = []
        fetches = {}
        if "attorney" in hubs:
            fetches["att"] = _cached_table(T_ATT_VENUES, br, bt)
        if "guerilla" in hubs:
            fetches["gor"] = _cached_table(T_GOR_VENUES, br, bt)
            fetches["boxes"] = _cached_table(T_GOR_BOXES, br, bt)
        if "community" in hubs:
            fetches["com"] = _cached_table(T_COM_VENUES, br, bt)
        if "pi_cases" in hubs:
            fetches["pi_act"] = _cached_table(T_PI_ACTIVE, br, bt)
            fetches["pi_bil"] = _cached_table(T_PI_BILLED, br, bt)
            fetches["pi_aw"] = _cached_table(T_PI_AWAITING, br, bt)
            fetches["pi_cl"] = _cached_table(T_PI_CLOSED, br, bt)

        if fetches:
            keys = list(fetches.keys())
            results = await asyncio.gather(*fetches.values())
            resolved = dict(zip(keys, results))
            att = resolved.get("att", [])
            gor = resolved.get("gor", [])
            com = resolved.get("com", [])
            boxes = resolved.get("boxes", [])
            pi_act = resolved.get("pi_act", [])
            pi_bil = resolved.get("pi_bil", [])
            pi_aw = resolved.get("pi_aw", [])
            pi_cl = resolved.get("pi_cl", [])

        def slim(row, name_field):
            return {
                "cs": row.get("Contact Status"),
                "fu": row.get("Follow-Up Date"),
                "n": row.get(name_field) or row.get("Name") or row.get("Law Firm Name") or "",
            }

        return JSONResponse({
            "att": [slim(r, "Law Firm Name") for r in att],
            "gor": [slim(r, "Name") for r in gor],
            "com": [slim(r, "Name") for r in com],
            "pi": {"a": len(pi_act), "b": len(pi_bil), "w": len(pi_aw), "c": len(pi_cl)},
            "boxes": [{"s": r.get("Status"), "d": r.get("Date Placed"), "p": r.get("Pickup Days")} for r in boxes],
        })

    # ── Calendar API ───────────────────────────────────────────────────────────
    @fapp.get("/api/calendar/events")
    async def calendar_events(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        env = _env()
        sid = request.cookies.get(SESSION_COOKIE, "")
        token = await _refresh_if_needed(sid, session, env)
        if not token:
            return JSONResponse({"error": "no_token"}, status_code=401)
        # Read from the signed-in user's primary calendar. `?calendar_id=...`
        # can override (e.g. for a shared team calendar view) — default "primary"
        # keeps each user scoped to their own events, matching how /api/meetings
        # writes to the user's primary calendar.
        q = dict(request.query_params)
        cal_id = q.get("calendar_id") or "primary"
        time_min = q.get("start") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        max_results = q.get("max") or "20"
        params = f"timeMin={quote(time_min)}&maxResults={max_results}&singleEvents=true&orderBy=startTime"
        if q.get("end"):
            params += f"&timeMax={quote(q['end'])}"
        url = f"https://www.googleapis.com/calendar/v3/calendars/{quote(cal_id)}/events?{params}"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        if r.status_code != 200:
            return JSONResponse({"error": "fetch_failed", "status": r.status_code, "detail": r.text[:500]},
                                status_code=502)
        data = r.json()
        def slim(ev):
            start = ev.get("start", {})
            end   = ev.get("end", {})
            all_day = "date" in start
            return {
                "id":       ev.get("id", ""),
                "summary":  ev.get("summary", "(no title)"),
                "start":    start.get("dateTime") or start.get("date", ""),
                "end":      end.get("dateTime") or end.get("date", ""),
                "allDay":   all_day,
                "location": ev.get("location", ""),
                "link":     ev.get("htmlLink", ""),
                "description": ev.get("description", ""),
            }
        return JSONResponse({"items": [slim(ev) for ev in data.get("items", [])]})

    # ── SMS (Twilio) ───────────────────────────────────────────────────────────
    # Secrets read from Modal secret `twilio-api`:
    #   TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER
    # Until the secret is attached to this app, every endpoint returns 503 via
    # `_sms.is_configured()` and the UI surfaces a friendly "not configured"
    # banner.
    def _sms_guard(request):
        session = _get_session(request)
        if not session:
            return None, JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not _has_hub_access(session, "communications"):
            return None, JSONResponse({"error": "forbidden"}, status_code=403)
        if not T_SMS_MESSAGES:
            return None, JSONResponse({"error": "sms table not configured"}, status_code=503)
        return session, None

    async def _sms_resolve_links(env, phone: str) -> dict:
        """Given an E.164 phone, find any existing Company / Contact / Lead
        whose Phone matches. Used by inbound-SMS handler to auto-link."""
        import re as _re
        def _digits(s):
            return _re.sub(r"\D", "", s or "")
        target = _digits(phone)
        if not target: return {}
        out = {}
        if T_COMPANIES:
            for c in await _cached_table(T_COMPANIES, env["br"], env["bt"]):
                if _digits(c.get("Phone", "")) and target.endswith(_digits(c["Phone"])[-10:]):
                    out["company_id"] = c["id"]; break
        if T_CONTACTS:
            for p in await _cached_table(T_CONTACTS, env["br"], env["bt"]):
                if _digits(p.get("Phone", "")) and target.endswith(_digits(p["Phone"])[-10:]):
                    out["contact_id"] = p["id"]; break
        if T_LEADS:
            for l in await _cached_table(T_LEADS, env["br"], env["bt"]):
                if _digits(l.get("Phone", "")) and target.endswith(_digits(l["Phone"])[-10:]):
                    out["lead_id"] = l["id"]; break
        return out

    @fapp.post("/api/sms/send")
    async def api_sms_send(request: Request):
        session, err = _sms_guard(request)
        if err: return err
        if not _sms.is_configured():
            return JSONResponse({"error": "twilio_not_configured",
                                  "hint": "Add TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER to Modal secret `twilio-api` and attach it to the hub app."},
                                 status_code=503)
        body = await request.json()
        to_raw = (body.get("to") or "").strip()
        text   = (body.get("body") or "").strip()
        if not to_raw or not text:
            return JSONResponse({"error": "to and body required"}, status_code=400)
        to_e164 = _sms.normalize_phone(to_raw)
        if not to_e164:
            return JSONResponse({"error": "invalid phone number"}, status_code=400)

        # Send via Twilio
        tw = await _sms.send_sms(to_e164, text)
        if tw.get("error"):
            return JSONResponse({"error": "twilio_send_failed", "detail": tw.get("error"),
                                  "status": tw.get("status")}, status_code=502)

        # Log to Baserow
        env = _env()
        row = {
            "Phone":      to_e164,
            "Direction":  "outbound",
            "Body":       text,
            "Status":     tw.get("status") or "sent",
            "Twilio SID": tw.get("sid") or "",
            "From":       os.environ.get("TWILIO_FROM_NUMBER", ""),
            "Author":     session.get("email", ""),
            "Created":    _iso_now(),
            "Updated":    _iso_now(),
        }
        if body.get("company_id"):
            try: row["Company"] = [int(body["company_id"])]
            except (TypeError, ValueError): pass
        if body.get("contact_id"):
            try: row["Contact"] = [int(body["contact_id"])]
            except (TypeError, ValueError): pass
        if body.get("lead_id"):
            try: row["Lead ID"] = int(body["lead_id"])
            except (TypeError, ValueError): pass
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{env['br']}/api/database/rows/table/{T_SMS_MESSAGES}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json={k: v for k, v in row.items() if v not in (None, "")},
            )
        _invalidate(T_SMS_MESSAGES)
        saved = r.json() if r.status_code in (200, 201) else {}
        return JSONResponse({"ok": True, "id": saved.get("id"),
                              "twilio_sid": tw.get("sid"), "status": tw.get("status")})

    @fapp.post("/api/sms/webhook")
    async def api_sms_webhook(request: Request):
        """Twilio inbound webhook. Signature-verified; creates an inbound row
        and auto-links to any existing Company / Contact / Lead by phone."""
        # Twilio posts application/x-www-form-urlencoded
        form = dict(await request.form())
        if not _sms.is_configured():
            return HTMLResponse("<Response/>", media_type="application/xml")
        # Verify signature (unless bypassed for local dev)
        if os.environ.get("TWILIO_SKIP_SIGNATURE", "0") != "1":
            signature = request.headers.get("X-Twilio-Signature", "")
            url = str(request.url)
            # Twilio may hit the upstream Modal URL through the Cloudflare
            # proxy — fall back to the configured PUBLIC_HUB_URL if host
            # differs (best-effort).
            if not _sms.verify_webhook_signature(url, form, signature):
                pub = os.environ.get("PUBLIC_HUB_URL", "")
                if pub:
                    alt = pub.rstrip("/") + request.url.path
                    if not _sms.verify_webhook_signature(alt, form, signature):
                        return HTMLResponse("Forbidden", status_code=403)
                else:
                    return HTMLResponse("Forbidden", status_code=403)
        from_num = form.get("From", "")
        to_num   = form.get("To", "")
        body_txt = form.get("Body", "")
        sid      = form.get("MessageSid", "")
        env = _env()
        links = await _sms_resolve_links(env, from_num)
        row = {
            "Phone":      from_num,   # thread key = external number
            "Direction":  "inbound",
            "Body":       body_txt,
            "Status":     "received",
            "Twilio SID": sid,
            "From":       to_num,     # our Twilio number
            "Created":    _iso_now(),
            "Updated":    _iso_now(),
        }
        if links.get("company_id"): row["Company"] = [links["company_id"]]
        if links.get("contact_id"): row["Contact"] = [links["contact_id"]]
        if links.get("lead_id"):    row["Lead ID"] = links["lead_id"]
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(
                f"{env['br']}/api/database/rows/table/{T_SMS_MESSAGES}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json={k: v for k, v in row.items() if v not in (None, "")},
            )
        _invalidate(T_SMS_MESSAGES)
        # Empty TwiML = "don't auto-reply"
        return HTMLResponse("<Response/>", media_type="application/xml")

    @fapp.get("/api/sms/thread")
    async def api_sms_thread(request: Request):
        """Fetch messages for a thread. Pass `?phone=+1...` for a phone-
        keyed thread, or `?company_id=X` / `?contact_id=X` / `?lead_id=X`
        to pull everything linked to that CRM record (may span multiple
        phones if someone texts from multiple devices)."""
        session, err = _sms_guard(request)
        if err: return err
        q = dict(request.query_params)
        env = _env()
        rows = await _cached_table(T_SMS_MESSAGES, env["br"], env["bt"])

        def _links(v):
            return [x.get("id") if isinstance(x, dict) else x for x in (v or [])]

        if q.get("company_id"):
            try: cid = int(q["company_id"])
            except: cid = 0
            rows = [r for r in rows if cid and cid in _links(r.get("Company"))]
        elif q.get("contact_id"):
            try: cid = int(q["contact_id"])
            except: cid = 0
            rows = [r for r in rows if cid and cid in _links(r.get("Contact"))]
        elif q.get("lead_id"):
            try: lid = int(q["lead_id"])
            except: lid = 0
            rows = [r for r in rows if lid and (r.get("Lead ID") or 0) == lid]
        elif q.get("phone"):
            e164 = _sms.normalize_phone(q["phone"]) or q["phone"].strip()
            rows = [r for r in rows if (r.get("Phone") or "") == e164]
        else:
            return JSONResponse({"error": "need phone, company_id, contact_id, or lead_id"}, status_code=400)

        rows.sort(key=lambda r: r.get("Created") or "")
        return JSONResponse({"items": rows, "configured": _sms.is_configured()})

    # ── Gmail API ──────────────────────────────────────────────────────────────
    @fapp.post("/api/gmail/send")
    async def gmail_send(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        body = await request.json()
        to = body.get("to", "")
        cc = body.get("cc", "")
        bcc = body.get("bcc", "")
        subject = body.get("subject", "")
        text = body.get("body", "")
        thread_id = body.get("threadId", "")
        if not to or not subject or not text:
            return JSONResponse({"error": "missing fields"}, status_code=400)

        env = _env()
        sid = request.cookies.get(SESSION_COOKIE, "")
        token = await _refresh_if_needed(sid, session, env)

        import base64, email as emaillib
        msg = emaillib.message.EmailMessage()
        msg["From"] = session["email"]
        msg["To"] = to
        if cc:  msg["Cc"] = cc
        if bcc: msg["Bcc"] = bcc
        msg["Subject"] = subject
        msg.set_content(text)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        payload = {"raw": raw}
        if thread_id:
            payload["threadId"] = thread_id

        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
        return JSONResponse(r.json(), status_code=r.status_code)

    @fapp.get("/api/gmail/threads")
    async def gmail_threads(request: Request, contact_email: str = ""):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)

        env = _env()
        sid = request.cookies.get(SESSION_COOKIE, "")
        token = await _refresh_if_needed(sid, session, env)

        params = {"maxResults": 15}
        if contact_email:
            params["q"] = f"from:{contact_email} OR to:{contact_email}"

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/threads",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            meta = r.json().get("threads", [])
            threads = []
            for t in meta[:10]:
                tr = await client.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{t['id']}",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"format": "metadata", "metadataHeaders": ["Subject", "From", "To", "Date"]},
                )
                td = tr.json()
                # Flatten into a simpler structure
                msgs = td.get("messages", [])
                subject = ""
                snippet = td.get("snippet", "")
                from_addr = ""
                date_str = ""
                for m in msgs[:1]:
                    for h in m.get("payload", {}).get("headers", []):
                        if h["name"] == "Subject": subject = h["value"]
                        if h["name"] == "From": from_addr = h["value"]
                        if h["name"] == "Date": date_str = h["value"]
                threads.append({
                    "id": td.get("id", ""),
                    "subject": subject,
                    "snippet": snippet,
                    "from": from_addr,
                    "date": date_str,
                    "messageCount": len(msgs),
                })
        return JSONResponse({"threads": threads})

    @fapp.get("/api/gmail/thread/{thread_id}")
    async def gmail_thread_detail(thread_id: str, request: Request):
        import base64
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        env = _env()
        sid = request.cookies.get(SESSION_COOKIE, "")
        token = await _refresh_if_needed(sid, session, env)

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{thread_id}",
                headers={"Authorization": f"Bearer {token}"},
                params={"format": "full"},
            )
        td = r.json()
        messages = []
        for m in td.get("messages", []):
            headers = {h["name"]: h["value"] for h in m.get("payload", {}).get("headers", [])}
            # Extract text body
            body_text = ""
            def _extract(part):
                nonlocal body_text
                if body_text:
                    return
                mime = part.get("mimeType", "")
                if mime == "text/plain" and part.get("body", {}).get("data"):
                    body_text = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                for sub in part.get("parts", []):
                    _extract(sub)
            _extract(m.get("payload", {}))
            messages.append({
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "date": headers.get("Date", ""),
                "subject": headers.get("Subject", ""),
                "body": body_text,
            })
        return JSONResponse({"messages": messages})

    # ── Page helper ────────────────────────────────────────────────────────────
    def _guard(request):
        """Return (user, br, bt) or raise redirect."""
        session = _get_session(request)
        if not session:
            return None, None, None
        env = _env()
        return session, env["br"], env["bt"]

    # ── Hub ────────────────────────────────────────────────────────────────────
    def _is_mobile(request: Request) -> bool:
        ua = (request.headers.get("user-agent") or "").lower()
        return any(k in ua for k in ("iphone", "android", "mobile", "ipod"))

    @fapp.get("/", response_class=HTMLResponse)
    async def hub(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        return HTMLResponse(_hub_page(br, bt, user=user))

    # ── Tool dashboards (viewable by field users, read-only) ──────────────────
    @fapp.get("/attorney", response_class=HTMLResponse)
    async def attorney(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "attorney"):
            return HTMLResponse(_forbidden_page(br, bt, user=user), status_code=403)
        return HTMLResponse(_tool_page("attorney", br, bt, user=user))

    @fapp.get("/guerilla", response_class=HTMLResponse)
    async def gorilla(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "guerilla"):
            return HTMLResponse(_forbidden_page(br, bt, user=user), status_code=403)
        return HTMLResponse(_tool_page("gorilla", br, bt, user=user))

    @fapp.get("/community", response_class=HTMLResponse)
    async def community(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "community"):
            return HTMLResponse(_forbidden_page(br, bt, user=user), status_code=403)
        return HTMLResponse(_tool_page("community", br, bt, user=user))

    # ── Map directories (admin only) ──────────────────────────────────────────
    @fapp.get("/outreach/planner", response_class=HTMLResponse)
    async def route_planner(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "guerilla"): return RedirectResponse(url="/")
        return HTMLResponse(_route_planner_page(br, bt, user=user))

    @fapp.get("/reps/live", response_class=HTMLResponse)
    async def reps_live_page(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _is_admin(user):
            return HTMLResponse(_forbidden_page(br, bt, user=user), status_code=403)
        from hub.rep_tracker import _rep_tracker_page
        return HTMLResponse(_rep_tracker_page(br, bt, user=user))

    @fapp.get("/api/admin/reps/live")
    async def api_admin_reps_live(request: Request):
        user, br, bt = _guard(request)
        if not user:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        from hub.rep_tracker import get_active_reps
        return await get_active_reps(request, br, bt, user)

    @fapp.post("/api/rep/ping")
    async def api_rep_ping(request: Request):
        user, br, bt = _guard(request)
        if not user:
            return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
        from hub.rep_tracker import update_rep_location
        return await update_rep_location(request, br, bt, user)

    @fapp.get("/reps/performance", response_class=HTMLResponse)
    async def reps_performance_page(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _is_admin(user):
            return HTMLResponse(_forbidden_page(br, bt, user=user), status_code=403)
        from hub.rep_performance import _rep_performance_page
        return HTMLResponse(_rep_performance_page(br, bt, user=user))

    @fapp.get("/api/admin/rep-performance")
    async def api_admin_rep_performance(request: Request):
        user, br, bt = _guard(request)
        if not user:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        from hub.rep_performance import get_rep_performance
        # Adapter: rep_performance handler expects cached_rows(tid); hub uses
        # _cached_table(tid, br, bt). Close over br/bt from this request.
        async def _cr(tid: int):
            return await _cached_table(tid, br, bt)
        return await get_rep_performance(request, br, bt, user, _cr)

    # ── Push notifications ────────────────────────────────────────────────────
    def _vapid_env_hub():
        return (
            os.environ.get("VAPID_PUBLIC_KEY", ""),
            os.environ.get("VAPID_PRIVATE_KEY", ""),
            os.environ.get("VAPID_SUBJECT", "mailto:techops@reformchiropractic.com"),
        )

    @fapp.get("/api/push/vapid-public-key")
    async def api_push_vapid_key(request: Request):
        user, br, bt = _guard(request)
        if not user:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        from hub.push import vapid_public_key
        pub, _, _ = _vapid_env_hub()
        return vapid_public_key(pub)

    @fapp.post("/api/push/subscribe")
    async def api_push_subscribe(request: Request):
        user, br, bt = _guard(request)
        if not user:
            return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
        from hub.push import subscribe
        return await subscribe(request, br, bt, user)

    @fapp.post("/api/push/test")
    async def api_push_test(request: Request):
        user, br, bt = _guard(request)
        if not user:
            return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
        from hub.push import test_push
        pub, priv, sub = _vapid_env_hub()
        return await test_push(
            request, br, bt, user,
            vapid_public_key_b64url=pub,
            vapid_private_key_b64url=priv,
            vapid_subject=sub,
        )

    @fapp.get("/outreach/list", response_class=HTMLResponse)
    async def outreach_list(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "guerilla"): return RedirectResponse(url="/")
        return HTMLResponse(_outreach_list_page(br, bt, user=user))

    @fapp.get("/attorney/map")
    async def attorney_map(request: Request):
        return RedirectResponse(url="/outreach/planner", status_code=302)

    @fapp.get("/guerilla/map")
    async def gorilla_map(request: Request):
        return RedirectResponse(url="/outreach/planner", status_code=302)

    @fapp.get("/guerilla/log")
    async def gorilla_log_page(request: Request):
        return RedirectResponse(url="/guerilla", status_code=302)

    @fapp.get("/guerilla/events/internal", response_class=HTMLResponse)
    async def gorilla_events_internal(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "guerilla"): return RedirectResponse(url="/")
        return HTMLResponse(_gorilla_events_internal_page(br, bt, user=user))

    @fapp.get("/guerilla/events/external", response_class=HTMLResponse)
    async def gorilla_events_external(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "guerilla"): return RedirectResponse(url="/")
        return HTMLResponse(_gorilla_events_external_page(br, bt, user=user))

    @fapp.get("/guerilla/businesses", response_class=HTMLResponse)
    async def gorilla_businesses(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "guerilla"): return RedirectResponse(url="/")
        return HTMLResponse(_gorilla_businesses_page(br, bt, user=user))

    @fapp.get("/guerilla/boxes", response_class=HTMLResponse)
    async def gorilla_boxes(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "guerilla"): return RedirectResponse(url="/")
        return HTMLResponse(_gorilla_boxes_page(br, bt, user=user))

    @fapp.get("/community/map")
    async def community_map(request: Request):
        return RedirectResponse(url="/outreach/planner", status_code=302)

    @fapp.get("/guerilla/routes", response_class=HTMLResponse)
    async def gorilla_routes(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "guerilla"):
            return HTMLResponse(_forbidden_page(br, bt, user=user), status_code=403)
        return HTMLResponse(_gorilla_routes_page(br, bt, user=user))

    @fapp.get("/guerilla/routes/new", response_class=HTMLResponse)
    async def gorilla_routes_new(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "guerilla"): return RedirectResponse(url="/")
        return HTMLResponse(_gorilla_routes_new_page(br, bt, user=user))

    # ── Unified contact list — redirect to Outreach Directory ───────────────
    @fapp.get("/outreach/contacts", response_class=HTMLResponse)
    async def outreach_contacts(request: Request):
        return RedirectResponse(url="/outreach/list", status_code=302)

    # ── Contact list directories (admin only, legacy — kept for bookmarks) ───
    @fapp.get("/attorney/directory", response_class=HTMLResponse)
    async def attorney_directory(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "attorney"): return RedirectResponse(url="/")
        return HTMLResponse(_directory_page("attorney", br, bt, user=user))

    @fapp.get("/guerilla/directory", response_class=HTMLResponse)
    async def gorilla_directory(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "guerilla"): return RedirectResponse(url="/")
        return HTMLResponse(_directory_page("gorilla", br, bt, user=user))

    @fapp.get("/community/directory", response_class=HTMLResponse)
    async def community_directory(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "community"): return RedirectResponse(url="/")
        return HTMLResponse(_directory_page("community", br, bt, user=user))

    # ── PI Cases (admin only) ─────────────────────────────────────────────────
    @fapp.get("/patients", response_class=HTMLResponse)
    async def patients(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "pi_cases"): return RedirectResponse(url="/")
        return HTMLResponse(_patients_page(br, bt, user=user))

    @fapp.get("/patients/active", response_class=HTMLResponse)
    async def patients_active(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "pi_cases"): return RedirectResponse(url="/")
        return HTMLResponse(_patients_page(br, bt, 'active', user=user))

    @fapp.get("/patients/billed", response_class=HTMLResponse)
    async def patients_billed(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "pi_cases"): return RedirectResponse(url="/")
        return HTMLResponse(_patients_page(br, bt, 'billed', user=user))

    @fapp.get("/patients/awaiting", response_class=HTMLResponse)
    async def patients_awaiting(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "pi_cases"): return RedirectResponse(url="/")
        return HTMLResponse(_patients_page(br, bt, 'awaiting', user=user))

    @fapp.get("/patients/closed", response_class=HTMLResponse)
    async def patients_closed(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "pi_cases"): return RedirectResponse(url="/")
        return HTMLResponse(_patients_page(br, bt, 'closed', user=user))

    @fapp.get("/firms", response_class=HTMLResponse)
    async def firms(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "pi_cases"): return RedirectResponse(url="/")
        return HTMLResponse(_firms_page(br, bt, user=user))

    # ── Billing (admin only) ──────────────────────────────────────────────────
    @fapp.get("/billing/collections", response_class=HTMLResponse)
    async def billing_collections(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "billing"): return RedirectResponse(url="/")
        return HTMLResponse(_billing_page("collections", br, bt, user=user))

    @fapp.get("/billing/settlements", response_class=HTMLResponse)
    async def billing_settlements(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "billing"): return RedirectResponse(url="/")
        return HTMLResponse(_billing_page("settlements", br, bt, user=user))

    # ── Communications ────────────────────────────────────────────────────────
    @fapp.get("/communications/email", response_class=HTMLResponse)
    async def communications_email(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "communications"): return RedirectResponse(url="/")
        return HTMLResponse(_communications_email_page(br, bt, user=user))

    # ── Contacts ──────────────────────────────────────────────────────────────
    @fapp.get("/contacts", response_class=HTMLResponse)
    async def contacts(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "communications"): return RedirectResponse(url="/")
        return HTMLResponse(_contacts_page(br, bt, user=user))

    @fapp.post("/api/contacts")
    async def contacts_create(request: Request):
        """Create a new contact. During Phase 2b migration, writes to BOTH the
        legacy per-category venue table AND the unified T_COMPANIES table (with
        the venue row's id stamped on Companies.Legacy ID for future cross-
        reference). Keeps legacy directory hubs and the unified Comms view in
        sync as we swap hubs over."""
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not _has_hub_access(session, "communications"):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        env = _env()
        body = await request.json()
        category = (body.get("category") or "guerilla").strip()
        name     = (body.get("name") or "").strip()
        phone    = (body.get("phone") or "").strip()
        email    = (body.get("email") or "").strip()
        address  = (body.get("address") or "").strip()
        status   = body.get("status") or "Not Contacted"
        if not name:
            return JSONResponse({"error": "name required"}, status_code=400)

        TABLE_MAP = {
            "attorney":  {"tid": T_ATT_VENUES, "name_f": "Law Firm Name", "phone_f": "Phone Number", "addr_f": "Law Office Address", "email_f": "Email", "status_map": {"Active Partner": "Active Relationship"}, "legacy_src": "attorney_venue"},
            "guerilla":  {"tid": T_GOR_VENUES, "name_f": "Name",          "phone_f": "Phone",        "addr_f": "Address",            "email_f": "Email", "status_map": {}, "legacy_src": "guerilla_venue"},
            "gorilla":   {"tid": T_GOR_VENUES, "name_f": "Name",          "phone_f": "Phone",        "addr_f": "Address",            "email_f": "Email", "status_map": {}, "legacy_src": "guerilla_venue"},
            "community": {"tid": T_COM_VENUES, "name_f": "Name",          "phone_f": "Phone",        "addr_f": "Address",            "email_f": "Email", "status_map": {}, "legacy_src": "community_venue"},
        }
        cfg = TABLE_MAP.get(category, TABLE_MAP["guerilla"])
        cat_norm = "guerilla" if category == "gorilla" else category

        # 1) Write to legacy venue table (old hubs still read these).
        venue_fields: dict = {
            cfg["name_f"]:    name,
            "Contact Status": cfg["status_map"].get(status, status),
        }
        if phone:   venue_fields[cfg["phone_f"]] = phone
        if email:   venue_fields[cfg["email_f"]] = email
        if address: venue_fields[cfg["addr_f"]]  = address
        async with httpx.AsyncClient(timeout=20) as client:
            rv = await client.post(
                f"{env['br']}/api/database/rows/table/{cfg['tid']}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=venue_fields,
            )
        if rv.status_code not in (200, 201):
            return JSONResponse({"error": rv.text}, status_code=rv.status_code)
        venue_row = rv.json()
        _invalidate(cfg["tid"])

        # 2) Mirror-write to Companies so the unified Comms view stays in sync.
        if T_COMPANIES:
            import datetime as _dt
            now = _dt.datetime.now(_dt.timezone.utc).isoformat()
            company_fields: dict = {
                "Name":           name,
                "Category":       cat_norm,
                "Contact Status": status,
                "Active":         True,
                "Legacy Source":  cfg["legacy_src"],
                "Legacy ID":      venue_row["id"],
                "Created":        now,
                "Updated":        now,
            }
            if phone:   company_fields["Phone"]   = phone
            if email:   company_fields["Email"]   = email
            if address: company_fields["Address"] = address
            async with httpx.AsyncClient(timeout=20) as client:
                await client.post(
                    f"{env['br']}/api/database/rows/table/{T_COMPANIES}/?user_field_names=true",
                    headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                    json=company_fields,
                )
            _invalidate(T_COMPANIES)
        return JSONResponse({"ok": True, "id": venue_row["id"]})

    # ── CRM: Companies, People (Contacts), Activities ─────────────────────────
    #
    # Phase 3 endpoints backing the detail pages. PATCH endpoints auto-log an
    # Activity row (Kind='edit') summarizing field-level diffs for the history
    # tab. GETs pull a single row + related activities / linked people.

    def _crm_guard(request):
        session = _get_session(request)
        if not session:
            return None, JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not _has_hub_access(session, "communications"):
            return None, JSONResponse({"error": "forbidden"}, status_code=403)
        return session, None

    def _sel(v):
        return v.get("value") if isinstance(v, dict) else (v or "")

    def _iso_now():
        import datetime as _dt
        return _dt.datetime.now(_dt.timezone.utc).isoformat()

    def _diff_summary(actor: str, before: dict, patch: dict) -> str:
        """Build a human-readable multi-line summary of field changes."""
        lines = []
        # Only diff primitive/string fields we know about — skip link_rows etc.
        tracked = ("Name", "Category", "Type", "Address", "Phone", "Email",
                   "Website", "Contact Status", "Outreach Goal", "Classification",
                   "Active", "Permanently Closed", "Notes", "Resolution Notes",
                   "Title", "Lifecycle Stage", "Fax Number", "Preferred MRI Facility",
                   "Preferred PM Facility", "Promo Items")
        for k, new in patch.items():
            if k not in tracked: continue
            old = before.get(k)
            old_s = _sel(old) if isinstance(old, dict) else (old if old is not None else "")
            new_s = new if not isinstance(new, dict) else _sel(new)
            if str(old_s or "") == str(new_s or ""): continue
            if not old_s and new_s:
                lines.append(f"{actor} set {k} to '{new_s}'")
            elif old_s and not new_s:
                lines.append(f"{actor} cleared {k} (was '{old_s}')")
            else:
                lines.append(f"{actor} changed {k} from '{old_s}' to '{new_s}'")
        return "\n".join(lines)

    async def _log_activity(env, *, company_id=None, contact_id=None, kind: str,
                             summary: str, author: str, type_=None):
        """Write a row to T_ACTIVITIES. kind: user_activity|edit|note|creation."""
        if not T_ACTIVITIES: return
        payload = {
            "Summary": summary,
            "Kind":    kind,
            "Author":  author,
            "Date":    _iso_now()[:10],
            "Created": _iso_now(),
        }
        if type_: payload["Type"] = type_
        if company_id: payload["Company"] = [company_id]
        if contact_id: payload["Contact"] = [contact_id]
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(
                f"{env['br']}/api/database/rows/table/{T_ACTIVITIES}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json={k: v for k, v in payload.items() if v not in (None, "")},
            )
        _invalidate(T_ACTIVITIES)

    @fapp.get("/api/companies/{company_id}")
    async def api_company_get(company_id: int, request: Request):
        session, err = _crm_guard(request)
        if err: return err
        env = _env()
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                f"{env['br']}/api/database/rows/table/{T_COMPANIES}/{company_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}"},
            )
        if r.status_code == 404: return JSONResponse({"error": "not found"}, status_code=404)
        if r.status_code != 200: return JSONResponse({"error": r.text}, status_code=r.status_code)
        return JSONResponse(r.json())

    # Mapping of Company fields → (legacy_venue_table, legacy_field_name)
    # Status values also get mapped where legacy uses a different label.
    _LEGACY_VENUE_MAPPINGS = {
        "attorney_venue": {
            "tid": T_ATT_VENUES,
            "fields": {
                "Name":                   "Law Firm Name",
                "Phone":                  "Phone Number",
                "Email":                  "Email Address",
                "Address":                "Law Office Address",
                "Website":                "Website",
                "Notes":                  "Notes",
                "Contact Status":         "Contact Status",
                "Classification":         "Classification",
                "Fax Number":             "Fax Number",
                "Preferred MRI Facility": "Preferred MRI Facility",
                "Preferred PM Facility":  "Preferred PM Facility",
            },
            "status_out": {"Active Partner": "Active Relationship"},
        },
        "guerilla_venue": {
            "tid": T_GOR_VENUES,
            "fields": {
                "Name":                "Name",
                "Phone":               "Phone",
                "Address":             "Address",
                "Website":             "Website",
                "Contact Status":      "Contact Status",
                "Outreach Goal":       "Outreach Goal",
                "Permanently Closed":  "Permanently Closed",
                "Promo Items":         "Promo Items",
                "Type":                "Type",
            },
            "status_out": {"Active Partner": "Partner"},
        },
        "community_venue": {
            "tid": T_COM_VENUES,
            "fields": {
                "Name":           "Name",
                "Phone":          "Phone",
                "Email":          "Email",
                "Address":        "Address",
                "Website":        "Website",
                "Notes":          "Notes",
                "Contact Status": "Contact Status",
                "Outreach Goal":  "Outreach Goal",
                "Type":           "Type",
            },
            "status_out": {},
        },
    }

    async def _mirror_to_legacy_venue(env, current_company: dict, patch: dict):
        """Phase 2b.3 sync: when a Company is edited, mirror the change to its
        legacy venue twin (looked up via Legacy Source + Legacy ID). Best-effort
        — failures are swallowed since the Companies write already succeeded."""
        legacy_source = current_company.get("Legacy Source")
        if isinstance(legacy_source, dict): legacy_source = legacy_source.get("value")
        legacy_id = current_company.get("Legacy ID")
        if not legacy_source or not legacy_id: return
        try: legacy_id = int(legacy_id)
        except (TypeError, ValueError): return
        mapping = _LEGACY_VENUE_MAPPINGS.get(legacy_source)
        if not mapping: return
        legacy_fields = {}
        for co_field, legacy_field in mapping["fields"].items():
            if co_field not in patch: continue
            v = patch[co_field]
            if co_field == "Contact Status" and v in mapping["status_out"]:
                v = mapping["status_out"][v]
            legacy_fields[legacy_field] = v
        if not legacy_fields: return
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                await client.patch(
                    f"{env['br']}/api/database/rows/table/{mapping['tid']}/{legacy_id}/?user_field_names=true",
                    headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                    json=legacy_fields,
                )
            _invalidate(mapping["tid"])
        except Exception:
            pass

    @fapp.patch("/api/companies/{company_id}")
    async def api_company_patch(company_id: int, request: Request):
        session, err = _crm_guard(request)
        if err: return err
        env = _env()
        body = await request.json()
        # Fetch current to compute diff
        async with httpx.AsyncClient(timeout=20) as client:
            rget = await client.get(
                f"{env['br']}/api/database/rows/table/{T_COMPANIES}/{company_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}"},
            )
        if rget.status_code != 200:
            return JSONResponse({"error": "not found"}, status_code=404)
        current = rget.json()
        patch = {k: v for k, v in body.items() if k != "id"}
        patch["Updated"] = _iso_now()

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.patch(
                f"{env['br']}/api/database/rows/table/{T_COMPANIES}/{company_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=patch,
            )
        if r.status_code != 200:
            return JSONResponse({"error": r.text}, status_code=r.status_code)

        actor = session.get("name") or session.get("email", "Someone")
        summary = _diff_summary(actor, current, patch)
        if summary:
            await _log_activity(env, company_id=company_id, kind="edit",
                                summary=summary, author=session.get("email", ""))
        # Mirror to legacy venue (non-fatal on failure)
        await _mirror_to_legacy_venue(env, current, patch)
        _invalidate(T_COMPANIES)
        return JSONResponse(r.json())

    @fapp.get("/api/companies/{company_id}/activities")
    async def api_company_activities(company_id: int, request: Request):
        session, err = _crm_guard(request)
        if err: return err
        env = _env()
        rows = await _cached_table(T_ACTIVITIES, env["br"], env["bt"])
        def _links(v):
            return [x.get("id") if isinstance(x, dict) else x for x in (v or [])]
        matched = [r for r in rows if company_id in _links(r.get("Company"))]
        matched.sort(key=lambda a: (a.get("Created") or a.get("Date") or ""), reverse=True)
        return JSONResponse(matched)

    @fapp.post("/api/companies/{company_id}/activities")
    async def api_company_activity_create(company_id: int, request: Request):
        session, err = _crm_guard(request)
        if err: return err
        env = _env()
        body = await request.json()
        summary = (body.get("summary") or "").strip()
        if not summary:
            return JSONResponse({"error": "summary required"}, status_code=400)
        sentiment = (body.get("sentiment") or "").strip()
        if sentiment not in ("Green", "Yellow", "Red"):
            sentiment = ""
        payload = {
            "Summary":        summary,
            "Kind":           body.get("kind") or "user_activity",
            "Type":           body.get("type") or None,
            "Outcome":        body.get("outcome") or None,
            "Contact Person": body.get("person") or "",
            "Follow-Up Date": body.get("follow_up") or None,
            "Date":           body.get("date") or _iso_now()[:10],
            "Author":         session.get("email", ""),
            "Created":        _iso_now(),
            "Company":        [company_id],
            "Sentiment":      sentiment or None,
            "Photo URL":      (body.get("photo_url") or "").strip() or None,
            "Audio URL":      (body.get("audio_url") or "").strip() or None,
            "Transcript":     (body.get("transcript") or "").strip() or None,
        }
        if body.get("contact_id"):
            payload["Contact"] = [int(body["contact_id"])]
        clean = {k: v for k, v in payload.items() if v not in (None, "")}
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{env['br']}/api/database/rows/table/{T_ACTIVITIES}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=clean,
            )
        if r.status_code not in (200, 201):
            return JSONResponse({"error": r.text}, status_code=r.status_code)
        _invalidate(T_ACTIVITIES)
        return JSONResponse(r.json())

    @fapp.post("/api/companies/{company_id}/activities/photo")
    async def api_company_activity_photo(company_id: int, request: Request):
        session, err = _crm_guard(request)
        if err: return err
        from hub import outreach_api
        env = _env()
        return await outreach_api.upload_activity_photo(
            request, env["br"], env["bt"], session, company_id,
            bunny_zone=os.environ.get("BUNNY_STORAGE_ZONE", "techopssocialmedia"),
            bunny_key=os.environ.get("BUNNY_STORAGE_API_KEY", ""),
            bunny_cdn_base="https://techopssocialmedia.b-cdn.net",
        )

    @fapp.post("/api/activities/transcribe")
    async def api_activity_transcribe(request: Request):
        session, err = _crm_guard(request)
        if err: return err
        from hub import outreach_api
        return await outreach_api.transcribe_activity_audio(
            request, session,
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            bunny_zone=os.environ.get("BUNNY_STORAGE_ZONE", "techopssocialmedia"),
            bunny_key=os.environ.get("BUNNY_STORAGE_API_KEY", ""),
            bunny_cdn_base="https://techopssocialmedia.b-cdn.net",
        )

    @fapp.get("/api/companies/{company_id}/people")
    async def api_company_people(company_id: int, request: Request):
        session, err = _crm_guard(request)
        if err: return err
        env = _env()
        rows = await _cached_table(T_CONTACTS, env["br"], env["bt"])
        def _links(v):
            return [x.get("id") if isinstance(x, dict) else x for x in (v or [])]
        matched = [r for r in rows
                   if company_id in _links(r.get("Primary Company"))
                   or company_id in _links(r.get("Lead Source Company"))]
        matched.sort(key=lambda p: (p.get("Name") or "").lower())
        return JSONResponse(matched)

    @fapp.get("/api/people")
    async def api_people_list(request: Request):
        session, err = _crm_guard(request)
        if err: return err
        env = _env()
        rows = await _cached_table(T_CONTACTS, env["br"], env["bt"])
        return JSONResponse(rows)

    @fapp.post("/api/people")
    async def api_people_create(request: Request):
        session, err = _crm_guard(request)
        if err: return err
        env = _env()
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            return JSONResponse({"error": "name required"}, status_code=400)
        payload = {
            "Name":            name,
            "Email":           body.get("email") or "",
            "Phone":           body.get("phone") or "",
            "Title":           body.get("title") or "",
            "Lifecycle Stage": body.get("lifecycle") or "Lead",
            "Notes":           body.get("notes") or "",
            "Active":          True,
            "Legacy Source":   "crm_native",
            "Created":         _iso_now(),
            "Updated":         _iso_now(),
        }
        if body.get("primary_company"):
            payload["Primary Company"] = [int(body["primary_company"])]
        if body.get("lead_source_company"):
            payload["Lead Source Company"] = [int(body["lead_source_company"])]
        clean = {k: v for k, v in payload.items() if v not in (None, "")}
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{env['br']}/api/database/rows/table/{T_CONTACTS}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=clean,
            )
        if r.status_code not in (200, 201):
            return JSONResponse({"error": r.text}, status_code=r.status_code)
        person = r.json()
        actor = session.get("name") or session.get("email", "Someone")
        await _log_activity(env, contact_id=person["id"], kind="creation",
                            summary=f"{actor} added this contact.",
                            author=session.get("email", ""))
        _invalidate(T_CONTACTS)
        return JSONResponse(person)

    @fapp.get("/api/people/{person_id}")
    async def api_person_get(person_id: int, request: Request):
        session, err = _crm_guard(request)
        if err: return err
        env = _env()
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                f"{env['br']}/api/database/rows/table/{T_CONTACTS}/{person_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}"},
            )
        if r.status_code == 404: return JSONResponse({"error": "not found"}, status_code=404)
        if r.status_code != 200: return JSONResponse({"error": r.text}, status_code=r.status_code)
        return JSONResponse(r.json())

    @fapp.patch("/api/people/{person_id}")
    async def api_person_patch(person_id: int, request: Request):
        session, err = _crm_guard(request)
        if err: return err
        env = _env()
        body = await request.json()
        async with httpx.AsyncClient(timeout=20) as client:
            rget = await client.get(
                f"{env['br']}/api/database/rows/table/{T_CONTACTS}/{person_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}"},
            )
        if rget.status_code != 200:
            return JSONResponse({"error": "not found"}, status_code=404)
        current = rget.json()
        patch = {k: v for k, v in body.items() if k != "id"}
        patch["Updated"] = _iso_now()
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.patch(
                f"{env['br']}/api/database/rows/table/{T_CONTACTS}/{person_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=patch,
            )
        if r.status_code != 200:
            return JSONResponse({"error": r.text}, status_code=r.status_code)
        actor = session.get("name") or session.get("email", "Someone")
        summary = _diff_summary(actor, current, patch)
        if summary:
            await _log_activity(env, contact_id=person_id, kind="edit",
                                summary=summary, author=session.get("email", ""))
        _invalidate(T_CONTACTS)
        return JSONResponse(r.json())

    @fapp.get("/api/people/{person_id}/activities")
    async def api_person_activities(person_id: int, request: Request):
        session, err = _crm_guard(request)
        if err: return err
        env = _env()
        rows = await _cached_table(T_ACTIVITIES, env["br"], env["bt"])
        def _links(v):
            return [x.get("id") if isinstance(x, dict) else x for x in (v or [])]
        matched = [r for r in rows if person_id in _links(r.get("Contact"))]
        matched.sort(key=lambda a: (a.get("Created") or a.get("Date") or ""), reverse=True)
        return JSONResponse(matched)

    @fapp.post("/api/people/{person_id}/activities")
    async def api_person_activity_create(person_id: int, request: Request):
        session, err = _crm_guard(request)
        if err: return err
        env = _env()
        body = await request.json()
        summary = (body.get("summary") or "").strip()
        if not summary:
            return JSONResponse({"error": "summary required"}, status_code=400)
        payload = {
            "Summary":        summary,
            "Kind":           body.get("kind") or "user_activity",
            "Type":           body.get("type") or None,
            "Outcome":        body.get("outcome") or None,
            "Contact Person": body.get("person") or "",
            "Follow-Up Date": body.get("follow_up") or None,
            "Date":           body.get("date") or _iso_now()[:10],
            "Author":         session.get("email", ""),
            "Created":        _iso_now(),
            "Contact":        [person_id],
        }
        if body.get("company_id"):
            payload["Company"] = [int(body["company_id"])]
        clean = {k: v for k, v in payload.items() if v not in (None, "")}
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{env['br']}/api/database/rows/table/{T_ACTIVITIES}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=clean,
            )
        if r.status_code not in (200, 201):
            return JSONResponse({"error": r.text}, status_code=r.status_code)
        _invalidate(T_ACTIVITIES)
        return JSONResponse(r.json())

    # ── Unified activity stream ────────────────────────────────────────────────
    # Merges T_ACTIVITIES (company/contact-linked) + T_TICKET_COMMENTS
    # (ticket-linked) into one sorted feed. Used by /inbox + dashboard
    # "Activity this week" widget.
    @fapp.get("/api/activities/stream")
    async def api_activity_stream(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not _has_hub_access(session, "inbox"):
            return JSONResponse({"error": "forbidden"}, status_code=403)

        q = dict(request.query_params)
        mine_only = (q.get("mine") or "").lower() in ("1", "true", "yes")
        try:    limit = max(1, min(500, int(q.get("limit", "100"))))
        except: limit = 100
        kinds = {k.strip() for k in (q.get("kind") or "").split(",") if k.strip()} or None
        user_email = (session.get("email") or "").lower()

        # `since` accepts: ISO ("2026-04-01"), or relative "<N>d" / "<N>h" / "<N>m"
        since_iso = None
        since_raw = (q.get("since") or "").strip()
        if since_raw:
            import re as _re
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
            m = _re.match(r"^(\d+)([dhm])$", since_raw)
            if m:
                n = int(m.group(1))
                delta = {"d": _td(days=n), "h": _td(hours=n), "m": _td(minutes=n)}[m.group(2)]
                since_iso = (_dt.now(_tz.utc) - delta).isoformat()
            else:
                since_iso = since_raw

        env = _env()
        activities = await _cached_table(T_ACTIVITIES, env["br"], env["bt"]) if T_ACTIVITIES else []
        ticket_comments = await _cached_table(T_TICKET_COMMENTS, env["br"], env["bt"]) if T_TICKET_COMMENTS else []

        # Lookup indices for source enrichment
        companies_idx, contacts_idx, tickets_idx = {}, {}, {}
        if T_COMPANIES:
            for c in await _cached_table(T_COMPANIES, env["br"], env["bt"]):
                companies_idx[c["id"]] = c.get("Name", "")
        if T_CONTACTS:
            for c in await _cached_table(T_CONTACTS, env["br"], env["bt"]):
                contacts_idx[c["id"]] = c.get("Name", "")
        if T_TICKETS:
            for t in await _cached_table(T_TICKETS, env["br"], env["bt"]):
                tickets_idx[t["id"]] = t.get("Title", "")

        def _link_ids(v):
            return [x.get("id") if isinstance(x, dict) else x for x in (v or [])]

        out = []

        for a in activities:
            comp_ids = _link_ids(a.get("Company"))
            cont_ids = _link_ids(a.get("Contact"))
            source = None
            if comp_ids:
                cid = comp_ids[0]
                source = {"type": "company", "id": cid,
                          "name": companies_idx.get(cid, f"Company #{cid}"),
                          "url":  f"/companies/{cid}"}
            elif cont_ids:
                pid = cont_ids[0]
                source = {"type": "person", "id": pid,
                          "name": contacts_idx.get(pid, f"Person #{pid}"),
                          "url":  f"/people/{pid}"}
            else:
                continue
            out.append({
                "kind":    _sel(a.get("Kind")) or "user_activity",
                "type":    _sel(a.get("Type")) or "",
                "author":  a.get("Author", ""),
                "summary": a.get("Summary", ""),
                "created": a.get("Created") or a.get("Date") or "",
                "source":  source,
            })

        for c in ticket_comments:
            tix_ids = _link_ids(c.get("Ticket"))
            if not tix_ids: continue
            tid = tix_ids[0]
            out.append({
                "kind":    _sel(c.get("Kind")) or "comment",
                "type":    "",
                "author":  c.get("Author", ""),
                "summary": c.get("Body", ""),
                "created": c.get("Created") or "",
                "source":  {"type": "ticket", "id": tid,
                            "name": tickets_idx.get(tid, f"Ticket #{tid}"),
                            "url":  f"/tickets/{tid}"},
            })

        if mine_only:
            out = [e for e in out if (e.get("author") or "").lower() == user_email]
        if kinds:
            out = [e for e in out if e.get("kind") in kinds]
        if since_iso:
            out = [e for e in out if (e.get("created") or "") >= since_iso]

        out.sort(key=lambda e: e.get("created") or "", reverse=True)
        return JSONResponse({"items": out[:limit], "total": len(out)})

    # ── Meetings (Phase 4) — create events on user's primary Google Calendar ──
    @fapp.post("/api/meetings")
    async def api_meeting_create(request: Request):
        """Schedule a meeting on the signed-in user's primary Google Calendar.
        `sendUpdates=all` makes Google email invites to the attendees list.
        Auto-logs an Activity row linked to the Company/Contact so the Meeting
        surfaces on the detail page's Activity + History tabs."""
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not (_has_hub_access(session, "communications") or _has_hub_access(session, "calendar")):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        env = _env()
        sid = request.cookies.get(SESSION_COOKIE, "")
        token = await _refresh_if_needed(sid, session, env)
        if not token:
            return JSONResponse({"error": "no_token", "hint": "sign out and sign back in"}, status_code=401)

        body = await request.json()
        title       = (body.get("title") or "").strip()
        start       = body.get("start")        # ISO 8601, with TZ offset
        end         = body.get("end")          # ISO 8601
        description = body.get("description") or ""
        location    = body.get("location") or ""
        attendees   = body.get("attendees") or []  # list of email strings
        tz          = body.get("tz") or "America/Los_Angeles"

        if not title or not start or not end:
            return JSONResponse({"error": "title, start, end required"}, status_code=400)

        event = {
            "summary":     title,
            "description": description,
            "location":    location,
            "start":       {"dateTime": start, "timeZone": tz},
            "end":         {"dateTime": end,   "timeZone": tz},
        }
        cleaned_attendees = [{"email": e.strip()} for e in attendees if isinstance(e, str) and e.strip() and "@" in e]
        if cleaned_attendees:
            event["attendees"] = cleaned_attendees

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events?sendUpdates=all",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=event,
            )
        if r.status_code not in (200, 201):
            detail = r.text[:500]
            status = r.status_code
            hint = ""
            if status in (401, 403):
                hint = "Your session may be missing calendar write permission — sign out and sign back in."
            return JSONResponse({"error": "calendar_api_failed", "status": status, "detail": detail, "hint": hint},
                                status_code=502)

        ev = r.json()
        actor = session.get("name") or session.get("email", "Someone")
        when = start.replace("T", " ")[:16]
        link = ev.get("htmlLink", "")
        summary_line = f"{actor} scheduled: {title} ({when})"
        if cleaned_attendees:
            summary_line += " with " + ", ".join(a["email"] for a in cleaned_attendees)
        if link:
            summary_line += f"\n{link}"

        company_id = body.get("company_id")
        contact_id = body.get("contact_id")
        if company_id or contact_id:
            try:
                await _log_activity(env,
                    company_id=int(company_id) if company_id else None,
                    contact_id=int(contact_id) if contact_id else None,
                    kind="user_activity",
                    type_="Meeting",
                    summary=summary_line,
                    author=session.get("email", ""),
                )
            except Exception:
                pass  # non-fatal if logging fails; the event was created

        return JSONResponse({
            "ok":       True,
            "id":       ev.get("id"),
            "htmlLink": link,
            "summary":  title,
            "start":    start,
            "end":      end,
        })

    # ── Guerilla Field Reports ─────────────────────────────────────────────────
    @fapp.post("/api/guerilla/log")
    async def guerilla_log(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
        env = _env()
        return await guerilla_api.guerilla_log(
            request, env["br"], env["bt"], session,
            bunny_zone=os.environ.get("BUNNY_STORAGE_ZONE", "techopssocialmedia"),
            bunny_key=os.environ.get("BUNNY_STORAGE_API_KEY", ""),
            bunny_cdn_base="https://techopssocialmedia.b-cdn.net",
        )


    # ── Massage Box CRUD ──────────────────────────────────────────────────────
    # Tables the field_rep app (Coolify) mirrors in its Redis cache. When the
    # hub writes to any of these, we POST the TID to field_rep's /api/invalidate
    # so reps see fresh data immediately instead of waiting for TTL to expire.
    _FIELD_REP_CACHE_TIDS = {
        T_GOR_VENUES, T_GOR_BOXES, T_GOR_ROUTES, T_GOR_ROUTE_STOPS,
        T_COMPANIES, T_ACTIVITIES,
    }

    async def _notify_field_rep_invalidate(*tids: int) -> None:
        """Fire-and-forget cache-bust to field_rep. Non-fatal on any error."""
        url   = os.environ.get("FIELD_REP_INVALIDATE_URL", "").strip()
        token = os.environ.get("FIELD_REP_INVALIDATE_TOKEN", "").strip()
        if not url or not token or not tids:
            return
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    url,
                    json={"tids": list(tids)},
                    headers={"X-Invalidate-Token": token},
                )
        except Exception:
            pass  # field_rep being down must not break hub writes

    def _invalidate(*tids: int) -> None:
        for tid in tids:
            try:
                hub_cache.pop(f"table:{tid}", None)
            except Exception:
                pass
        # Mirror the invalidation to the field_rep app for tables it caches.
        # Fire-and-forget via asyncio.create_task so the hub handler doesn't
        # block on the cross-app HTTP round-trip.
        mirror_tids = [t for t in tids if t in _FIELD_REP_CACHE_TIDS]
        if mirror_tids:
            try:
                import asyncio as _asyncio
                _asyncio.create_task(_notify_field_rep_invalidate(*mirror_tids))
            except RuntimeError:
                pass  # Not in an event loop — skip cross-app notify

    @fapp.post("/api/guerilla/boxes")
    async def create_box(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
        env = _env()
        resp = await guerilla_api.create_box(request, env["br"], env["bt"], session)
        _invalidate(T_GOR_BOXES)
        return resp

    @fapp.patch("/api/guerilla/boxes/{box_id}/pickup")
    async def pickup_box(request: Request, box_id: int):
        session = _get_session(request)
        if not session:
            return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
        env = _env()
        resp = await guerilla_api.pickup_box(request, env["br"], env["bt"], session, box_id)
        _invalidate(T_GOR_BOXES)
        return resp

    @fapp.patch("/api/guerilla/venues/{venue_id}")
    async def update_venue(request: Request, venue_id: int):
        session = _get_session(request)
        if not session:
            return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
        resp = await guerilla_api.update_venue(request, _env()["br"], _env()["bt"], session, venue_id)
        _invalidate(T_GOR_VENUES, T_COMPANIES)
        return resp

    @fapp.patch("/api/guerilla/boxes/{box_id}")
    async def update_box(request: Request, box_id: int):
        session = _get_session(request)
        if not session:
            return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
        env = _env()
        resp = await guerilla_api.update_box(request, env["br"], env["bt"], session, box_id)
        _invalidate(T_GOR_BOXES)
        return resp

    @fapp.patch("/api/guerilla/boxes/{box_id}/days")
    async def update_box_days(request: Request, box_id: int):
        session = _get_session(request)
        if not session:
            return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
        env = _env()
        resp = await guerilla_api.update_box_days(request, env["br"], env["bt"], session, box_id)
        _invalidate(T_GOR_BOXES)
        return resp

    # ── Route API Endpoints ───────────────────────────────────────────────────
    async def _hub_cached_rows(tid: int) -> list:
        env = _env()
        return await _cached_table(tid, env["br"], env["bt"])

    @fapp.get("/api/guerilla/routes/today")
    async def routes_today(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        env = _env()
        return await guerilla_api.routes_today(request, env["br"], env["bt"], session,
                                               _hub_cached_rows)

    @fapp.get("/api/guerilla/routes/{route_id}")
    async def route_detail(request: Request, route_id: int):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        env = _env()
        return await guerilla_api.route_detail(request, env["br"], env["bt"], session,
                                               route_id, _hub_cached_rows)

    @fapp.patch("/api/guerilla/routes/stops/{stop_id}")
    async def update_route_stop(request: Request, stop_id: int):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        env = _env()
        resp = await guerilla_api.update_route_stop(request, env["br"], env["bt"], session, stop_id)
        _invalidate(T_GOR_ROUTE_STOPS)
        return resp

    @fapp.post("/api/guerilla/routes")
    async def gorilla_routes_create(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        env = _env()
        resp = await guerilla_api.gorilla_routes_create(request, env["br"], env["bt"], session)
        _invalidate(T_GOR_ROUTES, T_GOR_ROUTE_STOPS)
        return resp

    @fapp.patch("/api/guerilla/routes/{route_id}/status")
    async def gorilla_route_status(request: Request, route_id: int):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        env = _env()
        resp = await guerilla_api.gorilla_route_status(request, env["br"], env["bt"], session, route_id)
        _invalidate(T_GOR_ROUTES)
        return resp

    @fapp.patch("/api/guerilla/routes/{route_id}")
    async def gorilla_route_update(request: Request, route_id: int):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        env = _env()
        resp = await guerilla_api.gorilla_route_update(request, env["br"], env["bt"], session,
                                                       route_id, _hub_cached_rows)
        _invalidate(T_GOR_ROUTES, T_GOR_ROUTE_STOPS)
        return resp

    @fapp.post("/api/guerilla/routes/{route_id}/stops")
    async def gorilla_route_append_stop(request: Request, route_id: int):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        env = _env()
        resp = await guerilla_api.gorilla_route_append_stop(request, env["br"], env["bt"], session,
                                                            route_id, _hub_cached_rows)
        _invalidate(T_GOR_ROUTE_STOPS)
        return resp

    @fapp.delete("/api/guerilla/routes/{route_id}")
    async def gorilla_route_delete(request: Request, route_id: int):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        env = _env()
        resp = await guerilla_api.gorilla_route_delete(request, env["br"], env["bt"], session,
                                                       route_id, _hub_cached_rows)
        _invalidate(T_GOR_ROUTES, T_GOR_ROUTE_STOPS)
        return resp

    # ── Outreach: overdue follow-ups across categories ────────────────────────
    @fapp.get("/api/outreach/due")
    async def outreach_due(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        from hub import outreach_api
        env = _env()
        return await outreach_api.get_outreach_due(env["br"], env["bt"], session,
                                                   _hub_cached_rows)

    # ── Social Poster Hub ──────────────────────────────────────────────────────
    @fapp.get("/social/inbox", response_class=HTMLResponse)
    async def social_inbox(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "social"): return RedirectResponse(url="/")
        return HTMLResponse(_social_inbox_page(br, bt, user=user))

    # Back-compat: legacy /social/poster URL redirects to the inbox
    @fapp.get("/social/poster", response_class=HTMLResponse)
    async def social_poster_legacy(request: Request):
        return RedirectResponse(url="/social/inbox")

    # ── Social Inbox API ───────────────────────────────────────────────────────
    @fapp.get("/api/social/notifications")
    async def social_notifications(request: Request):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        user = _get_user(request)
        if not _has_social_access(user):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        if not T_SOCIAL_NOTIFICATIONS:
            return JSONResponse({"rows": []})
        rows = await _fetch_table_all(
            os.environ.get("BASEROW_URL", ""),
            os.environ.get("BASEROW_API_TOKEN", ""),
            T_SOCIAL_NOTIFICATIONS,
        )
        def _sel(v):
            if isinstance(v, dict): return v.get("value", "") or ""
            return v or ""
        out = []
        for r in rows or []:
            out.append({
                "id":            r.get("id"),
                "source_id":     r.get("Source ID") or "",
                "platform":      _sel(r.get("Platform")),
                "kind":          _sel(r.get("Kind")),
                "author_name":   r.get("Author Name") or "",
                "author_handle": r.get("Author Handle") or "",
                "body":          r.get("Body") or "",
                "post_url":      r.get("Post URL") or "",
                "post_caption":  r.get("Post Caption") or "",
                "reply_url":     r.get("Reply URL") or "",
                "received_at":   r.get("Received At") or "",
                "status":        _sel(r.get("Status")) or "unread",
            })
        out.sort(key=lambda x: x.get("received_at", ""), reverse=True)
        return JSONResponse({"rows": out[:500]})

    @fapp.post("/api/social/notifications/{row_id}/read")
    async def social_notif_read(row_id: int, request: Request):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        user = _get_user(request)
        if not _has_social_access(user):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        br = os.environ.get("BASEROW_URL", "")
        bt = os.environ.get("BASEROW_API_TOKEN", "")
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.patch(
                f"{br}/api/database/rows/table/{T_SOCIAL_NOTIFICATIONS}/{row_id}/?user_field_names=true",
                headers={"Authorization": f"Token {bt}"},
                json={"Status": "read"},
            )
        try: hub_cache.pop(f"table:{T_SOCIAL_NOTIFICATIONS}", None)
        except Exception: pass
        return JSONResponse({"ok": r.is_success})

    @fapp.post("/api/social/notifications/mark-all-read")
    async def social_notif_mark_all(request: Request):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        user = _get_user(request)
        if not _has_social_access(user):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        br = os.environ.get("BASEROW_URL", "")
        bt = os.environ.get("BASEROW_API_TOKEN", "")
        rows = await _fetch_table_all(br, bt, T_SOCIAL_NOTIFICATIONS)
        unread_ids = [
            r["id"] for r in rows or []
            if (r.get("Status") or {}).get("value", r.get("Status")) in ("unread", {"value": "unread"})
               or r.get("Status") == "unread"
        ]
        updated = 0
        async with httpx.AsyncClient(timeout=40) as c:
            for rid in unread_ids:
                r = await c.patch(
                    f"{br}/api/database/rows/table/{T_SOCIAL_NOTIFICATIONS}/{rid}/?user_field_names=true",
                    headers={"Authorization": f"Token {bt}"},
                    json={"Status": "read"},
                )
                if r.is_success: updated += 1
        try: hub_cache.pop(f"table:{T_SOCIAL_NOTIFICATIONS}", None)
        except Exception: pass
        return JSONResponse({"ok": True, "updated": updated})

    @fapp.get("/api/social/connections")
    async def social_connections(request: Request):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        user = _get_user(request)
        if not _has_social_access(user):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        pages = []
        if os.environ.get("META_PAGE_ID"):
            pages.append({"platform": "facebook",  "id": os.environ.get("META_PAGE_ID")})
        if os.environ.get("INSTAGRAM_ACCOUNT_ID"):
            pages.append({"platform": "instagram", "id": os.environ.get("INSTAGRAM_ACCOUNT_ID")})
        status = None
        try: status = hub_cache.get("social-poll-status")
        except Exception: status = None
        return JSONResponse({
            "pages": pages,
            "last_poll": (status or {}).get("last_poll"),
            "inserted_last": (status or {}).get("inserted"),
        })

    @fapp.get("/oauth/meta/start")
    async def oauth_meta_start(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_social_access(user): return RedirectResponse(url="/")
        app_id = os.environ.get("META_APP_ID", "") or os.environ.get("FACEBOOK_APP_ID", "")
        if not app_id:
            return HTMLResponse(
                "<h3>Meta app credentials not configured</h3>"
                "<p>Add <code>META_APP_ID</code> to the <code>meta-secrets</code> Modal secret, "
                "then come back here. For now, the poller uses the existing <code>META_PAGE_TOKEN</code> — "
                "comments and mentions should still work.</p>"
                "<p><a href='/social/inbox'>&larr; Back to Inbox</a></p>",
                status_code=200,
            )
        redirect = os.environ.get("META_OAUTH_REDIRECT", "https://hub.reformchiropractic.app/oauth/meta/callback")
        scopes = "pages_show_list,pages_read_engagement,pages_messaging,pages_manage_metadata,instagram_basic,instagram_manage_comments"
        url = (
            "https://www.facebook.com/v22.0/dialog/oauth"
            f"?client_id={app_id}"
            f"&redirect_uri={quote(redirect)}"
            f"&scope={quote(scopes)}"
            "&response_type=code"
        )
        return RedirectResponse(url=url)

    @fapp.get("/oauth/meta/callback")
    async def oauth_meta_callback(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        code = request.query_params.get("code", "")
        if not code:
            err = request.query_params.get("error_description") or request.query_params.get("error") or "no code"
            return HTMLResponse(f"<h3>OAuth cancelled: {err}</h3><p><a href='/social/inbox'>&larr; Back</a></p>")
        return HTMLResponse(
            "<h3>Meta re-auth received</h3>"
            f"<p>Auth code captured (<code>{code[:10]}...</code>). Token exchange isn't wired yet — "
            "paste this code to the admin to swap the Modal secret. For now the inbox polls with the existing token.</p>"
            "<p><a href='/social/inbox'>&larr; Back to Inbox</a></p>"
        )

    # ── TikTok OAuth bootstrap ────────────────────────────────────────────────
    # One-time flow used to generate TIKTOK_REFRESH_TOKEN. Prereq: populate
    # TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET in the `tiktok-secrets` Modal
    # secret and redeploy. Visit /oauth/tiktok/start while logged into the
    # hub → TikTok → back to /oauth/tiktok/callback which exchanges the code
    # server-side and displays the refresh_token for copy-paste into the
    # Modal secret.
    @fapp.get("/oauth/tiktok/start")
    async def oauth_tiktok_start(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_social_access(user): return RedirectResponse(url="/")
        client_key = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
        if not client_key:
            return HTMLResponse(
                "<h3>TikTok client key not configured</h3>"
                "<p>Populate <code>TIKTOK_CLIENT_KEY</code> in the Modal "
                "<code>tiktok-secrets</code> secret and redeploy the hub, "
                "then visit this URL again.</p>"
                "<p><a href='/social/inbox'>&larr; Back to Inbox</a></p>",
                status_code=200,
            )
        redirect = "https://hub.reformchiropractic.app/oauth/tiktok/callback"
        scopes = "user.info.basic,user.info.profile,user.info.stats,video.list,video.upload"
        url = (
            "https://www.tiktok.com/v2/auth/authorize/"
            f"?client_key={quote(client_key)}"
            "&response_type=code"
            f"&scope={quote(scopes)}"
            f"&redirect_uri={quote(redirect)}"
        )
        return RedirectResponse(url=url)

    @fapp.get("/oauth/tiktok/callback")
    async def oauth_tiktok_callback(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_social_access(user):
            return HTMLResponse("<h3>Forbidden</h3>", status_code=403)
        code = (request.query_params.get("code") or "").strip()
        err = request.query_params.get("error", "")
        if err:
            err_desc = request.query_params.get("error_description") or err
            return HTMLResponse(f"<h3>TikTok OAuth cancelled: {err_desc}</h3>"
                                "<p><a href='/social/inbox'>&larr; Back</a></p>")
        if not code:
            return HTMLResponse("<h3>Missing <code>code</code> parameter</h3>", status_code=400)
        client_key = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
        client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
        if not client_key or not client_secret:
            return HTMLResponse(
                "<h3>TikTok credentials not configured</h3>"
                "<p>Populate <code>TIKTOK_CLIENT_KEY</code> and "
                "<code>TIKTOK_CLIENT_SECRET</code> in the Modal "
                "<code>tiktok-secrets</code> secret and redeploy the hub first.</p>",
                status_code=500,
            )
        redirect = "https://hub.reformchiropractic.app/oauth/tiktok/callback"
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                r = await client.post(
                    "https://open.tiktokapis.com/v2/oauth/token/",
                    data={
                        "client_key": client_key,
                        "client_secret": client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect,
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Cache-Control": "no-cache",
                    },
                )
            except Exception as ex:
                return HTMLResponse(f"<h3>Network error: {ex}</h3>", status_code=502)
        try:
            data = r.json()
        except Exception:
            return HTMLResponse(f"<h3>Unexpected response</h3><pre>{r.text}</pre>", status_code=502)
        refresh_token = data.get("refresh_token", "")
        access_token = data.get("access_token", "")
        scope_granted = data.get("scope", "") or ""
        if not refresh_token:
            return HTMLResponse(
                f"<h3>Token exchange failed</h3><pre>{data}</pre>",
                status_code=502,
            )
        scopes_html = "".join(
            f'<span class="scope-pill">{s.strip()}</span>'
            for s in scope_granted.split(",") if s.strip()
        )
        return HTMLResponse(f"""<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><title>TikTok OAuth — Success</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f8fafc;color:#1e293b;padding:40px 20px;line-height:1.6}}
.wrap{{max-width:720px;margin:0 auto;background:#fff;border-radius:12px;padding:40px;box-shadow:0 2px 12px rgba(0,0,0,.06)}}
h1{{color:#16a34a;margin-bottom:8px;font-size:24px}}
.sub{{color:#64748b;margin-bottom:24px;font-size:15px}}
.label{{font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.8px;margin-top:20px;margin-bottom:6px;display:block}}
.val-wrap{{position:relative}}
.val{{background:#f1f5f9;padding:14px 70px 14px 14px;border-radius:8px;font-family:ui-monospace,Menlo,monospace;font-size:13px;word-break:break-all;border:1px solid #e2e8f0}}
.copy-btn{{position:absolute;top:8px;right:8px;background:#ea580c;color:#fff;border:none;padding:6px 14px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer}}
.copy-btn:hover{{background:#dc2626}}
.copy-btn.done{{background:#16a34a}}
.scope-pill{{display:inline-block;background:#dbeafe;color:#1e40af;padding:3px 10px;border-radius:12px;font-size:12px;margin-right:4px;margin-bottom:4px}}
.note{{margin-top:28px;padding:14px 16px;background:#fff7ed;border-left:3px solid #ea580c;border-radius:4px;font-size:14px;color:#7c2d12}}
code{{background:#f1f5f9;padding:2px 6px;border-radius:4px;font-size:13px;font-family:ui-monospace,Menlo,monospace}}
.steps{{margin-top:8px;padding-left:20px}}
.steps li{{margin-top:6px}}
</style></head><body>
<div class="wrap">
<h1>✓ TikTok connected</h1>
<p class="sub">OAuth exchange succeeded. Paste the refresh token below into the Modal <code>tiktok-secrets</code> secret.</p>

<span class="label">TIKTOK_REFRESH_TOKEN (valid ~365 days)</span>
<div class="val-wrap">
  <div class="val" id="rt">{refresh_token}</div>
  <button class="copy-btn" onclick="copyIt('rt', this)">Copy</button>
</div>

<span class="label">TIKTOK_ACCESS_TOKEN (short-lived — optional; poller refreshes)</span>
<div class="val-wrap">
  <div class="val" id="at">{access_token}</div>
  <button class="copy-btn" onclick="copyIt('at', this)">Copy</button>
</div>

<span class="label">Scopes granted</span>
<div>{scopes_html}</div>

<div class="note">
<strong>Next steps:</strong>
<ol class="steps">
<li>Open <a href="https://modal.com/secrets" target="_blank">Modal Secrets dashboard</a> → <code>tiktok-secrets</code></li>
<li>Paste the refresh token above as <code>TIKTOK_REFRESH_TOKEN</code></li>
<li>(Optional) Paste the access token as <code>TIKTOK_ACCESS_TOKEN</code> — the poller refreshes automatically on first run anyway</li>
<li>Save. The engagement-digest poller picks up the new value on its next 15-minute tick. No redeploy needed — scheduled Modal functions spawn fresh containers each run.</li>
</ol>
</div>

</div>
<script>
function copyIt(id, btn) {{
  var txt = document.getElementById(id).innerText;
  navigator.clipboard.writeText(txt).then(function() {{
    btn.textContent = 'Copied!';
    btn.classList.add('done');
    setTimeout(function() {{ btn.textContent = 'Copy'; btn.classList.remove('done'); }}, 1800);
  }});
}}
</script>
</body></html>""")

    @fapp.get("/api/social/queue")
    async def social_queue(request: Request):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        user = _get_user(request)
        if not _has_social_access(user):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        zone = os.environ.get("BUNNY_STORAGE_ZONE", "")
        key  = os.environ.get("BUNNY_STORAGE_API_KEY", "")
        if not zone or not key:
            return JSONResponse({"error": "bunny not configured"}, status_code=500)
        import asyncio
        base = f"https://la.storage.bunnycdn.com/{zone}"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{base}/Scheduled/",
                headers={"AccessKey": key, "Accept": "application/json"})
            if not r.is_success:
                return JSONResponse([], status_code=200)
            files = [f for f in r.json() if (f.get("ObjectName") or "").endswith(".meta.json")]
            async def fetch_meta(f):
                mr = await client.get(f"{base}/Scheduled/{f['ObjectName']}",
                    headers={"AccessKey": key})
                if mr.is_success:
                    try: return mr.json()
                    except: return None
                return None
            metas = await asyncio.gather(*[fetch_meta(f) for f in files])
        return JSONResponse([m for m in metas if m])

    @fapp.get("/api/social/posted")
    async def social_posted(request: Request):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        user = _get_user(request)
        if not _has_social_access(user):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        zone = os.environ.get("BUNNY_STORAGE_ZONE", "")
        key  = os.environ.get("BUNNY_STORAGE_API_KEY", "")
        if not zone or not key:
            return JSONResponse({"error": "bunny not configured"}, status_code=500)
        import asyncio
        base = f"https://la.storage.bunnycdn.com/{zone}"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{base}/Posted/",
                headers={"AccessKey": key, "Accept": "application/json"})
            if not r.is_success:
                return JSONResponse([], status_code=200)
            files = [f for f in r.json() if (f.get("ObjectName") or "").endswith(".meta.json")]
            files.sort(key=lambda f: f.get("LastChanged", ""), reverse=True)
            files = files[:30]
            async def fetch_meta(f):
                mr = await client.get(f"{base}/Posted/{f['ObjectName']}",
                    headers={"AccessKey": key})
                if mr.is_success:
                    try: return mr.json()
                    except: return None
                return None
            metas = await asyncio.gather(*[fetch_meta(f) for f in files])
        return JSONResponse([m for m in metas if m])

    # ── Coming soon ────────────────────────────────────────────────────────────

    @fapp.get("/social", response_class=HTMLResponse)
    async def social(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "social"): return RedirectResponse(url="/")
        return HTMLResponse(_social_monitor_page(br, bt, user=user))

    # ── Queue control (Post now / Reschedule / Remove) ─────────────────────────
    SOCIAL_POSTER_WEBHOOK = "https://reformtechops--social-poster-post-to-socials-webhook.modal.run"

    import json as _json  # noqa: F401  (used by social queue mutations below)

    async def _bunny_ctx():
        zone = os.environ.get("BUNNY_STORAGE_ZONE", "")
        key  = os.environ.get("BUNNY_STORAGE_API_KEY", "")
        if not zone or not key:
            return None
        return {"zone": zone, "key": key, "base": f"https://la.storage.bunnycdn.com/{zone}"}

    async def _fetch_scheduled_meta(client, ctx, task_id):
        r = await client.get(f"{ctx['base']}/Scheduled/{task_id}.meta.json",
                             headers={"AccessKey": ctx["key"]})
        if not r.is_success:
            return None
        try: return r.json()
        except: return None

    @fapp.post("/api/social/post-now/{task_id}")
    async def social_post_now(task_id: str, request: Request):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        user = _get_user(request)
        if not _has_social_access(user):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        ctx = await _bunny_ctx()
        if not ctx:
            return JSONResponse({"error": "bunny not configured"}, status_code=500)
        async with httpx.AsyncClient(timeout=30) as client:
            meta = await _fetch_scheduled_meta(client, ctx, task_id)
            if not meta:
                return JSONResponse({"error": "not in queue"}, status_code=404)

            ct = meta.get("content_type") or "photo"
            if ct == "photo":
                platforms = ["instagram", "facebook"]
            else:
                platforms = ["instagram", "facebook", "tiktok", "youtube"]

            payload = {
                "platforms": platforms,
                "content_type": ct,
                "media_url": meta.get("media_url"),
                "caption": meta.get("caption", ""),
                "callback_url": "https://n8n1.reformchiropractic.app/webhook/social-posted",
                "job_id": f"hub-now-{task_id}",
                "metadata": {
                    "task_id": task_id,
                    "task_url": meta.get("task_url", ""),
                    "category": meta.get("category", ""),
                    "triggered_by": (user or {}).get("email", "hub"),
                },
            }
            wh = await client.post(SOCIAL_POSTER_WEBHOOK, json=payload)
            if not wh.is_success:
                return JSONResponse({"error": f"webhook rejected: {wh.status_code} {wh.text[:200]}"}, status_code=502)

            now_iso = datetime.utcnow().isoformat() + "Z"
            meta["status"] = "posting"
            meta["posted_at"] = now_iso
            meta["posted_by"] = (user or {}).get("email", "hub")
            put1 = await client.put(
                f"{ctx['base']}/Posted/{task_id}.meta.json",
                headers={"AccessKey": ctx["key"], "Content-Type": "application/json"},
                content=_json.dumps(meta),
            )
            if put1.is_success:
                await client.delete(
                    f"{ctx['base']}/Scheduled/{task_id}.meta.json",
                    headers={"AccessKey": ctx["key"]},
                )
            return JSONResponse({"ok": True, "task_id": task_id, "platforms": platforms})

    @fapp.post("/api/social/reschedule/{task_id}")
    async def social_reschedule(task_id: str, payload: dict, request: Request):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        user = _get_user(request)
        if not _has_social_access(user):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        new_when = (payload or {}).get("scheduled_at", "").strip()
        if not new_when:
            return JSONResponse({"error": "scheduled_at required"}, status_code=400)
        ctx = await _bunny_ctx()
        if not ctx:
            return JSONResponse({"error": "bunny not configured"}, status_code=500)
        async with httpx.AsyncClient(timeout=30) as client:
            meta = await _fetch_scheduled_meta(client, ctx, task_id)
            if not meta:
                return JSONResponse({"error": "not in queue"}, status_code=404)
            meta["scheduled_at"] = new_when
            r = await client.put(
                f"{ctx['base']}/Scheduled/{task_id}.meta.json",
                headers={"AccessKey": ctx["key"], "Content-Type": "application/json"},
                content=_json.dumps(meta),
            )
            if not r.is_success:
                return JSONResponse({"error": f"bunny write failed: {r.status_code}"}, status_code=502)
            return JSONResponse({"ok": True, "task_id": task_id, "scheduled_at": new_when})

    @fapp.delete("/api/social/remove/{task_id}")
    async def social_remove(task_id: str, request: Request):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        user = _get_user(request)
        if not _has_social_access(user):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        ctx = await _bunny_ctx()
        if not ctx:
            return JSONResponse({"error": "bunny not configured"}, status_code=500)
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.delete(
                f"{ctx['base']}/Scheduled/{task_id}.meta.json",
                headers={"AccessKey": ctx["key"]},
            )
            if not r.is_success and r.status_code != 404:
                return JSONResponse({"error": f"bunny delete failed: {r.status_code}"}, status_code=502)
            return JSONResponse({"ok": True, "task_id": task_id})

    @fapp.get("/social/history", response_class=HTMLResponse)
    async def social_history(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "social"): return RedirectResponse(url="/")
        return HTMLResponse(_coming_soon_page("social_history", "Social Media History", br, bt, user=user))

    @fapp.get("/calendar", response_class=HTMLResponse)
    async def calendar(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        return HTMLResponse(_calendar_page(br, bt, user=user))

    # ── Tickets (helpdesk) ─────────────────────────────────────────────────────
    @fapp.get("/tickets", response_class=HTMLResponse)
    async def tickets_list(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "tickets"): return RedirectResponse(url="/")
        return HTMLResponse(_tickets_list_page(br, bt, user=user))

    @fapp.get("/tickets/{ticket_id}", response_class=HTMLResponse)
    async def ticket_detail(request: Request, ticket_id: int):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "tickets"): return RedirectResponse(url="/")
        return HTMLResponse(_ticket_detail_page(ticket_id, br, bt, user=user))

    # ── Leads follow-up pipeline ───────────────────────────────────────────────
    @fapp.get("/leads", response_class=HTMLResponse)
    async def leads_list_page(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "leads"): return RedirectResponse(url="/")
        return HTMLResponse(_leads_list_page(br, bt, user=user))

    @fapp.get("/leads/{lead_id:int}", response_class=HTMLResponse)
    async def lead_detail_page(request: Request, lead_id: int):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "leads"): return RedirectResponse(url="/")
        return HTMLResponse(_lead_detail_page(lead_id, br, bt, user=user))

    @fapp.get("/tasks", response_class=HTMLResponse)
    async def tasks_page(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "tasks"): return RedirectResponse(url="/")
        return HTMLResponse(_tasks_page(br, bt, user=user))

    @fapp.get("/inbox", response_class=HTMLResponse)
    async def inbox_page_route(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "inbox"): return RedirectResponse(url="/")
        return HTMLResponse(_inbox_page(br, bt, user=user))

    @fapp.get("/sequences", response_class=HTMLResponse)
    async def sequences_list_route(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "sequences"): return RedirectResponse(url="/")
        return HTMLResponse(_sequences_list_page(br, bt, user=user))

    @fapp.get("/sequences/{seq_id:int}", response_class=HTMLResponse)
    async def sequence_detail_route(request: Request, seq_id: int):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "sequences"): return RedirectResponse(url="/")
        return HTMLResponse(_sequence_detail_page(seq_id, br, bt, user=user))

    # ── Sequences / Automations API ────────────────────────────────────────────
    def _sq_guard(request):
        session = _get_session(request)
        if not session:
            return None, JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not _has_hub_access(session, "sequences"):
            return None, JSONResponse({"error": "forbidden"}, status_code=403)
        if not T_SEQUENCES or not T_SEQUENCE_ENROLLMENTS:
            return None, JSONResponse({"error": "sequences tables not configured"}, status_code=503)
        return session, None

    async def _fire_trigger(trigger: str, *, subject_type: str = "",
                             subject_id: int = 0, subject_data: dict = None,
                             config_match: str = "",
                             enroller_email: str = ""):
        """Find every active Automation whose Trigger matches `trigger`
        (and whose Trigger Config matches `config_match` when non-empty) and
        start an Automation Run for the given subject.

        `subject_type`: "lead" | "company" | "person" (used to pull recipient
        data from `subject_data`).
        `subject_data`: the row dict for the subject (Email, Name, Phone, …).
        `enroller_email`: whose Gmail/identity the run should send from.
        Public endpoints with no signed-in user pass "" and the scheduler
        will mark send-email steps `needs_reauth` unless `AUTOMATION_DEFAULT_SENDER`
        is set and has a refreshable session.

        Safe to call from any mutation handler — errors are swallowed and
        logged so they can't break the parent request."""
        if not T_SEQUENCES or not T_SEQUENCE_ENROLLMENTS: return
        try:
            env = _env()
            autos = await _cached_table(T_SEQUENCES, env["br"], env["bt"])

            def _sel_v(v):
                if isinstance(v, dict): return v.get("value", "") or ""
                return v or ""

            matches = []
            for a in autos:
                if not a.get("Is Active"): continue
                if _sel_v(a.get("Trigger")) != trigger: continue
                cfg = (a.get("Trigger Config") or "").strip()
                if config_match:
                    if cfg and cfg != config_match: continue
                matches.append(a)
            if not matches: return

            # Pull recipient data from subject
            subject_data = subject_data or {}
            r_email = (subject_data.get("Email") or "").strip()
            r_name  = (subject_data.get("Name")  or "").strip()

            # Fallback sender for headless triggers
            if not enroller_email:
                enroller_email = os.environ.get("AUTOMATION_DEFAULT_SENDER", "") or ""

            import json as _json
            from datetime import datetime as _dt, timedelta as _td, timezone as _tz

            for auto in matches:
                try: steps = _json.loads(auto.get("Steps JSON") or "[]") or []
                except Exception: steps = []
                if not steps: continue
                first_delay = int(steps[0].get("delay_days", 0) or 0)
                next_at = (_dt.now(_tz.utc) + _td(days=first_delay)).isoformat()

                row = {
                    "Name":            r_email or (r_name or f"{subject_type}:{subject_id}"),
                    "Recipient Email": r_email,
                    "Recipient Name":  r_name,
                    "Sender Email":    enroller_email,
                    "Sequence":        [auto["id"]],
                    "Status":          "active",
                    "Current Step":    0,
                    "Next Send At":    next_at,
                    "Created":         _iso_now(),
                    "Updated":         _iso_now(),
                }
                if subject_type == "lead":
                    row["Lead ID"] = int(subject_id)
                elif subject_type == "company":
                    row["Company"] = [int(subject_id)]
                async with httpx.AsyncClient(timeout=20) as client:
                    await client.post(
                        f"{env['br']}/api/database/rows/table/{T_SEQUENCE_ENROLLMENTS}/?user_field_names=true",
                        headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                        json={k: v for k, v in row.items() if v not in (None, "")},
                    )
            _invalidate(T_SEQUENCE_ENROLLMENTS)
        except Exception as e:
            print(f"[_fire_trigger] swallowed error for {trigger}: {e}")

    @fapp.get("/api/sequences")
    async def api_sequences_list(request: Request):
        session, err = _sq_guard(request)
        if err: return err
        rows = await _cached_table(T_SEQUENCES, _env()["br"], _env()["bt"])
        return JSONResponse(rows)

    @fapp.post("/api/sequences")
    async def api_sequences_create(request: Request):
        session, err = _sq_guard(request)
        if err: return err
        env = _env()
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            return JSONResponse({"error": "name required"}, status_code=400)
        row = {
            "Name":           name,
            "Description":    body.get("description", ""),
            "Category":       body.get("category") or "other",
            "Steps JSON":     "[]",
            "Is Active":      False,
            "Trigger":        body.get("trigger") or "manual",
            "Trigger Config": body.get("trigger_config") or "",
            "Created":        _iso_now(),
            "Updated":        _iso_now(),
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{env['br']}/api/database/rows/table/{T_SEQUENCES}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=row,
            )
        if r.status_code not in (200, 201):
            return JSONResponse({"error": r.text[:400]}, status_code=r.status_code)
        _invalidate(T_SEQUENCES)
        return JSONResponse(r.json())

    @fapp.get("/api/sequences/{seq_id}")
    async def api_sequences_get(seq_id: int, request: Request):
        session, err = _sq_guard(request)
        if err: return err
        env = _env()
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{env['br']}/api/database/rows/table/{T_SEQUENCES}/{seq_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}"},
            )
        if r.status_code == 404: return JSONResponse({"error": "not found"}, status_code=404)
        if r.status_code != 200: return JSONResponse({"error": r.text[:300]}, status_code=r.status_code)
        return JSONResponse(r.json())

    @fapp.patch("/api/sequences/{seq_id}")
    async def api_sequences_update(seq_id: int, request: Request):
        session, err = _sq_guard(request)
        if err: return err
        body = await request.json()
        env = _env()
        import json as _json
        fields = {"Updated": _iso_now()}
        if "name"           in body: fields["Name"]            = body["name"]
        if "description"    in body: fields["Description"]     = body["description"]
        if "category"       in body: fields["Category"]        = body["category"]
        if "is_active"      in body: fields["Is Active"]       = bool(body["is_active"])
        if "trigger"        in body: fields["Trigger"]         = body["trigger"] or "manual"
        if "trigger_config" in body: fields["Trigger Config"]  = body["trigger_config"] or ""
        if "steps"       in body:
            steps = body["steps"]
            if not isinstance(steps, list):
                return JSONResponse({"error": "steps must be an array"}, status_code=400)
            # Minimal validation + normalization
            clean = []
            for s in steps:
                if not isinstance(s, dict): continue
                clean.append({
                    "delay_days": int(s.get("delay_days", 0) or 0),
                    "subject":    str(s.get("subject", "")),
                    "body":       str(s.get("body", "")),
                })
            fields["Steps JSON"] = _json.dumps(clean)
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.patch(
                f"{env['br']}/api/database/rows/table/{T_SEQUENCES}/{seq_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=fields,
            )
        if r.status_code not in (200, 201):
            return JSONResponse({"error": r.text[:400]}, status_code=r.status_code)
        _invalidate(T_SEQUENCES)
        return JSONResponse({"ok": True})

    @fapp.delete("/api/sequences/{seq_id}")
    async def api_sequences_delete(seq_id: int, request: Request):
        session, err = _sq_guard(request)
        if err: return err
        env = _env()
        # Mark all active/paused enrollments unenrolled before deleting.
        enrollments = await _cached_table(T_SEQUENCE_ENROLLMENTS, env["br"], env["bt"])
        def _lnk(v): return [x.get("id") if isinstance(x, dict) else x for x in (v or [])]
        live = [e for e in enrollments if seq_id in _lnk(e.get("Sequence"))
                and _sel(e.get("Status")) in ("active", "paused", "needs_reauth")]
        async with httpx.AsyncClient(timeout=60) as client:
            for e in live:
                await client.patch(
                    f"{env['br']}/api/database/rows/table/{T_SEQUENCE_ENROLLMENTS}/{e['id']}/?user_field_names=true",
                    headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                    json={"Status": "unenrolled", "Updated": _iso_now()},
                )
            await client.delete(
                f"{env['br']}/api/database/rows/table/{T_SEQUENCES}/{seq_id}/",
                headers={"Authorization": f"Token {env['bt']}"},
            )
        _invalidate(T_SEQUENCES, T_SEQUENCE_ENROLLMENTS)
        return JSONResponse({"ok": True})

    @fapp.get("/api/sequences/{seq_id}/enrollments")
    async def api_sequences_enrollments(seq_id: int, request: Request):
        session, err = _sq_guard(request)
        if err: return err
        env = _env()
        rows = await _cached_table(T_SEQUENCE_ENROLLMENTS, env["br"], env["bt"])
        def _lnk(v): return [x.get("id") if isinstance(x, dict) else x for x in (v or [])]
        matched = [r for r in rows if seq_id in _lnk(r.get("Sequence"))]
        matched.sort(key=lambda e: e.get("Created") or "", reverse=True)
        return JSONResponse(matched)

    @fapp.post("/api/sequences/{seq_id}/enroll")
    async def api_sequences_enroll(seq_id: int, request: Request):
        session, err = _sq_guard(request)
        if err: return err
        env = _env()
        body = await request.json()
        recipients = body.get("recipients") or []
        if not isinstance(recipients, list) or not recipients:
            return JSONResponse({"error": "recipients list required"}, status_code=400)

        # Load sequence to compute first-step delay
        async with httpx.AsyncClient(timeout=15) as client:
            sr = await client.get(
                f"{env['br']}/api/database/rows/table/{T_SEQUENCES}/{seq_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}"},
            )
        if sr.status_code != 200:
            return JSONResponse({"error": "sequence not found"}, status_code=404)
        seq = sr.json()
        import json as _json
        try: steps = _json.loads(seq.get("Steps JSON") or "[]") or []
        except Exception: steps = []
        if not steps:
            return JSONResponse({"error": "sequence has no steps yet"}, status_code=400)

        first_delay = int(steps[0].get("delay_days", 0) or 0)
        from datetime import datetime as _dt, timedelta as _td, timezone as _tz
        next_send = _dt.now(_tz.utc) + _td(days=first_delay)

        sender_email = session.get("email", "")
        created = []
        failed = []
        async with httpx.AsyncClient(timeout=60) as client:
            for rec in recipients:
                email = (rec.get("email") or "").strip()
                if not email:
                    failed.append({"email": "", "error": "missing email"}); continue
                row = {
                    "Name":            email,
                    "Recipient Email": email,
                    "Recipient Name":  (rec.get("name") or "").strip(),
                    "Sender Email":    sender_email,
                    "Sequence":        [seq_id],
                    "Status":          "active",
                    "Current Step":    0,
                    "Next Send At":    next_send.isoformat(),
                    "Created":         _iso_now(),
                    "Updated":         _iso_now(),
                }
                if rec.get("lead_id"):
                    try: row["Lead ID"] = int(rec["lead_id"])
                    except (TypeError, ValueError): pass
                if rec.get("company_id"):
                    try: row["Company"] = [int(rec["company_id"])]
                    except (TypeError, ValueError): pass
                r = await client.post(
                    f"{env['br']}/api/database/rows/table/{T_SEQUENCE_ENROLLMENTS}/?user_field_names=true",
                    headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                    json=row,
                )
                if r.status_code in (200, 201):
                    created.append(r.json().get("id"))
                else:
                    failed.append({"email": email, "error": r.text[:200]})
        _invalidate(T_SEQUENCE_ENROLLMENTS)
        return JSONResponse({"ok": True, "created": created, "failed": failed,
                              "next_send_at": next_send.isoformat()})

    @fapp.patch("/api/enrollments/{enr_id}")
    async def api_enrollment_update(enr_id: int, request: Request):
        session, err = _sq_guard(request)
        if err: return err
        env = _env()
        body = await request.json()
        allowed = {"status": "Status", "next_send_at": "Next Send At"}
        fields = {}
        for k_in, k_out in allowed.items():
            if k_in in body: fields[k_out] = body[k_in]
        if not fields:
            return JSONResponse({"error": "no fields"}, status_code=400)
        fields["Updated"] = _iso_now()
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.patch(
                f"{env['br']}/api/database/rows/table/{T_SEQUENCE_ENROLLMENTS}/{enr_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=fields,
            )
        if r.status_code not in (200, 201):
            return JSONResponse({"error": r.text[:300]}, status_code=r.status_code)
        _invalidate(T_SEQUENCE_ENROLLMENTS)
        return JSONResponse({"ok": True})

    @fapp.get("/reports", response_class=HTMLResponse)
    async def reports_page(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _is_admin(user): return RedirectResponse(url="/")
        return HTMLResponse(_coming_soon_page("reports", "Reports", br, bt, user=user))

    def _ld_guard(request):
        """Auth + hub check for /api/leads/* read endpoints (GET). Write
        endpoints that predate the hub (public POST /api/leads, etc.) keep
        their own lighter checks."""
        session = _get_session(request)
        if not session:
            return None, JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not _has_hub_access(session, "leads"):
            return None, JSONResponse({"error": "forbidden"}, status_code=403)
        if not T_LEADS:
            return None, JSONResponse({"error": "leads not configured"}, status_code=503)
        return session, None

    def _tk_guard(request):
        """Shared auth+hub check for /api/tickets/*. Returns (session, err_response) tuple."""
        session = _get_session(request)
        if not session:
            return None, JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not _has_hub_access(session, "tickets"):
            return None, JSONResponse({"error": "forbidden"}, status_code=403)
        if not T_TICKETS:
            return None, JSONResponse({"error": "tickets not configured"}, status_code=503)
        return session, None

    def _tk_now_iso():
        import datetime as _dt
        return _dt.datetime.now(_dt.timezone.utc).isoformat()

    def _tk_select(v):
        """Normalize Baserow select fields to string values."""
        if isinstance(v, dict): return v.get("value", "") or ""
        return v or ""

    @fapp.get("/api/tickets")
    async def api_tickets_list(request: Request):
        session, err = _tk_guard(request)
        if err: return err
        env = _env()
        rows = await _cached_table(T_TICKETS, env["br"], env["bt"])
        return JSONResponse(rows)

    @fapp.post("/api/tickets")
    async def api_tickets_create(request: Request):
        session, err = _tk_guard(request)
        if err: return err
        env = _env()
        body = await request.json()
        title = (body.get("title") or "").strip()
        if not title:
            return JSONResponse({"error": "title required"}, status_code=400)
        now = _tk_now_iso()
        payload = {
            "Title":       title,
            "Description": body.get("description") or "",
            "Status":      "Open",
            "Priority":    body.get("priority") or "Normal",
            "Category":    body.get("category") or "Other",
            "Reporter":    session.get("email", ""),
            "Assignee":    (body.get("assignee") or "").strip(),
            "Created":     now,
            "Updated":     now,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{env['br']}/api/database/rows/table/{T_TICKETS}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=payload,
            )
        if r.status_code not in (200, 201):
            return JSONResponse({"error": r.text}, status_code=r.status_code)
        ticket = r.json()
        ticket_id = ticket["id"]
        # System "creation" comment
        await _tk_post_system_comment(env, ticket_id, session.get("email", ""),
                                     f"{session.get('name') or session.get('email', 'Someone')} opened this ticket.",
                                     "creation")
        _invalidate(T_TICKETS)
        return JSONResponse(ticket)

    @fapp.get("/api/tickets/{ticket_id}")
    async def api_ticket_get(ticket_id: int, request: Request):
        session, err = _tk_guard(request)
        if err: return err
        env = _env()
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                f"{env['br']}/api/database/rows/table/{T_TICKETS}/{ticket_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}"},
            )
        if r.status_code == 404:
            return JSONResponse({"error": "not found"}, status_code=404)
        if r.status_code != 200:
            return JSONResponse({"error": r.text}, status_code=r.status_code)
        return JSONResponse(r.json())

    @fapp.patch("/api/tickets/{ticket_id}")
    async def api_ticket_update(ticket_id: int, request: Request):
        session, err = _tk_guard(request)
        if err: return err
        env = _env()
        body = await request.json()
        # Fetch current to compute diffs for system comments
        async with httpx.AsyncClient(timeout=20) as client:
            rget = await client.get(
                f"{env['br']}/api/database/rows/table/{T_TICKETS}/{ticket_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}"},
            )
        if rget.status_code != 200:
            return JSONResponse({"error": "ticket not found"}, status_code=404)
        current = rget.json()
        old_status = _tk_select(current.get("Status"))
        old_assignee = current.get("Assignee") or ""

        patch = {"Updated": _tk_now_iso()}
        if "status"      in body: patch["Status"]           = body["status"]
        if "priority"    in body: patch["Priority"]         = body["priority"]
        if "category"    in body: patch["Category"]         = body["category"]
        if "assignee"    in body: patch["Assignee"]         = (body["assignee"] or "").strip()
        if "description" in body: patch["Description"]      = body["description"]
        if "resolution"  in body: patch["Resolution Notes"] = body["resolution"]
        if "title"       in body: patch["Title"]            = body["title"]

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.patch(
                f"{env['br']}/api/database/rows/table/{T_TICKETS}/{ticket_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=patch,
            )
        if r.status_code != 200:
            return JSONResponse({"error": r.text}, status_code=r.status_code)

        actor = session.get("name") or session.get("email", "Someone")
        # Status change → system comment
        new_status = body.get("status")
        if new_status and new_status != old_status:
            await _tk_post_system_comment(env, ticket_id, session.get("email", ""),
                                         f"{actor} changed status from {old_status or '(none)'} to {new_status}.",
                                         "status_change")
        # Assignee change → system comment
        if "assignee" in body:
            new_assignee = (body["assignee"] or "").strip()
            if new_assignee != old_assignee:
                if new_assignee and old_assignee:
                    msg = f"{actor} reassigned from {old_assignee} to {new_assignee}."
                elif new_assignee:
                    msg = f"{actor} assigned to {new_assignee}."
                else:
                    msg = f"{actor} unassigned {old_assignee}."
                await _tk_post_system_comment(env, ticket_id, session.get("email", ""),
                                             msg, "assignment")
        _invalidate(T_TICKETS)
        return JSONResponse(r.json())

    async def _tk_post_system_comment(env, ticket_id, author_email, body_text, kind):
        """Write a Ticket Comments row (internal helper)."""
        if not T_TICKET_COMMENTS: return
        payload = {
            "Ticket":  [ticket_id],
            "Author":  "system" if kind != "comment" else author_email,
            "Body":    body_text,
            "Kind":    kind,
            "Created": _tk_now_iso(),
        }
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(
                f"{env['br']}/api/database/rows/table/{T_TICKET_COMMENTS}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=payload,
            )
        _invalidate(T_TICKET_COMMENTS)

    @fapp.get("/api/tickets/{ticket_id}/comments")
    async def api_ticket_comments_list(ticket_id: int, request: Request):
        session, err = _tk_guard(request)
        if err: return err
        env = _env()
        rows = await _cached_table(T_TICKET_COMMENTS, env["br"], env["bt"])
        # Filter to this ticket — link_row values come back as list of {"id", "value"} dicts
        def _links(row):
            v = row.get("Ticket") or []
            return [x.get("id") if isinstance(x, dict) else x for x in v]
        matched = [r for r in rows if ticket_id in _links(r)]
        return JSONResponse(matched)

    @fapp.post("/api/tickets/{ticket_id}/comments")
    async def api_ticket_comment_create(ticket_id: int, request: Request):
        session, err = _tk_guard(request)
        if err: return err
        env = _env()
        body = await request.json()
        text = (body.get("body") or "").strip()
        if not text:
            return JSONResponse({"error": "body required"}, status_code=400)
        payload = {
            "Ticket":  [ticket_id],
            "Author":  session.get("email", ""),
            "Body":    text,
            "Kind":    "comment",
            "Created": _tk_now_iso(),
        }
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{env['br']}/api/database/rows/table/{T_TICKET_COMMENTS}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=payload,
            )
        if r.status_code not in (200, 201):
            return JSONResponse({"error": r.text}, status_code=r.status_code)
        # Bump Updated on parent ticket
        async with httpx.AsyncClient(timeout=20) as client:
            await client.patch(
                f"{env['br']}/api/database/rows/table/{T_TICKETS}/{ticket_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json={"Updated": _tk_now_iso()},
            )
        _invalidate(T_TICKET_COMMENTS, T_TICKETS)
        return JSONResponse(r.json())

    # ── CRM detail pages (Phase 3) ────────────────────────────────────────────
    @fapp.get("/companies/{company_id}", response_class=HTMLResponse)
    async def company_detail(request: Request, company_id: int):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "communications"): return RedirectResponse(url="/")
        return HTMLResponse(_company_detail_page(company_id, br, bt, user=user))

    @fapp.get("/people", response_class=HTMLResponse)
    async def people_list(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "communications"): return RedirectResponse(url="/")
        return HTMLResponse(_people_list_page(br, bt, user=user))

    @fapp.get("/people/{person_id}", response_class=HTMLResponse)
    async def person_detail(request: Request, person_id: int):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "communications"): return RedirectResponse(url="/")
        return HTMLResponse(_person_detail_page(person_id, br, bt, user=user))

    # ── Settings ───────────────────────────────────────────────────────────────
    @fapp.get("/settings", response_class=HTMLResponse)
    async def settings(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        return HTMLResponse(_settings_page(br, bt, user=user))

    @fapp.post("/api/settings/view-as")
    async def settings_view_as(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not _can_view_as(session):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        body = await request.json()
        hubs = body.get("hubs", [])
        if not isinstance(hubs, list):
            return JSONResponse({"error": "hubs must be a list"}, status_code=400)
        hubs = [h for h in hubs if h in ALL_HUB_KEYS]
        sid = request.cookies.get(SESSION_COOKIE)
        if sid:
            session["view_as_hubs"] = hubs
            hub_sessions[sid] = session
        return JSONResponse({"ok": True, "hubs": hubs})

    @fapp.post("/api/settings/view-as/clear")
    async def settings_view_as_clear(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not _can_view_as(session):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        sid = request.cookies.get(SESSION_COOKIE)
        if sid and "view_as_hubs" in session:
            del session["view_as_hubs"]
            hub_sessions[sid] = session
        return JSONResponse({"ok": True})

    # ── Events & Leads ─────────────────────────────────────────────────────────

    @fapp.get("/events", response_class=HTMLResponse)
    async def events_index(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "events"): return RedirectResponse(url="/")
        return HTMLResponse(_events_index_page(br, bt, user=user))

    @fapp.get("/events/{event_id}", response_class=HTMLResponse)
    async def event_detail(request: Request, event_id: int):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "events"): return RedirectResponse(url="/")
        return HTMLResponse(_event_detail_page(event_id, br, bt, user=user))

    @fapp.get("/leads/by-event", response_class=HTMLResponse)
    async def leads_by_event(request: Request):
        """Legacy events-grouped leads dashboard. The primary /leads page now
        renders the full follow-up pipeline (hub/leads.py); this view is kept
        as a secondary tool for triaging leads captured at specific events."""
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        if not _has_hub_access(user, "guerilla"): return RedirectResponse(url="/")
        return HTMLResponse(_leads_dashboard_page(br, bt, user=user))

    @fapp.get("/form/{slug}", response_class=HTMLResponse)
    async def public_lead_form(slug: str):
        """Public lead capture form — no auth required."""
        if not T_EVENTS:
            return HTMLResponse("<h1>Not configured</h1>", status_code=503)
        env = _env()
        events = await _cached_table(T_EVENTS, env["br"], env["bt"])
        event = next((e for e in events if e.get("Form Slug") == slug), None)
        if not event:
            return HTMLResponse("<h1>Form not found</h1>", status_code=404)
        name = event.get("Name") or "Reform Chiropractic Event"
        return HTMLResponse(_lead_form_page(name, slug))

    # ── Public booking (/book) ─────────────────────────────────────────────────
    @fapp.get("/book", response_class=HTMLResponse)
    async def public_booking(request: Request):
        """Public self-booking page — no auth. Prospective patients pick a
        slot; POST /api/book creates the T_LEADS row."""
        from hub.booking import _booking_page
        q = dict(request.query_params)
        slug = (q.get("slug") or "").strip()
        # Optional ?event=... overrides the header title (useful for events).
        event_name = (q.get("event") or "").strip() or "Book a Consultation"
        # If `slug` corresponds to an active Event, pull its Name for the header.
        if slug and T_EVENTS:
            try:
                events = await _cached_table(T_EVENTS, _env()["br"], _env()["bt"])
                ev = next((e for e in events if e.get("Form Slug") == slug), None)
                if ev and ev.get("Name"):
                    event_name = ev["Name"]
            except Exception:
                pass
        return HTMLResponse(_booking_page(event_name=event_name, slug=slug))

    # ── Public legal pages (/legal/terms, /legal/privacy) ──────────────────────
    # Required by third-party developer portals (TikTok, Meta, etc.) so their
    # app-registration forms have a functioning ToS + Privacy URL to link to.
    @fapp.get("/legal/terms", response_class=HTMLResponse)
    async def legal_terms():
        from hub.legal import _terms_page
        return HTMLResponse(_terms_page())

    @fapp.get("/legal/privacy", response_class=HTMLResponse)
    async def legal_privacy():
        from hub.legal import _privacy_page
        return HTMLResponse(_privacy_page())

    # ── Public attorney micro-portal (/a/{slug}) ──────────────────────────────
    # Read-only branded page per referring firm showing their active patients.
    # No login — the slug IS the auth. Treat slugs like Calendly/Notion-public
    # share links. Requires Portal Enabled=true on the Company row.
    @fapp.get("/a/{slug}", response_class=HTMLResponse)
    async def attorney_portal(slug: str, request: Request):
        from hub.attorney_portal import _portal_page, _not_found_page
        from hub.case_packets import _normalize_firm
        if not T_COMPANIES:
            return HTMLResponse(_not_found_page(), status_code=404)
        env = _env()
        br, bt = env["br"], env["bt"]
        try:
            companies = await _cached_table(T_COMPANIES, br, bt)
        except Exception:
            return HTMLResponse(_not_found_page(), status_code=404)
        # Match slug case-sensitively (slugs are random tokens, not user-typed)
        firm = next(
            (c for c in (companies or [])
             if (c.get("Portal Slug") or "").strip() == slug
             and c.get("Portal Enabled")
             and (_sv_local(c.get("Category")) or "").lower() == "attorney"),
            None,
        )
        if not firm:
            return HTMLResponse(_not_found_page(), status_code=404)

        # Fetch patients for each open stage + filter by normalized firm name match
        firm_norm = _normalize_firm(firm.get("Name") or "")
        patients_by_stage: dict = {"active": [], "awaiting": [], "billed": []}
        latest_update = ""
        stage_tids = [
            ("active",   T_PI_ACTIVE),
            ("awaiting", T_PI_AWAITING),
            ("billed",   T_PI_BILLED),
        ]
        for stage_key, tid in stage_tids:
            if not tid: continue
            try:
                rows = await _cached_table(tid, br, bt)
            except Exception:
                rows = []
            for p in rows or []:
                # Match on any of the firm-name fields the PI sheet uses
                firm_on_patient = (
                    _normalize_firm(p.get("Law Firm Name ONLY") or "")
                    or _normalize_firm(p.get("Law Firm Name") or "")
                    or _normalize_firm(p.get("Law Firm") or "")
                )
                if firm_on_patient and firm_on_patient == firm_norm:
                    patients_by_stage[stage_key].append(p)
                    upd = p.get("Updated") or p.get("Created") or ""
                    if upd and upd > latest_update:
                        latest_update = upd

        # Increment view count + update last viewed (best effort; non-fatal)
        try:
            current_count = int(firm.get("Portal View Count") or 0)
            async with httpx.AsyncClient(timeout=10) as client:
                await client.patch(
                    f"{br}/api/database/rows/table/{T_COMPANIES}/{firm['id']}/?user_field_names=true",
                    headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
                    json={
                        "Portal View Count":  current_count + 1,
                        "Portal Last Viewed": _iso_now(),
                    },
                )
            _invalidate(T_COMPANIES)
        except Exception:
            pass

        html = _portal_page(firm, patients_by_stage, last_updated_iso=latest_update)
        return HTMLResponse(
            html,
            headers={
                "X-Robots-Tag":      "noindex, nofollow, noarchive",
                "Cache-Control":     "private, no-store",
                "Referrer-Policy":   "no-referrer",
            },
        )

    @fapp.post("/a/{slug}/request-packet")
    async def attorney_request_packet(slug: str, request: Request):
        """Public endpoint — attorney portal button. Logs a CRM activity on
        the firm so staff see the request in their feed. No auth (slug is auth)."""
        if not T_COMPANIES:
            return JSONResponse({"ok": False, "error": "not configured"}, status_code=404)
        # Light rate-limit: 1 request / slug / 20s via hub_cache
        rate_key = f"portal-rate:{slug}"
        try:
            last = hub_cache.get(rate_key)
            if last and (time.time() - float(last)) < 20:
                return JSONResponse({"ok": False, "error": "slow down"}, status_code=429)
            hub_cache[rate_key] = time.time()
        except Exception:
            pass
        body = await request.json()
        patient_id = body.get("patient_id")
        patient_name = (body.get("patient_name") or "").strip()[:120] or "(unknown)"

        env = _env()
        br, bt = env["br"], env["bt"]
        try:
            companies = await _cached_table(T_COMPANIES, br, bt)
        except Exception:
            return JSONResponse({"ok": False, "error": "not configured"}, status_code=503)
        firm = next(
            (c for c in (companies or [])
             if (c.get("Portal Slug") or "").strip() == slug
             and c.get("Portal Enabled")),
            None,
        )
        if not firm:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)

        try:
            await _log_activity(
                env,
                company_id=firm["id"],
                kind="user_activity",
                type_="Case Packet Requested",
                summary=f"Attorney-portal visitor requested a case packet for '{patient_name}' (patient id: {patient_id or 'n/a'}). Follow up via /patients to send.",
                author="attorney-portal",
            )
        except Exception as e:
            return JSONResponse({"ok": False, "error": f"log failed: {e}"}, status_code=500)

        return JSONResponse({"ok": True})

    # Helper: single-source the single_select unwrap used above. Mirror of
    # _sv in hub.attorney_portal but scoped here to avoid an import round-trip
    # inside the hot path.
    def _sv_local(v):
        if isinstance(v, dict): return v.get("value", "") or ""
        return v or ""

    # ── Admin: regenerate portal slug for a company ───────────────────────────
    @fapp.post("/api/companies/{company_id}/portal/regenerate")
    async def portal_regenerate_slug(company_id: int, request: Request):
        session, err = _crm_guard(request)
        if err: return err
        from hub.attorney_portal import generate_slug
        new_slug = generate_slug()
        env = _env()
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.patch(
                f"{env['br']}/api/database/rows/table/{T_COMPANIES}/{company_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json={"Portal Slug": new_slug, "Updated": _iso_now()},
            )
        if r.status_code != 200:
            return JSONResponse({"error": r.text}, status_code=r.status_code)
        try:
            await _log_activity(
                env, company_id=company_id, kind="edit",
                summary=f"{session.get('name') or session.get('email')} regenerated portal slug.",
                author=session.get("email", ""),
            )
        except Exception:
            pass
        _invalidate(T_COMPANIES)
        return JSONResponse({"ok": True, "slug": new_slug})

    @fapp.post("/api/book")
    async def create_booking(request: Request):
        """Public booking submission. Creates a T_LEADS row with Status=
        Appointment Scheduled and the chosen Appointment Date. No auth."""
        if not T_LEADS:
            return JSONResponse({"ok": False, "error": "leads table not configured"}, status_code=503)
        body = await request.json()
        name  = (body.get("name") or "").strip()
        phone = (body.get("phone") or "").strip()
        email = (body.get("email") or "").strip()
        reason = (body.get("reason") or "").strip()
        slug  = (body.get("slug") or "").strip()
        appointment = (body.get("appointment") or "").strip()  # ISO "YYYY-MM-DDTHH:MM:00"

        if not name or not phone:
            return JSONResponse({"ok": False, "error": "name and phone required"}, status_code=400)
        if not appointment or "T" not in appointment:
            return JSONResponse({"ok": False, "error": "appointment slot required"}, status_code=400)

        # Validate appointment is in the future (reject obvious past bookings).
        try:
            from datetime import datetime as _dt
            appt_dt = _dt.fromisoformat(appointment.replace("Z", ""))
            if appt_dt < _dt.now():
                return JSONResponse({"ok": False, "error": "appointment is in the past"}, status_code=400)
        except Exception:
            return JSONResponse({"ok": False, "error": "invalid appointment format"}, status_code=400)

        env = _env()

        # Determine source + optional Event link
        source = "Public booking"
        event_link = None
        if slug and T_EVENTS:
            try:
                events = await _cached_table(T_EVENTS, env["br"], env["bt"])
                ev = next((e for e in events if e.get("Form Slug") == slug), None)
                if ev:
                    source = ev.get("Name") or source
                    event_link = ev.get("id")
            except Exception:
                pass

        fields = {
            "Name":              name,
            "Phone":             phone,
            "Status":            "Appointment Scheduled",
            "Source":            source,
            "Reason":             reason,
            "Appointment Date":  appointment,
            "Stage Changed At":  _iso_now(),
            "Created":           _iso_now(),
            "Updated":           _iso_now(),
        }
        if email:      fields["Email"] = email
        if event_link: fields["Event"] = [int(event_link)]

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{env['br']}/api/database/rows/table/{T_LEADS}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=fields,
            )
        if r.status_code not in (200, 201):
            return JSONResponse({"ok": False, "error": r.text[:400]}, status_code=500)
        _invalidate(T_LEADS)

        # Bump Event's Lead Count if this was tied to an event (matches /api/leads).
        if event_link and T_EVENTS:
            try:
                events = await _cached_table(T_EVENTS, env["br"], env["bt"])
                ev = next((e for e in events if e.get("id") == int(event_link)), None)
                if ev:
                    cur_count = ev.get("Lead Count") or 0
                    async with httpx.AsyncClient(timeout=15) as client:
                        await client.patch(
                            f"{env['br']}/api/database/rows/table/{T_EVENTS}/{ev['id']}/?user_field_names=true",
                            headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                            json={"Lead Count": cur_count + 1},
                        )
                    _invalidate(T_EVENTS)
            except Exception:
                pass

        lead_id = r.json().get("id") or 0
        # Fire triggers: new_lead + lead_stage_changed (to:Appointment Scheduled)
        try:
            await _fire_trigger("new_lead", subject_type="lead",
                                 subject_id=lead_id, subject_data=fields,
                                 enroller_email="")
            await _fire_trigger("lead_stage_changed", subject_type="lead",
                                 subject_id=lead_id, subject_data=fields,
                                 config_match="to:Appointment Scheduled",
                                 enroller_email="")
        except Exception as _e:
            print(f"[book trigger] {_e}")

        return JSONResponse({"ok": True, "id": lead_id, "appointment": appointment})

    @fapp.post("/api/leads")
    async def create_lead(request: Request):
        """Public endpoint — no auth required. Creates a lead from the form."""
        if not T_EVENTS or not T_LEADS:
            return JSONResponse({"ok": False, "error": "not configured"}, status_code=503)
        body = await request.json()
        slug = (body.get("slug") or "").strip()
        name = (body.get("name") or "").strip()
        phone = (body.get("phone") or "").strip()
        email = (body.get("email") or "").strip()
        reason = (body.get("reason") or "").strip()
        if not name or not phone:
            return JSONResponse({"ok": False, "error": "name and phone required"}, status_code=400)
        env = _env()
        br, bt = env["br"], env["bt"]
        # Find event by slug
        events = await _cached_table(T_EVENTS, br, bt)
        event = next((e for e in events if e.get("Form Slug") == slug), None)
        if not event:
            return JSONResponse({"ok": False, "error": "event not found"}, status_code=404)
        fields = {
            "Name": name,
            "Phone": phone,
            "Status": "New",
            "Source": event.get("Name") or slug,
            "Event": [{"id": event["id"]}],
        }
        if email: fields["Email"] = email
        if reason: fields["Reason"] = reason
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{br}/api/database/rows/table/{T_LEADS}/?user_field_names=true",
                headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
                json=fields,
            )
            # Update lead count on event
            cur_count = event.get("Lead Count") or 0
            await client.patch(
                f"{br}/api/database/rows/table/{T_EVENTS}/{event['id']}/?user_field_names=true",
                headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
                json={"Lead Count": cur_count + 1},
            )
        if r.status_code in (200, 201):
            try:
                hub_cache.pop(f"table:{T_LEADS}")
                hub_cache.pop(f"table:{T_EVENTS}")
            except Exception:
                pass
            try:
                created = r.json()
                await _fire_trigger("new_lead", subject_type="lead",
                                     subject_id=created.get("id") or 0,
                                     subject_data=fields, enroller_email="")
            except Exception:
                pass
            return JSONResponse({"ok": True})
        return JSONResponse({"ok": False, "error": r.text[:200]}, status_code=500)

    @fapp.post("/api/leads/capture")
    async def capture_lead(request: Request):
        """Authenticated endpoint for field reps to capture leads.

        Thin wrapper around `hub.guerilla_api.capture_lead`. On successful
        insert, fires the `new_lead` automation trigger so sequences enroll
        the new lead. The field-rep app uses the same shared handler without
        the trigger (automations run on Modal; field_rep is a separate app)."""
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        env = _env()
        br, bt = env["br"], env["bt"]

        async def _cached(tid: int) -> list:
            return await _cached_table(tid, br, bt)

        async def _invalidate_tables(*tids: int) -> None:
            for tid in tids:
                try: hub_cache.pop(f"table:{tid}", None)
                except Exception: pass

        async def _on_created(created: dict, fields: dict) -> None:
            await _fire_trigger(
                "new_lead", subject_type="lead",
                subject_id=created.get("id") or 0,
                subject_data=fields,
                enroller_email=session.get("email", ""),
            )

        from hub.guerilla_api import capture_lead as _shared_capture
        return await _shared_capture(
            request, br, bt, session,
            cached_rows=_cached,
            on_created=_on_created,
            invalidate=_invalidate_tables,
        )

    # ── Leads follow-up API ────────────────────────────────────────────────
    # `GET /api/leads` + `GET /api/leads/{id}` are new (hub-gated reads).
    # `PATCH /api/leads/{id}` is the extended version — handles every new
    # field + auto-stamps stage-transition dates. Replaces the previous
    # narrow implementation without breaking the contract (status+notes
    # callers keep working).
    # `POST /api/leads` (public lead-form) and `/api/leads/capture` (field
    # reps) remain unchanged above.

    @fapp.get("/api/leads")
    async def api_leads_list(request: Request):
        session, err = _ld_guard(request)
        if err: return err
        rows = await _cached_table(T_LEADS, _env()["br"], _env()["bt"])
        return JSONResponse(rows)

    @fapp.get("/api/leads/{lead_id}")
    async def api_lead_get(lead_id: int, request: Request):
        session, err = _ld_guard(request)
        if err: return err
        env = _env()
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                f"{env['br']}/api/database/rows/table/{T_LEADS}/{lead_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}"},
            )
        if r.status_code == 404: return JSONResponse({"error": "not found"}, status_code=404)
        if r.status_code != 200: return JSONResponse({"error": r.text}, status_code=r.status_code)
        lead = r.json()
        # Enrich with referred-by Company + Person names for chip rendering.
        comp_id = lead.get("Referred By Company ID")
        pers_id = lead.get("Referred By Person ID")
        if comp_id and T_COMPANIES:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    rr = await client.get(
                        f"{env['br']}/api/database/rows/table/{T_COMPANIES}/{int(comp_id)}/?user_field_names=true",
                        headers={"Authorization": f"Token {env['bt']}"},
                    )
                if rr.status_code == 200:
                    lead["_refCompany"] = {"id": int(comp_id), "name": rr.json().get("Name", "")}
            except Exception:
                pass
        if pers_id and T_CONTACTS:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    rr = await client.get(
                        f"{env['br']}/api/database/rows/table/{T_CONTACTS}/{int(pers_id)}/?user_field_names=true",
                        headers={"Authorization": f"Token {env['bt']}"},
                    )
                if rr.status_code == 200:
                    lead["_refPerson"] = {"id": int(pers_id), "name": rr.json().get("Name", "")}
            except Exception:
                pass
        return JSONResponse(lead)

    @fapp.post("/api/leads/crm")
    async def api_lead_crm_create(request: Request):
        """Authenticated CRM-native lead creator. Used by the /leads + Company/
        Person detail pages. Accepts referral-source IDs that the public
        POST /api/leads endpoint doesn't know about."""
        session, err = _ld_guard(request)
        if err: return err
        body = await request.json()
        name  = (body.get("name") or "").strip()
        phone = (body.get("phone") or "").strip()
        if not name:
            return JSONResponse({"ok": False, "error": "name required"}, status_code=400)
        env = _env()
        email = session.get("email", "")
        fields = {
            "Name":    name,
            "Phone":   phone,
            "Status":  "New",
            "Source":  (body.get("source") or "").strip(),
            "Reason":  (body.get("reason") or "").strip(),
            "Notes":   (body.get("notes") or "").strip(),
            "Owner":   (body.get("owner") or "").strip() or email,
            "Created": _iso_now(),
            "Updated": _iso_now(),
            "Stage Changed At": _iso_now(),
        }
        if body.get("email"):
            fields["Email"] = (body.get("email") or "").strip()
        if body.get("follow_up_date"):
            fields["Follow-Up Date"] = body["follow_up_date"]
        # Referral source IDs — plain numbers (cross-DB link_rows forbidden)
        for k_out, k_in in (("Referred By Company ID", "referred_by_company_id"),
                            ("Referred By Person ID",  "referred_by_person_id")):
            v = body.get(k_in)
            if v:
                try: fields[k_out] = int(v)
                except (TypeError, ValueError): pass
        clean = {k: v for k, v in fields.items() if v not in (None, "")}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{env['br']}/api/database/rows/table/{T_LEADS}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=clean,
            )
        if r.status_code not in (200, 201):
            return JSONResponse({"ok": False, "error": r.text[:400]}, status_code=r.status_code)
        _invalidate(T_LEADS)
        created = r.json()
        lid = created.get("id")
        # Log an Activity on the referring Company/Person so their feed shows this lead.
        try:
            if body.get("referred_by_company_id") or body.get("referred_by_person_id"):
                await _log_activity(
                    env,
                    company_id=int(body["referred_by_company_id"]) if body.get("referred_by_company_id") else None,
                    contact_id=int(body["referred_by_person_id"])  if body.get("referred_by_person_id")  else None,
                    kind="user_activity",
                    type_="Referral",
                    summary=f"New lead logged: {name} ({phone}) — Source: {fields.get('Source','—')}",
                    author=email,
                )
        except Exception:
            pass
        # Fire new_lead trigger
        try:
            await _fire_trigger("new_lead", subject_type="lead",
                                 subject_id=lid or 0, subject_data=clean,
                                 enroller_email=email)
        except Exception:
            pass
        return JSONResponse({"ok": True, "id": lid})

    @fapp.patch("/api/leads/{lead_id}")
    async def update_lead(request: Request, lead_id: int):
        """Extended PATCH — handles every lead field, auto-stamps stage-
        transition dates, logs an Activity on the referring Company/Person
        for stage changes. Backward compatible with old `status`/`notes`
        payloads used by events.py and legacy callers."""
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        body = await request.json()
        env = _env()
        email = session.get("email", "")
        from datetime import date as _date
        today = _date.today().isoformat()

        # Fetch current lead to compute old vs new status (for auto-stamps
        # + activity logging).
        prev = None
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                rr = await client.get(
                    f"{env['br']}/api/database/rows/table/{T_LEADS}/{lead_id}/?user_field_names=true",
                    headers={"Authorization": f"Token {env['bt']}"},
                )
            if rr.status_code == 200: prev = rr.json()
        except Exception:
            pass

        def _sel(v):
            if isinstance(v, dict): return v.get("value", "") or ""
            return v or ""

        fields = {}

        # Back-compat + extended status handling
        if "status" in body:
            new_status = body["status"]
            fields["Status"] = new_status
            fields["Stage Changed At"] = _iso_now()
            # Auto-stamp transition dates
            if new_status == "Contacted":
                fields["Contacted At"] = today
                fields["Contacted By"] = email
            if new_status == "Appointment Scheduled":
                # Only stamp if not already set
                if not prev or not prev.get("Appointment Date"):
                    fields["Appointment Date"] = _iso_now()
            if new_status == "Seen":
                if not prev or not prev.get("Seen Date"):
                    fields["Seen Date"] = today
            if new_status == "Converted":
                if not prev or not prev.get("Converted Date"):
                    fields["Converted Date"] = today

        # Profile/contact fields
        _mapping = {
            "name":            "Name",
            "phone":           "Phone",
            "email":           "Email",
            "source":          "Source",
            "reason":          "Reason",
            "notes":           "Notes",
            "owner":           "Owner",
            "follow_up_date":  "Follow-Up Date",
            "call_status":     "Call Status",
            "call_notes":      "Call Notes",
        }
        for k_in, k_out in _mapping.items():
            if k_in in body:
                fields[k_out] = body[k_in]

        # Numeric referral-source overrides
        for k_in, k_out in (("referred_by_company_id", "Referred By Company ID"),
                            ("referred_by_person_id",  "Referred By Person ID")):
            if k_in in body:
                v = body[k_in]
                if v in (None, ""):
                    fields[k_out] = None
                else:
                    try: fields[k_out] = int(v)
                    except (TypeError, ValueError): pass

        # Always bump Updated if anything changed
        if fields:
            fields["Updated"] = _iso_now()

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.patch(
                f"{env['br']}/api/database/rows/table/{T_LEADS}/{lead_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=fields,
            )
        if r.status_code not in (200, 201):
            return JSONResponse({"ok": False, "error": r.text[:400]}, status_code=r.status_code)
        _invalidate(T_LEADS)

        # Log stage-change activity on referred-by Company/Person if Status changed,
        # AND fire automation triggers for the new stage.
        try:
            if prev and "status" in body:
                old_status = _sel(prev.get("Status")) or ""
                new_status = body["status"] or ""
                if old_status != new_status:
                    comp_id = prev.get("Referred By Company ID")
                    pers_id = prev.get("Referred By Person ID")
                    if comp_id or pers_id:
                        nm = prev.get("Name") or f"Lead #{lead_id}"
                        await _log_activity(
                            env,
                            company_id=int(comp_id) if comp_id else None,
                            contact_id=int(pers_id) if pers_id else None,
                            kind="edit",
                            type_="Lead",
                            summary=f"Lead '{nm}' moved {old_status or '(new)'} \u2192 {new_status}",
                            author=email,
                        )
                    # Merge prev + fields for subject_data so recipient info is accurate
                    subj = {**(prev or {}), **fields, "Status": new_status}
                    # Baserow select fields come back as dicts on reads — flatten for subject_data
                    for k in ("Email", "Phone", "Name"):
                        if isinstance(subj.get(k), dict):
                            subj[k] = subj[k].get("value", "") or ""
                    await _fire_trigger("lead_stage_changed", subject_type="lead",
                                         subject_id=lead_id, subject_data=subj,
                                         config_match=f"to:{new_status}",
                                         enroller_email=email)
                    if new_status == "Converted":
                        await _fire_trigger("lead_converted", subject_type="lead",
                                             subject_id=lead_id, subject_data=subj,
                                             enroller_email=email)
                    elif new_status == "Dropped":
                        await _fire_trigger("lead_dropped", subject_type="lead",
                                             subject_id=lead_id, subject_data=subj,
                                             enroller_email=email)
        except Exception as _e:
            print(f"[update_lead trigger] {_e}")

        return JSONResponse({"ok": True})

    @fapp.post("/api/leads/{lead_id}/convert")
    async def api_lead_convert(lead_id: int, request: Request):
        """Convert a Lead into a Patient. Creates a minimal row in
        T_PI_ACTIVE (Name + Phone + Email + Referring Attorney if available)
        and sets Lead Status=Converted + Converted Date=today."""
        session, err = _ld_guard(request)
        if err: return err
        if not T_PI_ACTIVE:
            return JSONResponse({"error": "PI cases not configured"}, status_code=503)
        env = _env()
        email = session.get("email", "")

        # Fetch the lead
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                f"{env['br']}/api/database/rows/table/{T_LEADS}/{lead_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}"},
            )
        if r.status_code != 200:
            return JSONResponse({"error": "lead not found"}, status_code=404)
        lead = r.json()

        # Build the patient row
        patient_fields = {
            "Name": lead.get("Name") or f"Lead {lead_id}",
        }
        if lead.get("Phone"): patient_fields["Phone"] = lead["Phone"]
        if lead.get("Email"): patient_fields["Email"] = lead["Email"]

        # If the Referred By Company is an Attorney firm, pre-populate
        # Law Firm Name so the PI side has the referral context.
        comp_id = lead.get("Referred By Company ID")
        if comp_id and T_COMPANIES:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    rr = await client.get(
                        f"{env['br']}/api/database/rows/table/{T_COMPANIES}/{int(comp_id)}/?user_field_names=true",
                        headers={"Authorization": f"Token {env['bt']}"},
                    )
                if rr.status_code == 200:
                    co = rr.json()
                    cat = co.get("Category")
                    if isinstance(cat, dict): cat = cat.get("value", "")
                    if cat == "attorney":
                        patient_fields["Law Firm Name"] = co.get("Name", "")
            except Exception:
                pass

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{env['br']}/api/database/rows/table/{T_PI_ACTIVE}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=patient_fields,
            )
        if r.status_code not in (200, 201):
            return JSONResponse({"ok": False, "error": r.text[:400]}, status_code=r.status_code)
        pid = r.json().get("id")
        _invalidate(T_PI_ACTIVE)

        # Mark the lead Converted
        from datetime import date as _date
        async with httpx.AsyncClient(timeout=15) as client:
            await client.patch(
                f"{env['br']}/api/database/rows/table/{T_LEADS}/{lead_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json={
                    "Status":           "Converted",
                    "Converted Date":   _date.today().isoformat(),
                    "Stage Changed At": _iso_now(),
                    "Updated":          _iso_now(),
                },
            )
        _invalidate(T_LEADS)

        # Fire lead_converted trigger (+ generic lead_stage_changed to:Converted)
        try:
            subj = {**lead, "Status": "Converted"}
            for k in ("Email", "Phone", "Name"):
                if isinstance(subj.get(k), dict): subj[k] = subj[k].get("value", "") or ""
            await _fire_trigger("lead_stage_changed", subject_type="lead",
                                 subject_id=lead_id, subject_data=subj,
                                 config_match="to:Converted", enroller_email=email)
            await _fire_trigger("lead_converted", subject_type="lead",
                                 subject_id=lead_id, subject_data=subj,
                                 enroller_email=email)
        except Exception as _e:
            print(f"[convert trigger] {_e}")

        return JSONResponse({"ok": True, "patient_id": pid})

    @fapp.get("/api/companies/{company_id}/leads")
    async def api_company_leads(company_id: int, request: Request):
        session, err = _crm_guard(request)
        if err: return err
        env = _env()
        rows = await _cached_table(T_LEADS, env["br"], env["bt"])
        matched = [r for r in rows if (r.get("Referred By Company ID") or 0) == company_id]
        matched.sort(key=lambda l: (l.get("Created") or ""), reverse=True)
        return JSONResponse(matched)

    @fapp.get("/api/people/{person_id}/leads")
    async def api_person_leads(person_id: int, request: Request):
        session, err = _crm_guard(request)
        if err: return err
        env = _env()
        rows = await _cached_table(T_LEADS, env["br"], env["bt"])
        matched = [r for r in rows if (r.get("Referred By Person ID") or 0) == person_id]
        matched.sort(key=lambda l: (l.get("Created") or ""), reverse=True)
        return JSONResponse(matched)

    # ── ClickUp tasks ──────────────────────────────────────────────────────────
    # Proxies the signed-in user's ClickUp tasks into the hub. No native Task
    # table — ClickUp is source of truth. Matching Google email → ClickUp user
    # happens via `resolve_user_by_email` (cached 10 min).
    def _tasks_guard(request):
        session = _get_session(request)
        if not session:
            return None, JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not _has_hub_access(session, "tasks"):
            return None, JSONResponse({"error": "forbidden"}, status_code=403)
        if not os.environ.get("CLICKUP_API_KEY"):
            return None, JSONResponse({"error": "CLICKUP_API_KEY not configured"}, status_code=503)
        return session, None

    @fapp.get("/api/clickup/lists")
    async def api_clickup_lists(request: Request):
        """Return every list in the Cabinet of Reform space, grouped by folder.
        Used by the Add Task modal to let the user pick a destination list."""
        session, err = _tasks_guard(request)
        if err: return err
        api_key = os.environ["CLICKUP_API_KEY"]
        async with httpx.AsyncClient(timeout=15) as client:
            lists = await _cu.get_space_lists(api_key, _cu.CLICKUP_SPACE_ID, client)
        return JSONResponse({
            "items": lists,
            "default_list_id": _cu.CLICKUP_DEFAULT_LIST_ID or None,
        })

    @fapp.get("/api/clickup/tasks")
    async def api_clickup_tasks(request: Request):
        """Current user's open ClickUp tasks. Optional filters:
           ?company_id=X / ?lead_id=X / ?person_id=X — match `crm:*:X` tags."""
        session, err = _tasks_guard(request)
        if err: return err
        api_key = os.environ["CLICKUP_API_KEY"]
        email = session.get("email", "")
        async with httpx.AsyncClient(timeout=15) as client:
            user = await _cu.resolve_user_by_email(api_key, email, client)
        if not user:
            return JSONResponse({
                "items": [], "unmatched": True,
                "hint": f"No ClickUp user found for {email}. Ask an admin to add you to the ClickUp workspace.",
            })
        tasks = await _cu.get_user_tasks(api_key, int(user["id"]))
        slim = [_cu.slim_task(t) for t in tasks]

        # Optional CRM-link filter
        q = dict(request.query_params)
        filt_kind, filt_val = None, None
        for k in ("company_id", "lead_id", "person_id"):
            if q.get(k):
                try:
                    filt_val = int(q[k]); filt_kind = k[:-3]  # 'company'/'lead'/'person'
                    break
                except (TypeError, ValueError):
                    pass
        if filt_kind and filt_val:
            tag_name = _cu.crm_tag(filt_kind, filt_val)
            slim = [t for t in slim if tag_name in (t.get("tags") or [])]

        # Attach parsed CRM link ids for the UI to render chips
        for t in slim:
            t["crm"] = _cu.parse_crm_tags(t.get("tags") or [])
        return JSONResponse({
            "items": slim,
            "user": {"id": user.get("id"), "username": user.get("username"),
                     "email": user.get("email")},
        })

    @fapp.post("/api/clickup/tasks")
    async def api_clickup_create(request: Request):
        """Create a task in ClickUp, assigned to the signed-in user by default.
        Body: `{name, description?, due_date?, list_id?, company_id?,
                 contact_id?, lead_id?, assignee_email?, priority?}`.
        - Adds `crm:<kind>:<id>` tags for any provided CRM link.
        - Appends the record URL to the description so the task links back."""
        session, err = _tasks_guard(request)
        if err: return err
        api_key = os.environ["CLICKUP_API_KEY"]
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            return JSONResponse({"error": "name required"}, status_code=400)

        # Resolve target list
        list_id = (body.get("list_id") or _cu.CLICKUP_DEFAULT_LIST_ID or "").strip()
        if not list_id:
            return JSONResponse({
                "error": "no_list_id",
                "hint": "Set CLICKUP_DEFAULT_LIST_ID in the outreach-hub-secrets Modal secret, or pass list_id in the request.",
            }, status_code=400)

        # Assignee: explicit email → ClickUp user, else the signed-in user
        assignee_email = (body.get("assignee_email") or session.get("email", "")).lower().strip()
        async with httpx.AsyncClient(timeout=15) as client:
            assignee = await _cu.resolve_user_by_email(api_key, assignee_email, client)
        assignees = [int(assignee["id"])] if assignee and assignee.get("id") else []

        # CRM link tags + URL line in description
        tags = []
        desc = (body.get("description") or "").strip()
        url_base = os.environ.get("PUBLIC_HUB_URL", "https://hub.reformchiropractic.app")
        crm_lines = []
        if body.get("company_id"):
            cid = int(body["company_id"]); tags.append(_cu.crm_tag("company", cid))
            crm_lines.append(f"Company: {url_base}/companies/{cid}")
        if body.get("lead_id"):
            lid = int(body["lead_id"]); tags.append(_cu.crm_tag("lead", lid))
            crm_lines.append(f"Lead: {url_base}/leads/{lid}")
        if body.get("contact_id"):
            pid = int(body["contact_id"]); tags.append(_cu.crm_tag("person", pid))
            crm_lines.append(f"Person: {url_base}/people/{pid}")
        if crm_lines:
            desc = (desc + "\n\n" if desc else "") + "\n".join(crm_lines)

        # Due date: accept ISO (YYYY-MM-DD or with time) → ms epoch
        due_ms = None
        if body.get("due_date"):
            from datetime import datetime as _dt
            try:
                d = body["due_date"]
                if "T" not in d: d = d + "T17:00:00"  # default 5pm local if no time
                due_ms = int(_dt.fromisoformat(d).timestamp() * 1000)
            except Exception:
                pass

        result = await _cu.create_task(
            api_key, list_id,
            name=name, description=desc,
            assignees=assignees,
            due_date_ms=due_ms,
            tags=tags or None,
            priority=body.get("priority"),
        )
        if result.get("error"):
            return JSONResponse({"error": result["error"], "status": result.get("status")},
                                status_code=502)
        return JSONResponse({
            "ok": True,
            "id":  result.get("id"),
            "url": result.get("url"),
            "name": result.get("name"),
        })

    @fapp.patch("/api/clickup/tasks/{task_id}")
    async def api_clickup_update(task_id: str, request: Request):
        """Update a task (status/due/name/description/complete)."""
        session, err = _tasks_guard(request)
        if err: return err
        api_key = os.environ["CLICKUP_API_KEY"]
        body = await request.json()
        patch = {}
        for k in ("name", "description", "status"):
            if k in body: patch[k] = body[k]
        if "due_date" in body and body["due_date"]:
            from datetime import datetime as _dt
            try:
                d = body["due_date"]
                if "T" not in d: d = d + "T17:00:00"
                patch["due_date"] = int(_dt.fromisoformat(d).timestamp() * 1000)
            except Exception:
                pass
        result = await _cu.update_task(api_key, task_id, patch)
        if result.get("error"):
            return JSONResponse({"error": result["error"], "status": result.get("status")},
                                status_code=502)
        return JSONResponse({"ok": True, "task": _cu.slim_task(result)})

    @fapp.post("/api/leads/bulk-contact")
    async def bulk_contact_leads(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        body = await request.json()
        ids = body.get("ids", [])
        env = _env()
        from datetime import date as _date
        today = _date.today().isoformat()
        email = session.get("email", "")
        async with httpx.AsyncClient(timeout=60) as client:
            for lid in ids:
                await client.patch(
                    f"{env['br']}/api/database/rows/table/{T_LEADS}/{lid}/?user_field_names=true",
                    headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                    json={"Status": "Contacted", "Contacted At": today, "Contacted By": email},
                )
        try:
            hub_cache.pop(f"table:{T_LEADS}")
        except Exception:
            pass
        return JSONResponse({"ok": True})

    # ── Bulk-patch endpoints ───────────────────────────────────────────────────
    # Shared shape across Companies / People / Tickets / Leads:
    #   POST body: {"ids": [int, ...], "patch": {field: value, ...}}
    # Each endpoint enforces a per-entity field allow-list (UI-friendly input
    # keys, translated to Baserow field names), loops over IDs, writes a
    # per-row audit trail where appropriate, and invalidates the table cache
    # once at the end.
    async def _bulk_apply(env, tid: int, ids: list, baserow_patch: dict,
                           max_ids: int = 200) -> dict:
        """Apply the same Baserow-shaped patch to every id. Returns
        `{updated: int, updated_ids: [int], failed: [int]}`. Caller is
        responsible for cache invalidation (so we only do it once per endpoint)."""
        failed = []
        updated_ids = []
        if not ids:
            return {"updated": 0, "updated_ids": [], "failed": []}
        # Cap to protect against runaway requests; UI should chunk.
        ids = list(ids)[:max_ids]
        async with httpx.AsyncClient(timeout=60) as client:
            for rid in ids:
                try:
                    r = await client.patch(
                        f"{env['br']}/api/database/rows/table/{tid}/{int(rid)}/?user_field_names=true",
                        headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                        json=baserow_patch,
                    )
                    if r.status_code in (200, 201):
                        updated_ids.append(int(rid))
                    else:
                        failed.append(int(rid))
                except Exception:
                    try: failed.append(int(rid))
                    except Exception: pass
        return {"updated": len(updated_ids), "updated_ids": updated_ids, "failed": failed}

    @fapp.post("/api/companies/bulk-patch")
    async def api_companies_bulk_patch(request: Request):
        session, err = _crm_guard(request)
        if err: return err
        body = await request.json()
        ids = body.get("ids") or []
        patch = body.get("patch") or {}
        # UI keys -> Baserow field names. Every allowed field is a simple
        # single_select / text / boolean — we skip legacy-venue mirror in
        # bulk (users needing sync should use the singular PATCH).
        allow = {
            "contact_status":   "Contact Status",
            "category":         "Category",
            "type":             "Type",
            "outreach_goal":    "Outreach Goal",
            "permanently_closed": "Permanently Closed",
            "active":           "Active",
        }
        baserow_patch = {allow[k]: v for k, v in patch.items() if k in allow}
        if not baserow_patch:
            return JSONResponse({"error": "no allowed fields in patch",
                                 "allowed": list(allow.keys())}, status_code=400)
        baserow_patch["Updated"] = _iso_now()
        env = _env()
        result = await _bulk_apply(env, T_COMPANIES, ids, baserow_patch)
        _invalidate(T_COMPANIES)
        # Best-effort audit activity per updated row (kept out of hot path —
        # we log a single rollup comment rather than one per row).
        try:
            if result["updated"]:
                summary = f"Bulk edit applied to {result['updated']} companies: " + ", ".join(
                    f"{k}={v}" for k, v in patch.items() if k in allow
                )
                await _log_activity(env, kind="edit", type_="Bulk",
                                     summary=summary, author=session.get("email", ""))
        except Exception:
            pass
        return JSONResponse({"ok": True, **result})

    @fapp.post("/api/people/bulk-patch")
    async def api_people_bulk_patch(request: Request):
        session, err = _crm_guard(request)
        if err: return err
        body = await request.json()
        ids = body.get("ids") or []
        patch = body.get("patch") or {}
        allow = {
            "lifecycle_stage": "Lifecycle Stage",
            "active":          "Active",
            "title":           "Title",
        }
        baserow_patch = {allow[k]: v for k, v in patch.items() if k in allow}
        if not baserow_patch:
            return JSONResponse({"error": "no allowed fields in patch",
                                 "allowed": list(allow.keys())}, status_code=400)
        baserow_patch["Updated"] = _iso_now()
        env = _env()
        result = await _bulk_apply(env, T_CONTACTS, ids, baserow_patch)
        _invalidate(T_CONTACTS)
        return JSONResponse({"ok": True, **result})

    @fapp.post("/api/tickets/bulk-patch")
    async def api_tickets_bulk_patch(request: Request):
        session, err = _tk_guard(request)
        if err: return err
        body = await request.json()
        ids = body.get("ids") or []
        patch = body.get("patch") or {}
        allow = {
            "status":    "Status",
            "priority":  "Priority",
            "category":  "Category",
            "assignee":  "Assignee",
        }
        baserow_patch = {allow[k]: v for k, v in patch.items() if k in allow}
        if not baserow_patch:
            return JSONResponse({"error": "no allowed fields in patch",
                                 "allowed": list(allow.keys())}, status_code=400)
        baserow_patch["Updated"] = _iso_now()
        env = _env()
        actor = session.get("email", "")
        result = await _bulk_apply(env, T_TICKETS, ids, baserow_patch)
        _invalidate(T_TICKETS)
        # System comment per row per changed field (status / assignee)
        try:
            for rid in result["updated_ids"]:
                if "status" in patch:
                    await _tk_post_system_comment(env, rid, actor,
                        f"{actor} set status to {patch['status']} (bulk)",
                        kind="status_change")
                if "assignee" in patch:
                    await _tk_post_system_comment(env, rid, actor,
                        f"{actor} set assignee to {patch['assignee'] or 'unassigned'} (bulk)",
                        kind="assignment")
        except Exception:
            pass
        return JSONResponse({"ok": True, **result})

    @fapp.post("/api/leads/bulk-patch")
    async def api_leads_bulk_patch(request: Request):
        session, err = _ld_guard(request)
        if err: return err
        body = await request.json()
        ids = body.get("ids") or []
        patch = body.get("patch") or {}
        allow = {
            "status":         "Status",
            "owner":          "Owner",
            "follow_up_date": "Follow-Up Date",
            "call_status":    "Call Status",
        }
        baserow_patch = {allow[k]: v for k, v in patch.items() if k in allow}
        if not baserow_patch:
            return JSONResponse({"error": "no allowed fields in patch",
                                 "allowed": list(allow.keys())}, status_code=400)
        # Auto-stamp stage-transition dates in bulk (matches singular PATCH).
        from datetime import date as _date
        today = _date.today().isoformat()
        now = _iso_now()
        email = session.get("email", "")
        if "status" in patch:
            s = patch["status"]
            baserow_patch["Stage Changed At"] = now
            if s == "Contacted":
                baserow_patch["Contacted At"] = today
                baserow_patch["Contacted By"] = email
            elif s == "Appointment Scheduled":
                baserow_patch["Appointment Date"] = now
            elif s == "Seen":
                baserow_patch["Seen Date"] = today
            elif s == "Converted":
                baserow_patch["Converted Date"] = today
        baserow_patch["Updated"] = now
        env = _env()
        result = await _bulk_apply(env, T_LEADS, ids, baserow_patch)
        _invalidate(T_LEADS)
        return JSONResponse({"ok": True, **result})

    _EVENT_STATUSES = {
        "Prospective", "Maybe", "Approved", "Declined", "Scheduled", "Completed",
    }
    _EVENT_PATCH_ALLOWLIST = {
        "Event Status", "Est Insurance Pct", "Other Chiropractor",
        "Doctors Needed", "Front Desk Needed", "Therapists Needed",
        "Generator Needed", "Table Needed", "EZ Up Needed",
        "Promotion", "Services Rendered", "Materials Needed",
        "Decision Notes", "Anticipated Count", "Organizer", "Organizer Phone",
        "Cost", "Duration", "Venue Address", "Event Date", "Name",
    }
    _EVENT_OTHER_CHIRO = {"Yes", "No", "Unknown"}
    _EVENT_TYPES = {
        "External Event", "Mobile Massage Service",
        "Lunch and Learn", "Health Assessment Screening",
    }

    @fapp.patch("/api/events/{event_id}/status")
    async def update_event_status(request: Request, event_id: int):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        body = await request.json()
        status = body.get("status", "")
        if status not in _EVENT_STATUSES:
            return JSONResponse({"error": "invalid status"}, status_code=400)
        env = _env()
        async with httpx.AsyncClient(timeout=30) as client:
            await client.patch(
                f"{env['br']}/api/database/rows/table/{T_EVENTS}/{event_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json={"Event Status": status},
            )
        try:
            hub_cache.pop(f"table:{T_EVENTS}")
        except Exception:
            pass
        return JSONResponse({"ok": True})

    @fapp.patch("/api/events/{event_id}")
    async def update_event(request: Request, event_id: int):
        """Generic event field update. Accepts any allowlisted T_EVENTS field;
        validates Event Status and Other Chiropractor against their enums."""
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        body = await request.json() or {}
        patch = {}
        for k, v in body.items():
            if k not in _EVENT_PATCH_ALLOWLIST:
                continue
            if k == "Event Status":
                if v and v not in _EVENT_STATUSES:
                    return JSONResponse({"error": f"invalid status: {v}"}, status_code=400)
            if k == "Other Chiropractor":
                if v and v not in _EVENT_OTHER_CHIRO:
                    return JSONResponse({"error": f"invalid Other Chiropractor: {v}"}, status_code=400)
            patch[k] = v
        if not patch:
            return JSONResponse({"error": "no valid fields"}, status_code=400)
        env = _env()
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.patch(
                f"{env['br']}/api/database/rows/table/{T_EVENTS}/{event_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=patch,
            )
            if r.status_code >= 300:
                return JSONResponse(
                    {"error": "baserow write failed", "detail": r.text[:400]},
                    status_code=502,
                )
        try:
            hub_cache.pop(f"table:{T_EVENTS}")
        except Exception:
            pass
        return JSONResponse({"ok": True})

    @fapp.post("/api/events")
    async def create_event(request: Request):
        """Create a blank-ish T_EVENTS row for manual intake. Requires Name,
        Event Type, Event Date. Status defaults to Prospective."""
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        body = await request.json() or {}
        name = (body.get("name") or "").strip()
        ev_type = (body.get("event_type") or "").strip()
        ev_date = (body.get("event_date") or "").strip()
        if not name or not ev_type or not ev_date:
            return JSONResponse(
                {"error": "name, event_type, event_date required"},
                status_code=400,
            )
        if ev_type not in _EVENT_TYPES:
            return JSONResponse({"error": f"invalid event_type: {ev_type}"}, status_code=400)
        import secrets
        fields = {
            "Name": name,
            "Event Type": ev_type,
            "Event Date": ev_date,
            "Event Status": "Prospective",
            "Form Slug": secrets.token_urlsafe(8)[:12],
            "Created By": session.get("email", ""),
        }
        env = _env()
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{env['br']}/api/database/rows/table/{T_EVENTS}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=fields,
            )
            if r.status_code >= 300:
                return JSONResponse(
                    {"error": "baserow create failed", "detail": r.text[:400]},
                    status_code=502,
                )
            data = r.json()
        try:
            hub_cache.pop(f"table:{T_EVENTS}")
        except Exception:
            pass
        return JSONResponse({"ok": True, "id": data.get("id")})

    @fapp.patch("/api/events/{event_id}/checkin")
    async def event_checkin(request: Request, event_id: int):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        env = _env()
        async with httpx.AsyncClient(timeout=30) as client:
            await client.patch(
                f"{env['br']}/api/database/rows/table/{T_EVENTS}/{event_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json={"Checked In": True},
            )
        try:
            hub_cache.pop(f"table:{T_EVENTS}")
        except Exception:
            pass
        return JSONResponse({"ok": True})

    return fapp


# ──────────────────────────────────────────────────────────────────────────────
# LOCAL DEV  —  python execution/modal_outreach_hub.py
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import httpx
    import uvicorn
    from pathlib import Path
    from dotenv import load_dotenv
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

    load_dotenv(Path(__file__).parent.parent / ".env")

    local_app = FastAPI()

    def _env():
        return {
            "br":     os.getenv("BASEROW_URL",        "https://baserow.reformchiropractic.app"),
            "bt":     os.getenv("BASEROW_API_TOKEN",  ""),
            "gid":    os.getenv("GOOGLE_CLIENT_ID",   ""),
            "gsec":   os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "domain": os.getenv("ALLOWED_DOMAIN",     ""),
        }

    def _redirect_uri(request: Request) -> str:
        host = request.headers.get("host", "localhost:8000")
        if "localhost" in host or "127.0.0.1" in host:
            return f"http://{host}/auth/google/callback"
        return "https://hub.reformchiropractic.app/auth/google/callback"

    async def _refresh_if_needed(sid: str, session: dict, env: dict) -> str:
        if time.time() < session.get("expires_at", 0) - 60:
            return session["access_token"]
        async with httpx.AsyncClient() as client:
            r = await client.post("https://oauth2.googleapis.com/token", data={
                "client_id":     env["gid"],
                "client_secret": env["gsec"],
                "refresh_token": session.get("refresh_token", ""),
                "grant_type":    "refresh_token",
            })
            data = r.json()
        if "access_token" not in data:
            return session.get("access_token", "")
        session["access_token"] = data["access_token"]
        session["expires_at"] = time.time() + data.get("expires_in", 3600)
        hub_sessions[sid] = session
        return session["access_token"]

    def _guard(request):
        session = _get_session(request)
        if not session:
            return None, None, None
        env = _env()
        return session, env["br"], env["bt"]

    # ── Login / OAuth ──────────────────────────────────────────────────────────
    @local_app.get("/login", response_class=HTMLResponse)
    async def _login_get(request: Request, error: str = ""):
        if _ok(request):
            return RedirectResponse(url="/")
        return HTMLResponse(_login_page(error))

    @local_app.get("/auth/google", response_class=HTMLResponse)
    async def _auth_google(request: Request):
        env = _env()
        state = secrets.token_urlsafe(32)
        hub_oauth_states[state] = time.time()
        params = urlencode({
            "client_id":     env["gid"],
            "redirect_uri":  _redirect_uri(request),
            "response_type": "code",
            "scope":         "openid email profile https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/calendar.events",
            "access_type":   "offline",
            "prompt":        "consent",
            "state":         state,
        })
        google_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
        return HTMLResponse(
            f'<html><head></head><body>'
            f'<script>window.location.href={repr(google_url)};</script>'
            f'<noscript><meta http-equiv="refresh" content="0;url={google_url}"></noscript>'
            f'</body></html>'
        )

    @local_app.get("/auth/google/callback")
    async def _auth_callback(request: Request, code: str = "", state: str = "", error: str = ""):
        if error or not code:
            return RedirectResponse("/login?error=1")
        stored_time = hub_oauth_states.get(state)
        if not stored_time or (time.time() - stored_time) > 300:
            return RedirectResponse("/login?error=1")
        del hub_oauth_states[state]

        env = _env()
        async with httpx.AsyncClient() as client:
            token_resp = await client.post("https://oauth2.googleapis.com/token", data={
                "code":          code,
                "client_id":     env["gid"],
                "client_secret": env["gsec"],
                "redirect_uri":  _redirect_uri(request),
                "grant_type":    "authorization_code",
            })
            tokens = token_resp.json()
            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {tokens.get('access_token','')}"}
            )
            user = userinfo_resp.json()

        email = user.get("email", "")
        allowed = env["domain"]
        if allowed and not email.endswith(f"@{allowed}"):
            return RedirectResponse("/login?error=domain")

        sid = secrets.token_urlsafe(32)
        hub_sessions[sid] = {
            "email":         email,
            "name":          user.get("name", email),
            "picture":       user.get("picture", ""),
            "access_token":  tokens.get("access_token", ""),
            "refresh_token": tokens.get("refresh_token", ""),
            "expires_at":    time.time() + tokens.get("expires_in", 3600),
        }
        resp = HTMLResponse('<html><head><meta http-equiv="refresh" content="0;url=/"></head></html>')
        resp.set_cookie(SESSION_COOKIE, sid, httponly=True, max_age=86400 * 7, samesite="lax")
        return resp

    @local_app.get("/logout")
    async def _logout(request: Request):
        sid = request.cookies.get(SESSION_COOKIE)
        if sid:
            try:
                del hub_sessions[sid]
            except KeyError:
                pass
        resp = HTMLResponse('<html><head><meta http-equiv="refresh" content="0;url=/login"></head></html>')
        resp.delete_cookie(SESSION_COOKIE)
        return resp

    # ── Gmail API ──────────────────────────────────────────────────────────────
    @local_app.post("/api/gmail/send")
    async def _gmail_send(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        body = await request.json()
        to = body.get("to", "")
        subject = body.get("subject", "")
        text = body.get("body", "")
        if not to or not subject or not text:
            return JSONResponse({"error": "missing fields"}, status_code=400)
        env = _env()
        sid = request.cookies.get(SESSION_COOKIE, "")
        token = await _refresh_if_needed(sid, session, env)
        import base64, email as emaillib
        msg = emaillib.message.EmailMessage()
        msg["From"] = session["email"]
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {token}"},
                json={"raw": raw},
            )
        return JSONResponse(r.json(), status_code=r.status_code)

    @local_app.get("/api/gmail/threads")
    async def _gmail_threads(request: Request, contact_email: str = ""):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not contact_email:
            return JSONResponse({"error": "contact_email required"}, status_code=400)
        env = _env()
        sid = request.cookies.get(SESSION_COOKIE, "")
        token = await _refresh_if_needed(sid, session, env)
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/threads",
                headers={"Authorization": f"Bearer {token}"},
                params={"q": f"from:{contact_email} OR to:{contact_email}", "maxResults": 20},
            )
            meta = r.json().get("threads", [])
            threads = []
            for t in meta[:10]:
                tr = await client.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{t['id']}",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"format": "metadata", "metadataHeaders": ["Subject", "From", "To", "Date"]},
                )
                threads.append(tr.json())
        return JSONResponse({"threads": threads})

    @local_app.get("/api/data/{tid}")
    async def _table_data(tid: int, request: Request):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        env = _env()
        rows = await _cached_table(tid, env["br"], env["bt"])
        return JSONResponse(rows)

    @local_app.post("/api/contacts")
    async def _contacts_create(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        env = _env()
        body = await request.json()
        category = body.get("category", "gorilla")
        name     = (body.get("name") or "").strip()
        phone    = (body.get("phone") or "").strip()
        address  = (body.get("address") or "").strip()
        status   = body.get("status", "Not Contacted")
        if not name:
            return JSONResponse({"error": "name required"}, status_code=400)
        TABLE_MAP = {
            "attorney":  {"tid": T_ATT_VENUES, "name_f": "Law Firm Name",  "phone_f": "Phone Number", "addr_f": "Law Office Address"},
            "gorilla":   {"tid": T_GOR_VENUES, "name_f": "Name",            "phone_f": "Phone",        "addr_f": "Address"},
            "community": {"tid": T_COM_VENUES, "name_f": "Name",            "phone_f": "Phone",        "addr_f": "Address"},
        }
        cfg = TABLE_MAP.get(category, TABLE_MAP["gorilla"])
        fields: dict = {
            cfg["name_f"]:    name,
            "Contact Status": status,
        }
        if phone:   fields[cfg["phone_f"]] = phone
        if address: fields[cfg["addr_f"]]  = address
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{env['br']}/api/database/rows/table/{cfg['tid']}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=fields,
            )
        if r.status_code in (200, 201):
            return JSONResponse({"ok": True})
        return JSONResponse({"error": r.text}, status_code=r.status_code)

    @local_app.get("/api/geocode")
    async def _geocode(request: Request, lat: float = 0.0, lng: float = 0.0):
        if not _ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        if not lat or not lng:
            return JSONResponse({"error": "lat/lng required"}, status_code=400)
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(
                    "https://nominatim.openstreetmap.org/reverse",
                    params={"lat": lat, "lon": lng, "format": "json"},
                    headers={"User-Agent": "ReformHub/1.0 (reformchiropractic.com)"},
                )
                d = r.json()
            a = d.get("address", {})
            parts = []
            num  = a.get("house_number", "")
            road = a.get("road", "")
            if num and road:
                parts.append(f"{num} {road}")
            elif road:
                parts.append(road)
            city = a.get("city") or a.get("town") or a.get("village") or ""
            if city:  parts.append(city)
            if a.get("state"):    parts.append(a["state"])
            if a.get("postcode"): parts.append(a["postcode"])
            addr = ", ".join(parts) if parts else d.get("display_name", "")
            return JSONResponse({"address": addr})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @local_app.get("/api/guerilla/routes/today")
    async def _gorilla_routes_today(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not T_GOR_ROUTES or not T_GOR_ROUTE_STOPS:
            return JSONResponse({"route": None, "stops": []})
        env = _env()
        user_email = session.get("email", "")
        import datetime
        today = datetime.date.today().isoformat()
        try:
            routes = await _cached_table(T_GOR_ROUTES, env["br"], env["bt"])
            # Find active route for today assigned to this user
            route = None
            for row in routes:
                row_date  = (row.get("Date") or "")[:10]
                row_email = (row.get("Assigned To") or "").strip().lower()
                row_status = row.get("Status") or ""
                if isinstance(row_status, dict): row_status = row_status.get("value", "")
                if row_date == today and row_email == user_email.lower() and row_status in ("Active", "Draft"):
                    route = row
                    break
            if not route:
                return JSONResponse({"route": None, "stops": []})
            route_id = route.get("id")
            stops_all = await _cached_table(T_GOR_ROUTE_STOPS, env["br"], env["bt"])
            # Filter stops for this route, sorted by Stop Order
            stops = [s for s in stops_all if any(
                (isinstance(v, dict) and v.get("id") == route_id) or v == route_id
                for v in (s.get("Route") or [])
            )]
            stops.sort(key=lambda s: s.get("Stop Order") or 999)
            # Enrich with venue lat/lng
            venues = await _cached_table(T_GOR_VENUES, env["br"], env["bt"])
            venue_map = {v["id"]: v for v in venues}
            stop_list = []
            for s in stops:
                venue_id = None
                for v in (s.get("Venue") or []):
                    if isinstance(v, dict): venue_id = v.get("id"); break
                    venue_id = v; break
                venue = venue_map.get(venue_id, {}) if venue_id else {}
                status = s.get("Status") or ""
                if isinstance(status, dict): status = status.get("value", "Pending")
                stop_list.append({
                    "stop_id":  s.get("id"),
                    "name":     venue.get("Name") or "",
                    "address":  venue.get("Address") or "",
                    "lat":      venue.get("Latitude"),
                    "lng":      venue.get("Longitude"),
                    "status":   status or "Pending",
                    "order":    s.get("Stop Order") or 0,
                    "notes":    s.get("Notes") or "",
                })
            route_status = route.get("Status") or ""
            if isinstance(route_status, dict): route_status = route_status.get("value", "")
            return JSONResponse({
                "route": {"id": route_id, "name": route.get("Route Name") or "Route", "status": route_status},
                "stops": stop_list,
            })
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @local_app.get("/api/guerilla/routes/{route_id}")
    async def _gorilla_route_detail(route_id: int, request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        env = _env()

        async def _local_cached_rows(tid: int) -> list:
            return await _cached_table(tid, env["br"], env["bt"])

        return await guerilla_api.route_detail(request, env["br"], env["bt"],
                                               session, route_id, _local_cached_rows)

    @local_app.patch("/api/guerilla/routes/stops/{stop_id}")
    async def _gorilla_route_stop_patch(stop_id: int, request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not T_GOR_ROUTE_STOPS:
            return JSONResponse({"error": "routes not configured"}, status_code=503)
        env = _env()
        body = await request.json()
        new_status = body.get("status", "")
        if new_status not in ("Pending", "Visited", "Skipped"):
            return JSONResponse({"error": "invalid status"}, status_code=400)
        async with httpx.AsyncClient() as client:
            r = await client.patch(
                f"{env['br']}/api/database/rows/table/{T_GOR_ROUTE_STOPS}/{stop_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json={"Status": new_status},
            )
        # Bust cache so next fetch reflects the update
        try: del hub_cache[f"table:{T_GOR_ROUTE_STOPS}"]
        except Exception: pass
        if r.status_code in (200, 201):
            return JSONResponse({"ok": True})
        return JSONResponse({"error": r.text}, status_code=r.status_code)

    @local_app.post("/api/guerilla/routes")
    async def _gorilla_routes_create(request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not T_GOR_ROUTES or not T_GOR_ROUTE_STOPS:
            return JSONResponse({"error": "routes not configured"}, status_code=503)
        env = _env()
        body = await request.json()
        name     = (body.get("name") or "").strip()
        date_str = (body.get("date") or "").strip()
        assignee = (body.get("assigned_to") or "").strip()
        status   = body.get("status") or "Draft"
        stops    = body.get("stops") or []  # [{venue_id}]
        if not name:
            return JSONResponse({"error": "name required"}, status_code=400)
        if status not in ("Draft", "Active", "Completed"):
            status = "Draft"
        async with httpx.AsyncClient() as client:
            # Create route record
            route_payload = {"Name": name, "Assigned To": assignee, "Status": status}
            if date_str:
                route_payload["Date"] = date_str
            r = await client.post(
                f"{env['br']}/api/database/rows/table/{T_GOR_ROUTES}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json=route_payload,
            )
            if r.status_code not in (200, 201):
                return JSONResponse({"error": r.text}, status_code=r.status_code)
            route_id = r.json()["id"]
            # Create stop records
            for i, stop in enumerate(stops):
                venue_id = stop.get("venue_id")
                if not venue_id:
                    continue
                stop_payload = {
                    "Route":      [{"id": route_id}],
                    "Venue":      [{"id": venue_id}],
                    "Stop Order": i + 1,
                    "Status":     "Pending",
                }
                await client.post(
                    f"{env['br']}/api/database/rows/table/{T_GOR_ROUTE_STOPS}/?user_field_names=true",
                    headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                    json=stop_payload,
                )
        try: del hub_cache[f"table:{T_GOR_ROUTES}"]
        except Exception: pass
        try: del hub_cache[f"table:{T_GOR_ROUTE_STOPS}"]
        except Exception: pass
        return JSONResponse({"ok": True, "route_id": route_id})

    @local_app.patch("/api/guerilla/routes/{route_id}/status")
    async def _gorilla_route_status_patch(route_id: int, request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        if not T_GOR_ROUTES:
            return JSONResponse({"error": "routes not configured"}, status_code=503)
        env = _env()
        body = await request.json()
        new_status = body.get("status", "")
        if new_status not in ("Draft", "Active", "Completed"):
            return JSONResponse({"error": "invalid status"}, status_code=400)
        async with httpx.AsyncClient() as client:
            r = await client.patch(
                f"{env['br']}/api/database/rows/table/{T_GOR_ROUTES}/{route_id}/?user_field_names=true",
                headers={"Authorization": f"Token {env['bt']}", "Content-Type": "application/json"},
                json={"Status": new_status},
            )
        try: del hub_cache[f"table:{T_GOR_ROUTES}"]
        except Exception: pass
        if r.status_code in (200, 201):
            return JSONResponse({"ok": True})
        return JSONResponse({"error": r.text}, status_code=r.status_code)

    @local_app.patch("/api/guerilla/routes/{route_id}")
    async def _gorilla_route_update(route_id: int, request: Request):
        return await gorilla_route_update(request, route_id)

    @local_app.post("/api/guerilla/routes/{route_id}/stops")
    async def _gorilla_route_append_stop(route_id: int, request: Request):
        session = _get_session(request)
        if not session:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        env = _env()

        async def _local_cached_rows(tid: int) -> list:
            return await _cached_table(tid, env["br"], env["bt"])

        resp = await guerilla_api.gorilla_route_append_stop(
            request, env["br"], env["bt"], session, route_id, _local_cached_rows
        )
        try: del hub_cache[f"table:{T_GOR_ROUTE_STOPS}"]
        except Exception: pass
        return resp

    @local_app.delete("/api/guerilla/routes/{route_id}")
    async def _gorilla_route_delete(route_id: int, request: Request):
        return await gorilla_route_delete(request, route_id)

    # ── Mobile detection for root route ───────────────────────────────────────
    def _is_mobile_local(request):
        ua = (request.headers.get("user-agent") or "").lower()
        return any(k in ua for k in ("iphone", "android", "mobile", "ipod"))

    async def _root_handler(request: Request):
        user, br, bt = _guard(request)
        if not user: return RedirectResponse(url="/login")
        return HTMLResponse(_hub_page(br, bt, user=user))
    local_app.add_api_route("/", _root_handler, methods=["GET"])

    # ── Pages ──────────────────────────────────────────────────────────────────
    for route, fn in [
        ("/attorney",            lambda r, u, br, bt: _tool_page("attorney",  br, bt, user=u)),
        ("/guerilla",             lambda r, u, br, bt: _tool_page("gorilla",   br, bt, user=u)),
        ("/community",           lambda r, u, br, bt: _tool_page("community", br, bt, user=u)),
        ("/attorney/map",        lambda r, u, br, bt: _map_page("attorney",   br, bt, user=u)),
        ("/guerilla/map",         lambda r, u, br, bt: _map_page("gorilla",    br, bt, user=u)),
        ("/community/map",       lambda r, u, br, bt: _map_page("community",  br, bt, user=u)),
        ("/guerilla/events/internal",  lambda r, u, br, bt: _gorilla_events_internal_page(br, bt, user=u)),
        ("/guerilla/events/external",  lambda r, u, br, bt: _gorilla_events_external_page(br, bt, user=u)),
        ("/guerilla/businesses",       lambda r, u, br, bt: _gorilla_businesses_page(br, bt, user=u)),
        ("/guerilla/boxes",            lambda r, u, br, bt: _gorilla_boxes_page(br, bt, user=u)),
        ("/guerilla/routes",           lambda r, u, br, bt: _gorilla_routes_page(br, bt, user=u)),
        ("/guerilla/routes/new",       lambda r, u, br, bt: _gorilla_routes_new_page(br, bt, user=u)),
        ("/outreach/contacts",   lambda r, u, br, bt: _unified_directory_page(br, bt, user=u)),
        ("/attorney/directory",  lambda r, u, br, bt: _directory_page("attorney",  br, bt, user=u)),
        ("/guerilla/directory",   lambda r, u, br, bt: _directory_page("gorilla",   br, bt, user=u)),
        ("/community/directory", lambda r, u, br, bt: _directory_page("community", br, bt, user=u)),
        ("/patients",            lambda r, u, br, bt: _patients_page(br, bt, user=u)),
        ("/firms",               lambda r, u, br, bt: _firms_page(br, bt, user=u)),
        ("/billing/collections", lambda r, u, br, bt: _billing_page("collections", br, bt, user=u)),
        ("/billing/settlements", lambda r, u, br, bt: _billing_page("settlements", br, bt, user=u)),
        ("/communications/email", lambda r, u, br, bt: _communications_email_page(br, bt, user=u)),
        ("/contacts",            lambda r, u, br, bt: _contacts_page(br, bt, user=u)),
        ("/social/inbox",        lambda r, u, br, bt: _social_inbox_page(br, bt, user=u)),
        ("/social",              lambda r, u, br, bt: _social_monitor_page(br, bt, user=u)),
        ("/social/history",      lambda r, u, br, bt: _coming_soon_page("social_history", "Social Media History", br, bt, user=u)),
        ("/calendar",            lambda r, u, br, bt: _calendar_page(br, bt, user=u)),
    ]:
        def make_handler(f):
            async def handler(request: Request):
                user, br, bt = _guard(request)
                if not user: return RedirectResponse(url="/login")
                return HTMLResponse(f(request, user, br, bt))
            return handler
        local_app.add_api_route(route, make_handler(fn), methods=["GET"])

    # patients sub-routes need stage arg — add separately
    for route, stage in [("/patients/active","active"),("/patients/billed","billed"),("/patients/awaiting","awaiting"),("/patients/closed","closed")]:
        def make_stage_handler(s):
            async def handler(request: Request):
                user, br, bt = _guard(request)
                if not user: return RedirectResponse(url="/login")
                return HTMLResponse(_patients_page(br, bt, s, user=user))
            return handler
        local_app.add_api_route(route, make_stage_handler(stage), methods=["GET"])

    print("Hub running at http://localhost:8000/login")
    uvicorn.run(local_app, host="0.0.0.0", port=8000)
