"""
Modal-Shotstack Async Worker
Accepts render jobs immediately and processes asynchronously with webhook callbacks

ARCHITECTURE:
1. n8n calls /render_video_webhook with shotstack_json + callback_url
2. Modal accepts job immediately, returns {accepted: true, job_id: ...}
3. Modal spawns async worker to process render
4. n8n continues with other work or waits on webhook subworkflow
5. When render completes, Modal sends POST to callback_url with results
6. n8n webhook receives completion and continues workflow
"""

import modal
import requests
import uuid
import os
import time
import subprocess
import json
import tempfile
import re
from io import BytesIO
from typing import Dict, Any, List, Optional, Tuple
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


# Create Modal app
app = modal.App("shotstack-worker")

# Create Modal image with required dependencies (includes ffprobe for duration detection)
image = (
    modal.Image.debian_slim()
    .apt_install("ffmpeg")
    .pip_install("requests", "fastapi", "openai>=1.0.0", "Pillow")
)

# Reform Chiropractic logo URLs on Bunny CDN
# Dark logo (original) - used on light backgrounds
LOGO_DARK_CDN_URL = "https://techopssocialmedia.b-cdn.net/logos/reform-logo.png"
# White logo (inverted) - used on dark backgrounds
LOGO_WHITE_CDN_URL = "https://techopssocialmedia.b-cdn.net/logos/reform-logo-white.png"

# Captioning routing: category → which post-processing path to use
VISION_CATEGORIES = {
    "doctor pov", "massage pov", "chiropractic asmr", "manuthera showcase"
}
TRANSCRIPTION_CATEGORIES = {
    "doctor q&a", "wellness tip", "testimonial",
    "anatomy and body care", "anatomy/body knowledge",  # handle old + new name
    "injury care and recovery", "about reform", "frequently asked questions"
}

web_app = FastAPI()

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://techopssocialmedia.b-cdn.net"],  # your form origin
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)


def send_n8n_event(event_name: str, data: dict = None):
    """
    Send event to n8n webhook following modal_n8n_integration.md standards

    Args:
        event_name: Event in format system.area.action (e.g., "shotstack.render.completed")
        data: Optional event payload data
    """
    payload = {
        "event": event_name,
        "job_id": str(uuid.uuid4()),
        "data": data if data is not None else {}
    }

    webhook_token = os.getenv("N8N_WEBHOOK_TOKEN")
    webhook_url = os.getenv("N8N_WEBHOOK_URL")

    print(f"DEBUG: webhook_url = {webhook_url}")
    print(f"DEBUG: webhook_token = {webhook_token[:10] if webhook_token else 'None'}...")

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
        print(f"[OK] Event sent: {event_name} (job_id: {payload['job_id']})")
        return response
    except Exception as e:
        print(f"[ERROR] Failed to send event {event_name}: {str(e)}")
        raise


