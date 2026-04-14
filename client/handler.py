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
from .memory import PersistentMemory, ConversationMemory
from .tools import (
    FileProcessor, DataScraper, ApiClient,
    ProcessManager, SystemInfo, GitHelper, DockerHelper,
    get_tool
)


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
        queue_manager=None,
        goal_engine=None,
        memory: PersistentMemory = None,
        on_autonomous_start: Optional[Callable[[], None]] = None,  # callback to start runner
        on_message_sent: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        self.ws = ws_manager
        self.claude = claude
        self.config = config
        self.scheduler = scheduler
        self.profile = profile
        self.queue_manager = queue_manager
        self.goal_engine = goal_engine
        self.memory = memory
        self.on_autonomous_start = on_autonomous_start
        self.on_message_sent = on_message_sent
        self.token_tracker = TokenTracker()
        self.autonomous_mode = True
        # Short-term conversation memory
        self.conversation_memory = ConversationMemory()

        # Register handlers
        self.ws.on("message", self.handle_message)
        self.ws.on("error", self.handle_error)
        self.ws.on("delivered", self.handle_delivered)
        self.ws.on("tasks", self.handle_tasks_request)

    async def handle_message(self, message: Message):
        """Handle incoming message from user"""
        try:
            message_id = message.message_id
            content = message.data.get("content", "")
            chat_id = message.data.get("chat_id")
            lark_open_id = message.data.get("lark_open_id")
            is_priority = message.data.get("priority", False)

            logger.info(f"Received message: {content[:50]}..., priority={is_priority}")

            # Add to conversation memory
            self.conversation_memory.add_user(content)

            # Send acknowledgment first
            if message_id:
                await self.ws.send_ack(message_id)

            # Check for /memory command (new)
            if content.strip() == "/memory":
                await self._handle_memory_command(message_id, lark_open_id)
                return

            # Check for /recall command (new)
            if content.strip().startswith("/recall "):
                query = content.strip()[8:].strip()
                await self._handle_recall_command(query, message_id, lark_open_id)
                return

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
                else:  # pragma: no cover — unreachable; '' is caught by _handle_setgoal_command guard
                    await self.ws.send_message("❌ 用法: /setgoal <goal_id>\n先用 /goals 查看所有目标及其ID", message_id, [], lark_open_id)
                return

            # Check for /newgoal <description> command
            if content.strip().startswith("/newgoal "):
                desc = content.strip()[9:].strip()
                if desc:
                    await self._handle_newgoal_command(desc, message_id, lark_open_id)
                else:  # pragma: no cover — unreachable; '' desc caught by _handle_newgoal_command guard
                    await self.ws.send_message("❌ 用法: /newgoal <目标描述>\n例如: /newgoal 完成用户登录功能", message_id, [], lark_open_id)
                return

            # Check for /delgoal <id> command
            if content.strip().startswith("/delgoal "):
                parts = content.strip().split(" ", 1)
                if len(parts) > 1:
                    goal_id = parts[1].strip()
                    await self._handle_delgoal_command(goal_id, message_id, lark_open_id)
                else:  # pragma: no cover — unreachable; '' is caught by _handle_delgoal_command guard
                    await self.ws.send_message("❌ 用法: /delgoal <goal_id>", message_id, [], lark_open_id)
                return

            # Check for /deltask <id> command
            if content.strip().startswith("/deltask "):
                parts = content.strip().split(" ", 1)
                if len(parts) > 1:
                    task_id = parts[1].strip()
                    await self._handle_deltask_command(task_id, message_id, lark_open_id)
                else:  # pragma: no cover — unreachable; '' is caught by _handle_deltask_command guard
                    await self.ws.send_message("❌ 用法: /deltask <task_id>", message_id, [], lark_open_id)
                return

            # User message — if priority, insert at front of queue (don't execute now)
            if is_priority and self.queue_manager:
                # Enqueue for autonomous execution (user's command goes to front)
                active_goals = self.profile.get_active_goals()
                if active_goals:
                    goal_id = active_goals[0].id
                else:
                    # No active goal — create one from this user task so the runner
                    # can match the task to a goal and execute it
                    adhoc_goal = self.profile.add_goal(content[:100])
                    goal_id = adhoc_goal.id
                    logger.info(f"Created ad-hoc goal {goal_id} for user task")
                self.queue_manager.add_user_task(content, goal_id)
                logger.info(f"User task enqueued at front: {content[:50]}...")
                # Acknowledge receipt
                if message_id:
                    ack_resp = "✅ 收到！任务已排到最前面，我会尽快完成。"
                    await self.ws.send_message(ack_resp, message_id, [], lark_open_id)
                return

            # Execute with Claude
            logger.info("Calling Claude executor...")

            # Build context from conversation memory and persistent memory
            context_addon = ""
            if self.memory:
                resume_context = self.memory.get_context_for_resume()
                if resume_context:
                    context_addon = f"\n\n{resume_context}\n"

            # Include recent conversation history
            recent_history = self.conversation_memory.get_formatted(n=5)
            if recent_history:
                context_addon += f"\n\n{recent_history}\n"

            # Execute with enhanced context
            full_prompt = content + context_addon if context_addon else content
            response, images, raw_data = await self.claude.execute(full_prompt)
            logger.info(f"Claude response: {response[:100]}...")

            # Add assistant response to conversation memory
            self.conversation_memory.add_assistant(response)

            # Extract token usage from raw JSON data
            usage = None
            if raw_data and 'usage' in raw_data:
                usage = self.token_tracker._build_usage(raw_data['usage'])
                if usage:
                    self.profile.record_usage(usage.total_tokens)
                    logger.info(f"Token usage recorded: {usage.total_tokens}")

            # Detect rate limit from response text
            is_rate_limited = self.token_tracker._detect_rate_limit(response)

            if is_rate_limited or "429" in response:
                self.profile.set_rate_limited(datetime.now())
                logger.warning("Rate limit detected!")

            if images:
                logger.info(f"Claude generated {len(images)} images")

            # Send response back to server
            if message_id:
                success = await asyncio.wait_for(
                    self.ws.send_message(response, message_id, images, lark_open_id),
                    timeout=30
                )
                logger.info(f"Response sent: {success}")
                if success and self.on_message_sent:
                    await self.on_message_sent(message_id)
        except Exception as e:
            logger.error(f"Error in handle_message: {e}", exc_info=True)

    async def handle_profile_data_message(self, message: Message):
        """Handle profile_data messages sent directly via WebSocket (not via queue)

        Received as: {"type": "profile_data", "profession": ..., "situation": ..., ...}
        No message_id that would cause echo-back to user.

        After saving profile, immediately triggers goal decomposition and
        starts the autonomous execution loop.
        """
        try:
            profession = message.data.get("profession", "")
            situation = message.data.get("situation", "")
            short_term_goal = message.data.get("short_term_goal", "")
            what_better_means = message.data.get("what_better_means", "")
            lark_open_id = message.data.get("lark_open_id")

            logger.info(f"Profile data received: profession={profession}, goal={short_term_goal[:30]}...")

            # Update profile fields in-place
            self.profile.profile.profession = profession
            self.profile.profile.situation = situation
            self.profile.profile.short_term_goal = short_term_goal
            self.profile.profile.what_better_means = what_better_means
            self.profile.profile.onboarding_completed = True
            self.profile.profile.updated_at = datetime.now().isoformat()
            self.profile._save()

            logger.info(f"Profile saved. onboarding_completed={self.profile.profile.onboarding_completed}")

            # Create initial goal from short_term_goal
            goal = None
            if short_term_goal:
                goal = self.profile.add_goal(short_term_goal)
                logger.info(f"Created initial goal: {goal.id} - {short_term_goal}")

            # Enable autonomous mode and start runner if not running
            self.autonomous_mode = True
            logger.info("Autonomous mode enabled")
            if self.on_autonomous_start:
                self.on_autonomous_start()
                logger.info("Autonomous runner started via callback")

            # Immediately decompose goal and add tasks to queue
            if goal and hasattr(self, 'goal_engine') and self.goal_engine:
                logger.info(f"Decomposing goal {goal.id} into tasks...")
                tasks = await self.goal_engine.decompose_goal(goal.id)
                if tasks:
                    logger.info(f"Decomposed into {len(tasks)} tasks, queueing...")
                    for task in tasks:
                        self.queue_manager.queue.enqueue(task, user_initiated=False)
                    logger.info(f"Queued {len(tasks)} tasks for autonomous execution")
                else:
                    logger.warning(f"Goal decomposition returned no tasks")

            # Note: we don't send a message back to server here because
            # profile_data messages don't carry a Lark message_id (intentionally)
            # The server already sent the "✅ 初始化完成" message directly to the user

        except Exception as e:
            logger.error(f"Error handling profile_data message: {e}", exc_info=True)

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

    async def _handle_memory_command(self, message_id: str, lark_open_id: str = None):
        """Handle /memory command - show memory stats and recent entries"""
        if not self.memory:
            response = "❌ Memory not available"
            await self.ws.send_message(response, message_id, [], lark_open_id)
            return

        stats = self.memory.get_stats()
        recent = self.memory.get_recent(limit=5)

        lines = ["🧠 **Memory Status**\n"]
        lines.append(f"Session: {stats['session_id']}")
        lines.append(f"Total entries: {stats['total_entries']}")
        lines.append(f"Categories: {stats['categories']}")
        lines.append(f"Tags: {', '.join(stats['all_tags'][:10]) or 'none'}")
        lines.append("\n**Recent Entries:**\n")

        for entry in recent:
            lines.append(f"[{entry.category}] {entry.content[:80]}...")

        response = "\n".join(lines)
        await self.ws.send_message(response, message_id, [], lark_open_id)

    async def _handle_recall_command(self, query: str, message_id: str, lark_open_id: str = None):
        """Handle /recall <query> command - search memory"""
        if not self.memory:
            response = "❌ Memory not available"
            await self.ws.send_message(response, message_id, [], lark_open_id)
            return

        results = self.memory.search(query, limit=5)

        if not results:
            response = f"🔍 No memories found for: {query}"
        else:
            lines = [f"🔍 **Memory Search: {query}**\n"]
            for entry in results:
                lines.append(f"[{entry.category}] {entry.content[:100]}...")
                lines.append(f"   {entry.timestamp}\n")
            response = "\n".join(lines)

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
        if not goal_id:
            response = "❌ 用法: /setgoal <goal_id>\n先用 /goals 查看所有目标及其ID"
            await self.ws.send_message(response, message_id, [], lark_open_id)
            return
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

    async def _handle_newgoal_command(self, description: str, message_id: str, lark_open_id: str = None):
        """Handle /newgoal <description> - create a new goal and decompose it"""
        if not description:
            response = "❌ 用法: /newgoal <目标描述>\n例如: /newgoal 完成用户登录功能"
            await self.ws.send_message(response, message_id, [], lark_open_id)
            return
        goal = self.profile.add_goal(description)
        response = f"🎯 目标已创建:\n[{goal.id[:8]}] {description}\n\n正在分解任务..."
        await self.ws.send_message(response, message_id, [], lark_open_id)
        logger.info(f"Created new goal: {goal.id} - {description}")

        # Decompose goal into tasks using MiniMax
        if self.goal_engine:
            tasks = await self.goal_engine.decompose_goal(goal.id)
            if tasks:
                # Enqueue tasks so autonomous runner can pick them up
                if self.queue_manager:
                    for task in tasks:
                        self.queue_manager.queue.enqueue(task, user_initiated=False)
                    logger.info(f"Enqueued {len(tasks)} tasks for goal {goal.id}")
                await self.ws.send_message(
                    f"✅ 已分解为 {len(tasks)} 个任务:\n" +
                    "\n".join(f"{i+1}. {t.description[:50]}" for i, t in enumerate(tasks[:10])),
                    message_id, [], lark_open_id
                )
            else:
                await self.ws.send_message("⚠️ 任务分解失败，请稍后重试。", message_id, [], lark_open_id)

    async def _handle_delgoal_command(self, goal_id: str, message_id: str, lark_open_id: str = None):
        """Handle /delgoal <id> - delete a goal and all its tasks"""
        # Find goal
        goal = None
        for g in self.profile.goals:
            if g.id == goal_id:
                goal = g
                break
        if not goal:
            await self.ws.send_message(f"❌ 未找到目标 {goal_id[:8]}", message_id, [], lark_open_id)
            return

        # Remove tasks belonging to this goal
        tasks = self.profile.get_tasks_for_goal(goal_id)
        for t in tasks:
            self.profile.tasks.remove(t)
        # Remove goal
        self.profile.goals.remove(goal)
        # If this was active goal, switch to another
        if self.profile.active_goal_id == goal_id:
            active = self.profile.get_active_goals()
            self.profile.active_goal_id = active[0].id if active else None
        self.profile._save()

        await self.ws.send_message(
            f"🗑️ 已删除目标 [{goal_id[:8]}] 及其 {len(tasks)} 个任务",
            message_id, [], lark_open_id
        )
        logger.info(f"Deleted goal: {goal_id}")

    async def _handle_deltask_command(self, task_id: str, message_id: str, lark_open_id: str = None):
        """Handle /deltask <id> - delete a pending task"""
        task = None
        for t in self.profile.tasks:
            if t.id == task_id:
                task = t
                break
        if not task:
            await self.ws.send_message(f"❌ 未找到任务 {task_id[:8]}", message_id, [], lark_open_id)
            return

        if task.status.value not in ("pending", "failed"):
            await self.ws.send_message(f"❌ 任务 {task_id[:8]} 正在执行或已完成，无法删除。", message_id, [], lark_open_id)
            return

        self.profile.tasks.remove(task)
        # Also remove from goal's task_ids
        for g in self.profile.goals:
            if task.id in g.task_ids:
                g.task_ids.remove(task.id)
        self.profile._save()

        await self.ws.send_message(f"🗑️ 已删除任务 [{task_id[:8]}]: {task.description[:50]}", message_id, [], lark_open_id)
        logger.info(f"Deleted task: {task_id}")

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
        # Try to use tools.py first
        tool_class = get_tool(tool_name)
        if tool_class:
            return await self._execute_from_tools(tool_name, params)

        # Fall back to built-in tools
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

    async def _execute_from_tools(self, tool_name: str, params: dict) -> str:
        """Execute a tool from tools.py"""
        try:
            tool_class = get_tool(tool_name)
            if not tool_class:
                return f"Tool not found: {tool_name}"

            # Get static method or class
            tool = tool_class

            # Map common tool names to methods
            if tool_name == "file":
                op = params.get("operation", "read")
                if op == "read":
                    return tool.read(params.get("path", ""))
                elif op == "write":
                    return str(tool.write(params.get("path", ""), params.get("content", "")))
                elif op == "append":
                    return str(tool.append(params.get("path", ""), params.get("content", "")))
                elif op == "find":
                    result = tool.find(params.get("pattern", "*"), params.get("path", "."))
                    return "\n".join(result) if result else "No matches found"
                elif op == "count_lines":
                    return str(tool.count_lines(params.get("path", "")))
                elif op == "search":
                    results = tool.search(params.get("pattern", ""), params.get("path", "."), params.get("file_type", "*"))
                    if not results:
                        return "No matches found"
                    return "\n".join([f"{r['file']}:{r['line']}: {r['content']}" for r in results[:20]])

            elif tool_name == "scraper":
                url = params.get("url", "")
                if not url:
                    return "URL required"
                method = params.get("method", "fetch")
                if method == "fetch":
                    result = tool.fetch(url, params.get("headers"), params.get("timeout", 30))
                    return f"Status: {result['status']}\nURL: {result['url']}\n\n{result['content'][:2000]}"
                elif method == "fetch_json":
                    result = tool.fetch_json(url, params.get("headers"), params.get("timeout", 30))
                    return str(result)[:2000]
                elif method == "extract_links":
                    html = params.get("html", "")
                    return "\n".join(tool.extract_links(html, url))
                elif method == "extract_emails":
                    return "\n".join(tool.extract_emails(params.get("text", "")))
                elif method == "extract_ips":
                    return "\n".join(tool.extract_ips(params.get("text", "")))

            elif tool_name == "api":
                return str(tool.call(
                    params.get("url", ""),
                    params.get("method", "GET"),
                    params.get("headers"),
                    params.get("params"),
                    params.get("json_data"),
                    params.get("timeout", 30)
                ))[:2000]

            elif tool_name == "process":
                if params.get("operation") == "kill":
                    return str(tool.kill(params.get("pid", 0), params.get("signal", 15)))
                elif params.get("operation") == "is_running":
                    return str(tool.is_running(params.get("pattern", "")))
                else:
                    processes = tool.list(params.get("pattern", ""))
                    if not processes:
                        return "No processes found"
                    return "\n".join([f"PID {p['pid']}: {p['command'][:60]}" for p in processes[:20]])

            elif tool_name == "system":
                op = params.get("operation", "disk_usage")
                if op == "disk_usage":
                    return str(tool.disk_usage(params.get("path", "/")))
                elif op == "memory":
                    return str(tool.memory())
                elif op == "cpu_load":
                    return str(tool.cpu_load())

            elif tool_name == "git":
                op = params.get("operation", "status")
                if op == "status":
                    return tool.status()
                elif op == "diff":
                    return tool.diff(params.get("file", ""))
                elif op == "log":
                    commits = tool.log(params.get("limit", 10))
                    return "\n".join([f"{c['hash']} | {c['message'][:50]}" for c in commits])
                elif op == "branch":
                    return tool.branch()

            elif tool_name == "docker":
                op = params.get("operation", "ps")
                if op == "ps":
                    containers = tool.ps(params.get("all", False))
                    if not containers:
                        return "No containers found"
                    return "\n".join([f"{c['id'][:12]} | {c['name']} | {c['status']}" for c in containers])
                elif op == "logs":
                    return tool.logs(params.get("container", ""), params.get("lines", 50))
                elif op == "restart":
                    return str(tool.restart(params.get("container", "")))
                elif op == "status":
                    return str(tool.status())

            elif tool_name == "database":
                op = params.get("operation", "query")
                if op == "query":
                    result = tool.query(params.get("db_path", ""), params.get("sql", ""))
                    return str(result)[:2000]
                elif op == "execute":
                    return str(tool.execute(params.get("db_path", ""), params.get("sql", "")))
                elif op == "list_tables":
                    return "\n".join(tool.list_tables(params.get("db_path", "")))
                elif op == "table_info":
                    return str(tool.table_info(params.get("db_path", ""), params.get("table", "")))
                elif op == "create_table":
                    return str(tool.create_table(
                        params.get("db_path", ""),
                        params.get("table", ""),
                        params.get("columns", {})
                    ))

            elif tool_name == "image":
                op = params.get("operation", "info")
                if op == "info":
                    return str(tool.info(params.get("path", "")))
                elif op == "resize":
                    return str(tool.resize(
                        params.get("path", ""),
                        params.get("output", ""),
                        params.get("width", 100),
                        params.get("height", 100)
                    ))
                elif op == "thumbnail":
                    return str(tool.thumbnail(
                        params.get("path", ""),
                        params.get("output", ""),
                        params.get("max_size", 256)
                    ))
                elif op == "convert":
                    return str(tool.convert(
                        params.get("input_path", ""),
                        params.get("output_path", ""),
                        params.get("format", "PNG")
                    ))
                elif op == "compress":
                    return str(tool.compress(
                        params.get("path", ""),
                        params.get("output", ""),
                        params.get("quality", 85)
                    ))

            elif tool_name == "notification":
                op = params.get("operation", "push")
                if op == "email":
                    return str(tool.send_email(
                        params.get("to", ""),
                        params.get("subject", ""),
                        params.get("body", ""),
                        params.get("smtp_host", "localhost"),
                        params.get("smtp_port", 25),
                        params.get("from_addr", "cc-claw@localhost")
                    ))
                elif op == "push":
                    return str(tool.push(
                        params.get("title", ""),
                        params.get("body", ""),
                        params.get("priority", "normal")
                    ))
                elif op == "slack":
                    return str(tool.slack_webhook(
                        params.get("webhook_url", ""),
                        params.get("text", ""),
                        params.get("channel", "")
                    ))

            elif tool_name == "code_analysis":
                op = params.get("operation", "count_lines")
                if op == "count_lines":
                    return str(tool.count_lines(
                        params.get("path", "."),
                        params.get("extensions", "py,js,ts,java,cpp,c,go,rs")
                    ))
                elif op == "find_functions":
                    return str(tool.find_functions(
                        params.get("path", "."),
                        params.get("language", "python")
                    ))
                elif op == "complexity":
                    return str(tool.complexity(
                        params.get("path", "."),
                        params.get("language", "python")
                    ))
                elif op == "dependencies":
                    return str(tool.dependencies(params.get("path", ".")))

            elif tool_name == "monitor":
                op = params.get("operation", "health_check")
                if op == "check_disk":
                    return str(tool.check_disk(params.get("threshold", 90)))
                elif op == "check_memory":
                    return str(tool.check_memory(params.get("threshold", 90)))
                elif op == "check_cpu":
                    return str(tool.check_cpu(params.get("threshold", 80.0)))
                elif op == "check_port":
                    return str(tool.check_port(
                        params.get("port", 80),
                        params.get("host", "localhost")
                    ))
                elif op == "check_url":
                    return str(tool.check_url(
                        params.get("url", ""),
                        params.get("timeout", 10)
                    ))
                elif op == "health_check":
                    return str(tool.health_check(params.get("port", 3000)))

            return f"Tool {tool_name} exists but operation not supported"

        except Exception as e:
            return f"Error executing tool {tool_name}: {e}"

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
