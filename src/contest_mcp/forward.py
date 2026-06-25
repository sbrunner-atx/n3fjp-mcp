"""A tiny loopback-to-remote TCP forwarder, with one-command install.

Why this exists: Claude Desktop runs the MCP connector **sandboxed so it can only
reach 127.0.0.1 (loopback), not LAN addresses**. If N3FJP runs on a *different*
computer than Claude Desktop, the connector cannot dial the LAN directly. This
forwarder runs *outside* that sandbox, listens on loopback, and relays to the
remote N3FJP. You then set the connector's *N3FJP host* to ``127.0.0.1``.

Standard-library only, and self-contained (this single file is also the install
logic), so it works whether run from the installed package or as a downloaded
script.

Quick start (on the same computer as Claude Desktop)::

    contest-mcp-forward install --to 192.168.1.50     # set up + start, survives reboot
    contest-mcp-forward status                         # check it
    contest-mcp-forward uninstall                      # remove it

Then set the connector's N3FJP host to 127.0.0.1 and restart Claude Desktop.
See ``docs/REMOTE-HOST.md``.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import threading
import time

LABEL = "com.contest-mcp.forward"
STABLE_DIR = os.path.expanduser("~/.contest-mcp")
STABLE_SCRIPT = os.path.join(STABLE_DIR, "forward.py")


# --- the actual forwarder ----------------------------------------------------


def _split_hostport(value: str, default_port: int) -> tuple[str, int]:
    if ":" in value:
        host, _, port = value.rpartition(":")
        return host, int(port)
    return value, default_port


def _pipe(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.close()
            except OSError:
                pass


def _handle(client: socket.socket, target: tuple[str, int], timeout: float) -> None:
    try:
        upstream = socket.create_connection(target, timeout=timeout)
    except OSError as exc:
        print(f"upstream connect to {target[0]}:{target[1]} failed: {exc}", flush=True)
        client.close()
        return
    threading.Thread(target=_pipe, args=(client, upstream), daemon=True).start()
    threading.Thread(target=_pipe, args=(upstream, client), daemon=True).start()


def serve(
    listen_host: str,
    listen_port: int,
    target_host: str,
    target_port: int,
    timeout: float = 6.0,
) -> None:
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((listen_host, listen_port))
    srv.listen(50)
    print(
        f"contest-mcp-forward: {listen_host}:{listen_port} -> {target_host}:{target_port}",
        flush=True,
    )
    while True:
        client, _ = srv.accept()
        threading.Thread(
            target=_handle, args=(client, (target_host, target_port), timeout), daemon=True
        ).start()


# --- connectivity test -------------------------------------------------------


def _probe(listen_host: str, listen_port: int) -> str:
    try:
        s = socket.create_connection((listen_host, listen_port), timeout=5)
        s.sendall(b"<CMD><PROGRAM></CMD>\r\n")
        s.settimeout(4)
        data = s.recv(400).decode("utf-8", "replace")
        s.close()
        if "PROGRAMRESPONSE" in data:
            return "OK — N3FJP answered through the forwarder."
        return f"connected, but unexpected reply: {data[:120]!r}"
    except OSError as exc:
        return f"FAILED: {exc}"


# --- install / uninstall (per OS) --------------------------------------------


def _stable_python() -> str:
    """A stable python3 path for the service (not an ephemeral uvx/pipx venv)."""
    if sys.platform == "darwin" and os.path.exists("/usr/bin/python3"):
        return "/usr/bin/python3"
    return shutil.which("python3") or shutil.which("python") or sys.executable


def _install_self() -> str:
    """Copy this file to a stable location so the service doesn't depend on $PATH."""
    os.makedirs(STABLE_DIR, exist_ok=True)
    shutil.copyfile(os.path.abspath(__file__), STABLE_SCRIPT)
    return STABLE_SCRIPT


def _run_args(script: str, target: str, listen: str) -> list[str]:
    return [_stable_python(), script, "run", "--to", target, "--listen", listen]


def _install_macos(target: str, listen: str) -> int:
    script = _install_self()
    plist = os.path.expanduser(f"~/Library/LaunchAgents/{LABEL}.plist")
    os.makedirs(os.path.dirname(plist), exist_ok=True)
    args = "".join(f"        <string>{a}</string>\n" for a in _run_args(script, target, listen))
    plist_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n<dict>\n'
        f"    <key>Label</key><string>{LABEL}</string>\n"
        "    <key>ProgramArguments</key>\n    <array>\n"
        f"{args}    </array>\n"
        "    <key>RunAtLoad</key><true/>\n"
        "    <key>KeepAlive</key><true/>\n"
        "    <key>StandardOutPath</key><string>/tmp/contest-mcp-forward.log</string>\n"
        "    <key>StandardErrorPath</key><string>/tmp/contest-mcp-forward.err</string>\n"
        "</dict>\n</plist>\n"
    )
    with open(plist, "w") as fh:
        fh.write(plist_xml)
    subprocess.run(["launchctl", "unload", plist], capture_output=True)
    subprocess.run(["launchctl", "load", plist], capture_output=True)
    print(f"Installed launchd agent {LABEL}\n  plist: {plist}\n  script: {script}")
    return 0


def _uninstall_macos() -> int:
    plist = os.path.expanduser(f"~/Library/LaunchAgents/{LABEL}.plist")
    subprocess.run(["launchctl", "unload", plist], capture_output=True)
    if os.path.exists(plist):
        os.remove(plist)
    print(f"Removed launchd agent {LABEL}.")
    return 0


