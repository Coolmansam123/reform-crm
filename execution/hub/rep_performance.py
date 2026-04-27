"""
Admin performance dashboard — Phase 2.4.

Aggregates per-rep activity over a configurable lookback window (7d / 30d / 90d):
  - Stops completed   (T_GOR_ROUTE_STOPS, Status=Visited, Completed By=email)
  - Leads captured    (T_LEADS,           Owner=email)
  - Conversions       (T_LEADS,           Owner=email, Status=Converted)
  - Activities logged (T_ACTIVITIES,      Author=email, Kind=user_activity)

Each metric is reported with a delta vs. the equivalent prior window so admins
see week-over-week trend without exporting CSVs. Sortable leaderboard table on
`/reps/performance`; data via `/api/admin/rep-performance?range=7d|30d|90d`.

Backend-agnostic — no modal.* / os.environ reads. Wrappers in
modal_outreach_hub.py register routes and pass env + cached_rows in.
"""
import os
from collections import defaultdict
from datetime import date as _date, datetime as _dt, timedelta as _td

from fastapi.responses import JSONResponse

from .access import _is_admin
from .constants import (
    T_ACTIVITIES, T_GOR_ROUTE_STOPS, T_LEADS, T_STAFF,
)


def _sv(v):
    if isinstance(v, dict): return (v.get("value") or v.get("name") or "")
    if isinstance(v, list) and v:
        x = v[0]
        if isinstance(x, dict): return (x.get("value") or x.get("name") or "")
        return str(x)
    return v or ""


def _parse_iso_date(s: str):
    """Accept ISO 'YYYY-MM-DD' OR 'YYYY-MM-DD HH:MM' OR ISO datetime; return date or None."""
    if not s:
        return None
    s = str(s)[:10]
    try:
        y, m, d = s.split("-")
        return _date(int(y), int(m), int(d))
    except Exception:
        return None


def _windows(range_key: str) -> tuple[_date, _date, _date, _date]:
    """Return (current_start, current_end, prev_start, prev_end) for a range key.
    Both windows are [start, end] inclusive on `end` (today)."""
    days = {"7d": 7, "30d": 30, "90d": 90}.get(range_key, 7)
    today = _date.today()
    cur_start  = today - _td(days=days - 1)
    prev_end   = cur_start - _td(days=1)
    prev_start = prev_end - _td(days=days - 1)
    return cur_start, today, prev_start, prev_end


def _in_window(d: _date, start: _date, end: _date) -> bool:
    return d is not None and start <= d <= end


