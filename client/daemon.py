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

        # Initialize handler with scheduler, profile, and queue manager
        self.handler = MessageHandler(
            self.ws_manager,
            self.claude,
            self.config,
            self.scheduler,
            self.profile,
            self.queue_manager,
        )

        # Register message handlers
        self.ws_manager.on("message", self.handler.handle_message)
        self.ws_manager.on("error", self.handler.handle_error)
        self.ws_manager.on("delivered", self.handler.handle_delivered)
        self.ws_manager.on("profile", self.handler.handle_profile_message)

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

                # Start autonomous runner if profile is ready
                if self.profile.is_onboarding_complete():
                    self._autonomous_runner_task = asyncio.create_task(self._autonomous_runner())
                else:
                    logger.info("Skipping autonomous runner — onboarding not complete")

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
        - When rate limited, apply exponential backoff
        """
        logger.info("Token budget checker started")
        while self._running:
            try:
                await asyncio.sleep(3600)  # Check every hour

                if not self.profile:
                    continue

                tb = self.profile.token_budget

                # If rate limited, check if backoff period has passed
                if tb.is_rate_limited:
                    logger.info(f"Still rate limited (backoff level {tb.backoff_level})")
                    continue

                # Check if daily usage was reset (new day = token refresh for some plans)
                old_reset_date = tb.last_reset_date
                tb.check_daily_reset()
                if tb.last_reset_date != old_reset_date:
                    logger.info(f"New day detected ({tb.last_reset_date}) — token budget may have refreshed")
                    # Clear rate limit state if we were limited
                    self.profile.clear_rate_limit()

                logger.info(f"Token check: total_used={tb.total_used}, daily_used={tb.daily_used}")

            except Exception as e:
                logger.error(f"Error in token checker: {e}")

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
                    wait_seconds = 60 * (2 ** (tb.backoff_level - 1)) if tb.backoff_level > 0 else 60
                    logger.info(f"Rate limited, backing off for {wait_seconds}s")
                    await asyncio.sleep(wait_seconds)
                    continue

                # Get active goal (the one we're currently working on)
                goal = self.profile.get_active_goal()
                if not goal:
                    # No active goals yet — wait
                    if loop_count % 60 == 0:  # Log every ~5 min
                        logger.info("No active goals, waiting...")
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

                # Pop top task from queue (priority queue handles user tasks first)
                qt = await self.queue_manager.get_next_task()
                if not qt:
                    await asyncio.sleep(5)
                    continue

                self.queue_manager.queue.mark_executing(qt)
                logger.info(f"[AUTONOMOUS] Executing task: {qt.task.description[:60]}...")
                await self._execute_autonomous_task(qt)

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

        try:
            # Execute with Claude
            response, images = await self.claude.execute(task.description)

            # Check for rate limit
            is_rate_limited = (
                "429" in response or
                "rate limit" in response.lower() or
                "too many requests" in response.lower()
            )

            if is_rate_limited:
                # Requeue at front, wait, will be retried
                from .profile import Task
                task_obj = Task(
                    id=task.id,
                    description=task.description,
                    goal_id=task.goal_id,
                    status=TaskStatus.PENDING,
                )
                self.queue_manager.requeue_front(qt)
                wait = self.profile.increment_backoff()
                logger.warning(f"Rate limited, requeued task, backing off {wait}s")
                await asyncio.sleep(wait)
                self.queue_manager.queue.mark_done()
                return

            # Parse token usage
            from .token_tracker import TokenTracker
            tracker = TokenTracker()
            _, usage, _ = tracker.parse_json_response(response)
            if usage:
                self.profile.record_usage(usage.total_tokens)
                logger.info(f"Token usage: {usage.total_tokens}")

            # Summarize result
            result_summary = response[:200].replace('\n', ' ')

            # Complete the task
            self.profile.complete_task(task.id, result_summary=result_summary)
            logger.info(f"Task completed: {task.id[:8]} — {result_summary[:50]}...")

            # Check if goal is complete
            if goal:
                remaining = [t for t in self.profile.get_tasks_for_goal(goal.id)
                             if t.status.value == "pending"]
                if not remaining:
                    logger.info(f"Goal '{goal.description}' — all tasks done!")
                    self.profile.complete_goal(goal.id)
                    if self.ws_manager and self.ws_manager.is_connected:
                        msg = {
                            "type": "goal_complete",
                            "goal_id": goal.id,
                            "goal_description": goal.description,
                        }
                        await self.ws_manager.send(msg)

        except Exception as e:
            logger.error(f"Error executing autonomous task {task.id[:8]}: {e}")
            self.profile.fail_task(task.id, str(e))
        finally:
            self.queue_manager.queue.mark_done()

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
            response, images = await self.claude.execute(task.command)

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
