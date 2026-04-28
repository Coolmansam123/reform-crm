"""
Shared business logic for /api/guerilla/* endpoints.

This module holds the pure handler functions — no route decorators, no session
lookup, no env-var reading. Each handler takes everything it needs via
parameters and returns a `fastapi.responses.JSONResponse`.

Both `execution/modal_outreach_hub.py` (hub on Modal) and
`execution/field_rep/routes/api.py` (field-rep app on Coolify) import from
here and register their own thin wrappers around these handlers.

Ground rules:
- No `modal.*` imports — must run outside Modal.
- No `os.environ` reads — env is the wrapper's responsibility.
- Session/auth is the wrapper's responsibility; handlers receive the resolved
  `user: dict` directly.
- Baserow URL + token come in as `br: str` and `bt: str` parameters.
"""
import hashlib
import json as _json
import secrets
from datetime import date as _date, datetime as _dt
from typing import Awaitable, Callable

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

from .access import _has_hub_access, _is_admin
from .constants import (
    T_EVENTS, T_GOR_ACTS, T_GOR_BOXES, T_GOR_ROUTES, T_GOR_ROUTE_STOPS,
    T_GOR_VENUES, T_COMPANIES, T_LEADS, T_ACTIVITIES,
)

# Type: backend-agnostic cached-table fetcher. Each app passes its own.
CachedRowsFn = Callable[[int], Awaitable[list]]


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/guerilla/log — log activity + optional Bunny flyer upload
# ─────────────────────────────────────────────────────────────────────────────
async def guerilla_log(request: Request, br: str, bt: str, user: dict,
                       bunny_zone: str, bunny_key: str, bunny_cdn_base: str) -> JSONResponse:
    """
    Creates a T_GOR_ACTS record from one of several form types. Optionally
    upserts a venue, uploads a flyer to Bunny CDN, and auto-creates a T_EVENTS
    row for event-type forms.

    `bunny_zone`, `bunny_key`, `bunny_cdn_base` are required for flyer uploads
    but only used for form_type == "External Event" with a multipart body.
    """
    if not _has_hub_access(user, "guerilla"):
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)

    # ── Parse payload (JSON or multipart for flyer upload) ─────────────────
    content_type = request.headers.get("content-type", "")
    flyer_bytes = None
    flyer_filename = None
    if "multipart/form-data" in content_type:
        form = await request.form()
        form_type = (form.get("form_type") or "").strip()
        try:
            fields = _json.loads(form.get("fields") or "{}")
        except Exception:
            fields = {}
        user_name = (form.get("user_name") or user.get("name", "")).strip()
        flyer_file = form.get("flyer")
        if flyer_file and hasattr(flyer_file, "read"):
            flyer_bytes = await flyer_file.read()
            flyer_filename = flyer_file.filename or "flyer.jpg"
    else:
        body = await request.json()
        form_type = (body.get("form_type") or "").strip()
        fields    = body.get("fields") or {}
        user_name = (body.get("user_name") or user.get("name", "")).strip()

    if not form_type:
        return JSONResponse({"ok": False, "error": "form_type required"}, status_code=400)

    today = _date.today().isoformat()

    async with httpx.AsyncClient(timeout=60) as client:
        br_headers = {"Authorization": f"Token {bt}", "Content-Type": "application/json"}

        # ── Venue resolution ──────────────────────────────────────────────
        # Caller can pass an explicit venue_id (route Check-In flow already
        # knows the venue) — that wins. Otherwise we name-lookup/upsert for
        # the form types that include a business field.
        venue_id = None
        explicit_vid = fields.get("venue_id")
        if explicit_vid not in (None, ""):
            try: venue_id = int(explicit_vid)
            except (ValueError, TypeError): pass
        FORMS_WITH_VENUE = {
            "Business Outreach Log", "Mobile Massage Service",
            "Lunch and Learn", "Health Assessment Screening",
        }
        if not venue_id and form_type in FORMS_WITH_VENUE:
            company_name = (
                fields.get("company_name") or fields.get("business_name") or ""
            ).strip()
            if company_name:
                sr = await client.get(
                    f"{br}/api/database/rows/table/{T_GOR_VENUES}/",
                    params={"search": company_name, "user_field_names": "true", "size": 10},
                    headers={"Authorization": f"Token {bt}"},
                )
                venue_row = None
                if sr.is_success:
                    for row in sr.json().get("results", []):
                        if (row.get("Name") or "").strip().lower() == company_name.lower():
                            venue_row = row
                            break
                if venue_row:
                    venue_id = venue_row["id"]
                else:
                    venue_fields: dict = {"Name": company_name}
                    addr    = (fields.get("venue_address") or fields.get("business_address") or "").strip()
                    phone   = (fields.get("contact_phone") or "").strip()
                    email   = (fields.get("contact_email") or "").strip()
                    contact = (fields.get("point_of_contact_name") or "").strip()
                    if addr:    venue_fields["Address"]        = addr
                    if phone:   venue_fields["Phone"]          = phone
                    if email:   venue_fields["Email"]          = email
                    if contact: venue_fields["Contact Person"] = contact
                    vr = await client.post(
                        f"{br}/api/database/rows/table/{T_GOR_VENUES}/?user_field_names=true",
                        headers=br_headers,
                        json=venue_fields,
                    )
                    if vr.status_code in (200, 201):
                        venue_id = vr.json().get("id")

        # ── Flyer upload to Bunny CDN (External Event only) ────────────────
        flyer_url = None
        if flyer_bytes and flyer_filename:
            safe_name  = flyer_filename.replace(" ", "_")
            upload_url = f"https://la.storage.bunnycdn.com/{bunny_zone}/guerilla/events/{safe_name}"
            ur = await client.put(
                upload_url,
                content=flyer_bytes,
                headers={"AccessKey": bunny_key, "Content-Type": "application/octet-stream"},
            )
            if ur.status_code in (200, 201):
                flyer_url = f"{bunny_cdn_base}/guerilla/events/{safe_name}"

        # ── Build Summary text ─────────────────────────────────────────────
        def _f(label, val):
            return f"{label}: {val}\n" if (val is not None and val != "") else ""

        lines = [f"Form: {form_type}", f"Submitted by: {user_name}", ""]

        if form_type == "Business Outreach Log":
            lines += [
                _f("Business",        fields.get("business_name")),
                _f("Contact",         fields.get("point_of_contact_name")),
                _f("Phone",           fields.get("contact_phone")),
                _f("Email",           fields.get("contact_email")),
                _f("Address",         fields.get("business_address")),
                _f("Massage Box Left",fields.get("massage_box_left")),
                "\n=== Lunch & Learn ===\n",
                _f("Interested",       fields.get("ll_interested")),
                _f("Follow-Up Date",   fields.get("ll_follow_up_date")),
                _f("Booking Requested",fields.get("ll_booking_requested")),
                _f("Notes",            fields.get("ll_notes")),
                "\n=== Health Assessment Screening ===\n",
                _f("Interested",       fields.get("has_interested")),
                _f("Follow-Up Date",   fields.get("has_follow_up_date")),
                _f("Booking Requested",fields.get("has_booking_requested")),
                _f("Notes",            fields.get("has_notes")),
                "\n=== Mobile Massage Service ===\n",
                _f("Interested",       fields.get("mms_interested")),
                _f("Follow-Up Date",   fields.get("mms_follow_up_date")),
                _f("Booking Requested",fields.get("mms_booking_requested")),
                _f("Notes",            fields.get("mms_notes")),
                "\n",
                _f("Consultations Gifted", fields.get("consultations_gifted")),
                _f("Massages Gifted",       fields.get("massages_gifted")),
            ]
        elif form_type == "External Event":
            lines += [
                _f("Event Name",      fields.get("event_name")),
                _f("Event Type",      fields.get("event_type")),
                _f("Organizer",       fields.get("event_organizer")),
                _f("Organizer Phone", fields.get("organizer_phone")),
                _f("Cost",            fields.get("event_cost")),
                _f("Date & Time",     fields.get("event_datetime")),
                _f("Duration",        fields.get("event_duration")),
                _f("Venue Address",   fields.get("venue_address")),
                _f("Indoor/Outdoor",  fields.get("indoor_outdoor")),
                _f("Electricity",     fields.get("has_electricity")),
                _f("Staff Type",      fields.get("staff_collar")),
                _f("Healthcare Ins.", fields.get("healthcare_insurance")),
                _f("Industry",        fields.get("company_industry")),
                _f("Event Flyer",     flyer_url),
                "",
                "--- Interaction ---",
                _f("Type",            fields.get("interaction_type")),
                _f("Outcome",         fields.get("interaction_outcome")),
                _f("Contact Person",  fields.get("interaction_person")),
                _f("Follow-Up",       fields.get("interaction_follow_up")),
                _f("What Happened",   fields.get("interaction_summary")),
            ]
        elif form_type == "Mobile Massage Service":
            lines += [
                _f("Company",          fields.get("company_name")),
                _f("Contact",          fields.get("point_of_contact_name")),
                _f("Phone",            fields.get("contact_phone")),
                _f("Email",            fields.get("contact_email")),
                _f("Venue Address",    fields.get("venue_address")),
                _f("Indoor/Outdoor",   fields.get("indoor_outdoor")),
                _f("Electricity",      fields.get("has_electricity")),
                _f("Audience Type",    fields.get("audience_type")),
                _f("Anticipated",      fields.get("anticipated_count")),
                _f("Industry",         fields.get("company_industry")),
                _f("Products/Services",fields.get("products_services")),
                _f("Massage Duration", fields.get("massage_duration")),
                _f("Massage Type",     fields.get("massage_type")),
                _f("Requested Date",   fields.get("requested_datetime")),
            ]
        elif form_type == "Lunch and Learn":
            lines += [
                _f("Company",           fields.get("company_name")),
                _f("Contact",           fields.get("point_of_contact_name")),
                _f("Phone",             fields.get("contact_phone")),
                _f("Email",             fields.get("contact_email")),
                _f("Venue Address",     fields.get("venue_address")),
                _f("Indoor/Outdoor",    fields.get("indoor_outdoor")),
                _f("Electricity",       fields.get("has_electricity")),
                _f("Conference Room",   fields.get("has_conference_room")),
                _f("Food Surfaces",     fields.get("has_food_surfaces")),
                _f("Projector/Screen",  fields.get("has_projector")),
                _f("Anticipated",       fields.get("anticipated_count")),
                _f("Dietary Restrict.", fields.get("dietary_restrictions")),
                _f("Staff Type",        fields.get("staff_collar")),
                _f("Healthcare Ins.",   fields.get("healthcare_insurance")),
                _f("Industry",          fields.get("company_industry")),
                _f("Products/Services", fields.get("products_services")),
                _f("Requested Date",    fields.get("requested_datetime")),
            ]
        elif form_type == "Health Assessment Screening":
            lines += [
                _f("Company",           fields.get("company_name")),
                _f("Contact",           fields.get("point_of_contact_name")),
                _f("Phone",             fields.get("contact_phone")),
                _f("Email",             fields.get("contact_email")),
                _f("Venue Address",     fields.get("venue_address")),
                _f("Indoor/Outdoor",    fields.get("indoor_outdoor")),
                _f("Electricity",       fields.get("has_electricity")),
                _f("Anticipated",       fields.get("anticipated_count")),
                _f("Staff Type",        fields.get("staff_collar")),
                _f("Healthcare Ins.",   fields.get("healthcare_insurance")),
                _f("Industry",          fields.get("company_industry")),
                _f("Products/Services", fields.get("products_services")),
                _f("Requested Date",    fields.get("requested_datetime")),
            ]
        elif form_type == "Interaction Only":
            lines += [
                _f("Type",           fields.get("interaction_type")),
                _f("Outcome",        fields.get("interaction_outcome")),
                _f("Contact Person", fields.get("interaction_person")),
                _f("Follow-Up",      fields.get("interaction_follow_up")),
                _f("What Happened",  fields.get("interaction_summary")),
            ]
        else:
            for k, v in fields.items():
                lines.append(_f(k, v))

        summary = "".join(l for l in lines if l is not None).strip()

        # For Interaction Only the structured fields (Type / Outcome / Contact
        # Person / Follow-Up Date) are already captured on dedicated columns.
        # Storing the Form/Submitted-by/Type/Outcome/... blob in Summary too
        # turns Visit History rendering into noise. Use just the user's
        # free-text note.
        if form_type == "Interaction Only":
            user_note = (fields.get("interaction_summary") or "").strip()
            if user_note:
                summary = user_note

        # ── Derive date, contact, follow-up, outcome ───────────────────────
        if form_type == "Business Outreach Log":
            activity_date  = today
            contact_person = fields.get("point_of_contact_name", "")
            follow_up      = next(
                (d for d in [
                    fields.get("ll_follow_up_date"),
                    fields.get("has_follow_up_date"),
                    fields.get("mms_follow_up_date"),
                ] if d),
                None,
            )
            outcome = "Visit Logged"
        elif form_type == "External Event":
            raw_dt         = fields.get("event_datetime") or ""
            activity_date  = raw_dt[:10] if raw_dt else today
            contact_person = fields.get("interaction_person") or fields.get("event_organizer", "")
            follow_up      = fields.get("interaction_follow_up") or None
            outcome        = fields.get("interaction_outcome") or "Event Logged"
        elif form_type == "Interaction Only":
            activity_date  = today
            contact_person = fields.get("interaction_person", "")
            follow_up      = fields.get("interaction_follow_up") or None
            outcome        = fields.get("interaction_outcome") or "Interaction Logged"
        else:
            raw_dt         = fields.get("requested_datetime") or ""
            activity_date  = raw_dt[:10] if raw_dt else today
            contact_person = fields.get("point_of_contact_name", "")
            follow_up      = None
            outcome        = "Booking Requested"

        # ── Create T_GOR_ACTS record ───────────────────────────────────────
        VALID_FORM_TYPES = {
            "Business Outreach Log", "External Event",
            "Mobile Massage Service", "Lunch and Learn",
            "Health Assessment Screening", "Interaction Only",
        }
        VALID_INTERACTION_TYPES = {"Call", "Email", "Drop-In", "Meeting", "Mail", "Other"}
        VALID_OUTCOMES = {"No Answer", "Left Message", "Spoke With",
                           "Scheduled Meeting", "Declined", "Follow-Up Needed"}

        # Interaction type: user choice when the form collects one; per-form defaults otherwise.
        interaction_type = (fields.get("interaction_type") or "").strip()
        if interaction_type not in VALID_INTERACTION_TYPES:
            interaction_type = {
                "Business Outreach Log":        "Drop-In",
                "Mobile Massage Service":       "Meeting",
                "Lunch and Learn":              "Meeting",
                "Health Assessment Screening":  "Meeting",
            }.get(form_type, "Other")

        # For External Event, prepend interaction notes to summary
        if form_type == "External Event":
            int_summary = fields.get("interaction_summary", "")
            if int_summary:
                summary = f"[{interaction_type}] {int_summary}\n\n{summary}"

        # Baserow single_select writes take bare strings, not {"value": ...}
        # dicts. The dict form is read-only on responses.
        act_fields: dict = {
            "Type":           interaction_type,
            "Date":           activity_date,
            "Contact Person": contact_person,
            "Summary":        summary,
        }
        if form_type in VALID_FORM_TYPES:
            act_fields["Source Form"] = form_type
        # Outcome: only set if it maps to a valid option; otherwise leave null.
        if outcome in VALID_OUTCOMES:
            act_fields["Outcome"] = outcome
        if venue_id:
            act_fields["Business"]      = [venue_id]
        if follow_up:
            act_fields["Follow-Up Date"] = follow_up
        if form_type == "External Event":
            event_status = (fields.get("event_status") or "Prospective").strip()
            valid_statuses = {"Prospective", "Approved", "Scheduled", "Completed"}
            if event_status in valid_statuses:
                act_fields["Event Status"] = event_status

        ar = await client.post(
            f"{br}/api/database/rows/table/{T_GOR_ACTS}/?user_field_names=true",
            headers=br_headers,
            json=act_fields,
        )

        # Optional venue Contact Status update — only when the form sent a
        # non-empty value AND we resolved a venue. Bare string per memory
        # (Baserow single_select writes don't take dict form).
        new_status = (fields.get("contact_status") or "").strip()
        if new_status and venue_id and new_status in (
            "Not Contacted", "Contacted", "In Discussion", "Active Partner",
        ):
            try:
                await client.patch(
                    f"{br}/api/database/rows/table/{T_GOR_VENUES}/{venue_id}/?user_field_names=true",
                    headers=br_headers,
                    json={"Contact Status": new_status},
                )
            except Exception:
                pass

    if ar.status_code not in (200, 201):
        return JSONResponse({"ok": False, "error": ar.text}, status_code=500)

    activity_id = ar.json().get("id")

    # ── Auto-create T_EVENTS row for event-type forms ────────────────────
    event_id = None
    EVENT_FORM_TYPES = {"External Event", "Mobile Massage Service", "Lunch and Learn", "Health Assessment Screening"}
    if T_EVENTS and form_type in EVENT_FORM_TYPES:
        slug = hashlib.sha256(f"{form_type}-{today}-{secrets.token_urlsafe(8)}".encode()).hexdigest()[:12]
        ev_fields = {
            "Name": fields.get("event_name") or fields.get("company") or f"{form_type} - {today}",
            "Event Type": form_type,
            "Event Date": fields.get("event_date") or today,
            "Form Slug": slug,
            "Created By": user_name or user.get("email", ""),
            "Lead Count": 0,
        }
        if form_type == "External Event":
            ev_status = (fields.get("event_status") or "Prospective").strip()
            if ev_status in {"Prospective", "Approved", "Scheduled", "Completed"}:
                ev_fields["Event Status"] = ev_status
            if fields.get("organizer"):
                ev_fields["Organizer"] = fields["organizer"]
            if fields.get("organizer_phone"):
                ev_fields["Organizer Phone"] = fields["organizer_phone"]
            if fields.get("cost"):
                ev_fields["Cost"] = fields["cost"]
            if fields.get("duration"):
                ev_fields["Duration"] = fields["duration"]
            if flyer_url:
                ev_fields["Flyer URL"] = flyer_url
        else:
            ev_fields["Event Status"] = "Scheduled"
        if fields.get("address") or fields.get("event_address"):
            ev_fields["Venue Address"] = fields.get("address") or fields.get("event_address")
        if fields.get("anticipated_count"):
            try:
                ev_fields["Anticipated Count"] = int(fields["anticipated_count"])
            except (ValueError, TypeError):
                pass
        if fields.get("staff_type"):
            ev_fields["Staff Type"] = fields["staff_type"]
        if fields.get("industry"):
            ev_fields["Industry"] = fields["industry"]
        if fields.get("indoor_outdoor"):
            ev_fields["Indoor Outdoor"] = fields["indoor_outdoor"]
        if venue_id:
            ev_fields["Business"] = [venue_id]
        try:
            async with httpx.AsyncClient(timeout=60) as ev_client:
                er = await ev_client.post(
                    f"{br}/api/database/rows/table/{T_EVENTS}/?user_field_names=true",
                    headers=br_headers,
                    json=ev_fields,
                )
            if er.status_code in (200, 201):
                event_id = er.json().get("id")
            else:
                print(f"[guerilla_log] T_EVENTS create failed ({er.status_code}): {er.text}")
        except Exception as e:
            print(f"[guerilla_log] T_EVENTS create error: {e}")

    return JSONResponse({"ok": True, "activity_id": activity_id, "event_id": event_id})


