# Modal-n8n Integration Standard

> Event contract and naming convention for all webhook communication between Modal and n8n.

## Event Contract

Every webhook call to n8n **MUST** send JSON with exactly these top-level keys:

```json
{
  "event": "string (required)",
  "job_id": "string (required)",
  "data": "object (optional but preferred; use {} if empty)"
}
```

### Required Fields

1. **event** (string, required)
   - Describes what happened
   - Follow naming convention below

2. **job_id** (string, required)
   - Unique identifier for this job/task
   - Used for tracking and logging
   - Generate with `uuid.uuid4()` or similar

3. **data** (object, optional but preferred)
   - Contains event-specific payload
   - Use `{}` if no data to send
   - Never omit this field—always include it

## Event Naming Convention

Format: `system.area.action.status`

### Rules
- **All lowercase**
- **Dot-separated** (no underscores, no camelCase)
- **2-4 segments** (system.action or system.area.action or system.area.action.status)
- **Descriptive and consistent**

### Structure
```
system    = service/platform name (bunny, shotstack, clickup, modal, etc.)
area      = functional area (upload, render, task, etc.) [optional]
action    = what happened (completed, failed, started, etc.)
status    = additional state info [optional]
```

### Examples

**Simple events (system.action):**
- `health.ping`
- `system.ready`

**Standard events (system.area.action):**
- `bunny.upload.completed`
- `bunny.upload.failed`
- `shotstack.render.completed`
- `shotstack.render.failed`
- `clickup.task.created`
- `clickup.update.completed`
- `modal.job.started`

**Complex events (system.area.action.status):**
- `bunny.video.upload.success`
- `shotstack.render.status.progress`

## Authentication

### Header-Based Auth (Required)
Always include the authentication header:

```
x-modal-token: <secret>
```

- Secret stored in `.env` as `N8N_WEBHOOK_TOKEN`
- Never send auth via query parameters
- Never include credentials in webhook body

## Request Format

### HTTP Method
- Always use `POST`

### Content-Type
- Always use `application/json`

### Payload Location
- **Always JSON body** (never query params)
- Never use form-encoded data
- Never use multipart

### Example Request

```python
import requests
import uuid
import os

def send_n8n_event(event_name, data=None):
    """Send event to n8n webhook."""

    payload = {
        "event": event_name,
        "job_id": str(uuid.uuid4()),
        "data": data if data is not None else {}
    }

    headers = {
        "Content-Type": "application/json",
        "x-modal-token": os.getenv("N8N_KEY")
    }

    response = requests.post(
        "https://your-n8n-webhook-url.com",
        json=payload,
        headers=headers
    )

    return response

# Usage examples
send_n8n_event("health.ping")
send_n8n_event("bunny.upload.completed", {"video_id": "abc123", "url": "https://..."})
send_n8n_event("shotstack.render.failed", {"error": "timeout", "job_id": "xyz789"})
```

## n8n Webhook Configuration

### Webhook Node Settings
- **Authentication**: Header Auth
- **Header Name**: `x-modal-token`
- **Header Value**: Reference from n8n credentials/environment

### Workflow Structure
1. Webhook trigger receives event
2. Switch node routes based on `event` field
3. Each branch handles specific event type
4. Log job_id for tracking

### Example n8n Switch Cases
```
Case 1: {{ $json.event === "bunny.upload.completed" }}
Case 2: {{ $json.event === "bunny.upload.failed" }}
Case 3: {{ $json.event === "shotstack.render.completed" }}
Default: Log unknown event
```

## Error Handling

### When Modal Calls n8n
- Always wrap in try/catch
- Log the event name and job_id on error
- Never fail silently
- Retry with exponential backoff for network errors

### When n8n Receives Invalid Events
- Check for required fields (event, job_id)
- Validate event naming convention
- Log malformed requests
- Return appropriate HTTP status codes

## Common Events Registry

Maintain consistency across the system by using these standard events:

### Health & System
- `health.ping` - Health check
- `system.ready` - Service initialization complete
- `system.shutdown` - Graceful shutdown initiated

### Bunny CDN
- `bunny.upload.started` - Upload initiated
- `bunny.upload.completed` - Upload successful
- `bunny.upload.failed` - Upload failed

### Shotstack
- `shotstack.render.queued` - Render job queued
- `shotstack.render.started` - Render in progress
- `shotstack.render.completed` - Render successful
- `shotstack.render.failed` - Render failed

### ClickUp
- `clickup.task.created` - New task created
- `clickup.task.updated` - Task modified
- `clickup.update.completed` - Bulk update finished
- `clickup.update.failed` - Bulk update failed

### Modal Jobs
- `modal.job.started` - Modal function started
- `modal.job.completed` - Modal function completed
- `modal.job.failed` - Modal function failed

## Validation Checklist

Before deploying any Modal-n8n integration:

- [ ] Event name follows `system.area.action` convention
- [ ] Event name is all lowercase
- [ ] Payload includes `event`, `job_id`, and `data` fields
- [ ] Authentication uses `x-modal-token` header
- [ ] No credentials in query params or body
- [ ] Payload sent as JSON (not form-encoded)
- [ ] Error handling includes logging job_id
- [ ] n8n webhook configured to handle this event
- [ ] Event added to common registry if reusable

## Self-Annealing Notes

Track learnings here as you discover edge cases:

- n8n has a 30-second timeout for webhook responses
- Batch operations should use a single job_id and send progress events
- Large data payloads (>1MB) should use reference URLs in data field, not inline content
