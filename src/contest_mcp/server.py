"""contest-mcp: an MCP server that logs amateur-radio QSOs to N3FJP software.

Tools are organised into logical **groups** (one permission each) rather than one
tool per command. Each group tool takes an ``operation`` argument, and every
documented capability is reachable either through a group or the ``n3fjp_call``
escape hatch (which also reaches commands added by newer N3FJP builds).

Permission model (set via tool annotations + a whole-database wipe gate):

* **Read** tools are marked ``readOnlyHint`` so clients can default them to
  *Always Allow*: ``status``, ``query``, ``fields``, ``search``.
* **Write** tools default to *Needs Approval*: ``log``, ``bandmode``,
  ``notifications``.
* Adding, editing, and deleting **individual** records (the ``database`` tool)
  are ordinary writes at the *Needs Approval* tier — same risk class as logging —
  so they can be globally allowed in the client for hands-off automation.
* Only operations that could wipe or overwrite the **entire** database (raw SQL
  ``DROP``/``TRUNCATE`` or an unscoped ``DELETE``/``UPDATE``) are hard-blocked,
  and only by the off-by-default ``N3FJP_ALLOW_DB_WIPE`` config switch —
  independent of, and stricter than, the client's approval prompts.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from contest_mcp import methods
from contest_mcp.client import N3fjp
from contest_mcp.config import Config
from contest_mcp.methods import NOT_FOUND_ID, control_id, fmt_bool, fmt_freq_hz, resolve
from contest_mcp.protocol import Block, build_cmd, is_db_wipe_sql

config = Config.from_env()
mcp = FastMCP("contest-mcp")
_n3fjp = N3fjp(config.host, config.port, timeout=config.timeout)

READ_ONLY = ToolAnnotations(readOnlyHint=True)


class DatabaseWipeBlocked(RuntimeError):
    """Raised when a whole-database operation is attempted with the switch off."""


# --- low-level helpers -------------------------------------------------------


def _fmt(blocks: list[Block]) -> list[dict]:
    """Render parsed blocks as plain dicts for the tool result."""
    return [{"id": b.id, **b.fields} for b in blocks]


def _check_supported(blocks: list[Block]) -> list[Block]:
    """Raise a clear error if N3FJP reported the command as unknown."""
    if any(b.id == NOT_FOUND_ID for b in blocks):
        raise ValueError(
            "N3FJP returned CMD_NOT_FOUND — this command is not supported by the "
            "connected program/version. Use `query` operation 'program' to see the "
            "API version, or reach newer commands via `n3fjp_call`."
        )
    return blocks


# CALLTAB triggers a synchronous CALLTABEVENT (call lookup + previous-contact /
# dupe info). It arrives a beat after the command, so give it a longer window.
CALLTAB_SETTLE = 1.0


def _send(raw: str, expect: str | None = None, settle: float = 0.4) -> list[Block]:
    return _check_supported(_n3fjp.command(raw, expect=expect, settle=settle))


def _qso_count() -> int | None:
    """Current QSO count as an int, or None if it can't be read."""
    blocks = _n3fjp.command(build_cmd("QSOCOUNT"), expect="QSOCOUNT")
    if not blocks:
        return None
    try:
        return int(blocks[0].value())
    except (TypeError, ValueError):
        return None


def _guard_db_wipe(statement: str) -> None:
    """Refuse a whole-database wipe/overwrite unless the operator enabled it."""
    if is_db_wipe_sql(statement) and not config.allow_db_wipe:
        raise DatabaseWipeBlocked(
            "REFUSED: this statement could delete or overwrite the ENTIRE log "
            "database. It is blocked because the N3FJP_ALLOW_DB_WIPE safety switch "
            "is OFF (the default). Adding, editing, or deleting individual records "
            "does not need that switch — only whole-database operations do. If you "
            "truly intend one, enable the switch in the server settings and back up "
            "your log first."
        )


