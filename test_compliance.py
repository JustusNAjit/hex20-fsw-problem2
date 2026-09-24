from packet import build_tc_packet
from frame import build_frame
from onboard import create_onboard, COUNTER_ORDER
from compliance import check_packet

ob = create_onboard()


def run(apid, service, subtype, data=b""):
    pkt = build_tc_packet(apid, 1, service, subtype, data)
    problems = check_packet(pkt, 1)
    assert problems == [], problems               # the command itself is compliant
    replies = ob.process(build_frame(pkt, 1))
    for r in replies:
        problems = check_packet(r, 0)
        assert problems == [], problems           # every receipt is compliant too
    return replies


# 1. Run many different commands, good and bad: everything must be compliant
run(100, 17, 1)
run(101, 8, 128, bytes([3, 1]))
run(102, 6, 5, (10).to_bytes(4, "big") + bytes([4]))
run(104, 6, 2, (10).to_bytes(4, "big") + bytes([7]))
run(100, 3, 1, bytes([5]))       # fails, ST[1,8]
run(500, 17, 1)                  # no route, ST[1,2]
run(120, 17, 1)

# 2. The checker must catch broken packets
good = build_tc_packet(100, 1, 17, 1)
assert check_packet(good, 1) == []

b = bytearray(good); b[0] |= 0x20
assert any("packet version" in p for p in check_packet(bytes(b), 1))

b = bytearray(good); b[6] = 0x10
assert any("PUS version" in p for p in check_packet(bytes(b), 1))

b = bytearray(good); b[7] = 0
assert any("service" in p for p in check_packet(bytes(b), 1))

b = bytearray(good); b[9] ^= 0xFF
assert any("CRC" in p for p in check_packet(bytes(b), 1))

assert check_packet(good, 0) != []    # a TC is not telemetry

# 3. Counters reported through ST[3] must match the satellite's real counters
damaged = bytearray(build_frame(good, 1))
damaged[10] ^= 0xFF
ob.process(bytes(damaged))                               # one rejected frame

reports = run(100, 3, 1, bytes([1]))
hk = [r for r in reports if (r[7], r[8]) == (3, 25)][0]
reported = {name: int.from_bytes(hk[20 + 4 * i:24 + 4 * i], "big")
            for i, name in enumerate(COUNTER_ORDER)}
print("Counters in ST[3] report:", reported)
assert reported == ob.counters.as_dict()
assert reported["frames_rejected"] == 1

print("Compliance check PASSED")