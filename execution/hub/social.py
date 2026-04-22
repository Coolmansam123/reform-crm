"""
Social media pages — unified monitor (/social) + legacy poster hub (/social/poster).
"""
import os

from .shared import _page, _has_social_access


def _social_inbox_page(br: str, bt: str, user: dict = None) -> str:
    """Incoming notifications from Facebook + Instagram (comments/DMs/mentions)."""
    user = user or {}
    header = (
        '<div class="header">'
        '<div class="header-left">'
        '<h1>\U0001f4e8 Social Inbox</h1>'
        '<div class="sub">Comments, mentions, and DMs from Facebook + Instagram</div>'
        '</div>'
        '<div class="header-right">'
        '<button class="btn btn-sec" onclick="connectMeta()" id="si-connect" style="margin-right:8px">\U0001f517 Connect Facebook + Instagram</button>'
        '<button class="btn btn-sec" onclick="markAllRead()" style="margin-right:8px">\u2713 Mark all read</button>'
        '<button class="btn btn-sec" onclick="loadInbox()">\u21bb Refresh</button>'
        '</div>'
        '</div>'
    )

    if not _has_social_access(user):
        body = (
            '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;'
            'padding:80px 20px;text-align:center">'
            '<div style="font-size:48px;margin-bottom:16px">\U0001f512</div>'
            '<div style="font-size:18px;font-weight:700;margin-bottom:8px">Access Restricted</div>'
            '<div style="font-size:14px;color:var(--text3);max-width:360px">Social Inbox is restricted to authorized team members.</div>'
            '</div>'
        )
        return _page('social_inbox', 'Social Inbox', header, body, '', br, bt, user=user)

    body = """
<div class="stats-row" style="grid-template-columns:repeat(4,1fr)">
  <div class="stat-chip c-blue">  <div class="label">Unread</div>       <div class="value" id="si-unread">—</div></div>
  <div class="stat-chip c-purple"><div class="label">Last 24h</div>      <div class="value" id="si-day">—</div></div>
  <div class="stat-chip c-green"> <div class="label">Connected Pages</div><div class="value" id="si-pages" style="font-size:14px">—</div></div>
  <div class="stat-chip c-yellow"><div class="label">Last Poll</div>     <div class="value" id="si-poll" style="font-size:14px">—</div></div>
</div>

<div class="panel" style="margin-top:16px">
  <div class="panel-hd" style="flex-wrap:wrap;gap:10px">
    <span class="panel-title">Feed</span>
    <div style="display:flex;gap:6px;flex-wrap:wrap">
      <select id="si-platform" onchange="render()">
        <option value="">All platforms</option>
        <option value="facebook">\U0001f310 Facebook</option>
        <option value="instagram">\U0001f4f7 Instagram</option>
        <option value="tiktok">\U0001f3b5 TikTok</option>
      </select>
      <select id="si-kind" onchange="render()">
        <option value="">All kinds</option>
        <option value="comment">Comments</option>
        <option value="reply">Replies</option>
        <option value="mention">Mentions</option>
        <option value="dm">DMs</option>
        <option value="digest">Engagement</option>
      </select>
      <select id="si-status" onchange="render()">
        <option value="unread">Unread only</option>
        <option value="">All</option>
        <option value="read">Read</option>
        <option value="archived">Archived</option>
      </select>
      <input type="text" id="si-q" placeholder="Search\u2026" oninput="render()" style="min-width:180px">
    </div>
    <span class="panel-meta" id="si-count"></span>
  </div>
  <div class="panel-body" id="si-body"><div class="loading">Loading\u2026</div></div>
</div>
"""
    js = """
const PLATFORM_ICONS = {instagram:'\U0001f4f7', facebook:'\U0001f310', tiktok:'\U0001f3b5', youtube:'\U0001f534'};
const KIND_COLORS = {comment:'#2563eb', reply:'#06b6d4', mention:'#ea580c', dm:'#7c3aed', follow:'#059669', digest:'#64748b'};
let _rows = [];

function fmtDt(s) {
  if (!s) return '';
  try { return new Date(s).toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}); }
  catch(e) { return s; }
}
function kindPill(k) {
  const col = KIND_COLORS[k] || '#64748b';
  return '<span style="font-size:10px;padding:2px 8px;border-radius:7px;font-weight:700;background:'+col+'22;color:'+col+'">'+esc(k||'')+'</span>';
}
function platformPill(p) {
  return '<span style="font-size:11px;padding:1px 7px;border-radius:5px;background:var(--badge-bg)">'+(PLATFORM_ICONS[p]||'')+' '+esc(p||'')+'</span>';
}

function passFilters(r) {
  const plat = document.getElementById('si-platform').value;
  const kind = document.getElementById('si-kind').value;
  const stat = document.getElementById('si-status').value;
  const q    = (document.getElementById('si-q').value || '').toLowerCase();
  if (plat && r.platform !== plat) return false;
  if (kind && r.kind !== kind) return false;
  if (stat && r.status !== stat) return false;
  if (q) {
    const hay = ((r.body||'')+' '+(r.author_name||'')+' '+(r.author_handle||'')+' '+(r.post_caption||'')).toLowerCase();
    if (!hay.includes(q)) return false;
  }
  return true;
}

function renderRow(r) {
  const isUnread = r.status === 'unread';
  const borderL = isUnread ? '4px solid #3b82f6' : '4px solid transparent';
  const postSnip = r.post_caption ? '<div style="font-size:11px;color:var(--text3);margin-top:4px;font-style:italic">on: \u201c'+esc((r.post_caption||'').substring(0,60))+((r.post_caption||'').length>60?'\u2026':'')+'\u201d</div>' : '';
  return '<div style="padding:12px 16px;border-bottom:1px solid var(--border);border-left:'+borderL+';display:flex;gap:10px">'
    + '<div style="flex:1;min-width:0">'
    + '<div style="display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:5px">'
    +   platformPill(r.platform) + kindPill(r.kind)
    +   '<b style="font-size:13px">'+esc(r.author_name||r.author_handle||'Unknown')+'</b>'
    +   (r.author_handle ? '<span style="font-size:11px;color:var(--text3)">@'+esc(r.author_handle)+'</span>' : '')
    +   '<span style="font-size:11px;color:var(--text3);margin-left:auto">'+fmtDt(r.received_at)+'</span>'
    + '</div>'
    + '<div style="font-size:13px;line-height:1.5;color:var(--text2);white-space:pre-wrap">'+esc(r.body||'')+'</div>'
    + postSnip
    + '<div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">'
    +   (r.reply_url ? '<a href="'+esc(r.reply_url)+'" target="_blank" rel="noopener" class="btn btn-sec" style="font-size:11px;padding:3px 10px">\u21aa Reply</a>' : '')
    +   (r.post_url ? '<a href="'+esc(r.post_url)+'" target="_blank" rel="noopener" class="btn btn-sec" style="font-size:11px;padding:3px 10px">\u2197 Open post</a>' : '')
    +   (isUnread ? '<button class="btn btn-sec" style="font-size:11px;padding:3px 10px" onclick="markRead('+r.id+')">\u2713 Mark read</button>' : '')
    + '</div>'
    + '</div></div>';
}

function render() {
  const filtered = _rows.filter(passFilters);
  document.getElementById('si-count').textContent = filtered.length + ' shown';
  document.getElementById('si-body').innerHTML = filtered.length
    ? filtered.map(renderRow).join('')
    : '<div class="empty" style="padding:32px;text-align:center">'
      + '<div style="font-size:36px;margin-bottom:10px">\U0001f4ed</div>'
      + '<div style="font-weight:700;margin-bottom:4px">No notifications yet</div>'
      + '<div style="color:var(--text3);font-size:13px">Connect Facebook + Instagram to start receiving comments and mentions.</div>'
      + '</div>';
}

async function loadInbox() {
  const [rowsRes, statRes] = await Promise.all([
    fetch('/api/social/notifications').then(r=>r.json()).catch(()=>({rows:[]})),
    fetch('/api/social/connections').then(r=>r.json()).catch(()=>({pages:[], last_poll:null})),
  ]);
  _rows = (rowsRes && rowsRes.rows) || [];

  document.getElementById('si-unread').textContent = _rows.filter(r=>r.status==='unread').length;
  const dayAgo = Date.now() - 24*60*60*1000;
  document.getElementById('si-day').textContent = _rows.filter(r => r.received_at && new Date(r.received_at).getTime() > dayAgo).length;
  const pages = (statRes && statRes.pages) || [];
  document.getElementById('si-pages').textContent = pages.length ? (pages.length + ' connected') : 'None';
  document.getElementById('si-poll').textContent = statRes && statRes.last_poll ? fmtDt(statRes.last_poll) : 'Never';

  render();
  stampRefresh();
}

async function markRead(rowId) {
  await fetch('/api/social/notifications/'+rowId+'/read', {method:'POST'});
  const r = _rows.find(x=>x.id===rowId);
  if (r) r.status = 'read';
  render();
  document.getElementById('si-unread').textContent = _rows.filter(x=>x.status==='unread').length;
}
async function markAllRead() {
  if (!confirm('Mark every unread notification as read?')) return;
  await fetch('/api/social/notifications/mark-all-read', {method:'POST'});
  loadInbox();
}
function connectMeta() {
  window.location.href = '/oauth/meta/start';
}

loadInbox();
setInterval(loadInbox, 60000);
"""
    return _page('social_inbox', 'Social Inbox', header, body, js, br, bt, user=user)


