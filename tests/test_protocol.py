"""Unit tests for the pure wire-protocol helpers (no socket, no N3FJP)."""

from __future__ import annotations

from contest_mcp.protocol import (
    build_cmd,
    extract_blocks,
    is_db_wipe_sql,
    matches,
    parse_block,
)


def test_build_cmd_basic():
    assert build_cmd("PROGRAM") == "<CMD><PROGRAM></CMD>"
    assert (
        build_cmd("READ", {"CONTROL": "TXTENTRYCALL"})
        == "<CMD><READ><CONTROL>TXTENTRYCALL</CONTROL></CMD>"
    )
    assert (
        build_cmd("UPDATE", {"CONTROL": "TXTENTRYCALL", "VALUE": "W1AW"})
        == "<CMD><UPDATE><CONTROL>TXTENTRYCALL</CONTROL><VALUE>W1AW</VALUE></CMD>"
    )


def test_build_cmd_flags_before_fields():
    # LIST with INCLUDEALL flag then a VALUE field, in that order.
    assert (
        build_cmd("LIST", {"VALUE": 20}, ["INCLUDEALL"])
        == "<CMD><LIST><INCLUDEALL><VALUE>20</VALUE></CMD>"
    )


def test_build_cmd_empty_value_clears():
    assert (
        build_cmd("UPDATE", {"CONTROL": "TXTENTRYCALL", "VALUE": ""})
        == "<CMD><UPDATE><CONTROL>TXTENTRYCALL</CONTROL><VALUE></VALUE></CMD>"
    )


def test_extract_blocks_multiple_in_one_packet():
    buf = "<CMD><A><V>1</V></CMD><CMD><B><V>2</V></CMD><CMD><C"  # last is partial
    inners, remaining = extract_blocks(buf)
    assert inners == ["<A><V>1</V>", "<B><V>2</V>"]
    assert remaining == "<CMD><C"


def test_parse_block_id_and_fields():
    b = parse_block(
        "<PROGRAMRESPONSE><PGM>N3FJP Field Day</PGM><VER>6.6.10</VER><APIVER>2.2</APIVER>"
    )
    assert b.id == "PROGRAMRESPONSE"
    assert b.value("PGM") == "N3FJP Field Day"
    assert b.value("VER") == "6.6.10"
    assert b.value("APIVER") == "2.2"


def test_parse_block_numeric_tag_names():
    # QSORATERESPONSE uses tags that start with a digit (20MIN, 60MIN).
    b = parse_block("<QSORATERESPONSE><20MIN>3</20MIN><60MIN>1</60MIN>")
    assert b.id == "QSORATERESPONSE"
    assert b.value("20MIN") == "3"
    assert b.value("60MIN") == "1"


def test_parse_block_empty_value():
    b = parse_block("<READRESPONSE><CONTROL>TXTENTRYCALL</CONTROL><VALUE></VALUE>")
    assert b.id == "READRESPONSE"
    assert b.value("CONTROL") == "TXTENTRYCALL"
    assert b.value("VALUE") == ""


def test_matches_request_to_response():
    assert matches("PROGRAMRESPONSE", "PROGRAM")
    assert matches("ENTERRESPONSE", "ENTER")
    assert matches("READBMFRESPONSE", "READBMF")
    assert not matches("READBMFRESPONSE", "PROGRAM")


def test_is_db_wipe_sql():
    # Whole-database operations.
    assert is_db_wipe_sql("DELETE FROM tblContacts")
    assert is_db_wipe_sql("delete from tblcontacts")
    assert is_db_wipe_sql("DROP TABLE tblContacts")
    assert is_db_wipe_sql("TRUNCATE TABLE tblContacts")
    assert is_db_wipe_sql("UPDATE tblContacts SET fldBand='20'")  # no WHERE
    # Scoped, single-record operations are not wipes.
    assert not is_db_wipe_sql("DELETE FROM tblContacts WHERE fldPrimaryID=5")
    assert not is_db_wipe_sql("UPDATE tblContacts SET fldBand='20' WHERE fldPrimaryID=5")
    assert not is_db_wipe_sql("SELECT * FROM tblContacts")
