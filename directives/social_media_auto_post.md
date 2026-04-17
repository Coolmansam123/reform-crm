# Social Media Auto-Poster

> Scheduled queue-based posting to Instagram, Facebook, TikTok, and YouTube.

## Architecture

```
Content pipeline completes (video/photo + caption on Bunny CDN)
  → n8n creates ClickUp task (CDN URL stored in "CDN URL" custom field)
  → Staff sets status to "Approved" (first review)
  → clickup_scheduled_handler (Modal) moves Drive file to "3. Ready for Scheduling" + Chat notification
  → Daniel or Ian opens ClickUp, does final review
  → Sets status to "Scheduled" (final approval)
  → clickup_scheduled_handler writes metadata JSON to Bunny Scheduled/
  → clickup_scheduled_handler moves Drive file: "3. Ready for Scheduling" → "4. Scheduled"
  → Hourly cron (run_posting_schedule) checks Bunny Scheduled/
  → Reads Google Sheets: 12 time slots, each with a Category Pool (2-3 categories)
  → For each matching slot: randomly picks from pool categories that have pending content
  → Fallback: if pool is empty, posts oldest available item from any category
  → Content-type routing: photos → Instagram + Facebook only; videos → all 4 platforms
  → After post: Bunny meta archived to Posted/, Drive file → Completed, ClickUp → "Posted"
```

## Cron Status

✅ **Cron is ENABLED** — runs hourly (`0 * * * *`). Deployed Feb 2026.
- YouTube: credentials active, posts as **private** — change `privacyStatus` to `"public"` (line ~668) when ready to go live
- TikTok: placeholder secret in place, posts skipped until real credentials added
- Instagram + Facebook: fully active

## Modal Worker: `execution/modal_social_poster.py`

**App:** `social-poster`

| Endpoint | Method | Purpose |
|---|---|---|
| `https://reformtechops--social-poster-post-to-socials-webhook.modal.run` | POST | Direct post trigger (original flow, still available) |
| `https://reformtechops--social-poster-notify-ready-to-post.modal.run` | POST | Sends Chat notification with ClickUp review link |
| `https://reformtechops--social-poster-move-to-scheduled.modal.run` | POST | Queues content: writes Bunny metadata + moves Drive file |
| `run_posting_schedule` | CRON | Hourly — checks queue, posts matching content |

## notify_ready_to_post Payload

```json
{
  "task_url": "https://app.clickup.com/t/...",
  "task_id": "clickup task id",
  "caption": "GPT-generated caption text",
  "content_type": "photo",
  "category": "Wellness Tip",
  "job_id": "optional"
}
```

## move_to_scheduled Payload

Called by n8n when ClickUp `taskStatusUpdated` fires with status = `"Scheduled"`.

```json
{
  "media_url": "https://techopssocialmedia.b-cdn.net/...",
  "drive_file_id": "Google Drive file ID",
  "caption": "...",
  "content_type": "video|photo",
  "category": "Wellness Tip",
  "task_id": "clickup-task-id",
  "task_url": "https://app.clickup.com/t/..."
}
```

Response:
```json
{
  "success": true,
  "task_id": "...",
  "meta_path": "Scheduled/{task_id}.meta.json",
  "message": "Content queued for scheduled posting."
}
```

## Google Sheets Posting Schedule Config

Sheet: **Social Media Posting Schedule**
Created by: `python execution/create_schedule_sheet.py`
Columns: `Category Pool | Post Days | Post Times | Platforms | Active`

- **Category Pool**: comma-separated list of eligible categories for this time slot (2-3 categories)
- Post Days: comma-separated 3-letter abbreviations (Mon, Tue, Wed, Thu, Fri, Sat, Sun)
- Post Times: comma-separated 24h hours (09:00, 17:00) — cron matches on the hour
- Platforms: comma-separated (instagram, facebook, tiktok, youtube)
- Active: true/false — inactive rows are skipped

Sheet ID stored in Modal secret `google-drive-secrets` as `SCHEDULE_SHEET_ID`.

### Pool-based selection logic

For each time slot that matches the current day + hour:
1. Check which categories in the pool have pending content in Bunny `Scheduled/`
2. Randomly pick one (`random.choice`) — content varies even at the same time slot each week
3. **Fallback:** if no pool category has content, post the globally oldest pending item from any category + send a Google Chat alert

### 12-slot weekly schedule

