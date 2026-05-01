#!/usr/bin/env python3
"""
Generate the Attorney CRM map.

Reads live from Baserow:
  - Law Firms (768) + Activities (784) + case tables (772/773/775/776)

Output: .tmp/attorney_map.html

Usage:
    python execution/generate_attorney_map.py
"""

import os
import sys
import json
import time
import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Make `hub.*` importable when invoked from the workspace root
# (e.g. `python execution/generate_attorney_map.py`).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hub.maps import ICON_BRIDGE_JS  # noqa: E402

load_dotenv()

BASEROW_URL = os.getenv("BASEROW_URL")
BASEROW_EMAIL = os.getenv("BASEROW_EMAIL")
BASEROW_PASSWORD = os.getenv("BASEROW_PASSWORD")
BASEROW_API_TOKEN = os.getenv("BASEROW_API_TOKEN")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
GOOGLE_MAPS_MAP_ID  = os.getenv("GOOGLE_MAPS_MAP_ID", "")
OFFICE_LATLNG = os.getenv("ATTORNEY_MAPPER_OFFICE_LAT_LNG", "34.0522,-118.2437")
RADIUS_MILES = float(os.getenv("ATTORNEY_MAPPER_RADIUS_MILES", 15))

LAW_FIRMS_TABLE_ID = 768
ATT_ACTIVITIES_TABLE_ID = 784
CLOSED_CASES_TABLE_ID = 772
ACTIVE_CASES_TABLE_ID = 775
BILLED_TABLE_ID = 773
AWAITING_TABLE_ID = 776

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


def _sv(field):
    """Extract single_select value from Baserow response."""
    if isinstance(field, dict):
        return field.get("value", "")
    return field or ""


def load_attorneys():
    print("Loading Law Firms from Baserow...")
    rows = read_all_rows(LAW_FIRMS_TABLE_ID)
    print(f"  {len(rows)} firms")

    def firm_names_from(table_id):
        names = {}
        for row in read_all_rows(table_id):
            name = (row.get("Law Firm Name") or "").strip().lower()
            if name:
                names[name] = names.get(name, 0) + 1
        return names

    print("  Loading case stats...")
    active_counts = firm_names_from(ACTIVE_CASES_TABLE_ID)
    billed_counts = firm_names_from(BILLED_TABLE_ID)
    awaiting_counts = firm_names_from(AWAITING_TABLE_ID)
    closed_counts = firm_names_from(CLOSED_CASES_TABLE_ID)

    attorneys = []
    for row in rows:
        try:
            lat = float(row.get("Latitude") or 0)
            lng = float(row.get("Longitude") or 0)
        except (TypeError, ValueError):
            continue
        if not lat or not lng:
            continue

        name = row.get("Law Firm Name", "")
        name_lower = name.strip().lower()

        active = row.get("Active Patients") or active_counts.get(name_lower, 0)
        billed = row.get("Billed Patients") or billed_counts.get(name_lower, 0)
        awaiting = row.get("Awaiting Billing") or awaiting_counts.get(name_lower, 0)
        settled = row.get("Settled Cases") or closed_counts.get(name_lower, 0)
        total = int(active) + int(billed) + int(awaiting) + int(settled)

        google_reviews = []
        reviews_raw = row.get("Google Reviews JSON", "")
        if reviews_raw:
            try:
                google_reviews = json.loads(reviews_raw)
            except Exception:
                pass

        attorneys.append({
            "id": row["id"],
            "name": name,
            "address": row.get("Law Office Address", "") or "",
            "phone": row.get("Phone Number", "") or "",
            "fax": row.get("Fax Number", "") or "",
            "email": row.get("Email Address", "") or "",
            "website": row.get("Website", "") or "",
            "rating": row.get("Rating", "") or "",
            "reviews": row.get("Reviews", 0) or 0,
            "distance": row.get("Distance (mi)", "") or "",
            "classification": _sv(row.get("Classification")),
            "contactStatus": _sv(row.get("Contact Status")) or "Not Contacted",
            "patientCount": row.get("Patient Count", 0) or 0,
            "notes": row.get("Notes", "") or "",
            "preferredMRI": row.get("Preferred MRI Facility", "") or "",
            "preferredPM": row.get("Preferred PM Facility", "") or "",
            "activeCases": int(active),
            "billedCases": int(billed),
            "awaitingBilling": int(awaiting),
            "settledCases": int(settled),
            "totalCases": total,
            "googleReviews": google_reviews,
            "googleMapsUrl": row.get("Google Maps URL", "") or "",
            "yelpSearchUrl": row.get("Yelp Search URL", "") or "",
            "lat": lat,
            "lng": lng,
        })

    print(f"  {len(attorneys)} attorneys with coordinates")
    return attorneys


