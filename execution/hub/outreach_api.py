"""
Shared business logic for /api/outreach/* endpoints.

Backend-agnostic handlers (no modal.*, no os.environ reads) that both the
Modal hub and the Coolify field_rep app wrap with thin route handlers.
See `execution/hub/guerilla_api.py` for the established pattern.
"""
from datetime import date as _date
from typing import Awaitable, Callable

from fastapi.responses import JSONResponse

from .constants import T_COMPANIES, T_ACTIVITIES, T_GOR_ROUTE_STOPS

CachedRowsFn = Callable[[int], Awaitable[list]]


def _sv(v):
    """Extract scalar from Baserow single_select / link_row shapes."""
    if isinstance(v, dict):
        return v.get("value", "") or v.get("name", "") or ""
    if isinstance(v, list) and v:
        x = v[0]
        if isinstance(x, dict):
            return x.get("value", "") or x.get("name", "") or ""
        return str(x)
    return v or ""


def _fu_date(company: dict) -> str:
    """Return the patient/contact's scheduled follow-up date (ISO yyyy-mm-dd)
    or empty string. T_COMPANIES uses `Follow-Up Date` as the canonical field;
    some legacy migration data may fall back to alternate casings."""
    v = (company.get("Follow-Up Date")
         or company.get("Follow Up Date")
         or "").strip()
    if not v:
        return ""
    return str(v)[:10]


def _is_overdue(company: dict, today_iso: str) -> bool:
    fu = _fu_date(company)
    if not fu:
        return False
    return fu < today_iso


def _excluded_status(company: dict) -> bool:
    """Blacklisted or permanently-closed companies are dropped from outreach."""
    status = _sv(company.get("Contact Status")).strip().lower()
    if status == "blacklisted":
        return True
    if company.get("Permanently Closed") is True:
        return True
    return False


from datetime import datetime as _dt, timezone as _tz


def _iso_now() -> str:
    return _dt.now(_tz.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/companies/{id} — fetch one company row by id
# ─────────────────────────────────────────────────────────────────────────────
async def get_company(br: str, bt: str, company_id: int) -> JSONResponse:
    import httpx
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{br}/api/database/rows/table/{T_COMPANIES}/{company_id}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}"},
        )
    if r.status_code == 404:
        return JSONResponse({"error": "not found"}, status_code=404)
    if r.status_code != 200:
        return JSONResponse({"error": r.text[:300]}, status_code=r.status_code)
    return JSONResponse(r.json())


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/companies/{id}/activities — list activities for a company
# ─────────────────────────────────────────────────────────────────────────────
async def get_company_activities(br: str, bt: str, company_id: int,
                                  cached_rows: CachedRowsFn) -> JSONResponse:
    if not T_ACTIVITIES:
        return JSONResponse([])
    rows = await cached_rows(T_ACTIVITIES)

    def _links(v):
        return [x.get("id") if isinstance(x, dict) else x for x in (v or [])]

    matched = [r for r in rows or [] if company_id in _links(r.get("Company"))]
    matched.sort(key=lambda a: (a.get("Created") or a.get("Date") or ""), reverse=True)
    return JSONResponse(matched)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/companies/{id}/activities — log a new activity on a company
