import socket
import threading
import time

from command_db import init_db
from sender import send_command
from onboard import create_onboard

init_db()
ob = create_onboard()
PORT = 5055

server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("127.0.0.1", PORT))
server.listen()


def serve():
    while True:
        conn, _ = server.accept()
        with conn:
            data = conn.recv(4096)
            try:
                for report in ob.process(data):
                    conn.sendall(report)
            except OSError:
                pass


threading.Thread(target=serve, daemon=True).start()


def wait_for(n):
    for _ in range(60):
        if ob.counters.packets_accepted >= n:
            return
        time.sleep(0.05)


def send(apid, service, subtype, values):
    return send_command(apid, service, subtype, values, port=PORT)


# 1. Three distinct commands are received and accepted by the satellite
r1 = send(100, 17, 1, [])
r2 = send(101, 8, 128, [3, 1])
r3 = send(104, 6, 2, [10, 7])
wait_for(3)
assert ob.counters.packets_accepted == 3, ob.counters.as_dict()
print("3 distinct commands received by the satellite")

# 2. Packet and frame counters go up on the next send to the same APID
r4 = send(100, 17, 1, [])
wait_for(4)
assert r4["packet_seq"] == (r1["packet_seq"] + 1) % 16384
assert r4["frame_seq"] == (r1["frame_seq"] + 1) % 256
print("Counters incremented correctly:", r1["packet_seq"], "->", r4["packet_seq"])

# 3. An out-of-range value is blocked and never reaches the satellite
try:
    send(101, 8, 128, [99, 1])
    raise AssertionError("out-of-range value was accepted")
except ValueError as e:
    print("Out-of-range blocked:", e)
time.sleep(0.3)
assert ob.counters.tc_received == 4
assert ob.counters.tc_rejected == 0

print("Integration check PASSED")