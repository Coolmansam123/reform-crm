# Modal + n8n Integration Setup

This guide shows how to connect Modal and n8n for bidirectional communication.

## Architecture

**Two-way communication:**
1. **Modal → n8n**: Send events/data from Modal to n8n webhooks (using `modal_n8n_gateway.py`)
2. **n8n → Modal**: Trigger Modal functions from n8n (using `modal_webhook.py`)

## Prerequisites

1. Modal account with CLI installed (`pip install modal`)
2. n8n instance (cloud or self-hosted)
3. Anthropic API key

## Setup Steps

### 1. Configure Modal Secrets

Create Modal secrets for n8n connection:

```bash
# Create n8n secrets
modal secret create N8N-Secrets \
  N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/your-webhook-id \
  N8N_WEBHOOK_TOKEN=your-secret-token

# Create Anthropic API key secret
modal secret create anthropic-api-key \
  ANTHROPIC_API_KEY=your-anthropic-api-key
```

### 2. Deploy Modal Apps

```bash
# Deploy the webhook receiver (n8n → Modal)
modal deploy execution/modal_webhook.py

# Deploy the gateway (Modal → n8n)
modal deploy execution/modal_n8n_gateway.py
```

After deployment, Modal will provide URLs like:
- `https://your-username--claude-orchestrator-directive.modal.run`
- `https://your-username--claude-orchestrator-test-endpoint.modal.run`
- `https://your-username--n8n-gateway-notify-n8n.modal.run`

### 3. Test the Connection

Test Modal → n8n:
```bash
modal run execution/modal_n8n_gateway.py
```

Test n8n → Modal with curl:
```bash
curl -X POST https://your-username--claude-orchestrator-test-endpoint.modal.run \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

### 4. Configure n8n Workflows

#### Option A: n8n calls Modal (Webhook Trigger)

1. In n8n, add a **HTTP Request** node
2. Set URL to: `https://your-username--claude-orchestrator-directive.modal.run`
3. Method: `POST`
4. Body:
   ```json
   {
     "slug": "your-webhook-slug",
     "data": {
       "your": "data"
     }
   }
   ```

#### Option B: Modal calls n8n (Webhook Receiver)

1. In n8n, add a **Webhook** node
2. Set HTTP Method: `POST`
3. Set Path: `/your-webhook-path`
4. Copy the webhook URL
5. Update Modal secret with this URL:
   ```bash
   modal secret update N8N-Secrets N8N_WEBHOOK_URL=<n8n-webhook-url>
   ```

## Using the Gateway

### Send events from Modal to n8n

```python
import modal

app = modal.App()
f = modal.Function.lookup("n8n-gateway", "notify_n8n")

# Send notification
result = f.remote(
    event="task.completed",
    data={"status": "success", "result": "data"},
    job_id="my-job-123"
)
```

### Trigger workflows from n8n

POST to Modal webhook endpoint:
```json
{
  "slug": "test",
  "data": {
    "message": "Hello from n8n"
  }
}
```

## Configuration Files

### webhooks.json

Maps webhook slugs to directives:

```json
{
  "webhooks": {
    "your-slug": {
      "directive": "your_directive.md",
      "description": "What this webhook does",
      "allowed_tools": ["send_email", "read_sheet"]
    }
  }
}
```

### Adding New Webhooks

1. Create directive in `directives/your_directive.md`
2. Add entry to `execution/webhooks.json`
3. Redeploy: `modal deploy execution/modal_webhook.py`

## Available Endpoints

After deployment:

- `POST /directive` - Execute a directive via webhook
- `GET /list_webhooks` - List all configured webhooks
- `POST /test_endpoint` - Test connectivity

## Troubleshooting

**Modal deployment fails:**
- Check secrets are created: `modal secret list`
- Verify workspace files are accessible

**n8n can't reach Modal:**
- Verify webhook URL is correct
- Check Modal app is deployed: `modal app list`

**Directive execution fails:**
- Check directive exists in `directives/`
- Verify slug matches `webhooks.json`
- Check Claude API key is valid

## Security Notes

- Always use `x-modal-token` header for authentication
- Store sensitive values in Modal secrets, never in code
- Validate webhook slugs before execution
- Limit allowed_tools per webhook to minimum required
