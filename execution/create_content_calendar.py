"""
Create the Social Media Content Calendar Google Sheet.

3-month forward calendar (13 weeks, 6 posts/week Mon-Sat) with specific
pre-assigned topics drawn from BookStack: Video Categories and Ideas.

Weekly pattern:
    Mon 12:00  Wellness Tip             (Staff)
    Tue 10:00  Anatomy & Body Knowledge (Doctor)
    Wed 12:00  Doctor Q&A              (Doctor)
    Thu 17:00  Staff variety rotation   (Staff)
    Fri 12:00  Injury Care & Recovery   (Doctor)
    Sat 11:00  Musculoskeletal Cond.    (Doctor)

Usage:
    cd "c:\\Users\\crazy\\Reform Workspace"
    python execution/create_content_calendar.py
"""

import json
import sys
from datetime import date, timedelta
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

# Use existing schedule sheet (service account already has access)
# Adding a new "Content Calendar" tab rather than creating a new file
SHEET_ID = "1d1V8wurYb9uPU86r8pBKFLshUaCS-YqumBrK5hBkXq0"


# ─── TOPIC BANKS ──────────────────────────────────────────────────────────────
# All topics sourced directly from BookStack: Video Categories and Ideas

WELLNESS_TIPS = [
    "Drink water right when you wake up",
    "Set a 1-hour movement timer at work",
    "Sleep with a small pillow between your knees",
    "Stretch before AND after workouts",
    "Switch to anti-inflammatory spices",
    "Change your desk chair height to match your elbows",
    "Avoid carrying your bag on one shoulder",
    "Do a 2-min posture check every lunch break",
    "Sleep on your side, not your stomach",
    "Stretch your calves daily if you wear heels",
    "Start the day with 5 deep breaths",
    "Don't ignore mild pain – it's a warning signal",
    "Add omega-3 foods to reduce joint pain",
    "Move every 30 minutes – even just standing up",
    "Hold your phone at eye level",
    "Foam roll after workouts to aid recovery",
]

ANATOMY = [
    "How the spine connects to the nervous system",
    "What causes 'cracking' sounds in adjustments?",
    "Why posture matters for your health",
    "Spinal anatomy explained in 60 sec",
    "The role of discs in your back",
    "How stress affects your spine",
    "Why sitting is called 'the new smoking'",
    "What is sciatica? Explained simply",
    "How posture impacts breathing",
    "Nervous system 101",
    "The difference between acute vs. chronic pain",
    "Why hydration supports joint health",
    "Top 5 causes of back pain",
    "Benefits of regular maintenance care",
    "How chiropractic supports digestion",
    "What is a subluxation?",
    "Why stretching alone may not be enough",
]

DOCTOR_QA = [
    "Is it normal to feel sore after a chiropractic adjustment?",
    "How often should I get adjusted if I work at a desk?",
    "Do chiropractors only crack backs?",
    "Can chiropractic help with headaches?",
    "Do kids benefit from chiropractic care?",
    "Is it safe to get adjusted during pregnancy?",
    "Why does my back crack when I stretch?",
    "Can I go to the gym after an adjustment?",
    "How do I know if my posture is bad?",
    "Do adjustments hurt?",
    "Do I need a referral to see a chiropractor?",
    "Can chiropractic help with sciatica?",
    "Should I see a chiropractor for neck stiffness?",
    "What's the difference between a chiropractor and a physical therapist?",
    "Is it okay to crack my own neck?",
    "How soon should I bring my child in for a check-up?",
    "Do chiropractors help with sleep problems?",
    "Can chiropractic care improve posture?",
    "Should I come in if I'm not in pain?",
    "Do I need an X-ray before care?",
    "What's the #1 posture mistake people make?",
    "Why does my back crack when I move?",
    "Expectation: Chiropractor just cracks backs",
    "Expectation: One adjustment fixes everything",
    "Expectation: Adjustments are painful",
    "Expectation: Chiropractors only treat athletes",
    "Expectation: Chiropractors only help with pain",
    "Expectation: You can't exercise after adjustments",
    "Expectation: You must get adjusted forever",
    "Expectation: Chiropractors don't use science",
    "Expectation: Cracks = bones breaking",
    "Expectation: Good posture means sitting stiff",
    "Expectation: Kids don't need adjustments",
    "Expectation: Chiropractors only help spines",
    "Expectation: Pregnant women can't get adjusted",
    "Expectation: You can 'fix' posture overnight",
    "Expectation: Pain is the only reason to see us",
]

