#!/usr/bin/env python3
"""CC-Claw Server Entry Point"""

import asyncio
import logging
import signal
import sys

from server.config import config
from server.bot import bot
from server.ws import ws_server
from server.services.tailscale import tailscale


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def setup_tailscale():
    """Setup Tailscale tunnel if configured"""
    if config.tailscale_mode == "off":
        return

    if not tailscale.is_installed():
        logger.warning("Tailscale not installed, skipping tunnel setup")
        return

    if not tailscale.is_logged_in():
        logger.warning("Tailscale not logged in, skipping tunnel setup")
        logger.info("Run 'tailscale login' to login")
        return

    if config.tailscale_mode == "serve":
        success = await tailscale.start_serve(config.ws_port)
    elif config.tailscale_mode == "funnel":
        success = await tailscale.start_funnel(config.ws_port)
    else:
        logger.warning(f"Unknown Tailscale mode: {config.tailscale_mode}")
        return

    if success and tailscale.url:
        logger.info(f"🌐 Tailscale URL: {tailscale.url}")
        logger.info("   Share this URL with your Telegram bot webhook (if using)")


async def main():
    """Main entry point"""
    logger.info("Starting CC-Claw server...")

    # Setup Tailscale if configured
    await setup_tailscale()

    # Start WebSocket server
    logger.info("Starting WebSocket server...")
    await ws_server.start()

    # Start Telegram bot
    logger.info("Starting Telegram bot...")
    await bot.start()


async def shutdown():
    """Shutdown gracefully"""
    logger.info("Shutting down...")

    # Stop Tailscale
    await tailscale.stop()

    # Stop WebSocket server
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
