"""Unit tests for Multi-Team Profiles migration.

Example-based tests validating:
- ATL069 team creation with all existing data (teammates, overrides, coverage requests, shift windows)
- Re-run produces same state (idempotency)
- Rollback on simulated IO failure leaves DB unchanged
- All users assigned as ATL069 members

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7
"""

import sqlite3
from unittest.mock import patch

import pytest

from dc_shiftmaster.migration import MigrationError, run_migration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _create_pre_migration_db() -> sqlite3.Connection:
    """Create an in-memory SQLite database with pre-migration schema and seed data.

    Simulates the state of the DB before multi-team migration:
    - 3 users
    - 4 teammates
    - 2 overrides
    - 2 coverage requests
    - 2 shift windows
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name  TEXT NOT NULL,
            teammate_name TEXT NOT NULL DEFAULT '',
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            email         TEXT NOT NULL DEFAULT '',
            email_notifications_enabled INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS teammates (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            shift_type TEXT NOT NULL CHECK(shift_type IN ('FHD','FHN','BHD','BHN','Custom')),
            custom_start TEXT NOT NULL DEFAULT '',
            custom_days TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS overrides (
            date       TEXT NOT NULL,
            shift_type TEXT NOT NULL,
            name       TEXT NOT NULL,
            PRIMARY KEY (date, shift_type)
        );

        CREATE TABLE IF NOT EXISTS coverage_requests (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id  INTEGER NOT NULL REFERENCES users(id),
            date          TEXT NOT NULL,
            shift_type    TEXT NOT NULL CHECK(shift_type IN ('day', 'night')),
            note          TEXT NOT NULL DEFAULT '',
            status        TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'claimed', 'cancelled')),
            claimer_id    INTEGER REFERENCES users(id),
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            claimed_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS shift_windows (
            shift_type TEXT PRIMARY KEY,
            start_time TEXT NOT NULL,
            end_time   TEXT NOT NULL
        );
    """)

    # Seed users
    conn.execute(
        "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
        ("alice", "hash1", "Alice"),
    )
    conn.execute(
        "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
        ("bob", "hash2", "Bob"),
    )
    conn.execute(
        "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
        ("charlie", "hash3", "Charlie"),
    )

    # Seed teammates
    conn.execute("INSERT INTO teammates (name, shift_type) VALUES (?, ?)", ("Alice", "FHD"))
    conn.execute("INSERT INTO teammates (name, shift_type) VALUES (?, ?)", ("Bob", "FHN"))
    conn.execute("INSERT INTO teammates (name, shift_type) VALUES (?, ?)", ("Charlie", "BHD"))
    conn.execute("INSERT INTO teammates (name, shift_type) VALUES (?, ?)", ("Dave", "BHN"))

    # Seed overrides
    conn.execute(
        "INSERT INTO overrides (date, shift_type, name) VALUES (?, ?, ?)",
        ("2025-01-15", "day", "Alice"),
    )
    conn.execute(
        "INSERT INTO overrides (date, shift_type, name) VALUES (?, ?, ?)",
        ("2025-01-16", "night", "Bob"),
    )

    # Seed coverage requests
    conn.execute(
        "INSERT INTO coverage_requests (requester_id, date, shift_type, note) VALUES (?, ?, ?, ?)",
        (1, "2025-01-20", "day", "Need coverage for appointment"),
    )
    conn.execute(
        "INSERT INTO coverage_requests (requester_id, date, shift_type, note) VALUES (?, ?, ?, ?)",
        (2, "2025-01-21", "night", "Family event"),
    )

    # Seed shift windows
    conn.execute(
        "INSERT INTO shift_windows (shift_type, start_time, end_time) VALUES (?, ?, ?)",
        ("day", "06:00", "18:30"),
    )
    conn.execute(
        "INSERT INTO shift_windows (shift_type, start_time, end_time) VALUES (?, ?, ?)",
        ("night", "18:00", "06:30"),
    )

    conn.commit()
    return conn


@pytest.fixture
def pre_migration_db():
    """Provide a fresh pre-migration database for each test."""
    conn = _create_pre_migration_db()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Test 1: Migration creates ATL069 team profile (Requirement 7.1)
# ---------------------------------------------------------------------------


