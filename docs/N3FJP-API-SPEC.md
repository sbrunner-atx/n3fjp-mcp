# N3FJP API — Machine-Readable Spec (for contest-mcp)

This is the structured command catalog that the `contest-mcp` code is generated
from. It is deliberately terse and unambiguous. The prose companion is
[`N3FJP-API.md`](N3FJP-API.md).

Source of truth: <https://www.n3fjp.com/help/api.html> (API version 0.9),
cross-checked against working community clients (e.g. `dslotter/wsjtx_to_n3fjp`).

## Transport

> **Verified live** against *N3FJP's ARRL Field Day Contest Log* v6.6.10,
> **API version 2.2**, on 2026-06-23. Corrections from the public 0.9 doc are
> folded in below and flagged **[live]**. See the "Live verification" section at
> the end for the full diff.

| Property | Value |
| --- | --- |
| Protocol | TCP (N3FJP is the **server**, your app is the client) |
| Default port | `1100` (configurable). **[live]** Port `1000` is a *different* N3FJP feature — the multi-PC networking/"server" port — and does **not** speak the API |
| Framing | Each command terminated with **CRLF** (`\r\n`) |
| Disconnect | Send a lone `\r\n`, or close the socket |
| Encoding | ASCII/UTF-8 text |
| Envelope | `<CMD> ... </CMD>` — command/response ID first, then nested XML tags |
| Casing | Command IDs UPPERCASE; tag matching is case-insensitive in N3FJP's parser |
| Multiplexing | One packet may contain **several** `<CMD>…</CMD>` blocks; parse by scanning for `<CMD>` … `</CMD>` |
| Push events | After opt-in, unsolicited notification blocks interleave with responses |

The client must therefore: read continuously, split on `</CMD>`, and route each
block either to a pending request (matched by response ID) or to a notification
buffer.

## Confidence legend

- **C** = Confirmed (literal request/response seen in official doc text and/or a
  working client).
