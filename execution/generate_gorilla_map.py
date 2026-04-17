#!/usr/bin/env python3
"""
Generate the Gorilla Marketing map.

Reads live from Baserow:
  - Business Venues + Business Activities (auto-discovered in database 203)

Output: .tmp/gorilla_map.html

Usage:
    python execution/generate_gorilla_map.py
"""

import os
import sys
import json
import time
import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

BASEROW_URL = os.getenv("BASEROW_URL")
BASEROW_EMAIL = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
BASEROW_API_TOKEN = os.getenv("BASEROW_API_TOKEN")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
OFFICE_LATLNG = os.getenv("ATTORNEY_MAPPER_OFFICE_LAT_LNG", "34.0522,-118.2437")
RADIUS_MILES = float(os.getenv("ATTORNEY_MAPPER_RADIUS_MILES", 15))

GORILLA_VENUES_TABLE_ID = int(os.getenv("GORILLA_VENUES_TABLE_ID", 0)) or None
GORILLA_ACTIVITIES_TABLE_ID = int(os.getenv("GORILLA_ACTIVITIES_TABLE_ID", 0)) or None
GORILLA_MASSAGE_BOXES_TABLE_ID = int(os.getenv("GORILLA_MASSAGE_BOXES_TABLE_ID", 0)) or None

# ─── JWT Auth ─────────────────────────────────────────────────────────────────

_jwt_token = None
_jwt_time = 0


def fresh_token():
    global _jwt_token, _jwt_time
    if _jwt_token is None or (time.time() - _jwt_time) > 480:
        r = requests.post(f"{BASEROW_URL}/api/user/token-auth/", json={
            "email": BASEROW_EMAIL, "password": BASEROW_PASSWORD,
        })
        r.raise_for_status()
        _jwt_token = r.json()["access_token"]
        _jwt_time = time.time()
    return _jwt_token


def hdrs():
    return {"Authorization": f"JWT {fresh_token()}", "Content-Type": "application/json"}


# ─── Data Loading ──────────────────────────────────────────────────────────────

def read_all_rows(table_id):
    rows = []
    page = 1
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
    """Extract single_select value from Baserow response."""
    if isinstance(field, dict):
        return field.get("value", "")
    return field or ""


def load_gorilla_table_ids():
    global GORILLA_VENUES_TABLE_ID, GORILLA_ACTIVITIES_TABLE_ID, GORILLA_MASSAGE_BOXES_TABLE_ID

    if not GORILLA_VENUES_TABLE_ID:
        print("Auto-discovering Business Venues table...")
        GORILLA_VENUES_TABLE_ID = find_table_by_name(203, "Business Venues")
        if not GORILLA_VENUES_TABLE_ID:
            print("  ERROR: 'Business Venues' table not found. Run setup_gorilla_marketing_tables.py")
            return False
        print(f"  Business Venues: {GORILLA_VENUES_TABLE_ID}")

    if not GORILLA_ACTIVITIES_TABLE_ID:
        print("Auto-discovering Business Activities table...")
        GORILLA_ACTIVITIES_TABLE_ID = find_table_by_name(203, "Business Activities")
        if not GORILLA_ACTIVITIES_TABLE_ID:
            print("  ERROR: 'Business Activities' table not found.")
            return False
        print(f"  Business Activities: {GORILLA_ACTIVITIES_TABLE_ID}")

    if not GORILLA_MASSAGE_BOXES_TABLE_ID:
        print("Auto-discovering Massage Boxes table...")
        GORILLA_MASSAGE_BOXES_TABLE_ID = find_table_by_name(203, "Massage Boxes")
        if GORILLA_MASSAGE_BOXES_TABLE_ID:
            print(f"  Massage Boxes: {GORILLA_MASSAGE_BOXES_TABLE_ID}")
        else:
            print("  WARN: 'Massage Boxes' table not found — massage box features disabled.")

    return True


def load_businesses():
    print("Loading Business Venues from Baserow...")
    rows = read_all_rows(GORILLA_VENUES_TABLE_ID)
    print(f"  {len(rows)} venues")

    businesses = []
    for row in rows:
        try:
            lat = float(row.get("Latitude") or 0)
            lng = float(row.get("Longitude") or 0)
        except (TypeError, ValueError):
            continue
        if not lat or not lng:
            continue

        google_reviews = []
        reviews_raw = row.get("Google Reviews JSON", "")
        if reviews_raw:
            try:
                google_reviews = json.loads(reviews_raw)
            except Exception:
                pass

        businesses.append({
            "id": row["id"],
            "name": row.get("Name", "") or row.get("Business Name", "") or "",
            "type": _sv(row.get("Type")),
            "address": row.get("Address", "") or "",
            "phone": row.get("Phone", "") or "",
            "website": row.get("Website", "") or "",
            "rating": row.get("Rating", "") or "",
            "reviews": row.get("Reviews", 0) or 0,
            "distance": row.get("Distance (mi)", "") or "",
            "contactStatus": _sv(row.get("Contact Status")) or "Not Contacted",
            "outreachGoal": _sv(row.get("Outreach Goal")),
            "notes": row.get("Notes", "") or "",
            "googleMapsUrl": row.get("Google Maps URL", "") or "",
            "yelpUrl": row.get("Yelp Search URL", "") or "",
            "googleReviews": google_reviews,
            "lat": lat,
            "lng": lng,
        })

    print(f"  {len(businesses)} businesses with coordinates")
    return businesses


