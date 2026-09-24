import json
import os
import socket
import time

from packet import crc16
from satellite import Satellite

ROUTING_FILE = "routing.json"
GROUND_ID = 1

FAIL_UNKNOWN_APID = 1
FAIL_UNKNOWN_COMMAND = 2
FAIL_BAD_PARAMETERS = 3
FAIL_UNKNOWN_REPORT = 4
FAIL_BAD_ADDRESS = 5
FAIL_INTERNAL = 6

COUNTER_ORDER = ["tc_received", "tc_rejected", "frames_accepted",
                 "frames_rejected", "packets_accepted", "packets_rejected"]

# bytes of parameters each ST[8,128] function expects, per APID
FUNCTION_ARG_LEN = {101: 2, 102: 3, 103: 2, 104: 2}


class CommandFailure(Exception):
    """Raised by a handler when a command cannot be executed: (code, message)."""


# ---------- handlers: each returns a list of extra reports ----------

def h_connection_test(ob, p):
    return [ob.build_tm(p["apid"], 17, 2)]


def get_report_id(p):
    if len(p["app_data"]) != 1:
        raise CommandFailure(FAIL_BAD_PARAMETERS, "expected 1 parameter byte")
    report_id = p["app_data"][0]
    if report_id != 1:
        raise CommandFailure(FAIL_UNKNOWN_REPORT, f"unknown report id {report_id}")
    return report_id


def h_hk_enable(ob, p):
    report_id = get_report_id(p)
    ob.hk_enabled.add(report_id)
    return [ob.hk_report(p["apid"], report_id)]


def h_hk_disable(ob, p):
    ob.hk_enabled.discard(get_report_id(p))
    return []


def h_load_memory(ob, p):
    d = p["app_data"]
    if len(d) != 5:
        raise CommandFailure(FAIL_BAD_PARAMETERS, "expected 5 parameter bytes")
    address = int.from_bytes(d[0:4], "big")
    if address >= len(ob.memory):
        raise CommandFailure(FAIL_BAD_ADDRESS, f"address {address} outside memory")
    ob.memory[address] = d[4]
    return []


def h_dump_memory(ob, p):
    d = p["app_data"]
    if len(d) != 5:
        raise CommandFailure(FAIL_BAD_PARAMETERS, "expected 5 parameter bytes")
    address = int.from_bytes(d[0:4], "big")
    length = d[4]
    if length == 0 or address + length > len(ob.memory):
        raise CommandFailure(FAIL_BAD_ADDRESS, "dump range outside memory")
    data = bytes(ob.memory[address:address + length])
    return [ob.build_tm(p["apid"], 6, 6, d[0:4] + bytes([length]) + data)]


def h_function(ob, p):
    expected = FUNCTION_ARG_LEN.get(p["apid"])
    if expected is None or len(p["app_data"]) != expected:
        raise CommandFailure(FAIL_BAD_PARAMETERS, "wrong number of parameter bytes")
    ob.log(f"FUNCTION executed APID={p['apid']} args={p['app_data'].hex()}")
    return []


# ---------- (service, subtype) table for each application ----------

APPLICATIONS = {
    "OBC": {(17, 1): h_connection_test, (3, 1): h_hk_enable, (3, 2): h_hk_disable},
    "EPS": {(17, 1): h_connection_test, (3, 1): h_hk_enable, (8, 128): h_function},
    "ADCS": {(3, 1): h_hk_enable, (6, 5): h_dump_memory, (8, 128): h_function},
    "THERMAL": {(3, 1): h_hk_enable, (3, 2): h_hk_disable, (8, 128): h_function},
    "PAYLOAD": {(17, 1): h_connection_test, (6, 2): h_load_memory, (8, 128): h_function},
    "SPARE": {(17, 1): h_connection_test},
}


# ---------- routing table (APID -> application), stored in routing.json ----------

def default_routing():
    table = {"100": "OBC", "101": "EPS", "102": "ADCS",
             "103": "THERMAL", "104": "PAYLOAD"}
    for apid in range(105, 132):
        table[str(apid)] = "SPARE"
    return table


def load_routing():
    if not os.path.exists(ROUTING_FILE):
        with open(ROUTING_FILE, "w") as f:
            json.dump(default_routing(), f, indent=2)
    with open(ROUTING_FILE) as f:
        return {int(k): v for k, v in json.load(f).items()}


