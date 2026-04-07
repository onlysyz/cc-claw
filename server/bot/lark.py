"""CC-Claw Lark (Feishu) Bot Module"""

import json
import logging
import threading
import time
from typing import Optional

from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.ws.client import Client as WSClient

from ..config import config
from ..services.storage import init_storage
from ..services.simple_storage import simple_storage

logger = logging.getLogger(__name__)


class LarkBot:
    """Lark Bot for CC-Claw using WebSocket mode"""

    def __init__(self):
        self.ws_client: Optional[WSClient] = None
        self._running = False
        self._tenant_access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def start(self):
        """Start the Lark bot in a background thread"""
        if not config.lark_app_id or not config.lark_app_secret:
            logger.error("Lark app_id or app_secret not configured")
            return

        # Initialize storage
        init_storage()

        logger.info("Starting Lark bot in background...")

        # Run in a separate thread since ws_client.start() is blocking
        self._running = True
        thread = threading.Thread(target=self._run_ws_client, daemon=True)
        thread.start()

    def _run_ws_client(self):
        """Run the WebSocket client (blocking)"""
        try:
            from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import P2ImMessageReceiveV1

            def handle_event(event: P2ImMessageReceiveV1):
                self._handle_message(event)

            handler = (EventDispatcherHandler
                .builder('', '')
                .register_p2_im_message_receive_v1(handle_event)
                .build())

            self.ws_client = WSClient(
                config.lark_app_id,
                config.lark_app_secret,
                event_handler=handler,
            )

            logger.info("Connecting to Lark WebSocket...")
            self.ws_client.start()

        except Exception as e:
            logger.error(f"Lark WebSocket error: {e}", exc_info=True)
            self._running = False

    def _get_tenant_access_token(self) -> Optional[str]:
        """Get or refresh tenant access token"""
        # Check if current token is still valid
        if self._tenant_access_token and time.time() < self._token_expires_at - 60:
            return self._tenant_access_token

        try:
            import requests
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            headers = {"Content-Type": "application/json"}
            data = {
                "app_id": config.lark_app_id,
                "app_secret": config.lark_app_secret
            }

            resp = requests.post(url, headers=headers, json=data, timeout=10)
            result = resp.json()

            if result.get("code") == 0:
                self._tenant_access_token = result.get("tenant_access_token")
                self._token_expires_at = time.time() + result.get("expire", 7200)
                return self._tenant_access_token
            else:
                logger.error(f"Failed to get tenant access token: {result}")
                return None

        except Exception as e:
            logger.error(f"Error getting tenant access token: {e}")
            return None

    def _send_lark_message(self, open_id: str, text: str):
        """Send message to a Lark user via REST API"""
        token = self._get_tenant_access_token()
        if not token:
            logger.error("No tenant access token available")
            return

        try:
            import requests
            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }
            params = {"receive_id_type": "open_id"}
            data = {
                "receive_id": open_id,
                "msg_type": "text",
                "content": json.dumps({"text": text})
            }

            resp = requests.post(url, headers=headers, params=params, json=data, timeout=10)
            result = resp.json()

            if result.get("code") == 0:
                logger.info(f"Lark message sent to {open_id}: {text[:50]}...")
            else:
                logger.error(f"Failed to send Lark message: {result}")

        except Exception as e:
            logger.error(f"Error sending Lark message: {e}")

    def _handle_message(self, event):
        """Handle incoming message from Lark"""
        try:
            # Extract message and sender
            sender = event.event.sender
            message = event.event.message

            # Only handle text messages
            if message.message_type != "text":
                logger.info(f"Ignoring non-text message type: {message.message_type}")
                return

            # Get sender info
            sender_id = sender.sender_id
            if sender.sender_type != "user":
                logger.info(f"Ignoring non-user sender type: {sender.sender_type}")
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

            from ..services.storage import storage

            # Check if it's a command
            if text.startswith("/"):
                self._handle_command(open_id, text, message.message_id)
                return

            # Look up user by lark_open_id
            user = storage.get_user_by_lark_open_id(open_id)

            if not user:
                # User not paired - prompt to pair
                self._send_lark_message(open_id, "❌ 您的飞书账号未绑定设备。\n\n发送 /pair 开始配对您的设备。")
                return

            # Get user's device
            device = storage.get_user_device(user["id"])
            if not device:
                self._send_lark_message(open_id, "❌ 您没有已配对的设备。\n\n发送 /pair 重新配对。")
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

    def _handle_command(self, open_id: str, text: str, message_id: str):
        """Handle commands from Lark"""
        from ..services.storage import storage

        # /start - Welcome message
        if text == "/start":
            self._send_lark_message(open_id,
                "👋 欢迎使用 CC-Claw！\n\n"
                "发送 /pair 开始配对您的设备。\n"
                "/help 查看所有命令。"
            )
            return

        # /help - Help message
        if text == "/help":
            self._send_lark_message(open_id,
                "📖 CC-Claw 命令：\n\n"
                "/start - 欢迎消息\n"
                "/pair - 配对设备\n"
                "/unpair - 解绑设备\n"
                "/status - 查看状态\n"
                "/tasks - 查看定时任务\n"
                "/delay <分钟> <命令> - 延迟执行\n"
                "/help - 帮助信息"
            )
            return

        # /pair - Start pairing process
        if text == "/pair":
            # Get or create user
            user = storage.get_or_create_user_by_lark(open_id)

            # Check if already has device paired
            device = storage.get_user_device(user["id"])
            if device:
                self._send_lark_message(open_id,
                    "⚠️ 您已经有一个设备配对了。\n"
                    "发送 /unpair 解绑后再试。"
                )
                return

            # Generate pairing code
            code, expires_at = storage.create_pairing(user["id"])

            self._send_lark_message(open_id,
                f"🔗 配对码：{code}\n\n"
                "请在您的设备上运行：\n"
                f"cc-claw pair\n\n"
                "配对码 5 分钟内有效。"
            )
            logger.info(f"Created pairing code {code} for Lark user {open_id}")
            return

        # /unpair - Unpair device
        if text == "/unpair":
            user = storage.get_user_by_lark_open_id(open_id)
            if not user:
                self._send_lark_message(open_id, "❌ 您没有配对过设备。")
                return

            device = storage.get_user_device(user["id"])
            if device:
                storage.delete_device(device["id"])
                simple_storage.delete_user_device(int(user.get("telegram_id", 0)))
                self._send_lark_message(open_id, "✅ 设备已解绑！")
            else:
                self._send_lark_message(open_id, "❌ 您没有配对过设备。")
            return

        # /status - Check status
        if text == "/status":
            user = storage.get_user_by_lark_open_id(open_id)
            if not user:
                self._send_lark_message(open_id,
                    "❌ 未配对\n\n发送 /pair 开始配对。"
                )
                return

            device = storage.get_user_device(user["id"])
            if device:
                status = simple_storage.get_device_status(device["id"])
                is_online = status == "online"
                self._send_lark_message(open_id,
                    f"📱 设备状态\n\n"
                    f"名称：{device['name']}\n"
                    f"平台：{device['platform']}\n"
                    f"状态：{'🟢 在线' if is_online else '🔴 离线'}"
                )
            else:
                self._send_lark_message(open_id,
                    "❌ 未配对\n\n发送 /pair 开始配对。"
                )
            return

        # /tasks - List scheduled tasks (forward to device)
        if text.strip() == "/tasks":
            user = storage.get_user_by_lark_open_id(open_id)
            if not user:
                self._send_lark_message(open_id, "❌ 您没有配对过设备。\n\n发送 /pair 配对。")
                return

            device = storage.get_user_device(user["id"])
            if not device:
                self._send_lark_message(open_id, "❌ 您没有配对过设备。\n\n发送 /pair 配对。")
                return

            # Forward to device
            message_data = {
                "lark_open_id": open_id,
                "content": "/tasks",
                "message_id": str(message_id),
            }
            simple_storage.publish_message(device["id"], message_data)
            self._send_lark_message(open_id, "⏳ 获取任务列表...")
            return

        # /delay - Forward to device for processing
        if text.startswith("/delay "):
            user = storage.get_user_by_lark_open_id(open_id)
            if not user:
                self._send_lark_message(open_id, "❌ 您没有配对过设备。\n\n发送 /pair 配对。")
                return

            device = storage.get_user_device(user["id"])
            if not device:
                self._send_lark_message(open_id, "❌ 您没有配对过设备。\n\n发送 /pair 配对。")
                return

            status = simple_storage.get_device_status(device["id"])
            if status != "online":
                self._send_lark_message(open_id, "🔴 您的设备不在线。")
                return

            # Forward to device
            message_data = {
                "lark_open_id": open_id,
                "content": text,
                "message_id": str(message_id),
            }
            simple_storage.publish_message(device["id"], message_data)
            self._send_lark_message(open_id, "⏳ 处理中...")
            return

        # Unknown command
        self._send_lark_message(open_id,
            "❌ 未知命令。\n\n发送 /help 查看可用命令。"
        )

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