# --- status (read) -----------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
def status() -> dict:
    """Snapshot: program, version, API version, QSO count, band/mode/frequency, log path.

    A quick health check that also confirms the connection and which N3FJP
    program/contest is loaded.
    """
    prog = _send(build_cmd("PROGRAM"), expect="PROGRAM")
    bmf = _send(build_cmd("READBMF"), expect="READBMF")
    count = _send(build_cmd("QSOCOUNT"), expect="QSOCOUNT")
    p = prog[0].fields if prog else {}
    b = bmf[0].fields if bmf else {}
    return {
        "connected": True,
        "host": _n3fjp.url,
        "program": p.get("PGM"),
        "version": p.get("VER"),
        "api_version": p.get("APIVER"),
        "qso_count": count[0].value() if count else None,
        "band": b.get("BAND"),
        "mode": b.get("MODE"),
        "mode_contest": b.get("MODETEST"),
        "frequency": b.get("FREQ"),
        "db_wipe_enabled": config.allow_db_wipe,
    }


# --- query (read) ------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
def query(operation: str) -> dict:
    """Read-only program queries.

    operations: program (name/version/API version), qso_count, next_serial,
    log_path, settings_path, shared_path, qso_rate (contest stats),
    band_mode_freq (current band/mode/frequency).
    """
    command_id, expect = resolve(methods.QUERY_OPS, operation)
    blocks = _send(build_cmd(command_id), expect=expect)
    result = _fmt(blocks)
    return {"operation": operation, "result": result[0] if len(result) == 1 else result}


# --- fields (read) -----------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
def fields(operation: str, field: str | None = None) -> dict:
    """Read entry-box (text field) values.

    operations:
      - read (field=name): read one box. `field` may be a friendly name (call,
        rst_rcvd, class, section, name, …) or a raw control id (TXTENTRY…).
      - visible: every field the current contest shows, with values.
      - all: every field (regardless of visibility), with values.

    Derived fields (country_worked, cq_zone, itu_zone, continent, prefix) are
    readable here but are computed by N3FJP from the call — never write them.
    """
    if operation == "read":
        if not field:
            raise ValueError("read requires a field name.")
        control = control_id(field, writable=False)
        blocks = _send(build_cmd("READ", {"CONTROL": control}), expect="READ")
        value = blocks[0].value() if blocks else None
        return {"operation": "read", "field": field, "control": control, "value": value}
    command_id, expect = resolve(methods.FIELD_READ_OPS, operation)
    blocks = _send(build_cmd(command_id), expect=expect)
    return {
        "operation": operation,
        "fields": {b.fields.get("CONTROL", ""): b.value() for b in blocks if "CONTROL" in b.fields},
    }


# --- log (write) -------------------------------------------------------------


def _set_field(friendly: str, value: str) -> str:
    control = control_id(friendly, writable=True)
    _n3fjp.command(build_cmd("UPDATE", {"CONTROL": control, "VALUE": value}), settle=0.05)
    return control


@mcp.tool()
def log(
    operation: str,
    field: str | None = None,
    value: str | None = None,
    fields: dict[str, str] | None = None,
    call: str | None = None,
    contest: str | None = None,
    exchange: dict[str, str] | None = None,
    calltab: bool = True,
) -> dict:
    """Logbook entry: set fields, run Call-tab, and ENTER a QSO. The headline tool.

    operations:
      - log_qso: the automatic-logging flow. Provide `call` (and usually
        `exchange`, a dict of friendly field names → values, e.g.
        {"class": "2A", "section": "CT"}). Sets the call, runs CALLTAB (dupe
        check + lookups) unless calltab=false, sets the exchange, then ENTER.
        Returns the number of records added and any dupe response.
      - set (field, value): write one entry box.
      - set_many (fields={...}): write several entry boxes.
      - calltab: run CALLTAB (after setting the call).
      - enter: log the current form (returns records added).
      - clear: clear the entry form.
      - focus (field): move focus to a box (e.g. to auto-fill default RST).

    Tip: `contest` (e.g. "field_day", "cq_wpx") lets the tool warn if the
    exchange is missing a field that contest needs.
    """
    if operation == "log_qso":
        return _log_qso(call, contest, exchange, calltab)
    if operation == "set":
        if not field or value is None:
            raise ValueError("set requires field and value.")
        return {"operation": "set", "control": _set_field(field, value), "value": value}
    if operation == "set_many":
        if not fields:
            raise ValueError("set_many requires fields={...}.")
        written = {name: _set_field(name, val) for name, val in fields.items()}
        return {"operation": "set_many", "controls": written}
    if operation == "focus":
        if not field:
            raise ValueError("focus requires a field.")
        control = control_id(field, writable=True)
        _n3fjp.command(build_cmd("SETFOCUS", {"CONTROL": control}), settle=0.05)
        return {"operation": "focus", "control": control}
    if operation in methods.ACTION_OPS:
        action, expect = methods.ACTION_OPS[operation]
        settle = CALLTAB_SETTLE if action == "CALLTAB" else 0.4
        blocks = _send(build_cmd("ACTION", {"VALUE": action}), expect=expect, settle=settle)
        events = _fmt(_n3fjp.drain_notifications())
        out = {"operation": operation, "result": _fmt(blocks) or None}
        if operation == "enter" and blocks:
            out["records_added"] = blocks[0].value()
        if events:
            out["events"] = events
        return out
    raise ValueError(
        "operation must be one of: log_qso, set, set_many, calltab, enter, clear, focus"
    )


