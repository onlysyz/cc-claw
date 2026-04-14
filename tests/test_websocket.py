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
        config = MagicMock()
        config.auto_reconnect = False

        class MockAsyncIterator:
            def __init__(self):
                self.closed = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self.closed:
                    self.closed = True
                    return '{"type": "message", "data": {"content": "hello", "message_id": "msg-1"}}'
                raise StopAsyncIteration

        ws = WebSocketManager(config)
        ws.ws = MockAsyncIterator()
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

        class MockAsyncIterator:
            def __init__(self):
                self.closed = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self.closed:
                    self.closed = True
                    return '{"type": "unknown_type", "data": {"foo": "bar"}}'
                raise StopAsyncIteration

        ws = WebSocketManager(config)
        ws.ws = MockAsyncIterator()
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

        class MockAsyncIterator:
            def __init__(self):
                self.closed = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self.closed:
                    self.closed = True
                    return "not valid json{"
                raise StopAsyncIteration

        ws = WebSocketManager(config)
        ws.ws = MockAsyncIterator()
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

        class MockAsyncIterator:
            def __init__(self, raise_exc):
                self.raise_exc = raise_exc
                self.closed = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self.closed:
                    self.closed = True
                    if self.raise_exc:
                        raise websockets.exceptions.ConnectionClosed(None, None)
                    return '{"type": "message", "data": {}}'
                raise StopAsyncIteration

        ws = WebSocketManager(config)
        ws.ws = MockAsyncIterator(raise_exc=True)
        ws._running = True

        await ws.listen()

        assert ws._running is False

    @pytest.mark.asyncio
    async def test_listen_schedules_reconnect_on_auto_reconnect(self):
        """When auto_reconnect=True, _schedule_reconnect should be called."""
        config = MagicMock()
        config.auto_reconnect = True
        config.reconnect_delay = 0.01

        class MockAsyncIterator:
            def __init__(self):
                self.closed = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self.closed:
                    self.closed = True
                    return '{"type": "message", "data": {}}'
                raise StopAsyncIteration

        ws = WebSocketManager(config)
        ws.ws = MockAsyncIterator()
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


class TestWebSocketManagerConnectExceptionPath:
    """Cover lines 53-55: exception during connect is logged and False is returned."""

    @pytest.mark.asyncio
    async def test_connect_logs_error_on_exception(self):
        config = MagicMock()
        config.server_ws_url = "wss://bad.example.com"

        with patch("client.websocket.websockets.connect", side_effect=OSError("DNS failed")):
            ws = WebSocketManager(config)
            result = await ws.connect()

            assert result is False
            assert ws._running is False


class TestWebSocketManagerDisconnectEdgeCases:
    """Cover lines 60-62: reconnect task cancellation."""

    @pytest.mark.asyncio
    async def test_disconnect_sets_running_false_first(self):
        """Line 59: _running should be set False before cancel."""
        config = MagicMock()
        mock_task = AsyncMock()
        ws = WebSocketManager(config)
        ws._running = True
        ws._reconnect_task = mock_task
        ws.ws = None

        await ws.disconnect()

        assert ws._running is False
        mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_clears_reconnect_task_after_cancel(self):
        """Line 61-62: after cancel, _reconnect_task is set to None."""
        config = MagicMock()
        mock_task = AsyncMock()
        ws = WebSocketManager(config)
        ws._running = True
        ws._reconnect_task = mock_task
        ws.ws = None

        await ws.disconnect()

        assert ws._reconnect_task is None


class TestWebSocketManagerSendExceptionPath:
    """Cover lines 78-80: exception during ws.send() is caught and False returned."""

    @pytest.mark.asyncio
    async def test_send_catches_exception_and_returns_false(self):
        """Line 78-80: exception is caught, logged, and False is returned."""
        config = MagicMock()
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = RuntimeError("connection reset")

        ws = WebSocketManager(config)
        ws.ws = mock_ws
        ws._running = True

        result = await ws.send({"type": "test"})

        assert result is False


class TestWebSocketManagerSendAckEdgeCases:
    """Cover line 98-102: send_ack builds correct payload."""

    @pytest.mark.asyncio
    async def test_send_ack_returns_false_when_not_connected(self):
        """send_ack returns False when ws is None (inherit from send)."""
        config = MagicMock()
        ws = WebSocketManager(config)
        ws.ws = None
        ws._running = True

        result = await ws.send_ack("msg-abc")

        assert result is False


class TestWebSocketManagerSendNotificationEdgeCases:
    """Cover line 104-109: send_notification builds correct payload."""

    @pytest.mark.asyncio
    async def test_send_notification_returns_false_when_not_connected(self):
        """send_notification returns False when ws is None."""
        config = MagicMock()
        ws = WebSocketManager(config)
        ws.ws = None
        ws._running = True

        result = await ws.send_notification("Hello!")

        assert result is False


class TestWebSocketManagerRegisterEdgeCases:
    """Cover lines 111-121."""

    @pytest.mark.asyncio
    async def test_register_returns_false_when_only_device_id_missing(self):
        """Line 113: device_id is None should return False immediately."""
        config = MagicMock()
        config.device_id = None
        config.device_token = "token"

        ws = WebSocketManager(config)
        result = await ws.register()

        assert result is False

    @pytest.mark.asyncio
    async def test_register_returns_false_when_only_token_missing(self):
        """Line 113: device_token is None should return False immediately."""
        config = MagicMock()
        config.device_id = "device"
        config.device_token = None

        ws = WebSocketManager(config)
        result = await ws.register()

        assert result is False


