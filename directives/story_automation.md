# Story Automation - Photo Branding Pipeline

> Adds Reform Chiropractic logo overlay to photos during the n8n intake flow, before ClickUp review.

## Architecture

```
Photo in → Bunny CDN (raw) → Modal story-processor (add logo) → Bunny CDN (branded)
  → GPT captions → Google Drive → ClickUp (reviewer sees branded image)
  → Approved → Manual story posting with interactive IG features
```

## Modal Worker: `execution/modal_story_processor.py`

**App:** `story-processor`
**Endpoint:** `https://reformtechops--story-processor-process-story-webhook.modal.run`

### Input (POST)

```json
{
    "photo_url": "https://techopssocialmedia.b-cdn.net/Photos/example.jpg",
    "callback_url": "https://n8n1.reformchiropractic.app/webhook/story-callback",
    "job_id": "optional-n8n-execution-id",
    "notify_n8n": true
}
```

### Immediate Response

```json
{
    "accepted": true,
    "status": "processing",
    "job_id": "...",
    "message": "Story processing accepted. You will receive a webhook callback when complete."
}
```

### Callback (when complete)

```json
{
    "success": true,
    "status": "completed",
    "job_id": "...",
    "cdn_url": "https://techopssocialmedia.b-cdn.net/stories/story_{job_id}.png",
    "photo_url": "https://...(original)",
    "message": "Story image processed and uploaded successfully."
}
```

## What It Does

1. Downloads photo from `photo_url`
2. Downloads Reform logo from Bunny CDN (`logos/reform-logo.png`)
3. Resizes/crops photo to **1080x1920** (9:16 story format)
4. Detects brightness in top-right corner area
5. If background is dark → inverts logo to white; if light → keeps black
6. Pastes logo in **top-right corner** (40px padding, 200px wide)
7. Uploads branded image to Bunny CDN at `stories/story_{job_id}.png`
8. Sends callback to n8n with branded CDN URL

## Events

| Event | When |
|---|---|
| `story.process.started` | Processing begins |
| `story.process.completed` | Branded image uploaded to Bunny |
| `story.process.failed` | Error during processing |

## n8n Integration

Insert the Modal call in the intake workflow **after** the raw Bunny CDN upload and **before** GPT/ClickUp:

1. **HTTP Request node** → POST to the endpoint above with `photo_url` (raw Bunny URL) + `callback_url`
2. **Webhook Wait node** → Wait for Modal callback
3. Use `cdn_url` from callback for the rest of the flow (GPT analysis, Google Drive, ClickUp)

## GPT Caption Prompt

Use this category-aware prompt in the n8n "Analyze Image" node for better caption suggestions:

```
You are a social media caption writer for Reform Chiropractic, a modern
chiropractic and wellness office. You write captions that feel human,
warm, and authentic — never corporate or salesy.

Photo category: {{ $json.category }}

Category tone guide:
- Chiropractic Photo: Educational — explain what's happening and why
  it helps. Knowledgeable but approachable.
- Community Event Snapshot: Highlight energy and community connection.
  Excited and genuine.
- Consult Candid: Behind-the-scenes care. Build trust. Warm and authentic.
- Consult Smiles: Happy patient moment. Positive experience. Upbeat.
- Massage Photo: Relaxation, recovery, self-care. Calming and inviting.
- New Patient/Welcome Back Special: Celebrate new/returning patients.
  Welcoming, include soft invitation for others.
- Patients on Modalities: Explain the modality and how it helps.
  Educational and reassuring.
- Reform Strong Wall: Patient posing at the mural — milestone moment.
  Celebrate their commitment. Empowering.
- Team & Patient Smiles: Team culture, relationships. Friendly and real.
- Victory Pose With Patient: Celebratory achievement moment. Energetic
  and proud.

Write 3 caption options for this photo. Rules:
- Each caption should be 2-4 sentences (a short paragraph)
- Match the tone for this category
- At least one option should include a soft CTA
- Sound like a real person, not a brand
- No hashtags, no emojis unless natural
- Reference what you see in the photo to be specific

Return as a numbered list with just the captions.
```

## Deployment

```powershell
cd "c:\Users\crazy\Reform Workspace"
$env:PYTHONUTF8="1"
modal deploy execution/modal_story_processor.py
```

## Dependencies

- **Modal secrets:** `bunny-secrets`, `n8n-webhook-secrets`
- **Bunny CDN:** Logo at `logos/reform-logo.png`, outputs to `stories/`
- **LA region endpoint:** `https://la.storage.bunnycdn.com/` (NOT generic)

## Learnings

- Logo auto-inverts to white when background brightness < 128/255
- Stories are posted manually to allow interactive IG features (polls, stickers, links)
- The Meta API credentials are stored in `.env` for future feed post automation
