# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/sbrunner-atx/contest-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sbrunner-atx/contest-mcp/releases/tag/v0.1.0
