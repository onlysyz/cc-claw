"""CC-Claw Client Claude Executor Module - Using --print mode with JSON output"""

import asyncio
import json
import logging
import os
import subprocess
from typing import Optional

from .config import ClientConfig


logger = logging.getLogger(__name__)


class ClaudeExecutor:
    """Execute Claude Code CLI using --print mode with JSON output"""

    def __init__(self, config: ClientConfig):
        self.config = config

    def _build_env(self) -> dict:
        """Build clean environment for Claude"""
        env = os.environ.copy()
        # Remove ALL Claude-related environment variables
        for key in list(env.keys()):
            if "CLAUDE" in key.upper() or key == "AWS_PROFILE":
                env.pop(key, None)
        return env

    async def execute(self, prompt: str) -> str:
        """Execute a prompt using --print mode with JSON output"""
        work_dir = getattr(self.config, 'working_dir', '/tmp') or '/tmp'

        # Build command - use --print with JSON output
        cmd = [
            self.config.claude_path,
            "--print",
            "--output-format", "json",
            "--continue",  # Continue session for context
        ]

        # Add permission mode
        if self.config.permission_mode and self.config.permission_mode != "default":
            cmd.append("--dangerously-skip-permissions")

        logger.info(f"Running Claude: {' '.join(cmd)} with prompt: {prompt[:30]}...")

        try:
            # Use communicate() for simple command execution
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._build_env(),
                cwd=work_dir,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=prompt.encode()),
                timeout=self.config.timeout
            )

            # Parse JSON output
            output = stdout.decode() if stdout else ""
            error = stderr.decode() if stderr else ""

            if error:
                logger.warning(f"Claude stderr: {error[:500]}")

            # Try to parse JSON response
            try:
                # Find JSON in output (may have extra text)
                json_start = output.find('{')
                if json_start != -1:
                    # Try to parse from the first {
                    json_str = output[json_start:]
                    data = json.loads(json_str)

                    # Extract result text
                    result = data.get('result', '')
                    if result:
                        logger.info(f"Claude response: {result[:100]}...")
                        return result

                # If no valid JSON, return raw output
                if output:
                    logger.info(f"Claude raw response: {output[:100]}...")
                    return output.strip()

                return "No response"

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")
                logger.error(f"Raw output: {output[:500]}")
                return f"Error parsing response: {output[:200]}"

        except asyncio.TimeoutError:
            logger.error("Timeout waiting for Claude")
            return "Timeout"
        except Exception as e:
            logger.error(f"Error running Claude: {e}", exc_info=True)
            return f"Error: {str(e)}"

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
