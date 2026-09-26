# HEX20 FSW: Ground Telecommanding and Onboard TC Reception

Part 1: a ground platform that builds and sends CCSDS/PUS-C telecommands.
Part 2: onboard software that receives, validates, routes and executes them,
and answers with PUS-C ST[1] verification reports.
Python 3.10 or newer, standard library only (nothing to install).

## Quick start

Terminal 1 (the satellite):

    python run_onboard.py

Terminal 2 (the operator screen):

    python ui.py

Optional, to see the reports coming back from the satellite:

    python demo_ground.py

## Files

| File | Purpose |
|---|---|
| packet.py | CRC-16, Space Packet build and parse (PUS-C TC) |
| frame.py | TC Transfer Frame with start and tail sequences |
| command_db.py | SQLite command database (schema, seed data, queries) |
| sender.py | Validation, encoding, counters, TCP transmit, rotating log |
| ui.py | Operator screen (Tkinter) |
| satellite.py | Byte-stream state machine, frame and packet validation, counters |
| onboard.py | Routing table, handlers, ST[1] reports, ST[3] housekeeping |
| routing.json | Configurable routing table (32 entries, APID to application) |
| compliance.py | Automated header-field checker |
| run_all_tests.py | Runs every test |

## Part 1: Ground platform

### Database schema (commands.db, created and filled at startup)

- apid(apid, name)
- command(id, apid, service, subtype, name), unique on (apid, service, subtype)
- parameter(id, command_id, position, name, type, min_value, max_value, unit)

Parameter types: uint8, uint16, uint32, int16 (big-endian).
The seed data has 5 APIDs (100 to 104), each with 3 commands.

### Encoding assumptions

- All fields are big-endian.
- Space Packet primary header (6 bytes): version 0, type 1, secondary header
  flag 1, APID (11 bits), sequence flags 11, sequence count (14 bits),
  data length = (bytes after the primary header) - 1.
- PUS-C TC secondary header (5 bytes): 0x20 (PUS version 2, ack flags 0),
  service, subtype, source ID (16 bits, 0).
- Packet CRC: CRC-16-CCITT (poly 0x1021, init 0xFFFF, no reflection) over the
  whole packet except the CRC itself, appended as the last 2 bytes.
- TC Transfer Frame: START (EB90) + 5-byte header + packet + CRC-16 + TAIL
  (C5C5C5C5C5C5C579). Header: version 0, bypass 0, control 0, spare 0,
  spacecraft ID (10 bits, 0x123), virtual channel (6 bits, 0), frame length
  (10 bits, total frame bytes - 1), frame sequence number (8 bits).
  The frame CRC covers the header and the packet.
- The spacecraft ID acts as the frame "credentials".
- Packet sequence counter (14 bits) and frame sequence number (8 bits) are kept
  per APID in counters.json and survive restarts.
- Every transmitted command is logged with a UTC timestamp in tc_log.txt
  (rotating: 100 KB, 3 backups).

### How to add a new APID

1. In command_db.py, add an entry to SEED with the APID, its name and its
   commands: (service, subtype, name, [(param, type, min, max, unit)]).
2. Delete commands.db so it is rebuilt at the next start.
3. In routing.json, map the APID to an application name.
4. If it needs new behaviour, add an application to APPLICATIONS in onboard.py
   with its (service, subtype) handlers. Otherwise use "SPARE".

## Part 2: Onboard software

### Architecture

    uplink bytes
      -> FrameExtractor (state machine: SEARCH_START, COLLECT until tail)
      -> parse_frame  (start/tail, length, CRC, spacecraft ID)
      -> parse_tc_packet (version 0, type 1, length, CRC, PUS version, non-zero
                          service and subtype)
      -> routing table (APID -> application, 32 entries in routing.json)
      -> (service, subtype) table of that application -> handler
      -> ST[1,3] on entry, ST[1,7] on success, ST[1,8] with failure code

Anything invalid is discarded, logged to satellite_log.txt and counted.

### Handlers

ST[3,1/2] housekeeping (report 1 only), ST[6,2/5] memory load and dump (simulated
64 KB), ST[8,128] function management (stub), ST[17,1] connection test (replies
ST[17,2]).

### Failure codes (ST[1,8])

1 unknown APID, 2 unknown command, 3 bad parameters, 4 unknown report,
5 bad memory address, 6 internal error.

### Counters

TCs received and rejected, frames accepted and rejected, packets accepted and
rejected. They are returned in the ST[3,25] housekeeping report.

## Tests

    python run_all_tests.py

Each acceptance criterion has a test: test_db.py, test_packet.py, test_frame.py,
test_satellite.py, test_onboard.py, test_compliance.py, test_integration.py.

See the ["Test result screenshots"](./Test%20result%20screenshots) folder for output...

## Integration with Part 1

sender.py sends frames over TCP to 127.0.0.1:5000. onboard.py (the reference
simulator) listens there and returns its reports on the same connection.
demo_ground.py shows them. test_integration.py runs both sides together.

## Known limits

- Only TCP is implemented (no serial/USB).
- Routing failures reply with ST[1,2]; the standard's ST[1,10] is not used.
- Only housekeeping report 1 exists on board, so other report IDs fail with code 4.
- The receiver does not enforce frame sequence numbers (no COP-1/FARM).
- Report timestamps are Unix seconds plus milliseconds, not CUC.
- No authentication beyond the spacecraft ID check.
- The ground UI does not display incoming reports (use demo_ground.py).
- Single-threaded, one connection at a time.