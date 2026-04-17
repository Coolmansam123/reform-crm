"""
Social media pages — poster hub and scheduling.
"""
import os

from .shared import _page, _has_social_access


def _social_poster_hub_page(br: str, bt: str, user: dict = None) -> str:
    user = user or {}
    header = (
        '<div class="header" style="background:linear-gradient(135deg,rgba(124,58,237,0.15),transparent)">'
        '<div class="header-left">'
        '<h1>\U0001f3ac Poster Hub</h1>'
        '<div class="sub">Social media posting queue and recent history</div>'
        '</div></div>'
    )

    # ── Permission wall ───────────────────────────────────────────────────────
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

    # ── Full page ─────────────────────────────────────────────────────────────
    platform_icons = {'instagram': '\U0001f4f7', 'facebook': '\U0001f310', 'tiktok': '\U0001f3b5', 'youtube': '\U0001f534'}
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
    ? '<img src="'+esc(m.media_url)+'" style="width:52px;height:52px;object-fit:cover;border-radius:6px;flex-shrink:0" onerror="this.style.display=\'none\'">'
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

  // Stats
  document.getElementById('s-queue').textContent  = queue.length;
  document.getElementById('s-photos').textContent = queue.filter(m=>m.content_type==='photo').length;
  document.getElementById('s-videos').textContent = queue.filter(m=>m.content_type==='video').length;
  const weekAgo = Date.now() - 7*24*60*60*1000;
  document.getElementById('s-week').textContent = posted.filter(m => m.posted_at && new Date(m.posted_at).getTime() > weekAgo).length;

  // Queue panel
  document.getElementById('queue-ct').textContent = queue.length + ' pending';
  const queueSorted = queue.slice().sort((a,b)=>(a.scheduled_at||'').localeCompare(b.scheduled_at||''));
  document.getElementById('queue-body').innerHTML = queueSorted.length
    ? queueSorted.map(renderQueueItem).join('')
    : '<div class="empty" style="padding:24px">Queue is empty</div>';

  // Posted panel
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


def _social_schedule_page(br: str, bt: str, user: dict = None) -> str:
    embed_url = os.environ.get("GOOGLE_SOCIAL_CALENDAR_EMBED_URL", "")
    header = (
        '<div class="header"><div class="header-left">'
        '<h1>\U0001f4f1 Social Media Schedule</h1>'
        '<div class="sub">Upcoming social media posts and campaigns</div>'
        '</div></div>'
    )
    if embed_url:
        body = (
            '<div style="padding:16px 18px;height:calc(100vh - 120px)">'
            f'<iframe src="{embed_url}" style="width:100%;height:100%;border:none;border-radius:10px" '
            'frameborder="0" scrolling="no"></iframe>'
            '</div>'
        )
    else:
        body = (
            '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;'
            'padding:80px 20px;text-align:center">'
            '<div style="font-size:48px;margin-bottom:16px">\U0001f4f1</div>'
            '<div style="font-size:16px;font-weight:700;margin-bottom:8px">Calendar Not Configured</div>'
            '<div style="font-size:13px;color:var(--text3)">Add <code>GOOGLE_SOCIAL_CALENDAR_EMBED_URL</code> to the Modal secret.</div>'
            '</div>'
        )
    return _page('social', 'Social Media Schedule', header, body, '', br, bt, user=user)
