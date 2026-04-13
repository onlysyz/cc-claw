#!/usr/bin/env python3
"""CC-Claw CLI Entry Point"""

import argparse
import asyncio
import logging
import os
import sys
import uuid
import platform
from pathlib import Path

from dotenv import load_dotenv

from client import ClientConfig, PairingInfo, CCClawDaemon, APIClient

# Load .env file if it exists
load_dotenv(Path(__file__).parent / ".env")


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


def cmd_solve(args):
    """Search AgentSolveHub for solutions"""
    from client import AgentSolveHubPlugin

    ash = AgentSolveHubPlugin()

    query = args.query
    print(f"🔍 Searching AgentSolveHub for: {query}\n")

    solutions = ash.search_solutions(query, platform=args.platform, limit=args.limit)

    if not solutions:
        print("❌ No solutions found.")
        print("\nTry:")
        print("  - Different keywords")
        print("  - Broader search terms")
        print("  - Submit this problem at https://agentsolvehub.com")
        return

    print(f"✅ Found {len(solutions)} solutions:\n")

    for i, sol in enumerate(solutions, 1):
        print(f"{i}. {sol.title}")
        print(f"   Platform: {sol.platform}")
        print(f"   👍 {sol.vote_count} votes | 👁 {sol.view_count} views")
        print(f"   {sol.content[:150]}...")
        if sol.steps:
            print(f"   📋 {len(sol.steps)} steps")
        print()

    print("---")
    print("💡 Solutions powered by AgentSolveHub")
    print("   Submit your solutions at https://agentsolvehub.com")


def cmd_submit(args):
    """Submit a solution to AgentSolveHub"""
    from client import AgentSolveHubPlugin

    ash = AgentSolveHubPlugin()

    print(f"📤 Submitting solution to AgentSolveHub...\n")
    print(f"  Title: {args.title[:50]}...")
    print(f"  Type: {args.type}")
    print(f"  Platform: {args.platform or 'cc-claw'}")

    # First submit a problem, then submit solution
    problem_id = ash.submit_problem(
        title=args.title[:100],
        goal=args.content[:500],
        platform_name=args.platform or "cc-claw",
        task_type=args.type,
    )

    if not problem_id:
        print("\n❌ Failed to submit problem. Check your API key.")
        print("   Make sure you're registered: cc-claw solvehub register")
        return

    solution_id = ash.submit_solution(
        problem_id=problem_id,
        title=args.title[:100],
        steps=[{"order": 1, "content": args.content[:500]}],
    )

    if solution_id:
        print(f"\n✅ Solution submitted!")
        print(f"   Problem ID: {problem_id}")
        print(f"   Solution ID: {solution_id}")
        print(f"   View at: https://agentsolvehub.com")
    else:
        print("\n❌ Submission failed. Check your API key.")


def cmd_solvehub_export(args):
    """Export CC-Claw solutions to AgentSolveHub"""
    from client import AgentSolveHubPlugin

    ash = AgentSolveHubPlugin()

    print("🚀 CC-Claw → AgentSolveHub Export\n")

    # Check API key
    if not ash._api_key:
        print("⚠️  No API key found.")
        print("   Options:")
        print("   1. Run 'cc-claw solvehub register' to register")
        print("   2. Set AGENTSOLVEHUB_API_KEY environment variable")
        print("   3. Set 'export AGENTSOLVEHUB_API_KEY=your_key'")
        print("\n   Registering now...")
        try:
            ash.register()
            print("   ✅ Registration successful!")
        except Exception as e:
            print(f"   ❌ Registration failed: {e}")
            return

    # Export built-in solutions as problems with solutions
    problems_submitted = 0
    solutions_submitted = 0

    for sol in ash.BUILTIN_SOLUTIONS:
        print(f"📤 Exporting: {sol.title[:50]}...")

        # Submit as problem
        problem_id = ash.submit_problem(
            title=sol.title[:100],
            goal=f"CC-Claw feature: {sol.title}",
            platform_name="cc-claw",
            task_type="feature",
        )

        if problem_id:
            print(f"   ✅ Problem submitted (ID: {problem_id})")
            problems_submitted += 1

            # Submit as solution
            solution_id = ash.submit_solution(
                problem_id=problem_id,
                title=f"Solution: {sol.title}",
                steps=sol.steps,
                root_cause=sol.content[:200],
            )

            if solution_id:
                print(f"   ✅ Solution submitted (ID: {solution_id})")
                solutions_submitted += 1
            else:
                print(f"   ⚠️  Problem submitted but solution failed")
        else:
            print(f"   ⚠️  Rate limited or API error")

        import time
        time.sleep(0.5)  # Rate limiting

    print(f"\n✅ Export complete!")
    print(f"   Problems submitted: {problems_submitted}")
    print(f"   Solutions submitted: {solutions_submitted}")
    print(f"\n   View at: https://agentsolvehub.com/platform/cc-claw")