# ─────────────────────────────────────────────────────────────────────────────
# Massage Box CRUD
# ─────────────────────────────────────────────────────────────────────────────
async def create_box(request: Request, br: str, bt: str, user: dict) -> JSONResponse:
    if not _has_hub_access(user, "guerilla"):
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    body = await request.json()
    venue_id       = body.get("venue_id")
    location       = (body.get("location") or "").strip()
    contact_person = (body.get("contact_person") or "").strip()
    pickup_days    = body.get("pickup_days")
    promo_items    = (body.get("promo_items") or "").strip()
    if not venue_id:
        return JSONResponse({"ok": False, "error": "venue_id required"}, status_code=400)
    today = _date.today().isoformat()
    box_fields = {
        "Business": [int(venue_id)],
        "Status":   "Active",
        "Date Placed": today,
    }
    if location:       box_fields["Location Notes"] = location
    if contact_person: box_fields["Contact Person"] = contact_person
    if pickup_days:    box_fields["Pickup Days"]    = int(pickup_days)
    if promo_items:    box_fields["Promo Items"]    = promo_items
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{br}/api/database/rows/table/{T_GOR_BOXES}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
            json=box_fields,
        )
    if r.status_code not in (200, 201):
        return JSONResponse({"ok": False, "error": r.text}, status_code=500)
    return JSONResponse({"ok": True, "box_id": r.json().get("id")})


