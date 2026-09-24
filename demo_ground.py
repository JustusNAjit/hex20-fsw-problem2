import socket

from onboard import COUNTER_ORDER
from packet import build_tc_packet
from frame import build_frame

NAMES = {
    (1, 2): "ST[1,2]  REJECTED (could not route)",
    (1, 3): "ST[1,3]  handler started",
    (1, 7): "ST[1,7]  completed successfully",
    (1, 8): "ST[1,8]  FAILED",
    (17, 2): "ST[17,2] connection test reply",
    (3, 25): "ST[3,25] housekeeping report",
    (6, 6): "ST[6,6]  memory dump data",
}


def send_and_listen(apid, service, subtype, app_data=b""):
    pkt = build_tc_packet(apid, 1, service, subtype, app_data)
    wire = build_frame(pkt, 1)
    data = b""
    with socket.create_connection(("127.0.0.1", 5000), timeout=3) as s:
        s.sendall(wire)
        s.settimeout(1)
        try:
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass
    reports = []
    while len(data) >= 6:
        total = int.from_bytes(data[4:6], "big") + 7
        reports.append(data[:total])
        data = data[total:]
    return reports


def show(apid, service, subtype, app_data=b""):
    print(f"\n--- Sent to APID {apid}: ST[{service},{subtype}] ---")
    for r in send_and_listen(apid, service, subtype, app_data):
        kind = (r[7], r[8])
        print("  ", NAMES.get(kind, kind))
        if kind in ((1, 8), (1, 2)):
            print("      failure code:", int.from_bytes(r[23:25], "big"))
        if kind == (3, 25):
            values = [int.from_bytes(r[20 + 4 * i:24 + 4 * i], "big")
                      for i in range(len(COUNTER_ORDER))]
            print("      counters:", dict(zip(COUNTER_ORDER, values)))


show(100, 17, 1)               # connection test
show(100, 3, 1, bytes([1]))    # housekeeping report with counters
show(100, 3, 1, bytes([5]))    # unknown report id, so it fails
show(500, 17, 1)               # APID with no route