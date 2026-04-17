"""
Modal Worker: Social Media Auto-Poster
Posts approved content to Instagram (Feed + Reels), Facebook Page, and YouTube (Phase 2).

ARCHITECTURE (scheduled queue flow):
1. Staff approves content in ClickUp → n8n moves file to Drive "3. Ready for Scheduling"
2. n8n calls /notify_ready_to_post → Google Chat notification with ClickUp task link
3. Daniel/Ian does final review in ClickUp → sets status to "Scheduled"
4. n8n calls /move_to_scheduled → metadata saved to Bunny Scheduled/, Drive file moved
5. Hourly cron checks Bunny Scheduled/ → reads Google Sheets posting schedule per category
   → posts to Instagram + Facebook when schedule matches
   → after post: moves Drive file to Completed, archives meta on Bunny, updates ClickUp

Directive: directives/social_media_auto_post.md
"""

import modal
import requests
import uuid
import os
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Optional

# --- Modal App ---
app = modal.App("social-poster")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "requests",
        "fastapi",
        "google-auth",
        "google-api-python-client",
        "tzdata",
    )
)

# Meta Graph API version
META_API_VERSION = "v22.0"
META_API_BASE = f"https://graph.facebook.com/{META_API_VERSION}"

# Google Chat Space (Social Media Poster — Daniel + Ian only)
GOOGLE_CHAT_SPACE = "spaces/AAQAgfLjkSY"

# Bunny CDN storage base (LA region)
BUNNY_STORAGE_BASE = "https://la.storage.bunnycdn.com"


def get_pacific():
    """Return Pacific timezone. Lazy to avoid tzdata import error on Windows."""
    return ZoneInfo("America/Los_Angeles")


# ============================================================
# Utility functions (reused patterns from existing workers)
# ============================================================

def send_n8n_event(event_name: str, data: dict = None):
    """Send event to n8n webhook (pattern from modal_story_processor.py)."""
    payload = {
        "event": event_name,
        "job_id": str(uuid.uuid4()),
        "data": data if data is not None else {},
    }

    webhook_token = os.getenv("N8N_WEBHOOK_TOKEN")
    webhook_url = os.getenv("N8N_WEBHOOK_URL")

    headers = {
        "Content-Type": "application/json",
        "x-modal-token": webhook_token,
    }

    try:
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        print(f"[OK] Event sent: {event_name}")
    except Exception as e:
        print(f"[ERROR] Failed to send event {event_name}: {e}")


