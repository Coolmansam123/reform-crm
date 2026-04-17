"""
Create/update Modal secret: google-drive-secrets
Reads service_account.json from workspace root.
"""

import json
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

workspace = Path(__file__).parent.parent

# Load service account JSON
sa_path = workspace / "service_account.json"
if not sa_path.exists():
    print(f"ERROR: service_account.json not found at {sa_path}")
    sys.exit(1)

with open(sa_path) as f:
    sa_json = json.dumps(json.load(f))  # compact, no extra whitespace

# Completed folder IDs (category -> Drive folder ID)
completed_folder_ids = {
    "Anatomy and Body Knowledge": "1sOyMsjM8ih98KTo8UygzBgq7J_LKvxNW",
    "Chiropractic ASMR": "1qmfAG4_RDxZUj24ELMn6tqh2x6LZYs45",
    "Doctor Q&A": "133FDkxK9UWFjyx-sRKsjKGpjUJird3Ir",
    "About Reform": "1c_ZVSOSrKKAhEhwvgXUxmGL0Qrspmez7",
    "Frequently Asked Questions": "1ZXBvGLEot3Ka-qRMg8LGYGkKWQOEcjGr",
    "Injury Care and Recovery": "1V44KLcauE97DxCtqMYO0rVKQgoGKql2S",
    "Manuthera Showcase": "1DNrq8-QWCUcPkUJfSahNOub63xNY8oKv",
    "P.O.V": "1A-3j1AkXeF7Xj1bFwiYrxyjjgCx8vDJg",
    "Doctor POV": "1OQyXx7squFHarJ5tkDXxgSpfMAqMKWo4",
    "Massage POV": "1yqUXuTT1GiuGgHkpyy1-rdoIlrGljrtn",
    "Testimonial": "1G4R2irU9VSKsTtCYi23JOrPq-cl-ZMRT",
    "Time-Lapse": "10mfRm0c-AJl6zDcl-Pud4e5Yei3O9m7O",
    "Wellness Tip": "1bcNXPgr1bE3BnDhk-MDxfi-l1-AMJxvj",
}

secret_vars = {
    "GOOGLE_SERVICE_ACCOUNT_JSON": sa_json,
    "DRIVE_SCHEDULED_VIDEOS_FOLDER_ID": "11AUk8rnucvdwLhz1BJrDaDZ7oZn3agX7",
    "DRIVE_SCHEDULED_PHOTOS_FOLDER_ID": "1SuMVHjgcpd7f9Xf6vSCn706QgIYJvby-",
    "DRIVE_COMPLETED_FOLDER_IDS": json.dumps(completed_folder_ids),
    "SCHEDULE_SHEET_ID": "1d1V8wurYb9uPU86r8pBKFLshUaCS-YqumBrK5hBkXq0",
}

print("=" * 60)
print("Creating Modal Secret: google-drive-secrets")
print("=" * 60)
for k, v in secret_vars.items():
    if k == "GOOGLE_SERVICE_ACCOUNT_JSON":
        print(f"  {k}=<service account JSON, {len(v)} chars>")
    elif k == "DRIVE_COMPLETED_FOLDER_IDS":
        print(f"  {k}=<JSON mapping, {len(completed_folder_ids)} categories>")
    else:
        print(f"  {k}={v or '<empty>'}")
print()

cmd = ["python", "-m", "modal", "secret", "create", "google-drive-secrets", "--force"]
for k, v in secret_vars.items():
    cmd.append(f"{k}={v}")

try:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    print("google-drive-secrets created/updated successfully!")
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
except subprocess.CalledProcessError as e:
    print(f"ERROR: {e}")
    print(e.stderr)
    sys.exit(1)
