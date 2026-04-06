"""CC-Claw Lark (Feishu) Bot Module"""

import json
import logging
import threading
from typing import Optional

from lark_oapi.adapter.websocket import WebSocketClient
from lark_oapi.event.dispatch import EventDispatcher
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
from lark_oapi import Lark

from ..config import config
from ..services.storage import init_storage
from ..services.redis import simple_storage

logger = logging.getLogger(__name__)


class LarkBot:
    """Lark Bot for CC-Claw using WebSocket mode"""

    def __init__(self):
        self.ws_client: Optional[WebSocketClient] = None
        self.lark_client: Optional[Lark] = None
        self._running = False

    def start(self):
        """Start the Lark bot in a background thread"""
        if not config.lark_app_id or not config.lark_app_secret:
            logger.error("Lark app_id or app_secret not configured")
            return

        # Initialize storage
        init_storage()

        # Create Lark API client for sending messages
        self.lark_client = Lark(
            app_id=config.lark_app_id,
            app_secret=config.lark_app_secret,
            enable_db=False,
        )

        logger.info("Starting Lark bot in background...")

        # Run in a separate thread since WebSocketClient.start() is blocking
        self._running = True
        thread = threading.Thread(target=self._run_ws_client, daemon=True)
        thread.start()

    def _run_ws_client(self):
        """Run the WebSocket client (blocking)"""
        try:
            # Create event dispatcher
            dispatcher = EventDispatcher.create(self._handle_event)

            # Create WebSocket client
            self.ws_client = WebSocketClient(
                config.lark_app_id,
                config.lark_app_secret,
                event_dispatcher=dispatcher,
            )

            # Start WebSocket connection
            logger.info("Connecting to Lark WebSocket...")
            self.ws_client.start()

        except Exception as e:
            logger.error(f"Lark WebSocket error: {e}", exc_info=True)
            self._running = False

    def _handle_event(self, event):
        """Handle incoming Lark events"""
        try:
            # Handle message receive events
            if isinstance(event, P2ImMessageReceiveV1):
                self._handle_message(event)
            else:
                logger.info(f"Received unknown event type: {type(event)}")
        except Exception as e:
            logger.error(f"Error handling Lark event: {e}", exc_info=True)

    def _handle_message(self, event: P2ImMessageReceiveV1):
        """Handle incoming message from Lark"""
        try:
            # Extract message content
            sender = event.event.message.sender
            message = event.event.message

            # Only handle text messages from user (not bot)
            if message.message_type != "text":
                logger.info(f"Ignoring non-text message type: {message.message_type}")
                return

            # Get sender info
            sender_id = sender.sender_id
            if sender_id.id_type != "open_id":
                logger.info(f"Ignoring non-open_id sender type: {sender_id.id_type}")
                return

            open_id = sender_id.open_id

            # Get message content
            content = message.content
            if not content:
                return

            # Parse content (it's JSON string)
            try:
                content_obj = json.loads(content)
                text = content_obj.get("text", "").strip()
            except (json.JSONDecodeError, AttributeError):
                text = str(content)
                logger.warning(f"Could not parse message content as JSON: {content}")

            if not text:
                return

            logger.info(f"Received Lark message from {open_id}: {text[:50]}...")

            # Look up user by lark_open_id
            from ..services.storage import storage
            user = storage.get_user_by_lark_open_id(open_id)

            if not user:
                # User not paired with any device
                self._send_lark_message(open_id, "❌ 您的飞书账号未绑定设备。\n请先使用 Telegram 配对您的设备。")
                return

            # Get user's device
            device = storage.get_user_device(user["id"])
            if not device:
                self._send_lark_message(open_id, "❌ 您没有已配对的设备。")
                return

            # Check if device is online
            status = simple_storage.get_device_status(device["id"])
            if status != "online":
                self._send_lark_message(open_id, "🔴 您的设备不在线。\n请确保 cc-claw 正在运行。")
                return

            # Store message for device to poll
            message_data = {
                "chat_id": user.get("telegram_id"),  # Keep for backward compat
                "lark_open_id": open_id,  # Add Lark identification
                "user_id": user.get("telegram_id"),
                "content": text,
                "message_id": str(message.message_id),
            }
            simple_storage.publish_message(device["id"], message_data)

            # Send acknowledgment to user
            self._send_lark_message(open_id, "⏳ 处理中...")

            logger.info(f"Published message to device {device['id']} for user {user['id']}")

        except Exception as e:
            logger.error(f"Error handling Lark message: {e}", exc_info=True)

    def _send_lark_message(self, open_id: str, text: str):
        """Send message to a Lark user via REST API"""
        if not self.lark_client:
            logger.warning("Lark client not initialized")
            return

        try:
            from lark_oapi.api.im.v1 import CreateMessageRequest

            # Build the request
            request = CreateMessageRequest.builder().build()
            request.receive_id = open_id
            request.receive_id_type = "open_id"
            request.msg_type = "text"
            request.content = json.dumps({"text": text})

            # Send the message
            response = self.lark_client.im.v1.message.create(request)

            if response.code == 0:
                logger.info(f"Lark message sent to {open_id}: {text[:50]}...")
            else:
                logger.error(f"Failed to send Lark message: {response.code} - {response.msg}")

        except Exception as e:
            logger.error(f"Error sending Lark message: {e}")

    def send_message_to_lark_user(self, open_id: str, text: str):
        """Send message to a Lark user (called from other parts of the server)"""
        # Run in a thread to avoid blocking
        thread = threading.Thread(target=self._send_lark_message, args=(open_id, text), daemon=True)
        thread.start()

    def stop(self):
        """Stop the Lark bot"""
        logger.info("Stopping Lark bot...")
        self._running = False
        if self.ws_client:
            try:
                self.ws_client.stop()
            except Exception as e:
                logger.error(f"Error stopping Lark WebSocket: {e}")


# Global Lark bot instance
lark_bot = LarkBot()


def send_lark_message(open_id: str, text: str):
    """Helper function to send message to Lark user"""
    lark_bot.send_message_to_lark_user(open_id, text)