def load_attorney_activities():
    print("Loading attorney Activities...")
    rows = read_all_rows(ATT_ACTIVITIES_TABLE_ID)
    print(f"  {len(rows)} activities")

    by_id = {}
    for row in rows:
        links = row.get("Law Firm", [])
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
            "createdBy": row.get("Created By", "") or "",
        }
        for link in links:
            fid = link.get("id")
            if fid:
                by_id.setdefault(fid, []).append(act)

    for fid in by_id:
        by_id[fid].sort(key=lambda a: a.get("date", "") or "", reverse=True)
    return by_id


def build_closed_cases_by_firm(closed_cases):
    """Group closed case rows by normalized law firm name."""
    by_firm = {}
    for row in closed_cases:
        firm = (row.get("Law Firm Name") or "").strip()
        if not firm:
            continue
        key = firm.lower()
        if key not in by_firm:
            by_firm[key] = {"display": firm, "cases": []}
        by_firm[key]["cases"].append({
            "label": (row.get("Case Label") or "").strip(),
            "doi":   (row.get("DOI") or "").strip(),
            "visits": str(row.get("# of Visits") or "").strip(),
        })
    for entry in by_firm.values():
        entry["cases"].sort(key=lambda c: c["doi"] or "", reverse=True)
    return by_firm


# ─── HTML Generation ───────────────────────────────────────────────────────────

