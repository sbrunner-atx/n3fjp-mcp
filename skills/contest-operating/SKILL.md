---
name: contest-operating
description: >
  Run a contest operating loop end-to-end: call CQ, work callers through the
  exchange, handle QRM/garble/no-copy situations, and log completed QSOs to
  N3FJP via n3fjp-mcp. Use for ARRL Field Day and similar exchange-based
  contests on digital modes (pairs with the fldigi-operating skill in
  fldigi-mcp for radio control). Field-proven during ARRL Field Day 2026
  (class-2A club station, BPSK31; example callsigns anonymized).
---

# Contest operating: exchange state machine and N3FJP logging

## The QSO state machine (Field Day example)

Exchange = class + section (e.g., `2A STX`). Substitute your contest's
exchange as needed.

```
CQ:        "CQ FD CQ FD de <MYCALL> <MYCALL> pse k\n"
             ↓ caller heard (their callsign decoded)
EXCHANGE:  "<CALL> de <MYCALL> <MYCALL>\nPse copy 2A 2A STX STX\nde <MYCALL> BK\n"
             ↓ they QSL and give (or already gave) their class+section
TU:        "QSL <their CLASS> <their SECTION> TU <CALL> de <MYCALL> GL FD sk sk\n"
             ↓
LOG:       log to N3FJP (see below), then back to CQ
```

Rules that improved completion rate during live operation:

- **Double everything important.** `2A 2A STX STX` copies far better than
  `2A STX` through QSB and QRM.
- **Echo their exchange back in the TU** (`QSL 1D AZ TU W7XYZ ...`). It lets
  the other station verify you logged them correctly before you QRZ.
- **Never log without a confirmed callsign.** Class and section can be
  inferred from a repeat; the callsign cannot.
- A "CQ" from a station heard mid-loop is **not** a caller — see QRM below.

## Special cases (all encountered live)

**Caller sends callsign only, no exchange.** Normal. Some operators send
just `<MYCALL> de <THEIRCALL>` and wait. Send your exchange; their
class/section arrives in the next over.

**They already sent their exchange with the first call.** Also normal
(`K6ABC de W7XYZ 1D AZ 1D AZ pse k`). Send your exchange; they reply `QSL`;
go straight to TU.

**Caller didn't copy you** (`repeat`, `no cpy`, `AGN`). Resend once, in
abbreviated form: `<CALL> de <MYCALL>\n2A STX 2A STX\nBK\n`. If still no
response, QRZ once, then return to CQ.

**Garbled/partial callsign.** Send `de <MYCALL> AGN AGN pse k\n`, wait one
listen window. If the repeat is still unreadable, return to CQ. Budget at
most two overs on an undecodable station.

**Two stations doubled (called simultaneously).** Output looks like two
callsigns interleaved with control garbage. Same treatment as garble: one
AGN, then CQ. Usually one of them calls again alone.

**Another station calling CQ on/near your frequency.** PSK's narrow
passband decodes neighbors. A line matching `CQ ... de <OTHERCALL>` where
OTHERCALL ≠ yours is not a caller — ignore it and continue your own loop.

**Signal lost mid-QSO.** If the exchange never completes (no confirmed
callsign + exchange), do not log. An incomplete QSO is not a contact.

**Callsign fragment validation.** Before any directed reply, check the
decoded call against `[A-Z0-9]{1,3}[0-9][A-Z]{1,3}` (plus optional `/`
suffix). Noise fragments frequently look call-ish.

## Logging to N3FJP (n3fjp-mcp)

Preferred: the one-shot flow. Exchange fields go in the `exchange` dict —
they are **not** top-level parameters:

```
log → log_qso  {"call": "W7XYZ", "contest": "field_day",
                "exchange": {"class": "1D", "section": "AZ"}}
```

Manual alternative:

```
log → set_many  {"CALL": "W7XYZ", "CLASS": "1D", "SECTION": "AZ"}
log → enter
```

**Success is `logged: true` in the response — trust nothing else.**
Both paths return a `logged` boolean derived from the QSO-count delta
and/or an ENTEREVENT push. `records_added` can report `0` on a QSO that
*was* written (N3FJP networked/master-table mode commits asynchronously —
see docs/N3FJP-API.md gotchas). **Never retry on `records_added: 0`
alone** — blind retries at Field Day 2026 produced duplicate log records.
Retry only when `logged` is false.

Other quirks (observed live, Field Day 2026):

- `set_many → calltab` can trigger an ENTEREVENT directly (band/mode/dupe
  check fires on callsign entry). If it does, the QSO is logged — do not
  send another `enter`.
- `calltab` after `set_many` also populates COUNTRY/STATE/section lookups;
  useful for verifying the section you copied is plausible.
- A `CALLTABDUPEEVENT` means the call is already in the log for this
  band/mode — usually a sign you (or a retry) already logged it.
- N3FJP modal dialogs block the API. If calls stop responding, a dialog is
  open on the logging PC and needs human attention.

Log **while the TU transmission is still sending** — the radio is busy for
~15 s, which is exactly the time logging takes. By the time TX drops you
are ready to CQ again.

## Cadence

- After every over: listen ~10 s (one or two RX polls) before the next CQ.
- Work callers immediately; the CQ loop resumes only after the QSO
  completes or is abandoned.
- The operator can say "stop" at any time: send `transmit → abort` (via
  fldigi-mcp) — immediate PTT drop, discards queued text.
