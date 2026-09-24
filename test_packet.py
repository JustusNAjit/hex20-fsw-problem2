from packet import build_tc_packet, parse_tc_packet

raw = build_tc_packet(apid=100, seq=1, service=17, subtype=1)
print(parse_tc_packet(raw))

bad = bytearray(raw)
bad[8] ^= 0xFF          # damage one byte
try:
    parse_tc_packet(bytes(bad))
    print("FAIL: bad packet was accepted")
except ValueError as e:
    print("Bad packet rejected:", e)