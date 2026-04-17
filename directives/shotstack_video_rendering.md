# Shotstack Video Rendering via Modal

> Render videos using Shotstack API with Modal as a reliability layer

## Goal

Use Modal to handle Shotstack API calls with robust error handling, polling, and n8n notifications. n8n handles all orchestration and decision-making (AI agent, template selection), while Modal acts as a reliable worker for the Shotstack API.

## Architecture

**n8n (Brain)** - Orchestration
- Receives intake form data
- AI agent decides template/music/graphics
- Merges placeholders into final Shotstack JSON
- Calls Modal with complete payload + callback_url
- **Gets immediate response** (job accepted/rejected)
- Sets up webhook subworkflow to wait for completion
- Continues with Google Drive upload & ClickUp tasks when webhook fires

**Modal (Worker)** - Async Shotstack Reliability Layer
- **Accepts job immediately** and returns {accepted: true, job_id}
- Spawns async worker to process render in background
- Submits render to Shotstack API
- Polls with retries and timeout handling
- Better error logging
- **Sends POST callback to n8n webhook** when done (success or failure)

**Shotstack** - Video Rendering Service
- Receives render requests from Modal
- Processes video renders (can take 1-30 minutes)
- Returns video URL when complete

## Prerequisites

### Environment Variables (in .env)

The execution script reads all configuration from `.env` file in the project root:

```bash
# Shotstack Configuration
# Production API Key and Endpoint
SHOTSTACK_PRODUCTION_API_KEY=a7ZPiF5pSm0kRFx7OGvCA3cg8QKjcnn72GDNvlLh
SHOTSTACK_PRODUCTION_ENDPOINT=https://api.shotstack.io/v1

# Sandbox API Key and Endpoint (for testing)
SHOTSTACK_SANDBOX_API_KEY=IEA7TNTqdsD1F9OJHRrmTMVgZzNluIkI76SwhKvd
SHOTSTACK_SANDBOX_ENDPOINT=https://api.shotstack.io/stage

# Active Environment (set to 'production' or 'sandbox')
SHOTSTACK_ENVIRONMENT=sandbox

# N8N Integration (already configured)
N8N_WEBHOOK_TOKEN=modal-n8n-9f3c8a7d2e4b6c1f
N8N_WEBHOOK_URL=https://n8n1.reformchiropractic.app/webhook/modal/intake
```

**Important Notes**:
- API keys are sent as `x-api-key` header in HTTP requests (the execution script handles this)
- Variable names in `.env` use `SHOTSTACK_*_API_KEY` for clarity, but get sent as `x-api-key` header
- The script uses `SHOTSTACK_ENVIRONMENT` to auto-select the correct API key + endpoint
- Sandbox is free for testing, production bills per render

### Switching Between Sandbox and Production

**CRITICAL: Endpoint URLs are different:**
- Production: `https://api.shotstack.io/v1`
- Sandbox: `https://api.shotstack.io/stage` (NOT `/stage/v1`)

**To switch to sandbox (for testing):**
```bash
modal secret create shotstack-secrets --force \
  SHOTSTACK_PRODUCTION_API_KEY=<your-prod-key> \
  SHOTSTACK_SANDBOX_API_KEY=<your-sandbox-key> \
  SHOTSTACK_ENVIRONMENT=sandbox

# Then redeploy
PYTHONUTF8=1 modal deploy execution/modal_shotstack_worker.py
```

**To switch back to production:**
```bash
modal secret create shotstack-secrets --force \
  SHOTSTACK_PRODUCTION_API_KEY=<your-prod-key> \
  SHOTSTACK_SANDBOX_API_KEY=<your-sandbox-key> \
  SHOTSTACK_ENVIRONMENT=production

# Then redeploy
PYTHONUTF8=1 modal deploy execution/modal_shotstack_worker.py
```

**Sandbox limitations:**
- Videos have watermark
- Lower priority rendering
- Free and unlimited

### Modal Secrets Required

Modal needs secrets synced from your `.env` file:

