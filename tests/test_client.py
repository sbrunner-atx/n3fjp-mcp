"""Unit tests for client helpers; socket calls are faked."""

from __future__ import annotations

import errno

import pytest

import n3fjp_mcp.client as client_mod
from n3fjp_mcp.client import N3fjp, N3fjpError, _is_loopback


def test_is_loopback():
    assert _is_loopback("127.0.0.1")
    assert _is_loopback("localhost")
    assert _is_loopback("::1")
    assert _is_loopback(" 127.0.0.1 ")
    assert not _is_loopback("192.168.1.50")
    assert not _is_loopback("10.0.0.5")


def _refuse(*_args, **_kwargs):
    raise OSError(errno.EHOSTUNREACH, "No route to host")


def test_lan_error_says_ask_again_before_the_bridge(monkeypatch):
    monkeypatch.setattr(client_mod.socket, "create_connection", _refuse)
    n3 = N3fjp("192.168.1.50", 1100)
    with pytest.raises(N3fjpError) as info:
        n3._ensure_connected()
    msg = str(info.value)
    assert "target=192.168.1.50:1100" in msg
    assert "ask again" in msg
    assert "Local Network" in msg
    assert "mcp-host-bridge install n3fjp --to 192.168.1.50" in msg  # fallback
    assert msg.index("Local Network") < msg.index("mcp-host-bridge")


def test_loopback_error_has_no_lan_hint(monkeypatch):
    monkeypatch.setattr(client_mod.socket, "create_connection", _refuse)
    n3 = N3fjp("127.0.0.1", 1100)
    with pytest.raises(N3fjpError) as info:
        n3._ensure_connected()
    assert "mcp-host-bridge" not in str(info.value)
    assert "Local Network" not in str(info.value)
