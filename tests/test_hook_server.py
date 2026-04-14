"""Tests for hook_server.py - HTTP hook receiver."""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from client.hook_server import HookServer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class AsyncWriterMock(MagicMock):
    """MagicMock that supports await on drain()/wait_closed()."""
    async def drain(self): pass
    async def wait_closed(self): pass


async def send_raw_post(server, path: str, body: dict, task_id: str = None):
    """Send a raw HTTP POST to the server's _handle_request."""
    path_with_qs = path
    if task_id:
        path_with_qs = f"{path}?task_id={task_id}"
    body_bytes = json.dumps(body).encode()

    reader = asyncio.StreamReader()
    writer = MagicMock()

    # Write the request line
    reader.feed_data(f"POST {path_with_qs} HTTP/1.1\r\n".encode())
    reader.feed_data(f"Content-Length: {len(body_bytes)}\r\n".encode())
    reader.feed_data(b"\r\n")
    reader.feed_data(body_bytes)
    reader.feed_eof()

    await server._handle_request(reader, writer)


async def drain_writer(writer):
    """Await drain and close."""
    await writer.drain()
    writer.close()
    await writer.wait_closed()


# ---------------------------------------------------------------------------
# HookServer init
# ---------------------------------------------------------------------------

class TestHookServerInit:
    def test_default_port(self):
        srv = HookServer()
        assert srv.port == 3456
        assert srv.host == "127.0.0.1"
        assert srv._running is False

    def test_custom_port(self):
        srv = HookServer(port=9999)
        assert srv.port == 9999

    def test_initial_callbacks_none(self):
        srv = HookServer()
        assert srv._on_stop is None
        assert srv._on_post_tool_use is None
        assert srv._on_pre_tool_use is None
        assert srv._on_notification is None


# ---------------------------------------------------------------------------
# Callback registration
# ---------------------------------------------------------------------------

class TestCallbackRegistration:
    def test_register_stop_handler(self):
        srv = HookServer()
        cb = AsyncMock()
        srv.register_stop_handler(cb)
        assert srv._on_stop is cb

    def test_register_post_tool_use_handler(self):
        srv = HookServer()
        cb = AsyncMock()
        srv.register_post_tool_use_handler(cb)
        assert srv._on_post_tool_use is cb

    def test_register_pre_tool_use_handler(self):
        srv = HookServer()
        cb = AsyncMock()
        srv.register_pre_tool_use_handler(cb)
        assert srv._on_pre_tool_use is cb

    def test_register_notification_handler(self):
        srv = HookServer()
        cb = AsyncMock()
        srv.register_notification_handler(cb)
        assert srv._on_notification is cb


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

class TestLifecycle:
    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """stop() returns early when _running is False (line 73)."""
        srv = HookServer()
        assert srv._running is False
        # Should not raise, just return early
        await srv.stop()
        assert srv._running is False

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        srv = HookServer(port=0)  # port 0 = ephemeral
        await srv.start()
        try:
            assert srv.is_running is True
        finally:
            await srv.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running(self):
        srv = HookServer(port=0)
        await srv.start()
        assert srv.is_running is True
        await srv.stop()
        assert srv.is_running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        srv = HookServer(port=0)
        await srv.start()
        try:
            # second start should warn, not crash
            await srv.start()
            assert srv.is_running is True
        finally:
            await srv.stop()


# ---------------------------------------------------------------------------
# _dispatch routing
# ---------------------------------------------------------------------------

