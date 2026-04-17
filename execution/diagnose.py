#!/usr/bin/env python3
"""
Reform Workspace Diagnostic Tool
Runs fast, local-first checks to surface root causes without burning context.

Usage:
  python execution/diagnose.py            # all checks
  python execution/diagnose.py --js       # JS syntax + function inventory only
  python execution/diagnose.py --env      # env vars only
  python execution/diagnose.py --live     # live endpoint + Baserow checks only
"""

import os, sys, re, asyncio, time, ast
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent

def _ok(msg):    print(f"  \033[32mPASS\033[0m {msg}")
def _fail(msg):  print(f"  \033[31mFAIL\033[0m {msg}")
def _warn(msg):  print(f"  \033[33mWARN\033[0m {msg}")
def _info(msg):  print(f"  .... {msg}")
def _head(msg):  print(f"\n\033[1m{msg}\033[0m")

# ─────────────────────────────────────────────────────────────────────────────
# 1. JS Syntax Check
# ─────────────────────────────────────────────────────────────────────────────

def _extract_js_blocks(source: str) -> list[tuple[str, str]]:
    """
    Returns list of (label, js_code) tuples extracted from the Python source.

    Only extracts named constants (_FOO_JS = \"\"\") — these are plain (non-f)
    triple-quoted strings whose runtime value is deterministic.  Uses
    ast.literal_eval so Python escape sequences (e.g. \\\\' → \\') are
    processed exactly as the interpreter would, giving esprima the same JS
    the browser receives.

    f-string js blocks are skipped: injected {expr} values can span multiple
    lines and produce too many false positives when naively replaced with null.
    """
    blocks = []
    for m in re.finditer(r'(\b_\w+_JS)\s*=\s*"""(.*?)"""', source, re.DOTALL):
        label = m.group(1)
        raw   = m.group(2)
        try:
            # Process escape sequences just as Python does at import time
            code = ast.literal_eval('"""' + raw + '"""')
        except Exception:
            code = raw  # fallback: use raw bytes
        blocks.append((label, code))
    return blocks


def check_js_syntax(source: str) -> bool:
    _head("[1] JS Syntax Check")

    try:
        import esprima
    except ImportError:
        _warn("esprima not installed — run: pip install esprima")
        return True

    blocks = _extract_js_blocks(source)
    if not blocks:
        _warn("No JS blocks found in source")
        return True

    _info(f"Checking {len(blocks)} JS block(s) via esprima")

    all_ok = True
    for label, code in blocks:
        try:
            esprima.parseScript(code, tolerant=False)
            lines = code.count('\n')
            _ok(f"{label} ({lines} lines)")
        except Exception as e:
            all_ok = False
            # Find the line in context
            line_no = getattr(e, 'lineNumber', None)
            desc    = getattr(e, 'description', str(e))
            _fail(f"{label} — line {line_no}: {desc}")
            if line_no:
                code_lines = code.splitlines()
                start = max(0, line_no - 3)
                end   = min(len(code_lines), line_no + 2)
                for i, ln in enumerate(code_lines[start:end], start=start + 1):
                    marker = ">>>" if i == line_no else "   "
                    color  = "\033[31m" if i == line_no else "\033[90m"
                    print(f"       {color}{marker} {i:4d} | {ln}\033[0m")

    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# 2. JS Function Inventory
# ─────────────────────────────────────────────────────────────────────────────

