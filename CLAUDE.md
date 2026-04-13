# CC-Claw Project Guide

## Project Overview

CC-Claw is an autonomous AI working companion for Claude Code CLI. It runs as a daemon, decomposes goals into tasks, and executes them autonomously 24/7.

## Project Structure

```
cc-claw/
├── client/              # Local daemon (main focus)
│   ├── daemon.py        # Main entry point
│   ├── handler.py       # Message handling
│   ├── profile.py       # User profile & goals
│   ├── goal_engine.py   # Goal decomposition
│   ├── task_queue.py   # Priority queue
│   ├── memory.py        # Persistent memory (NEW)
│   ├── collaboration.py # Multi-agent (NEW)
│   ├── retry.py         # Smart retry (NEW)
│   ├── tools.py         # Built-in tools
│   ├── websocket.py     # WebSocket client
│   ├── claude.py        # Claude CLI wrapper
│   ├── config.py        # Configuration
│   └── token_tracker.py # Token tracking
├── server/              # Cloud server (optional)
├── docs/                # Documentation
├── demos/               # Demo materials
└── outreach/            # Outreach materials
```

## Key Modules

### Client Core

- **daemon.py** - Main async daemon loop, autonomous runner
- **handler.py** - Message handling, commands (/pause, /resume, /progress, /goals)
- **goal_engine.py** - Claude-powered goal decomposition
- **task_queue.py** - Priority queue with user_task front-insertion

### New Features (v0.1.0)

- **memory.py** - PersistentMemory + ConversationMemory classes
- **collaboration.py** - MultiAgentCollaboration, AgentInfo, CollaborationTask
- **retry.py** - SmartRetry class with RetryConfig, CircuitBreaker

## Development Commands

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run client
cc-claw daemon

# Run server
python run_server.py
```

## Design Principles

1. **Autonomous First** - Everything runs without user input by default
2. **Token Efficient** - Aggressive rate limit handling, token budgeting
3. **Local Execution** - All code execution happens locally
4. **Resilient** - Exponential backoff, circuit breakers, retry logic

## Common Tasks

### Adding a New Tool

Add to `client/tools.py`:

```python
class MyTool:
    @staticmethod
    def my_operation(param: str) -> str:
        """Description"""
        return f"result: {param}"

TOOLS['mytool'] = MyTool
```

### Adding a New Command

Add handler in `client/handler.py`:

```python
if content.strip() == "/mycommand":
    await self._handle_mycommand(message_id, lark_open_id)
    return
```

Then implement the handler method.

## Architecture Notes

### Async/Await

The daemon is fully async using `asyncio`. Use `async def` and `await` throughout.

### Message Flow

```
Server (Telegram/Lark) → WebSocket → handler.py → daemon.py → claude.py
```

### Rate Limiting

TokenBudget tracks usage and implements exponential backoff:
- Level 1: 1 min wait
- Level 2: 2 min wait
- Level 3: 4 min wait
- etc.

## File Naming

- Python modules: `snake_case.py`
- Classes: `PascalCase`
- Functions/methods: `snake_case()`
- Constants: `SCREAMING_SNAKE_CASE`

## Git Conventions

- Branch: `feature/description` or `fix/description`
- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`)
- PR: Title describes what, body explains why