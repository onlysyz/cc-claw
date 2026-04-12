"""CC-Claw Client Package"""

__version__ = "0.1.0"

from .config import ClientConfig, PairingInfo
from .websocket import WebSocketManager
from .claude import ClaudeExecutor
from .handler import MessageHandler, ToolExecutor
from .daemon import CCClawDaemon
from .api import APIClient
from .scheduler import TaskScheduler, ScheduledTask

__all__ = [
    "ClientConfig",
    "PairingInfo",
    "WebSocketManager",
    "ClaudeExecutor",
    "MessageHandler",
    "ToolExecutor",
    "CCClawDaemon",
    "APIClient",
    "TaskScheduler",
    "ScheduledTask",
]
