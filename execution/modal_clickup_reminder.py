"""
Modal Worker: Weekly ClickUp Task Reminder
Sends employees a weekly email with their open tasks every Monday at 8am Pacific.
Posts to Google Chat Space via Chat App (service account, no domain-wide delegation).

Directive: directives/weekly_clickup_reminder.md
Version: 4 - Chat App (service account as bot) + @mentions via <users/email>
"""
import os
import json
import modal
from datetime import datetime, timedelta
from typing import Optional

app = modal.App("clickup-reminder")

# ClickUp Space ID to filter tasks (from URL: https://app.clickup.com/8406969/v/o/s/90142723798)
CLICKUP_SPACE_ID = "90142723798"

# Google Chat Space
GOOGLE_CHAT_SPACE_NAME = "spaces/AAQA_BV1Fq0"  # Production space

# Image with required dependencies
image = modal.Image.debian_slim().pip_install(
    "requests",
    "google-auth",
    "google-auth-oauthlib",
    "google-api-python-client",
    "python-dotenv",
    "fastapi"
)


TITLE_PREFIXES = {"dr.", "mr.", "ms.", "mrs.", "prof."}


def get_first_name(username: str) -> str:
    """Extract first name from username, skipping titles like Dr., Mr., etc."""
    if not username:
        return "Team Member"
    parts = username.split()
    if len(parts) >= 2 and parts[0].lower() in TITLE_PREFIXES:
        return f"{parts[0]} {parts[1]}"
    return parts[0]


def get_clickup_teams(api_key: str) -> list:
    """Get all ClickUp teams/workspaces"""
    import requests

    response = requests.get(
        "https://api.clickup.com/api/v2/team",
        headers={"Authorization": api_key}
    )
    response.raise_for_status()
    return response.json().get("teams", [])


def get_team_members(api_key: str, team_id: str) -> list:
    """Get all members of a ClickUp team"""
    import requests

    response = requests.get(
        f"https://api.clickup.com/api/v2/team/{team_id}",
        headers={"Authorization": api_key}
    )
    response.raise_for_status()
    team_data = response.json().get("team", {})
    return team_data.get("members", [])


def get_space_lists(api_key: str, space_id: str) -> list:
    """Get all lists in a ClickUp space (including folderless lists)"""
    import requests

    all_lists = []

    # Get folderless lists
    response = requests.get(
        f"https://api.clickup.com/api/v2/space/{space_id}/list",
        headers={"Authorization": api_key}
    )
    response.raise_for_status()
    all_lists.extend(response.json().get("lists", []))

    # Get folders and their lists
    response = requests.get(
        f"https://api.clickup.com/api/v2/space/{space_id}/folder",
        headers={"Authorization": api_key}
    )
    response.raise_for_status()
    folders = response.json().get("folders", [])

    for folder in folders:
        folder_id = folder.get("id")
        response = requests.get(
            f"https://api.clickup.com/api/v2/folder/{folder_id}/list",
            headers={"Authorization": api_key}
        )
        response.raise_for_status()
        all_lists.extend(response.json().get("lists", []))

    return all_lists


def get_user_tasks_in_space(api_key: str, space_id: str, user_id: int) -> list:
    """Get open tasks assigned to a specific user within a specific space"""
    import requests

    all_tasks = []
    lists = get_space_lists(api_key, space_id)

    for lst in lists:
        list_id = lst.get("id")
        params = {
            "assignees[]": user_id,
            "subtasks": "true",
            "include_closed": "false",
            "order_by": "due_date",
            "reverse": "false"
        }

        response = requests.get(
            f"https://api.clickup.com/api/v2/list/{list_id}/task",
            headers={"Authorization": api_key},
            params=params
        )
        response.raise_for_status()
        all_tasks.extend(response.json().get("tasks", []))

    return all_tasks


