"""
Shared CSS and JS template for the Reform Operations Hub.
`_CSS` is injected into every page; `_JS_SHARED` is a format template — call
`.format(br=..., bt=...)` before embedding.
"""

# ─── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
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
body { font-family:system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--text); display:block; min-height:100vh; transition:background 0.2s,color 0.2s; }
a { color:inherit; text-decoration:none; }

/* Top Nav */
.tnav { position:sticky; top:0; z-index:800; background:var(--bg2); border-bottom:1px solid var(--border);
        display:flex; align-items:center; height:48px; padding:0 20px; gap:4px; }
.tnav-logo { font-size:14px; font-weight:700; color:var(--text); margin-right:8px; white-space:nowrap; text-decoration:none; }
.tnav-logo span { font-size:10px; color:var(--text3); font-weight:400; margin-left:4px; }
.tnav-items { display:flex; align-items:center; gap:2px; flex:1; }
.tnav-right { display:flex; align-items:center; gap:8px; margin-left:auto; }
.tnav-btn { padding:5px 11px; border-radius:6px; font-size:13px; color:var(--text2);
            background:none; border:none; cursor:pointer; white-space:nowrap;
            display:flex; align-items:center; gap:3px; height:34px; font-family:inherit;
            text-decoration:none; transition:background 0.12s, color 0.12s; }
