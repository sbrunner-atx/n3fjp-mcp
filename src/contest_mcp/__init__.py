"""contest-mcp — log amateur-radio QSOs to N3FJP software from MCP clients.

Every program in the N3FJP Software suite (Amateur Contact Log and the contest
loggers) exposes the same TCP control API. This package speaks that protocol
directly — with Python's standard-library :mod:`socket`, no third-party wrapper —
and presents it to MCP clients (Claude Desktop, the MCP Inspector, etc.) as a
small set of logically-grouped tools.

It is the logging half of an "operate → log" workflow; its sibling project
``fldigi-mcp`` operates the radio.
"""

__version__ = "0.1.2"