async def pickup_box(request: Request, br: str, bt: str, user: dict,
                     box_id: int) -> JSONResponse:
    if not _has_hub_access(user, "guerilla"):
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    async with httpx.AsyncClient(timeout=30) as client:
        await client.patch(
            f"{br}/api/database/rows/table/{T_GOR_BOXES}/{box_id}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
            json={"Status": "Picked Up", "Date Removed": _date.today().isoformat()},
        )
    return JSONResponse({"ok": True})


async def update_box(request: Request, br: str, bt: str, user: dict,
                     box_id: int) -> JSONResponse:
    """General edit: location, contact, pickup_days, promo_items. All optional."""
    if not _has_hub_access(user, "guerilla"):
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    body = await request.json()
    fields: dict = {}
    if "location" in body:
        fields["Location Notes"] = (body.get("location") or "").strip()
    if "contact_person" in body:
        fields["Contact Person"] = (body.get("contact_person") or "").strip()
    if "promo_items" in body:
        fields["Promo Items"] = (body.get("promo_items") or "").strip()
    if "pickup_days" in body and body.get("pickup_days"):
        try:
            pd = int(body["pickup_days"])
            if pd >= 1:
                fields["Pickup Days"] = pd
        except (ValueError, TypeError):
            return JSONResponse({"ok": False, "error": "invalid pickup_days"}, status_code=400)
    if not fields:
        return JSONResponse({"ok": False, "error": "no fields to update"}, status_code=400)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.patch(
            f"{br}/api/database/rows/table/{T_GOR_BOXES}/{box_id}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
            json=fields,
        )
    if r.status_code != 200:
        return JSONResponse({"ok": False, "error": r.text[:300]}, status_code=r.status_code)
    return JSONResponse({"ok": True})


