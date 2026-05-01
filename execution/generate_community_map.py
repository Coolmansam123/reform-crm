#!/usr/bin/env python3
"""
Generate the Community Outreach map (v2).

New in v2:
- Outreach Score (type priority + rating + distance + reviews)
- Top 50 filter — one-click to show only highest-scored orgs
- Priority View — pins color-scaled by outreach score
- Editable Contact Person + Email in side panel (live Baserow save on blur)
Reads live from Baserow:
  - Community Organizations, Community Activities (DB 204)

Output: .tmp/community_map.html

Usage:
    python execution/generate_community_map.py
"""

import os
import sys
import json
import time
import math
import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Make `hub.*` importable when invoked from the workspace root.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hub.maps import ICON_BRIDGE_JS  # noqa: E402

load_dotenv()

BASEROW_URL        = os.getenv("BASEROW_URL")
BASEROW_EMAIL      = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD   = os.getenv("BASEROW_PASSWORD")
BASEROW_API_TOKEN  = os.getenv("BASEROW_API_TOKEN")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
GOOGLE_MAPS_MAP_ID  = os.getenv("GOOGLE_MAPS_MAP_ID", "")
OFFICE_LATLNG      = os.getenv("ATTORNEY_MAPPER_OFFICE_LAT_LNG", "34.0522,-118.2437")
RADIUS_MILES       = float(os.getenv("COMMUNITY_RADIUS_MILES",
                           os.getenv("ATTORNEY_MAPPER_RADIUS_MILES", 7)))

COMMUNITY_VENUES_TABLE_ID    = int(os.getenv("COMMUNITY_VENUES_TABLE_ID", 0)) or None
COMMUNITY_ACTIVITIES_TABLE_ID = int(os.getenv("COMMUNITY_ACTIVITIES_TABLE_ID", 0)) or None

# ─── Scoring ──────────────────────────────────────────────────────────────────

TYPE_PRIORITY = {
    "Chamber of Commerce": 10, "BNI Chapter": 9,  "Rotary Club": 8,
    "Lions Club": 7,           "Networking Mixer": 6, "Community Center": 5,
    "Parks & Rec": 4,          "High School": 3,  "Church": 2,  "Other": 1,
}

def outreach_score(org):
    type_pts    = TYPE_PRIORITY.get(org["type"], 1) * 10
    rating_pts  = float(org["rating"] or 0) * 10
    reviews_pts = min(math.log1p(int(org["reviews"] or 0)) * 5, 25)
    try:
        dist = float(str(org["distance"]).replace(" mi", "").strip() or 7)
    except (ValueError, TypeError):
        dist = 7
    dist_pts = max(0, (10 - dist)) * 2
    return round(type_pts + rating_pts + reviews_pts + dist_pts)

# ─── JWT Auth ─────────────────────────────────────────────────────────────────

_jwt_token = None
_jwt_time  = 0


def fresh_token():
    global _jwt_token, _jwt_time
    if _jwt_token is None or (time.time() - _jwt_time) > 480:
        r = requests.post(f"{BASEROW_URL}/api/user/token-auth/", json={
            "email": BASEROW_EMAIL, "password": BASEROW_PASSWORD,
        })
        r.raise_for_status()
        _jwt_token = r.json()["access_token"]
        _jwt_time  = time.time()
    return _jwt_token


def hdrs():
    return {"Authorization": f"JWT {fresh_token()}", "Content-Type": "application/json"}


# ─── Data Loading ─────────────────────────────────────────────────────────────

def read_all_rows(table_id):
    rows, page = [], 1
    while True:
        r = requests.get(
            f"{BASEROW_URL}/api/database/rows/table/{table_id}/"
            f"?size=200&page={page}&user_field_names=true",
            headers=hdrs(),
        )
        if r.status_code != 200:
            break
        data = r.json()
        rows.extend(data["results"])
        if not data.get("next"):
            break
        page += 1
    return rows


def find_table_by_name(database_id, name):
    r = requests.get(
        f"{BASEROW_URL}/api/database/tables/database/{database_id}/",
        headers=hdrs(),
    )
    r.raise_for_status()
    for t in r.json():
        if t["name"] == name:
            return t["id"]
    return None


def _sv(field):
    """Extract single_select value string from Baserow response."""
    if isinstance(field, dict):
        return field.get("value", "")
    return field or ""


def load_community_table_ids():
    global COMMUNITY_VENUES_TABLE_ID, COMMUNITY_ACTIVITIES_TABLE_ID

    if not COMMUNITY_VENUES_TABLE_ID:
        print("Auto-discovering Community Organizations table...")
        COMMUNITY_VENUES_TABLE_ID = find_table_by_name(204, "Community Organizations")
        if not COMMUNITY_VENUES_TABLE_ID:
            print("  ERROR: 'Community Organizations' not found. Run setup_community_tables.py")
            return False
        print(f"  Community Organizations: {COMMUNITY_VENUES_TABLE_ID}")

    if not COMMUNITY_ACTIVITIES_TABLE_ID:
        print("Auto-discovering Community Activities table...")
        COMMUNITY_ACTIVITIES_TABLE_ID = find_table_by_name(204, "Community Activities")
        if not COMMUNITY_ACTIVITIES_TABLE_ID:
            print("  ERROR: 'Community Activities' not found.")
            return False
        print(f"  Community Activities: {COMMUNITY_ACTIVITIES_TABLE_ID}")

    return True


def load_organizations():
    print("Loading Community Organizations from Baserow...")
    rows = read_all_rows(COMMUNITY_VENUES_TABLE_ID)
    print(f"  {len(rows)} rows")

    orgs = []
    for row in rows:
        try:
            lat = float(row.get("Latitude") or 0)
            lng = float(row.get("Longitude") or 0)
        except (TypeError, ValueError):
            continue
        if not lat or not lng:
            continue

        org = {
            "id":            row["id"],
            "name":          row.get("Name", "") or "",
            "type":          _sv(row.get("Type")),
            "address":       row.get("Address", "") or "",
            "phone":         row.get("Phone", "") or "",
            "email":         row.get("Email", "") or "",
            "contactPerson": row.get("Contact Person", "") or "",
            "website":       row.get("Website", "") or "",
            "rating":        row.get("Rating", "") or "",
            "reviews":       row.get("Reviews", 0) or 0,
            "distance":      row.get("Distance (mi)", "") or "",
            "contactStatus": _sv(row.get("Contact Status")) or "Not Contacted",
            "outreachGoal":  _sv(row.get("Outreach Goal")),
            "notes":         row.get("Notes", "") or "",
            "googleMapsUrl": row.get("Google Maps URL", "") or "",
            "yelpUrl":       row.get("Yelp Search URL", "") or "",
            "lat":           lat,
            "lng":           lng,
        }
        org["score"] = outreach_score(org)
        orgs.append(org)

    print(f"  {len(orgs)} organizations with coordinates")
    return orgs


def load_community_activities():
    print("Loading Community Activities from Baserow...")
    rows = read_all_rows(COMMUNITY_ACTIVITIES_TABLE_ID)
    print(f"  {len(rows)} activities")

    by_id = {}
    for row in rows:
        links = row.get("Organization", [])
        if not links:
            continue
        act = {
            "id":            row["id"],
            "date":          row.get("Date", "") or "",
            "type":          _sv(row.get("Type")),
            "outcome":       _sv(row.get("Outcome")),
            "contactPerson": row.get("Contact Person", "") or "",
            "summary":       row.get("Summary", "") or "",
            "followUpDate":  row.get("Follow-Up Date", "") or "",
        }
        for link in links:
            oid = link.get("id")
            if oid:
                by_id.setdefault(oid, []).append(act)

    for oid in by_id:
        by_id[oid].sort(key=lambda a: a.get("date", "") or "", reverse=True)
    return by_id



# ─── HTML Generation ──────────────────────────────────────────────────────────

