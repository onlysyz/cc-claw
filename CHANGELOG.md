# Changelog

All notable changes to CC-Claw will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.0] - 2024-01-15

### Added

#### New Features

- **Persistent Memory Module** (`client/memory.py`)
  - `PersistentMemory` class for long-term context retention
  - `ConversationMemory` class for short-term conversation history
  - Automatic context snapshots before/after task execution
  - Keyword search over memory entries
  - Automatic pruning of old entries (90 days max age)

- **Multi-Agent Collaboration** (`client/collaboration.py`)
  - `MultiAgentCollaboration` manager for coordinating multiple agents
  - Agent roles: Coordinator, Specialist, Worker, Reviewer
  - Task dependency graph (DAG) support
  - Shared knowledge base for inter-agent communication
  - Automatic workflow status tracking and reporting

- **Smart Retry Module** (`client/retry.py`)
  - `SmartRetry` executor with multiple backoff strategies
  - `CircuitBreaker` pattern for failing services
  - Pre-built retry configs: network, API, database, fast
  - Retry statistics and monitoring
  - Decorator support (`@with_retry`)

- **Enhanced Tools Ecosystem** (`client/tools.py`)
  - Added `CodeAnalysisTool` with complexity analysis
  - Added `MonitorTool` with health check capabilities
  - Improved error handling across all tools

#### Improvements

- **Goal Engine** (`client/goal_engine.py`)
  - Better task decomposition prompts with user context
  - Improved JSON parsing for task list extraction
  - Support for task prioritization

- **Token Management**
  - Improved rate limit detection
  - Better backoff calculation
  - Hourly token budget checking

- **Documentation**
  - Complete API documentation
  - SEO-optimized README (English + Chinese)
  - Demo video scripts and social media package

### Bug Fixes

- Fixed task requeue logic on rate limit (daemon.py)
- Fixed race condition in task queue
- Fixed memory leak in long-running daemons

### Documentation

- Comprehensive README with SEO keywords
- API reference documentation
- Multi-agent collaboration guide
- Persistent memory usage guide

## [0.0.1] - 2024-01-01

### Added

- Initial release
- Basic autonomous goal execution
- WebSocket communication with server
- Telegram/Lark bot integration
- Task queue with priority support
- Token budget tracking
- Basic rate limit handling