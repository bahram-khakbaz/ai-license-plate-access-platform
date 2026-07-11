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


def _columns(con, table):
    return {r['name'] for r in con.execute(f'PRAGMA table_info({table})').fetchall()}


def _add_column(con, table, name, ddl):
    if name not in _columns(con, table):
        con.execute(f'ALTER TABLE {table} ADD COLUMN {ddl}')


def setup():
    with db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS sites (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, code TEXT UNIQUE, description TEXT, enabled INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT)')
        con.execute('CREATE TABLE IF NOT EXISTS vehicles (id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER, plate TEXT NOT NULL, driver_name TEXT, phone TEXT, unit TEXT, vehicle_model TEXT, vehicle_color TEXT, status TEXT, created_at TEXT, updated_at TEXT, UNIQUE(site_id, plate))')
        con.execute('CREATE TABLE IF NOT EXISTS cameras (id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER, name TEXT, stream_url TEXT, gate_role TEXT, enabled INTEGER, created_at TEXT, updated_at TEXT)')
        con.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER, plate TEXT, gate_role TEXT, source TEXT, operator_name TEXT, note TEXT, plate_color TEXT, score REAL, image_path TEXT, crop_path TEXT, created_at TEXT)')
        _add_column(con, 'vehicles', 'site_id', 'site_id INTEGER')
        _add_column(con, 'cameras', 'site_id', 'site_id INTEGER')
        _add_column(con, 'events', 'site_id', 'site_id INTEGER')
        row = con.execute('SELECT id FROM sites ORDER BY id LIMIT 1').fetchone()
        if not row:
            stamp = ts()
            con.execute('INSERT INTO sites(name, code, description, enabled, created_at, updated_at) VALUES(?,?,?,?,?,?)', ('Default Site', 'default', 'Default monitoring site', 1, stamp, stamp))
        default_id = default_site_id(con)
        con.execute('UPDATE vehicles SET site_id=? WHERE site_id IS NULL', (default_id,))
        con.execute('UPDATE cameras SET site_id=? WHERE site_id IS NULL', (default_id,))
        con.execute('UPDATE events SET site_id=? WHERE site_id IS NULL', (default_id,))


def default_site_id(con=None):
    own = con is None
    if own:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
    try:
        row = con.execute('SELECT id FROM sites WHERE enabled=1 ORDER BY id LIMIT 1').fetchone()
        if row:
            return row['id']
        row = con.execute('SELECT id FROM sites ORDER BY id LIMIT 1').fetchone()
        return row['id'] if row else 1
    finally:
        if own:
            con.close()


def clean_plate(value):
    return (value or '').replace(' ', '').replace('-', '').strip()


def site_id(value=None):
    if value and value != 'all':
        try:
            return int(value)
        except Exception:
            pass
    return default_site_id()


def sites(active_only=False, enabled_only=None):
    if enabled_only is not None:
        active_only = enabled_only
    with db() as con:
        q = 'SELECT * FROM sites'
        if active_only:
            q += ' WHERE enabled=1'
        q += ' ORDER BY id ASC'
        return [dict(r) for r in con.execute(q).fetchall()]


def save_site(data):
    stamp = ts()
    name = (data.get('name') or '').strip()
    code = (data.get('code') or '').strip() or None
    description = (data.get('description') or '').strip()
    enabled = 1 if str(data.get('enabled', '1')).lower() in ('1', 'true', 'on', 'yes') else 0
    sid = data.get('id')
    with db() as con:
        if sid:
            con.execute('UPDATE sites SET name=?, code=?, description=?, enabled=?, updated_at=? WHERE id=?', (name, code, description, enabled, stamp, sid))
        else:
            con.execute('INSERT INTO sites(name, code, description, enabled, created_at, updated_at) VALUES(?,?,?,?,?,?)', (name, code, description, enabled, stamp, stamp))


def toggle_site(sid):
    with db() as con:
        row = con.execute('SELECT enabled FROM sites WHERE id=?', (sid,)).fetchone()
        if row:
            new_value = 0 if row['enabled'] else 1
            con.execute('UPDATE sites SET enabled=?, updated_at=? WHERE id=?', (new_value, ts(), sid))


