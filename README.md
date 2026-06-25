# contest-mcp

<!-- mcp-name: io.github.sbrunner-atx/contest-mcp -->

An [MCP](https://modelcontextprotocol.io/) server for **logging amateur-radio
QSOs** to [N3FJP logging software](https://www.n3fjp.com/) — Amateur Contact Log
and the 100-plus N3FJP contest loggers — from MCP-aware clients such as Claude
Desktop.

Every program in the N3FJP suite shares one TCP control API. `contest-mcp` speaks
that protocol directly (Python's standard-library `socket`, no third-party
wrapper) and exposes it as a small set of logically-grouped MCP tools, so an
assistant can log contacts, read the log, run dupe checks, and manage band/mode
through plain language.

It is the **logging** half of an "operate → log" workflow; its sibling project
[`fldigi-mcp`](https://github.com/sbrunner-atx/fldigi-mcp) operates the radio.

> **Status:** experimental (v0.1). Verified live against N3FJP's ARRL Field Day
> Contest Log, **API version 2.2**. The protocol is shared across the suite, but
> field sets vary per contest — confirm with the `fields` tool.

> The project is named **contest-mcp** (not "n3fjp-mcp") to avoid any conflict
> with the N3FJP name and callsign. It is an independent project and is not
> affiliated with or endorsed by Affirmatech / N3FJP.

## Highlights

- **Automatic logging** — the headline `log` tool runs the real N3FJP flow:
  set the call → `CALLTAB` (dupe check + previous-contact lookup) → set the
  exchange → `ENTER`, surfacing the dupe response and the number of records added.
- **Broad coverage** — read queries, field read/write, search/list, dupe and
  entity checks, band/mode/frequency, direct database operations, and opt-in
  push notifications, grouped into 9 tools (one permission each) plus an
  `n3fjp_call` escape hatch for the long tail and future commands.
- **Safe by design** for a tool that can touch your log database:
  - **Reads** are marked read-only so clients can default them to *Always Allow*.
  - **Writes** (logging, band/mode) default to *Needs Approval*.
  - **Destructive** operations (add-direct, delete a record, raw SQL)
    additionally require `confirm=true`.
  - **Whole-database** wipes/overwrites are refused outright unless you flip a
    dedicated, off-by-default `N3FJP_ALLOW_DB_WIPE` switch.
- **Names match N3FJP** — tools and fields mirror N3FJP's own terminology
  (Action `ENTER`, `CALLTAB`, the `TXTENTRY…` boxes, Class/Section, etc.).
- **No fragile dependencies** — the only runtime dependency is the MCP SDK.

## Requirements

To **install the desktop extension** (`.mcpb`):

- An **N3FJP program** running, with **Settings → Application Program Interface →
  "TCP API Enabled"** checked (default API port `1100`).

Claude Desktop's `uv` runtime supplies Python and the dependencies, so end users
do **not** install Python or `uv` themselves.

For **development from source** you additionally need **Python 3.10+** and
**[uv](https://docs.astral.sh/uv/)** (and **Node.js**, only for the MCP Inspector).

## Install

### Easiest: one-click desktop extension

Download `contest-mcp.mcpb` from the latest
[release](https://github.com/sbrunner-atx/contest-mcp/releases), then in Claude
Desktop go to **Settings → Extensions → Advanced settings → Install Extension…**
and choose the file. A short settings form asks for the host/port (defaults to
`127.0.0.1:1100`). **No terminal, no Python, no uv to install.**

👉 New to this? Follow the step-by-step [install guide](docs/INSTALL.md).

### From source (development)

```bash
git clone https://github.com/sbrunner-atx/contest-mcp.git
cd contest-mcp
uv sync
```

Then add it to Claude Desktop's config
(`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "contest": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/contest-mcp", "run", "contest-mcp"],
      "env": { "N3FJP_HOST": "127.0.0.1", "N3FJP_PORT": "1100" }
    }
  }
}
```

Restart Claude Desktop and ask *"What's the N3FJP status?"*.

### Try it with the MCP Inspector

```bash
uv run mcp dev src/contest_mcp/server.py
```

## Tools

Each tool is one permission and takes an `operation` argument.

| Tool | Default | Controls |
| --- | --- | --- |
| `status` | read | snapshot: program, version, API version, QSO count, band/mode/frequency |
| `query` | read | program, qso_count, next_serial, log/settings/shared paths, qso_rate, band_mode_freq |
| `fields` | read | read one entry box, or list visible / all fields with values |
| `search` | read | list recent, search, dupecheck (no side effects), entity status |
| `log` | **approval** | `log_qso` (set call → CALLTAB → exchange → ENTER), set, set_many, calltab, enter, clear, focus |
| `bandmode` | **approval** | change_freq, set_band, set_mode, ignore_rig_polls |
| `notifications` | **approval** | enable / disable push events, drain buffered events |
| `database` | **approval** | add_direct, delete a record, raw sql, checklog, openlog, sqlclose |
| `n3fjp_call` | **approval** | escape hatch — send any raw command, incl. future ones |

All write tools sit at the **Needs Approval** tier, so you can set them to *Always
Allow* in the client for hands-off automation. The single exception is a
whole-database wipe (see below), which is hard-blocked regardless.

The headline is `log` → `log_qso`:

```
log_qso  call="W1AW"  contest="field_day"  exchange={"class":"2A","section":"CT"}
```

This sets the call, fires `CALLTAB` (dupe check), fills the exchange, sends
`ENTER`, and reports records added plus any dupe detail.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `N3FJP_HOST` | `127.0.0.1` | N3FJP API host |
| `N3FJP_PORT` | `1100` | N3FJP API port (the suite's default) |
| `N3FJP_TIMEOUT` | `6` | Socket/response timeout, seconds |
| `N3FJP_ALLOW_DB_WIPE` | `off` | **Danger.** Allow whole-database delete/overwrite (raw SQL `DROP`/`TRUNCATE`/unscoped `DELETE`/`UPDATE`). Leave **off** unless you really mean it |

In the packaged desktop extension these appear as a settings form.

### Safety model

Logging doesn't key a transmitter, so there is no transmit gate. The protection
here is about your **log database**:

- **Read** operations (`status`, `query`, `fields`, `search`) are marked
  read-only — clients can default them to *Always Allow*.
- **Write** operations — logging (`log`), band/mode (`bandmode`),
  notifications, and **adding, editing, or deleting individual records**
  (`database`), plus the `n3fjp_call` escape hatch — all sit at the *Needs
  Approval* tier. There is no extra in-band confirmation, so you can set them to
  *Always Allow* in the client and let automation run hands-off.
- **Whole-database** operations — raw SQL that could delete or overwrite the
  entire log (`DROP`, `TRUNCATE`, a `DELETE`/`UPDATE` with no `WHERE`) — are the
  one exception: **refused** unless `N3FJP_ALLOW_DB_WIPE` is on. This switch is
  separate from, and stricter than, the client's approval prompts, and carries a
  stern warning in the settings form. **Back up your log before ever enabling
  it.**

Wherever possible, `contest-mcp` leans on N3FJP's own validation (it dupe-checks
and reports oddities) and surfaces those responses rather than re-implementing
them.

### Remote / contest-station setups (N3FJP on another computer)

If N3FJP runs on the **same** computer as Claude Desktop (the common case), leave
`N3FJP_HOST` at `127.0.0.1` and you're done.

If N3FJP runs on a **different** computer, there's a catch: Claude Desktop runs
the connector **sandboxed so it can only reach `127.0.0.1`, not LAN addresses** —
so putting N3FJP's LAN IP in the settings will time out even though `telnet` to
that IP works. The fix ships with the package: run the `contest-mcp-forward`
forwarder on the Claude Desktop machine and point the connector at `127.0.0.1`:

```
contest-mcp-forward --to 192.168.1.50      # relays 127.0.0.1:1100 -> the N3FJP PC
```

Then set **N3FJP host = `127.0.0.1`**. Full install / modify / remove
instructions (macOS launchd, Windows, Linux) are in
[docs/REMOTE-HOST.md](docs/REMOTE-HOST.md). Keep the link on a trusted LAN — the
API is unauthenticated.

## Documentation

### 📻 A field-tested N3FJP API reference (free community resource)

Building this server meant reverse-engineering and **live-verifying** the N3FJP
TCP API, including several places where today's API (v2.2) differs from the
public 0.9 documentation. We've written that up as a complete, human-readable
guide and are sharing it freely to give back to the community:

- **[The N3FJP TCP API — A Field-Tested Reference](docs/N3FJP-API.md)**
  ([PDF](docs/N3FJP-API.pdf)) — transport, every command grouped by area,
  verified response examples, contest exchange fields, and a hard-won
  **gotchas** section (the API vs. networking ports, `CMD_NOT_FOUND`, commands
  removed since 0.9, the `CALLTABEVENT` lookup, and why `ENTER` can report 0 yet
  still log in networked mode).
- **[Machine-readable spec](docs/N3FJP-API-SPEC.md)** — the same information in a
  terse, structured command catalog suitable for code generation.

Corrections and additions are welcome — please
[open an issue or PR](https://github.com/sbrunner-atx/contest-mcp/issues).

### Project docs

- [Install guide](docs/INSTALL.md) and [Test plan](docs/TEST-PLAN.md).

## Development

```bash
uv sync
uv run ruff check .      # lint
uv run pytest            # tests (no running N3FJP required)
python3 smoke_test.py 192.168.1.50 1100   # Phase 0: prove the link to N3FJP
```

The test suite covers the wire protocol, the operation maps and field catalog,
type coercion, and the permission/confirm safety model; none of it requires a
running N3FJP.

## License

[MIT](LICENSE) © 2026 Stefan Brunner (AE5VG)
