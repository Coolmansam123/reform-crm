"""
Gmail sender — standalone helpers for refreshing an access token and
sending an email via the Gmail API. Both sequence automation and
per-user action endpoints use these helpers so there's one shared code
path and one place to fix bugs.
"""
import base64
import email as _emaillib

import httpx


async def refresh_access_token(refresh_token: str,
                                client_id: str,
                                client_secret: str) -> str:
    """Exchange a long-lived refresh_token for a short-lived access_token."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post("https://oauth2.googleapis.com/token", data={
            "client_id":     client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type":    "refresh_token",
        })
    if r.status_code != 200:
        return ""
    return r.json().get("access_token", "")


async def send_email(access_token: str,
                      to_email: str,
                      from_email: str,
                      subject: str,
                      body: str,
                      cc_email: str = "",
                      attachment: tuple = None) -> dict:
    """Send a plain-text email, optionally with cc and one binary attachment.

    attachment: (filename: str, data: bytes). MIME is inferred from the
    filename extension (.pdf → application/pdf, else application/octet-stream).

    Returns: {"ok": True, "id": "..."} on success, or
             {"ok": False, "status": int, "error": ...} on failure.
    """
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
    except Exception: detail = {"raw": r.text[:300]}
    return {"ok": False, "status": r.status_code, "error": detail}
