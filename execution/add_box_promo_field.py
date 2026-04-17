"""Add 'Promo Items' long_text field to T_GOR_BOXES (800)."""
import os, requests, sys
from dotenv import load_dotenv

load_dotenv()
BR = os.environ["BASEROW_URL"]
EMAIL = os.environ["BASEROW_EMAIL"]
PASSWORD = os.environ["BASEROW_PASSWORD"]

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TID = 800
FIELD = {"name": "Promo Items", "type": "long_text"}

r = requests.post(f"{BR}/api/user/token-auth/", json={"email": EMAIL, "password": PASSWORD})
r.raise_for_status()
jwt = r.json().get("access_token") or r.json().get("token")
h = {"Authorization": f"JWT {jwt}", "Content-Type": "application/json"}

existing = {f["name"] for f in requests.get(f"{BR}/api/database/fields/table/{TID}/", headers=h).json()}
if FIELD["name"] in existing:
    print(f"SKIP {FIELD['name']} — already exists")
else:
    r2 = requests.post(f"{BR}/api/database/fields/table/{TID}/", headers=h, json=FIELD)
    print(f"{'OK' if r2.status_code in (200,201) else 'FAIL'}: {r2.status_code}")
    if r2.status_code not in (200,201):
        print(r2.text[:200])
