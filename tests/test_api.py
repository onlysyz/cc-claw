"""Tests for client/api.py - API client for server communication."""

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import aiohttp

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.api import APIClient
from client.config import ClientConfig


class AsyncCtx:
    """Wraps a mock response so it can be used as an async context manager."""
    def __init__(self, mock_response):
        self._resp = mock_response

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *args):
        return None


def make_response(status, data=None):
    """Create a mock response for aiohttp."""
    mock = MagicMock()
    mock.status = status
    if data is not None:
        mock.json = AsyncMock(return_value=data)
    return mock


class TestAPIClientGeneratePairing:
    """Test APIClient.generate_pairing()."""

    @pytest.mark.asyncio
    async def test_generate_pairing_success(self):
        """200 response returns JSON data."""
        config = ClientConfig()
        config.server_api_url = "http://localhost:8080"
        client = APIClient(config)

        resp = make_response(200, {"code": "ABC123", "expires_at": "2024-01-01T00:00:00Z"})

        def mock_post(*args, **kwargs):
            return AsyncCtx(resp)
        mock_session = MagicMock()
        mock_session.post = mock_post
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)

        with patch('client.api.aiohttp.ClientSession', return_value=mock_session):
            result = await client.generate_pairing(telegram_id=123456)

        assert result == {"code": "ABC123", "expires_at": "2024-01-01T00:00:00Z"}

    @pytest.mark.asyncio
    async def test_generate_pairing_non_200(self):
        """Non-200 response returns None."""
        config = ClientConfig()
        config.server_api_url = "http://localhost:8080"
        client = APIClient(config)

        resp = make_response(500)

        def mock_post(*args, **kwargs):
            return AsyncCtx(resp)
        mock_session = MagicMock()
        mock_session.post = mock_post
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)

        with patch('client.api.aiohttp.ClientSession', return_value=mock_session):
            result = await client.generate_pairing(telegram_id=123456)

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_pairing_exception(self):
        """Exception returns None."""
        config = ClientConfig()
        config.server_api_url = "http://localhost:8080"
        client = APIClient(config)

        mock_session = AsyncMock()
        mock_session.__aenter__.side_effect = aiohttp.ClientError("Connection failed")

        with patch('client.api.aiohttp.ClientSession', return_value=mock_session):
            result = await client.generate_pairing(telegram_id=123456)

        assert result is None


class TestAPIClientVerifyPairing:
    """Test APIClient.verify_pairing()."""

    @pytest.mark.asyncio
    async def test_verify_pairing_valid_true(self):
        """200 with valid=True returns True."""
        config = ClientConfig()
        config.server_api_url = "http://localhost:8080"
        client = APIClient(config)

        resp = make_response(200, {"valid": True})

        def mock_post(*args, **kwargs):
            return AsyncCtx(resp)
        mock_session = MagicMock()
        mock_session.post = mock_post
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)

        with patch('client.api.aiohttp.ClientSession', return_value=mock_session):
            result = await client.verify_pairing(code="ABC123")

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_pairing_valid_false(self):
        """200 with valid=False returns False."""
        config = ClientConfig()
        config.server_api_url = "http://localhost:8080"
        client = APIClient(config)

        resp = make_response(200, {"valid": False})

        def mock_post(*args, **kwargs):
            return AsyncCtx(resp)
        mock_session = MagicMock()
        mock_session.post = mock_post
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)

        with patch('client.api.aiohttp.ClientSession', return_value=mock_session):
            result = await client.verify_pairing(code="INVALID")

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_pairing_non_200(self):
        """Non-200 response returns False."""
        config = ClientConfig()
        config.server_api_url = "http://localhost:8080"
        client = APIClient(config)

        resp = make_response(404)

        def mock_post(*args, **kwargs):
            return AsyncCtx(resp)
        mock_session = MagicMock()
        mock_session.post = mock_post
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)

        with patch('client.api.aiohttp.ClientSession', return_value=mock_session):
            result = await client.verify_pairing(code="ABC123")

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_pairing_exception(self):
        """Exception returns False."""
        config = ClientConfig()
        config.server_api_url = "http://localhost:8080"
        client = APIClient(config)

        mock_session = AsyncMock()
        mock_session.__aenter__.side_effect = asyncio.TimeoutError("Timeout")

        with patch('client.api.aiohttp.ClientSession', return_value=mock_session):
            result = await client.verify_pairing(code="ABC123")

        assert result is False


