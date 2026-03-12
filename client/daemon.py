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
        self._running = False

    async def start(self):
        """Start the daemon"""
        if self._running:
            logger.warning("Daemon already running")
            return

        logger.info("Starting CC-Claw daemon...")

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

        # Initialize handler
        self.handler = MessageHandler(
            self.ws_manager,
            self.claude,
            self.config,
        )

        # Connect and start listening
        if await self.ws_manager.connect():
            if await self.ws_manager.register():
                logger.info("Registered with server")
                self._running = True

                # Start listening in background
                asyncio.create_task(self.ws_manager.listen())

                # Keep running
                while self._running:
                    await asyncio.sleep(1)
            else:
                logger.error("Failed to register with server")
                sys.exit(1)
        else:
            logger.error("Failed to connect to server")
            sys.exit(1)

    async def stop(self):
        """Stop the daemon"""
        logger.info("Stopping CC-Claw daemon...")
        self._running = False

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