def _social_poster_hub_page(br: str, bt: str, user: dict = None) -> str:
    user = user or {}
    header = (
        '<div class="header" style="background:linear-gradient(135deg,rgba(124,58,237,0.15),transparent)">'
        '<div class="header-left">'
        '<h1>\U0001f3ac Poster Hub</h1>'
        '<div class="sub">Social media posting queue and recent history</div>'
        '</div></div>'
    )

    if not _has_social_access(user):
        body = (
            '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;'
            'padding:80px 20px;text-align:center">'
            '<div style="font-size:48px;margin-bottom:16px">\U0001f512</div>'
            '<div style="font-size:18px;font-weight:700;margin-bottom:8px">Access Restricted</div>'
            '<div style="font-size:14px;color:var(--text3);max-width:360px">The Poster Hub is restricted to authorized team members. '
            'Contact an admin to request access.</div>'
            '</div>'
        )
        return _page('social_poster', 'Poster Hub', header, body, '', br, bt, user=user)

    body = """
<div class="stats-row" style="grid-template-columns:repeat(4,1fr)">
  <div class="stat-chip c-purple"><div class="label">Queued Posts</div><div class="value" id="s-queue">—</div></div>
  <div class="stat-chip c-green"> <div class="label">Posted This Week</div><div class="value" id="s-week">—</div></div>
  <div class="stat-chip c-blue">  <div class="label">Photos Queued</div><div class="value" id="s-photos">—</div></div>
  <div class="stat-chip c-yellow"><div class="label">Videos Queued</div><div class="value" id="s-videos">—</div></div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
  <div class="panel" style="margin:0">
    <div class="panel-hd">
      <span class="panel-title">\u23f3 Posting Queue</span>
      <span class="panel-meta" id="queue-ct"></span>
    </div>
    <div class="panel-body" id="queue-body"><div class="loading">Loading\u2026</div></div>
  </div>
  <div class="panel" style="margin:0">
    <div class="panel-hd">
      <span class="panel-title">\u2705 Recently Posted</span>
      <span class="panel-meta" id="posted-ct"></span>
    </div>
    <div class="panel-body" id="posted-body"><div class="loading">Loading\u2026</div></div>
  </div>
</div>
"""
    js = """
const PLATFORM_ICONS = {instagram:'\U0001f4f7', facebook:'\U0001f310', tiktok:'\U0001f3b5', youtube:'\U0001f534'};
const CAT_COLORS = {
  'Testimonial':'#7c3aed','P.O.V':'#ea580c','Wellness Tip':'#059669',
  'Doctor Q&A':'#2563eb','Informative':'#0891b2','Chiropractic ASMR':'#db2777',
  'Injury Care and Recovery':'#dc2626','Anatomy and Body Knowledge':'#65a30d',
  'Manuthera Showcase':'#d97706','Time-Lapse':'#7c3aed',
};

function catBadge(cat) {
  const col = CAT_COLORS[cat] || '#475569';
  return '<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:8px;background:'+col+'22;color:'+col+'">'+esc(cat||'Unknown')+'</span>';
}
function platformPills(platforms) {
  if (!platforms) return '';
  const list = Array.isArray(platforms) ? platforms : String(platforms).split(',').map(s=>s.trim());
  return list.map(p => '<span style="font-size:11px;padding:1px 6px;border-radius:4px;background:var(--badge-bg);margin-right:3px">'+(PLATFORM_ICONS[p]||'')+' '+esc(p)+'</span>').join('');
}
function resultPills(results) {
  if (!Array.isArray(results)) return '';
  return results.map(r => {
    const ok = r.success || r.ok || (r.status === 'ok');
    const p  = r.platform || '';
    return '<span style="font-size:11px;padding:1px 6px;border-radius:4px;background:'+(ok?'rgba(5,150,105,0.2)':'rgba(239,68,68,0.2)')+';color:'+(ok?'#34d399':'#f87171')+';margin-right:3px">'+(PLATFORM_ICONS[p]||'')+' '+esc(p)+' '+(ok?'\u2713':'\u2717')+'</span>';
  }).join('');
}
function fmtDt(s) {
  if (!s) return '';
  try { return new Date(s).toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}); }
  catch(e) { return s; }
}
function statusChip(s) {
  const map = {pending:'#f59e0b',posting:'#3b82f6',posted:'#34d399',failed:'#ef4444'};
  const col = map[s] || '#64748b';
  return '<span style="font-size:10px;padding:2px 7px;border-radius:6px;font-weight:700;background:'+col+'22;color:'+col+'">'+esc(s||'unknown')+'</span>';
}

function renderQueueItem(m) {
  const caption = esc((m.caption||'').substring(0,90)) + ((m.caption||'').length>90?'\u2026':'');
  const thumb = m.media_url && m.content_type==='photo'
    ? '<img src="'+esc(m.media_url)+'" style="width:52px;height:52px;object-fit:cover;border-radius:6px;flex-shrink:0" onerror="this.style.display=\\'none\\'">'
    : '<div style="width:52px;height:52px;border-radius:6px;background:var(--card);display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:20px">'+(m.content_type==='video'?'\U0001f3ac':'\U0001f4f7')+'</div>';
  return '<div style="display:flex;gap:12px;padding:12px 16px;border-bottom:1px solid var(--border);align-items:flex-start">'
    + thumb
    + '<div style="flex:1;min-width:0">'
    + '<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:4px">'+catBadge(m.category)+statusChip(m.status)+'</div>'
    + '<div style="font-size:12px;color:var(--text2);margin-bottom:5px;line-height:1.4">'+caption+'</div>'
    + '<div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center">'
    + platformPills(m.platforms)
    + (m.scheduled_at ? '<span style="font-size:11px;color:var(--text3);margin-left:4px">\U0001f4c5 '+fmtDt(m.scheduled_at)+'</span>' : '')
    + '</div></div></div>';
}

function renderPostedItem(m) {
  const caption = esc((m.caption||'').substring(0,80)) + ((m.caption||'').length>80?'\u2026':'');
  return '<div style="padding:12px 16px;border-bottom:1px solid var(--border)">'
    + '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">'
    + catBadge(m.category)
    + '<span style="font-size:11px;color:var(--text3)">'+fmtDt(m.posted_at)+'</span>'
    + '</div>'
    + (caption ? '<div style="font-size:12px;color:var(--text2);margin-bottom:5px;line-height:1.4">'+caption+'</div>' : '')
    + '<div>'+resultPills(m.post_results)+'</div>'
    + '</div>';
}

async function load() {
  const [qRes, pRes] = await Promise.all([
    fetch('/api/social/queue').then(r=>r.json()).catch(()=>[]),
    fetch('/api/social/posted').then(r=>r.json()).catch(()=>[]),
  ]);

  const queue  = Array.isArray(qRes) ? qRes : [];
  const posted = Array.isArray(pRes) ? pRes : [];

  document.getElementById('s-queue').textContent  = queue.length;
  document.getElementById('s-photos').textContent = queue.filter(m=>m.content_type==='photo').length;
  document.getElementById('s-videos').textContent = queue.filter(m=>m.content_type==='video').length;
  const weekAgo = Date.now() - 7*24*60*60*1000;
  document.getElementById('s-week').textContent = posted.filter(m => m.posted_at && new Date(m.posted_at).getTime() > weekAgo).length;

  document.getElementById('queue-ct').textContent = queue.length + ' pending';
  const queueSorted = queue.slice().sort((a,b)=>(a.scheduled_at||'').localeCompare(b.scheduled_at||''));
  document.getElementById('queue-body').innerHTML = queueSorted.length
    ? queueSorted.map(renderQueueItem).join('')
    : '<div class="empty" style="padding:24px">Queue is empty</div>';

  document.getElementById('posted-ct').textContent = posted.length + ' total';
  const postedSorted = posted.slice().sort((a,b)=>(b.posted_at||'').localeCompare(a.posted_at||'')).slice(0,20);
  document.getElementById('posted-body').innerHTML = postedSorted.length
    ? postedSorted.map(renderPostedItem).join('')
    : '<div class="empty" style="padding:24px">No posts yet</div>';

  stampRefresh();
}
load();
"""
    return _page('social_poster', 'Poster Hub', header, body, js, br, bt, user=user)


