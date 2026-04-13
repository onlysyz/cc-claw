"""CC-Claw Client Daemon Module"""

import asyncio
import logging
import signal
import sys
from typing import Optional

from .config import ClientConfig
from .websocket import WebSocketManager
from .claude import ClaudeExecutor
from .handler import MessageHandler
from .scheduler import TaskScheduler
from .profile import ProfileManager
from .goal_engine import GoalEngine
from .task_queue import QueueManager
from .retry import get_retry_manager, RetryConfig, RetryStrategy, MaxRetriesExceeded
from .memory import PersistentMemory


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CCClawDaemon:
    """CC-Claw daemon process"""

    def __init__(self, config: ClientConfig):
        self.config = config
        self.ws_manager: Optional[WebSocketManager] = None
        self.claude: Optional[ClaudeExecutor] = None
        self.handler: Optional[MessageHandler] = None
        self.scheduler: Optional[TaskScheduler] = None
        self.profile: Optional[ProfileManager] = None
        self.goal_engine: Optional[GoalEngine] = None
        self.queue_manager: Optional[QueueManager] = None
        self._running = False
        self._task_checker_task: Optional[asyncio.Task] = None
        self._token_checker_task: Optional[asyncio.Task] = None
        self._autonomous_runner_task: Optional[asyncio.Task] = None
        # New features
        self.memory: Optional[PersistentMemory] = None
        self.retry_manager = get_retry_manager()

    async def start(self):
        """Start the daemon"""
        if self._running:
            logger.warning("Daemon already running")
            return

        logger.info("Starting CC-Claw daemon...")

        # Initialize scheduler
        self.scheduler = TaskScheduler()
        logger.info("Task scheduler initialized")

        # Initialize profile manager
        self.profile = ProfileManager()
        if self.profile.is_onboarding_complete():
            logger.info(f"Profile loaded: {self.profile.profile.profession}")
        else:
            logger.info("Profile not onboarded yet — will start when configured")

        # Initialize persistent memory for context retention
        self.memory = PersistentMemory()
        logger.info("Persistent memory initialized")

        # Check Claude CLI availability
        self.claude = ClaudeExecutor(self.config)
        if not self.claude.is_available():
            logger.error("Claude CLI not found. Please install it first.")
            logger.info(f"Expected path: {self.config.claude_path}")
            sys.exit(1)

        logger.info(f"Claude CLI version: {self.claude.get_version()}")

        # Initialize goal engine
        self.goal_engine = GoalEngine(self.config, self.profile, self.claude)

        # Initialize queue manager
        self.queue_manager = QueueManager(self.profile)

        # Check configuration
        if not self.config.device_id or not self.config.device_token:
            logger.error("Device not configured. Please run 'cc-claw pair' first.")
            sys.exit(1)

        # Initialize WebSocket
        self.ws_manager = WebSocketManager(self.config)

        # Initialize handler with scheduler, profile, goal_engine, and queue manager
        self.handler = MessageHandler(
            self.ws_manager,
            self.claude,
            self.config,
            self.scheduler,
            self.profile,
            self.queue_manager,
            self.goal_engine,
            self.memory,
            on_autonomous_start=lambda: self._start_autonomous_runner_if_needed(),
        )

        # Register message handlers
        self.ws_manager.on("message", self.handler.handle_message)
        self.ws_manager.on("error", self.handler.handle_error)
        self.ws_manager.on("delivered", self.handler.handle_delivered)
        self.ws_manager.on("profile_data", self.handler.handle_profile_data_message)

        # Connect and start listening
        if await self.ws_manager.connect():
            if await self.ws_manager.register():
                logger.info("Registered with server")
                self._running = True

                # Start listening in background
                asyncio.create_task(self.ws_manager.listen())

                # Start task checker in background
                self._task_checker_task = asyncio.create_task(self._task_checker())

                # Start token budget checker in background
                self._token_checker_task = asyncio.create_task(self._token_checker())

                # If profile is already onboarded (daemon restart), restore queue from pending tasks
                if self.profile.is_onboarding_complete():
                    pending = self.profile.get_pending_tasks()
                    for task in pending:
                        self.queue_manager.queue.enqueue(task, user_initiated=False)
                    logger.info(f"Restored {len(pending)} pending tasks to queue")
                    # Start autonomous runner
                    self._start_autonomous_runner_if_needed()
                else:
                    logger.info("Autonomous runner will start after onboarding completes")

                # Keep running
                while self._running:
                    await asyncio.sleep(1)
            else:
                logger.error("Failed to register with server")
                sys.exit(1)
        else:
            logger.error("Failed to connect to server")
            sys.exit(1)

    async def _token_checker(self):
        """Background task to check token usage and handle rate limits
        - Every 1 hour, check if tokens have been refreshed
        - When rate limited for >1 hour, auto-clear and let runner retry
        """
        import time
        logger.info("Token budget checker started")
        while self._running:
            try:
                await asyncio.sleep(3600)  # Check every hour

                if not self.profile:
                    continue

                tb = self.profile.token_budget

                # If rate limited, check if we've been rate limited for >1 hour
                if tb.is_rate_limited:
                    if tb.rate_limit_since:
                        elapsed = time.time() - tb.rate_limit_since
                        if elapsed >= 3600:
                            logger.info(f"Rate limited for {elapsed/3600:.1f}h — auto-clearing to retry")
                            self.profile.clear_rate_limit()
                        else:
                            logger.info(f"Still rate limited ({elapsed/60:.0f}min elapsed, backoff level {tb.backoff_level})")
                    continue

                # Check if daily usage was reset (new day = token refresh for some plans)
                old_reset_date = tb.last_reset_date
                tb.check_daily_reset()
                if tb.last_reset_date != old_reset_date:
                    logger.info(f"New day detected ({tb.last_reset_date}) — token budget may have refreshed")

                logger.info(f"Token check: total_used={tb.total_used}, daily_used={tb.daily_used}")

            except Exception as e:
                logger.error(f"Error in token checker: {e}")

    def _start_autonomous_runner_if_needed(self):
        """Start the autonomous runner if not already running (called from handler callback)"""
        if self._autonomous_runner_task is not None and not self._autonomous_runner_task.done():
            logger.info("Autonomous runner already running")
            return
        logger.info("Starting autonomous runner (triggered by profile save)")
        loop = asyncio.get_event_loop()
        self._autonomous_runner_task = loop.create_task(self._autonomous_runner())

    async def _autonomous_runner(self):
        """Autonomous goal execution loop
        - While autonomous_mode is True and goals exist
        - Pop top pending task, execute it
        - If no tasks, decompose goal
        - On 429/rate limit, backoff and retry
        """
        logger.info("Autonomous runner started")
        loop_count = 0

        while self._running:
            try:
                loop_count += 1

                # Check if autonomous mode is enabled
                if not self.handler.autonomous_mode:
                    await asyncio.sleep(5)
                    continue

                # Check token budget — if rate limited, apply backoff
                tb = self.profile.token_budget
                if tb.is_rate_limited:
                    wait_seconds = min(60 * (2 ** (tb.backoff_level - 1)) if tb.backoff_level > 0 else 60, 3600)
                    logger.info(f"Rate limited, backing off for {wait_seconds}s")
                    await asyncio.sleep(wait_seconds)
                    continue

                # Get active goal (the one we're currently working on)
                goal = self.profile.get_active_goal()
                if not goal:
                    # No active goal — check if queue has tasks with an existing goal
                    qt = await self.queue_manager.get_next_task()
                    if qt and qt.task.goal_id:
                        # Find the goal for this task
                        for g in self.profile.goals:
                            if g.id == qt.task.goal_id:
                                goal = g
                                self.profile.set_active_goal(g.id)
                                logger.info(f"Resuming goal: {g.description}")
                                break
                        if not goal:
                            # Put task back and suggest new goal
                            self.queue_manager.queue.enqueue(qt.task, user_initiated=False)
                            qt = None

                if not goal:
                    # No active goals — ask Claude to suggest one based on context
                    if loop_count % 10 == 0:  # Don't spam every iteration
                        logger.info("No active goals, asking Claude to suggest a goal...")
                        suggested_goal = await self._suggest_new_goal()
                        if suggested_goal:
                            goal = self.profile.add_goal(suggested_goal)
                            logger.info(f"Claude suggested goal: {goal.description}")
                            # Auto-decompose and enqueue
                            new_tasks = await self.goal_engine.decompose_goal(goal.id)
                            if new_tasks:
                                for task in new_tasks:
                                    self.queue_manager.queue.enqueue(task, user_initiated=False)
                                logger.info(f"Enqueued {len(new_tasks)} tasks")
                        else:
                            if loop_count % 60 == 0:
                                logger.info("No goal suggested, waiting...")
                            await asyncio.sleep(5)
                            continue
                    else:
                        await asyncio.sleep(5)
                        continue

                if not goal:
                    await asyncio.sleep(5)
                    continue

                logger.info(f"Working on goal: {goal.description}")

                # Check if goal needs decomposition
                pending = [t for t in self.profile.get_tasks_for_goal(goal.id)
                           if t.status.value == "pending"]
                if not pending:
                    logger.info(f"Goal '{goal.description}' has no tasks — decomposing...")
                    new_tasks = await self.goal_engine.decompose_goal(goal.id)
                    if not new_tasks:
                        logger.warning(f"Could not decompose goal {goal.id}, waiting...")
                        await asyncio.sleep(30)
                        continue
                    # Enqueue newly created tasks
                    for task in new_tasks:
                        self.queue_manager.queue.enqueue(task, user_initiated=False)
                    logger.info(f"Enqueued {len(new_tasks)} new tasks for goal '{goal.description}'")
                    continue

                # Pop top task from queue (priority queue handles user tasks first)
                qt = await self.queue_manager.get_next_task()
                if not qt:
                    await asyncio.sleep(5)
                    continue

                self.queue_manager.queue.mark_executing(qt)
                logger.info(f"[AUTONOMOUS] Executing task: {qt.task.description[:60]}...")
                await self._execute_autonomous_task(qt)

                # After task execution, check if we need to continue
                goal = self.profile.get_active_goal()
                if goal:
                    pending = [t for t in self.profile.get_tasks_for_goal(goal.id)
                               if t.status.value == "pending"]
                    if not pending:
                        # Goal complete — suggest new goal immediately
                        logger.info(f"Goal '{goal.description}' complete, suggesting new goal...")
                        suggested = await self._suggest_new_goal()
                        if suggested:
                            new_goal = self.profile.add_goal(suggested)
                            logger.info(f"New goal suggested: {new_goal.description}")
                            tasks = await self.goal_engine.decompose_goal(new_goal.id)
                            if tasks:
                                for t in tasks:
                                    self.queue_manager.queue.enqueue(t, user_initiated=False)
                                logger.info(f"Enqueued {len(tasks)} new tasks")
                        else:
                            logger.info("No goal suggested, will retry later")

            except Exception as e:
                logger.error(f"Error in autonomous runner: {e}", exc_info=True)
                await asyncio.sleep(10)

    async def _execute_autonomous_task(self, qt):
        """Execute a task in autonomous mode and handle result"""
        from .profile import TaskStatus

        task = qt.task
        goal_id = task.goal_id

        # Find the goal
        goal = None
        for g in self.profile.goals:
            if g.id == goal_id:
                goal = g
                break

        # Track outcome for notification
        notify_status = "failed"
        notify_msg = ""
        goal_complete = False

        try:
            # Execute with Claude (with retry on transient errors)
            retry_config = RetryConfig(
                max_retries=3,
                base_delay=2.0,
                max_delay=60.0,
                strategy=RetryStrategy.EXPONENTIAL_WITH_JITTER,
                retry_on=(ConnectionError, TimeoutError),
            )

            response, images, raw_data = await self.retry_manager.execute(
                f"claude_task_{task.id[:8]}",
                self.claude.execute,
                task.description,
                config=retry_config,
                circuit_breaker_name="claude_api"
            )

            # Check for rate limit
            is_rate_limited = (
                "429" in response or
                "rate limit" in response.lower() or
                "too many requests" in response.lower()
            )

            if is_rate_limited:
                # Requeue at front for retry later, apply backoff
                task.status = TaskStatus.PENDING
                self.queue_manager.requeue_front(qt)
                wait = self.profile.increment_backoff()
                logger.warning(f"Rate limited, requeued task {task.id[:8]}, backing off {wait}s")

                if self.memory:
                    self.memory.add_error_recovery("Rate limit (429)", f"Backoff {wait}s, will retry")

                self.queue_manager.queue.mark_done()
                await asyncio.sleep(wait)
                return

            # Parse token usage from raw JSON data
            from .token_tracker import TokenTracker
            tracker = TokenTracker()
            if raw_data and 'usage' in raw_data:
                usage = tracker._build_usage(raw_data['usage'])
                if usage:
                    self.profile.record_usage(usage.total_tokens)
                    logger.info(f"Token usage: {usage.total_tokens}")

            # Summarize result
            result_summary = response[:200].replace('\n', ' ')

            # Complete the task
            self.profile.complete_task(task.id, result_summary=result_summary)
            logger.info(f"Task completed: {task.id[:8]} — {result_summary[:50]}...")

            if self.memory:
                self.memory.add_context_snapshot(task.description, "", result_summary)

            # Check if goal is complete
            if goal:
                remaining = [t for t in self.profile.get_tasks_for_goal(goal.id)
                             if t.status.value == "pending"]
                if not remaining:
                    logger.info(f"Goal '{goal.description}' — all tasks done!")
                    self.profile.complete_goal(goal.id)
                    goal_complete = True
                    if self.ws_manager and self.ws_manager.is_connected:
                        await self.ws_manager.send({
                            "type": "goal_complete",
                            "goal_id": goal.id,
                            "goal_description": goal.description,
                        })

            notify_status = "completed"
            task_num = len([t for t in self.profile.get_tasks_for_goal(goal_id)
                           if t.status.value == "completed"])
            total = len(self.profile.get_tasks_for_goal(goal_id))
            notify_msg = f"✅ Task done [{task_num}/{total}]\n📋 {task.description}\n📤 {result_summary}"

        except MaxRetriesExceeded as e:
            logger.error(f"Task {task.id[:8]} failed after all retries: {e}")
            self.profile.fail_task(task.id, str(e))
            if self.memory:
                self.memory.add_error_recovery("Task execution failed after retries", str(e))
            notify_msg = f"❌ Task failed (max retries)\n📋 {task.description}\n💥 {e}"

        except Exception as e:
            logger.error(f"Error executing autonomous task {task.id[:8]}: {e}", exc_info=True)
            self.profile.fail_task(task.id, str(e))
            if self.memory:
                self.memory.add_error_recovery("Task execution failed", str(e))
            notify_msg = f"❌ Task failed\n📋 {task.description}\n💥 {e}"

        finally:
            self.queue_manager.queue.mark_done()

        # Always send notification when task ends (success or failure)
        if self.ws_manager and self.ws_manager.is_connected and notify_msg:
            success = await self.ws_manager.send_notification(notify_msg)
            if success:
                logger.info(f"Notification sent: {notify_msg[:50]}...")
            else:
                logger.warning(f"Failed to send notification")
        elif notify_msg:
            logger.warning(f"Notification not sent: ws_manager={self.ws_manager is not None}, connected={getattr(self.ws_manager, 'is_connected', False)}")

    async def _suggest_new_goal(self) -> Optional[str]:
        """Ask Claude to suggest a new goal based on user's context and current situation"""
        p = self.profile.profile
        if not p or not p.onboarding_completed:
            logger.info("Profile not onboarded, cannot suggest goal")
            return None

        # Build context from memory and profile
        memory_context = ""
        if self.memory:
            recent = self.memory.get_recent(limit=5)
            if recent:
                memory_context = "Recent work:\n" + "\n".join(f"- {e.content[:100]}" for e in recent) + "\n\n"

        prompt = f"""You are an AI coding assistant. Based on the user's context, suggest ONE concrete goal they should work on.

User Context:
- Profession: {p.profession}
- Current Situation: {p.situation}
- Short-term Goal: {p.short_term_goal}
- What 'Better' Means: {p.what_better_means}

{memory_context}Current project state: Review what files exist in the working directory and determine what would be most valuable to work on next.

Based on the context and project state, suggest ONE specific, actionable goal. This should be something achievable in 1-3 coding sessions.

Return format (MUST be valid JSON):
{{"goal": "your goal description here"}}

No markdown, no explanation, just the JSON object."""

        try:
            response, _, _ = await self.claude.execute(prompt)

            if response:
                # Parse JSON response
                import json
                try:
                    # Find JSON in response
                    json_start = response.find('{')
                    if json_start != -1:
                        data = json.loads(response[json_start:])
                        if isinstance(data, dict) and "goal" in data:
                            goal_text = data["goal"].strip()
                            if goal_text:
                                return goal_text
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse goal suggestion: {e}")

            logger.warning(f"No valid goal in response: {response[:100] if response else 'empty'}")
            return None

        except Exception as e:
            logger.error(f"Error suggesting new goal: {e}")
            return None

    async def _task_checker(self):
        """Background task to check and execute due tasks"""
        logger.info("Task checker started")
        while self._running:
            try:
                due_tasks = self.scheduler.get_due_tasks()
                for task in due_tasks:
                    logger.info(f"Executing due task: {task.id[:8]}")
                    asyncio.create_task(self._execute_task(task))
                # Also cleanup old completed tasks
                self.scheduler.remove_completed_tasks(older_than_hours=24)
            except Exception as e:
                logger.error(f"Error in task checker: {e}")

            await asyncio.sleep(10)  # Check every 10 seconds

    async def _execute_task(self, task):
        """Execute a scheduled task"""
        self.scheduler.mark_executing(task.id)

        try:
            logger.info(f"Executing scheduled task: {task.command}")

            # Execute the command
            response, images, raw_data = await self.claude.execute(task.command)

            # Track token usage
            if raw_data and 'usage' in raw_data:
                tracker = TokenTracker()
                usage = tracker._build_usage(raw_data['usage'])
                if usage:
                    self.profile.record_usage(usage.total_tokens)
                    logger.info(f"Token usage: {usage.total_tokens}")

            # Format the response
            result_msg = f"🔔 定时任务完成 [{task.id[:8]}]\n\n📋 命令:\n{task.command}\n\n📤 结果:\n{response}"

            # Send result to server (with lark_open_id if present)
            await self.ws_manager.send_message(result_msg, task.original_message_id, images, task.lark_open_id)

            logger.info(f"Task {task.id[:8]} completed and result sent")

        except Exception as e:
            logger.error(f"Error executing task {task.id[:8]}: {e}")
            error_msg = f"🔔 定时任务失败 [{task.id[:8]}]\n\n命令: {task.command}\n\n错误: {e}"
            await self.ws_manager.send_message(error_msg, task.original_message_id, [], task.lark_open_id)

        finally:
            self.scheduler.mark_completed(task.id)

    async def stop(self):
        """Stop the daemon"""
        logger.info("Stopping CC-Claw daemon...")
        self._running = False

        if self._task_checker_task:
            self._task_checker_task.cancel()

        if self._token_checker_task:
            self._token_checker_task.cancel()

        if self._autonomous_runner_task:
            self._autonomous_runner_task.cancel()

        if self.ws_manager:
            await self.ws_manager.disconnect()

        logger.info("Daemon stopped")

    def run(self):
        """Run the daemon with signal handling"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Signal handling
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}")
            loop.create_task(self.stop())
            loop.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            loop.run_until_complete(self.start())
        except Exception as e:
            logger.error(f"Daemon error: {e}")
            sys.exit(1)
        finally:
            loop.close()
