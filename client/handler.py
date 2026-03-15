"""CC-Claw Client Message Handler Module"""

import asyncio
import logging
from typing import Optional, Callable, Awaitable

from .websocket import WebSocketManager, Message
from .claude import ClaudeExecutor
from .config import ClientConfig


logger = logging.getLogger(__name__)


class MessageHandler:
    """Handle messages from server"""

    def __init__(
        self,
        ws_manager: WebSocketManager,
        claude: ClaudeExecutor,
        config: ClientConfig,
        on_message_sent: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        self.ws = ws_manager
        self.claude = claude
        self.config = config
        self.on_message_sent = on_message_sent

        # Register handlers
        self.ws.on("message", self.handle_message)
        self.ws.on("error", self.handle_error)
        self.ws.on("delivered", self.handle_delivered)

    async def handle_message(self, message: Message):
        """Handle incoming message from user"""
        try:
            message_id = message.message_id
            content = message.data.get("content", "")
            chat_id = message.data.get("chat_id")

            logger.info(f"Received message: {content[:50]}...")

            # Send acknowledgment first
            if message_id:
                await self.ws.send_ack(message_id)

            # Execute with Claude
            logger.info("Calling Claude executor...")
            response, images = await self.claude.execute(content)
            logger.info(f"Claude response: {response[:100]}...")
            if images:
                logger.info(f"Claude generated {len(images)} images")

            # Send response back to server (with images if any)
            if message_id:
                logger.info(f"Sending response back to server, message_id={message_id}")
                success = await asyncio.wait_for(
                    self.ws.send_message(response, message_id, images),
                    timeout=30
                )
                logger.info(f"Response sent: {success}")
                if success and self.on_message_sent:
                    await self.on_message_sent(message_id)
        except Exception as e:
            logger.error(f"Error in handle_message: {e}", exc_info=True)

    async def handle_error(self, message: Message):
        """Handle error message from server"""
        error_code = message.data.get("code", "UNKNOWN")
        error_msg = message.data.get("message", "Unknown error")
        logger.error(f"Server error: {error_code} - {error_msg}")

    async def handle_delivered(self, message: Message):
        """Handle message delivered confirmation"""
        message_id = message.message_id
        logger.info(f"Message delivered: {message_id}")


class ToolExecutor:
    """Execute local tools"""

    def __init__(self, config: ClientConfig):
        self.config = config
        self._results: dict = {}

    async def execute_tool(self, tool_name: str, params: dict) -> str:
        """Execute a tool and return result"""
        if tool_name == "screenshot":
            return await self._screenshot()
        elif tool_name == "list_dir":
            return await self._list_dir(params.get("path", "."))
        elif tool_name == "read_file":
            return await self._read_file(params.get("path", ""))
        elif tool_name == "shell":
            return await self._shell(params.get("command", ""))
        else:
            return f"Unknown tool: {tool_name}"

    async def _screenshot(self) -> str:
        """Take a screenshot"""
        import platform
        import os

        system = platform.system()
        temp_file = "/tmp/cc-claw-screenshot.png"

        try:
            if system == "Darwin":  # macOS
                cmd = ["screencapture", temp_file]
            elif system == "Linux":
                cmd = ["scrot", temp_file]
            else:
                return "Screenshot not supported on this platform"

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()

            if os.path.exists(temp_file):
                self._results["screenshot"] = temp_file
                return f"Screenshot saved: {temp_file}"
            else:
                return "Failed to capture screenshot"

        except Exception as e:
            return f"Error capturing screenshot: {e}"

    async def _list_dir(self, path: str) -> str:
        """List directory contents"""
        try:
            import os
            items = os.listdir(path)
            return "\n".join(items)
        except Exception as e:
            return f"Error listing directory: {e}"

    async def _read_file(self, path: str) -> str:
        """Read file contents"""
        try:
            with open(path, "r") as f:
                content = f.read(10000)  # Limit to 10KB
                if len(content) >= 10000:
                    content += "\n... (truncated)"
                return content
        except Exception as e:
            return f"Error reading file: {e}"

    async def _shell(self, command: str) -> str:
        """Execute shell command"""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60,
            )
            result = stdout.decode() if stdout else ""
            error = stderr.decode() if stderr else ""
            if error:
                result += f"\nStderr: {error}"
            return result or "No output"
        except Exception as e:
            return f"Error executing command: {e}"
