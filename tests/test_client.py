"""Unit tests for client helpers that don't need a socket."""

from __future__ import annotations

from contest_mcp.client import _is_loopback


def test_is_loopback():
    assert _is_loopback("127.0.0.1")
    assert _is_loopback("localhost")
    assert _is_loopback("::1")
    assert _is_loopback(" 127.0.0.1 ")
    assert not _is_loopback("192.168.1.50")
    assert not _is_loopback("10.0.0.5")
