# contest-mcp — Test Plan

A repeatable plan to verify the server end to end against a real N3FJP instance,
whether running from source or as the installed `.mcpb` extension. Most tests are
read-only or self-restoring; record-writing tests are clearly marked.

## Preconditions

- An N3FJP program is running with **Settings → Application Program Interface →
  "TCP API Enabled"** (default API port `1100`).
- For logging tests: N3FJP is **standalone** (Settings → Network off) *or* its
  networking server is reachable — otherwise `ENTER` returns 0 records and N3FJP
  shows "Server Failed to Respond".
- The MCP client (Claude Desktop or the MCP Inspector) shows the contest-mcp tools.
- A scratch/practice log you don't mind writing to for the logging tests.

## Conventions

- **Restore** steps return the log/form to its prior state.
- Pass = result matches "Expected"; note any deviation and your N3FJP program +
  API version (from `status`).

---

## A. Connectivity & configuration

| ID | Action | Expected |
| --- | --- | --- |
| A1 | `status` | program, version, **api_version**, qso_count, band/mode/frequency, db_wipe_enabled. |
| A2 | Confirm `api_version` | A real version (e.g. `2.2`). |
| A3 | Stop N3FJP, run any read | Clear "Could not reach N3FJP … TCP API Enabled?" error, no crash. |
| A4 | Point `N3FJP_PORT` at 1000 (networking port) | Reads time out / no API response — confirms 1100 is the API. Restore to 1100. |

## B. Read operations

| ID | Action | Expected |
| --- | --- | --- |
| B1 | `query` program / qso_count / next_serial | Correct strings; integer count. |
| B2 | `query` log_path / settings_path / shared_path | Real file paths. |
| B3 | `query` qso_rate | Contest stats incl. TOTSCORE/TOTQSOS and labelled totals. |
| B4 | `query` band_mode_freq | BAND, MODE, MODETEST (CW/PH/DIG), FREQ. |
| B5 | `fields` visible | One entry per visible field for the current contest. |
| B6 | `fields` all | Every field (40–50+ for a contest) with values. |
| B7 | `fields` read (field=call) | The current Call box value. |
| B8 | `search` dupecheck (call=W1AW) | `is_dupe` + detail (empty if new). No side effects. |
| B9 | `search` list (count=5) | Up to 5 recent records (empty if log empty). |

## C. Field write / round-trip (with restore)

| ID | Action | Expected |
| --- | --- | --- |
| C1 | `log` set (field=call, value=AE5VG); `fields` read call | Reads back `AE5VG`. |
| C2 | `log` set (field=country_worked, …) | **Refused** — derived field is not writable. |
| C3 | `log` clear; `fields` read call | Call box empty. |
| C4 | `log` calltab (after setting a call) | Returns a `CALLTABEVENT` with country/DXCC/zones/bearing/distance. |

## D. Logging (writes a record — use a scratch log)

| ID | Action | Expected |
| --- | --- | --- |
| D1 | Set band+mode in N3FJP (menu or rig), standalone mode | Prereq for ENTER to commit. |
| D2 | `log` log_qso (call, contest, exchange) | `records_added` = 1; `logged` true; `lookup` present; qso_count +1. |
| D3 | `search` search (call) | The new QSO is found. |
| D4 | `log` log_qso same call again | `dupe` surfaced (CALLTABDUPEEVENT) / dupecheck non-empty. |
| D5 | Restore | Remove the test QSO (N3FJP UI, or `database` delete with confirm). |

## E. Band / mode

| ID | Action | Expected |
| --- | --- | --- |
| E1 | `bandmode` change_freq (value=14070000) | With rig interface: frequency/band update (no rig: may be a no-op). |
| E2 | `bandmode` set_band / set_mode | Updates the boxes (effective when rig interface is off). |

## F. Safety model (the important part)

| ID | Action | Expected |
| --- | --- | --- |
| F1 | `database` delete (where="fldPrimaryID=…") **without** confirm | **Refused**: ConfirmationRequired. |
| F2 | `database` delete (same) with confirm=true | Runs a scoped `DELETE … WHERE …`. |
| F3 | `database` sql (sql="DELETE FROM tblContacts") confirm=true, switch **off** | **Refused**: DatabaseWipeBlocked. |
| F4 | Same as F3 with `N3FJP_ALLOW_DB_WIPE=on` | Allowed (only do this on a throwaway log!). |
| F5 | `database` delete (where="") confirm=true, switch off | **Refused** — empty WHERE is treated as a wipe. |
| F6 | `n3fjp_call` "PROGRAM" (no confirm) | Works — recognised read-only command. |
| F7 | `n3fjp_call` "<ACTION><VALUE>CLEAR</VALUE>" (no confirm) | **Refused** — non-read command needs confirm=true. |
| F8 | Confirm read tools show as Always-Allow-capable in the client | `status`/`query`/`fields`/`search` are read-only annotated. |

## G. Notifications

| ID | Action | Expected |
| --- | --- | --- |
| G1 | `notifications` enable | OK. |
| G2 | In N3FJP, the operator changes a field / works a station | `notifications` drain returns event blocks. |
| G3 | `notifications` disable | OK. |

## H. Escape hatch & discovery

| ID | Action | Expected |
| --- | --- | --- |
| H1 | `n3fjp_call` "QSORATE" | `QSORATERESPONSE` parsed. |
| H2 | `n3fjp_call` an unknown command | Reports `CMD_NOT_FOUND` clearly. |

---

### Notes from live verification (N3FJP Field Day, API 2.2)

- Reads, field round-trip, `CALLTAB` lookup, and `DUPECHECK` all verified.
- `APIVERSION`, `READQSOCOUNT`, `READUSERDATA`, `CHECKENTITY`/`ENTITYSTATUS`
  return `CMD_NOT_FOUND` on this build (use `PROGRAM`→APIVER, `QSOCOUNT`, etc.).
- `ENTER` adding 0 records traced to N3FJP **Network mode** timing out on its
  networking server — run standalone for logging tests.
