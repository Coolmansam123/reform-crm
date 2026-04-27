"""
Push notifications — Phase 3.

Subscribe → POST /api/push/subscribe records {endpoint, keys{p256dh,auth}} on
T_PUSH_SUBSCRIPTIONS (827) keyed by Email. Send → `send_push_to_email` looks
up active subs and dispatches via pywebpush; on 410 Gone it flips Active=false
so we don't keep retrying dead subs.

Backend-agnostic. Wrappers in modal_outreach_hub.py / field_rep/routes/api.py
register the endpoints; this module never reads os.environ directly.
"""
import json
from datetime import datetime as _dt

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

from .constants import T_PUSH_SUBSCRIPTIONS


def _now() -> str:
    return _dt.utcnow().strftime("%Y-%m-%d %H:%M")


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/push/vapid-public-key — client uses this to subscribe
# ─────────────────────────────────────────────────────────────────────────────
def vapid_public_key(vapid_public_key_b64url: str) -> JSONResponse:
    if not vapid_public_key_b64url:
        return JSONResponse({"error": "push not configured"}, status_code=503)
    return JSONResponse({"key": vapid_public_key_b64url})


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/push/subscribe — record a browser PushSubscription
# Body: {endpoint, keys: {p256dh, auth}}
# ─────────────────────────────────────────────────────────────────────────────
async def subscribe(request: Request, br: str, bt: str, user: dict) -> JSONResponse:
    email = (user.get("email") or "").strip().lower()
    if not email:
        return JSONResponse({"ok": False, "error": "no email"}, status_code=400)
    body = await request.json()
    endpoint = (body.get("endpoint") or "").strip()
    keys = body.get("keys") or {}
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        return JSONResponse({"ok": False, "error": "endpoint + keys required"}, status_code=400)
    headers = {"Authorization": f"Token {bt}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15) as client:
        # Replace any existing row for this (email, endpoint) so we don't
        # accumulate stale subs.
        sr = await client.get(
            f"{br}/api/database/rows/table/{T_PUSH_SUBSCRIPTIONS}/?user_field_names=true&size=200",
            headers={"Authorization": f"Token {bt}"},
        )
        existing_id = None
        if sr.status_code == 200:
            for row in sr.json().get("results", []):
                if (row.get("Email") or "").lower().strip() == email \
                   and (row.get("Endpoint") or "").strip() == endpoint:
                    existing_id = row["id"]
                    break
        payload = {
            "Email":     email,
            "Endpoint":  endpoint,
            "Keys":      json.dumps(keys),
            "Created":   _now() if existing_id is None else None,
            "Last Used": "",
            "Active":    True,
        }
        clean = {k: v for k, v in payload.items() if v is not None}
        if existing_id is not None:
            r = await client.patch(
                f"{br}/api/database/rows/table/{T_PUSH_SUBSCRIPTIONS}/{existing_id}/?user_field_names=true",
                headers=headers, json=clean,
            )
        else:
            r = await client.post(
                f"{br}/api/database/rows/table/{T_PUSH_SUBSCRIPTIONS}/?user_field_names=true",
                headers=headers, json=clean,
            )
    if r.status_code not in (200, 201):
        return JSONResponse({"ok": False, "error": r.text[:300]}, status_code=r.status_code)
    return JSONResponse({"ok": True, "id": r.json().get("id")})


# ─────────────────────────────────────────────────────────────────────────────
# Internal: send a push to a specific email (used by triggers + cron)
# ─────────────────────────────────────────────────────────────────────────────
async def send_push_to_email(
    br: str, bt: str, email: str, title: str, body_text: str,
    *,
    url: str = "/",
    vapid_private_key_b64url: str = "",
    vapid_public_key_b64url: str = "",
    vapid_subject: str = "",
) -> dict:
    """Returns {sent: int, failed: int, deactivated: int}."""
    if not (vapid_private_key_b64url and vapid_public_key_b64url and vapid_subject):
        return {"sent": 0, "failed": 0, "deactivated": 0, "error": "vapid not configured"}
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return {"sent": 0, "failed": 0, "deactivated": 0, "error": "pywebpush not installed"}
    email = (email or "").strip().lower()
    if not email:
        return {"sent": 0, "failed": 0, "deactivated": 0}
    headers = {"Authorization": f"Token {bt}", "Content-Type": "application/json"}
    sent = 0; failed = 0; deactivated = 0
    async with httpx.AsyncClient(timeout=20) as client:
        sr = await client.get(
            f"{br}/api/database/rows/table/{T_PUSH_SUBSCRIPTIONS}/?user_field_names=true&size=200",
            headers={"Authorization": f"Token {bt}"},
        )
        if sr.status_code != 200:
            return {"sent": 0, "failed": 0, "deactivated": 0, "error": "fetch subs failed"}
        rows = [
            r for r in sr.json().get("results", [])
            if (r.get("Email") or "").lower().strip() == email and r.get("Active")
        ]
        payload = json.dumps({"title": title, "body": body_text, "url": url})
        for row in rows:
            try:
                keys = json.loads(row.get("Keys") or "{}")
                webpush(
                    subscription_info={"endpoint": row.get("Endpoint") or "", "keys": keys},
                    data=payload,
                    vapid_private_key=vapid_private_key_b64url,
                    vapid_claims={"sub": vapid_subject},
                )
                sent += 1
                # Mark Last Used (fire-and-forget; if this fails it's not critical)
                try:
                    await client.patch(
                        f"{br}/api/database/rows/table/{T_PUSH_SUBSCRIPTIONS}/{row['id']}/?user_field_names=true",
                        headers=headers, json={"Last Used": _now()},
                    )
                except Exception:
                    pass
            except WebPushException as e:
                code = getattr(e.response, "status_code", 0)
                if code in (404, 410):
                    deactivated += 1
                    try:
                        await client.patch(
                            f"{br}/api/database/rows/table/{T_PUSH_SUBSCRIPTIONS}/{row['id']}/?user_field_names=true",
                            headers=headers, json={"Active": False},
                        )
                    except Exception:
                        pass
                else:
                    failed += 1
            except Exception:
                failed += 1
    return {"sent": sent, "failed": failed, "deactivated": deactivated}


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/push/test — fire a self-test push to the caller
# ─────────────────────────────────────────────────────────────────────────────
async def test_push(
    request: Request, br: str, bt: str, user: dict,
    *,
    vapid_private_key_b64url: str,
    vapid_public_key_b64url: str,
    vapid_subject: str,
) -> JSONResponse:
    email = (user.get("email") or "").strip().lower()
    if not email:
        return JSONResponse({"ok": False, "error": "no email"}, status_code=400)
    result = await send_push_to_email(
        br, bt, email,
        title="Reform — test push",
        body_text="If you see this, push notifications are working.",
        url="/",
        vapid_private_key_b64url=vapid_private_key_b64url,
        vapid_public_key_b64url=vapid_public_key_b64url,
        vapid_subject=vapid_subject,
    )
    return JSONResponse({"ok": True, **result})