def get_video_duration_from_url(url: str) -> Optional[float]:
    """
    Get video duration from URL using ffprobe without downloading the entire file.
    Returns duration in seconds, or None if unable to determine.
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            url
        ]
        print(f"[FFPROBE] Getting duration for: {url}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout.strip():
            duration = float(result.stdout.strip())
            print(f"[FFPROBE] Duration: {duration:.2f}s")
            return duration
        else:
            print(f"[FFPROBE] Failed to get duration: {result.stderr}")
            return None
    except Exception as e:
        print(f"[FFPROBE] Error: {str(e)}")
        return None


def detect_outro_trim(video_url: str, video_duration: float, check_window: float = 4.0, brightness_threshold: int = 25) -> float:
    """
    Detect CapCut or similar app outro frames at the END of a video.
    Scans the last few seconds for dark frames and returns how many seconds
    to trim from the end (0.0 if no dark outro detected).
    """
    try:
        check_start = max(0, video_duration - check_window)
        frame_width, frame_height, fps = 160, 90, 4
        cmd = [
            "ffmpeg",
            "-ss", str(check_start),
            "-i", video_url,
            "-t", str(check_window),
            "-vf", f"fps={fps},scale={frame_width}:{frame_height}",
            "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)

        if result.returncode != 0 or not result.stdout:
            print(f"[OUTRO] Could not extract frames for outro detection")
            return 0.0

        frame_size = frame_width * frame_height
        raw = result.stdout
        num_frames = len(raw) // frame_size
        frame_interval = 1.0 / fps  # 0.25s per frame

        # Walk forward to find first dark frame — that's where the CapCut outro begins
        for i in range(num_frames):
            frame_bytes = raw[i * frame_size:(i + 1) * frame_size]
            brightness = sum(frame_bytes) / frame_size
            timestamp = check_start + (i * frame_interval)
            print(f"[OUTRO] t={timestamp:.2f}s brightness={brightness:.1f}")

            if brightness < brightness_threshold:
                trim_amount = round(video_duration - timestamp, 2)
                print(f"[OUTRO] Dark outro detected at t={timestamp:.2f}s — trimming last {trim_amount:.2f}s")
                return trim_amount

        print(f"[OUTRO] No dark outro detected")
        return 0.0
    except Exception as e:
        print(f"[OUTRO] Detection failed ({e}) — skipping trim")
        return 0.0


def find_main_video_url(shotstack_json: Dict[str, Any]) -> Optional[str]:
    """
    Find the main video URL in the Shotstack JSON.

    Identifies the main video (not end cards) by looking for:
    1. Videos with start=0 (legitimate start at beginning)
    2. Videos on the last track (bottom layer in Shotstack)
    3. Falls back to first video found if no better match
    """
    if "timeline" not in shotstack_json or "tracks" not in shotstack_json["timeline"]:
        return None

    tracks = shotstack_json["timeline"]["tracks"]
    all_videos = []

    # Collect all video clips with their track index
    for track_idx, track in enumerate(tracks):
        if "clips" not in track:
            continue
        for clip in track["clips"]:
            if "asset" not in clip:
                continue
            asset = clip["asset"]
            if asset.get("type") == "video" and "src" in asset:
                all_videos.append({
                    "url": asset["src"],
                    "start": clip.get("start"),
                    "track_idx": track_idx,
                    "clip": clip
                })

    if not all_videos:
        return None

    # Priority 1: Video with start=0 (not a placeholder)
    for v in all_videos:
        if v["start"] == 0:
            print(f"[MAIN VIDEO] Found video with start=0 on track {v['track_idx']}")
            return v["url"]

    # Priority 2: Video on the LAST track (bottom layer - main content)
    last_track_videos = [v for v in all_videos if v["track_idx"] == len(tracks) - 1]
    if last_track_videos:
        print(f"[MAIN VIDEO] Found video on last track (track {len(tracks) - 1})")
        return last_track_videos[0]["url"]

    # Priority 3: Fall back to first video
    print(f"[MAIN VIDEO] Falling back to first video found")
    return all_videos[0]["url"]


def update_clip_timings(shotstack_json: Dict[str, Any], video_duration: float, main_video_url: str = None) -> Dict[str, Any]:
    """
    Update clip timings in Shotstack JSON based on detected video duration.

    - Updates main video clip length to match actual duration
    - Repositions end card/outro to start when main video ends
    - Keeps existing transition effects (fade in)

    Args:
        shotstack_json: The Shotstack JSON payload
        video_duration: Detected duration of the main video in seconds
        main_video_url: URL of the main video (to match against clips)
    """
    if "timeline" not in shotstack_json or "tracks" not in shotstack_json["timeline"]:
        return shotstack_json

    # Configuration
    outro_overlap = 0.7  # End card starts 0.7s before video ends (smooth crossfade)
    outro_duration = 3.0  # End card runs for 3 seconds

    # First pass: Find and update the main video clip
    # Match by URL if provided, otherwise use same logic as find_main_video_url
    main_video_clip = None
    main_video_end = 0.0
    tracks = shotstack_json["timeline"]["tracks"]

    for track_idx, track in enumerate(tracks):
        if "clips" not in track:
            continue
        for clip in track["clips"]:
            if "asset" not in clip:
                continue
            asset = clip["asset"]
            if asset.get("type") == "video" and "src" in asset:
                clip_url = asset["src"]

                # If main_video_url provided, only match that specific video
                if main_video_url and clip_url != main_video_url:
                    print(f"[TIMING] Skipping video on track {track_idx} (not main video): {clip_url[:50]}...")
                    continue

                # This is the main video clip
                print(f"[TIMING] Found main video on track {track_idx}: {clip_url[:50]}...")
                raw_start = clip.get("start")

                # Fix placeholder values - main video should ALWAYS start at 0
                if raw_start is None or raw_start == 999 or raw_start == 0:
                    if raw_start != 0:
                        print(f"[TIMING] Main video had placeholder start={raw_start}, setting to 0")
                    clip["start"] = 0
                    clip_start = 0
                else:
                    clip_start = raw_start

                # Update length to match actual video duration
                clip["length"] = video_duration
                main_video_end = clip_start + video_duration

                print(f"[TIMING] Main video clip updated: start={clip_start}, length={video_duration:.2f}s, ends at {main_video_end:.2f}s")
                main_video_clip = clip
                break
        if main_video_clip:
            break

    if not main_video_clip or main_video_end <= 0:
        print("[WARNING] No main video clip found - skipping timing updates")
        return shotstack_json

    # Second pass: Reposition end card/outro clips
    for track in shotstack_json["timeline"]["tracks"]:
        if "clips" not in track:
            continue
        for clip in track["clips"]:
            # Skip the main video clip
            if clip is main_video_clip:
                continue

            if "asset" not in clip:
                continue

            # Get RAW values first to detect placeholders
            raw_start = clip.get("start")
            raw_length = clip.get("length")

            # Check for placeholder values (only 999) BEFORE converting
            is_placeholder_start = raw_start == 999
            is_placeholder_length = raw_length == 999

            clip_start = raw_start if raw_start is not None else 0
            clip_length = raw_length

            # Skip clips with length="end" - these are persistent overlays (like logo)
            # that should maintain their original start time and run to the end
            if raw_length == "end":
                print(f"[TIMING] Skipping persistent overlay (length='end') at start={clip_start}")
                continue

            # Skip clips that have NO placeholder values - they have intentional timing
            # (e.g., lower third at start: 3, length: 5 should stay as-is)
            if not is_placeholder_start and not is_placeholder_length:
                print(f"[TIMING] Skipping clip with explicit timing: start={clip_start}, length={clip_length}")
                continue

            # Only reposition clips that have placeholder values (999 or null)
            old_start = clip_start
            old_length = clip_length

            # Position end card to start 0.5s before video ends
            new_start = max(0, main_video_end - outro_overlap)
            clip["start"] = new_start
            clip["length"] = outro_duration

            # Add smooth fade-in transition
            clip["transition"] = {
                "in": "fade"
            }

            print(f"[TIMING] End card repositioned: start {old_start} -> {new_start:.2f}s, length {old_length} -> {outro_duration}s")

    # Final cleanup: replace any remaining placeholder values (999 or null)
    def cleanup_placeholders(obj, default_time=main_video_end):
        """Recursively replace 999 placeholder values with sensible defaults (null values are left as-is)"""
        if isinstance(obj, dict):
            for key, value in list(obj.items()):  # list() to allow modification during iteration
                if value == 999:
                    # Replace timing placeholders with calculated values
                    if key in ("start", "offset"):
                        obj[key] = 0  # Default start to 0
                        print(f"[CLEANUP] Replaced {key}={value} with {obj[key]}")
                    elif key in ("length", "duration"):
                        obj[key] = outro_duration
                        print(f"[CLEANUP] Replaced {key}={value} with {obj[key]}")
                    else:
                        obj[key] = 0  # Safe default for unknown numeric fields
                        print(f"[CLEANUP] Replaced {key}={value} with 0")
                elif isinstance(value, (dict, list)):
                    cleanup_placeholders(value, default_time)
        elif isinstance(obj, list):
            for item in obj:
                cleanup_placeholders(item, default_time)

    cleanup_placeholders(shotstack_json)

    return shotstack_json


def get_first_frame_bytes(video_url: str) -> Optional[bytes]:
    """Extract first frame from video URL as PNG bytes using ffmpeg."""
    try:
        cmd = [
            "ffmpeg",
            "-i", video_url,
            "-vframes", "1",
            "-f", "image2pipe",
            "-vcodec", "png",
            "pipe:1"
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0 and result.stdout:
            print(f"[LOGO] First frame extracted: {len(result.stdout)} bytes")
            return result.stdout
        else:
            print(f"[LOGO] Failed to extract first frame: {result.stderr.decode()[:200]}")
            return None
    except Exception as e:
        print(f"[LOGO] Error extracting first frame: {e}")
        return None


def detect_logo_should_use_white(frame_bytes: bytes) -> bool:
    """
    Detect if the top-right corner of a frame is dark enough to warrant a white logo.
    Returns True if should use white logo, False for dark logo.
    Mirrors the brightness detection logic in modal_story_processor.py.
    """
    from PIL import Image

    img = Image.open(BytesIO(frame_bytes)).convert("L")
    width, height = img.size

    # Sample top-right region where the logo will sit
    region_left = int(width * 0.80)
    region_top = 0
    region_right = width
    region_bottom = int(height * 0.15)

    region = img.crop((region_left, region_top, region_right, region_bottom))
    pixels = list(region.tobytes())
    brightness = sum(pixels) / len(pixels) if pixels else 128

    should_use_white = brightness < 128
    print(f"[LOGO] Top-right brightness: {brightness:.0f}/255 → {'white' if should_use_white else 'dark'} logo")
    return should_use_white


def strip_old_logo_clips(shotstack_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove any old Shotstack-ingested logo clips from the JSON before rendering.
    These come from stale template caches and have a src pointing to
    shotstack-ingest-api-stage-sources.s3.amazonaws.com.
    """
    if "timeline" not in shotstack_json or "tracks" not in shotstack_json["timeline"]:
        return shotstack_json

    cleaned_tracks = []
    for track in shotstack_json["timeline"]["tracks"]:
        cleaned_clips = []
        for clip in track.get("clips", []):
            src = clip.get("asset", {}).get("src", "")
            if "shotstack-ingest-api-stage-sources" in src and clip.get("asset", {}).get("type") == "image":
                print(f"[STRIP] Removed old logo clip: {src[:80]}...")
            else:
                cleaned_clips.append(clip)
        if cleaned_clips:
            cleaned_tracks.append({**track, "clips": cleaned_clips})
        else:
            print(f"[STRIP] Removed empty track after stripping old logo clips")

    shotstack_json["timeline"]["tracks"] = cleaned_tracks
    return shotstack_json


