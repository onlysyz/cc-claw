"""CC-Claw MiniMax API Client - For goal decomposition to save Claude Code tokens

Uses the standard Anthropic SDK with MiniMax's API endpoint.
Set environment variables:
  ANTHROPIC_API_KEY=your-minimax-api-key
  ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic  (optional, for MiniMax)
"""

import os
import asyncio
import logging
from typing import Tuple, Optional

import anthropic

logger = logging.getLogger(__name__)


class MiniMaxClient:
    """Call MiniMax API for goal decomposition using Anthropic SDK"""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = "MiniMax-M2.7"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("MINIMAX_API_KEY")
        self.base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL") or os.environ.get("MINIMAX_API_URL")
        self.model = model or os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7")

        if not self.api_key:
            logger.error("MiniMax API key not configured (ANTHROPIC_API_KEY or MINIMAX_API_KEY)")
            logger.error(f"  env vars: ANTHROPIC_API_KEY={os.environ.get('ANTHROPIC_API_KEY', 'NOT SET')}, MINIMAX_API_KEY={os.environ.get('MINIMAX_API_KEY', 'NOT SET')}")
            self.client = None
            return

        # Build client kwargs
        kwargs = {
            "api_key": self.api_key,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url

        self.client = anthropic.Anthropic(**kwargs)
        logger.info(f"MiniMax client initialized: model={self.model}, base_url={self.base_url}")

    async def chat(self, prompt: str, system_prompt: str = "") -> Tuple[str, Optional[dict]]:
        """Send a chat request to MiniMax API (runs sync SDK call in executor)
        Returns: (text_response, raw_response_dict)
        """
        if not self.api_key:
            return "Error: MiniMax API key not configured", None

        if not hasattr(self, 'client') or self.client is None:
            return "Error: MiniMax client not initialized", None

        def _call():
            return self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt or None,
                messages=[{"role": "user", "content": prompt}],
            )

        try:
            # Run sync HTTP call in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, _call)

            # Extract text from response
            text_parts = []
            for block in response.content:
                if hasattr(block, 'text') and block.text:
                    text_parts.append(block.text)
            text = "\n".join(text_parts)

            logger.info(f"MiniMax response: {text[:100]}...")

            usage = None
            if hasattr(response, 'usage') and response.usage:
                usage = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                }

            return text, {"usage": usage}

        except anthropic.APIError as e:
            logger.error(f"MiniMax API error {getattr(e, 'status_code', '?')}: {e}")
            return f"Error: API returned {getattr(e, 'status_code', '?')}", None
        except Exception as e:
            logger.error(f"MiniMax unexpected error: {e}")
            return f"Error: {e}", None

