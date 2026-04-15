#!/usr/bin/env python3
"""CC-Claw CLI Entry Point"""

import argparse
import asyncio
import logging
import os
import sys
import uuid
import platform
import shutil
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from client import ClientConfig, PairingInfo, CCClawDaemon, APIClient

# Load .env file if it exists
load_dotenv(Path(__file__).parent.parent / ".env")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def cmd_start(args):
    """Start the daemon, guiding through first-time setup if needed."""
    config = ClientConfig.load()

    # Not paired → run guided install flow
    if not config.device_id or not config.device_token:
        print("=== First-time setup ===\n")
        print("CC-Claw needs to connect to a server and pair with your bot.\n")

        # Step 1: Server URL
        if "example.com" in config.server_api_url:
            print("Step 1: Server URL")
            print("  Press Enter for http://localhost:3000")
            server_url = input("  > ").strip() or "http://localhost:3000"
            config.server_api_url = server_url
            config.server_ws_url = _derive_ws_url(server_url)
            print(f"  API: {config.server_api_url}")
            print(f"  WS:  {config.server_ws_url}\n")

        # Step 2: Pairing
        print("Step 2: Pairing with bot")
        print("  1. Open Telegram → find your CC-Claw bot")
        print("  2. Send /pair to the bot")
        print("  3. The bot will reply with a 6-digit code")
        print("  4. Enter the code below:\n")

        device_id = str(uuid.uuid4())
        device_token = str(uuid.uuid4())
        device_name = platform.node() or "My Device"
        device_platform = platform.system().lower()

        pairing_code = input("Code: ").strip().upper()
        if not pairing_code or len(pairing_code) != 6:
            print("✗ Invalid code, run 'cc-claw start' again to retry")
            return

        print("\nConnecting...")
        async def do_pair():
            from client import APIClient
            api = APIClient(config)
            return await api.complete_pairing(
                code=pairing_code,
                device_id=device_id,
                device_name=device_name,
                platform=device_platform,
                token=device_token,
            )

        if not asyncio.run(do_pair()):
            print("✗ Pairing failed — check the code and try again")
            return

        config.device_id = device_id
        config.device_token = device_token
        config.save()
        print("✓ Paired successfully!\n")

    daemon = CCClawDaemon(config)
    daemon.run()


def _auto_detect_claude_path() -> Optional[str]:
    """Try to find claude in PATH."""
    for name in ("claude", "claude-code", "/usr/local/bin/claude",
                 "/usr/bin/claude", shutil.which("claude")):
        if name and shutil.which(name):
            return name
    return None


def _derive_ws_url(api_url: str) -> str:
    ws = api_url.replace("https://", "wss://").replace("http://", "ws://")
    if "/api" in ws:
        ws = ws.replace("/api", "/ws")
    elif not ws.endswith("/ws"):
        ws = ws.rstrip("/") + "/ws"
    return ws


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