# ─── Unified Social Monitor (/social) ──────────────────────────────────────────
def _social_monitor_page(br: str, bt: str, user: dict = None) -> str:
    user = user or {}
    header = (
        '<div class="header">'
        '<div class="header-left">'
        '<h1>\U0001f4f1 Social Monitor</h1>'
        '<div class="sub">Scheduled posts, recent activity, and queue controls</div>'
        '</div>'
        '<div class="header-right">'
        '<a href="/social/inbox" class="btn btn-sec" style="margin-right:8px">\U0001f4e8 Inbox</a>'
        '<button class="btn btn-sec" onclick="loadAll()">\u21bb Refresh</button>'
        '</div>'
        '</div>'
    )

    if not _has_social_access(user):
        body = (
            '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;'
            'padding:80px 20px;text-align:center">'
            '<div style="font-size:48px;margin-bottom:16px">\U0001f512</div>'
            '<div style="font-size:18px;font-weight:700;margin-bottom:8px">Access Restricted</div>'
            '<div style="font-size:14px;color:var(--text3);max-width:360px">Social access is restricted to authorized team members.</div>'
            '</div>'
        )
        return _page('social', 'Social Monitor', header, body, '', br, bt, user=user)

    body = """
<div class="stats-row" style="grid-template-columns:repeat(5,1fr)">
  <div class="stat-chip c-purple"><div class="label">Scheduled</div><div class="value" id="k-queue">—</div></div>
  <div class="stat-chip c-green"> <div class="label">Posted (7d)</div><div class="value" id="k-week">—</div></div>
  <div class="stat-chip c-red">   <div class="label">Failures (7d)</div><div class="value" id="k-fail">—</div></div>
  <div class="stat-chip c-blue">  <div class="label">Next Up</div><div class="value" id="k-next" style="font-size:14px">—</div></div>
  <div class="stat-chip c-yellow"><div class="label">Auto-post</div><div class="value" id="k-cron" style="font-size:14px">—</div></div>
</div>

<div class="panel" style="margin-top:16px">
  <div class="panel-hd" style="flex-wrap:wrap;gap:10px">
    <span class="panel-title">\u23f3 Posting Queue</span>
    <div style="display:flex;gap:6px;flex-wrap:wrap">
      <select id="f-platform" onchange="render()">
        <option value="">All platforms</option>
        <option value="instagram">\U0001f4f7 Instagram</option>
        <option value="facebook">\U0001f310 Facebook</option>
        <option value="tiktok">\U0001f3b5 TikTok</option>
        <option value="youtube">\U0001f534 YouTube</option>
      </select>
      <select id="f-type" onchange="render()">
        <option value="">All types</option>
        <option value="photo">\U0001f4f7 Photos</option>
        <option value="video">\U0001f3ac Videos</option>
      </select>
      <input type="text" id="f-search" placeholder="Search caption\u2026" oninput="render()" style="min-width:180px">
    </div>
    <span class="panel-meta" id="queue-ct"></span>
  </div>
  <div class="panel-body" id="queue-body"><div class="loading">Loading\u2026</div></div>
</div>

<div class="panel" style="margin-top:16px">
  <div class="panel-hd">
    <span class="panel-title">\u2705 Recently Posted</span>
    <span class="panel-meta" id="posted-ct"></span>
  </div>
  <div class="panel-body" id="posted-body"><div class="loading">Loading\u2026</div></div>
</div>

<div id="sm-drawer-bd" class="sm-drawer-bd" onclick="closeDrawer()"></div>
<div id="sm-drawer" class="sm-drawer">
  <div class="sm-drawer-hdr">
    <div id="sm-d-title" style="font-weight:700;font-size:15px">Post details</div>
    <button class="btn btn-sec" onclick="closeDrawer()">\u2715</button>
  </div>
  <div id="sm-d-body" style="padding:16px 18px;overflow-y:auto;flex:1"></div>
</div>
"""
    css = """
<style>
.sm-drawer-bd{position:fixed;inset:0;background:rgba(0,0,0,0.4);display:none;z-index:900}
.sm-drawer-bd.open{display:block}
.sm-drawer{position:fixed;top:0;right:0;height:100vh;width:min(520px,94vw);background:var(--bg2);border-left:1px solid var(--border);transform:translateX(100%);transition:transform .18s ease;z-index:901;display:flex;flex-direction:column}
.sm-drawer.open{transform:translateX(0)}
.sm-drawer-hdr{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid var(--border)}
.sm-row{display:flex;gap:12px;padding:12px 16px;border-bottom:1px solid var(--border);align-items:flex-start;cursor:pointer;transition:background .12s}
.sm-row:hover{background:var(--card)}
.sm-thumb{width:56px;height:56px;border-radius:7px;object-fit:cover;flex-shrink:0;background:var(--card)}
.sm-row-actions{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}
.sm-row-actions button{font-size:11px;padding:3px 9px;border-radius:6px;border:1px solid var(--border);background:var(--bg2);color:var(--text);cursor:pointer}
.sm-row-actions button:hover{background:var(--card);border-color:var(--accent)}
.sm-row-actions .danger{color:#f87171;border-color:rgba(239,68,68,0.3)}
.sm-row-actions .primary{color:#34d399;border-color:rgba(52,211,153,0.3)}
</style>
"""
    body = css + body
    js = """
const PLATFORM_ICONS = {instagram:'\U0001f4f7', facebook:'\U0001f310', tiktok:'\U0001f3b5', youtube:'\U0001f534'};
const CAT_COLORS = {
  'Testimonial':'#7c3aed','P.O.V':'#ea580c','Wellness Tip':'#059669',
  'Doctor Q&A':'#2563eb','Informative':'#0891b2','Chiropractic ASMR':'#db2777',
  'Injury Care and Recovery':'#dc2626','Anatomy and Body Knowledge':'#65a30d',
  'Manuthera Showcase':'#d97706','Time-Lapse':'#7c3aed',
};
let _queue = [];
let _posted = [];
let _byId = {};

function catBadge(cat) {
  const col = CAT_COLORS[cat] || '#475569';
  return '<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:8px;background:'+col+'22;color:'+col+'">'+esc(cat||'Unknown')+'</span>';
}
function platformList(m) {
  const list = Array.isArray(m.platforms) ? m.platforms
    : (m.post_results ? m.post_results.map(r=>r.platform) : []);
  return list;
}
function platformPills(platforms) {
  if (!platforms) return '';
  const list = Array.isArray(platforms) ? platforms : String(platforms).split(',').map(s=>s.trim());
  return list.map(p => '<span style="font-size:11px;padding:1px 6px;border-radius:4px;background:var(--badge-bg);margin-right:3px">'+(PLATFORM_ICONS[p]||'')+' '+esc(p)+'</span>').join('');
}
function resultPills(results) {
  if (!Array.isArray(results)) return '';
  return results.map(r => {
    const ok = r.success || r.ok || (r.status === 'ok');
    const p  = r.platform || '';
    return '<span style="font-size:11px;padding:1px 6px;border-radius:4px;background:'+(ok?'rgba(5,150,105,0.2)':'rgba(239,68,68,0.2)')+';color:'+(ok?'#34d399':'#f87171')+';margin-right:3px">'+(PLATFORM_ICONS[p]||'')+' '+esc(p)+' '+(ok?'\u2713':'\u2717')+'</span>';
  }).join('');
}
function fmtDt(s) {
  if (!s) return '';
  try { return new Date(s).toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}); }
  catch(e) { return s; }
}
function statusChip(s) {
  const map = {pending:'#f59e0b',posting:'#3b82f6',posted:'#34d399',failed:'#ef4444'};
  const col = map[s] || '#64748b';
  return '<span style="font-size:10px;padding:2px 7px;border-radius:6px;font-weight:700;background:'+col+'22;color:'+col+'">'+esc(s||'unknown')+'</span>';
}
function hasFailure(m) {
  return Array.isArray(m.post_results) && m.post_results.some(r => !(r.success||r.ok||r.status==='ok'));
}

function passFilters(m) {
  const plat = document.getElementById('f-platform').value;
  const typ  = document.getElementById('f-type').value;
  const q    = (document.getElementById('f-search').value || '').toLowerCase();
  if (plat && !platformList(m).includes(plat)) return false;
  if (typ && m.content_type !== typ) return false;
  if (q && !((m.caption||'')+ ' ' + (m.category||'')).toLowerCase().includes(q)) return false;
  return true;
}

function renderQueueRow(m) {
  const caption = esc((m.caption||'').substring(0,110)) + ((m.caption||'').length>110?'\u2026':'');
  const thumb = m.media_url && m.content_type==='photo'
    ? '<img class="sm-thumb" src="'+esc(m.media_url)+'" onerror="this.style.display=\\'none\\'">'
    : '<div class="sm-thumb" style="display:flex;align-items:center;justify-content:center;font-size:22px">'+(m.content_type==='video'?'\U0001f3ac':'\U0001f4f7')+'</div>';
  const id = esc(m.task_id||'');
  return '<div class="sm-row" onclick="openDrawer(\\''+id+'\\')">'
    + thumb
    + '<div style="flex:1;min-width:0">'
    + '<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:4px">'+catBadge(m.category)+statusChip(m.status)+'</div>'
    + '<div style="font-size:12px;color:var(--text2);margin-bottom:5px;line-height:1.4">'+caption+'</div>'
    + '<div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center">'
    + platformPills(platformList(m))
    + (m.scheduled_at ? '<span style="font-size:11px;color:var(--text3);margin-left:4px">\U0001f4c5 '+fmtDt(m.scheduled_at)+'</span>' : '')
    + '</div>'
    + '<div class="sm-row-actions" onclick="event.stopPropagation()">'
    +   '<button class="primary" onclick="postNow(\\''+id+'\\')">\u25b6 Post now</button>'
    +   '<button onclick="reschedule(\\''+id+'\\')">\U0001f4c5 Reschedule</button>'
    +   '<button class="danger" onclick="removeFromQueue(\\''+id+'\\')">\u2715 Remove</button>'
    +   (m.task_url ? '<a href="'+esc(m.task_url)+'" target="_blank" rel="noopener"><button>\u2197 ClickUp</button></a>' : '')
    + '</div>'
    + '</div></div>';
}

function renderPostedRow(m) {
  const caption = esc((m.caption||'').substring(0,110)) + ((m.caption||'').length>110?'\u2026':'');
  const id = esc(m.task_id||'');
  return '<div class="sm-row" onclick="openDrawer(\\''+id+'\\')">'
    + '<div style="flex:1;min-width:0">'
    + '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">'
    +   catBadge(m.category)
    +   '<span style="font-size:11px;color:var(--text3)">'+fmtDt(m.posted_at)+'</span>'
    + '</div>'
    + (caption ? '<div style="font-size:12px;color:var(--text2);margin-bottom:5px;line-height:1.4">'+caption+'</div>' : '')
    + '<div>'+resultPills(m.post_results)+'</div>'
    + '</div></div>';
}

function render() {
  const qFiltered = _queue.filter(passFilters)
    .sort((a,b)=>(a.scheduled_at||'').localeCompare(b.scheduled_at||''));
  const pFiltered = _posted.filter(passFilters)
    .sort((a,b)=>(b.posted_at||'').localeCompare(a.posted_at||'')).slice(0,30);

  document.getElementById('queue-ct').textContent  = qFiltered.length + ' pending';
  document.getElementById('posted-ct').textContent = pFiltered.length + ' shown';

  document.getElementById('queue-body').innerHTML = qFiltered.length
    ? qFiltered.map(renderQueueRow).join('')
    : '<div class="empty" style="padding:24px">Queue is empty</div>';
  document.getElementById('posted-body').innerHTML = pFiltered.length
    ? pFiltered.map(renderPostedRow).join('')
    : '<div class="empty" style="padding:24px">No posts yet</div>';
}

async function loadAll() {
  const [qRes, pRes] = await Promise.all([
    fetch('/api/social/queue').then(r=>r.json()).catch(()=>[]),
    fetch('/api/social/posted').then(r=>r.json()).catch(()=>[]),
  ]);
  _queue  = Array.isArray(qRes) ? qRes : [];
  _posted = Array.isArray(pRes) ? pRes : [];
  _byId = {};
  _queue.forEach(m => { if (m.task_id) _byId[m.task_id] = m; });
  _posted.forEach(m => { if (m.task_id) _byId[m.task_id] = m; });

  document.getElementById('k-queue').textContent = _queue.length;
  const weekAgo = Date.now() - 7*24*60*60*1000;
  const posted7 = _posted.filter(m => m.posted_at && new Date(m.posted_at).getTime() > weekAgo);
  document.getElementById('k-week').textContent = posted7.length;
  document.getElementById('k-fail').textContent = posted7.filter(hasFailure).length;

  const next = _queue.slice().sort((a,b)=>(a.scheduled_at||'').localeCompare(b.scheduled_at||''))[0];
  document.getElementById('k-next').textContent = next && next.scheduled_at ? fmtDt(next.scheduled_at) : '—';
  document.getElementById('k-cron').textContent = 'Manual only';

  render();
  stampRefresh();
}

function openDrawer(taskId) {
  const m = _byId[taskId];
  if (!m) return;
  document.getElementById('sm-d-title').textContent = m.category || 'Post details';
  const media = m.content_type==='video' && m.media_url
    ? '<video src="'+esc(m.media_url)+'" controls style="width:100%;max-height:320px;border-radius:8px;background:#000"></video>'
    : (m.media_url ? '<img src="'+esc(m.media_url)+'" style="width:100%;max-height:320px;object-fit:contain;border-radius:8px;background:var(--card)">' : '');
  const scheduled = m.scheduled_at ? '<div style="color:var(--text3);font-size:12px;margin:6px 0">\U0001f4c5 Scheduled: '+fmtDt(m.scheduled_at)+'</div>' : '';
  const posted = m.posted_at ? '<div style="color:var(--text3);font-size:12px;margin:6px 0">\u2705 Posted: '+fmtDt(m.posted_at)+'</div>' : '';
  const plats = platformList(m);
  const platformsRow = plats.length ? '<div style="margin:8px 0">'+platformPills(plats)+'</div>' : '';
  const results = Array.isArray(m.post_results) ? m.post_results.map(r => {
    const ok = r.success || r.ok || r.status === 'ok';
    const link = r.permalink || r.url || '';
    return '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border)">'
      + '<div>'+(PLATFORM_ICONS[r.platform]||'')+' <b>'+esc(r.platform||'')+'</b></div>'
      + '<div>'
      +   (ok ? '<span style="color:#34d399;font-size:11px;font-weight:700">\u2713 Posted</span>'
             : '<span style="color:#f87171;font-size:11px;font-weight:700">\u2717 '+esc(r.error||'Failed')+'</span>')
      +   (link ? ' <a href="'+esc(link)+'" target="_blank" rel="noopener" style="margin-left:8px;font-size:11px">\u2197 view</a>' : '')
      + '</div></div>';
  }).join('') : '';
  const clickUp = m.task_url ? '<a href="'+esc(m.task_url)+'" target="_blank" rel="noopener" class="btn btn-sec" style="margin-top:10px;display:inline-block">\u2197 Open in ClickUp</a>' : '';
  document.getElementById('sm-d-body').innerHTML =
      media
    + scheduled
    + posted
    + platformsRow
    + '<div style="margin:6px 0">'+catBadge(m.category)+' '+statusChip(m.status)+'</div>'
    + (m.caption ? '<div style="white-space:pre-wrap;font-size:13px;line-height:1.5;padding:10px;background:var(--card);border-radius:7px;margin:8px 0">'+esc(m.caption)+'</div>' : '')
    + (results ? '<div style="margin-top:14px"><b>Platform results</b>'+results+'</div>' : '')
    + clickUp;
  document.getElementById('sm-drawer').classList.add('open');
  document.getElementById('sm-drawer-bd').classList.add('open');
}
function closeDrawer() {
  document.getElementById('sm-drawer').classList.remove('open');
  document.getElementById('sm-drawer-bd').classList.remove('open');
}

async function postNow(taskId) {
  if (!confirm('Post this to all its platforms right now?')) return;
  const r = await fetch('/api/social/post-now/'+encodeURIComponent(taskId), {method:'POST'});
  if (!r.ok) { alert('Post-now failed: ' + (await r.text())); return; }
  alert('Posting started. Check Recently Posted in a minute.');
  loadAll();
}
async function reschedule(taskId) {
  const m = _byId[taskId];
  const cur = m && m.scheduled_at ? m.scheduled_at.slice(0,16) : '';
  const when = prompt('Reschedule to (YYYY-MM-DD HH:MM, 24h, Pacific):', cur.replace('T',' '));
  if (!when) return;
  const iso = when.replace(' ', 'T');
  if (!/^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}/.test(iso)) { alert('Bad format — use YYYY-MM-DD HH:MM'); return; }
  const r = await fetch('/api/social/reschedule/'+encodeURIComponent(taskId), {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({scheduled_at: iso}),
  });
  if (!r.ok) { alert('Reschedule failed: ' + (await r.text())); return; }
  loadAll();
}
async function removeFromQueue(taskId) {
  if (!confirm('Remove this from the queue? The ClickUp task stays, but the scheduled post is deleted.')) return;
  const r = await fetch('/api/social/remove/'+encodeURIComponent(taskId), {method:'DELETE'});
  if (!r.ok) { alert('Remove failed: ' + (await r.text())); return; }
  loadAll();
}

loadAll();
setInterval(loadAll, 60000);
"""
    return _page('social', 'Social Monitor', header, body, js, br, bt, user=user)


def _social_schedule_page(br: str, bt: str, user: dict = None) -> str:
    # Back-compat shim — all /social renders the monitor now.
    return _social_monitor_page(br, bt, user=user)