def send_callback(callback_url: str, data: Dict[str, Any]):
    """Send callback with 3 retries (pattern from modal_story_processor.py)."""
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(callback_url, json=data, timeout=30)
            response.raise_for_status()
            print(f"[OK] Callback sent to {callback_url} (attempt {attempt})")
            return True
        except Exception as e:
            print(f"[ERROR] Callback failed (attempt {attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                time.sleep(5)
            else:
                print(f"[FATAL] Callback failed after {max_attempts} attempts")
                return False


def get_chat_service(service_account_json: str):
    """Build Google Chat API service (pattern from modal_clickup_reminder.py)."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_data = json.loads(service_account_json)
    credentials = service_account.Credentials.from_service_account_info(
        creds_data,
        scopes=["https://www.googleapis.com/auth/chat.bot"],
    )
    return build("chat", "v1", credentials=credentials)


def send_chat_notification(message: str):
    """Send a notification to Google Chat space."""
    sa_json = os.environ.get("GOOGLE_CHAT_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        print("[WARN] No GOOGLE_CHAT_SERVICE_ACCOUNT_JSON, skipping Chat notification")
        return

    try:
        service = get_chat_service(sa_json)
        service.spaces().messages().create(
            parent=GOOGLE_CHAT_SPACE,
            body={"text": message},
        ).execute()
        print("[OK] Google Chat notification sent")
    except Exception as e:
        print(f"[ERROR] Google Chat notification failed: {e}")


# ============================================================
# Instagram posting (Meta Graph API)
# ============================================================

def verify_instagram_auth() -> Dict[str, Any]:
    """Verify Instagram API credentials are valid by fetching account info."""
    ig_user_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
    access_token = os.getenv("META_PAGE_TOKEN")

    resp = requests.get(
        f"{META_API_BASE}/{ig_user_id}",
        params={"fields": "id,username,name,media_count", "access_token": access_token},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def post_to_instagram(media_url: str, caption: str, content_type: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Post to Instagram via Meta Graph API.

    Two-step process:
    1. Create media container (POST /{ig-user-id}/media)
    2. Poll until container is FINISHED
    3. Publish (POST /{ig-user-id}/media_publish) — skipped in dry_run

    In dry_run mode: creates container + polls status to validate everything,
    but does NOT publish. The container expires after 24h automatically.
    """
    ig_user_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
    access_token = os.getenv("META_PAGE_TOKEN")

    mode_label = "[DRY RUN] " if dry_run else ""
    print(f"[IG] {mode_label}Posting {content_type} to Instagram...")

    # Step 1: Create media container
    container_params = {
        "caption": caption,
        "access_token": access_token,
    }

    if content_type in ("reel", "video"):
        container_params["media_type"] = "REELS"
        container_params["video_url"] = media_url
    elif content_type == "photo":
        container_params["image_url"] = media_url
    else:
        container_params["image_url"] = media_url

    container_url = f"{META_API_BASE}/{ig_user_id}/media"
    resp = requests.post(container_url, data=container_params, timeout=60)
    resp.raise_for_status()
    container_id = resp.json().get("id")
    print(f"[IG] Container created: {container_id}")

    # Step 2: Poll container status until FINISHED
    max_wait = 300 if content_type in ("reel", "video") else 60
    poll_interval = 5
    elapsed = 0

    while elapsed < max_wait:
        status_url = f"{META_API_BASE}/{container_id}"
        status_resp = requests.get(
            status_url,
            params={"fields": "status_code,status", "access_token": access_token},
            timeout=30,
        )
        status_resp.raise_for_status()
        status_data = status_resp.json()
        status_code = status_data.get("status_code")

        if status_code == "FINISHED":
            print(f"[IG] Container ready after {elapsed}s")
            break
        elif status_code == "ERROR":
            error_msg = status_data.get("status", "Unknown error during media processing")
            raise Exception(f"Instagram container error: {error_msg}")

        print(f"[IG] Container status: {status_code}, waiting... ({elapsed}s)")
        time.sleep(poll_interval)
        elapsed += poll_interval
    else:
        raise Exception(f"Instagram container timed out after {max_wait}s (status: {status_code})")

    # Step 3: Publish (skip in dry_run — container expires in 24h)
    if dry_run:
        print(f"[IG] [DRY RUN] Container {container_id} is FINISHED and ready to publish.")
        print(f"[IG] [DRY RUN] Skipping publish. Container will expire in 24h.")
        return {
            "platform": "instagram",
            "post_id": f"dry_run_{container_id}",
            "permalink": None,
            "dry_run": True,
            "container_id": container_id,
            "container_status": "FINISHED",
        }

    publish_url = f"{META_API_BASE}/{ig_user_id}/media_publish"
    publish_resp = requests.post(
        publish_url,
        data={"creation_id": container_id, "access_token": access_token},
        timeout=60,
    )
    publish_resp.raise_for_status()
    post_id = publish_resp.json().get("id")

    # Get permalink
    permalink = None
    try:
        perm_resp = requests.get(
            f"{META_API_BASE}/{post_id}",
            params={"fields": "permalink", "access_token": access_token},
            timeout=30,
        )
        perm_resp.raise_for_status()
        permalink = perm_resp.json().get("permalink")
    except Exception as e:
        print(f"[IG] Could not fetch permalink: {e}")

    print(f"[IG] Published! Post ID: {post_id}, Permalink: {permalink}")
    return {
        "platform": "instagram",
        "post_id": post_id,
        "permalink": permalink,
    }


# ============================================================
# Facebook Page posting (Meta Graph API)
# ============================================================

def verify_facebook_auth() -> Dict[str, Any]:
    """Verify Facebook Page API credentials by fetching page info."""
    page_id = os.getenv("META_PAGE_ID")
    access_token = os.getenv("META_PAGE_TOKEN")

    resp = requests.get(
        f"{META_API_BASE}/{page_id}",
        params={"fields": "id,name,fan_count,link", "access_token": access_token},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def post_to_facebook(media_url: str, caption: str, content_type: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Post to Facebook Page via Graph API.

    - Photos: POST /{page-id}/photos with url + message
    - Videos: POST /{page-id}/videos with file_url + description

    In dry_run mode: uses published=false to create an unpublished draft
    that won't appear on the page. Drafts can be deleted from Page settings.
    """
    page_id = os.getenv("META_PAGE_ID")
    access_token = os.getenv("META_PAGE_TOKEN")

    mode_label = "[DRY RUN] " if dry_run else ""
    print(f"[FB] {mode_label}Posting {content_type} to Facebook Page...")

    if content_type in ("video", "reel"):
        post_url = f"{META_API_BASE}/{page_id}/videos"
        params = {
            "file_url": media_url,
            "description": caption,
            "access_token": access_token,
        }
        if dry_run:
            params["published"] = "false"
    else:
        post_url = f"{META_API_BASE}/{page_id}/photos"
        params = {
            "url": media_url,
            "message": caption,
            "access_token": access_token,
        }
        if dry_run:
            params["published"] = "false"

    resp = requests.post(post_url, data=params, timeout=120)
    resp.raise_for_status()
    result = resp.json()

    post_id = result.get("id") or result.get("post_id")

    if dry_run:
        print(f"[FB] [DRY RUN] Unpublished draft created: {post_id}")
        return {
            "platform": "facebook",
            "post_id": f"dry_run_{post_id}",
            "dry_run": True,
            "draft_id": post_id,
        }

    print(f"[FB] Published! Post ID: {post_id}")
    return {
        "platform": "facebook",
        "post_id": post_id,
    }


# ============================================================
# Video download helper (TikTok + YouTube require file upload)
# ============================================================

def download_to_temp(url: str, suffix: str = ".mp4"):
    """
    Download a media file from a URL to /tmp/ and return (path, size).
    Uses streaming to handle large video files efficiently.
    Caller is responsible for os.unlink(path) in a finally block.
    """
    import tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir="/tmp")
    tmp_path = tmp.name
    tmp.close()

    print(f"[DOWNLOAD] Fetching {url} → {tmp_path}")
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    with open(tmp_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8 * 1024 * 1024):  # 8 MB chunks
            f.write(chunk)

    file_size = os.path.getsize(tmp_path)
    print(f"[DOWNLOAD] Done — {file_size:,} bytes")
    return tmp_path, file_size


# ============================================================
# TikTok posting (Content Posting API v2 — Direct Post)
# ============================================================

def refresh_tiktok_token() -> str:
    """
    Refresh TikTok access token using the stored refresh token.
    TikTok access tokens expire every ~24 hours.
    Refresh tokens are valid for 365 days.
    """
    client_key = os.environ.get("TIKTOK_CLIENT_KEY", "")
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "")
    refresh_token = os.environ.get("TIKTOK_REFRESH_TOKEN", "")

    if not all([client_key, client_secret, refresh_token]):
        raise ValueError("TikTok credentials incomplete — set TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN")

    resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        raise Exception(f"TikTok token refresh failed: {data}")

    new_token = data.get("data", {}).get("access_token") or data.get("access_token")
    if not new_token:
        raise Exception(f"TikTok token refresh returned no access_token: {data}")

    print("[TT] Access token refreshed")
    return new_token


def post_to_tiktok(media_url: str, caption: str, content_type: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Post a video to TikTok via Content Posting API v2 — Direct Post mode.

    ⚠️  PRIVACY NOTE: privacy_level is hardcoded to SELF_ONLY (private).
    Unaudited TikTok apps cannot post publicly. After passing TikTok's
    audit process, change "SELF_ONLY" → "PUBLIC_TO_EVERYONE" and redeploy.

    Photos are not supported here (TikTok photo carousels use a different
    endpoint and are out of scope).

    Flow:
    1. Try stored access token; auto-refresh on 401
    2. Query creator info (required before every Direct Post)
    3. Download video from Bunny CDN to /tmp/
    4. Init Direct Post → get upload_url + publish_id
    5. Upload in 10 MB chunks with Content-Range headers
    6. Poll publish status until PUBLISH_COMPLETE (max 5 min)
    """
    if content_type == "photo":
        return {
            "platform": "tiktok",
            "skipped": True,
            "reason": "TikTok photo posting not implemented (carousel API). Videos only.",
        }

    access_token = os.environ.get("TIKTOK_ACCESS_TOKEN", "")
    if not access_token:
        raise ValueError("TIKTOK_ACCESS_TOKEN not set in tiktok-secrets")

    mode_label = "[DRY RUN] " if dry_run else ""
    print(f"[TT] {mode_label}Posting video to TikTok...")
    print("[TT] NOTE: Posts as SELF_ONLY (private) until TikTok audit approved")

    TIKTOK_BASE = "https://open.tiktokapis.com/v2"

    def tt_headers(token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    # Step 1: Query creator info (required before every Direct Post)
    creator_resp = requests.post(
        f"{TIKTOK_BASE}/post/publish/creator_info/query/",
        headers=tt_headers(access_token),
        json={},
        timeout=30,
    )
    if creator_resp.status_code == 401:
        print("[TT] Token expired — refreshing...")
        access_token = refresh_tiktok_token()
        creator_resp = requests.post(
            f"{TIKTOK_BASE}/post/publish/creator_info/query/",
            headers=tt_headers(access_token),
            json={},
            timeout=30,
        )
    creator_resp.raise_for_status()
    creator_data = creator_resp.json().get("data", {})
    print(f"[TT] Creator info: max_duration={creator_data.get('max_video_post_duration_sec')}s, "
          f"privacy_options={creator_data.get('privacy_level_options')}")

    if dry_run:
        print("[TT] [DRY RUN] Creator info verified. Skipping upload.")
        return {"platform": "tiktok", "dry_run": True, "creator_info": creator_data}

    # Step 2: Download video to temp file
    tmp_path, file_size = download_to_temp(media_url, suffix=".mp4")

    try:
        # Step 3: Init Direct Post
        CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB
        total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

        init_resp = requests.post(
            f"{TIKTOK_BASE}/post/publish/video/init/",
            headers=tt_headers(access_token),
            json={
                "post_info": {
                    "title": caption[:150],
                    "privacy_level": "SELF_ONLY",  # ⚠️ Change to PUBLIC_TO_EVERYONE after audit
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                    "video_cover_timestamp_ms": 1000,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": CHUNK_SIZE,
                    "total_chunk_count": total_chunks,
                },
            },
            timeout=30,
        )
        init_resp.raise_for_status()
        init_data = init_resp.json()
        if init_data.get("error", {}).get("code") not in (None, "ok"):
            raise Exception(f"TikTok init failed: {init_data}")

        upload_url = init_data["data"]["upload_url"]
        publish_id = init_data["data"]["publish_id"]
        print(f"[TT] Upload initialized — publish_id={publish_id}, chunks={total_chunks}")

        # Step 4: Upload in chunks
        with open(tmp_path, "rb") as f:
            for chunk_idx in range(total_chunks):
                start = chunk_idx * CHUNK_SIZE
                chunk_data = f.read(CHUNK_SIZE)
                end = start + len(chunk_data) - 1

                upload_resp = requests.put(
                    upload_url,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Range": f"bytes {start}-{end}/{file_size}",
                        "Content-Length": str(len(chunk_data)),
                    },
                    data=chunk_data,
                    timeout=120,
                )
                if upload_resp.status_code not in (200, 201, 206):
                    raise Exception(f"TikTok chunk {chunk_idx} upload failed: {upload_resp.status_code} {upload_resp.text[:200]}")
                print(f"[TT] Chunk {chunk_idx + 1}/{total_chunks} uploaded")

        # Step 5: Poll publish status
        max_wait, poll_interval, elapsed = 300, 10, 0
        publish_status = None
        while elapsed < max_wait:
            status_resp = requests.post(
                f"{TIKTOK_BASE}/post/publish/status/fetch/",
                headers=tt_headers(access_token),
                json={"publish_id": publish_id},
                timeout=30,
            )
            status_resp.raise_for_status()
            status_data = status_resp.json().get("data", {})
            publish_status = status_data.get("status")
            print(f"[TT] Publish status: {publish_status} ({elapsed}s)")
            if publish_status == "PUBLISH_COMPLETE":
                break
            elif publish_status in ("FAILED", "PUBLISH_FAILED"):
                raise Exception(f"TikTok publish failed: {status_data.get('fail_reason', 'unknown')}")
            time.sleep(poll_interval)
            elapsed += poll_interval
        else:
            raise Exception(f"TikTok publish timed out after {max_wait}s (status: {publish_status})")

        print(f"[TT] Published! publish_id={publish_id}")
        return {
            "platform": "tiktok",
            "publish_id": publish_id,
            "privacy": "SELF_ONLY",
            "note": "Posted as SELF_ONLY — change to PUBLIC_TO_EVERYONE after TikTok audit approval",
        }

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ============================================================
# YouTube posting (YouTube Data API v3 — resumable upload)
# ============================================================

def refresh_youtube_token() -> str:
    """
    Refresh YouTube OAuth2 access token using the stored refresh token.
    YouTube access tokens expire every 1 hour.
    Refresh tokens persist indefinitely for production apps.
    """
    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("YouTube credentials incomplete — set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN")

    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise Exception(f"YouTube token refresh failed: {data}")

    access_token = data.get("access_token")
    if not access_token:
        raise Exception(f"YouTube token refresh returned no access_token: {data}")

    print(f"[YT] Access token refreshed (expires in {data.get('expires_in', 3600)}s)")
    return access_token


def post_to_youtube(
    media_url: str,
    caption: str,
    content_type: str,
    title: str = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Upload a video to YouTube via YouTube Data API v3 (resumable upload).

    Photos are skipped — YouTube is video-only.
    OAuth2 token is refreshed via direct HTTP on every call (tokens expire hourly).

    Flow:
    1. Refresh access token
    2. Download video from Bunny CDN to /tmp/
    3. Initiate resumable upload session (POST → get Location URI)
    4. PUT the full file to the Location URI
    5. Return video_id + watch URL
    """
    if content_type == "photo":
        return {
            "platform": "youtube",
            "skipped": True,
            "reason": "YouTube does not support photo posts. Videos only.",
        }

    mode_label = "[DRY RUN] " if dry_run else ""
    print(f"[YT] {mode_label}Posting video to YouTube...")

    access_token = refresh_youtube_token()

    if dry_run:
        print("[YT] [DRY RUN] Token refreshed successfully. Skipping upload.")
        return {"platform": "youtube", "dry_run": True, "token_ok": True}

    tmp_path, file_size = download_to_temp(media_url, suffix=".mp4")

    try:
        video_title = (title or caption[:100]).strip() or "Reform Chiropractic"
        video_description = caption.strip()

        # Initiate resumable upload session
        init_resp = requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(file_size),
            },
            json={
                "snippet": {
                    "title": video_title,
                    "description": video_description,
                    "categoryId": "22",       # People & Blogs
                    "defaultLanguage": "en",
                },
                "status": {
                    "privacyStatus": "private",  # ⚠️ Change to "public" when ready to go live
                    "selfDeclaredMadeForKids": False,
                },
            },
            timeout=30,
        )
        init_resp.raise_for_status()

        upload_uri = init_resp.headers.get("Location")
        if not upload_uri:
            raise Exception("YouTube resumable upload init returned no Location header")
        print("[YT] Resumable upload session initiated")

        # Upload the full file (single PUT — fine for chiro clips ≤200MB / 10min timeout)
        with open(tmp_path, "rb") as f:
            video_data = f.read()

        upload_resp = requests.put(
            upload_uri,
            headers={"Content-Type": "video/mp4", "Content-Length": str(file_size)},
            data=video_data,
            timeout=600,
        )
        if upload_resp.status_code not in (200, 201):
            raise Exception(f"YouTube upload failed: {upload_resp.status_code} {upload_resp.text[:500]}")

        video_id = upload_resp.json().get("id")
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"[YT] Published! ID={video_id}, URL={video_url}")
        return {"platform": "youtube", "post_id": video_id, "url": video_url}

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ============================================================
# Main worker function
# ============================================================

@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("meta-secrets"),
        modal.Secret.from_name("n8n-webhook-secrets"),
        modal.Secret.from_name("google-chat-social-poster"),
        modal.Secret.from_name("tiktok-secrets"),
        modal.Secret.from_name("youtube-secrets"),
    ],
    timeout=600,
)
def post_to_socials(
    platforms: List[str],
    media_url: str,
    caption: str,
    content_type: str = "photo",
    title: str = None,
    description: str = None,
    tags: List[str] = None,
    callback_url: str = None,
    job_id: str = None,
    notify_n8n: bool = True,
    metadata: dict = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Post content to one or more social media platforms.
    Each platform is attempted independently — partial success is OK.

    dry_run=True: validates auth, creates containers/drafts, but does NOT
    publish anything publicly. Safe for testing.
    """
    if not job_id:
        job_id = str(uuid.uuid4())

    mode_label = "[DRY RUN] " if dry_run else ""
    print(f"[START] {mode_label}Social posting job {job_id}")
    print(f"[INFO] Platforms: {platforms}, Type: {content_type}, Dry run: {dry_run}")
    print(f"[INFO] Media URL: {media_url}")

    results = []
    failed = []

    if notify_n8n:
        send_n8n_event("social.post.started", {
            "job_id": job_id,
            "platforms": platforms,
            "content_type": content_type,
            "media_url": media_url,
            "dry_run": dry_run,
        })

    # Post to each platform independently
    for platform in platforms:
        try:
            if platform == "instagram":
                result = post_to_instagram(media_url, caption, content_type, dry_run=dry_run)
                results.append(result)

            elif platform == "facebook":
                result = post_to_facebook(media_url, caption, content_type, dry_run=dry_run)
                results.append(result)

            elif platform == "tiktok":
                result = post_to_tiktok(media_url, caption, content_type, dry_run=dry_run)
                if result.get("skipped"):
                    print(f"[INFO] TikTok skipped: {result.get('reason')}")
                else:
                    results.append(result)

            elif platform == "youtube":
                result = post_to_youtube(
                    media_url=media_url,
                    caption=caption,
                    content_type=content_type,
                    title=title,
                    dry_run=dry_run,
                )
                if result.get("skipped"):
                    print(f"[INFO] YouTube skipped: {result.get('reason')}")
                else:
                    results.append(result)

            else:
                failed.append({
                    "platform": platform,
                    "error": f"Unknown platform: {platform}",
                })

        except Exception as e:
            print(f"[ERROR] {platform} posting failed: {e}")
            failed.append({
                "platform": platform,
                "error": str(e),
            })

    # Build final result
    all_succeeded = len(failed) == 0
    any_succeeded = len(results) > 0

    final_result = {
        "success": any_succeeded,
        "status": "completed" if all_succeeded else ("partial" if any_succeeded else "failed"),
        "job_id": job_id,
        "results": results,
        "failed": failed,
        "metadata": metadata or {},
    }

    # Send n8n event
    if notify_n8n:
        event_name = "social.post.completed" if any_succeeded else "social.post.failed"
        send_n8n_event(event_name, final_result)

    # Send callback
    if callback_url:
        send_callback(callback_url, final_result)

    # Google Chat notification
    _send_chat_summary(job_id, results, failed, content_type)

    print(f"[DONE] Job {job_id}: {len(results)} succeeded, {len(failed)} failed")
    return final_result


def _send_chat_summary(job_id: str, results: list, failed: list, content_type: str):
    """Build and send a Google Chat notification summarizing the posting results."""
    lines = []

    if results:
        lines.append(f"*Social post published* ({content_type})")
        for r in results:
            platform = r["platform"].capitalize()
            link = r.get("permalink") or r.get("url")
            if link:
                lines.append(f"  {platform}: <{link}|View post>")
            else:
                lines.append(f"  {platform}: Posted (ID: {r.get('post_id', 'unknown')})")

    if failed:
        for f in failed:
            lines.append(f"  {f['platform'].capitalize()}: FAILED — {f['error']}")

    if not results and failed:
        lines[0:0] = ["*Social posting failed*"]

    if lines:
        send_chat_notification("\n".join(lines))


# ============================================================
# Webhook endpoint
# ============================================================

@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def post_to_socials_webhook(data: dict) -> dict:
    """
    Web endpoint for n8n to trigger social media posting.

    Expected payload:
    {
        "platforms": ["instagram", "facebook"],
        "content_type": "photo",
        "media_url": "https://techopssocialmedia.b-cdn.net/...",
        "caption": "Post caption text",
        "callback_url": "https://n8n1.reformchiropractic.app/webhook/social-posted",
        "job_id": "optional",
        "title": "YouTube title (optional)",
        "description": "YouTube description (optional)",
        "tags": ["optional"],
        "metadata": {}
    }
    """
    platforms = data.get("platforms")
    media_url = data.get("media_url")
    caption = data.get("caption", "")
    content_type = data.get("content_type", "photo")
    callback_url = data.get("callback_url")
    job_id = data.get("job_id")
    title = data.get("title")
    description = data.get("description")
    tags = data.get("tags")
    metadata = data.get("metadata")
    notify_n8n = data.get("notify_n8n", True)
    dry_run = data.get("dry_run", False)

    # Validate required fields
    if not platforms or not isinstance(platforms, list):
        return {
            "accepted": False,
            "status": "error",
            "error_code": "missing_platforms",
            "message": "platforms is required and must be a list (e.g. ['instagram', 'facebook'])",
        }

    if not media_url:
        return {
            "accepted": False,
            "status": "error",
            "error_code": "missing_media_url",
            "message": "media_url is required",
        }

    if not callback_url:
        return {
            "accepted": False,
            "status": "error",
            "error_code": "missing_callback_url",
            "message": "callback_url is required for async processing",
        }

    valid_platforms = {"instagram", "facebook", "tiktok", "youtube"}
    invalid = [p for p in platforms if p not in valid_platforms]
    if invalid:
        return {
            "accepted": False,
            "status": "error",
            "error_code": "invalid_platforms",
            "message": f"Invalid platforms: {invalid}. Valid: {sorted(valid_platforms)}",
        }

    if not job_id:
        job_id = str(uuid.uuid4())

    # Spawn async worker
    post_to_socials.spawn(
        platforms=platforms,
        media_url=media_url,
        caption=caption,
        content_type=content_type,
        title=title,
        description=description,
        tags=tags,
        callback_url=callback_url,
        job_id=job_id,
        notify_n8n=notify_n8n,
        metadata=metadata,
        dry_run=dry_run,
    )

    return {
        "accepted": True,
        "status": "processing",
        "job_id": job_id,
        "message": f"Social posting accepted for {platforms}. Callback will be sent when complete.",
        "callback_url": callback_url,
    }


# ============================================================
# Ready-to-post notification (final review link)
# ============================================================

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("google-chat-social-poster")],
)
@modal.fastapi_endpoint(method="POST")
def notify_ready_to_post(data: dict) -> dict:
    """
    Called by n8n after a file is moved to the 'Ready for Scheduling' Drive folder.
    Sends a Google Chat notification with a link to the ClickUp task for final review.

    Expected payload:
    {
        "task_url": "https://app.clickup.com/t/...",
        "task_id": "clickup task id",
        "caption": "GPT-generated caption text",
        "content_type": "photo",  // or "video"/"reel"
        "category": "optional category label",
        "job_id": "optional"
    }
    """
    task_url = data.get("task_url")
    task_id = data.get("task_id", "")
    caption = data.get("caption", "")
    content_type = data.get("content_type", "photo")
    category = data.get("category", "")
    job_id = data.get("job_id") or str(uuid.uuid4())

    if not task_url:
        return {
            "accepted": False,
            "status": "error",
            "error_code": "missing_task_url",
            "message": "task_url is required",
        }

    # Build Chat message with ClickUp review link
    caption_preview = caption[:120] + "..." if len(caption) > 120 else caption
    lines = [
        "*New content ready for final review*",
        f"Type: {content_type}" + (f"  |  Category: {category}" if category else ""),
        f"Caption: _{caption_preview}_" if caption_preview else "",
        f"<{task_url}|Review in ClickUp>  —  set status to *Scheduled* to approve",
    ]
    message = "\n".join(line for line in lines if line)

    send_chat_notification(message)
    print(f"[OK] Final review notification sent for job {job_id} (task {task_id})")

    return {
        "accepted": True,
        "status": "notified",
        "job_id": job_id,
        "message": "Chat notification sent with ClickUp review link.",
    }


# ============================================================
# Bunny CDN helpers
# ============================================================

def bunny_list_folder(storage_zone: str, api_key: str, folder_path: str) -> list:
    """List files in a Bunny CDN storage folder."""
    url = f"{BUNNY_STORAGE_BASE}/{storage_zone}/{folder_path.strip('/')}/"
    resp = requests.get(url, headers={"AccessKey": api_key}, timeout=30)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json()


def bunny_upload_json(storage_zone: str, api_key: str, path: str, data: dict):
    """Upload a JSON object to Bunny CDN storage."""
    content = json.dumps(data, indent=2).encode("utf-8")
    url = f"{BUNNY_STORAGE_BASE}/{storage_zone}/{path.lstrip('/')}"
    resp = requests.put(
        url,
        data=content,
        headers={"AccessKey": api_key, "Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()


def bunny_fetch_json(cdn_base: str, path: str) -> dict:
    """Fetch a JSON file from Bunny CDN public URL."""
    url = f"{cdn_base.rstrip('/')}/{path.lstrip('/')}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def bunny_delete(storage_zone: str, api_key: str, path: str):
    """Delete a file from Bunny CDN storage."""
    url = f"{BUNNY_STORAGE_BASE}/{storage_zone}/{path.lstrip('/')}"
    resp = requests.delete(url, headers={"AccessKey": api_key}, timeout=30)
    resp.raise_for_status()


# ============================================================
# Google Drive helpers
# ============================================================

def get_drive_service(service_account_json: str):
    """Build Google Drive API service using service account."""
    from google.oauth2 import service_account as sa_module
    from googleapiclient.discovery import build

    creds_data = json.loads(service_account_json)
    credentials = sa_module.Credentials.from_service_account_info(
        creds_data,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=credentials)


def move_drive_file(service_account_json: str, file_id: str, new_parent_id: str):
    """Move a Google Drive file to a new folder. Supports both My Drive and Shared Drives."""
    service = get_drive_service(service_account_json)
    file_info = service.files().get(
        fileId=file_id,
        fields="parents",
        supportsAllDrives=True,
    ).execute()
    old_parents = ",".join(file_info.get("parents", []))
    service.files().update(
        fileId=file_id,
        addParents=new_parent_id,
        removeParents=old_parents,
        fields="id,parents",
        supportsAllDrives=True,
    ).execute()
    print(f"[OK] Drive file {file_id} moved to folder {new_parent_id}")


# ============================================================
# Google Sheets helper (posting schedule config)
# ============================================================

def get_sheets_service(service_account_json: str, readonly: bool = True):
    """Build Google Sheets API service using service account."""
    from google.oauth2 import service_account as sa_module
    from googleapiclient.discovery import build

    creds_data = json.loads(service_account_json)
    scope = "https://www.googleapis.com/auth/spreadsheets.readonly" if readonly else "https://www.googleapis.com/auth/spreadsheets"
    credentials = sa_module.Credentials.from_service_account_info(
        creds_data,
        scopes=[scope],
    )
    return build("sheets", "v4", credentials=credentials)


def append_sheet_row(service_account_json: str, sheet_id: str, row_values: list):
    """Append a row to a Google Sheet."""
    service = get_sheets_service(service_account_json, readonly=False)
    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range="2026",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row_values]},
    ).execute()
    print(f"[OK] Row appended to sheet {sheet_id}")


def read_posting_schedule(service_account_json: str, sheet_id: str) -> list:
    """
    Read the Social Media Posting Schedule Google Sheet.
    Expected columns: Category Pool | Post Days | Post Times | Platforms | Active
    Category Pool: comma-separated list of eligible categories for this time slot
    Post Days: comma-separated abbreviations e.g. "Mon,Wed,Fri"
    Post Times: comma-separated 24h times e.g. "09:00,17:00"
    Returns list of active schedule entry dicts, each with a 'category_pool' list.
    """
    service = get_sheets_service(service_account_json)
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range="Sheet1",
    ).execute()
    rows = result.get("values", [])
    if not rows:
        return []
    headers = [h.strip().lower().replace(" ", "_") for h in rows[0]]
    schedule = []
    for row in rows[1:]:
        if not row:
            continue
        entry = {headers[i]: (row[i].strip() if i < len(row) else "") for i in range(len(headers))}
        if entry.get("active", "").lower() != "true":
            continue
        # Parse category pool — supports both "category_pool" (new) and "category" (legacy single-value)
        raw_pool = entry.get("category_pool") or entry.get("category", "")
        entry["category_pool"] = [c.strip() for c in raw_pool.split(",") if c.strip()]
        schedule.append(entry)
    return schedule