- **D** = Documented (described in the official doc; exact tag spelling derived
  from the doc's stated conventions).
- **I** = Inferred (capability documented but literal tag not shown in the
  fetched text; verify live, reach via the escape hatch until confirmed).

## Kind / safety classification

- **read** — no state change. Default harness permission: **Always Allow**
  (`readOnlyHint: true`).
- **write** — mutates N3FJP state or the log. Default: **Needs Approval**.
- **destructive** — deletes/overwrites individual records or keys a
  transmitter. Default: **Needs Approval** *and* requires `confirm=true` in the
  tool call.
- **db-wipe** — can delete or overwrite the **entire** log database (raw SQL
  `DELETE`/`DROP`/`UPDATE`-without-WHERE). Refused unless the operator sets the
  `N3FJP_ALLOW_DB_WIPE` config switch (default **off**); independent of the
  harness permission tiers.

---

## 1. Text entry boxes — read / write / focus

Generic envelope (CONTROL = a text box name from §8):

| Op | Request | Response | Kind | Conf |
| --- | --- | --- | --- | --- |
| read field | `<CMD><READ><CONTROL>{CONTROL}</CONTROL></CMD>` | `<CMD><READRESPONSE><CONTROL>{CONTROL}</CONTROL><VALUE>{v}</VALUE></CMD>` | read | C |
| write field | `<CMD><UPDATE><CONTROL>{CONTROL}</CONTROL><VALUE>{v}</VALUE></CMD>` | none | write | C |
| clear field | `<CMD><UPDATE><CONTROL>{CONTROL}</CONTROL><VALUE></VALUE></CMD>` | none | write | C |
| set focus | `<CMD><SETFOCUS><CONTROL>{CONTROL}</CONTROL></CMD>` | none | write | D |

Notes: never write `TXTENTRYCOUNTRYWORKED` or zones — N3FJP derives them from the
call. Band/mode boxes are writable but the **wrong** way to change band/mode (see §4).

## 2. Action commands

Envelope: `<CMD><ACTION><VALUE>{ACTION}</VALUE></CMD>`. Wait ≥5 ms after an action
before the next command.

| Op | ACTION | Response | Kind | Conf |
| --- | --- | --- | --- | --- |
| log QSO | `ENTER` | `<CMD><ENTERRESPONSE><VALUE>{n_added}</VALUE></CMD>` (1 = added, 0 = not) | write | C/D |
| clear form | `CLEAR` | none | write | C |
| call-tab | `CALLTAB` | fires dupe-check + previous-contact lookups; may emit `CALLTABDUPEEVENT` | write | C |
| dupe action | `DUPECHECK` | contest-software dupe action + events | write | D |

The **headline logging flow**: `UPDATE TXTENTRYCALL` → `ACTION CALLTAB` → set
exchange fields → ensure band/mode (§4) → `ACTION ENTER` → read `ENTERRESPONSE`.

## 3. Dupe check (query, non-action)

| Op | Request | Response | Kind | Conf |
| --- | --- | --- | --- | --- |
| dupe query | `<CMD><DUPECHECK><CALL>{call}</CALL></CMD>` | `<CMD><DUPECHECKRESPONSE><CALL>{call}</CALL><VALUE>{detail or empty}</VALUE></CMD>` | read | C |

Contest software only. Empty `VALUE` ⇒ not a dupe. State QSO-party programs return
nothing here; use `ACTION DUPECHECK` or watch `CALLTABDUPEEVENT`.

## 4. Band / mode / frequency

| Op | Request | Response | Kind | Conf |
| --- | --- | --- | --- | --- |
| read B/M/F | `<CMD><READBMF></CMD>` | `<CMD><READBMFRESPONSE><BAND>{b}</BAND><MODE>{m}</MODE><MODETEST>{CW\|PH\|DIG}</MODETEST><FREQ>{hz}</FREQ></CMD>` | read | D |
| change freq | `<CMD><CHANGEFREQ><FREQ>{hz}</FREQ></CMD>` | `<CMD><CHANGEFREQRESPONSE>…</CMD>` | write | C |
| change freq (no mode default) | `<CMD><CHANGEFREQ><FREQ>{hz}</FREQ><SUPPRESSMODEDEFAULT>TRUE</SUPPRESSMODEDEFAULT></CMD>` | `CHANGEFREQRESPONSE` | write | D |
| rig-iface enabled? | `<CMD><RADIOAPPCOMMASEPCONTROL></CMD>` *(tag uncertain)* | rig name, or `None` | read | I |
| set mode (rig) | mode command then `CHANGEFREQ` w/ `SUPPRESSMODEDEFAULT` | — | write | I |
| ignore rig polls | `<CMD><IGNORERIGPOLLS><VALUE>TRUE\|FALSE</VALUE></CMD>` | none | write | D |

`MODETEST` is always `CW`, `PH`, or `DIG` (used for dupe checking). **Set the
correct band/mode before `ENTER`.** With rig interface enabled, change band/mode
via `CHANGEFREQ`/mode commands, not by writing the band/mode boxes.

## 5. Queries (read-only)

| Op | Request | Response | Conf |
| --- | --- | --- | --- |
| program + version | `<CMD><PROGRAM></CMD>` | `<CMD><PROGRAMRESPONSE><PGM>{name}</PGM><VERSION>{v}</VERSION></CMD>` | D |
| API version | `<CMD><APIVERSION></CMD>` | `<CMD><APIVERSIONRESPONSE><VALUE>{v}</VALUE></CMD>` | D |
| QSO count | `<CMD><CHECKLOG></CMD>` then read count *(count tag uncertain)* | — | I |
| next serial | `<CMD><NEXTSERIALNUMBER></CMD>` | `<CMD><NEXTSERIALNUMBERRESPONSE><VALUE>{n}</VALUE></CMD>` | D |
| log file path | `<CMD><FILEPATH></CMD>` | `<CMD><FILEPATHRESPONSE><VALUE>{path}</VALUE></CMD>` | C |
| settings path | `<CMD><SETTINGSPATH></CMD>` | `<CMD><SETTINGSPATHRESPONSE><VALUE>{path}</VALUE></CMD>` | C |
| shared folder path | `<CMD><SETTINGSPATHSHARED></CMD>` | `<CMD><SETTINGSPATHSHAREDRESPONSE><VALUE>{path}</VALUE></CMD>` | C |
| QSO rate / contest stats | `<CMD><QSORATE></CMD>` | `<CMD><QSORATERESPONSE><20MIN>..</20MIN><60MIN>..</60MIN><L1>..</L1><V1>..</V1>…</CMD>` | C |
| visible fields | `<CMD><VISIBLEFIELDS></CMD>` | list of visible fields + values | D |
| all fields | `<CMD><ALLFIELDS></CMD>` | all fields + values | D |
| all fields w/ values | `<CMD><ALLFIELDSVALUES></CMD>` *(tag uncertain)* | only non-empty fields | I |
| read user data | `<CMD><READUSERDATA></CMD>` *(tag uncertain)* | CALL, NAME, STATE, SECTION, CLASS, COUNTRY, CQZ, ITUZ, LAT, LONG, CNTY, CONT | I |
| rig command passthrough | `<CMD><SENDRIGCOMMAND><VALUE>{raw}</VALUE></CMD>` | none | C (write) |

## 6. Search / list / entity status (read-only)

| Op | Request | Conf |
| --- | --- | --- |
| list recent (primary fields) | `<CMD><LIST></CMD>` or `<CMD><LIST><VALUE>{n}</VALUE></CMD>` | C |
| list recent (all fields) | `<CMD><LIST><INCLUDEALL></CMD>` or `<CMD><LIST><INCLUDEALL><VALUE>{n}</VALUE></CMD>` | C |
| search | `<CMD><SEARCH>[<CALL>..</CALL>][<BAND>..</BAND>][<MODE>..</MODE>][<COUNTRYWORKED>..</COUNTRYWORKED>][<DXCC>..</DXCC>][<CONFIRMED>TRUE\|FALSE</CONFIRMED>][<INCLUDEALL>][<MAXRECORDS>{n}</MAXRECORDS>]</CMD>` | C |
| entity status | `<CMD><CHECKENTITY><CALL>{c}</CALL><BAND>{b}</BAND><MODE>{m}</MODE></CMD>` *(tag uncertain)* → `ATNO\|OW\|OC\|OWBMW\|OCBMW\|BMC` | I |

`MODE` is normalized to CW/PH/DIG. `COUNTRYWORKED` must match the country DB
exactly; prefer `DXCC` (ADIF number). `INCLUDEALL` returns every non-empty field.

## 7. Notifications (opt-in push)

Enable, then drain asynchronously arriving blocks.

| Op | Request | Effect | Kind | Conf |
| --- | --- | --- | --- | --- |
| all field updates | `<CMD><ALLUPDATES><VALUE>TRUE\|FALSE</VALUE></CMD>` | every text-box change pushed back | write | D |
| enter/calltab events | on by default in 0.8+; disable with `<CMD><SENDNOTIFICATIONS><VALUE>FALSE</VALUE></CMD>` *(tag uncertain)* | push on user ENTER / Call-tab | write | I |
| DX spot relay | `<CMD><DXSPOTS><VALUE>TRUE</VALUE></CMD>` *(tag uncertain)* | relays filtered DX spots | write | I |
| keydown relay | `<CMD><SENDKEYDOWN><VALUE>0\|1\|2</VALUE></CMD>` *(tag uncertain)* | 0 off, 1 F-keys, 2 all | write | I |
| rig poll from app | `<CMD><SENDRIGPOLL>…</CMD>` *(tag uncertain)* | app simulates rig interface | write | I |

Async event blocks include: `READBMFRESPONSE` (auto on B/M/F change), control
update blocks (when ALLUPDATES on), `CALLTABDUPEEVENT`, enter/calltab events,
DX-spot blocks, keydown blocks. The client buffers these; a `notifications` tool
drains them.

## 8. Control (text box) names

Exchange / entry boxes (subset; use `VISIBLEFIELDS` to see what a given contest
shows): `TXTENTRYCALL`, `TXTENTRYRSTR`, `TXTENTRYRSTS`, `TXTENTRYCLASS`,
`TXTENTRYSECTION`, `TXTENTRYSPCNUM`, `TXTENTRYNAME`, `TXTENTRYCHECK`,
`TXTENTRYSERIALNOR`, `TXTENTRYSERIALNOS`, `TXTENTRYGRIDR`, `TXTENTRYGRIDS`,
`TXTENTRYCOMMENTS`, `TXTENTRYPOWER`, `LBLDIALOGUE` (status label).

Derived/read-only (do **not** write): `TXTENTRYCOUNTRYWORKED`, CQ zone, ITU zone,
continent, prefix — all computed from the call.

## 9. Add-direct & SQL (destructive)

| Op | Request | Kind | Conf |
| --- | --- | --- | --- |
| add direct | `<CMD><ADDDIRECT>[<EXCLUDEDUPES>TRUE</EXCLUDEDUPES>][<STAYOPEN>TRUE\|FALSE</STAYOPEN>]<fldCall>..</fldCall>…</CMD>` | destructive (direct DB write) | C |
| SQL close | `<CMD><SQLCLOSE></CMD>` | write | C |
| check log (reload new) | `<CMD><CHECKLOG></CMD>` | write | C |
| open log (reload all) | `<CMD><OPENLOG></CMD>` | write | C |
| raw SQL | `<CMD><SENDSQL><VALUE>{sql}</VALUE></CMD>` *(tag uncertain)* | destructive / **db-wipe** if DELETE/DROP/UPDATE-all | I |

`ADDDIRECT` field names use the `fld…` prefix (e.g. `fldCall`, `fldBand`,
`fldMode`, `fldModeContest`, `fldDateStr` `YYYY/MM/DD`, `fldTimeOnStr` `HH:MM`,
`fldRstR`, `fldRstS`, `fldClass`, `fldSection`, `fldGridR`, `fldComments`,
`fldPoints`, `fldOperator`, `fldComputerName`). Direct DB writes bypass N3FJP's
contest scoring/multiplier logic — prefer `ACTION ENTER`.

## 10. Transmit / CW (destructive — escape-hatch + confirm)

Out of scope for a logging server's friendly tools; reachable via escape hatch
with `confirm=true`.

| Op | Request | Conf |
| --- | --- | --- |
| rig TX | `<CMD><RIGTX></CMD>` | C |
| rig RX | `<CMD><RIGRX></CMD>` | C |
| CW key down (com port) | `<CMD><CWCOMPORTKEYDOWN></CMD>` *(tag uncertain)* | I |
| CW key up | `<CMD><CWCOMPORTKEYUP></CMD>` *(tag uncertain)* | I |
| send CW | `<CMD><SENDCW><VALUE>{text}</VALUE></CMD>` *(tag uncertain)* | I |

## 11. Escape hatch

`n3fjp_call(raw, expect=None, confirm=False)` sends an arbitrary `<CMD>…</CMD>`
(CRLF appended automatically) and returns parsed response/notification blocks.
The single way to reach any **I**-confidence command above. Destructive raw
commands require `confirm=true`; whole-DB SQL still requires `N3FJP_ALLOW_DB_WIPE`.

---

## Live verification (API 2.2) — corrections to the public 0.9 doc

Verified against *N3FJP's ARRL Field Day Contest Log* v6.6.10, API 2.2.

**Unknown-command sentinel.** An unrecognised command returns
`<CMD><CMD_NOT_FOUND></CMD>` — distinct from "no response". The client uses this
to report unsupported commands clearly.

**Confirmed response tags (exact):**

| Request | Response (real) |
| --- | --- |
| `PROGRAM` | `<PROGRAMRESPONSE><PGM>…</PGM><VER>6.6.10</VER><APIVER>2.2</APIVER>` — note `VER`/`APIVER`, **not** `VERSION` |
| `QSOCOUNT` | `<QSOCOUNTRESPONSE><VALUE>n</VALUE>` (the count command is `QSOCOUNT`, not `READQSOCOUNT`) |
| `READBMF` | `<READBMFRESPONSE><BAND>20</BAND><MODE>DIG</MODE><MODETEST>DIG</MODETEST><FREQ>0.000000</FREQ>` (FREQ is a float string) |
| `NEXTSERIALNUMBER` | `<NEXTSERIALNUMBERRESPONSE><VALUE></VALUE>` |
| `FILEPATH` / `SETTINGSPATH` / `SETTINGSPATHSHARED` | `…RESPONSE><VALUE>path</VALUE>` |
| `QSORATE` | `<QSORATERESPONSE><TOTSCORE>…</TOTSCORE><TOTQSOS>…</TOTQSOS><20MIN>…</20MIN><60MIN>…</60MIN><L1>…</L1><V1>…</V1>…</CMD>` (adds `TOTSCORE`/`TOTQSOS`) |
| `VISIBLEFIELDS` | one `<VISIBLEFIELDSRESPONSE><CONTROL>…</CONTROL><VALUE>…</VALUE>` block **per field** |
| `ALLFIELDS` | one `<ALLFIELDSRESPONSE><CONTROL>…</CONTROL><VALUE>…</VALUE>` block per field (52 for Field Day) |
| `READ` | `<READRESPONSE><CONTROL>…</CONTROL><VALUE>…</VALUE>` |
| `DUPECHECK` | `<DUPECHECKRESPONSE><CALL>…</CALL><VALUE>detail or empty</VALUE>` |
| `SEARCH` | `<SEARCHRESPONSE>…` (empty `<SEARCHRESPONSE></SEARCHRESPONSE>`-style block when no match) |
| `ACTION ENTER` | `<ENTERRESPONSE><VALUE>n_added</VALUE>` |
| `ACTION CALLTAB` | `<CALLTABEVENT>…` (see below) |

**`CALLTABEVENT` is rich and synchronous.** Tabbing from the call (or sending
`ACTION CALLTAB`) returns, a beat later, a single `CALLTABEVENT` block with the
full call lookup:
`CALL, BAND, MODE, MODETEST, COUNTRY, DXCC, MYCALL, OPERATOR, QSOCOUNT, PFX,
CONT, CQZ, ITUZ, LAT, LON, BEARING, LONGPATH, DISTANCE`. `contest-mcp` surfaces
the geographic/entity subset as `lookup` in `log_qso`. A duplicate adds a
`CALLTABDUPEEVENT`.

**Commands that do NOT exist in 2.2** (return `CMD_NOT_FOUND`): `APIVERSION`
(use `PROGRAM`→`APIVER`), `READQSOCOUNT` (use `QSOCOUNT`), `ALLFIELDSVALUES`,
`READUSERDATA`, `CHECKENTITY`, `ENTITYSTATUS`. The entity-status feature could
not be confirmed under any tested tag; treat it as unavailable on this build
(reach via `n3fjp_call` if a tag is found).

**Notifications caveat.** With `ALLUPDATES TRUE`, *app-initiated* field changes
did **not** echo back as push events on this build; the async buffer mainly
catches *operator-driven* activity. Events caused by your own commands (e.g.
`CALLTABEVENT`) arrive **inline** in that command's reply, not the async buffer.

**Logging in Network mode (confirmed live).** N3FJP runs the **API** (port 1100)
and the multi-PC **networking/"server"** socket (port 1000) side by side; any
cluster node answers API calls regardless of its client/server role. With the
networking server **up**, `ENTER` logs correctly — verified: the record appears
in `SEARCH`, the `QSOCOUNT` increments, and a repeat `DUPECHECK` returns
*"Duplicate! … Rec# 1"*. **But `ENTERRESPONSE` returned `VALUE=0` even on
success** (the master-table commit is asynchronous, so the immediate count is 0).
**Do not trust `ENTERRESPONSE`'s value to confirm logging** in networked mode —
`contest-mcp`'s `log_qso` instead confirms success via the `QSOCOUNT` **delta**.
With the networking server **down/absent**, `ENTER` times out with N3FJP's
*"Server Failed to Respond"* dialog and nothing is logged; run standalone or keep
the networking server reachable.

**SEARCHRESPONSE fields (with INCLUDEALL), confirmed:** `CALL, DATE, TIMEON,
BAND, MODE, MODETEST, CLASS, CONTINENT, …`. **DUPECHECKRESPONSE detail** is a
human string that contains an embedded CRLF, e.g.
`Duplicate!  AE5VG at 6/23 22:01 on 20 DIG\r\nRec# 1` — the parser keeps it
intact because block splitting is on `</CMD>`, not newlines.

*Observation to re-confirm:* in that same networked state, `UPDATE`s to
`TXTENTRYBAND`/`TXTENTRYMODE` read back empty. Per the operator, all GUI fields
are editable and the rig only *auto-populates* them — so this is most likely a
control-type/timing nuance (band/mode may be combo/menu controls rather than
plain text boxes) rather than a write restriction. To re-verify once standalone.
`ADDDIRECT` (explicit `fldBand`/`fldMode`/`fldModeContest`) remains the direct,
rig-independent path that bypasses the entry form entirely.
