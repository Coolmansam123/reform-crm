---
name: deploy-modal
description: Deploy Python scripts to Modal serverless platform. Use when user wants to deploy to Modal, update Modal workers, or push changes to Modal.
disable-model-invocation: false
allowed-tools: Bash, Read, Glob
argument-hint: [script-path]
---

# Modal Deployment (Windows)

Deploy Python scripts to Modal with Windows Unicode fix applied automatically.

## Windows Unicode Issue

Modal CLI outputs Unicode characters (checkmarks, etc.) that cause `charmap` codec errors on Windows. Always set `PYTHONUTF8=1` before running Modal commands.

## Deployment Steps

1. **Navigate to workspace root first:**
   ```bash
   cd "c:\Users\crazy\Reform Workspace"
   ```

2. **Deploy with Unicode fix (bash syntax):**
   ```bash
   PYTHONUTF8=1 modal deploy $ARGUMENTS
   ```

3. **If deploying multiple scripts**, run them sequentially with the same pattern:
   ```bash
   PYTHONUTF8=1 modal deploy execution/script1.py
   PYTHONUTF8=1 modal deploy execution/script2.py
   ```

## Common Deployment Targets

Modal workers in this workspace:
- `execution/modal_shotstack_worker.py` - Video rendering (includes audio extraction + transcription)
- `execution/modal_webhook.py` - Webhook orchestrator
- `execution/modal_clickup_reminder.py` - ClickUp weekly reminders
- `execution/modal_story_processor.py` - Story automation
- `execution/modal_upload_proxy.py` - Upload proxy
- `execution/modal_description_generator.py` - AI descriptions

## Secret Management

To update Modal secrets:
```bash
PYTHONUTF8=1 modal secret create <secret-name> --force KEY1=value1 KEY2=value2
```

## Verification

After deployment, Modal returns the webhook URL. Verify it's accessible.

## Arguments

If `$ARGUMENTS` is provided, deploy that specific file.
If no arguments, ask which Modal worker(s) to deploy.