```bash
# Create Shotstack secrets from .env (includes both sandbox and production)
modal secret create shotstack-secrets \
  SHOTSTACK_PRODUCTION_API_KEY=$(grep SHOTSTACK_PRODUCTION_API_KEY .env | cut -d '=' -f2) \
  SHOTSTACK_SANDBOX_API_KEY=$(grep SHOTSTACK_SANDBOX_API_KEY .env | cut -d '=' -f2) \
  SHOTSTACK_ENVIRONMENT=$(grep SHOTSTACK_ENVIRONMENT .env | cut -d '=' -f2)

# Create n8n webhook secrets from .env (if not already created)
modal secret create n8n-webhook-secrets \
  N8N_WEBHOOK_TOKEN=$(grep N8N_WEBHOOK_TOKEN .env | cut -d '=' -f2) \
  N8N_WEBHOOK_URL=$(grep N8N_WEBHOOK_URL .env | cut -d '=' -f2)
```

### Tools Required
- `execution/modal_shotstack_worker.py` - Modal Shotstack worker script
- Modal account configured with secrets
- n8n workflow that calls Modal

## Usage

### From n8n Workflow (ASYNC PATTERN)

**New Async Flow:**

```
# Step 1: Submit job to Modal
AI Agent → Merge Fields → HTTP Request to Modal

# Step 2: Modal returns immediately
← {accepted: true, job_id: "abc-123"}

# Step 3: n8n waits on webhook subworkflow
Wait for Webhook (listening on specific URL)

# Step 4: Modal sends callback when done
Modal → POST to callback_url with results

# Step 5: n8n continues
Download video → Upload to Drive → Update ClickUp
```

**n8n HTTP Request Node Configuration:**

- **Method**: POST
- **URL**: `https://reformtechops--shotstack-worker-render-video-webhook.modal.run`
- **Body**:
```json
{
  "shotstack_json": {{ $json }},
  "job_id": "{{ $execution.id }}",
  "metadata": {
    "category": "{{ $('Get Video Info').item.json.category }}",
    "user": "{{ $('Get Video Info').item.json.user }}",
    "task_name": "{{ $('Get Video Info').item.json.name }}"
  },
  "callback_url": "https://n8n1.reformchiropractic.app/webhook/shotstack-callback",
  "notify_n8n": false
}
```

**Important**:
- `callback_url` is REQUIRED. This is where Modal will POST the results.
- `job_id` is OPTIONAL but recommended. Use `{{ $execution.id }}` to track the job with n8n's execution ID. If not provided, Modal will generate a UUID.

**n8n Webhook Subworkflow:**
1. Create a webhook node listening at `/webhook/shotstack-callback`
2. Modal will POST to this URL when render completes
3. Webhook receives:
   - Success: `{success: true, video_url: "...", render_id: "..."}`
   - Failure: `{success: false, error: "...", render_id: "..."}`
4. Switch node to handle success/failure
5. Continue with download/upload on success

### Programmatic Usage

```python
from execution.modal_shotstack_worker import render_video

# Complete Shotstack JSON payload (from n8n AI agent)
shotstack_payload = {
    "timeline": {
        "soundtrack": {
            "src": "https://techopssocialmedia.b-cdn.net/music/track.mp3"
        },
        "tracks": [
            {
                "clips": [
                    {
                        "asset": {
                            "type": "video",
                            "src": "https://techopssocialmedia.b-cdn.net/Videos/source.mp4"
                        },
                        "start": 0,
                        "length": 30
                    }
                ]
            }
        ]
    },
    "output": {
        "format": "mp4",
        "resolution": "hd"
    }
}

# Optional metadata for tracking
metadata = {
    "category": "Doctor POV",
    "user": "Person A",
    "intake_id": "abc123"
}

# Render video
result = render_video.remote(
    shotstack_json=shotstack_payload,
    metadata=metadata,
    notify_n8n=True
)

if result["success"]:
    print(f"Video URL: {result['video_url']}")
    print(f"Render ID: {result['render_id']}")
else:
    print(f"Error: {result['error']}")
```

