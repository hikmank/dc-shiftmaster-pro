"""Property test for database import merge with conflict resolution (Property 15).

Feature: dc-shiftmaster-web, Property 15: Database import merge with conflict resolution
"""

from __future__ import annotations

import sqlite3
import tempfile
from types import SimpleNamespace

import pytest
from hypothesis import given, settings, strategies as st

from dc_shiftmaster.models import Override, ShiftWindow, Teammate
from dc_shiftmaster_web.migration import import_database
from dc_shiftmaster_web.storage import StorageAdapter


# ------------------------------------------------------------------ #
# Mock helpers
# ------------------------------------------------------------------ #

class MockClientStorage:
    """Dict-backed mock of Flet's client_storage for testing."""

    def __init__(self):
        self._data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def remove(self, key: str) -> None:
        self._data.pop(key, None)


def _make_storage() -> StorageAdapter:
    page = SimpleNamespace(shared_preferences=MockClientStorage())
    return StorageAdapter(page)


def _create_db_bytes(
    teammates: list[Teammate] | None = None,
    shift_windows: dict[str, ShiftWindow] | None = None,
    overrides: list[Override] | None = None,
) -> bytes:
    """Create a valid teammates.db file in memory and return its bytes."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    conn = sqlite3.connect(tmp_path)
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE shift_windows (
            shift_type TEXT PRIMARY KEY,
            start_time TEXT NOT NULL,
            end_time   TEXT NOT NULL
        );
        CREATE TABLE teammates (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            shift_type TEXT NOT NULL,
            custom_start TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE overrides (
            date       TEXT NOT NULL,
            shift_type TEXT NOT NULL,
            name       TEXT NOT NULL,
            PRIMARY KEY (date, shift_type)
        );
    """)

    if shift_windows:
        for sw in shift_windows.values():
            cursor.execute(
                "INSERT INTO shift_windows VALUES (?, ?, ?)",
                (sw.shift_type, sw.start_time, sw.end_time),
            )

    if teammates:
        for t in teammates:
            cursor.execute(
                "INSERT INTO teammates (id, name, shift_type, custom_start) VALUES (?, ?, ?, ?)",
                (t.id, t.name, t.shift_type, t.custom_start),
            )

    if overrides:
        for o in overrides:
            cursor.execute(
                "INSERT INTO overrides VALUES (?, ?, ?)",
                (o.date, o.shift_type, o.name),
            )

    conn.commit()
    conn.close()

    with open(tmp_path, "rb") as f:
        return f.read()


# ------------------------------------------------------------------ #
# Hypothesis strategies
# ------------------------------------------------------------------ #

_valid_shift_types = st.sampled_from(["FHD", "FHN", "BHD", "BHN"])
_valid_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=10,
)
_valid_times = st.from_regex(r"^[01]\d:[0-5]\d$", fullmatch=True)


# ------------------------------------------------------------------ #
# Property 15: Database import merge with conflict resolution
# ------------------------------------------------------------------ #

class TestDatabaseImportMerge:
    """Property 15: After import, all imported records are present,
    existing non-conflicting records are preserved, and imported values
    win for conflicting keys."""

    @settings(max_examples=50)
    @given(
        existing_name=_valid_names,
        imported_name=_valid_names,
        shift_type=_valid_shift_types,
    )
    def test_imported_teammate_wins_on_conflict(
        self, existing_name, imported_name, shift_type
    ):
        """Same teammate ID → imported value should win."""
        storage = _make_storage()

        # Pre-populate with an existing teammate at ID 1
        storage._storage.set(
            "dcshift.teammates",
            StorageAdapter._serialize_teammates(
                [Teammate(id=1, name=existing_name, shift_type="FHD", custom_start="")]
            ),
        )

        # Import a DB with a teammate at the same ID
        db_bytes = _create_db_bytes(
            teammates=[Teammate(id=1, name=imported_name, shift_type=shift_type, custom_start="")],
            shift_windows={
                "day": ShiftWindow("day", "06:00", "18:30"),
                "night": ShiftWindow("night", "18:00", "06:30"),
            },
        )

        import_database(db_bytes, storage)

        result = storage.get_teammates()
        t1 = next(t for t in result if t.id == 1)
        assert t1.name == imported_name
        assert t1.shift_type == shift_type

    @settings(max_examples=50)
    @given(
        override_name_existing=_valid_names,
        override_name_imported=_valid_names,
    )
    def test_imported_override_wins_on_conflict(
        self, override_name_existing, override_name_imported
    ):
        """Same date+shift_type → imported override should win."""
        storage = _make_storage()

        # Pre-populate with an existing override
        storage.set_override("2025-06-15", "day", override_name_existing)

        # Import a DB with an override for the same date+shift_type
        db_bytes = _create_db_bytes(
            overrides=[Override(date="2025-06-15", shift_type="day", name=override_name_imported)],
            shift_windows={
                "day": ShiftWindow("day", "06:00", "18:30"),
                "night": ShiftWindow("night", "18:00", "06:30"),
            },
        )

        import_database(db_bytes, storage)

        overrides = storage.get_overrides(2025)
        match = [o for o in overrides if o.date == "2025-06-15" and o.shift_type == "day"]
        assert len(match) == 1
        assert match[0].name == override_name_imported

    def test_existing_non_conflicting_records_preserved(self):
        """Records that don't conflict with imports should survive."""
        storage = _make_storage()

        # Pre-populate
        storage._storage.set(
            "dcshift.teammates",
            StorageAdapter._serialize_teammates(
                [Teammate(id=99, name="Existing", shift_type="BHN", custom_start="")]
            ),
        )
        storage.set_override("2025-01-01", "night", "ExistingOverride")

        # Import different records
        db_bytes = _create_db_bytes(
            teammates=[Teammate(id=1, name="Imported", shift_type="FHD", custom_start="")],
            overrides=[Override(date="2025-06-15", shift_type="day", name="ImportedOverride")],
            shift_windows={
                "day": ShiftWindow("day", "07:00", "19:00"),
                "night": ShiftWindow("night", "19:00", "07:00"),
            },
        )

        import_database(db_bytes, storage)

        teammates = storage.get_teammates()
        ids = {t.id for t in teammates}
        assert 99 in ids  # existing preserved
        assert 1 in ids   # imported added

        overrides = storage.get_overrides(2025)
        keys = {(o.date, o.shift_type) for o in overrides}
        assert ("2025-01-01", "night") in keys  # existing preserved
        assert ("2025-06-15", "day") in keys     # imported added

    def test_invalid_db_raises_valueerror(self):
        """Non-SQLite bytes should raise ValueError."""
        storage = _make_storage()
        with pytest.raises(ValueError, match="Invalid database file"):
            import_database(b"not a database", storage)
