def crc16(data, crc=0xFFFF):
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return crc

def build_tc_packet(apid, seq, service, subtype, app_data=b"", source_id=0):
    sec = bytes([0x20, service, subtype]) + source_id.to_bytes(2, "big")
    data = sec + app_data
    length = len(data) + 2 - 1
    word1 = (0 << 13) | (1 << 12) | (1 << 11) | apid
    word2 = (0b11 << 14) | seq
    header = word1.to_bytes(2, "big") + word2.to_bytes(2, "big") + length.to_bytes(2, "big")
    packet = header + data
    return packet + crc16(packet).to_bytes(2, "big")

def parse_tc_packet(raw):
    if len(raw) < 13:
        raise ValueError("Packet too short")
    word1 = int.from_bytes(raw[0:2], "big")
    word2 = int.from_bytes(raw[2:4], "big")
    length = int.from_bytes(raw[4:6], "big")
    if (word1 >> 13) != 0:
        raise ValueError("Wrong packet version")
    if ((word1 >> 12) & 1) != 1:
        raise ValueError("Type is not telecommand")
    if len(raw) != 6 + length + 1:
        raise ValueError("Data length field does not match")
    if crc16(raw[:-2]) != int.from_bytes(raw[-2:], "big"):
        raise ValueError("CRC mismatch")
    if raw[6] != 0x20:
        raise ValueError("Wrong PUS version")
    if raw[7] == 0 or raw[8] == 0:
        raise ValueError("Service or subtype is zero")
    return {
        "apid": word1 & 0x7FF,
        "seq": word2 & 0x3FFF,
        "service": raw[7],
        "subtype": raw[8],
        "source_id": int.from_bytes(raw[9:11], "big"),
        "app_data": raw[11:-2],
    }

if __name__ == "__main__":
    assert crc16(b"123456789") == 0x29B1
    print(build_tc_packet(apid=100, seq=1, service=17, subtype=1).hex())