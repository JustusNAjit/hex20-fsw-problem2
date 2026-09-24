from packet import build_tc_packet, parse_tc_packet
from frame import build_frame, parse_frame

pkt = build_tc_packet(apid=100, seq=1, service=17, subtype=1)
wire = build_frame(pkt, frame_seq=5)
print("Frame bytes:", wire.hex())

info = parse_frame(wire)
print("Frame OK, frame_seq =", info["frame_seq"])
print("Packet inside:", parse_tc_packet(info["packet"]))


def expect_reject(name, data):
    try:
        parse_frame(data)
        print("FAIL:", name, "was accepted")
    except ValueError as e:
        print("OK,", name, "rejected:", e)


damaged = bytearray(wire)
damaged[8] ^= 0xFF
expect_reject("damaged frame", bytes(damaged))
expect_reject("missing tail", wire[:-1] + b"\x00")
expect_reject("wrong credentials", build_frame(pkt, 5, scid=0x999))