class TestDispatchRouting:
    @pytest.mark.asyncio
    async def test_stop_path_calls_callback(self):
        srv = HookServer()
        cb = AsyncMock()
        srv.register_stop_handler(cb)

        writer = AsyncWriterMock()
        await srv._dispatch(writer, "POST", "/hooks/stop", "task-42", b'{"hook_event_name":"Stop"}')

        cb.assert_called_once_with("task-42", {"hook_event_name": "Stop"})
        writer.write.assert_called_once()
        # Check response code in the first call
        call_str = writer.write.call_args[0][0].decode()
        assert "HTTP/1.1 200" in call_str

    @pytest.mark.asyncio
    async def test_stop_hook_event_name_calls_callback(self):
        srv = HookServer()
        cb = AsyncMock()
        srv.register_stop_handler(cb)

        writer = AsyncWriterMock()
        await srv._dispatch(writer, "POST", "/some/other", "task-99", b'{"hook_event_name":"Stop"}')

        cb.assert_called_once_with("task-99", {"hook_event_name": "Stop"})

    @pytest.mark.asyncio
    async def test_post_tool_use_path_calls_callback(self):
        srv = HookServer()
        cb = AsyncMock()
        srv.register_post_tool_use_handler(cb)

        writer = AsyncWriterMock()
        await srv._dispatch(writer, "POST", "/hooks/post-tool-use", "t1", b'{"hook_event_name":"PostToolUse"}')

        cb.assert_called_once_with("t1", {"hook_event_name": "PostToolUse"})

    @pytest.mark.asyncio
    async def test_pre_tool_use_path_calls_callback(self):
        srv = HookServer()
        cb = AsyncMock()
        srv.register_pre_tool_use_handler(cb)

        writer = AsyncWriterMock()
        await srv._dispatch(writer, "POST", "/hooks/pre-tool-use", "t2", b'{"hook_event_name":"PreToolUse"}')

        cb.assert_called_once_with("t2", {"hook_event_name": "PreToolUse"})

    @pytest.mark.asyncio
    async def test_notification_path_calls_callback(self):
        srv = HookServer()
        cb = AsyncMock()
        srv.register_notification_handler(cb)

        writer = AsyncWriterMock()
        await srv._dispatch(writer, "POST", "/hooks/notification", "t3", b'{"hook_event_name":"Notification"}')

        cb.assert_called_once_with("t3", {"hook_event_name": "Notification"})

    @pytest.mark.asyncio
    async def test_unknown_path_returns_404(self):
        srv = HookServer()

        writer = AsyncWriterMock()
        await srv._dispatch(writer, "POST", "/hooks/nonexistent", None, b'{}')

        call_str = writer.write.call_args[0][0].decode()
        assert "HTTP/1.1 404" in call_str

    @pytest.mark.asyncio
    async def test_stop_with_no_callback_succeeds(self):
        srv = HookServer()
        # No callback registered

        writer = AsyncWriterMock()
        await srv._dispatch(writer, "POST", "/hooks/stop", "t1", b'{"hook_event_name":"Stop"}')

        # Should still return 200
        call_str = writer.write.call_args[0][0].decode()
        assert "HTTP/1.1 200" in call_str


# ---------------------------------------------------------------------------
# Body parsing
# ---------------------------------------------------------------------------

class TestBodyParsing:
    @pytest.mark.asyncio
    async def test_non_json_body_returns_400(self):
        srv = HookServer()
        writer = AsyncWriterMock()

        await srv._dispatch(writer, "POST", "/hooks/stop", None, b"not json at all")

        call_str = writer.write.call_args[0][0].decode()
        assert "HTTP/1.1 400" in call_str

    @pytest.mark.asyncio
    async def test_empty_body_succeeds(self):
        srv = HookServer()
        cb = AsyncMock()
        srv.register_stop_handler(cb)

        writer = AsyncWriterMock()
        await srv._dispatch(writer, "POST", "/hooks/stop", "t1", b"")

        cb.assert_called_once_with("t1", {})

    @pytest.mark.asyncio
    async def test_complex_payload(self):
        srv = HookServer()
        cb = AsyncMock()
        srv.register_notification_handler(cb)

        payload = {
            "hook_event_name": "Notification",
            "notification": {
                "level": "info",
                "message": "Task completed",
            },
            "metadata": {"task_id": "abc"},
        }
        writer = AsyncWriterMock()
        await srv._dispatch(writer, "POST", "/hooks/notification", "t1", json.dumps(payload).encode())

        cb.assert_called_once()
        _, received_payload = cb.call_args[0]
        assert received_payload["notification"]["message"] == "Task completed"


# ---------------------------------------------------------------------------
# Query param task_id extraction
# ---------------------------------------------------------------------------

class TestTaskIdExtraction:
    @pytest.mark.asyncio
    async def test_task_id_from_query_param(self):
        srv = HookServer()
        cb = AsyncMock()
        srv.register_stop_handler(cb)

        writer = AsyncWriterMock()
        # _dispatch receives raw path from _handle_request after raw_path.partition("?")
        # so path is the part before "?" and task_id is from params dict
        await srv._dispatch(writer, "POST", "/hooks/stop", "my-task-id", b'{}')

        cb.assert_called_once_with("my-task-id", {})

    @pytest.mark.asyncio
    async def test_task_id_none_when_missing(self):
        srv = HookServer()
        cb = AsyncMock()
        srv.register_stop_handler(cb)

        writer = AsyncWriterMock()
        await srv._dispatch(writer, "POST", "/hooks/stop", None, b'{}')

        cb.assert_called_once_with(None, {})

    @pytest.mark.asyncio
    async def test_task_id_complex_url(self):
        srv = HookServer()
        cb = AsyncMock()
        srv.register_stop_handler(cb)

        writer = AsyncWriterMock()
        # urllib.parse decodes %3D → '=', %26 → '&'
        await srv._dispatch(writer, "POST", "/hooks/stop", "t=1&x=2", b'{}')

        cb.assert_called_once()
        task_id_arg = cb.call_args[0][0]
        assert task_id_arg == "t=1&x=2"


# ---------------------------------------------------------------------------
# Response format
# ---------------------------------------------------------------------------

