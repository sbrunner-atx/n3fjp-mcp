#!/usr/bin/env python3
"""
Phase 0 smoke test for contest-mcp.

Goal: prove this machine can talk to a running N3FJP instance over its TCP API,
using ONLY the Python standard library (socket) — exactly the way the real MCP
server does. No third-party packages.

N3FJP is the server. Enable its API first: Settings → Application Program
Interface → tick "TCP API Enabled".

Usage (defaults target the Windows test VM on the LAN):

    python3 smoke_test.py                      # 192.168.10.74:1000
    python3 smoke_test.py 127.0.0.1 1100       # a local instance
    N3FJP_HOST=192.168.10.74 N3FJP_PORT=1000 python3 smoke_test.py

You should see the program/version, the API version, and the current band/mode/
frequency.
"""

import os
import re
import socket
import sys

CRLF = "\r\n"
_BLOCK_RE = re.compile(r"<CMD>(.*?)</CMD>", re.DOTALL)


def send(sock: socket.socket, command: str, wait: float = 1.0) -> str:
    """Send one <CMD>…</CMD>, then read for ``wait`` seconds and return raw text."""
    sock.sendall((command + CRLF).encode())
    sock.settimeout(wait)
    chunks = []
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data.decode("utf-8", "replace"))
            if "</CMD>" in "".join(chunks):
                break
    except TimeoutError:
        pass
    return "".join(chunks)


def first_block(text: str) -> str:
    m = _BLOCK_RE.search(text)
    return m.group(0) if m else "(no <CMD> block received)"


def main() -> int:
    host = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("N3FJP_HOST", "192.168.10.74")
    port = int(sys.argv[2] if len(sys.argv) > 2 else os.environ.get("N3FJP_PORT", "1000"))

    print(f"Connecting to N3FJP at {host}:{port} ...")
    try:
        sock = socket.create_connection((host, port), timeout=6)
    except (ConnectionRefusedError, OSError) as exc:
        print(f"Could not connect: {type(exc).__name__} - {exc}")
        print("Is N3FJP running, with 'TCP API Enabled', and reachable on this host/port?")
        return 1

    try:
        for label, command in (
            ("Program/version", "<CMD><PROGRAM></CMD>"),
            ("API version", "<CMD><APIVERSION></CMD>"),
            ("Band/Mode/Freq", "<CMD><READBMF></CMD>"),
            ("Log file path", "<CMD><FILEPATH></CMD>"),
        ):
            reply = send(sock, command)
            print(f"  {label:16} -> {first_block(reply)}")
    finally:
        sock.sendall(CRLF.encode())  # polite disconnect
        sock.close()

    print()
    print("Success — this machine can talk to N3FJP. Ready for Phase 1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
