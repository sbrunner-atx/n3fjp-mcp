# Field Day 2026 — Automation Lessons Learned

**Station:** class-2A club station (all callsigns in this document are
anonymized ARRL-style sample calls — K6ABC, W7XYZ, etc.; exchanges, flow,
and garble are verbatim from the session)  
**Mode:** BPSK31 at 14.070 MHz (20m)  
**Event:** ARRL Field Day 2026  
**Author:** Post-session handoff for development team

---

## 1. Operating Loop — What We Settled On

### CQ cycle
```
transmit → send "CQ FD CQ FD de K6ABC K6ABC pse k\n"  (return_to_rx=true)
poll get_trx_status until "rx"
read rx_length once (≈10-second listen window)
if new content contains a callsign → work them
else → send CQ again immediately
```

The 10-second window is one rx_length poll cycle after get_trx_status returns "rx". This felt right operationally — not so short that we miss slow-typing callers, not so long that the CQ rate drops.

### Exchange sequence
1. **Our CQ:** `CQ FD CQ FD de K6ABC K6ABC pse k\n`
2. **Caller heard → send exchange:** `[CALL] de K6ABC K6ABC\nPse copy 2A 2A STX STX\nde K6ABC BK\n`
3. **They QSL → send TU:** `QSL [CLASS] [SECTION] TU [CALL] de K6ABC GL FD sk sk\n`
4. **Log to N3FJP, return to CQ**

---

## 2. TX/RX Control — Key Finding

Use `transmit → send` with `return_to_rx=true` for every over. This embeds `^r` in the TX stream, causing fldigi to drop PTT at the exact moment the last character finishes — no polling, no lag, no idle carrier.

- **`transmit → send` (return_to_rx=true):** normal over end — use this always
- **`transmit → abort`:** panic stop (immediate, discards queued text) — use when caller comes back early or we make a mistake
- **`transmit → rx`:** buffered return, slow — do not use

**Never poll the TX buffer to decide when to stop.**

### Newline character
Use a real `\n` newline at the end of each transmitted message for display readability in fldigi. The string `^n` is transmitted as two literal characters, not a control sequence — it does NOT produce a line break.

---

## 3. RX Buffer — Critical Clarification

**fldigi does not echo TX into the RX buffer.** Any text appearing in the RX window came from an external station. This means:

- If we see "K6ABC" in the RX buffer, someone is transmitting our callsign — i.e., they are calling us. Always pursue it.
- During development we incorrectly dismissed many RX reads as "our own echo." This was wrong. The automation must never assume RX content is self-generated.

### RX buffer tracking
Track position via `text → rx_length`. Read from `last_known_position` to current length. Never re-read the full buffer; only read the delta.

Edge case: `rx_length` can reset to a small value if fldigi is restarted mid-session. Detect this as `new_length < last_position` and re-baseline from 0.

---

## 4. N3FJP Logging — Discovered Protocol

The correct logging sequence is **set_many → enter → enter**:

```
log → set_many  {"CALL": "W7XYZ", "CLASS": "1D", "SECTION": "AZ"}
log → enter     (first call — may return records_added: 0)
log → set_many  {"CALL": "W7XYZ", "CLASS": "1D", "SECTION": "AZ"}  (repeat)
log → enter     (second call — produces ENTEREVENT with QSOCOUNT)
```

A single `set_many → enter` sequence reliably returned `records_added: 0` (no log). A repeated `set_many → enter` produced the ENTEREVENT confirming the QSO was written.

**Side effect:** The double-enter pattern triggers a `CALLTABDUPEEVENT` on the second call (N3FJP flags it as a duplicate of the first entry). The QSO IS logged, but the log will contain duplicate records for each QSO worked this way. Recommend a cleanup pass after the contest, or investigate whether `calltab` before the first `enter` provides a cleaner path (it did work once during the session for W7XYZ, producing a direct ENTEREVENT).

**Alternative that worked for W7XYZ:** `set_many → calltab` triggered an ENTEREVENT directly. This may be the cleaner path but was not consistently reproducible.

**Root cause (post-contest):** the [N3FJP API reference](N3FJP-API.md) gotchas section documents that `ENTER` can report 0 yet still log in networked mode. The first `enter` likely logged silently; the retry then created the duplicate. Success detection should key off the ENTEREVENT, not `records_added`.

---

## 5. Special Cases Encountered

### 5a. Garbled / partial callsign
Received `PSE CPY 3A OH 3A OH DE WeaCCA K` — callsign unreadable. Sent AGN, no reply. **Decision: send one AGN, wait one poll, if no improvement return to CQ.** Do not spend more than two overs trying to decode a station with a consistently bad signal.

