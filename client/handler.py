"""CC-Claw Client Message Handler Module - with Profile, Onboarding, Token Tracking"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Callable, Awaitable

from .websocket import WebSocketManager, Message
from .claude import ClaudeExecutor
from .config import ClientConfig
from .scheduler import TaskScheduler
from .profile import ProfileManager
from .token_tracker import TokenTracker


logger = logging.getLogger(__name__)


class MessageHandler:
    """Handle messages from server"""

    def __init__(
        self,
        ws_manager: WebSocketManager,
        claude: ClaudeExecutor,
        config: ClientConfig,
        scheduler: TaskScheduler,
        profile: ProfileManager,
        queue_manager=None,  # optional, for priority queue
        on_message_sent: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        self.ws = ws_manager
        self.claude = claude
        self.config = config
        self.scheduler = scheduler
        self.profile = profile
        self.queue_manager = queue_manager
        self.on_message_sent = on_message_sent
        self.token_tracker = TokenTracker()
        self.autonomous_mode = True  # start in autonomous mode by default

        # Register handlers
        self.ws.on("message", self.handle_message)
        self.ws.on("error", self.handle_error)
        self.ws.on("delivered", self.handle_delivered)
        self.ws.on("tasks", self.handle_tasks_request)
        self.ws.on("profile", self.handle_profile_message)

    async def handle_message(self, message: Message):
        """Handle incoming message from user"""
        try:
            message_id = message.message_id
            content = message.data.get("content", "")
            chat_id = message.data.get("chat_id")
            lark_open_id = message.data.get("lark_open_id")
            is_priority = message.data.get("priority", False)

            logger.info(f"Received message: {content[:50]}..., priority={is_priority}")

            # Check for profile action nested inside data (server sends as data.type == "profile")
            if message.data.get("type") == "profile":
                logger.info("Detected profile message nested in data")
                await self.handle_profile_message(message.data)
                return

            # Send acknowledgment first
            if message_id:
                await self.ws.send_ack(message_id)

            # Check for /delay command
            if content.startswith("/delay "):
                await self._handle_delay_command(content, message_id, lark_open_id)
                return

            # Check for /tasks command
            if content.strip() == "/tasks":
                await self._handle_tasks_command(message_id, lark_open_id)
                return

            # Check for /progress command
            if content.strip() == "/progress":
                await self._handle_progress_command(message_id, lark_open_id)
                return

            # Check for /pause command
            if content.strip() == "/pause":
                await self._handle_pause_command(message_id, lark_open_id)
                return

            # Check for /resume command
            if content.strip() == "/resume":
                await self._handle_resume_command(message_id, lark_open_id)
                return

            # Check for /goals command
            if content.strip() == "/goals":
                await self._handle_goals_command(message_id, lark_open_id)
                return

            # Check for /setgoal <id> command
            if content.strip().startswith("/setgoal "):
                parts = content.strip().split(" ", 1)
                if len(parts) > 1:
                    goal_id = parts[1].strip()
                    await self._handle_setgoal_command(goal_id, message_id, lark_open_id)
                else:
                    await self.ws.send_message("❌ 用法: /setgoal <goal_id>\n先用 /goals 查看所有目标及其ID", message_id, [], lark_open_id)
                return

            # User message — if priority, insert at front of queue (don't execute now)
            if is_priority and self.queue_manager:
                # Enqueue for autonomous execution (user's command goes to front)
                active_goals = self.profile.get_active_goals()
                goal_id = active_goals[0].id if active_goals else "default"
                self.queue_manager.add_user_task(content, goal_id)
                logger.info(f"User task enqueued at front: {content[:50]}...")
                # Acknowledge receipt
                if message_id:
                    ack_resp = "✅ 收到！任务已排到最前面，我会尽快完成。"
                    await self.ws.send_message(ack_resp, message_id, [], lark_open_id)
                return

            # Execute with Claude
            logger.info("Calling Claude executor...")
            response, images = await self.claude.execute(content)
            logger.info(f"Claude response: {response[:100]}...")

            # Parse response for token usage and 429
            result_text, usage, is_rate_limited = self.token_tracker.parse_json_response(
                response if not images else ""
            )
            if usage:
                self.profile.record_usage(usage.total_tokens)
                logger.info(f"Token usage recorded: {usage.total_tokens}")

            if is_rate_limited or "429" in response:
                self.profile.set_rate_limited(asyncio.get_event_loop().time())
                logger.warning("Rate limit detected!")

            if images:
                logger.info(f"Claude generated {len(images)} images")

            # Send response back to server
            if message_id:
                final_response = result_text if result_text else response
                success = await asyncio.wait_for(
                    self.ws.send_message(final_response, message_id, images, lark_open_id),
                    timeout=30
                )
                logger.info(f"Response sent: {success}")
                if success and self.on_message_sent:
                    await self.on_message_sent(message_id)
        except Exception as e:
            logger.error(f"Error in handle_message: {e}", exc_info=True)

    async def handle_profile_message(self, inner_data: dict):
        """Handle profile save/update messages from server
        inner_data is message.data from the WebSocket message, which contains:
        {type: "profile", action: "save_profile", data: {...}, lark_open_id: ..., user_id: ...}
        """
        try:
            action = inner_data.get("action", "")
            profile_data = inner_data.get("data", {})
            lark_open_id = inner_data.get("lark_open_id")
            user_id = inner_data.get("user_id")
            message_id = inner_data.get("message_id")

            logger.info(f"Profile message: action={action}, data={profile_data}")

            if action == "save_profile":
                # Update profile fields in-place
                self.profile.profile.profession = profile_data.get("profession", "")
                self.profile.profile.situation = profile_data.get("situation", "")
                self.profile.profile.short_term_goal = profile_data.get("short_term_goal", "")
                self.profile.profile.what_better_means = profile_data.get("what_better_means", "")
                self.profile.profile.onboarding_completed = True
                self.profile.profile.updated_at = datetime.now().isoformat()
                self.profile._save()

                logger.info(f"Profile saved and persisted for user {user_id}")
                logger.info(f"  onboarding_completed={self.profile.profile.onboarding_completed}")

                # Create initial goal from profile
                goal_text = profile_data.get("short_term_goal", "")
                if goal_text:
                    goal = self.profile.add_goal(goal_text)
                    logger.info(f"Created initial goal: {goal.id} - {goal_text}")

                # Confirm to user via Lark (or Telegram)
                confirm = (
                    f"✅ Profile received!\n\n"
                    f"Goal set: {goal_text[:50]}...\n"
                    f"🎯 Autonomous mode starting..."
                )
                await self.ws.send_message(confirm, message_id, [], lark_open_id)

        except Exception as e:
            logger.error(f"Error handling profile message: {e}", exc_info=True)

    async def _handle_delay_command(self, content: str, message_id: str, lark_open_id: str = None):
        """Handle /delay command"""
        try:
            parts = content.split(" ", 2)
            if len(parts) < 3:
                response = "❌ 用法: /delay <分钟> <命令>\n例如: /delay 5 测试部署"
                await self.ws.send_message(response, message_id, [], lark_open_id)
                return

            delay_minutes = int(parts[1])
            command = parts[2]

            if delay_minutes <= 0 or delay_minutes > 10080:
                response = "❌ 延迟时间需在 1-10080 分钟之间"
                await self.ws.send_message(response, message_id, [], lark_open_id)
                return

            task_id = self.scheduler.add_task(command, delay_minutes, message_id, lark_open_id)

            response = f"✅ 已安排 {delay_minutes} 分钟后执行:\n{command}\n\n任务ID: {task_id[:8]}"
            await self.ws.send_message(response, message_id, [], lark_open_id)
            logger.info(f"Scheduled task {task_id[:8]}: /delay {delay_minutes} {command}")
        except ValueError:
            response = "❌ 无效的延迟时间，请输入数字\n例如: /delay 5 测试部署"
            await self.ws.send_message(response, message_id, [], lark_open_id)
        except Exception as e:
            logger.error(f"Error handling delay command: {e}")
            response = f"❌ 安排任务失败: {e}"
            await self.ws.send_message(response, message_id, [], lark_open_id)

    async def _handle_tasks_command(self, message_id: str, lark_open_id: str = None):
        """Handle /tasks command"""
        response = self.scheduler.format_tasks_list()
        await self.ws.send_message(response, message_id, [], lark_open_id)

    async def _handle_progress_command(self, message_id: str, lark_open_id: str = None):
        """Handle /progress command - enhanced with queue status"""
        lines = [self.profile.format_progress()]

        # Add queue status if queue_manager available
        if self.queue_manager:
            queue_status = self.queue_manager.format_status()
            lines.append("\n" + queue_status)

        response = "\n".join(lines)
        await self.ws.send_message(response, message_id, [], lark_open_id)

    async def _handle_pause_command(self, message_id: str, lark_open_id: str = None):
        """Handle /pause command"""
        self.autonomous_mode = False
        logger.info("Autonomous mode PAUSED")
        response = "⏸️ Autonomous mode paused. CC-Claw will not execute tasks automatically.\nResume with /resume"
        await self.ws.send_message(response, message_id, [], lark_open_id)

    async def _handle_resume_command(self, message_id: str, lark_open_id: str = None):
        """Handle /resume command"""
        self.autonomous_mode = True
        logger.info("Autonomous mode RESUMED")
        response = "▶️ Autonomous mode resumed. CC-Claw is working for you again."
        await self.ws.send_message(response, message_id, [], lark_open_id)

    async def _handle_goals_command(self, message_id: str, lark_open_id: str = None):
        """Handle /goals command - shows all goals with status"""
        all_goals = self.profile.goals
        if not all_goals:
            response = "🎯 No goals yet. Complete onboarding to set your first goal."
        else:
            lines = ["🎯 **Goals**\n"]
            for g in all_goals:
                tasks = self.profile.get_tasks_for_goal(g.id)
                completed = len([t for t in tasks if t.status.value == "completed"])
                total = len(tasks)
                status_map = {"active": "🟢", "completed": "✅", "paused": "⏸️"}
                marker = status_map.get(g.status.value, "⚪")
                active_marker = " ◀" if g.id == self.profile.active_goal_id else ""
                lines.append(f"{marker} [{g.id[:8]}] {g.description}")
                lines.append(f"   {completed}/{total} tasks{active_marker}")
            lines.append("\n◀ = currently working on")
            lines.append("Use /setgoal <id> to switch")
            response = "\n".join(lines)
        await self.ws.send_message(response, message_id, [], lark_open_id)

    async def _handle_setgoal_command(self, goal_id: str, message_id: str, lark_open_id: str = None):
        """Handle /setgoal <id> command - switch active goal"""
        success = self.profile.set_active_goal(goal_id)
        if success:
            goal = None
            for g in self.profile.goals:
                if g.id == goal_id:
                    goal = g
                    break
            response = f"✅ 已切换到目标:\n[{goal_id[:8]}] {goal.description if goal else goal_id}"
            logger.info(f"Switched active goal to {goal_id}")
        else:
            response = f"❌ 未找到目标 {goal_id}，或目标不是 active 状态。\n先用 /goals 查看所有目标。"
        await self.ws.send_message(response, message_id, [], lark_open_id)

    async def handle_tasks_request(self, message: Message):
        """Handle tasks list request from server"""
        pass

    async def handle_error(self, message: Message):
        """Handle error message from server"""
        error_code = message.data.get("code", "UNKNOWN")
        error_msg = message.data.get("message", "Unknown error")
        logger.error(f"Server error: {error_code} - {error_msg}")

    async def handle_delivered(self, message: Message):
        """Handle message delivered confirmation"""
        message_id = message.message_id
        logger.info(f"Message delivered: {message_id}")


class ToolExecutor:
    """Execute local tools"""

    def __init__(self, config: ClientConfig):
        self.config = config
        self._results: dict = {}

    async def execute_tool(self, tool_name: str, params: dict) -> str:
        """Execute a tool and return result"""
        if tool_name == "screenshot":
            return await self._screenshot()
        elif tool_name == "list_dir":
            return await self._list_dir(params.get("path", "."))
        elif tool_name == "read_file":
            return await self._read_file(params.get("path", ""))
        elif tool_name == "shell":
            return await self._shell(params.get("command", ""))
        else:
            return f"Unknown tool: {tool_name}"

    async def _screenshot(self) -> str:
        """Take a screenshot"""
        import platform
        import os

        system = platform.system()
        temp_file = os.path.join(self.config.working_dir, "cc-claw-screenshot.png")

        try:
            if system == "Darwin":
                cmd = ["screencapture", temp_file]
            elif system == "Linux":
                cmd = ["scrot", temp_file]
            else:
                return "Screenshot not supported on this platform"

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()

            if os.path.exists(temp_file):
                self._results["screenshot"] = temp_file
                return f"Screenshot saved: {temp_file}"
            else:
                return "Failed to capture screenshot"

        except Exception as e:
            return f"Error capturing screenshot: {e}"

    async def _list_dir(self, path: str) -> str:
        """List directory contents"""
        try:
            import os
            items = os.listdir(path)
            return "\n".join(items)
        except Exception as e:
            return f"Error listing directory: {e}"

    async def _read_file(self, path: str) -> str:
        """Read file contents"""
        try:
            with open(path, "r") as f:
                content = f.read(10000)
                if len(content) >= 10000:
                    content += "\n... (truncated)"
                return content
        except Exception as e:
            return f"Error reading file: {e}"

    async def _shell(self, command: str) -> str:
        """Execute shell command"""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60,
            )
            result = stdout.decode() if stdout else ""
            error = stderr.decode() if stderr else ""
            if error:
                result += f"\nStderr: {error}"
            return result or "No output"
        except Exception as e:
            return f"Error executing command: {e}"
