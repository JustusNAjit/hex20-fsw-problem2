import tkinter as tk
from tkinter import ttk

from command_db import init_db, get_apids, get_commands, get_parameters
from sender import send_command

init_db()

root = tk.Tk()
root.title("HEX20 Ground Telecommanding")
root.geometry("540x460")

apid_map = {f"{a} - {n}": a for a, n in get_apids()}
cmd_map = {}
entries = []

ttk.Label(root, text="APID").pack(anchor="w", padx=10, pady=(10, 0))
apid_box = ttk.Combobox(root, values=list(apid_map), state="readonly", width=45)
apid_box.pack(anchor="w", padx=10)

ttk.Label(root, text="Command (service, subtype)").pack(anchor="w", padx=10, pady=(10, 0))
cmd_box = ttk.Combobox(root, state="readonly", width=45)
cmd_box.pack(anchor="w", padx=10)

params_frame = ttk.Frame(root)
params_frame.pack(anchor="w", padx=10, pady=10, fill="x")

status = tk.Label(root, text="", wraplength=500, justify="left", anchor="w")
status.pack(anchor="w", padx=10, pady=10)


def show(message, error=False):
    status.config(text=message, fg="red" if error else "green")


def clear_params():
    for w in params_frame.winfo_children():
        w.destroy()
    entries.clear()


def on_apid(event=None):
    cmd_map.clear()
    apid = apid_map[apid_box.get()]
    for service, subtype, name in get_commands(apid):
        cmd_map[f"ST[{service},{subtype}] {name}"] = (service, subtype)
    cmd_box["values"] = list(cmd_map)
    cmd_box.set("")
    clear_params()
    show("")


def on_cmd(event=None):
    clear_params()
    apid = apid_map[apid_box.get()]
    service, subtype = cmd_map[cmd_box.get()]
    params = get_parameters(apid, service, subtype)
    if not params:
        ttk.Label(params_frame, text="This command has no parameters.").grid(row=0, column=0)
    for i, (name, ptype, pmin, pmax, unit) in enumerate(params):
        ttk.Label(params_frame,
                  text=f"{name}  ({ptype}, {pmin:g} to {pmax:g} {unit})").grid(
            row=i, column=0, sticky="w", padx=(0, 10), pady=3)
        entry = ttk.Entry(params_frame, width=14)
        entry.grid(row=i, column=1)
        entries.append(entry)
    show("")


def on_send():
    if not apid_box.get() or not cmd_box.get():
        show("Please choose an APID and a command first.", error=True)
        return
    apid = apid_map[apid_box.get()]
    service, subtype = cmd_map[cmd_box.get()]
    try:
        r = send_command(apid, service, subtype, [e.get() for e in entries])
    except ValueError as err:
        show(f"ERROR: {err}", error=True)
    except OSError as err:
        show(f"Could not send. Is the receiver running?\n({err})", error=True)
    else:
        show(f"Sent OK: APID {apid} ST[{service},{subtype}] "
             f"packet_seq={r['packet_seq']} frame_seq={r['frame_seq']}\n{r['hex']}")


apid_box.bind("<<ComboboxSelected>>", on_apid)
cmd_box.bind("<<ComboboxSelected>>", on_cmd)
ttk.Button(root, text="Send", command=on_send).pack(anchor="w", padx=10)

root.mainloop()