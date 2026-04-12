"""CC-Claw Client API Module"""

import asyncio
import logging
from typing import Optional

import aiohttp

from .config import ClientConfig


logger = logging.getLogger(__name__)


class APIClient:
    """API client for server communication"""

    def __init__(self, config: ClientConfig):
        self.config = config

    async def generate_pairing(self, telegram_id: int) -> Optional[dict]:
        """Generate a pairing code"""
        url = f"{self.config.server_api_url}/api/pairing/generate"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={"telegram_id": telegram_id}) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.error(f"Failed to generate pairing: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Error generating pairing: {e}")
            return None

    async def verify_pairing(self, code: str) -> bool:
        """Verify a pairing code"""
        url = f"{self.config.server_api_url}/api/pairing/verify"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={"code": code}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("valid", False)
                    return False
        except Exception as e:
            logger.error(f"Error verifying pairing: {e}")
            return False

    async def complete_pairing(
        self,
        code: str,
        device_id: str,
        device_name: str,
        platform: str,
        token: str,
    ) -> Optional[dict]:
        """Complete the pairing process"""
        url = f"{self.config.server_api_url}/api/pairing/complete"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={
                    "code": code,
                    "device_id": device_id,
                    "device_name": device_name,
                    "platform": platform,
                    "token": token,
                }) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.error(f"Failed to complete pairing: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Error completing pairing: {e}")
            return None

    async def get_pairing_status(self, telegram_id: int) -> Optional[dict]:
        """Get pairing status"""
        url = f"{self.config.server_api_url}/api/pairing/status/{telegram_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return None
        except Exception as e:
            logger.error(f"Error getting pairing status: {e}")
            return None