### 5b. Another station CQing on our frequency (QRM)
W5MNO was also calling CQ FD and their signal was decoded interleaved with ours. PSK31 is narrowband and multiple stations coexist on the same audio passband — fldigi decodes whichever signal it is tuned to. When the RX buffer contains a CQ that uses a different callsign (not K6ABC), it is not our caller and should be ignored. **Detection rule:** a line starting with "CQ FD" containing a callsign other than K6ABC = ignore.

### 5c. Two stations transmitting simultaneously (QRM on response)
Received `K6ABC D6d5Oe\x1c7ABCWC d STX 3A STX 3AKE` — two stations called us at the same time, producing overlapping/garbled output. Could partially decode class (3A) and section (STX) but not a clean callsign. Sent AGN, no usable reply. **Decision: send AGN once; if still unreadable, return to CQ.** Do not attempt to log a QSO without a confirmed callsign.

### 5d. Caller did not copy our exchange
K0GHI (1E UT) sent `nt z repeat no cpy` after our first exchange. Resent a shorter version: `K0GHI de K6ABC\n2A STX 2A STX\nBK\n`. K0GHI did not respond further. **Decision: one resend with abbreviated exchange; if no response, QRZ and return to CQ.**

### 5e. Caller sends callsign only, no exchange
N4DEF called with callsign only (`K6ABC K6ABC de N4DEF N4DEF`), no class/section. We sent our exchange; they then provided `QSL PSE COPY 1D 1D NFL DE N4DEF K`. **This is normal** — some operators send their callsign first, wait for our exchange, then give their exchange. The automation should send our exchange upon hearing the callsign and wait for their class/section in the next over.

### 5f. Weak signal / signal dropped mid-QSO
N4JKL (1D VA) was partially decoded from the initial response, but after we sent our exchange their reply was pure noise (`e   eŒ   oe l`). Sent AGN, no reply. **Decision: same as 5b — one AGN, then CQ.**

---

## 6. Exchange Format Tuning

Several iterations were made on the exchange wording:

| Version | Issue |
|---|---|
| Initial: `pse copy 2A STX` | Too terse; some stations confused |
| With double: `2A 2A STX STX` | Better copy rate; standard FD practice |
| Final TU: `QSL [CLASS] [SECTION] TU [CALL] de K6ABC GL FD sk sk\n` | Confirmed correct — echoes their exchange back to them for verification |

Including their class/section in the TU message (`QSL 1D AZ TU W7XYZ...`) lets the other station verify we logged them correctly before we QRZ.

---

## 7. QSOs Completed This Session

| Callsign | Class | Section | Notes |
|---|---|---|---|
| W7XYZ | 1D | AZ | Clean QSO |
| K7ABC | 4A | WY | Clean QSO |
| N4DEF | 1D | NFL | Callsign-first caller |
| K0GHI | 1E | UT | No copy on resend — not logged |
| N4JKL | 1D | VA | Signal lost mid-QSO — not logged |

---

## 8. Recommended Improvements for Development

1. **Smarter RX parsing:** Build a regex that distinguishes `[CALLSIGN] de K6ABC` (someone calling us) from `CQ FD ... de [CALLSIGN]` (someone else calling CQ). Currently the automation reads raw text and eyeballs it.

2. **Callsign validator:** Before responding, validate the decoded callsign against a standard regex (`[A-Z0-9]{1,3}[0-9][A-Z]{1,3}`). Discard QRM garbage before sending a directed exchange.

3. **N3FJP logging:** Investigate a clean one-shot log path. The `set_many → calltab` → ENTEREVENT path worked once (W7XYZ) but wasn't reproducible. The `set_many → enter → set_many → enter` double-call workaround produces duplicate records needing post-contest cleanup.

4. **No-echo assumption:** Bake the "no RX echo" rule into the detection logic permanently. All RX content is external. Remove any "dismiss as own TX" logic.

5. **QRM handling:** If two successive reads return only garbled content (non-callsign printable characters with no valid words), auto-send one AGN and set a "gave up on this caller" flag. Return to CQ after one AGN with no clean reply.

6. **Session restart detection:** Watch for `rx_length` dropping below `last_known_position`. On detection, log a warning and re-baseline to 0. This handles fldigi restarts gracefully without manual intervention.

---

## 9. Ports and Config

- fldigi XML-RPC: `127.0.0.1:7372` (non-default; default is 7362)
- N3FJP logging: via `mcp__N3FJP_Logging__*` connector
- fldigi connector: `mcp__fldigi__*`
