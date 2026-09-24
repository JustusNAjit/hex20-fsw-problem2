import sqlite3

DB_FILE = "commands.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS apid (
    apid INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS command (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    apid INTEGER NOT NULL REFERENCES apid(apid),
    service INTEGER NOT NULL,
    subtype INTEGER NOT NULL,
    name TEXT NOT NULL,
    UNIQUE (apid, service, subtype)
);
CREATE TABLE IF NOT EXISTS parameter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id INTEGER NOT NULL REFERENCES command(id),
    position INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    min_value REAL NOT NULL,
    max_value REAL NOT NULL,
    unit TEXT NOT NULL
);
"""

# apid: (name, [(service, subtype, command name, [(param, type, min, max, unit)])])
SEED = {
    100: ("OBC", [
        (17, 1, "Connection test", []),
        (3, 1, "Enable housekeeping report", [("report_id", "uint8", 1, 10, "id")]),
        (3, 2, "Disable housekeeping report", [("report_id", "uint8", 1, 10, "id")]),
    ]),
    101: ("EPS", [
        (17, 1, "Connection test", []),
        (3, 1, "Enable housekeeping report", [("report_id", "uint8", 1, 10, "id")]),
        (8, 128, "Switch power line", [("line_id", "uint8", 1, 8, "id"),
                                       ("state", "uint8", 0, 1, "0=off 1=on")]),
    ]),
    102: ("ADCS", [
        (3, 1, "Enable housekeeping report", [("report_id", "uint8", 1, 10, "id")]),
        (6, 5, "Dump memory", [("address", "uint32", 0, 65535, "addr"),
                               ("length", "uint8", 1, 64, "bytes")]),
        (8, 128, "Set wheel speed", [("wheel_id", "uint8", 1, 4, "id"),
                                     ("speed", "int16", -6000, 6000, "rpm")]),
    ]),
    103: ("THERMAL", [
        (3, 1, "Enable housekeeping report", [("report_id", "uint8", 1, 10, "id")]),
        (3, 2, "Disable housekeeping report", [("report_id", "uint8", 1, 10, "id")]),
        (8, 128, "Set heater setpoint", [("setpoint", "int16", -40, 85, "degC")]),
    ]),
    104: ("PAYLOAD", [
        (17, 1, "Connection test", []),
        (6, 2, "Load memory", [("address", "uint32", 0, 65535, "addr"),
                               ("value", "uint8", 0, 255, "raw")]),
        (8, 128, "Start capture", [("duration", "uint16", 1, 3600, "s")]),
    ]),
}


def init_db(db_file=DB_FILE):
    conn = sqlite3.connect(db_file)
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM apid").fetchone()[0] == 0:
        for apid, (name, commands) in SEED.items():
            conn.execute("INSERT INTO apid VALUES (?, ?)", (apid, name))
            for service, subtype, cname, params in commands:
                cur = conn.execute(
                    "INSERT INTO command (apid, service, subtype, name) VALUES (?, ?, ?, ?)",
                    (apid, service, subtype, cname))
                for pos, (pname, ptype, pmin, pmax, unit) in enumerate(params):
                    conn.execute(
                        "INSERT INTO parameter (command_id, position, name, type, "
                        "min_value, max_value, unit) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (cur.lastrowid, pos, pname, ptype, pmin, pmax, unit))
        conn.commit()
    conn.close()


def _query(sql, args=(), db_file=DB_FILE):
    conn = sqlite3.connect(db_file)
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return rows


def get_apids(db_file=DB_FILE):
    return _query("SELECT apid, name FROM apid ORDER BY apid", (), db_file)


def get_commands(apid, db_file=DB_FILE):
    return _query("SELECT service, subtype, name FROM command "
                  "WHERE apid = ? ORDER BY service, subtype", (apid,), db_file)


def get_parameters(apid, service, subtype, db_file=DB_FILE):
    return _query(
        "SELECT p.name, p.type, p.min_value, p.max_value, p.unit "
        "FROM parameter p JOIN command c ON p.command_id = c.id "
        "WHERE c.apid = ? AND c.service = ? AND c.subtype = ? "
        "ORDER BY p.position", (apid, service, subtype), db_file)