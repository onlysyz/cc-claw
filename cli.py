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
        print(f"Working Directory: {config.working_dir or '/tmp'}")
        print(f"Permission Mode: {config.permission_mode} (use 'bypassPermissions' to skip all)")
        print(f"Timeout: {config.timeout}s")
        print(f"Auto Reconnect: {config.auto_reconnect}")
        print(f"Log Level: {config.log_level}")


def cmd_setup(args):
    """Interactive setup wizard"""
    config = ClientConfig.load()

    print("=== CC-Claw Setup Wizard ===\n")

    # Step 1: Server URL
    print("Step 1: Configure Server URL")
    print(f"  Current: {config.server_api_url}")
    print("  Default: http://localhost:3000 (local development)")
    server_url = input("  Enter server URL (or press Enter for localhost): ").strip()
    if server_url:
        config.server_api_url = server_url
        # Derive WS URL from API URL
        ws_url = server_url.replace("https://", "wss://").replace("http://", "ws://")
        if "/api" in ws_url:
            ws_url = ws_url.replace("/api", "/ws")
        else:
            ws_url += "/ws"
        config.server_ws_url = ws_url
    elif "example.com" in config.server_api_url:
        # Default to localhost
        config.server_api_url = "http://localhost:3000"
        config.server_ws_url = "ws://localhost:3001"
    print(f"  API: {config.server_api_url}")
    print(f"  WS:  {config.server_ws_url}")

    # Step 2: Claude path
    print("\nStep 2: Configure Claude CLI")
    print(f"  Current: {config.claude_path}")
    claude_path = input("  Enter Claude CLI path (or press Enter to keep): ").strip()
    if claude_path:
        config.claude_path = claude_path
        print(f"  Set claude_path: {config.claude_path}")

    # Step 3: Permission mode
    print("\nStep 3: Permission Mode")
    print("  Options:")
    print("    1. default    - Ask for permissions when needed")
    print("    2. bypassPermissions - Skip all permission prompts (recommended)")
    choice = input("  Enter choice [1-2] (default: 2): ").strip() or "2"
    if choice == "2":
        config.permission_mode = "bypassPermissions"
        print("  Set permission_mode: bypassPermissions")
    else:
        config.permission_mode = "default"
        print("  Set permission_mode: default")

    # Step 4: Working directory
    print("\nStep 4: Working Directory")
    print(f"  Current: {config.working_dir or '/tmp'}")
    work_dir = input("  Enter working directory (or press Enter to keep): ").strip()
    if work_dir:
        config.working_dir = work_dir
        print(f"  Set working_dir: {config.working_dir}")

    # Save config
    config.save()
    print("\n✓ Configuration saved!")

    # Check Claude availability
    from client import ClaudeExecutor
    claude = ClaudeExecutor(config)
    if claude.is_available():
        print(f"✓ Claude CLI found: {claude.get_version()}")
    else:
        print("✗ Claude CLI not found! Please install Claude Code first.")
        print("  Install: https://docs.anthropic.com/en/docs/claude-code/initial-setup")

    print("\n=== Setup Complete ===")
    print("\nNext steps:")
    print("  1. Run 'cc-claw pair' to pair with Telegram bot")
    print("  2. Run 'cc-claw start' to start the daemon")


def cmd_install(args):
    """One-command install: setup + pair + start"""
    config = ClientConfig.load()

    print("=== CC-Claw One-Command Install ===\n")

    # Check if already paired
    if config.device_id and config.device_token:
        print("✓ Already paired!")
        print("\nStarting daemon...")
        cmd_start(args)
        return

    # Check if server URL is configured (default to localhost)
    if "example.com" in config.server_api_url:
        print("Step 1: Server URL")
        print("  Default: http://localhost:3000 (local development)")
        server_url = input("  Enter server URL (or press Enter for localhost): ").strip()
        if not server_url:
            server_url = "http://localhost:3000"
        config.server_api_url = server_url
        # Derive WS URL
        ws_url = server_url.replace("https://", "wss://").replace("http://", "ws://")
        if "/api" in ws_url:
            ws_url = ws_url.replace("/api", "/ws")
        else:
            ws_url += "/ws"
        config.server_ws_url = ws_url
        print(f"  API: {config.server_api_url}")
        print(f"  WS:  {config.server_ws_url}")

    # Set recommended defaults
    config.permission_mode = "bypassPermissions"
    config.working_dir = "/tmp/cc-claw-sessions"

    # Check Claude
    from client import ClaudeExecutor
    claude = ClaudeExecutor(config)
    if not claude.is_available():
        print("\n✗ Claude CLI not found!")
        print("  Please install Claude Code first:")
        print("  https://docs.anthropic.com/en/docs/claude-code/initial-setup")
        return

    print(f"✓ Claude CLI: {claude.get_version()}")

    # Save config
    config.save()

    # Do pairing
    print("\n=== Pairing with Telegram ===")
    print("  1. Open Telegram and send /pair to your bot")
    print("  2. Enter the 6-digit code below:\n")

    device_id = str(uuid.uuid4())
    device_token = str(uuid.uuid4())
    device_name = platform.node() or "My Device"
    device_platform = platform.system().lower()

    print(f"Device: {device_name} ({device_platform})")
    pairing_code = input("Enter pairing code: ").strip().upper()

    if not pairing_code or len(pairing_code) != 6:
        print("✗ Invalid pairing code")
        return

    print("\nCompleting pairing...")

    async def complete():
        from client import APIClient
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
        config.device_id = device_id
        config.device_token = device_token
        config.save()
        print("\n✓ Pairing successful!")
    else:
        print("\n✗ Pairing failed!")
        print("  - Check if the code is correct")
        print("  - Code expires in 5 minutes")
        return

    print("\n=== Starting daemon ===")
    cmd_start(args)


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

    # setup
    parser_setup = subparsers.add_parser("setup", help="Interactive setup wizard")
    parser_setup.set_defaults(func=cmd_setup)

    # install
    parser_install = subparsers.add_parser("install", help="One-command install: setup + pair + start")
    parser_install.set_defaults(func=cmd_install)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