def _delta_pct(curr: int, prev: int) -> int:
    """Round percent delta. 0 if both 0; +100% if prev=0 and curr>0."""
    if prev == 0:
        return 100 if curr > 0 else 0
    return int(round((curr - prev) / prev * 100))


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/admin/rep-performance?range=7d|30d|90d
# Returns {range, current: {start,end}, previous: {...}, reps: [...]}
# ─────────────────────────────────────────────────────────────────────────────
async def get_rep_performance(request, br: str, bt: str, user: dict,
                              cached_rows) -> JSONResponse:
    if not _is_admin(user):
        return JSONResponse({"error": "admin only"}, status_code=403)
    rk = (request.query_params.get("range") or "7d").lower()
    if rk not in ("7d", "30d", "90d"):
        rk = "7d"
    cur_start, cur_end, prev_start, prev_end = _windows(rk)

    # Pull every table we need — all are warm-cached; full table scan in Python
    # is fine at current data sizes (tens of thousands of rows max).
    stops, leads, acts, staff = [], [], [], []
    try: stops = await cached_rows(T_GOR_ROUTE_STOPS) or []
    except Exception: pass
    try: leads = await cached_rows(T_LEADS) or []
    except Exception: pass
    try: acts  = await cached_rows(T_ACTIVITIES) or []
    except Exception: pass
    try: staff = await cached_rows(T_STAFF) or []
    except Exception: pass

    # Build rep-name lookup keyed by lowercase email.
    rep_name: dict[str, str] = {}
    for s in staff:
        e = (s.get("Email") or "").strip().lower()
        if e:
            rep_name[e] = (s.get("Name") or s.get("Full Name") or e).strip() or e

    # Counters: per-email per-metric, current + prior window.
    metrics = ("stops", "leads", "convs", "acts")
    cur: dict[str, dict[str, int]] = defaultdict(lambda: {m: 0 for m in metrics})
    prv: dict[str, dict[str, int]] = defaultdict(lambda: {m: 0 for m in metrics})

    def _bump(bucket, email, key):
        if not email: return
        bucket[email.lower().strip()][key] += 1

    # Stops — Completed By email, Status=Visited, Completed At date.
    for r in stops:
        if _sv(r.get("Status")) != "Visited":
            continue
        email = (r.get("Completed By") or "").strip()
        d = _parse_iso_date(r.get("Completed At"))
        if not email or not d:
            continue
        if _in_window(d, cur_start, cur_end):  _bump(cur, email, "stops")
        elif _in_window(d, prev_start, prev_end): _bump(prv, email, "stops")

    # Leads — Owner email, Created date. Conversions tracked separately.
    for L in leads:
        email = (L.get("Owner") or "").strip()
        if not email:
            continue
        d = _parse_iso_date(L.get("Created") or L.get("Date"))
        if not d:
            continue
        is_conv = _sv(L.get("Status")) == "Converted"
        if _in_window(d, cur_start, cur_end):
            _bump(cur, email, "leads")
            if is_conv: _bump(cur, email, "convs")
        elif _in_window(d, prev_start, prev_end):
            _bump(prv, email, "leads")
            if is_conv: _bump(prv, email, "convs")

    # Activities — Author email, Date or Created.
    for a in acts:
        email = (a.get("Author") or "").strip()
        if not email:
            continue
        if _sv(a.get("Kind")) and _sv(a.get("Kind")) != "user_activity":
            # Allow blank Kind (legacy rows) but skip system kinds (e.g. 'system_log').
            continue
        d = _parse_iso_date(a.get("Date") or a.get("Created"))
        if not d:
            continue
        if _in_window(d, cur_start, cur_end):    _bump(cur, email, "acts")
        elif _in_window(d, prev_start, prev_end): _bump(prv, email, "acts")

    # Build the per-rep response.
    all_emails = set(cur.keys()) | set(prv.keys())
    reps = []
    for email in all_emails:
        c = cur[email]; p = prv[email]
        conv_pct = int(round((c["convs"] / c["leads"]) * 100)) if c["leads"] else 0
        reps.append({
            "email":         email,
            "name":          rep_name.get(email, email),
            "stops":         c["stops"],         "stops_delta":      _delta_pct(c["stops"], p["stops"]),
            "leads":         c["leads"],         "leads_delta":      _delta_pct(c["leads"], p["leads"]),
            "activities":    c["acts"],          "activities_delta": _delta_pct(c["acts"],  p["acts"]),
            "conversions":   c["convs"],         "conversions_delta": _delta_pct(c["convs"], p["convs"]),
            "conversion_pct": conv_pct,
        })
    reps.sort(key=lambda r: (-r["stops"], -r["leads"], r["name"].lower()))
    return JSONResponse({
        "range":    rk,
        "current":  {"start": cur_start.isoformat(),  "end": cur_end.isoformat()},
        "previous": {"start": prev_start.isoformat(), "end": prev_end.isoformat()},
        "reps":     reps,
    })


