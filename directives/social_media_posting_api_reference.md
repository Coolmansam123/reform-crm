# Social Media Automatic Posting - API Reference Directive

> Master reference for programmatically posting content to Instagram, YouTube, TikTok, and Facebook Pages via their official APIs. Current as of early 2026.

---

## Table of Contents

1. [Instagram (Feed + Reels) via Meta Graph API](#1-instagram-feed--reels-via-meta-graph-api)
2. [YouTube via YouTube Data API v3](#2-youtube-via-youtube-data-api-v3)
3. [TikTok via Content Posting API](#3-tiktok-via-content-posting-api)
4. [Facebook Page via Graph API](#4-facebook-page-via-graph-api)
5. [Token Management](#5-token-management)
6. [Environment Variables](#6-environment-variables)

---

## 1. Instagram (Feed + Reels) via Meta Graph API

**API Version:** v22.0 (latest stable)
**Base URL:** `https://graph.facebook.com/v22.0`

### Required Environment Variables

- `META_APP_ID`
- `META_APP_SECRET`
- `META_PAGE_ID`
- `META_PAGE_TOKEN`
- `INSTAGRAM_ACCOUNT_ID`

### Required OAuth Scopes/Permissions

- `instagram_basic`
- `instagram_content_publish`
- `pages_show_list`
- `pages_read_engagement`

The Instagram account MUST be a **Business** or **Creator** account linked to a Facebook Page. Creator accounts are NOT supported for content publishing via API.

### Content Types Supported

| Type | Supported | Notes |
|------|-----------|-------|
| Single Image | Yes | JPEG only, max 8MB |
| Carousel (2-10 items) | Yes | Mix of images and videos allowed |
| Reels (Video) | Yes | Up to 90 seconds, MP4, H.264 |
| Stories | Yes | Images or video up to 60 seconds |

### Endpoints

#### Step 1: Create a Media Container

**Single Image Post:**
```
POST /{ig-user-id}/media
  ?image_url={public_image_url}
  &caption={caption_text}
  &access_token={access_token}
```

**Reels (Video) Post:**
```
POST /{ig-user-id}/media
  ?media_type=REELS
  &video_url={public_video_url}
  &caption={caption_text}
  &share_to_feed=true
  &access_token={access_token}
```

**Carousel Post (multi-step):**
```
# Step 1a: Create child containers for each item (2-10 items)
POST /{ig-user-id}/media
  ?image_url={url}        # for image children
  &is_carousel_item=true
  &access_token={access_token}

POST /{ig-user-id}/media
  ?video_url={url}        # for video children
  &media_type=VIDEO
  &is_carousel_item=true
  &access_token={access_token}

# Step 1b: Create the carousel container
POST /{ig-user-id}/media
  ?media_type=CAROUSEL
  &children={child_container_id_1},{child_container_id_2},...
  &caption={caption_text}
  &access_token={access_token}
```

**Story Post:**
```
POST /{ig-user-id}/media
  ?media_type=STORIES
  &image_url={url}        # or video_url for video stories
  &access_token={access_token}
```

#### Step 2: Check Container Status (for video/carousel)

```
GET /{container-id}
  ?fields=status_code
  &access_token={access_token}
```

Possible statuses:
- `FINISHED` - Ready to publish
- `IN_PROGRESS` - Still processing
- `ERROR` - Failed (check `status` field for details)
- `EXPIRED` - Container was not published within 24 hours

**Poll this endpoint** until status is `FINISHED` before publishing. Recommended polling interval: every 5-10 seconds.

#### Step 3: Publish the Container

```
POST /{ig-user-id}/media_publish
  ?creation_id={container-id}
  &access_token={access_token}
```

#### Check Publishing Rate Limit

```
GET /{ig-user-id}/content_publishing_limit
  ?fields=config,quota_usage
  &access_token={access_token}
```

### Rate Limits

- **25 posts per Instagram account per 24-hour rolling window** (carousel counts as 1 post)
- **200 API calls per user per hour** (general Graph API limit)
- Containers expire after **24 hours** if not published

### Key Gotchas

1. Media URLs must be **publicly accessible** (no auth-gated URLs). The API fetches the media from the URL server-side.
2. Video containers require **polling the status** before publishing. Attempting to publish before `FINISHED` will fail.
3. Only **Business** IG accounts are supported. Creator accounts cannot use the Content Publishing API.
4. Image must be JPEG. PNG, GIF, and other formats are not supported.
5. Reels must be MP4 with H.264 encoding, AAC audio, max 90 seconds.
6. The `instagram_content_publish` permission requires **App Review** by Meta before production use.
7. Hashtags count toward caption character limits (2,200 chars max).
8. Carousel child containers must all reach `FINISHED` status before creating the parent carousel container.

---

## 2. YouTube via YouTube Data API v3

**Base URL:** `https://www.googleapis.com/youtube/v3`
**Upload URL:** `https://www.googleapis.com/upload/youtube/v3/videos`

### Required OAuth Scopes

- `https://www.googleapis.com/auth/youtube.upload` - Upload videos
- `https://www.googleapis.com/auth/youtube` - Full account access (needed for thumbnails, playlists)
- `https://www.googleapis.com/auth/youtube.force-ssl` - Full read/write access over SSL

For upload-only use, `youtube.upload` is sufficient. To also set custom thumbnails after upload, you need `youtube` or `youtube.force-ssl`.

### Content Types Supported

| Type | Supported | Notes |
|------|-----------|-------|
| Video Upload | Yes | Most common formats (MP4, MOV, AVI, etc.) |
| Custom Thumbnail | Yes | Separate API call after upload |
| Shorts | Yes | Upload as normal video, <=60s, vertical (9:16) |

### Endpoints

#### Upload a Video (Resumable Upload - Recommended)

**Step 1: Initiate the upload session**
```
POST https://www.googleapis.com/upload/youtube/v3/videos
  ?uploadType=resumable
  &part=snippet,status
Content-Type: application/json
Authorization: Bearer {access_token}

{
  "snippet": {
    "title": "Video Title",
    "description": "Video description",
    "tags": ["tag1", "tag2"],
    "categoryId": "22",
    "defaultLanguage": "en"
  },
  "status": {
    "privacyStatus": "public",      // "public", "private", or "unlisted"
    "selfDeclaredMadeForKids": false,
    "publishAt": "2026-03-01T12:00:00Z"  // optional scheduled publish (requires "private" status)
  }
}
```

Response returns a `Location` header with the upload URI.

**Step 2: Upload the video file**
```
PUT {upload_uri_from_location_header}
Content-Type: video/*
Content-Length: {file_size}

{binary video data}
```

For large files, use chunked upload by sending byte ranges.

#### Set Custom Thumbnail

```
POST https://www.googleapis.com/upload/youtube/v3/thumbnails/set
  ?videoId={video_id}
Content-Type: image/jpeg
Authorization: Bearer {access_token}

{binary image data}
```

Thumbnail requirements: JPEG or PNG, 2MB max, 1280x720 recommended. The channel must be verified to use custom thumbnails.

#### Update Video Metadata (after upload)

```
PUT https://www.googleapis.com/youtube/v3/videos
  ?part=snippet,status
Authorization: Bearer {access_token}

{
  "id": "{video_id}",
  "snippet": {
    "title": "Updated Title",
    "description": "Updated description",
    "tags": ["new_tag"],
    "categoryId": "22"
  }
}
```

### Quota Costs

| Operation | Cost (units) |
|-----------|-------------|
| videos.insert (upload) | 1,600 |
| thumbnails.set | 50 |
| videos.update | 50 |
| videos.list | 1 |

**Default daily quota: 10,000 units per project.** This allows approximately **6 video uploads per day** with the default quota.

To request higher quota:
1. Go to Google Cloud Console > APIs & Services > YouTube Data API v3
2. Submit a Quota Extension Request form
3. Approval is based on use case compliance, not payment

### OAuth Flow

YouTube requires **OAuth 2.0 user consent** (no service account support for uploads). The flow:

1. Redirect user to Google OAuth consent screen
2. User grants permission
3. Receive authorization code
4. Exchange code for access token + refresh token
5. Use refresh token to obtain new access tokens (access tokens expire in 1 hour)

**Refresh tokens do not expire** unless the user revokes access or the app is unverified for >7 days (in testing mode, tokens expire after 7 days; production apps with verified OAuth screen have persistent refresh tokens).

### Rate Limits

- **10,000 quota units per day** (default)
- Quota resets at **midnight Pacific Time**
- No per-minute rate limit for uploads, but large uploads may be throttled by Google

### Key Gotchas

1. **Quota is extremely limited by default.** 6 uploads/day is the ceiling without a quota extension.
2. **OAuth consent screen must be verified** for production. Unverified apps are limited to 100 test users and tokens expire after 7 days.
3. **No service accounts for upload.** You must use OAuth 2.0 with user consent. A headless/automated flow requires storing a refresh token from an initial manual consent.
4. **Custom thumbnails require a verified channel.** New channels may not have this enabled.
5. **Shorts are just regular uploads** that are <=60 seconds and vertical. No separate API endpoint.
6. **Scheduled publishing** requires setting `privacyStatus` to `"private"` and providing a `publishAt` timestamp.
7. **The `madeForKids` field is mandatory.** Failing to set `selfDeclaredMadeForKids` may cause issues.
8. **Resumable upload is strongly recommended** over simple upload for reliability on large files.

---

## 3. TikTok via Content Posting API

**Base URL:** `https://open.tiktokapis.com/v2`
**Developer Portal:** `https://developers.tiktok.com`

### Required OAuth Scopes

| Scope | Purpose |
|-------|---------|
| `video.publish` | Direct Post (fully automated posting) |
| `video.upload` | Upload to drafts (user must manually publish from TikTok app) |
| `user.info.basic` | Required to query creator info before posting |

### Content Types Supported

| Type | Supported | Notes |
|------|-----------|-------|
| Video (Direct Post) | Yes | Requires audit approval for public visibility |
| Video (Upload to Drafts) | Yes | User publishes manually from TikTok |
| Photo Post (Carousel) | Yes | Multiple images as a slideshow |

### Two Posting Modes

#### Mode 1: Direct Post (Fully Automated)

Content goes live on TikTok immediately. Requires `video.publish` scope.

**Step 1: Query Creator Info**
```
POST https://open.tiktokapis.com/v2/post/publish/creator_info/query/
Authorization: Bearer {access_token}
Content-Type: application/json
```

This returns the creator's privacy options, max video duration, and whether they allow comments/duets/stitches.

**Step 2: Initialize Direct Post**
```
POST https://open.tiktokapis.com/v2/post/publish/video/init/
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "post_info": {
    "title": "Video caption",
    "privacy_level": "PUBLIC_TO_EVERYONE",
    "disable_duet": false,
    "disable_comment": false,
    "disable_stitch": false,
    "video_cover_timestamp_ms": 1000
  },
  "source_info": {
    "source": "FILE_UPLOAD",
    "video_size": {file_size_in_bytes},
    "chunk_size": {chunk_size_in_bytes},
    "total_chunk_count": {number_of_chunks}
  }
}
```

Response returns an `upload_url` and `publish_id`.

**Step 3: Upload video chunks to the upload_url**
```
PUT {upload_url}
Content-Type: video/mp4
Content-Range: bytes {start}-{end}/{total}

{binary chunk data}
```

**Step 4: Check publish status**
```
POST https://open.tiktokapis.com/v2/post/publish/status/fetch/
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "publish_id": "{publish_id}"
}
```

#### Mode 2: Upload to Drafts

Content goes to the creator's TikTok drafts. They get a notification and must manually publish. Requires `video.upload` scope.

```
POST https://open.tiktokapis.com/v2/post/publish/inbox/video/init/
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "source_info": {
    "source": "FILE_UPLOAD",
    "video_size": {file_size_in_bytes},
    "chunk_size": {chunk_size_in_bytes},
    "total_chunk_count": {number_of_chunks}
  }
}
```

**Note:** Upload to Drafts does NOT allow setting title, caption, privacy, or any metadata. The user must add all metadata in the TikTok app.

#### Photo Post (Carousel)

```
POST https://open.tiktokapis.com/v2/post/publish/content/init/
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "post_info": {
    "title": "Photo post caption",
    "privacy_level": "PUBLIC_TO_EVERYONE"
  },
  "source_info": {
    "source": "FILE_UPLOAD"
  },
  "post_mode": "DIRECT_POST",
  "media_type": "PHOTO"
}
```

### Rate Limits

- **6 requests per minute** per user access token
- **Unaudited clients:** max 5 unique users can post in a 24-hour window
- **Audited clients:** limits based on usage estimates provided in audit application
- Per-creator daily posting limits apply (varies by creator account)

### Approval / Audit Process

This is the most restrictive platform of the four:

1. **Register as a TikTok Developer** and create an app at developers.tiktok.com
2. **Apply for Content Posting API access** - requires detailed description of use case
3. **Unaudited clients** can only post content with `SELF_ONLY` (private) visibility. Content CANNOT be made public until the app passes audit.
4. **Audit process** verifies compliance with TikTok's Terms of Service and Content Sharing Guidelines
5. Audit approval is required before content can be posted publicly
6. TikTok has made the approval process **stricter in 2025**, requiring more details about app functionality and data usage

### Key Gotchas

1. **Unaudited apps can only post privately.** This is the biggest blocker. All content from unaudited clients is forced to `SELF_ONLY` visibility. You MUST pass the audit to post publicly.
2. **The audit process can take weeks** and TikTok may reject applications.
3. **Draft uploads cannot include metadata.** If using Upload to Drafts mode, users must add title/caption/settings manually in the TikTok app.
4. **You must query Creator Info before every Direct Post** to get the creator's current settings and limits.
5. **OAuth tokens must be refreshed.** TikTok access tokens expire (typically in 24 hours). Refresh tokens last 365 days.
6. **Video requirements:** MP4 or WebM, max 287.6 MB for direct upload, recommended vertical (9:16) aspect ratio.
7. **No scheduling support.** There is no native schedule parameter in the API. You must implement scheduling on your end.
8. **Content Sharing Guidelines are strict.** TikTok can revoke API access if content violates guidelines.

---

## 4. Facebook Page via Graph API

**API Version:** v22.0 (latest stable)
**Base URL:** `https://graph.facebook.com/v22.0`

### Required Environment Variables

- `META_PAGE_ID`
- `META_PAGE_TOKEN` (long-lived / never-expiring page token)

### Required OAuth Scopes/Permissions

- `pages_show_list`
- `pages_read_engagement`
- `pages_manage_posts`
- `pages_read_user_content`
- `publish_video` (for video uploads)

All page posting permissions require **App Review** by Meta for production use.

### Content Types Supported

| Type | Supported | Notes |
|------|-----------|-------|
| Text Post | Yes | Plain text to feed |
| Photo Post | Yes | Single image or via URL |
| Video Post | Yes | Upload or via URL |
| Link Post | Yes | URL with preview card |
| Reels | Yes | Pages only, 3-90 seconds |
| Stories | Yes | Pages only, up to 60 seconds |

### Endpoints

#### Text Post

```
POST /{page-id}/feed
  ?message={text}
  &access_token={page_access_token}
```

#### Photo Post

```
POST /{page-id}/photos
  ?url={public_image_url}
  &message={caption}
  &access_token={page_access_token}
```

Or upload directly:
```
POST /{page-id}/photos
Content-Type: multipart/form-data

  source={file_data}
  &message={caption}
  &access_token={page_access_token}
```

#### Link Post (with preview)

```
POST /{page-id}/feed
  ?message={text}
  &link={url}
  &access_token={page_access_token}
```

#### Video Post

**Simple upload (small videos):**
```
POST /{page-id}/videos
Content-Type: multipart/form-data

  source={file_data}
  &description={description}
  &title={title}
  &access_token={page_access_token}
```

**Resumable upload (large videos):**
```
# Step 1: Start
POST /{page-id}/videos
  ?upload_phase=start
  &file_size={size_in_bytes}
  &access_token={page_access_token}

# Response includes upload_session_id and video_id

# Step 2: Transfer chunks
POST /{page-id}/videos
  ?upload_phase=transfer
  &upload_session_id={session_id}
  &start_offset={offset}
  &access_token={page_access_token}
  (multipart with video_file_chunk)

# Step 3: Finish
POST /{page-id}/videos
  ?upload_phase=finish
  &upload_session_id={session_id}
  &access_token={page_access_token}
```

#### Facebook Reels

```
# Step 1: Initialize
POST /{page-id}/video_reels
  ?upload_phase=start
  &access_token={page_access_token}

# Response includes video_id and upload_url

# Step 2: Upload video binary
POST {upload_url}
Authorization: OAuth {page_access_token}
Content-Type: application/octet-stream

{binary video data}

# Step 3: Publish
POST /{page-id}/video_reels
  ?upload_phase=finish
  &video_id={video_id}
  &description={description}
  &access_token={page_access_token}
```

Reels requirements: 3-90 seconds, vertical recommended, MP4 with H.264, AAC audio.

#### Facebook Stories

```
# Photo story
POST /{page-id}/photo_stories
  ?photo_id={photo_id}
  &access_token={page_access_token}

# Video story
POST /{page-id}/video_stories
  ?video_id={video_id}
  &access_token={page_access_token}
```

Stories on Pages cannot exceed 60 seconds for video.

### Rate Limits

- **200 API calls per user token per hour**
- **600 API calls per app per 600 seconds** (app-level)
- Posting limits vary by page age and engagement history
- Facebook may throttle pages that post too frequently (exact limits undisclosed, but 24-50 posts/day is generally safe)

### Key Gotchas

1. **App Review is mandatory** for `pages_manage_posts` and other page permissions. This can take days to weeks.
2. **Page tokens derived from long-lived user tokens never expire** (see Token Management section below).
3. **Reels are Page-only.** You cannot post Reels to personal accounts or Groups via the API.
4. **Video uploads require the `publish_video` permission** in addition to `pages_manage_posts`.
5. **Link previews are cached.** If you update the OG tags on a URL, you need to scrape the URL again via the Sharing Debugger or `POST /?id={url}&scrape=true`.
6. **Unpublished/scheduled posts:** Use `published=false` and `scheduled_publish_time` (Unix timestamp) to schedule posts.
7. **Photo source vs URL:** When using `url` parameter, the image must be publicly accessible. For private images, use multipart `source` upload.

---

## 5. Token Management

### Meta (Instagram + Facebook) - Long-Lived Page Token

Page access tokens that never expire are essential for automated posting. Here is the process:

**Step 1: Get a short-lived user token**
- Via Facebook Login or Graph API Explorer
- Expires in ~1 hour

**Step 2: Exchange for long-lived user token**
```
GET https://graph.facebook.com/v22.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id={META_APP_ID}
  &client_secret={META_APP_SECRET}
  &fb_exchange_token={short_lived_user_token}
```
- Returns a user token valid for ~60 days

**Step 3: Get the never-expiring page token**
```
GET https://graph.facebook.com/v22.0/me/accounts
  ?access_token={long_lived_user_token}
```
- The `access_token` field in the response for each page is a **never-expiring page token**
- Verify at: https://developers.facebook.com/tools/debug/accesstoken/

**Important:** If the user changes their password, deauthorizes the app, or the app secret changes, the page token is invalidated.

### YouTube - Refresh Token

- Access tokens expire in **1 hour**
- Store the **refresh token** from the initial OAuth flow
- Refresh via:
```
POST https://oauth2.googleapis.com/token
  grant_type=refresh_token
  &refresh_token={refresh_token}
  &client_id={client_id}
  &client_secret={client_secret}
```
- Refresh tokens persist indefinitely for verified production apps
- **For unverified/testing apps, refresh tokens expire after 7 days**

### TikTok - Access + Refresh Tokens

- Access tokens expire in **~24 hours**
- Refresh tokens expire in **365 days**
- Refresh via:
```
POST https://open.tiktokapis.com/v2/oauth/token/
Content-Type: application/x-www-form-urlencoded

  client_key={client_key}
  &client_secret={client_secret}
  &grant_type=refresh_token
  &refresh_token={refresh_token}
```

---

## 6. Environment Variables

The following environment variables should be configured for the automated posting system:

```env
# Meta / Facebook / Instagram
META_APP_ID=
META_APP_SECRET=
META_PAGE_ID=
META_PAGE_TOKEN=                    # Never-expiring page token
INSTAGRAM_ACCOUNT_ID=               # IG Business account ID

# YouTube
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
YOUTUBE_REFRESH_TOKEN=
YOUTUBE_CHANNEL_ID=

# TikTok
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_ACCESS_TOKEN=
TIKTOK_REFRESH_TOKEN=
```

---

## Quick Reference: Platform Comparison

| Feature | Instagram | YouTube | TikTok | Facebook Page |
|---------|-----------|---------|--------|---------------|
| **Image Post** | Yes | No | Yes (carousel) | Yes |
| **Video Post** | Yes (Reels) | Yes | Yes | Yes |
| **Carousel** | Yes (2-10) | No | Yes (photos) | No |
| **Stories** | Yes | No | No | Yes |
| **Scheduling** | No (build your own) | Yes (publishAt) | No (build your own) | Yes (scheduled_publish_time) |
| **Daily Post Limit** | 25/24hrs | ~6 (quota) | Varies | ~24-50 safe |
| **Token Expiry** | Never (page token) | 1hr (refresh available) | 24hrs (refresh available) | Never (page token) |
| **App Review Required** | Yes | Yes (OAuth verification) | Yes (audit for public posting) | Yes |
| **Hardest Part** | Public media URLs | Quota limits | Audit approval | App Review wait time |

---

## Sources

- [Instagram Graph API Complete Developer Guide](https://elfsight.com/blog/instagram-graph-api-complete-developer-guide-for-2026/)
- [Instagram Content Publishing Overview (Medium)](https://datkira.medium.com/instagram-graph-api-overview-content-publishing-limitations-and-references-to-do-quickly-99004f21be02)
- [Instagram Reels API Guide (Phyllo)](https://www.getphyllo.com/post/a-complete-guide-to-the-instagram-reels-api)
- [YouTube Data API v3 - Videos: insert](https://developers.google.com/youtube/v3/docs/videos/insert)
- [YouTube Resumable Uploads](https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol)
- [YouTube Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost)
- [YouTube API Complete Guide 2026](https://getlate.dev/blog/youtube-api)
- [TikTok Content Posting API - Getting Started](https://developers.tiktok.com/doc/content-posting-api-get-started)
- [TikTok Direct Post Reference](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post)
- [TikTok API Rate Limits](https://developers.tiktok.com/doc/tiktok-api-v2-rate-limit)
- [TikTok Content Sharing Guidelines](https://developers.tiktok.com/doc/content-sharing-guidelines)
- [Facebook Reels API (Ayrshare)](https://www.ayrshare.com/facebook-reels-api-how-to-post-fb-reels-using-a-social-media-api/)
- [Facebook Graph API Guide (Data365)](https://data365.co/blog/facebook-graph-api-alternative)
- [Long-Lived Facebook Page Token (GitHub Gist)](https://gist.github.com/msramalho/4fc4bbc2f7ca58e0f6dc4d6de6215dc0)
