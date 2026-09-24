from packet import crc16

START = bytes([0xEB, 0x90])
TAIL = bytes([0xC5] * 7 + [0x79])
SCID = 0x123      # our spacecraft ID (the "credentials")
VCID = 0


def build_frame(packet, frame_seq, scid=SCID, vcid=VCID):
    total = 5 + len(packet) + 2          # header + packet + CRC
    if total > 1024:
        raise ValueError("Frame too long")
    word1 = scid                          # version 0, flags 0, then 10-bit spacecraft ID
    word2 = (vcid << 10) | (total - 1)    # 6-bit channel, 10-bit length
    header = word1.to_bytes(2, "big") + word2.to_bytes(2, "big") + bytes([frame_seq & 0xFF])
    body = header + packet
    body += crc16(body).to_bytes(2, "big")
    return START + body + TAIL


def parse_frame(raw):
    if not raw.startswith(START):
        raise ValueError("Start sequence missing")
    if not raw.endswith(TAIL):
        raise ValueError("Tail sequence missing")
    body = raw[len(START):-len(TAIL)]
    if len(body) < 8:
        raise ValueError("Frame too short")
    word1 = int.from_bytes(body[0:2], "big")
    word2 = int.from_bytes(body[2:4], "big")
    if len(body) != (word2 & 0x3FF) + 1:
        raise ValueError("Frame length field does not match")
    if crc16(body[:-2]) != int.from_bytes(body[-2:], "big"):
        raise ValueError("CRC mismatch")
    if (word1 >> 14) != 0:
        raise ValueError("Wrong frame version")
    if (word1 & 0x3FF) != SCID:
        raise ValueError("Wrong credentials")
    return {
        "scid": word1 & 0x3FF,
        "vcid": word2 >> 10,
        "frame_seq": body[4],
        "packet": body[5:-2],
    }