def matches_schedule(entry: dict, now_pacific: datetime) -> bool:
    """Return True if the schedule entry matches the current Pacific day and hour."""
    day_abbrevs = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    current_day = day_abbrevs[now_pacific.weekday()]
    allowed_days = [d.strip().lower()[:3] for d in entry.get("post_days", "").split(",")]
    if current_day not in allowed_days:
        return False
    current_hour = now_pacific.hour
    for t in entry.get("post_times", "").split(","):
        t = t.strip()
        if ":" in t and int(t.split(":")[0]) == current_hour:
            return True
    return False


# ============================================================
# ClickUp helper
# ============================================================

def update_clickup_status(task_id: str, api_key: str, status: str):
    """Update a ClickUp task status."""
    resp = requests.put(
        f"https://api.clickup.com/api/v2/task/{task_id}",
        json={"status": status},
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    print(f"[OK] ClickUp task {task_id} status → {status}")


# ============================================================
# move_to_scheduled endpoint
# ============================================================

@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("bunny-secrets"),
        modal.Secret.from_name("google-drive-secrets"),
        modal.Secret.from_name("google-chat-social-poster"),
    ],
    timeout=60,
)
@modal.fastapi_endpoint(method="POST")
def move_to_scheduled(data: dict) -> dict:
    """
    Called by n8n when a ClickUp task status is set to 'Scheduled' (final approval).
    1. Writes metadata JSON to Bunny CDN Scheduled/ folder
    2. Moves Drive file from 'Ready for Scheduling' to 'Scheduled' folder

    Expected payload:
    {
        "media_url": "https://techopssocialmedia.b-cdn.net/...",
        "drive_file_id": "Google Drive file ID",
        "caption": "...",
        "content_type": "video|photo",
        "category": "Wellness Tip",
        "task_id": "clickup-task-id",
        "task_url": "https://app.clickup.com/t/..."
    }
    """
    media_url = data.get("media_url")
    drive_file_id = data.get("drive_file_id")
    caption = data.get("caption", "")
    content_type = data.get("content_type", "photo")
    category = data.get("category", "")
    task_id = data.get("task_id")
    task_url = data.get("task_url", "")

    if not media_url or not task_id:
        return {
            "success": False,
            "error": "media_url and task_id are required",
        }

    bunny_api_key = os.environ["BUNNY_STORAGE_API_KEY"]
    bunny_storage_zone = os.environ["BUNNY_STORAGE_ZONE"]
    drive_sa_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]

    # Route to Videos or Photos subfolder based on content_type
    if content_type in ("video", "reel"):
        drive_scheduled_folder_id = os.environ.get("DRIVE_SCHEDULED_VIDEOS_FOLDER_ID", "")
    else:
        drive_scheduled_folder_id = os.environ.get("DRIVE_SCHEDULED_PHOTOS_FOLDER_ID", "")

    meta_path = f"Scheduled/{task_id}.meta.json"
    metadata = {
        "task_id": task_id,
        "task_url": task_url,
        "media_url": media_url,
        "caption": caption,
        "content_type": content_type,
        "category": category,
        "drive_file_id": drive_file_id or "",
        "scheduled_at": datetime.now(get_pacific()).isoformat(),
        "status": "pending",
    }

    # Write metadata to Bunny Scheduled/
    bunny_upload_json(bunny_storage_zone, bunny_api_key, meta_path, metadata)
    print(f"[OK] Metadata written to Bunny: {meta_path}")

    # Move Drive file to Scheduled folder
    if drive_file_id and drive_scheduled_folder_id:
        try:
            move_drive_file(drive_sa_json, drive_file_id, drive_scheduled_folder_id)
        except Exception as e:
            print(f"[WARN] Drive move failed (non-fatal): {e}")
    else:
        print("[WARN] Skipping Drive move — missing drive_file_id or scheduled folder ID")

    return {
        "success": True,
        "task_id": task_id,
        "meta_path": meta_path,
        "message": "Content queued for scheduled posting.",
    }


