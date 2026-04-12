#!/usr/bin/env python3
"""CC-Claw Server Entry Point"""

import asyncio
import logging
import signal
import sys
import threading

from server.config import config
from server.bot import telegram_bot, lark_bot
from server.ws import ws_server
from server.api.main import app as api_app
from server.services.tailscale import tailscale
import uvicorn


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

    # Start API server in a separate thread
    logger.info(f"Starting API server on {config.host}:{config.api_port}...")
    api_config = uvicorn.Config(
        api_app,
        host=config.host,
        port=config.api_port,
        log_level="info",
    )
    api_server = uvicorn.Server(api_config)
    api_thread = threading.Thread(target=api_server.run, daemon=True)
    api_thread.start()
    logger.info(f"API server started on {config.host}:{config.api_port}")

    # Start Telegram bot in a separate thread (it's blocking)
    logger.info("Starting Telegram bot in background...")
    bot_thread = threading.Thread(target=telegram_bot.start, daemon=True)
    bot_thread.start()

    # Start Lark bot if configured
    if config.lark_app_id and config.lark_app_secret:
        logger.info("Starting Lark bot in background...")
        lark_bot.start()
    else:
        logger.info("Lark bot not configured (set LARK_APP_ID and LARK_APP_SECRET)")

    # Keep the main thread alive
    logger.info("Server running. Press Ctrl+C to stop.")
    await asyncio.Event().wait()


async def shutdown():
    """Shutdown gracefully"""
    logger.info("Shutting down...")

    # Stop Telegram bot
    telegram_bot.stop()

    # Stop Lark bot
    lark_bot.stop()

    # Stop Tailscale
    await tailscale.stop()

    # Stop WebSocket server
    await ws_server.stop()

    logger.info("Server stopped")
    sys.exit(0)


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