## Output

### Immediate Response (Job Acceptance)
Modal returns this immediately to n8n:
```json
{
  "accepted": true,
  "status": "processing",
  "job_id": "n8n-execution-12345",
  "message": "Job accepted. You will receive a webhook callback when complete.",
  "callback_url": "https://n8n1.reformchiropractic.app/webhook/shotstack-callback"
}
```

**Note**: `job_id` will be the same ID you provided in the request (e.g., `{{ $execution.id }}`), making it easy to correlate with your n8n execution.

### Webhook Callback (Sent Later)
Modal POSTs this to callback_url when render completes:

**Success (vision category, e.g. Doctor POV):**
```json
{
  "success": true,
  "status": "success",
  "job_id": "n8n-execution-12345",
  "render_id": "shotstack-render-id-123",
  "video_url": "https://shotstack-output.s3.amazonaws.com/video.mp4",
  "url": "https://shotstack-output.s3.amazonaws.com/video.mp4",
  "bunny_cdn_url": "https://techopssocialmedia.b-cdn.net/Videos/Rendered/Doctor-POV_20260218_abc12345.mp4",
  "video_description": "A chiropractor performs cervical adjustments on a patient lying face-up...",
  "attempts": 12,
  "polling_attempts": 15,
  "metadata": {
    "category": "Doctor POV",
    "user": "Person A"
  }
}
```

**Success (transcription category, e.g. Wellness Tip):**
```json
{
  "success": true,
  "status": "success",
  "job_id": "n8n-execution-12345",
  "render_id": "shotstack-render-id-123",
  "video_url": "https://shotstack-output.s3.amazonaws.com/video.mp4",
  "url": "https://shotstack-output.s3.amazonaws.com/video.mp4",
  "bunny_cdn_url": "https://techopssocialmedia.b-cdn.net/Videos/Rendered/Wellness-Tip_20260218_abc12345.mp4",
  "audio_url": "https://techopssocialmedia.b-cdn.net/Audio/extracted/Wellness-Tip_20260218.mp3",
  "video_description": "Staying hydrated supports spinal disc health by maintaining the fluid...",
  "transcription": { "text": "...", "language": "en", "duration": 45.2, "segments": [...] },
  "attempts": 12,
  "polling_attempts": 15,
  "metadata": {
    "category": "Wellness Tip",
    "user": "Person A"
  }
}
```

**Failure:**
```json
{
  "success": false,
  "status": "error",
  "error_code": "render_failed",
  "job_id": "n8n-execution-12345",
  "render_id": "shotstack-render-id-123",
  "error": "Render failed: Invalid source URL",
  "message": "Shotstack render failed after 2 attempts",
  "attempts": 2,
  "metadata": {
    "category": "Doctor POV"
  }
}
```

**Note**: The same `job_id` from your request is returned in the callback, allowing you to match it to the original n8n execution.

## Events Sent to n8n

Following `modal_n8n_integration.md` standards:

### Render Lifecycle Events
- `shotstack.render.started` - Render request initiated
- `shotstack.render.queued` - Shotstack accepted the render
- `shotstack.render.completed` - Render successful, video ready
- `shotstack.render.failed` - Render failed with error

### Event Payload Example
```json
{
  "event": "shotstack.render.completed",
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "data": {
    "render_id": "shotstack-render-id-123",
    "video_url": "https://shotstack-output.s3.amazonaws.com/video.mp4",
    "attempts": 12,
    "metadata": {
      "category": "Doctor POV",
      "user": "Person A"
    }
  }
}
```

## Polling Configuration

Default polling settings (configurable in code):

- **Poll Interval**: 30 seconds
- **Max Attempts**: 60 (30 minutes total)
- **Timeout**: 1 hour function timeout
- **Retry Logic**: Automatic retry on network errors