def generate_html(orgs, org_activities):
    office_lat, office_lng = [float(x.strip()) for x in OFFICE_LATLNG.split(",")]

    # Compute top-50 IDs by score
    sorted_by_score = sorted(orgs, key=lambda o: o["score"], reverse=True)
    top50_ids        = [o["id"] for o in sorted_by_score[:50]]
    max_score        = sorted_by_score[0]["score"] if sorted_by_score else 100

    # Sanitize backticks from string fields — a literal ` in data breaks the JS f-string template
    def strip_backticks(obj):
        if isinstance(obj, str):   return obj.replace('`', '')
        if isinstance(obj, list):  return [strip_backticks(i) for i in obj]
        if isinstance(obj, dict):  return {k: strip_backticks(v) for k, v in obj.items()}
        return obj

    orgs_json       = json.dumps(strip_backticks(orgs), ensure_ascii=False)
    acts_json       = json.dumps(strip_backticks(org_activities), ensure_ascii=False)
    top50_json      = json.dumps(top50_ids, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Community Outreach</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f6fa; color: #222; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}

    #header {{ background: linear-gradient(160deg, #0f3460 0%, #16213e 100%); padding: 0 16px; display: flex; align-items: center; border-bottom: 2px solid rgba(255,255,255,0.08); flex-shrink: 0; box-shadow: 0 2px 12px rgba(0,0,0,0.28); min-height: 44px; }}
    #header .brand h1 {{ font-size: 14px; font-weight: 700; color: #fff; letter-spacing: 1px; }}
    #header .brand .tagline {{ font-size: 10px; color: rgba(255,255,255,0.55); }}

    #controls {{ background: linear-gradient(160deg, #0f3460 0%, #16213e 100%); padding: 7px 14px; display: flex; flex-direction: column; gap: 6px; border-bottom: 1px solid rgba(255,255,255,0.07); flex-shrink: 0; }}
    #controls-row1 {{ display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
    #controls-row2 {{ display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
    #controls-row3 {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}

    #search-container {{ position: relative; margin-left: auto; }}
    #search {{ background: #fff; border: 1px solid #ddd; color: #222; padding: 5px 10px; border-radius: 6px; font-size: 13px; width: 200px; }}
    #search::placeholder {{ color: #aaa; }}
    #search-dropdown {{ position: absolute; top: 100%; left: 0; width: 310px; background: #fff; border: 1px solid #ddd; border-radius: 6px; max-height: 200px; overflow-y: auto; z-index: 1000; display: none; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
    .search-item {{ padding: 7px 10px; cursor: pointer; border-bottom: 1px solid #f0f0f0; }}
    .search-item:hover {{ background: #f5f6fa; }}
    .search-item .si-name {{ font-size: 13px; font-weight: 600; }}
    .search-item .si-meta {{ font-size: 11px; color: #888; margin-top: 1px; }}
    .search-highlight {{ color: #e94560; font-weight: 700; }}

    .toggle-btn {{ padding: 3px 9px; border-radius: 10px; border: 1px solid #ccc; background: transparent; color: #aaa; font-size: 11px; cursor: pointer; transition: all 0.2s; white-space: nowrap; }}
    .toggle-btn.active {{ border-color: transparent; color: #fff; }}
    .toggle-btn[data-ctype="Chamber of Commerce"].active {{ background: #0D47A1; border-color: #0D47A1; }}
    .toggle-btn[data-ctype="Lions Club"].active {{ background: #F57F17; border-color: #F57F17; }}
    .toggle-btn[data-ctype="Rotary Club"].active {{ background: #1565C0; border-color: #1565C0; }}
    .toggle-btn[data-ctype="BNI Chapter"].active {{ background: #B71C1C; border-color: #B71C1C; }}
    .toggle-btn[data-ctype="Networking Mixer"].active {{ background: #E65100; border-color: #E65100; }}
    .toggle-btn[data-ctype="Church"].active {{ background: #4E342E; border-color: #4E342E; }}
    .toggle-btn[data-ctype="Parks & Rec"].active {{ background: #1B5E20; border-color: #1B5E20; }}
    .toggle-btn[data-ctype="Community Center"].active {{ background: #880E4F; border-color: #880E4F; }}
    .toggle-btn[data-ctype="High School"].active {{ background: #4527A0; border-color: #4527A0; }}
    .toggle-btn[data-ctype="Other"].active {{ background: #546E7A; border-color: #546E7A; }}
    .toggle-btn[data-cstatus="Not Contacted"].active {{ background: #455A64; border-color: #455A64; }}
    .toggle-btn[data-cstatus="Contacted"].active {{ background: #1565C0; border-color: #1565C0; }}
    .toggle-btn[data-cstatus="In Discussion"].active {{ background: #6A1B9A; border-color: #6A1B9A; }}
    .toggle-btn[data-cstatus="Active Partner"].active {{ background: #2E7D32; border-color: #2E7D32; }}

    .view-btn {{ padding: 4px 12px; border-radius: 6px; border: 1px solid #556; background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.7); font-size: 12px; cursor: pointer; transition: all 0.2s; font-weight: 500; }}
    .view-btn.active {{ background: #e94560; border-color: #e94560; color: #fff; }}
    .top50-btn {{ padding: 4px 12px; border-radius: 6px; border: 1px solid #F4A922; background: transparent; color: #F4A922; font-size: 12px; cursor: pointer; font-weight: 600; transition: all 0.2s; }}
    .top50-btn.active {{ background: #F4A922; color: #000; }}
    .sep {{ width: 1px; height: 18px; background: rgba(255,255,255,0.2); }}

    #stats-bar {{ display: flex; gap: 12px; margin-left: auto; }}
    .stat {{ text-align: center; }}
    .stat .num {{ font-size: 16px; font-weight: 700; color: #fff; }}
    .stat .lbl {{ font-size: 9px; color: rgba(255,255,255,0.55); text-transform: uppercase; }}

    #main {{ position: relative; display: flex; flex: 1; overflow: hidden; }}
    #map {{ flex: 1; }}

    #sidebar {{ position: absolute; top: 0; right: 0; bottom: 0; width: 360px; background: #fff; border-left: 1px solid #e8e8e8; overflow-y: auto; transform: translateX(100%); transition: transform 0.3s cubic-bezier(0.4,0,0.2,1); z-index: 100; box-shadow: -4px 0 20px rgba(0,0,0,0.15); }}
    #sidebar.open {{ transform: translateX(0); }}
    #sidebar-inner {{ padding: 14px; }}
    #sidebar-placeholder {{ color: #bbb; font-size: 13px; text-align: center; margin-top: 50px; }}
    #sidebar-content {{ display: none; }}
    #sidebar-content.visible {{ display: block; }}

    .ent-name {{ font-size: 15px; font-weight: 700; color: #111; margin-bottom: 4px; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; margin-right: 4px; margin-bottom: 6px; }}
    .score-badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 700; background: #F57F17; color: #fff; margin-right: 4px; margin-bottom: 6px; }}
    .section {{ margin-bottom: 12px; }}
    .slabel {{ font-size: 10px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 3px; }}
    .sval {{ font-size: 13px; color: #444; }}
    a.link {{ color: #1a73e8; text-decoration: none; font-size: 12px; }}
    a.link:hover {{ text-decoration: underline; }}
    .divider {{ border: none; border-top: 1px solid #eee; margin: 12px 0; }}
    .stars {{ color: #f4a922; font-size: 12px; }}

    .editable-field {{ width: 100%; padding: 5px 8px; background: #f5f6fa; border: 1px solid #e0e0e0; color: #222; border-radius: 6px; font-size: 13px; font-family: inherit; transition: border-color 0.2s; }}
    .editable-field:focus {{ outline: none; border-color: #e94560; background: #fff; }}
    .save-indicator {{ font-size: 10px; color: #aaa; height: 12px; margin-top: 3px; }}

    .status-select {{ width: 100%; padding: 6px 8px; background: #f5f6fa; border: 1px solid #ddd; color: #222; border-radius: 6px; font-size: 13px; cursor: pointer; }}
    .save-st {{ font-size: 10px; color: #aaa; height: 12px; margin-top: 3px; }}

    .act-item {{ background: #f5f6fa; border-radius: 5px; padding: 7px 9px; margin-bottom: 7px; font-size: 12px; border: 1px solid #eee; }}
    .act-hdr {{ display: flex; justify-content: space-between; margin-bottom: 3px; }}
    .act-type {{ font-weight: 600; color: #1a73e8; }}
    .act-date {{ color: #999; }}
    .act-outcome {{ color: #2e7d32; }}
    .act-summary {{ color: #444; margin-top: 2px; }}
    .act-person {{ color: #888; font-style: italic; }}
    .act-followup {{ color: #e65100; margin-top: 2px; }}
    .no-acts {{ color: #bbb; font-size: 12px; font-style: italic; }}

    .box-item {{ background: #fff8e1; border-radius: 5px; padding: 7px 9px; margin-bottom: 7px; font-size: 12px; border: 1px solid #ffe082; }}
    .box-item.active {{ border-color: #F57F17; background: #fff3e0; }}
    .box-item.lost {{ border-color: #ef9a9a; background: #fff5f5; }}
    .box-hdr {{ display: flex; justify-content: space-between; margin-bottom: 3px; }}
    .box-status-active {{ color: #E65100; font-weight: 700; font-size: 11px; }}
    .box-status-pickedup {{ color: #2e7d32; font-weight: 700; font-size: 11px; }}
    .box-status-lost {{ color: #c62828; font-weight: 700; font-size: 11px; }}
    .box-date {{ color: #999; font-size: 11px; }}
    .box-loc {{ color: #555; margin-top: 2px; }}
    .box-leads {{ color: #1565C0; margin-top: 2px; font-weight: 600; }}

    .log-form {{ background: #f5f6fa; border-radius: 7px; padding: 11px; margin-top: 10px; border: 1px solid #eee; }}
    .log-form h4 {{ font-size: 12px; color: #e94560; margin-bottom: 8px; }}
    .log-form-box h4 {{ color: #E65100; }}
    .fr {{ margin-bottom: 7px; }}
    .fl {{ font-size: 10px; color: #999; margin-bottom: 2px; display: block; }}
    .fi {{ width: 100%; padding: 4px 7px; background: #fff; border: 1px solid #ddd; color: #222; border-radius: 4px; font-size: 12px; font-family: inherit; }}
    .fi:focus {{ outline: none; border-color: #e94560; }}
    .fta {{ width: 100%; padding: 4px 7px; background: #fff; border: 1px solid #ddd; color: #222; border-radius: 4px; font-size: 12px; resize: vertical; min-height: 55px; font-family: inherit; }}
    .log-btn {{ padding: 6px 0; background: #e94560; color: #fff; border: none; border-radius: 5px; font-size: 12px; cursor: pointer; font-weight: 600; width: 100%; margin-top: 4px; }}
    .log-btn:hover {{ background: #c0392b; }}
    .log-btn:disabled {{ background: #ccc; cursor: default; }}
    .log-btn-box {{ background: #E65100; }}
    .log-btn-box:hover {{ background: #bf360c; }}
    .form-st {{ font-size: 10px; color: #aaa; margin-top: 3px; }}

    .notes-log {{ max-height: 160px; overflow-y: auto; border: 1px solid #eee; border-radius: 6px; padding: 6px 8px; background: #fafafa; margin-top: 4px; }}
    .notes-log > div:last-child {{ border-bottom: none; }}

    /* score legend in priority view */
    #score-legend {{ position: absolute; bottom: 12px; left: 12px; background: rgba(255,255,255,0.92); border-radius: 8px; padding: 10px 14px; font-size: 11px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); display: none; z-index: 10; }}
    #score-legend.visible {{ display: block; }}
    .legend-row {{ display: flex; align-items: center; gap: 7px; margin-bottom: 4px; }}
    .legend-dot {{ width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }}
    /* ── Pipeline stepper ── */
    .pipeline-stepper {{ display: flex; align-items: flex-start; margin: 4px 0 6px; }}
    .ps-step {{ flex: 1; display: flex; flex-direction: column; align-items: center; cursor: pointer; }}
    .ps-step:hover .ps-dot {{ transform: scale(1.2); }}
    .ps-dot {{ width: 15px; height: 15px; border-radius: 50%; border: 2px solid #ddd; background: #fff; flex-shrink: 0; transition: transform 0.15s; }}
    .ps-line {{ flex: 1; height: 2px; background: #e0e0e0; margin-top: 7px; transition: background 0.2s; }}
    .ps-label {{ font-size: 9px; color: #bbb; text-align: center; margin-top: 4px; line-height: 1.3; user-select: none; }}

    /* ── Empty state overlay ── */
    #empty-state {{ display: none; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(255,255,255,0.96); border-radius: 16px; padding: 28px 36px; text-align: center; box-shadow: 0 8px 32px rgba(0,0,0,0.13); z-index: 50; pointer-events: none; }}
    #empty-state.visible {{ display: block; }}
    #empty-state h3 {{ font-size: 15px; color: #444; margin: 12px 0 4px; font-weight: 600; }}
    #empty-state p {{ font-size: 12px; color: #aaa; }}

    /* ── Export button ── */
    .export-btn {{ padding: 4px 11px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.3); background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.85); font-size: 12px; cursor: pointer; font-weight: 500; transition: all 0.2s; letter-spacing: 0.2px; }}
    .export-btn:hover {{ background: rgba(255,255,255,0.2); border-color: rgba(255,255,255,0.5); color: #fff; }}

    /* ── Last activity chip ── */
    .last-act-chip {{ display: inline-flex; align-items: center; gap: 5px; background: #f5f6fa; border: 1px solid #eee; border-radius: 20px; padding: 3px 10px; font-size: 11px; color: #666; margin-bottom: 10px; }}
  </style>
</head>
<body>

<div id="header">
  <div class="brand">
    <h1>COMMUNITY OUTREACH</h1>
    <div class="tagline">Local Organizations &amp; Events</div>
  </div>
</div>

<div id="controls">
  <div id="controls-row1">
    <button class="toggle-btn active" data-ctype="Chamber of Commerce">Chamber</button>
    <button class="toggle-btn active" data-ctype="Lions Club">Lions</button>
    <button class="toggle-btn active" data-ctype="Rotary Club">Rotary</button>
    <button class="toggle-btn active" data-ctype="BNI Chapter">BNI</button>
    <button class="toggle-btn active" data-ctype="Networking Mixer">Networking</button>
    <button class="toggle-btn active" data-ctype="Church">Church</button>
    <button class="toggle-btn active" data-ctype="Parks &amp; Rec">Parks &amp; Rec</button>
    <button class="toggle-btn active" data-ctype="Community Center">Comm. Center</button>
    <button class="toggle-btn active" data-ctype="High School">High School</button>
    <button class="toggle-btn active" data-ctype="Other">Other</button>
    <div id="search-container" style="margin-left:auto">
      <input type="text" id="search" placeholder="Search organizations..." autocomplete="off">
      <div id="search-dropdown"></div>
    </div>
  </div>
  <div id="controls-row2">
    <button class="toggle-btn active" data-cstatus="Not Contacted">Not Contacted</button>
    <button class="toggle-btn active" data-cstatus="Contacted">Contacted</button>
    <button class="toggle-btn active" data-cstatus="In Discussion">In Discussion</button>
    <button class="toggle-btn active" data-cstatus="Active Partner">Active Partner</button>
    <div id="stats-bar">
      <div class="stat"><div class="num" id="comm-stat-total">0</div><div class="lbl">Visible</div></div>
      <div class="stat"><div class="num" id="comm-stat-nc">0</div><div class="lbl">Not Contact.</div></div>
      <div class="stat"><div class="num" id="comm-stat-p">0</div><div class="lbl">Partners</div></div>
    </div>
  </div>
  <div id="controls-row3">
    <span style="color:rgba(255,255,255,0.6);font-size:11px;font-weight:500">VIEW:</span>
    <button class="view-btn active" id="view-outreach" onclick="setViewMode('outreach')">Outreach Status</button>
    <button class="view-btn" id="view-priority" onclick="setViewMode('priority')">Priority Score</button>
    <div class="sep"></div>
    <button class="top50-btn" id="top50-btn" onclick="toggleTop50()">&#9733; Top 50</button>
    <span style="color:rgba(255,255,255,0.45);font-size:10px" id="top50-label"></span>
    <div style="margin-left:auto">
      <button class="export-btn" onclick="exportCSV()">&#8615; Export CSV</button>
    </div>
  </div>
</div>

<div id="main">
  <div id="map"></div>
  <div id="empty-state">
    <svg width="52" height="52" viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="26" cy="26" r="24" stroke="#e0e0e0" stroke-width="2"/>
      <circle cx="23" cy="23" r="9" stroke="#ccc" stroke-width="2" fill="none"/>
      <path d="M30 30l7 7" stroke="#ccc" stroke-width="2.5" stroke-linecap="round"/>
      <path d="M20 20l6 6M26 20l-6 6" stroke="#e8e8e8" stroke-width="1.5" stroke-linecap="round"/>
    </svg>
    <h3>No organizations match</h3>
    <p>Try adjusting the filters above</p>
  </div>
  <div id="score-legend">
    <div style="font-weight:700;font-size:12px;margin-bottom:6px;color:#333">Priority Score</div>
    <div class="legend-row"><div class="legend-dot" style="background:#1B5E20"></div><span>Very High (&ge;75%)</span></div>
    <div class="legend-row"><div class="legend-dot" style="background:#388E3C"></div><span>High (55–75%)</span></div>
    <div class="legend-row"><div class="legend-dot" style="background:#1565C0"></div><span>Medium (40–55%)</span></div>
    <div class="legend-row"><div class="legend-dot" style="background:#E65100"></div><span>Low (25–40%)</span></div>
    <div class="legend-row"><div class="legend-dot" style="background:#B71C1C"></div><span>Lowest (&lt;25%)</span></div>
  </div>
  <div id="sidebar">
    <div id="sidebar-inner">
      <div id="sidebar-placeholder">Click a pin to view details</div>
      <div id="sidebar-content"></div>
    </div>
  </div>
</div>

<script>
const ORGS = {orgs_json};
const ORG_ACTIVITIES = {acts_json};
const TOP_50_IDS = new Set({top50_json});
const MAX_SCORE = {max_score};

const BASEROW_URL  = "{BASEROW_URL}";
const API_TOKEN    = "{BASEROW_API_TOKEN}";
const VENUES_TABLE = {COMMUNITY_VENUES_TABLE_ID or 0};
const ACTS_TABLE   = {COMMUNITY_ACTIVITIES_TABLE_ID or 0};
const OFFICE_LAT   = {office_lat};
const OFFICE_LNG   = {office_lng};
const RADIUS_MILES = {RADIUS_MILES};
const MAP_ID       = "{GOOGLE_MAPS_MAP_ID}";

let map, officeMarker, radiusCircle;
let orgMarkers = {{}};
let activeTypes = new Set(["Chamber of Commerce","Lions Club","Rotary Club","BNI Chapter","Networking Mixer","Church","Parks & Rec","Community Center","High School","Other"]);
let activeStatuses = new Set(["Not Contacted","Contacted","In Discussion","Active Partner"]);
let actCache  = Object.assign({{}}, ORG_ACTIVITIES);
let selectedMarkerId = null;
let viewMode  = "outreach";   // "outreach" | "priority"
let top50Only = false;

// ── Color maps ────────────────────────────────────────────────────────────────
const STATUS_COLORS = {{
  "Not Contacted": "#455A64",
  "Contacted":     "#1565C0",
  "In Discussion": "#6A1B9A",
  "Active Partner":"#2E7D32",
}};
const TYPE_COLORS = {{
  "Chamber of Commerce":"#0D47A1","Lions Club":"#F57F17","Rotary Club":"#1565C0",
  "BNI Chapter":"#B71C1C","Networking Mixer":"#E65100","Church":"#4E342E",
  "Parks & Rec":"#1B5E20","Community Center":"#880E4F","High School":"#4527A0","Other":"#546E7A",
}};
const TYPE_ICONS = {{
  "Chamber of Commerce": '<rect x="7" y="9" width="10" height="8" rx="1" fill="none" stroke="white" stroke-width="1.5"/><path d="M9 9V7a3 3 0 0 1 6 0v2" stroke="white" stroke-width="1.5" fill="none"/><circle cx="12" cy="13" r="1.5" fill="white"/>',
  "Lions Club": '<path d="M12 5c-1.5 0-3 1-3.5 2.5C8 9 8 10 9 11c.5.5 1 .5 1.5.5H12c1 0 2-.5 2.5-1.5.5-1 .5-2-.5-3C13.5 6 13 5 12 5z" fill="white"/><path d="M9 13c-1 .5-2 1.5-2 3h10c0-1.5-1-2.5-2-3" fill="white"/>',
  "Rotary Club": '<circle cx="12" cy="12" r="5" fill="none" stroke="white" stroke-width="1.5"/><circle cx="12" cy="12" r="2" fill="white"/><circle cx="12" cy="7" r="1" fill="white"/><circle cx="12" cy="17" r="1" fill="white"/><circle cx="7" cy="12" r="1" fill="white"/><circle cx="17" cy="12" r="1" fill="white"/>',
  "BNI Chapter": '<circle cx="8" cy="10" r="2" fill="white"/><circle cx="16" cy="10" r="2" fill="white"/><circle cx="12" cy="15" r="2" fill="white"/><line x1="10" y1="10" x2="14" y2="10" stroke="white" stroke-width="1.5"/><line x1="9" y1="11.5" x2="11" y2="13.5" stroke="white" stroke-width="1.5"/><line x1="15" y1="11.5" x2="13" y2="13.5" stroke="white" stroke-width="1.5"/>',
  "Networking Mixer": '<path d="M8 8h2v2H8zm6 0h2v2h-2zm-3 5h2v2h-2z" fill="white"/><line x1="10" y1="9" x2="14" y2="9" stroke="white" stroke-width="1.5"/><line x1="9" y1="10" x2="11" y2="13" stroke="white" stroke-width="1.5"/><line x1="15" y1="10" x2="13" y2="13" stroke="white" stroke-width="1.5"/>',
  "Church": '<rect x="10" y="12" width="4" height="5" rx="0.5" fill="white"/><path d="M7 12h10L12 7z" fill="white"/><rect x="11" y="5" width="2" height="4" rx="0.5" fill="white"/><rect x="10" y="7" width="4" height="1.5" rx="0.5" fill="white"/>',
  "Parks & Rec": '<path d="M12 5c0 0-5 3-5 6s2 3 5 3 5 0 5-3-5-6-5-6z" fill="white"/><rect x="11" y="14" width="2" height="4" rx="0.5" fill="white"/>',
  "Community Center": '<rect x="6" y="10" width="12" height="8" rx="1" fill="none" stroke="white" stroke-width="1.5"/><path d="M4 10l8-5 8 5" stroke="white" stroke-width="1.5" fill="none"/><rect x="10" y="14" width="4" height="4" rx="0.5" fill="white"/>',
  "High School": '<path d="M12 5l-7 4v1h14v-1z" fill="white"/><rect x="7" y="10" width="10" height="7" rx="0.5" fill="none" stroke="white" stroke-width="1.5"/><rect x="10" y="13" width="4" height="4" rx="0.5" fill="white"/>',
  "Other": '<circle cx="12" cy="12" r="4" fill="white" fill-opacity="0.85"/>',
}};

// ── Pipeline stepper ──────────────────────────────────────────────────────────
const PIPELINE_STEPS = ["Not Contacted","Contacted","In Discussion","Active Partner"];
const PIPELINE_COLORS = {{
  "Not Contacted":"#455A64","Contacted":"#1565C0","In Discussion":"#6A1B9A","Active Partner":"#2E7D32"
}};
function renderPipeline(orgId, status) {{
  const curIdx = PIPELINE_STEPS.indexOf(status);
  let html = '<div class="pipeline-stepper">';
  PIPELINE_STEPS.forEach(function(step, i) {{
    const done   = i < curIdx;
    const active = i === curIdx;
    const col    = PIPELINE_COLORS[step];
    const dotBg  = active ? col : done ? "#2E7D32" : "#fff";
    const dotBdr = active ? col : done ? "#2E7D32" : "#ddd";
    const lineBg = done ? "#2E7D32" : "#e0e0e0";
    const lblCol = active ? col : done ? "#2E7D32" : "#bbb";
    const lblWt  = active ? "700" : "400";
    const lbl    = step.replace(/ /g, "<br>");
    html += '<div class="ps-step" data-step="' + step + '" data-org="' + orgId + '" onclick="pipelineClick(this)" title="Set: ' + step + '">';
    html += '<div style="display:flex;align-items:center;width:100%">';
    html += '<div class="ps-dot" style="background:' + dotBg + ';border-color:' + dotBdr + '"></div>';
    if (i < PIPELINE_STEPS.length - 1) {{
      html += '<div class="ps-line" style="background:' + lineBg + '"></div>';
    }}
    html += '</div>';
    html += '<div class="ps-label" style="color:' + lblCol + ';font-weight:' + lblWt + '">' + lbl + '</div>';
    html += '</div>';
  }});
  html += '</div>';
  html += '<div class="save-st" id="comm-st-status-' + orgId + '"></div>';
  return html;
}}
function pipelineClick(el) {{
  updateStatus(parseInt(el.dataset.org), el.dataset.step);
}}

// ── Score helpers ─────────────────────────────────────────────────────────────
function scoreColor(score) {{
  const pct = MAX_SCORE > 0 ? score / MAX_SCORE : 0;
  if (pct >= 0.75) return "#1B5E20";
  if (pct >= 0.55) return "#388E3C";
  if (pct >= 0.40) return "#1565C0";
  if (pct >= 0.25) return "#E65100";
  return "#B71C1C";
}}

function pinColor(org) {{
  if (viewMode === "priority") return scoreColor(org.score);
  return STATUS_COLORS[org.contactStatus] || "#546E7A";
}}

// ── Activity ring ─────────────────────────────────────────────────────────────
function computeRingColor(id, cache) {{
  const acts = cache[id];
  if (!acts || !acts.length) return null;
  const last = acts[0].date;
  if (!last) return null;
  const days = (Date.now() - new Date(last).getTime()) / 86400000;
  if (days <= 14) return "#4CAF50";
  if (days <= 45) return "#FF9800";
  return "#F44336";
}}

// ── Marker icon ───────────────────────────────────────────────────────────────
function markerIcon(color, scale=9, orgType=null, ringColor=null) {{
  const w = Math.round(scale * 2.4);
  const h = Math.round(w * 1.4);
  const iconHtml = orgType && TYPE_ICONS[orgType]
    ? `<g transform="translate(4,4) scale(0.67)">${{TYPE_ICONS[orgType]}}</g>`
    : `<circle cx="12" cy="12" r="4" fill="white" fill-opacity="0.85"/>`;
  const ringSvg = ringColor
    ? `<circle cx="12" cy="12" r="13" stroke="${{ringColor}}" stroke-width="3" fill="none"/>`
    : "";
  const boxDot = "";
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${{w}}" height="${{h}}" viewBox="0 0 24 33">`
    + ringSvg
    + `<path d="M12 0C5.373 0 0 5.373 0 12c0 8.5 12 21 12 21S24 20.5 24 12C24 5.373 18.627 0 12 0z" fill="${{color}}" stroke="white" stroke-width="1.5"/>`
    + iconHtml
    + boxDot
    + `</svg>`;
  return {{
    url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
    scaledSize: new google.maps.Size(w, h),
    anchor: new google.maps.Point(w / 2, h),
  }};
}}

{ICON_BRIDGE_JS}
// Alias kept so existing `_iconEl(...)` call sites stay terse.
const _iconEl = _mapIconEl;

function homeMarkerIcon() {{
  const w = 34, h = 38;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${{w}}" height="${{h}}" viewBox="0 0 34 38">`
    + `<path d="M17 1L1 13.5V37h12V26h8v11h12V13.5L17 1z" fill="#e94560" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>`
    + `<path d="M13 37V27h8v10" fill="white" fill-opacity="0.2"/>`
    + `</svg>`;
  return {{
    url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
    scaledSize: new google.maps.Size(w, h),
    anchor: new google.maps.Point(w / 2, h),
  }};
}}

// ── Map init ──────────────────────────────────────────────────────────────────
function initMap() {{
  if (!MAP_ID) console.warn('GOOGLE_MAPS_MAP_ID is not set — AdvancedMarkers may not render.');
  const _mapOpts = {{
    center: {{ lat: OFFICE_LAT, lng: OFFICE_LNG }},
    zoom: 12,
    styles: [
      {{featureType:"poi",stylers:[{{visibility:"off"}}]}},
      {{featureType:"transit",stylers:[{{visibility:"off"}}]}},
    ],
  }};
  if (MAP_ID) _mapOpts.mapId = MAP_ID;
  map = new google.maps.Map(document.getElementById("map"), _mapOpts);

  officeMarker = new google.maps.marker.AdvancedMarkerElement({{
    position: {{ lat: OFFICE_LAT, lng: OFFICE_LNG }},
    map, title: "Reform Chiropractic",
    content: _iconEl(homeMarkerIcon()),
    zIndex: 9999,
  }});

  radiusCircle = new google.maps.Circle({{
    map, center: {{ lat: OFFICE_LAT, lng: OFFICE_LNG }},
    radius: RADIUS_MILES * 1609.34,
    strokeColor: "#e94560", strokeOpacity: 0.25, strokeWeight: 1,
    fillColor: "#e94560", fillOpacity: 0.03,
  }});

  ORGS.forEach(org => {{
    const m = new google.maps.marker.AdvancedMarkerElement({{
      position: {{ lat: org.lat, lng: org.lng }},
      map, title: org.name,
      content: _iconEl(markerIcon(pinColor(org), 9, org.type, computeRingColor(org.id, actCache))),
    }});
    m.addListener("gmpClick", () => openOrgSidebar(org.id));
    orgMarkers[org.id] = m;
  }});

  updateStats();
  setupSearch();
  setupLayerToggles();
  document.addEventListener("keydown", function(e) {{ if (e.key === "Escape") clearSidebar(); }});
}}

// ── Visibility ────────────────────────────────────────────────────────────────
function clearSidebar() {{
  clearSelectedMarker();
  document.getElementById("sidebar").classList.remove("open");
  document.getElementById("sidebar-placeholder").style.display = "block";
  const c = document.getElementById("sidebar-content");
  c.className = ""; c.innerHTML = "";
}}

function updateVisibility() {{
  let anyVisible = false;
  ORGS.forEach(org => {{
    const m = orgMarkers[org.id];
    if (!m) return;
    const typeOk   = activeTypes.has(org.type);
    const statusOk = activeStatuses.has(org.contactStatus);
    const top50Ok  = !top50Only || TOP_50_IDS.has(org.id);
    const show = typeOk && statusOk && top50Ok;
    m.map = show ? map : null;
    m.content = _iconEl(markerIcon(pinColor(org), 9, org.type, computeRingColor(org.id, actCache)));
    if (show) anyVisible = true;
  }});
  updateStats();
  const es = document.getElementById("empty-state");
  if (es) es.classList.toggle("visible", !anyVisible);
}}

function animateStat(el, target) {{
  const from = parseInt(el.textContent) || 0;
  if (from === target) {{ el.textContent = target; return; }}
  const steps = 14;
  const diff = (target - from) / steps;
  let step = 0;
  const tid = setInterval(function() {{
    step++;
    el.textContent = step >= steps ? target : Math.round(from + diff * step);
    if (step >= steps) clearInterval(tid);
  }}, 22);
}}

function updateStats() {{
  const visible = ORGS.filter(o => {{
    const typeOk   = activeTypes.has(o.type);
    const statusOk = activeStatuses.has(o.contactStatus);
    const top50Ok  = !top50Only || TOP_50_IDS.has(o.id);
    return typeOk && statusOk && top50Ok;
  }});
  animateStat(document.getElementById("comm-stat-total"), visible.length);
  animateStat(document.getElementById("comm-stat-nc"), visible.filter(o => o.contactStatus === "Not Contacted").length);
  animateStat(document.getElementById("comm-stat-p"),  visible.filter(o => o.contactStatus === "Active Partner").length);
}}

// ── View mode ─────────────────────────────────────────────────────────────────
function setViewMode(mode) {{
  viewMode = mode;
  document.getElementById("view-outreach").classList.toggle("active", mode === "outreach");
  document.getElementById("view-priority").classList.toggle("active", mode === "priority");
  document.getElementById("score-legend").classList.toggle("visible", mode === "priority");
  updateVisibility();
}}

function toggleTop50() {{
  top50Only = !top50Only;
  const btn = document.getElementById("top50-btn");
  btn.classList.toggle("active", top50Only);
  document.getElementById("top50-label").textContent = top50Only ? "(showing top 50)" : "";
  updateVisibility();
}}

// ── Layer toggles ─────────────────────────────────────────────────────────────
function setupLayerToggles() {{
  document.querySelectorAll(".toggle-btn[data-ctype]").forEach(btn => {{
    btn.addEventListener("click", () => {{
      const t = btn.dataset.ctype;
      if (activeTypes.has(t)) {{ activeTypes.delete(t); btn.classList.remove("active"); }}
      else {{ activeTypes.add(t); btn.classList.add("active"); }}
      updateVisibility();
    }});
  }});
  document.querySelectorAll(".toggle-btn[data-cstatus]").forEach(btn => {{
    btn.addEventListener("click", () => {{
      const s = btn.dataset.cstatus;
      if (activeStatuses.has(s)) {{ activeStatuses.delete(s); btn.classList.remove("active"); }}
      else {{ activeStatuses.add(s); btn.classList.add("active"); }}
      updateVisibility();
    }});
  }});
}}

// ── Search ────────────────────────────────────────────────────────────────────
function setupSearch() {{
  const input = document.getElementById("search");
  const dd    = document.getElementById("search-dropdown");
  input.addEventListener("input", () => {{
    const q = input.value.trim().toLowerCase();
    if (!q) {{ dd.style.display = "none"; return; }}
    const matches = ORGS.filter(o =>
      o.name.toLowerCase().includes(q) || o.type.toLowerCase().includes(q)
    ).slice(0, 8);
    if (!matches.length) {{ dd.style.display = "none"; return; }}
    function hl(s) {{ return String(s).replace(new RegExp(q.replace(/[.*+?^${{}}()|[\]\\\\]/g,"\\$&"),"gi"), m => `<span class="search-highlight">${{m}}</span>`); }}
    dd.innerHTML = matches.map(o => `
      <div class="search-item" onclick="selectSearch(${{o.id}})">
        <div class="si-name">${{hl(o.name)}}</div>
        <div class="si-meta">${{hl(o.type)}} &middot; ${{o.address}}</div>
      </div>`).join("");
    dd.style.display = "block";
  }});
  document.addEventListener("click", e => {{
    if (!document.getElementById("search-container").contains(e.target)) dd.style.display = "none";
  }});
}}

function selectSearch(id) {{
  const org = ORGS.find(o => o.id === id);
  if (!org) return;
  document.getElementById("search-dropdown").style.display = "none";
  document.getElementById("search").value = org.name;
  map.setCenter({{ lat: org.lat, lng: org.lng }});
  map.setZoom(15);
  openOrgSidebar(id);
}}

// ── Selected marker ───────────────────────────────────────────────────────────
function setSelectedMarker(id) {{
  if (selectedMarkerId !== null) {{
    const prev = orgMarkers[selectedMarkerId];
    if (prev) {{
      const org = ORGS.find(o => o.id === selectedMarkerId);
      if (org) prev.content = _iconEl(markerIcon(pinColor(org), 9, org.type, computeRingColor(org.id, actCache)));
      // prev.setAnimation(null);  // AdvancedMarker has no setAnimation API; pin scale conveys selection.
    }}
  }}
  selectedMarkerId = id;
  const m = orgMarkers[id];
  if (m) {{
    const org = ORGS.find(o => o.id === id);
    if (org) m.content = _iconEl(markerIcon(pinColor(org), 13, org.type, computeRingColor(id, actCache)));
    // m.setAnimation(BOUNCE) — not supported on AdvancedMarker.
  }}
}}

function clearSelectedMarker() {{
  if (selectedMarkerId === null) return;
  const m = orgMarkers[selectedMarkerId];
  if (m) {{
    const org = ORGS.find(o => o.id === selectedMarkerId);
    if (org) m.content = _iconEl(markerIcon(pinColor(org), 9, org.type, computeRingColor(org.id, actCache)));
    // m.setAnimation(null);  // AdvancedMarker has no setAnimation API.
  }}
  selectedMarkerId = null;
}}

// ── Sidebar ───────────────────────────────────────────────────────────────────
function openOrgSidebar(orgId) {{
  setSelectedMarker(orgId);
  const org = ORGS.find(o => o.id === orgId);
  if (!org) return;

  document.getElementById("sidebar").classList.add("open");
  document.getElementById("sidebar-placeholder").style.display = "none";
  const c = document.getElementById("sidebar-content");
  c.className = "visible";

  const activities = actCache[orgId] || [];
  const goalColors = {{"Event Presence":"#1565C0","Referral Partnership":"#2E7D32","Sponsorship":"#E65100","Both":"#6A1B9A"}};
  const goalColor   = goalColors[org.outreachGoal] || "#546E7A";
  const statusColor = STATUS_COLORS[org.contactStatus] || "#455A64";
  const isTop50     = TOP_50_IDS.has(org.id);

  const lastAct = activities.length ? activities[0] : null;
  const lastActDays = (lastAct && lastAct.date) ? Math.floor((Date.now() - new Date(lastAct.date).getTime()) / 86400000) : null;
  const lastActLabel = lastActDays === null ? "" : lastActDays === 0 ? "Today" : lastActDays === 1 ? "Yesterday" : lastActDays + "d ago";
  const lastActColor = lastActDays === null ? "#aaa" : lastActDays > 30 ? "#e94560" : lastActDays > 14 ? "#E65100" : "#2E7D32";

  c.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
      <div class="ent-name" style="margin-bottom:0">${{esc(org.name || org.address || "Unknown")}}</div>
      <button onclick="clearSidebar()" title="Close" style="background:none;border:none;font-size:18px;line-height:1;cursor:pointer;color:#999;padding:0 2px;flex-shrink:0;">&#x2715;</button>
    </div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:4px;">
      <span class="badge" style="background:${{TYPE_COLORS[org.type]||'#546E7A'}};color:#fff">${{esc(org.type)}}</span>
      <span class="badge" style="background:${{statusColor}};color:#fff">${{esc(org.contactStatus||"Not Contacted")}}</span>
      ${{org.outreachGoal ? `<span class="badge" style="background:${{goalColor}};color:#fff">${{esc(org.outreachGoal)}}</span>` : ""}}
      <span class="score-badge">&#9733; Score: ${{org.score}}</span>
      ${{isTop50 ? '<span class="badge" style="background:#F57F17;color:#fff">Top 50</span>' : ""}}
    </div>
    ${{lastActLabel ? `<div class="last-act-chip">&#128337; Last contact: <strong style="color:${{lastActColor}}">${{lastActLabel}}</strong>${{lastActDays > 30 ? '&nbsp;<span style="font-size:10px;color:#e94560">— follow up!</span>' : ""}}</div>` : ""}}
    <hr class="divider">

    <div class="slabel" style="margin-bottom:8px">Contact Info</div>
    ${{org.address ? `<div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:8px"><span>&#128205;</span><span class="sval">${{esc(org.address)}}</span></div>` : ""}}
    ${{org.phone ? `<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px"><span>&#128222;</span><a class="link" href="tel:${{org.phone}}">${{esc(org.phone)}}</a></div>` : ""}}

    <div class="section">
      <div class="slabel">Contact Person</div>
      <input type="text" class="editable-field" id="cp-${{orgId}}" value="${{esc(org.contactPerson||'')}}"
        placeholder="Enter contact name..."
        onblur="saveField(${{orgId}}, 'Contact Person', this.value, 'cp-st-${{orgId}}')">
      <div class="save-indicator" id="cp-st-${{orgId}}"></div>
    </div>

    <div class="section">
      <div class="slabel">Email</div>
      <input type="email" class="editable-field" id="em-${{orgId}}" value="${{esc(org.email||'')}}"
        placeholder="Enter email address..."
        onblur="saveField(${{orgId}}, 'Email', this.value, 'em-st-${{orgId}}')">
      <div class="save-indicator" id="em-st-${{orgId}}"></div>
    </div>

    ${{org.website ? `<div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:8px"><span>&#127760;</span><a class="link" href="${{esc(org.website)}}" target="_blank" style="word-break:break-all">${{esc(org.website)}}</a></div>` : ""}}
    ${{(org.googleMapsUrl||org.yelpUrl) ? `<div style="display:flex;gap:10px;margin-bottom:12px">${{org.googleMapsUrl?`<a class="link" href="${{org.googleMapsUrl}}" target="_blank">Google Maps &#8599;</a>`:""}}${{org.yelpUrl?`<a class="link" href="${{org.yelpUrl}}" target="_blank">Yelp &#8599;</a>`:""}}</div>` : ""}}
    <hr class="divider">

    <div class="slabel" style="margin-bottom:8px">Details</div>
    ${{org.distance ? `<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px"><span>&#127991;&#65039;</span><span class="sval">${{esc(String(org.distance))}} miles from office</span></div>` : ""}}
    ${{org.rating ? `<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px"><span>&#11088;</span><span class="sval">${{"&#9733;".repeat(Math.round(parseFloat(org.rating)||0))}}<span style="color:#888;font-size:12px;margin-left:4px">${{esc(String(org.rating))}} (${{org.reviews||0}} reviews)</span></span></div>` : ""}}
    <hr class="divider">

    <div class="section"><div class="slabel">Outreach Pipeline</div>
      ${{renderPipeline(orgId, org.contactStatus)}}
    </div>

    <div class="section">
      <div class="slabel">Notes</div>
      <div class="notes-log" id="comm-notes-log-${{orgId}}">${{renderNotesLog(org.notes)}}</div>
      <div style="display:flex;gap:6px;margin-top:8px;">
        <input type="text" class="fi" id="comm-notes-input-${{orgId}}" placeholder="Add a note..." style="flex:1;">
        <button onclick="addNote(${{orgId}})" style="background:#e94560;color:#fff;border:none;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:12px;font-weight:600;">Add</button>
      </div>
      <div class="save-st" id="comm-note-st-${{orgId}}"></div>
    </div>
    <hr class="divider">

    <div class="section"><div class="slabel">Activities (${{activities.length}})</div>
      <div id="comm-act-log-${{orgId}}">
        ${{activities.length ? activities.map(renderAct).join("") : '<div class="no-acts">No activities yet</div>'}}
      </div>
    </div>
    ${{renderLogForm(orgId)}}
  `;
}}

// ── Field savers ──────────────────────────────────────────────────────────────
async function saveField(id, fieldName, value, stId) {{
  const org = ORGS.find(o => o.id === id);
  if (!org) return;
  const stEl = document.getElementById(stId);
  if (stEl) stEl.textContent = "Saving...";
  const data = {{}};
  data[fieldName] = value;
  try {{
    await bpatch(VENUES_TABLE, id, data);
    if (fieldName === "Contact Person") org.contactPerson = value;
    if (fieldName === "Email") org.email = value;
    if (stEl) {{ stEl.textContent = "Saved &#10003;"; setTimeout(()=>{{if(stEl)stEl.textContent="";}},2000); }}
  }} catch(e) {{
    if (stEl) stEl.textContent = "Save failed";
  }}
}}

async function updateStatus(id, val) {{
  const org = ORGS.find(o => o.id === id);
  if (!org) return;
  org.contactStatus = val;
  const m = orgMarkers[id];
  if (m) m.content = _iconEl(markerIcon(pinColor(org), selectedMarkerId === id ? 13 : 9, org.type, computeRingColor(id, actCache)));
  updateStats();
  const st = document.getElementById(`comm-st-status-${{id}}`);
  if (st) st.textContent = "Saving...";
  await bpatch(VENUES_TABLE, id, {{"Contact Status": {{"value": val}}}});
  if (st) {{ st.textContent = "Saved &#10003;"; setTimeout(()=>{{if(st)st.textContent="";}},2000); }}
}}

// ── Activities ────────────────────────────────────────────────────────────────
async function logActivity(id) {{
  const btn = document.getElementById(`comm-log-btn-${{id}}`);
  const st  = document.getElementById(`comm-log-st-${{id}}`);
  btn.disabled = true;
  if (st) st.textContent = "Saving...";
  const date     = document.getElementById(`comm-act-date-${{id}}`).value;
  const type     = document.getElementById(`comm-act-type-${{id}}`).value;
  const outcome  = document.getElementById(`comm-act-outcome-${{id}}`).value;
  const person   = document.getElementById(`comm-act-person-${{id}}`).value;
  const summary  = document.getElementById(`comm-act-summary-${{id}}`).value;
  const followup = document.getElementById(`comm-act-followup-${{id}}`).value;
  try {{
    const resp = await bpost(ACTS_TABLE, {{
      "Organization":  [id],
      "Date":          date || null,
      "Type":          {{"value": type}},
      "Outcome":       {{"value": outcome}},
      "Contact Person": person,
      "Summary":       summary,
      "Follow-Up Date": followup || null,
    }});
    if (resp.ok) {{
      const newAct = {{ id: (await resp.json()).id, date, type, outcome, contactPerson: person, summary, followUpDate: followup }};
      if (!actCache[id]) actCache[id] = [];
      actCache[id].unshift(newAct);
      const logEl = document.getElementById(`comm-act-log-${{id}}`);
      if (logEl) logEl.innerHTML = actCache[id].map(renderAct).join("");
      document.getElementById(`comm-act-summary-${{id}}`).value = "";
      document.getElementById(`comm-act-person-${{id}}`).value  = "";
      document.getElementById(`comm-act-followup-${{id}}`).value = "";
      if (st) {{ st.textContent = "Saved &#10003;"; setTimeout(()=>{{if(st)st.textContent="";}},3000); }}
      // Refresh ring color
      const m = orgMarkers[id];
      if (m) {{
        const org = ORGS.find(o => o.id === id);
        if (org) m.content = _iconEl(markerIcon(pinColor(org), selectedMarkerId===id?13:9, org.type, computeRingColor(id, actCache)));
      }}
    }} else {{
      if (st) st.textContent = "Failed to save";
    }}
  }} catch(e) {{
    if (st) st.textContent = "Error: " + e.message;
  }}
  btn.disabled = false;
}}

function renderLogForm(id) {{
  return `
    <div class="log-form">
      <h4>+ Log Activity</h4>
      <div class="fr"><label class="fl">Date</label><input type="date" class="fi" id="comm-act-date-${{id}}" value="${{new Date().toISOString().split("T")[0]}}"></div>
      <div class="fr"><label class="fl">Type</label><select class="fi" id="comm-act-type-${{id}}">
        <option>Call</option><option>Email</option><option>Drop-In</option><option>Meeting</option><option>Event</option><option>Mail</option><option>Other</option>
      </select></div>
      <div class="fr"><label class="fl">Outcome</label><select class="fi" id="comm-act-outcome-${{id}}">
        <option>No Answer</option><option>Left Message</option><option>Spoke With</option><option>Scheduled Meeting</option><option>Declined</option><option>Follow-Up Needed</option>
      </select></div>
      <div class="fr"><label class="fl">Contact Person</label><input type="text" class="fi" id="comm-act-person-${{id}}" placeholder="Name"></div>
      <div class="fr"><label class="fl">Summary</label><textarea class="fta" id="comm-act-summary-${{id}}" placeholder="What happened..."></textarea></div>
      <div class="fr"><label class="fl">Follow-Up Date (optional)</label><input type="date" class="fi" id="comm-act-followup-${{id}}"></div>
      <button class="log-btn" id="comm-log-btn-${{id}}" onclick="logActivity(${{id}})">Save Activity</button>
      <div class="form-st" id="comm-log-st-${{id}}"></div>
    </div>`;
}}

function renderAct(a) {{
  return `<div class="act-item">
    <div class="act-hdr"><span class="act-type">${{esc(a.type)}}</span><span class="act-date">${{esc(a.date||"")}}</span></div>
    <div class="act-outcome">${{esc(a.outcome||"")}}</div>
    ${{a.contactPerson?`<div class="act-person">with ${{esc(a.contactPerson)}}</div>`:""}}
    ${{a.summary?`<div class="act-summary">${{esc(a.summary)}}</div>`:""}}
    ${{a.followUpDate?`<div class="act-followup">Follow up: ${{esc(a.followUpDate)}}</div>`:""}}
  </div>`;
}}

function renderNotesLog(notesText) {{
  if (!notesText || !notesText.trim()) return '<div style="color:#aaa;font-size:12px;padding:4px 0;">No notes yet</div>';
  return notesText.split('\\n---\\n').filter(e => e.trim()).map(entry => {{
    const match = entry.match(/^\\[(\\d{{4}}-\\d{{2}}-\\d{{2}})\\] ([\\s\\S]*)$/);
    if (match) {{
      return `<div style="padding:6px 0;border-bottom:1px solid #f0f0f0;">
        <div style="font-size:10px;color:#aaa;margin-bottom:2px;">${{match[1]}}</div>
        <div style="font-size:12px;color:#333;">${{esc(match[2].trim())}}</div>
      </div>`;
    }}
    return `<div style="padding:6px 0;border-bottom:1px solid #f0f0f0;font-size:12px;color:#333;">${{esc(entry.trim())}}</div>`;
  }}).join('');
}}

async function addNote(id) {{
  const inputEl = document.getElementById(`comm-notes-input-${{id}}`);
  const st      = document.getElementById(`comm-note-st-${{id}}`);
  const text    = (inputEl?.value || '').trim();
  if (!text) return;
  const today    = new Date().toISOString().split('T')[0];
  const newEntry = `[${{today}}] ${{text}}`;
  const org = ORGS.find(o => o.id === id);
  if (!org) return;
  const existing = (org.notes || '').trim();
  org.notes = existing ? newEntry + '\\n---\\n' + existing : newEntry;
  inputEl.value = '';
  const logEl = document.getElementById(`comm-notes-log-${{id}}`);
  if (logEl) logEl.innerHTML = renderNotesLog(org.notes);
  if (st) st.textContent = 'Saving...';
  try {{
    await bpatch(VENUES_TABLE, id, {{'Notes': org.notes}});
    if (st) {{ st.textContent = 'Saved &#10003;'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
  }} catch(e) {{ if (st) st.textContent = 'Save failed'; }}
}}

// ── Export CSV ────────────────────────────────────────────────────────────────
function exportCSV() {{
  const visible = ORGS.filter(o => {{
    return activeTypes.has(o.type) && activeStatuses.has(o.contactStatus) && (!top50Only || TOP_50_IDS.has(o.id));
  }});
  const headers = ["Name","Type","Status","Score","Distance (mi)","Phone","Email","Contact Person","Address","Last Activity","Total Activities"];
  const rows = visible.map(o => {{
    const acts  = actCache[o.id] || [];
    const lastAct = acts.length ? (acts[0].date || "") : "";
    return [o.name, o.type, o.contactStatus, o.score, o.distance||"", o.phone||"", o.email||"",
            o.contactPerson||"", o.address||"", lastAct, acts.length]
      .map(v => '"' + String(v||"").replace(/"/g,'""') + '"').join(",");
  }});
  const csv  = [headers.join(","), ...rows].join("\\n");
  const blob = new Blob([csv], {{type:"text/csv"}});
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = "community_outreach_" + new Date().toISOString().split("T")[0] + ".csv";
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}}

// ── Baserow API helpers ───────────────────────────────────────────────────────
function apiHdrs() {{
  return {{ "Authorization": `Token ${{API_TOKEN}}`, "Content-Type": "application/json" }};
}}
function bpatch(tableId, rowId, data) {{
  return fetch(`${{BASEROW_URL}}/api/database/rows/table/${{tableId}}/${{rowId}}/?user_field_names=true`,
    {{ method:"PATCH", headers: apiHdrs(), body: JSON.stringify(data) }});
}}
function bpost(tableId, data) {{
  return fetch(`${{BASEROW_URL}}/api/database/rows/table/${{tableId}}/?user_field_names=true`,
    {{ method:"POST", headers: apiHdrs(), body: JSON.stringify(data) }});
}}
function esc(s) {{
  return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}}
</script>

<script async defer
  src="https://maps.googleapis.com/maps/api/js?key={GOOGLE_MAPS_API_KEY}&v=weekly&libraries=marker&callback=initMap">
</script>
</body>
</html>"""


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("COMMUNITY OUTREACH — MAP GENERATOR v2")
    print("=" * 60)

    if not load_community_table_ids():
        print("\nERROR: Could not find required Baserow tables.")
        return

    orgs       = load_organizations()
    activities = load_community_activities()

    if not orgs:
        print("\nERROR: No organization data found. Run scrape + sync scripts first.")
        return

    scores = [o["score"] for o in orgs]
    top50  = sorted(orgs, key=lambda o: o["score"], reverse=True)[:50]
    print(f"\n  Score range: {min(scores)}–{max(scores)}")
    print(f"  Top 50 threshold: score >= {top50[-1]['score'] if top50 else 0}")

    print(f"\nGenerating Community Outreach map...")
    html = generate_html(orgs, activities)

    os.makedirs(".tmp", exist_ok=True)
    output_path = ".tmp/community_map.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n  Output: {output_path}")
    print(f"  {len(orgs)} organizations | {sum(len(v) for v in activities.values())} activities")
    print("\nOpen .tmp/community_map.html in your browser.")


if __name__ == "__main__":
    main()
