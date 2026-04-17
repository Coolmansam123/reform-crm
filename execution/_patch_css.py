#!/usr/bin/env python3
"""Patch 1: Replace _CSS block in modal_outreach_hub.py with CSS-variable version."""
import pathlib

f = pathlib.Path("execution/modal_outreach_hub.py")
src = f.read_text(encoding="utf-8")

OLD_START = '_CSS = """\n'
# Use closing triple-quote only; preserve the separator comment that follows
OLD_END   = '\n"""\n\n# ─── Shared JS'

i = src.find(OLD_START)
j = src.find(OLD_END, i)
assert i != -1 and j != -1, f"anchors not found (i={i}, j={j})"

NEW_CSS = '''_CSS = """
:root {
  --bg:          #0d1b2a;
  --bg2:         #0a1628;
  --border:      #1e3a5f;
  --hdr-grad:    linear-gradient(135deg,#0f3460,#16213e);
  --text:        #e2e8f0;
  --text2:       #94a3b8;
  --text3:       #64748b;
  --text4:       #475569;
  --card:        rgba(255,255,255,0.04);
  --card-hover:  rgba(255,255,255,0.08);
  --nav-active:  #1e3a5f;
  --badge-bg:    rgba(30,58,95,0.8);
  --input-bg:    #0d1b2a;
  --chip-border: #1e3a5f;
  --shadow:      0 2px 8px rgba(0,0,0,0.3);
}
[data-theme="light"] {
  --bg:          #f1f5f9;
  --bg2:         #ffffff;
  --border:      #e2e8f0;
  --hdr-grad:    linear-gradient(135deg,#2563eb,#1d4ed8);
  --text:        #0f172a;
  --text2:       #334155;
  --text3:       #64748b;
  --text4:       #94a3b8;
  --card:        #ffffff;
  --card-hover:  #f8fafc;
  --nav-active:  #dbeafe;
  --badge-bg:    #e2e8f0;
  --input-bg:    #f8fafc;
  --chip-border: #e2e8f0;
  --shadow:      0 2px 8px rgba(0,0,0,0.08);
}
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--text); display:flex; min-height:100vh; transition:background 0.2s,color 0.2s; }
a { color:inherit; text-decoration:none; }

/* Sidebar */
.sidebar { width:210px; min-width:210px; background:var(--bg2); border-right:1px solid var(--border); display:flex; flex-direction:column; position:sticky; top:0; height:100vh; overflow-y:auto; flex-shrink:0; transition:background 0.2s; }
.sidebar-logo { padding:20px 16px 14px; border-bottom:1px solid var(--border); }
.sidebar-logo .brand { font-size:15px; font-weight:700; color:var(--text); }
.sidebar-logo .sub { font-size:11px; color:var(--text3); margin-top:3px; }
.sidebar-section { padding:14px 16px 4px; font-size:10px; font-weight:600; color:var(--text4); text-transform:uppercase; letter-spacing:1px; }
.sidebar-nav { list-style:none; padding:0 8px 8px; }
.sidebar-nav li a { display:flex; align-items:center; gap:8px; padding:8px 10px; border-radius:7px; font-size:13px; color:var(--text2); transition:all 0.12s; }
.sidebar-nav li a:hover { background:var(--card-hover); color:var(--text); }
.sidebar-nav li a.active { background:var(--nav-active); color:var(--text); font-weight:600; }
[data-theme="light"] .sidebar-nav li a.active { color:#1d4ed8; }
.sidebar-bottom { margin-top:auto; padding:10px 8px 16px; border-top:1px solid var(--border); display:flex; flex-direction:column; gap:4px; }
.sidebar-bottom a { display:block; padding:8px 10px; border-radius:7px; font-size:13px; color:var(--text3); }
.sidebar-bottom a:hover { background:var(--card-hover); color:var(--text); }
.theme-toggle { width:100%; padding:8px 10px; border-radius:7px; font-size:13px; color:var(--text3); background:none; border:none; cursor:pointer; text-align:left; display:flex; align-items:center; gap:8px; transition:all 0.12s; }
.theme-toggle:hover { background:var(--card-hover); color:var(--text); }

/* Accordion Nav Groups */
.nav-group-hd { display:flex; align-items:center; justify-content:space-between; padding:6px 10px; margin:1px 8px; border-radius:7px; font-size:10px; font-weight:600; color:var(--text4); text-transform:uppercase; letter-spacing:1px; cursor:pointer; transition:all 0.12s; }
.nav-group-hd:hover { background:var(--card-hover); color:var(--text2); }
.nav-arrow { font-size:8px; transition:transform 0.18s; display:inline-block; flex-shrink:0; }
.nav-group.open .nav-arrow { transform:rotate(90deg); }
.nav-group-body { overflow:hidden; max-height:0; transition:max-height 0.22s ease; }
.nav-group.open .nav-group-body { max-height:400px; }

/* Main */
.main { flex:1; overflow-y:auto; min-width:0; }
.header { background:var(--hdr-grad); border-bottom:1px solid var(--border); padding:18px 28px; display:flex; align-items:center; justify-content:space-between; }
.header-left h1 { font-size:19px; font-weight:700; color:#fff; }
.header-left .sub { font-size:12px; color:rgba(255,255,255,0.6); margin-top:3px; }
.header-right { display:flex; align-items:center; gap:10px; }
.btn { display:inline-flex; align-items:center; gap:6px; padding:7px 13px; border-radius:7px; font-size:12px; font-weight:500; cursor:pointer; border:none; transition:all 0.12s; }
.btn-ghost { background:rgba(255,255,255,0.15); color:#fff; }
.btn-ghost:hover { background:rgba(255,255,255,0.25); }
.content { padding:22px 28px; }

/* Stats row */
.stats-row { display:flex; gap:12px; margin-bottom:22px; flex-wrap:wrap; }
.stat-chip { flex:1; min-width:120px; background:var(--card); border:1px solid var(--chip-border); border-radius:10px; padding:14px 16px; }
.stat-chip .label { font-size:10px; color:var(--text3); text-transform:uppercase; letter-spacing:0.5px; margin-bottom:5px; }
.stat-chip .value { font-size:28px; font-weight:700; color:var(--text); }
.stat-chip.c-purple .value { color:#a78bfa; }
.stat-chip.c-green  .value { color:#34d399; }
.stat-chip.c-red    .value { color:#f87171; }
.stat-chip.c-yellow .value { color:#fbbf24; }
.stat-chip.c-orange .value { color:#fb923c; }
.stat-chip.c-blue   .value { color:#60a5fa; }

/* Tool cards */
.tool-cards { display:flex; gap:14px; margin-bottom:22px; flex-wrap:wrap; }
.tool-card { flex:1; min-width:190px; background:var(--card); border:1px solid var(--chip-border); border-radius:12px; padding:18px 20px; box-shadow:var(--shadow); }
.tc-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; }
.tc-name { font-size:14px; font-weight:700; }
.tc-pill { font-size:10px; padding:3px 8px; border-radius:10px; font-weight:600; }
.tc-stats { display:flex; gap:20px; margin-bottom:12px; }
.tc-stat .n { font-size:22px; font-weight:700; }
.tc-stat .l { font-size:11px; color:var(--text3); margin-top:1px; }
.prog-wrap { background:var(--border); border-radius:4px; height:6px; overflow:hidden; margin-bottom:12px; }
.prog-fill { height:100%; border-radius:4px; transition:width 0.4s; }
.tc-btn { display:block; text-align:center; padding:7px; border-radius:7px; font-size:12px; font-weight:600; background:var(--card-hover); border:1px solid var(--border); }
.tc-btn:hover { background:var(--nav-active); }

/* Two-column */
.two-col { display:flex; gap:14px; }
.col-l { flex:55; min-width:0; }
.col-r { flex:45; min-width:0; }

/* Panel */
.panel { background:var(--card); border:1px solid var(--chip-border); border-radius:12px; margin-bottom:16px; box-shadow:var(--shadow); }
.panel-hd { padding:13px 18px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }
.panel-title { font-size:14px; font-weight:700; }
.panel-ct { font-size:12px; color:var(--text3); }
.panel-body { padding:4px 0; }

/* Alert rows */
.a-row { display:flex; align-items:center; gap:10px; padding:9px 18px; border-bottom:1px solid rgba(30,58,95,0.3); }
.a-row:last-child { border-bottom:none; }
.dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.dot-r { background:#ef4444; }
.dot-y { background:#f59e0b; }
.dot-g { background:#10b981; }
.a-name { font-size:13px; flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.a-meta { font-size:11px; color:var(--text3); flex-shrink:0; }
.badge { font-size:10px; padding:2px 7px; border-radius:8px; font-weight:600; flex-shrink:0; }
.b-pi  { background:rgba(124,58,237,0.2); color:#a78bfa; }
.b-gor { background:rgba(234,88,12,0.2);  color:#fb923c; }
.b-com { background:rgba(5,150,105,0.2);  color:#34d399; }
.date-badge { font-size:10px; background:var(--badge-bg); color:var(--text2); padding:2px 8px; border-radius:6px; flex-shrink:0; }

/* Pipeline */
.pipeline { padding:14px 18px; }
.pipe-row { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
.pipe-label { width:170px; font-size:12px; color:var(--text2); flex-shrink:0; }
.pipe-bar { flex:1; background:var(--border); border-radius:4px; height:10px; overflow:hidden; }
.pipe-fill { height:100%; border-radius:4px; transition:width 0.4s; }
.pipe-n { font-size:12px; color:var(--text2); width:40px; text-align:right; flex-shrink:0; }
.pipe-pct { font-size:11px; color:var(--text4); width:38px; text-align:right; flex-shrink:0; }

/* Activity rows */
.act-row { display:flex; gap:10px; padding:9px 18px; border-bottom:1px solid rgba(30,58,95,0.3); align-items:flex-start; }
.act-row:last-child { border-bottom:none; }
.act-date { font-size:11px; color:var(--text3); width:64px; flex-shrink:0; padding-top:2px; }
.act-body { flex:1; min-width:0; }
.act-name { font-size:13px; font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.act-type { font-size:11px; color:var(--text3); margin-top:1px; }

/* Type breakdown */
.type-row { display:flex; align-items:center; justify-content:space-between; padding:8px 18px; border-bottom:1px solid rgba(30,58,95,0.3); }
.type-row:last-child { border-bottom:none; }
.type-name { font-size:13px; }
.type-n { font-size:13px; font-weight:600; color:var(--text2); }

/* Empty / loading */
.empty   { padding:24px; text-align:center; color:var(--text4); font-size:13px; }
.loading { padding:32px; text-align:center; color:var(--text4); font-size:13px; }

/* Login */
body.login-body { display:block; }
.login-wrap { display:flex; align-items:center; justify-content:center; min-height:100vh; }
.login-box { background:#0a1628; border:1px solid #1e3a5f; border-radius:16px; padding:40px; width:340px; }
.login-box h1 { font-size:22px; font-weight:700; margin-bottom:6px; }
.login-box .sub { font-size:13px; color:#64748b; margin-bottom:28px; }
.login-box input { width:100%; padding:10px 14px; background:#0d1b2a; border:1px solid #1e3a5f; border-radius:8px; color:#e2e8f0; font-size:14px; margin-bottom:12px; outline:none; }
.login-box input:focus { border-color:#3b82f6; }
.login-box button { width:100%; padding:10px; background:#3b82f6; color:white; border:none; border-radius:8px; font-size:14px; font-weight:600; cursor:pointer; }
.login-box button:hover { background:#2563eb; }
.login-err { color:#ef4444; font-size:13px; margin-top:10px; text-align:center; }

/* Data table */
.data-table { width:100%; border-collapse:collapse; font-size:13px; }
.data-table th { text-align:left; padding:10px 14px; font-size:11px; font-weight:600; color:var(--text3); text-transform:uppercase; border-bottom:1px solid var(--border); }
.data-table th.r { text-align:right; }
.data-table th.c { text-align:center; }
.data-table td { padding:9px 14px; border-bottom:1px solid rgba(30,58,95,0.3); color:var(--text); }
.data-table td.r { text-align:right; }
.data-table td.c { text-align:center; }
.data-table tr:last-child td { border-bottom:none; }
.data-table tr:hover td { background:var(--card-hover); }

/* Filter bar */
.filter-bar { padding:14px 18px 10px; display:flex; gap:8px; flex-wrap:wrap; align-items:center; border-bottom:1px solid var(--border); }
.filter-btn { padding:4px 12px; border-radius:20px; font-size:12px; font-weight:500; border:1px solid var(--border); background:var(--card); color:var(--text2); cursor:pointer; transition:all 0.12s; }
.filter-btn:hover,.filter-btn.on { background:var(--nav-active); color:var(--text); border-color:transparent; }
.search-input { flex:1; min-width:160px; padding:6px 12px; border-radius:20px; border:1px solid var(--border); background:var(--input-bg); color:var(--text); font-size:12px; outline:none; }
.search-input:focus { border-color:#3b82f6; }

/* Venue directory */
.venue-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; padding:16px 18px; }
.venue-card { background:var(--bg); border:1px solid var(--border); border-radius:10px; padding:14px 16px; transition:box-shadow 0.12s; }
.venue-card:hover { box-shadow:var(--shadow); }
.vc-name { font-size:13px; font-weight:600; margin-bottom:6px; }
.vc-type { font-size:11px; color:var(--text3); margin-bottom:8px; }
.vc-row { display:flex; gap:6px; align-items:flex-start; margin-bottom:4px; font-size:12px; color:var(--text2); }
.vc-icon { flex-shrink:0; color:var(--text4); width:14px; }
.vc-foot { display:flex; gap:6px; align-items:center; margin-top:10px; flex-wrap:wrap; }
.status-badge { font-size:10px; padding:2px 8px; border-radius:8px; font-weight:600; flex-shrink:0; }
.sb-not  { background:rgba(71,85,105,0.2);  color:#94a3b8; }
.sb-cont { background:rgba(37,99,235,0.2);  color:#60a5fa; }
.sb-disc { background:rgba(217,119,6,0.2);  color:#fbbf24; }
.sb-act  { background:rgba(5,150,105,0.2);  color:#34d399; }

/* Rolodex (patients) */
.rolodex-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:14px; padding:16px 18px; }
.patient-card { background:var(--bg); border:1px solid var(--border); border-radius:12px; padding:16px 18px; transition:box-shadow 0.12s; }
.patient-card:hover { box-shadow:var(--shadow); }
.pc-head { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px; }
.pc-name { font-size:14px; font-weight:700; line-height:1.3; }
.pc-stage { font-size:10px; padding:3px 9px; border-radius:10px; font-weight:700; flex-shrink:0; margin-left:8px; }
.stage-active   { background:rgba(124,58,237,0.2); color:#a78bfa; }
.stage-billed   { background:rgba(217,119,6,0.2);  color:#fbbf24; }
.stage-awaiting { background:rgba(37,99,235,0.2);  color:#60a5fa; }
.stage-closed   { background:rgba(5,150,105,0.2);  color:#34d399; }
.pc-row { display:flex; gap:8px; margin-bottom:5px; font-size:12px; }
.pc-lbl { color:var(--text4); width:80px; flex-shrink:0; }
.pc-val { color:var(--text2); flex:1; }
.pc-divider { height:1px; background:var(--border); margin:10px 0; }
"""'''

# Reconstruct: preserve the "# ─── Shared JS" separator comment
result = src[:i] + NEW_CSS + '\n\n# ─── Shared JS' + src[j + len(OLD_END):]
assert '_CSS = """' in result
assert ':root {' in result
assert '[data-theme="light"]' in result
f.write_text(result, encoding="utf-8")
print(f"Batch 1 done. File is {len(result)} chars.")
