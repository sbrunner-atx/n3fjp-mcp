"""Operation maps, the control-name catalog, contest presets, and coercion.

Kept as plain data (separate from ``server.py``) so the whole mapping — and the
read/write/destructive classification that drives the permission model — is
unit-testable without the MCP SDK or a running N3FJP.

The control names, query tags, and response IDs here were verified live against
a real instance (N3FJP ARRL Field Day Log, API version 2.2). Where the public
0.9 documentation disagreed with the live API, the live values win and the
differences are noted in ``docs/N3FJP-API-SPEC.md``.
"""

from __future__ import annotations

_TRUE = {"1", "true", "yes", "on"}

# N3FJP answers an unrecognised command with this block ID — a handy way to tell
# "command not supported by this build" apart from "no response".
NOT_FOUND_ID = "CMD_NOT_FOUND"


class UnknownOperation(ValueError):
    """Raised when a group tool is given an operation it does not support."""


# --- value coercion ----------------------------------------------------------


def fmt_bool(value) -> str:
    """Coerce a truthy/falsey value to N3FJP's ``TRUE`` / ``FALSE``."""
    if isinstance(value, str):
        return "TRUE" if value.strip().lower() in _TRUE else "FALSE"
    return "TRUE" if bool(value) else "FALSE"


def fmt_freq_hz(value) -> str:
    """Coerce a frequency to an integer-Hz string (N3FJP wants whole Hz)."""
    return str(int(round(float(value))))


# --- read-only query operations (no arguments) -------------------------------
# operation -> (command_id, expect_response_id). All verified live.

QUERY_OPS: dict[str, tuple[str, str]] = {
    "program": ("PROGRAM", "PROGRAM"),  # -> PGM, VER, APIVER
    "qso_count": ("QSOCOUNT", "QSOCOUNT"),
    "next_serial": ("NEXTSERIALNUMBER", "NEXTSERIALNUMBER"),
    "log_path": ("FILEPATH", "FILEPATH"),
    "settings_path": ("SETTINGSPATH", "SETTINGSPATH"),
    "shared_path": ("SETTINGSPATHSHARED", "SETTINGSPATHSHARED"),
    "qso_rate": ("QSORATE", "QSORATE"),  # -> TOTSCORE, TOTQSOS, 20MIN, 60MIN, L*/V*
    "band_mode_freq": ("READBMF", "READBMF"),  # -> BAND, MODE, MODETEST, FREQ
}

# --- field (text box) reads --------------------------------------------------
# Each returns one RESPONSE block per field: <...><CONTROL>..</CONTROL><VALUE>..</VALUE>

FIELD_READ_OPS: dict[str, tuple[str, str]] = {
    "visible": ("VISIBLEFIELDS", "VISIBLEFIELDS"),
    "all": ("ALLFIELDS", "ALLFIELDS"),
}

# --- action commands ---------------------------------------------------------
# operation -> (action_value, expect_response_id_or_None)

ACTION_OPS: dict[str, tuple[str, str | None]] = {
    "calltab": ("CALLTAB", None),
    "enter": ("ENTER", "ENTER"),
    "clear": ("CLEAR", None),
    "dupecheck_action": ("DUPECHECK", None),
}

# --- entry-box control catalog (verified via live ALLFIELDS) -----------------
# friendly name -> N3FJP CONTROL id. Writable AND readable.

SETTABLE_CONTROLS: dict[str, str] = {
    "call": "TXTENTRYCALL",
    "rst_rcvd": "TXTENTRYRSTR",
    "rst_sent": "TXTENTRYRSTS",
    "class": "TXTENTRYCLASS",
    "section": "TXTENTRYSECTION",
    "spc_num": "TXTENTRYSPCNUM",
    "name": "TXTENTRYNAMER",
    "check": "TXTENTRYCHECK",
    "serial_rcvd": "TXTENTRYSERIALNOR",
    "serial_sent": "TXTENTRYSERIALNOS",
    "grid": "TXTENTRYGRID",
    "state": "TXTENTRYSTATE",
    "county": "TXTENTRYCOUNTYR",
    "category": "TXTENTRYCATEGORY",
    "age": "TXTENTRYAGE",
    "ten_ten": "TXTENTRY1010",
    "comments": "TXTENTRYCOMMENTS",
    "power": "TXTENTRYPOWER",
    "band": "TXTENTRYBAND",  # only when rig interface is OFF (see bandmode tool)
    "mode": "TXTENTRYMODE",  # only when rig interface is OFF
    "frequency": "TXTENTRYFREQUENCY",
    "dialogue": "LBLDIALOGUE",
}

