"""Host/network diagnostics helpers — for legible connection errors and the
``diagnostics`` tool.

Standard library only, plus a best-effort call to the platform's interface
command (``ifconfig`` / ``ip`` / ``ipconfig``). None of this connects to N3FJP;
it only describes the host the server is running on, so you can tell from inside
Desktop Chat whether this process can even see the target's network.
"""

from __future__ import annotations

import errno as _errno
import re
import shutil
import socket
import subprocess
import sys

_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def errno_name(exc: BaseException) -> str:
    """Return the symbolic errno (ETIMEDOUT, EHOSTUNREACH, ENETUNREACH,
    ECONNREFUSED, …) for an OSError, or a sensible name otherwise."""
    if isinstance(exc, socket.gaierror):
        return "ENOTFOUND"  # DNS resolution failure (Node's ENOTFOUND)
    code = getattr(exc, "errno", None)
    if code is None:
        return type(exc).__name__
    return _errno.errorcode.get(code, str(code))


def primary_outbound_ip() -> str | None:
    """The source IP the OS would use to reach the outside world.

    Uses a UDP ``connect`` to TEST-NET-1 (192.0.2.1) — this sets the route and
    reveals the source address **without sending any packets**, and never touches
    the real N3FJP host.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def _interface_command() -> list[str] | None:
    if sys.platform.startswith("win"):
        return ["ipconfig", "/all"]
    if sys.platform == "darwin":
        return ["ifconfig"]
    if shutil.which("ip"):
        return ["ip", "-o", "addr"]
    if shutil.which("ifconfig"):
        return ["ifconfig", "-a"]
    return None


def network_interfaces() -> dict:
    """A description of this host's network: hostname, primary IP, and the raw
    output of the platform interface command (so LAN visibility is obvious)."""
    cmd = _interface_command()
    raw = ""
    if cmd:
        try:
            raw = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5
            ).stdout
        except (OSError, subprocess.SubprocessError):
            raw = ""
    return {
        "hostname": socket.gethostname(),
        "fqdn": socket.getfqdn(),
        "primary_outbound_ip": primary_outbound_ip(),
        "interface_command": " ".join(cmd) if cmd else None,
        "ipv4_addresses": sorted(set(_IPV4_RE.findall(raw))),
        "interfaces_raw": raw[:4000],
    }


def connection_error(host: str, port: int, exc: BaseException) -> str:
    """A structured, legible one-line(ish) connection-failure message."""
    net = network_interfaces()
    return (
        f"Could not reach N3FJP. target={host}:{port} errno={errno_name(exc)} "
        f"detail={exc} | host={net['hostname']} primary_ip={net['primary_outbound_ip']} "
        f"ipv4_seen={net['ipv4_addresses']}"
    )