def format_due_date(due_date_ms: Optional[str], for_html: bool = True) -> str:
    """Format ClickUp due date (milliseconds) to readable string"""
    if not due_date_ms:
        return "No due date"

    try:
        due_date = datetime.fromtimestamp(int(due_date_ms) / 1000)
        today = datetime.now().date()
        due_day = due_date.date()

        if due_day < today:
            if for_html:
                return f"<span style='color: #dc3545;'>OVERDUE - {due_date.strftime('%b %d')}</span>"
            else:
                return f"OVERDUE - {due_date.strftime('%b %d')}"
        elif due_day == today:
            if for_html:
                return f"<span style='color: #ffc107;'>Today</span>"
            else:
                return "TODAY"
        elif due_day == today + timedelta(days=1):
            return "Tomorrow"
        else:
            return due_date.strftime("%b %d, %Y")
    except:
        return "No due date"


def generate_email_html(first_name: str, tasks: list, week_date: str) -> str:
    """Generate HTML email content"""

    if not tasks:
        return None

    task_rows = ""
    for task in tasks:
        name = task.get("name", "Untitled Task")
        due = format_due_date(task.get("due_date"), for_html=True)
        url = task.get("url", "#")
        status = task.get("status", {}).get("status", "to do")

        task_rows += f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #eee;">
                <a href="{url}" style="color: #2563eb; text-decoration: none;">{name}</a>
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">{due}</td>
            <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">
                <span style="background: #e5e7eb; padding: 4px 8px; border-radius: 4px; font-size: 12px;">{status}</span>
            </td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">Your Tasks for the Week</h1>
            <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">{week_date}</p>
        </div>

        <div style="background: #fff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 10px 10px;">
            <p style="margin-top: 0;">Hi {first_name},</p>

            <p>Here are your <strong>{len(tasks)} open task(s)</strong> for this week:</p>

            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <thead>
                    <tr style="background: #f9fafb;">
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb;">Task</th>
                        <th style="padding: 12px; text-align: center; border-bottom: 2px solid #e5e7eb;">Due Date</th>
                        <th style="padding: 12px; text-align: center; border-bottom: 2px solid #e5e7eb;">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {task_rows}
                </tbody>
            </table>

            <div style="text-align: center; margin-top: 30px;">
                <a href="https://app.clickup.com" style="background: #667eea; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; display: inline-block;">View All Tasks in ClickUp</a>
            </div>

            <p style="margin-top: 30px; color: #666;">Have a productive week!</p>

            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

            <p style="color: #999; font-size: 12px; margin: 0;">
                Reform Chiropractic<br>
                This is an automated reminder from your task management system.
            </p>
        </div>
    </body>
    </html>
    """

    return html


NOREPLY_SENDER = "noreply@reformchiropractic.com"


def send_email_gmail(to_email: str, subject: str, html_content: str, service_account_json: str) -> dict:
    """Send email using Gmail API via service account with domain-wide delegation.
    Impersonates NOREPLY_SENDER to send emails.
    Returns {"success": True} or {"error": "..."}
    """
    import base64
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    try:
        creds_data = json.loads(service_account_json)
        credentials = service_account.Credentials.from_service_account_info(
            creds_data,
            scopes=["https://www.googleapis.com/auth/gmail.send"]
        )
        delegated_credentials = credentials.with_subject(NOREPLY_SENDER)

        service = build("gmail", "v1", credentials=delegated_credentials)

        message = MIMEMultipart("alternative")
        message["to"] = to_email
        message["subject"] = subject
        message["from"] = f"Reform Chiropractic <{NOREPLY_SENDER}>"

        html_part = MIMEText(html_content, "html")
        message.attach(html_part)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()

        return {"success": True}
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return {"error": str(e)}


def notify_slack(message: str, webhook_url: Optional[str] = None):
    """Send notification to Slack"""
    import requests

    if not webhook_url:
        webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    if not webhook_url:
        print(f"Slack notification (no webhook): {message}")
        return

    try:
        requests.post(webhook_url, json={"text": message})
    except Exception as e:
        print(f"Slack notification failed: {e}")



def get_chat_service(service_account_json: str):
    """Build and return a Google Chat API service using service account credentials."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_data = json.loads(service_account_json)
    credentials = service_account.Credentials.from_service_account_info(
        creds_data,
        scopes=['https://www.googleapis.com/auth/chat.bot']
    )
    return build('chat', 'v1', credentials=credentials)