async def update_box_days(request: Request, br: str, bt: str, user: dict,
                          box_id: int) -> JSONResponse:
    if not _has_hub_access(user, "guerilla"):
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    body = await request.json()
    days = body.get("pickup_days")
    if not days or int(days) < 1:
        return JSONResponse({"ok": False, "error": "invalid days"}, status_code=400)
    async with httpx.AsyncClient(timeout=30) as client:
        await client.patch(
            f"{br}/api/database/rows/table/{T_GOR_BOXES}/{box_id}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
            json={"Pickup Days": int(days)},
        )
    return JSONResponse({"ok": True})


# ─────────────────────────────────────────────────────────────────────────────
# Venue update
# ─────────────────────────────────────────────────────────────────────────────
async def update_venue(request: Request, br: str, bt: str, user: dict,
                       venue_id: int) -> JSONResponse:
    """Edit a guerilla venue's Promo Items (and other future fields).

    Phase 2b.3 sync: after writing the legacy venue row, also mirror the
    change to the matching Company row (Legacy Source=guerilla_venue +
    Legacy ID=venue_id) so the unified Companies view stays current."""
    if not _has_hub_access(user, "guerilla"):
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    body = await request.json()
    fields: dict = {}
    if "promo_items" in body:
        fields["Promo Items"] = (body.get("promo_items") or "").strip()
    if not fields:
        return JSONResponse({"ok": False, "error": "no fields to update"}, status_code=400)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.patch(
            f"{br}/api/database/rows/table/{T_GOR_VENUES}/{venue_id}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
            json=fields,
        )
    if r.status_code != 200:
        return JSONResponse({"ok": False, "error": r.text[:300]}, status_code=r.status_code)

    # Mirror to Companies (best-effort; failures don't fail the venue write).
    # Filter by Legacy ID (numeric, safe) then confirm Legacy Source in code —
    # single_select filters via the HTTP API require the option ID, not value.
    if T_COMPANIES:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                lookup = await client.get(
                    f"{br}/api/database/rows/table/{T_COMPANIES}/?user_field_names=true"
                    f"&filter__Legacy+ID__equal={venue_id}&size=5",
                    headers={"Authorization": f"Token {bt}"},
                )
                if lookup.status_code == 200:
                    matched = None
                    for row in lookup.json().get("results", []):
                        src = row.get("Legacy Source")
                        if isinstance(src, dict): src = src.get("value")
                        if src == "guerilla_venue":
                            matched = row; break
                    if matched:
                        await client.patch(
                            f"{br}/api/database/rows/table/{T_COMPANIES}/{matched['id']}/?user_field_names=true",
                            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
                            json=fields,  # Promo Items field name is identical on both sides
                        )
        except Exception:
            pass

    return JSONResponse({"ok": True})