def load_gorilla_activities():
    print("Loading Business Activities from Baserow...")
    rows = read_all_rows(GORILLA_ACTIVITIES_TABLE_ID)
    print(f"  {len(rows)} activities")

    by_id = {}
    for row in rows:
        links = row.get("Business", [])
        if not links:
            continue
        act = {
            "id": row["id"],
            "date": row.get("Date", "") or "",
            "type": _sv(row.get("Type")),
            "outcome": _sv(row.get("Outcome")),
            "contactPerson": row.get("Contact Person", "") or "",
            "summary": row.get("Summary", "") or "",
            "followUpDate": row.get("Follow-Up Date", "") or "",
        }
        for link in links:
            bid = link.get("id")
            if bid:
                by_id.setdefault(bid, []).append(act)

    for bid in by_id:
        by_id[bid].sort(key=lambda a: a.get("date", "") or "", reverse=True)
    return by_id


def load_massage_boxes():
    if not GORILLA_MASSAGE_BOXES_TABLE_ID:
        return {}
    print("Loading Massage Boxes from Baserow...")
    rows = read_all_rows(GORILLA_MASSAGE_BOXES_TABLE_ID)
    print(f"  {len(rows)} massage boxes")

    by_id = {}
    for row in rows:
        links = row.get("Business", [])
        if not links:
            continue
        box = {
            "id":            row["id"],
            "datePlaced":    row.get("Date Placed", "") or "",
            "dateRemoved":   row.get("Date Removed", "") or "",
            "locationNotes": row.get("Location Notes", "") or "",
            "status":        _sv(row.get("Status")) or "Active",
            "leadsGenerated": row.get("Leads Generated", 0) or 0,
            "notes":         row.get("Notes", "") or "",
        }
        for link in links:
            bid = link.get("id")
            if bid:
                by_id.setdefault(bid, []).append(box)

    for bid in by_id:
        by_id[bid].sort(key=lambda b: b.get("datePlaced", "") or "", reverse=True)
    return by_id


# ─── HTML Generation ───────────────────────────────────────────────────────────

