"""
Re-authenticate Gmail OAuth and save a fresh token.json.
Run this script once on any new machine or when token.json is expired/missing.

Usage:
    python execution/reauth_gmail.py

A browser window will open asking you to sign in with your Google account.
After approval, token.json will be saved and Gmail sending will work.
"""

import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).parent.parent
CREDENTIALS_FILE = WORKSPACE_ROOT / os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
TOKEN_FILE = WORKSPACE_ROOT / os.getenv("GMAIL_TOKEN_FILE", "token.json")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/chat.spaces",
    "https://www.googleapis.com/auth/chat.messages.create",
]

if not CREDENTIALS_FILE.exists():
    print(f"[ERROR] credentials.json not found at {CREDENTIALS_FILE}")
    print("Make sure credentials.json is in the workspace root.")
    exit(1)

print("Opening browser for Google sign-in...")
print("Sign in with your reformchiropractic.com Google account.\n")

flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
creds = flow.run_local_server(port=0)

TOKEN_FILE.write_text(creds.to_json())
print(f"\n[OK] token.json saved to {TOKEN_FILE}")
print("Gmail authentication is ready.")
