"""Property-based tests for DatabaseManager.

Uses Hypothesis to verify storage round-trip and validation properties
for shift windows, teammates, overrides, and full database state.
"""

import tempfile
import os

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster.models import Override, ShiftWindow, Teammate
from tests.conftest import (
    VALID_SHIFT_TYPES,
    valid_override,
    valid_teammate,
    valid_time,
    valid_year,
)


def _make_db():
    """Create a fresh DatabaseManager backed by a temp file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return DatabaseManager(path), path


def _cleanup_db(db, path):
    """Close the database and remove the temp file."""
    db.conn.close()
    try:
        os.unlink(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Property 1: Shift window storage round-trip
# Feature: dc-shiftmaster-pro, Property 1: Shift window storage round-trip
# **Validates: Requirements 1.1, 1.3**
# ---------------------------------------------------------------------------


@given(
    shift_type=st.sampled_from(["day", "night"]),
    start=valid_time(),
    end=valid_time(),
)
@settings(max_examples=100, deadline=None)
def test_shift_window_storage_round_trip(shift_type, start, end):
    """For any valid shift type and HH:MM time pair, storing a shift window
    and retrieving it should return the same start and end times."""
    db, path = _make_db()
    try:
        db.update_shift_window(shift_type, start, end)
        windows = db.get_shift_windows()
        assert shift_type in windows
        assert windows[shift_type].start_time == start
        assert windows[shift_type].end_time == end
    finally:
        _cleanup_db(db, path)


# ---------------------------------------------------------------------------
# Property 3: Teammate CRUD round-trip
# Feature: dc-shiftmaster-pro, Property 3: Teammate CRUD round-trip
# **Validates: Requirements 2.1, 2.2, 2.3**
# ---------------------------------------------------------------------------


@given(data=st.data())
@settings(max_examples=100, deadline=None)
def test_teammate_crud_round_trip(data):
    """For any valid teammate, adding then retrieving should include that record.
    Updating name or shift type and re-retrieving should reflect the changes."""
    db, path = _make_db()
    try:
        name, shift_type = data.draw(valid_teammate())

        # Add
        new_id = db.add_teammate(name, shift_type)
        teammates = db.get_teammates()
        match = [t for t in teammates if t.id == new_id]
        assert len(match) == 1
        assert match[0].name == name
        assert match[0].shift_type == shift_type

        # Update with new values
        new_name, new_shift_type = data.draw(valid_teammate())
        db.update_teammate(new_id, new_name, new_shift_type)
        teammates = db.get_teammates()
        match = [t for t in teammates if t.id == new_id]
        assert len(match) == 1
        assert match[0].name == new_name
        assert match[0].shift_type == new_shift_type
    finally:
        _cleanup_db(db, path)


# ---------------------------------------------------------------------------
# Property 4: Empty name rejection
# Feature: dc-shiftmaster-pro, Property 4: Empty name rejection
# **Validates: Requirements 2.5**
# ---------------------------------------------------------------------------


@given(
    empty_name=st.text(
        alphabet=st.characters(whitelist_categories=("Zs",)),
        min_size=0,
        max_size=20,
    ),
    shift_type=st.sampled_from(VALID_SHIFT_TYPES),
)
@settings(max_examples=100, deadline=None)
def test_empty_name_rejection(empty_name, shift_type):
    """For any whitespace-only or empty string, adding as a teammate name
    should be rejected and the teammate list should remain unchanged."""
    db, path = _make_db()
    try:
        before = db.get_teammates()
        with pytest.raises(ValueError):
            db.add_teammate(empty_name, shift_type)
        after = db.get_teammates()
        assert len(after) == len(before)
    finally:
        _cleanup_db(db, path)


# ---------------------------------------------------------------------------
# Property 8: Override storage round-trip
# Feature: dc-shiftmaster-pro, Property 8: Override storage round-trip
# **Validates: Requirements 5.2, 5.5**
# ---------------------------------------------------------------------------


@given(data=st.data())
@settings(max_examples=100, deadline=None)
def test_override_storage_round_trip(data):
    """For any valid override, storing it and retrieving overrides for that year
    should include the stored override with matching date, shift type, and name."""
    db, path = _make_db()
    try:
        year = data.draw(valid_year())
        date_str, shift_type, name = data.draw(valid_override(year=year))

        db.set_override(date_str, shift_type, name)
        overrides = db.get_overrides(year)
        match = [
            o for o in overrides if o.date == date_str and o.shift_type == shift_type
        ]
        assert len(match) == 1
        assert match[0].name == name
    finally:
        _cleanup_db(db, path)


# ---------------------------------------------------------------------------
# Property 15: Database state round-trip
# Feature: dc-shiftmaster-pro, Property 15: Database state round-trip
# **Validates: Requirements 8.2**
# ---------------------------------------------------------------------------


@given(data=st.data())
@settings(max_examples=100, deadline=None)
def test_database_state_round_trip(data):
    """For any valid application state (teammates, shift windows, overrides),
    persisting all data and loading it back should produce equivalent state."""
    db, path = _make_db()
    try:
        # Generate and persist shift windows
        day_start = data.draw(valid_time())
        day_end = data.draw(valid_time())
        night_start = data.draw(valid_time())
        night_end = data.draw(valid_time())
        db.update_shift_window("day", day_start, day_end)
        db.update_shift_window("night", night_start, night_end)

        # Generate and persist a few teammates
        num_teammates = data.draw(st.integers(min_value=0, max_value=5))
        expected_teammates = []
        for _ in range(num_teammates):
            name, shift_type = data.draw(valid_teammate())
            tid = db.add_teammate(name, shift_type)
            expected_teammates.append((tid, name, shift_type))

        # Generate and persist a few overrides within a single year
        year = data.draw(valid_year())
        num_overrides = data.draw(st.integers(min_value=0, max_value=5))
        expected_overrides = {}
        for _ in range(num_overrides):
            date_str, shift_type, name = data.draw(valid_override(year=year))
            db.set_override(date_str, shift_type, name)
            # Last write wins for same (date, shift_type) key
            expected_overrides[(date_str, shift_type)] = name

        # Reload and verify shift windows
        windows = db.get_shift_windows()
        assert windows["day"].start_time == day_start
        assert windows["day"].end_time == day_end
        assert windows["night"].start_time == night_start
        assert windows["night"].end_time == night_end

        # Reload and verify teammates
        teammates = db.get_teammates()
        for tid, name, shift_type in expected_teammates:
            match = [t for t in teammates if t.id == tid]
            assert len(match) == 1
            assert match[0].name == name
            assert match[0].shift_type == shift_type

        # Reload and verify overrides
        overrides = db.get_overrides(year)
        for (date_str, shift_type), name in expected_overrides.items():
            match = [
                o
                for o in overrides
                if o.date == date_str and o.shift_type == shift_type
            ]
            assert len(match) == 1
            assert match[0].name == name
    finally:
        _cleanup_db(db, path)