INJURY_CARE = [
    "Best way to ice vs. heat an injury",
    "Simple ankle rehab exercise",
    "How to tape a sprained wrist (educational demo)",
    "Shoulder rehab band exercise",
    "3 mistakes after an injury",
    "How to rest without losing mobility",
    "Lower back pain do's and don'ts",
    "Best pillow for neck pain recovery",
    "60-second sciatica relief exercise",
    "Tips for healing after whiplash",
    "Gentle exercise for knee pain",
    "What NOT to do after pulling a muscle",
    "Recovery tips after sports injury",
    "Breathing exercise to aid healing",
    "Walking tips for back pain recovery",
    "Foot strengthening after plantar fasciitis",
    "Rotator cuff rehab moves",
    "Core stability exercise post-injury",
    "How long should I rest after an injury?",
    "Lower back brace: when and when not to use",
    "Best foods to eat during injury recovery",
]

MUSCULOSKELETAL = [
    "What actually causes a herniated disc?",
    "What is spinal stenosis and why does it affect walking?",
    "What is osteoarthritis and why does it affect joints over time?",
    "Why does tendonitis develop from repetitive movement?",
    "What is carpal tunnel syndrome?",
    "What causes sciatica to flare up?",
    "What causes trigger finger?",
    "What causes chronic back pain over time?",
    "What happens to your spine as you age?",
    "What causes muscle strains?",
    "What is fibromyalgia and why does it affect the whole body?",
    "What causes joint inflammation?",
    "Why do people lose range of motion in their joints?",
    "What causes a bulging disc in the spine?",
    "What is degenerative disc disease?",
    "What causes muscle knots in the back or neck?",
    "What is bursitis and why does it affect joints?",
    "Why does plantar fasciitis cause heel pain?",
    "What causes rotator cuff injuries in the shoulder?",
    "What is a pinched nerve in the neck?",
    "What causes hip bursitis?",
    "Why do some people develop shin splints?",
    "What is a labral tear in the hip or shoulder?",
    "Why do some people experience chronic neck stiffness?",
    "What causes patellar tendonitis in the knee?",
    "Why does the lower back tighten after long periods of sitting?",
    "What is sacroiliac joint dysfunction?",
    "What causes tight hip flexors?",
    "What is thoracic outlet syndrome?",
    "What causes piriformis syndrome?",
    "What is spondylolisthesis?",
    "What causes frozen shoulder?",
    "What is a stress fracture?",
    "What causes Achilles tendonitis?",
    "What is cervical radiculopathy?",
    "What causes a meniscus tear in the knee?",
    "What is costochondritis and why does it cause chest pain?",
    "What causes iliotibial band syndrome?",
    "What is kyphosis?",
    "What causes muscle imbalances?",
    "What is cubital tunnel syndrome?",
    "What causes facet joint irritation in the spine?",
    "What is Scheuermann's disease?",
    "What is a slipped disc vs. a herniated disc?",
    "What is spondylosis in the spine?",
    "What causes facet joint syndrome?",
    "What is spondylolysis?",
    "What is spinal nerve compression?",
    "What causes muscle spasms in the lower back?",
    "What is a compression fracture in the spine?",
    "What is lordosis in the lower back?",
    "What causes spinal instability?",
    "Why does the pain between my shoulder blades happen?",
    "Why does my neck hurt at the base of my skull?",
    "Why do I feel pain on only one side of my lower back?",
    "Why does the middle of my back feel stiff when I twist?",
    "Why does my lower back hurt right above the hips?",
    "Why does my neck hurt when I turn my head?",
    "Why do I feel pain near my shoulder blade when I move my neck?",
    "Why does my upper back feel tight after sitting all day?",
    "Why does my lower back hurt when I bend forward?",
    "Why does my back feel tight when I stand up after sitting?",
    "Why does the area around my tailbone hurt when I sit?",
    "Why does my upper back feel like it needs to crack?",
    "Why does my neck feel tight when I look down at my phone?",
    "Why does my lower back hurt more when I arch backward?",
    "Why does the center of my lower back feel sore after lifting?",
]

# Thursday rotation — Staff variety + filler placeholders for empty chapters
# (category, topic, films)
THURSDAY_ROTATION = [
    ("Skits",               "POV: Our front desk welcomes you in",                    "Staff"),
    ("Staff Q&A",           "Do you take walk-ins?",                                  "Staff"),
    ("Informative",         "'What To Expect' – highlight one step per video",        "Staff"),
    ("Time-Lapse",          "TBD – Time-lapse of clinic setup or patient flow",       "Staff"),
    ("Skits",               "Staff thumbs up montage",                                "Staff"),
    ("Staff Q&A",           "How do I book an appointment?",                          "Staff"),
    ("Testimonial",         "TBD – Patient testimonial (filmed with consent)",        "Staff"),
    ("Skits",               "POV: Your first visit – what you'll see",                "Staff"),
    ("Staff Q&A",           "Do you accept insurance?",                               "Staff"),
    ("Massage POV",         "TBD – Massage room POV from client perspective",         "Staff"),
    ("Informative",         "'Yes, We Do!' – insurance, kids, walk-ins",              "Staff"),
    ("Manuthera Showcase",  "TBD – Manuthera table in action",                        "Staff + Doctor"),
    ("Staff Q&A",           "What's your busiest day?",                               "Staff"),
]


