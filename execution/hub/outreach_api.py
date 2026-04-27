"""
Shared business logic for /api/outreach/* endpoints.

Backend-agnostic handlers (no modal.*, no os.environ reads) that both the
Modal hub and the Coolify field_rep app wrap with thin route handlers.
See `execution/hub/guerilla_api.py` for the established pattern.
"""
from datetime import date as _date
from typing import Awaitable, Callable

from fastapi.responses import JSONResponse

from .constants import T_COMPANIES, T_ACTIVITIES

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
# POST /api/companies/{id}/activities/photo — upload a photo to Bunny CDN
# Returns {url}; client then includes it as `photo_url` in the activity payload.
# ─────────────────────────────────────────────────────────────────────────────
async def upload_activity_photo(
    request, br: str, bt: str, user: dict, company_id: int,
    bunny_zone: str, bunny_key: str, bunny_cdn_base: str,
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
    upload_url = f"https://la.storage.bunnycdn.com/{bunny_zone}/activities/{company_id}/{key}"
    async with httpx.AsyncClient(timeout=60) as client:
        ur = await client.put(
            upload_url,
            content=data,
            headers={"AccessKey": bunny_key, "Content-Type": "application/octet-stream"},
        )
    if ur.status_code not in (200, 201):
        return JSONResponse({"error": f"bunny upload {ur.status_code}"}, status_code=502)
    return JSONResponse({"url": f"{bunny_cdn_base}/activities/{company_id}/{key}"})


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
               status, follow_up_date, days_overdue}
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
        })
    out.sort(key=lambda r: r["days_overdue"], reverse=True)
    return JSONResponse(out[:limit])