.tnav-btn:hover { background:var(--card-hover); color:var(--text); }
.tnav-btn.active { color:var(--text); font-weight:600; border-bottom:2px solid #ea580c; border-radius:0; }
.tnav-menu { position:relative; }
.tnav-menu:hover .tnav-drop { display:block; }
.tnav-drop { display:none; position:absolute; top:calc(100% + 1px); left:0; min-width:200px;
             background:var(--bg2); border:1px solid var(--border); border-radius:10px;
             box-shadow:0 8px 24px rgba(0,0,0,0.35); padding:6px 0; z-index:900; }
.tnav-drop a { display:flex; align-items:center; padding:8px 16px; font-size:13px;
               color:var(--text2); gap:7px; }
.tnav-drop a:hover { background:var(--card-hover); color:var(--text); }
.tnav-drop a.active { background:var(--nav-active); color:var(--text); font-weight:600; }
[data-theme="light"] .tnav-drop a.active { color:#1d4ed8; }
.tnav-sep { height:1px; background:var(--border); margin:5px 0; }
.tnav-grp-lbl { padding:6px 16px 2px; font-size:10px; font-weight:700; color:var(--text4);
                text-transform:uppercase; letter-spacing:0.8px; }
a.tnav-grp-lbl { display:flex; align-items:center; gap:7px; padding:8px 16px 6px;
                 cursor:pointer; text-decoration:none; }
a.tnav-grp-lbl:hover { background:var(--card-hover); color:var(--text); }
a.tnav-grp-lbl.active { background:var(--nav-active); color:var(--text); }
[data-theme="light"] a.tnav-grp-lbl.active { color:#1d4ed8; }
.tnav-theme-btn { background:none; border:none; color:var(--text3); font-size:16px;
                  cursor:pointer; padding:4px 8px; border-radius:6px; font-family:inherit; }
.tnav-theme-btn:hover { background:var(--card-hover); color:var(--text); }
.tnav-user { font-size:12px; color:var(--text3); padding:4px 8px; }
.tnav-signout { font-size:12px; color:var(--text3); padding:5px 10px; border-radius:6px;
                border:1px solid var(--border); }
.tnav-signout:hover { color:var(--text); background:var(--card-hover); }

/* Main */
.main { width:100%; overflow-y:auto; min-width:0; }

/* Gorilla Map Sidebar Tabs */
.sb-tabs { display:flex; border-bottom:1px solid var(--border); background:var(--bg2); }
.sb-tab  { flex:1; padding:10px 6px; font-size:12px; font-weight:600; color:var(--text3);
           text-align:center; cursor:pointer; border-bottom:2px solid transparent;
           transition:color 0.12s, border-color 0.12s; }
.sb-tab:hover { color:var(--text); }
.sb-tab.active { color:#ea580c; border-bottom-color:#ea580c; }
.sb-panel { display:none; padding:14px; }
.sb-panel.active { display:block; }
.sb-section-lbl { font-size:10px; font-weight:700; color:var(--text4);
                   text-transform:uppercase; letter-spacing:0.6px; margin-bottom:5px; }
.sb-status-badge { display:inline-flex; align-items:center; gap:5px; padding:4px 10px;
                   border-radius:6px; font-size:12px; font-weight:600; cursor:pointer;
                   border:1px solid var(--border); background:var(--card); color:var(--text2); }
.sb-status-badge:hover { background:var(--card-hover); }
.sb-inline-select { display:none; width:100%; margin-top:6px; background:var(--input-bg);
                    border:1px solid var(--border); color:var(--text); border-radius:6px;
                    padding:5px 8px; font-size:12px; }
.sb-act-item { padding:7px 0; border-bottom:1px solid rgba(30,58,95,0.3); font-size:12px; }
.sb-act-item:last-child { border-bottom:none; }
.sb-act-type { font-weight:600; color:var(--text); }
.sb-act-meta { color:var(--text3); font-size:11px; margin-top:2px; }
.sb-log-grid { display:grid; gap:6px; margin-top:8px; }
.sb-log-grid select, .sb-log-grid input, .sb-log-grid textarea {
  background:var(--input-bg); border:1px solid var(--border); color:var(--text);
  border-radius:6px; padding:6px 8px; font-size:12px; font-family:inherit; width:100%; outline:none; }
.sb-log-grid textarea { min-height:56px; resize:vertical; }
.sb-log-btn { width:100%; margin-top:6px; padding:8px; background:#3b82f6; color:#fff;
              border:none; border-radius:7px; font-size:13px; font-weight:600; cursor:pointer; }
.sb-log-btn:hover { background:#2563eb; }
.sb-evt-item { padding:8px 0; border-bottom:1px solid rgba(30,58,95,0.3); font-size:12px; }
.sb-evt-item:last-child { border-bottom:none; }

.header { background:var(--hdr-grad); border-bottom:1px solid var(--border); padding:10px 28px; display:flex; align-items:center; justify-content:space-between; }
.header-left h1 { font-size:16px; font-weight:700; color:#fff; }
.header-left .sub { font-size:11px; color:rgba(255,255,255,0.6); margin-top:2px; }
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
.google-btn { display:flex; align-items:center; justify-content:center; gap:10px; width:100%; padding:11px; background:#fff; color:#333; border:1px solid #ddd; border-radius:8px; font-size:14px; font-weight:500; cursor:pointer; text-decoration:none; transition:background 0.12s; }
.google-btn:hover { background:#f5f5f5; }
.login-err { color:#ef4444; font-size:13px; margin-top:14px; text-align:center; }
/* Compose modal */
.compose-ac-list{display:none;position:absolute;top:100%;left:0;right:0;background:#fff;border:1px solid #d1d5db;border-top:none;border-radius:0 0 7px 7px;max-height:200px;overflow-y:auto;z-index:10;box-shadow:0 4px 12px rgba(0,0,0,0.1)}
.compose-ac-list.open{display:block}
.compose-ac-item{padding:8px 12px;cursor:pointer;font-size:13px;display:flex;justify-content:space-between;align-items:center;gap:10px}
.compose-ac-item:hover,.compose-ac-item.sel{background:#eff6ff}
.compose-ac-name{font-weight:600;color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.compose-ac-email{color:#64748b;font-size:11px;white-space:nowrap}
.compose-fab { position:fixed; bottom:28px; right:28px; width:52px; height:52px; border-radius:50%; background:#3b82f6; color:#fff; border:none; font-size:22px; cursor:pointer; display:flex; align-items:center; justify-content:center; box-shadow:0 4px 14px rgba(59,130,246,0.5); z-index:900; transition:background 0.12s; }
.compose-fab:hover { background:#2563eb; }
.compose-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.45); z-index:950; align-items:center; justify-content:center; }
.compose-overlay.open { display:flex; }
.compose-box { background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:0; width:580px; max-width:95vw; display:flex; flex-direction:column; box-shadow:0 20px 60px rgba(0,0,0,0.25); }
.compose-header { display:flex; justify-content:space-between; align-items:center; padding:16px 22px; border-bottom:1px solid #e2e8f0; }
.compose-header h3 { font-size:15px; font-weight:700; color:#1e293b; margin:0; }
.compose-header .compose-close { background:none; border:none; font-size:18px; color:#94a3b8; cursor:pointer; padding:4px; line-height:1; }
.compose-header .compose-close:hover { color:#475569; }
.compose-fields { padding:16px 22px 0; display:flex; flex-direction:column; gap:8px; }
.compose-field-row { display:flex; align-items:center; gap:0; border-bottom:1px solid #f1f5f9; padding-bottom:8px; }
.compose-field-label { font-size:12px; font-weight:600; color:#94a3b8; width:36px; flex-shrink:0; }
.compose-box input { width:100%; padding:6px 0; background:transparent; border:none; color:#1e293b; font-size:13px; outline:none; font-family:inherit; }
.compose-box input::placeholder { color:#94a3b8; }
.compose-ccbcc-toggle { font-size:11px; color:#3b82f6; cursor:pointer; white-space:nowrap; margin-left:auto; }
.compose-ccbcc-toggle:hover { text-decoration:underline; }
.compose-ccbcc { display:none; }
.compose-ccbcc.open { display:flex; flex-direction:column; gap:8px; }
.compose-body-wrap { padding:12px 22px; flex:1; }
.compose-box textarea { width:100%; padding:0; background:transparent; border:none; color:#1e293b; font-size:13px; outline:none; font-family:inherit; min-height:180px; resize:none; line-height:1.6; }
.compose-box textarea::placeholder { color:#94a3b8; }
.compose-sig { padding:0 22px 8px; font-size:11px; color:#94a3b8; line-height:1.5; border-top:1px solid #f1f5f9; padding-top:10px; }
.compose-toolbar { display:flex; align-items:center; gap:8px; padding:12px 22px; border-top:1px solid #e2e8f0; }
.compose-template-sel { padding:6px 10px; border:1px solid #d1d5db; border-radius:6px; font-size:12px; color:#475569; background:#f8fafc; cursor:pointer; outline:none; }
.compose-toolbar .spacer { flex:1; }
.compose-actions { display:flex; gap:8px; align-items:center; }
.compose-actions button { padding:8px 18px; border-radius:7px; font-size:13px; font-weight:600; cursor:pointer; border:none; }
.btn-send { background:#3b82f6; color:#fff; transition:background .12s; }
.btn-send:hover { background:#2563eb; }
.btn-cancel { background:#f1f5f9; color:#64748b; }
.btn-cancel:hover { background:#e2e8f0; }
.compose-status { font-size:12px; min-height:16px; display:flex; align-items:center; gap:6px; }
.compose-undo { background:none; border:none; color:#3b82f6; font-size:12px; font-weight:600; cursor:pointer; text-decoration:underline; }
.btn-cancel:hover { background:rgba(255,255,255,0.12); }
.compose-status { font-size:12px; color:#94a3b8; text-align:right; min-height:16px; }

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
.view-toggle { display:flex; gap:4px; margin-left:auto; flex-shrink:0; }
.view-btn { padding:4px 12px; border-radius:20px; font-size:12px; font-weight:500; border:1px solid var(--border); background:var(--card); color:var(--text2); cursor:pointer; transition:all 0.12s; }
.view-btn.on { background:#3b82f6; color:#fff; border-color:#3b82f6; }
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
.patient-card { background:var(--bg); border:1px solid var(--border); border-radius:12px; padding:16px 18px; transition:box-shadow 0.12s,border-color 0.12s; cursor:pointer; }
.patient-card:hover { box-shadow:var(--shadow); border-color:rgba(37,99,235,0.4); }
.pc-head { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px; }
.pc-name { font-size:14px; font-weight:700; line-height:1.3; }
.pc-stage { font-size:10px; padding:3px 9px; border-radius:10px; font-weight:700; flex-shrink:0; margin-left:8px; }
.stage-active   { background:rgba(124,58,237,0.2); color:#a78bfa; }
.stage-billed   { background:rgba(217,119,6,0.2);  color:#fbbf24; }
.stage-awaiting { background:rgba(37,99,235,0.2);  color:#60a5fa; }
.stage-closed   { background:rgba(5,150,105,0.2);  color:#34d399; }
.pc-row { display:flex; gap:14px; margin-bottom:6px; font-size:12px; }
.pc-lbl { color:var(--text4); width:90px; flex-shrink:0; }
.pc-val { color:var(--text2); flex:1; }
.pc-divider { height:1px; background:var(--border); margin:10px 0; }

/* ── Contact Detail Modal ── */
.cd-overlay {
  display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6);
  z-index:940; align-items:flex-start; justify-content:center;
  overflow-y:auto; padding:40px 16px;
}
.cd-overlay.open { display:flex; }
.cd-modal {
  background:var(--bg2); border:1px solid var(--border); border-radius:14px;
  width:560px; max-width:100%; display:flex; flex-direction:column;
  box-shadow:0 20px 60px rgba(0,0,0,0.5); overflow:hidden; flex-shrink:0;
}
.cd-header {
  display:flex; align-items:flex-start; justify-content:space-between;
  padding:16px 18px 12px; border-bottom:1px solid var(--border);
  background:var(--hdr-grad);
}
.cd-title { font-size:15px; font-weight:700; color:#fff; line-height:1.3; margin-bottom:4px; }
.cd-header-actions { display:flex; gap:6px; align-items:center; flex-shrink:0; margin-left:10px; }
.cd-btn-email {
  background:rgba(255,255,255,0.15); border:1px solid rgba(255,255,255,0.3);
  color:#fff; border-radius:8px; padding:5px 10px; font-size:13px;
  cursor:pointer; transition:background 0.12s; white-space:nowrap; font-family:inherit;
}
.cd-btn-email:hover { background:rgba(255,255,255,0.25); color:#fff; }
.cd-btn-close { background:none; border:none; color:rgba(255,255,255,0.6); font-size:20px; line-height:1; cursor:pointer; padding:2px 4px; }
.cd-btn-close:hover { color:#fff; }
.cd-body { padding:16px 18px 20px; overflow-y:auto; max-height:calc(90vh - 100px); }
.cd-panel { display:none; }
.cd-panel.active { display:block; }
.cd-back-btn {
  display:inline-flex; align-items:center; gap:5px; background:none; border:none;
  color:var(--text3); font-size:12px; cursor:pointer; padding:0 0 12px; font-family:inherit;
}
.cd-back-btn:hover { color:var(--text); }
.tpl-grid { display:flex; flex-direction:column; gap:10px; }
.tpl-card {
  background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 16px;
  transition:border-color 0.12s, background 0.12s;
}
.tpl-card:hover { background:var(--card-hover); border-color:#3b82f6; }
.tpl-card-name { font-size:13px; font-weight:700; margin-bottom:3px; }
.tpl-card-subj { font-size:11px; color:var(--text3); margin-bottom:8px; }
.tpl-card-preview {
  font-size:12px; color:var(--text2); line-height:1.5;
  display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden;
}
.tpl-use-btn {
  margin-top:10px; padding:5px 14px; background:#3b82f6; color:#fff; border:none;
  border-radius:6px; font-size:12px; font-weight:600; cursor:pointer; transition:background 0.12s;
}
.tpl-use-btn:hover { background:#2563eb; }
.venue-card { cursor:pointer; }

/* ── Mobile Hub ──────────────────────────────────────────────────────────────── */
.mobile-wrap { min-height:100vh; display:flex; flex-direction:column; background:var(--bg); }
.mobile-hdr  { padding:14px 18px 10px; background:var(--bg2); border-bottom:1px solid var(--border);
               display:flex; align-items:flex-start; justify-content:space-between; }
.mobile-hdr-title { font-size:16px; font-weight:700; }
.mobile-hdr-sub   { font-size:11px; color:var(--text3); margin-top:2px; }
.mobile-body { flex:1; padding:16px; overflow-y:auto; padding-bottom:80px; }
.mobile-greeting h2  { font-size:20px; font-weight:700; margin-bottom:3px; }
.mobile-greeting .sub { font-size:13px; color:var(--text3); }
.mobile-section-lbl { font-size:10px; font-weight:700; text-transform:uppercase;
                      letter-spacing:0.8px; color:var(--text4); margin:16px 0 8px; }
.mobile-cta-grid { display:flex; flex-direction:column; gap:12px; margin-top:16px; }
.mobile-cta { display:flex; align-items:center; gap:14px; padding:18px 22px;
              border-radius:14px; border:none; cursor:pointer; font-size:16px;
              font-weight:700; color:#fff; text-decoration:none; width:100%; }
.mobile-cta-icon  { font-size:28px; line-height:1; }
.mobile-cta-sub   { font-size:12px; font-weight:400; opacity:.85; margin-top:2px; }
.mobile-cta-orange { background:#ea580c; }
.mobile-cta-blue   { background:#2563eb; }
.mobile-cta-green  { background:#059669; }
.mobile-links { display:flex; gap:8px; flex-wrap:wrap; }
.mobile-link  { padding:7px 14px; border-radius:20px; background:var(--card);
                border:1px solid var(--border); color:var(--text2); font-size:13px;
                text-decoration:none; white-space:nowrap; }
.mobile-link:hover { color:var(--text); background:var(--card-hover); }
/* Mobile theme toggle */
.m-theme-btn { background:none; border:1px solid var(--border); color:var(--text3); font-size:16px;
               cursor:pointer; padding:4px 8px; border-radius:6px; font-family:inherit;
               line-height:1; }
.m-theme-btn:hover { background:var(--card-hover); color:var(--text); }
.mobile-bnav { position:fixed; bottom:0; left:0; right:0; background:var(--bg2);
               border-top:1px solid var(--border); display:flex; height:60px; z-index:800; }
.mobile-bnav-btn { flex:1; display:flex; flex-direction:column; align-items:center;
                   justify-content:center; gap:2px; font-size:10px; color:var(--text3);
                   text-decoration:none; border:none; background:none; cursor:pointer;
                   font-family:inherit; padding:0; }
.mobile-bnav-btn.active { color:#ea580c; }
.mobile-bnav-btn .mbi   { font-size:20px; line-height:1; }
.mobile-stop-card { background:var(--card); border:1px solid var(--border);
                    border-radius:12px; padding:14px 16px; margin-bottom:10px; }
.mobile-stop-card.visited { opacity:.55; }
.mobile-stop-num  { font-size:11px; color:var(--text4); margin-bottom:3px; }
.mobile-stop-name { font-size:15px; font-weight:700; margin-bottom:4px; }
.mobile-stop-addr { font-size:12px; color:var(--text3); margin-bottom:6px; }
.mobile-stop-dist { font-size:11px; color:var(--text2); }
.mobile-stop-actions { display:flex; gap:8px; margin-top:10px; }
.mobile-stop-actions button { flex:1; padding:10px; border-radius:8px; font-size:14px;
                               font-weight:600; cursor:pointer; border:none; }
.mobile-stop-checkin { background:#ea580c; color:#fff; }
.mobile-stop-skip    { background:var(--bg); border:1px solid var(--border) !important;
                        color:var(--text2); }
.mobile-stop-badge { display:inline-flex; align-items:center; padding:2px 8px;
                     border-radius:6px; font-size:10px; font-weight:600; margin-top:4px; }
.msb-pending  { background:rgba(71,85,105,.2);   color:#94a3b8; }
.msb-visited  { background:rgba(5,150,105,.2);   color:#34d399; }
.msb-skipped  { background:rgba(239,68,68,.2);   color:#f87171; }
.mobile-act-item { background:var(--card); border:1px solid var(--border);
                   border-radius:10px; padding:12px 14px; margin-bottom:8px; }
.mobile-act-type { font-size:10px; font-weight:700; padding:2px 8px; border-radius:6px;
                   background:rgba(234,88,12,.15); color:#fb923c; margin-bottom:6px;
                   display:inline-block; }
.mobile-act-biz  { font-size:14px; font-weight:600; margin-bottom:3px; }
.mobile-act-meta { font-size:12px; color:var(--text3); }
/* Geo button */
.geo-btn { display:inline-flex; align-items:center; gap:5px; margin-top:5px; padding:5px 10px;
           background:rgba(37,99,235,.12); border:1px solid rgba(37,99,235,.3); color:#60a5fa;
           border-radius:6px; font-size:12px; cursor:pointer; font-family:inherit; }
.geo-btn:hover { background:rgba(37,99,235,.22); }
/* Responsive: stack GFR 2-col fields on small screens */
/* Hamburger menu (desktop pages on small screens) */
.tnav-hamburger { display:none; background:none; border:none; color:var(--text); font-size:22px;
                   cursor:pointer; padding:6px 8px; line-height:1; font-family:inherit; }
.tnav-drawer-backdrop { display:none; position:fixed; inset:0; background:rgba(0,0,0,.5); z-index:899; }
.tnav-drawer-backdrop.open { display:block; }
.tnav-drawer { position:fixed; top:0; right:0; bottom:0; width:280px; max-width:85vw;
               background:var(--bg2); border-left:1px solid var(--border); z-index:900;
               transform:translateX(100%); transition:transform .25s ease; overflow-y:auto;
               padding:16px 0; }
.tnav-drawer.open { transform:translateX(0); }
.tnav-drawer-hdr { display:flex; justify-content:space-between; align-items:center;
                    padding:0 16px 12px; border-bottom:1px solid var(--border); margin-bottom:8px; }
.tnav-drawer-hdr .tnav-logo { margin:0; }
.tnav-drawer-close { background:none; border:none; color:var(--text2); font-size:22px;
                      cursor:pointer; padding:4px 8px; font-family:inherit; }
.tnav-drawer a { display:block; padding:10px 20px; font-size:14px; color:var(--text2);
                  text-decoration:none; }
.tnav-drawer a:hover { background:var(--card-hover); color:var(--text); }
.tnav-drawer a.active { color:var(--text); font-weight:600; background:var(--nav-active); }
.tnav-drawer .tnav-sep { height:1px; background:var(--border); margin:6px 16px; }
.tnav-drawer .tnav-grp-lbl { padding:10px 20px 4px; font-size:10px; font-weight:700;
                              color:var(--text4); text-transform:uppercase; letter-spacing:.6px; }
.tnav-drawer a.tnav-grp-lbl { padding:12px 20px 8px; cursor:pointer; text-decoration:none; }
.tnav-drawer a.tnav-grp-lbl:hover { background:var(--card-hover); color:var(--text); }
.tnav-drawer a.tnav-grp-lbl.active { color:var(--text); background:var(--nav-active); }
.tnav-drawer .drawer-mobile-link { background:rgba(234,88,12,.08); color:#ea580c !important;
                                    font-weight:600; margin:8px 16px; border-radius:8px;
                                    text-align:center; padding:12px; }

@media (max-width:768px) {
  .gfr-two { grid-template-columns:1fr !important; }
  .gfr-grid { grid-template-columns:1fr !important; }
  .gfr-input,.gfr-select,.gfr-textarea { font-size:16px !important; }
  .gfr-btn-cancel,.gfr-btn-submit { min-height:44px; font-size:15px !important; padding:10px 20px; }
  .gfr-form-body { max-height:82vh; }
  .tnav-items,.tnav-right { display:none; }
  .tnav-hamburger { display:block; }
  .tnav { justify-content:space-between; }
  .tnav-logo { margin:0; }
}
/* ── Mobile venue bottom sheet ─────────────────────────────────────────────── */
.m-sheet-backdrop {
  display:none; position:fixed; inset:0;
  background:rgba(0,0,0,.55); z-index:850;
}
.m-sheet-backdrop.open { display:block; }
.m-sheet {
  position:fixed; bottom:0; left:0; right:0; height:82vh;
  background:var(--bg2); border-radius:20px 20px 0 0;
  transform:translateY(100%); transition:transform .3s ease;
  overflow-y:auto; z-index:900; padding-bottom:80px;
}
.m-sheet.open { transform:translateY(0); }
.m-sheet-handle {
  width:40px; height:4px; background:var(--border);
  border-radius:2px; margin:10px auto 2px; cursor:pointer;
}
.m-sheet-sec { padding:12px 16px; border-bottom:1px solid var(--border); }
.m-sheet-lbl {
  font-size:10px; font-weight:700; color:var(--text4);
  text-transform:uppercase; letter-spacing:.04em; margin-bottom:6px;
}
/* Map page — map fills viewport above bottom nav */
.mobile-wrap.map-mode { background:transparent; min-height:0; }
.m-map-wrap { position:fixed; top:0; left:0; right:0; bottom:60px; z-index:100; height:calc(100vh - 60px); width:100%; }
.m-map-filters {
  position:fixed; top:10px; left:10px; right:10px;
  z-index:110; display:flex; gap:6px; flex-wrap:wrap;
}
.m-map-filter-btn {
  padding:6px 14px; border-radius:20px; font-size:12px; font-weight:600;
  border:none; cursor:pointer; background:var(--bg2); color:var(--text1);
  box-shadow:0 1px 4px rgba(0,0,0,.4);
}
.m-map-filter-btn.on { background:#ea580c; color:#fff; }
/* Mobile sheet tabs */
.m-tabs { display:flex; border-bottom:1px solid var(--border); background:var(--bg2); position:sticky; top:0; z-index:5; }
.m-tab { flex:1; padding:11px 4px; font-size:12px; font-weight:600; color:var(--text3); text-align:center; cursor:pointer; border-bottom:2px solid transparent; }
.m-tab.active { color:#ea580c; border-bottom-color:#ea580c; }
.m-panel { display:none; }
.m-panel.active { display:block; }
"""

# ─── Shared JS (template — call .format(br=..., bt=...) before use) ─────────────
_JS_SHARED = """
const BR = '{br}';
const BT = '{bt}';

async function fetchAll(tid, _attempt) {{
  if (window.__OFFLINE_FETCH) return window.__OFFLINE_FETCH(tid);
  var attempt = _attempt || 0;
  try {{
    const r = await fetch('/api/data/' + tid);
    if (!r.ok) {{
      if (attempt < 2) {{
        await new Promise(ok => setTimeout(ok, 1000 * (attempt + 1)));
        return fetchAll(tid, attempt + 1);
      }}
      return [];
    }}
    return await r.json();
  }} catch(e) {{
    if (attempt < 2) {{
      await new Promise(ok => setTimeout(ok, 1000 * (attempt + 1)));
      return fetchAll(tid, attempt + 1);
    }}
    return [];
  }}
}}

function sv(f) {{
  if (!f) return '';
  if (typeof f === 'object' && f.value !== undefined) return f.value;
  return String(f);
}}

function daysUntil(ds) {{
  if (!ds) return null;
  return Math.round(
    (new Date(ds + 'T00:00:00').setHours(0,0,0,0) - new Date().setHours(0,0,0,0)) / 86400000
  );
}}

function fmt(ds) {{
  if (!ds) return '';
  return new Date(ds + 'T00:00:00').toLocaleDateString('en-US', {{month:'short', day:'numeric'}});
}}

function esc(s) {{
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

let _lastRefresh = '';
function stampRefresh() {{
  _lastRefresh = new Date().toLocaleTimeString('en-US', {{hour:'numeric',minute:'2-digit'}});
  const el = document.getElementById('refresh-stamp');
  if (el) el.textContent = 'Updated ' + _lastRefresh;
}}
"""