def check_js_functions(source: str) -> bool:
    _head("[2] JS Function Inventory")

    # For function names we don't need escape processing — scan all JS blocks
    # including inline f-string blocks (raw content is fine for name extraction)
    all_js_source = '\n'.join([
        m.group(1)
        for m in re.finditer(r'\b_\w+_JS\s*=\s*"""(.*?)"""', source, re.DOTALL)
    ] + [
        m.group(1)
        for m in re.finditer(r'\bjs\s*=\s*f?"""(.*?)"""', source, re.DOTALL)
    ])

    blocks = _extract_js_blocks(source)
    defined = set()
    for _, code in blocks:
        for m in re.finditer(r'\bfunction\s+(\w+)\s*\(', code):
            defined.add(m.group(1))
        # Arrow functions assigned to const/let/var: const foo = (...) =>
        for m in re.finditer(r'\b(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(', code):
            defined.add(m.group(1))

    # Also scan raw inline blocks just for names
    for m in re.finditer(r'\bfunction\s+(\w+)\s*\(', all_js_source):
        defined.add(m.group(1))
    for m in re.finditer(r'\b(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(', all_js_source):
        defined.add(m.group(1))

    # Extract function names called directly from HTML event attributes
    # e.g. onclick="openGFRChooser()" → openGFRChooser
    # Match the leading function name only (before the first '(')
    referenced = set()
    for m in re.finditer(r'\bon\w+=["\']([a-zA-Z_]\w*)\s*\(', source):
        referenced.add(m.group(1))

    _info(f"{len(defined)} functions defined, {len(referenced)} referenced in HTML event attrs")

    # Filter browser built-ins, DOM APIs, and keywords that regex can false-positive on
    builtins = {
        'alert', 'confirm', 'fetch', 'JSON', 'parseInt', 'parseFloat',
        'setTimeout', 'clearTimeout', 'setInterval', 'clearInterval',
        'console', 'document', 'window', 'event', 'Promise', 'FormData',
        'Object', 'Array', 'if', 'return', 'this', 'getElementById',
        'querySelector', 'classList', 'addEventListener',
        # Defined as concatenated string literals inside _page() — not in triple-quoted blocks
        'toggleNav', 'toggleTheme',
    }
    missing = referenced - defined - builtins

    if missing:
        for fn in sorted(missing):
            _warn(f"Referenced but not found in JS: {fn}()")
        # Don't fail — these could be browser APIs or loaded elsewhere
        return True
    else:
        _ok("All HTML-referenced functions found in JS blocks")
        return True


# ─────────────────────────────────────────────────────────────────────────────
# 3. f-string JS Escape Check
# ─────────────────────────────────────────────────────────────────────────────

def check_fstring_escapes(source: str) -> bool:
    """
    Scans f-string JS blocks (js = f\"\"\"...\"\"\") for bare \\' sequences.

    In a Python triple-quoted f-string, \\' is processed as an escape sequence
    for a single quote — stripping the backslash.  The JS output sees just ' ,
    which breaks JS string literals that used \\' to embed a quote.

    Correct form: use \\\\' in the Python source so Python produces \\' in the
    JS output (i.e. \\\\' → \\ + ' → \\').

    Real incident: onclick="sbTab(this,\\'info-' written as \\' produced
    onclick="sbTab(this,'info-' which is a JS syntax error.
    """
    _head("[3] f-string JS Escape Check")

    # Match f-string blocks assigned to `js`
    fblocks = []
    for m in re.finditer(r'js\s*=\s*f"""(.*?)"""', source, re.DOTALL):
        start_line = source[:m.start()].count('\n') + 1
        fblocks.append((start_line, m.group(1)))

    if not fblocks:
        _info("No f-string JS blocks found — skipping")
        return True

    _info(f"Scanning {len(fblocks)} f-string JS block(s) for bare \\\\' sequences")

    issues = []
    for block_start, block_content in fblocks:
        for i, line in enumerate(block_content.splitlines(), start=1):
            abs_line = block_start + i
            # Match a \  NOT preceded by another \  and NOT followed by another \
            # i.e. bare \' (bad) but not \\' (ok — that produces \' in JS output)
            if re.search(r"(?<!\\)\\(?!\\)'", line):
                issues.append((abs_line, line.strip()))

    if issues:
        for line_no, line_text in issues:
            _warn(f"Line {line_no}: bare \\' in f-string JS — Python collapses this to ' (use \\\\\\\\' to emit \\' in JS)")
            print(f"         \033[90m{line_text[:100]}\033[0m")
        return False
    else:
        _ok("No bare \\' found in f-string JS blocks")
        return True


# ─────────────────────────────────────────────────────────────────────────────
# 5. Environment Variables
# ─────────────────────────────────────────────────────────────────────────────

