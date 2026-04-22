"""
Inbox — cross-entity activity stream.

One page that merges:
  - Every T_ACTIVITIES row (company / person-linked edits, user activities,
    meetings, referrals, bulk-edit summaries, lead stage-change logs)
  - Every T_TICKET_COMMENTS row (ticket comments + system state changes)

Filter sidebar: Mine toggle, Kind checkboxes, Time range. Rows reuse a
compact feed style and link directly to the source record.
"""
from .shared import _page


_INBOX_STYLES = """
<style>
.ib-grid{display:grid;grid-template-columns:240px 1fr;gap:22px;padding:16px 0 0}
@media(max-width:860px){.ib-grid{grid-template-columns:1fr}}
.ib-side{position:sticky;top:18px;align-self:start;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px 18px}
.ib-side h4{font-size:11px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.4px;margin:14px 0 6px}
.ib-side h4:first-child{margin-top:0}
.ib-side label{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--text);margin-bottom:5px;cursor:pointer;line-height:1.3}
.ib-side input[type=checkbox]{accent-color:#3b82f6}
.ib-side select{width:100%;padding:6px 9px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:13px}
.ib-side .count{color:var(--text3);font-size:11px;margin-left:auto}
.ib-refresh{margin-top:18px;padding:7px 0;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:12px;width:100%;cursor:pointer}
.ib-refresh:hover{border-color:var(--text3)}
.ib-hint{font-size:11px;color:var(--text3);margin-top:10px}
.ib-feed{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:6px 0;min-height:240px}
.ib-item{padding:12px 18px;border-bottom:1px solid rgba(30,58,95,.25);display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:baseline}
.ib-item:last-child{border-bottom:0}
.ib-item:hover{background:rgba(59,130,246,.04)}
.ib-kind{font-size:10px;font-weight:700;color:#fff;background:#3b82f6;padding:2px 7px;border-radius:4px;text-transform:uppercase;letter-spacing:.3px;white-space:nowrap;align-self:start;margin-top:2px}
.ib-kind.edit{background:#64748b}
.ib-kind.user_activity{background:#059669}
.ib-kind.comment{background:#3b82f6}
.ib-kind.status_change{background:#ea580c}
.ib-kind.assignment{background:#7c3aed}
.ib-kind.creation{background:#10b981}
.ib-kind.note{background:#0891b2}
.ib-body{min-width:0;line-height:1.4}
.ib-summary{font-size:13px;color:var(--text);white-space:pre-wrap;overflow-wrap:anywhere}
.ib-meta{font-size:11px;color:var(--text3);margin-top:3px;display:flex;gap:10px;flex-wrap:wrap}
.ib-src{font-weight:600;color:var(--text2);text-decoration:none}
.ib-src:hover{color:#3b82f6}
.ib-src-type{font-size:10px;text-transform:uppercase;letter-spacing:.3px;color:var(--text4);margin-right:4px}
.ib-when{color:var(--text3);font-size:11px;font-variant-numeric:tabular-nums;white-space:nowrap;align-self:start;margin-top:3px}
.ib-empty{padding:60px 20px;text-align:center;color:var(--text3);font-size:13px}
.ib-loading{padding:40px 20px;text-align:center;color:var(--text3);font-size:12px}
.ib-count{font-size:12px;color:var(--text3);padding:10px 18px 6px;border-bottom:1px solid var(--border)}
</style>
"""

_KINDS = [
    ("user_activity", "Activities"),
    ("edit",          "Edits"),
    ("creation",      "New records"),
    ("comment",       "Comments"),
    ("status_change", "Status changes"),
    ("assignment",    "Assignments"),
    ("note",          "Notes"),
]


