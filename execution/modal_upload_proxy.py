"""
Modal Upload Proxy API
Accepts video uploads via multipart form, streams to Bunny CDN,
then notifies n8n with metadata.

Upload is async: file bytes are read into memory, 200 is returned to the
browser immediately, then Bunny CDN upload + n8n notification happen in
a FastAPI BackgroundTask so the browser connection doesn't have to wait.

Deploy: See directives/video_upload_proxy.md
"""

import modal
import os
import uuid
from datetime import datetime

app = modal.App("upload-proxy")

image = (
    modal.Image.debian_slim()
    .pip_install("python-multipart", "requests", "fastapi", "uvicorn")
)


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("bunny-secrets"),
        modal.Secret.from_name("n8n-webhook-secrets"),
    ],
    memory=2048,
    timeout=600,
)
@modal.concurrent(max_inputs=5)
@modal.asgi_app()
def asgi_app():
    from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    import requests

    web_app = FastAPI(title="Upload Proxy")

    web_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def process_upload(file_data: bytes, filename: str, destination: str, cdn_url: str,
                       job_id: str, category: str, projectLead: str,
                       featuredName, featuredRole, subtitle):
        """Background task: upload to Bunny CDN then notify n8n."""
        bunny_api_key = os.getenv("BUNNY_STORAGE_API_KEY")
        storage_zone = os.getenv("BUNNY_STORAGE_ZONE")

        upload_url = f"https://la.storage.bunnycdn.com/{storage_zone}/{destination}"

        print(f"[UPLOAD] Job {job_id}: Uploading {filename} to Bunny CDN ({len(file_data)/1024/1024:.1f} MB)...")
        try:
            response = requests.put(
                upload_url,
                data=file_data,
                headers={"AccessKey": bunny_api_key, "Content-Type": "application/octet-stream"},
                timeout=300,
            )
            response.raise_for_status()
            print(f"[UPLOAD] Job {job_id}: Bunny upload complete → {cdn_url}")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Job {job_id}: Bunny upload failed: {e}")
            return

        n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL")
        n8n_webhook_token = os.getenv("N8N_WEBHOOK_TOKEN")

        if not n8n_webhook_url:
            print(f"[WARNING] Job {job_id}: N8N_WEBHOOK_URL not set, skipping n8n notification")
            return

        video_webhook_url = n8n_webhook_url.replace("/webhook/modal/intake", "/webhook/video-uploaded")
        webhook_headers = {"Content-Type": "application/json"}
        if n8n_webhook_token:
            webhook_headers["x-modal-token"] = n8n_webhook_token

        try:
            print(f"[N8N] Job {job_id}: Notifying n8n...")
            n8n_response = requests.post(
                video_webhook_url,
                json={
                    "videoURL": cdn_url,
                    "category": category,
                    "projectLead": projectLead,
                    "featuredName": featuredName,
                    "featuredRole": featuredRole,
                    "subtitle": subtitle,
                    "job_id": job_id,
                },
                headers=webhook_headers,
                timeout=30,
            )
            n8n_response.raise_for_status()
            print(f"[N8N] Job {job_id}: Notification sent successfully")
        except Exception as e:
            print(f"[WARNING] Job {job_id}: n8n notification failed: {e}")

    @web_app.post("/upload")
    async def upload_video(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        category: str = Form(...),
        projectLead: str = Form(...),
        featuredName: str = Form(None),
        featuredRole: str = Form(None),
        subtitle: str = Form(None),
    ):
        bunny_api_key = os.getenv("BUNNY_STORAGE_API_KEY")
        storage_zone = os.getenv("BUNNY_STORAGE_ZONE")
        cdn_base = os.getenv("BUNNY_CDN_BASE", "https://techopssocialmedia.b-cdn.net")

        if not bunny_api_key or not storage_zone:
            raise HTTPException(status_code=500, detail="Bunny CDN not configured")

        job_id = f"n8n-{uuid.uuid4()}"

        original_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".mp4"
        if original_ext not in (".mp4", ".mov"):
            original_ext = ".mp4"
        timestamp = datetime.now().strftime("%b %d %Y %I%M %p")
        filename = f"{category} - {timestamp}{original_ext}"
        destination = f"Videos/{filename}"
        cdn_url = f"{cdn_base.rstrip('/')}/{destination}"

        # Read file into memory (fast — already received from browser)
        file_data = await file.read()
        print(f"[UPLOAD] Job {job_id}: Received {len(file_data)/1024/1024:.1f} MB — returning 200, processing in background")

        # Return success immediately; Bunny upload + n8n happen in background
        background_tasks.add_task(
            process_upload,
            file_data, filename, destination, cdn_url,
            job_id, category, projectLead, featuredName, featuredRole, subtitle,
        )

        return JSONResponse(content={
            "success": True,
            "job_id": job_id,
            "videoURL": cdn_url,
            "filename": filename,
            "fileSize": len(file_data),
            "message": "Video received — processing in background",
        })

    @web_app.get("/health")
    async def health():
        return {"status": "ok", "service": "upload-proxy"}

    return web_app