def get_space_member_ids(service_account_json: str, space_name: str) -> dict:
    """Get a mapping of displayName (lowercased) -> Google user ID for all human members in a Chat Space.
    The bot must be a member of the space to list members.
    Returns dict like {"daniel cisneros": "users/123456789"}
    Note: Chat API with bot auth does not return email, so we match by display name.
    """
    try:
        service = get_chat_service(service_account_json)
        name_to_id = {}
        page_token = None

        while True:
            result = service.spaces().members().list(
                parent=space_name,
                pageToken=page_token,
                pageSize=100
            ).execute()

            for membership in result.get("memberships", []):
                member_info = membership.get("member", {})
                member_name = member_info.get("name", "")  # e.g. "users/123456789"
                member_type = member_info.get("type", "")
                display_name = member_info.get("displayName", "")

                if member_type == "HUMAN" and member_name and display_name:
                    name_to_id[display_name.lower()] = member_name

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        print(f"Found {len(name_to_id)} members in space: {name_to_id}")
        return name_to_id

    except Exception as e:
        print(f"Failed to list space members: {e}")
        return {}


def send_chat_api_message(service_account_json: str, space_name: str, text: str) -> dict:
    """Send a message to Google Chat using Chat API with service account as a Chat App (bot).
    The service account must be configured as a Chat App and added to the space.
    """
    try:
        service = get_chat_service(service_account_json)

        message_body = {"text": text}

        result = service.spaces().messages().create(
            parent=space_name,
            body=message_body
        ).execute()

        return {"success": True, "message_name": result.get("name")}

    except Exception as e:
        print(f"Failed to send Chat API message: {e}")
        return {"error": str(e)}



def generate_individual_chat_message(email: str, first_name: str, tasks: list, week_date: str, user_id: Optional[str] = None) -> str:
    """Generate a Chat Space message for a single user with @mention.
    user_id should be in format 'users/123456789' for proper @mentions.
    """

    # Use user_id for proper @mention, fall back to name if not available
    if user_id:
        mention = f"<{user_id}>"
    else:
        mention = first_name

    lines = [
        f"*Weekly Task Reminder - {week_date}*",
        "",
        f"{mention} you have {len(tasks)} open task(s):",
        ""
    ]

    for i, task in enumerate(tasks[:10], 1):  # Limit to 10 tasks per person
        name = task.get("name", "Untitled Task")
        due = format_due_date(task.get("due_date"), for_html=False)
        url = task.get("url", "")

        if url:
            lines.append(f"  {i}. <{url}|{name}>")
        else:
            lines.append(f"  {i}. {name}")
        lines.append(f"      Due: {due}")

    if len(tasks) > 10:
        lines.append(f"  ... and {len(tasks) - 10} more tasks")

    lines.append("")
    lines.append("View all tasks: https://app.clickup.com")

    return "\n".join(lines)