def check_env() -> bool:
    _head("[5] Environment Variables")

    env_file = ROOT / ".env"
    if env_file.exists():
        # Load without dotenv dependency
        for line in env_file.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    REQUIRED = {
        "Hub": [
            "BASEROW_URL",
            "BASEROW_API_TOKEN",
            "BUNNY_STORAGE_API_KEY",
            "BUNNY_STORAGE_ZONE",
            "BUNNY_CDN_BASE",
            "BUNNY_ACCOUNT_API_KEY",
        ],
        "Shotstack Worker": [
            "SHOTSTACK_SANDBOX_API_KEY",
            "BUNNY_STORAGE_API_KEY",   # shared
            "N8N_WEBHOOK_URL",
            "N8N_WEBHOOK_TOKEN",
        ],
    }

    OPTIONAL = [
        "SHOTSTACK_PRODUCTION_API_KEY",
        "GOOGLE_MAPS_API_KEY",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "SLACK_WEBHOOK_URL",
        "BUNNY_STORAGE_REGION",
    ]

    all_ok = True
    for group, keys in REQUIRED.items():
        _info(f"--- {group} ---")
        for k in keys:
            v = os.environ.get(k, "")
            if v:
                masked = v[:4] + "****" if len(v) > 4 else "****"
                _ok(f"{k} = {masked}")
            else:
                _fail(f"{k} MISSING")
                all_ok = False

    _info("--- Optional ---")
    for k in OPTIONAL:
        v = os.environ.get(k, "")
        if v:
            _ok(f"{k} set")
        else:
            _warn(f"{k} not set")

    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# 6. Live Endpoint & Baserow Checks
# ─────────────────────────────────────────────────────────────────────────────

async def check_live() -> bool:
    _head("[6] Live Endpoint & Baserow Checks")

    try:
        import httpx
    except ImportError:
        _warn("httpx not installed — skipping live checks (pip install httpx)")
        return True

    all_ok = True
    HUB = "https://reformtechops--outreach-hub-web.modal.run"
    br  = os.environ.get("BASEROW_URL", "")
    bt  = os.environ.get("BASEROW_API_TOKEN", "")

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:

        # Hub ping
        try:
            r = await client.get(f"{HUB}/login")
            if r.status_code == 200:
                _ok(f"Hub /login → {r.status_code} ({r.elapsed.total_seconds():.2f}s)")
            else:
                _fail(f"Hub /login → {r.status_code}")
                all_ok = False
        except Exception as e:
            _fail(f"Hub unreachable: {e}")
            all_ok = False

        # Baserow auth + key tables
        if br and bt:
            # Key tables
            KEY_TABLES = [
                ("T_GOR_VENUES", 790),
                ("T_GOR_ACTS",   791),
            ]
            first = True
            for name, tid in KEY_TABLES:
                try:
                    r = await client.get(
                        f"{br}/api/database/rows/table/{tid}/",
                        params={"size": 1, "user_field_names": "true"},
                        headers={"Authorization": f"Token {bt}"}
                    )
                    if r.status_code == 200:
                        ct = r.json().get("count", "?")
                        prefix = "Baserow auth OK — " if first else ""
                        _ok(f"{prefix}{name} ({tid}): {ct} rows")
                        first = False
                    elif r.status_code == 401:
                        _fail(f"Baserow token invalid (401)")
                        all_ok = False
                        break
                    else:
                        _fail(f"Baserow {name}: {r.status_code}")
                        all_ok = False
                except Exception as e:
                    _fail(f"Baserow {name}: {e}")
                    all_ok = False
        else:
            _warn("Skipping Baserow checks — BASEROW_URL or BASEROW_API_TOKEN not set")

    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    from datetime import datetime
    print(f"\033[1mReform Workspace Diagnostics\033[0m — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    args = set(sys.argv[1:])
    run_js   = not args or '--js'   in args or '--all' in args
    run_env  = not args or '--env'  in args or '--all' in args
    run_live = not args or '--live' in args or '--all' in args

    hub_file = ROOT / "execution" / "modal_outreach_hub.py"
    source = hub_file.read_text(encoding='utf-8') if hub_file.exists() else ""

    results: dict[str, bool] = {}
    t0 = time.time()

    if run_js and source:
        results["js_syntax"]        = check_js_syntax(source)
        results["js_functions"]     = check_js_functions(source)
        results["fstring_escapes"]  = check_fstring_escapes(source)
    elif run_js:
        _fail("modal_outreach_hub.py not found")

    if run_env:
        results["env"] = check_env()

    if run_live:
        results["live"] = await check_live()

    elapsed = time.time() - t0

    print(f"\n{'=' * 60}")
    print(f"\033[1mSummary\033[0m  ({elapsed:.1f}s)")
    any_fail = False
    for k, v in results.items():
        icon = "\033[32mPASS\033[0m" if v else "\033[31mFAIL\033[0m"
        print(f"  {k:<20} {icon}")
        if not v:
            any_fail = True

    if any_fail:
        print("\n\033[31mIssues found — see above for details.\033[0m")
    else:
        print("\n\033[32mAll checks passed.\033[0m")

    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    asyncio.run(main())