Adjust in `modal_shotstack_worker.py`:
```python
poll_shotstack_status(
    render_id=render_id,
    api_key=api_key,
    max_attempts=60,      # Change this
    poll_interval=30      # Change this
)
```

## Error Handling

### Common Errors

**401 Unauthorized**
- Check `SHOTSTACK_API_KEY` in Modal secrets
- Verify API key is valid in Shotstack dashboard

**400 Bad Request**
- Shotstack JSON payload is malformed
- Check that source URLs are accessible
- Verify asset types and parameters

**Timeout Error**
- Render took longer than max polling attempts
- Increase `max_attempts` or `poll_interval`
- Check Shotstack dashboard for render status

**Network Errors**
- Modal automatically retries on connection errors
- Check Modal logs for detailed error messages

### Self-Annealing

When errors occur:
1. Check Modal function logs: `modal app logs shotstack-worker`
2. Check n8n webhook execution history
3. Verify Shotstack JSON payload is valid
4. Test with Shotstack's online editor first
5. Check Shotstack dashboard for render details
6. Update this directive with solution

## Testing

### Test Modal Function Locally
```bash
# Run test with sample payload
modal run execution/modal_shotstack_worker.py

# Check logs
modal app logs shotstack-worker
```

### Test n8n Integration
```bash
# 1. Trigger n8n workflow manually
# 2. Check Modal logs for render submission
# 3. Verify n8n receives webhook events
# 4. Check that video downloads successfully
```

### Test Shotstack Payload
Use Shotstack's online editor to validate JSON:
https://shotstack.io/demo/

## Deployment

### Step 1: Configure Modal Secrets
```bash
# Create shotstack-secrets (if not already created)
modal secret create shotstack-secrets \
  SHOTSTACK_PRODUCTION_API_KEY=$(grep SHOTSTACK_PRODUCTION_API_KEY .env | cut -d '=' -f2) \
  SHOTSTACK_SANDBOX_API_KEY=$(grep SHOTSTACK_SANDBOX_API_KEY .env | cut -d '=' -f2) \
  SHOTSTACK_ENVIRONMENT=$(grep SHOTSTACK_ENVIRONMENT .env | cut -d '=' -f2)

# Create n8n-webhook-secrets (if not already created)
modal secret create n8n-webhook-secrets \
  N8N_WEBHOOK_TOKEN=$(grep N8N_WEBHOOK_TOKEN .env | cut -d '=' -f2) \
  N8N_WEBHOOK_URL=$(grep N8N_WEBHOOK_URL .env | cut -d '=' -f2)
```

### Step 2: Deploy Modal Function
```bash
# Deploy as web endpoint
modal deploy execution/modal_shotstack_worker.py

# Modal will output the webhook URL (example):
# https://nick-90891--shotstack-worker-render-video-webhook.modal.run
```

### Step 3: Update n8n Workflow

**n8n Main Workflow:**
1. HTTP Request to Modal
   - URL: `https://nick-90891--shotstack-worker-render-video-webhook.modal.run`
   - Body: `{shotstack_json, metadata, callback_url}`
   - Response: `{accepted: true, job_id: "..."}`

2. (Optional) Wait for Webhook Subworkflow
   - Or trigger separate workflow via webhook

**n8n Webhook Subworkflow:**
1. Webhook Trigger (`/webhook/shotstack-callback`)
2. Switch on `success` field
3. If success: Download video from `video_url`
4. If failure: Send error notification
5. Continue with upload/ClickUp tasks

## Monitoring

### Check Render Status
```bash
# View Modal function logs
modal app logs shotstack-worker

# Check recent executions
modal app list

# View n8n execution history
# Login to n8n → Executions → Filter by workflow
```

### Debug Failed Renders
1. Get job_id from n8n webhook
2. Check Modal logs: `modal app logs shotstack-worker | grep job_id`
3. Get render_id from logs
4. Check Shotstack dashboard with render_id
5. Review error message in webhook payload

## Edge Cases

