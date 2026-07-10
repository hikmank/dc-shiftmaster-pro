"""Unit tests for DatabaseManager teammate CRUD methods."""

import os
import tempfile

import pytest

from dc_shiftmaster.database import DatabaseManager


@pytest.fixture
def db():
    """Create a fresh DatabaseManager with a temp file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    manager = DatabaseManager(path)
    yield manager
    manager.conn.close()
    if os.path.exists(path):
        os.unlink(path)


def test_get_teammates_empty(db):
    assert db.get_teammates() == []


def test_add_teammate_returns_id(db):
    row_id = db.add_teammate("Alice", "FHD")
    assert isinstance(row_id, int)
    assert row_id > 0


def test_add_and_get_teammate(db):
    db.add_teammate("Alice", "FHD")
    teammates = db.get_teammates()
    assert len(teammates) == 1
    assert teammates[0].name == "Alice"
    assert teammates[0].shift_type == "FHD"


def test_add_multiple_teammates(db):
    db.add_teammate("Alice", "FHD")
    db.add_teammate("Bob", "BHN")
    teammates = db.get_teammates()
    assert len(teammates) == 2
    names = {t.name for t in teammates}
    assert names == {"Alice", "Bob"}


def test_update_teammate_name(db):
    row_id = db.add_teammate("Alice", "FHD")
    db.update_teammate(row_id, "Alicia", "FHD")
    teammates = db.get_teammates()
    assert len(teammates) == 1
    assert teammates[0].name == "Alicia"


def test_update_teammate_shift_type(db):
    row_id = db.add_teammate("Alice", "FHD")
    db.update_teammate(row_id, "Alice", "BHN")
    teammates = db.get_teammates()
    assert teammates[0].shift_type == "BHN"


def test_delete_teammate(db):
    row_id = db.add_teammate("Alice", "FHD")
    db.delete_teammate(row_id)
    assert db.get_teammates() == []


def test_delete_one_of_many(db):
    id1 = db.add_teammate("Alice", "FHD")
    db.add_teammate("Bob", "BHN")
    db.delete_teammate(id1)
    teammates = db.get_teammates()
    assert len(teammates) == 1
    assert teammates[0].name == "Bob"


def test_add_empty_name_raises(db):
    with pytest.raises(ValueError):
        db.add_teammate("", "FHD")


def test_add_whitespace_name_raises(db):
    with pytest.raises(ValueError):
        db.add_teammate("   ", "FHD")


def test_update_empty_name_raises(db):
    row_id = db.add_teammate("Alice", "FHD")
    with pytest.raises(ValueError):
        db.update_teammate(row_id, "", "FHD")


def test_update_whitespace_name_raises(db):
    row_id = db.add_teammate("Alice", "FHD")
    with pytest.raises(ValueError):
        db.update_teammate(row_id, "  \t  ", "FHD")


def test_empty_name_does_not_modify_db(db):
    """Ensure a failed add doesn't leave partial data."""
    with pytest.raises(ValueError):
        db.add_teammate("", "FHD")
    assert db.get_teammates() == []
