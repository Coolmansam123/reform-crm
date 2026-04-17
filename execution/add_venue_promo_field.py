"""Add 'Promo Items' long_text field to T_GOR_VENUES (790)."""
import os, requests, sys
from dotenv import load_dotenv

load_dotenv()
BR = os.environ["BASEROW_URL"]
EMAIL = os.environ["BASEROW_EMAIL"]
PASSWORD = os.environ["BASEROW_PASSWORD"]

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TID = 790

r = requests.post(f"{BR}/api/user/token-auth/", json={"email": EMAIL, "password": PASSWORD})
r.raise_for_status()
jwt = r.json().get("access_token") or r.json().get("token")
h = {"Authorization": f"JWT {jwt}", "Content-Type": "application/json"}

existing = {f["name"] for f in requests.get(f"{BR}/api/database/fields/table/{TID}/", headers=h).json()}
if "Promo Items" in existing:
    print("SKIP — already exists")
else:
    r2 = requests.post(f"{BR}/api/database/fields/table/{TID}/", headers=h, json={"name": "Promo Items", "type": "long_text"})
    print("OK" if r2.status_code in (200, 201) else f"FAIL {r2.status_code}: {r2.text[:200]}")
