import json
import logging
import os
import socket
import struct
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from command_db import get_commands, get_parameters
from packet import build_tc_packet
from frame import build_frame

COUNTER_FILE = "counters.json"
LOG_FILE = "tc_log.txt"

FORMATS = {"uint8": ">B", "uint16": ">H", "uint32": ">I", "int16": ">h"}

log = logging.getLogger("tc_log")
log.setLevel(logging.INFO)
if not log.handlers:
    _h = RotatingFileHandler(LOG_FILE, maxBytes=100_000, backupCount=3)
    _h.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(_h)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_and_encode(apid, service, subtype, values):
    params = get_parameters(apid, service, subtype)
    if len(values) != len(params):
        raise ValueError(f"Expected {len(params)} parameter(s), got {len(values)}")
    out = b""
    for (name, ptype, pmin, pmax, unit), raw in zip(params, values):
        try:
            num = float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"Parameter '{name}' must be a number")
        if num != int(num):
            raise ValueError(f"Parameter '{name}' must be a whole number")
        num = int(num)
        if not pmin <= num <= pmax:
            raise ValueError(
                f"Parameter '{name}' = {num} is out of range ({pmin:g} to {pmax:g} {unit})")
        out += struct.pack(FORMATS[ptype], num)
    return out


def load_counters():
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE) as f:
            return json.load(f)
    return {}


def save_counters(counters):
    with open(COUNTER_FILE, "w") as f:
        json.dump(counters, f, indent=2)


def send_command(apid, service, subtype, values, host="127.0.0.1", port=5000):
    known = [(s, st) for s, st, _ in get_commands(apid)]
    if (service, subtype) not in known:
        raise ValueError(f"APID {apid} has no command ST[{service},{subtype}]")
    app_data = validate_and_encode(apid, service, subtype, values)

    counters = load_counters()
    c = counters.get(str(apid), {"packet_seq": 0, "frame_seq": 0})
    packet = build_tc_packet(apid, c["packet_seq"], service, subtype, app_data)
    wire = build_frame(packet, c["frame_seq"])

    try:
        with socket.create_connection((host, port), timeout=3) as s:
            s.sendall(wire)
    except OSError as e:
        log.info(f"{utc_now()} APID={apid} ST[{service},{subtype}] SEND_FAILED {e}")
        raise

    log.info(f"{utc_now()} APID={apid} ST[{service},{subtype}] "
             f"packet_seq={c['packet_seq']} frame_seq={c['frame_seq']} "
             f"params={list(values)} hex={wire.hex()}")

    result = {"apid": apid, "service": service, "subtype": subtype,
              "packet_seq": c["packet_seq"], "frame_seq": c["frame_seq"],
              "hex": wire.hex()}
    counters[str(apid)] = {"packet_seq": (c["packet_seq"] + 1) % 16384,
                           "frame_seq": (c["frame_seq"] + 1) % 256}
    save_counters(counters)
    return result