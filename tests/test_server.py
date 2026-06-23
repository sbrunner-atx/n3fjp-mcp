"""Tests for the server's dispatch and the safety model, using a fake client.

These exercise the permission/confirm logic and the headline logging flow without
a running N3FJP — the socket layer is replaced with a recorder.
"""

from __future__ import annotations

import pytest

from contest_mcp import server
from contest_mcp.protocol import Block, parse_block


class FakeN3fjp:
    """Stand-in for the socket client: records commands, returns canned blocks."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.canned: dict[str, list[Block]] = {}
        self._notifications: list[Block] = []
        self.url = "fake:1100"

    def command(self, raw, expect=None, settle=0.4, timeout=None):
        self.sent.append(raw)
        return self.canned.get(expect, [])

    def drain_notifications(self):
        items = self._notifications
        self._notifications = []
        return items


@pytest.fixture
def fake(monkeypatch):
    client = FakeN3fjp()
    monkeypatch.setattr(server, "_n3fjp", client)
    monkeypatch.setattr(server.config, "allow_db_wipe", False)
    return client


def test_status_reads_program_and_bmf(fake):
    fake.canned["PROGRAM"] = [
        parse_block("<PROGRAMRESPONSE><PGM>FD Log</PGM><VER>6.6.10</VER><APIVER>2.2</APIVER>")
    ]
    fake.canned["READBMF"] = [
        parse_block(
            "<READBMFRESPONSE><BAND>20</BAND><MODE>DIG</MODE>"
            "<MODETEST>DIG</MODETEST><FREQ>14070000</FREQ>"
        )
    ]
    fake.canned["QSOCOUNT"] = [parse_block("<QSOCOUNTRESPONSE><VALUE>7</VALUE>")]
    out = server.status()
    assert out["program"] == "FD Log"
    assert out["api_version"] == "2.2"
    assert out["band"] == "20"
    assert out["qso_count"] == "7"


def test_fields_read_friendly_name(fake):
    fake.canned["READ"] = [
        parse_block("<READRESPONSE><CONTROL>TXTENTRYCALL</CONTROL><VALUE>W1AW</VALUE>")
    ]
    out = server.fields("read", field="call")
    assert out["control"] == "TXTENTRYCALL"
    assert out["value"] == "W1AW"
    assert "<READ><CONTROL>TXTENTRYCALL</CONTROL>" in fake.sent[-1]


def test_log_set_refuses_derived_field(fake):
    with pytest.raises(ValueError, match="derived"):
        server.log("set", field="country_worked", value="USA")


def test_log_qso_flow(fake):
    fake.canned["ENTER"] = [parse_block("<ENTERRESPONSE><VALUE>1</VALUE>")]
    out = server.log(
        "log_qso",
        call="W1AW",
        contest="field_day",
        exchange={"class": "2A", "section": "CT"},
    )
    assert out["records_added"] == "1"
    assert out["logged"] is True
    # Call was set, CALLTAB fired, exchange set, ENTER sent — in order.
    joined = " ".join(fake.sent)
    assert "TXTENTRYCALL</CONTROL><VALUE>W1AW" in joined
    assert "<ACTION><VALUE>CALLTAB</VALUE>" in joined
    assert "TXTENTRYCLASS</CONTROL><VALUE>2A" in joined
    assert "<ACTION><VALUE>ENTER</VALUE>" in joined


def test_log_qso_logged_via_count_delta(fake):
    # Networked/master-table mode: ENTER reports 0 even though it logged. The
    # tool must confirm success via the QSO-count delta instead.
    fake.canned["ENTER"] = [parse_block("<ENTERRESPONSE><VALUE>0</VALUE>")]
    counts = iter(["3", "4"])  # before, after

    def cmd(raw, expect=None, settle=0.4, timeout=None):
        fake.sent.append(raw)
        if expect == "QSOCOUNT":
            return [parse_block(f"<QSOCOUNTRESPONSE><VALUE>{next(counts)}</VALUE>")]
        return fake.canned.get(expect, [])

    fake.command = cmd
    out = server.log("log_qso", call="W1AW")
    assert out["records_added"] == "0"
    assert out["qso_count"] == 4
    assert out["logged"] is True


def test_log_qso_warns_on_missing_exchange(fake):
    fake.canned["ENTER"] = [parse_block("<ENTERRESPONSE><VALUE>1</VALUE>")]
    out = server.log("log_qso", call="W1AW", contest="field_day", exchange={"class": "2A"})
    assert "warning" in out and "section" in out["warning"]


def test_database_delete_requires_confirm(fake):
    with pytest.raises(server.ConfirmationRequired):
        server.database("delete", where="fldPrimaryID=5")


def test_database_scoped_delete_runs_with_confirm(fake):
    out = server.database("delete", where="fldPrimaryID=5", confirm=True)
    assert "WHERE fldPrimaryID=5" in out["statement"]
    assert any("SENDSQL" in s for s in fake.sent)


def test_database_wipe_blocked_when_switch_off(fake):
    with pytest.raises(server.DatabaseWipeBlocked):
        server.database("sql", sql="DELETE FROM tblContacts", confirm=True)


def test_database_wipe_allowed_when_switch_on(fake, monkeypatch):
    monkeypatch.setattr(server.config, "allow_db_wipe", True)
    out = server.database("sql", sql="DELETE FROM tblContacts", confirm=True)
    assert out["statement"] == "DELETE FROM tblContacts"


def test_database_empty_delete_is_wipe_gated(fake):
    # A delete with no WHERE would clear the table -> blocked even with confirm.
    with pytest.raises(server.DatabaseWipeBlocked):
        server.database("delete", where="", confirm=True)


def test_n3fjp_call_read_only_no_confirm(fake):
    fake.canned[None] = [parse_block("<PROGRAMRESPONSE><PGM>FD</PGM>")]
    out = server.n3fjp_call("PROGRAM")
    assert out["command"] == "<CMD><PROGRAM></CMD>"


def test_n3fjp_call_write_requires_confirm(fake):
    with pytest.raises(server.ConfirmationRequired):
        server.n3fjp_call("<ACTION><VALUE>CLEAR</VALUE>")


def test_n3fjp_call_normalises_forms(fake):
    assert server._normalise_raw("PROGRAM") == "<CMD><PROGRAM></CMD>"
    assert server._normalise_raw("<PROGRAM>") == "<CMD><PROGRAM></CMD>"
    assert server._normalise_raw("<CMD><PROGRAM></CMD>") == "<CMD><PROGRAM></CMD>"


def test_bandmode_change_freq_coerces_hz(fake):
    fake.canned["CHANGEFREQ"] = [parse_block("<CHANGEFREQRESPONSE><FREQ>14070000</FREQ>")]
    server.bandmode("change_freq", value=14070000.2)
    assert "<FREQ>14070000</FREQ>" in fake.sent[-1]
