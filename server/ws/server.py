"""CC-Claw WebSocket Server"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import websockets
from websockets.server import WebSocketServerProtocol

from ..config import config
from ..services.storage import init_storage
from ..services.redis import simple_storage


logger = logging.getLogger(__name__)


@dataclass
class Client:
    """WebSocket client"""
    websocket: WebSocketServerProtocol
    device_id: str
    user_id: Optional[int] = None

    def __hash__(self):
        return hash(self.device_id)


class WebSocketServer:
    """WebSocket server for device communication"""

    def __init__(self):
        self.clients: Dict[str, Set[Client]] = {}  # device_id -> set of clients
        self.server = None

    async def start(self):
        """Start WebSocket server"""
        # Initialize storage
        init_storage()

        logger.info(f"Starting WebSocket server on {config.host}:{config.ws_port}...")
        self.server = await websockets.serve(
            self.handle_connection,
            config.host,
            config.ws_port,
            ping_interval=30,
            ping_timeout=10,
        )
        logger.info(f"WebSocket server started on {config.host}:{config.ws_port}")
        logger.info(f"Server object: {self.server}")

    async def stop(self):
        """Stop WebSocket server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        logger.info("WebSocket server stopped")

    async def handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        """Handle new WebSocket connection"""
        logger.info(f"New connection from {websocket.remote_address}, path: {path}")
        client: Optional[Client] = None

        try:
            # Try to get token and device_id from query string first
            query = parse_qs(urlparse(path).query)
            query_token = query.get("token", [None])[0]
            query_device_id = query.get("device_id", [None])[0]

            # Wait for registration message
            try:
                register_msg = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=10
                )
                logger.info(f"Received registration message: {register_msg[:200]}...")
            except asyncio.TimeoutError:
                logger.warning("Client did not register in time")
                return

            # Parse registration message
            try:
                data = json.loads(register_msg)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON: {register_msg}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "code": "INVALID_JSON",
                    "message": "Invalid JSON"
                }))
                return

            if data.get("type") != "register":
                logger.error(f"Invalid message type: {data.get('type')}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "code": "INVALID_MESSAGE",
                    "message": "First message must be registration"
                }))
                return

            # Use query string params or message params
            device_id = query_device_id or data.get("device_id")
            token = query_token or data.get("token")

            logger.info(f"device_id={device_id}, token={token}")

            if not device_id or not token:
                await websocket.send(json.dumps({
                    "type": "error",
                    "code": "MISSING_FIELDS",
                    "message": "device_id and token required"
                }))
                return

            # Verify token using storage
            from ..services.storage import storage
            token_data = storage.verify_token(token)

            logger.info(f"Token verification result: {token_data}")

            if not token_data:
                await websocket.send(json.dumps({
                    "type": "error",
                    "code": "AUTH_FAILED",
                    "message": "Invalid token"
                }))
                return

            if token_data.get("device_id") != device_id:
                await websocket.send(json.dumps({
                    "type": "error",
                    "code": "AUTH_FAILED",
                    "message": "Token does not match device"
                }))
                return

            # Get device and user info
            device = storage.get_device(device_id)
            user_id = None
            if device:
                user = storage.get_user_by_id(device.get("user_id"))
                if user:
                    user_id = int(user["telegram_id"])

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

            # Update device status
            simple_storage.set_device_status(device_id, "online")
            storage.update_device_status(device_id, "online")

            logger.info(f"Device {device_id} connected")

            # Send registration success
            await websocket.send(json.dumps({
                "type": "registered",
                "device_id": device_id,
            }))

            # Start message polling task for this client
            message_task = asyncio.create_task(self.poll_messages(client))

            # Listen for messages from client
            try:
                async for raw_message in websocket:
                    logger.info(f"Received raw message from client: {raw_message[:100]}...")
                    await self.handle_message(client, raw_message)
            finally:
                message_task.cancel()

        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error handling connection: {e}", exc_info=True)
        finally:
            # Cleanup
            if client:
                self._remove_client(client)

    async def poll_messages(self, client: Client):
        """Poll for messages from Telegram and send to client"""
        logger.info(f"Started polling messages for device {client.device_id}")
        while True:
            try:
                messages = simple_storage.get_messages(client.device_id)
                if messages:
                    logger.info(f"Found {len(messages)} messages for device {client.device_id}")
                for msg in messages:
                    try:
                        msg_json = json.dumps({
                            "type": "message",
                            "data": msg,
                        })
                        logger.info(f"Sending message to client: {msg_json[:100]}...")
                        await client.websocket.send(msg_json)
                        logger.info(f"Message sent to client successfully")
                    except Exception as e:
                        logger.error(f"Error sending message to client: {e}")
                await asyncio.sleep(0.5)  # Poll every 500ms
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error polling messages: {e}")
                break

    async def handle_message(self, client: Client, raw_message: str):
        """Handle message from device"""
        try:
            data = json.loads(raw_message)
            msg_type = data.get("type")
            logger.info(f"Received message from device: type={msg_type}, data={str(data)[:100]}")

            if msg_type == "message":
                # Forward message response to Telegram user
                content = data.get("content", "")
                message_id = data.get("message_id")

                logger.info(f"Sending response to Telegram user {client.user_id}: {content[:50]}...")

                if client.user_id:
                    # Split long messages
                    if len(content) > 4000:
                        chunks = [content[i:i+4000] for i in range(0, len(content), 4000)]
                        for chunk in chunks:
                            await self._send_to_telegram(client.user_id, chunk)
                    else:
                        await self._send_to_telegram(client.user_id, content)

                logger.info("Message sent to Telegram")

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

    async def _send_to_telegram(self, user_id: int, text: str):
        """Send message to Telegram user"""
        from ..bot import send_message
        send_message(user_id, text)

    def _remove_client(self, client: Client):
        """Remove client from connections"""
        if client.device_id in self.clients:
            self.clients[client.device_id].discard(client)

            if not self.clients[client.device_id]:
                del self.clients[client.device_id]
                simple_storage.delete_device_status(client.device_id)

                from ..services.storage import storage
                if storage:
                    storage.update_device_status(client.device_id, "offline")

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