# ============================================================
# Hourly posting scheduler (cron)
# ============================================================

@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("meta-secrets"),
        modal.Secret.from_name("bunny-secrets"),
        modal.Secret.from_name("google-drive-secrets"),
        modal.Secret.from_name("google-chat-social-poster"),
        modal.Secret.from_name("clickup-api"),
        modal.Secret.from_name("tiktok-secrets"),
        modal.Secret.from_name("youtube-secrets"),
    ],
    timeout=600,
    # CRON DISABLED — re-enable for go-live:
    # schedule=modal.Cron("0 0,1,16,17,18,19,20 * * 1-6"),
)
def run_posting_schedule():
    """
    Runs every hour. Reads the Google Sheets posting schedule (pool-based), checks
    Bunny Scheduled/ for pending items, and posts one item per matching time slot.

    Pool-based selection: each slot defines a list of eligible categories. The cron
    randomly picks from whichever pool categories have pending content, so the feed
    never feels predictable. If no pool category has content, falls back to the
    globally oldest pending item from any category.

    Content-type routing: photos are restricted to Instagram + Facebook only,
    regardless of what platforms are listed in the schedule. Videos go to all
    platforms in the slot's Platforms list.

    After a successful post: archives meta to Bunny Posted/, moves Drive file to
    Completed folder, updates ClickUp task status to 'Posted'.
    On failure: updates meta status to 'failed', sends a Chat alert.
    """
    import random

    bunny_api_key = os.environ["BUNNY_STORAGE_API_KEY"]
    bunny_storage_zone = os.environ["BUNNY_STORAGE_ZONE"]
    bunny_cdn_base = os.environ["BUNNY_CDN_BASE"]
    drive_sa_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    completed_folder_ids_raw = os.environ.get("DRIVE_COMPLETED_FOLDER_IDS", "{}")
    try:
        completed_folder_ids = json.loads(completed_folder_ids_raw)
    except Exception:
        completed_folder_ids = {}
        print("[WARN] Could not parse DRIVE_COMPLETED_FOLDER_IDS — Drive moves to Completed will be skipped")
    schedule_sheet_id = os.environ.get("SCHEDULE_SHEET_ID", "")
    clickup_api_key = os.environ.get("CLICKUP_API_KEY", "")

    now = datetime.now(get_pacific())
    print(f"[SCHEDULER] Running at {now.strftime('%A %Y-%m-%d %H:%M')} Pacific")

    if not schedule_sheet_id:
        print("[WARN] SCHEDULE_SHEET_ID not set — skipping run")
        return

    try:
        schedule = read_posting_schedule(drive_sa_json, schedule_sheet_id)
        print(f"[INFO] Loaded {len(schedule)} active schedule entries")
    except Exception as e:
        send_chat_notification(f"*Scheduler error:* Could not read posting schedule sheet\n{e}")
        return

    # Find all slots that match the current day + hour
    matching_slots = [entry for entry in schedule if matches_schedule(entry, now)]
    if not matching_slots:
        print(f"[INFO] No slots scheduled for {now.strftime('%A %H:00')} — nothing to post")
        return

    print(f"[INFO] {len(matching_slots)} slot(s) match this hour")

    # Load ALL pending meta files from Bunny once (avoid repeated API calls per slot)
    files = bunny_list_folder(bunny_storage_zone, bunny_api_key, "Scheduled")
    meta_files = [f for f in files if f.get("ObjectName", "").endswith(".meta.json")]
    print(f"[INFO] Found {len(meta_files)} item(s) in Scheduled/")

    # Build pending_by_category — sorted oldest-first per category
    pending_by_category: Dict[str, list] = {}
    for f in meta_files:
        obj_name = f.get("ObjectName", "")
        try:
            meta = bunny_fetch_json(bunny_cdn_base, f"Scheduled/{obj_name}")
        except Exception as e:
            print(f"[WARN] Could not read meta {obj_name}: {e}")
            continue
        if meta.get("status") in ("posted", "failed", "posting"):
            continue
        cat = meta.get("category", "").strip()
        pending_by_category.setdefault(cat, []).append((f.get("DateCreated", ""), obj_name, meta))

    for cat in pending_by_category:
        pending_by_category[cat].sort(key=lambda x: x[0])

    # Track items posted this cron run to prevent double-posting across slots
    posted_obj_names: set = set()

    def _post_item(obj_name: str, meta: dict, slot_platforms: list):
        """Post a single queued item, then archive/update as needed."""
        task_id = meta.get("task_id", "")
        cat = meta.get("category", "").strip()
        meta_path = f"Scheduled/{obj_name}"

        # Content-type routing: photos only go to IG + FB
        content_type_for_post = meta.get("content_type", "photo")
        if content_type_for_post == "photo":
            effective_platforms = [p for p in slot_platforms if p in {"instagram", "facebook"}]
            if not effective_platforms:
                effective_platforms = ["instagram", "facebook"]
            print(f"[INFO] Photo — restricting platforms to {effective_platforms} (slot had {slot_platforms})")
        else:
            effective_platforms = slot_platforms

        print(f"[POST] '{cat}' → {effective_platforms} (task {task_id})")

        # Mark as in-progress to prevent double-posting on re-runs
        meta["status"] = "posting"
        try:
            bunny_upload_json(bunny_storage_zone, bunny_api_key, meta_path, meta)
        except Exception as e:
            print(f"[WARN] Could not mark as posting: {e}")

        try:
            result = post_to_socials.remote(
                platforms=effective_platforms,
                media_url=meta["media_url"],
                caption=meta.get("caption", ""),
                content_type=content_type_for_post,
                job_id=task_id or str(uuid.uuid4()),
                callback_url=None,
                notify_n8n=False,
                metadata={"category": cat, "task_id": task_id},
            )

            if result.get("success"):
                print(f"[OK] Post succeeded for task {task_id}")

                meta["status"] = "posted"
                meta["posted_at"] = datetime.now(get_pacific()).isoformat()
                meta["post_results"] = result.get("results", [])
                try:
                    bunny_upload_json(bunny_storage_zone, bunny_api_key, f"Posted/{obj_name}", meta)
                    bunny_delete(bunny_storage_zone, bunny_api_key, meta_path)
                except Exception as e:
                    print(f"[WARN] Bunny archive failed: {e}")

                drive_file_id = meta.get("drive_file_id")
                drive_completed_folder_id = completed_folder_ids.get(cat, "")
                if drive_file_id and drive_completed_folder_id:
                    try:
                        move_drive_file(drive_sa_json, drive_file_id, drive_completed_folder_id)
                    except Exception as e:
                        print(f"[WARN] Drive move to Completed failed: {e}")
                elif drive_file_id and not drive_completed_folder_id:
                    print(f"[WARN] No Completed folder mapped for '{cat}' — skipping Drive move")

                if task_id and clickup_api_key:
                    try:
                        update_clickup_status(task_id, clickup_api_key, "posted")
                    except Exception as e:
                        print(f"[WARN] ClickUp update failed: {e}")
            else:
                raise Exception(f"Posting returned success=false: {result.get('failed')}")

        except Exception as e:
            print(f"[ERROR] Posting failed for task {task_id}: {e}")
            meta["status"] = "failed"
            meta["error"] = str(e)
            meta["failed_at"] = datetime.now(get_pacific()).isoformat()
            try:
                bunny_upload_json(bunny_storage_zone, bunny_api_key, meta_path, meta)
            except Exception:
                pass
            send_chat_notification(
                f"*Scheduler: posting failed*\nCategory: {cat}  |  Task: {task_id}\nError: {e}\n"
                f"File remains in Scheduled/ — reset status to 'pending' to retry."
            )

    # Process each matching slot
    for slot in matching_slots:
        pool = slot.get("category_pool", [])
        slot_platforms = [p.strip() for p in slot.get("platforms", "instagram,facebook").split(",")]

        # Find pool categories that have unposted pending content
        available = [
            cat for cat in pool
            if cat in pending_by_category
            and any(item[1] not in posted_obj_names for item in pending_by_category[cat])
        ]

        if available:
            chosen_cat = random.choice(available)
            _, obj_name, meta = next(
                item for item in pending_by_category[chosen_cat]
                if item[1] not in posted_obj_names
            )
            print(f"[SLOT] Pool {pool} → randomly selected '{chosen_cat}'")
        else:
            # Fallback: oldest pending item from any category not yet posted this run
            all_pending = [
                item for items in pending_by_category.values()
                for item in items
                if item[1] not in posted_obj_names
            ]
            if not all_pending:
                print(f"[INFO] No pending content anywhere — skipping slot {pool}")
                send_chat_notification(
                    f"*Scheduler:* Slot {pool} had nothing to post — queue is empty across all categories."
                )
                continue
            all_pending.sort(key=lambda x: x[0])
            _, obj_name, meta = all_pending[0]
            chosen_cat = meta.get("category", "unknown")
            print(f"[FALLBACK] Pool {pool} empty — posting oldest available: '{chosen_cat}'")
            send_chat_notification(
                f"*Scheduler fallback:* No content in pool {pool}. "
                f"Posting oldest available (category: {chosen_cat})."
            )

        posted_obj_names.add(obj_name)
        _post_item(obj_name, meta, slot_platforms)


