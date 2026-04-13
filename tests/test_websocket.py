"""Tests for websocket.py - WebSocketManager."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.websocket import WebSocketManager, Message
from client.config import ClientConfig


class TestWebSocketManagerConnect:
    """Test WebSocket connection."""

    @pytest.mark.asyncio
    async def test_connect_builds_url_with_token(self):
        config = MagicMock()
        config.server_ws_url = "wss://example.com/ws"
        config.device_token = "test-token"
        config.device_id = "device-123"

        with patch("client.websocket.websockets.connect", new_callable=AsyncMock) as mock_connect:
            ws = WebSocketManager(config)
            await ws.connect()

            call_args = mock_connect.call_args
            url = call_args[0][0]
            assert "token=test-token" in url
            assert "device_id=device-123" in url

    @pytest.mark.asyncio
    async def test_connect_returns_false_on_failure(self):
        config = MagicMock()
        config.server_ws_url = "wss://invalid.example.com"

        with patch("client.websocket.websockets.connect", side_effect=Exception("Connection failed")):
            ws = WebSocketManager(config)
            result = await ws.connect()

            assert result is False


class TestWebSocketManagerDisconnect:
    """Test WebSocket disconnection."""

    @pytest.mark.asyncio
    async def test_disconnect_closes_websocket(self):
        config = MagicMock()
        mock_ws = AsyncMock()

        with patch("client.websocket.websockets.connect", new_callable=AsyncMock):
            ws = WebSocketManager(config)
            ws.ws = mock_ws
            ws._running = True

            await ws.disconnect()

            mock_ws.close.assert_called_once()
            assert ws._running is False


class TestWebSocketManagerSend:
    """Test sending messages."""

    @pytest.mark.asyncio
    async def test_send_serializes_json(self):
        config = MagicMock()
        mock_ws = AsyncMock()

        with patch("client.websocket.websockets.connect", new_callable=AsyncMock):
            ws = WebSocketManager(config)
            ws.ws = mock_ws
            ws._running = True

            result = await ws.send({"type": "test", "data": "value"})

            assert result is True
            mock_ws.send.assert_called_once()
            sent_data = mock_ws.send.call_args[0][0]
            assert json.loads(sent_data) == {"type": "test", "data": "value"}

    @pytest.mark.asyncio
    async def test_send_returns_false_when_not_connected(self):
        config = MagicMock()
        ws = WebSocketManager(config)
        ws._running = False

        result = await ws.send({"type": "test"})

        assert result is False


class TestWebSocketManagerSendMessage:
    """Test send_message."""

    @pytest.mark.asyncio
    async def test_send_message_includes_all_fields(self):
        config = MagicMock()
        mock_ws = AsyncMock()

        with patch("client.websocket.websockets.connect", new_callable=AsyncMock):
            ws = WebSocketManager(config)
            ws.ws = mock_ws
            ws._running = True

            result = await ws.send_message(
                content="Hello",
                message_id="msg-123",
                images=["img1.png"],
                lark_open_id="user-456"
            )

            assert result is True
            call_args = mock_ws.send.call_args[0][0]
            data = json.loads(call_args)

            assert data["type"] == "message"
            assert data["content"] == "Hello"
            assert data["message_id"] == "msg-123"
            assert data["images"] == ["img1.png"]
            assert data["lark_open_id"] == "user-456"


class TestWebSocketManagerSendAck:
    """Test sending acknowledgments."""

    @pytest.mark.asyncio
    async def test_send_ack(self):
        config = MagicMock()
        mock_ws = AsyncMock()

        with patch("client.websocket.websockets.connect", new_callable=AsyncMock):
            ws = WebSocketManager(config)
            ws.ws = mock_ws
            ws._running = True

            result = await ws.send_ack("msg-123")

            assert result is True
            call_args = mock_ws.send.call_args[0][0]
            data = json.loads(call_args)
            assert data["type"] == "ack"
            assert data["message_id"] == "msg-123"


class TestWebSocketManagerSendNotification:
    """Test sending notifications."""

    @pytest.mark.asyncio
    async def test_send_notification(self):
        config = MagicMock()
        mock_ws = AsyncMock()

        with patch("client.websocket.websockets.connect", new_callable=AsyncMock):
            ws = WebSocketManager(config)
            ws.ws = mock_ws
            ws._running = True

            result = await ws.send_notification("Task completed!")

            assert result is True
            call_args = mock_ws.send.call_args[0][0]
            data = json.loads(call_args)
            assert data["type"] == "notification"
            assert data["content"] == "Task completed!"


class TestWebSocketManagerRegister:
    """Test device registration."""

    @pytest.mark.asyncio
    async def test_register_sends_device_info(self):
        config = MagicMock()
        config.device_id = "device-123"
        config.device_token = "secret-token"
        mock_ws = AsyncMock()

        with patch("client.websocket.websockets.connect", new_callable=AsyncMock):
            ws = WebSocketManager(config)
            ws.ws = mock_ws
            ws._running = True

            result = await ws.register()

            assert result is True
            call_args = mock_ws.send.call_args[0][0]
            data = json.loads(call_args)
            assert data["type"] == "register"
            assert data["device_id"] == "device-123"
            assert data["token"] == "secret-token"

    @pytest.mark.asyncio
    async def test_register_fails_without_credentials(self):
        config = MagicMock()
        config.device_id = None
        config.device_token = None

        ws = WebSocketManager(config)
        result = await ws.register()

        assert result is False


class TestWebSocketManagerOn:
    """Test message handler registration."""

    def test_on_registers_handler(self):
        config = MagicMock()
        ws = WebSocketManager(config)

        async def handler(msg):
            pass

        ws.on("message", handler)

        assert "message" in ws._message_handlers
        assert ws._message_handlers["message"] is handler


class TestWebSocketManagerIsConnected:
    """Test connection state check."""

    def test_is_connected_false_when_not_running(self):
        config = MagicMock()
        ws = WebSocketManager(config)
        ws._running = False

        assert ws.is_connected is False

    def test_is_connected_false_when_ws_none(self):
        config = MagicMock()
        ws = WebSocketManager(config)
        ws._running = True
        ws.ws = None

        assert ws.is_connected is False

    def test_is_connected_true_when_state_is_open(self):
        from websockets.connection import State

        config = MagicMock()
        mock_ws = MagicMock()
        mock_ws.state = State.OPEN

        ws = WebSocketManager(config)
        ws._running = True
        ws.ws = mock_ws

        assert ws.is_connected is True

    def test_is_connected_false_when_state_is_closed(self):
        from websockets.connection import State

        config = MagicMock()
        mock_ws = MagicMock()
        mock_ws.state = State.CLOSED

        ws = WebSocketManager(config)
        ws._running = True
        ws.ws = mock_ws

        assert ws.is_connected is False

    def test_is_connected_false_when_not_running_despite_open_state(self):
        """_running=False short-circuits even if ws state is OPEN."""
        from websockets.connection import State

        config = MagicMock()
        mock_ws = MagicMock()
        mock_ws.state = State.OPEN

        ws = WebSocketManager(config)
        ws._running = False
        ws.ws = mock_ws

        assert ws.is_connected is False