def cmd_uninstall(args):
    """Remove all local configuration, data, and hooks."""
    import shutil
    from client.hook_config import remove_hooks

    config_dir = Path.home() / ".config" / "cc-claw"
    cache_dir = Path.home() / ".cache" / "cc-claw"

    if not args.yes:
        print("=== CC-Claw Uninstall ===\n")
        print("This will remove:")
        items = []
        if config_dir.exists():
            items.append(f"  - {config_dir}/ (config, profile, pairing)")
        if cache_dir.exists():
            items.append(f"  - {cache_dir}/ (cache)")
        items.append(f"  - Claude Code hooks from ~/.claude/settings.json")
        print("\n".join(items))
        print("\nType 'yes' to confirm: ", end="")
        if input().strip() != "yes":
            print("Cancelled.")
            return

    # Remove hooks from Claude Code settings
    try:
        remove_hooks()
        print("✓ Removed Claude Code hooks")
    except Exception as e:
        print(f"⚠ Could not remove hooks: {e}")

    # Remove config directory
    if config_dir.exists():
        shutil.rmtree(config_dir)
        print(f"✓ Removed {config_dir}")

    # Remove cache directory
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print(f"✓ Removed {cache_dir}")

    print("\nUninstall complete. To reinstall, run:")
    print("  pip install cc-claw && cc-claw start")


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
    """One-command install: configure + auto-detect + pair + start"""
    config = ClientConfig.load()

    print("=== CC-Claw Install ===\n")

    # Already paired → just start
    if config.device_id and config.device_token:
        print("✓ Already paired")
        cmd_start(args)
        return

    # --- 1. Server URL ---
    server_url = None
    if args.server_url:
        server_url = args.server_url
        config.server_api_url = server_url
        config.server_ws_url = _derive_ws_url(server_url)
        print(f"  Server: {server_url}")
    elif "example.com" in config.server_api_url:
        print("Step 1: Server URL")
        print("  Press Enter for http://localhost:3000")
        server_url = input("  > ").strip() or "http://localhost:3000"
        config.server_api_url = server_url
        config.server_ws_url = _derive_ws_url(server_url)
    else:
        print(f"  Server: {config.server_api_url} (already configured)")

    # --- 2. Claude path (auto-detect) ---
    claude_path = None
    if args.claude_path:
        claude_path = args.claude_path
    elif config.claude_path and config.claude_path != "claude":
        claude_path = config.claude_path
    else:
        claude_path = _auto_detect_claude_path()

    if not claude_path:
        print("\n✗ Claude CLI not found in PATH!")
        print("  Install: https://docs.anthropic.com/en/docs/claude-code")
        return

    config.claude_path = claude_path
    print(f"  Claude: {claude_path}")

    # Verify Claude is actually callable
    from client import ClaudeExecutor
    claude_exec = ClaudeExecutor(config)
    if not claude_exec.is_available():
        print(f"\n✗ Claude CLI not working at '{claude_path}'")
        print("  Try: cc-claw install --claude-path=/full/path/to/claude")
        return

    print(f"  Version: {claude_exec.get_version()}")

    # --- 3. Working directory (auto-detect) ---
    working_dir = args.working_dir or config.working_dir or os.getcwd()
    config.working_dir = working_dir
    print(f"  Working dir: {working_dir}")

    # --- 4. Permission mode ---
    config.permission_mode = "bypassPermissions"

    config.save()
    print("\n✓ Configuration saved")

    # --- 5. Pairing ---
    print("\n=== Pairing ===")
    print("  1. Open Telegram → send /pair to your bot")
    print("  2. Enter the 6-digit code below:\n")

    device_id = str(uuid.uuid4())
    device_token = str(uuid.uuid4())
    device_name = platform.node() or "My Device"
    device_platform = platform.system().lower()

    print(f"Device: {device_name} ({device_platform})")
    pairing_code = input("Code: ").strip().upper()

    if not pairing_code or len(pairing_code) != 6:
        print("✗ Invalid code, run 'cc-claw install' again to retry")
        return

    print("\nConnecting...")
    async def complete():
        from client import APIClient
        api = APIClient(config)
        return await api.complete_pairing(
            code=pairing_code,
            device_id=device_id,
            device_name=device_name,
            platform=device_platform,
            token=device_token,
        )

    if asyncio.run(complete()):
        config.device_id = device_id
        config.device_token = device_token
        config.save()
        print("✓ Pairing successful!\n")
    else:
        print("✗ Pairing failed — check the code and try again\n")
        return

    print("Starting daemon...\n")
    cmd_start(args)


def main():
    parser = argparse.ArgumentParser(
        description="CC-Claw - Autonomous AI coding agent for Claude Code"
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

    # uninstall
    parser_uninstall = subparsers.add_parser("uninstall", help="Remove all local config, data, and hooks")
    parser_uninstall.add_argument("--yes", "-y", action="store_true",
                                 help="Skip confirmation prompt")
    parser_uninstall.set_defaults(func=cmd_uninstall)

    # config
    parser_config = subparsers.add_parser("config", help="View or modify configuration")
    parser_config.add_argument("--get", metavar="KEY", help="Get config value")
    parser_config.add_argument("--set", metavar="KEY=VALUE", help="Set config value")
    parser_config.set_defaults(func=cmd_config)

    # setup
    parser_setup = subparsers.add_parser("setup", help="Interactive setup wizard")
    parser_setup.set_defaults(func=cmd_setup)

    # install
    parser_install = subparsers.add_parser("install", help="One-command install: configure + pair + start")
    parser_install.add_argument("--server-url", metavar="URL",
                               help="Server URL (e.g. https://cc-claw.example.com)")
    parser_install.add_argument("--claude-path", metavar="PATH",
                               help="Path to Claude CLI (auto-detected if omitted)")
    parser_install.add_argument("--working-dir", metavar="DIR",
                               help="Working directory for Claude sessions (default: cwd)")
    parser_install.set_defaults(func=cmd_install)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
