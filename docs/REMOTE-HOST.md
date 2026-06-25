# Running N3FJP on a different computer than Claude

## The common case: same computer → nothing to do

If N3FJP runs on the **same computer** as Claude Desktop, leave **N3FJP host =
`127.0.0.1`** in the connector settings. It just works. You can stop reading.

## Different computer → one command

If N3FJP runs on **another computer** (a Windows PC or VM) while Claude Desktop
runs elsewhere, there's a catch: Claude Desktop runs the connector **sandboxed so
it can only reach `127.0.0.1`, not LAN addresses**. So entering N3FJP's LAN IP
(e.g. `192.168.1.50`) in the settings will *time out* — even though `telnet` to
that IP works from a terminal. It's a security sandbox, not a bug.

The fix is a tiny **forwarder** that runs on the Claude Desktop computer, listens
on `127.0.0.1`, and relays to the remote N3FJP. It's bundled with the package and
installs itself with one command.

```
Claude Desktop (sandboxed)  ──127.0.0.1:1100──▶  forwarder  ──LAN──▶  N3FJP @ 192.168.1.50:1100
```

### Step 1 — install + start the forwarder (on the Claude Desktop computer)

Replace `192.168.1.50` with your N3FJP computer's IP.

**macOS / Linux:**
```
pipx install contest-mcp        # or: pip install --user contest-mcp
contest-mcp-forward install --to 192.168.1.50
```

**Windows (PowerShell):**
```
pip install contest-mcp
contest-mcp-forward install --to 192.168.1.50
```

That sets up a background service that **starts automatically on login and
restarts if it dies** (launchd on macOS, systemd on Linux, a logon Scheduled
Task on Windows), then prints a connection test.

> No Python? Install it first — macOS already has it; on Windows use
> `winget install Python.Python.3` (or python.org); on Linux it's preinstalled.

### Step 2 — point the connector at loopback

In the **contest-mcp settings**, set **N3FJP host = `127.0.0.1`** (port `1100`),
click **Save**, then **fully quit and reopen** Claude Desktop. Ask Claude *"what's
the N3FJP status?"* to confirm.

That's it — you never touch the connector settings again.

## Managing the forwarder

```
contest-mcp-forward status                    # check it + test the connection
contest-mcp-forward install --to 192.168.1.99 # change the N3FJP IP (just re-run install)
contest-mcp-forward uninstall                 # stop + remove it
```

When your N3FJP computer's IP changes, just re-run `install --to <new-ip>` — the
connector stays on `127.0.0.1` forever.

### Try it without installing a service (foreground)

```
contest-mcp-forward run --to 192.168.1.50
```

Leave it running in a terminal window; Ctrl-C to stop. Good for a quick test
before committing to the background service.

## Notes

- The forwarder only relays bytes — no auth, no encryption — so keep it on a
  trusted LAN, exactly like the N3FJP API itself.
- One forwarder per remote service. If `fldigi-mcp` also talks to fldigi on
  another host, run a second forwarder on a different local port and point that
  connector at `127.0.0.1` too.
- This sandbox limitation is imposed by Claude Desktop on the connector, so it
  can't be removed from inside the package — but the bundled installer makes the
  remote-host setup a one-line, one-time task.
- Best of all: if you can simply run N3FJP and Claude Desktop on the **same**
  computer, you avoid all of this.