# ─────────────────────────────────────────────────────────────────────────────
async def create_company_activity(
    request, br: str, bt: str, user: dict, company_id: int,
    invalidate=None,
) -> JSONResponse:
    """Body: {summary, kind, type, outcome, person, follow_up, date, contact_id,
    sentiment, photo_url}. `kind` defaults to 'user_activity'. `summary` is required.
    `sentiment` is optional; one of 'Green' / 'Yellow' / 'Red'. `photo_url` is
    optional (uploaded separately via /api/companies/{id}/activities/photo)."""
    import httpx
    if not T_ACTIVITIES:
        return JSONResponse({"error": "activities not configured"}, status_code=503)
    body = await request.json()
    summary = (body.get("summary") or "").strip()
    if not summary:
        return JSONResponse({"error": "summary required"}, status_code=400)
    sentiment = (body.get("sentiment") or "").strip()
    if sentiment and sentiment not in ("Green", "Yellow", "Red"):
        sentiment = ""
    payload = {
        "Summary":        summary,
        "Kind":           body.get("kind") or "user_activity",
        "Type":           body.get("type") or None,
        "Outcome":        body.get("outcome") or None,
        "Contact Person": body.get("person") or "",
        "Follow-Up Date": body.get("follow_up") or None,
        "Date":           body.get("date") or _iso_now()[:10],
        "Author":         user.get("email", ""),
        "Created":        _iso_now(),
        "Company":        [company_id],
        "Sentiment":      sentiment or None,
        "Photo URL":      (body.get("photo_url") or "").strip() or None,
        "Audio URL":      (body.get("audio_url") or "").strip() or None,
        "Transcript":     (body.get("transcript") or "").strip() or None,
    }
    if body.get("contact_id"):
        try: payload["Contact"] = [int(body["contact_id"])]
        except Exception: pass
    clean = {k: v for k, v in payload.items() if v not in (None, "")}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            f"{br}/api/database/rows/table/{T_ACTIVITIES}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
            json=clean,
        )
    if r.status_code not in (200, 201):
        return JSONResponse({"error": r.text[:300]}, status_code=r.status_code)
    # Also patch the parent Company so Follow-Up Date + Contact Status reflect
    # the latest activity. Field reps rely on the Outreach Due dashboard
    # computed from Company.Follow-Up Date, so NOT patching here would leave
    # the company "overdue" even after a fresh check-in.
    patch: dict = {}
    if body.get("follow_up"):
        patch["Follow-Up Date"] = body["follow_up"]
    new_status = (body.get("new_status") or "").strip()
    if new_status:
        patch["Contact Status"] = new_status
    if patch:
        patch["Updated"] = _iso_now()
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                await client.patch(
                    f"{br}/api/database/rows/table/{T_COMPANIES}/{company_id}/?user_field_names=true",
                    headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
                    json=patch,
                )
            except Exception:
                pass
    if invalidate is not None:
        try: await invalidate(T_ACTIVITIES, T_COMPANIES)
        except Exception: pass
    return JSONResponse(r.json())


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/activities/transcribe — upload audio to Bunny + transcribe via Whisper
# Returns {audio_url, transcript}; client fills the Notes textarea with the
# transcript (rep can edit) and includes both in the activity payload.
# ─────────────────────────────────────────────────────────────────────────────
async def transcribe_activity_audio(
    request, user: dict, openai_api_key: str,
    bunny_zone: str, bunny_key: str, bunny_cdn_base: str,
    bunny_prefix: str = "activities",
) -> JSONResponse:
    import httpx, secrets
    if not openai_api_key:
        return JSONResponse({"error": "transcription not configured"}, status_code=503)
    form = await request.form()
    audio = form.get("audio")
    if not audio or not hasattr(audio, "read"):
        return JSONResponse({"error": "audio file required"}, status_code=400)
    data = await audio.read()
    if not data:
        return JSONResponse({"error": "empty audio"}, status_code=400)
    fname = (audio.filename or "recording.webm").rsplit(".", 1)
    ext = fname[1].lower() if len(fname) == 2 else "webm"
    if ext not in ("webm", "mp4", "m4a", "mp3", "wav", "ogg"):
        ext = "webm"
    key = f"{secrets.token_urlsafe(8)}.{ext}"
    sub = "Transcriptions" if bunny_prefix != "activities" else "audio"
    upload_url = f"https://la.storage.bunnycdn.com/{bunny_zone}/{bunny_prefix}/{sub}/{key}"
    audio_url = ""
    async with httpx.AsyncClient(timeout=60) as client:
        ur = await client.put(
            upload_url,
            content=data,
            headers={"AccessKey": bunny_key, "Content-Type": "application/octet-stream"},
        )
        if ur.status_code in (200, 201):
            audio_url = f"{bunny_cdn_base}/{bunny_prefix}/{sub}/{key}"
        else:
            return JSONResponse({"error": f"bunny upload {ur.status_code}"}, status_code=502)
    # Transcribe via OpenAI Whisper. AsyncOpenAI accepts a (filename, bytes) tuple.
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=openai_api_key)
        result = await client.audio.transcriptions.create(
            model="whisper-1",
            file=(f"recording.{ext}", data),
        )
        transcript = (getattr(result, "text", "") or "").strip()
    except Exception as e:
        # Bunny upload succeeded; surface partial result so the rep doesn't lose
        # the recording even if Whisper fails.
        return JSONResponse({
            "audio_url": audio_url,
            "transcript": "",
            "error": f"transcription failed: {str(e)[:200]}",
        }, status_code=200)
    return JSONResponse({"audio_url": audio_url, "transcript": transcript})


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/companies/{id}/activities/photo — upload a photo to Bunny CDN
# Returns {url}; client then includes it as `photo_url` in the activity payload.
# ─────────────────────────────────────────────────────────────────────────────
async def upload_activity_photo(
    request, br: str, bt: str, user: dict, company_id: int,
    bunny_zone: str, bunny_key: str, bunny_cdn_base: str,
    bunny_prefix: str = "activities",
) -> JSONResponse:
    import httpx, secrets
    form = await request.form()
    photo = form.get("photo")
    if not photo or not hasattr(photo, "read"):
        return JSONResponse({"error": "photo file required"}, status_code=400)
    data = await photo.read()
    if not data:
        return JSONResponse({"error": "empty file"}, status_code=400)
    fname = (photo.filename or "photo.jpg").rsplit(".", 1)
    ext = fname[1].lower() if len(fname) == 2 else "jpg"
    if ext not in ("jpg", "jpeg", "png", "webp", "heic"):
        ext = "jpg"
    key = f"{secrets.token_urlsafe(8)}.{ext}"
    # Legacy "activities" prefix kept the per-company subfolder; new
    # "Routes"/"CRM" prefixes are flat under Photos/.
    if bunny_prefix == "activities":
        path = f"activities/{company_id}/{key}"
    else:
        path = f"{bunny_prefix}/Photos/{key}"
    upload_url = f"https://la.storage.bunnycdn.com/{bunny_zone}/{path}"
    async with httpx.AsyncClient(timeout=60) as client:
        ur = await client.put(
            upload_url,
            content=data,
            headers={"AccessKey": bunny_key, "Content-Type": "application/octet-stream"},
        )
    if ur.status_code not in (200, 201):
        return JSONResponse({"error": f"bunny upload {ur.status_code}"}, status_code=502)
    return JSONResponse({"url": f"{bunny_cdn_base}/{path}"})


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/outreach/due — all companies with Follow-Up Date < today
# ─────────────────────────────────────────────────────────────────────────────
async def get_outreach_due(
    br: str, bt: str, user: dict,
    cached_rows: CachedRowsFn,
    *,
    limit: int = 200,
) -> JSONResponse:
    """Return overdue-follow-up companies across all categories, sorted
    by how overdue. Shape: lightweight list tailored for a mobile dashboard.

    Each row: {id, name, category, phone, address, latitude, longitude,
               status, follow_up_date, days_overdue, venue_id}
    `venue_id` is populated only for guerilla-category companies whose
    `Legacy Source == 'guerilla_venue'`; the To Do page uses it to enable
    the "+ Add to route" button (route stops link to T_GOR_VENUES).
    """
    if not T_COMPANIES:
        return JSONResponse([])
    rows = await cached_rows(T_COMPANIES)
    today_iso = _date.today().isoformat()

    out: list[dict] = []
    for c in rows or []:
        if _excluded_status(c):
            continue
        if not _is_overdue(c, today_iso):
            continue
        fu = _fu_date(c)
        try:
            y, m, d = fu.split("-")
            from datetime import date as _d
            days = (_date.today() - _d(int(y), int(m), int(d))).days
        except Exception:
            days = 0
        venue_id = None
        if _sv(c.get("Legacy Source")) == "guerilla_venue":
            try: venue_id = int(c.get("Legacy ID"))
            except (TypeError, ValueError): venue_id = None
        out.append({
            "id":              c.get("id"),
            "name":            (c.get("Name") or "").strip() or "(unnamed)",
            "category":        _sv(c.get("Category")) or "other",
            "phone":           (c.get("Phone") or "").strip(),
            "address":         (c.get("Address") or "").strip(),
            "latitude":        (c.get("Latitude") or "").strip() if isinstance(c.get("Latitude"), str) else c.get("Latitude"),
            "longitude":       (c.get("Longitude") or "").strip() if isinstance(c.get("Longitude"), str) else c.get("Longitude"),
            "status":          _sv(c.get("Contact Status")),
            "follow_up_date":  fu,
            "days_overdue":    days,
            "venue_id":        venue_id,
        })
    out.sort(key=lambda r: r["days_overdue"], reverse=True)
    return JSONResponse(out[:limit])


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/outreach/skipped — recent route stops the rep skipped or didn't reach
# ─────────────────────────────────────────────────────────────────────────────
async def get_skipped_stops(
    br: str, bt: str, user: dict,
    cached_rows: CachedRowsFn,
    *,
    window_days: int = 30,
    limit: int = 200,
) -> JSONResponse:
    """Return recent T_GOR_ROUTE_STOPS rows where Status is Skipped or
    Not Reached, deduped by venue (latest skip wins). Used by the To Do
    page so reps can re-queue abandoned venues onto a fresh route.

    Each row: {venue_id, venue_name, company_id, status, reason,
               completed_at, days_ago}
    """
    if not T_GOR_ROUTE_STOPS:
        return JSONResponse([])
    stops = await cached_rows(T_GOR_ROUTE_STOPS) or []
    today = _date.today()
    cutoff_ord = today.toordinal() - window_days

    from datetime import date as _d
    by_venue: dict[int, dict] = {}
    for s in stops:
        status = _sv(s.get("Status"))
        if status not in ("Skipped", "Not Reached"):
            continue
        completed = (s.get("Completed At") or "").strip()
        if not completed:
            continue
        try:
            y, m, dd = completed[:10].split("-")
            stop_date = _d(int(y), int(m), int(dd))
        except Exception:
            continue
        if stop_date.toordinal() < cutoff_ord:
            continue
        venue_link = s.get("Venue") or []
        venue_id = None
        venue_name = ""
        if isinstance(venue_link, list) and venue_link:
            v0 = venue_link[0]
            if isinstance(v0, dict):
                venue_id = v0.get("id")
                venue_name = v0.get("value") or v0.get("name") or ""
            else:
                venue_id = v0
        if venue_id is None:
            continue
        try: venue_id = int(venue_id)
        except (TypeError, ValueError): continue
        if not venue_name:
            venue_name = (s.get("Name") or "").strip() or f"Venue {venue_id}"
        existing = by_venue.get(venue_id)
        if existing and existing["completed_at"] >= completed:
            continue
        by_venue[venue_id] = {
            "venue_id":     venue_id,
            "venue_name":   venue_name,
            "company_id":   None,  # filled below
            "status":       status,
            "reason":       (s.get("Notes") or "").strip(),
            "completed_at": completed,
            "days_ago":     (today - stop_date).days,
        }

    if by_venue and T_COMPANIES:
        companies = await cached_rows(T_COMPANIES) or []
        venue_to_co: dict[int, int] = {}
        for c in companies:
            if _sv(c.get("Legacy Source")) != "guerilla_venue":
                continue
            lid = c.get("Legacy ID")
            try: venue_to_co[int(lid)] = c.get("id")
            except (TypeError, ValueError): pass
        for vid, row in by_venue.items():
            row["company_id"] = venue_to_co.get(vid)

    out = list(by_venue.values())
    out.sort(key=lambda r: r["completed_at"], reverse=True)
    return JSONResponse(out[:limit])
