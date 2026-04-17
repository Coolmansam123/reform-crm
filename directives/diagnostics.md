# Diagnostics — Directive

## What This Is

`execution/diagnose.py` is a fast, local-first diagnostic tool for the Reform workspace. Run it whenever something is broken or after a significant deploy to confirm everything is healthy. It surfaces root causes in seconds instead of burning session context on iterative debugging.

---

## When to Run It

- **Before starting a bug investigation** — run this first, not last
- **After any deploy** — confirm nothing is broken
- **When something "stops working"** — run before reading any code
- **After rotating API keys or updating Modal secrets** — verify env vars propagated

---

## Usage

```bash
cd "c:\Users\crazy\Reform Workspace"

# All checks (default)
python execution/diagnose.py

# JS only (fastest — catches syntax errors and missing function errors)
python execution/diagnose.py --js

# Environment variables only
python execution/diagnose.py --env

# Live endpoint + Baserow connectivity only
python execution/diagnose.py --live
```

---

## What It Checks

### [1] JS Syntax Check
Extracts every JavaScript block from `modal_outreach_hub.py` and runs each through `node --check`. Reports the exact line and column of any syntax error, along with which block it came from.

**Catches:**
- String escaping bugs (e.g., unescaped single quotes inside JS single-quoted strings)
- Unclosed brackets, malformed function bodies
- Any error that would cause `SyntaxError` in the browser and silently prevent all JS from running

**Requires:** Node.js installed and on PATH.

### [2] JS Function Inventory
Lists all functions defined across all JS blocks and cross-references them against function names referenced in HTML `onclick`/`oninput` attributes. Warns on any function called from HTML that isn't defined in the JS.

**Catches:**
- `ReferenceError: X is not defined` class of errors
- Functions removed or renamed without updating HTML

### [3] Environment Variables
Reads `.env` and checks that all required keys are present for both the hub and the Shotstack worker. Masks values (shows first 4 chars only).

**Required for hub:** `BASEROW_URL`, `BASEROW_API_TOKEN`, `BUNNY_STORAGE_API_KEY`, `BUNNY_STORAGE_ZONE`, `BUNNY_CDN_BASE`, `BUNNY_ACCOUNT_API_KEY`

**Required for Shotstack worker:** `SHOTSTACK_SANDBOX_API_KEY`, `BUNNY_STORAGE_API_KEY`, `N8N_WEBHOOK_URL`, `N8N_WEBHOOK_TOKEN`

**Catches:**
- Missing keys that cause silent failures (e.g., Bunny upload silently skipping, n8n callback missing fields)
- Modal secrets not propagated (secret exists but var is missing)

### [4] Live Endpoint & Baserow Checks
- GETs the hub `/login` page and verifies it returns 200
- Authenticates to Baserow with `BASEROW_API_TOKEN` and verifies the token is valid
- Checks row counts on key tables (T_GOR_VENUES 790, T_GOR_ACTS 791) to confirm access

**Catches:**
- Hub not deployed or crashed
- Expired/rotated Baserow token
- Table access permission issues

---

## Adding New Checks

When you add a new feature, update this script:

**New env vars:** Add to the `REQUIRED` dict under the appropriate group in `check_env()`.

**New Baserow tables:** Add to `KEY_TABLES` in `check_live()`.

**New API endpoints:** Add to the `check_live()` function. Pattern: make a request, check status code and response shape.

**New JS files:** The script auto-discovers `_*_JS` constants and `js = [f]"""..."""` blocks, so new JS constants are picked up automatically without changes.

---

## Known Limitations

- JS f-string blocks have `{expr}` substitutions replaced with `null` for syntax checking — this catches structural errors but not value-dependent errors
- Live checks require the hub to be deployed and reachable
- Function inventory only catches functions referenced in HTML `onclick`-style attributes within the Python source — it won't catch calls made from pure JS

---

## Root Cause Map

| Symptom | Most likely check to run | What to look for |
|---------|--------------------------|------------------|
| Button does nothing, no error in console | `--js` | SyntaxError in JS Syntax Check |
| `X is not defined` in console | `--js` | Warning in JS Function Inventory |
| API returns 401 or missing field | `--env` | Missing API key |
| Feature worked, then stopped | `--env` then `--live` | Rotated secret or Baserow token |
| Bunny upload silently fails | `--env` | `BUNNY_STORAGE_API_KEY` missing |
| n8n callback missing field | `--env` | `N8N_WEBHOOK_TOKEN` or Bunny keys missing |
| Hub not loading at all | `--live` | Hub endpoint check |

---

## File Reference

| File | Purpose |
|------|---------|
| `execution/diagnose.py` | The diagnostic script |
| `execution/modal_outreach_hub.py` | Hub source (JS extracted from here) |
| `.env` | Environment variables checked |