def _install_linux(target: str, listen: str) -> int:
    script = _install_self()
    unit_dir = os.path.expanduser("~/.config/systemd/user")
    os.makedirs(unit_dir, exist_ok=True)
    unit = os.path.join(unit_dir, "contest-mcp-forward.service")
    exec_start = " ".join(_run_args(script, target, listen))
    with open(unit, "w") as fh:
        fh.write(
            "[Unit]\nDescription=contest-mcp loopback forwarder to remote N3FJP\n\n"
            f"[Service]\nExecStart={exec_start}\nRestart=always\n\n"
            "[Install]\nWantedBy=default.target\n"
        )
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
    subprocess.run(
        ["systemctl", "--user", "enable", "--now", "contest-mcp-forward.service"],
        capture_output=True,
    )
    print(f"Installed systemd --user service.\n  unit: {unit}\n  script: {script}")
    return 0


def _uninstall_linux() -> int:
    subprocess.run(
        ["systemctl", "--user", "disable", "--now", "contest-mcp-forward.service"],
        capture_output=True,
    )
    unit = os.path.expanduser("~/.config/systemd/user/contest-mcp-forward.service")
    if os.path.exists(unit):
        os.remove(unit)
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
    print("Removed systemd --user service.")
    return 0


def _install_windows(target: str, listen: str) -> int:
    script = _install_self()
    cmd = " ".join(f'"{a}"' if " " in a else a for a in _run_args(script, target, listen))
    rc = subprocess.run(
        ["schtasks", "/Create", "/TN", "contest-mcp-forward", "/TR", cmd,
         "/SC", "ONLOGON", "/F"],
        capture_output=True, text=True,
    )
    if rc.returncode == 0:
        subprocess.run(["schtasks", "/Run", "/TN", "contest-mcp-forward"], capture_output=True)
        print("Installed scheduled task 'contest-mcp-forward' (runs at logon).")
        return 0
    print(
        "Could not create a scheduled task automatically. Run this in a terminal "
        "and leave it open, or add it to startup:\n  " + cmd
    )
    return 1


def _uninstall_windows() -> int:
    subprocess.run(["schtasks", "/End", "/TN", "contest-mcp-forward"], capture_output=True)
    subprocess.run(["schtasks", "/Delete", "/TN", "contest-mcp-forward", "/F"], capture_output=True)
    print("Removed scheduled task 'contest-mcp-forward'.")
    return 0


def _done_message(listen_host: str, listen_port: int) -> None:
    print(
        "\nNext steps:\n"
        f"  1. In the contest-mcp connector settings, set N3FJP host to {listen_host} "
        f"(port {listen_port}).\n"
        "  2. Click Save, then fully quit and reopen Claude Desktop (Cmd-Q / Alt-F4).\n"
        "  3. Ask Claude for the N3FJP status to confirm.\n"
    )
    time.sleep(1.5)  # let the just-started service bind its port before probing
    print(f"Probe: {_probe(listen_host, listen_port)}")


# --- CLI ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="contest-mcp-forward",
        description=(
            "Bridge a sandboxed MCP connector (loopback-only) to N3FJP on another "
            "computer. Point the connector's N3FJP host at 127.0.0.1."
        ),
    )
    sub = parser.add_subparsers(dest="cmd")

    def add_common(p):
        p.add_argument("--to", required=True, metavar="HOST[:PORT]",
                       help="Remote N3FJP host (or host:port). Port defaults to 1100.")
        p.add_argument("--listen", default="127.0.0.1:1100", metavar="HOST:PORT",
                       help="Local address to listen on (default 127.0.0.1:1100).")

    p_run = sub.add_parser("run", help="Run in the foreground (Ctrl-C to stop).")
    add_common(p_run)
    p_run.add_argument("--timeout", type=float, default=6.0)

    p_inst = sub.add_parser(
        "install", help="Install + start a background service that survives reboot."
    )
    add_common(p_inst)

    sub.add_parser("uninstall", help="Stop and remove the background service.")

    p_stat = sub.add_parser("status", help="Show the service state and test the connection.")
    p_stat.add_argument("--listen", default="127.0.0.1:1100", metavar="HOST:PORT")

    args = parser.parse_args(argv)
    cmd = args.cmd or "run"

    if cmd in ("run", "install") and not getattr(args, "to", None):
        parser.error("--to is required")

    if cmd == "run":
        th, tp = _split_hostport(args.to, 1100)
        lh, lp = _split_hostport(args.listen, 1100)
        try:
            serve(lh, lp, th, tp, args.timeout)
        except KeyboardInterrupt:
            return 0
        except OSError as exc:
            print(f"contest-mcp-forward failed: {exc}", file=sys.stderr)
            return 1
        return 0

    if cmd == "install":
        th, tp = _split_hostport(args.to, 1100)
        lh, lp = _split_hostport(args.listen, 1100)
        target, listen = f"{th}:{tp}", f"{lh}:{lp}"
        rc = {
            "darwin": _install_macos,
            "linux": _install_linux,
            "win32": _install_windows,
        }.get(sys.platform, _install_linux)(target, listen)
        if rc == 0:
            _done_message(lh, lp)
        return rc

    if cmd == "uninstall":
        return {
            "darwin": _uninstall_macos,
            "linux": _uninstall_linux,
            "win32": _uninstall_windows,
        }.get(sys.platform, _uninstall_linux)()

    if cmd == "status":
        lh, lp = _split_hostport(args.listen, 1100)
        print(f"Forwarder listen target: {lh}:{lp}")
        print(_probe(lh, lp))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
