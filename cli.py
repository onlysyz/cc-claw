#!/usr/bin/env python3
"""CC-Claw CLI Entry Point"""

import argparse
import asyncio
import logging
import sys
import uuid

from client import ClientConfig, PairingInfo, CCClawDaemon


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def cmd_start(args):
    """Start the daemon"""
    config = ClientConfig.load()
    daemon = CCClawDaemon(config)
    daemon.run()


def cmd_stop(args):
    """Stop the daemon"""
    # This would require a daemon manager or PID file
    logger.info("Stop command - to be implemented")
    print("Use Ctrl+C to stop the daemon")


def cmd_status(args):
    """Check daemon status"""
    config = ClientConfig.load()

    print("=== CC-Claw Status ===")
    print(f"Server: {config.server_ws_url}")
    print(f"Device ID: {config.device_id or 'Not configured'}")
    print(f"Claude Path: {config.claude_path}")

    # Check Claude CLI
    from client import ClaudeExecutor
    claude = ClaudeExecutor(config)
    if claude.is_available():
        print(f"Claude: Available ({claude.get_version()})")
    else:
        print("Claude: Not found")


def cmd_pair(args):
    """Start pairing process"""
    print("=== CC-Claw Pairing ===")

    # Generate a random device ID
    device_id = str(uuid.uuid4())

    # Load or create config
    config = ClientConfig.load()
    config.device_id = device_id
    config.save()

    # Load pairing info
    pairing = PairingInfo()

    print(f"Device ID: {device_id}")
    print("\nPlease send /pair to the CC-Claw Telegram bot")
    print("Then enter the pairing code shown by the bot:")

    # For now, just save the device ID
    print(f"\nConfiguration saved. Run 'cc-claw start' after pairing.")


def cmd_unpair(args):
    """Unpair device"""
    config = ClientConfig.load()
    pairing = PairingInfo.load()

    config.device_id = None
    config.device_token = None
    config.save()

    pairing.code = None
    pairing.user_id = None
    pairing.save()

    print("Device unpaired successfully")


def cmd_config(args):
    """View or modify configuration"""
    config = ClientConfig.load()

    if args.get:
        # Get specific config
        key = args.get
        if hasattr(config, key):
            print(f"{key}: {getattr(config, key)}")
        else:
            print(f"Unknown config: {key}")
    elif args.set:
        # Set specific config
        key, value = args.set.split("=", 1)
        if hasattr(config, key):
            setattr(config, key, value)
            config.save()
            print(f"{key} updated to: {value}")
        else:
            print(f"Unknown config: {key}")
    else:
        # Show all config
        print("=== CC-Claw Configuration ===")
        print(f"Server WS URL: {config.server_ws_url}")
        print(f"Server API URL: {config.server_api_url}")
        print(f"Device ID: {config.device_id or 'Not configured'}")
        print(f"Claude Path: {config.claude_path}")
        print(f"Timeout: {config.timeout}s")
        print(f"Auto Reconnect: {config.auto_reconnect}")
        print(f"Log Level: {config.log_level}")


def main():
    parser = argparse.ArgumentParser(
        description="CC-Claw - Telegram bot to control Claude Code CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # start
    parser_start = subparsers.add_parser("start", help="Start the daemon")
    parser_start.set_defaults(func=cmd_start)

    # stop
    parser_stop = subparsers.add_parser("stop", help="Stop the daemon")
    parser_stop.set_defaults(func=cmd_stop)

    # status
    parser_status = subparsers.add_parser("status", help="Check daemon status")
    parser_status.set_defaults(func=cmd_status)

    # pair
    parser_pair = subparsers.add_parser("pair", help="Start pairing process")
    parser_pair.set_defaults(func=cmd_pair)

    # unpair
    parser_unpair = subparsers.add_parser("unpair", help="Unpair device")
    parser_unpair.set_defaults(func=cmd_unpair)

    # config
    parser_config = subparsers.add_parser("config", help="View or modify configuration")
    parser_config.add_argument("--get", metavar="KEY", help="Get config value")
    parser_config.add_argument("--set", metavar="KEY=VALUE", help="Set config value")
    parser_config.set_defaults(func=cmd_config)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
