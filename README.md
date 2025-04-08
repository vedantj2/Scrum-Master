# ScrumMasterBot 🧠🤖
![tag : innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

## 📌 Overview

ScrumMasterBot is an intelligent AI Scrum Master agent built using the [Fetch.ai uAgents framework](https://github.com/fetchai/uAgents). It lives in your Slack workspace and automates daily standups, tracks team updates, logs tasks, integrates with Jira, and ensures everyone stays on track.

Designed for productivity-focused teams, this agent enhances coordination and reduces manual effort by leveraging AI and agentic automation.

---

## 🎯 Motivation

In fast-paced development teams, daily standups are critical—but they often lack structure, get delayed, or don’t yield actionable insight. ScrumMasterBot automates this process, giving structure to updates, tracking task progress, and reducing the Scrum Master's burden through conversational AI.

---

## 💡 Key Features

- 🔁 **Automated Standup Reminders** – Posts daily prompts in Slack.
- 📝 **Standup Summary** – Uses Gemini to generate structured daily summaries for each team member.
- 🧠 **Natural Language Task Parsing** – Parses task updates from Slack messages and stores them in MongoDB.
- 🚦 **Task Lifecycle Tracking** – Detects task progress (STARTED, IN PROGRESS, ENDED, ABANDONED) based on message context.
- 🧾 **Jira Integration** – Automatically creates tasks in your Jira board from Slack messages.
- 🧠 **Conversational Agent** – Responds to questions about tasks or provides task plans when asked.
- 📬 **Slack DMs for Deadlines** – Sends deadline reminders to users directly.
- 🧵 **Contextual Replies** – Replies with MongoDB task context when tagged.

---

## 🛠️ Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/scrummasterbot.git

