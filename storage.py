import sqlite3
from contextlib import contextmanager
from datetime import datetime
from config import DB_PATH


def ts():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


@contextmanager
def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def setup():
    with db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS vehicles (id INTEGER PRIMARY KEY AUTOINCREMENT, plate TEXT UNIQUE, driver_name TEXT, phone TEXT, unit TEXT, vehicle_model TEXT, vehicle_color TEXT, status TEXT, created_at TEXT, updated_at TEXT)')
        con.execute('CREATE TABLE IF NOT EXISTS cameras (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, stream_url TEXT, gate_role TEXT, enabled INTEGER, created_at TEXT, updated_at TEXT)')
        con.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, plate TEXT, gate_role TEXT, source TEXT, operator_name TEXT, note TEXT, plate_color TEXT, score REAL, image_path TEXT, crop_path TEXT, created_at TEXT)')


def clean_plate(value):
    return (value or '').replace(' ', '').replace('-', '').strip()


def save_vehicle(data):
    plate = clean_plate(data.get('plate'))
    stamp = ts()
    with db() as con:
        found = con.execute('SELECT id FROM vehicles WHERE plate=?', (plate,)).fetchone()
        row = (plate, data.get('driver_name'), data.get('phone'), data.get('unit'), data.get('vehicle_model'), data.get('vehicle_color'), data.get('status') or 'unknown', stamp)
        if found:
            con.execute('UPDATE vehicles SET driver_name=?, phone=?, unit=?, vehicle_model=?, vehicle_color=?, status=?, updated_at=? WHERE plate=?', row[1:] + (plate,))
        else:
            con.execute('INSERT INTO vehicles(plate,driver_name,phone,unit,vehicle_model,vehicle_color,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)', row + (stamp,))


def vehicles():
    with db() as con:
        return [dict(r) for r in con.execute('SELECT * FROM vehicles ORDER BY id DESC').fetchall()]


def save_camera(data):
    stamp = ts()
    with db() as con:
        con.execute('INSERT INTO cameras(name,stream_url,gate_role,enabled,created_at,updated_at) VALUES(?,?,?,?,?,?)', (data.get('name'), data.get('stream_url'), data.get('gate_role') or 'entry', 1, stamp, stamp))


def cameras():
    with db() as con:
        return [dict(r) for r in con.execute('SELECT id,name,gate_role,enabled,created_at,updated_at FROM cameras ORDER BY id DESC').fetchall()]


def save_event(data):
    with db() as con:
        con.execute('INSERT INTO events(plate,gate_role,source,operator_name,note,plate_color,score,image_path,crop_path,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)', (clean_plate(data.get('plate')), data.get('gate_role') or 'entry', data.get('source') or 'manual', data.get('operator_name'), data.get('note'), data.get('plate_color') or 'white', float(data.get('score') or 1), data.get('image_path'), data.get('crop_path'), ts()))


def events(limit=50):
    with db() as con:
        return [dict(r) for r in con.execute('SELECT e.*, v.driver_name, v.status FROM events e LEFT JOIN vehicles v ON v.plate=e.plate ORDER BY e.id DESC LIMIT ?', (limit,)).fetchall()]


def stats():
    recent = events(20)
    with db() as con:
        total = con.execute('SELECT COUNT(*) c FROM events').fetchone()['c']
        entry = con.execute("SELECT COUNT(*) c FROM events WHERE gate_role='entry'").fetchone()['c']
        exit_count = con.execute("SELECT COUNT(*) c FROM events WHERE gate_role='exit'").fetchone()['c']
        vehicle_total = con.execute('SELECT COUNT(*) c FROM vehicles').fetchone()['c']
    alerts = [r for r in recent if r.get('status') in (None, '', 'unknown', 'blocked')][:6]
    return {'today': {'total': total, 'entries': entry, 'exits': exit_count}, 'vehicles': {'total': vehicle_total}, 'latest': recent[:8], 'alerts': alerts}
