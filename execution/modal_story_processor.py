"""
Modal Story Processor
Adds Reform Chiropractic logo overlay to photos for Instagram/Facebook stories.

ARCHITECTURE:
1. n8n calls /process_story_webhook with photo_url + callback_url
2. Modal accepts job immediately, returns {accepted: true, job_id: ...}
3. Modal spawns async worker to process image
4. Worker downloads photo, adds logo overlay, uploads to Bunny CDN
5. When complete, Modal sends POST to callback_url with branded CDN URL
6. n8n continues workflow (GPT captions, Google Drive, ClickUp)
"""

import modal
import requests
import uuid
import os
import time
from io import BytesIO
from typing import Dict, Any

# Create Modal app
app = modal.App("story-processor")

# Create Modal image with Pillow for image processing
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("requests", "Pillow", "fastapi")
)

# Logo location on Bunny CDN (uploaded once during setup)
LOGO_CDN_URL = "https://techopssocialmedia.b-cdn.net/logos/reform-logo.png"

# Story dimensions (9:16 vertical)
STORY_WIDTH = 1080
STORY_HEIGHT = 1920

# Logo placement
LOGO_WIDTH = 200  # Logo resized to this width
LOGO_PADDING = 40  # Padding from edges


def send_n8n_event(event_name: str, data: dict = None):
    """
    Send event to n8n webhook following modal_n8n_integration.md standards

    Args:
        event_name: Event in format system.area.action (e.g., "story.process.completed")
        data: Optional event payload data
    """
    payload = {
        "event": event_name,
        "job_id": str(uuid.uuid4()),
        "data": data if data is not None else {}
    }

    webhook_token = os.getenv("N8N_WEBHOOK_TOKEN")
    webhook_url = os.getenv("N8N_WEBHOOK_URL")

    headers = {
        "Content-Type": "application/json",
        "x-modal-token": webhook_token
    }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        print(f"[OK] Event sent: {event_name}")
        return response
    except Exception as e:
        print(f"[ERROR] Failed to send event {event_name}: {str(e)}")