# Readable but NOT writable — N3FJP derives these from the call sign. Writing
# them corrupts country/zone/multiplier accounting, so the tool refuses.
DERIVED_CONTROLS: dict[str, str] = {
    "country_worked": "TXTENTRYCOUNTRYWORKED",
    "cq_zone": "TXTENTRYCQZONE",
    "itu_zone": "TXTENTRYITUZ",
    "iaru_zone": "TXTENTRYIARUZONE",
    "continent": "TXTENTRYCONTINENT",
    "prefix": "TXTENTRYPREFIX",
}

READABLE_CONTROLS: dict[str, str] = {**SETTABLE_CONTROLS, **DERIVED_CONTROLS}

# --- per-contest exchange presets -------------------------------------------
# The exchange (beyond Call) each digital-capable contest needs. Lets the `log`
# tool prompt for / validate the right fields per contest. Field names are the
# friendly keys above.

CONTEST_FIELDS: dict[str, list[str]] = {
    "field_day": ["class", "section"],
    "winter_field_day": ["category", "section"],
    "cq_wpx": ["rst_sent", "serial_rcvd"],
    "cq_ww_rtty": ["rst_sent", "state"],  # CQ Zone auto from call
    "naqp": ["name", "spc_num"],
    "na_sprint": ["serial_rcvd", "name", "spc_num"],
    "rtty_roundup": ["rst_sent", "spc_num"],
    "school_club_roundup": ["rst_sent", "class", "spc_num", "name"],
    "kids_day": ["name", "age", "spc_num"],
    "rookie_roundup": ["name", "check", "spc_num"],
    "africa_all_mode": ["rst_sent", "serial_rcvd"],
    "ari_intl_dx": ["rst_sent", "spc_num"],
    "ten_ten": ["name", "spc_num", "ten_ten"],
    "vhf": ["grid", "rst_rcvd"],
    "worked_all_europe": ["rst_sent", "serial_rcvd"],
    "state_qso_party": ["name", "spc_num"],
}

# --- classification (drives the permission model & tests) --------------------

# Operations that are purely informational (Always Allow at the client).
READ_OPS: frozenset[str] = frozenset(
    {*QUERY_OPS, *FIELD_READ_OPS, "read", "list", "search", "dupecheck", "entity"}
)

# Write operations (Needs Approval by default).
WRITE_OPS: frozenset[str] = frozenset(
    {
        "set",
        "set_many",
        "focus",
        "calltab",
        "enter",
        "clear",
        "dupecheck_action",
        "change_freq",
        "set_band",
        "set_mode",
        "ignore_rig_polls",
        "checklog",
        "openlog",
        "sqlclose",
        "enable",
        "disable",
        "drain",
    }
)

# Direct-database operations. These are ordinary writes (Needs Approval, no
# in-band confirm); only a *whole-database* wipe is hard-blocked, by the
# N3FJP_ALLOW_DB_WIPE switch enforced in server.py.
DESTRUCTIVE_OPS: frozenset[str] = frozenset({"add_direct", "delete", "sql"})


def resolve(opmap: dict, operation: str):
    """Return the spec for ``operation`` in ``opmap``, or raise UnknownOperation."""
    spec = opmap.get(operation)
    if spec is None:
        valid = ", ".join(sorted(opmap))
        raise UnknownOperation(f"Unknown operation '{operation}'. Valid operations: {valid}")
    return spec


def control_id(name: str, *, writable: bool) -> str:
    """Map a friendly field name (or a raw TXTENTRY… id) to a CONTROL id.

    ``writable=True`` refuses the derived/read-only controls.
    """
    key = name.strip().lower()
    if writable:
        if key in SETTABLE_CONTROLS:
            return SETTABLE_CONTROLS[key]
        if key in DERIVED_CONTROLS:
            raise ValueError(
                f"Field '{name}' is derived by N3FJP from the call sign and must not "
                f"be written. Set the call instead and let N3FJP fill it."
            )
    else:
        if key in READABLE_CONTROLS:
            return READABLE_CONTROLS[key]
    # Allow a raw control id (e.g. a box this catalog doesn't list yet).
    if name.upper().startswith(("TXTENTRY", "LBL")):
        return name.upper()
    catalog = SETTABLE_CONTROLS if writable else READABLE_CONTROLS
    raise ValueError(f"Unknown field '{name}'. Known fields: {', '.join(sorted(catalog))}")
