"""Unit tests for operation maps, the control catalog, coercion, and classification."""

from __future__ import annotations

import pytest

from contest_mcp import methods
from contest_mcp.methods import (
    UnknownOperation,
    control_id,
    fmt_bool,
    fmt_freq_hz,
    resolve,
)


def test_fmt_bool():
    assert fmt_bool(True) == "TRUE"
    assert fmt_bool(False) == "FALSE"
    assert fmt_bool("on") == "TRUE"
    assert fmt_bool("0") == "FALSE"
    assert fmt_bool("yes") == "TRUE"


def test_fmt_freq_hz_integer_string():
    assert fmt_freq_hz(14070000) == "14070000"
    assert fmt_freq_hz(14070000.4) == "14070000"
    assert fmt_freq_hz("7035000") == "7035000"


def test_resolve_known_and_unknown():
    assert resolve(methods.QUERY_OPS, "program") == ("PROGRAM", "PROGRAM")
    with pytest.raises(UnknownOperation):
        resolve(methods.QUERY_OPS, "nope")


def test_query_and_field_maps_well_formed():
    for opmap in (methods.QUERY_OPS, methods.FIELD_READ_OPS):
        for op, (command_id, expect) in opmap.items():
            assert isinstance(op, str) and op
            assert command_id.isupper()
            assert expect.isupper()


def test_control_id_writable_and_read_only():
    assert control_id("call", writable=True) == "TXTENTRYCALL"
    assert control_id("name", writable=True) == "TXTENTRYNAMER"
    assert control_id("grid", writable=True) == "TXTENTRYGRID"
    # Derived fields are readable but refused for writes.
    assert control_id("country_worked", writable=False) == "TXTENTRYCOUNTRYWORKED"
    with pytest.raises(ValueError, match="derived"):
        control_id("country_worked", writable=True)


def test_control_id_raw_passthrough_and_unknown():
    assert control_id("TXTENTRYOTHER1", writable=True) == "TXTENTRYOTHER1"
    with pytest.raises(ValueError, match="Unknown field"):
        control_id("definitely_not_a_field", writable=True)


def test_classification_disjoint_and_covering():
    # Read / write / destructive must not overlap.
    assert methods.READ_OPS.isdisjoint(methods.WRITE_OPS)
    assert methods.READ_OPS.isdisjoint(methods.DESTRUCTIVE_OPS)
    assert methods.WRITE_OPS.isdisjoint(methods.DESTRUCTIVE_OPS)
    # The destructive set is exactly the three guarded operations.
    assert methods.DESTRUCTIVE_OPS == {"add_direct", "delete", "sql"}


def test_action_ops_enter_expects_response():
    assert methods.ACTION_OPS["enter"] == ("ENTER", "ENTER")
    assert methods.ACTION_OPS["clear"][1] is None


def test_contest_fields_reference_known_fields():
    known = set(methods.SETTABLE_CONTROLS)
    for contest, fields in methods.CONTEST_FIELDS.items():
        for f in fields:
            assert f in known, f"{contest} references unknown field {f}"