# ─────────────────────────────────────────────────────────────────────────────
# Route endpoints
# ─────────────────────────────────────────────────────────────────────────────
async def _build_route_response(route: dict, cached_rows: CachedRowsFn) -> dict:
    """Shared enrichment: take a T_GOR_ROUTES row and return the
    {route, stops} payload with venue details and pending-box hints.
    Used by both routes_today and route_detail."""
    route_id = route.get("id")
    stops_all = await cached_rows(T_GOR_ROUTE_STOPS)
    stops = [s for s in stops_all if any(
        (isinstance(v, dict) and v.get("id") == route_id) or v == route_id
        for v in (s.get("Route") or [])
    )]
    stops.sort(key=lambda s: s.get("Stop Order") or 999)
    venues = await cached_rows(T_GOR_VENUES)
    venue_map = {v["id"]: v for v in venues}
    boxes = await cached_rows(T_GOR_BOXES)
    today_d = _date.today()
    pending_box_by_venue = {}
    for b in boxes:
        b_status = b.get("Status") or ""
        if isinstance(b_status, dict): b_status = b_status.get("value", "")
        if b_status != "Active":
            continue
        placed = b.get("Date Placed")
        if not placed:
            continue
        try:
            placed_d = _date.fromisoformat(str(placed)[:10])
            age = (today_d - placed_d).days
        except Exception:
            continue
        pickup_days = b.get("Pickup Days")
        try:
            pickup_days = int(pickup_days) if pickup_days else 14
        except Exception:
            pickup_days = 14
        if age < pickup_days:
            continue
        biz = b.get("Business") or []
        v_id = None
        for v in biz:
            if isinstance(v, dict): v_id = v.get("id"); break
            v_id = v; break
        if v_id:
            existing = pending_box_by_venue.get(v_id)
            if not existing or age > existing["age"]:
                pending_box_by_venue[v_id] = {
                    "box_id": b.get("id"), "age": age,
                    "overdue_by": age - pickup_days,
                    "location": b.get("Location Notes") or "",
                }
    stop_list = []
    for s in stops:
        venue_id = None
        for v in (s.get("Venue") or []):
            if isinstance(v, dict): venue_id = v.get("id"); break
            venue_id = v; break
        venue = venue_map.get(venue_id, {}) if venue_id else {}
        status = s.get("Status") or ""
        if isinstance(status, dict): status = status.get("value", "Pending")
        pending_box = pending_box_by_venue.get(venue_id) if venue_id else None
        stop_list.append({
            "stop_id":     s.get("id"),
            "venue_id":    venue_id,
            "name":        venue.get("Name") or "",
            "address":     venue.get("Address") or "",
            "lat":         venue.get("Latitude"),
            "lng":         venue.get("Longitude"),
            "status":      status or "Pending",
            "order":       s.get("Stop Order") or 0,
            "notes":       s.get("Notes") or "",
            "pending_box": pending_box,
        })
    route_status = route.get("Status") or ""
    if isinstance(route_status, dict): route_status = route_status.get("value", "")
    return {
        "route": {"id": route_id,
                  "name": route.get("Name") or route.get("Route Name") or "Route",
                  "status": route_status,
                  "date": (route.get("Date") or "")[:10],
                  "assigned_to": (route.get("Assigned To") or "").strip()},
        "stops": stop_list,
    }


