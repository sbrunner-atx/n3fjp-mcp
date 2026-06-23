"""Pure N3FJP wire-protocol helpers: build commands, split and parse responses.

N3FJP's API is line-of-text over TCP. Every message is wrapped in a
``<CMD>…</CMD>`` envelope whose first token is the command/response ID, followed
by nested ``<TAG>value</TAG>`` parameters. One TCP packet may carry several
envelopes back to back.

Everything here is deliberately free of sockets and threads so it can be unit
tested without a running N3FJP instance. The socket plumbing lives in
:mod:`contest_mcp.client`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# One <CMD>…</CMD> envelope. Non-greedy so adjacent envelopes don't merge.
_BLOCK_RE = re.compile(r"<CMD>(.*?)</CMD>", re.DOTALL | re.IGNORECASE)
# A closed <TAG>value</TAG> pair. Tag names may start with a digit (e.g. 20MIN).
_FIELD_RE = re.compile(r"<([A-Za-z0-9_]+)>(.*?)</\1>", re.DOTALL)
# The leading response/command ID (an opening tag, usually NOT closed by N3FJP).
_ID_RE = re.compile(r"\s*<([A-Za-z0-9_]+)>")

CRLF = "\r\n"


@dataclass
class Block:
    """A parsed ``<CMD>…</CMD>`` envelope."""

    id: str
    fields: dict[str, str] = field(default_factory=dict)
    raw: str = ""

    def value(self, tag: str = "VALUE", default: str | None = None) -> str | None:
        """Return a field by tag name (case-insensitive), or ``default``."""
        return self.fields.get(tag.upper(), default)


def build_cmd(
    command_id: str,
    fields: dict[str, object] | None = None,
    flags: list[str] | None = None,
) -> str:
    """Build a ``<CMD>…</CMD>`` string.

    ``command_id`` is the leading token (e.g. ``READ``, ``ACTION``, ``SEARCH``).
    ``flags`` are value-less tags emitted first (e.g. ``INCLUDEALL``).
    ``fields`` are ``<TAG>value</TAG>`` pairs, emitted in insertion order.
    """
    parts = [f"<{command_id.upper()}>"]
    for flag in flags or []:
        parts.append(f"<{flag.upper()}>")
    for tag, val in (fields or {}).items():
        text = "" if val is None else str(val)
        parts.append(f"<{tag}>{text}</{tag}>")
    return "<CMD>" + "".join(parts) + "</CMD>"


def extract_blocks(buffer: str) -> tuple[list[str], str]:
    """Split a receive buffer into complete inner-blocks and the leftover tail.

    Returns ``(inners, remaining)`` where each *inner* is the text between
    ``<CMD>`` and ``</CMD>`` and *remaining* is any trailing partial envelope to
    carry into the next read.
    """
    inners: list[str] = []
    last_end = 0
    for match in _BLOCK_RE.finditer(buffer):
        inners.append(match.group(1))
        last_end = match.end()
    return inners, buffer[last_end:]


def parse_block(inner: str) -> Block:
    """Parse one inner-block (text between the CMD tags) into a :class:`Block`."""
    id_match = _ID_RE.match(inner)
    cmd_id = id_match.group(1).upper() if id_match else ""
    fields: dict[str, str] = {}
    for fmatch in _FIELD_RE.finditer(inner):
        tag = fmatch.group(1).upper()
        if tag == cmd_id:
            continue
        fields[tag] = fmatch.group(2)
    return Block(id=cmd_id, fields=fields, raw=f"<CMD>{inner}</CMD>")


def matches(block_id: str, expect: str) -> bool:
    """True if a response ``block_id`` answers a request whose ID is ``expect``.

    N3FJP usually answers ``FOO`` with ``FOORESPONSE`` and ``ACTION ENTER`` with
    ``ENTERRESPONSE``, so we accept the exact ID and the ``…RESPONSE`` form.
    """
    bid = block_id.upper()
    exp = expect.upper()
    return bid == exp or bid == exp + "RESPONSE"


# --- Raw-SQL safety classification ------------------------------------------

# Statements that can wipe or overwrite the whole log database.
_DROP_RE = re.compile(r"\b(drop|truncate|alter)\b", re.IGNORECASE)
_DELETE_RE = re.compile(r"\bdelete\b", re.IGNORECASE)
_UPDATE_RE = re.compile(r"\bupdate\b", re.IGNORECASE)
_WHERE_RE = re.compile(r"\bwhere\b", re.IGNORECASE)


def is_db_wipe_sql(sql: str) -> bool:
    """True if ``sql`` could delete or overwrite the entire database.

    Conservative: any DROP/TRUNCATE/ALTER, or a DELETE/UPDATE without a WHERE
    clause, is treated as a whole-database operation.
    """
    if _DROP_RE.search(sql):
        return True
    if (_DELETE_RE.search(sql) or _UPDATE_RE.search(sql)) and not _WHERE_RE.search(sql):
        return True
    return False
