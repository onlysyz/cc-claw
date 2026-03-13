"""CC-Claw WebSocket Server"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set, Optional
from dataclasses import dataclass

import websockets
from websockets.server import WebSocketServerProtocol

from ..config import config
from ..services.redis import redis_service
from ..bot import send_message
from ..models.db import SessionLocal
from ..services.pairing import PairingService


logger = logging.getLogger(__name__)


@dataclass
class Client:
    """WebSocket client"""
    websocket: WebSocketServerProtocol
    device_id: str
    user_id: Optional[int] = None


class WebSocketServer:
    """WebSocket server for device communication"""

    def __init__(self):
        self.clients: Dict[str, Set[Client]] = {}  # device_id -> set of clients
        self.server = None

    async def start(self):
        """Start WebSocket server"""
        logger.info(f"Starting WebSocket server on {config.ws_port}...")
        self.server = await websockets.serve(
            self.handle_connection,
            config.host,
            config.ws_port,
            ping_interval=30,
            ping_timeout=10,
        )
        logger.info(f"WebSocket server started on port {config.ws_port}")

    async def stop(self):
        """Stop WebSocket server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        logger.info("WebSocket server stopped")

    async def handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        """Handle new WebSocket connection"""
        client: Optional[Client] = None

        try:
            # Wait for registration message
            try:
                register_msg = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=10
                )
            except asyncio.TimeoutError:
                logger.warning("Client did not register in time")
                return

            # Parse registration message
            try:
                data = json.loads(register_msg)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "type": "error",
                    "code": "INVALID_JSON",
                    "message": "Invalid JSON"
                }))
                return

            if data.get("type") != "register":
                await websocket.send(json.dumps({
                    "type": "error",
                    "code": "INVALID_MESSAGE",
                    "message": "First message must be registration"
                }))
                return

            device_id = data.get("device_id")
            token = data.get("token")

            if not device_id or not token:
                await websocket.send(json.dumps({
                    "type": "error",
                    "code": "MISSING_FIELDS",
                    "message": "device_id and token required"
                }))
                return

            # Verify token
            db = SessionLocal()
            try:
                from ..models.models import DeviceToken, Device
                device_token = db.query(DeviceToken).filter(
                    DeviceToken.token == token,
                    DeviceToken.device_id == device_id,
                ).first()

                if not device_token:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "code": "AUTH_FAILED",
                        "message": "Invalid token"
                    }))
                    return

                if device_token.expires_at < datetime.utcnow():
                    await websocket.send(json.dumps({
                        "type": "error",
                        "code": "TOKEN_EXPIRED",
                        "message": "Token expired"
                    }))
                    return

                device = db.query(Device).filter(Device.id == device_id).first()
                user_id = device.user.telegram_id if device else None

            finally:
                db.close()

            # Create client
            client = Client(
                websocket=websocket,
                device_id=device_id,
                user_id=user_id,
            )

            # Add to clients
            if device_id not in self.clients:
                self.clients[device_id] = set()
            self.clients[device_id].add(client)

            # Update Redis
            redis_service.set_device_status(device_id, "online")

            logger.info(f"Device {device_id} connected")

            # Send registration success
            await websocket.send(json.dumps({
                "type": "registered",
                "device_id": device_id,
            }))

            # Listen for messages
            async for raw_message in websocket:
                await self.handle_message(client, raw_message)

        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error handling connection: {e}")
        finally:
            # Cleanup
            if client:
                self._remove_client(client)

    async def handle_message(self, client: Client, raw_message: str):
        """Handle message from device"""
        try:
            data = json.loads(raw_message)
            msg_type = data.get("type")

            if msg_type == "message":
                # Forward message response to Telegram user
                content = data.get("content", "")
                message_id = data.get("message_id")

                if client.user_id:
                    # Split long messages
                    if len(content) > 4000:
                        chunks = [content[i:i+4000] for i in range(0, len(content), 4000)]
                        for chunk in chunks:
                            await send_message(client.user_id, chunk)
                    else:
                        await send_message(client.user_id, content)

            elif msg_type == "ack":
                # Message acknowledged
                logger.debug(f"Message {data.get('message_id')} acknowledged")

            elif msg_type == "error":
                # Device error
                error_code = data.get("code", "UNKNOWN")
                error_msg = data.get("message", "Unknown error")
                logger.error(f"Device error: {error_code} - {error_msg}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from device: {raw_message}")

    def _remove_client(self, client: Client):
        """Remove client from connections"""
        if client.device_id in self.clients:
            self.clients[client.device_id].discard(client)

            if not self.clients[client.device_id]:
                del self.clients[client.device_id]
                redis_service.delete_device_status(client.device_id)
                logger.info(f"Device {client.device_id} disconnected")

    async def send_to_device(self, device_id: str, message: dict):
        """Send message to device"""
        if device_id not in self.clients:
            logger.warning(f"No connection found for device {device_id}")
            return False

        message_json = json.dumps(message)
        connected = False

        for client in self.clients[device_id]:
            try:
                await client.websocket.send(message_json)
                connected = True
            except Exception as e:
                logger.error(f"Error sending to device {device_id}: {e}")

        return connected


# Global WebSocket server instance
ws_server = WebSocketServer()