async def routes_today(request: Request, br: str, bt: str, user: dict,
                       cached_rows: CachedRowsFn) -> JSONResponse:
    """Return the caller's active/draft route for today (or most recent fallback)
    with expanded stop info (venue, coords, pending-box hints)."""
    if not T_GOR_ROUTES or not T_GOR_ROUTE_STOPS:
        return JSONResponse({"route": None, "stops": []})
    user_email = (user.get("email") or "").lower()
    today = _date.today().isoformat()
    try:
        routes = await cached_rows(T_GOR_ROUTES)
        route = None
        for row in routes:
            row_date   = (row.get("Date") or "")[:10]
            row_email  = (row.get("Assigned To") or "").strip().lower()
            row_status = row.get("Status") or ""
            if isinstance(row_status, dict): row_status = row_status.get("value", "")
            if row_date == today and row_email == user_email and row_status in ("Active", "Draft"):
                route = row
                break
        if not route:
            candidates = []
            for row in routes:
                row_email  = (row.get("Assigned To") or "").strip().lower()
                row_status = row.get("Status") or ""
                if isinstance(row_status, dict): row_status = row_status.get("value", "")
                if row_email == user_email and row_status in ("Active", "Draft"):
                    candidates.append(row)
            candidates.sort(key=lambda r: r.get("Date") or "", reverse=True)
            if candidates:
                route = candidates[0]
        if not route:
            return JSONResponse({"route": None, "stops": []})
        return JSONResponse(await _build_route_response(route, cached_rows))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def route_detail(request: Request, br: str, bt: str, user: dict,
                       route_id: int, cached_rows: CachedRowsFn) -> JSONResponse:
    """Return a specific route by id with enriched stops. Admin sees any route;
    field reps can only view routes assigned to them."""
    if not T_GOR_ROUTES or not T_GOR_ROUTE_STOPS:
        return JSONResponse({"error": "routes not configured"}, status_code=503)
    user_email = (user.get("email") or "").strip().lower()
    try:
        routes = await cached_rows(T_GOR_ROUTES)
        route = next((r for r in routes if r.get("id") == route_id), None)
        if not route:
            return JSONResponse({"error": "route not found"}, status_code=404)
        assignee = (route.get("Assigned To") or "").strip().lower()
        if not _is_admin(user) and assignee != user_email:
            return JSONResponse({"error": "not your route"}, status_code=403)
        return JSONResponse(await _build_route_response(route, cached_rows))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def update_route_stop(request: Request, br: str, bt: str, user: dict,
                            stop_id: int) -> JSONResponse:
    if not _has_hub_access(user, "guerilla"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    body = await request.json()
    status = body.get("status", "")
    notes  = (body.get("notes") or "").strip()
    lat    = body.get("lat")
    lng    = body.get("lng")
    if status not in ("Pending", "In Progress", "Visited", "Skipped", "Not Reached"):
        return JSONResponse({"error": "invalid status"}, status_code=400)
    now_str = _dt.now().strftime("%Y-%m-%d %H:%M")
    fields = {"Status": status}
    if notes:
        fields["Notes"] = notes
    if status == "In Progress":
        fields["Arrived At"] = now_str
    if status in ("Visited", "Skipped", "Not Reached"):
        fields["Completed At"] = now_str
        fields["Completed By"] = user.get("email", "")
        fields["Departed At"]  = now_str
        # Compute Duration Mins from existing Arrived At (round-trip GET so the
        # client doesn't have to track Arrive timestamp through a refresh).
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                gr = await client.get(
                    f"{br}/api/database/rows/table/{T_GOR_ROUTE_STOPS}/{stop_id}/?user_field_names=true",
                    headers={"Authorization": f"Token {bt}"},
                )
            if gr.is_success:
                arrived = (gr.json().get("Arrived At") or "").strip()
                if arrived:
                    a = _dt.strptime(arrived, "%Y-%m-%d %H:%M")
                    delta = _dt.now() - a
                    fields["Duration Mins"] = max(0, int(round(delta.total_seconds() / 60)))
        except Exception:
            pass
    if status == "Visited" and isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        fields["Check-In Lat"] = lat
        fields["Check-In Lng"] = lng
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(
            f"{br}/api/database/rows/table/{T_GOR_ROUTE_STOPS}/{stop_id}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
            json=fields,
        )
    if resp.status_code not in (200, 201):
        return JSONResponse(
            {"ok": False, "error": resp.text[:300], "fields": fields},
            status_code=resp.status_code,
        )
    return JSONResponse({"ok": True})


async def gorilla_routes_create(request: Request, br: str, bt: str,
                                user: dict) -> JSONResponse:
    if not _is_admin(user):
        return JSONResponse({"error": "admin only"}, status_code=403)
    if not T_GOR_ROUTES or not T_GOR_ROUTE_STOPS:
        return JSONResponse({"error": "routes not configured"}, status_code=503)
    body = await request.json()
    name     = (body.get("name") or "").strip()
    date_str = (body.get("date") or "").strip()
    assignee = (body.get("assigned_to") or "").strip()
    status   = body.get("status") or "Draft"
    stops    = body.get("stops") or []
    if not name:
        return JSONResponse({"error": "name required"}, status_code=400)
    if status not in ("Draft", "Active", "Completed"):
        status = "Draft"
    async with httpx.AsyncClient() as client:
        route_payload = {"Name": name, "Assigned To": assignee, "Status": status}
        if date_str:
            route_payload["Date"] = date_str
        r = await client.post(
            f"{br}/api/database/rows/table/{T_GOR_ROUTES}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
            json=route_payload,
        )
        if r.status_code not in (200, 201):
            return JSONResponse({"error": r.text}, status_code=r.status_code)
        route_id = r.json()["id"]
        for i, stop in enumerate(stops):
            venue_id = stop.get("venue_id")
            if not venue_id:
                continue
            stop_payload = {
                "Route":      [route_id],
                "Stop Order": i + 1,
                "Status":     "Pending",
                "Name":       stop.get("name") or "",
            }
            try:
                stop_payload["Venue"] = [int(venue_id)]
            except (ValueError, TypeError):
                pass
            await client.post(
                f"{br}/api/database/rows/table/{T_GOR_ROUTE_STOPS}/?user_field_names=true",
                headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
                json=stop_payload,
            )
    return JSONResponse({"ok": True, "route_id": route_id})


async def gorilla_route_append_stop(request: Request, br: str, bt: str, user: dict,
                                    route_id: int,
                                    cached_rows: CachedRowsFn) -> JSONResponse:
    """Append a single stop to an existing route.

    Field-rep allowed (not admin-gated) as long as the route is assigned to them.
    Used by the home-page 'Boxes Due' panel to queue a box pickup on today's route.
    """
    if not _has_hub_access(user, "guerilla"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if not T_GOR_ROUTES or not T_GOR_ROUTE_STOPS:
        return JSONResponse({"error": "routes not configured"}, status_code=503)
    body = await request.json()
    try:
        venue_id = int(body.get("venue_id"))
    except (ValueError, TypeError):
        return JSONResponse({"error": "venue_id required"}, status_code=400)
    stop_name = (body.get("name") or "").strip()

    async with httpx.AsyncClient(timeout=30) as client:
        rr = await client.get(
            f"{br}/api/database/rows/table/{T_GOR_ROUTES}/{route_id}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}"},
        )
        if rr.status_code != 200:
            return JSONResponse({"error": "route not found"}, status_code=404)
        route = rr.json()
        assignee = (route.get("Assigned To") or "").strip().lower()
        user_email = (user.get("email") or "").strip().lower()
        if not _is_admin(user) and assignee != user_email:
            return JSONResponse({"error": "not your route"}, status_code=403)

        all_stops = await cached_rows(T_GOR_ROUTE_STOPS)
        existing = [s for s in all_stops
                    if any(x.get("id") == route_id for x in (s.get("Route") or []))]
        next_order = max((int(s.get("Stop Order") or 0) for s in existing), default=0) + 1

        payload = {
            "Route":      [route_id],
            "Venue":      [venue_id],
            "Stop Order": next_order,
            "Status":     "Pending",
            "Name":       stop_name,
        }
        sr = await client.post(
            f"{br}/api/database/rows/table/{T_GOR_ROUTE_STOPS}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
            json=payload,
        )
    if sr.status_code in (200, 201):
        return JSONResponse({"ok": True, "stop_id": sr.json().get("id"), "stop_order": next_order})
    return JSONResponse({"error": sr.text}, status_code=sr.status_code)


async def gorilla_route_status(request: Request, br: str, bt: str, user: dict,
                               route_id: int) -> JSONResponse:
    if not _is_admin(user):
        return JSONResponse({"error": "admin only"}, status_code=403)
    if not T_GOR_ROUTES:
        return JSONResponse({"error": "routes not configured"}, status_code=503)
    body = await request.json()
    new_status = body.get("status", "")
    if new_status not in ("Draft", "Active", "Completed"):
        return JSONResponse({"error": "invalid status"}, status_code=400)
    async with httpx.AsyncClient() as client:
        r = await client.patch(
            f"{br}/api/database/rows/table/{T_GOR_ROUTES}/{route_id}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
            json={"Status": new_status},
        )
    if r.status_code in (200, 201):
        return JSONResponse({"ok": True})
    return JSONResponse({"error": r.text}, status_code=r.status_code)


async def gorilla_route_update(request: Request, br: str, bt: str, user: dict,
                               route_id: int,
                               cached_rows: CachedRowsFn) -> JSONResponse:
    """Admin: update route metadata and optionally replace its stops."""
    if not _is_admin(user):
        return JSONResponse({"error": "admin only"}, status_code=403)
    if not T_GOR_ROUTES or not T_GOR_ROUTE_STOPS:
        return JSONResponse({"error": "routes not configured"}, status_code=503)
    body = await request.json()
    route_patch = {}
    if "name" in body:
        route_patch["Name"] = (body["name"] or "").strip()
    if "date" in body:
        route_patch["Date"] = (body["date"] or "").strip() or None
    if "assigned_to" in body:
        route_patch["Assigned To"] = (body["assigned_to"] or "").strip()
    if "status" in body:
        s = body["status"]
        if s in ("Draft", "Active", "Completed"):
            route_patch["Status"] = s
    async with httpx.AsyncClient(timeout=30) as client:
        if route_patch:
            r = await client.patch(
                f"{br}/api/database/rows/table/{T_GOR_ROUTES}/{route_id}/?user_field_names=true",
                headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
                json=route_patch,
            )
            if r.status_code not in (200, 201):
                return JSONResponse({"error": r.text}, status_code=r.status_code)
        if "stops" in body:
            new_stops = body["stops"] or []
            all_stops = await cached_rows(T_GOR_ROUTE_STOPS)
            old_stops = [s for s in all_stops
                         if any(x.get("id") == route_id for x in (s.get("Route") or []))]
            for s in old_stops:
                await client.delete(
                    f"{br}/api/database/rows/table/{T_GOR_ROUTE_STOPS}/{s['id']}/",
                    headers={"Authorization": f"Token {bt}"},
                )
            for i, stop in enumerate(new_stops):
                venue_id = stop.get("venue_id")
                if not venue_id:
                    continue
                stop_payload = {
                    "Route":      [route_id],
                    "Stop Order": i + 1,
                    "Status":     "Pending",
                    "Name":       stop.get("name") or "",
                }
                try:
                    stop_payload["Venue"] = [int(venue_id)]
                except (ValueError, TypeError):
                    pass
                await client.post(
                    f"{br}/api/database/rows/table/{T_GOR_ROUTE_STOPS}/?user_field_names=true",
                    headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
                    json=stop_payload,
                )
    return JSONResponse({"ok": True})


async def gorilla_route_delete(request: Request, br: str, bt: str, user: dict,
                               route_id: int,
                               cached_rows: CachedRowsFn) -> JSONResponse:
    """Admin: delete route + all its stops."""
    if not _is_admin(user):
        return JSONResponse({"error": "admin only"}, status_code=403)
    if not T_GOR_ROUTES or not T_GOR_ROUTE_STOPS:
        return JSONResponse({"error": "routes not configured"}, status_code=503)
    all_stops = await cached_rows(T_GOR_ROUTE_STOPS)
    route_stops = [s for s in all_stops
                   if any(x.get("id") == route_id for x in (s.get("Route") or []))]
    async with httpx.AsyncClient(timeout=30) as client:
        for s in route_stops:
            await client.delete(
                f"{br}/api/database/rows/table/{T_GOR_ROUTE_STOPS}/{s['id']}/",
                headers={"Authorization": f"Token {bt}"},
            )
        r = await client.delete(
            f"{br}/api/database/rows/table/{T_GOR_ROUTES}/{route_id}/",
            headers={"Authorization": f"Token {bt}"},
        )
    if r.status_code in (200, 204):
        return JSONResponse({"ok": True})
    return JSONResponse({"error": r.text}, status_code=r.status_code)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/leads/capture — field-rep lead capture form
# ─────────────────────────────────────────────────────────────────────────────
async def capture_lead(
    request: Request, br: str, bt: str, user: dict,
    cached_rows: CachedRowsFn,
    on_created: Callable[[dict, dict], Awaitable[None]] | None = None,
    invalidate: Callable[..., Awaitable[None]] | None = None,
) -> JSONResponse:
    """Create a T_LEADS row from the field-rep Capture Lead form.

    Reads: name, phone, email (optional), service, event_id (optional), notes.
    Source = event name if event_id is provided, else "Field Capture".
    Notes are prefixed with the capturing user's email.
    Linked events get their "Lead Count" incremented.

    `on_created`, if supplied, is awaited after a successful insert with
    `(created_row, submitted_fields)` — the hub wrapper uses this to fire the
    `new_lead` automation trigger. Field_rep passes None (no trigger firing).

    `invalidate`, if supplied, is awaited with `(T_LEADS, T_EVENTS)` so the
    caller's cache layer can drop stale entries.
    """
    if not T_LEADS:
        return JSONResponse({"ok": False, "error": "not configured"}, status_code=503)
    body = await request.json()
    name = (body.get("name") or "").strip()
    phone = (body.get("phone") or "").strip()
    email = (body.get("email") or "").strip()
    service = (body.get("service") or "").strip()
    event_id = body.get("event_id")
    notes = (body.get("notes") or "").strip()
    if not name or not phone:
        return JSONResponse({"ok": False, "error": "name and phone required"}, status_code=400)

    # Resolve the linked event (if any) for Source + lead-count bump
    event = None
    source = "Field Capture"
    if event_id and T_EVENTS:
        events = await cached_rows(T_EVENTS)
        event = next((e for e in events if e.get("id") == int(event_id)), None)
        if event:
            source = event.get("Name") or "Event"

    # Optional: link to a referring Company — if set, we'll prefer the
    # company's Name as Source and auto-mark the company "Contacted" + log
    # an activity once the lead is created (Feature #6).
    referred_company_id = body.get("company_id")
    referred_company_row = None
    if referred_company_id:
        try:
            cid = int(referred_company_id)
            companies = await cached_rows(T_COMPANIES)
            referred_company_row = next((c for c in companies if c.get("id") == cid), None)
            if referred_company_row and not event:  # event name takes priority
                source = referred_company_row.get("Name") or source
        except Exception:
            referred_company_row = None

    fields: dict = {
        "Name": name,
        "Phone": phone,
        "Status": "New",
        "Source": source,
        "Reason": service,
    }
    if email:
        fields["Email"] = email
    if notes:
        fields["Notes"] = f"[{user.get('email','')}] {notes}"
    if event_id and T_EVENTS:
        fields["Event"] = [int(event_id)]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{br}/api/database/rows/table/{T_LEADS}/?user_field_names=true",
            headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
            json=fields,
        )
        if event_id and T_EVENTS and event:
            cur_count = event.get("Lead Count") or 0
            await client.patch(
                f"{br}/api/database/rows/table/{T_EVENTS}/{event['id']}/?user_field_names=true",
                headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
                json={"Lead Count": cur_count + 1},
            )

    # Feature #6: mark the referring Company "Contacted" + log an activity
    # on its CRM feed so outreach stays in sync with what reps are doing.
    if referred_company_row and r.status_code in (200, 201):
        from datetime import datetime as _dt_inner, timezone as _tz_inner
        iso_now = _dt_inner.now(_tz_inner.utc).isoformat()
        today = iso_now[:10]
        current_status = referred_company_row.get("Contact Status")
        if isinstance(current_status, dict):
            current_status = current_status.get("value", "")
        patch = {"Updated": iso_now}
        # Promote from Not Contacted / blank → Contacted. Never downgrade.
        if (current_status or "").strip() in ("", "Not Contacted"):
            patch["Contact Status"] = "Contacted"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                await client.patch(
                    f"{br}/api/database/rows/table/{T_COMPANIES}/{referred_company_row['id']}/?user_field_names=true",
                    headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
                    json=patch,
                )
                # Log activity on the company's CRM feed
                activity_payload = {
                    "Summary": f"Lead captured in the field: {name} ({phone}). Reason: {service or '(none)'}",
                    "Kind":    "user_activity",
                    "Type":    "Lead",
                    "Date":    today,
                    "Author":  user.get("email", ""),
                    "Created": iso_now,
                    "Company": [referred_company_row["id"]],
                }
                clean_act = {k: v for k, v in activity_payload.items() if v not in (None, "")}
                await client.post(
                    f"{br}/api/database/rows/table/{T_ACTIVITIES}/?user_field_names=true",
                    headers={"Authorization": f"Token {bt}", "Content-Type": "application/json"},
                    json=clean_act,
                )
        except Exception:
            pass
        if invalidate is not None:
            try: await invalidate(T_COMPANIES, T_ACTIVITIES)
            except Exception: pass

    if invalidate is not None:
        try: await invalidate(T_LEADS, T_EVENTS)
        except Exception: pass

    if r.status_code in (200, 201):
        created = r.json()
        if on_created is not None:
            try: await on_created(created, fields)
            except Exception: pass
        return JSONResponse({"ok": True, "id": created.get("id")})
    return JSONResponse({"ok": False, "error": r.text[:200]}, status_code=500)
