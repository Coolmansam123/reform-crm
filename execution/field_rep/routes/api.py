"""
API routes for the field-rep app.

Thin wrappers around the shared handlers in `hub/guerilla_api.py`. Each
wrapper resolves the session + Baserow creds, calls the shared handler, then
invalidates any relevant Redis cache entries.

One endpoint (`GET /api/data/{tid}`) is NOT in the shared module — it reads
from this app's Redis cache specifically, so it stays here.

URL paths match the hub exactly (`/api/guerilla/*`, `/api/data/{tid}`) so the
existing mobile.py JS ports over without changes.
"""
import asyncio
import os
from typing import Awaitable, Callable

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from hub import guerilla_api
from hub.access import _is_admin
from hub.constants import (
    T_EVENTS, T_GOR_ACTS, T_GOR_BOXES, T_GOR_ROUTES, T_GOR_ROUTE_STOPS,
    T_GOR_VENUES, T_LEADS,
    T_CONSENT_FORMS, T_CONSENT_SUBMISSIONS,
)

from .. import kiosk as kiosk_mod
from .. import storage
from ..auth import get_session

router = APIRouter()


# ─── helpers ─────────────────────────────────────────────────────────────────
def _env() -> tuple[str, str]:
    return (os.environ.get("BASEROW_URL", ""),
            os.environ.get("BASEROW_API_TOKEN", ""))


async def _fetch_table_all(br: str, bt: str, tid: int) -> list:
    """Paginated full-table fetch. Mirrors the hub's implementation."""
    headers = {"Authorization": f"Token {bt}"}
    base_url = f"{br}/api/database/rows/table/{tid}/?size=200&user_field_names=true&page="
    async with httpx.AsyncClient(timeout=30) as client:
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


async def _cached_rows(tid: int) -> list:
    """Cache-aware fetcher passed to shared handlers that need table data."""
    br, bt = _env()
    return await storage.cached_table(tid, lambda: _fetch_table_all(br, bt, tid))


async def _invalidate(*tids: int) -> None:
    for tid in tids:
        try:
            await storage.invalidate_table(tid)
        except Exception:
            pass


def _bunny_env() -> tuple[str, str, str]:
    return (
        os.environ.get("BUNNY_STORAGE_ZONE", "techopssocialmedia"),
        os.environ.get("BUNNY_STORAGE_API_KEY", ""),
        os.environ.get("BUNNY_CDN_BASE", "https://techopssocialmedia.b-cdn.net"),
    )


# ─── Generic table fetch (locally-cached) ────────────────────────────────────
@router.get("/api/data/{tid}")
async def table_data(tid: int, request: Request):
    if not await get_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    rows = await _cached_rows(tid)
    return JSONResponse(rows)


# ─── Cross-app cache invalidation (hub → field_rep webhook) ──────────────────
# When an admin writes to a guerilla table on the Modal hub, the hub POSTs
# here so field_rep's Redis cache for that table gets dropped and the next
# mobile read pulls fresh data. Without this, reps see stale data until TTL
# expires (~5min depending on cache config).
#
# Token-gated with FIELD_REP_INVALIDATE_TOKEN to prevent random DoS. The
# hub's matching FIELD_REP_INVALIDATE_TOKEN comes from the `field-rep-sync`
# Modal secret.
@router.post("/api/invalidate")
async def invalidate_cache(request: Request):
    expected = os.environ.get("FIELD_REP_INVALIDATE_TOKEN", "").strip()
    if not expected:
        return JSONResponse({"ok": False, "error": "not configured"}, status_code=503)
    supplied = request.headers.get("X-Invalidate-Token", "").strip()
    if supplied != expected:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        body = {}
    tids = body.get("tids") or []
    invalidated: list[int] = []
    for tid in tids:
        try:
            await storage.invalidate_table(int(tid))
            invalidated.append(int(tid))
        except Exception:
            pass
    return JSONResponse({"ok": True, "invalidated": invalidated})


