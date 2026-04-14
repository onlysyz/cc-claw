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
    async def test_connect_success(self):
        """Successful connection returns True."""
        config = MagicMock()
        config.server_ws_url = "wss://example.com/ws"
        config.device_token = None
        config.device_id = None

        with patch("client.websocket.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_ws = AsyncMock()
            mock_connect.return_value = mock_ws

            ws = WebSocketManager(config)
            result = await ws.connect()

            assert result is True
            assert ws.ws is mock_ws
            assert ws._running is True

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
    async def test_connect_url_without_token_when_missing(self):
        """URL does not include token params when device_token or device_id is None."""
        config = MagicMock()
        config.server_ws_url = "wss://example.com/ws"
        config.device_token = None
        config.device_id = "device-123"

        with patch("client.websocket.websockets.connect", new_callable=AsyncMock) as mock_connect:
            ws = WebSocketManager(config)
            await ws.connect()

            url = mock_connect.call_args[0][0]
            assert "token=" not in url
            assert "device_id=" not in url

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

    @pytest.mark.asyncio
    async def test_disconnect_cancels_reconnect_task(self):
        """When _reconnect_task exists, it should be cancelled."""
        config = MagicMock()
        mock_task = AsyncMock()

        with patch("client.websocket.websockets.connect", new_callable=AsyncMock):
            ws = WebSocketManager(config)
            ws.ws = None
            ws._running = True
            ws._reconnect_task = mock_task

            await ws.disconnect()

            mock_task.cancel.assert_called_once()
            assert ws._reconnect_task is None
            assert ws._running is False

    @pytest.mark.asyncio
    async def test_disconnect_no_ws_does_not_call_close(self):
        """When ws is None, close() should not be called."""
        config = MagicMock()

        with patch("client.websocket.websockets.connect", new_callable=AsyncMock):
            ws = WebSocketManager(config)
            ws.ws = None
            ws._running = True

            await ws.disconnect()

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

    @pytest.mark.asyncio
    async def test_send_returns_false_when_ws_none(self):
        """ws=None should return False without calling send."""
        config = MagicMock()
        ws = WebSocketManager(config)
        ws.ws = None
        ws._running = True

        result = await ws.send({"type": "test"})

        assert result is False

    @pytest.mark.asyncio
    async def test_send_exception_returns_false(self):
        """ws.send() raising exception should return False."""
        config = MagicMock()
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = Exception("Send failed")

        with patch("client.websocket.websockets.connect", new_callable=AsyncMock):
            ws = WebSocketManager(config)
            ws.ws = mock_ws
            ws._running = True

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

    @pytest.mark.asyncio
    async def test_send_message_without_optional_fields(self):
        """images=None and lark_open_id=None should not appear in payload."""
        config = MagicMock()
        mock_ws = AsyncMock()

        with patch("client.websocket.websockets.connect", new_callable=AsyncMock):
            ws = WebSocketManager(config)
            ws.ws = mock_ws
            ws._running = True

            result = await ws.send_message(
                content="Hello",
                message_id="msg-123"
            )

            assert result is True
            call_args = mock_ws.send.call_args[0][0]
            data = json.loads(call_args)

            assert data["type"] == "message"
            assert data["content"] == "Hello"
            assert data["message_id"] == "msg-123"
            assert "images" not in data
            assert "lark_open_id" not in data

    @pytest.mark.asyncio
    async def test_send_message_with_only_images(self):
        """Only images provided, lark_open_id is None."""
        config = MagicMock()
        mock_ws = AsyncMock()

        with patch("client.websocket.websockets.connect", new_callable=AsyncMock):
            ws = WebSocketManager(config)
            ws.ws = mock_ws
            ws._running = True

            result = await ws.send_message(
                content="Hello",
                message_id="msg-123",
                images=["img1.png"]
            )

            assert result is True
            call_args = mock_ws.send.call_args[0][0]
            data = json.loads(call_args)

            assert data["images"] == ["img1.png"]
            assert "lark_open_id" not in data

    @pytest.mark.asyncio
    async def test_send_message_with_only_lark_open_id(self):
        """Only lark_open_id provided, images is None."""
        config = MagicMock()
        mock_ws = AsyncMock()

        with patch("client.websocket.websockets.connect", new_callable=AsyncMock):
            ws = WebSocketManager(config)
            ws.ws = mock_ws
            ws._running = True

            result = await ws.send_message(
                content="Hello",
                message_id="msg-123",
                lark_open_id="user-456"
            )

            assert result is True
            call_args = mock_ws.send.call_args[0][0]
            data = json.loads(call_args)

            assert data["lark_open_id"] == "user-456"
            assert "images" not in data


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


class TestWebSocketManagerListen:
    """Test listen() method."""

    @pytest.mark.asyncio
    async def test_listen_returns_early_when_ws_none(self):
        """ws=None should return immediately without listening."""
        config = MagicMock()
        ws = WebSocketManager(config)
        ws.ws = None

        await ws.listen()

    @pytest.mark.asyncio
    async def test_listen_message_handler_called(self):
        """When a message with registered handler is received, handler should be called."""
        import websockets.exceptions

        config = MagicMock()
        config.auto_reconnect = False

        async def async_messages():
            yield '{"type": "message", "data": {"content": "hello", "message_id": "msg-1"}}'
            raise websockets.exceptions.ConnectionClosed(None, None)

        mock_ws = MagicMock()
        mock_ws.__aiter__ = lambda self: async_messages()

        ws = WebSocketManager(config)
        ws.ws = mock_ws
        ws._running = True

        received = []

        async def handler(msg):
            received.append(msg)

        ws.on("message", handler)

        await ws.listen()
        await asyncio.sleep(0)  # Allow create_task handler to complete

        assert len(received) == 1
        assert received[0].type == "message"
        assert received[0].data["content"] == "hello"
        assert received[0].message_id == "msg-1"
        assert ws._running is False

    @pytest.mark.asyncio
    async def test_listen_no_handler_message_ignored(self):
        """When no handler is registered, message should be ignored gracefully."""
        import websockets.exceptions

        config = MagicMock()
        config.auto_reconnect = False
        mock_ws = MagicMock()

        async def mock_aiter():
            yield '{"type": "unknown_type", "data": {"foo": "bar"}}'
            raise websockets.exceptions.ConnectionClosed(None, None)

        mock_ws.__aiter__ = mock_aiter

        ws = WebSocketManager(config)
        ws.ws = mock_ws
        ws._running = True

        await ws.listen()

        assert ws._running is False

    @pytest.mark.asyncio
    async def test_listen_invalid_json_logs_error(self):
        """Invalid JSON should be logged and listening should continue."""
        import websockets.exceptions

        config = MagicMock()
        config.auto_reconnect = False
        mock_ws = MagicMock()

        async def mock_aiter():
            yield "not valid json{"
            raise websockets.exceptions.ConnectionClosed(None, None)

        mock_ws.__aiter__ = mock_aiter

        ws = WebSocketManager(config)
        ws.ws = mock_ws
        ws._running = True

        await ws.listen()

        assert ws._running is False

    @pytest.mark.asyncio
    async def test_listen_connection_closed(self):
        """ConnectionClosed exception should be caught and _running set to False."""
        import websockets.exceptions

        config = MagicMock()
        config.auto_reconnect = False
        mock_ws = MagicMock()

        async def mock_aiter():
            raise websockets.exceptions.ConnectionClosed(None, None)

        mock_ws.__aiter__ = mock_aiter

        ws = WebSocketManager(config)
        ws.ws = mock_ws
        ws._running = True

        await ws.listen()

        assert ws._running is False

    @pytest.mark.asyncio
    async def test_listen_schedules_reconnect_on_auto_reconnect(self):
        """When auto_reconnect=True, _schedule_reconnect should be called."""
        import websockets.exceptions

        config = MagicMock()
        config.auto_reconnect = True
        config.reconnect_delay = 0.01
        mock_ws = MagicMock()

        async def mock_aiter():
            yield '{"type": "message", "data": {}}'
            raise websockets.exceptions.ConnectionClosed(None, None)

        mock_ws.__aiter__ = mock_aiter

        ws = WebSocketManager(config)
        ws.ws = mock_ws
        ws._running = True

        with patch.object(ws, '_schedule_reconnect', new_callable=AsyncMock) as mock_reconnect:
            await ws.listen()

            mock_reconnect.assert_called_once()
        assert ws._running is False

    @pytest.mark.asyncio
    async def test_listen_multiple_messages(self):
        """Multiple messages should each trigger handler."""
        import websockets.exceptions

        config = MagicMock()
        config.auto_reconnect = False

        class MockAsyncIterator:
            def __init__(self):
                self.msgs = [
                    '{"type": "message", "data": {"content": "first", "message_id": "m1"}}',
                    '{"type": "message", "data": {"content": "second", "message_id": "m2"}}',
                ]
                self.closed = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.msgs:
                    return self.msgs.pop(0)
                if not self.closed:
                    self.closed = True
                    raise websockets.exceptions.ConnectionClosed(None, None)
                raise StopAsyncIteration

        mock_ws = MockAsyncIterator()

        ws = WebSocketManager(config)
        ws.ws = mock_ws
        ws._running = True

        received = []

        async def handler(msg):
            received.append(msg)

        ws.on("message", handler)

        await ws.listen()
        await asyncio.sleep(0)  # Allow create_task handlers to complete

        assert len(received) == 2
        assert received[0].message_id == "m1"
        assert received[1].message_id == "m2"


class TestWebSocketManagerScheduleReconnect:
    """Test _schedule_reconnect() method."""

    @pytest.mark.asyncio
    async def test_schedule_reconnect_returns_early_when_disabled(self):
        """When auto_reconnect=False, should return immediately without sleeping."""
        config = MagicMock()
        config.auto_reconnect = False
        config.reconnect_delay = 999

        ws = WebSocketManager(config)
        ws._running = True  # should not matter since auto_reconnect=False

        import time
        start = time.time()
        await ws._schedule_reconnect()
        elapsed = time.time() - start

        assert elapsed < 0.1  # Should return immediately

    @pytest.mark.asyncio
    async def test_schedule_reconnect_returns_early_if_running(self):
        """If _running becomes True during sleep, should not reconnect."""
        config = MagicMock()
        config.auto_reconnect = True
        config.reconnect_delay = 0.01
        config.server_ws_url = "wss://example.com/ws"
        config.device_token = None
        config.device_id = None

        ws = WebSocketManager(config)
        ws._running = False

        with patch('client.websocket.websockets.connect', new_callable=AsyncMock) as mock_connect:
            # Set _running to True during the sleep, simulating another task
            async def set_running_true():
                await asyncio.sleep(0.005)
                ws._running = True

            asyncio.create_task(set_running_true())
            await ws._schedule_reconnect()

            # connect() should not be called since _running became True
            mock_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_schedule_reconnect_success_flow(self):
        """When auto_reconnect=True and _running=False, should connect and register."""
        config = MagicMock()
        config.auto_reconnect = True
        config.reconnect_delay = 0.01
        config.server_ws_url = "wss://example.com/ws"
        config.device_token = "token"
        config.device_id = "device"
        mock_ws = AsyncMock()

        ws = WebSocketManager(config)
        ws._running = False

        with patch('client.websocket.websockets.connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            async def mock_register():
                return True

            original_listen = ws.listen
            listen_called = []

            async def mock_listen():
                listen_called.append(True)

            with patch.object(ws, 'register', mock_register):
                with patch.object(ws, 'listen', mock_listen):
                    await ws._schedule_reconnect()
                    await asyncio.sleep(0.005)

            mock_connect.assert_called_once()
            # listen is called via create_task so we just verify connect succeeded
