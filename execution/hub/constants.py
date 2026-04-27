"""
Shared constants for the Reform Operations Hub.
Pure data — no imports, no side effects.
"""

# ─── Table IDs ─────────────────────────────────────────────────────────────────
T_ATT_VENUES = 768
T_ATT_ACTS   = 784
T_GOR_VENUES = 790
T_GOR_ACTS   = 791
T_GOR_BOXES  = 800
T_COM_VENUES = 797
T_COM_ACTS   = 798
T_GOR_ROUTES      = 801
T_GOR_ROUTE_STOPS = 802

# ─── PI Cases Table IDs ────────────────────────────────────────────────────────
T_PI_ACTIVE   = 775
T_PI_BILLED   = 773
T_PI_AWAITING = 776
T_PI_CLOSED   = 772
T_PI_FINANCE  = 781

# ─── Operations Table IDs ─────────────────────────────────────────────────────
T_STAFF  = 815
T_EVENTS = 816
T_LEADS  = 817

# ─── Tickets (Helpdesk) — 'Operations Hub' database (206) ─────────────────────
T_TICKETS         = 818
T_TICKET_COMMENTS = 819

# ─── CRM (Companies + Contacts + Activities) — 'Reform Chiropractic CRM' (197) ─
# Superset tables created 2026-04-21 by setup_crm_tables.py + populated by
# migrate_venues_to_companies.py. Phase 2b swaps hubs to read/write these
# instead of the legacy T_ATT_VENUES / T_GOR_VENUES / T_COM_VENUES tables.
# T_ACTIVITIES unifies the three legacy activity tables (T_*_ACTS) — link_row
# to Company (+ optional Contact for the person on the other end).
T_COMPANIES            = 820
T_CONTACTS             = 821
T_ACTIVITIES           = 822
T_SMS_MESSAGES         = 823
T_SEQUENCES            = 824
T_SEQUENCE_ENROLLMENTS = 825
T_SOCIAL_NOTIFICATIONS = 826
T_PUSH_SUBSCRIPTIONS   = 827  # Phase 3 push notifications (rep, endpoint, keys)


# ─── Leads follow-up pipeline ─────────────────────────────────────────────────
# Extends the existing T_LEADS (817, in Gorilla Marketing DB 203). Populated
# initially by the public lead-capture forms (hub/events.py); the hub now
# surfaces those rows as a full follow-up pipeline via hub/leads.py.
LEAD_STAGES = ["New", "Contacted", "Appointment Scheduled",
               "Seen", "Converted", "Dropped"]
OPEN_LEAD_STAGES   = {"New", "Contacted", "Appointment Scheduled", "Seen"}
CLOSED_LEAD_STAGES = {"Converted", "Dropped"}