# ============================================================
# ClickUp webhook handler (direct — no n8n)
# ============================================================

@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("bunny-secrets"),
        modal.Secret.from_name("google-drive-secrets"),
        modal.Secret.from_name("google-chat-social-poster"),
        modal.Secret.from_name("clickup-api"),
    ],
    timeout=60,
)
@modal.fastapi_endpoint(method="POST")
def clickup_scheduled_handler(data: dict) -> dict:
    """
    Receives ClickUp webhook events directly (replaces n8n Social Media ClickUp Webhook flow).

    Handles three status transitions:
      APPROVED       → move Drive file to "3. Ready for Scheduling" + Chat review notification
      SCHEDULED      → write Bunny metadata + move Drive to "4. Scheduled" + log to Sheet
      CUTOFF NOT MET → move Drive file to archive folder

    ClickUp webhook registered:
      Team: 8406969 | List: 901413473007 | Event: taskStatusUpdated
    """
    event = data.get("event")
    task_id = data.get("task_id")

    if event != "taskStatusUpdated":
        return {"accepted": False, "reason": f"ignored event: {event}"}

    if not task_id:
        return {"accepted": False, "reason": "missing task_id"}

    # Extract new status from history
    history_items = data.get("history_items", [])
    new_status = None
    for item in history_items:
        if item.get("field") == "status":
            new_status = item.get("after", {}).get("status", "").lower()
            break

    handled_statuses = ("approved", "scheduled", "cutoff not met")
    if new_status not in handled_statuses:
        print(f"[INFO] Task {task_id} status → {new_status!r}, ignoring")
        return {"accepted": False, "reason": f"status '{new_status}' not handled"}

    print(f"[OK] Task {task_id} → {new_status.upper()}")

    # Fetch full task from ClickUp
    clickup_api_key = os.environ["CLICKUP_API_KEY"]
    resp = requests.get(
        f"https://api.clickup.com/api/v2/task/{task_id}",
        headers={"Authorization": clickup_api_key},
        timeout=30,
    )
    resp.raise_for_status()
    task = resp.json()

    custom_fields = {cf["name"]: cf for cf in task.get("custom_fields", [])}

    def get_text_field(name: str) -> str:
        field = custom_fields.get(name, {})
        val = field.get("value")
        return str(val).strip() if val else ""

    drive_file_id = get_text_field("Drive ID")
    drive_sa_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    task_url = task.get("url") or f"https://app.clickup.com/t/{task_id}"
    task_name = task.get("name", "")

    # Shared: content type from Video Duration
    duration_raw = get_text_field("Video Duration")
    try:
        content_type = "video" if float(duration_raw) > 0 else "photo"
    except (ValueError, TypeError):
        content_type = "photo"

    # Shared: category from Video Category dropdown
    # ClickUp dropdowns return value as orderindex (int); look up name from type_config.options
    category = ""
    cat_field = custom_fields.get("Video Category", {})
    cat_val = cat_field.get("value")
    if isinstance(cat_val, dict):
        category = cat_val.get("name", "")
    elif isinstance(cat_val, str):
        category = cat_val
    elif isinstance(cat_val, int):
        options = cat_field.get("type_config", {}).get("options", [])
        for opt in options:
            if opt.get("orderindex") == cat_val:
                category = opt.get("name", "")
                break

    # ----------------------------------------------------------------
    # CUTOFF NOT MET — archive the Drive file, no notification
    # ----------------------------------------------------------------
    if new_status == "cutoff not met":
        if drive_file_id:
            try:
                move_drive_file(drive_sa_json, drive_file_id, "1DziclMe5M9m7iy-32hirPzJAI8YqggiR")
                print(f"[OK] Drive file {drive_file_id} moved to Cutoff Not Met archive")
            except Exception as e:
                print(f"[WARN] Drive move to archive failed: {e}")
        else:
            print(f"[WARN] No Drive ID on task {task_id}, skipping archive move")
        return {"accepted": True, "action": "archived", "task_id": task_id}

    # ----------------------------------------------------------------
    # APPROVED — move to "3. Ready for Scheduling" + Chat notification
    # ----------------------------------------------------------------
    if new_status == "approved":
        ready_folder_id = (
            "1l8WQCW7YrAnkA1E4QCu0dEBjmRXLc_G3"  # Videos
            if content_type == "video"
            else "12UTqALM0Kh_XtWMenYFqWPXaOFvEjbIr"  # Photos
        )
        if drive_file_id:
            try:
                move_drive_file(drive_sa_json, drive_file_id, ready_folder_id)
                print(f"[OK] Drive file moved to Ready for Scheduling ({content_type})")
            except Exception as e:
                print(f"[WARN] Drive move to Ready for Scheduling failed: {e}")

        caption = (task.get("description") or "").strip() or task_name
        caption_preview = caption[:120] + "..." if len(caption) > 120 else caption
        lines = [
            "*New content ready for final review*",
            f"Category: {category}  |  Type: {content_type}" if category else f"Type: {content_type}",
            f"Caption: _{caption_preview}_" if caption_preview else "",
            f"<{task_url}|Review in ClickUp>  —  set status to *Scheduled* to approve",
        ]
        send_chat_notification("\n".join(l for l in lines if l))
        print(f"[OK] Approved — review notification sent for task {task_id}")
        return {"accepted": True, "action": "ready_for_scheduling", "task_id": task_id}

    # ----------------------------------------------------------------
    # SCHEDULED — Bunny metadata + Drive move + Sheet log
    # ----------------------------------------------------------------
    media_url = get_text_field("CDN URL")
    caption = (task.get("description") or "").strip() or task_name
    lead = get_text_field("Lead")

    if not media_url:
        msg = f"*Scheduler warning:* Task {task_id} set to Scheduled but has no CDN URL.\n<{task_url}|View task>"
        send_chat_notification(msg)
        return {"accepted": False, "error": "No CDN URL on task"}

    bunny_api_key = os.environ["BUNNY_STORAGE_API_KEY"]
    bunny_storage_zone = os.environ["BUNNY_STORAGE_ZONE"]

    # Idempotency: skip if meta.json already exists (handles ClickUp retries / duplicate webhooks)
    meta_path = f"Scheduled/{task_id}.meta.json"
    check_url = f"{BUNNY_STORAGE_BASE}/{bunny_storage_zone}/{meta_path}"
    existing = requests.get(check_url, headers={"AccessKey": bunny_api_key}, timeout=10)
    if existing.status_code == 200:
        print(f"[SKIP] Meta already exists for {task_id}, ignoring duplicate webhook")
        return {"accepted": False, "reason": "duplicate — already processed"}

    drive_scheduled_folder_id = (
        os.environ.get("DRIVE_SCHEDULED_VIDEOS_FOLDER_ID", "")
        if content_type in ("video", "reel")
        else os.environ.get("DRIVE_SCHEDULED_PHOTOS_FOLDER_ID", "")
    )

    # Write Bunny metadata
    metadata = {
        "task_id": task_id,
        "task_url": task_url,
        "media_url": media_url,
        "caption": caption,
        "content_type": content_type,
        "category": category,
        "drive_file_id": drive_file_id,
        "scheduled_at": datetime.now(get_pacific()).isoformat(),
        "status": "pending",
    }
    bunny_upload_json(bunny_storage_zone, bunny_api_key, meta_path, metadata)
    print(f"[OK] Bunny metadata written: {meta_path}")

    # Move Drive file to "4. Scheduled"
    if drive_file_id and drive_scheduled_folder_id:
        try:
            move_drive_file(drive_sa_json, drive_file_id, drive_scheduled_folder_id)
        except Exception as e:
            print(f"[WARN] Drive move to Scheduled failed: {e}")
    else:
        print(f"[WARN] Skipping Drive move — drive_file_id={drive_file_id!r}, folder={drive_scheduled_folder_id!r}")

    # Log row to tracking sheet
    drive_link = f"https://drive.google.com/file/d/{drive_file_id}" if drive_file_id else ""
    try:
        append_sheet_row(
            drive_sa_json,
            "1ybOSGblVcLTGHdbYCQmp1lJQnyFn8LaKBzqPxLRsTpQ",
            [task_name, content_type, category, duration_raw, lead, drive_file_id, drive_link, media_url],
        )
    except Exception as e:
        print(f"[WARN] Sheet logging failed (non-fatal): {e}")

    return {
        "success": True,
        "task_id": task_id,
        "meta_path": meta_path,
        "message": "Content queued for scheduled posting.",
    }


