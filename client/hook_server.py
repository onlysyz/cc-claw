"""CC-Claw Hook Server - Receives Claude Code hook events via HTTP POST"""

import asyncio
import json
import logging
import urllib.parse
import time
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)

# Type alias for hook callbacks
HookCallback = Callable[[str, dict], Awaitable[None]]


class HookServer:
    """Lightweight async HTTP server that receives Claude Code hook callbacks.

    Claude Code sends HTTP POST to these endpoints when hooks fire.
    We parse the ?task_id=xxx query param to route to the right task.

    Includes a heartbeat monitor: if the daemon stops sending heartbeats
    for longer than heartbeat_timeout seconds, hooks are automatically removed
    from settings.json so Claude Code is not blocked by stale hooks.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 3456,
        heartbeat_timeout: float = 60.0,
    ):
        self.host = host
        self.port = port
        self.heartbeat_timeout = heartbeat_timeout
        self._server: Optional[asyncio.Server] = None
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

        # Callbacks registered by the daemon
        self._on_stop: Optional[HookCallback] = None
        self._on_post_tool_use: Optional[HookCallback] = None
        self._on_pre_tool_use: Optional[HookCallback] = None
        self._on_notification: Optional[HookCallback] = None
        self._on_heartbeat: Optional[Callable[[], None]] = None

        # Heartbeat tracking
        self._last_heartbeat: float = time.monotonic()
        self._daemon_alive: bool = True

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def register_stop_handler(self, cb: HookCallback):
        """Register callback for Stop hook events."""
        self._on_stop = cb

    def register_post_tool_use_handler(self, cb: HookCallback):
        """Register callback for PostToolUse hook events."""
        self._on_post_tool_use = cb

    def register_pre_tool_use_handler(self, cb: HookCallback):
        """Register callback for PreToolUse hook events."""
        self._on_pre_tool_use = cb

    def register_notification_handler(self, cb: HookCallback):
        """Register callback for Notification hook events."""
        self._on_notification = cb

    def register_heartbeat_handler(self, cb: Callable[[], None]):
        """Register callback for daemon heartbeat ticks."""
        self._on_heartbeat = cb

    async def start(self):
        """Start the HTTP server and heartbeat monitor."""
        if self._running:
            logger.warning("Hook server already running")
            return

        self._server = await asyncio.start_server(
            self._handle_request,
            self.host,
            self.port,
            reuse_address=True,
        )
        self._running = True
        addr = self._server.sockets[0].getsockname()
        logger.info(f"Hook server listening on {addr[0]}:{addr[1]}")

        # Start heartbeat monitor
        self._last_heartbeat = time.monotonic()
        self._daemon_alive = True
        self._monitor_task = asyncio.create_task(self._heartbeat_monitor())

    async def stop(self):
        """Stop the HTTP server and cancel the heartbeat monitor."""
        if not self._running:
            return
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        self._server.close()
        await self._server.wait_closed()
        self._running = False
        logger.info("Hook server stopped")

    async def _heartbeat_monitor(self):
        """Periodically check if the daemon is still sending heartbeats.

        If no heartbeat is received for longer than heartbeat_timeout seconds,
        the daemon is considered dead and hooks are removed from settings.json.
        """
        from .hook_config import remove_hooks
        while True:
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break

            elapsed = time.monotonic() - self._last_heartbeat
            if elapsed > self.heartbeat_timeout:
                if self._daemon_alive:
                    logger.warning(
                        f"No heartbeat from daemon for {elapsed:.0f}s (timeout={self.heartbeat_timeout}s). "
                        "Daemon appears dead — removing hooks from settings.json."
                    )
                    self._daemon_alive = False
                    try:
                        remove_hooks()
                    except Exception as e:
                        logger.error(f"Failed to remove hooks on heartbeat timeout: {e}")
                # Keep checking; daemon might reconnect on restart

    def _record_heartbeat(self):
        """Record that the daemon is alive."""
        self._last_heartbeat = time.monotonic()
        self._daemon_alive = True

    @property
    def is_running(self) -> bool:
        return self._running

    # -------------------------------------------------------------------------
    # Request handling
    # -------------------------------------------------------------------------

    async def _handle_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        """Handle incoming HTTP request from Claude Code."""
        addr = writer.get_extra_info("peername")
        try:
            # Read request line
            request_line = await reader.readline()
            if not request_line:
                await self._write_response(writer, 400, "Empty request")
                return

            method, raw_path, _ = request_line.decode().strip().split(" ")
            if method != "POST":
                await self._write_response(writer, 405, "Method Not Allowed")
                return

            # Read headers
            headers = {}
            content_length = 0
            while True:
                line = await reader.readline()
                if not line or line == b"\r\n":
                    break
                key, _, value = line.decode().strip().partition(": ")
                if key.lower() == "content-length":
                    content_length = int(value)

            # Read body
            body = b""
            if content_length > 0:
                body = await reader.readexactly(content_length)

            # Parse URL
            path, _, query_string = raw_path.partition("?")
            params = urllib.parse.parse_qs(query_string)
            task_id = params.get("task_id", [None])[0]

            # Route to handler
            await self._dispatch(writer, method, path, task_id, body)

        except Exception as e:
            logger.error(f"Hook server error handling request from {addr}: {e}", exc_info=True)
            try:
                await self._write_response(writer, 500, "Internal Server Error")
            except Exception:
                pass

    async def _dispatch(
        self,
        writer: asyncio.StreamWriter,
        method: str,
        path: str,
        task_id: Optional[str],
        body: bytes,
    ):
        """Dispatch request to the appropriate hook handler."""
        # Refresh heartbeat on any incoming request from the daemon
        self._record_heartbeat()

        logger.info(f"Hook received: {method} {path} task_id={task_id}")

        # Parse JSON body
        payload = {}
        if body:
            try:
                payload = json.loads(body.decode())
            except json.JSONDecodeError:
                logger.warning(f"Hook body not JSON: {body[:100]}")
                await self._write_response(writer, 400, "Invalid JSON body")
                return

        hook_event = payload.get("hook_event_name", "")
        response_data = None

        # Call registered handler and collect response data
        if path == "/hooks/stop" or hook_event == "Stop":
            if self._on_stop:
                await self._on_stop(task_id, payload)
            response_data = {"continue": True}

        elif path == "/hooks/post-tool-use" or hook_event == "PostToolUse":
            if self._on_post_tool_use:
                await self._on_post_tool_use(task_id, payload)
            response_data = {"continue": True}

        elif path == "/hooks/pre-tool-use" or hook_event == "PreToolUse":
            if self._on_pre_tool_use:
                await self._on_pre_tool_use(task_id, payload)
            response_data = {"continue": True}

        elif path == "/hooks/notification" or hook_event == "Notification":
            if self._on_notification:
                await self._on_notification(task_id, payload)
            response_data = {"continue": True}

        elif path == "/health":
            self._record_heartbeat()
            await self._write_response(writer, 200, json.dumps({"status": "ok"}), content_type="application/json")
            return

        elif path == "/hooks/heartbeat":
            self._record_heartbeat()
            if self._on_heartbeat:
                self._on_heartbeat()
            await self._write_response(writer, 200, json.dumps({"alive": True}), content_type="application/json")
            return

        else:
            logger.warning(f"Unknown hook path: {path}")
            await self._write_response(writer, 404, "Not Found")
            return

        # Default 200 response
        if response_data:
            await self._write_response(writer, 200, json.dumps(response_data), content_type="application/json")
        else:
            # Unreachable: all dispatch branches either return early or set response_data.
            await self._write_response(writer, 200, "", content_type="application/json")  # pragma: no cover

    async def _write_response(
        self,
        writer: asyncio.StreamWriter,
        status_code: int,
        body: str,
        content_type: str = "text/plain",
    ):
        """Write a simple HTTP response."""
        body_bytes = body.encode()
        response_lines = [
            f"HTTP/1.1 {status_code} {'OK' if status_code < 400 else 'ERROR'}",
            f"Content-Type: {content_type}",
            f"Content-Length: {len(body_bytes)}",
            "Connection: close",
            "",
            "",
        ]
        writer.write("\r\n".join(response_lines).encode() + body_bytes)
        await writer.drain()
        writer.close()
        await writer.wait_closed()
