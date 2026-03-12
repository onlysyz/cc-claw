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
- 🛠️ **Tools** - Screenshot, file operations, shell commands

## Quick Start

### Server (Cloud)

```bash
# Clone and setup
cp .env.example .env
# Edit .env with your Telegram Bot Token and other configs

# Run with Docker
docker-compose up -d
```

### Client (Local)

```bash
# Install client
pip install cc-claw

# Start pairing
cc-claw pair

# Start daemon
cc-claw start
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/pair` | Start pairing process |
| `/unpair` | Unpair device |
| `/status` | Check connection status |
| `/help` | Help information |

## Tech Stack

- **Server**: Python, Telegram Bot API, WebSocket, Redis, PostgreSQL
- **Client**: Python, WebSocket Client

## License

MIT
