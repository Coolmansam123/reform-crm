"""
Page routes for the field-rep app.

Maps root URLs to the page renderers in `field_rep.pages`. This file only
registers the URLs and wires in the auth guard — the rendering lives in
the pages package, which previously lived in `hub/mobile.py`.
"""
import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from hub.access import _is_admin
from field_rep.pages import (
    _mobile_company_detail_page,
    _mobile_directory_page,
    _mobile_home_page,
    _mobile_lead_capture_page,
    _mobile_map_page,
    _mobile_outreach_due_page,
    _mobile_outreach_map_page,
    _mobile_recent_page,
    _mobile_route_page,
    _mobile_routes_dashboard_page,
)

from ..auth import get_session

router = APIRouter()


async def _guard(request: Request):
    """Return (session, br, bt) or (None, None, None) if unauthenticated."""
    session = await get_session(request)
    if not session:
        return None, None, None
    br = os.environ.get("BASEROW_URL", "")
    bt = os.environ.get("BASEROW_API_TOKEN", "")
    return session, br, bt


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user, br, bt = await _guard(request)
    if not user:
        return RedirectResponse(url="/login")
    return HTMLResponse(_mobile_home_page(br, bt, user=user))


@router.get("/routes", response_class=HTMLResponse)
async def routes_dashboard(request: Request):
    user, br, bt = await _guard(request)
    if not user:
        return RedirectResponse(url="/login")
    return HTMLResponse(_mobile_routes_dashboard_page(br, bt, user=user))


@router.get("/route", response_class=HTMLResponse)
async def route_detail(request: Request):
    user, br, bt = await _guard(request)
    if not user:
        return RedirectResponse(url="/login")
    return HTMLResponse(_mobile_route_page(br, bt, user=user))


@router.get("/lead", response_class=HTMLResponse)
async def lead_capture(request: Request):
    user, br, bt = await _guard(request)
    if not user:
        return RedirectResponse(url="/login")
    return HTMLResponse(_mobile_lead_capture_page(br, bt, user=user))


@router.get("/recent", response_class=HTMLResponse)
async def recent(request: Request):
    user, br, bt = await _guard(request)
    if not user:
        return RedirectResponse(url="/login")
    if not _is_admin(user):
        return RedirectResponse(url="/")
    return HTMLResponse(_mobile_recent_page(br, bt, user=user))


@router.get("/outreach", response_class=HTMLResponse)
async def outreach_due_page(request: Request):
    user, br, bt = await _guard(request)
    if not user:
        return RedirectResponse(url="/login")
    return HTMLResponse(_mobile_outreach_due_page(br, bt, user=user))


@router.get("/outreach/map", response_class=HTMLResponse)
async def outreach_map_page(request: Request):
    user, br, bt = await _guard(request)
    if not user:
        return RedirectResponse(url="/login")
    return HTMLResponse(_mobile_outreach_map_page(br, bt, user=user))


@router.get("/company/{company_id}", response_class=HTMLResponse)
async def company_detail_page(company_id: int, request: Request):
    user, br, bt = await _guard(request)
    if not user:
        return RedirectResponse(url="/login")
    return HTMLResponse(_mobile_company_detail_page(br, bt, company_id, user=user))


@router.get("/directory", response_class=HTMLResponse)
async def directory_page(request: Request):
    """Unified directory — all outreach companies across categories."""
    user, br, bt = await _guard(request)
    if not user:
        return RedirectResponse(url="/login")
    return HTMLResponse(_mobile_directory_page(br, bt, category="", user=user))


@router.get("/attorney", response_class=HTMLResponse)
async def attorney_directory_page(request: Request):
    user, br, bt = await _guard(request)
    if not user:
        return RedirectResponse(url="/login")
    return HTMLResponse(_mobile_directory_page(br, bt, category="attorney", user=user))


@router.get("/guerilla", response_class=HTMLResponse)
async def guerilla_directory_page(request: Request):
    user, br, bt = await _guard(request)
    if not user:
        return RedirectResponse(url="/login")
    return HTMLResponse(_mobile_directory_page(br, bt, category="guerilla", user=user))


@router.get("/community", response_class=HTMLResponse)
async def community_directory_page(request: Request):
    user, br, bt = await _guard(request)
    if not user:
        return RedirectResponse(url="/login")
    return HTMLResponse(_mobile_directory_page(br, bt, category="community", user=user))


@router.get("/map", response_class=HTMLResponse)
async def field_map(request: Request):
    """Focus view for a single venue: /map?venue=<venue_id>.

    Route planning is hub-only, so bare /map redirects home. When ?venue= is
    supplied, any authenticated user can see the focused view (reps follow
    the Navigate link from a company page).
    """
    user, br, bt = await _guard(request)
    if not user:
        return RedirectResponse(url="/login")
    if not request.query_params.get("venue"):
        return RedirectResponse(url="/")
    return HTMLResponse(_mobile_map_page(br, bt, user=user))


@router.get("/log")
async def log_redirect():
    """Legacy path from earlier hub iteration; keep redirecting so old bookmarks still land."""
    return RedirectResponse(url="/map", status_code=302)
