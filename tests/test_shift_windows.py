"""Unit tests for DatabaseManager shift window CRUD methods (task 2.2)."""

import os
import tempfile

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster.models import ShiftWindow


def _make_db():
    """Create a DatabaseManager with a temp file and return (db, path)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    return DatabaseManager(path), path


def test_get_shift_windows_returns_defaults():
    db, path = _make_db()
    windows = db.get_shift_windows()
    db.conn.close()
    os.unlink(path)

    assert len(windows) == 2
    assert "day" in windows
    assert "night" in windows
    assert windows["day"] == ShiftWindow("day", "06:00", "18:30")
    assert windows["night"] == ShiftWindow("night", "18:00", "06:30")


def test_update_shift_window_persists_new_times():
    db, path = _make_db()
    db.update_shift_window("day", "07:00", "19:00")
    windows = db.get_shift_windows()
    db.conn.close()
    os.unlink(path)

    assert windows["day"].start_time == "07:00"
    assert windows["day"].end_time == "19:00"
    # night should be unchanged
    assert windows["night"] == ShiftWindow("night", "18:00", "06:30")


def test_update_shift_window_survives_reopen():
    db, path = _make_db()
    db.update_shift_window("night", "20:00", "08:00")
    db.conn.close()

    db2 = DatabaseManager(path)
    windows = db2.get_shift_windows()
    db2.conn.close()
    os.unlink(path)

    assert windows["night"].start_time == "20:00"
    assert windows["night"].end_time == "08:00"


def test_update_both_shift_windows():
    db, path = _make_db()
    db.update_shift_window("day", "05:00", "17:00")
    db.update_shift_window("night", "17:00", "05:00")
    windows = db.get_shift_windows()
    db.conn.close()
    os.unlink(path)

    assert windows["day"] == ShiftWindow("day", "05:00", "17:00")
    assert windows["night"] == ShiftWindow("night", "17:00", "05:00")