class TestResponseFormat:
    @pytest.mark.asyncio
    async def test_stop_returns_json_continue_true(self):
        srv = HookServer()
        cb = AsyncMock()
        srv.register_stop_handler(cb)

        writer = AsyncWriterMock()
        await srv._dispatch(writer, "POST", "/hooks/stop", "t1", b'{"hook_event_name":"Stop"}')

        response = writer.write.call_args[0][0].decode()
        assert "Content-Type: application/json" in response
        assert '"continue": true' in response

    @pytest.mark.asyncio
    async def test_health_returns_ok(self):
        srv = HookServer()
        writer = AsyncWriterMock()

        await srv._dispatch(writer, "POST", "/health", None, b"")

        response = writer.write.call_args[0][0].decode()
        assert "HTTP/1.1 200" in response
        assert '"status": "ok"' in response


# ---------------------------------------------------------------------------
# _handle_request integration (non-HTTP method, malformed requests)
# ---------------------------------------------------------------------------

class TestHandleRequestEdgeCases:
    @pytest.mark.asyncio
    async def test_handle_request_parses_headers_and_body(self):
        """Full _handle_request flow: reads headers, body, parses URL, dispatches."""
        srv = HookServer(port=0)
        cb = AsyncMock()
        srv.register_stop_handler(cb)

        await srv.start()
        try:
            reader = asyncio.StreamReader()
            writer = AsyncWriterMock()

            # POST with headers + body
            body = b'{"hook_event_name":"Stop","extra":"data"}'
            reader.feed_data(f"POST /hooks/stop?task_id=t99 HTTP/1.1\r\n".encode())
            reader.feed_data(f"Content-Length: {len(body)}\r\n".encode())
            reader.feed_data(b"\r\n")
            reader.feed_data(body)
            reader.feed_eof()

            await srv._handle_request(reader, writer)

            # Handler was called with parsed task_id and body
            cb.assert_called_once()
            args = cb.call_args[0]
            assert args[0] == "t99"
            assert args[1]["hook_event_name"] == "Stop"
            assert args[1]["extra"] == "data"

            # 200 response sent
            response = writer.write.call_args[0][0].decode()
            assert "HTTP/1.1 200" in response
            assert "Content-Type: application/json" in response
        finally:
            await srv.stop()

    @pytest.mark.asyncio
    async def test_handle_request_truly_empty_request_line(self):
        """Truly empty request line → 400 (lines 97-99).

        Note: b'\\r\\n' is truthy so it hits split() and gets caught as a ValueError.
        b'' is falsy so it hits the empty check.
        """
        srv = HookServer(port=0)
        await srv.start()
        try:
            reader = asyncio.StreamReader()
            writer = AsyncWriterMock()
            # b'' is falsy → hits `if not request_line:` at line 97 → 400 response
            reader.feed_data(b"")
            reader.feed_eof()

            await srv._handle_request(reader, writer)

            response = writer.write.call_args[0][0].decode()
            assert "HTTP/1.1 400" in response
        finally:
            await srv.stop()

    @pytest.mark.asyncio
    async def test_dispatch_returns_200_empty_response(self):
        """Line 195: _write_response called with empty string body (edge case)."""
        srv = HookServer()
        writer = AsyncWriterMock()
        await srv._write_response(writer, 200, "", content_type="text/plain")
        response = writer.write.call_args[0][0].decode()
        assert "HTTP/1.1 200" in response
        assert "Content-Length: 0" in response

    @pytest.mark.asyncio
    async def test_exception_handler_inner_except(self):
        """Lines 130-135: exception inside try block caught, then _write_response raises (inner except)."""
        srv = HookServer(port=0)
        await srv.start()
        try:
            reader = asyncio.StreamReader()
            writer = AsyncWriterMock()

            # Patch reader.readline to raise inside the try block → outer except fires
            original_readline = reader.readline
            call_count = [0]

            async def flaky_readline():
                call_count[0] += 1
                if call_count[0] == 1:
                    raise RuntimeError("readline fail")
                return await original_readline()

            reader.readline = flaky_readline

            # Patch _write_response so the error handler's call also raises → inner except
            original_write_response = srv._write_response

            async def flaky_write_response(w, code, body, content_type="text/plain"):
                raise RuntimeError("write fail")

            srv._write_response = flaky_write_response
            reader.feed_data(b"POST /hooks/stop HTTP/1.1\r\n\r\n")
            reader.feed_eof()

            # Should not raise — inner except silently swallows both errors
            await srv._handle_request(reader, writer)
            # No assertion needed — the fact it didn't raise is the test
        finally:
            await srv.stop()
            srv._write_response = original_write_response

    @pytest.mark.asyncio
    async def test_non_post_returns_405(self):
        srv = HookServer(port=0)
        await srv.start()
        try:
            reader = asyncio.StreamReader()
            writer = AsyncWriterMock()

            reader.feed_data(b"GET /hooks/stop HTTP/1.1\r\n\r\n")
            reader.feed_eof()

            await srv._handle_request(reader, writer)

            # _write_response was called with status 405
            assert writer.write.called
            response = writer.write.call_args[0][0].decode()
            assert "HTTP/1.1 405" in response
        finally:
            await srv.stop()