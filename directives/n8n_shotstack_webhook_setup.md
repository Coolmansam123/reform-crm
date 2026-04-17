# n8n Shotstack Webhook Setup Guide

> How to set up webhooks in n8n to receive async results from Modal Shotstack Worker

## Architecture

```
Main Workflow                    Modal Worker              Callback Workflow
─────────────                    ────────────              ─────────────────
│                                     │                           │
│ Build Shotstack JSON                │                           │
│                                     │                           │
│ POST to Modal ────────────────────▶ │                           │
│ (with callback_url)                 │                           │
│                                     │                           │
│ ◀────────────── {accepted: true}    │                           │
│                                     │                           │
│ [Workflow ends or continues]        │                           │
│                                     │                           │
│                                     │ [Rendering 1-30 min...]   │
│                                     │                           │
│                                     │                           │
│                                     │ POST callback ───────────▶│
│                                     │                           │
│                                     │                           │ Process result
│                                     │                           │ Download video
│                                     │                           │ Upload to CDN
│                                     │                           │ Update ClickUp
│                                     │                           │
│                                     │                           ▼
│                                     │                      [Complete]
```

## Setup Instructions

### Step 1: Create Callback Webhook Workflow

**Workflow Name**: `Shotstack - Callback Handler`

#### 1.1 Webhook Trigger Node
```
Name: Webhook Trigger
Webhook URLs: Production URL
HTTP Method: POST
Path: shotstack-callback
Authentication: None (or add header auth if desired)
Response Mode: Immediately
Response Code: 200
Response Data: Success
```

**Get the webhook URL**:
After saving, n8n will show you the production URL:
`https://n8n1.reformchiropractic.app/webhook/shotstack-callback`

Copy this URL - you'll use it in the main workflow.

#### 1.2 Set Node (Extract Data)
```javascript
// Clean up the incoming data
{
  "success": "={{ $json.success }}",
  "job_id": "={{ $json.job_id }}",
  "render_id": "={{ $json.render_id }}",
  "video_url": "={{ $json.video_url }}",
  "error": "={{ $json.error }}",
  "metadata": "={{ $json.metadata }}"
}
```

#### 1.3 Switch Node (Branch on Success)
```
Name: Check Success
Mode: Rules

Rule 1 (Success):
  - Conditions: {{ $json.success }} = true
  - Output: 0 (Success)

Rule 2 (Failure):
  - Conditions: {{ $json.success }} = false
  - Output: 1 (Failure)
```

#### 1.4a Success Branch

**HTTP Request - Download Video**
```
URL: {{ $json.video_url }}
Method: GET
Response Format: File
Download File Name: {{ $json.job_id }}.mp4
```

**Code Node - Prepare Upload** (Optional)
```javascript
// Add any transformations or metadata
return {
  video_data: $binary,
  filename: `${$json.metadata.category}_${$json.job_id}.mp4`,
  job_id: $json.job_id,
  render_id: $json.render_id
};
```

**HTTP Request - Upload to Bunny CDN**
```
URL: https://storage.bunnycdn.com/techopssocialmedia/Videos/{{ $json.filename }}
Method: PUT
Authentication: Generic Credential Type
  Header Name: AccessKey
  Value: {{ $env.BUNNY_STORAGE_API_KEY }}
Body Content Type: Binary File
Binary Property: video_data
```

**Set Node - Build Result**
```javascript
{
  "success": true,
  "job_id": "={{ $json.job_id }}",
  "cdn_url": "=https://techopssocialmedia.b-cdn.net/Videos/{{ $json.filename }}",
  "shotstack_url": "={{ $json.video_url }}"
}
```

**HTTP Request - Update ClickUp** (Optional)
```javascript
// Update task with video URL
{
  url: 'https://api.clickup.com/api/v2/task/TASK_ID/field/FIELD_ID',
  method: 'POST',
  headers: {
    'Authorization': $env.CLICKUP_API_KEY,
    'Content-Type': 'application/json'
  },
  body: {
    value: $json.cdn_url
  }
}
```

#### 1.4b Failure Branch

**Code Node - Format Error**
```javascript
return {
  error: true,
  job_id: $json.job_id,
  render_id: $json.render_id,
  error_code: $json.error_code,
  error_message: $json.error,
  message: $json.message,
  metadata: $json.metadata
};
```

**Send Email / Slack Notification**
```
To: team@reformchiropractic.com
Subject: Shotstack Render Failed - {{ $json.job_id }}
Body:
  Render failed for job {{ $json.job_id }}

  Error: {{ $json.error_message }}
  Error Code: {{ $json.error_code }}

  Metadata:
  {{ JSON.stringify($json.metadata, null, 2) }}

  Please check Modal logs for details.
```

**Activate Workflow** ✅

---

### Step 2: Update Main Workflow

In your existing video rendering workflow:

#### 2.1 Update HTTP Request to Modal

Replace your existing Shotstack HTTP node with:

```
Node: HTTP Request
URL: https://reformtechops--shotstack-worker-render-video-webhook.modal.run
Method: POST
Body Content Type: JSON

Body:
{
  "shotstack_json": {{ $json }},
  "job_id": "{{ $execution.id }}",
  "callback_url": "https://n8n1.reformchiropractic.app/webhook/shotstack-callback",
  "metadata": {
    "category": "{{ $json.category }}",
    "user": "{{ $json.user }}",
    "execution_id": "{{ $execution.id }}",
    "workflow_id": "{{ $workflow.id }}"
  }
}
```

