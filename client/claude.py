"""CC-Claw Client Claude Executor Module"""

import asyncio
import logging
import subprocess
from typing import Optional, AsyncGenerator

from .config import ClientConfig


logger = logging.getLogger(__name__)


class ClaudeExecutor:
    """Execute Claude Code CLI commands"""

    def __init__(self, config: ClientConfig):
        self.config = config
        self._process: Optional[asyncio.subprocess.Process] = None

    async def execute(self, prompt: str) -> str:
        """Execute a prompt and return the result"""
        cmd = [self.config.claude_path, "-p", prompt]

        logger.info(f"Executing: {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.config.timeout
            )

            result = stdout.decode() if stdout else ""
            error = stderr.decode() if stderr else ""

            if error and not result:
                logger.warning(f"Claude CLI stderr: {error}")
                return f"Error: {error}"

            return result or "No response"

        except asyncio.TimeoutError:
            logger.error(f"Claude CLI timed out after {self.config.timeout}s")
            if process:
                process.kill()
            return "Error: Command timed out"
        except FileNotFoundError:
            logger.error(f"Claude CLI not found at: {self.config.claude_path}")
            return "Error: Claude CLI not found. Please check your configuration."
        except Exception as e:
            logger.error(f"Error executing Claude CLI: {e}")
            return f"Error: {str(e)}"

    async def execute_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Execute a prompt and yield output as a stream"""
        cmd = [self.config.claude_path, "-p", prompt]

        logger.info(f"Executing (streaming): {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )

            self._process = process

            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                yield line.decode()

            # Get remaining stderr
            stderr = await process.stderr.read()
            if stderr:
                logger.warning(f"Claude CLI stderr: {stderr.decode()}")

            self._process = None

        except asyncio.TimeoutError:
            logger.error(f"Claude CLI timed out after {self.config.timeout}s")
            if self._process:
                self._process.kill()
            yield "Error: Command timed out"
        except FileNotFoundError:
            logger.error(f"Claude CLI not found at: {self.config.claude_path}")
            yield "Error: Claude CLI not found. Please check your configuration."
        except Exception as e:
            logger.error(f"Error executing Claude CLI: {e}")
            yield f"Error: {str(e)}"

    def is_available(self) -> bool:
        """Check if Claude CLI is available"""
        try:
            result = subprocess.run(
                [self.config.claude_path, "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_version(self) -> Optional[str]:
        """Get Claude CLI version"""
        try:
            result = subprocess.run(
                [self.config.claude_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None
