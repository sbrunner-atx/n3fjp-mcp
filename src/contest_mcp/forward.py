"""A tiny loopback-to-remote TCP forwarder, shipped with the package.

Why this exists: Claude Desktop may run the MCP connector **sandboxed so it can
only reach 127.0.0.1 (loopback), not LAN addresses** — even with macOS Local
Network permission granted. If N3FJP runs on a *different* computer than Claude
Desktop, the connector cannot dial the LAN directly. Running this forwarder on
the same machine as Claude Desktop bridges loopback to the remote N3FJP: you set
the connector's *N3FJP host* to ``127.0.0.1`` and this relays to the real host.

It is standard-library only and exposed as the ``contest-mcp-forward`` console
script. See ``docs/REMOTE-HOST.md`` for install / modify / remove instructions.

Examples::

    contest-mcp-forward --to 192.168.1.50
    contest-mcp-forward --to 192.168.1.50:1100 --listen 127.0.0.1:1100
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading


def _split_hostport(value: str, default_port: int) -> tuple[str, int]:
    """Parse ``host`` or ``host:port`` into ``(host, port)``."""
    if ":" in value:
        host, _, port = value.rpartition(":")
        return host, int(port)
    return value, default_port


def _pipe(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.close()
            except OSError:
                pass


def _handle(client: socket.socket, target: tuple[str, int], timeout: float) -> None:
    try:
        upstream = socket.create_connection(target, timeout=timeout)
    except OSError as exc:
        print(f"upstream connect to {target[0]}:{target[1]} failed: {exc}", flush=True)
        client.close()
        return
    threading.Thread(target=_pipe, args=(client, upstream), daemon=True).start()
    threading.Thread(target=_pipe, args=(upstream, client), daemon=True).start()


def serve(
    listen_host: str,
    listen_port: int,
    target_host: str,
    target_port: int,
    timeout: float = 6.0,
) -> None:
    """Listen on ``listen_host:listen_port`` and relay to ``target_host:target_port``."""
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((listen_host, listen_port))
    srv.listen(50)
    print(
        f"contest-mcp-forward: {listen_host}:{listen_port} -> {target_host}:{target_port}",
        flush=True,
    )
    while True:
        client, _ = srv.accept()
        threading.Thread(
            target=_handle, args=(client, (target_host, target_port), timeout), daemon=True
        ).start()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="contest-mcp-forward",
        description=(
            "Forward 127.0.0.1:<port> to a remote N3FJP so a sandboxed MCP connector "
            "(which can only reach loopback) can talk to N3FJP on another computer. "
            "Point the connector's N3FJP host at 127.0.0.1."
        ),
    )
    parser.add_argument(
        "--to",
        required=True,
        metavar="HOST[:PORT]",
        help="Remote N3FJP host (or host:port). Port defaults to 1100.",
    )
    parser.add_argument(
        "--listen",
        default="127.0.0.1:1100",
        metavar="HOST:PORT",
        help="Local address to listen on (default 127.0.0.1:1100).",
    )
    parser.add_argument(
        "--timeout", type=float, default=6.0, help="Upstream connect timeout (seconds)."
    )
    args = parser.parse_args(argv)

    target_host, target_port = _split_hostport(args.to, 1100)
    listen_host, listen_port = _split_hostport(args.listen, 1100)
    try:
        serve(listen_host, listen_port, target_host, target_port, args.timeout)
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        print(f"contest-mcp-forward failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