# ─── CALENDAR GENERATION ──────────────────────────────────────────────────────

start_date = date(2026, 3, 30)  # Monday
num_weeks = 13                   # ~3 months

# Cycling indices per category
idx = dict(wellness=0, anatomy=0, doctor_qa=0, injury=0, musculo=0, thursday=0)

def pick(key, lst):
    topic = lst[idx[key] % len(lst)]
    idx[key] += 1
    return topic

# Column header
header = ["Week", "Date", "Day", "Time (PT)", "Category", "Specific Topic", "Films", "Status", "Notes"]
rows = [header]

# Day config: (day_name, time, category, films, list_key)  — Thursday handled separately
DAY_CONFIG = [
    ("Monday",    "12:00", "Wellness Tip",              "Staff",  "wellness",  WELLNESS_TIPS),
    ("Tuesday",   "10:00", "Anatomy & Body Knowledge",  "Doctor", "anatomy",   ANATOMY),
    ("Wednesday", "12:00", "Doctor Q&A",                "Doctor", "doctor_qa", DOCTOR_QA),
    None,  # Thursday — rotation
    ("Friday",    "12:00", "Injury Care & Recovery",    "Doctor", "injury",    INJURY_CARE),
    ("Saturday",  "11:00", "Musculoskeletal Conditions","Doctor", "musculo",   MUSCULOSKELETAL),
]

for week in range(num_weeks):
    for day_offset in range(6):  # 0=Mon ... 5=Sat
        post_date = start_date + timedelta(weeks=week, days=day_offset)
        date_str = post_date.strftime("%b %d, %Y").replace(" 0", " ")  # "Mar 30, 2026"

        if day_offset == 3:  # Thursday
            cat, topic, films = THURSDAY_ROTATION[idx["thursday"] % len(THURSDAY_ROTATION)]
            idx["thursday"] += 1
            rows.append([f"Week {week + 1}", date_str, "Thursday", "17:00", cat, topic, films, "", ""])
        else:
            day_name, time, category, films, key, lst = DAY_CONFIG[day_offset]
            topic = pick(key, lst)
            rows.append([f"Week {week + 1}", date_str, day_name, time, category, topic, films, "", ""])


# ─── ADD NEW TAB TO EXISTING SHEET ───────────────────────────────────────────

sheet_id = SHEET_ID
TAB_TITLE = "Content Calendar"

# Delete existing tab if it's there (clean re-run)
existing = sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
tab_id = None
delete_requests = []
for s in existing["sheets"]:
    if s["properties"]["title"] == TAB_TITLE:
        delete_requests.append({"deleteSheet": {"sheetId": s["properties"]["sheetId"]}})

if delete_requests:
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": delete_requests},
    ).execute()
    print(f"[OK] Removed old '{TAB_TITLE}' tab")

# Add fresh tab
add_result = sheets_service.spreadsheets().batchUpdate(
    spreadsheetId=sheet_id,
    body={"requests": [{
        "addSheet": {
            "properties": {
                "title": TAB_TITLE,
                "gridProperties": {"frozenRowCount": 1},
            }
        }
    }]},
).execute()
tab_id = add_result["replies"][0]["addSheet"]["properties"]["sheetId"]
print(f"[OK] '{TAB_TITLE}' tab created (tab id: {tab_id})")
print(f"     URL: https://docs.google.com/spreadsheets/d/{sheet_id}")

# Write all rows
sheets_service.spreadsheets().values().update(
    spreadsheetId=sheet_id,
    range=f"{TAB_TITLE}!A1",
    valueInputOption="RAW",
    body={"values": rows},
).execute()
print(f"[OK] {len(rows) - 1} rows written")


# ─── FORMATTING ───────────────────────────────────────────────────────────────

def rgb(r, g, b):
    return {"red": r / 255, "green": g / 255, "blue": b / 255}