def request_id(p):
    """4 bytes that identify the command a report refers to."""
    word1 = (0 << 13) | (1 << 12) | (1 << 11) | p["apid"]
    word2 = (0b11 << 14) | p["seq"]
    return word1.to_bytes(2, "big") + word2.to_bytes(2, "big")


# ---------- the onboard software ----------

class Onboard(Satellite):
    def setup(self):
        self.routing = load_routing()
        self.tm_seq = {}
        self.tm_type_count = {}
        self.memory = bytearray(65536)
        self.hk_enabled = set()
        self.last_report_ms = 0.0

    def build_tm(self, apid, service, subtype, data=b""):
        seq = self.tm_seq.get(apid, 0)
        self.tm_seq[apid] = (seq + 1) % 16384
        key = (apid, service, subtype)
        count = self.tm_type_count.get(key, 0)
        self.tm_type_count[key] = (count + 1) % 65536
        now = time.time()
        secs = int(now)
        millis = int((now - secs) * 1000)
        sec_header = (bytes([0x20, service, subtype])
                      + count.to_bytes(2, "big")
                      + GROUND_ID.to_bytes(2, "big")
                      + secs.to_bytes(4, "big")
                      + millis.to_bytes(2, "big"))
        body = sec_header + data
        length = len(body) + 2 - 1
        word1 = (0 << 13) | (0 << 12) | (1 << 11) | apid     # type 0 = telemetry
        word2 = (0b11 << 14) | seq
        header = (word1.to_bytes(2, "big") + word2.to_bytes(2, "big")
                  + length.to_bytes(2, "big"))
        packet = header + body
        return packet + crc16(packet).to_bytes(2, "big")

    def hk_report(self, apid, report_id):
        c = self.counters.as_dict()
        data = bytes([report_id])
        for name in COUNTER_ORDER:
            data += c[name].to_bytes(4, "big")
        return self.build_tm(apid, 3, 25, data)

    def report_failure(self, p, subtype, code, message):
        self.log(f"COMMAND FAILED APID={p['apid']} ST[{p['service']},{p['subtype']}] "
                 f"code={code} {message}")
        return self.build_tm(p["apid"], 1, subtype, request_id(p) + code.to_bytes(2, "big"))

    def dispatch(self, p, t0):
        apid = p["apid"]
        rid = request_id(p)
        app = self.routing.get(apid)
        if app is None:
            self.counters.tc_rejected += 1
            reports = [self.report_failure(p, 2, FAIL_UNKNOWN_APID,
                                           f"no route for APID {apid}")]
        else:
            handler = APPLICATIONS.get(app, {}).get((p["service"], p["subtype"]))
            if handler is None:
                self.counters.tc_rejected += 1
                reports = [self.report_failure(
                    p, 2, FAIL_UNKNOWN_COMMAND,
                    f"{app} has no command ST[{p['service']},{p['subtype']}]")]
            else:
                reports = [self.build_tm(apid, 1, 3, rid)]         # ST[1,3] handler entered
                try:
                    reports += handler(self, p)
                    reports.append(self.build_tm(apid, 1, 7, rid))  # ST[1,7] success
                except CommandFailure as e:
                    code, message = e.args
                    reports.append(self.report_failure(p, 8, code, message))
                except Exception as e:
                    reports.append(self.report_failure(p, 8, FAIL_INTERNAL,
                                                       f"internal error: {e}"))
        self.last_report_ms = (time.perf_counter() - t0) * 1000
        return reports

    def process(self, data):
        """Raw uplink bytes in, list of report packets (bytes) out."""
        t0 = time.perf_counter()
        replies = []
        for p in self.receive_bytes(data):
            replies += self.dispatch(p, t0)
        for r in replies:
            apid = int.from_bytes(r[0:2], "big") & 0x7FF
            self.log(f"TM SENT ST[{r[7]},{r[8]}] APID={apid}")
        return replies


def create_onboard():
    ob = Onboard()
    ob.setup()
    return ob


def run_server(host="127.0.0.1", port=5000):
    ob = create_onboard()
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen()
    server.settimeout(1)
    print(f"Onboard software waiting on port {port}... (press Ctrl+C to stop)")
    try:
        while True:
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            with conn:
                conn.settimeout(2)
                try:
                    while True:
                        try:
                            data = conn.recv(4096)
                        except socket.timeout:
                            break
                        if not data:
                            break
                        for report in ob.process(data):
                            conn.sendall(report)
                except OSError:
                    print("(ground link closed before all reports were sent)")
            print("Counters:", ob.counters.as_dict())
    except KeyboardInterrupt:
        print("\nOnboard software stopped.")