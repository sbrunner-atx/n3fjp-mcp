"""Unit tests for the forwarder arg parsing and the loopback hint (no sockets)."""

from __future__ import annotations

from contest_mcp.client import _is_loopback
from contest_mcp.forward import _split_hostport


def test_split_hostport_with_and_without_port():
    assert _split_hostport("192.168.1.50", 1100) == ("192.168.1.50", 1100)
    assert _split_hostport("192.168.1.50:1234", 1100) == ("192.168.1.50", 1234)
    assert _split_hostport("127.0.0.1:1100", 1100) == ("127.0.0.1", 1100)


def test_is_loopback():
    assert _is_loopback("127.0.0.1")
    assert _is_loopback("localhost")
    assert _is_loopback("::1")
    assert _is_loopback(" 127.0.0.1 ")
    assert not _is_loopback("192.168.1.50")
    assert not _is_loopback("10.0.0.5")