def inject_logo_into_shotstack(shotstack_json: Dict[str, Any], logo_url: str, video_duration: Optional[float] = None) -> Dict[str, Any]:
    """
    Inject a Reform Chiropractic logo overlay track into the Shotstack JSON.
    Placed in the top-right corner, fades in at 3s after the title card clears
    and fades out when the end card starts (video_duration - 0.7s overlap).
    """
    logo_start = 3
    outro_overlap = 0.7
    if video_duration and video_duration > logo_start + outro_overlap:
        logo_length = video_duration - outro_overlap - logo_start
    else:
        logo_length = "end"  # fallback

    logo_track = {
        "clips": [
            {
                "asset": {
                    "type": "image",
                    "src": logo_url
                },
                "start": logo_start,
                "length": logo_length,
                "position": "topRight",
                "offset": {
                    "x": -0.05,
                    "y": -0.03
                },
                "scale": 0.03,
                "opacity": 0.46,
                "transition": {
                    "in": "fade",
                    "out": "fade"
                }
            }
        ]
    }

    if "timeline" in shotstack_json and "tracks" in shotstack_json["timeline"]:
        # Insert at index 0 so the logo renders on top of everything
        shotstack_json["timeline"]["tracks"].insert(0, logo_track)
        print(f"[LOGO] Logo track injected (top-right, start=3, scale=0.03, opacity=0.46): {logo_url}")
    else:
        print("[LOGO] WARNING: No tracks found — skipping logo injection")

    return shotstack_json


def add_logo_overlay(shotstack_json: Dict[str, Any], main_video_url: Optional[str], video_duration: Optional[float] = None) -> Dict[str, Any]:
    """
    Add brightness-adaptive logo overlay to the Shotstack JSON.
    Samples the first frame of the main video to detect background brightness,
    then injects the appropriate logo (white for dark BG, dark for light BG).
    Defaults to white logo if frame sampling fails.
    """
    logo_url = LOGO_WHITE_CDN_URL  # Safe default

    if main_video_url:
        frame_bytes = get_first_frame_bytes(main_video_url)
        if frame_bytes:
            use_white = detect_logo_should_use_white(frame_bytes)
            logo_url = LOGO_WHITE_CDN_URL if use_white else LOGO_DARK_CDN_URL
        else:
            print("[LOGO] Could not sample first frame — defaulting to white logo")
    else:
        print("[LOGO] No main video URL available — defaulting to white logo")

    return inject_logo_into_shotstack(shotstack_json, logo_url, video_duration)


def submit_shotstack_render(shotstack_json: Dict[str, Any], api_key: str, endpoint: str) -> Dict[str, Any]:
    """
    Submit render request to Shotstack API

    Args:
        shotstack_json: Complete Shotstack render JSON payload
        api_key: Shotstack API key
        endpoint: Shotstack API endpoint

    Returns:
        dict with render_id and response data
    """
    url = f"{endpoint}/render"

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }

    response = requests.post(
        url,
        json=shotstack_json,
        headers=headers,
        timeout=30
    )

    # Log detailed error info for debugging
    if not response.ok:
        print(f"[SHOTSTACK ERROR] Status: {response.status_code}")
        print(f"[SHOTSTACK ERROR] Response: {response.text}")

    response.raise_for_status()

    result = response.json()

    return {
        "render_id": result["response"]["id"],
        "status": "queued",
        "message": result["response"].get("message", "Render queued successfully")
    }


def poll_shotstack_status(render_id: str, api_key: str, endpoint: str, max_attempts: int = 60, poll_interval: int = 30) -> Dict[str, Any]:
    """
    Poll Shotstack API for render status with retries

    Args:
        render_id: Shotstack render ID
        api_key: Shotstack API key
        endpoint: Shotstack API endpoint
        max_attempts: Maximum number of polling attempts (default: 60 = 30 minutes)
        poll_interval: Seconds between polls (default: 30)

    Returns:
        dict with final status and video URL or error
    """
    url = f"{endpoint}/render/{render_id}"

    headers = {
        "x-api-key": api_key
    }

    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        print(f"[POLL] Attempt {attempt}/{max_attempts} for render {render_id}")

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            status = result["response"]["status"]

            print(f"[STATUS] Render status: {status}")

            if status == "done":
                return {
                    "status": "done",
                    "url": result["response"]["url"],
                    "render_id": render_id,
                    "attempts": attempt
                }

            elif status == "failed":
                return {
                    "status": "failed",
                    "error": result["response"].get("error", "Render failed"),
                    "render_id": render_id,
                    "attempts": attempt
                }

            elif status in ["queued", "rendering"]:
                # Still processing, wait and retry
                print(f"[WAIT] Status: {status}, waiting {poll_interval}s before next poll")
                time.sleep(poll_interval)
                continue

            else:
                # Unknown status
                print(f"[WARNING] Unknown status: {status}")
                time.sleep(poll_interval)
                continue

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Polling failed on attempt {attempt}: {str(e)}")

            if attempt >= max_attempts:
                raise

            # Wait before retry
            time.sleep(poll_interval)
            continue

    # Max attempts reached
    raise TimeoutError(f"Render polling timed out after {max_attempts} attempts ({max_attempts * poll_interval}s)")