def save_vehicle(data):
    sid = site_id(data.get('site_id'))
    plate = clean_plate(data.get('plate'))
    if not plate:
        return False
    stamp = ts()
    row = (sid, plate, data.get('driver_name'), data.get('phone'), data.get('unit'), data.get('vehicle_model'), data.get('vehicle_color'), data.get('status') or 'unknown', stamp)
    with db() as con:
        found = con.execute('SELECT id FROM vehicles WHERE site_id=? AND plate=?', (sid, plate)).fetchone()
        if found:
            con.execute('UPDATE vehicles SET driver_name=?, phone=?, unit=?, vehicle_model=?, vehicle_color=?, status=?, updated_at=? WHERE site_id=? AND plate=?', row[2:] + (sid, plate))
        else:
            con.execute('INSERT INTO vehicles(site_id,plate,driver_name,phone,unit,vehicle_model,vehicle_color,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)', row + (stamp,))
    return True


def vehicles(site=None):
    sid = site_id(site)
    with db() as con:
        return [dict(r) for r in con.execute('SELECT v.*, s.name site_name FROM vehicles v LEFT JOIN sites s ON s.id=v.site_id WHERE v.site_id=? ORDER BY v.id DESC', (sid,)).fetchall()]


def save_camera(data):
    stamp = ts()
    with db() as con:
        con.execute('INSERT INTO cameras(site_id,name,stream_url,gate_role,enabled,created_at,updated_at) VALUES(?,?,?,?,?,?,?)', (site_id(data.get('site_id')), data.get('name'), data.get('stream_url'), data.get('gate_role') or 'entry', 1, stamp, stamp))


def cameras(site=None):
    sid = site_id(site)
    with db() as con:
        return [dict(r) for r in con.execute('SELECT c.id,c.name,c.gate_role,c.enabled,c.created_at,c.updated_at,s.name site_name FROM cameras c LEFT JOIN sites s ON s.id=c.site_id WHERE c.site_id=? ORDER BY c.id DESC', (sid,)).fetchall()]


def save_event(data):
    with db() as con:
        con.execute('INSERT INTO events(site_id,plate,gate_role,source,operator_name,note,plate_color,score,image_path,crop_path,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (site_id(data.get('site_id')), clean_plate(data.get('plate')), data.get('gate_role') or 'entry', data.get('source') or 'manual', data.get('operator_name'), data.get('note'), data.get('plate_color') or 'white', float(data.get('score') or 1), data.get('image_path'), data.get('crop_path'), ts()))


def events(limit=50, site=None):
    sid = site_id(site)
    with db() as con:
        return [dict(r) for r in con.execute('SELECT e.*, v.driver_name, v.status, s.name site_name FROM events e LEFT JOIN vehicles v ON v.plate=e.plate AND v.site_id=e.site_id LEFT JOIN sites s ON s.id=e.site_id WHERE e.site_id=? ORDER BY e.id DESC LIMIT ?', (sid, limit)).fetchall()]


def stats(site=None):
    sid = site_id(site)
    recent = events(20, sid)
    with db() as con:
        total = con.execute('SELECT COUNT(*) c FROM events WHERE site_id=?', (sid,)).fetchone()['c']
        entry = con.execute("SELECT COUNT(*) c FROM events WHERE site_id=? AND gate_role='entry'", (sid,)).fetchone()['c']
        exit_count = con.execute("SELECT COUNT(*) c FROM events WHERE site_id=? AND gate_role='exit'", (sid,)).fetchone()['c']
        vehicle_total = con.execute('SELECT COUNT(*) c FROM vehicles WHERE site_id=?', (sid,)).fetchone()['c']
    alerts = [r for r in recent if r.get('status') in (None, '', 'unknown', 'review')][:6]
    return {'site_id': sid, 'today': {'total': total, 'entries': entry, 'exits': exit_count}, 'vehicles': {'total': vehicle_total}, 'latest': recent[:8], 'alerts': alerts}