class TestAPIClientCompletePairing:
    """Test APIClient.complete_pairing()."""

    @pytest.mark.asyncio
    async def test_complete_pairing_success(self):
        """200 response returns JSON data."""
        config = ClientConfig()
        config.server_api_url = "http://localhost:8080"
        client = APIClient(config)

        resp = make_response(200, {"device_token": "tok123", "user_id": 1})

        def mock_post(*args, **kwargs):
            return AsyncCtx(resp)
        mock_session = MagicMock()
        mock_session.post = mock_post
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)

        with patch('client.api.aiohttp.ClientSession', return_value=mock_session):
            result = await client.complete_pairing(
                code="ABC123",
                device_id="device-001",
                device_name="Test Device",
                platform="darwin",
                token="token123"
            )

        assert result == {"device_token": "tok123", "user_id": 1}

    @pytest.mark.asyncio
    async def test_complete_pairing_non_200(self):
        """Non-200 response returns None."""
        config = ClientConfig()
        config.server_api_url = "http://localhost:8080"
        client = APIClient(config)

        resp = make_response(400)

        def mock_post(*args, **kwargs):
            return AsyncCtx(resp)
        mock_session = MagicMock()
        mock_session.post = mock_post
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)

        with patch('client.api.aiohttp.ClientSession', return_value=mock_session):
            result = await client.complete_pairing(
                code="ABC123",
                device_id="device-001",
                device_name="Test Device",
                platform="darwin",
                token="token123"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_complete_pairing_exception(self):
        """Exception returns None."""
        config = ClientConfig()
        config.server_api_url = "http://localhost:8080"
        client = APIClient(config)

        mock_session = AsyncMock()
        mock_session.__aenter__.side_effect = aiohttp.ClientError("Network error")

        with patch('client.api.aiohttp.ClientSession', return_value=mock_session):
            result = await client.complete_pairing(
                code="ABC123",
                device_id="device-001",
                device_name="Test Device",
                platform="darwin",
                token="token123"
            )

        assert result is None


class TestAPIClientGetPairingStatus:
    """Test APIClient.get_pairing_status()."""

    @pytest.mark.asyncio
    async def test_get_pairing_status_success(self):
        """200 response returns JSON data."""
        config = ClientConfig()
        config.server_api_url = "http://localhost:8080"
        client = APIClient(config)

        resp = make_response(200, {"paired": True, "device_id": "device-001"})

        def mock_get(*args, **kwargs):
            return AsyncCtx(resp)
        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)

        with patch('client.api.aiohttp.ClientSession', return_value=mock_session):
            result = await client.get_pairing_status(telegram_id=123456)

        assert result == {"paired": True, "device_id": "device-001"}

    @pytest.mark.asyncio
    async def test_get_pairing_status_non_200(self):
        """Non-200 response returns None."""
        config = ClientConfig()
        config.server_api_url = "http://localhost:8080"
        client = APIClient(config)

        resp = make_response(404)

        def mock_get(*args, **kwargs):
            return AsyncCtx(resp)
        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)

        with patch('client.api.aiohttp.ClientSession', return_value=mock_session):
            result = await client.get_pairing_status(telegram_id=999999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_pairing_status_exception(self):
        """Exception returns None."""
        config = ClientConfig()
        config.server_api_url = "http://localhost:8080"
        client = APIClient(config)

        mock_session = AsyncMock()
        mock_session.__aenter__.side_effect = OSError("Connection refused")

        with patch('client.api.aiohttp.ClientSession', return_value=mock_session):
            result = await client.get_pairing_status(telegram_id=123456)

        assert result is None
