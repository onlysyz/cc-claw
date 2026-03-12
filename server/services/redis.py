"""CC-Claw Redis Service"""

import json
from typing import Optional

import redis

from ..config import config


class RedisService:
    """Redis service for pub/sub and caching"""

    def __init__(self):
        self._client: Optional[redis.Redis] = None

    @property
    def client(self) -> redis.Redis:
        """Get Redis client"""
        if self._client is None:
            self._client = redis.from_url(config.redis_url, decode_responses=True)
        return self._client

    # Device Status
    def set_device_status(self, device_id: str, status: str):
        """Set device status"""
        self.client.set(f"device:{device_id}:status", status, ex=3600)

    def get_device_status(self, device_id: str) -> Optional[str]:
        """Get device status"""
        return self.client.get(f"device:{device_id}:status")

    def delete_device_status(self, device_id: str):
        """Delete device status"""
        self.client.delete(f"device:{device_id}:status")

    # User-Device Mapping
    def set_user_device(self, user_id: int, device_id: str):
        """Map user to device"""
        self.client.set(f"user:{user_id}:device", device_id)

    def get_user_device(self, user_id: int) -> Optional[str]:
        """Get user's device"""
        return self.client.get(f"user:{user_id}:device")

    def delete_user_device(self, user_id: int):
        """Delete user-device mapping"""
        self.client.delete(f"user:{user_id}:device")

    # WebSocket Connections
    def add_ws_connection(self, device_id: str, ws_id: str):
        """Add WebSocket connection"""
        self.client.sadd(f"device:{device_id}:ws", ws_id)

    def remove_ws_connection(self, device_id: str, ws_id: str):
        """Remove WebSocket connection"""
        self.client.srem(f"device:{device_id}:ws", ws_id)

    def get_ws_connections(self, device_id: str) -> set:
        """Get all WebSocket connections for device"""
        return self.client.smembers(f"device:{device_id}:ws")

    # Pub/Sub for message routing
    def publish_message(self, device_id: str, message: dict):
        """Publish message to device channel"""
        self.client.publish(f"device:{device_id}:messages", json.dumps(message))

    def subscribe_to_device(self, device_id: str):
        """Subscribe to device messages"""
        return self.client.pubsub()

    # Pairing
    def set_pairing(self, code: str, data: dict, expire_seconds: int = 300):
        """Store pairing data"""
        self.client.setex(f"pairing:{code}", expire_seconds, json.dumps(data))

    def get_pairing(self, code: str) -> Optional[dict]:
        """Get pairing data"""
        data = self.client.get(f"pairing:{code}")
        return json.loads(data) if data else None

    def delete_pairing(self, code: str):
        """Delete pairing data"""
        self.client.delete(f"pairing:{code}")

    # Online Users (for broadcasting)
    def add_online_user(self, user_id: int):
        """Add online user"""
        self.client.sadd("online:users", user_id)

    def remove_online_user(self, user_id: int):
        """Remove online user"""
        self.client.srem("online:users", user_id)

    def get_online_users(self) -> set:
        """Get all online users"""
        return self.client.smembers("online:users")


# Global instance
redis_service = RedisService()