# ============================================================
# Time-lapse functions (auto-detected when category = "Time Lapse")
# ============================================================

def find_videos_to_speedup(shotstack_json: Dict[str, Any], cdn_domain: str = "techopssocialmedia.b-cdn.net") -> List[str]:
    """
    Find video URLs from Bunny CDN that should be sped up.
    Excludes Shotstack ingest URLs (transitions, etc.)
    """
    videos = []
    json_str = json.dumps(shotstack_json)

    pattern = rf'https?://[^"]*{re.escape(cdn_domain)}[^"]*\.mp4'
    matches = re.findall(pattern, json_str, re.IGNORECASE)

    for url in matches:
        if "/TimeLapse/" in url or "/timelapse/" in url:
            print(f"[SKIP] Already a timelapse video: {url}")
            continue
        if url not in videos:
            videos.append(url)
            print(f"[FOUND] Video to speed up: {url}")

    return videos


def download_video(url: str, output_path: str) -> str:
    """Download video from URL to local path"""
    print(f"[DOWNLOAD] Downloading video from {url}")

    response = requests.get(url, stream=True, timeout=300)
    response.raise_for_status()

    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    file_size = os.path.getsize(output_path)
    print(f"[DOWNLOAD] Complete: {file_size / 1024 / 1024:.2f} MB")

    return output_path