def send_callback(callback_url: str, data: Dict[str, Any]):
    """
    Send callback to n8n or other webhook.
    Retries up to 3 times to ensure delivery.
    """
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(callback_url, json=data, timeout=30)
            response.raise_for_status()
            print(f"[OK] Callback sent to {callback_url} (attempt {attempt})")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to send callback (attempt {attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                time.sleep(5)
            else:
                print(f"[FATAL] Callback failed after {max_attempts} attempts")
                return False


def download_image(url: str) -> bytes:
    """Download image from URL and return raw bytes."""
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.content


def prepare_logo(logo_bytes: bytes, invert: bool = False):
    """
    Load and prepare the logo image.
    Resizes to LOGO_WIDTH and optionally inverts colors for dark backgrounds.
    """
    from PIL import Image, ImageOps

    logo = Image.open(BytesIO(logo_bytes)).convert("RGBA")

    if invert:
        # Split into channels, invert RGB, keep alpha
        r, g, b, a = logo.split()
        rgb = Image.merge("RGB", (r, g, b))
        rgb_inverted = ImageOps.invert(rgb)
        ri, gi, bi = rgb_inverted.split()
        logo = Image.merge("RGBA", (ri, gi, bi, a))

    # Resize to target width, maintain aspect ratio
    ratio = LOGO_WIDTH / logo.width
    new_height = int(logo.height * ratio)
    logo = logo.resize((LOGO_WIDTH, new_height), Image.LANCZOS)

    return logo


def detect_brightness(img, region_box):
    """
    Detect average brightness of a region in the image.
    Returns value 0-255 (0=black, 255=white).
    """
    region = img.crop(region_box)
    # Convert to grayscale and get average
    grayscale = region.convert("L")
    pixels = list(grayscale.tobytes())
    return sum(pixels) / len(pixels) if pixels else 128


def process_image(photo_bytes: bytes, logo_bytes: bytes) -> bytes:
    """
    Process a photo into a branded story image:
    1. Resize/crop to 1080x1920
    2. Detect brightness in top-right corner
    3. Add logo (inverted if background is dark)
    4. Return processed image bytes
    """
    from PIL import Image, ImageOps

    # Open and resize/crop to story dimensions
    photo = Image.open(BytesIO(photo_bytes)).convert("RGBA")
    photo = ImageOps.fit(photo, (STORY_WIDTH, STORY_HEIGHT), method=Image.LANCZOS)

    # Detect brightness in top-right area where logo will go
    logo_region = (
        STORY_WIDTH - LOGO_WIDTH - LOGO_PADDING * 2,  # left
        0,                                               # top
        STORY_WIDTH,                                     # right
        LOGO_PADDING * 2 + 80                            # bottom (approximate logo height area)
    )
    brightness = detect_brightness(photo, logo_region)
    should_invert = brightness < 128
    print(f"[INFO] Top-right brightness: {brightness:.0f}/255, invert logo: {should_invert}")

    # Prepare logo
    logo = prepare_logo(logo_bytes, invert=should_invert)

    # Position logo in top-right corner
    logo_x = STORY_WIDTH - logo.width - LOGO_PADDING
    logo_y = LOGO_PADDING

    # Paste logo with alpha compositing
    photo.paste(logo, (logo_x, logo_y), logo)

    # Convert to RGB for PNG/JPEG output
    output = photo.convert("RGB")

    # Save to bytes
    buffer = BytesIO()
    output.save(buffer, format="PNG", quality=95)
    return buffer.getvalue()


def upload_to_bunny(image_bytes: bytes, filename: str) -> str:
    """
    Upload processed image to Bunny CDN.
    Uses LA region endpoint per CLAUDE.md.

    Returns the public CDN URL.
    """
    bunny_api_key = os.getenv("BUNNY_STORAGE_API_KEY")
    storage_zone = os.getenv("BUNNY_STORAGE_ZONE")
    cdn_base = os.getenv("BUNNY_CDN_BASE")

    destination_path = f"stories/{filename}"
    upload_url = f"https://la.storage.bunnycdn.com/{storage_zone}/{destination_path}"

    headers = {
        "AccessKey": bunny_api_key,
        "Content-Type": "application/octet-stream"
    }

    response = requests.put(
        upload_url,
        data=image_bytes,
        headers=headers,
        timeout=120
    )
    response.raise_for_status()

    cdn_url = f"{cdn_base.rstrip('/')}/{destination_path}"
    print(f"[OK] Uploaded to Bunny CDN: {cdn_url}")
    return cdn_url


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("bunny-secrets"),
        modal.Secret.from_name("n8n-webhook-secrets"),
    ],
    timeout=300,
)
def process_story(
    photo_url: str,
    callback_url: str = None,
    job_id: str = None,
    notify_n8n: bool = True,
) -> dict:
    """
    Process a photo into a branded story image.

    1. Downloads the photo
    2. Downloads the Reform logo from Bunny CDN
    3. Resizes photo to 1080x1920 (9:16 story format)
    4. Adds logo to top-right corner (auto-inverts for dark backgrounds)
    5. Uploads branded image to Bunny CDN
    6. Sends callback with CDN URL
    """
    if not job_id:
        job_id = str(uuid.uuid4())

    print(f"[START] Processing story {job_id}")
    print(f"[INFO] Photo URL: {photo_url}")

    try:
        # Send started event
        if notify_n8n:
            send_n8n_event("story.process.started", {
                "job_id": job_id,
                "photo_url": photo_url,
            })

        # Download photo and logo
        print("[STEP 1] Downloading photo...")
        photo_bytes = download_image(photo_url)
        print(f"[OK] Photo downloaded: {len(photo_bytes)} bytes")

        print("[STEP 2] Downloading logo...")
        logo_bytes = download_image(LOGO_CDN_URL)
        print(f"[OK] Logo downloaded: {len(logo_bytes)} bytes")

        # Process image
        print("[STEP 3] Processing image (resize + logo overlay)...")
        processed_bytes = process_image(photo_bytes, logo_bytes)
        print(f"[OK] Processed image: {len(processed_bytes)} bytes")

        # Upload to Bunny CDN
        print("[STEP 4] Uploading to Bunny CDN...")
        filename = f"story_{job_id}.png"
        cdn_url = upload_to_bunny(processed_bytes, filename)

        # Build success result
        result = {
            "success": True,
            "status": "completed",
            "job_id": job_id,
            "cdn_url": cdn_url,
            "photo_url": photo_url,
            "message": "Story image processed and uploaded successfully.",
        }

        # Send completed event
        if notify_n8n:
            send_n8n_event("story.process.completed", result)

        # Send callback
        if callback_url:
            send_callback(callback_url, result)

        print(f"[DONE] Story {job_id} processed successfully: {cdn_url}")
        return result

    except Exception as e:
        error_result = {
            "success": False,
            "status": "failed",
            "job_id": job_id,
            "error": str(e),
            "photo_url": photo_url,
            "message": f"Story processing failed: {str(e)}",
        }

        if notify_n8n:
            send_n8n_event("story.process.failed", error_result)

        if callback_url:
            send_callback(callback_url, error_result)

        print(f"[ERROR] Story {job_id} failed: {str(e)}")
        return error_result


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def process_story_webhook(data: dict) -> dict:
    """
    Web endpoint for n8n to call - ASYNC VERSION

    Returns immediately with job acceptance status.
    Sends webhook callback when processing completes.

    Expected payload from n8n:
    {
        "photo_url": "https://techopssocialmedia.b-cdn.net/photos/example.jpg",
        "callback_url": "https://n8n1.reformchiropractic.app/webhook/story-callback",
        "job_id": "optional-n8n-execution-id",
        "notify_n8n": true
    }
    """
    photo_url = data.get("photo_url")
    callback_url = data.get("callback_url")
    job_id = data.get("job_id")
    notify_n8n = data.get("notify_n8n", True)

    # Validate required fields
    if not photo_url:
        return {
            "accepted": False,
            "status": "error",
            "error_code": "missing_photo_url",
            "message": "photo_url is required",
        }

    if not callback_url:
        return {
            "accepted": False,
            "status": "error",
            "error_code": "missing_callback_url",
            "message": "callback_url is required for async processing",
        }

    # Use provided job_id or generate one
    if not job_id:
        job_id = str(uuid.uuid4())

    # Spawn async processing (non-blocking)
    process_story.spawn(
        photo_url=photo_url,
        callback_url=callback_url,
        job_id=job_id,
        notify_n8n=notify_n8n,
    )

    # Return immediately with acceptance
    return {
        "accepted": True,
        "status": "processing",
        "job_id": job_id,
        "message": "Story processing accepted. You will receive a webhook callback when complete.",
        "callback_url": callback_url,
    }


@app.local_entrypoint()
def main():
    """
    Local test entrypoint
    Usage: modal run execution/modal_story_processor.py
    """
    # Test with a real photo from Bunny CDN
    test_result = process_story.remote(
        photo_url="https://techopssocialmedia.b-cdn.net/Photos/howdy.jpeg",
        callback_url=None,
        job_id="test-local",
        notify_n8n=False,
    )
    print(f"\nTest result: {test_result}")