#### 2.2 Handle Response

**Set Node - Extract Job Info**
```javascript
{
  "submitted": true,
  "job_id": "={{ $json.job_id }}",
  "status": "={{ $json.status }}",
  "message": "={{ $json.message }}"
}
```

**IF Node - Check Acceptance**
```
Condition: {{ $json.accepted }} = true
True: Continue workflow or end
False: Handle rejection error
```

---

### Step 3: Test the Setup

#### 3.1 Test Webhook Callback Manually

Use curl or Postman to test the webhook:

```bash
curl -X POST https://n8n1.reformchiropractic.app/webhook/shotstack-callback \
  -H "Content-Type: application/json" \
  -d '{
    "success": true,
    "job_id": "test-123",
    "render_id": "shotstack-abc",
    "video_url": "https://shotstack-output.s3.amazonaws.com/test.mp4",
    "metadata": {
      "test": true
    }
  }'
```

Check that:
- Webhook receives the data ✓
- Success branch executes ✓
- Video downloads (if URL is real) ✓

#### 3.2 Test with Modal Worker

Submit a real render job:

```bash
curl -X POST https://reformtechops--shotstack-worker-render-video-webhook.modal.run \
  -H "Content-Type: application/json" \
  -d '{
    "shotstack_json": {
      "timeline": {
        "tracks": [{
          "clips": [{
            "asset": {
              "type": "video",
              "src": "https://shotstack-assets.s3-ap-southeast-2.amazonaws.com/footage/skater.hd.mp4"
            },
            "start": 0,
            "length": 3
          }]
        }]
      },
      "output": {
        "format": "mp4",
        "resolution": "sd"
      }
    },
    "job_id": "test-render-123",
    "callback_url": "https://n8n1.reformchiropractic.app/webhook/shotstack-callback"
  }'
```

Monitor:
1. Modal logs: `python -m modal app logs shotstack-worker`
2. n8n execution history for callback workflow
3. Check that video is downloaded and uploaded

---

## Advanced: Track Job State (Optional)

If you want to track job status between submission and callback:

### Add State Tracking Table

Create a simple state tracker (Google Sheets, Postgres, etc):

| job_id | status | submitted_at | completed_at | video_url | error |
|--------|--------|--------------|--------------|-----------|-------|
| n8n-123 | rendering | 2026-01-14 10:00 | NULL | NULL | NULL |

### Update Main Workflow - Store Job

After submitting to Modal:
```javascript
// Store job submission
await $http.request({
  url: 'YOUR_STATE_API/jobs',
  method: 'POST',
  body: {
    job_id: $json.job_id,
    status: 'rendering',
    submitted_at: new Date(),
    metadata: $json.metadata
  }
});
```

### Update Callback Workflow - Update State

In webhook callback:
```javascript
// Update job status
await $http.request({
  url: `YOUR_STATE_API/jobs/${$json.job_id}`,
  method: 'PATCH',
  body: {
    status: $json.success ? 'completed' : 'failed',
    completed_at: new Date(),
    video_url: $json.video_url,
    error: $json.error
  }
});
```

Now you can query job status anytime:
```
GET /jobs/n8n-123
→ { status: 'rendering', submitted_at: '...' }
```

---

## Troubleshooting

### Webhook Not Receiving Callbacks

**Check 1: Webhook URL is correct**
```bash
# Get your webhook URL from n8n
# Should be: https://n8n1.reformchiropractic.app/webhook/shotstack-callback

# Test it's accessible
curl https://n8n1.reformchiropractic.app/webhook/shotstack-callback
# Should return 200 OK (webhook waiting for POST)
```

**Check 2: Webhook workflow is active**
- n8n UI → Workflows → "Shotstack - Callback Handler"
- Status should show "Active" toggle ON

**Check 3: Modal has correct callback_url**
- Check Modal logs: `python -m modal app logs shotstack-worker`
- Look for: `[OK] Callback sent to https://...`

**Check 4: Firewall / Network**
- Ensure n8n is accessible from internet
- Modal needs to POST to your n8n instance

### Callback Received but Workflow Fails

**Check execution history**:
- n8n UI → Executions
- Find the failed webhook execution
- Click to see error details

**Common issues**:
- Video URL expired or invalid
- Upload credentials wrong
- Missing required fields in $json

### Video Download Fails

**Check video URL**:
```javascript
// Add logging before download
console.log('Video URL:', $json.video_url);

// Test URL directly
curl -I {{ $json.video_url }}
# Should return 200 OK
```

**Shotstack URLs expire**: Download within 24 hours

---

## Production Checklist

Before going live:

- [ ] Webhook workflow created and activated
- [ ] Webhook URL copied to main workflow
- [ ] Tested manual webhook POST (success case)
- [ ] Tested manual webhook POST (failure case)
- [ ] Tested full flow with real Shotstack render
- [ ] Video downloads successfully
- [ ] Video uploads to CDN successfully
- [ ] Error notifications working
- [ ] Modal logs show successful callbacks
- [ ] n8n execution history shows clean runs

---

## Summary

**Main Workflow**: Submits job → Gets immediate acceptance → Ends (or continues)

**Modal Worker**: Processes async → Polls Shotstack → Sends webhook when done

**Callback Workflow**: Receives result → Downloads video → Uploads to CDN → Updates ClickUp

Clean separation of concerns, no timeouts, reliable delivery! 🎯