| Slot | Days | Time (PT) | Category Pool |
|---|---|---|---|
| Mon-A | Mon | 12:00 | Testimonial, Manuthera Showcase, Time-Lapse |
| Mon-B | Mon | 17:00 | P.O.V, Injury Care and Recovery |
| Tue-A | Tue | 10:00 | Doctor Q&A, Informative |
| Tue-B | Tue | 12:00 | Chiropractic ASMR, Wellness Tip |
| Wed-A | Wed | 09:00 | Anatomy and Body Knowledge, Testimonial |
| Wed-B | Wed | 12:00 | P.O.V, Doctor Q&A, Informative |
| Thu-A | Thu | 12:00 | Manuthera Showcase, Time-Lapse |
| Thu-B | Thu | 17:00 | Injury Care and Recovery, Chiropractic ASMR |
| Fri-A | Fri | 12:00 | Testimonial, Wellness Tip |
| Fri-B | Fri | 17:00 | Anatomy and Body Knowledge, P.O.V |
| Sat-A | Sat | 11:00 | Time-Lapse, Doctor Q&A |
| Sat-B | Sat | 12:00 | Informative, Chiropractic ASMR, Manuthera Showcase |

Each category appears in 2-3 pools, so all 10 content types rotate across the week.

### Content-type routing

Photos (`content_type = "photo"`) are automatically restricted to `instagram, facebook` only,
even if the slot's Platforms column lists all 4 platforms. This is enforced in code, not the sheet.
Videos go to all platforms listed in the slot.

## Bunny CDN Folder Structure

| Folder | Contents |
|---|---|
| `Scheduled/` | `{task_id}.meta.json` — pending posts |
| `Posted/` | `{task_id}.meta.json` — archived after posting |
| Other folders | Unchanged (source media files stay in place) |

Media files are NOT moved on Bunny — only lightweight metadata JSONs. The original Bunny CDN URL is preserved in the metadata and used directly for Meta API calls.

## Metadata JSON Structure (Bunny Scheduled/)

```json
{
  "task_id": "...",
  "task_url": "https://app.clickup.com/t/...",
  "media_url": "https://techopssocialmedia.b-cdn.net/...",
  "caption": "...",
  "content_type": "video|photo",
  "category": "Wellness Tip",
  "drive_file_id": "...",
  "scheduled_at": "2026-02-19T10:00:00-08:00",
  "status": "pending|posting|posted|failed",
  "posted_at": "...",
  "post_results": [...],
  "error": "..."
}
```

To retry a failed post: set `status` back to `"pending"` in the `.meta.json` on Bunny.

## Google Drive Folder IDs (Modal secret: `google-drive-secrets`)

### Scheduled (content_type-based routing)

| Variable | Folder | ID |
|---|---|---|
| `DRIVE_SCHEDULED_VIDEOS_FOLDER_ID` | 4. Scheduled/Videos | `11AUk8rnucvdwLhz1BJrDaDZ7oZn3agX7` |
| `DRIVE_SCHEDULED_PHOTOS_FOLDER_ID` | 4. Scheduled/Photos | `1SuMVHjgcpd7f9Xf6vSCn706QgIYJvby-` |

### Completed (category-based routing — stored as JSON in `DRIVE_COMPLETED_FOLDER_IDS`)

| Category | Folder ID |
|---|---|
| Anatomy and Body Knowledge | `1sOyMsjM8ih98KTo8UygzBgq7J_LKvxNW` |
| Chiropractic ASMR | `1qmfAG4_RDxZUj24ELMn6tqh2x6LZYs45` |
| Doctor Q&A | `133FDkxK9UWFjyx-sRKsjKGpjUJird3Ir` |
| Informative | `1c_ZVSOSrKKAhEhwvgXUxmGL0Qrspmez7` |
| Injury Care and Recovery | `1V44KLcauE97DxCtqMYO0rVKQgoGKql2S` |
| Manuthera Showcase | `1DNrq8-QWCUcPkUJfSahNOub63xNY8oKv` |
| P.O.V | `1A-3j1AkXeF7Xj1bFwiYrxyjjgCx8vDJg` |
| Testimonial | `1G4R2irU9VSKsTtCYi23JOrPq-cl-ZMRT` |
| Time-Lapse | `10mfRm0c-AJl6zDcl-Pud4e5Yei3O9m7O` |
| Wellness Tip | `1bcNXPgr1bE3BnDhk-MDxfi-l1-AMJxvj` |