def get_video_duration_local(file_path: str) -> float:
    """Get video duration in seconds using ffprobe (local file)"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode == 0 and result.stdout.strip():
        return float(result.stdout.strip())
    return 0.0


def speedup_video_ffmpeg(input_path: str, output_path: str, speed_factor: float = 6.0) -> str:
    """
    Speed up video using FFmpeg.
    Audio is dropped for time-lapse (would sound bad sped up).
    """
    input_duration = get_video_duration_local(input_path)
    expected_output = input_duration / speed_factor
    print(f"[FFMPEG] Input: {input_duration:.2f}s, Speed: {speed_factor}x, Expected output: {expected_output:.2f}s")

    pts_multiplier = 1 / speed_factor

    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-filter:v", f"setpts={pts_multiplier}*PTS",
        "-an",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-y",
        output_path
    ]

    print(f"[FFMPEG] Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)

    if result.returncode != 0:
        print(f"[FFMPEG] STDERR: {result.stderr}")
        raise RuntimeError(f"FFmpeg failed: {result.stderr}")

    output_size = os.path.getsize(output_path)
    output_duration = get_video_duration_local(output_path)
    print(f"[FFMPEG] Complete: {output_size / 1024 / 1024:.2f} MB, duration: {output_duration:.2f}s")

    return output_path


def upload_to_bunny(file_path: str, destination_path: str) -> dict:
    """Upload file to Bunny.net storage zone"""
    bunny_api_key = os.getenv("BUNNY_STORAGE_API_KEY")
    storage_zone = os.getenv("BUNNY_STORAGE_ZONE")
    cdn_base = os.getenv("BUNNY_CDN_BASE")
    storage_region = os.getenv("BUNNY_STORAGE_REGION", "la")

    if not all([bunny_api_key, storage_zone, cdn_base]):
        raise ValueError("Missing Bunny.net configuration")

    with open(file_path, 'rb') as f:
        file_content = f.read()

    upload_url = f"https://{storage_region}.storage.bunnycdn.com/{storage_zone}/{destination_path}"

    headers = {
        "AccessKey": bunny_api_key,
        "Content-Type": "application/octet-stream"
    }

    print(f"[BUNNY] Uploading to {upload_url}")

    response = requests.put(upload_url, data=file_content, headers=headers, timeout=300)
    response.raise_for_status()

    cdn_url = f"{cdn_base.rstrip('/')}/{destination_path}"

    return {
        "success": True,
        "cdn_url": cdn_url,
        "storage_path": destination_path,
        "file_size": len(file_content)
    }


def update_timelapse_clip_lengths(shotstack_json: Dict[str, Any], url_to_duration: Dict[str, float]) -> Dict[str, Any]:
    """
    Update clip lengths in Shotstack JSON to match sped-up video durations.
    Repositions outro/end card clips with placeholder timing.
    """
    if "timeline" not in shotstack_json or "tracks" not in shotstack_json["timeline"]:
        return shotstack_json

    main_video_clip = None
    main_video_end = 0.0

    for track in shotstack_json["timeline"]["tracks"]:
        if "clips" not in track:
            continue
        for clip in track["clips"]:
            if "asset" not in clip:
                continue
            asset = clip["asset"]
            if asset.get("type") == "video" and "src" in asset:
                src_url = asset["src"]
                if src_url in url_to_duration:
                    new_length = url_to_duration[src_url]
                    clip["length"] = new_length
                    clip_start = clip.get("start", 0)
                    main_video_end = clip_start + new_length
                    print(f"[CLIP] Updated video length to {new_length:.2f}s, ends at {main_video_end:.2f}s")
                    main_video_clip = clip
                    break
        if main_video_clip:
            break

    if not main_video_clip or main_video_end <= 0:
        print("[WARNING] No main video clip found to base timing on")
        return shotstack_json

    outro_overlap = 1.0
    outro_duration = 3.0

    for track in shotstack_json["timeline"]["tracks"]:
        if "clips" not in track:
            continue
        for clip in track["clips"]:
            if clip is main_video_clip:
                continue
            if "asset" not in clip:
                continue

            clip_start = clip.get("start", 0)
            clip_length = clip.get("length")

            if clip_length == "end":
                print(f"[TIMING] Skipping persistent overlay (length='end') at start={clip_start}")
                continue

            is_placeholder_start = clip_start == 999
            is_placeholder_length = clip_length == 999

            if not is_placeholder_start and not is_placeholder_length:
                print(f"[TIMING] Skipping clip with explicit timing: start={clip_start}, length={clip_length}")
                continue

            old_start = clip_start
            old_length = clip.get("length", "auto")

            new_start = max(0, main_video_end - outro_overlap)
            clip["start"] = new_start
            clip["length"] = outro_duration
            clip["transition"] = {"in": "fade"}

            print(f"[OUTRO] Repositioned: start {old_start} -> {new_start:.2f}s, length {old_length} -> {outro_duration}s")

    return shotstack_json


def process_videos_for_timelapse(
    shotstack_json: Dict[str, Any],
    temp_dir: str,
    speed_factor: float,
    job_id: str
) -> Tuple[Dict[str, Any], List[str], float]:
    """
    Find videos in Shotstack JSON, speed them up, upload to Bunny, replace URLs.
    Returns updated JSON, list of new timelapse URLs, and total sped-up duration in seconds.
    """
    cdn_domain = os.getenv("BUNNY_CDN_BASE", "techopssocialmedia.b-cdn.net")
    cdn_domain = cdn_domain.replace("https://", "").replace("http://", "").rstrip("/")

    videos_to_process = find_videos_to_speedup(shotstack_json, cdn_domain)

    if not videos_to_process:
        print("[WARNING] No videos from Bunny CDN found to speed up")
        return shotstack_json, [], 0.0

    timelapse_urls = []
    url_to_duration = {}
    json_str = json.dumps(shotstack_json)

    for idx, original_url in enumerate(videos_to_process):
        print(f"\n[PROCESSING] Video {idx + 1}/{len(videos_to_process)}: {original_url}")

        original_path = os.path.join(temp_dir, f"original_{idx}.mp4")
        download_video(original_url, original_path)

        timelapse_path = os.path.join(temp_dir, f"timelapse_{idx}.mp4")
        speedup_video_ffmpeg(original_path, timelapse_path, speed_factor)

        new_duration = get_video_duration_local(timelapse_path)

        destination = f"Videos/TimeLapse/{job_id}_{idx}.mp4"
        upload_result = upload_to_bunny(timelapse_path, destination)
        new_url = upload_result["cdn_url"]
        timelapse_urls.append(new_url)

        url_to_duration[new_url] = new_duration

        print(f"[REPLACED] {original_url} -> {new_url}")
        print(f"[DURATION] Sped-up video: {new_duration:.2f}s")

        json_str = json_str.replace(original_url, new_url)

    updated_json = json.loads(json_str)
    updated_json = update_timelapse_clip_lengths(updated_json, url_to_duration)

    total_duration = sum(url_to_duration.values())
    return updated_json, timelapse_urls, total_duration


# ============================================================
# Post-processing: Audio extraction + Whisper transcription
# (Merged from modal_audio_extractor.py and modal_whisper_transcriber.py)
# ============================================================

def extract_audio_from_url(video_url: str, temp_dir: str, job_id: str, metadata: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    """
    Download rendered video, extract audio to MP3, upload to Bunny CDN.

    Args:
        video_url: URL of the rendered video
        temp_dir: Temporary directory for processing
        job_id: Job ID for logging/naming
        metadata: Optional metadata (uses category for filename)

    Returns:
        dict with {audio_url, audio_path, duration_seconds} or None if no audio track
    """
    from datetime import datetime

    metadata = metadata or {}
    date_str = datetime.utcnow().strftime("%Y%m%d")

    # Build human-readable filename from category
    category = metadata.get("category", "")
    if category:
        safe_category = category.replace(" ", "-").replace("/", "-")
        safe_category = "".join(c for c in safe_category if c.isalnum() or c == "-")
        audio_filename = f"{safe_category}_{date_str}.mp3"
    else:
        audio_filename = f"audio_{date_str}.mp3"

    video_path = os.path.join(temp_dir, f"{job_id}_video.tmp")
    audio_path = os.path.join(temp_dir, audio_filename)

    # Download the rendered video
    print(f"[AUDIO] Downloading rendered video for audio extraction...")
    download_video(video_url, video_path)

    # Extract audio with ffmpeg
    print(f"[AUDIO] Extracting audio to MP3...")
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-ab", "128k",
        "-ar", "44100",
        "-y",
        audio_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        stderr = result.stderr
        if "does not contain any stream" in stderr or "No audio" in stderr:
            print(f"[AUDIO] Video has no audio track — skipping")
        else:
            print(f"[AUDIO] ffmpeg error: {stderr}")
        return None

    audio_size = os.path.getsize(audio_path)
    print(f"[AUDIO] Extracted: {audio_size / 1024:.1f} KB")

    # Get duration
    duration_seconds = get_video_duration_local(audio_path)

    # Upload to Bunny CDN
    bunny_path = f"Audio/extracted/{audio_filename}"
    upload_result = upload_to_bunny(audio_path, bunny_path)

    print(f"[AUDIO] Uploaded to: {upload_result['cdn_url']}")

    return {
        "audio_url": upload_result["cdn_url"],
        "audio_path": audio_path,
        "duration_seconds": duration_seconds,
        "audio_size_bytes": audio_size
    }


def transcribe_audio_whisper(audio_path: str, language: str = "en") -> Optional[Dict[str, Any]]:
    """
    Transcribe a local audio file using OpenAI Whisper API.

    Args:
        audio_path: Path to the local audio file
        language: Language code (default: 'en')

    Returns:
        dict with {text, language, duration, segments} or None on failure
    """
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[WHISPER] OPENAI_API_KEY not configured — skipping transcription")
        return None

    # Check file size (Whisper has 25MB limit)
    file_size = os.path.getsize(audio_path)
    max_size = 25 * 1024 * 1024
    if file_size > max_size:
        print(f"[WHISPER] Audio file too large ({file_size / 1024 / 1024:.2f} MB > 25 MB limit) — skipping")
        return None

    print(f"[WHISPER] Transcribing {file_size / 1024:.1f} KB audio (language: {language})...")

    try:
        client = OpenAI(api_key=api_key)

        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                language=language
            )

        result = {
            "text": transcript.text,
            "language": transcript.language,
            "duration": transcript.duration,
            "segments": [
                {
                    "id": seg.id,
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                }
                for seg in transcript.segments
            ]
        }

        print(f"[WHISPER] Transcription complete: {len(result['text'])} chars, {len(result['segments'])} segments")
        return result

    except Exception as e:
        print(f"[WHISPER] Transcription failed: {e}")
        return None


def analyze_video_frames(
    video_url: str,
    temp_dir: str,
    job_id: str,
    metadata: Dict[str, Any] = None,
    num_frames: int = 6
) -> Optional[str]:
    """
    Extract evenly-spaced frames from source video and send to GPT-4o vision.
    Used for visual categories (Doctor POV, Massage POV, etc.) where speech is absent.
    Uses main_video_url (Bunny CDN source) — no production overlays.
    Returns a natural language caption, or None on failure.
    """
    import base64
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[VISION] OPENAI_API_KEY not configured — skipping vision analysis")
        return None

    duration = get_video_duration_from_url(video_url)
    if not duration or duration <= 0:
        print("[VISION] Could not determine video duration — skipping")
        return None

    # Evenly-spaced timestamps, skip first/last 1s to avoid title cards
    start_offset = min(1.0, duration * 0.05)
    end_offset = max(duration - 1.0, duration * 0.95)
    actual_frames = min(num_frames, max(3, int(duration / 5)))
    timestamps = [
        start_offset + (end_offset - start_offset) * i / max(actual_frames - 1, 1)
        for i in range(actual_frames)
    ]

    frame_paths = []
    for i, ts in enumerate(timestamps):
        frame_path = os.path.join(temp_dir, f"frame_{i:03d}.jpg")
        cmd = [
            "ffmpeg", "-ss", str(ts), "-i", video_url,
            "-vframes", "1", "-q:v", "4", "-y", frame_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode == 0 and os.path.exists(frame_path):
            frame_paths.append(frame_path)
        else:
            print(f"[VISION] Failed to extract frame at {ts:.1f}s")

    if not frame_paths:
        print("[VISION] No frames extracted — skipping vision analysis")
        return None

    print(f"[VISION] Extracted {len(frame_paths)} frames from source video...")

    category = (metadata or {}).get("category", "chiropractic")
    content = [
        {
            "type": "text",
            "text": (
                f"These are {len(frame_paths)} frames sampled evenly from a chiropractic/wellness video "
                f"from Reform Chiropractic. Category: {category}.\n\n"
                "Describe what you observe across the frames: what treatment, exercise, or activity is being "
                "performed, what body area is involved, patient/doctor positioning, and any notable moments.\n\n"
                "Then write a 2-3 sentence natural description suitable as a social media caption. "
                "Be specific, not generic. No hashtags, no emojis, no 'In this video...' opener."
            )
        }
    ]
    for frame_path in frame_paths:
        with open(frame_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"}
        })

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            max_tokens=400
        )
        description = response.choices[0].message.content.strip()
        print(f"[VISION] Description generated: {len(description)} chars")
        return description
    except Exception as e:
        print(f"[VISION] GPT-4o call failed: {e}")
        return None


def generate_caption_from_transcript(
    transcription: Dict[str, Any],
    metadata: Dict[str, Any] = None
) -> Optional[str]:
    """
    Generate a social media caption from a Whisper transcription.
    Used for speech-driven categories (Wellness Tip, Doctor Q&A, etc.).
    Returns a 2-3 sentence caption, or None on failure.
    """
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[CAPTION] OPENAI_API_KEY not configured — skipping caption generation")
        return None

    transcript_text = transcription.get("text", "").strip()
    if not transcript_text:
        print("[CAPTION] Empty transcript — skipping caption generation")
        return None

    category = (metadata or {}).get("category", "wellness")

    prompt = (
        f"This is the transcript from a {category} video by Reform Chiropractic:\n\n"
        f"\"{transcript_text}\"\n\n"
        "Write a 2-3 sentence social media caption based on what was said. "
        "Be specific and informative — capture the key point or advice from the video. "
        "No hashtags, no emojis, no 'In this video...' opener. Write in third person or as a statement."
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        caption = response.choices[0].message.content.strip()
        print(f"[CAPTION] Caption generated from transcript: {len(caption)} chars")
        return caption
    except Exception as e:
        print(f"[CAPTION] GPT-4o call failed: {e}")
        return None


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("shotstack-secrets"),
        modal.Secret.from_name("n8n-webhook-secrets"),
        modal.Secret.from_name("bunny-secrets"),
        modal.Secret.from_name("openai-secret"),
    ],
    timeout=7200  # 2 hour timeout (timelapse needs more time for FFmpeg + upload)
)
def render_video(
    shotstack_json: Dict[str, Any],
    metadata: Dict[str, Any] = None,
    notify_n8n: bool = True,
    callback_url: str = None,
    max_retries: int = 1,
    job_id: str = None,
    speed_factor: float = 6.0
) -> Dict[str, Any]:
    """
    Modal function to render video via Shotstack with retry logic.
    Auto-detects Time Lapse category and speeds up videos accordingly.

    Args:
        shotstack_json: Complete Shotstack render JSON payload
        metadata: Optional metadata to include in n8n events (task info, etc.)
        notify_n8n: Whether to send n8n events (default: True)
        callback_url: Optional callback URL to send result to
        max_retries: Maximum number of retry attempts on failure (default: 1)
        job_id: Optional job ID from n8n (will generate if not provided)
        speed_factor: Speed multiplier for timelapse videos (default: 6.0)

    Returns:
        dict with render results including video URL
    """
    # Use provided job_id or generate one
    if not job_id:
        job_id = str(uuid.uuid4())

    # Get Shotstack configuration
    environment = os.getenv("SHOTSTACK_ENVIRONMENT", "sandbox")
    if environment == "production":
        api_key = os.getenv("SHOTSTACK_PRODUCTION_API_KEY")
        endpoint = os.getenv("SHOTSTACK_PRODUCTION_ENDPOINT", "https://api.shotstack.io/v1")
    else:
        api_key = os.getenv("SHOTSTACK_SANDBOX_API_KEY")
        endpoint = os.getenv("SHOTSTACK_SANDBOX_ENDPOINT", "https://api.shotstack.io/stage")

    if not api_key:
        error_result = {
            "success": False,
            "status": "error",
            "error_code": "missing_api_key",
            "message": f"Shotstack API key not configured for {environment}",
            "job_id": job_id,
            "metadata": metadata or {}
        }
        if callback_url:
            send_callback(callback_url, error_result)
        return error_result

    print(f"[START] Job {job_id} - Environment: {environment}")

    # Check if this is a timelapse job based on metadata category
    category = (metadata or {}).get("category", "")
    is_timelapse = category.lower().replace("-", " ").strip() in ("time lapse", "timelapse")
    timelapse_urls = []
    main_video_url = None  # Used for logo brightness detection
    video_duration = None  # Detected duration, added to result payload

    if is_timelapse:
        # Time-lapse flow: speed up Bunny CDN videos before rendering
        print(f"[TIMELAPSE] Category is 'Time Lapse' - speeding up videos at {speed_factor}x")
        timelapse_duration = 0.0
        # Find main video URL before processing (for logo brightness detection)
        main_video_url = find_main_video_url(shotstack_json)
        with tempfile.TemporaryDirectory() as temp_dir:
            shotstack_json, timelapse_urls, timelapse_duration = process_videos_for_timelapse(
                shotstack_json, temp_dir, speed_factor, job_id
            )
        if timelapse_urls:
            print(f"[TIMELAPSE] Processed {len(timelapse_urls)} video(s)")
        else:
            print("[TIMELAPSE] No videos were processed - submitting original JSON")
    else:
        # Normal flow: auto-detect video duration and update clip timings
        main_video_url = find_main_video_url(shotstack_json)
        if main_video_url:
            print(f"[DURATION] Detecting duration for main video...")
            video_duration = get_video_duration_from_url(main_video_url)
            if video_duration:
                # Detect and strip CapCut/app outro frames from the end
                outro_trim = detect_outro_trim(main_video_url, video_duration)
                if outro_trim > 0:
                    video_duration = video_duration - outro_trim
                    print(f"[OUTRO] Adjusted duration after trim: {video_duration:.2f}s")

                print(f"[DURATION] Detected: {video_duration:.2f}s - updating clip timings")
                shotstack_json = update_clip_timings(shotstack_json, video_duration, main_video_url)
            else:
                print(f"[DURATION] Could not detect duration - using original timings")
        else:
            print(f"[DURATION] No main video found - skipping duration detection")

    # Strip any old Shotstack-ingested logo clips from stale templates (no-op if already clean)
    shotstack_json = strip_old_logo_clips(shotstack_json)

    # Add brightness-adaptive logo overlay (top-right corner, white/dark based on background)
    print(f"[LOGO] Injecting logo overlay...")
    shotstack_json = add_logo_overlay(shotstack_json, main_video_url, video_duration)

    # Retry loop
    for attempt in range(1, max_retries + 2):  # +2 because we want initial + retries
        try:
            print(f"[ATTEMPT] {attempt}/{max_retries + 1}")

            # Send started event
            if notify_n8n and attempt == 1:
                send_n8n_event("shotstack.render.started", {
                    "job_id": job_id,
                    "metadata": metadata or {}
                })

            # Submit render to Shotstack
            submit_result = submit_shotstack_render(shotstack_json, api_key, endpoint)
            render_id = submit_result["render_id"]

            print(f"[OK] Render submitted: {render_id}")

            # Send queued event
            if notify_n8n:
                send_n8n_event("shotstack.render.queued", {
                    "job_id": job_id,
                    "render_id": render_id,
                    "metadata": metadata or {}
                })

            # Poll for completion
            print(f"[POLLING] Starting to poll for render {render_id}")
            poll_start_time = time.time()
            poll_result = poll_shotstack_status(render_id, api_key, endpoint)
            poll_duration = time.time() - poll_start_time
            print(f"[POLLING] Completed after {poll_duration:.1f} seconds")

            if poll_result["status"] == "done":
                result = {
                    "success": True,
                    "status": "success",
                    "job_id": job_id,
                    "render_id": render_id,
                    "video_url": poll_result["url"],
                    "url": poll_result["url"],  # Compatibility
                    "attempts": attempt,
                    "polling_attempts": poll_result["attempts"],
                    "metadata": metadata or {}
                }

                # Add timelapse-specific fields if applicable
                if is_timelapse:
                    result["timelapse_urls"] = timelapse_urls
                    result["speed_factor"] = speed_factor
                    result["duration"] = round(timelapse_duration)
                elif video_duration:
                    result["duration"] = round(video_duration + 2.3)  # +2.3s = end card (3s) - overlap (0.7s)

                # Post-processing: hybrid captioning (vision or transcription based on category)
                if not is_timelapse:
                    try:
                        with tempfile.TemporaryDirectory() as post_dir:
                            category_key = category.lower().strip()

                            if category_key in VISION_CATEGORIES:
                                print(f"[POST] Vision path for '{category}' — analyzing source video frames...")
                                description = analyze_video_frames(
                                    main_video_url, post_dir, job_id, metadata
                                )
                                if description:
                                    result["video_description"] = description
                                    print(f"[POST] Vision description added ({len(description)} chars)")
                                else:
                                    print(f"[POST] No vision description produced")

                            elif category_key in TRANSCRIPTION_CATEGORIES:
                                print(f"[POST] Transcription path for '{category}' — extracting audio...")
                                audio_result = extract_audio_from_url(
                                    poll_result["url"], post_dir, job_id, metadata
                                )
                                if audio_result:
                                    result["audio_url"] = audio_result["audio_url"]
                                    transcription = transcribe_audio_whisper(audio_result["audio_path"])
                                    if transcription:
                                        result["transcription"] = transcription  # raw, for n8n flexibility
                                        description = generate_caption_from_transcript(transcription, metadata)
                                        if description:
                                            result["video_description"] = description
                                            print(f"[POST] Caption generated from transcript ({len(description)} chars)")
                                    else:
                                        print(f"[POST] No transcription produced (Whisper skipped or failed)")
                                else:
                                    print(f"[POST] No audio extracted (video may have no audio track)")

                            else:
                                print(f"[POST] Category '{category}' not in routing table — skipping captioning")

                    except Exception as e:
                        print(f"[POST] Post-processing failed (non-fatal): {e}")
                        # Don't fail the whole job — video rendered successfully

                # Post-processing: upload rendered video to Bunny CDN
                # Gives n8n a permanent public URL (bunny_cdn_url) for social posting.
                # Shotstack S3 URLs are temporary; Bunny URL persists indefinitely.
                try:
                    from datetime import datetime
                    date_str = datetime.utcnow().strftime("%Y%m%d")
                    category = (metadata or {}).get("category", "")
                    if category:
                        safe_cat = "".join(
                            c for c in category.replace(" ", "-").replace("/", "-")
                            if c.isalnum() or c == "-"
                        )
                        video_filename = f"{safe_cat}_{date_str}_{job_id[:8]}.mp4"
                    else:
                        video_filename = f"video_{date_str}_{job_id[:8]}.mp4"

                    print(f"[BUNNY] Uploading rendered video to Bunny CDN: {video_filename}")
                    with tempfile.TemporaryDirectory() as bunny_dir:
                        video_path = os.path.join(bunny_dir, video_filename)
                        download_video(poll_result["url"], video_path)
                        upload_result = upload_to_bunny(video_path, f"Videos/Rendered/{video_filename}")
                        result["bunny_cdn_url"] = upload_result["cdn_url"]
                        print(f"[BUNNY] Rendered video uploaded: {upload_result['cdn_url']}")
                except Exception as e:
                    print(f"[BUNNY] Rendered video upload failed (non-fatal): {e}")
                    # Don't fail — video rendered successfully, Bunny upload is supplemental

                print(f"[OK] Render completed: {poll_result['url']}")

                # Add minimum delay before callback to ensure stability
                # Even if Shotstack says "done", wait a bit for CDN propagation
                min_wait = 5  # 5 seconds minimum
                if poll_duration < min_wait:
                    wait_time = min_wait - poll_duration
                    print(f"[WAIT] Waiting additional {wait_time:.1f}s before callback (min {min_wait}s policy)")
                    time.sleep(wait_time)

                # Send completed event
                if notify_n8n:
                    send_n8n_event("shotstack.render.completed", result)

                # Send callback
                if callback_url:
                    print(f"[CALLBACK] Sending callback to {callback_url}")
                    send_callback(callback_url, result)

                return result

            else:
                # Render failed
                print(f"[ERROR] Render failed: {poll_result.get('error', 'Unknown error')}")

                if attempt < max_retries + 1:
                    print(f"[RETRY] Waiting 10 seconds before retry {attempt + 1}...")
                    time.sleep(10)
                    continue
                else:
                    error_result = {
                        "success": False,
                        "status": "error",
                        "error_code": "render_failed",
                        "job_id": job_id,
                        "render_id": render_id,
                        "error": poll_result.get("error", "Unknown error"),
                        "message": f"Shotstack render failed after {attempt} attempts",
                        "attempts": attempt,
                        "metadata": metadata or {}
                    }

                    # Send failed event
                    if notify_n8n:
                        send_n8n_event("shotstack.render.failed", error_result)

                    # Send callback
                    if callback_url:
                        send_callback(callback_url, error_result)

                    return error_result

        except Exception as e:
            print(f"[ERROR] Exception on attempt {attempt}: {str(e)}")

            if attempt < max_retries + 1:
                print(f"[RETRY] Waiting 10 seconds before retry {attempt + 1}...")
                time.sleep(10)
                continue
            else:
                error_result = {
                    "success": False,
                    "status": "error",
                    "error_code": "processing_error",
                    "job_id": job_id,
                    "error": str(e),
                    "message": f"Error after {attempt} attempts: {str(e)}",
                    "attempts": attempt,
                    "metadata": metadata or {}
                }

                # Send failed event
                if notify_n8n:
                    send_n8n_event("shotstack.render.failed", error_result)

                # Send callback
                if callback_url:
                    send_callback(callback_url, error_result)

                return error_result


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
                time.sleep(5)  # Wait 5s before retry
            else:
                print(f"[FATAL] Callback failed after {max_attempts} attempts")
                return False


@web_app.post("/")
async def render_video_webhook(request: Request):
    data = await request.json()

    shotstack_json = data.get("shotstack_json")
    metadata = data.get("metadata") or data.get("context") or {}
    notify_n8n = data.get("notify_n8n", False)
    callback_url = data.get("callback_url")
    max_retries = data.get("max_retries", 1)
    speed_factor = data.get("speed_factor", 6.0)
    job_id = metadata.get("job_id") or data.get("job_id")

    if not shotstack_json:
        return JSONResponse(
            {
                "accepted": False,
                "status": "error",
                "error_code": "missing_shotstack_json",
                "message": "shotstack_json is required",
            },
            status_code=400,
        )

    if not callback_url:
        return JSONResponse(
            {
                "accepted": False,
                "status": "error",
                "error_code": "missing_callback_url",
                "message": "callback_url is required for async processing",
            },
            status_code=400,
        )

    if not job_id:
        job_id = str(uuid.uuid4())

    render_video.spawn(
        shotstack_json=shotstack_json,
        metadata=metadata,
        notify_n8n=notify_n8n,
        callback_url=callback_url,
        max_retries=max_retries,
        job_id=job_id,
        speed_factor=speed_factor,
    )

    return {
        "accepted": True,
        "status": "processing",
        "job_id": job_id,
        "message": "Job accepted. You will receive a webhook callback when complete.",
        "callback_url": callback_url,
    }


@app.function(image=image)
@modal.asgi_app()
def web():
    return web_app


@app.local_entrypoint()
def main():
    """
    Local test entrypoint
    Usage: modal run execution/modal_shotstack_worker.py
    """
    # Test payload
    test_payload = {
        "timeline": {
            "soundtrack": {
                "src": "https://shotstack-assets.s3-ap-southeast-2.amazonaws.com/music/unminus/lit.mp3"
            },
            "tracks": [
                {
                    "clips": [
                        {
                            "asset": {
                                "type": "video",
                                "src": "https://shotstack-assets.s3-ap-southeast-2.amazonaws.com/footage/skater.hd.mp4"
                            },
                            "start": 0,
                            "length": 3
                        }
                    ]
                }
            ]
        },
        "output": {
            "format": "mp4",
            "resolution": "sd"
        }
    }

    print("[TEST] Running Shotstack render test...")
    result = render_video.remote(
        shotstack_json=test_payload,
        metadata={"test": True, "source": "local_test"}
    )

    if result["success"]:
        print(f"\n[OK] Test render successful!")
        print(f"  Video URL: {result['video_url']}")
        print(f"  Render ID: {result['render_id']}")
        print(f"  Job ID: {result['job_id']}")
        print(f"  Polling attempts: {result['attempts']}")
    else:
        print(f"\n[ERROR] Test render failed!")
        print(f"  Error: {result['error']}")
        import sys
        sys.exit(1)
