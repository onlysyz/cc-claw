"""CC-Claw Client WebSocket Module"""

import asyncio
import json
import logging
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass

import websockets
from websockets.client import WebSocketClientProtocol

from .config import ClientConfig


logger = logging.getLogger(__name__)


@dataclass
class Message:
    """WebSocket message"""
    type: str
    data: Dict[str, Any]
    message_id: Optional[str] = None


class WebSocketManager:
    """WebSocket connection manager"""

    def __init__(self, config: ClientConfig):
        self.config = config
        self.ws: Optional[WebSocketClientProtocol] = None
        self._running = False
        self._message_handlers: Dict[str, Callable] = {}
        self._reconnect_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """Connect to WebSocket server"""
        try:
            # Build URL with token as query param
            url = self.config.server_ws_url
            if self.config.device_token and self.config.device_id:
                separator = "&" if "?" in url else "?"
                url = f"{url}{separator}token={self.config.device_token}&device_id={self.config.device_id}"

            self.ws = await websockets.connect(
                url,
                ping_interval=30,
                ping_timeout=10,
            )
            logger.info("Connected to WebSocket server")
            self._running = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}", exc_info=True)
            return False

    async def disconnect(self):
        """Disconnect from WebSocket server"""
        self._running = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None

        if self.ws:
            await self.ws.close()
            self.ws = None
        logger.info("Disconnected from WebSocket server")

    async def send(self, message: Dict[str, Any]) -> bool:
        """Send message to server"""
        if not self.ws or not self._running:
            logger.warning("WebSocket not connected")
            return False

        try:
            await self.ws.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def send_message(self, content: str, message_id: str) -> bool:
        """Send a chat message to server (response)"""
        return await self.send({
            "type": "message",
            "message_id": message_id,
            "content": content,
        })

    async def send_ack(self, message_id: str) -> bool:
        """Send message acknowledgment"""
        return await self.send({
            "type": "ack",
            "message_id": message_id,
        })

    async def register(self) -> bool:
        """Register device with server"""
        if not self.config.device_id or not self.config.device_token:
            logger.error("Device ID or token not configured")
            return False

        return await self.send({
            "type": "register",
            "device_id": self.config.device_id,
            "token": self.config.device_token,
        })

    def on(self, message_type: str, handler: Callable[[Message], Any]):
        """Register message handler"""
        self._message_handlers[message_type] = handler

    async def listen(self):
        """Listen for messages from server"""
        if not self.ws:
            logger.error("WebSocket not connected")
            return

        try:
            async for raw_message in self.ws:
                logger.info(f"Received from server: {raw_message[:100]}...")
                try:
                    data = json.loads(raw_message)
                    msg_data = data.get("data", {})
                    message = Message(
                        type=data.get("type", ""),
                        data=msg_data,
                        message_id=msg_data.get("message_id"),
                    )

                    handler = self._message_handlers.get(message.type)
                    if handler:
                        logger.info(f"Calling handler for {message.type}")
                        asyncio.create_task(handler(message))
                    else:
                        logger.debug(f"No handler for message type: {message.type}")

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON: {raw_message}")

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket connection closed: {e}")
        except Exception as e:
            logger.error(f"Error in listen: {e}", exc_info=True)
        finally:
            self._running = False
            if self.config.auto_reconnect:
                await self._schedule_reconnect()

    async def _schedule_reconnect(self):
        """Schedule reconnection"""
        if not self.config.auto_reconnect:
            return

        logger.info(f"Scheduling reconnect in {self.config.reconnect_delay}s")
        await asyncio.sleep(self.config.reconnect_delay)

        if not self._running:
            if await self.connect():
                if await self.register():
                    logger.info("Reconnected successfully")
                    asyncio.create_task(self.listen())

    @property
    def is_connected(self) -> bool:
        """Check if connected"""
        return self._running and self.ws and self.ws.open