@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("clickup-api"),
        modal.Secret.from_name("google-chat-service-account"),
    ],
    schedule=modal.Cron("0 8 * * 1", timezone="America/Los_Angeles")  # Monday 8am Pacific
)
def send_weekly_reminders():
    """Main scheduled function - sends weekly task reminders via email + Chat API with @mentions"""

    clickup_api_key = os.environ.get("CLICKUP_API_KEY")
    service_account_json = os.environ.get("GOOGLE_CHAT_SERVICE_ACCOUNT_JSON")

    if not all([clickup_api_key, service_account_json]):
        notify_slack("❌ ClickUp Reminder: Missing required secrets (clickup-api or service account)")
        return {"error": "Missing required secrets"}

    week_date = datetime.now().strftime("%B %d, %Y")
    results = {"sent_email": [], "skipped": [], "failed": []}
    members_with_tasks = []

    try:
        teams = get_clickup_teams(clickup_api_key)
        if not teams:
            notify_slack("⚠️ ClickUp Reminder: No teams found")
            return {"error": "No teams found"}

        for team in teams:
            team_id = team["id"]
            members = get_team_members(clickup_api_key, team_id)

            for member_data in members:
                member = member_data.get("user", {})
                user_id = member.get("id")
                email = member.get("email")
                username = member.get("username", "Team Member")
                first_name = get_first_name(username)

                if not email:
                    results["skipped"].append(f"{username} (no email)")
                    continue

                # Get user's tasks from the specific space
                tasks = get_user_tasks_in_space(clickup_api_key, CLICKUP_SPACE_ID, user_id)

                if not tasks:
                    results["skipped"].append(f"{username} (no tasks in space)")
                    continue

                members_with_tasks.append({
                    "email": email,
                    "first_name": first_name,
                    "username": username,
                    "tasks": tasks,
                })

                # Generate and send individual email
                html = generate_email_html(first_name, tasks, week_date)
                subject = f"Your Tasks for the Week - {week_date}"

                email_result = send_email_gmail(
                    to_email=email,
                    subject=subject,
                    html_content=html,
                    service_account_json=service_account_json
                )

                if email_result.get("success"):
                    results["sent_email"].append(f"{username} ({len(tasks)} tasks)")
                else:
                    results["failed"].append(f"{username} email: {email_result.get('error', 'unknown')}")

        # Send individual Chat API messages with @mentions (one per person)
        chat_sent = 0
        chat_failed = 0
        if service_account_json and members_with_tasks:
            # Look up space members to get Google user IDs for @mentions (matched by display name)
            name_to_user_id = get_space_member_ids(service_account_json, GOOGLE_CHAT_SPACE_NAME)

            for member in members_with_tasks:
                username_lower = member["username"].lower()
                google_user_id = name_to_user_id.get(username_lower)
                # If no match, try stripping title prefix (e.g. "dr. daniel sanchez" -> "daniel sanchez")
                if not google_user_id:
                    parts = username_lower.split()
                    if len(parts) >= 2 and parts[0] in TITLE_PREFIXES:
                        google_user_id = name_to_user_id.get(" ".join(parts[1:]))

                chat_text = generate_individual_chat_message(
                    email=member["email"],
                    first_name=member["first_name"],
                    tasks=member["tasks"],
                    week_date=week_date,
                    user_id=google_user_id
                )

                chat_result = send_chat_api_message(
                    service_account_json, GOOGLE_CHAT_SPACE_NAME, chat_text
                )
                if chat_result.get("success"):
                    chat_sent += 1
                else:
                    chat_failed += 1
                    results["failed"].append(f"{member['username']} chat: {chat_result.get('error', 'unknown')}")

        # Summary notification
        summary = f"""📋 Weekly ClickUp Reminder Complete
✅ Emails sent: {len(results['sent_email'])}
⏭️ Skipped: {len(results['skipped'])}
❌ Failed: {len(results['failed'])}
💬 Chat API: {chat_sent} messages sent{f', {chat_failed} failed' if chat_failed else ''}"""

        notify_slack(summary)

        return results

    except Exception as e:
        error_msg = f"❌ ClickUp Reminder Error: {str(e)}"
        notify_slack(error_msg)
        return {"error": str(e)}


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("clickup-api"),
        modal.Secret.from_name("google-chat-service-account"),
    ],
)
@modal.fastapi_endpoint(method="POST")
def trigger(data: dict = {}):
    """Manual trigger endpoint for testing"""
    result = send_weekly_reminders.remote()
    return {"triggered": True, "result": result}




if __name__ == "__main__":
    print("Run with: modal serve execution/modal_clickup_reminder.py")
    print("Or deploy: modal deploy execution/modal_clickup_reminder.py")
