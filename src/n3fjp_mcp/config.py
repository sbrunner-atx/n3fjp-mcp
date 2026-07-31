"""Runtime configuration for the contest (N3FJP) MCP server.

Settings come from environment variables. In development you set them in the
Claude Desktop server entry's ``env`` block; in the packaged ``.mcpb`` desktop
extension they are surfaced as a settings form and passed through as the same
environment variables, so the code does not care which one set them.

Safety model
------------
Logging does not key a transmitter, so there is no transmit gate (unlike
``fldigi-mcp``). The protection here is about the **log database** instead:

* Read operations are harmless and default to *Always Allow* at the client.
* Write operations (logging a QSO, changing band/mode, adding direct) default to
  *Needs Approval*.
* Deleting individual records and other destructive calls additionally require an
  explicit ``confirm=true`` argument.
* Operations that could delete or overwrite the **entire** log database (raw SQL
  ``DELETE`` / ``DROP`` / unscoped ``UPDATE``) are refused outright **unless** the
  operator deliberately turns on :data:`Config.allow_db_wipe`. That switch is off
  by default and carries a stern warning in the settings form. It is intentionally
  separate from — and stricter than — the client's permission prompts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_TRUE = {"1", "true", "yes", "on"}

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 1100


def _as_bool(value: str | None) -> bool:
    return value is not None and str(value).strip().lower() in _TRUE


@dataclass
class Config:
    """Resolved server configuration."""

    host: str
    port: int
    timeout: float
    allow_db_wipe: bool

    @classmethod
    def from_env(cls) -> Config:
        try:
            timeout = float(os.environ.get("N3FJP_TIMEOUT", "6"))
        except ValueError:
            timeout = 6.0
        return cls(
            host=os.environ.get("N3FJP_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST,
            port=int(os.environ.get("N3FJP_PORT", str(DEFAULT_PORT))),
            timeout=timeout,
            allow_db_wipe=_as_bool(os.environ.get("N3FJP_ALLOW_DB_WIPE")),
        )
