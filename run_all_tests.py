import subprocess
import sys

TESTS = [
    "test_packet.py",
    "test_frame.py",
    "test_db.py",
    "test_satellite.py",
    "test_onboard.py",
    "test_compliance.py",
    "test_integration.py",
]

failed = []
for name in TESTS:
    result = subprocess.run([sys.executable, name], capture_output=True, text=True)
    ok = result.returncode == 0 and "FAIL:" not in result.stdout
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        failed.append(name)
        print(result.stdout[-800:])
        print(result.stderr[-800:])

print()
if failed:
    print(f"{len(failed)} test(s) FAILED: {', '.join(failed)}")
else:
    print("ALL TESTS PASSED")