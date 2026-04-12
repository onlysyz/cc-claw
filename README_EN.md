# CC-Claw

**Your tireless AI working companion — making every token count.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8+-green.svg)](https://www.python.org/)

> **Token is resources. Wasted if unused. CC-Claw makes every token count.**

## What is CC-Claw?

CC-Claw is an **autonomous AI working companion** that transforms your Claude coding plan tokens into continuous progress toward your goals. Unlike a chatbot that waits for your input, CC-Claw is always on — consuming your tokens purposefully, breaking down your goals into tasks, executing them, and generating the next steps.

```
You (Telegram/Lark) → CC-Claw Cloud → Your Device → Claude Code CLI
                               ↑                              ↓
                    Progress Reports ← ─────── Results / New Tasks
```

## Core Philosophy

**"凡事发生皆有利于我"** — Everything that happens benefits me.

CC-Claw learns who you are, understands what you want to achieve, and then works relentlessly to get you there. It doesn't just respond — it acts, iterates, and pushes forward while you live your life.

## Key Features

### 🎯 Goal-Driven
Works toward *your* goals, not just answering questions. Set it once, forget it, let it work.

### ⚡ Autonomous Loop
Task → Execute → Next Task → Repeat. Continuously working until your goal is reached.

### 🏖️ Smart Rest
Stops on 429 (rate limit), checks hourly for token refresh, resumes automatically. No wasted tokens on retries.

### 🔝 Priority Queue
Your new instructions jump to the front of the queue. Urgent? Just send it.

### 🤫 Silent Mode
No periodic check-ins. Reports only when you ask, or when milestones are reached.

### 🔒 Private
All execution happens on your local machine. Your code, your machine, your control.

## How It Works

### 1. Onboarding
CC-Claw asks about your profession, current situation, and goals via Telegram/Lark.

### 2. Goal Setting
Together you define what "better" looks like for you — specific, measurable outcomes.

### 3. Task Decomposition
CC-Claw breaks your goal into actionable tasks using AI.

### 4. Continuous Execution
The autonomous loop executes tasks one by one, generating next steps automatically.

### 5. Smart Throttling
Never wastes tokens on 429 errors. Checks hourly for token refresh, resumes full speed.

## Use Cases

### 🐛 Bug Fixing on Autopilot
```
Goal: "Fix all critical bugs in the auth module"
↓
CC-Claw decomposes → finds related files → analyzes each bug → submits fixes → verifies
```

### 📦 Feature Development
```
Goal: "Implement user profile system"
↓
CC-Claw creates models → writes API endpoints → adds tests → reviews code → iterates
```

### 🚀 DevOps Automation
```
Goal: "Set up CI/CD pipeline"
↓
CC-Claw creates GitHub Actions → configures tests → sets up deployment → monitors
```

### 📚 Learning & Documentation
```
Goal: "Document the entire API"
↓
CC-Claw analyzes routes → writes OpenAPI spec → creates examples → generates guides
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Internet                                 │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Cloud Server                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Telegram    │  │   API       │  │  WebSocket Server       │ │
│  │ Bot / Lark  │  │   Server   │  │  (persistent connection) │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │ WSS
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Your Device (Local)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Gateway     │  │ Goal Engine │  │  Claude Code CLI        │ │
│  │ Client      │  │ Task Queue  │  │  (executes tasks)       │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.8+
- Claude Code CLI installed
- Telegram Bot token (or Lark)

### 1. Server Setup

```bash
git clone https://github.com/onlysyz/cc-claw.git
cd cc-claw
pip install -e .
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN
python run_server.py
```

### 2. Client Setup

```bash
pip install -e .
cc-claw install
```

### 3. First Run — Onboarding

When you first message the bot, CC-Claw will ask:

- What is your profession?
- What is your current situation?
- What is your short-term goal?
- What does "better" look like for you?

These define your **User Profile** and **Goal**, which power the autonomous loop.

## Client CLI Commands

| Command | Description |
|---------|-------------|
| `cc-claw start` | Start the daemon |
| `cc-claw status` | Check connection and goal progress |
| `cc-claw progress` | View completed tasks and token stats |
| `cc-claw pause` | Pause autonomous mode |
| `cc-claw resume` | Resume autonomous mode |
| `cc-claw goals` | List current goals |

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome + onboarding |
| `/progress` | View goal progress and task history |
| `/pause` | Pause autonomous execution |
| `/resume` | Resume autonomous execution |
| `/tasks` | List current task queue |
| `/goals` | Manage goals |
| `/status` | Connection status |
| `/help` | Help |

> **Note**: CC-Claw does NOT send periodic check-ins. It works silently unless you ask.

## Token Budget Management

CC-Claw is designed for coding plans with periodic token refresh:

| Situation | Behavior |
|-----------|----------|
| Normal | Continuous task execution |
| 429 Rate Limit | Stop, wait with exponential backoff |
| Hourly Check | Poll for token usage refresh |
| Tokens Refreshed | Resume full speed |
| Tokens < 10% remaining | Slow down (lower concurrency) |

## Built-in Tools

CC-Claw includes 8 practical tool classes for common tasks:

| Tool | Capabilities |
|------|-------------|
| **FileProcessor** | Read, write, append, search, count lines |
| **DataScraper** | Fetch pages, extract links, emails, IPs |
| **ApiClient** | HTTP calls with optional auth |
| **ProcessManager** | List, kill, check running processes |
| **SystemInfo** | Disk usage, memory, CPU load |
| **GitHelper** | Status, diff, log, branch |
| **DockerHelper** | PS, logs, restart, status |

## Project Structure

```
cc-claw/
├── client/              # Local gateway & execution engine
│   ├── api.py          # Server API client
│   ├── claude.py       # Claude CLI executor
│   ├── config.py       # Configuration
│   ├── daemon.py       # Daemon process
│   ├── handler.py      # Message handler
│   ├── scheduler.py    # Task scheduler
│   ├── websocket.py    # WebSocket manager
│   ├── profile.py      # User profile & goals
│   ├── goal_engine.py  # Goal → Task decomposition
│   ├── task_queue.py   # Priority task queue
│   ├── token_tracker.py # Token usage tracking
│   └── tools.py        # Built-in tools (file, scraper, etc.)
├── server/             # Cloud server
│   ├── api/           # REST API
│   ├── bot/           # Telegram & Lark bots
│   ├── services/      # Storage
│   └── ws/            # WebSocket server
├── .claude/           # Claude Code skills
│   └── skills/
│       └── agentsolvehub/  # Agent Solve Hub integration
├── cli.py              # Client CLI
└── run_server.py       # Server entry point
```

## Tech Stack

- **Server**: Python, Telegram Bot API, Lark API, WebSocket, FastAPI
- **Client**: Python, WebSocket Client, Claude Code CLI

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.

## Star History

If CC-Claw helps you, give it a ⭐

---

**Made with ❤️ for developers who want to make every token count.**
