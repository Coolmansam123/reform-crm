# Reform Workspace

This workspace follows a 3-layer architecture for AI orchestration that separates concerns between intent, decision-making, and execution.

## Architecture Overview

### Layer 1: Directives (What to do)
- **Location**: `directives/`
- **Purpose**: SOPs written in Markdown that define goals, inputs, tools, outputs, and edge cases
- **Examples**: Natural language instructions like you'd give a mid-level employee

### Layer 2: Orchestration (Decision making)
- **Purpose**: AI agent reads directives, calls execution tools in the right order, handles errors, and updates directives
- **Role**: Intelligent routing between intent and execution

### Layer 3: Execution (Doing the work)
- **Location**: `execution/`
- **Purpose**: Deterministic Python scripts that handle API calls, data processing, file operations, and database interactions
- **Benefits**: Reliable, testable, fast execution

## Directory Structure

```
Reform Workspace/
├── directives/          # Markdown SOPs and instructions
│   ├── CLAUDE.md       # Main agent instructions
│   ├── AGENTS.md       # Mirror of CLAUDE.md
│   └── GEMINI.md       # Mirror of CLAUDE.md
├── execution/          # Python scripts (deterministic tools)
├── .tmp/               # Intermediate files (never commit, always regenerated)
├── resources/          # Static resources and assets
├── .env                # Environment variables and API keys (gitignored)
├── credentials.json    # Google OAuth credentials (gitignored)
└── token.json         # Google OAuth tokens (gitignored)
```

## Key Principles

1. **Check for tools first**: Before writing a script, check `execution/` for existing tools
2. **Self-anneal when things break**: Fix errors, update scripts, update directives
3. **Update directives as you learn**: Directives are living documents
4. **Deliverables vs Intermediates**:
   - Deliverables live in cloud services (Google Sheets, Slides)
   - Intermediates live in `.tmp/` and can be deleted/regenerated

## Cloud Webhooks (Modal)

The system supports event-driven execution via Modal webhooks.

**Key files:**
- `execution/webhooks.json` - Webhook slug → directive mapping
- `execution/modal_webhook.py` - Modal app
- `directives/add_webhook.md` - Complete setup guide

**Available tools for webhooks:** `send_email`, `read_sheet`, `update_sheet`

## Getting Started

1. Ensure `.env` contains all necessary API keys
2. Place Google OAuth credentials in `credentials.json`
3. Create directives in `directives/` for new tasks
4. Write execution scripts in `execution/` for deterministic operations
5. All temporary files go in `.tmp/`

## Self-Annealing Loop

When errors occur:
1. Fix the issue
2. Update the tool
3. Test to ensure it works
4. Update directive to include new flow
5. System is now stronger

## Philosophy

Be pragmatic. Be reliable. Self-anneal.
