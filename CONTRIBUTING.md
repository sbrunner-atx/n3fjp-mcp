# Contributing to contest-mcp

Thanks for your interest in improving contest-mcp! This is an experimental,
community project (MIT licensed) and contributions are welcome.

## Development setup

```bash
git clone https://github.com/sbrunner-atx/contest-mcp.git
cd contest-mcp
uv sync
```

- **Lint:** `uv run ruff check .`
- **Test:** `uv run pytest` (no running N3FJP required)
- **Try it live:** `python3 smoke_test.py <host> <port>` with N3FJP running and
  its API enabled (Settings → Application Program Interface → "TCP API Enabled").

## Project layout

```
src/contest_mcp/
  config.py     # env-var configuration (N3FJP_HOST/PORT/TIMEOUT/ALLOW_DB_WIPE)
  protocol.py   # pure wire helpers: build/parse <CMD> blocks, SQL-wipe check
  client.py     # persistent TCP client + reader thread + notification buffer
  methods.py    # operation maps, control catalog, contest presets, coercion
  server.py     # FastMCP tools (the 9 groups + escape hatch) and the safety model
docs/           # API reference (md + pdf), spec, install, test plan
tests/          # unit tests (protocol, methods, server safety model)
```

`protocol.py` and `methods.py` are deliberately free of sockets and the MCP SDK
so they can be unit-tested in isolation. Keep new wire logic there where possible.

## Guidelines

- **Match N3FJP's terminology** in tool/operation/field names so the API stays
  recognizable to operators.
- **Respect the safety model.** Reads should be marked `readOnlyHint`; new write
  operations default to approval; anything that deletes/overwrites records is
  destructive and must require `confirm=true`; nothing may bypass the
  `N3FJP_ALLOW_DB_WIPE` gate for whole-database operations.
- **Verify against a real instance** when you can, and note the N3FJP program and
  API version you tested with (the API evolves; e.g. v2.2 dropped some 0.9
  commands and renamed response tags).
- Keep runtime dependencies minimal (standard library + the MCP SDK).
- Run `ruff` and `pytest` before opening a PR; CI runs them on 3.10–3.12.

## Reporting issues

Please include your N3FJP program and version, the API version (from the `status`
tool), the command/operation, and the raw `<CMD>` exchange if you can capture it.
Use the [thumbs-down / issues](https://github.com/sbrunner-atx/contest-mcp/issues)
to report problems.

## License

By contributing you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