def generate_html(attorneys, att_activities, closed_cases_by_firm=None):
    office_lat, office_lng = [float(x.strip()) for x in OFFICE_LATLNG.split(",")]

    att_json = json.dumps(attorneys, ensure_ascii=False)
    att_act_json = json.dumps(att_activities, ensure_ascii=False)
    closed_cases_json = json.dumps(closed_cases_by_firm or {}, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Attorney CRM</title>
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
    .toggle-btn[data-status="Not Contacted"].active {{ background: #4285f4; border-color: #4285f4; }}
    .toggle-btn[data-status="Contacted"].active {{ background: #fbbc04; border-color: #fbbc04; color: #333; }}
    .toggle-btn[data-status="In Discussion"].active {{ background: #ff9800; border-color: #ff9800; color: #333; }}
    .toggle-btn[data-status="Active Relationship"].active {{ background: #34a853; border-color: #34a853; }}

    #view-mode-btn {{ padding: 4px 12px; border-radius: 6px; border: none; background: #e94560; color: #fff; font-size: 11px; cursor: pointer; font-weight: 600; white-space: nowrap; }}
    #view-mode-btn:hover {{ background: #c73652; }}

    #stats-bar {{ display: flex; gap: 12px; }}
    .stat {{ text-align: center; }}
    .stat .num {{ font-size: 16px; font-weight: 700; color: #fff; }}
    .stat .lbl {{ font-size: 9px; color: rgba(255,255,255,0.55); text-transform: uppercase; }}

    #rel-legend {{ display: none; gap: 6px; align-items: center; flex-wrap: wrap; font-size: 11px; color: #888; }}
    .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 3px; }}

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

    .stats-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 4px; margin-bottom: 12px; }}
    .stat-cell {{ background: #f5f6fa; border-radius: 4px; padding: 6px 4px; text-align: center; border: 1px solid #eee; }}
    .stat-cell .n {{ font-size: 16px; font-weight: 700; color: #e94560; }}
    .stat-cell .l {{ font-size: 9px; color: #999; text-transform: uppercase; }}

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

    .rev-item {{ background: #f5f6fa; border-radius: 5px; padding: 7px 9px; margin-bottom: 7px; font-size: 12px; border: 1px solid #eee; }}
    .rev-hdr {{ display: flex; justify-content: space-between; margin-bottom: 3px; }}
    .rev-author {{ font-weight: 600; color: #333; }}
    .rev-time {{ color: #999; font-size: 11px; }}
    .rev-text {{ color: #555; line-height: 1.4; }}

    .settled-case {{ padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 12px; }}
    .settled-case:last-child {{ border-bottom: none; }}
    .settled-case-label {{ font-weight: 600; color: #111; margin-bottom: 3px; }}
    .settled-case-meta {{ display: flex; flex-wrap: wrap; gap: 8px; font-size: 11px; color: #666; }}
    .section-hdr {{ font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #888; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }}
    .count-badge {{ background: #e94560; color: #fff; border-radius: 10px; padding: 1px 6px; font-size: 10px; font-weight: 700; }}

    .notes-log {{ max-height: 160px; overflow-y: auto; border: 1px solid #eee; border-radius: 6px; padding: 6px 8px; background: #fafafa; margin-top: 4px; }}
    .notes-log > div:last-child {{ border-bottom: none; }}
  </style>
</head>
<body>

<div id="header">
  <div class="brand">
    <h1>ATTORNEY CRM</h1>
    <div class="tagline">PI Outreach &amp; Relationships</div>
  </div>
</div>

<div id="controls">
  <div style="display:flex;gap:5px;flex-wrap:wrap">
    <button class="toggle-btn active" data-status="Not Contacted">Not Contacted</button>
    <button class="toggle-btn active" data-status="Contacted">Contacted</button>
    <button class="toggle-btn active" data-status="In Discussion">In Discussion</button>
    <button class="toggle-btn active" data-status="Active Relationship">Active</button>
  </div>
  <div id="rel-legend">
    <span><span class="legend-dot" style="background:#90A4AE"></span>0–2</span>
    <span><span class="legend-dot" style="background:#42A5F5"></span>3–5</span>
    <span><span class="legend-dot" style="background:#26A69A"></span>6–10</span>
    <span><span class="legend-dot" style="background:#FFA726"></span>11–20</span>
    <span><span class="legend-dot" style="background:#EF5350"></span>20+</span>
  </div>
  <div id="stats-bar">
    <div class="stat"><div class="num" id="att-stat-nc">0</div><div class="lbl">Not Contact.</div></div>
    <div class="stat"><div class="num" id="att-stat-c">0</div><div class="lbl">Contacted</div></div>
    <div class="stat"><div class="num" id="att-stat-id">0</div><div class="lbl">In Discussion</div></div>
    <div class="stat"><div class="num" id="att-stat-ar">0</div><div class="lbl">Active</div></div>
  </div>
  <div id="search-container">
    <input type="text" id="search" placeholder="Search attorneys..." autocomplete="off">
    <div id="search-dropdown"></div>
  </div>
  <button id="view-mode-btn" onclick="toggleViewMode()">Outreach View</button>
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
const ATTORNEYS = {att_json};
const ATT_ACTIVITIES = {att_act_json};
const CLOSED_CASES_BY_FIRM = {closed_cases_json};

const BASEROW_URL = "{BASEROW_URL}";
const API_TOKEN = "{BASEROW_API_TOKEN}";
const LAW_FIRMS_TABLE = {LAW_FIRMS_TABLE_ID};
const ATT_ACTS_TABLE = {ATT_ACTIVITIES_TABLE_ID};
const OFFICE_LAT = {office_lat};
const OFFICE_LNG = {office_lng};
const RADIUS_MILES = {RADIUS_MILES};
const MAP_ID = "{GOOGLE_MAPS_MAP_ID}";

let map, officeMarker, radiusCircle;
let attMarkers = {{}};
let viewMode = "outreach";
let activeStatuses = new Set(["Not Contacted", "Contacted", "In Discussion", "Active Relationship"]);
let attActCache = Object.assign({{}}, ATT_ACTIVITIES);
let selectedMarkerId = null;

const ATT_STATUS_COLORS = {{
  "Not Contacted": "#4285f4",
  "Contacted": "#fbbc04",
  "In Discussion": "#ff9800",
  "Active Relationship": "#34a853",
  "Office": "#ea4335",
}};
const REL_COLORS = ["#90A4AE","#42A5F5","#26A69A","#FFA726","#EF5350"];

function relColor(total) {{
  if (total <= 2) return REL_COLORS[0];
  if (total <= 5) return REL_COLORS[1];
  if (total <= 10) return REL_COLORS[2];
  if (total <= 20) return REL_COLORS[3];
  return REL_COLORS[4];
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

function markerIcon(color, scale=9, ringColor=null) {{
  const w = Math.round(scale * 2.4);
  const h = Math.round(w * 1.4);
  const ringSvg = ringColor ? `<circle cx="12" cy="12" r="13" stroke="${{ringColor}}" stroke-width="3" fill="none"/>` : "";
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${{w}}" height="${{h}}" viewBox="0 0 24 33">`
    + ringSvg
    + `<path d="M12 0C5.373 0 0 5.373 0 12c0 8.5 12 21 12 21S24 20.5 24 12C24 5.373 18.627 0 12 0z" fill="${{color}}" stroke="white" stroke-width="1.5"/>`
    + `<circle cx="12" cy="12" r="4" fill="white" fill-opacity="0.85"/>`
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
    + `<path d="M17 4L3 15.5V37h10V26h8v11h10V15.5L17 4z" fill="none" stroke="white" stroke-width="0.5" opacity="0.4"/>`
    + `</svg>`;
  return {{
    url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
    scaledSize: new google.maps.Size(w, h),
    anchor: new google.maps.Point(w / 2, h),
  }};
}}

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

  ATTORNEYS.forEach(att => {{
    const m = new google.maps.marker.AdvancedMarkerElement({{
      position: {{ lat: att.lat, lng: att.lng }},
      map, title: att.name,
      content: _iconEl(markerIcon(ATT_STATUS_COLORS[att.contactStatus] || "#4285f4", 9, computeRingColor(att.id, attActCache))),
    }});
    m.addListener("gmpClick", () => openAttSidebar(att.id));
    attMarkers[att.id] = m;
  }});

  updateAttStats();
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

function toggleViewMode() {{
  viewMode = viewMode === "outreach" ? "relationship" : "outreach";
  document.getElementById("view-mode-btn").textContent = viewMode === "outreach" ? "Outreach View" : "Relationship View";
  document.getElementById("rel-legend").style.display = viewMode === "relationship" ? "flex" : "none";
  updateAttVisibility();
}}

function updateAttVisibility() {{
  ATTORNEYS.forEach(att => {{
    const m = attMarkers[att.id];
    if (!m) return;
    m.map = activeStatuses.has(att.contactStatus) ? map : null;
    const ring = computeRingColor(att.id, attActCache);
    if (viewMode === "relationship") {{
      m.content = _iconEl(att.contactStatus === "Active Relationship"
        ? markerIcon(relColor(att.totalCases), 9, ring)
        : markerIcon("#555", 0.7, ring));
    }} else {{
      m.content = _iconEl(markerIcon(ATT_STATUS_COLORS[att.contactStatus] || "#4285f4", 9, ring));
    }}
  }});
  updateAttStats();
}}

function updateAttStats() {{
  document.getElementById("att-stat-nc").textContent = ATTORNEYS.filter(a => a.contactStatus === "Not Contacted").length;
  document.getElementById("att-stat-c").textContent = ATTORNEYS.filter(a => a.contactStatus === "Contacted").length;
  document.getElementById("att-stat-id").textContent = ATTORNEYS.filter(a => a.contactStatus === "In Discussion").length;
  document.getElementById("att-stat-ar").textContent = ATTORNEYS.filter(a => a.contactStatus === "Active Relationship").length;
}}

function setupLayerToggles() {{
  document.querySelectorAll(".toggle-btn[data-status]").forEach(btn => {{
    btn.addEventListener("click", () => {{
      const s = btn.dataset.status;
      if (activeStatuses.has(s)) {{ activeStatuses.delete(s); btn.classList.remove("active"); }}
      else {{ activeStatuses.add(s); btn.classList.add("active"); }}
      updateAttVisibility();
    }});
  }});
}}

function setupSearch() {{
  const input = document.getElementById("search");
  const dd = document.getElementById("search-dropdown");
  input.addEventListener("input", () => {{
    const q = input.value.trim().toLowerCase();
    if (!q) {{ dd.style.display = "none"; return; }}
    const matches = ATTORNEYS.filter(a =>
      a.name.toLowerCase().includes(q) || a.address.toLowerCase().includes(q)
    ).slice(0, 8);
    if (!matches.length) {{ dd.style.display = "none"; return; }}
    function hl(s) {{ return String(s).replace(new RegExp(q.replace(/[.*+?^${{}}()|[\]\\]/g,"\\$&"),"gi"), m => `<span class="search-highlight">${{m}}</span>`); }}
    dd.innerHTML = matches.map(a => `
      <div class="search-item" onclick="selectAttSearch(${{a.id}})">
        <div class="si-name">${{hl(a.name)}}</div>
        <div class="si-meta">${{hl(a.address)}} &middot; ${{a.distance}} mi</div>
      </div>`).join("");
    dd.style.display = "block";
  }});
  document.addEventListener("click", e => {{
    if (!document.getElementById("search-container").contains(e.target)) dd.style.display = "none";
  }});
}}

function selectAttSearch(id) {{
  const att = ATTORNEYS.find(a => a.id === id);
  if (!att) return;
  document.getElementById("search-dropdown").style.display = "none";
  document.getElementById("search").value = att.name;
  map.setCenter({{ lat: att.lat, lng: att.lng }});
  map.setZoom(15);
  openAttSidebar(id);
}}

function setSelectedMarker(id) {{
  if (selectedMarkerId !== null) {{
    const prev = attMarkers[selectedMarkerId];
    if (prev) {{
      const att = ATTORNEYS.find(a => a.id === selectedMarkerId);
      if (att) prev.content = _iconEl(markerIcon(ATT_STATUS_COLORS[att.contactStatus] || "#4285f4", 9, computeRingColor(att.id, attActCache)));
      // prev.setAnimation(null);  // AdvancedMarker has no setAnimation API; pin scale is the selection cue.
    }}
  }}
  selectedMarkerId = id;
  const m = attMarkers[id];
  if (m) {{
    const att = ATTORNEYS.find(a => a.id === id);
    if (att) m.content = _iconEl(markerIcon(ATT_STATUS_COLORS[att.contactStatus] || "#4285f4", 13, computeRingColor(id, attActCache)));
    // m.setAnimation(BOUNCE) — not supported on AdvancedMarker. Pin scale 13 instead.
  }}
}}

function clearSelectedMarker() {{
  if (selectedMarkerId === null) return;
  const m = attMarkers[selectedMarkerId];
  if (m) {{
    const att = ATTORNEYS.find(a => a.id === selectedMarkerId);
    if (att) m.content = _iconEl(markerIcon(ATT_STATUS_COLORS[att.contactStatus] || "#4285f4", 9, computeRingColor(att.id, attActCache)));
    // m.setAnimation(null);  // AdvancedMarker has no setAnimation API.
  }}
  selectedMarkerId = null;
}}

function getClosedCasesForFirm(firmName) {{
  const entry = CLOSED_CASES_BY_FIRM[firmName.trim().toLowerCase()];
  return entry ? entry.cases : [];
}}

function openAttSidebar(attId) {{
  setSelectedMarker(attId);
  const att = ATTORNEYS.find(a => a.id === attId);
  if (!att) return;

  document.getElementById("sidebar").classList.add("open");
  document.getElementById("sidebar-placeholder").style.display = "none";
  const c = document.getElementById("sidebar-content");
  c.className = "visible";

  const activities = attActCache[attId] || [];
  const cases = getClosedCasesForFirm(att.name);
  const last3 = cases.slice(0, 3);
  const casesHtml = last3.length
    ? last3.map(c2 => `<div class="settled-case"><div class="settled-case-label">${{esc(c2.label || 'Unnamed')}}</div><div class="settled-case-meta">${{c2.doi ? `<span>📅 DOI: ${{esc(c2.doi)}}</span>` : ""}}${{c2.visits ? `<span>📋 ${{esc(c2.visits)}} visits</span>` : ""}}</div></div>`).join("")
    : '<div class="no-acts">No settled cases on record</div>';

  c.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px;">
      <div class="ent-name" style="margin-bottom:0">${{esc(att.name)}}</div>
      <button onclick="clearSidebar()" title="Close" style="background:none;border:none;font-size:18px;line-height:1;cursor:pointer;color:#999;padding:0 2px;flex-shrink:0;">✕</button>
    </div>
    ${{att.classification ? `<span class="badge" style="background:#1565C0;color:#fff">${{esc(att.classification)}}</span>` : ""}}
    <hr class="divider">
    <div class="stats-grid">
      <div class="stat-cell"><div class="n">${{att.activeCases}}</div><div class="l">Active</div></div>
      <div class="stat-cell"><div class="n">${{att.billedCases}}</div><div class="l">Billed</div></div>
      <div class="stat-cell"><div class="n">${{att.awaitingBilling}}</div><div class="l">Awaiting</div></div>
      <div class="stat-cell"><div class="n">${{att.settledCases}}</div><div class="l">Settled</div></div>
      <div class="stat-cell"><div class="n">${{att.totalCases}}</div><div class="l">Total</div></div>
    </div>
    ${{att.address ? `<div class="section"><div class="slabel">Address</div><div class="sval">${{esc(att.address)}}</div></div>` : ""}}
    ${{att.phone ? `<div class="section"><div class="slabel">Phone</div><div class="sval"><a class="link" href="tel:${{att.phone}}">${{esc(att.phone)}}</a></div></div>` : ""}}
    ${{att.website ? `<div class="section"><div class="slabel">Website</div><div class="sval"><a class="link" href="${{esc(att.website)}}" target="_blank">${{esc(att.website)}}</a></div></div>` : ""}}
    ${{att.rating ? `<div class="section"><div class="slabel">Rating</div><div style="display:flex;align-items:center;gap:6px"><span class="stars">${{"★".repeat(Math.round(parseFloat(att.rating)||0))}}</span><span class="sval">${{att.rating}} (${{att.reviews}} reviews)</span></div></div>` : ""}}
    ${{att.distance ? `<div class="section"><div class="slabel">Distance</div><div class="sval">${{att.distance}} mi</div></div>` : ""}}
    ${{(att.googleMapsUrl||att.yelpSearchUrl) ? `<div style="display:flex;gap:10px;margin-bottom:12px">${{att.googleMapsUrl?`<a class="link" href="${{att.googleMapsUrl}}" target="_blank">Google Maps ↗</a>`:""}}${{att.yelpSearchUrl?`<a class="link" href="${{att.yelpSearchUrl}}" target="_blank">Yelp ↗</a>`:""}}</div>` : ""}}
    ${{att.googleReviews && att.googleReviews.length ? `<div class="section"><div class="slabel">Google Reviews</div>${{att.googleReviews.map(r=>`<div class="rev-item"><div class="rev-hdr"><span class="rev-author">${{esc(r.author_name||"")}}</span><span class="stars">${{"★".repeat(r.rating||0)}}</span></div><div class="rev-time">${{esc(r.relative_time_description||"")}}</div><div class="rev-text">${{esc((r.text||"").substring(0,160))}}${{(r.text||"").length>160?"…":""}}</div></div>`).join("")}}</div>` : ""}}
    <hr class="divider">
    <div class="section"><div class="slabel">Contact Status</div>
      <select class="status-select" onchange="updateAttStatus(${{attId}}, this.value)">
        <option ${{att.contactStatus==="Not Contacted"?"selected":""}}>Not Contacted</option>
        <option ${{att.contactStatus==="Contacted"?"selected":""}}>Contacted</option>
        <option ${{att.contactStatus==="In Discussion"?"selected":""}}>In Discussion</option>
        <option ${{att.contactStatus==="Active Relationship"?"selected":""}}>Active Relationship</option>
      </select>
    </div>
    <div class="section">
      <div class="slabel">Notes</div>
      <div class="notes-log" id="att-notes-log-${{attId}}">${{renderNotesLog(att.notes)}}</div>
      <div style="display:flex;gap:6px;margin-top:8px;">
        <input type="text" class="fi" id="att-notes-input-${{attId}}" placeholder="Add a note..." style="flex:1;">
        <button onclick="addNote(${{attId}})" style="background:#e94560;color:#fff;border:none;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:12px;font-weight:600;">Add</button>
      </div>
      <div class="save-st" id="att-note-st-${{attId}}"></div>
    </div>
    <hr class="divider">
    <div class="section"><div class="slabel">Activities (${{activities.length}})</div>
      <div id="att-act-log-${{attId}}">
        ${{activities.length ? activities.map(renderAct).join("") : '<div class="no-acts">No activities yet</div>'}}
      </div>
    </div>
    ${{renderLogForm(attId)}}
    <hr class="divider">
    <div class="section">
      <div class="section-hdr"><a href="https://baserow.reformchiropractic.app/database/199/table/772/3377" target="_blank" style="color:inherit;text-decoration:none;letter-spacing:inherit;" onmouseover="this.style.textDecoration='underline'" onmouseout="this.style.textDecoration='none'">Settled Cases</a> <span class="count-badge">${{cases.length || 0}}</span></div>
      <div>${{casesHtml}}</div>
    </div>
  `;
}}

async function updateAttStatus(id, val) {{
  const att = ATTORNEYS.find(a => a.id === id);
  if (!att) return;
  att.contactStatus = val;
  const m = attMarkers[id];
  if (m) m.content = _iconEl(markerIcon(ATT_STATUS_COLORS[val] || "#4285f4", 9, computeRingColor(id, attActCache)));
  updateAttStats();
  await bpatch(LAW_FIRMS_TABLE, id, {{"Contact Status": {{"value": val}}}});
}}

async function logAttActivity(id) {{
  const btn = document.getElementById(`att-log-btn-${{id}}`);
  const st = document.getElementById(`att-log-st-${{id}}`);
  btn.disabled = true;
  if (st) st.textContent = "Saving...";
  const date = document.getElementById(`att-act-date-${{id}}`).value;
  const type = document.getElementById(`att-act-type-${{id}}`).value;
  const outcome = document.getElementById(`att-act-outcome-${{id}}`).value;
  const person = document.getElementById(`att-act-person-${{id}}`).value;
  const summary = document.getElementById(`att-act-summary-${{id}}`).value;
  const followup = document.getElementById(`att-act-followup-${{id}}`).value;
  try {{
    const resp = await bpost(ATT_ACTS_TABLE, {{
      "Law Firm": [{{id}}],
      "Date": date || null,
      "Type": {{"value": type}},
      "Outcome": {{"value": outcome}},
      "Contact Person": person,
      "Summary": summary,
      "Follow-Up Date": followup || null,
    }});
    if (resp.ok) {{
      const newAct = {{ id: (await resp.json()).id, date, type, outcome, contactPerson: person, summary, followUpDate: followup }};
      if (!attActCache[id]) attActCache[id] = [];
      attActCache[id].unshift(newAct);
      const logEl = document.getElementById(`att-act-log-${{id}}`);
      if (logEl) logEl.innerHTML = attActCache[id].map(renderAct).join("");
      document.getElementById(`att-act-summary-${{id}}`).value = "";
      document.getElementById(`att-act-person-${{id}}`).value = "";
      document.getElementById(`att-act-followup-${{id}}`).value = "";
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
      <div class="fr"><label class="fl">Date</label><input type="date" class="fi" id="att-act-date-${{id}}" value="${{new Date().toISOString().split("T")[0]}}"></div>
      <div class="fr"><label class="fl">Type</label><select class="fi" id="att-act-type-${{id}}">
        <option>Call</option><option>Email</option><option>Drop-In</option><option>Meeting</option><option>Mail</option><option>Other</option>
      </select></div>
      <div class="fr"><label class="fl">Outcome</label><select class="fi" id="att-act-outcome-${{id}}">
        <option>No Answer</option><option>Left Message</option><option>Spoke With</option><option>Scheduled Meeting</option><option>Declined</option><option>Follow-Up Needed</option>
      </select></div>
      <div class="fr"><label class="fl">Contact Person</label><input type="text" class="fi" id="att-act-person-${{id}}" placeholder="Name"></div>
      <div class="fr"><label class="fl">Summary</label><textarea class="fta" id="att-act-summary-${{id}}" placeholder="What happened..."></textarea></div>
      <div class="fr"><label class="fl">Follow-Up Date (optional)</label><input type="date" class="fi" id="att-act-followup-${{id}}"></div>
      <button class="log-btn" id="att-log-btn-${{id}}" onclick="logAttActivity(${{id}})">Save Activity</button>
      <div class="form-st" id="att-log-st-${{id}}"></div>
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
  const inputEl = document.getElementById(`att-notes-input-${{id}}`);
  const st = document.getElementById(`att-note-st-${{id}}`);
  const text = (inputEl?.value || '').trim();
  if (!text) return;
  const today = new Date().toISOString().split('T')[0];
  const newEntry = `[${{today}}] ${{text}}`;
  const entity = ATTORNEYS.find(a => a.id === id);
  if (!entity) return;
  const existing = (entity.notes || '').trim();
  entity.notes = existing ? newEntry + '\\n---\\n' + existing : newEntry;
  inputEl.value = '';
  const logEl = document.getElementById(`att-notes-log-${{id}}`);
  if (logEl) logEl.innerHTML = renderNotesLog(entity.notes);
  if (st) st.textContent = 'Saving...';
  try {{
    await bpatch(LAW_FIRMS_TABLE, id, {{'Notes': entity.notes}});
    if (st) {{ st.textContent = 'Saved ✓'; setTimeout(() => {{ if(st) st.textContent=''; }}, 2000); }}
  }} catch(e) {{ if (st) st.textContent = 'Save failed'; }}
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
  src="https://maps.googleapis.com/maps/api/js?key={GOOGLE_MAPS_API_KEY}&v=weekly&libraries=marker&callback=initMap">
</script>
</body>
</html>"""


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("ATTORNEY CRM — MAP GENERATOR")
    print("=" * 60)

    print("\n── Attorney Data ──")
    attorneys = load_attorneys()
    att_activities = load_attorney_activities()

    if not attorneys:
        print("\nERROR: No attorney data found in Baserow. Run sync scripts first.")
        return

    print("  Loading closed cases for attorney sidebar...")
    closed_cases_raw = read_all_rows(CLOSED_CASES_TABLE_ID)
    closed_cases_by_firm = build_closed_cases_by_firm(closed_cases_raw)
    total_cases = sum(len(v["cases"]) for v in closed_cases_by_firm.values())
    print(f"  {total_cases} closed cases across {len(closed_cases_by_firm)} firms")

    for att in attorneys:
        key = att["name"].strip().lower()
        settled = len(closed_cases_by_firm.get(key, {}).get("cases", []))
        att["settledCases"] = settled
        att["totalCases"] = att.get("activeCases", 0) + att.get("billedCases", 0) + att.get("awaitingBilling", 0) + settled

    print(f"\nGenerating Attorney CRM map...")
    print(f"  {len(attorneys)} attorneys")

    html = generate_html(attorneys, att_activities, closed_cases_by_firm)

    os.makedirs(".tmp", exist_ok=True)
    output_path = ".tmp/attorney_map.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nSaved: {output_path}")
    print("Open in browser.")


if __name__ == "__main__":
    main()
