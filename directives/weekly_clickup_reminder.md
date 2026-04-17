# Weekly ClickUp Task Reminder

Sends employees a weekly email AND Google Chat Space message (with @mentions) every Monday at 8am Pacific with their open ClickUp tasks.

## Trigger

- **Schedule:** Monday 8:00 AM Pacific Time
- **Execution:** Modal cron job (`modal_clickup_reminder.py`)

## Inputs

None required - the script pulls all team members from ClickUp automatically.

## Process

1. **Fetch ClickUp Team Members**
   - Get all members from the ClickUp workspace
   - Extract their email addresses

2. **For Each Team Member:**
   - Query ClickUp API for tasks assigned to them within Space `90142723798`
   - Iterates all lists (including inside folders) in the space
   - Filter to tasks that are not closed
   - Sort by due date (soonest first)

3. **Generate & Send Email**
   - Format task list as styled HTML email with task name, due date, status
   - Include clickable links to each task
   - Skip users with no tasks (no empty emails)
   - Send via Gmail API from `noreply@reformchiropractic.com` (service account with domain-wide delegation)

4. **Send Google Chat Messages**
   - Authenticate as Chat App ("Cabinet of Reform") via service account
   - Look up space members by display name to get Google user IDs
   - Send one message per person with proper @mention (triggers notification)
   - Task names are hyperlinked to ClickUp URLs
   - Users not in the space won't get @mentioned (falls back to plain name)

## Output

- Email sent to each employee with tasks (HTML formatted)
- Google Chat Space message per employee with @mention and hyperlinked tasks
- Slack notification summarizing results
- Console log for debugging

## Architecture

**Chat App approach (no domain-wide delegation):**
- Service account configured as a Google Chat App ("Cabinet of Reform")
- App must be added to the target Chat Space
- Authenticates with `chat.bot` scope (no user impersonation)
- @mentions use `<users/{user_id}>` format resolved via `spaces.members.list()`
- Display name matching: ClickUp username matched to Chat displayName (case-insensitive)

## ClickUp API Details

**Endpoints Used:**
- `GET /team` - List teams (workspaces)
- `GET /team/{team_id}` - Get team members
- `GET /space/{space_id}/list` - Get folderless lists
- `GET /space/{space_id}/folder` - Get folders
- `GET /folder/{folder_id}/list` - Get lists in folder
- `GET /list/{list_id}/task?assignees[]={user_id}` - Get tasks per list

**Authentication:**
- Header: `Authorization: {CLICKUP_API_KEY}`

**Rate Limits:**
- 100 requests per minute per token

## Configuration

**Key constants in script:**
- `CLICKUP_SPACE_ID = "90142723798"` - ClickUp space to pull tasks from
- `GOOGLE_CHAT_SPACE_NAME = "spaces/XXXX"` - Production Chat Space ID

## Modal Secrets Required

| Secret Name | Keys | Purpose |
|---|---|---|
| `clickup-api` | `CLICKUP_API_KEY` | ClickUp API access |
| `google-chat-service-account` | `GOOGLE_CHAT_SERVICE_ACCOUNT_JSON` | Chat App bot auth + Gmail send (domain-wide delegation) |

## Google Chat Setup

1. Enable Google Chat API in Google Cloud Console
2. Configure Chat API as an app ("Cabinet of Reform")
3. Under Functionality: check "Join spaces and group conversations"
4. Under Visibility: make available to specific people in the org
5. Add the app to the target Chat Space
6. Service account authenticates as the app (bot), not as a user

## Testing

**Trigger full run (email + chat):**
```
POST https://reformtechops--clickup-reminder-trigger.modal.run
```

**Test email only to one user:**
```
POST https://reformtechops--clickup-reminder-test-single.modal.run
Body: {"email": "user@reformchiropractic.com"}
```

**Test Chat message (filtered):**
```
POST https://reformtechops--clickup-reminder-test-chat.modal.run
Body: {"emails": ["user@reformchiropractic.com"]}
```

**Test Chat custom message:**
```
POST https://reformtechops--clickup-reminder-test-chat.modal.run
Body: {"message": "Hello from the bot!"}
```

**Preview (no sending):**
```
GET https://reformtechops--clickup-reminder-preview.modal.run
```

## Learnings

- Chat API with bot auth does NOT return email in `spaces.members.list()` - only displayName and user ID. Must match by display name.
- `<users/email>` syntax does NOT work for @mentions with bot auth. Must use `<users/{numeric_id}>` format.
- Domain-wide delegation is NOT required. Chat App (bot) auth with `chat.bot` scope is sufficient.
- The Chat App must have "Join spaces and group conversations" enabled in the Chat API configuration or it won't appear when adding apps to a space.
- Hyperlinks in Chat messages use `<url|text>` syntax (like Slack).
- Bunny CDN region note: use `la.storage.bunnycdn.com` for LA region uploads.
- Emails now sent via service account with domain-wide delegation (impersonating `noreply@reformchiropractic.com`), not personal OAuth. Requires: (1) domain-wide delegation enabled on service account in GCP, (2) service account client ID authorized for `https://www.googleapis.com/auth/gmail.send` scope in Google Workspace Admin > Security > API Controls > Domain-wide Delegation, (3) `noreply@reformchiropractic.com` user or alias exists in Google Workspace.
