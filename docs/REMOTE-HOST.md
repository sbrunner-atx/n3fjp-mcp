# Running N3FJP on a different computer than Claude

## Same computer: nothing to do

If N3FJP runs on the **same computer** as your MCP client (for example Claude
Desktop on a Windows PC), leave **N3FJP host = `127.0.0.1`** in the connector
settings. You can stop reading.

## Different computer: enter its address

N3FJP runs only on Windows, so on a Mac it is always somewhere else: in a Windows
virtual machine (Parallels, VMware Fusion, UTM) or on a Windows PC on the LAN. A
VM has its own network address, so it counts as a different computer.

1. In N3FJP, check **Settings → Application Program Interface → "TCP API
   Enabled"**. Note the computer's address (for example `192.168.1.50`) and the
   API port (default `1100`).
2. In the **n3fjp-mcp settings**, set **N3FJP host** to that address and the
   port to match. Save.
3. Ask Claude for N3FJP's status. On a Mac, the very first connection can fail
   with "No route to host" while macOS checks the Local Network permission. Ask
   again; the second try connects.
4. If it keeps failing, open **System Settings → Privacy & Security → Local
   Network** on the Mac and turn Claude on. Then check that the Windows firewall
   lets port 1100 in.

Claude Desktop connects to the LAN address directly. This was tested on
23 November 2026 with Claude Desktop on macOS 27 and N3FJP's ARRL Field Day log
on a Windows PC, and the first try connected and read the log.

If you installed mcp-host-bridge for N3FJP earlier, you no longer need it with a
current Claude Desktop. Set the host to the LAN address as above, then remove the
relay with `mcp-host-bridge uninstall n3fjp`, or leave it running; it does no harm.

## Fallback: mcp-host-bridge

Some clients still run connectors so that they reach only `127.0.0.1`, not LAN
addresses: an older Claude Desktop or macOS, or an MCP client that sandboxes its
connectors. There, entering N3FJP's LAN address times out even though `telnet`
to it works from a terminal. The client causes this, and no n3fjp-mcp setting
changes it.

The fix is a small relay on the client computer that listens on `127.0.0.1` and
forwards to the remote N3FJP. n3fjp-mcp uses the standalone tool
**[mcp-host-bridge](https://github.com/sbrunner-atx/mcp-host-bridge)** (it serves
fldigi and other local services too).

1. Get `mcp-host-bridge`: download the single binary for your OS from its
   [releases](https://github.com/sbrunner-atx/mcp-host-bridge/releases)
   (`mcp-host-bridge-macos`, `mcp-host-bridge.exe` or `mcp-host-bridge-linux`),
   or `pipx install mcp-host-bridge`.
2. Install the bridge for N3FJP (it knows `n3fjp` = port 1100):
   ```
   mcp-host-bridge install n3fjp --to 192.168.1.50
   ```
   This sets up a self-starting background service (launchd on macOS, `netsh`
   portproxy on Windows, systemd on Linux) and tests the connection.
3. In the **n3fjp-mcp settings**, set **N3FJP host = `127.0.0.1`** (port
   `1100`), Save, then fully quit and reopen the client.

Manage it with `mcp-host-bridge status n3fjp` and `uninstall n3fjp`, and change
the N3FJP address by running `install n3fjp --to <new-ip>` again. Full
instructions are in the
[mcp-host-bridge README](https://github.com/sbrunner-atx/mcp-host-bridge#readme).

## Troubleshooting

Run n3fjp-mcp's **`diagnostics`** tool (it does not connect to N3FJP). It
reports the resolved `N3FJP_HOST` and `PORT`, this process's hostname and
Python, and the host's network interfaces, so you can see whether the process
can reach the `192.168.x` network at all.

## Notes

- The N3FJP API has no authentication and no encryption, and neither does the
  bridge. Keep both on a trusted LAN.
- If you can run N3FJP and the MCP client on the **same** computer, none of this
  applies.