def test_migration_creates_atl069_team_profile(pre_migration_db):
    """Migration SHALL create a Team_Profile with Site_Code 'ATL069'."""
    conn = pre_migration_db

    result = run_migration(conn)

    assert result["status"] == "success"
    assert "team_id" in result

    # Verify team_profiles table has exactly one entry with site_code ATL069
    rows = conn.execute("SELECT id, site_code, display_name FROM team_profiles").fetchall()
    assert len(rows) == 1
    assert rows[0][1] == "ATL069"
    assert rows[0][2] == "ATL069"
    assert rows[0][0] == result["team_id"]


# ---------------------------------------------------------------------------
# Test 2: All existing teammates get team_id = ATL069's id (Requirement 7.1)
# ---------------------------------------------------------------------------


def test_migration_associates_all_teammates(pre_migration_db):
    """All existing teammates SHALL be associated with ATL069 team_id."""
    conn = pre_migration_db

    result = run_migration(conn)
    team_id = result["team_id"]

    rows = conn.execute("SELECT id, name, team_id FROM teammates").fetchall()
    assert len(rows) == 4  # 4 seeded teammates

    for row in rows:
        assert row[2] == team_id, f"Teammate '{row[1]}' has team_id={row[2]}, expected {team_id}"


# ---------------------------------------------------------------------------
# Test 3: All existing overrides get team_id = ATL069's id (Requirement 7.2)
# ---------------------------------------------------------------------------


def test_migration_associates_all_overrides(pre_migration_db):
    """All existing overrides SHALL be associated with ATL069 team_id."""
    conn = pre_migration_db

    result = run_migration(conn)
    team_id = result["team_id"]

    rows = conn.execute("SELECT date, shift_type, name, team_id FROM overrides").fetchall()
    assert len(rows) == 2  # 2 seeded overrides

    for row in rows:
        assert row[3] == team_id, f"Override ({row[0]}, {row[1]}) has team_id={row[3]}, expected {team_id}"


# ---------------------------------------------------------------------------
# Test 4: All existing coverage requests get team_id = ATL069's id (Req 7.3)
# ---------------------------------------------------------------------------


def test_migration_associates_all_coverage_requests(pre_migration_db):
    """All existing coverage requests SHALL be associated with ATL069 team_id."""
    conn = pre_migration_db

    result = run_migration(conn)
    team_id = result["team_id"]

    rows = conn.execute(
        "SELECT id, requester_id, date, shift_type, team_id FROM coverage_requests"
    ).fetchall()
    assert len(rows) == 2  # 2 seeded coverage requests

    for row in rows:
        assert row[4] == team_id, f"Coverage request id={row[0]} has team_id={row[4]}, expected {team_id}"


# ---------------------------------------------------------------------------
# Test 5: All existing shift windows get team_id = ATL069's id (Req 7.4)
# ---------------------------------------------------------------------------


def test_migration_associates_all_shift_windows(pre_migration_db):
    """All existing shift windows SHALL be associated with ATL069 team_id."""
    conn = pre_migration_db

    result = run_migration(conn)
    team_id = result["team_id"]

    rows = conn.execute(
        "SELECT shift_type, start_time, end_time, team_id FROM shift_windows"
    ).fetchall()
    assert len(rows) == 2  # 2 seeded shift windows (day, night)

    for row in rows:
        assert row[3] == team_id, f"Shift window '{row[0]}' has team_id={row[3]}, expected {team_id}"


# ---------------------------------------------------------------------------
# Test 6: All existing users become members of ATL069 with admin role (Req 7.5)
# ---------------------------------------------------------------------------


def test_migration_assigns_all_users_as_atl069_admins(pre_migration_db):
    """All existing users SHALL be assigned as ATL069 members with admin role."""
    conn = pre_migration_db

    result = run_migration(conn)
    team_id = result["team_id"]

    # Get all user IDs
    user_rows = conn.execute("SELECT id FROM users").fetchall()
    user_ids = {row[0] for row in user_rows}
    assert len(user_ids) == 3  # 3 seeded users

    # Get all team_members entries
    member_rows = conn.execute(
        "SELECT team_id, user_id, role FROM team_members"
    ).fetchall()
    assert len(member_rows) == 3  # One entry per user

    for row in member_rows:
        assert row[0] == team_id, f"Member has team_id={row[0]}, expected {team_id}"
        assert row[1] in user_ids, f"Member user_id={row[1]} not in seeded users"
        assert row[2] == "admin", f"Member user_id={row[1]} has role='{row[2]}', expected 'admin'"

    # Verify all users are accounted for
    member_user_ids = {row[1] for row in member_rows}
    assert member_user_ids == user_ids