def _log_qso(
    call: str | None,
    contest: str | None,
    exchange: dict[str, str] | None,
    calltab: bool,
) -> dict:
    if not call:
        raise ValueError("log_qso requires a call.")
    exchange = exchange or {}
    out: dict[str, Any] = {"operation": "log_qso", "call": call}

    if contest:
        needed = methods.CONTEST_FIELDS.get(contest.lower())
        if needed:
            missing = [f for f in needed if f not in exchange]
            if missing:
                out["warning"] = (
                    f"Contest '{contest}' usually needs: {', '.join(needed)}. "
                    f"Missing from exchange: {', '.join(missing)}."
                )

    _set_field("call", call)
    if calltab:
        ct = _send(build_cmd("ACTION", {"VALUE": "CALLTAB"}), settle=CALLTAB_SETTLE)
        ct += _n3fjp.drain_notifications()
        # CALLTABEVENT carries the call lookup (country/zones/bearing/distance);
        # a CALLTABDUPEEVENT (or non-empty DUPECHECKRESPONSE) flags a duplicate.
        event = next((b for b in ct if b.id == "CALLTABEVENT"), None)
        if event:
            out["lookup"] = {
                k: event.fields[k]
                for k in ("COUNTRY", "DXCC", "CONT", "CQZ", "ITUZ", "PFX", "BEARING", "DISTANCE")
                if k in event.fields
            }
        dupe_blocks = [b for b in ct if "DUPE" in b.id and b.value("VALUE")]
        if dupe_blocks:
            out["dupe"] = _fmt(dupe_blocks)
    for name, val in exchange.items():
        _set_field(name, val)

    before = _qso_count()
    entered = _send(build_cmd("ACTION", {"VALUE": "ENTER"}), expect="ENTER")
    after = _qso_count()
    reported = entered[0].value() if entered else None
    out["records_added"] = reported
    out["qso_count"] = after
    # ENTERRESPONSE can report 0 even on success when N3FJP runs in networked
    # (master-table) mode, where the commit is asynchronous. Confirm via the
    # QSO-count delta when we can read it; fall back to the reported value.
    if before is not None and after is not None:
        out["logged"] = after > before
    else:
        out["logged"] = reported not in (None, "0", "")
    return out


# --- bandmode (write) --------------------------------------------------------


@mcp.tool()
def bandmode(operation: str, value: Any = None, suppress_mode_default: bool = False) -> dict:
    """Change band, mode, and frequency before logging.

    operations:
      - change_freq (value=Hz): set the frequency (and thus band) via the rig
        interface. Use suppress_mode_default=true to keep the current mode rather
        than letting CW/phone segments flip it.
      - set_band (value=band, e.g. "20"): write the band box (rig interface OFF only).
      - set_mode (value=mode, e.g. "DIG"): write the mode box (rig interface OFF only).
      - ignore_rig_polls (value=bool): pause rig polling so band/mode boxes can be
        written while a rig is connected. Remember to set it back to false.

    Always make sure the program is on the correct band and mode before ENTER.
    """
    if operation == "change_freq":
        if value is None:
            raise ValueError("change_freq requires value (Hz).")
        cmd_fields: dict[str, object] = {"FREQ": fmt_freq_hz(value)}
        if suppress_mode_default:
            cmd_fields["SUPPRESSMODEDEFAULT"] = "TRUE"
        blocks = _send(build_cmd("CHANGEFREQ", cmd_fields), expect="CHANGEFREQ")
        return {"operation": operation, "result": _fmt(blocks) or None}
    if operation == "set_band":
        return {"operation": operation, "control": _set_field("band", str(value))}
    if operation == "set_mode":
        return {"operation": operation, "control": _set_field("mode", str(value))}
    if operation == "ignore_rig_polls":
        _n3fjp.command(build_cmd("IGNORERIGPOLLS", {"VALUE": fmt_bool(value)}), settle=0.05)
        return {"operation": operation, "value": fmt_bool(value)}
    raise ValueError("operation must be one of: change_freq, set_band, set_mode, ignore_rig_polls")


