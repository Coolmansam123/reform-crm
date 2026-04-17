"""
Send an AES-256 encrypted zip of the workspace to a recipient via Gmail OAuth.
"""

import os
import sys
import secrets
import string
import pyzipper
import base64
import mimetypes
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).parent.parent
ZIP_OUTPUT = WORKSPACE_ROOT / ".tmp" / "workspace_encrypted.zip"
EXCLUDE_DIRS = {".git", "__pycache__"}

RECIPIENT = "ian@reformchiropractic.com"
SENDER = os.getenv("COMPANY_EMAIL", "daniel.cis@reformchiropractic.com")


def generate_password(length=20):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_encrypted_zip(password: str) -> Path:
    print(f"Creating encrypted zip at {ZIP_OUTPUT}...")
    ZIP_OUTPUT.parent.mkdir(exist_ok=True)

    with pyzipper.AESZipFile(
        ZIP_OUTPUT,
        "w",
        compression=pyzipper.ZIP_LZMA,
        encryption=pyzipper.WZ_AES,
    ) as zf:
        zf.setpassword(password.encode())

        for path in WORKSPACE_ROOT.rglob("*"):
            # Skip excluded directories
            if any(part in EXCLUDE_DIRS for part in path.parts):
                continue
            # Skip the output zip itself
            if path == ZIP_OUTPUT:
                continue
            if path.is_file():
                arcname = path.relative_to(WORKSPACE_ROOT)
                zf.write(path, arcname)
                print(f"  Added: {arcname}")

    size_mb = ZIP_OUTPUT.stat().st_size / (1024 * 1024)
    print(f"Zip created: {size_mb:.1f} MB")
    return ZIP_OUTPUT


def get_gmail_service():
    creds_file = WORKSPACE_ROOT / os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
    token_file = WORKSPACE_ROOT / os.getenv("GMAIL_TOKEN_FILE", "token.json")

    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(
            str(token_file),
            scopes=["https://www.googleapis.com/auth/gmail.send"],
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise RuntimeError("Gmail token is invalid or expired. Re-authenticate.")

    return build("gmail", "v1", credentials=creds)


def upload_to_bunny(zip_path: Path) -> str:
    import requests as req
    api_key = os.getenv("BUNNY_STORAGE_API_KEY")
    storage_zone = os.getenv("BUNNY_STORAGE_ZONE", "techopssocialmedia")
    cdn_base = os.getenv("BUNNY_CDN_BASE", "https://techopssocialmedia.b-cdn.net").rstrip("/")
    remote_path = f"backups/{zip_path.name}"
    url = f"https://la.storage.bunnycdn.com/{storage_zone}/{remote_path}"
    print(f"Uploading to Bunny CDN: {remote_path}...")
    with open(zip_path, "rb") as f:
        resp = req.put(url, data=f, headers={"AccessKey": api_key, "Content-Type": "application/zip"}, timeout=120)
    resp.raise_for_status()
    cdn_url = f"{cdn_base}/{remote_path}"
    print(f"Uploaded: {cdn_url}")
    return cdn_url


def send_email_with_link(download_url: str, password: str):
    print(f"Sending email to {RECIPIENT}...")
    service = get_gmail_service()

    msg = MIMEMultipart()
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg["Subject"] = "Reform Workspace — Encrypted Backup"

    body = f"""Hi Ian,

Your encrypted backup of the Reform Workspace is ready for download:

    Download: {download_url}

To open the zip file, use the password below:

    Password: {password}

The archive is AES-256 encrypted. You can open it with 7-Zip (free) or any modern zip tool that supports AES encryption.

Best,
Reform Tech Ops
"""
    msg.attach(MIMEText(body, "plain"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"Email sent to {RECIPIENT}")


def main():
    password = generate_password()
    zip_path = create_encrypted_zip(password)
    download_url = upload_to_bunny(zip_path)
    send_email_with_link(download_url, password)
    print(f"\nDone. Download link and password sent to {RECIPIENT}.")


if __name__ == "__main__":
    main()
