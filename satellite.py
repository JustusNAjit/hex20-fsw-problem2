import socket
from datetime import datetime, timezone

from frame import START, TAIL, parse_frame
from packet import parse_tc_packet

MAX_FRAME = len(START) + 1024 + len(TAIL)
SAT_LOG = "satellite_log.txt"


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Counters:
    def __init__(self):
        self.tc_received = 0
        self.tc_rejected = 0
        self.frames_accepted = 0
        self.frames_rejected = 0
        self.packets_accepted = 0
        self.packets_rejected = 0

    def as_dict(self):
        return dict(self.__dict__)


class FrameExtractor:
    """State machine: turns a stream of bytes into complete raw frames."""
    SEARCH_START = "SEARCH_START"
    COLLECT = "COLLECT"

    def __init__(self):
        self.state = self.SEARCH_START
        self.buf = bytearray()
        self.discarded = []

    def feed(self, data):
        self.buf += data
        frames = []
        while True:
            if self.state == self.SEARCH_START:
                i = self.buf.find(START)
                if i < 0:
                    if len(self.buf) > 1:
                        self.discarded.append(
                            (f"{len(self.buf) - 1} noise bytes discarded", False))
                        del self.buf[:-1]
                    break
                if i > 0:
                    self.discarded.append((f"{i} noise bytes discarded", False))
                    del self.buf[:i]
                self.state = self.COLLECT
            if self.state == self.COLLECT:
                j = self.buf.find(TAIL, len(START))
                if j >= 0:
                    end = j + len(TAIL)
                    frames.append(bytes(self.buf[:end]))
                    del self.buf[:end]
                    self.state = self.SEARCH_START
                    continue
                if len(self.buf) > MAX_FRAME:
                    self.discarded.append(("no tail sequence found, frame dropped", True))
                    del self.buf[:len(START)]
                    self.state = self.SEARCH_START
                    continue
                break
        return frames


class Satellite:
    def __init__(self):
        self.counters = Counters()
        self.extractor = FrameExtractor()

    def log(self, msg):
        line = f"{utc_now()} {msg}"
        print(line)
        with open(SAT_LOG, "a") as f:
            f.write(line + "\n")

    def receive_bytes(self, data):
        accepted = []
        for raw in self.extractor.feed(data):
            pkt = self.handle_frame(raw)
            if pkt:
                accepted.append(pkt)
        for msg, was_frame in self.extractor.discarded:
            self.log("DISCARD " + msg)
            if was_frame:
                c = self.counters
                c.tc_received += 1
                c.frames_rejected += 1
                c.tc_rejected += 1
        self.extractor.discarded.clear()
        return accepted

    def handle_frame(self, raw):
        c = self.counters
        c.tc_received += 1
        try:
            finfo = parse_frame(raw)
        except ValueError as e:
            c.frames_rejected += 1
            c.tc_rejected += 1
            self.log(f"FRAME REJECTED: {e}")
            return None
        c.frames_accepted += 1
        try:
            pinfo = parse_tc_packet(finfo["packet"])
        except ValueError as e:
            c.packets_rejected += 1
            c.tc_rejected += 1
            self.log(f"PACKET REJECTED: {e}")
            return None
        c.packets_accepted += 1
        pinfo["frame_seq"] = finfo["frame_seq"]
        self.log(f"ACCEPTED APID={pinfo['apid']} ST[{pinfo['service']},{pinfo['subtype']}] "
                 f"packet_seq={pinfo['seq']} frame_seq={pinfo['frame_seq']}")
        return pinfo


def run_server(host="127.0.0.1", port=5000):
    sat = Satellite()
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen()
    server.settimeout(1)
    print(f"Satellite waiting on port {port}... (press Ctrl+C to stop)")
    try:
        while True:
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            with conn:
                conn.settimeout(2)
                while True:
                    try:
                        data = conn.recv(4096)
                    except socket.timeout:
                        break
                    if not data:
                        break
                    sat.receive_bytes(data)
            print("Counters:", sat.counters.as_dict())
    except KeyboardInterrupt:
        print("\nSatellite stopped.")


if __name__ == "__main__":
    run_server()