# --- search (read) -----------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
def search(
    operation: str,
    call: str | None = None,
    band: str | None = None,
    mode: str | None = None,
    dxcc: str | None = None,
    country: str | None = None,
    confirmed: bool | None = None,
    include_all: bool = False,
    max_records: int | None = None,
    count: int | None = None,
) -> dict:
    """Search and list the log (read-only).

    operations:
      - list (count, include_all): the most recent QSOs (primary fields, or every
        field with include_all=true).
      - search (call/band/mode/dxcc/country/confirmed, include_all, max_records):
        find matching QSOs. Prefer dxcc (ADIF number) over country (must match
        N3FJP's spelling exactly). mode is normalized to CW/PH/DIG.
      - dupecheck (call): is this call a dupe? Returns previous-contact detail or
        empty if new. (No side effects, unlike the log tool's calltab.)
      - entity (call, band, mode): all-time-new/worked/confirmed status.
    """
    if operation == "list":
        flags = ["INCLUDEALL"] if include_all else None
        fields = {"VALUE": count} if count else None
        blocks = _send(build_cmd("LIST", fields, flags), expect="LIST")
        return {"operation": "list", "records": _fmt(blocks)}
    if operation == "search":
        crit: dict[str, object] = {}
        if call:
            crit["CALL"] = call
        if band:
            crit["BAND"] = band
        if mode:
            crit["MODE"] = mode
        if dxcc:
            crit["DXCC"] = dxcc
        if country:
            crit["COUNTRYWORKED"] = country
        if confirmed is not None:
            crit["CONFIRMED"] = fmt_bool(confirmed)
        if max_records:
            crit["MAXRECORDS"] = max_records
        flags = ["INCLUDEALL"] if include_all else None
        blocks = _send(build_cmd("SEARCH", crit, flags), expect="SEARCH")
        return {"operation": "search", "records": _fmt(blocks)}
    if operation == "dupecheck":
        if not call:
            raise ValueError("dupecheck requires a call.")
        blocks = _send(build_cmd("DUPECHECK", {"CALL": call}), expect="DUPECHECK")
        detail = blocks[0].value() if blocks else None
        return {"operation": "dupecheck", "call": call, "is_dupe": bool(detail), "detail": detail}
    if operation == "entity":
        if not call:
            raise ValueError("entity requires a call.")
        crit = {"CALL": call}
        if band:
            crit["BAND"] = band
        if mode:
            crit["MODE"] = mode
        # Entity-status command tag not yet confirmed against API 2.2; reachable
        # via n3fjp_call. Surface a clear note rather than a silent empty result.
        blocks = _n3fjp.command(build_cmd("CHECKENTITY", crit), expect="CHECKENTITY")
        if not blocks or any(b.id == NOT_FOUND_ID for b in blocks):
            return {
                "operation": "entity",
                "supported": False,
                "note": "Entity-status command not confirmed on this build; try n3fjp_call.",
            }
        return {"operation": "entity", "result": _fmt(blocks)}
    raise ValueError("operation must be one of: list, search, dupecheck, entity")


# --- database (destructive) --------------------------------------------------