CATEGORY_COLORS = {
    "Wellness Tip":               rgb(198, 239, 206),  # soft green
    "Anatomy & Body Knowledge":   rgb(255, 235, 156),  # soft yellow
    "Doctor Q&A":                 rgb(189, 215, 238),  # soft blue
    "Injury Care & Recovery":     rgb(255, 199, 206),  # soft red/pink
    "Musculoskeletal Conditions": rgb(226, 209, 255),  # soft purple
    "Skits":                      rgb(255, 230, 199),  # soft orange
    "Staff Q&A":                  rgb(204, 230, 255),  # pale blue
    "Informative":                rgb(225, 225, 225),  # light grey
    "Time-Lapse":                 rgb(255, 242, 204),  # pale gold
    "Testimonial":                rgb(208, 240, 221),  # pale mint
    "Massage POV":                rgb(255, 220, 240),  # pale rose
    "Manuthera Showcase":         rgb(200, 220, 255),  # pale periwinkle
    "Doctor POV":                 rgb(255, 245, 200),  # pale cream
}

format_requests = [
    # Header: dark background, white bold text, centered
    {
        "repeatCell": {
            "range": {"sheetId": tab_id, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {"bold": True, "foregroundColor": rgb(255, 255, 255)},
                    "backgroundColor": rgb(50, 50, 50),
                    "horizontalAlignment": "CENTER",
                }
            },
            "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)",
        }
    },
    # Auto-resize all 9 columns
    {
        "autoResizeDimensions": {
            "dimensions": {
                "sheetId": tab_id,
                "dimension": "COLUMNS",
                "startIndex": 0,
                "endIndex": 9,
            }
        }
    },
    # Set Topic column (F = index 5) to a fixed wider width
    {
        "updateDimensionProperties": {
            "range": {
                "sheetId": tab_id,
                "dimension": "COLUMNS",
                "startIndex": 5,
                "endIndex": 6,
            },
            "properties": {"pixelSize": 420},
            "fields": "pixelSize",
        }
    },
    # Set Notes column (I = index 8) to fixed width
    {
        "updateDimensionProperties": {
            "range": {
                "sheetId": tab_id,
                "dimension": "COLUMNS",
                "startIndex": 8,
                "endIndex": 9,
            },
            "properties": {"pixelSize": 200},
            "fields": "pixelSize",
        }
    },
]

# Color each data row by category
for i, row in enumerate(rows[1:], start=1):
    cat = row[4]  # Category column
    color = CATEGORY_COLORS.get(cat, rgb(255, 255, 255))
    format_requests.append({
        "repeatCell": {
            "range": {
                "sheetId": tab_id,
                "startRowIndex": i,
                "endRowIndex": i + 1,
                "startColumnIndex": 0,
                "endColumnIndex": 9,
            },
            "cell": {"userEnteredFormat": {"backgroundColor": color}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

# Add dropdown validation for Status column (H = index 7)
format_requests.append({
    "setDataValidation": {
        "range": {
            "sheetId": tab_id,
            "startRowIndex": 1,
            "endRowIndex": len(rows),
            "startColumnIndex": 7,
            "endColumnIndex": 8,
        },
        "rule": {
            "condition": {
                "type": "ONE_OF_LIST",
                "values": [
                    {"userEnteredValue": "Not Started"},
                    {"userEnteredValue": "In Production"},
                    {"userEnteredValue": "Filmed"},
                    {"userEnteredValue": "Edited"},
                    {"userEnteredValue": "Approved"},
                    {"userEnteredValue": "Scheduled"},
                    {"userEnteredValue": "Posted"},
                    {"userEnteredValue": "Skipped"},
                ],
            },
            "showCustomUi": True,
            "strict": False,
        },
    }
})

sheets_service.spreadsheets().batchUpdate(
    spreadsheetId=sheet_id,
    body={"requests": format_requests},
).execute()
print("[OK] Formatting applied (category colors, status dropdown, column widths)")


# ─── SUMMARY ──────────────────────────────────────────────────────────────────

print()
print("=" * 70)
print("CONTENT CALENDAR READY")
print(f"  https://docs.google.com/spreadsheets/d/{sheet_id}")
print()
print(f"  {len(rows) - 1} posts  |  13 weeks  |  Mar 30 – Jun 27, 2026")
print()
print("  Weekly pattern (6 posts/week):")
print("    Mon 12:00  Wellness Tip              Staff")
print("    Tue 10:00  Anatomy & Body Knowledge  Doctor")
print("    Wed 12:00  Doctor Q&A               Doctor")
print("    Thu 17:00  Variety / Filler          Staff")
print("    Fri 12:00  Injury Care & Recovery    Doctor")
print("    Sat 11:00  Musculoskeletal Cond.     Doctor")
print()
print("  Status dropdown: Not Started → In Production → Filmed →")
print("                   Edited → Approved → Scheduled → Posted")
print("=" * 70)
