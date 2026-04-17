#!/usr/bin/env python3
"""Patch 2c+2d: Expand outreach group children and add theme toggle."""
import pathlib

f = pathlib.Path("execution/modal_outreach_hub.py")
src = f.read_text(encoding="utf-8")

# 2c: Expand outreach group children
OLD = (
    "        + grp('outreach', '📡', 'Outreach', (\n"
    "            li('attorney',  '⚖', 'PI Attorney',    '/attorney') +\n"
    "            li('gorilla',   '◉', 'Gorilla Mktg',   '/gorilla') +\n"
    "            li('community', '♦', 'Community',       '/community')\n"
    "        ))"
)
NEW = (
    "        + grp('outreach', '📡', 'Outreach', (\n"
    "            li('attorney',     '⚖', 'PI Attorney',    '/attorney') +\n"
    "            li('attorney_map', '·', 'Map Directory',  '/attorney/map') +\n"
    "            li('gorilla',      '◉', 'Gorilla Mktg',   '/gorilla') +\n"
    "            li('gorilla_map',  '·', 'Map Directory',  '/gorilla/map') +\n"
    "            li('community',    '♦', 'Community',       '/community') +\n"
    "            li('community_map','·', 'Map Directory',  '/community/map')\n"
    "        ))"
)
count = src.count(OLD)
assert count == 1, f"outreach group not found uniquely (found {count})"
src = src.replace(OLD, NEW, 1)

# 2d: Add theme toggle button to sidebar-bottom
OLD2 = (
    "        + '<div class=\"sidebar-bottom\">'\n"
    "        '<a href=\"/logout\">\u21a9&nbsp; Logout</a>'\n"
    "        '</div>'"
)
NEW2 = (
    "        + '<div class=\"sidebar-bottom\">'\n"
    "        '<button class=\"theme-toggle\" id=\"theme-btn\" onclick=\"toggleTheme()\">'\n"
    "        '<span id=\"theme-icon\">\U0001f319</span>&nbsp; Toggle Theme'\n"
    "        '</button>'\n"
    "        '<a href=\"/logout\">\u21a9&nbsp; Logout</a>'\n"
    "        '</div>'"
)
count2 = src.count(OLD2)
assert count2 == 1, f"sidebar-bottom not found uniquely (found {count2})"
src = src.replace(OLD2, NEW2, 1)

f.write_text(src, encoding="utf-8")
print("Batch 2c+2d done.")
