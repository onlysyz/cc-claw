#!/usr/bin/env python3
"""CC-Claw CLI Entry Point"""

import argparse
import asyncio
import logging
import sys
import uuid
import platform

from client import ClientConfig, PairingInfo, CCClawDaemon, APIClient


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
    print(f"Server: {config.server_api_url}")

    if not config.device_id:
        print("\n❌ Not paired")
        print("   Run 'cc-claw pair' to connect")
        return

    print(f"Device ID: {config.device_id}")
    print(f"Claude Path: {config.claude_path}")

    # Check Claude CLI
    from client import ClaudeExecutor
    claude = ClaudeExecutor(config)
    if claude.is_available():
        print(f"Claude: Available ({claude.get_version()})")
    else:
        print("Claude: Not found")

    # Check server connection
    if "example.com" not in config.server_api_url:
        print("\n🔄 Checking server connection...")

        async def check():
            api = APIClient(config)
            result = await api.get_pairing_status(0)  # Just test connectivity
            return result is not None

        try:
            connected = asyncio.run(check())
            if connected:
                print("Server: ✅ Connected")
            else:
                print("Server: ⚠️  Could not connect")
        except Exception as e:
            print(f"Server: ❌ Connection failed ({e})")
    else:
        print("\n⚠️  Server not configured")


def cmd_pair(args):
    """Start pairing process"""
    print("=== CC-Claw Pairing ===\n")

    # Load config
    config = ClientConfig.load()

    # Check server URL
    if "example.com" in config.server_api_url:
        print("⚠️  Server URL not configured!")
        print("   Run: cc-claw config --set server_api_url=https://your-server.com")
        print("   Run: cc-claw config --set server_ws_url=wss://your-server.com")
        return

    # Generate device ID and token
    device_id = str(uuid.uuid4())
    device_token = str(uuid.uuid4())
    device_name = platform.node() or "My Device"
    device_platform = platform.system().lower()

    print(f"Device Name: {device_name}")
    print(f"Platform: {device_platform}")
    print(f"\n📱 Please do the following:")
    print("   1. Open Telegram and send /pair to the CC-Claw bot")
    print("   2. The bot will give you a pairing code")
    print("   3. Enter the code below:\n")

    pairing_code = input("Enter pairing code: ").strip().upper()

    if not pairing_code:
        print("❌ Pairing cancelled")
        return

    if len(pairing_code) != 6:
        print("❌ Invalid pairing code format")
        return

    print("\n🔄 Completing pairing...")

    # Complete pairing via API
    async def complete():
        api = APIClient(config)
        result = await api.complete_pairing(
            code=pairing_code,
            device_id=device_id,
            device_name=device_name,
            platform=device_platform,
            token=device_token,
        )
        return result

    result = asyncio.run(complete())

    if result:
        # Save config
        config.device_id = device_id
        config.device_token = device_token
        config.save()

        print("\n✅ Pairing completed successfully!")
        print(f"   Device ID: {device_id}")
        print("\n🚀 Run 'cc-claw start' to connect to server")
    else:
        print("\n❌ Pairing failed!")
        print("   - Check if the code is correct")
        print("   - Check if the code has expired (5 minutes)")
        print("   - Make sure the server is running")


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