Category names must match exactly what n8n sends in the `category` field. If a category has no mapping, the Drive move is skipped with a warning (non-fatal).

## Modal Secrets Required

| Secret | Keys |
|---|---|
| `meta-secrets` | INSTAGRAM_ACCOUNT_ID, META_PAGE_TOKEN, META_PAGE_ID |
| `n8n-webhook-secrets` | N8N_WEBHOOK_TOKEN, N8N_WEBHOOK_URL |
| `google-chat-social-poster` | GOOGLE_CHAT_SERVICE_ACCOUNT_JSON |
| `bunny-secrets` | BUNNY_STORAGE_API_KEY, BUNNY_ACCOUNT_API_KEY, BUNNY_STORAGE_ZONE, BUNNY_CDN_BASE |
| `google-drive-secrets` | GOOGLE_SERVICE_ACCOUNT_JSON, DRIVE_SCHEDULED_VIDEOS_FOLDER_ID, DRIVE_SCHEDULED_PHOTOS_FOLDER_ID, DRIVE_COMPLETED_FOLDER_IDS, SCHEDULE_SHEET_ID |
| `clickup-api` | CLICKUP_API_KEY |
| `tiktok-secrets` *(Phase B)* | TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_ACCESS_TOKEN, TIKTOK_REFRESH_TOKEN |
| `youtube-secrets` *(Phase B)* | YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN, YOUTUBE_CHANNEL_ID |

## Platform Details

### Instagram (Feed + Reels)
- API: Meta Graph API v22.0
- Flow: Create container → poll status → publish
- Content types: `photo` (single image), `reel`/`video` (Reels up to 90s)
- Media URL must be publicly accessible (Bunny CDN URLs work)
- Rate limit: 25 posts per 24 hours
- Container polling: Photos ~5-10s, Videos up to 5 minutes

### Facebook Page
- API: Meta Graph API v22.0
- Flow: Single POST request
- Content types: `photo` (image), `video` (video upload)

### TikTok (Phase B — Credentials Pending)
- API: TikTok Content Posting API v2
- Flow: Query creator info → download video to /tmp/ → init Direct Post → chunked upload (10MB) → poll status
- Token: Access token expires every ~24h; auto-refreshed using TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET + TIKTOK_REFRESH_TOKEN
- ⚠️ **SELF_ONLY visibility hardcoded** — unaudited apps cannot post publicly. After TikTok audit approval, change `"SELF_ONLY"` → `"PUBLIC_TO_EVERYONE"` in `post_to_tiktok()` and redeploy.
- Photos: NOT supported (TikTok photo carousel requires a separate API flow)
- New Modal secret: `tiktok-secrets` (TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_ACCESS_TOKEN, TIKTOK_REFRESH_TOKEN)
- Blocker: TikTok developer portal login issues (IP geolocation). Create placeholder secret first: `modal secret create tiktok-secrets TIKTOK_CLIENT_KEY="" ...`

### YouTube (Phase B — Google Cloud Project Pending)
- API: YouTube Data API v3
- Flow: Refresh OAuth2 token → download video to /tmp/ → initiate resumable upload → PUT file → return video_id
- Token: Access token expires every 1h; auto-refreshed using YOUTUBE_CLIENT_ID + YOUTUBE_CLIENT_SECRET + YOUTUBE_REFRESH_TOKEN
- Quota: 1,600 units per upload; default 10,000 units/day ≈ 6 videos/day (sufficient for this schedule)
- Privacy: `public`, `selfDeclaredMadeForKids: false`, categoryId: `22` (People & Blogs)
- Photos: NOT supported — YouTube is video-only
- New Modal secret: `youtube-secrets` (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN, YOUTUBE_CHANNEL_ID)
- Blocker: Needs Google Cloud project setup + OAuth consent screen + refresh token from initial manual OAuth flow

## n8n Integration

### In the approval workflow (first approval)
After "Move to Ready for Scheduling folder", add HTTP Request node:
- **URL:** `https://reformtechops--social-poster-notify-ready-to-post.modal.run`
- **Body:** task_url, task_id, caption, content_type, category, job_id

### In the clickup-gateway webhook workflow
Add a branch for `taskStatusUpdated` where status == `"Scheduled"`:
1. Fetch the ClickUp task to get CDN URL, Drive file ID, caption, category, content_type
2. POST to `move_to_scheduled` endpoint with all fields

## Deployment