# ─────────────────────────────────────────────────────────────────────────────
# /reps/performance — admin leaderboard page
# ─────────────────────────────────────────────────────────────────────────────
def _rep_performance_page(br: str, bt: str, user: dict = None) -> str:
    from .shells import _page
    user = user or {}
    body = (
        '<div style="padding:18px 22px">'
        '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">'
        '<h2 style="margin:0;font-size:20px;font-weight:700">Rep Performance</h2>'
        '<select id="rp-range" onchange="loadRepPerf()" '
        'style="margin-left:auto;background:var(--bg2);border:1px solid var(--border);'
        'color:var(--text);border-radius:6px;padding:6px 10px;font-size:13px;font-family:inherit">'
        '<option value="7d">Last 7 days</option>'
        '<option value="30d">Last 30 days</option>'
        '<option value="90d">Last 90 days</option>'
        '</select>'
        '</div>'
        '<div id="rp-window" style="font-size:11px;color:var(--text3);margin-bottom:12px">—</div>'
        '<div id="rp-board" style="background:var(--bg2);border:1px solid var(--border);'
        'border-radius:10px;overflow:hidden">'
        '<div style="padding:30px;text-align:center;color:var(--text3);font-size:13px">Loading…</div>'
        '</div>'
        '</div>'
    )
    js = """
let _rpData = null;
let _rpSort = { col: 'stops', dir: 'desc' };

function _deltaPill(d) {
  if (d === 0) return '<span style="font-size:10px;color:var(--text3)">—</span>';
  var color = d > 0 ? '#059669' : '#ef4444';
  var arrow = d > 0 ? '▲' : '▼';
  return '<span style="font-size:10px;color:' + color + ';margin-left:4px;font-weight:700">' + arrow + Math.abs(d) + '%</span>';
}

function renderRepPerf() {
  if (!_rpData) return;
  var rows = _rpData.reps.slice();
  var c = _rpSort.col, d = _rpSort.dir;
  rows.sort(function(a, b) {
    var av = a[c] || 0, bv = b[c] || 0;
    if (typeof av === 'string') return d === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
    return d === 'asc' ? av - bv : bv - av;
  });
  var headers = [
    { k: 'name',          label: 'Rep',         num: false },
    { k: 'stops',         label: 'Stops',       num: true  },
    { k: 'leads',         label: 'Leads',       num: true  },
    { k: 'conversions',   label: 'Converted',   num: true  },
    { k: 'conversion_pct',label: 'Conv %',      num: true  },
    { k: 'activities',    label: 'Activities',  num: true  },
  ];
  function _arrow(k) {
    if (_rpSort.col !== k) return '';
    return _rpSort.dir === 'desc' ? ' ↓' : ' ↑';
  }
  var html = '<table style="width:100%;border-collapse:collapse;font-size:13px">';
  html += '<thead><tr style="background:var(--bg);border-bottom:1px solid var(--border)">';
  headers.forEach(function(h) {
    html += '<th onclick="sortRepPerf(\\'' + h.k + '\\')" style="padding:10px 14px;text-align:' + (h.num ? 'right' : 'left') + ';font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:var(--text3);cursor:pointer;user-select:none">' + h.label + _arrow(h.k) + '</th>';
  });
  html += '</tr></thead><tbody>';
  if (!rows.length) {
    html += '<tr><td colspan="6" style="padding:30px;text-align:center;color:var(--text3);font-size:13px">No activity in this window.</td></tr>';
  }
  rows.forEach(function(r, i) {
    var bg = i % 2 ? 'var(--bg)' : 'transparent';
    html += '<tr style="background:' + bg + ';border-bottom:1px solid var(--border)">';
    html += '<td style="padding:10px 14px;font-weight:600">' + esc(r.name) + '<div style="font-size:10px;color:var(--text3);font-weight:400">' + esc(r.email) + '</div></td>';
    html += '<td style="padding:10px 14px;text-align:right">' + r.stops + _deltaPill(r.stops_delta) + '</td>';
    html += '<td style="padding:10px 14px;text-align:right">' + r.leads + _deltaPill(r.leads_delta) + '</td>';
    html += '<td style="padding:10px 14px;text-align:right">' + r.conversions + _deltaPill(r.conversions_delta) + '</td>';
    html += '<td style="padding:10px 14px;text-align:right">' + r.conversion_pct + '%</td>';
    html += '<td style="padding:10px 14px;text-align:right">' + r.activities + _deltaPill(r.activities_delta) + '</td>';
    html += '</tr>';
  });
  html += '</tbody></table>';
  document.getElementById('rp-board').innerHTML = html;
  document.getElementById('rp-window').textContent =
    'Current: ' + _rpData.current.start + ' → ' + _rpData.current.end +
    '   ·   Compared to: ' + _rpData.previous.start + ' → ' + _rpData.previous.end;
}

function sortRepPerf(col) {
  if (_rpSort.col === col) {
    _rpSort.dir = _rpSort.dir === 'desc' ? 'asc' : 'desc';
  } else {
    _rpSort = { col: col, dir: col === 'name' ? 'asc' : 'desc' };
  }
  renderRepPerf();
}

async function loadRepPerf() {
  var range = document.getElementById('rp-range').value;
  document.getElementById('rp-board').innerHTML =
    '<div style="padding:30px;text-align:center;color:var(--text3);font-size:13px">Loading…</div>';
  try {
    var r = await fetch('/api/admin/rep-performance?range=' + encodeURIComponent(range), { cache: 'no-store' });
    if (!r.ok) {
      document.getElementById('rp-board').innerHTML =
        '<div style="padding:30px;text-align:center;color:#ef4444;font-size:13px">Failed (HTTP ' + r.status + ')</div>';
      return;
    }
    _rpData = await r.json();
    renderRepPerf();
  } catch (e) {
    document.getElementById('rp-board').innerHTML =
      '<div style="padding:30px;text-align:center;color:#ef4444;font-size:13px">Network error</div>';
  }
}

loadRepPerf();
"""
    return _page('reps_perf', 'Rep Performance', '', body, js, br, bt, user=user)