# ============================================================
# Local test entrypoint
# ============================================================

@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("meta-secrets"),
        modal.Secret.from_name("google-chat-social-poster"),
    ],
    timeout=60,
)
def verify_credentials() -> Dict[str, Any]:
    """
    Verify all API credentials are valid without posting anything.
    Tests: Meta token, Instagram account, Facebook page, Google Chat.
    """
    results = {}

    # Instagram auth check
    try:
        ig_info = verify_instagram_auth()
        results["instagram"] = {
            "status": "ok",
            "username": ig_info.get("username"),
            "name": ig_info.get("name"),
            "media_count": ig_info.get("media_count"),
        }
        print(f"[OK] Instagram: @{ig_info.get('username')} ({ig_info.get('media_count')} posts)")
    except Exception as e:
        results["instagram"] = {"status": "error", "error": str(e)}
        print(f"[FAIL] Instagram: {e}")

    # Facebook auth check
    try:
        fb_info = verify_facebook_auth()
        results["facebook"] = {
            "status": "ok",
            "page_name": fb_info.get("name"),
            "page_id": fb_info.get("id"),
            "fan_count": fb_info.get("fan_count"),
        }
        print(f"[OK] Facebook: {fb_info.get('name')} ({fb_info.get('fan_count')} fans)")
    except Exception as e:
        results["facebook"] = {"status": "error", "error": str(e)}
        print(f"[FAIL] Facebook: {e}")

    # Google Chat check
    try:
        send_chat_notification("Social Poster: credential verification test")
        results["google_chat"] = {"status": "ok"}
        print("[OK] Google Chat: notification sent")
    except Exception as e:
        results["google_chat"] = {"status": "error", "error": str(e)}
        print(f"[FAIL] Google Chat: {e}")

    return results


