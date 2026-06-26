# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] - 2026-06-23

### Added
- **`diagnostics` tool** (read-only, no N3FJP connection): reports the resolved
  `N3FJP_HOST`/`PORT`, this process's Python/hostname, and the host's network
  interfaces — so you can tell whether the process can even see the target's
  network (e.g. host-side vs. sandboxed).

### Changed
- **Structured connection errors.** The "could not reach N3FJP" message now
  reports `target=host:port`, the symbolic `errno`
  (ETIMEDOUT/EHOSTUNREACH/ENETUNREACH/ECONNREFUSED/ENOTFOUND), and host network
  info — far more useful than the old "is N3FJP running?" text.
- **Remote-host setups now use the standalone
  [mcp-host-bridge](https://github.com/sbrunner-atx/mcp-host-bridge) tool**
  instead of a bundled forwarder. A sandboxed MCP client (e.g. Claude Desktop)
  can only reach loopback, so when N3FJP is on another computer you run
  `mcp-host-bridge install n3fjp --to <ip>` on the client machine and set the
  N3FJP host to `127.0.0.1`. Keeping the relay external keeps contest-mcp
  universal across MCP clients. See `docs/REMOTE-HOST.md`.

## [0.1.1] - 2026-06-23

### Changed
- **Permission model:** adding, editing, and deleting *individual* records (the
  `database` tool) and the `n3fjp_call` escape hatch are now ordinary
  *Needs Approval* writes — the same tier as logging — instead of requiring an
  extra in-band `confirm=true`. This lets them be globally allowed in the client
  for hands-off automation. The `confirm` argument was removed.
- The **only** hard-blocked class is now a whole-database wipe/overwrite
  (`DROP`/`TRUNCATE` or an unscoped `DELETE`/`UPDATE`), still gated by the
  off-by-default `N3FJP_ALLOW_DB_WIPE` switch. Scoped record operations run
  without it. Docs (README, INSTALL, API spec) updated to match.

## [0.1.0] - 2026-06-23

Initial release.

### Added
- MCP server exposing the N3FJP logging software's TCP API (shared across
  Amateur Contact Log and the contest loggers), talking to it directly with
  Python's standard-library `socket` — no third-party wrapper.
- Persistent TCP client with a background reader thread that splits the
  `<CMD>…</CMD>` stream, matches responses to requests, and buffers opt-in push
  notifications for on-demand draining.
- **Coverage** organised into 9 logically-grouped tools (one permission each):
  `status`, `query`, `fields`, `search`, `log`, `bandmode`, `notifications`,
  `database`, and an `n3fjp_call` escape hatch for anything else (including
  newer commands — an unknown command is reported via N3FJP's `CMD_NOT_FOUND`).
- **Automatic logging**: `log` → `log_qso` runs the real N3FJP flow (set call →
  `CALLTAB` → exchange → `ENTER`), surfacing the `CALLTABEVENT` call lookup
  (country, DXCC, zones, bearing, distance), dupe detection, and records added.
- Tool and field names aligned with N3FJP's own terminology (Action `ENTER`,
  `CALLTAB`, the `TXTENTRY…` boxes, Class/Section). Per-contest exchange presets.
- **Safety model** for a tool that can touch the log database:
  - reads are marked read-only (clients can default them to Always Allow);
  - writes default to Needs Approval;
  - destructive operations (add-direct, delete a record, raw SQL) require
    `confirm=true`;
  - whole-database wipes/overwrites (DROP/TRUNCATE, unscoped DELETE/UPDATE) are
    refused unless the off-by-default `N3FJP_ALLOW_DB_WIPE` switch is enabled.
- Configuration via environment variables (`N3FJP_HOST`, `N3FJP_PORT`,
  `N3FJP_TIMEOUT`, `N3FJP_ALLOW_DB_WIPE`), surfaced as a settings form in the
  packaged desktop extension.
- Unit test suite (wire protocol, operation maps and field catalog, type
  coercion, and the permission/confirm safety model) and a GitHub Actions CI
  workflow running ruff and pytest on Python 3.10–3.12.
- Documentation: README, a human-readable N3FJP API reference (+ PDF) and a
  machine-readable spec, an install guide, and a live test plan. The API
  reference and spec were verified live against N3FJP API version 2.2.

[Unreleased]: https://github.com/sbrunner-atx/contest-mcp/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/sbrunner-atx/contest-mcp/releases/tag/v0.1.2
[0.1.1]: https://github.com/sbrunner-atx/contest-mcp/releases/tag/v0.1.1
[0.1.0]: https://github.com/sbrunner-atx/contest-mcp/releases/tag/v0.1.0
