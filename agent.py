import os
import re
import json
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from uagents import Agent, Context, Model
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
import httpx
import asyncio
import sys

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Load environment variables
load_dotenv()

# JIRA setup
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")


# Slack setup
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = "C08JG343TGE"
slack_client = WebClient(token=SLACK_BOT_TOKEN)

# MongoDB setup
mongo_client = MongoClient(os.getenv("MONGODB_URI"))
db = mongo_client.get_database("scrum_maestro")
tasks_collection = db.get_collection("tasks")
print("✅ Connected to MongoDB!")

# Create agent
scrum_master = Agent(name="ScrumMasterAI", seed="YOUR NEW PHRASE", port=8000, endpoint=["http://localhost:8000/submit"])

BOT_USER_ID = None
standup_updates = []
seen_message_ts = set()

class StandupUpdate(Model):
    user: str
    update: str

async def call_gemini_api(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            print(f"❌ Gemini API error {response.status_code}: {response.text}")
            return "Sorry, I couldn’t process that request at the moment."

        return response.json()["candidates"][0]["content"]["parts"][0]["text"]

    except httpx.ReadTimeout:
        print("❌ Gemini API timed out.")
        return "Sorry, the AI is taking too long to respond. Please try again later."

    except Exception as e:
        print("❌ Error during Gemini API call:", str(e))
        return "Something went wrong with processing your request."



def send_slack_message(message):
    try:
        slack_client.chat_postMessage(channel=SLACK_CHANNEL, text=message)
    except SlackApiError as e:
        print(f"Slack error: {e.response['error']}")

@scrum_master.on_event("startup")
async def initialize(ctx: Context):
    global BOT_USER_ID
    auth_info = slack_client.auth_test()
    BOT_USER_ID = auth_info["user_id"]
    ctx.logger.info(f"ScrumMasterBot Slack ID: {BOT_USER_ID}")

@scrum_master.on_interval(period=86400.0)
async def standup_reminder(ctx: Context):
    # standup_updates.clear()
    send_slack_message(":brain: Good morning team! What did you do yesterday? What are you working on today? Any blockers?")

def fetch_slack_messages():
    response = slack_client.conversations_history(channel=SLACK_CHANNEL, limit=30)
    messages = response.get("messages", [])
    updates = []
    for msg in messages:
        if "user" in msg and "text" in msg and msg["user"] != BOT_USER_ID and msg["ts"] not in seen_message_ts:
            if msg.get("subtype") != "bot_message":
                slack_id = msg["user"]
                user_info = slack_client.users_info(user=slack_id)
                username = user_info["user"]["real_name"]
                updates.append((msg["ts"], username, slack_id, msg["text"]))
    return updates


@scrum_master.on_interval(period=60.0)
async def fetch_and_store_updates(ctx: Context):
    print("📥 Fetching new Slack messages...")
    new_messages = fetch_slack_messages()
    
    if not new_messages:
        print("🔍 No new messages found.")
    else:
        print(f"🆕 Found {len(new_messages)} new message(s)")

    for ts, name, slack_id, text in new_messages:
        print(f"\n📨 Processing message from {name}:")
        print(f"🔹 Timestamp: {ts}")
        print(f"🔹 Text: {text}")

        # 🚫 Skip messages that mention the bot directly
        if f"<@{BOT_USER_ID}>" in text:
            print(f"🔕 Skipping Gemini task parsing: message to bot from {name}")
            seen_message_ts.add(ts)
            continue

        seen_message_ts.add(ts)
        standup_updates.append((name, text))
        print(f"✅ Added to standup_updates: ({name}, {text})")


        prompt = (
            "Extract structured task details from the following message. "
            "Return a JSON list with task_id, description, duration_in_days:\n\n"
            f"{text}"
        )

        result = await call_gemini_api(prompt)
        print("🤖 Gemini API response:")
        print(result)
        
        try:
            raw_list = re.search(r"\[.*?\]", result, re.DOTALL)
            if not raw_list:
                raise ValueError("No valid JSON list found in response")
            tasks = json.loads(raw_list.group(0))
            print(f"📦 Extracted {len(tasks)} task(s) from message.")
        except Exception as e:
            print(f"⚠️ Failed to parse Gemini response: {e}")
            continue

        for task in tasks:
            task_id = str(task.get("task_id"))
            task_text = task.get("description")
            duration = task.get("duration_in_days")
            if duration is None:
                duration = 0
            else:
                duration = int(duration)
            due_date = datetime.now(timezone.utc) + timedelta(days=duration)

            if not task_id or not task_text or task_id.lower() == "none":
                print(f"❌ Skipping task for {name}: invalid task_id or description")
                continue

            existing = tasks_collection.find_one({"task_id": task_id})
            if not existing:
                print(f"🆕 Inserting new task {task_id} for {name}")
                tasks_collection.insert_one({
                    "task_id": task_id,
                    "user": name,
                    "slack_id": slack_id,
                    "task": task_text,
                    "due": due_date,
                    "progress": "STARTED",
                    "last_updated": datetime.now(timezone.utc)
                })

                # After inserting into MongoDB
                jira_issue_key = create_jira_issue(
                    summary=task_text,
                    description=f"Task created by {name} via ScrumMasterBot",
                    # assignee_email=f"{slack_id}@yourcompany.com",  # Optional, if you map emails
                    project_key="SCRUMMSTR"
                )
                if jira_issue_key:
                    print(f"📝 Linked Jira issue: {jira_issue_key}")

                send_slack_message(f"✅ Task {task_id} added for {name}.")
            else:
                completion_keywords = ["finished", "completed", "done", "wrapped up"]
                in_progress_keywords = ["in progress", "halfway", "started", "still working", "ongoing"]

                text_lower = text.lower()

                if any(phrase in text_lower for phrase in in_progress_keywords):
                    print(f"🚧 Marking task {task_id} as IN PROGRESS based on user message")
                    tasks_collection.update_one(
                        {"task_id": task_id},
                        {"$set": {
                            "progress": "IN PROGRESS",
                            "last_updated": datetime.now(timezone.utc),
                            "slack_id": slack_id
                        }}
                    )
                    send_slack_message(f"🔄 Task {task_id} marked IN PROGRESS for {name}. Keep it up!")
                elif any(word in text_lower for word in completion_keywords):
                    print(f"🏁 Marking task {task_id} as ENDED based on user message")
                    tasks_collection.update_one(
                        {"task_id": task_id},
                        {"$set": {
                            "progress": "ENDED",
                            "last_updated": datetime.now(timezone.utc),
                            "slack_id": slack_id
                        }}
                    )
                    send_slack_message(f"✅ Task {task_id} marked as *ENDED* for {name}. Great job!")
                else:
                    print(f"♻️ Updating existing task {task_id} to IN PROGRESS")
                    tasks_collection.update_one(
                        {"task_id": task_id},
                        {"$set": {
                            "progress": "IN PROGRESS",
                            "last_updated": datetime.now(timezone.utc),
                            "slack_id": slack_id
                        }}
                    )
                    send_slack_message(f"🔄 Task {task_id} marked IN PROGRESS for {name}.")



@scrum_master.on_interval(period=300.0)  # every hour
async def task_due_reminder(ctx: Context):
    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    for task in tasks_collection.find():
        if task["due"].date() == tomorrow and task["progress"] in {"STARTED", "IN PROGRESS"}:
            user_id = task.get("slack_id")
            if user_id:
                message = f"🔔 Reminder: Task *{task['task_id']}* ('{task['task']}') is due *tomorrow!*"
                try:
                    slack_client.chat_postMessage(channel=user_id, text=message)
                    print(f"📨 Reminder sent to {user_id} for task {task['task_id']}")
                except SlackApiError as e:
                    print(f"⚠️ Could not DM {user_id}: {e.response['error']}")


@scrum_master.on_interval(period=30.0)
async def update_task_statuses(ctx: Context):
    now = datetime.now(timezone.utc)
    for task in tasks_collection.find():
        due = task["due"]
        last_updated = task.get("last_updated")
        if task["progress"] == "IN PROGRESS" and last_updated.date() == due.date():
            tasks_collection.update_one({"task_id": task["task_id"]}, {"$set": {"progress": "ENDED"}})
        elif task["progress"] != "ENDED" and now.date() > due.date():
            tasks_collection.update_one({"task_id": task["task_id"]}, {"$set": {"progress": "ABANDONED"}})

@scrum_master.on_interval(period=30.0)
async def reply_to_mentions(ctx: Context):
    messages = fetch_slack_messages()
    for ts, name, slack_id, text in messages:
        if f"<@{BOT_USER_ID}>" in text:
            cleaned = text.replace(f"<@{BOT_USER_ID}>", "").strip()

            # Try to find task ID in the message
            match = re.search(r"task\s*(\d+)", cleaned, re.IGNORECASE)
            task_context = ""

            if match:
                task_id = match.group(1)
                task = tasks_collection.find_one({"task_id": task_id})
                if task:
                    task_context = (
                        f"\n\nContext from MongoDB:\n"
                        f"- Task ID: {task['task_id']}\n"
                        f"- Description: {task['task']}\n"
                        f"- Due Date: {task['due'].strftime('%Y-%m-%d')}\n"
                        f"- Progress: {task['progress']}\n"
                    )

            prompt = (
                f"You are ScrumMasterBot. Respond only to serious or work-related questions."
                f"{task_context}\n\nMessage from {name}:\n{cleaned}"
            )

            reply = await call_gemini_api(prompt)
            send_slack_message(f"*ScrumMasterBot to {name}*: {reply}")
            break



async def summarize_standup(ctx: Context):
    if not standup_updates:
        send_slack_message("*:clipboard: Daily Standup Summary:*\nNo standup updates received today.")
        return
    from collections import defaultdict

    grouped_updates = defaultdict(list)
    for name, text in standup_updates:
        grouped_updates[name].append(text)

    conversation = "\n".join([f"{name}: {' '.join(messages)}" for name, messages in grouped_updates.items()])
    prompt = (
        "You are ScrumMasterBot, an AI Scrum Master summarizing daily updates.\n"
        "Based on the following standup inputs, write a brief yet descriptive summary per person.\n"
        "For each individual, mention what they accomplished yesterday, what they plan to do today, and any blockers. "
        "Sound like a helpful Scrum Master facilitating a meeting.\n\n"
        f"{conversation}\n\n"
        "Return the summary in a conversational tone but keep it organized per person."
    )

    summary = await call_gemini_api(prompt)
    send_slack_message(f"*:clipboard: Daily Standup Summary:*\n{summary}")
    
    # Notify users who didn’t submit updates
    all_members = slack_client.conversations_members(channel=SLACK_CHANNEL)["members"]
    submitted_users = set(grouped_updates.keys())
    missing_users = []

    for uid in all_members:
        if uid == BOT_USER_ID:
            continue
        user_info = slack_client.users_info(user=uid)
        username = user_info["user"]["real_name"]
        if username not in submitted_users:
            missing_users.append(f"<@{uid}>")

    if missing_users:
        reminder_msg = f"⏰ Friendly reminder to submit your standup updates: {', '.join(missing_users)}"
        send_slack_message(reminder_msg)
    # ✅ Clear data after summary
    standup_updates.clear()
    # seen_message_ts.clear()

startup_time = datetime.now(timezone.utc)

@scrum_master.on_interval(period=90.0)
async def periodic_summary(ctx: Context):
    now = datetime.now(timezone.utc)
    # Wait at least 3 minutes before first summary
    if (now - startup_time).total_seconds() < 60:
        return
    await summarize_standup(ctx)

import requests
from requests.auth import HTTPBasicAuth

def create_jira_issue(summary, description, assignee_email=None, project_key="YOUR_PROJECT_KEY", issue_type="Task"):
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": description
                            }
                        ]
                    }
                ]
            },
            "issuetype": {"name": issue_type}
        }
    }

    # if assignee_email:
    #     payload["fields"]["assignee"] = {"id": get_user_account_id(assignee_email)}

    response = requests.post(url, json=payload, headers=headers, auth=auth)

    if response.status_code == 201:
        issue_key = response.json()["key"]
        print(f"✅ Jira issue {issue_key} created!")
        return issue_key
    else:
        print(f"❌ Failed to create Jira issue: {response.text}")
        return None


if __name__ == "__main__":
    scrum_master.run()
