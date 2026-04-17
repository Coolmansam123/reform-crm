# Video Upload Proxy

> Replaces n8n's built-in form + file upload with a custom HTML form on Bunny CDN and a Modal upload proxy. Large video files bypass n8n entirely.

## Architecture

```
Browser (HTML form on Bunny CDN)
  → POST multipart to Modal Upload Proxy
    → Streams video to Bunny CDN (LA region)
    → POSTs metadata JSON to n8n webhook /webhook/video-uploaded
      → n8n routes to Shotstack or Timelapse worker as before
```

Photos still go through the existing n8n form (they're small enough).

## Components

### 1. Modal Upload Proxy
- **File:** `execution/modal_upload_proxy.py`
- **App name:** `upload-proxy`
- **Endpoint:** `POST /upload` (multipart: file + metadata fields)
- **Secrets:** `bunny-secrets`, `n8n-webhook-secrets`
- **Container:** 2GB memory, 10min timeout, 5 concurrent inputs

**What it does:**
1. Receives video file + metadata (category, user, name, jobTitle, subtitle, role)
2. Generates filename: `{category} - {MMM DD YYYY HHMM AM/PM}.mp4`
3. Streams file to Bunny CDN at `Videos/{filename}` via LA region endpoint
4. POSTs metadata to n8n at `/webhook/video-uploaded`
5. Returns JSON success/error to browser

**Deploy:**
```powershell
cd "c:\Users\crazy\Reform Workspace"
$env:PYTHONUTF8="1"; modal deploy execution/modal_upload_proxy.py
```

### 2. Custom HTML Intake Form
- **Hosted on Bunny CDN:** `Workflow Assets/form/index.html`
- **Config file:** `Workflow Assets/form/form-config.json`
- **URL:** `https://techopssocialmedia.b-cdn.net/Workflow Assets/form/index.html`
- **Optional subdomain:** `upload.reformchiropractic.app` via CNAME

**Multi-step flow:**
1. Video or Photo? (Photo → redirects to n8n form)
2. Category dropdown
3. Role + Featured Person (conditional — only for categories in `categoriesRequiringName`)
4. Project Lead
5. Title (optional, 70 char max)
6. File upload with progress bar
7. Thank you page

**To update categories/staff:** Edit the hard-coded `CONFIG` object in `.tmp/index.html` (the `loadConfig()` function), then run `python execution/upload_form_to_bunny.py` to push to Bunny CDN. The `form-config.json` file is no longer used by the form.

### 3. Shotstack Config (replaces Google Sheets)
- **File:** `Workflow Assets/shotstack-config.json` on Bunny CDN
- **Replaces:** Google Sheet `1vj_d15yRb4A3QrGGD3RQvSRhTUnaaGWBnuKgmas6ZI4` (tab "Configuration")
- **Export script:** `execution/export_shotstack_config.py`

**n8n changes (manual):**
- Replace `Get Config` Google Sheets node with HTTP Request: `GET https://techopssocialmedia.b-cdn.net/Workflow Assets/shotstack-config.json`
- Add Code node to extract category: `const config = $input.first().json; const category = $('Get Video Info').item.json.category; return [{ json: config[category] || {} }];`

### 4. n8n Webhook Receiver (manual setup)
In the Social Media Intake workflow:
- Add Webhook node: `POST /webhook/video-uploaded`
- Add Set node to map: videoURL, category, user, Name, JobTitle, subtitle, job_id
- Connect Set node to existing Time-Lapse If node
- Disable old video form path (File Upload, End1, Set Bunny File name, Upload .mp4 to Bunny.net Storage)
- Keep photo path unchanged

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| `execution/modal_upload_proxy.py` | Local/Modal | Upload proxy API |
| `execution/export_shotstack_config.py` | Local | One-time Sheet→JSON export |
| `.tmp/index.html` | Local (source) | HTML form (upload to Bunny) |
| `.tmp/form-config.json` | Local (source) | Form config (upload to Bunny) |
| `.tmp/shotstack-config.json` | Local (source) | Shotstack config (upload to Bunny) |
| `Workflow Assets/form/index.html` | Bunny CDN | Live form |
| `Workflow Assets/form/form-config.json` | Bunny CDN | Live config |
| `Workflow Assets/shotstack-config.json` | Bunny CDN | Live Shotstack config |

## Testing

1. **Upload proxy:** `curl -X POST https://reformtechops--upload-proxy-asgi-app.modal.run/upload -F "file=@test.mp4" -F "category=Time-Lapse" -F "user=Iyleen" -F "name=Dr. Dominick Hernandez" -F "jobTitle=Doctor of Chiropractic" -F "subtitle=test"`
2. **HTML form:** Visit Bunny CDN URL, fill form, upload small .mp4
3. **Large file:** Upload 5+ minute .mp4, verify no timeout
4. **Shotstack config:** Update n8n to use HTTP Request, run test video through pipeline

## Learnings & Edge Cases

- Bunny CDN LA region endpoint: `https://la.storage.bunnycdn.com/` (generic endpoint returns 401)
- Service account `cabinet-of-reform@buoyant-ground-474317-m3.iam.gserviceaccount.com` needs Sheet access for config export
- Modal ASGI apps use `@modal.asgi_app()` decorator (not `@modal.fastapi_endpoint`)
- CORS must be enabled on the Modal endpoint since the form is served from Bunny CDN

## Future (Phase 2)

- Modal uploads final rendered video to Google Drive
- Modal creates ClickUp task directly
- Consolidate ASMR path to use same upload proxy
- Add photo upload support to custom form
