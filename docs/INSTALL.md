# Installing contest-mcp — Operator's Guide

This lets you log contacts in **N3FJP** by chatting with Claude — for example
*"log W1AW, 2A in STX"* or *"how many QSOs do we have?"*. No programming, no
terminal.

## Where does it work?

This is a **Claude Desktop** extension. It runs in:

- ✅ **Claude Desktop** on **macOS** or **Windows**

It does **not** work in:

- ❌ Claude in a web browser (claude.ai)
- ❌ Claude on iPhone or Android

## What you need

- **Claude Desktop** installed (from <https://claude.ai/download>).
- An **N3FJP program** installed and running (Amateur Contact Log or any of the
  contest loggers), with its API turned on:
  **Settings → Application Program Interface → check "TCP API Enabled"**.
  The default API port is **1100**.

You do **not** need Python or anything technical — Claude Desktop handles that.

> **Heads-up on ports.** N3FJP's **API** (port **1100**) is what this extension
> uses. That is *different* from N3FJP's multi-computer **Network** feature
> (Settings → Network), which uses its own port. They are unrelated — you only
> need the API enabled.

## Step 1 — Download the extension

1. Go to **<https://github.com/sbrunner-atx/contest-mcp/releases/latest>**
2. Under **Assets**, click **`contest-mcp.mcpb`** to download it.

## Step 2 — Install it in Claude Desktop

1. Open **Claude Desktop**.
2. Open **Settings** (the Claude menu, or the gear/⚙︎ icon).
3. Click **Extensions**.
4. Click **Advanced settings**, then **Install Extension…**.
5. Choose the **`contest-mcp.mcpb`** file you just downloaded, and **Install**.

> Tip: the **Install Extension…** button lives under **Advanced settings** —
> that's the spot people tend to miss.

## Step 3 — Settings

A short form appears. For a normal setup where N3FJP runs on the same computer,
the defaults are correct:

- **N3FJP host** — `127.0.0.1` (change only if N3FJP runs on another PC).
- **N3FJP API port** — `1100` (match what N3FJP shows on the API form).
- **Allow whole-database wipe** — **leave OFF.** This is a safety switch; only
  turn it on if you truly need Claude to run database-wide deletes/overwrites and
  you have backed up your log.

Click **Save**.

## Step 4 — Try it

1. Make sure your **N3FJP program is open** and the API is enabled.
2. In Claude Desktop, type: **"What's the N3FJP status?"**
3. Claude replies with the program, version, QSO count, and current band/mode.

Then try *"check if W1AW is a dupe"*, or *"log K1ABC, 1D in EMA"*.

## About logging (please read)

- **Reads** (status, search, dupe checks) happen freely.
- **Logging and changes** ask for your approval each time.
- **Deleting records or running raw SQL** require an explicit confirmation.
- **Whole-database** operations are blocked unless you deliberately enabled the
  danger switch in settings.

You remain the responsible operator — treat Claude as an assistant, and keep a
backup of your log.

### If a contact won't log ("0 records added")

If Claude logs a QSO but N3FJP reports **0 records added** (or you see a *"Server
Failed to Respond"* popup), N3FJP is probably in **Network mode** pointing at a
networking server that isn't responding. Either run N3FJP **standalone** (log to
the local file) or make sure your N3FJP networking server is reachable. This is
an N3FJP setting, not an extension problem.

## Running N3FJP on another computer

In the extension settings, set **N3FJP host** to that computer's address (e.g.
`192.168.1.50`) and the API port. Keep it on a trusted LAN — the API is not
encrypted or authenticated.

## Troubleshooting

- **"Could not reach N3FJP"** — make sure the program is open and
  **Settings → Application Program Interface → "TCP API Enabled"** is checked,
  and that the host/port match.
- **Nothing happens after installing** — fully quit Claude Desktop and reopen it.
- **"CMD_NOT_FOUND"** — that command isn't supported by your N3FJP version; ask
  Claude for the `status` to see your API version.

## Updating

Download the newest `contest-mcp.mcpb` from the releases page and install it the
same way — it replaces the old one.
