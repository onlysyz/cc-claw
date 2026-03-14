# CC-Claw

Telegram bot to remotely control Claude Code CLI.

## What is CC-Claw?

CC-Claw is a gateway service that allows you to control your local Claude Code CLI through a Telegram bot. Send messages from your phone via Telegram, and CC-Claw forwards them to your local machine, executes them with Claude Code, and returns the results.

## Architecture

```
Telegram User → Telegram Bot → Cloud Server → Local Gateway → Claude Code CLI
                    ↑                                    ↓
                    └──────────── Response ←─────────────┘
```

## Features

- 🔗 **Simple Pairing** - Connect your device with a 6-digit code
- 🔒 **Secure** - WebSocket with authentication and token-based access
- 💬 **Multi-device** - Support multiple devices per user
- 🛠️ **Full Claude Code** - Execute any Claude Code command remotely
- 🔄 **Session Continuity** - Uses `--continue` flag for conversation context
- ⚡ **Permissions Bypass** - Skip permission prompts for automation

## Prerequisites

### Server
- Python 3.10+
- Telegram Bot Token (get from @BotFather)
- (Optional) Domain with SSL for production

### Client
- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code/initial-setup) installed
- Internet connection to reach your server

## Quick Start

### 1. Server Setup (Cloud/VPS)

#### Option A: Run with Python (Development)

```bash
# Clone and setup
git clone https://github.com/onlysyz/cc-claw.git
cd cc-claw

# Install dependencies
pip install -e .

# Copy and edit environment
cp .env.example .env
# Edit .env with your settings:
# - TELEGRAM_BOT_TOKEN=your_bot_token
# - SERVER_API_URL=https://your-domain.com/api
# - SERVER_WS_URL=wss://your-domain.com/ws

# Start server
python run_server.py
```

#### Option B: Run with Docker (Recommended)

```bash
# Clone and setup
git clone https://github.com/onlysyz/cc-claw.git
cd cc-claw

# Copy and edit environment
cp .env.example .env
# Edit .env with your Telegram Bot Token

# Start with Docker Compose
docker-compose up -d
```

### 2. Client Setup (Local Machine)

#### One-Command Install (Recommended)

```bash
# Install client
pip install -e .

# Run one-command install (setup + pair + start)
cc-claw install
```

This will:
1. Ask for your server URL
2. Check Claude CLI
3. Guide you through pairing
4. Start the daemon

#### Manual Setup

```bash
# Install client
pip install -e .

# Interactive setup wizard
cc-claw setup

# Or manually configure
cc-claw config --set server_api_url=https://your-server.com/api
cc-claw config --set server_ws_url=wss://your-server.com/ws

# Pair with Telegram bot
cc-claw pair
```

During pairing:
1. Open Telegram and send `/pair` to your bot
2. Enter the 6-digit code shown in terminal
3. After pairing, start the daemon:

```bash
# Start the daemon (runs in background)
cc-claw start
```

## Usage

### After Setup

1. Send messages to your Telegram bot
2. Messages are forwarded to your local Claude Code CLI
3. Responses are sent back to Telegram

### Client Commands

```bash
# Check status
cc-claw status

# View configuration
cc-claw config

# Update configuration
cc-claw config --set timeout=600      # Set timeout (seconds)
cc-claw config --set working_dir=~/projects  # Set working directory

# Unpair device
cc-claw unpair
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `server_api_url` | `https://cc-claw.example.com/api` | Server API URL |
| `server_ws_url` | `wss://cc-claw.example.com/ws` | Server WebSocket URL |
| `claude_path` | `claude` | Path to Claude CLI |
| `timeout` | `300` | Command timeout (seconds) |
| `working_dir` | `/tmp` | Working directory for Claude sessions |
| `permission_mode` | `default` | Permission mode: `default`, `bypassPermissions` |

#### Permission Modes

- `default` - Ask for permissions when needed
- `bypassPermissions` - Skip all permission prompts (recommended for automation)

### Server Commands (Telegram)

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/pair` | Start pairing process |
| `/unpair` | Unpair device |
| `/status` | Check connection status |
| `/help` | Help information |

## Development

### Project Structure

```
cc-claw/
├── client/              # Client package
│   ├── api.py          # API client
│   ├── claude.py       # Claude CLI executor
│   ├── config.py       # Configuration
│   ├── daemon.py       # Daemon process
│   ├── handler.py      # Message handler
│   └── websocket.py    # WebSocket manager
├── server/             # Server package
│   ├── api/           # REST API
│   ├── bot/           # Telegram bot
│   ├── services/      # Storage, Redis
│   └── ws/            # WebSocket server
├── cli.py              # Client CLI
└── run_server.py       # Server entry point
```

### Running Server Locally

```bash
# Start server on custom port
python run_server.py --host 0.0.0.0 --port 3000
```

### Running Client Locally

```bash
# Start client
python cli.py start

# Or install and use the command
pip install -e .
cc-claw start
```

## Tech Stack

- **Server**: Python, Telegram Bot API, WebSocket, FastAPI
- **Client**: Python, WebSocket Client, Claude Code CLI

## License

MIT