@mcp.tool()
def database(
    operation: str,
    fields: dict[str, str] | None = None,
    exclude_dupes: bool = False,
    where: str | None = None,
    sql: str | None = None,
) -> dict:
    """Direct database operations on individual records.

    These are ordinary writes (the *Needs Approval* tier — same as logging), so
    they can be globally allowed in the client for automation. The ONLY hard
    block is a whole-database wipe/overwrite, gated by N3FJP_ALLOW_DB_WIPE.

    operations:
      - add_direct (fields={fldCall:..., fldBand:...}, exclude_dupes): insert a
        record directly, bypassing N3FJP's scoring. Prefer log's log_qso/ENTER.
      - delete (where="fldPrimaryID=123"): delete matching records. A missing or
        empty WHERE would clear the whole table and is refused unless
        N3FJP_ALLOW_DB_WIPE is on.
      - sql (sql="..."): run a raw SQL statement against the Access database.
        Only statements that could wipe/overwrite the whole database (DROP,
        TRUNCATE, unscoped DELETE/UPDATE) are refused unless N3FJP_ALLOW_DB_WIPE
        is on; scoped statements run normally.
      - checklog / openlog: ask N3FJP to reload new / all records.
      - sqlclose: close the SQL connection.
    """
    if operation in ("checklog", "openlog", "sqlclose"):
        cmd = {"checklog": "CHECKLOG", "openlog": "OPENLOG", "sqlclose": "SQLCLOSE"}[operation]
        _n3fjp.command(build_cmd(cmd), settle=0.1)
        return {"operation": operation, "ok": True}

    if operation == "add_direct":
        if not fields:
            raise ValueError("add_direct requires fields={fldCall:..., ...}.")
        body: dict[str, object] = {}
        if exclude_dupes:
            body["EXCLUDEDUPES"] = "TRUE"
        body["STAYOPEN"] = "FALSE"
        body.update(fields)
        blocks = _send(build_cmd("ADDDIRECT", body), expect="ADDDIRECT")
        _n3fjp.command(build_cmd("CHECKLOG"), settle=0.1)
        return {"operation": "add_direct", "result": _fmt(blocks) or None}

    if operation in ("delete", "sql"):
        statement = sql if operation == "sql" else _build_delete(where)
        _guard_db_wipe(statement)
        blocks = _n3fjp.command(build_cmd("SENDSQL", {"VALUE": statement}), settle=0.3)
        _n3fjp.command(build_cmd("SQLCLOSE"), settle=0.05)
        _n3fjp.command(build_cmd("OPENLOG"), settle=0.1)
        return {"operation": operation, "statement": statement, "result": _fmt(blocks) or None}

    raise ValueError(
        "operation must be one of: add_direct, delete, sql, checklog, openlog, sqlclose"
    )


def _build_delete(where: str | None) -> str:
    where = (where or "").strip()
    if not where:
        return "DELETE FROM tblContacts"  # intentionally WHERE-less → wipe gate
    return f"DELETE FROM tblContacts WHERE {where}"


# --- notifications (write) ---------------------------------------------------


@mcp.tool()
def notifications(operation: str) -> dict:
    """Opt-in push events from N3FJP (field updates, enter/calltab, dupes).

    operations:
      - enable: turn on all-field-update notifications.
      - disable: turn them off.
      - drain: return and clear the buffered notification blocks received so far.

    MCP is request/response, so events are buffered and you pull them with drain
    rather than receiving a live stream.
    """
    if operation == "enable":
        _n3fjp.command(build_cmd("ALLUPDATES", {"VALUE": "TRUE"}), settle=0.1)
        return {"operation": "enable", "notifications": "on"}
    if operation == "disable":
        _n3fjp.command(build_cmd("ALLUPDATES", {"VALUE": "FALSE"}), settle=0.1)
        return {"operation": "disable", "notifications": "off"}
    if operation == "drain":
        return {"operation": "drain", "events": _fmt(_n3fjp.drain_notifications())}
    raise ValueError("operation must be one of: enable, disable, drain")


# --- escape hatch ------------------------------------------------------------


@mcp.tool()
def n3fjp_call(command: str, expect: str | None = None) -> dict:
    """Escape hatch: send any raw N3FJP command and return the parsed reply.

    `command` may be a bare command id ("PROGRAM"), a full envelope
    ("<CMD><PROGRAM></CMD>"), or the inner form ("<PROGRAM>") — it is normalised
    and CRLF-terminated for you. `expect` is the response id to wait for.

    This reaches anything not surfaced by a group tool, including newer commands.
    Like the group tools, it runs at the *Needs Approval* tier; the only hard
    block is a raw SQL statement that could wipe/overwrite the whole database,
    which still requires the N3FJP_ALLOW_DB_WIPE switch.
    """
    raw = _normalise_raw(command)
    _guard_db_wipe(raw)
    blocks = _n3fjp.command(raw, expect=expect)
    return {"command": raw, "result": _fmt(blocks)}


def _normalise_raw(command: str) -> str:
    text = command.strip()
    if text.upper().startswith("<CMD>"):
        return text
    if text.startswith("<"):
        return f"<CMD>{text}</CMD>"
    return f"<CMD><{text.upper()}></CMD>"


def main() -> None:
    """Console-script entry point (wired up in pyproject.toml's [project.scripts])."""
    mcp.run()


if __name__ == "__main__":
    main()
