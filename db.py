import sqlite3
from contextlib import contextmanager
from datetime import datetime
from config import DB_PATH


def now():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with connect() as con:
        con.execute('CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, created_at TEXT)')


def create_item(name):
    with connect() as con:
        con.execute('INSERT INTO items(name, created_at) VALUES(?, ?)', (name, now()))


def list_items():
    with connect() as con:
        return [dict(r) for r in con.execute('SELECT * FROM items ORDER BY id DESC').fetchall()]