def _inbox_page(br: str, bt: str, user: dict = None) -> str:
    header = (
        '<div class="header">'
        '<div class="header-left">'
        '<h1>\U0001f4e5 Inbox</h1>'
        '<div class="sub">Everything happening across the CRM</div>'
        '</div>'
        '<div class="header-right">'
        '<span id="ib-refreshed" style="font-size:11px;color:var(--text3)"></span>'
        '</div>'
        '</div>'
    )

    kind_checks = "".join(
        f'<label><input type="checkbox" class="ib-kind-check" data-kind="{k}" checked>{lbl}</label>'
        for k, lbl in _KINDS
    )

    body = (
        _INBOX_STYLES
        + '<div class="ib-grid">'
        + '<aside class="ib-side">'
        + '<h4>Scope</h4>'
        + '<label><input type="checkbox" id="ib-mine"> Mine only</label>'
        + '<h4>Time range</h4>'
        + '<select id="ib-since">'
        + '<option value="1d">Last 24 hours</option>'
        + '<option value="7d" selected>Last 7 days</option>'
        + '<option value="30d">Last 30 days</option>'
        + '<option value="">All time</option>'
        + '</select>'
        + f'<h4>Kinds</h4>{kind_checks}'
        + '<button class="ib-refresh" onclick="ibLoad()">Refresh now</button>'
        + '<div class="ib-hint">Auto-refreshes every 60s.</div>'
        + '</aside>'
        + '<section class="ib-feed">'
        + '<div class="ib-count" id="ib-count">Loading\u2026</div>'
        + '<div id="ib-list"><div class="ib-loading">Loading activity\u2026</div></div>'
        + '</section>'
        + '</div>'
    )

    js = r"""
const USER_EMAIL = __USER_EMAIL_JS__;
let _IB_TIMER = null;

function fmtWhen(iso){
  if (!iso) return '\u2014';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const now = new Date();
  const diffMs = now - d;
  const mins = Math.round(diffMs / 60000);
  if (mins < 1)    return 'just now';
  if (mins < 60)   return mins + 'm ago';
  const hrs = Math.round(mins / 60);
  if (hrs < 24)    return hrs + 'h ago';
  const days = Math.round(hrs / 24);
  if (days < 7)    return days + 'd ago';
  return d.toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'});
}

function srcIcon(type){
  return {company:'\U0001f3e2', person:'\U0001f464', ticket:'\U0001f39f', lead:'\U0001f4e5'}[type] || '\u2022';
}

function buildParams(){
  const p = new URLSearchParams();
  if (document.getElementById('ib-mine').checked) p.set('mine', '1');
  const since = document.getElementById('ib-since').value;
  if (since) p.set('since', since);
  const kinds = Array.from(document.querySelectorAll('.ib-kind-check:checked')).map(b => b.dataset.kind);
  const allKinds = document.querySelectorAll('.ib-kind-check').length;
  if (kinds.length && kinds.length < allKinds) p.set('kind', kinds.join(','));
  p.set('limit', '200');
  return p.toString();
}

async function ibLoad(){
  try {
    const r = await fetch('/api/activities/stream?' + buildParams());
    if (!r.ok) {
      document.getElementById('ib-list').innerHTML = '<div class="ib-empty">Failed to load (' + r.status + ').</div>';
      document.getElementById('ib-count').textContent = '';
      return;
    }
    const data = await r.json();
    const items = data.items || [];
    document.getElementById('ib-count').textContent =
      items.length + (data.total && data.total > items.length ? ' of ' + data.total : '') + ' events';
    document.getElementById('ib-refreshed').textContent = 'Updated ' +
      new Date().toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'});
    if (!items.length){
      document.getElementById('ib-list').innerHTML = '<div class="ib-empty">No activity matches the current filters.</div>';
      return;
    }
    document.getElementById('ib-list').innerHTML = items.map(function(e){
      const src = e.source || {};
      const kind = e.kind || 'user_activity';
      const type = e.type ? (' \u00b7 ' + e.type) : '';
      return '<div class="ib-item">'
        + '<span class="ib-kind ' + kind + '">' + (kind.replace('_',' ')) + '</span>'
        + '<div class="ib-body">'
        +   '<div class="ib-summary">' + esc(e.summary || '(no summary)') + '</div>'
        +   '<div class="ib-meta">'
        +     (src.url
                ? '<a class="ib-src" href="' + esc(src.url) + '">'
                    + srcIcon(src.type) + ' ' + esc(src.name || '(unknown)')
                  + '</a>'
                : '<span class="ib-src">\u2014</span>')
        +     (e.author ? '<span>' + esc(e.author) + '</span>' : '')
        +     (type     ? '<span>' + esc(type) + '</span>'     : '')
        +   '</div>'
        + '</div>'
        + '<span class="ib-when">' + esc(fmtWhen(e.created)) + '</span>'
        + '</div>';
    }).join('');
  } catch(err) {
    document.getElementById('ib-list').innerHTML = '<div class="ib-empty">Error: ' + esc(String(err)) + '</div>';
  }
}

function ibScheduleRefresh(){
  if (_IB_TIMER) clearInterval(_IB_TIMER);
  _IB_TIMER = setInterval(ibLoad, 60000);
}

document.getElementById('ib-mine').addEventListener('change', ibLoad);
document.getElementById('ib-since').addEventListener('change', ibLoad);
document.querySelectorAll('.ib-kind-check').forEach(function(b){ b.addEventListener('change', ibLoad); });

ibLoad();
ibScheduleRefresh();
"""

    js = js.replace("__USER_EMAIL_JS__",
                    '"' + ((user or {}).get("email") or "").replace('"', '\\"') + '"')

    return _page('inbox', 'Inbox', header, body, js, br, bt, user=user)
