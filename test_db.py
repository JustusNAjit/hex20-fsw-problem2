from command_db import init_db, get_apids, get_commands, get_parameters

init_db()
apids = get_apids()
for apid, name in apids:
    cmds = get_commands(apid)
    print(f"APID {apid} ({name}): {len(cmds)} commands")
    for service, subtype, cname in cmds:
        print(f"   ST[{service},{subtype}] {cname}")
        for p in get_parameters(apid, service, subtype):
            print("      param:", p)

assert len(apids) >= 5
assert all(len(get_commands(a)) >= 3 for a, _ in apids)
assert get_commands(100) != get_commands(101)   # each APID shows its own commands
print("Database check PASSED")