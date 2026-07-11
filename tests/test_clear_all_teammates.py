"""Property-based and unit tests for the clear_all_teammates feature."""

import os
import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dc_shiftmaster.database import DatabaseManager
from tests.conftest import valid_teammate, valid_region


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
# Property 1: Clear removes all teammates and returns correct count
# Feature: clear-all-teammates, Property 1: Clear removes all teammates and returns correct count
# **Validates: Requirements 1.1, 1.2, 1.3, 6.2, 6.4**
# ---------------------------------------------------------------------------


@given(teammates=st.lists(valid_teammate(), min_size=0, max_size=50))
@settings(max_examples=100, deadline=None)
def test_clear_all_removes_all_and_returns_count(teammates):
    """Property 1: Clear removes all teammates and returns correct count.

    For any team with N teammates (where N >= 0), calling clear_all_teammates(team_id)
    results in get_teammates(team_id) returning an empty list, and the method returns N.

    **Validates: Requirements 1.1, 1.2, 1.3, 6.2, 6.4**

    Feature: clear-all-teammates, Property 1: Clear removes all teammates and returns correct count
    """
    db, path = _make_db()
    try:
        team_id = 1

        # Set up team profile
        db.conn.execute(
            "INSERT OR IGNORE INTO team_profiles (id, site_code, display_name) VALUES (?, ?, ?)",
            (team_id, "TST1", "TestTeam"),
        )
        db.conn.commit()

        # Insert N teammates
        for name, shift_type in teammates:
            db.add_teammate(name, shift_type, team_id=team_id)

        # Execute clear
        deleted_count = db.clear_all_teammates(team_id=team_id)

        # Assert return value equals number inserted
        assert deleted_count == len(teammates)

        # Assert roster is now empty
        remaining = db.get_teammates(team_id=team_id)
        assert remaining == []
    finally:
        _cleanup_db(db, path)


# ---------------------------------------------------------------------------
# Property 2: Team isolation — clearing one team preserves others
# Feature: clear-all-teammates, Property 2: Team isolation — clearing one team preserves others
# **Validates: Requirements 2.1, 2.3**
# ---------------------------------------------------------------------------


@given(
    teammates_a=st.lists(valid_teammate(), min_size=0, max_size=20),
    teammates_b=st.lists(valid_teammate(), min_size=0, max_size=20),
    regions=st.lists(valid_region(), min_size=2, max_size=2, unique=True),
)
@settings(max_examples=100, deadline=None)
def test_clear_all_team_isolation(teammates_a, teammates_b, regions):
    """Property 2: Team isolation — clearing one team preserves others.

    For any two distinct teams A and B, each with arbitrary teammate lists,
    calling clear_all_teammates(team_id=A) shall leave all teammate records
    for team B unchanged (same IDs, names, shift types, and count).

    **Validates: Requirements 2.1, 2.3**

    Feature: clear-all-teammates, Property 2: Team isolation — clearing one team preserves others
    """
    region_a, region_b = regions
    db, path = _make_db()
    try:
        # Create two distinct team profiles
        db.conn.execute(
            "INSERT INTO team_profiles (id, site_code, display_name) VALUES (?, ?, ?)",
            (1, region_a, "Team A"),
        )
        db.conn.execute(
            "INSERT INTO team_profiles (id, site_code, display_name) VALUES (?, ?, ?)",
            (2, region_b, "Team B"),
        )
        db.conn.commit()

        team_a_id = 1
        team_b_id = 2

        # Insert teammates for team A
        for name, shift_type in teammates_a:
            db.add_teammate(name, shift_type, team_id=team_a_id)

        # Insert teammates for team B
        for name, shift_type in teammates_b:
            db.add_teammate(name, shift_type, team_id=team_b_id)

        # Snapshot team B's teammates before clearing team A
        team_b_before = db.get_teammates(team_id=team_b_id)

        # Clear team A
        db.clear_all_teammates(team_id=team_a_id)

        # Verify team B is unchanged
        team_b_after = db.get_teammates(team_id=team_b_id)

        assert len(team_b_after) == len(team_b_before), (
            f"Team B count changed: {len(team_b_before)} -> {len(team_b_after)}"
        )

        # Verify each teammate record is identical
        for before, after in zip(team_b_before, team_b_after):
            assert before.id == after.id, f"ID mismatch: {before.id} != {after.id}"
            assert before.name == after.name, (
                f"Name mismatch: {before.name} != {after.name}"
            )
            assert before.shift_type == after.shift_type, (
                f"Shift type mismatch: {before.shift_type} != {after.shift_type}"
            )
    finally:
        _cleanup_db(db, path)
