"""Tests for minimax.py - MiniMax API client."""

import asyncio
import os
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.minimax import MiniMaxClient


class TestMiniMaxClientInit:
    """Test MiniMaxClient.__init__() branches."""

    def test_client_is_none_when_api_key_missing(self, caplog):
        """No api_key → client=None, error logged."""
        with patch.dict(os.environ, {}, clear=True):
            client = MiniMaxClient()
            assert client.client is None
            assert any("API key not configured" in r.message for r in caplog.records)

    def test_client_initialized_with_env_api_key(self):
        """api_key in env → client is Anthropic instance."""
        with patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "test-key-123",
            "MINIMAX_API_URL": ""
        }, clear=True):
            with patch('anthropic.Anthropic') as mock_anthropic:
                mock_anthropic.return_value = MagicMock()
                client = MiniMaxClient()
                assert client.client is not None
                mock_anthropic.assert_called_once_with(api_key="test-key-123")

    def test_client_initialized_with_minimax_api_key(self):
        """MINIMAX_API_KEY env var also works."""
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "minimax-key"}, clear=True):
            with patch('anthropic.Anthropic') as mock_anthropic:
                mock_anthropic.return_value = MagicMock()
                client = MiniMaxClient()
                assert client.client is not None
                assert client.api_key == "minimax-key"

    def test_base_url_passed_when_set(self):
        """base_url parameter is passed to Anthropic client."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}, clear=False):
            with patch('anthropic.Anthropic') as mock_anthropic:
                mock_anthropic.return_value = MagicMock()
                client = MiniMaxClient(base_url="https://custom.url")
                assert client.client is not None
                mock_anthropic.assert_called_once_with(
                    api_key="key",
                    base_url="https://custom.url",
                )

    def test_base_url_from_env(self):
        """ANTHROPIC_BASE_URL env var is used as base_url."""
        with patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "key",
            "ANTHROPIC_BASE_URL": "https://env.url"
        }, clear=False):
            with patch('anthropic.Anthropic') as mock_anthropic:
                mock_anthropic.return_value = MagicMock()
                client = MiniMaxClient()
                assert client.base_url == "https://env.url"

    def test_model_param_passed_correctly(self):
        """model parameter is stored and used."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}, clear=False):
            with patch('anthropic.Anthropic') as mock_anthropic:
                mock_anthropic.return_value = MagicMock()
                client = MiniMaxClient(model="MyModel")
                assert client.model == "MyModel"

    def test_default_model_is_minimax_m2_7(self):
        """Default model is MiniMax-M2.7."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}, clear=False):
            with patch('anthropic.Anthropic'):
                client = MiniMaxClient()
                assert client.model == "MiniMax-M2.7"

    def test_no_base_url_when_not_provided(self):
        """No base_url → not passed to Anthropic kwargs."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}, clear=True):
            with patch('anthropic.Anthropic') as mock_anthropic:
                mock_anthropic.return_value = MagicMock()
                client = MiniMaxClient()
                assert client.client is not None
                mock_anthropic.assert_called_once_with(api_key="key")