### Step 1: Create the schedule Google Sheet
```powershell
cd "c:\Users\crazy\Reform Workspace"
python execution/create_schedule_sheet.py
```
Copy the printed sheet ID → paste into `execution/create_drive_secrets.py` line 44 → re-run:
```powershell
python execution/create_drive_secrets.py
```

### Step 2: Create placeholder TikTok + YouTube secrets (allows deploy before real creds)
```powershell
modal secret create tiktok-secrets TIKTOK_CLIENT_KEY="" TIKTOK_CLIENT_SECRET="" TIKTOK_ACCESS_TOKEN="" TIKTOK_REFRESH_TOKEN=""
modal secret create youtube-secrets YOUTUBE_CLIENT_ID="" YOUTUBE_CLIENT_SECRET="" YOUTUBE_REFRESH_TOKEN="" YOUTUBE_CHANNEL_ID=""
```

### Step 3: Enable cron + deploy (when TikTok + YouTube credentials are ready)
In `execution/modal_social_poster.py` line ~1275, uncomment:
```python
schedule=modal.Cron("0 * * * *"),
```
Then:
```powershell
$env:PYTHONUTF8="1"
modal deploy execution/modal_social_poster.py
```

### Step 4: When credentials arrive — update secrets with real values
```powershell
modal secret create tiktok-secrets --force TIKTOK_CLIENT_KEY="<key>" TIKTOK_CLIENT_SECRET="<secret>" TIKTOK_ACCESS_TOKEN="<token>" TIKTOK_REFRESH_TOKEN="<refresh>"
modal secret create youtube-secrets --force YOUTUBE_CLIENT_ID="<id>" YOUTUBE_CLIENT_SECRET="<secret>" YOUTUBE_REFRESH_TOKEN="<refresh>" YOUTUBE_CHANNEL_ID="<channel>"
```
No redeploy needed — secrets are read at runtime.

## Verification

1. **Manual cron trigger:** `modal run -f run_posting_schedule execution/modal_social_poster.py` → verify logs show `[INFO] Loaded 12 active schedule entries`
2. **Pool randomization:** Queue 2+ items in different categories from the same pool. Trigger cron multiple times. Verify different categories post each run.
3. **Fallback:** Empty one pool's categories in Bunny. Trigger cron. Verify: Chat fallback alert fires, oldest item from any category gets posted.
4. **Content-type routing:** Queue a photo item. Verify logs show platform restriction to `[instagram, facebook]` even when slot has all 4 platforms.
5. **End-to-end:** ClickUp task → "Scheduled" → meta in Bunny `Scheduled/` → cron run → post fires → meta in `Posted/` → Drive → Completed → ClickUp → "Posted" → Chat notification
6. **TikTok dry run** (when token available): `post_to_socials.remote(platforms=["tiktok"], ..., dry_run=True)` → creator info query succeeds
7. **YouTube dry run** (when credentials available): `post_to_socials.remote(platforms=["youtube"], ..., dry_run=True)` → token refresh succeeds

## Learnings

- Instagram container polling can take up to 5 minutes for video/Reels
- Media URLs must be publicly accessible — Bunny CDN URLs work perfectly
- Meta Page Token (from `me/accounts`) never expires
- Each platform is posted independently — one failure doesn't block others
- Google Chat notifications use the service account bot pattern (no domain-wide delegation needed)
- Google Chat service account: `socials-poster@celtic-fact-487620-u9.iam.gserviceaccount.com`, posts to `spaces/AAQAgfLjkSY`
- The Bunny CDN URL must be preserved in ClickUp "CDN URL" custom field — it gets replaced by Drive URL in the approval workflow
- Only `.meta.json` files live in Bunny Scheduled/ — source media files stay in their original location
- To retry a failed post: reset `status` to `"pending"` in the meta JSON on Bunny
- Cron matches on the hour — Post Times "09:00" means the 9am cron run picks it up
- Pool-based scheduling: one item per slot per cron run, randomly selected from pool categories with available content
- TikTok requires file upload (not URL) — video is downloaded to /tmp/ first, then chunked upload
- TikTok: SELF_ONLY hardcoded until audit approval — do NOT change to PUBLIC_TO_EVERYONE without completing the TikTok audit process
- YouTube: OAuth2 access tokens expire every 1h — always call refresh_youtube_token() before upload
- YouTube: Single PUT upload works for chiro clips (typically ≤200MB). For longer videos, implement chunked PUT with Content-Range headers.