def generate_html(businesses, biz_activities, massage_boxes):
    office_lat, office_lng = [float(x.strip()) for x in OFFICE_LATLNG.split(",")]

    def strip_backticks(obj):
        if isinstance(obj, str):  return obj.replace('`', '')
        if isinstance(obj, list): return [strip_backticks(i) for i in obj]
        if isinstance(obj, dict): return {k: strip_backticks(v) for k, v in obj.items()}
        return obj

    biz_json = json.dumps(strip_backticks(businesses), ensure_ascii=False)
    biz_act_json = json.dumps(strip_backticks(biz_activities), ensure_ascii=False)
    boxes_json = json.dumps(strip_backticks(massage_boxes), ensure_ascii=False)
    boxes_table_id = GORILLA_MASSAGE_BOXES_TABLE_ID or 0

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gorilla Marketing</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f6fa; color: #222; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}

    #header {{ background: #0f3460; padding: 0 16px; display: flex; align-items: center; border-bottom: 2px solid #1a4a8a; flex-shrink: 0; box-shadow: 0 1px 4px rgba(0,0,0,0.08); min-height: 44px; }}
    #header .brand h1 {{ font-size: 14px; font-weight: 700; color: #fff; letter-spacing: 1px; }}
    #header .brand .tagline {{ font-size: 10px; color: rgba(255,255,255,0.55); }}

    #controls {{ background: #0f3460; padding: 7px 14px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; border-bottom: 1px solid #1a4a8a; flex-shrink: 0; min-height: 42px; }}

    #search-container {{ position: relative; margin-left: auto; }}
    #search {{ background: #fff; border: 1px solid #ddd; color: #222; padding: 5px 10px; border-radius: 6px; font-size: 13px; width: 200px; }}
    #search::placeholder {{ color: #aaa; }}
    #search-dropdown {{ position: absolute; top: 100%; left: 0; width: 310px; background: #fff; border: 1px solid #ddd; border-radius: 6px; max-height: 200px; overflow-y: auto; z-index: 1000; display: none; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
    .search-item {{ padding: 7px 10px; cursor: pointer; border-bottom: 1px solid #f0f0f0; }}
    .search-item:hover {{ background: #f5f6fa; }}
    .search-item .si-name {{ font-size: 13px; font-weight: 600; }}
    .search-item .si-meta {{ font-size: 11px; color: #888; margin-top: 1px; }}
    .search-highlight {{ color: #e94560; font-weight: 700; }}

    .toggle-btn {{ padding: 3px 9px; border-radius: 10px; border: 1px solid #ccc; background: transparent; color: #555; font-size: 11px; cursor: pointer; transition: all 0.2s; white-space: nowrap; }}
    .toggle-btn.active {{ border-color: transparent; color: #fff; }}
    .toggle-btn[data-type="Gym"].active {{ background: #1565C0; border-color: #1565C0; }}
    .toggle-btn[data-type="Yoga Studio"].active {{ background: #6A1B9A; border-color: #6A1B9A; }}
    .toggle-btn[data-type="Health Store"].active {{ background: #BF360C; border-color: #BF360C; }}
    .toggle-btn[data-type="Chiropractor/Wellness"].active {{ background: #1B5E20; border-color: #1B5E20; }}
    .toggle-btn[data-bstatus="Not Contacted"].active {{ background: #455A64; border-color: #455A64; }}
    .toggle-btn[data-bstatus="Contacted"].active {{ background: #1565C0; border-color: #1565C0; }}
    .toggle-btn[data-bstatus="In Discussion"].active {{ background: #6A1B9A; border-color: #6A1B9A; }}
    .toggle-btn[data-bstatus="Partner"].active {{ background: #2E7D32; border-color: #2E7D32; }}

    #stats-bar {{ display: flex; gap: 12px; }}
    .stat {{ text-align: center; }}
    .stat .num {{ font-size: 16px; font-weight: 700; color: #fff; }}
    .stat .lbl {{ font-size: 9px; color: rgba(255,255,255,0.55); text-transform: uppercase; }}

    #main {{ position: relative; display: flex; flex: 1; overflow: hidden; }}
    #map {{ flex: 1; }}

    #sidebar {{ position: absolute; top: 0; right: 0; bottom: 0; width: 340px; background: #fff; border-left: 1px solid #e8e8e8; overflow-y: auto; transform: translateX(100%); transition: transform 0.3s cubic-bezier(0.4,0,0.2,1); z-index: 100; box-shadow: -4px 0 20px rgba(0,0,0,0.15); }}
    #sidebar.open {{ transform: translateX(0); }}
    #sidebar-inner {{ padding: 14px; }}
    #sidebar-placeholder {{ color: #bbb; font-size: 13px; text-align: center; margin-top: 50px; }}
    #sidebar-content {{ display: none; }}
    #sidebar-content.visible {{ display: block; }}

    .ent-name {{ font-size: 15px; font-weight: 700; color: #111; margin-bottom: 4px; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; margin-right: 4px; margin-bottom: 6px; }}
    .section {{ margin-bottom: 12px; }}
    .slabel {{ font-size: 10px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 3px; }}
    .sval {{ font-size: 13px; color: #444; }}
    a.link {{ color: #1a73e8; text-decoration: none; font-size: 12px; }}
    a.link:hover {{ text-decoration: underline; }}
    .divider {{ border: none; border-top: 1px solid #eee; margin: 12px 0; }}
    .stars {{ color: #f4a922; font-size: 12px; }}

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

    .log-form {{ background: #f5f6fa; border-radius: 7px; padding: 11px; margin-top: 10px; border: 1px solid #eee; }}
    .log-form h4 {{ font-size: 12px; color: #e94560; margin-bottom: 8px; }}
    .fr {{ margin-bottom: 7px; }}
    .fl {{ font-size: 10px; color: #999; margin-bottom: 2px; display: block; }}
    .fi {{ width: 100%; padding: 4px 7px; background: #fff; border: 1px solid #ddd; color: #222; border-radius: 4px; font-size: 12px; }}
    .fi:focus {{ outline: none; border-color: #e94560; }}
    .fta {{ width: 100%; padding: 4px 7px; background: #fff; border: 1px solid #ddd; color: #222; border-radius: 4px; font-size: 12px; resize: vertical; min-height: 55px; font-family: inherit; }}
    .log-btn {{ padding: 6px 0; background: #e94560; color: #fff; border: none; border-radius: 5px; font-size: 12px; cursor: pointer; font-weight: 600; width: 100%; margin-top: 4px; }}
    .log-btn:hover {{ background: #c0392b; }}
    .log-btn:disabled {{ background: #ccc; cursor: default; }}
    .form-st {{ font-size: 10px; color: #aaa; margin-top: 3px; }}

    .notes-log {{ max-height: 160px; overflow-y: auto; border: 1px solid #eee; border-radius: 6px; padding: 6px 8px; background: #fafafa; margin-top: 4px; }}
    .notes-log > div:last-child {{ border-bottom: none; }}
  </style>
</head>
<body>

<div id="header">
  <div class="brand">
    <h1>GORILLA MARKETING</h1>
    <div class="tagline">Local Business Outreach</div>
  </div>
</div>

<div id="controls">
  <div style="display:flex;gap:5px;flex-wrap:wrap">
    <button class="toggle-btn active" data-type="Gym">Gyms</button>
    <button class="toggle-btn active" data-type="Yoga Studio">Yoga</button>
    <button class="toggle-btn active" data-type="Health Store">Health</button>
    <button class="toggle-btn active" data-type="Chiropractor/Wellness">Wellness</button>
  </div>
  <div style="display:flex;gap:5px;flex-wrap:wrap">
    <button class="toggle-btn active" data-bstatus="Not Contacted">Not Contacted</button>
    <button class="toggle-btn active" data-bstatus="Contacted">Contacted</button>
    <button class="toggle-btn active" data-bstatus="In Discussion">In Discussion</button>
    <button class="toggle-btn active" data-bstatus="Partner">Partner</button>
  </div>
  <div id="stats-bar">
    <div class="stat"><div class="num" id="biz-stat-total">0</div><div class="lbl">Total</div></div>
    <div class="stat"><div class="num" id="biz-stat-nc">0</div><div class="lbl">Not Contact.</div></div>
    <div class="stat"><div class="num" id="biz-stat-p">0</div><div class="lbl">Partner</div></div>
    <div class="stat"><div class="num" id="biz-stat-boxes">0</div><div class="lbl">Active Massage Boxes</div></div>
  </div>
  <div id="search-container">
    <input type="text" id="search" placeholder="Search businesses..." autocomplete="off">
    <div id="search-dropdown"></div>
  </div>
</div>

<div id="main">
  <div id="map"></div>
  <div id="sidebar">
    <div id="sidebar-inner">
      <div id="sidebar-placeholder">Click a pin to view details</div>
      <div id="sidebar-content"></div>
    </div>
  </div>
</div>

<script>
const BUSINESSES = {biz_json};
const BIZ_ACTIVITIES = {biz_act_json};
const MASSAGE_BOXES = {boxes_json};

const BASEROW_URL = "{BASEROW_URL}";
const API_TOKEN = "{BASEROW_API_TOKEN}";
const VENUES_TABLE = {GORILLA_VENUES_TABLE_ID or 0};
const BIZ_ACTS_TABLE = {GORILLA_ACTIVITIES_TABLE_ID or 0};
const BOXES_TABLE = {boxes_table_id};
const OFFICE_LAT = {office_lat};
const OFFICE_LNG = {office_lng};
const RADIUS_MILES = {RADIUS_MILES};

let map, officeMarker, radiusCircle;
let bizMarkers = {{}};
let activeTypes = new Set(["Gym", "Yoga Studio", "Health Store", "Chiropractor/Wellness"]);
let activeBizStatuses = new Set(["Not Contacted", "Contacted", "In Discussion", "Partner"]);
let bizActCache = Object.assign({{}}, BIZ_ACTIVITIES);
let boxCache = Object.assign({{}}, MASSAGE_BOXES);
let selectedMarkerId = null;

const BIZ_STATUS_COLORS = {{
  "Not Contacted": "#455A64",
  "Contacted": "#1565C0",
  "In Discussion": "#6A1B9A",
  "Partner": "#2E7D32",
}};

const BIZ_TYPE_ICONS = {{
  "Gym": '<circle cx="5.5" cy="12" r="2" fill="white"/><circle cx="18.5" cy="12" r="2" fill="white"/><rect x="7" y="10" width="10" height="4" rx="1" fill="white"/>',
  "Yoga Studio": '<path d="M12 5a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm-1 2c-1 0-2 .5-2.5 1.5L7 11h2l1-1.5V15l-2 3h2l1-2 1 2h2l-2-3v-5.5L13 11h2l-1.5-2.5C13 7.5 12 7 11 7z" fill="white"/>',
  "Health Store": '<rect x="10.5" y="6" width="3" height="12" rx="1" fill="white"/><rect x="6" y="10.5" width="12" height="3" rx="1" fill="white"/>',
  "Chiropractor/Wellness": '<path d="M12 4c0 0-6 3-6 8s6 8 6 8 6-3 6-8-6-8-6-8z" fill="none" stroke="white" stroke-width="1.5"/><circle cx="12" cy="12" r="2" fill="white"/>',
}};

function typeColor(type) {{
  return {{Gym:"#1565C0","Yoga Studio":"#6A1B9A","Health Store":"#E65100","Chiropractor/Wellness":"#1B5E20"}}[type] || "#333";
}}

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

function hasActiveBox(id) {{
  const boxes = boxCache[id];
  return boxes ? boxes.some(b => b.status === "Active") : false;
}}

function markerIcon(color, scale=9, bizType=null, ringColor=null, dropBox=false) {{
  const w = Math.round(scale * 2.4);
  const h = Math.round(w * 1.4);
  const iconHtml = bizType && BIZ_TYPE_ICONS[bizType]
    ? `<g transform="translate(4,4) scale(0.67)">${{BIZ_TYPE_ICONS[bizType]}}</g>`
    : `<circle cx="12" cy="12" r="4" fill="white" fill-opacity="0.85"/>`;
  const ringSvg = ringColor ? `<circle cx="12" cy="12" r="13" stroke="${{ringColor}}" stroke-width="3" fill="none"/>` : "";
  const boxDot = dropBox ? `<circle cx="20" cy="4" r="4" fill="#FF6D00" stroke="white" stroke-width="1.2"/>` : "";
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

function homeMarkerIcon() {{
  const w = 34, h = 38;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${{w}}" height="${{h}}" viewBox="0 0 34 38">`
    + `<path d="M17 1L1 13.5V37h12V26h8v11h12V13.5L17 1z" fill="#e94560" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>`
    + `<path d="M13 37V27h8v10" fill="white" fill-opacity="0.2"/>`
    + `<path d="M17 4L3 15.5V37h10V26h8v11h10V15.5L17 4z" fill="none" stroke="white" stroke-width="0.5" opacity="0.4"/>`
    + `</svg>`;
  return {{
    url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
    scaledSize: new google.maps.Size(w, h),
    anchor: new google.maps.Point(w / 2, h),
  }};
}}

function initMap() {{
  map = new google.maps.Map(document.getElementById("map"), {{
    center: {{ lat: OFFICE_LAT, lng: OFFICE_LNG }},
    zoom: 12,
    styles: [
      {{featureType:"poi",stylers:[{{visibility:"off"}}]}},
      {{featureType:"transit",stylers:[{{visibility:"off"}}]}},
    ],
  }});

  officeMarker = new google.maps.Marker({{
    position: {{ lat: OFFICE_LAT, lng: OFFICE_LNG }},
    map, title: "Reform Chiropractic",
    icon: homeMarkerIcon(),
    zIndex: 9999,
  }});

  radiusCircle = new google.maps.Circle({{
    map, center: {{ lat: OFFICE_LAT, lng: OFFICE_LNG }},
    radius: RADIUS_MILES * 1609.34,
    strokeColor: "#e94560", strokeOpacity: 0.25, strokeWeight: 1,
    fillColor: "#e94560", fillOpacity: 0.03,
  }});

  BUSINESSES.forEach(biz => {{
    const m = new google.maps.Marker({{
      position: {{ lat: biz.lat, lng: biz.lng }},
      map, title: biz.name,
      icon: markerIcon(BIZ_STATUS_COLORS[biz.contactStatus] || "#546E7A", 9, biz.type, computeRingColor(biz.id, bizActCache), hasActiveBox(biz.id)),
    }});
    m.addListener("click", () => openBizSidebar(biz.id));
    bizMarkers[biz.id] = m;
  }});

  updateBizStats();
  setupSearch();
  setupLayerToggles();
}}

function clearSidebar() {{
  clearSelectedMarker();
  document.getElementById("sidebar").classList.remove("open");
  document.getElementById("sidebar-placeholder").style.display = "block";
  const c = document.getElementById("sidebar-content");
  c.className = ""; c.innerHTML = "";
}}

function updateBizVisibility() {{
  BUSINESSES.forEach(biz => {{
    const m = bizMarkers[biz.id];
    if (!m) return;
    m.setVisible(activeTypes.has(biz.type) && activeBizStatuses.has(biz.contactStatus));
    m.setIcon(markerIcon(BIZ_STATUS_COLORS[biz.contactStatus] || "#546E7A", 9, biz.type, computeRingColor(biz.id, bizActCache), hasActiveBox(biz.id)));
  }});
  updateBizStats();
}}

function updateBizStats() {{
  const visible = BUSINESSES.filter(b => activeTypes.has(b.type));
  document.getElementById("biz-stat-total").textContent = visible.length;
  document.getElementById("biz-stat-nc").textContent = visible.filter(b => b.contactStatus === "Not Contacted").length;
  document.getElementById("biz-stat-p").textContent = visible.filter(b => b.contactStatus === "Partner").length;
  let activeBoxes = 0;
  Object.values(boxCache).forEach(boxes => {{ activeBoxes += boxes.filter(b => b.status === "Active").length; }});
  document.getElementById("biz-stat-boxes").textContent = activeBoxes;
}}

function setupLayerToggles() {{
  document.querySelectorAll(".toggle-btn[data-type]").forEach(btn => {{
    btn.addEventListener("click", () => {{
      const t = btn.dataset.type;
      if (activeTypes.has(t)) {{ activeTypes.delete(t); btn.classList.remove("active"); }}
      else {{ activeTypes.add(t); btn.classList.add("active"); }}
      updateBizVisibility();
    }});
  }});
  document.querySelectorAll(".toggle-btn[data-bstatus]").forEach(btn => {{
    btn.addEventListener("click", () => {{
      const s = btn.dataset.bstatus;
      if (activeBizStatuses.has(s)) {{ activeBizStatuses.delete(s); btn.classList.remove("active"); }}
      else {{ activeBizStatuses.add(s); btn.classList.add("active"); }}
      updateBizVisibility();
    }});
  }});
}}

function setupSearch() {{
  const input = document.getElementById("search");
  const dd = document.getElementById("search-dropdown");
  input.addEventListener("input", () => {{
    const q = input.value.trim().toLowerCase();
    if (!q) {{ dd.style.display = "none"; return; }}
    const matches = BUSINESSES.filter(b =>
      b.name.toLowerCase().includes(q) || b.type.toLowerCase().includes(q)
    ).slice(0, 8);
    if (!matches.length) {{ dd.style.display = "none"; return; }}
    function hl(s) {{ return String(s).replace(new RegExp(q.replace(/[.*+?^${{}}()|[\]\\]/g,"\\$&"),"gi"), m => `<span class="search-highlight">${{m}}</span>`); }}
    dd.innerHTML = matches.map(b => `
      <div class="search-item" onclick="selectBizSearch(${{b.id}})">
        <div class="si-name">${{hl(b.name)}}</div>
        <div class="si-meta">${{hl(b.type)}} &middot; ${{b.address}}</div>
      </div>`).join("");
    dd.style.display = "block";
  }});
  document.addEventListener("click", e => {{
    if (!document.getElementById("search-container").contains(e.target)) dd.style.display = "none";
  }});
}}

function selectBizSearch(id) {{
  const biz = BUSINESSES.find(b => b.id === id);
  if (!biz) return;
  document.getElementById("search-dropdown").style.display = "none";
  document.getElementById("search").value = biz.name;
  map.setCenter({{ lat: biz.lat, lng: biz.lng }});
  map.setZoom(15);
  openBizSidebar(id);
}}

function setSelectedMarker(id) {{
  if (selectedMarkerId !== null) {{
    const prev = bizMarkers[selectedMarkerId];
    if (prev) {{
      const biz = BUSINESSES.find(b => b.id === selectedMarkerId);
      if (biz) prev.setIcon(markerIcon(BIZ_STATUS_COLORS[biz.contactStatus] || "#546E7A", 9, biz.type, computeRingColor(biz.id, bizActCache), hasActiveBox(biz.id)));
      prev.setAnimation(null);
    }}
  }}
  selectedMarkerId = id;
  const m = bizMarkers[id];
  if (m) {{
    const biz = BUSINESSES.find(b => b.id === id);
    if (biz) m.setIcon(markerIcon(BIZ_STATUS_COLORS[biz.contactStatus] || "#546E7A", 13, biz.type, computeRingColor(id, bizActCache), hasActiveBox(id)));
    m.setAnimation(google.maps.Animation.BOUNCE);
    setTimeout(() => {{ if (selectedMarkerId === id) m.setAnimation(null); }}, 600);
  }}
}}

function clearSelectedMarker() {{
  if (selectedMarkerId === null) return;
  const m = bizMarkers[selectedMarkerId];
  if (m) {{
    const biz = BUSINESSES.find(b => b.id === selectedMarkerId);
    if (biz) m.setIcon(markerIcon(BIZ_STATUS_COLORS[biz.contactStatus] || "#546E7A", 9, biz.type, computeRingColor(biz.id, bizActCache), hasActiveBox(biz.id)));
    m.setAnimation(null);
  }}
  selectedMarkerId = null;
}}

function bizDisplayName(biz) {{
  if (biz.name) return biz.name;
  if (biz.yelpUrl) {{
    const slug = (biz.yelpUrl.split('/biz/')[1] || "").split('?')[0];
    if (slug) {{
      try {{
        const clean = decodeURIComponent(slug).replace(/-\d+$/, "");
        return clean.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
      }} catch(e) {{
        const clean = slug.replace(/-\d+$/, "");
        return clean.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
      }}
    }}
  }}
  return biz.address ? biz.address.split(',')[0] : 'Unknown';
}}

function openBizSidebar(bizId) {{
  setSelectedMarker(bizId);
  const biz = BUSINESSES.find(b => b.id === bizId);
  if (!biz) return;

  document.getElementById("sidebar").classList.add("open");
  document.getElementById("sidebar-placeholder").style.display = "none";
  const c = document.getElementById("sidebar-content");
  c.className = "visible";

  const activities = bizActCache[bizId] || [];
  const boxes = boxCache[bizId] || [];
  const activeBoxes = boxes.filter(b => b.status === "Active").length;
  const goalClass = biz.outreachGoal === "Referral Partner" ? "#0d47a1" : biz.outreachGoal === "Co-Marketing" ? "#4a148c" : "#1b5e20";
  const name = bizDisplayName(biz);
  const statusColor = BIZ_STATUS_COLORS[biz.contactStatus] || "#455A64";

  c.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
      <div class="ent-name" style="margin-bottom:0">${{esc(name)}}</div>
      <button onclick="clearSidebar()" title="Close" style="background:none;border:none;font-size:18px;line-height:1;cursor:pointer;color:#999;padding:0 2px;flex-shrink:0;">✕</button>
    </div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:4px;">
      <span class="badge" style="background:${{typeColor(biz.type)}};color:#fff">${{esc(biz.type)}}</span>
      <span class="badge" style="background:${{statusColor}};color:#fff">${{esc(biz.contactStatus||"Not Contacted")}}</span>
      ${{biz.outreachGoal ? `<span class="badge" style="background:${{goalClass}};color:#ddd">${{esc(biz.outreachGoal)}}</span>` : ""}}
      ${{activeBoxes > 0 ? `<span class="badge" style="background:#FF6D00;color:#fff">&#128230; ${{activeBoxes}} Massage Box${{activeBoxes>1?"es":""}}</span>` : ""}}
    </div>
    <hr class="divider">
    <div class="slabel" style="margin-bottom:8px">Contact Info</div>
    ${{biz.address ? `<div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:8px"><span>📍</span><span class="sval">${{esc(biz.address)}}</span></div>` : ""}}
    ${{biz.phone ? `<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px"><span>📞</span><a class="link" href="tel:${{biz.phone}}">${{esc(biz.phone)}}</a></div>` : ""}}
    ${{biz.website ? `<div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:8px"><span>🌐</span><a class="link" href="${{esc(biz.website)}}" target="_blank" style="word-break:break-all">${{esc(biz.website)}}</a></div>` : ""}}
    ${{(biz.googleMapsUrl||biz.yelpUrl) ? `<div style="display:flex;gap:10px;margin-bottom:12px;padding-left:26px">${{biz.googleMapsUrl?`<a class="link" href="${{biz.googleMapsUrl}}" target="_blank">Google Maps ↗</a>`:""}}${{biz.yelpUrl?`<a class="link" href="${{biz.yelpUrl}}" target="_blank">Yelp ↗</a>`:""}}</div>` : ""}}
    <hr class="divider">
    <div class="slabel" style="margin-bottom:8px">Details</div>
    ${{biz.distance ? `<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px"><span>🏷️</span><span class="sval">${{esc(String(biz.distance))}} miles from office</span></div>` : ""}}
    ${{biz.rating ? `<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px"><span>⭐</span><span class="sval">${{"★".repeat(Math.round(parseFloat(biz.rating)||0))}}<span style="color:#888;font-size:12px;margin-left:4px">${{esc(String(biz.rating))}} (${{biz.reviews||0}} reviews)</span></span></div>` : ""}}
    <hr class="divider">
    <div class="section"><div class="slabel">Contact Status</div>
      <select class="status-select" onchange="updateBizStatus(${{bizId}}, this.value)">
        <option ${{biz.contactStatus==="Not Contacted"?"selected":""}}>Not Contacted</option>
        <option ${{biz.contactStatus==="Contacted"?"selected":""}}>Contacted</option>
        <option ${{biz.contactStatus==="In Discussion"?"selected":""}}>In Discussion</option>
        <option ${{biz.contactStatus==="Partner"?"selected":""}}>Partner</option>
      </select>
    </div>
    <div class="section">
      <div class="slabel">Notes</div>
      <div class="notes-log" id="biz-notes-log-${{bizId}}">${{renderNotesLog(biz.notes)}}</div>
      <div style="display:flex;gap:6px;margin-top:8px;">
        <input type="text" class="fi" id="biz-notes-input-${{bizId}}" placeholder="Add a note..." style="flex:1;">
        <button onclick="addNote(${{bizId}})" style="background:#e94560;color:#fff;border:none;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:12px;font-weight:600;">Add</button>
      </div>
      <div class="save-st" id="biz-note-st-${{bizId}}"></div>
    </div>
    <hr class="divider">
    <div class="section">
      <div class="slabel">Massage Boxes (${{boxes.length}})
        ${{activeBoxes > 0 ? `<span style="color:#FF6D00;font-weight:700;margin-left:6px">&#128230; ${{activeBoxes}} Active</span>` : ""}}
      </div>
      <div id="biz-box-log-${{bizId}}">
        ${{boxes.length ? boxes.map(renderBox).join("") : '<div class="no-acts">No massage boxes logged</div>'}}
      </div>
      ${{BOXES_TABLE ? renderBoxForm(bizId) : ""}}
    </div>
    <hr class="divider">
    <div class="section"><div class="slabel">Activities (${{activities.length}})</div>
      <div id="biz-act-log-${{bizId}}">
        ${{activities.length ? activities.map(renderAct).join("") : '<div class="no-acts">No activities yet</div>'}}
      </div>
    </div>
    ${{renderLogForm(bizId)}}
  `;
}}

async function updateBizStatus(id, val) {{
  const biz = BUSINESSES.find(b => b.id === id);
  if (!biz) return;
  biz.contactStatus = val;
  const m = bizMarkers[id];
  if (m) m.setIcon(markerIcon(BIZ_STATUS_COLORS[val] || "#546E7A", 9, biz.type, computeRingColor(id, bizActCache), hasActiveBox(id)));
  updateBizStats();
  await bpatch(VENUES_TABLE, id, {{"Contact Status": {{"value": val}}}});
}}

async function logBizActivity(id) {{
  const btn = document.getElementById(`biz-log-btn-${{id}}`);
  const st = document.getElementById(`biz-log-st-${{id}}`);
  btn.disabled = true;
  if (st) st.textContent = "Saving...";
  const date = document.getElementById(`biz-act-date-${{id}}`).value;
  const type = document.getElementById(`biz-act-type-${{id}}`).value;
  const outcome = document.getElementById(`biz-act-outcome-${{id}}`).value;
  const person = document.getElementById(`biz-act-person-${{id}}`).value;
  const summary = document.getElementById(`biz-act-summary-${{id}}`).value;
  const followup = document.getElementById(`biz-act-followup-${{id}}`).value;
  try {{
    const resp = await bpost(BIZ_ACTS_TABLE, {{
      "Business": [{{id}}],
      "Date": date || null,
      "Type": {{"value": type}},
      "Outcome": {{"value": outcome}},
      "Contact Person": person,
      "Summary": summary,
      "Follow-Up Date": followup || null,
    }});
    if (resp.ok) {{
      const newAct = {{ id: (await resp.json()).id, date, type, outcome, contactPerson: person, summary, followUpDate: followup }};
      if (!bizActCache[id]) bizActCache[id] = [];
      bizActCache[id].unshift(newAct);
      const logEl = document.getElementById(`biz-act-log-${{id}}`);
      if (logEl) logEl.innerHTML = bizActCache[id].map(renderAct).join("");
      document.getElementById(`biz-act-summary-${{id}}`).value = "";
      document.getElementById(`biz-act-person-${{id}}`).value = "";
      document.getElementById(`biz-act-followup-${{id}}`).value = "";
      if (st) {{ st.textContent = "Saved ✓"; setTimeout(()=>{{if(st)st.textContent="";}},3000); }}
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
      <div class="fr"><label class="fl">Date</label><input type="date" class="fi" id="biz-act-date-${{id}}" value="${{new Date().toISOString().split("T")[0]}}"></div>
      <div class="fr"><label class="fl">Type</label><select class="fi" id="biz-act-type-${{id}}">
        <option>Call</option><option>Email</option><option>Drop-In</option><option>Meeting</option><option>Mail</option><option>Other</option>
      </select></div>
      <div class="fr"><label class="fl">Outcome</label><select class="fi" id="biz-act-outcome-${{id}}">
        <option>No Answer</option><option>Left Message</option><option>Spoke With</option><option>Scheduled Meeting</option><option>Declined</option><option>Follow-Up Needed</option>
      </select></div>
      <div class="fr"><label class="fl">Contact Person</label><input type="text" class="fi" id="biz-act-person-${{id}}" placeholder="Name"></div>
      <div class="fr"><label class="fl">Summary</label><textarea class="fta" id="biz-act-summary-${{id}}" placeholder="What happened..."></textarea></div>
      <div class="fr"><label class="fl">Follow-Up Date (optional)</label><input type="date" class="fi" id="biz-act-followup-${{id}}"></div>
      <button class="log-btn" id="biz-log-btn-${{id}}" onclick="logBizActivity(${{id}})">Save Activity</button>
      <div class="form-st" id="biz-log-st-${{id}}"></div>
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
    const match = entry.match(/^\[(\d{{4}}-\d{{2}}-\d{{2}})\] ([\s\S]*)$/);
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
  const inputEl = document.getElementById(`biz-notes-input-${{id}}`);
  const st = document.getElementById(`biz-note-st-${{id}}`);
  const text = (inputEl?.value || '').trim();
  if (!text) return;
  const today = new Date().toISOString().split('T')[0];
  const newEntry = `[${{today}}] ${{text}}`;
  const entity = BUSINESSES.find(b => b.id === id);
  if (!entity) return;
  const existing = (entity.notes || '').trim();
  entity.notes = existing ? newEntry + '\\n---\\n' + existing : newEntry;
  inputEl.value = '';
  const logEl = document.getElementById(`biz-notes-log-${{id}}`);
  if (logEl) logEl.innerHTML = renderNotesLog(entity.notes);
  if (st) st.textContent = 'Saving...';
  try {{
    await bpatch(VENUES_TABLE, id, {{'Notes': entity.notes}});
    if (st) {{ st.textContent = 'Saved ✓'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
  }} catch(e) {{ if (st) st.textContent = 'Save failed'; }}
}}

// ── Massage Boxes ─────────────────────────────────────────────────────────────
function renderBox(b) {{
  const statusLabel = b.status === "Active"
    ? `<span style="color:#FF6D00;font-weight:700;font-size:11px">&#9679; ACTIVE</span>`
    : b.status === "Lost"
    ? `<span style="color:#F44336;font-weight:700;font-size:11px">&#10007; LOST</span>`
    : `<span style="color:#4CAF50;font-weight:700;font-size:11px">&#10003; PICKED UP</span>`;
  return `<div class="act-item">
    <div class="act-hdr">${{statusLabel}}<span class="act-date">${{esc(b.datePlaced||"")}}</span></div>
    ${{b.locationNotes ? `<div class="act-summary">&#128205; ${{esc(b.locationNotes)}}</div>` : ""}}
    ${{b.dateRemoved ? `<div class="act-person">Removed: ${{esc(b.dateRemoved)}}</div>` : ""}}
    ${{b.leadsGenerated ? `<div class="act-person">&#128200; ${{b.leadsGenerated}} lead${{b.leadsGenerated>1?"s":""}}</div>` : ""}}
    ${{b.notes ? `<div class="act-summary">${{esc(b.notes)}}</div>` : ""}}
  </div>`;
}}

function renderBoxForm(id) {{
  return `
    <div class="log-form" style="margin-top:8px">
      <h4>&#128230; Log Massage Box</h4>
      <div class="fr"><label class="fl">Date Placed</label><input type="date" class="fi" id="box-date-${{id}}" value="${{new Date().toISOString().split("T")[0]}}"></div>
      <div class="fr"><label class="fl">Location Notes</label><input type="text" class="fi" id="box-loc-${{id}}" placeholder="e.g. Front desk, waiting room"></div>
      <div class="fr"><label class="fl">Status</label><select class="fi" id="box-status-${{id}}">
        <option value="Active">Active</option>
        <option value="Picked Up">Picked Up</option>
        <option value="Lost">Lost</option>
      </select></div>
      <div class="fr"><label class="fl">Leads Generated</label><input type="number" class="fi" id="box-leads-${{id}}" value="0" min="0"></div>
      <div class="fr"><label class="fl">Notes</label><textarea class="fta" id="box-notes-${{id}}" placeholder="Any additional notes..."></textarea></div>
      <button class="log-btn" id="box-btn-${{id}}" onclick="logBox(${{id}})">Save Massage Box</button>
      <div class="form-st" id="box-st-${{id}}"></div>
    </div>`;
}}

async function logBox(id) {{
  const btn = document.getElementById(`box-btn-${{id}}`);
  const st = document.getElementById(`box-st-${{id}}`);
  btn.disabled = true;
  if (st) st.textContent = "Saving...";
  const datePlaced = document.getElementById(`box-date-${{id}}`).value;
  const locationNotes = document.getElementById(`box-loc-${{id}}`).value;
  const status = document.getElementById(`box-status-${{id}}`).value;
  const leadsGenerated = parseInt(document.getElementById(`box-leads-${{id}}`).value) || 0;
  const notes = document.getElementById(`box-notes-${{id}}`).value;
  try {{
    const resp = await bpost(BOXES_TABLE, {{
      "Business": [{{id}}],
      "Date Placed": datePlaced || null,
      "Location Notes": locationNotes,
      "Status": {{"value": status}},
      "Leads Generated": leadsGenerated,
      "Notes": notes,
    }});
    if (resp.ok) {{
      const newBox = {{ id: (await resp.json()).id, datePlaced, locationNotes, status, leadsGenerated, notes, dateRemoved: "" }};
      if (!boxCache[id]) boxCache[id] = [];
      boxCache[id].unshift(newBox);
      const logEl = document.getElementById(`biz-box-log-${{id}}`);
      if (logEl) logEl.innerHTML = boxCache[id].map(renderBox).join("");
      document.getElementById(`box-loc-${{id}}`).value = "";
      document.getElementById(`box-leads-${{id}}`).value = "0";
      document.getElementById(`box-notes-${{id}}`).value = "";
      if (st) {{ st.textContent = "Saved &#10003;"; setTimeout(()=>{{if(st)st.textContent="";}},3000); }}
      const m = bizMarkers[id];
      if (m) {{
        const biz = BUSINESSES.find(b => b.id === id);
        if (biz) m.setIcon(markerIcon(BIZ_STATUS_COLORS[biz.contactStatus]||"#546E7A", 9, biz.type, computeRingColor(id, bizActCache), hasActiveBox(id)));
      }}
      updateBizStats();
      openBizSidebar(id);
    }} else {{
      if (st) st.textContent = "Failed to save";
    }}
  }} catch(e) {{
    if (st) st.textContent = "Error: " + e.message;
  }}
  btn.disabled = false;
}}

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
  src="https://maps.googleapis.com/maps/api/js?key={GOOGLE_MAPS_API_KEY}&callback=initMap">
</script>
</body>
</html>"""


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("GORILLA MARKETING — MAP GENERATOR")
    print("=" * 60)

    print("\n── Gorilla Marketing Data ──")
    if not load_gorilla_table_ids():
        print("\nERROR: Could not find Baserow tables. Run setup_gorilla_marketing_tables.py first.")
        return

    businesses = load_businesses()
    biz_activities = load_gorilla_activities()
    massage_boxes = load_massage_boxes()

    if not businesses:
        print("\nERROR: No business data found in Baserow. Run scrape + sync scripts first.")
        return

    print(f"\nGenerating Gorilla Marketing map...")
    print(f"  {len(businesses)} businesses | {sum(len(v) for v in biz_activities.values())} activities | {sum(len(v) for v in massage_boxes.values())} massage boxes")

    html = generate_html(businesses, biz_activities, massage_boxes)

    os.makedirs(".tmp", exist_ok=True)
    output_path = ".tmp/gorilla_map.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nSaved: {output_path}")
    print("Open in browser.")

    type_counts = {}
    for b in businesses:
        t = b.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    print("\nPin breakdown:")
    for t, count in sorted(type_counts.items()):
        print(f"  {t}: {count}")


if __name__ == "__main__":
    main()
