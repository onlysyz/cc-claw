"""CC-Claw Simple Storage Service - In-memory with file persistence"""

import json
import threading
from typing import Optional, Dict, Set
from dataclasses import dataclass, field
from datetime import datetime


class SimpleStorage:
    """Simple in-memory storage with file persistence - NO external dependencies"""

    def __init__(self):
        self._lock = threading.RLock()
        self._device_status: Dict[str, str] = {}  # device_id -> status
        self._user_device: Dict[int, str] = {}  # telegram_id -> device_id
        self._ws_connections: Dict[str, Set[str]] = {}  # device_id -> set of ws_ids
        self._message_queue: Dict[str, list] = {}  # device_id -> messages

    # --- Device Status ---
    def set_device_status(self, device_id: str, status: str):
        """Set device status"""
        with self._lock:
            self._device_status[device_id] = status

    def get_device_status(self, device_id: str) -> Optional[str]:
        """Get device status"""
        return self._device_status.get(device_id)

    def delete_device_status(self, device_id: str):
        """Delete device status"""
        with self._lock:
            self._device_status.pop(device_id, None)

    # --- User-Device Mapping ---
    def set_user_device(self, user_id: int, device_id: str):
        """Map user to device"""
        with self._lock:
            self._user_device[user_id] = device_id

    def get_user_device(self, user_id: int) -> Optional[str]:
        """Get user's device"""
        return self._user_device.get(user_id)

    def delete_user_device(self, user_id: int):
        """Delete user-device mapping"""
        with self._lock:
            self._user_device.pop(user_id, None)

    # --- WebSocket Connections ---
    def add_ws_connection(self, device_id: str, ws_id: str):
        """Add WebSocket connection"""
        with self._lock:
            if device_id not in self._ws_connections:
                self._ws_connections[device_id] = set()
            self._ws_connections[device_id].add(ws_id)

    def remove_ws_connection(self, device_id: str, ws_id: str):
        """Remove WebSocket connection"""
        with self._lock:
            if device_id in self._ws_connections:
                self._ws_connections[device_id].discard(ws_id)
                if not self._ws_connections[device_id]:
                    del self._ws_connections[device_id]

    def get_ws_connections(self, device_id: str) -> Set[str]:
        """Get all WebSocket connections for device"""
        return self._ws_connections.get(device_id, set())

    # --- Message Queue (for pub/sub alternative) ---
    def publish_message(self, device_id: str, message: dict):
        """Store message for device (polled by WebSocket)"""
        with self._lock:
            if device_id not in self._message_queue:
                self._message_queue[device_id] = []
            self._message_queue[device_id].append(message)

    def get_messages(self, device_id: str) -> list:
        """Get and clear messages for device"""
        with self._lock:
            messages = self._message_queue.get(device_id, [])
            self._message_queue[device_id] = []
            return messages


# Global simple storage instance
simple_storage = SimpleStorage()


# Keep backward compatibility
class RedisService:
    """Backward compatibility wrapper - now uses in-memory storage"""

    def __init__(self):
        self._client = simple_storage

    @property
    def client(self):
        """Get storage client"""
        return simple_storage

    # Delegate all methods to simple_storage
    def set_device_status(self, device_id: str, status: str):
        simple_storage.set_device_status(device_id, status)

    def get_device_status(self, device_id: str) -> Optional[str]:
        return simple_storage.get_device_status(device_id)

    def delete_device_status(self, device_id: str):
        simple_storage.delete_device_status(device_id)

    def set_user_device(self, user_id: int, device_id: str):
        simple_storage.set_user_device(user_id, device_id)

    def get_user_device(self, user_id: int) -> Optional[str]:
        return simple_storage.get_user_device(user_id)

    def delete_user_device(self, user_id: int):
        simple_storage.delete_user_device(user_id)

    def add_ws_connection(self, device_id: str, ws_id: str):
        simple_storage.add_ws_connection(device_id, ws_id)

    def remove_ws_connection(self, device_id: str, ws_id: str):
        simple_storage.remove_ws_connection(device_id, ws_id)

    def get_ws_connections(self, device_id: str) -> Set[str]:
        return simple_storage.get_ws_connections(device_id)

    def publish_message(self, device_id: str, message: dict):
        simple_storage.publish_message(device_id, message)


# Global instance
redis_service = RedisService()

# Storage instance
storage = None


def init_storage(data_dir: str = None):
    """Initialize file storage"""
    from .storage import init_storage as _init_storage
    global storage
    storage = _init_storage(data_dir)
    return storage
