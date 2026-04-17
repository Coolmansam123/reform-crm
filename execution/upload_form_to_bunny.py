"""
Upload form files to Bunny CDN.

Uploads:
  .tmp/index.html       -> Workflow Assets/form/index.html
  .tmp/form-config.json -> Workflow Assets/form/form-config.json

Usage:
    python execution/upload_form_to_bunny.py
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

BUNNY_API_KEY = os.getenv("BUNNY_STORAGE_API_KEY")
STORAGE_ZONE = os.getenv("BUNNY_STORAGE_ZONE", "techopssocialmedia")
CDN_BASE = os.getenv("BUNNY_CDN_BASE", "https://techopssocialmedia.b-cdn.net")

FILES = [
    (".tmp/index.html", "Workflow Assets/form/index.html", "text/html"),
]


def upload_file(local_path, remote_path, content_type):
    with open(local_path, "rb") as f:
        data = f.read()

    url = f"https://la.storage.bunnycdn.com/{STORAGE_ZONE}/{remote_path}"

    headers = {
        "AccessKey": BUNNY_API_KEY,
        "Content-Type": content_type,
    }

    print(f"[UPLOAD] {local_path} -> {remote_path}")
    resp = requests.put(url, data=data, headers=headers, timeout=30)
    resp.raise_for_status()

    cdn_url = f"{CDN_BASE.rstrip('/')}/{remote_path}"
    print(f"  [OK] {cdn_url}")
    return cdn_url


def main():
    if not BUNNY_API_KEY:
        print("[ERROR] BUNNY_STORAGE_API_KEY not set in .env")
        return

    for local, remote, ct in FILES:
        if not os.path.exists(local):
            print(f"[SKIP] {local} not found")
            continue
        upload_file(local, remote, ct)

    print("\n[DONE] Form files uploaded to Bunny CDN")
    print(f"  Form URL: {CDN_BASE.rstrip('/')}/Workflow Assets/form/index.html")


if __name__ == "__main__":
    main()
