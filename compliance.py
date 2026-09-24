from packet import crc16


def check_packet(raw, expect_type):
    """Check every header field. Returns a list of problems (empty = compliant).
    expect_type: 1 for a telecommand packet, 0 for a telemetry packet."""
    kind = "telecommand" if expect_type == 1 else "telemetry"
    secondary_len = 5 if expect_type == 1 else 13
    if len(raw) < 6 + secondary_len + 2:
        return [f"too short to be a {kind} packet"]

    problems = []
    word1 = int.from_bytes(raw[0:2], "big")
    word2 = int.from_bytes(raw[2:4], "big")
    length = int.from_bytes(raw[4:6], "big")

    if (word1 >> 13) != 0:
        problems.append("packet version must be 0")
    if ((word1 >> 12) & 1) != expect_type:
        problems.append(f"packet type must be {expect_type} ({kind})")
    if ((word1 >> 11) & 1) != 1:
        problems.append("secondary header flag must be 1")
    if (word2 >> 14) != 0b11:
        problems.append("sequence flags must be 11 (unsegmented)")
    if length != len(raw) - 7:
        problems.append("packet data length field is wrong")
    if crc16(raw[:-2]) != int.from_bytes(raw[-2:], "big"):
        problems.append("CRC is wrong")
    if (raw[6] >> 4) != 2:
        problems.append("PUS version must be 2 (first secondary header byte 0x2_)")
    if raw[7] == 0:
        problems.append("service type must not be 0")
    if raw[8] == 0:
        problems.append("message subtype must not be 0")

    if expect_type == 0 and raw[7] == 1:            # ST[1] verification reports
        data = raw[19:-2]
        if len(data) < 4:
            problems.append("ST[1] report must contain a 4-byte request ID")
        if raw[8] in (2, 4, 6, 8, 10) and len(data) < 6:
            problems.append("ST[1] failure report must contain a failure code")
    return problems