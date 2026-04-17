"""
Modal Webhook Receiver
Receives webhooks from n8n and executes directives via Claude orchestration
"""
import os
import json
import modal
from pathlib import Path

app = modal.App("claude-orchestrator")

# Mount the workspace files
workspace_mount = modal.Mount.from_local_dir(
    ".",
    remote_path="/workspace",
    condition=lambda pth: not any(part.startswith('.') for part in Path(pth).parts if part != '.env')
)

@app.function(
    image=modal.Image.debian_slim().pip_install("anthropic", "requests", "python-dotenv"),
    secrets=[
        modal.Secret.from_name("anthropic-api-key"),
        modal.Secret.from_name("N8N-Secrets")
    ],
    mounts=[workspace_mount],
)
@modal.web_endpoint(method="POST")
async def directive(request_data: dict):
    """
    Execute a directive based on webhook slug

    Expected payload:
    {
        "slug": "webhook-slug",
        "data": {...}  // Data to pass to the directive
    }
    """
    import anthropic

    slug = request_data.get("slug")
    input_data = request_data.get("data", {})

    if not slug:
        return {"error": "Missing 'slug' parameter"}, 400

    # Load webhooks configuration
    webhooks_path = "/workspace/execution/webhooks.json"
    try:
        with open(webhooks_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        return {"error": f"Failed to load webhooks.json: {str(e)}"}, 500

    # Find webhook configuration
    webhook_config = config.get("webhooks", {}).get(slug)
    if not webhook_config:
        return {"error": f"Webhook '{slug}' not found"}, 404

    directive_file = webhook_config.get("directive")
    allowed_tools = webhook_config.get("allowed_tools", [])

    # Load directive
    directive_path = f"/workspace/directives/{directive_file}"
    try:
        with open(directive_path, 'r') as f:
            directive_content = f.read()
    except Exception as e:
        return {"error": f"Failed to load directive '{directive_file}': {str(e)}"}, 500

    # Call Claude to execute the directive
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    prompt = f"""You are executing a webhook-triggered directive.

Directive:
{directive_content}

Input Data:
{json.dumps(input_data, indent=2)}

Available Tools: {', '.join(allowed_tools)}

Execute the directive with the provided input data. Be concise and return structured output."""

    try:
        message = client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        result = message.content[0].text

        return {
            "success": True,
            "slug": slug,
            "directive": directive_file,
            "result": result
        }
    except Exception as e:
        return {"error": f"Claude execution failed: {str(e)}"}, 500


@app.function()
@modal.web_endpoint(method="GET")
async def list_webhooks():
    """List all available webhooks"""
    webhooks_path = "/workspace/execution/webhooks.json"
    try:
        with open(webhooks_path, 'r') as f:
            config = json.load(f)
        return {"webhooks": config.get("webhooks", {})}
    except Exception as e:
        return {"error": str(e)}, 500


@app.function()
@modal.web_endpoint(method="POST")
async def test_endpoint(data: dict):
    """Simple test endpoint to verify n8n connectivity"""
    return {
        "success": True,
        "message": "Modal webhook is working!",
        "received_data": data,
        "timestamp": modal.functions.FunctionCall.current().end_time
    }
