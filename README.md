# CC-Claw

Your tireless AI partner — continuously working to make you better, not just answering questions.

## What is CC-Claw?

CC-Claw is an **autonomous AI working companion** that turns your Claude coding plan tokens into continuous progress toward your goals. Unlike a chatbot that waits for your input, CC-Claw is always on — consuming your tokens purposefully, breaking down your goals into tasks, executing them, and generating the next step.

> **Token is resources. Wasted if unused. CC-Claw makes every token count.**

## Core Philosophy

**"凡事发生皆有利于我"** — Everything that happens benefits me.

CC-Claw learns who you are, understands what you want to achieve, and then works relentlessly to get you there. It doesn't just respond — it acts, iterates, and pushes forward while you live your life.

## How It Works

```
You (Telegram/Lark) → CC-Claw Cloud → Your Device → Claude Code CLI
                               ↑                              ↓
                    Progress Reports ← ─────── Results / New Tasks
```

1. **Onboarding** — CC-Claw asks about your profession, situation, and goals
2. **Goal Setting** — Together you define what "better" looks like for you
3. **Continuous Work** — CC-Claw breaks goals into tasks, executes, generates next tasks
4. **Smart Throttling** — Never wastes tokens on 429 errors; checks hourly for token refresh

## Features

- 🎯 **Goal-Driven** — Works toward *your* goals, not just answering questions
- ⚡ **Autonomous Loop** — Task → Execute → Next Task → Repeat (until goal reached)
- 🏖️ **Smart Rest** — Stops on 429, checks hourly for token refresh, resumes automatically
- 🔝 **Priority Queue** — Your new instructions jump to the front of the queue
- 🤫 **Silent Mode** — No periodic check-ins. Reports only when you ask, or when milestones are reached
- 🔒 **Private** — All execution happens on your local machine

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

## Usage

### Client CLI

```bash
cc-claw start        # Start the daemon
cc-claw status       # Check connection and goal progress
cc-claw progress     # View completed tasks and token stats
cc-claw pause        # Pause autonomous mode
cc-claw resume       # Resume autonomous mode
cc-claw goals        # List current goals
```

### Bot Commands

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

## Development

### Project Structure

```
cc-claw/
├── client/              # Local gateway & execution engine
│   ├── api.py          # Server API client
│   ├── claude.py       # Claude CLI executor
│   ├── config.py       # Configuration
│   ├── daemon.py       # Daemon process
│   ├── handler.py      # Message handler
│   ├── scheduler.py     # Task scheduler
│   ├── websocket.py    # WebSocket manager
│   ├── profile.py       # User profile & goals
│   ├── goal_engine.py  # Goal → Task decomposition
│   ├── task_queue.py   # Priority task queue
│   └── token_tracker.py # Token usage tracking
├── server/             # Cloud server
│   ├── api/           # REST API
│   ├── bot/           # Telegram & Lark bots
│   ├── services/      # Storage
│   └── ws/            # WebSocket server
├── cli.py              # Client CLI
└── run_server.py       # Server entry point
```

## Tech Stack

- **Server**: Python, Telegram Bot API, Lark API, WebSocket, FastAPI
- **Client**: Python, WebSocket Client, Claude Code CLI

## License

MIT
