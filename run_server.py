#!/usr/bin/env python3
"""CC-Claw Server Entry Point"""

import asyncio
import logging
import signal
import sys

from server.config import config
from server.models.db import init_db
from server.bot import bot
from server.ws import ws_server


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point"""
    logger.info("Starting CC-Claw server...")

    # Initialize database
    logger.info("Initializing database...")
    init_db()

    # Start WebSocket server
    logger.info("Starting WebSocket server...")
    await ws_server.start()

    # Start Telegram bot
    logger.info("Starting Telegram bot...")
    await bot.start()


async def shutdown():
    """Shutdown gracefully"""
    logger.info("Shutting down...")
    await ws_server.stop()
    logger.info("Server stopped")


def signal_handler(sig, frame):
    """Handle signals"""
    logger.info(f"Received signal {sig}")
    asyncio.create_task(shutdown())
    sys.exit(0)


if __name__ == "__main__":
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
