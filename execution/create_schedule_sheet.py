"""
Create the Social Media Posting Schedule Google Sheet.

Uses the Drive/Sheets service account to create a new sheet,
populate it with the 12-slot pool-based schedule, and print the
sheet ID so you can paste it into create_drive_secrets.py line 44.

Usage:
    cd "c:\\Users\\crazy\\Reform Workspace"
    python execution/create_schedule_sheet.py

After running:
    1. Copy the printed SCHEDULE_SHEET_ID
    2. Paste it into execution/create_drive_secrets.py line 44
    3. Re-run: python execution/create_drive_secrets.py
"""

import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from google.oauth2 import service_account
from googleapiclient.discovery import build

workspace = Path(__file__).parent.parent

sa_path = workspace / "service_account.json"
if not sa_path.exists():
    print(f"ERROR: service_account.json not found at {sa_path}")
    sys.exit(1)

with open(sa_path) as f:
    sa_data = json.load(f)

creds = service_account.Credentials.from_service_account_info(
    sa_data,
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)

sheets_service = build("sheets", "v4", credentials=creds)

# Create the spreadsheet
result = sheets_service.spreadsheets().create(body={
    "properties": {"title": "Social Media Posting Schedule"},
    "sheets": [{
        "properties": {
            "title": "Sheet1",
            "gridProperties": {"frozenRowCount": 1},
        }
    }],
}).execute()

sheet_id = result["spreadsheetId"]
print(f"[OK] Spreadsheet created: {sheet_id}")
print(f"     URL: https://docs.google.com/spreadsheets/d/{sheet_id}")

# 12 slots — Category Pool is comma-separated.
# Each category appears in 2-3 pools so content rotates organically.
# Platforms include all 4; content-type routing in the cron restricts
# photos to instagram,facebook automatically at runtime.
rows = [
    ["Category Pool", "Post Days", "Post Times", "Platforms", "Active"],
    # Mon
    ["Testimonial,Manuthera Showcase,Time-Lapse",           "Mon", "12:00", "instagram,facebook,tiktok,youtube", "true"],
    ["P.O.V,Injury Care and Recovery",                      "Mon", "17:00", "instagram,facebook,tiktok,youtube", "true"],
    # Tue
    ["Doctor Q&A,About Reform",                              "Tue", "10:00", "instagram,facebook,tiktok,youtube", "true"],
    ["Chiropractic ASMR,Wellness Tip",                      "Tue", "12:00", "instagram,facebook,tiktok,youtube", "true"],
    # Wed
    ["Anatomy and Body Knowledge,Testimonial",              "Wed", "09:00", "instagram,facebook,tiktok,youtube", "true"],
    ["P.O.V,Doctor Q&A,About Reform",                       "Wed", "12:00", "instagram,facebook,tiktok,youtube", "true"],
    # Thu
    ["Manuthera Showcase,Time-Lapse",                       "Thu", "12:00", "instagram,facebook,tiktok,youtube", "true"],
    ["Injury Care and Recovery,Chiropractic ASMR",          "Thu", "17:00", "instagram,facebook,tiktok,youtube", "true"],
    # Fri
    ["Testimonial,Wellness Tip",                            "Fri", "12:00", "instagram,facebook,tiktok,youtube", "true"],
    ["Anatomy and Body Knowledge,P.O.V",                    "Fri", "17:00", "instagram,facebook,tiktok,youtube", "true"],
    # Sat
    ["Time-Lapse,Doctor Q&A",                               "Sat", "11:00", "instagram,facebook,tiktok,youtube", "true"],
    ["About Reform,Chiropractic ASMR,Manuthera Showcase",    "Sat", "12:00", "instagram,facebook,tiktok,youtube", "true"],
]

sheets_service.spreadsheets().values().update(
    spreadsheetId=sheet_id,
    range="Sheet1!A1",
    valueInputOption="RAW",
    body={"values": rows},
).execute()
print(f"[OK] {len(rows) - 1} schedule rows written")

# Bold header row + auto-resize columns
sheets_service.spreadsheets().batchUpdate(
    spreadsheetId=sheet_id,
    body={"requests": [
        {
            "repeatCell": {
                "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                "fields": "userEnteredFormat.textFormat.bold",
            }
        },
        {
            "autoResizeDimensions": {
                "dimensions": {"sheetId": 0, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 5}
            }
        },
    ]},
).execute()
print("[OK] Header bolded, columns auto-resized")

print()
print("=" * 60)
print("NEXT STEPS:")
print(f"  1. Open the sheet and confirm it looks right:")
print(f"     https://docs.google.com/spreadsheets/d/{sheet_id}")
print()
print(f"  2. Paste this ID into execution/create_drive_secrets.py line 44:")
print(f'     "SCHEDULE_SHEET_ID": "{sheet_id}",')
print()
print(f"  3. Re-run: python execution/create_drive_secrets.py")
print("=" * 60)
