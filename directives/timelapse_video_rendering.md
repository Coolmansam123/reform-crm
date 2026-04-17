# Time-lapse Video Rendering via Modal

> **Status: Absorbed** — Time-lapse functionality is handled by `modal_shotstack_worker.py`. There is no separate timelapse worker.

## How It Works

Time-lapse rendering goes through the same Shotstack worker as regular videos. The FFmpeg 6x speed-up post-processing was consolidated into `modal_shotstack_worker.py`.

**Worker:** `execution/modal_shotstack_worker.py`

## Architecture

```
n8n (Brain)
    │
    ├── Receives intake form with "Time Lapse" / "Time-Lapse" category
    ├── AI agent decides template/music/graphics
    ├── Merges placeholders into Shotstack JSON
    ├── Calls Modal shotstack worker endpoint (with speed_factor param)
    │
    ▼
Modal (modal_shotstack_worker.py)
    │
    ├── Accepts job immediately → returns {accepted: true}
    ├── Submits to Shotstack API
    ├── Polls until render complete
    ├── Downloads rendered video
    ├── FFmpeg: speeds up 6x (removes audio)
    ├── Uploads to Bunny CDN
    ├── Sends callback to n8n
    │
    ▼
n8n (Continues)
    │
    └── Downloads from Bunny CDN → Upload to Drive → Update ClickUp
```

## FFmpeg Speed-Up

```bash
ffmpeg -i input.mp4 \
  -filter:v "setpts=0.166667*PTS" \
  -an \
  -c:v libx264 \
  -preset fast \
  -crf 23 \
  output.mp4
```

- `setpts=0.166667*PTS`: Divides timestamps by 6 (6x faster)
- `-an`: Removes audio (sounds terrible at 6x)
- Time-lapse videos have no audio — add music in Shotstack if needed

## n8n Integration Notes

- Category matching supports: `"Time Lapse"`, `"Time-Lapse"`, `"timelapse"` — n8n currently sends `"Time-Lapse"` (with hyphen)
- Pass `speed_factor: 6.0` in the payload to trigger speed-up
- Same callback structure as regular Shotstack jobs, with additional fields:
  - `original_url`: Pre-speedup Shotstack URL
  - `speed_factor`: Applied speed multiplier

## Learnings

- Audio is removed for time-lapse (add music in Shotstack if needed)
- FFmpeg processing adds ~30-60 seconds depending on video length
- Bunny CDN URLs are permanent (unlike Shotstack's temporary S3 URLs)
- 6x speed means a 5-minute video becomes 50 seconds
- Very long videos may timeout; increase Modal timeout or split video