@app.local_entrypoint()
def main():
    """
    Local test entrypoint — SAFE, nothing gets published.
    Usage: modal run execution/modal_social_poster.py

    Runs two test phases:
    1. Credential verification (fetches account info, no posting)
    2. Dry run (creates IG container + FB draft, but does NOT publish)
    """
    print("=" * 60)
    print("  Social Poster: Safe Test (nothing will be published)")
    print("=" * 60)

    # Phase 1: Verify credentials
    print("\n--- Phase 1: Credential Verification ---\n")
    cred_results = verify_credentials.remote()
    print(f"\nCredentials: {json.dumps(cred_results, indent=2)}")

    # Check if creds passed before doing dry run
    ig_ok = cred_results.get("instagram", {}).get("status") == "ok"
    fb_ok = cred_results.get("facebook", {}).get("status") == "ok"

    if not ig_ok and not fb_ok:
        print("\n[STOP] Both Instagram and Facebook auth failed. Fix credentials first.")
        return

    # Phase 2: Dry run (container + draft, no publish)
    platforms = []
    if ig_ok:
        platforms.append("instagram")
    if fb_ok:
        platforms.append("facebook")

    print(f"\n--- Phase 2: Dry Run ({', '.join(platforms)}) ---\n")
    print("Instagram: will create a media container but NOT publish (expires in 24h)")
    print("Facebook: will create an unpublished draft (visible only in Page settings)\n")

    test_result = post_to_socials.remote(
        platforms=platforms,
        media_url="https://techopssocialmedia.b-cdn.net/Photos/howdy.jpeg",
        caption="[DRY RUN TEST] Social poster verification. Not published.",
        content_type="photo",
        callback_url=None,
        job_id="test-dry-run",
        notify_n8n=False,
        dry_run=True,
    )

    print(f"\nDry run result: {json.dumps(test_result, indent=2)}")

    if test_result.get("success"):
        print("\n[SUCCESS] Dry run passed! The worker is ready for production use.")
        print("To do a real post, call the webhook with dry_run=false (the default).")
    else:
        print("\n[ISSUE] Some platforms failed. Check errors above.")
