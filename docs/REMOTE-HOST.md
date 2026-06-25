# Running N3FJP on a different computer than Claude

Most people run N3FJP on the **same** computer as Claude Desktop. In that case
leave **N3FJP host = `127.0.0.1`** and everything just works — you can ignore
this page.

This page is for the case where **N3FJP runs on another computer** (a Windows PC
or VM) while Claude Desktop runs elsewhere (e.g. a Mac).

## Why a correct LAN IP can still fail

Claude Desktop runs the MCP connector in a **sandbox that can only reach
`127.0.0.1` (loopback) — not LAN addresses**, even with macOS *Privacy &
Security → Local Network → Claude* turned on. So if you put N3FJP's LAN IP
(e.g. `192.168.1.50`) into the connector settings, it will **time out** — even
though `telnet 192.168.1.50 1100` works fine from a terminal on the same machine.
That's not a bug in N3FJP or contest-mcp; the connector simply isn't allowed to
dial the LAN.

The fix is a tiny **forwarder** that runs *outside* the sandbox on the same
machine as Claude Desktop. It listens on loopback and relays to the remote
N3FJP. You then point the connector at `127.0.0.1`, and the forwarder does the
LAN hop.

```
Claude Desktop (sandboxed connector)  --127.0.0.1:1100-->  forwarder  --LAN-->  N3FJP @ 192.168.1.50:1100
```

The forwarder ships with the package as the `contest-mcp-forward` command.

---

## macOS (launchd) — recommended, survives reboots

Replace `192.168.1.50` with your N3FJP computer's IP throughout.

### Add (install + start)

1. Find the forwarder. If you installed the `.mcpb` extension you can just use a
   copy of the script; the simplest is to install the package once:

   ```
   pipx install contest-mcp        # or: pip install --user contest-mcp
   which contest-mcp-forward
   ```

2. Create the launchd agent file
   `~/Library/LaunchAgents/com.contest-mcp.forward.plist` with this content
   (set the `--to` IP and the full path to `contest-mcp-forward` from step 1):

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
     <key>Label</key><string>com.contest-mcp.forward</string>
     <key>ProgramArguments</key>
     <array>
       <string>/FULL/PATH/TO/contest-mcp-forward</string>
       <string>--to</string><string>192.168.1.50:1100</string>
       <string>--listen</string><string>127.0.0.1:1100</string>
     </array>
     <key>RunAtLoad</key><true/>
     <key>KeepAlive</key><true/>
     <key>StandardOutPath</key><string>/tmp/contest-mcp-forward.log</string>
     <key>StandardErrorPath</key><string>/tmp/contest-mcp-forward.err</string>
   </dict>
   </plist>
   ```

3. Load and start it:

   ```
   launchctl load ~/Library/LaunchAgents/com.contest-mcp.forward.plist
   ```

4. In the contest-mcp connector settings, set **N3FJP host = `127.0.0.1`**, Save,
   then **Cmd-Q and reopen** Claude Desktop.

Verify:

```
launchctl list | grep contest-mcp.forward          # shows it running (status 0)
python3 -c "import socket;s=socket.create_connection(('127.0.0.1',1100),3);s.sendall(b'<CMD><PROGRAM></CMD>\r\n');print(s.recv(200))"
```

### Modify (e.g. the N3FJP computer's IP changed)

Edit the `--to` value in the plist, then reload:

```
launchctl unload ~/Library/LaunchAgents/com.contest-mcp.forward.plist
# edit the <string>192.168.1.50:1100</string> line to the new IP
launchctl load ~/Library/LaunchAgents/com.contest-mcp.forward.plist
```

The connector stays on `127.0.0.1` — you never touch the connector settings
again; only the plist's target IP changes.

### Delete (stop + remove)

```
launchctl unload ~/Library/LaunchAgents/com.contest-mcp.forward.plist
rm ~/Library/LaunchAgents/com.contest-mcp.forward.plist
```

(Then set the connector host back to wherever N3FJP actually is, if you stop
using the forwarder.)

### Quick test without installing a service (foreground)

```
contest-mcp-forward --to 192.168.1.50
```

Leave it running in a terminal; Ctrl-C to stop. Good for trying it before you
commit to the launchd agent.

---

## Windows (N3FJP on another Windows PC)

Run the forwarder on the machine where Claude Desktop runs:

```
pip install contest-mcp
contest-mcp-forward --to 192.168.1.50
```

To make it persistent, create a **Task Scheduler** task that runs
`contest-mcp-forward --to 192.168.1.50` *At log on* with *Run whether user is
logged on or not* unticked (so it shares your session), or drop a shortcut to it
in `shell:startup`.

## Linux (systemd --user)

```
pip install --user contest-mcp
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/contest-mcp-forward.service <<'EOF'
[Unit]
Description=contest-mcp loopback forwarder to remote N3FJP
[Service]
ExecStart=%h/.local/bin/contest-mcp-forward --to 192.168.1.50:1100 --listen 127.0.0.1:1100
Restart=always
[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now contest-mcp-forward.service
```

Modify: edit the `--to` IP in the unit and `systemctl --user restart
contest-mcp-forward`. Delete: `systemctl --user disable --now
contest-mcp-forward` then remove the unit file.

---

## Notes

- The forwarder only relays bytes; it adds no auth and no encryption. Keep it on
  a trusted LAN, exactly like the N3FJP API itself.
- One forwarder per remote service. If you also run fldigi on another host for
  `fldigi-mcp`, run a second forwarder (different local port) and point that
  connector at `127.0.0.1` the same way.
- This limitation is imposed by Claude Desktop's connector sandbox, so it can't
  be removed from inside the package — but the bundled forwarder makes the
  remote-host setup a one-time, few-line task.