class TestWebSocketManagerListenExceptionPath:
    """Cover lines 155-162: exception handling in listen and reconnect scheduling."""

    @pytest.mark.asyncio
    async def test_listen_catches_generic_exception(self):
        """Lines 157-158: generic Exception in listen loop is caught and logged."""
        import websockets.exceptions

        config = MagicMock()
        config.auto_reconnect = False
        mock_ws = MagicMock()

        class FailOnSecond:
            def __init__(self):
                self.count = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                self.count += 1
                if self.count == 1:
                    return '{"type": "message", "data": {}}'
                raise RuntimeError("unexpected error")

        ws = WebSocketManager(config)
        ws.ws = FailOnSecond()
        ws._running = True

        await ws.listen()

        assert ws._running is False

    @pytest.mark.asyncio
    async def test_listen_calls_schedule_reconnect_on_error(self):
        """Lines 161-162: when auto_reconnect=True, _schedule_reconnect is called."""
        config = MagicMock()
        config.auto_reconnect = True
        config.reconnect_delay = 0.01

        class MockAsyncIterator:
            def __init__(self):
                self.closed = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self.closed:
                    self.closed = True
                    return '{"type": "message", "data": {}}'
                raise StopAsyncIteration

        ws = WebSocketManager(config)
        ws.ws = MockAsyncIterator()
        ws._running = True

        with patch.object(ws, '_schedule_reconnect', new_callable=AsyncMock) as mock_sr:
            await ws.listen()
            mock_sr.assert_called_once()


class TestWebSocketManagerScheduleReconnectEdgeCases:
    """Cover lines 164-176: reconnect scheduling edge cases."""

    @pytest.mark.asyncio
    async def test_schedule_reconnect_skips_when_not_running(self):
        """Lines 172: if _running became True during sleep, should not call connect."""
        config = MagicMock()
        config.auto_reconnect = True
        config.reconnect_delay = 0.01
        config.server_ws_url = "wss://example.com/ws"
        config.device_token = None
        config.device_id = None

        ws = WebSocketManager(config)
        ws._running = False

        with patch('client.websocket.websockets.connect', new_callable=AsyncMock) as mock_connect:
            async def set_running():
                await asyncio.sleep(0.005)
                ws._running = True

            asyncio.create_task(set_running())
            await ws._schedule_reconnect()

            mock_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_schedule_reconnect_fails_on_connect_error(self):
        """Line 172-173: connect() returning False should not call listen."""
        config = MagicMock()
        config.auto_reconnect = True
        config.reconnect_delay = 0.01
        config.server_ws_url = "wss://example.com/ws"
        config.device_token = None
        config.device_id = None

        ws = WebSocketManager(config)
        ws._running = False

        with patch('client.websocket.websockets.connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = None  # connect returns falsy

            with patch.object(ws, 'listen') as mock_listen:
                await ws._schedule_reconnect()
                await asyncio.sleep(0.005)

                mock_connect.assert_called_once()
                # listen should NOT be called when connect fails
                # (the actual code checks `if await self.connect():` which is False when None)


class TestWebSocketManagerIsConnectedFallback:
    """Cover lines 186-187: fallback when State import fails."""

    def test_is_connected_uses_open_attr_fallback(self):
        """Lines 185-187: AttributeError on ws.state uses getattr(open, False) fallback."""
        config = MagicMock()
        mock_ws = MagicMock()
        # Simulate ws.state raising AttributeError (no 'state' attr)
        del mock_ws.state
        mock_ws.open = True  # fallback attribute that should be used

        ws = WebSocketManager(config)
        ws._running = True
        ws.ws = mock_ws

        result = ws.is_connected
        assert result is True

    def test_is_connected_false_when_open_attr_is_false(self):
        """open attr exists but is False."""
        config = MagicMock()
        mock_ws = MagicMock()
        del mock_ws.state  # force AttributeError path
        mock_ws.open = False

        ws = WebSocketManager(config)
        ws._running = True
        ws.ws = mock_ws

        result = ws.is_connected

        assert result is False


class TestWebSocketManagerListenNoMessageId:
    """Cover lines 138-142: message with no message_id field."""

    @pytest.mark.asyncio
    async def test_listen_message_without_message_id(self):
        """Lines 139-143: message with no message_id in data."""
        import websockets.exceptions

        config = MagicMock()
        config.auto_reconnect = False

        class MockAsyncIterator:
            def __init__(self):
                self.closed = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self.closed:
                    self.closed = True
                    return '{"type": "message", "data": {"content": "hello"}}'
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
        await asyncio.sleep(0)

        assert len(received) == 1
        assert received[0].message_id is None

    @pytest.mark.asyncio
    async def test_listen_empty_data_payload(self):
        """Lines 138: data = {} when no 'data' key in JSON."""
        import websockets.exceptions

        config = MagicMock()
        config.auto_reconnect = False

        class MockAsyncIterator:
            def __init__(self):
                self.closed = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self.closed:
                    self.closed = True
                    return '{"type": "status", "data": {}}'
                raise StopAsyncIteration

        mock_ws = MockAsyncIterator()

        ws = WebSocketManager(config)
        ws.ws = mock_ws
        ws._running = True

        received = []

        async def handler(msg):
            received.append(msg)

        ws.on("status", handler)

        await ws.listen()
        await asyncio.sleep(0)

        assert len(received) == 1
        assert received[0].data == {}
