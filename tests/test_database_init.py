"""Smoke tests for DatabaseManager.__init__, schema creation, and seeding."""

import os
import sqlite3
import tempfile

from dc_shiftmaster.database import DatabaseManager


def _make_db():
    """Create a DatabaseManager with a temp file and return (db, path)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)  # let DatabaseManager create it fresh
    return DatabaseManager(path), path


def test_tables_created():
    db, path = _make_db()
    cur = db.conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    db.conn.close()
    os.unlink(path)
    assert "overrides" in tables
    assert "shift_windows" in tables
    assert "teammates" in tables


def test_default_shift_windows_seeded():
    db, path = _make_db()
    cur = db.conn.cursor()
    cur.execute("SELECT shift_type, start_time, end_time FROM shift_windows ORDER BY shift_type")
    rows = cur.fetchall()
    db.conn.close()
    os.unlink(path)
    assert rows == [("day", "06:00", "18:30"), ("night", "18:00", "06:30")]


def test_teammates_table_empty_on_first_run():
    db, path = _make_db()
    cur = db.conn.cursor()
    cur.execute("SELECT COUNT(*) FROM teammates")
    count = cur.fetchone()[0]
    db.conn.close()
    os.unlink(path)
    assert count == 0


def test_overrides_table_empty_on_first_run():
    db, path = _make_db()
    cur = db.conn.cursor()
    cur.execute("SELECT COUNT(*) FROM overrides")
    count = cur.fetchone()[0]
    db.conn.close()
    os.unlink(path)
    assert count == 0


def test_no_reseed_on_reopen():
    db, path = _make_db()
    db.conn.close()
    # Reopen the same database
    db2 = DatabaseManager(path)
    cur = db2.conn.cursor()
    cur.execute("SELECT COUNT(*) FROM shift_windows")
    count = cur.fetchone()[0]
    db2.conn.close()
    os.unlink(path)
    assert count == 2  # still just the original 2 rows, not 4


def test_shift_type_check_constraint():
    """Verify the CHECK constraint on teammates.shift_type rejects invalid values."""
    db, path = _make_db()
    cur = db.conn.cursor()
    try:
        cur.execute("INSERT INTO teammates (name, shift_type) VALUES ('Test', 'INVALID')")
        db.conn.commit()
        constraint_enforced = False
    except sqlite3.IntegrityError:
        constraint_enforced = True
    db.conn.close()
    os.unlink(path)
    assert constraint_enforced


def test_overrides_composite_primary_key():
    """Verify the composite PK on overrides (date, shift_type) prevents duplicates."""
    db, path = _make_db()
    cur = db.conn.cursor()
    cur.execute("INSERT INTO overrides VALUES ('2025-01-01', 'day', 'Alice')")
    db.conn.commit()
    try:
        cur.execute("INSERT INTO overrides VALUES ('2025-01-01', 'day', 'Bob')")
        db.conn.commit()
        pk_enforced = False
    except sqlite3.IntegrityError:
        pk_enforced = True
    db.conn.close()
    os.unlink(path)
    assert pk_enforced
