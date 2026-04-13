"""CC-Claw Token Tracker Module - Parses Claude output for token usage and 429 detection"""

import re
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token usage extracted from Claude response"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: Optional[float] = None


class TokenTracker:
    """Parse Claude CLI output to extract token usage and detect errors"""

    # Anthropic pricing (approximate, per 1M tokens)
    PRICING = {
        "claude-opus-4-5": {"input": 15.0, "output": 75.0},
        "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5": {"input": 0.8, "output": 4.0},
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-5-haiku": {"input": 0.8, "output": 4.0},
        "claude-3-opus": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
    }

    def __init__(self, model: str = "claude-sonnet-4-5"):
        self.model = model

    def parse_json_response(self, raw_output: str) -> Tuple[Optional[str], Optional[TokenUsage], bool]:
        """Parse Claude --print JSON output
        Returns: (result_text, token_usage, is_rate_limited)
        """
        is_rate_limited = self._detect_rate_limit(raw_output)

        # Find JSON block
        json_start = raw_output.find('{')
        if json_start == -1:
            return raw_output.strip(), None, is_rate_limited

        json_str = raw_output[json_start:]

        try:
            import json
            data = json.loads(json_str)

            # Extract result text
            result = data.get('result', '')

            # Extract token usage if present
            usage = None
            if 'usage' in data:
                usage_data = data['usage']
                input_tok = usage_data.get('input_tokens', 0)
                output_tok = usage_data.get('output_tokens', 0)
                total = input_tok + output_tok

                # Estimate cost
                cost = self._estimate_cost(total, input_tok, output_tok)

                usage = TokenUsage(
                    input_tokens=input_tok,
                    output_tokens=output_tok,
                    total_tokens=total,
                    cost_usd=cost,
                )

            return result, usage, is_rate_limited

        except json.JSONDecodeError:
            return raw_output.strip(), None, is_rate_limited

    def _detect_rate_limit(self, output: str) -> bool:
        """Detect if output indicates a 429 rate limit error"""
        output_lower = output.lower()
        indicators = [
            "429",
            "rate limit",
            "too many requests",
            "rate_limit_exceeded",
            "overloaded",
            "try again later",
            "retry after",
            "quota exceeded",
        ]
        return any(ind in output_lower for ind in indicators)

    def parse_streaming_output(self, raw_output: str) -> Tuple[Optional[str], Optional[TokenUsage], bool]:
        """Parse streaming output (non-JSON mode) for token info and errors
        Streaming output looks like:
        {
          "type": "usage",
          "usage": { "input_tokens": 100, "output_tokens": 200 }
        }
        {
          "type": "content",
          "content": [...]
        }
        """
        is_rate_limited = self._detect_rate_limit(raw_output)

        # Try to extract usage block from streaming output
        total_input = 0
        total_output = 0
        texts = []

        for line in raw_output.split('\n'):
            if not line.strip():
                continue
            try:
                import json
                obj = json.loads(line)
                obj_type = obj.get('type', '')

                if obj_type == 'usage':
                    usage_data = obj.get('usage', {})
                    total_input += usage_data.get('input_tokens', 0)
                    total_output += usage_data.get('output_tokens', 0)
                elif obj_type == 'content':
                    content = obj.get('content', '')
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                texts.append(item.get('text', ''))
                    elif isinstance(content, str):
                        texts.append(content)
                elif obj_type == 'error':
                    if obj.get('error', {}).get('type') == 'rate_limit_error':
                        is_rate_limited = True
            except json.JSONDecodeError:
                # Not a JSON line, might be plain text
                if line.strip():
                    texts.append(line.strip())

        result = '\n'.join(texts)
        usage = None
        if total_input > 0 or total_output > 0:
            usage = TokenUsage(
                input_tokens=total_input,
                output_tokens=total_output,
                total_tokens=total_input + total_output,
                cost_usd=self._estimate_cost(total_input + total_output, total_input, total_output),
            )

        return result, usage, is_rate_limited

    def _build_usage(self, usage_data: dict) -> Optional[TokenUsage]:
        """Build TokenUsage from raw usage dict (from parsed JSON)"""
        if not usage_data:
            return None
        try:
            input_tok = usage_data.get('input_tokens', 0)
            output_tok = usage_data.get('output_tokens', 0)
            total = input_tok + output_tok
            cost = self._estimate_cost(total, input_tok, output_tok)
            return TokenUsage(
                input_tokens=input_tok,
                output_tokens=output_tok,
                total_tokens=total,
                cost_usd=cost,
            )
        except Exception:
            return None

    def _estimate_cost(self, total: int, input_tok: int, output_tok: int) -> Optional[float]:
        """Estimate cost in USD based on model pricing"""
        pricing = self.PRICING.get(self.model)
        if not pricing:
            return None

        # Cost per token (divide by 1M)
        input_cost = (input_tok / 1_000_000) * pricing["input"]
        output_cost = (output_tok / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 6)

    def format_usage_report(self, usage: TokenUsage) -> str:
        """Format token usage as a readable string"""
        lines = [
            f"📊 **Token Usage**",
            f"   Input:  {usage.input_tokens:,} tokens",
            f"   Output: {usage.output_tokens:,} tokens",
            f"   Total:  {usage.total_tokens:,} tokens",
        ]
        if usage.cost_usd is not None:
            lines.append(f"   Est. cost: ${usage.cost_usd:.4f}")
        return "\n".join(lines)
