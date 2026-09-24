from command_db import init_db
from sender import send_command, validate_and_encode

init_db()

# 1. An out-of-range value must be blocked
try:
    validate_and_encode(101, 8, 128, [99, 1])
    print("FAIL: out-of-range value was accepted")
except ValueError as e:
    print("OK, rejected:", e)

# 2. Send three different commands
r1 = send_command(100, 17, 1, [])
r2 = send_command(101, 8, 128, [3, 1])
r3 = send_command(102, 8, 128, [2, -1500])
for r in (r1, r2, r3):
    print(f"Sent APID {r['apid']} ST[{r['service']},{r['subtype']}] "
          f"packet_seq={r['packet_seq']} frame_seq={r['frame_seq']}")

# 3. Counters must go up
r4 = send_command(100, 17, 1, [])
print("APID 100 packet_seq:", r1["packet_seq"], "->", r4["packet_seq"])
assert r4["packet_seq"] == r1["packet_seq"] + 1
assert r4["frame_seq"] == r1["frame_seq"] + 1
print("Sender check PASSED")