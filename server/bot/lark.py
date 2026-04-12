"""CC-Claw Lark (Feishu) Bot Module - with Onboarding and Autonomous Commands"""

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

# Onboarding steps (same as Telegram)
ONBOARDING_STEPS = [
    ("profession", "🏠 你的职业是什么？\n\n（比如：软件工程师、学生、设计师、写作者...）"),
    ("situation", "📍 你目前的状况是什么？\n\n（比如：在做一个项目、学习编程、正在找工作...）"),
    ("goal", "🎯 你的短期目标是什么？\n\n（比如：完成作品集、学习 React、启动我的创业项目...）"),
    ("better", "✨ 对你来说，「更好」是什么样的？\n\n（比如：更有生产力、更井井有条、在编程上更有信心...）"),
]

STEP_NEXT = {
    "pending": "profession",
    "profession": "situation",
    "situation": "goal",
    "goal": "better",
    "better": "complete",
}


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
            sender = event.event.sender
            message = event.event.message

            if message.message_type != "text":
                logger.info(f"Ignoring non-text message type: {message.message_type}")
                return

            sender_id = sender.sender_id
            if sender.sender_type != "user":
                logger.info(f"Ignoring non-user sender type: {sender.sender_type}")
                return

            open_id = sender_id.open_id

            # Parse content
            try:
                content_obj = json.loads(message.content)
                text = content_obj.get("text", "").strip()
            except (json.JSONDecodeError, AttributeError):
                text = str(message.content).strip()
                logger.warning(f"Could not parse message content as JSON: {message.content}")

            if not text:
                return

            logger.info(f"Received Lark message from {open_id}: {text[:50]}...")

            from ..services.storage import storage

            # Get or create user
            user = storage.get_user_by_lark_open_id(open_id)
            if not user:
                user = storage.get_or_create_user_by_lark(open_id)

            # Check onboarding state
            state = user.get("onboarding_state", "pending")
            logger.info(f"Onboarding state for {open_id}: {state}")
            if state != "complete":
                return self._handle_onboarding_message(open_id, text, user)

            # Check if it's a command
            if text.startswith("/"):
                return self._handle_command(open_id, text, message.message_id, user)

            # Normal message — forward to device
            return self._handle_normal_message(open_id, text, message.message_id, user)

        except Exception as e:
            logger.error(f"Error handling Lark message: {e}", exc_info=True)

    def _handle_onboarding_message(self, open_id: str, text: str, user: dict):
        """Handle onboarding messages"""
        from ..services.storage import storage

        state = user.get("onboarding_state", "pending")
        onboarding_data = user.get("onboarding_data", {})
        user_id = user["id"]

        step_map = {k: i for i, (k, _) in enumerate(ONBOARDING_STEPS)}
        next_state = STEP_NEXT.get(state, "complete")

        if state in step_map:
            step_key = state
            onboarding_data[step_key] = text.strip()

        if next_state == "complete":
            # Onboarding complete
            storage.set_onboarding_state(user_id, "complete", onboarding_data)
            logger.info(f"Onboarding complete for Lark user {open_id}: {onboarding_data}")

            # Forward profile to paired device directly via WebSocket (not via queue)
            if user.get("device_ids"):
                device = storage.get_user_device(user_id)
                if device:
                    from ..ws import ws_server
                    ws_server.send_profile_to_device(
                        device["id"],
                        profile_data={
                            "profession": onboarding_data.get("profession", ""),
                            "situation": onboarding_data.get("situation", ""),
                            "short_term_goal": onboarding_data.get("goal", ""),
                            "what_better_means": onboarding_data.get("better", ""),
                        },
                        lark_open_id=open_id,
                        message_id=None,  # no Lark message_id - not a task
                    )

            self._send_lark_message(open_id,
                "✅ 初始化完成！\n\n"
                f"📋 摘要：\n"
                f"• 职业：{onboarding_data.get('profession', 'N/A')}\n"
                f"• 现状：{onboarding_data.get('situation', 'N/A')}\n"
                f"• 目标：{onboarding_data.get('goal', 'N/A')}\n"
                f"• 更好：{onboarding_data.get('better', 'N/A')}\n\n"
                "🎯 你的 AI 伙伴正在为你工作！\n"
                "发送 /progress 查看状态。"
            )

        else:
            # Move to next step
            storage.set_onboarding_state(user_id, next_state, onboarding_data)
            step_idx = step_map.get(next_state, 0)
            if step_idx < len(ONBOARDING_STEPS):
                _, question = ONBOARDING_STEPS[step_idx]
                self._send_lark_message(open_id, question)
            else:
                self._send_lark_message(open_id, "出错了，发送 /onboarding 重试。")

    def _handle_normal_message(self, open_id: str, text: str, message_id: str, user: dict):
        """Handle regular messages — forward to device (skip during onboarding)"""
        from ..services.storage import storage

        # Skip forwarding during onboarding — user is in onboarding flow,
        # server handles sending next question via _send_lark_message directly
        state = user.get("onboarding_state", "pending")
        if state != "complete":
            # During onboarding, don't forward to device — just silently absorb
            # The next onboarding question will be sent via _handle_onboarding_message
            return

        device = storage.get_user_device(user["id"])
        if not device:
            self._send_lark_message(open_id, "❌ 未配对设备。\n\n发送 /pair 配对。")
            return

        status = simple_storage.get_device_status(device["id"])
        if status != "online":
            self._send_lark_message(open_id, "🔴 设备不在线。\n请确保 cc-claw 正在运行。")
            return

        message_data = {
            "chat_id": user.get("telegram_id"),
            "lark_open_id": open_id,
            "user_id": user.get("telegram_id", ""),
            "content": text,
            "message_id": str(message_id),
            "priority": True,
        }
        simple_storage.publish_message(device["id"], message_data)
        self._send_lark_message(open_id, "⏳ 处理中...")

    def _handle_command(self, open_id: str, text: str, message_id: str, user: dict):
        """Handle all commands"""
        from ..services.storage import storage

        # /start
        if text == "/start" or text == "/onboarding":
            # /onboarding always forces restart regardless of current state
            if text == "/onboarding":
                storage.set_onboarding_state(user["id"], "profession", {})
            else:
                state = user.get("onboarding_state", "pending")
                if state != "complete":
                    storage.set_onboarding_state(user["id"], "profession", {})

            self._send_lark_message(open_id,
                f"👋 让我们开始吧！\n\n"
                f"{ONBOARDING_STEPS[0][1]}\n\n"
                "直接输入你的回答即可。"
            )
            return
            self._send_lark_message(open_id,
                "👋 欢迎回到 CC-Claw！\n"
                "你的 AI 伙伴正在为你工作。\n\n"
                "命令：\n"
                "/progress - 查看进度\n"
                "/pause - 暂停自动执行\n"
                "/resume - 恢复自动执行\n"
                "/goals - 查看所有目标\n"
                "/status - 连接状态\n"
                "/help - 帮助"
            )
            return

        # /help
        if text == "/help":
            self._send_lark_message(open_id,
                "📖 CC-Claw 命令：\n\n"
                "/start - 欢迎 + 初始化\n"
                "/progress - 查看进度和 Token 统计\n"
                "/pause - 暂停自动执行\n"
                "/resume - 恢复自动执行\n"
                "/tasks - 查看任务队列\n"
                "/goals - 查看所有目标\n"
                "/setgoal <id> - 切换工作目标\n"
                "/status - 连接状态\n"
                "/onboarding - 重新初始化\n"
                "/help - 帮助"
            )
            return

        # /progress
        if text.strip() == "/progress":
            device = storage.get_user_device(user["id"])
            if not device:
                self._send_lark_message(open_id, "❌ 未配对设备。\n\n发送 /pair 配对。")
                return
            status = simple_storage.get_device_status(device["id"])
            if status != "online":
                self._send_lark_message(open_id, "🔴 设备不在线。")
                return
            message_data = {
                "lark_open_id": open_id,
                "content": "/progress",
                "message_id": str(message_id),
            }
            simple_storage.publish_message(device["id"], message_data)
            self._send_lark_message(open_id, "⏳ 获取进度报告...")
            return

        # /pause
        if text.strip() == "/pause":
            device = storage.get_user_device(user["id"])
            if not device:
                self._send_lark_message(open_id, "❌ 未配对设备。")
                return
            status = simple_storage.get_device_status(device["id"])
            if status != "online":
                self._send_lark_message(open_id, "🔴 设备不在线。")
                return
            message_data = {
                "lark_open_id": open_id,
                "content": "/pause",
                "message_id": str(message_id),
            }
            simple_storage.publish_message(device["id"], message_data)
            self._send_lark_message(open_id, "⏸️ 已发送暂停信号...")
            return

        # /resume
        if text.strip() == "/resume":
            device = storage.get_user_device(user["id"])
            if not device:
                self._send_lark_message(open_id, "❌ 未配对设备。")
                return
            status = simple_storage.get_device_status(device["id"])
            if status != "online":
                self._send_lark_message(open_id, "🔴 设备不在线。")
                return
            message_data = {
                "lark_open_id": open_id,
                "content": "/resume",
                "message_id": str(message_id),
            }
            simple_storage.publish_message(device["id"], message_data)
            self._send_lark_message(open_id, "▶️ 已发送恢复信号...")
            return

        # /goals
        if text.strip() == "/goals":
            device = storage.get_user_device(user["id"])
            if not device:
                self._send_lark_message(open_id, "❌ 未配对设备。")
                return
            status = simple_storage.get_device_status(device["id"])
            if status != "online":
                self._send_lark_message(open_id, "🔴 设备不在线。")
                return
            message_data = {
                "lark_open_id": open_id,
                "content": "/goals",
                "message_id": str(message_id),
            }
            simple_storage.publish_message(device["id"], message_data)
            self._send_lark_message(open_id, "⏳ 获取目标列表...")
            return

        # /setgoal <id>
        if text.strip().startswith("/setgoal "):
            parts = text.strip().split(" ", 1)
            if len(parts) > 1:
                goal_id = parts[1].strip()
                device = storage.get_user_device(user["id"])
                if not device:
                    self._send_lark_message(open_id, "❌ 未配对设备。")
                    return
                status = simple_storage.get_device_status(device["id"])
                if status != "online":
                    self._send_lark_message(open_id, "🔴 设备不在线。")
                    return
                message_data = {
                    "lark_open_id": open_id,
                    "content": f"/setgoal {goal_id}",
                    "message_id": str(message_id),
                }
                simple_storage.publish_message(device["id"], message_data)
                self._send_lark_message(open_id, "🔄 切换目标中...")
                return
            self._send_lark_message(open_id,
                "❌ 用法：/setgoal <目标ID>\n\n"
                "先用 /goals 查看所有目标及其ID。"
            )
            return

        # /status
        if text.strip() == "/status":
            device = storage.get_user_device(user["id"])
            if not device:
                self._send_lark_message(open_id, "❌ 未配对设备。\n\n发送 /pair 配对。")
                return
            status = simple_storage.get_device_status(device["id"])
            is_online = status == "online"
            state = user.get("onboarding_state", "pending")
            self._send_lark_message(open_id,
                f"📱 设备状态\n\n"
                f"名称：{device['name']}\n"
                f"平台：{device['platform']}\n"
                f"状态：{'🟢 在线' if is_online else '🔴 离线'}\n"
                f"初始化：{'✅ 完成' if state == 'complete' else '⏳ 未完成'}"
            )
            return

        # /tasks
        if text.strip() == "/tasks":
            device = storage.get_user_device(user["id"])
            if not device:
                self._send_lark_message(open_id, "❌ 未配对设备。")
                return
            status = simple_storage.get_device_status(device["id"])
            if status != "online":
                self._send_lark_message(open_id, "🔴 设备不在线。")
                return
            message_data = {
                "lark_open_id": open_id,
                "content": "/tasks",
                "message_id": str(message_id),
            }
            simple_storage.publish_message(device["id"], message_data)
            self._send_lark_message(open_id, "⏳ 获取任务列表...")
            return

        # /delay
        if text.startswith("/delay "):
            device = storage.get_user_device(user["id"])
            if not device:
                self._send_lark_message(open_id, "❌ 未配对设备。")
                return
            status = simple_storage.get_device_status(device["id"])
            if status != "online":
                self._send_lark_message(open_id, "🔴 设备不在线。")
                return
            message_data = {
                "lark_open_id": open_id,
                "content": text,
                "message_id": str(message_id),
            }
            simple_storage.publish_message(device["id"], message_data)
            self._send_lark_message(open_id, "⏳ 处理中...")
            return

        # /pair
        if text.strip() == "/pair":
            device = storage.get_user_device(user["id"])
            if device:
                self._send_lark_message(open_id, "⚠️ 已配对设备。\n发送 /unpair 解绑后再试。")
                return
            code, expires_at = storage.create_pairing(user["id"])
            self._send_lark_message(open_id,
                f"🔗 配对码：{code}\n\n"
                "在你的设备上运行：\n"
                f"cc-claw pair\n\n"
                "配对码 5 分钟内有效。"
            )
            logger.info(f"Created pairing code {code} for Lark user {open_id}")
            return

        # /unpair
        if text.strip() == "/unpair":
            device = storage.get_user_device(user["id"])
            if not device:
                self._send_lark_message(open_id, "❌ 未配对过设备。")
                return
            storage.delete_device(device["id"])
            simple_storage.delete_user_device_by_lark(open_id)
            self._send_lark_message(open_id, "✅ 设备已解绑！")
            return

        # Unknown command
        self._send_lark_message(open_id,
            "❌ 未知命令。\n\n发送 /help 查看可用命令。"
        )

    def send_message_to_lark_user(self, open_id: str, text: str):
        """Send message to a Lark user (called from other parts of the server)"""
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
