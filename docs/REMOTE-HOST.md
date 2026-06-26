# Running N3FJP on a different computer than Claude

## The common case: same computer → nothing to do

If N3FJP runs on the **same computer** as your MCP client (e.g. Claude Desktop),
leave **N3FJP host = `127.0.0.1`** in the connector settings. It just works. You
can stop reading.

## Different computer → use mcp-host-bridge

If N3FJP runs on **another computer** while a **sandboxed** MCP client (notably
Claude Desktop) runs elsewhere, there's a catch: the client runs the connector
**sandboxed so it can only reach `127.0.0.1`, not LAN addresses**. So entering
N3FJP's LAN IP (e.g. `192.168.1.50`) in the settings will *time out* — even though
`telnet` to that IP works from a terminal. It's a security sandbox, not a bug, and
it's a property of the **client**, not of contest-mcp.

The fix is a tiny relay that runs on the client computer, listens on `127.0.0.1`,
and forwards to the remote N3FJP. Rather than bundle that here, contest-mcp uses
the standalone, reusable tool **[mcp-host-bridge](https://github.com/sbrunner-atx/mcp-host-bridge)**
(it serves fldigi and other local MCPs too).

### Setup (on the computer running the MCP client)

1. Get `mcp-host-bridge`: download the single binary for your OS from its
   [releases](https://github.com/sbrunner-atx/mcp-host-bridge/releases)
   (`mcp-host-bridge-macos` / `mcp-host-bridge.exe` / `mcp-host-bridge-linux`),
   or `pipx install mcp-host-bridge`.
2. Install the bridge for N3FJP (it knows `n3fjp` = port 1100):
   ```
   mcp-host-bridge install n3fjp --to 192.168.1.50
   ```
   This sets up a self-starting background service (launchd on macOS, `netsh`
   portproxy on Windows, systemd on Linux) and tests the connection.
3. In the **contest-mcp settings**, set **N3FJP host = `127.0.0.1`** (port
   `1100`), Save, then fully quit and reopen the client.

Manage it with `mcp-host-bridge status n3fjp` / `uninstall n3fjp`, and change the
N3FJP IP by re-running `install n3fjp --to <new-ip>`. Full instructions are in the
[mcp-host-bridge README](https://github.com/sbrunner-atx/mcp-host-bridge#readme).

## Troubleshooting

Run contest-mcp's **`diagnostics`** tool (it does not connect to N3FJP). It
reports the resolved `N3FJP_HOST`/`PORT`, this process's hostname/Python, and the
host's network interfaces — so you can see whether the process can even reach the
`192.168.x` network, and whether you need the bridge above.

## Notes

- The bridge only relays bytes — no auth, no encryption — so keep it on a trusted
  LAN, like the N3FJP API itself.
- Best of all: if you can run N3FJP and the MCP client on the **same** computer,
  you avoid all of this.