# ─── Guerilla activity log ───────────────────────────────────────────────────
@router.post("/api/guerilla/log")
async def guerilla_log(request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    bzone, bkey, bcdn = _bunny_env()
    resp = await guerilla_api.guerilla_log(request, br, bt, session,
                                           bunny_zone=bzone, bunny_key=bkey,
                                           bunny_cdn_base=bcdn)
    # Drop cached snapshots so the next read (briefing + visit history) picks
    # up the row we just wrote. Without this the rep sees "No prior visits"
    # right after a successful Check-In submit.
    if 200 <= resp.status_code < 300:
        await _invalidate(T_GOR_ACTS, T_GOR_VENUES, T_EVENTS)
    return resp


# ─── Events: admin-only patch (Event Status / Checked In / Decision Notes) ──
_EVENT_STATUSES = {
    "Prospective", "Maybe", "Approved", "Declined", "Scheduled", "Completed",
}
_EVENT_PATCH_ALLOWLIST = {
    "Event Status", "Checked In", "Decision Notes",
    "Anticipated Count", "Notes", "Staff Attending",
    # Equipment booleans (existing + B5 additions)
    "Generator Needed", "Table Needed", "EZ Up Needed",
    "Massage Chair Needed", "Massage Table Needed",
    "Banner Needed", "Flyers Needed", "Intake Forms Needed",
    "Tablet Needed", "Power Strip Needed",
}


@router.patch("/api/events/{event_id}")
async def update_event(event_id: int, request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    if not _is_admin(session):
        return JSONResponse({"error": "admin only"}, status_code=403)
    body = await request.json() or {}
    patch: dict = {}
    for k, v in body.items():
        if k not in _EVENT_PATCH_ALLOWLIST:
            continue
        if k == "Event Status" and v and v not in _EVENT_STATUSES:
            return JSONResponse({"error": f"invalid status: {v}"}, status_code=400)
        patch[k] = v
    if not patch:
        return JSONResponse({"error": "no valid fields"}, status_code=400)
    br, bt = _env()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.patch(
            f"{br}/api/database/rows/table/{T_EVENTS}/{event_id}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
            json=patch,
        )
    if r.status_code >= 300:
        return JSONResponse({"error": "baserow write failed", "detail": r.text[:400]}, status_code=502)
    await _invalidate(T_EVENTS)
    return JSONResponse({"ok": True})


# ─── Outreach: overdue follow-ups across categories ─────────────────────────
@router.get("/api/outreach/due")
async def outreach_due(request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    from hub import outreach_api
    br, bt = _env()
    return await outreach_api.get_outreach_due(br, bt, session, _cached_rows)


# ─── Outreach: recent skipped / not-reached route stops ─────────────────────
@router.get("/api/outreach/skipped")
async def outreach_skipped(request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    from hub import outreach_api
    br, bt = _env()
    return await outreach_api.get_skipped_stops(br, bt, session, _cached_rows)


# ─── Leaderboard (Top Performers card on the rep home) ──────────────────────
@router.get("/api/leaderboard")
async def leaderboard(request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    from hub import rep_performance
    br, bt = _env()
    return await rep_performance.rep_leaderboard(request, br, bt, session, _cached_rows)


# ─── Companies: read + activity log (mobile detail page uses these) ─────────
async def _invalidate_async(*tids: int) -> None:
    await _invalidate(*tids)


@router.get("/api/companies/{company_id}")
async def get_company(company_id: int, request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    from hub import outreach_api
    br, bt = _env()
    return await outreach_api.get_company(br, bt, company_id)


@router.get("/api/companies/{company_id}/activities")
async def get_company_activities(company_id: int, request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    from hub import outreach_api
    br, bt = _env()
    return await outreach_api.get_company_activities(br, bt, company_id, _cached_rows)


@router.post("/api/companies/{company_id}/activities")
async def create_company_activity(company_id: int, request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    from hub import outreach_api
    br, bt = _env()
    return await outreach_api.create_company_activity(
        request, br, bt, session, company_id,
        invalidate=_invalidate_async,
    )


@router.post("/api/companies/{company_id}/activities/photo")
async def upload_activity_photo(company_id: int, request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    from hub import outreach_api
    br, bt = _env()
    bzone, bkey, bcdn = _bunny_env()
    return await outreach_api.upload_activity_photo(
        request, br, bt, session, company_id,
        bunny_zone=bzone, bunny_key=bkey, bunny_cdn_base=bcdn,
        bunny_prefix="Routes",
    )


@router.post("/api/activities/photo")
async def upload_generic_activity_photo(request: Request):
    """Generic (non-company-scoped) photo upload for the s2 Check-In form.
    Accepts a `venue_id` form field for the Bunny path prefix; reuses the
    existing outreach_api.upload_activity_photo helper which only uses the
    int it's given as a path component."""
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    from hub import outreach_api
    br, bt = _env()
    bzone, bkey, bcdn = _bunny_env()
    form = await request.form()
    try:
        venue_id = int(form.get("venue_id") or 0)
    except (TypeError, ValueError):
        venue_id = 0
    return await outreach_api.upload_activity_photo(
        request, br, bt, session, venue_id,
        bunny_zone=bzone, bunny_key=bkey, bunny_cdn_base=bcdn,
        bunny_prefix="Routes",
    )


@router.post("/api/activities/transcribe")
async def transcribe_activity_audio(request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    from hub import outreach_api
    bzone, bkey, bcdn = _bunny_env()
    return await outreach_api.transcribe_activity_audio(
        request, session,
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        bunny_zone=bzone, bunny_key=bkey, bunny_cdn_base=bcdn,
        bunny_prefix="Routes",
    )


@router.post("/api/rep/ping")
async def rep_ping(request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
    from hub.rep_tracker import update_rep_location
    br, bt = _env()
    return await update_rep_location(request, br, bt, session)


# ─── Push notifications ─────────────────────────────────────────────────────
def _vapid_env() -> tuple[str, str, str]:
    return (
        os.environ.get("VAPID_PUBLIC_KEY", ""),
        os.environ.get("VAPID_PRIVATE_KEY", ""),
        os.environ.get("VAPID_SUBJECT", "mailto:techops@reformchiropractic.com"),
    )


@router.get("/api/push/vapid-public-key")
async def push_vapid_public_key(request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    from hub.push import vapid_public_key
    pub, _, _ = _vapid_env()
    return vapid_public_key(pub)


@router.post("/api/push/subscribe")
async def push_subscribe(request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
    from hub.push import subscribe
    br, bt = _env()
    return await subscribe(request, br, bt, session)


@router.post("/api/push/test")
async def push_test(request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
    from hub.push import test_push
    br, bt = _env()
    pub, priv, sub = _vapid_env()
    return await test_push(
        request, br, bt, session,
        vapid_public_key_b64url=pub,
        vapid_private_key_b64url=priv,
        vapid_subject=sub,
    )


# ─── Lead detail (read + edit) ───────────────────────────────────────────────
@router.get("/api/leads/{lead_id}")
async def get_lead(lead_id: int, request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{br}/api/database/rows/table/{T_LEADS}/{lead_id}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}"},
        )
    if r.status_code == 404:
        return JSONResponse({"error": "not found"}, status_code=404)
    if r.status_code != 200:
        return JSONResponse({"error": r.text[:300]}, status_code=r.status_code)
    return JSONResponse(r.json())


@router.patch("/api/leads/{lead_id}")
async def update_lead(lead_id: int, request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    body = await request.json()
    # Whitelist editable fields. Single_select values pass as bare strings
    # (per memory feedback_baserow_single_select.md).
    allowed = {"Name", "Phone", "Email", "Status", "Reason", "Source",
               "Notes", "Follow-Up Date"}
    payload = {k: v for k, v in (body or {}).items() if k in allowed}
    if not payload:
        return JSONResponse({"error": "no fields to update"}, status_code=400)
    br, bt = _env()
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.patch(
            f"{br}/api/database/rows/table/{T_LEADS}/{lead_id}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
            json=payload,
        )
    if r.status_code not in (200, 201):
        return JSONResponse({"error": r.text[:300]}, status_code=r.status_code)
    await _invalidate(T_LEADS)
    return JSONResponse(r.json())


# ─── Lead capture (field-rep form) ───────────────────────────────────────────
# Field reps submit the Capture Lead form to this endpoint. Creates a T_LEADS
# row; on success, the mobile UI closes the form. The hub has an analogous
# endpoint that also fires `new_lead` automations — this field-rep version
# skips trigger firing because automations run on the Modal hub, which we
# don't have a direct handle to from here. If/when that matters, wire a
# cross-app HTTP call here.
@router.post("/api/leads/capture")
async def capture_lead(request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    return await guerilla_api.capture_lead(
        request, br, bt, session,
        cached_rows=_cached_rows,
        invalidate=_invalidate,
    )


# ─── Massage box CRUD ────────────────────────────────────────────────────────
@router.post("/api/guerilla/boxes")
async def create_box(request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    resp = await guerilla_api.create_box(request, br, bt, session)
    await _invalidate(T_GOR_BOXES)
    return resp


@router.patch("/api/guerilla/boxes/{box_id}/pickup")
async def pickup_box(request: Request, box_id: int):
    session = await get_session(request)
    if not session:
        return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    resp = await guerilla_api.pickup_box(request, br, bt, session, box_id)
    await _invalidate(T_GOR_BOXES)
    return resp


@router.patch("/api/guerilla/boxes/{box_id}")
async def update_box(request: Request, box_id: int):
    session = await get_session(request)
    if not session:
        return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    resp = await guerilla_api.update_box(request, br, bt, session, box_id)
    await _invalidate(T_GOR_BOXES)
    return resp


@router.patch("/api/guerilla/boxes/{box_id}/days")
async def update_box_days(request: Request, box_id: int):
    session = await get_session(request)
    if not session:
        return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    resp = await guerilla_api.update_box_days(request, br, bt, session, box_id)
    await _invalidate(T_GOR_BOXES)
    return resp


# ─── Venue update ────────────────────────────────────────────────────────────
@router.patch("/api/guerilla/venues/{venue_id}")
async def update_venue(request: Request, venue_id: int):
    session = await get_session(request)
    if not session:
        return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    resp = await guerilla_api.update_venue(request, br, bt, session, venue_id)
    await _invalidate(T_GOR_VENUES)
    return resp


# ─── Routes API ──────────────────────────────────────────────────────────────
@router.get("/api/guerilla/routes/today")
async def routes_today(request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    return await guerilla_api.routes_today(request, br, bt, session, _cached_rows)


@router.get("/api/guerilla/routes/{route_id}")
async def route_detail(route_id: int, request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    return await guerilla_api.route_detail(request, br, bt, session, route_id, _cached_rows)


@router.patch("/api/guerilla/routes/stops/{stop_id}")
async def update_route_stop(request: Request, stop_id: int):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    resp = await guerilla_api.update_route_stop(request, br, bt, session, stop_id)
    await _invalidate(T_GOR_ROUTE_STOPS)
    return resp


@router.get("/api/guerilla/active-stop")
async def get_active_stop(request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    return await guerilla_api.get_active_stop(request, br, bt, session, _cached_rows)


@router.post("/api/guerilla/routes")
async def gorilla_routes_create(request: Request):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    resp = await guerilla_api.gorilla_routes_create(request, br, bt, session)
    await _invalidate(T_GOR_ROUTES, T_GOR_ROUTE_STOPS)
    return resp


@router.patch("/api/guerilla/routes/{route_id}/status")
async def gorilla_route_status(request: Request, route_id: int):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    resp = await guerilla_api.gorilla_route_status(request, br, bt, session, route_id)
    await _invalidate(T_GOR_ROUTES)
    return resp


@router.patch("/api/guerilla/routes/{route_id}")
async def gorilla_route_update(request: Request, route_id: int):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    resp = await guerilla_api.gorilla_route_update(request, br, bt, session, route_id, _cached_rows)
    await _invalidate(T_GOR_ROUTES, T_GOR_ROUTE_STOPS)
    return resp


@router.post("/api/guerilla/routes/{route_id}/stops")
async def gorilla_route_append_stop(request: Request, route_id: int):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    resp = await guerilla_api.gorilla_route_append_stop(
        request, br, bt, session, route_id, _cached_rows
    )
    await _invalidate(T_GOR_ROUTE_STOPS)
    return resp


@router.delete("/api/guerilla/routes/{route_id}")
async def gorilla_route_delete(request: Request, route_id: int):
    session = await get_session(request)
    if not session:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    br, bt = _env()
    resp = await guerilla_api.gorilla_route_delete(request, br, bt, session, route_id, _cached_rows)
    await _invalidate(T_GOR_ROUTES, T_GOR_ROUTE_STOPS)
    return resp


# ─── Kiosk + Consent (kiosk mode) ───────────────────────────────────────────

@router.post("/api/kiosk/start")
async def kiosk_start(request: Request):
    """Authenticated rep creates a new kiosk session. Returns {kiosk_id, ...}."""
    session = await get_session(request)
    if not session:
        return JSONResponse({"ok": False, "error": "unauthenticated"}, status_code=401)
    body = await request.json() or {}
    try:
        result = await kiosk_mod.start_kiosk(
            event_id=int(body.get("event_id") or 0),
            event_name=str(body.get("event_name") or ""),
            consent_slugs=list(body.get("consent_slugs") or []),
            pin=str(body.get("pin") or ""),
            created_by=session.get("email") or session.get("name") or "",
        )
    except ValueError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    return JSONResponse({"ok": True, **result})


@router.post("/api/kiosk/exit")
async def kiosk_exit(request: Request):
    """Public endpoint — validates PIN against the kiosk session and ends it."""
    body = await request.json() or {}
    ok = await kiosk_mod.exit_kiosk(
        kiosk_id=str(body.get("kiosk_id") or ""),
        pin=str(body.get("pin") or ""),
    )
    if not ok:
        return JSONResponse({"ok": False, "error": "invalid pin or expired session"}, status_code=401)
    return JSONResponse({"ok": True})


@router.get("/api/kiosk/{kiosk_id}")
async def kiosk_get(kiosk_id: str):
    """Public — returns kiosk metadata sans PIN. Includes the consent forms
    selected by the rep so the run page can render their bodies."""
    public = await kiosk_mod.get_public_kiosk(kiosk_id)
    if not public:
        return JSONResponse({"error": "not found or expired"}, status_code=404)
    # Hydrate consent form bodies from T_CONSENT_FORMS so the kiosk page can
    # render them without a second round-trip per form.
    forms_full: list[dict] = []
    if public["consent_slugs"]:
        all_forms = await _cached_rows(T_CONSENT_FORMS)
        by_slug = {f.get("Slug"): f for f in all_forms}
        for slug in public["consent_slugs"]:
            f = by_slug.get(slug)
            if not f or not f.get("Active"):
                continue
            forms_full.append({
                "id": f.get("id"),
                "slug": f.get("Slug"),
                "name": f.get("Display Name") or slug,
                "version": f.get("Version") or "v1",
                "body": f.get("Body") or "",
            })
    public["consent_forms"] = forms_full
    return JSONResponse(public)


@router.post("/api/kiosk/{kiosk_id}/lead")
async def kiosk_capture_lead(kiosk_id: str, request: Request):
    """Public lead capture inside an active kiosk session."""
    body = await request.json() or {}
    br, bt = _env()
    result = await kiosk_mod.capture_lead_via_kiosk(
        br=br, bt=bt, kiosk_id=kiosk_id,
        name=str(body.get("name") or ""),
        phone=str(body.get("phone") or ""),
        email=str(body.get("email") or ""),
        reason=str(body.get("reason") or ""),
        notes=str(body.get("notes") or ""),
    )
    if not result.get("ok"):
        return JSONResponse(result, status_code=400)
    return JSONResponse(result)


@router.post("/api/kiosk/{kiosk_id}/consent")
async def kiosk_submit_consent(kiosk_id: str, request: Request):
    """Public consent submission from a kiosk lead. Uploads signature PNG to
    Bunny and writes a Consent Submissions row."""
    body = await request.json() or {}
    br, bt = _env()
    result = await kiosk_mod.submit_consent(
        br=br, bt=bt, kiosk_id=kiosk_id,
        lead_id=int(body.get("lead_id") or 0),
        consent_form_id=int(body.get("consent_form_id") or 0),
        form_slug=str(body.get("form_slug") or ""),
        form_version=str(body.get("form_version") or ""),
        signed_name=str(body.get("signed_name") or ""),
        signature_data_url=str(body.get("signature_data_url") or ""),
        payload=body.get("payload") or {},
    )
    if not result.get("ok"):
        return JSONResponse(result, status_code=400)
    return JSONResponse(result)
