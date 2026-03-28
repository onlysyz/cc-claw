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
        self._running = False
        self._task_checker_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the daemon"""
        if self._running:
            logger.warning("Daemon already running")
            return

        logger.info("Starting CC-Claw daemon...")

        # Initialize scheduler
        self.scheduler = TaskScheduler()
        logger.info("Task scheduler initialized")

        # Check Claude CLI availability
        self.claude = ClaudeExecutor(self.config)
        if not self.claude.is_available():
            logger.error("Claude CLI not found. Please install it first.")
            logger.info(f"Expected path: {self.config.claude_path}")
            sys.exit(1)

        logger.info(f"Claude CLI version: {self.claude.get_version()}")

        # Check configuration
        if not self.config.device_id or not self.config.device_token:
            logger.error("Device not configured. Please run 'cc-claw pair' first.")
            sys.exit(1)

        # Initialize WebSocket
        self.ws_manager = WebSocketManager(self.config)

        # Initialize handler with scheduler
        self.handler = MessageHandler(
            self.ws_manager,
            self.claude,
            self.config,
            self.scheduler,
        )

        # Register message handlers
        self.ws_manager.on("message", self.handler.handle_message)
        self.ws_manager.on("error", self.handler.handle_error)
        self.ws_manager.on("delivered", self.handler.handle_delivered)

        # Connect and start listening
        if await self.ws_manager.connect():
            if await self.ws_manager.register():
                logger.info("Registered with server")
                self._running = True

                # Start listening in background
                asyncio.create_task(self.ws_manager.listen())

                # Start task checker in background
                self._task_checker_task = asyncio.create_task(self._task_checker())

                # Keep running
                while self._running:
                    await asyncio.sleep(1)
            else:
                logger.error("Failed to register with server")
                sys.exit(1)
        else:
            logger.error("Failed to connect to server")
            sys.exit(1)

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

            # Send result to server
            await self.ws_manager.send_message(result_msg, task.original_message_id, images)

            logger.info(f"Task {task.id[:8]} completed and result sent")

        except Exception as e:
            logger.error(f"Error executing task {task.id[:8]}: {e}")
            error_msg = f"🔔 定时任务失败 [{task.id[:8]}]\n\n命令: {task.command}\n\n错误: {e}"
            await self.ws_manager.send_message(error_msg, task.original_message_id, [])

        finally:
            self.scheduler.mark_completed(task.id)

    async def stop(self):
        """Stop the daemon"""
        logger.info("Stopping CC-Claw daemon...")
        self._running = False

        if self._task_checker_task:
            self._task_checker_task.cancel()

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
