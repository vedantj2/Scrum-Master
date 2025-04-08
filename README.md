
# 🤖 ScrumMasterBot - AI Scrum Assistant  
![tag : innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

ScrumMasterBot is an AI-powered Slack bot that automates daily standups, tracks task progress, generates Jira issues, and acts like a real Scrum Master. Built using the [uAgents](https://docs.fetch.ai/uagents/) framework and integrated with Slack, MongoDB, Gemini, and Jira, this agent offers a smart assistant experience for agile teams.

---

## 💡 Project Motivation

Daily standups are a core part of agile methodology, but managing them manually can be time-consuming and inconsistent. The motivation behind ScrumMasterBot was to:

- Eliminate repetitive coordination tasks for Scrum Masters  
- Keep teams aligned asynchronously  
- Automatically track task statuses and deadlines  
- Generate insightful summaries  
- Seamlessly integrate with Jira for real-time issue logging  

---

## ⚙️ Features

- 🧠 **Daily Standup Automation**: Collects standup updates from Slack and generates structured summaries
- 📋 **Task Extraction via LLM**: Uses Gemini API to extract task IDs, durations, and descriptions from natural messages
- ✅ **Progress Detection**: Auto-detects task status from messages (e.g., "finished" → ENDED)
- 🧾 **Jira Integration**: Automatically creates and links tasks as Jira issues using Atlassian's API
- 💬 **Interactive Agent**: Responds to Slack mentions with task context, advice, or generated plans
- ⏰ **Deadline Reminders**: Sends reminders before task due dates
- 🔄 **Realistic Agent Behavior**: Emulates a real Scrum Master, provides encouragement, feedback, and structure

---

## 🛠️ Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ScrumMasterBot.git
cd ScrumMasterBot
```

---

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 3. Set Environment Variables

Create a `.env` file in the root directory and add the following:

```env
SLACK_BOT_TOKEN=your-slack-bot-token
SLACK_CHANNEL=your-channel-id
MONGODB_URI=your-mongodb-uri
GEMINI_API_KEY=your-gemini-api-key
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-api-token
JIRA_BASE_URL=https://your-domain.atlassian.net
```

---

### 4. Run the Bot

```bash
python scrum_master.py
```

---

### 5. Slack Bot Setup Guide

#### 🔐 Step 1: Create a Slack App
1. Go to [https://api.slack.com/apps](https://api.slack.com/apps).
2. Click **"Create New App"** → **From scratch**
3. Choose a name and select your Slack workspace

---

#### 🔑 Step 2: Add Bot Token Scopes

In **OAuth & Permissions**, add these scopes under **Bot Token Scopes**:
- `app_mentions:read`
- `channels:history`
- `channels:read`
- `chat:write`
- `users:read`
- `users:read.email`
- `im:write`
- `im:history`

---

#### ⚙️ Step 3: Install to Workspace

- Click **Install App** under **OAuth & Permissions**
- Copy the **Bot User OAuth Token** and place it in your `.env` as `SLACK_BOT_TOKEN`

---

#### 💬 Step 4: Invite Bot to Channel

- Go to your Slack channel (e.g. `#standup-daily`)
- Run:

```bash
/invite @ScrumMasterBot
```

- Set `SLACK_CHANNEL` in your `.env` to the **channel ID**  
  (Can be found in the channel URL or under **channel details** in Slack)

---

## 🧪 Tech Stack

- ⚙️ uAgents (Fetch.ai)
- 💬 Slack SDK
- 🧠 Gemini API (LLM for task extraction, planning, summarization)
- 🗃️ MongoDB (Task state persistence)
- 🧾 Jira REST API (Issue creation)
- 🐍 Python 3.10+

---

## 📹 Demo Video

Coming soon! [📺 Demo Video Link](https://your-demo-video-link.com)

---

## 📂 Repository Structure

```
ScrumMasterBot/
│
├── scrum_master.py         # Main bot logic
├── requirements.txt        # Python dependencies
├── .env                    # Secrets (not checked in)
└── README.md               # You are here :)
```

---

## 🚀 Future Improvements

- Add intent classification for smarter understanding
- Fine-tune summaries using role-based voice
- Integrate with Google Calendar for deadline syncing
- Enable voice/video standups using Whisper + agent streaming

---

## 🧠 Agent Details

- **Name**: `ScrumMasterBot`
- **Address**: Will be printed in logs during startup
- **Registered On**: [Agentverse](https://agentverse.ai/)

---

## 📜 License

MIT License – feel free to fork, use, and contribute!