# ── Email outreach templates (plain string — no f-string so braces don't need doubling) ──
# NOTE: _TEMPLATES is already declared as `var` in compose.py (_COMPOSE_JS).
# Use Object.assign to merge directory templates into the existing object
# instead of redeclaring with `const` (which causes SyntaxError in same scope).
_TEMPLATES_JS = r"""
Object.assign(_TEMPLATES, {
  attorney: [
    {
      name: 'Introduction',
      subject: 'Reform Chiropractic \u2014 PI Services & LOP Partnership',
      body: `Hi {name},\n\nMy name is [Your Name], and I\u2019m with Reform Chiropractic in [City]. We specialize in personal injury care \u2014 treating soft-tissue injuries, documenting clinical findings for litigation, and working entirely on a letter of protection so your clients never pay out of pocket.\n\nWe\u2019d welcome any referrals from your firm and offer same-week appointments and detailed progress reports tailored for your legal team.\n\nWould you have 10 minutes this week for a quick call? Happy to come by your office as well.\n\nBest regards,\n[Your Name]\nReform Chiropractic\n[Phone]`
    },
    {
      name: 'Follow-Up',
      subject: 'Following Up \u2014 Reform Chiropractic PI Partnership',
      body: `Hi {name},\n\nI wanted to follow up on my earlier outreach. Here\u2019s what we offer your PI clients:\n\n\u2022 Same-week appointments\n\u2022 LOP accepted \u2014 zero out-of-pocket cost during the case\n\u2022 Detailed medical narratives and deposition-ready documentation\n\u2022 Direct communication with your legal team throughout treatment\n\nIs there a time in the next week or two for a brief call or drop-in?\n\nBest,\n[Your Name]\nReform Chiropractic`
    },
    {
      name: 'Reconnect',
      subject: 'Checking In \u2014 Reform Chiropractic',
      body: `Hi {name},\n\nI hope things are going well at your firm. I wanted to reconnect \u2014 it\u2019s been a while since we last spoke.\n\nWe\u2019re actively looking to deepen partnerships with PI attorneys who prioritize thorough, well-documented care. If you have any active or incoming cases involving soft-tissue injuries, we\u2019d be glad to get those clients in quickly and keep you closely updated.\n\nWarm regards,\n[Your Name]\nReform Chiropractic\n[Phone]`
    }
  ],
  gorilla: [
    {
      name: 'Introduction',
      subject: 'Local Partnership Opportunity \u2014 Reform Chiropractic',
      body: `Hi {name},\n\nMy name is [Your Name] from Reform Chiropractic in [City]. We\u2019re a local clinic focused on injury recovery and wellness, and we\u2019re reaching out to connect with great local businesses about mutual referral opportunities.\n\nWe\u2019d love to explore ways to support each other\u2019s customers \u2014 co-promoting, sharing referrals, or simply getting to know your team.\n\nWould you be open to a quick coffee or call to see if there\u2019s a fit?\n\nThanks,\n[Your Name]\nReform Chiropractic\n[Phone]`
    },
    {
      name: 'Drop Box Placement',
      subject: 'Referral Drop Box \u2014 Reform Chiropractic Partnership',
      body: `Hi {name},\n\nI wanted to follow up with a simple, no-obligation idea: we\u2019d love to place a small referral information box at your location.\n\nIt\u2019s a compact display with our cards \u2014 useful for any customers dealing with pain, injuries, or accident recovery. We handle all restocking at no cost or commitment on your end.\n\nIn return, we\u2019re glad to refer our patients to local businesses we trust, including yours.\n\nWould you be open to us stopping by to set it up?\n\nBest,\n[Your Name]\nReform Chiropractic\n[Phone]`
    },
    {
      name: 'Follow-Up',
      subject: 'Following Up \u2014 Reform Chiropractic Partnership',
      body: `Hi {name},\n\nI wanted to follow up on the conversation we started about a local referral partnership.\n\nWe\u2019ve had great success partnering with businesses in [Area] \u2014 it\u2019s a low-effort way to add value for your customers while creating a new referral channel for both of us.\n\nIf the timing isn\u2019t right, no problem \u2014 we\u2019d love to support what you\u2019re building whenever it makes sense.\n\nThanks again,\n[Your Name]\nReform Chiropractic`
    }
  ],
  community: [
    {
      name: 'Introduction',
      subject: 'Community Health Partnership \u2014 Reform Chiropractic',
      body: `Hi {name},\n\nMy name is [Your Name] with Reform Chiropractic in [City]. We\u2019re passionate about serving our local community and would love to explore a partnership with your organization.\n\nWe\u2019d be glad to offer free health screenings at your events, sponsor community gatherings, or present short educational talks on injury prevention \u2014 with no strings attached.\n\nWould you be open to a quick call to brainstorm ideas?\n\nWith gratitude,\n[Your Name]\nReform Chiropractic\n[Phone]`
    },
    {
      name: 'Event Collaboration',
      subject: 'Supporting Your Upcoming Event \u2014 Reform Chiropractic',
      body: `Hi {name},\n\nI wanted to reach out about how Reform Chiropractic might support your upcoming events.\n\nWe\u2019d be glad to:\n\u2022 Set up a free injury and posture screening booth\n\u2022 Provide educational materials on pain management\n\u2022 Sponsor a portion of the event in exchange for a brief table presence\n\u2022 Offer a special gift card or discount for your participants\n\nWould you have a few minutes to talk through the possibilities?\n\nBest,\n[Your Name]\nReform Chiropractic\n[Phone]`
    },
    {
      name: 'Follow-Up',
      subject: 'Following Up \u2014 Reform Chiropractic Community Partnership',
      body: `Hi {name},\n\nI just wanted to follow up on my previous message about a potential partnership.\n\nWe\u2019re committed to finding ways to give back \u2014 whether through health education, event support, or simply being a reliable local resource for the people you serve. If you\u2019ve had a chance to think it over and have any questions, I\u2019m happy to chat at your convenience.\n\nThank you for all that you do for our community.\n\nWarmly,\n[Your Name]\nReform Chiropractic\n[Phone]`
    }
  ]
});
"""