- **Very long videos (>5 minutes)**: May timeout, increase `max_attempts`
- **Invalid source URLs**: Shotstack returns 400, Modal forwards error to n8n
- **n8n webhook timeout**: Modal continues rendering, n8n can query status later
- **Duplicate renders**: Each call gets unique job_id, safe to retry
- **Rate limits**: Shotstack has rate limits, implement queue if needed
- **Orphaned placeholders (ph*)**: Modal worker converts `999`/`null` to safe defaults
- **Placeholder values burned credits**: NEVER use large numbers - use 0 or let Modal handle

## Automatic Duration Detection & End Card Timing

The shotstack worker now automatically detects video duration and positions end cards correctly:

**How it works:**
1. Worker finds the main video URL in your shotstack_json
2. Uses ffprobe to detect the actual video duration (without downloading)
3. Updates the main video clip's `length` to match the detected duration
4. Repositions any end card/outro clips to start **0.5 seconds before** the video ends
5. End cards get a **fade-in transition** for smooth appearance
6. End cards run for **3 seconds**

**What this means:**
- You no longer need to specify video duration during intake
- End cards automatically appear at the right time
- Transition is smooth (fade in over the last 0.5s of video)

**Clips that are NOT moved:**
- Clips starting at `start: 0` (header/logo overlays that run throughout)
- The main video clip itself

**Example:**
If your video is 45.3 seconds long:
- Main video clip: `length: 45.3`
- End card: `start: 44.8` (0.5s before end), `length: 3`, `transition: {in: "fade"}`

## CRITICAL: Placeholder Values in Templates

**NEVER use large numbers (like 999) as placeholder values for timing fields.**

If a placeholder isn't replaced, large numbers become actual timing values:
- `"start": 999` = video starts at 999 seconds (16+ minutes of blank video)
- `"length": 999` = clip runs for 16+ minutes
- This burns Shotstack credits on useless renders

**Safe approach for n8n Code node:**
```javascript
// Replace orphaned placeholders with 0 (safe default)
dataString = dataString.replace(/\bph[A-Z][a-zA-Z0-9]*\b/g, '0');
dataString = dataString.replace(/"ph[A-Z][a-zA-Z0-9]*"/g, '""');
```

**Why 0 is safe:**
- `start: 0` = clip starts at beginning (correct for main video)
- `length: 0` = gets overwritten by Modal worker's auto-duration detection

**The Modal worker now handles these defensively:**
- Detects `999` or `null` in main video start → sets to 0
- Detects `999` or `null` in end card timing → calculates correct position
- Logs `[CLEANUP]` messages when fixing placeholder values

## Automatic Logo Overlay

The worker automatically injects the Reform Chiropractic logo into every video before rendering:

1. Extracts the first frame of the main video using ffmpeg (fast, no full download)
2. Detects average brightness in the top-right corner region (where logo will appear)
3. If brightness < 128/255 (dark background) → uses white logo; otherwise uses dark logo
4. Injects a logo image track at the top of the Shotstack timeline (so it renders above all content)

**Logo behavior:**
- Position: top-right corner (`position: "topRight"`, offset inward ~2%)
- Scale: `0.1` (≈10% of canvas width = ~192px on 1920px video)
- Duration: full video (`length: "end"`)
- Transition: fade in
- Defaults to white logo if frame sampling fails

**Required Bunny CDN files (upload once):**
- `logos/reform-logo.png` — dark/original logo (for light backgrounds)
- `logos/reform-logo-white.png` — white version (for dark backgrounds)

**Do NOT include a logo clip in Shotstack templates.** The worker injects it dynamically. If a logo clip exists in the template with `length: "end"`, it will be skipped by timing logic but the injected logo will still appear on top.

## Hybrid Captioning System

After render + Bunny upload, the worker auto-generates a `video_description` caption based on the video's category. This replaces the old audio-extraction → Whisper → n8n description generator pipeline.

### Routing Table

