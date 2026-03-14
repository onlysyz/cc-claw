"""CC-Claw Tailscale Integration"""

import asyncio
import logging
import os
import subprocess
from typing import Optional

from ..config import config


logger = logging.getLogger(__name__)


class TailscaleService:
    """Tailscale tunnel service"""

    def __init__(self):
        self.process: Optional[asyncio.subprocess.Process] = None
        self.tailscale_url: Optional[str] = None

    def is_installed(self) -> bool:
        """Check if Tailscale is installed"""
        result = subprocess.run(
            ["which", "tailscale"],
            capture_output=True,
        )
        return result.returncode == 0

    def is_logged_in(self) -> bool:
        """Check if Tailscale is logged in"""
        result = subprocess.run(
            ["tailscale", "status"],
            capture_output=True,
            timeout=10,
        )
        # If not logged in, it will show "not logged in"
        return "not logged in" not in result.stderr.decode().lower()

    async def start_serve(self, port: int) -> bool:
        """Start Tailscale serve (tailnet only)"""
        if not self.is_installed():
            logger.error("Tailscale not installed")
            return False

        logger.info(f"Starting Tailscale serve on port {port}...")

        try:
            # tailscale serve tcp localhost:18789
            process = await asyncio.create_subprocess_exec(
                "tailscale", "serve", "tcp", f"localhost:{port}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self.process = process

            # Get the serve URL
            self.tailscale_url = await self._get_serve_url(port)

            logger.info(f"Tailscale serve started: {self.tailscale_url}")
            return True

        except Exception as e:
            logger.error(f"Failed to start Tailscale serve: {e}")
            return False

    async def start_funnel(self, port: int) -> bool:
        """Start Tailscale funnel (public HTTPS)"""
        if not self.is_installed():
            logger.error("Tailscale not installed")
            return False

        logger.info(f"Starting Tailscale funnel on port {port}...")

        try:
            # tailscale funnel serve localhost:18789
            process = await asyncio.create_subprocess_exec(
                "tailscale", "funnel", "serve", f"localhost:{port}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self.process = process

            # Get the funnel URL
            self.tailscale_url = await self._get_funnel_url()

            logger.info(f"Tailscale funnel started: {self.tailscale_url}")
            return True

        except Exception as e:
            logger.error(f"Failed to start Tailscale funnel: {e}")
            return False

    async def _get_serve_url(self, port: int) -> Optional[str]:
        """Get Tailscale serve URL"""
        try:
            result = await asyncio.create_subprocess_exec(
                "tailscale", "status", "-json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            # Parse JSON to get serve status
            # For now, return the known pattern
            # TODO: Parse actual URL from status
            return f"https://your-machine.tail-scale.ts.net:{port}"
        except Exception as e:
            logger.error(f"Failed to get serve URL: {e}")
            return None

    async def _get_funnel_url(self) -> Optional[str]:
        """Get Tailscale funnel URL"""
        try:
            result = await asyncio.create_subprocess_exec(
                "tailscale", "funnel", "status", "-json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # TODO: Parse actual URL from status
            return "https://your-machine.ts.net"
        except Exception as e:
            logger.error(f"Failed to get funnel URL: {e}")
            return None

    async def stop(self):
        """Stop Tailscale serve/funnel"""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            self.process = None
            logger.info("Tailscale serve/funnel stopped")

    @property
    def url(self) -> Optional[str]:
        """Get current tunnel URL"""
        return self.tailscale_url


# Global instance
tailscale = TailscaleService()
