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
    standup_updates.clear()
    send_slack_message(":brain: Good morning team! What did you do yesterday? What are you working on today? Any blockers?")

def fetch_slack_messages():
    response = slack_client.conversations_history(channel=SLACK_CHANNEL, limit=30)
    messages = response.get("messages", [])
    updates = []
    for msg in messages:
        if "user" in msg and "text" in msg and msg["user"] != BOT_USER_ID and msg["ts"] not in seen_message_ts:
            if msg.get("subtype") != "bot_message":
                user_info = slack_client.users_info(user=msg["user"])
                username = user_info["user"]["real_name"]
                updates.append((msg["ts"], username, msg["text"]))
    return updates

@scrum_master.on_interval(period=60.0)
async def fetch_and_store_updates(ctx: Context):
    new_messages = fetch_slack_messages()
    for ts, name, text in new_messages:
        seen_message_ts.add(ts)
        standup_updates.append((name, text))

        prompt = (
            "Extract structured task details from the following message. "
            "Return a JSON list with task_id, description, duration_in_days:\n\n"
            f"{text}"
        )
        result = await call_gemini_api(prompt)

        try:
            tasks = json.loads(re.search(r"\[.*?\]", result, re.DOTALL).group(0))
        except Exception:
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

            if not task_id or not task_text:
                continue

            existing = tasks_collection.find_one({"task_id": task_id})
            if not existing:
                tasks_collection.insert_one({
                    "task_id": task_id,
                    "user": name,
                    "task": task_text,
                    "due": due_date,
                    "progress": "STARTED",
                    "last_updated": datetime.now(timezone.utc)
                })
                send_slack_message(f"✅ Task {task_id} added for {name}.")
            else:
                tasks_collection.update_one(
                    {"task_id": task_id},
                    {"$set": {"progress": "IN PROGRESS", "last_updated": datetime.now(timezone.utc)}}
                )
                send_slack_message(f"🔄 Task {task_id} marked IN PROGRESS for {name}.")

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
    for ts, name, text in messages:
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

    conversation = "\n".join([f"{name}: {text}" for name, text in standup_updates])
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
    standup_updates.clear()
    # Notify users who didn’t submit updates
    all_members = slack_client.conversations_members(channel=SLACK_CHANNEL)["members"]
    submitted_users = {user for user, _ in standup_updates}
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

@scrum_master.on_interval(period=120.0)
async def periodic_summary(ctx: Context):
    await summarize_standup(ctx)

if __name__ == "__main__":
    scrum_master.run()