| Category | Path | Method |
|---|---|---|
| Doctor POV | Vision | GPT-4o frame analysis |
| Massage POV | Vision | GPT-4o frame analysis |
| Chiropractic ASMR | Vision | GPT-4o frame analysis |
| Manuthera Showcase | Vision | GPT-4o frame analysis |
| Time-Lapse | Skip | No captioning (timelapse) |
| Doctor Q&A | Transcription | Whisper → GPT-4o caption |
| Wellness Tip | Transcription | Whisper → GPT-4o caption |
| Testimonial | Transcription | Whisper → GPT-4o caption |
| Anatomy and Body Care | Transcription | Whisper → GPT-4o caption |
| Injury Care and Recovery | Transcription | Whisper → GPT-4o caption |
| Informative | Transcription | Whisper → GPT-4o caption |

### Vision Path (Doctor POV, Massage POV, etc.)
- Extracts 6 evenly-spaced frames from `main_video_url` (Bunny CDN source — no overlays)
- Skips first/last 1s to avoid title cards
- Sends frames as base64 JPEG to `gpt-4o` with category-aware prompt (`detail: "low"`)
- Returns `video_description` in callback payload

### Transcription Path (Wellness Tip, Doctor Q&A, etc.)
- Extracts audio from rendered Shotstack video
- Transcribes with Whisper (`whisper-1`, verbose_json)
- Sends transcript to `gpt-4o` to write a 2-3 sentence caption
- Returns `video_description` + `transcription` (raw) + `audio_url` in callback

### Callback Payload Fields

| Field | Vision | Transcription | Time-Lapse |
|---|---|---|---|
| `video_description` | GPT-4o from frames | GPT-4o from transcript | absent |
| `transcription` | absent | Raw Whisper JSON | absent |
| `audio_url` | absent | Bunny CDN MP3 URL | absent |
| `bunny_cdn_url` | present | present | present |

### n8n Integration
- `video_description` arrives directly in the Modal callback — **no description generator call needed**
- `transcription` (raw) is included for speech categories in case n8n needs it (subtitles, ClickUp notes, etc.)
- To add a new category: add its lowercase name to `VISION_CATEGORIES` or `TRANSCRIPTION_CATEGORIES` at the top of `modal_shotstack_worker.py`

### Naming Convention Note
Category names use "and" not "/" (e.g. "Anatomy and Body Care" not "Anatomy/Body Care"). The code handles both old (`anatomy/body knowledge`) and new names during transition.

## Learnings

- After render completes, the worker automatically uploads the rendered video to Bunny CDN at `Videos/Rendered/{category}_{date}_{job_id[:8]}.mp4` and includes `bunny_cdn_url` in the callback. Use this URL (not `video_url`) for social posting and the ClickUp "CDN URL" custom field — Shotstack S3 URLs are temporary, Bunny URLs are permanent.
- **NEVER use 999 as placeholder** - it becomes actual timing and burns credits
- Shotstack stage endpoint responses faster than production
- Poll interval of 30s is optimal (not too aggressive)
- Always include metadata for easier debugging
- n8n webhook must be configured BEFORE testing Modal
- Modal timeout should be 2x expected render time
- Shotstack render IDs are permanent, can query anytime
- ffprobe can read video duration from URL without downloading entire file
- End card overlap of 0.5s provides smooth transition without cutting off content

## Comparison: Before vs After

### Before (blocking HTTP in n8n)
- ❌ Timeout issues in n8n (30+ minute renders)
- ❌ HTTP node waits entire render time
- ❌ Complex error handling in workflow
- ❌ Manual polling with Wait nodes
- ❌ Limited retry logic
- ❌ Hard to debug failures

### After (async Modal with webhooks)
- ✅ **Immediate job acceptance** (< 1 second response)
- ✅ n8n can continue with other work or wait on webhook
- ✅ Reliable polling with automatic retries in Modal
- ✅ Better error messages and logging
- ✅ n8n stays lightweight (just orchestration)
- ✅ Can monitor renders in Modal dashboard
- ✅ Easier to add features (queue, priority, etc.)
- ✅ **Webhook callbacks guarantee delivery** (3 retry attempts)
