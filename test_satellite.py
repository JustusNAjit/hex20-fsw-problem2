from packet import build_tc_packet
from frame import build_frame
from satellite import Satellite


def wire(pseq=1, fseq=1, scid=None):
    pkt = build_tc_packet(100, pseq, 17, 1)
    if scid is None:
        return build_frame(pkt, fseq)
    return build_frame(pkt, fseq, scid=scid)


sat = Satellite()

# 1. One good frame
got = sat.receive_bytes(wire())
assert len(got) == 1 and got[0]["apid"] == 100

# 2. Noise first, then two frames stuck together
got = sat.receive_bytes(b"\x00\x11\x22" + wire(2, 2) + wire(3, 3))
assert [g["seq"] for g in got] == [2, 3]

# 3. One frame arriving in three pieces
w = wire(4, 4)
assert sat.receive_bytes(w[:7]) == []
assert sat.receive_bytes(w[7:15]) == []
got = sat.receive_bytes(w[15:])
assert len(got) == 1 and got[0]["seq"] == 4

# 4. Damaged frame (bad CRC)
bad = bytearray(wire(5, 5))
bad[10] ^= 0xFF
assert sat.receive_bytes(bytes(bad)) == []

# 5. Wrong credentials
assert sat.receive_bytes(wire(scid=0x155)) == []

# 6. Good frame carrying a packet with a bad CRC
pkt = bytearray(build_tc_packet(100, 6, 17, 1))
pkt[-1] ^= 0xFF
assert sat.receive_bytes(build_frame(bytes(pkt), 6)) == []

# 7. Pure noise
assert sat.receive_bytes(b"\x01\x02\x03") == []

assert sat.counters.as_dict() == {
    "tc_received": 7, "tc_rejected": 3,
    "frames_accepted": 5, "frames_rejected": 2,
    "packets_accepted": 4, "packets_rejected": 1,
}
print("Satellite decoding check PASSED")