# ---------------------------------------------------------------------------
# Test 7: Re-running migration returns {"status": "already_applied"} (Req 7.7)
# ---------------------------------------------------------------------------


def test_migration_idempotency(pre_migration_db):
    """Running migration twice SHALL produce same state; second run returns 'already_applied'."""
    conn = pre_migration_db

    # First run
    result1 = run_migration(conn)
    assert result1["status"] == "success"
    team_id = result1["team_id"]

    # Capture state after first migration
    team_profiles = conn.execute("SELECT * FROM team_profiles").fetchall()
    team_members = conn.execute("SELECT * FROM team_members").fetchall()
    teammates = conn.execute("SELECT id, name, shift_type, team_id FROM teammates").fetchall()
    overrides = conn.execute("SELECT date, shift_type, name, team_id FROM overrides").fetchall()

    # Second run
    result2 = run_migration(conn)
    assert result2["status"] == "already_applied"

    # Verify state is unchanged
    assert conn.execute("SELECT * FROM team_profiles").fetchall() == team_profiles
    assert conn.execute("SELECT * FROM team_members").fetchall() == team_members
    assert conn.execute("SELECT id, name, shift_type, team_id FROM teammates").fetchall() == teammates
    assert conn.execute("SELECT date, shift_type, name, team_id FROM overrides").fetchall() == overrides


# ---------------------------------------------------------------------------
# Test 8: Simulated failure results in MigrationError and no partial state (Req 7.6)
# ---------------------------------------------------------------------------


class FailingConnectionWrapper:
    """Wrapper around sqlite3.Connection that raises an error on a target SQL statement."""

    def __init__(self, real_conn: sqlite3.Connection, fail_on: str):
        self._real_conn = real_conn
        self._fail_on = fail_on

    def execute(self, sql, *args, **kwargs):
        if self._fail_on in sql:
            raise sqlite3.OperationalError("disk I/O error")
        return self._real_conn.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._real_conn, name)


def test_migration_rollback_on_failure(pre_migration_db):
    """Simulated IO failure SHALL result in MigrationError with no partial state."""
    conn = pre_migration_db

    # Capture pre-migration state
    pre_teammates = conn.execute("SELECT * FROM teammates").fetchall()
    pre_overrides = conn.execute("SELECT * FROM overrides").fetchall()
    pre_coverage = conn.execute("SELECT * FROM coverage_requests").fetchall()
    pre_shift_windows = conn.execute("SELECT * FROM shift_windows").fetchall()
    pre_users = conn.execute("SELECT * FROM users").fetchall()

    # Create a wrapper that fails when UPDATE teammates is executed
    wrapper = FailingConnectionWrapper(conn, "UPDATE teammates")

    # Migration should raise MigrationError
    with pytest.raises(MigrationError) as exc_info:
        run_migration(wrapper)

    assert "rolled back" in str(exc_info.value).lower()

    # Verify database is unchanged (no partial state)
    assert conn.execute("SELECT * FROM teammates").fetchall() == pre_teammates
    assert conn.execute("SELECT * FROM overrides").fetchall() == pre_overrides
    assert conn.execute("SELECT * FROM coverage_requests").fetchall() == pre_coverage
    assert conn.execute("SELECT * FROM shift_windows").fetchall() == pre_shift_windows
    assert conn.execute("SELECT * FROM users").fetchall() == pre_users

    # Verify no team_profiles table was created (or it's empty)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='team_profiles'"
    )
    table_exists = cursor.fetchone()
    if table_exists:
        rows = conn.execute("SELECT * FROM team_profiles").fetchall()
        assert rows == [], "team_profiles should be empty after rollback"

    # Verify no team_members table was created (or it's empty)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='team_members'"
    )
    table_exists = cursor.fetchone()
    if table_exists:
        rows = conn.execute("SELECT * FROM team_members").fetchall()
        assert rows == [], "team_members should be empty after rollback"