class TestMiniMaxClientChat:
    """Test MiniMaxClient.chat() normal path."""

    @pytest.mark.asyncio
    async def test_chat_returns_text_and_usage(self):
        """Successful API call returns (text, usage_dict)."""
        mock_block = MagicMock()
        mock_block.text = "Goal decomposed into 3 tasks."

        mock_usage = MagicMock()
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50

        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_response.usage = mock_usage

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}, clear=True):
            async def mock_run_in_executor(_, func, *args, **kwargs):
                return func(*args, **kwargs)

            with patch('asyncio.get_event_loop') as mock_loop_cls:
                mock_loop = MagicMock()
                mock_loop.run_in_executor = mock_run_in_executor
                mock_loop_cls.return_value = mock_loop

                client = MiniMaxClient()
                client.client = mock_client

                text, data = await client.chat("Decompose this goal")

                assert text == "Goal decomposed into 3 tasks."
                assert data == {"usage": {"input_tokens": 100, "output_tokens": 50}}

    @pytest.mark.asyncio
    async def test_chat_with_system_prompt(self):
        """system_prompt is passed to messages.create."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="result")]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}, clear=True):
            async def mock_run_in_executor(_, func, *args, **kwargs):
                return func(*args, **kwargs)

            with patch('asyncio.get_event_loop') as mock_loop_cls:
                mock_loop = MagicMock()
                mock_loop.run_in_executor = mock_run_in_executor
                mock_loop_cls.return_value = mock_loop

                client = MiniMaxClient()
                client.client = mock_client

                await client.chat("user prompt", system_prompt="You are helpful")

                call_kwargs = mock_client.messages.create.call_args[1]
                assert call_kwargs["system"] == "You are helpful"
                assert call_kwargs["messages"] == [{"role": "user", "content": "user prompt"}]
                assert call_kwargs["model"] == "MiniMax-M2.7"
                assert call_kwargs["max_tokens"] == 4096

    @pytest.mark.asyncio
    async def test_chat_no_system_prompt_passes_none(self):
        """No system_prompt → None passed to API."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="result")]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}, clear=True):
            async def mock_run_in_executor(_, func, *args, **kwargs):
                return func(*args, **kwargs)

            with patch('asyncio.get_event_loop') as mock_loop_cls:
                mock_loop = MagicMock()
                mock_loop.run_in_executor = mock_run_in_executor
                mock_loop_cls.return_value = mock_loop

                client = MiniMaxClient()
                client.client = mock_client

                await client.chat("prompt only")

                call_kwargs = mock_client.messages.create.call_args[1]
                assert call_kwargs["system"] is None


class TestMiniMaxClientChatExceptions:
    """Test MiniMaxClient.chat() exception paths."""

    @pytest.mark.asyncio
    async def test_chat_returns_error_when_no_api_key(self):
        """No api_key → returns error text."""
        with patch.dict(os.environ, {}, clear=True):
            client = MiniMaxClient()
            text, data = await client.chat("hello")
            assert "API key not configured" in text
            assert data is None

    @pytest.mark.asyncio
    async def test_chat_returns_error_when_client_is_none(self):
        """client is None → returns error text."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}, clear=True):
            client = MiniMaxClient()
            client.client = None
            text, data = await client.chat("hello")
            assert "not initialized" in text
            assert data is None

    @pytest.mark.asyncio
    async def test_chat_returns_error_on_api_error(self):
        """APIError → error message with status code."""
        import anthropic

        mock_client = MagicMock()
        # Create APIError with proper signature: (message, request, *, body)
        mock_request = MagicMock()
        mock_request.url = "https://api.minimaxi.com/anthropic"
        api_error = anthropic.APIError(message="Rate limit exceeded", request=mock_request, body=None)
        mock_client.messages.create.side_effect = api_error

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}, clear=True):
            async def mock_run_in_executor(_, func, *args, **kwargs):
                return func(*args, **kwargs)

            with patch('asyncio.get_event_loop') as mock_loop_cls:
                mock_loop = MagicMock()
                mock_loop.run_in_executor = mock_run_in_executor
                mock_loop_cls.return_value = mock_loop

                client = MiniMaxClient()
                client.client = mock_client

                text, data = await client.chat("hello")

                # APIError has no status_code attr → getattr returns '?', message contains 'Rate limit exceeded'
                assert "Error" in text
                assert data is None

    @pytest.mark.asyncio
    async def test_chat_returns_error_on_generic_exception(self):
        """Generic Exception → error message."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("connection refused")

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}, clear=True):
            async def mock_run_in_executor(_, func, *args, **kwargs):
                return func(*args, **kwargs)

            with patch('asyncio.get_event_loop') as mock_loop_cls:
                mock_loop = MagicMock()
                mock_loop.run_in_executor = mock_run_in_executor
                mock_loop_cls.return_value = mock_loop

                client = MiniMaxClient()
                client.client = mock_client

                text, data = await client.chat("hello")

                assert "connection refused" in text
                assert data is None

