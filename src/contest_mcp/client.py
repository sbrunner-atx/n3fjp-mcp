"""A small, dependency-free TCP client for N3FJP's logging API.

N3FJP (the server) listens on TCP, default port 1100. This client keeps a single
persistent connection with a background reader thread that splits the incoming
byte stream into ``<CMD>…</CMD>`` blocks (see :mod:`contest_mcp.protocol`).

Because the same stream carries both responses and opt-in push notifications, the
reader routes each parsed block to whichever command is currently waiting for it,
or — when no command is in flight — into a bounded notifications buffer that the
``notifications`` tool can drain.

The rest of the project talks to N3FJP only through :class:`N3fjp`, never to raw
sockets, which keeps the server module clean and the protocol logic unit-testable.
"""

from __future__ import annotations

import socket
import threading
import time
from collections import deque
from collections.abc import Callable

from contest_mcp import diag
from contest_mcp.protocol import (
    CRLF,
    Block,
    extract_blocks,
    matches,
    parse_block,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 1100

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _is_loopback(host: str) -> bool:
    return host.strip().lower() in _LOOPBACK


class N3fjpError(RuntimeError):
    """Raised when N3FJP cannot be reached or the connection drops."""


class N3fjp:
    """A persistent connection to a running N3FJP instance.

    Construction is cheap and opens no socket; the first command connects. Host
    and port default to N3FJP's defaults but are normally supplied from
    :class:`contest_mcp.config.Config`.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        timeout: float = 6.0,
        notification_buffer: int = 500,
    ) -> None:
        self.host = host or DEFAULT_HOST
        self.port = int(port or DEFAULT_PORT)
        self.timeout = float(timeout)
        self.url = f"{self.host}:{self.port}"

        self._sock: socket.socket | None = None
        self._reader: threading.Thread | None = None
        self._buf = ""
        self._closed = False
        self._send_lock = threading.Lock()  # one command in flight at a time
        self._sink: Callable[[Block], None] | None = None
        self._notifications: deque[Block] = deque(maxlen=notification_buffer)

    # -- connection management ------------------------------------------------

    def _ensure_connected(self) -> None:
        if self._sock is not None:
            return
        try:
            self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except (ConnectionRefusedError, OSError) as exc:
            self._sock = None
            msg = diag.connection_error(self.host, self.port, exc)
            if not _is_loopback(self.host):
                msg += (
                    " | If this host cannot reach the target (e.g. a sandboxed MCP "
                    "client that only reaches loopback), run the standalone "
                    f"mcp-host-bridge on this machine — `mcp-host-bridge install n3fjp "
                    f"--to {self.host}` — and set N3FJP host to 127.0.0.1. See "
                    "docs/REMOTE-HOST.md. Run the `diagnostics` tool for host/network detail."
                )
            raise N3fjpError(msg) from exc
        self._buf = ""
        self._closed = False
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()

    def _reader_loop(self) -> None:
        sock = self._sock
        if sock is None:
            return
        while not self._closed:
            try:
                data = sock.recv(4096)
            except OSError:
                break
            if not data:
                break  # peer closed
            self._feed(data.decode("utf-8", "replace"))
        self._drop_socket()

    def _feed(self, text: str) -> None:
        self._buf += text
        inners, self._buf = extract_blocks(self._buf)
        for inner in inners:
            block = parse_block(inner)
            sink = self._sink
            if sink is not None:
                sink(block)
            else:
                self._notifications.append(block)

    def _drop_socket(self) -> None:
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    # -- core request/response ------------------------------------------------

    def command(
        self,
        raw: str,
        expect: str | None = None,
        settle: float = 0.4,
        timeout: float | None = None,
    ) -> list[Block]:
        """Send a raw ``<CMD>…</CMD>`` string and collect the reply block(s).

        ``expect`` is the request ID whose ``…RESPONSE`` we wait for (e.g.
        ``"PROGRAM"`` or ``"ENTER"``). With ``expect=None`` (fire-and-forget or
        unknown response tag) we simply collect whatever arrives within
        ``settle`` seconds. Returns the parsed blocks received during the window.
        """
        timeout = self.timeout if timeout is None else timeout
        with self._send_lock:
            self._ensure_connected()
            collected: list[Block] = []
            done = threading.Event()

            def sink(block: Block) -> None:
                collected.append(block)
                if expect is not None and matches(block.id, expect):
                    done.set()

            self._sink = sink
            try:
                self._write(raw)
                if expect is None:
                    time.sleep(settle)
                else:
                    done.wait(timeout)
                    time.sleep(0.05)  # grace for trailing blocks in the same packet
            finally:
                self._sink = None
            return collected

    def _write(self, raw: str) -> None:
        if self._sock is None:
            raise N3fjpError(f"Not connected to N3FJP at {self.url}.")
        payload = (raw if raw.endswith(CRLF) else raw + CRLF).encode("utf-8")
        try:
            self._sock.sendall(payload)
        except OSError as exc:
            self._drop_socket()
            raise N3fjpError(f"Connection to N3FJP at {self.url} was lost: {exc}") from exc

    # -- notifications --------------------------------------------------------

    def drain_notifications(self) -> list[Block]:
        """Return and clear all buffered async notification blocks."""
        items = list(self._notifications)
        self._notifications.clear()
        return items

    def close(self) -> None:
        """Disconnect cleanly (a lone CRLF tells N3FJP to drop the link)."""
        self._closed = True
        if self._sock is not None:
            try:
                self._sock.sendall(CRLF.encode("utf-8"))
            except OSError:
                pass
        self._drop_socket()
