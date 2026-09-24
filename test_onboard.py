from packet import build_tc_packet, crc16
from frame import build_frame
from onboard import create_onboard, FAIL_UNKNOWN_REPORT, FAIL_BAD_PARAMETERS

ob = create_onboard()
all_tm = []


def send(apid, service, subtype, app_data=b""):
    pkt = build_tc_packet(apid, 1, service, subtype, app_data)
    replies = ob.process(build_frame(pkt, 1))
    all_tm.extend(replies)
    return replies


def kinds(replies):
    return [(r[7], r[8]) for r in replies]


# 1. Routing table has at least 32 entries
assert len(ob.routing) >= 32

# 2. Connection test: started, ST[17,2] reply, completed
r = send(100, 17, 1)
assert kinds(r) == [(1, 3), (17, 2), (1, 7)]
assert r[0][:2].hex() == "0864"            # type 0 (telemetry), APID 100
assert r[0][19:23].hex() == "1864c001"     # request ID = the command we sent
assert ob.last_report_ms < 100             # reports generated within 100 ms

# 3. Housekeeping report carries the counters
r = send(100, 3, 1, bytes([1]))
assert kinds(r) == [(1, 3), (3, 25), (1, 7)]
assert int.from_bytes(r[1][20:24], "big") == 2     # tc_received so far

# 4. Failures give ST[1,8] with a failure code
r = send(100, 3, 1, bytes([5]))
assert kinds(r) == [(1, 3), (1, 8)]
assert int.from_bytes(r[1][23:25], "big") == FAIL_UNKNOWN_REPORT
r = send(100, 3, 1, b"")
assert kinds(r) == [(1, 3), (1, 8)]
assert int.from_bytes(r[1][23:25], "big") == FAIL_BAD_PARAMETERS

# 5. Memory load then dump
assert kinds(send(104, 6, 2, (10).to_bytes(4, "big") + bytes([0xAB]))) == [(1, 3), (1, 7)]
r = send(102, 6, 5, (10).to_bytes(4, "big") + bytes([1]))
assert kinds(r) == [(1, 3), (6, 6), (1, 7)]
assert r[1][24] == 0xAB

# 6. Function management
assert kinds(send(101, 8, 128, bytes([3, 1]))) == [(1, 3), (1, 7)]
assert kinds(send(101, 8, 128, bytes([3]))) == [(1, 3), (1, 8)]

# 7. Routing failures give ST[1,2]
assert kinds(send(100, 6, 2, (10).to_bytes(4, "big") + bytes([1]))) == [(1, 2)]
assert kinds(send(500, 17, 1)) == [(1, 2)]

# 8. A spare APID still answers a connection test
assert kinds(send(120, 17, 1)) == [(1, 3), (17, 2), (1, 7)]

# 9. A damaged frame produces no reply at all
bad = bytearray(build_frame(build_tc_packet(100, 1, 17, 1), 1))
bad[10] ^= 0xFF
assert ob.process(bytes(bad)) == []

# 10. Every report has a valid CRC
for tm in all_tm:
    assert crc16(tm[:-2]) == int.from_bytes(tm[-2:], "big")

print("Counters:", ob.counters.as_dict())
print("Onboard check PASSED")