def cmd_solvehub_list(args):
    """List available CC-Claw solutions"""
    from client import AgentSolveHubPlugin

    ash = AgentSolveHubPlugin()

    print("📚 CC-Claw Built-in Solutions\n")
    print(f"{'ID':<12} {'Title':<50} {'Votes':<8} {'Tags'}")
    print("-" * 100)

    for sol in ash.BUILTIN_SOLUTIONS:
        tags = ", ".join(sol.tags[:2])
        print(f"{sol.id:<12} {sol.title[:48]:<50} {sol.vote_count:<8} {tags}")

    print(f"\nTotal: {len(ash.BUILTIN_SOLUTIONS)} solutions")
    print("\nUse 'cc-claw solve <query>' to search for solutions")


def cmd_solvehub_register(args):
    """Register CC-Claw as an AgentSolveHub agent"""
    from client import AgentSolveHubPlugin

    ash = AgentSolveHubPlugin()

    print("🚀 Registering CC-Claw with AgentSolveHub...\n")

    try:
        result = ash.register()
        print("✅ Registration successful!")
        print(f"\n   Agent ID: {result['agent']['agentId']}")
        print(f"   API Key: {result['apiKey'][:20]}...")
        print(f"\n   Credentials saved to: ~/.config/agentsolvehub/credentials.json")
        print("\n   Next steps:")
        print("   - cc-claw solvehub export  # Export built-in solutions")
        print("   - cc-claw solve 'docker error'  # Search for solutions")
    except Exception as e:
        print(f"❌ Registration failed: {e}")
        print("\n   Make sure you're connected to AgentSolveHub API.")


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

    # solve - Search AgentSolveHub
    parser_solve = subparsers.add_parser("solve", help="Search AgentSolveHub for solutions")
    parser_solve.add_argument("query", help="Search query")
    parser_solve.add_argument("--platform", "-p", default=None, help="Filter by platform")
    parser_solve.add_argument("--limit", "-l", type=int, default=5, help="Max results (default: 5)")
    parser_solve.set_defaults(func=cmd_solve)

    # submit - Submit to AgentSolveHub
    parser_submit = subparsers.add_parser("submit", help="Submit a solution to AgentSolveHub")
    parser_submit.add_argument("--title", "-t", required=True, help="Solution title")
    parser_submit.add_argument("--content", "-c", required=True, help="Solution content")
    parser_submit.add_argument("--type", default="feature", help="Type (feature/debug/refactor)")
    parser_submit.add_argument("--platform", "-p", default="cc-claw", help="Platform name")
    parser_submit.add_argument("--tags", help="Comma-separated tags")
    parser_submit.set_defaults(func=cmd_submit)

    # solvehub - AgentSolveHub integration
    parser_solvehub = subparsers.add_parser("solvehub", help="AgentSolveHub integration")
    subparsers_solvehub = parser_solvehub.add_subparsers(dest="solvehub_action", help="Action")

    # solvehub register
    parser_solvehub_register = subparsers_solvehub.add_parser("register", help="Register CC-Claw as agent")
    parser_solvehub_register.set_defaults(func=cmd_solvehub_register)

    # solvehub list
    parser_solvehub_list = subparsers_solvehub.add_parser("list", help="List available solutions")
    parser_solvehub_list.set_defaults(func=cmd_solvehub_list)

    # solvehub export
    parser_solvehub_export = subparsers_solvehub.add_parser("export", help="Export solutions to AgentSolveHub")
    parser_solvehub_export.set_defaults(func=cmd_solvehub_export)

    # Top-level aliases for convenience
    parser_solvehub_list_alias = subparsers.add_parser("solvehub-list", help="List CC-Claw solutions")
    parser_solvehub_list_alias.set_defaults(func=cmd_solvehub_list)

    parser_solvehub_export_alias = subparsers.add_parser("solvehub-export", help="Export solutions to AgentSolveHub")
    parser_solvehub_export_alias.set_defaults(func=cmd_solvehub_export)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
