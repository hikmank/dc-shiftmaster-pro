"""Property-based tests for Multi-Team Profiles.

Uses the hypothesis library to validate correctness properties defined in the
multi-team-profiles design document.
"""

import sqlite3

import pytest
from hypothesis import given, settings, strategies as st

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster.migration import MigrationError, run_migration


# ---------------------------------------------------------------------------
# Hypothesis strategies for migration tests
# ---------------------------------------------------------------------------

VALID_SHIFT_TYPES = ["FHD", "FHN", "BHD", "BHN", "Custom"]


@st.composite
def teammate_name(draw: st.DrawFn) -> str:
    """Generate a non-empty teammate name."""
    return draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
            min_size=1,
            max_size=30,
        ).filter(lambda s: s.strip())
    )


@st.composite
def initial_db_state(draw: st.DrawFn) -> dict:
    """Generate a random initial database state for migration testing.

    Returns a dict with:
        - num_teammates: number of teammates to seed
        - teammates: list of (name, shift_type) tuples
        - num_overrides: number of overrides to seed
        - overrides: list of (date, shift_type, name) tuples
        - num_users: number of users to seed (at least 1)
        - users: list of (username, display_name) tuples
    """
    num_teammates = draw(st.integers(min_value=0, max_value=10))
    teammates = []
    for i in range(num_teammates):
        name = draw(teammate_name())
        shift_type = draw(st.sampled_from(VALID_SHIFT_TYPES))
        teammates.append((f"{name}_{i}", shift_type))

    num_overrides = draw(st.integers(min_value=0, max_value=5))
    overrides = []
    for i in range(num_overrides):
        date_str = f"2025-01-{(i % 28) + 1:02d}"
        shift_type = draw(st.sampled_from(["day", "night"]))
        name = f"Override_{i}"
        overrides.append((date_str, shift_type, name))

    num_users = draw(st.integers(min_value=1, max_value=5))
    users = []
    for i in range(num_users):
        users.append((f"user_{i}", f"User {i}"))

    return {
        "teammates": teammates,
        "overrides": overrides,
        "users": users,
    }


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def create_test_db(state: dict) -> sqlite3.Connection:
    """Create an in-memory SQLite database seeded with the given state.

    Sets up the base schema (without multi-team tables) and seeds data,
    simulating a pre-migration database state.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")

    # Create base tables (pre-migration schema without team_profiles/team_members)
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
    for username, display_name in state["users"]:
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
            (username, "hash_placeholder", display_name),
        )

    # Seed teammates
    for name, shift_type in state["teammates"]:
        conn.execute(
            "INSERT INTO teammates (name, shift_type) VALUES (?, ?)",
            (name, shift_type),
        )

    # Seed overrides
    for date_str, shift_type, name in state["overrides"]:
        conn.execute(
            "INSERT OR IGNORE INTO overrides (date, shift_type, name) VALUES (?, ?, ?)",
            (date_str, shift_type, name),
        )

    # Seed default shift windows
    conn.execute(
        "INSERT INTO shift_windows (shift_type, start_time, end_time) VALUES ('day', '06:00', '18:30')"
    )
    conn.execute(
        "INSERT INTO shift_windows (shift_type, start_time, end_time) VALUES ('night', '18:00', '06:30')"
    )

    conn.commit()
    return conn


def snapshot_db(conn: sqlite3.Connection) -> dict:
    """Capture a snapshot of all relevant tables in the database.

    Returns a dict keyed by table name with sorted lists of row tuples.
    """
    snapshot = {}

    # team_profiles
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='team_profiles'"
    )
    if cursor.fetchone():
        rows = conn.execute("SELECT id, site_code, display_name FROM team_profiles").fetchall()
        snapshot["team_profiles"] = sorted(rows)
    else:
        snapshot["team_profiles"] = []

    # team_members
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='team_members'"
    )
    if cursor.fetchone():
        rows = conn.execute("SELECT team_id, user_id, role FROM team_members").fetchall()
        snapshot["team_members"] = sorted(rows)
    else:
        snapshot["team_members"] = []

    # migrations_applied
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations_applied'"
    )
    if cursor.fetchone():
        rows = conn.execute("SELECT migration_name FROM migrations_applied").fetchall()
        snapshot["migrations_applied"] = sorted(rows)
    else:
        snapshot["migrations_applied"] = []

    # teammates (with team_id)
    cursor = conn.execute("PRAGMA table_info(teammates)")
    cols = [row[1] for row in cursor.fetchall()]
    if "team_id" in cols:
        rows = conn.execute("SELECT id, name, shift_type, team_id FROM teammates").fetchall()
    else:
        rows = conn.execute("SELECT id, name, shift_type FROM teammates").fetchall()
    snapshot["teammates"] = sorted(rows)

    # overrides (with team_id)
    cursor = conn.execute("PRAGMA table_info(overrides)")
    cols = [row[1] for row in cursor.fetchall()]
    if "team_id" in cols:
        rows = conn.execute("SELECT date, shift_type, name, team_id FROM overrides").fetchall()
    else:
        rows = conn.execute("SELECT date, shift_type, name FROM overrides").fetchall()
    snapshot["overrides"] = sorted(rows)

    # coverage_requests (with team_id)
    cursor = conn.execute("PRAGMA table_info(coverage_requests)")
    cols = [row[1] for row in cursor.fetchall()]
    if "team_id" in cols:
        rows = conn.execute(
            "SELECT id, requester_id, date, shift_type, status, team_id FROM coverage_requests"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, requester_id, date, shift_type, status FROM coverage_requests"
        ).fetchall()
    snapshot["coverage_requests"] = sorted(rows)

    # shift_windows (with team_id)
    cursor = conn.execute("PRAGMA table_info(shift_windows)")
    cols = [row[1] for row in cursor.fetchall()]
    if "team_id" in cols:
        rows = conn.execute(
            "SELECT shift_type, start_time, end_time, team_id FROM shift_windows"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT shift_type, start_time, end_time FROM shift_windows"
        ).fetchall()
    snapshot["shift_windows"] = sorted(rows)

    # users
    rows = conn.execute("SELECT id, username, display_name FROM users").fetchall()
    snapshot["users"] = sorted(rows)

    return snapshot


# ---------------------------------------------------------------------------
# Property 15: Migration idempotence
# Feature: multi-team-profiles, Property 15: Migration idempotence
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(state=initial_db_state())
def test_migration_idempotence(state):
    """Property 15: Running migration twice produces identical database state.

    **Validates: Requirements 7.7**

    For any database state, running the Migration_Service once and then running
    it again SHALL produce an identical database state (same team profile, same
    membership records, same team_id associations). The second run SHALL return
    {"status": "already_applied"}.
    """
    # Feature: multi-team-profiles, Property 15: Migration idempotence

    # Create a fresh database with seeded state
    conn = create_test_db(state)

    # Run migration the first time
    result1 = run_migration(conn)
    assert result1["status"] == "success"
    assert "team_id" in result1

    # Capture state after first migration
    snapshot_after_first = snapshot_db(conn)

    # Verify first migration created ATL069 team profile
    assert len(snapshot_after_first["team_profiles"]) == 1
    team_profile = snapshot_after_first["team_profiles"][0]
    assert team_profile[1] == "ATL069"  # site_code

    # Verify team_members has entries for all users
    assert len(snapshot_after_first["team_members"]) == len(state["users"])

    # Verify all teammates have team_id set
    for row in snapshot_after_first["teammates"]:
        assert row[-1] == result1["team_id"]  # team_id column is last

    # Run migration the second time
    result2 = run_migration(conn)
    assert result2["status"] == "already_applied"

    # Capture state after second migration
    snapshot_after_second = snapshot_db(conn)

    # Assert both states are identical
    assert snapshot_after_first == snapshot_after_second

    conn.close()


# ---------------------------------------------------------------------------
# Property 1: Site code validation accepts only valid codes
# Feature: multi-team-profiles, Property 1: Site code validation accepts only valid codes
# ---------------------------------------------------------------------------

import re
import string

from dc_shiftmaster.database import DatabaseManager

SITE_CODE_PATTERN = re.compile(r"^[A-Z]{3}[0-9]{3}$")


@st.composite
def valid_site_code(draw: st.DrawFn) -> str:
    """Generate a valid site code: 3 uppercase ASCII letters + 3 digits."""
    letters = draw(st.text(alphabet=string.ascii_uppercase, min_size=3, max_size=3))
    digits = draw(st.text(alphabet=string.digits, min_size=3, max_size=3))
    return letters + digits


@st.composite
def invalid_site_code(draw: st.DrawFn) -> str:
    """Generate a string that does NOT match ^[A-Z]{3}[0-9]{3}$."""
    # Generate arbitrary text and filter out any accidental valid codes
    code = draw(
        st.text(min_size=0, max_size=20).filter(
            lambda s: not SITE_CODE_PATTERN.match(s)
        )
    )
    return code


@settings(max_examples=100)
@given(site_code=valid_site_code())
def test_site_code_validation_accepts_valid_codes(site_code):
    """Property 1: Site code validation accepts only valid codes (valid case).

    **Validates: Requirements 1.3, 1.5**

    For any string matching ^[A-Z]{3}[0-9]{3}$, create_team() should succeed
    without raising a ValueError.
    """
    # Feature: multi-team-profiles, Property 1: Site code validation accepts only valid codes

    import tempfile
    import os

    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test.db")
    db = DatabaseManager(db_path)
    try:
        # Create a user to act as creator
        user_id = db.create_user("testuser", "hash", "Test User")

        # Valid site code should not raise ValueError
        result = db.create_team(site_code, "Test Team", user_id)
        assert result["site_code"] == site_code
        assert result["role"] == "admin"
    finally:
        db.conn.close()


@settings(max_examples=100)
@given(site_code=invalid_site_code())
def test_site_code_validation_rejects_invalid_codes(site_code):
    """Property 1: Site code validation accepts only valid codes (invalid case).

    **Validates: Requirements 1.3, 1.5**

    For any string NOT matching ^[A-Z]{3}[0-9]{3}$, create_team() should raise
    a ValueError with a descriptive validation error.
    """
    # Feature: multi-team-profiles, Property 1: Site code validation accepts only valid codes

    import tempfile
    import os

    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test.db")
    db = DatabaseManager(db_path)
    try:
        # Create a user to act as creator
        user_id = db.create_user("testuser", "hash", "Test User")

        # Invalid site code should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            db.create_team(site_code, "Test Team", user_id)

        # Verify the error message is descriptive
        assert "site code" in str(exc_info.value).lower() or "Site code" in str(exc_info.value)
    finally:
        db.conn.close()


# ---------------------------------------------------------------------------
# Hypothesis strategies for team profile tests
# ---------------------------------------------------------------------------


@st.composite
def valid_site_code(draw: st.DrawFn) -> str:
    """Generate a valid site code matching ^[A-Z]{3}[0-9]{3}$."""
    letters = draw(st.text(
        alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        min_size=3, max_size=3,
    ))
    digits = draw(st.text(
        alphabet=st.sampled_from("0123456789"),
        min_size=3, max_size=3,
    ))
    return letters + digits


# ---------------------------------------------------------------------------
# Property 3: Site code uniqueness
# Feature: multi-team-profiles, Property 3: Site code uniqueness
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(site_code=valid_site_code(), display_name=st.text(min_size=1, max_size=30).filter(lambda s: s.strip()))
def test_site_code_uniqueness(site_code, display_name):
    """Property 3: Duplicate site codes are rejected with IntegrityError.

    **Validates: Requirements 1.2**

    WHEN a user submits a Site_Code that already exists, THE Profile_Service
    SHALL reject the request. At the database layer, this manifests as an
    sqlite3.IntegrityError due to the UNIQUE constraint on site_code.
    """
    # Feature: multi-team-profiles, Property 3: Site code uniqueness
    import tempfile
    import os
    from dc_shiftmaster.database import DatabaseManager

    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_uniqueness.db")
    db = DatabaseManager(db_path)

    try:
        # Create a user to serve as the team creator
        user_id = db.create_user(
            username="creator_1",
            password_hash="hash_placeholder",
            display_name="Test Creator",
        )

        # First creation should succeed
        result = db.create_team(site_code, display_name, user_id)
        assert result["site_code"] == site_code
        assert result["id"] is not None

        # Second creation with the same site_code must raise IntegrityError
        # Create a different user for the second attempt
        user_id_2 = db.create_user(
            username="creator_2",
            password_hash="hash_placeholder",
            display_name="Test Creator 2",
        )

        with pytest.raises(sqlite3.IntegrityError):
            db.create_team(site_code, display_name, user_id_2)
    finally:
        db.conn.close()
        os.unlink(db_path)
        os.rmdir(tmp_dir)


# ---------------------------------------------------------------------------
# Hypothesis strategies for team deletion cascade tests
# ---------------------------------------------------------------------------


@st.composite
def valid_site_code(draw: st.DrawFn) -> str:
    """Generate a valid site code matching ^[A-Z]{3}[0-9]{3}$."""
    letters = draw(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=3, max_size=3))
    digits = draw(st.text(alphabet="0123456789", min_size=3, max_size=3))
    return letters + digits


@st.composite
def team_data_set(draw: st.DrawFn) -> dict:
    """Generate data to associate with a team: teammates, overrides, coverage requests.

    Returns a dict with:
        - teammates: list of (name, shift_type) tuples
        - overrides: list of (date, shift_type, name) tuples
        - coverage_dates: list of (date, shift_type) tuples for coverage requests
    """
    num_teammates = draw(st.integers(min_value=1, max_value=5))
    teammates = []
    for i in range(num_teammates):
        name = f"Teammate_{draw(st.integers(min_value=100, max_value=999))}"
        shift_type = draw(st.sampled_from(VALID_SHIFT_TYPES))
        teammates.append((name, shift_type))

    num_overrides = draw(st.integers(min_value=0, max_value=3))
    overrides = []
    used_date_shifts = set()
    for i in range(num_overrides):
        date_str = f"2025-03-{(i % 28) + 1:02d}"
        shift_type = draw(st.sampled_from(["day", "night"]))
        key = (date_str, shift_type)
        if key not in used_date_shifts:
            used_date_shifts.add(key)
            overrides.append((date_str, shift_type, f"Override_{i}"))

    num_coverage = draw(st.integers(min_value=0, max_value=3))
    coverage_dates = []
    used_coverage = set()
    for i in range(num_coverage):
        date_str = f"2025-04-{(i % 28) + 1:02d}"
        shift_type = draw(st.sampled_from(["day", "night"]))
        key = (date_str, shift_type)
        if key not in used_coverage:
            used_coverage.add(key)
            coverage_dates.append((date_str, shift_type))

    return {
        "teammates": teammates,
        "overrides": overrides,
        "coverage_dates": coverage_dates,
    }


# ---------------------------------------------------------------------------
# Property 4: Team deletion cascades all associated data but preserves users
# Feature: multi-team-profiles, Property 4: Team deletion cascades all associated data but preserves users
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    site_code=valid_site_code(),
    data_set=team_data_set(),
)
def test_team_deletion_cascade_preserves_users(site_code, data_set):
    """Property 4: Team deletion cascades all associated data but preserves users.

    **Validates: Requirements 2.1, 2.3, 2.4**

    For any Team_Profile with associated teammates, overrides, coverage requests,
    shift windows, and members, deleting that team SHALL remove all associated
    data rows AND all membership rows, while all user accounts that were members
    continue to exist.
    """
    # Feature: multi-team-profiles, Property 4: Team deletion cascades all associated data but preserves users

    from dc_shiftmaster.database import DatabaseManager

    # Create an in-memory DatabaseManager
    db = DatabaseManager(":memory:")

    # Create a user to be the team creator/admin
    creator_user_id = db.create_user(
        username=f"creator_{site_code}",
        password_hash="hash_placeholder",
        display_name=f"Creator {site_code}",
    )

    # Create a second user to join the team as a member
    member_user_id = db.create_user(
        username=f"member_{site_code}",
        password_hash="hash_placeholder",
        display_name=f"Member {site_code}",
    )

    # Create team
    team = db.create_team(site_code, f"Team {site_code}", creator_user_id)
    team_id = team["id"]

    # Add the second user as a team member
    db.join_team(member_user_id, team_id)

    # Add associated data: teammates
    for name, shift_type in data_set["teammates"]:
        db.add_teammate(name, shift_type, team_id=team_id)

    # Add associated data: overrides
    for date_str, shift_type, name in data_set["overrides"]:
        db.set_override(date_str, shift_type, name, team_id=team_id)

    # Add associated data: coverage requests
    for date_str, shift_type in data_set["coverage_dates"]:
        db.create_coverage_request(
            requester_id=creator_user_id,
            date=date_str,
            shift_type=shift_type,
            note="Test coverage request",
            team_id=team_id,
        )

    # Verify data was actually created
    assert db.get_team_by_site_code(site_code) is not None
    assert len(db.get_teammates(team_id=team_id)) == len(data_set["teammates"])
    assert db.is_team_member(creator_user_id, team_id) is True
    assert db.is_team_member(member_user_id, team_id) is True

    # --- Delete the team ---
    db.delete_team(team_id)

    # Verify: team no longer exists
    assert db.get_team_by_site_code(site_code) is None

    # Verify: no teammates with that team_id remain
    assert db.get_teammates(team_id=team_id) == []

    # Verify: no overrides with that team_id remain
    assert db.get_overrides(2025, team_id=team_id) == []

    # Verify: no coverage requests with that team_id remain
    assert db.get_coverage_requests(team_id=team_id) == []

    # Verify: no shift windows with that team_id remain
    # (get_shift_windows with team_id would try lazy init, use direct query instead)
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM shift_windows WHERE team_id = ?", (team_id,))
    assert cursor.fetchone()[0] == 0

    # Verify: no team membership rows remain for that team
    assert db.is_team_member(creator_user_id, team_id) is False
    assert db.is_team_member(member_user_id, team_id) is False
    assert db.get_team_members(team_id) == []

    # Verify: user accounts still exist (preserved)
    assert db.get_user_by_id(creator_user_id) is not None
    assert db.get_user_by_id(member_user_id) is not None

    # Verify: users can still be looked up by username
    assert db.get_user_by_username(f"creator_{site_code}") is not None
    assert db.get_user_by_username(f"member_{site_code}") is not None

    db.conn.close()


# ---------------------------------------------------------------------------
# Property 2: Team creation assigns creator as admin with resilient shift initialization
# Feature: multi-team-profiles, Property 2: Team creation assigns creator as admin with resilient shift initialization
# ---------------------------------------------------------------------------


@st.composite
def display_name_strategy(draw: st.DrawFn) -> str:
    """Generate a non-empty display name for a team."""
    return draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
            min_size=1,
            max_size=40,
        ).filter(lambda s: s.strip())
    )


@settings(max_examples=100)
@given(site_code=valid_site_code(), name=display_name_strategy())
def test_team_creation_assigns_admin_with_resilient_shift_init(site_code, name):
    """Property 2: Team creation assigns creator as admin with resilient shift initialization.

    **Validates: Requirements 1.1, 1.4**

    For any valid site code and display name, creating a Team_Profile SHALL produce
    a team where the creating user has the "admin" role. IF shift initialization
    succeeds, the team SHALL have exactly two shift windows: day (06:00–18:30)
    and night (18:00–06:30). IF shift initialization fails, the profile SHALL
    still exist and shift windows SHALL be initialized on the next access.
    """
    # Feature: multi-team-profiles, Property 2: Team creation assigns creator as admin with resilient shift initialization

    # Create an in-memory DatabaseManager for each test case
    db = DatabaseManager(":memory:")

    try:
        # Create a user to be the team creator
        creator_id = db.create_user(
            username=f"creator_{site_code}",
            password_hash="hash_placeholder",
            display_name="Creator User",
        )

        # Create the team
        result = db.create_team(site_code, name, creator_id)

        # Verify team was created
        assert result["id"] is not None
        assert result["site_code"] == site_code
        assert result["display_name"] == name
        assert result["role"] == "admin"
        assert result["shift_init_status"] in ("ok", "pending")

        team_id = result["id"]

        # Verify creator has admin role via get_teams_for_user
        user_teams = db.get_teams_for_user(creator_id)
        assert len(user_teams) >= 1
        team_entry = next(t for t in user_teams if t["id"] == team_id)
        assert team_entry["role"] == "admin"
        assert team_entry["site_code"] == site_code

        # Verify shift windows exist with correct defaults
        shift_windows = db.get_shift_windows_for_team(team_id)
        assert "day" in shift_windows
        assert "night" in shift_windows
        assert shift_windows["day"].start_time == "06:00"
        assert shift_windows["day"].end_time == "18:30"
        assert shift_windows["night"].start_time == "18:00"
        assert shift_windows["night"].end_time == "06:30"

        # --- Test resilient shift initialization (simulate failure + lazy retry) ---
        # Delete shift windows to simulate a failed initial shift init
        db.conn.execute(
            "DELETE FROM shift_windows WHERE team_id = ?", (team_id,)
        )
        db.conn.commit()

        # Verify shift windows are gone
        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM shift_windows WHERE team_id = ?", (team_id,)
        )
        assert cursor.fetchone()[0] == 0

        # Access shift windows again — lazy retry should re-create defaults
        shift_windows_retry = db.get_shift_windows_for_team(team_id)
        assert "day" in shift_windows_retry
        assert "night" in shift_windows_retry
        assert shift_windows_retry["day"].start_time == "06:00"
        assert shift_windows_retry["day"].end_time == "18:30"
        assert shift_windows_retry["night"].start_time == "18:00"
        assert shift_windows_retry["night"].end_time == "06:30"

    finally:
        db.conn.close()


# ---------------------------------------------------------------------------
# Property 6: Data isolation with active cross-team rejection
# Feature: multi-team-profiles, Property 6: Data isolation with active cross-team rejection
# ---------------------------------------------------------------------------


@st.composite
def two_teams_with_teammates(draw: st.DrawFn) -> dict:
    """Generate data for two teams, each with a non-empty list of teammates.

    Returns a dict with:
        - team_a_teammates: list of (name, shift_type) for team A
        - team_b_teammates: list of (name, shift_type) for team B
    """
    num_a = draw(st.integers(min_value=1, max_value=5))
    num_b = draw(st.integers(min_value=1, max_value=5))

    team_a_teammates = []
    for i in range(num_a):
        name = draw(teammate_name())
        shift_type = draw(st.sampled_from(VALID_SHIFT_TYPES))
        team_a_teammates.append((f"A_{name}_{i}", shift_type))

    team_b_teammates = []
    for i in range(num_b):
        name = draw(teammate_name())
        shift_type = draw(st.sampled_from(VALID_SHIFT_TYPES))
        team_b_teammates.append((f"B_{name}_{i}", shift_type))

    return {
        "team_a_teammates": team_a_teammates,
        "team_b_teammates": team_b_teammates,
    }


@settings(max_examples=100)
@given(data=two_teams_with_teammates())
def test_data_isolation_with_active_cross_team_rejection(data, tmp_path_factory):
    """Property 6: Data isolation with active cross-team rejection.

    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

    Create two teams with data; query from team A context returns only team A
    data; attempt to access team B resource by ID from team A context raises
    CrossTeamAccessError.
    """
    # Feature: multi-team-profiles, Property 6: Data isolation with active cross-team rejection
    from dc_shiftmaster.database import CrossTeamAccessError, DatabaseManager

    # Create a fresh database for each test run
    db_path = str(tmp_path_factory.mktemp("db") / "test.db")
    db = DatabaseManager(db_path)

    try:
        # Create a user to be the team creator
        user_id = db.create_user("testuser", "hash", "Test User")

        # Create two teams
        team_a = db.create_team("AAA111", "Team Alpha", user_id)
        team_b = db.create_team("BBB222", "Team Beta", user_id)

        team_a_id = team_a["id"]
        team_b_id = team_b["id"]

        # Add teammates to team A
        team_a_ids = []
        for name, shift_type in data["team_a_teammates"]:
            tid = db.add_teammate(name, shift_type, team_id=team_a_id)
            team_a_ids.append(tid)

        # Add teammates to team B
        team_b_ids = []
        for name, shift_type in data["team_b_teammates"]:
            tid = db.add_teammate(name, shift_type, team_id=team_b_id)
            team_b_ids.append(tid)

        # --- Verify query isolation ---
        # get_teammates scoped to team A returns only team A's teammates
        teammates_a = db.get_teammates(team_id=team_a_id)
        teammates_a_names = {t.name for t in teammates_a}
        expected_a_names = {name for name, _ in data["team_a_teammates"]}
        assert teammates_a_names == expected_a_names, (
            f"Team A query returned wrong teammates: {teammates_a_names} != {expected_a_names}"
        )

        # get_teammates scoped to team B returns only team B's teammates
        teammates_b = db.get_teammates(team_id=team_b_id)
        teammates_b_names = {t.name for t in teammates_b}
        expected_b_names = {name for name, _ in data["team_b_teammates"]}
        assert teammates_b_names == expected_b_names, (
            f"Team B query returned wrong teammates: {teammates_b_names} != {expected_b_names}"
        )

        # No overlap: team A teammates should not appear in team B query and vice versa
        assert teammates_a_names.isdisjoint(teammates_b_names)

        # --- Verify active cross-team rejection on update ---
        # Pick a teammate from team B and try to update from team A context
        target_b_id = team_b_ids[0]
        try:
            db.update_teammate(target_b_id, "Hacked Name", "FHD", team_id=team_a_id)
            assert False, "Expected CrossTeamAccessError on cross-team update"
        except CrossTeamAccessError as e:
            assert e.table == "teammates"
            assert e.resource_id == target_b_id
            assert e.expected_team_id == team_a_id
            assert e.actual_team_id == team_b_id

        # --- Verify active cross-team rejection on delete ---
        # Pick a teammate from team B and try to delete from team A context
        try:
            db.delete_teammate(target_b_id, team_id=team_a_id)
            assert False, "Expected CrossTeamAccessError on cross-team delete"
        except CrossTeamAccessError as e:
            assert e.table == "teammates"
            assert e.resource_id == target_b_id
            assert e.expected_team_id == team_a_id
            assert e.actual_team_id == team_b_id

        # Verify team B data is unchanged after rejected operations
        teammates_b_after = db.get_teammates(team_id=team_b_id)
        teammates_b_names_after = {t.name for t in teammates_b_after}
        assert teammates_b_names_after == expected_b_names, (
            "Team B data was modified despite CrossTeamAccessError"
        )

    finally:
        db.conn.close()


# ---------------------------------------------------------------------------
# Property 9: Join creates membership; duplicate join is rejected
# Feature: multi-team-profiles, Property 9: Join creates membership; duplicate join is rejected
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(site_code=valid_site_code())
def test_join_creates_membership_duplicate_join_rejected(site_code):
    """Property 9: Join creates membership; duplicate join is rejected.

    **Validates: Requirements 5.1, 5.2, 5.4**

    For any valid site code, joining a team SHALL produce a membership record
    with a joined_at timestamp and the user SHALL be a member (is_team_member
    returns True). A second join attempt SHALL raise TeamMembershipError with
    code='ALREADY_MEMBER'.
    """
    # Feature: multi-team-profiles, Property 9: Join creates membership; duplicate join is rejected

    from dc_shiftmaster.database import DatabaseManager, TeamMembershipError

    db = DatabaseManager(":memory:")

    try:
        # Create a user who will be the team creator (admin)
        admin_id = db.create_user("admin_user", "hash", "Admin User")

        # Create another user who will join the team
        joiner_id = db.create_user("joiner_user", "hash", "Joiner User")

        # Create a team (admin is automatically a member with admin role)
        team = db.create_team(site_code, f"Team {site_code}", admin_id)
        team_id = team["id"]

        # Verify the joiner is NOT yet a member
        assert db.is_team_member(joiner_id, team_id) is False

        # Join the team
        result = db.join_team(joiner_id, team_id)

        # Verify join_team returns a dict with joined_at timestamp
        assert isinstance(result, dict)
        assert result["user_id"] == joiner_id
        assert result["team_id"] == team_id
        assert result["role"] == "member"
        assert result["joined_at"] is not None
        assert len(result["joined_at"]) > 0  # non-empty timestamp string

        # Verify the user is now a member
        assert db.is_team_member(joiner_id, team_id) is True

        # Attempt to join again — must raise ALREADY_MEMBER
        with pytest.raises(TeamMembershipError) as exc_info:
            db.join_team(joiner_id, team_id)

        assert exc_info.value.code == "ALREADY_MEMBER"

    finally:
        db.conn.close()


# ---------------------------------------------------------------------------
# Property 10: Multi-team membership
# Feature: multi-team-profiles, Property 10: Multi-team membership
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(num_teams=st.integers(min_value=2, max_value=5))
def test_multi_team_membership(num_teams):
    """Property 10: A single user can hold simultaneous membership in multiple teams.

    **Validates: Requirements 5.3**

    For any number of teams (2-5), a single user who creates the first team
    (becoming admin) and joins the remaining teams SHALL be reported as a member
    of ALL those teams by get_teams_for_user, and is_team_member SHALL return
    True for every team.
    """
    # Feature: multi-team-profiles, Property 10: Multi-team membership

    from dc_shiftmaster.database import DatabaseManager

    db = DatabaseManager(":memory:")

    try:
        # Create the user who will join multiple teams
        user_id = db.create_user("multiuser", "hash", "Multi Team User")

        # Create a helper user to own teams beyond the first
        helper_id = db.create_user("helper", "hash", "Helper User")

        # Generate distinct site codes for each team
        team_ids = []
        for i in range(num_teams):
            site_code = f"MTM{i:03d}"  # e.g., MTM000, MTM001, ...

            if i == 0:
                # User creates the first team (becomes admin automatically)
                result = db.create_team(site_code, f"Team {i}", user_id)
                team_ids.append(result["id"])
            else:
                # Helper creates the team, then our user joins it
                result = db.create_team(site_code, f"Team {i}", helper_id)
                team_ids.append(result["id"])
                db.join_team(user_id, result["id"])

        # Verify: get_teams_for_user returns all teams
        user_teams = db.get_teams_for_user(user_id)
        user_team_ids = {t["id"] for t in user_teams}
        assert len(user_team_ids) == num_teams, (
            f"Expected {num_teams} teams, got {len(user_team_ids)}"
        )
        for tid in team_ids:
            assert tid in user_team_ids, (
                f"Team {tid} not found in user's team list"
            )

        # Verify: is_team_member returns True for all teams
        for tid in team_ids:
            assert db.is_team_member(user_id, tid) is True, (
                f"is_team_member returned False for team {tid}"
            )

    finally:
        db.conn.close()


# ---------------------------------------------------------------------------
# Property 13: Sole admin self-removal prevention
# Feature: multi-team-profiles, Property 13: Sole admin self-removal prevention
# ---------------------------------------------------------------------------

from dc_shiftmaster.database import TeamMembershipError


@settings(max_examples=100)
@given(site_code=valid_site_code())
def test_sole_admin_self_removal_prevention(site_code):
    """Property 13: Sole admin self-removal prevention.

    **Validates: Requirements 6.3**

    Sole admin cannot remove themselves; if two admins exist, an admin can
    remove themselves.
    """
    # Feature: multi-team-profiles, Property 13: Sole admin self-removal prevention

    from dc_shiftmaster.database import DatabaseManager, TeamMembershipError

    db = DatabaseManager(":memory:")

    try:
        # Create a user who will be sole admin (team creator)
        admin_user_id = db.create_user(
            username=f"admin_{site_code}",
            password_hash="hash_placeholder",
            display_name="Admin User",
        )

        # Create the team — creator becomes sole admin
        team = db.create_team(site_code, f"Team {site_code}", admin_user_id)
        team_id = team["id"]

        # --- Case 1: Sole admin cannot remove themselves ---
        with pytest.raises(TeamMembershipError) as exc_info:
            db.remove_member(team_id, admin_user_id, requesting_user_id=admin_user_id)

        assert exc_info.value.code == "SOLE_ADMIN"

        # Verify admin is still a member after failed removal
        assert db.is_team_member(admin_user_id, team_id) is True
        assert db.get_user_role(admin_user_id, team_id) == "admin"

        # --- Case 2: With two admins, an admin can remove themselves ---
        # Create a second user and add them to the team
        second_user_id = db.create_user(
            username=f"second_{site_code}",
            password_hash="hash_placeholder",
            display_name="Second Admin",
        )
        db.join_team(second_user_id, team_id)

        # Promote the second user to admin via direct SQL
        db.conn.execute(
            "UPDATE team_members SET role='admin' WHERE team_id=? AND user_id=?",
            (team_id, second_user_id),
        )
        db.conn.commit()

        # Verify second user is now admin
        assert db.get_user_role(second_user_id, team_id) == "admin"

        # Now the first admin should be able to remove themselves
        db.remove_member(team_id, admin_user_id, requesting_user_id=admin_user_id)

        # Verify first admin is no longer a member
        assert db.is_team_member(admin_user_id, team_id) is False

        # Verify second admin is still a member
        assert db.is_team_member(second_user_id, team_id) is True
        assert db.get_user_role(second_user_id, team_id) == "admin"

    finally:
        db.conn.close()


# ---------------------------------------------------------------------------
# Property 12: Non-member removal rejection
# Feature: multi-team-profiles, Property 12: Non-member removal rejection
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(site_code=valid_site_code())
def test_non_member_removal_rejection(site_code):
    """Property 12: Attempting to remove a non-member returns NOT_A_MEMBER error.

    **Validates: Requirements 6.4**

    For any valid team, when an admin attempts to remove a user who is NOT a
    member of the team, the Profile_Service SHALL reject the request and raise
    TeamMembershipError with code='NOT_A_MEMBER'.
    """
    # Feature: multi-team-profiles, Property 12: Non-member removal rejection

    from dc_shiftmaster.database import DatabaseManager, TeamMembershipError

    db = DatabaseManager(":memory:")

    try:
        # Create an admin user who will own the team
        admin_id = db.create_user("admin_user", "hash", "Admin User")

        # Create a second user who will NOT join the team
        non_member_id = db.create_user("non_member", "hash", "Non Member User")

        # Create a team (admin is automatically a member with admin role)
        team = db.create_team(site_code, f"Team {site_code}", admin_id)
        team_id = team["id"]

        # Verify admin is a member
        assert db.is_team_member(admin_id, team_id) is True

        # Verify non_member is NOT a member
        assert db.is_team_member(non_member_id, team_id) is False

        # Admin attempts to remove the non-member — must raise NOT_A_MEMBER
        with pytest.raises(TeamMembershipError) as exc_info:
            db.remove_member(team_id, non_member_id, requesting_user_id=admin_id)

        assert exc_info.value.code == "NOT_A_MEMBER"

    finally:
        db.conn.close()


# ---------------------------------------------------------------------------
# Property 11: Member removal revokes access
# Feature: multi-team-profiles, Property 11: Member removal revokes access
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(site_code=valid_site_code())
def test_member_removal_revokes_access(site_code):
    """Property 11: Member removal revokes access.

    **Validates: Requirements 6.1, 6.5**

    For any Team_Profile and Team_Member, when a Team_Admin removes that member,
    the member SHALL no longer appear in the team's member list and the team
    SHALL no longer appear in the removed user's team list.
    """
    # Feature: multi-team-profiles, Property 11: Member removal revokes access

    from dc_shiftmaster.database import DatabaseManager

    # Create an in-memory DatabaseManager
    db = DatabaseManager(":memory:")

    try:
        # Create an admin user who will own the team
        admin_user_id = db.create_user(
            username=f"admin_{site_code}",
            password_hash="hash_placeholder",
            display_name=f"Admin {site_code}",
        )

        # Create a second user who will be the member to remove
        member_user_id = db.create_user(
            username=f"member_{site_code}",
            password_hash="hash_placeholder",
            display_name=f"Member {site_code}",
        )

        # Create a team (admin_user_id becomes admin)
        team = db.create_team(site_code, f"Team {site_code}", admin_user_id)
        team_id = team["id"]

        # Join the second user to the team
        db.join_team(member_user_id, team_id)

        # Verify: member is part of the team before removal
        assert db.is_team_member(member_user_id, team_id) is True
        members_before = db.get_team_members(team_id)
        member_ids_before = [m["user_id"] for m in members_before]
        assert member_user_id in member_ids_before

        # Verify: team appears in user's team list before removal
        user_teams_before = db.get_teams_for_user(member_user_id)
        team_ids_before = [t["id"] for t in user_teams_before]
        assert team_id in team_ids_before

        # Admin removes the member
        db.remove_member(team_id, member_user_id, requesting_user_id=admin_user_id)

        # Verify: is_team_member returns False for the removed user
        assert db.is_team_member(member_user_id, team_id) is False

        # Verify: removed user NOT in get_team_members
        members_after = db.get_team_members(team_id)
        member_ids_after = [m["user_id"] for m in members_after]
        assert member_user_id not in member_ids_after

        # Verify: team NOT in get_teams_for_user for the removed user
        user_teams_after = db.get_teams_for_user(member_user_id)
        team_ids_after = [t["id"] for t in user_teams_after]
        assert team_id not in team_ids_after

    finally:
        db.conn.close()


# ---------------------------------------------------------------------------
# Property 5: Admin-only operations reject non-admin users
# Feature: multi-team-profiles, Property 5: Admin-only operations reject non-admin users
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(site_code=valid_site_code())
def test_admin_only_operations_reject_non_admin_users(site_code):
    """Property 5: Admin-only operations reject non-admin users.

    **Validates: Requirements 2.2, 6.2**

    For any Team_Profile and any user with "member" role (not "admin"),
    attempting to delete the team or remove a team member SHALL be rejected
    with a permission error (403 PERMISSION_DENIED).
    """
    # Feature: multi-team-profiles, Property 5: Admin-only operations reject non-admin users

    import tempfile
    import os

    from dc_shiftmaster_html.server import create_app

    # Create a fresh app with a temp database for each test iteration
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_admin_only.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    db = app.config["db"]

    try:
        # Create an admin user (team creator)
        admin_id = db.create_user(
            username=f"admin_{site_code}",
            password_hash="hash_placeholder",
            display_name="Admin User",
        )

        # Create a regular member
        member_id = db.create_user(
            username=f"member_{site_code}",
            password_hash="hash_placeholder",
            display_name="Member User",
        )

        # Create a third user to serve as the target for removal attempts
        target_id = db.create_user(
            username=f"target_{site_code}",
            password_hash="hash_placeholder",
            display_name="Target User",
        )

        # Create the team (admin_id becomes admin)
        team = db.create_team(site_code, f"Team {site_code}", admin_id)
        team_id = team["id"]

        # Add member and target to the team
        db.join_team(member_id, team_id)
        db.join_team(target_id, team_id)

        with app.test_client() as client:
            # --- Test 1: Non-admin cannot delete the team ---
            with client.session_transaction() as sess:
                sess["user_id"] = member_id
                sess["active_team_id"] = team_id

            resp = client.delete(f"/api/teams/{team_id}")
            assert resp.status_code == 403
            data = resp.get_json()
            assert data["code"] == "PERMISSION_DENIED"

            # Verify team still exists after failed delete
            assert db.get_team_by_site_code(site_code) is not None

            # --- Test 2: Non-admin cannot remove a member ---
            with client.session_transaction() as sess:
                sess["user_id"] = member_id
                sess["active_team_id"] = team_id

            resp = client.delete(f"/api/teams/{team_id}/members/{target_id}")
            assert resp.status_code == 403
            data = resp.get_json()
            assert data["code"] == "PERMISSION_DENIED"

            # Verify target is still a member after failed removal
            assert db.is_team_member(target_id, team_id) is True

    finally:
        db.conn.close()
        try:
            os.unlink(db_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Property 7: Team selection updates session context
# Feature: multi-team-profiles, Property 7: Team selection updates session context
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(site_code=valid_site_code())
def test_team_selection_updates_session_context(site_code, tmp_path_factory):
    """Property 7: Team selection updates session context.

    **Validates: Requirements 4.2, 8.1**

    For any user who is a member of a team, selecting that team SHALL store the
    team's identifier in the session as `active_team_id`, and subsequent requests
    SHALL carry that context.
    """
    # Feature: multi-team-profiles, Property 7: Team selection updates session context
    from dc_shiftmaster_html.server import create_app

    # Create a fresh app + database for each example
    db_path = str(tmp_path_factory.mktemp("data") / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    with app.test_client() as client:
        db = app.config["db"]

        # Create a user
        user_id = db.create_user(
            username=f"user_{site_code}",
            password_hash="hash_placeholder",
            display_name=f"User {site_code}",
        )

        # Create a team (user becomes admin and member)
        team = db.create_team(site_code, f"Team {site_code}", user_id)
        team_id = team["id"]

        # Set up authenticated session
        with client.session_transaction() as sess:
            sess["user_id"] = user_id

        # Select the team via POST /api/teams/select
        resp = client.post("/api/teams/select", json={"team_id": team_id})
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.get_json()}"
        )

        # Verify response contains active_team_id
        data = resp.get_json()
        assert "active_team_id" in data
        assert data["active_team_id"] == team_id

        # Verify the session now has active_team_id set
        with client.session_transaction() as sess:
            assert "active_team_id" in sess
            assert sess["active_team_id"] == team_id


# ---------------------------------------------------------------------------
# Property 8: Team-scoped endpoints reject missing or invalid team context
# Feature: multi-team-profiles, Property 8: Team-scoped endpoints reject missing or invalid team context
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(site_code=valid_site_code())
def test_team_scoped_endpoints_reject_missing_or_invalid_team_context(site_code):
    """Property 8: Team-scoped endpoints reject missing or invalid team context.

    **Validates: Requirements 8.2, 8.3, 8.4**

    For any team-scoped API endpoint, if the session has no active_team_id the
    request SHALL be rejected with 403 and code NO_TEAM. If the active_team_id
    references a team the user does not belong to, the request SHALL be rejected
    with 403 and code INVALID_TEAM, and the invalid team context SHALL be cleared
    from the session.
    """
    # Feature: multi-team-profiles, Property 8: Team-scoped endpoints reject missing or invalid team context

    from dc_shiftmaster_html.server import create_app

    app = create_app(db_path=":memory:")
    app.config["TESTING"] = True  # needed for test client session handling

    db = app.config["db"]

    # Create a user for our tests
    user_id = db.create_user("prop8_user", "hash", "Property 8 User")

    # Create a team so the user belongs to it
    team = db.create_team(site_code, f"Team {site_code}", user_id)
    team_id = team["id"]

    # Create a second user/team that our user does NOT belong to
    other_user_id = db.create_user("other_user", "hash", "Other User")
    other_team = db.create_team("ZZZ999", "Other Team", other_user_id)
    other_team_id = other_team["id"]

    # Verify our user is NOT a member of the other team
    assert not db.is_team_member(user_id, other_team_id)

    with app.test_client() as client:
        # --- Test 1: NO_TEAM — session has user_id but NO active_team_id ---
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess.pop("active_team_id", None)

        # Override TESTING to False so middleware enforces team context
        app.config["TESTING"] = False

        resp = client.get("/api/teammates")
        assert resp.status_code == 403, (
            f"Expected 403 for missing team context, got {resp.status_code}"
        )
        data = resp.get_json()
        assert data["code"] == "NO_TEAM", (
            f"Expected code NO_TEAM, got {data.get('code')}"
        )

        # Restore TESTING for session manipulation
        app.config["TESTING"] = True

        # --- Test 2: INVALID_TEAM — session has active_team_id for a team
        # the user does NOT belong to ---
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["active_team_id"] = other_team_id

        # Disable TESTING bypass
        app.config["TESTING"] = False

        resp = client.get("/api/teammates")
        assert resp.status_code == 403, (
            f"Expected 403 for invalid team context, got {resp.status_code}"
        )
        data = resp.get_json()
        assert data["code"] == "INVALID_TEAM", (
            f"Expected code INVALID_TEAM, got {data.get('code')}"
        )

        # Verify: active_team_id has been cleared from the session
        app.config["TESTING"] = True
        with client.session_transaction() as sess:
            assert "active_team_id" not in sess, (
                "active_team_id should be cleared from session after INVALID_TEAM"
            )


# ---------------------------------------------------------------------------
# Property 17: Non-Custom shift_type with custom_days is rejected
# Feature: multi-team-profiles, Property 17: Non-Custom shift_type with custom_days is rejected
# ---------------------------------------------------------------------------

VALID_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
NON_CUSTOM_SHIFT_TYPES = ["FHD", "FHN", "BHD", "BHN"]


@st.composite
def non_custom_entry_with_custom_days(draw: st.DrawFn) -> dict:
    """Generate a JSON import entry with a non-Custom shift_type and a custom_days field.

    This combination is invalid per Req 9.7 and should always be rejected.
    """
    name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
            min_size=1,
            max_size=30,
        ).filter(lambda s: s.strip())
    )
    shift_type = draw(st.sampled_from(NON_CUSTOM_SHIFT_TYPES))
    # Generate a non-empty list of valid days
    custom_days = draw(
        st.lists(st.sampled_from(VALID_DAYS), min_size=1, max_size=7, unique=True)
    )
    return {"name": name, "shift_type": shift_type, "custom_days": custom_days}


@settings(max_examples=100, deadline=None)
@given(
    entries=st.lists(non_custom_entry_with_custom_days(), min_size=1, max_size=10)
)
def test_non_custom_shift_type_with_custom_days_rejected(entries):
    """Property 17: Non-Custom shift_type with custom_days is rejected.

    **Validates: Requirements 9.7**

    For any JSON import entry that has a shift_type other than "Custom" and also
    includes a `custom_days` field, that entry SHALL be rejected and reported in
    `skipped_rows` with reason indicating an invalid field combination.
    """
    # Feature: multi-team-profiles, Property 17: Non-Custom shift_type with custom_days is rejected
    import io
    import json

    from dc_shiftmaster_html.server import create_app

    app = create_app(db_path=":memory:")
    app.config["TESTING"] = True

    with app.test_client() as client:
        db = app.config["db"]

        # Create a user and team
        user_id = db.create_user("prop17_user", "hash", "Prop17 User")
        team = db.create_team("AAA111", "Property 17 Team", user_id)
        team_id = team["id"]

        # Set session with user_id and active_team_id
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["active_team_id"] = team_id

        # Build JSON file from generated entries
        json_content = json.dumps(entries).encode("utf-8")
        data = {
            "file": (io.BytesIO(json_content), "import.json"),
        }

        resp = client.post(
            "/api/teams/import-json",
            content_type="multipart/form-data",
            data=data,
        )

        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.get_json()}"
        )

        result = resp.get_json()

        # All entries should be rejected — imported_count must be 0
        assert result["imported_count"] == 0, (
            f"Expected 0 imported, got {result['imported_count']}. "
            f"Entries: {entries}, Result: {result}"
        )

        # All entries should appear in skipped_rows
        assert len(result["skipped_rows"]) == len(entries), (
            f"Expected {len(entries)} skipped rows, got {len(result['skipped_rows'])}. "
            f"Result: {result}"
        )

        # Each skipped row should have the correct rejection reason
        expected_reason = (
            "Invalid field combination: custom_days not allowed for non-Custom shift_type"
        )
        for i, skipped in enumerate(result["skipped_rows"]):
            assert skipped["index"] == i, (
                f"Expected index {i}, got {skipped['index']}"
            )
            assert skipped["reason"] == expected_reason, (
                f"Expected reason '{expected_reason}', got '{skipped['reason']}' "
                f"for entry {entries[i]}"
            )


# ---------------------------------------------------------------------------
# Property 16: JSON import creates valid entries and filters invalid ones
# Feature: multi-team-profiles, Property 16: JSON import creates valid entries and filters invalid ones
# ---------------------------------------------------------------------------

import io
import json as json_module

from hypothesis import given, settings, strategies as st, HealthCheck


@st.composite
def valid_json_entry(draw: st.DrawFn) -> dict:
    """Generate a valid teammate JSON entry.

    Produces entries with valid name, valid shift_type, and if Custom,
    a non-empty list of valid day abbreviations.
    """
    name = draw(st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=20,
    ).filter(lambda s: s.strip()))
    shift_type = draw(st.sampled_from(["FHD", "FHN", "BHD", "BHN", "Custom"]))

    entry = {"name": name, "shift_type": shift_type}

    if shift_type == "Custom":
        days = draw(st.lists(
            st.sampled_from(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]),
            min_size=1,
            max_size=7,
            unique=True,
        ))
        entry["custom_days"] = days

    return entry


@st.composite
def invalid_json_entry(draw: st.DrawFn) -> dict:
    """Generate an invalid teammate JSON entry.

    Returns one of:
    - Entry with no name field
    - Entry with an invalid shift_type value
    - Custom shift_type with empty custom_days
    - Non-Custom shift_type with custom_days present
    """
    kind = draw(st.sampled_from([
        "missing_name", "bad_shift_type", "custom_empty_days", "non_custom_with_days"
    ]))

    if kind == "missing_name":
        return {"shift_type": draw(st.sampled_from(["FHD", "FHN", "BHD", "BHN"]))}

    elif kind == "bad_shift_type":
        name = draw(st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=1, max_size=10,
        ).filter(lambda s: s.strip()))
        bad_type = draw(st.text(min_size=1, max_size=5).filter(
            lambda s: s not in ("FHD", "FHN", "BHD", "BHN", "Custom")
        ))
        return {"name": name, "shift_type": bad_type}

    elif kind == "custom_empty_days":
        name = draw(st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=1, max_size=10,
        ).filter(lambda s: s.strip()))
        return {"name": name, "shift_type": "Custom", "custom_days": []}

    else:  # non_custom_with_days
        name = draw(st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=1, max_size=10,
        ).filter(lambda s: s.strip()))
        shift_type = draw(st.sampled_from(["FHD", "FHN", "BHD", "BHN"]))
        days = draw(st.lists(
            st.sampled_from(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]),
            min_size=1, max_size=3,
            unique=True,
        ))
        return {"name": name, "shift_type": shift_type, "custom_days": days}


@st.composite
def mixed_json_import_data(draw: st.DrawFn) -> tuple:
    """Generate a mixed list of valid and invalid JSON entries for import.

    Returns a tuple of (entries_list, valid_indices, invalid_indices).
    Entries are placed in a deterministic interleaved order: all valid entries
    first, then all invalid entries.
    """
    num_valid = draw(st.integers(min_value=1, max_value=5))
    num_invalid = draw(st.integers(min_value=1, max_value=5))

    valid_entries = [draw(valid_json_entry()) for _ in range(num_valid)]
    invalid_entries = [draw(invalid_json_entry()) for _ in range(num_invalid)]

    # Interleave: valid at even positions, invalid at odd positions
    entries = []
    valid_indices = set()
    invalid_indices = set()
    vi, ii = 0, 0
    idx = 0
    while vi < num_valid or ii < num_invalid:
        if vi < num_valid:
            entries.append(valid_entries[vi])
            valid_indices.add(idx)
            vi += 1
            idx += 1
        if ii < num_invalid:
            entries.append(invalid_entries[ii])
            invalid_indices.add(idx)
            ii += 1
            idx += 1

    return (entries, valid_indices, invalid_indices)


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(data=mixed_json_import_data())
def test_json_import_creates_valid_entries_and_filters_invalid(data):
    """Property 16: JSON import creates valid entries and filters invalid ones.

    **Validates: Requirements 9.1, 9.2, 9.3, 9.5, 9.6, 9.7**

    For any JSON array containing a mix of valid teammate objects and invalid ones
    (missing name, invalid shift_type, Custom with empty/invalid days, non-Custom
    with custom_days present), the import SHALL create records only for valid entries
    and SHALL report all invalid entries in the skipped_rows list with appropriate
    reasons.
    """
    # Feature: multi-team-profiles, Property 16: JSON import creates valid entries and filters invalid ones

    from dc_shiftmaster_html.server import create_app

    entries, valid_indices, invalid_indices = data

    # Create a fresh app with in-memory DB for each test iteration
    app = create_app(db_path=":memory:")
    app.config["TESTING"] = True

    db = app.config["db"]

    # Create user and team
    user_id = db.create_user("import_user", "hash", "Import User")
    team = db.create_team("IMP001", "Import Team", user_id)
    team_id = team["id"]

    with app.test_client() as client:
        # Set up authenticated session with active team
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["active_team_id"] = team_id

        # Prepare JSON payload
        json_bytes = json_module.dumps(entries).encode("utf-8")

        # Send multipart form request
        resp = client.post(
            "/api/teams/import-json",
            data={"file": (io.BytesIO(json_bytes), "import.json")},
            content_type="multipart/form-data",
        )

        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.get_json()}"
        )

        result = resp.get_json()

        # Verify imported_count is non-negative and at most the number of valid entries
        assert result["imported_count"] >= 0
        assert result["imported_count"] <= len(valid_indices)

        # Verify all invalid entries appear in skipped_rows
        skipped_indices = {row["index"] for row in result["skipped_rows"]}
        for idx in invalid_indices:
            assert idx in skipped_indices, (
                f"Invalid entry at index {idx} was not in skipped_rows. "
                f"Entry: {entries[idx]}, Skipped: {result['skipped_rows']}"
            )

        # Verify each skipped row has an index and a non-empty reason
        for row in result["skipped_rows"]:
            assert "index" in row
            assert "reason" in row
            assert len(row["reason"]) > 0

        # Verify the count invariant holds:
        # imported_count + len(skipped_rows) + duplicate_count == total entries
        total_entries = len(entries)
        assert (
            result["imported_count"]
            + len(result["skipped_rows"])
            + result["duplicate_count"]
            == total_entries
        ), (
            f"Count invariant failed: {result['imported_count']} + "
            f"{len(result['skipped_rows'])} + {result['duplicate_count']} "
            f"!= {total_entries}"
        )

        # Verify the number of teammates in DB matches imported_count
        teammates = db.get_teammates(team_id=team_id)
        assert len(teammates) == result["imported_count"], (
            f"DB has {len(teammates)} teammates but imported_count is "
            f"{result['imported_count']}"
        )

    db.conn.close()


# ---------------------------------------------------------------------------
# Property 18: JSON import deduplication
# Feature: multi-team-profiles, Property 18: JSON import deduplication
# ---------------------------------------------------------------------------


@st.composite
def dedup_import_data(draw: st.DrawFn) -> dict:
    """Generate data for deduplication testing.

    Returns a dict with:
        - existing_names: list of names already in the team (1-5)
        - new_names: list of unique new names to import (1-5)
        - overlap_indices: which existing names to duplicate in import (case variations)
    """
    # Generate existing teammate names (1-5)
    num_existing = draw(st.integers(min_value=1, max_value=5))
    existing_names = [f"Existing_{i}" for i in range(num_existing)]

    # Generate new unique names that don't collide with existing (1-5)
    num_new = draw(st.integers(min_value=1, max_value=5))
    new_names = [f"NewPerson_{i}" for i in range(num_new)]

    # Decide how many existing names to include as duplicates (0 to num_existing)
    num_duplicates = draw(st.integers(min_value=0, max_value=num_existing))
    # Pick which existing names to duplicate
    duplicate_indices = draw(
        st.lists(
            st.integers(min_value=0, max_value=num_existing - 1),
            min_size=num_duplicates,
            max_size=num_duplicates,
            unique=True,
        )
    )

    # For each duplicate, optionally change case to test case-insensitive dedup
    duplicate_names = []
    for idx in duplicate_indices:
        original = existing_names[idx]
        # Randomly choose a case variation
        variation = draw(st.sampled_from(["same", "upper", "lower", "title"]))
        if variation == "same":
            duplicate_names.append(original)
        elif variation == "upper":
            duplicate_names.append(original.upper())
        elif variation == "lower":
            duplicate_names.append(original.lower())
        else:
            duplicate_names.append(original.title())

    return {
        "existing_names": existing_names,
        "new_names": new_names,
        "duplicate_names": duplicate_names,
    }


@settings(max_examples=100, deadline=None)
@given(data=dedup_import_data())
def test_json_import_deduplication(data):
    """Property 18: JSON import deduplication.

    **Validates: Requirements 9.4**

    For any team with existing teammates and a JSON import containing entries
    with names that already exist in that team (case-insensitive), those
    duplicate entries SHALL be skipped and reported as duplicates, while new
    unique names SHALL be imported successfully.
    """
    # Feature: multi-team-profiles, Property 18: JSON import deduplication

    import io
    import json
    import tempfile
    import os

    from dc_shiftmaster_html.server import create_app

    # Create a fresh app with a temp database
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_dedup.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    db = app.config["db"]

    try:
        # Create a user (admin)
        user_id = db.create_user(
            username="dedup_admin",
            password_hash="hash_placeholder",
            display_name="Dedup Admin",
        )

        # Create a team
        team = db.create_team("DDP001", "Dedup Team", user_id)
        team_id = team["id"]

        # Pre-populate team with existing teammates
        for name in data["existing_names"]:
            db.add_teammate(name, "FHD", team_id=team_id)

        # Build the JSON import payload:
        # - duplicate_names: should be detected as duplicates (case-insensitive)
        # - new_names: should be imported successfully
        import_entries = []
        for name in data["duplicate_names"]:
            import_entries.append({"name": name, "shift_type": "FHD"})
        for name in data["new_names"]:
            import_entries.append({"name": name, "shift_type": "BHD"})

        json_content = json.dumps(import_entries)

        with app.test_client() as client:
            # Set session with user_id and active_team_id
            with client.session_transaction() as sess:
                sess["user_id"] = user_id
                sess["active_team_id"] = team_id

            # POST the JSON file to the import endpoint
            resp = client.post(
                "/api/teams/import-json",
                data={
                    "file": (io.BytesIO(json_content.encode("utf-8")), "import.json"),
                },
                content_type="multipart/form-data",
            )

            assert resp.status_code == 200, (
                f"Expected 200, got {resp.status_code}: {resp.get_json()}"
            )

            result = resp.get_json()

            # Verify: duplicate_count matches the number of duplicate names
            expected_duplicate_count = len(data["duplicate_names"])
            assert result["duplicate_count"] == expected_duplicate_count, (
                f"Expected duplicate_count={expected_duplicate_count}, "
                f"got {result['duplicate_count']}"
            )

            # Verify: imported_count matches the number of new names
            expected_imported_count = len(data["new_names"])
            assert result["imported_count"] == expected_imported_count, (
                f"Expected imported_count={expected_imported_count}, "
                f"got {result['imported_count']}"
            )

            # Verify: skipped_rows should be empty (all entries are valid)
            assert result["skipped_rows"] == [], (
                f"Expected no skipped rows, got {result['skipped_rows']}"
            )

            # Verify: total teammates in team = existing + new
            all_teammates = db.get_teammates(team_id=team_id)
            expected_total = len(data["existing_names"]) + len(data["new_names"])
            assert len(all_teammates) == expected_total, (
                f"Expected {expected_total} total teammates, got {len(all_teammates)}"
            )

            # Verify: new names are actually present in the team
            all_names_lower = {t.name.lower() for t in all_teammates}
            for new_name in data["new_names"]:
                assert new_name.lower() in all_names_lower, (
                    f"New name '{new_name}' not found in team after import"
                )

    finally:
        db.conn.close()
        try:
            os.unlink(db_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Property 19: JSON export/import round-trip
# Feature: multi-team-profiles, Property 19: JSON export/import round-trip
# ---------------------------------------------------------------------------


VALID_DAYS_LIST = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@st.composite
def teammate_entries_for_roundtrip(draw: st.DrawFn) -> list:
    """Generate a list of valid teammate entries for round-trip testing.

    Each entry has a unique name, a valid shift_type, and appropriate
    custom_start / custom_days fields.
    """
    num = draw(st.integers(min_value=1, max_value=8))
    entries = []
    used_names = set()
    for i in range(num):
        # Generate a unique name
        base_name = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N")),
                min_size=1,
                max_size=15,
            ).filter(lambda s: s.strip())
        )
        name = f"{base_name}_{i}"
        if name.lower() in used_names:
            name = f"{name}_x"
        used_names.add(name.lower())

        shift_type = draw(st.sampled_from(["FHD", "FHN", "BHD", "BHN", "Custom"]))

        custom_start = ""
        custom_days = []

        if shift_type == "Custom":
            # Generate 1-7 valid days
            num_days = draw(st.integers(min_value=1, max_value=7))
            custom_days = draw(
                st.lists(
                    st.sampled_from(VALID_DAYS_LIST),
                    min_size=num_days,
                    max_size=num_days,
                    unique=True,
                )
            )

        entries.append({
            "name": name,
            "shift_type": shift_type,
            "custom_start": custom_start,
            "custom_days": custom_days,
        })

    return entries


@settings(max_examples=100, deadline=None)
@given(
    site_code_a=valid_site_code(),
    site_code_b=valid_site_code(),
    teammates=teammate_entries_for_roundtrip(),
)
def test_json_export_import_roundtrip(site_code_a, site_code_b, teammates):
    """Property 19: JSON export/import round-trip.

    **Validates: Requirements 9.8**

    Export teammates as JSON from team A via GET /api/teammates, import into a
    fresh team B via POST /api/teams/import-json, then verify team B has
    identical teammate names and shift types as team A.
    """
    # Feature: multi-team-profiles, Property 19: JSON export/import round-trip

    import io
    from hypothesis import assume
    from dc_shiftmaster_html.server import create_app

    # Ensure site codes are different so we can create two distinct teams
    assume(site_code_a != site_code_b)

    app = create_app(db_path=":memory:")
    app.config["TESTING"] = True

    db = app.config["db"]

    # Create a user
    user_id = db.create_user("roundtrip_user", "hash", "Round Trip User")

    # Create team A
    team_a = db.create_team(site_code_a, f"Team A {site_code_a}", user_id)
    team_a_id = team_a["id"]

    # Create team B
    team_b = db.create_team(site_code_b, f"Team B {site_code_b}", user_id)
    team_b_id = team_b["id"]

    with app.test_client() as client:
        # Authenticate and select team A
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["active_team_id"] = team_a_id

        # Add teammates to team A via the API
        for entry in teammates:
            payload = {
                "name": entry["name"],
                "shift_type": entry["shift_type"],
            }
            if entry["custom_start"]:
                payload["custom_start"] = entry["custom_start"]
            if entry["custom_days"]:
                payload["custom_days"] = entry["custom_days"]
            resp = client.post("/api/teammates", json=payload)
            assert resp.status_code == 201, (
                f"Failed to add teammate {entry['name']}: {resp.get_json()}"
            )

        # Export: GET /api/teammates from team A
        export_resp = client.get("/api/teammates")
        assert export_resp.status_code == 200
        exported_json = export_resp.get_json()

        # Verify export has the same count as input
        assert len(exported_json) == len(teammates)

        # Switch to team B and import the exported JSON
        with client.session_transaction() as sess:
            sess["active_team_id"] = team_b_id

        # The import endpoint expects a multipart file upload with JSON content
        import_data = io.BytesIO(
            __import__("json").dumps(exported_json).encode("utf-8")
        )
        resp = client.post(
            "/api/teams/import-json",
            data={"file": (import_data, "export.json")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200, (
            f"Import failed: {resp.get_json()}"
        )
        import_result = resp.get_json()

        # All entries should be imported (no duplicates since team B is fresh)
        assert import_result["imported_count"] == len(teammates), (
            f"Expected {len(teammates)} imported, got {import_result['imported_count']}. "
            f"Skipped: {import_result.get('skipped_rows')}, "
            f"Duplicates: {import_result.get('duplicate_count')}"
        )
        assert import_result["duplicate_count"] == 0
        assert len(import_result["skipped_rows"]) == 0

        # Verify: GET /api/teammates from team B should match team A
        team_b_resp = client.get("/api/teammates")
        assert team_b_resp.status_code == 200
        team_b_teammates = team_b_resp.get_json()

        assert len(team_b_teammates) == len(teammates)

        # Build lookup by name for comparison
        team_b_by_name = {t["name"]: t for t in team_b_teammates}

        for original in teammates:
            assert original["name"] in team_b_by_name, (
                f"Teammate '{original['name']}' not found in team B after import"
            )
            imported = team_b_by_name[original["name"]]
            assert imported["shift_type"] == original["shift_type"], (
                f"Shift type mismatch for '{original['name']}': "
                f"expected {original['shift_type']}, got {imported['shift_type']}"
            )
            # For Custom shift types, verify custom_days match (as sets)
            if original["shift_type"] == "Custom":
                assert set(imported["custom_days"]) == set(original["custom_days"]), (
                    f"Custom days mismatch for '{original['name']}': "
                    f"expected {original['custom_days']}, got {imported['custom_days']}"
                )


# ---------------------------------------------------------------------------
# Property 20: Import summary counts invariant
# Feature: multi-team-profiles, Property 20: Import summary counts invariant
# ---------------------------------------------------------------------------

VALID_DAYS_LIST = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
IMPORT_VALID_SHIFT_TYPES = ["FHD", "FHN", "BHD", "BHN", "Custom"]


@st.composite
def import_entry(draw: st.DrawFn) -> dict:
    """Generate a random JSON import entry — may be valid, invalid, or a duplicate trigger.

    Produces a mix of:
    - Valid entries with proper name + shift_type (+ custom_days for Custom)
    - Invalid entries: missing name, empty name, invalid shift_type
    - Entries with non-Custom shift_type that include custom_days (invalid combo)
    - Non-dict entries (invalid structure)
    """
    entry_type = draw(st.sampled_from([
        "valid_standard",
        "valid_custom",
        "missing_name",
        "empty_name",
        "invalid_shift_type",
        "non_custom_with_custom_days",
        "custom_missing_days",
        "custom_invalid_days",
        "not_a_dict",
    ]))

    if entry_type == "valid_standard":
        name = draw(st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1, max_size=20,
        ).filter(lambda s: s.strip()))
        shift_type = draw(st.sampled_from(["FHD", "FHN", "BHD", "BHN"]))
        return {"name": name, "shift_type": shift_type}

    elif entry_type == "valid_custom":
        name = draw(st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1, max_size=20,
        ).filter(lambda s: s.strip()))
        days = draw(st.lists(
            st.sampled_from(VALID_DAYS_LIST),
            min_size=1, max_size=7, unique=True,
        ))
        return {"name": name, "shift_type": "Custom", "custom_days": days}

    elif entry_type == "missing_name":
        shift_type = draw(st.sampled_from(IMPORT_VALID_SHIFT_TYPES))
        return {"shift_type": shift_type}

    elif entry_type == "empty_name":
        shift_type = draw(st.sampled_from(IMPORT_VALID_SHIFT_TYPES))
        return {"name": "", "shift_type": shift_type}

    elif entry_type == "invalid_shift_type":
        name = draw(st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1, max_size=20,
        ).filter(lambda s: s.strip()))
        bad_type = draw(st.text(min_size=1, max_size=10).filter(
            lambda s: s not in IMPORT_VALID_SHIFT_TYPES
        ))
        return {"name": name, "shift_type": bad_type}

    elif entry_type == "non_custom_with_custom_days":
        name = draw(st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1, max_size=20,
        ).filter(lambda s: s.strip()))
        shift_type = draw(st.sampled_from(["FHD", "FHN", "BHD", "BHN"]))
        days = draw(st.lists(
            st.sampled_from(VALID_DAYS_LIST),
            min_size=1, max_size=3, unique=True,
        ))
        return {"name": name, "shift_type": shift_type, "custom_days": days}

    elif entry_type == "custom_missing_days":
        name = draw(st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1, max_size=20,
        ).filter(lambda s: s.strip()))
        return {"name": name, "shift_type": "Custom"}

    elif entry_type == "custom_invalid_days":
        name = draw(st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1, max_size=20,
        ).filter(lambda s: s.strip()))
        invalid_days = draw(st.lists(
            st.text(min_size=1, max_size=5).filter(
                lambda d: d not in VALID_DAYS_LIST
            ),
            min_size=1, max_size=3,
        ))
        return {"name": name, "shift_type": "Custom", "custom_days": invalid_days}

    else:  # not_a_dict
        return draw(st.sampled_from(["string_entry", 42, None, True, [1, 2]]))


@settings(max_examples=100, deadline=None)
@given(entries=st.lists(import_entry(), min_size=0, max_size=15))
def test_import_summary_counts_invariant(entries, tmp_path_factory):
    """Property 20: Import summary counts invariant.

    **Validates: Requirements 9.9**

    For any import, the sum of imported_count + len(skipped_rows) + duplicate_count
    SHALL equal the total number of entries in the input JSON array.
    """
    # Feature: multi-team-profiles, Property 20: Import summary counts invariant
    import io
    import json
    from dc_shiftmaster_html.server import create_app

    db_path = str(tmp_path_factory.mktemp("data") / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    db = app.config["db"]

    # Create a user and a team
    user_id = db.create_user("import_user", "hash", "Import User")
    team = db.create_team("IMP001", "Import Team", user_id)
    team_id = team["id"]

    with app.test_client() as client:
        # Set up authenticated session with active team
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["active_team_id"] = team_id

        # Build the JSON file content
        json_content = json.dumps(entries)

        # Send the import request
        data = {
            "file": (io.BytesIO(json_content.encode("utf-8")), "import.json"),
        }
        resp = client.post(
            "/api/teams/import-json",
            data=data,
            content_type="multipart/form-data",
        )

        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.get_json()}"
        )

        result = resp.get_json()
        imported_count = result["imported_count"]
        skipped_rows = result["skipped_rows"]
        duplicate_count = result["duplicate_count"]

        # THE INVARIANT: imported + skipped + duplicates == total input entries
        total_entries = len(entries)
        actual_sum = imported_count + len(skipped_rows) + duplicate_count

        assert actual_sum == total_entries, (
            f"Invariant violated: imported({imported_count}) + "
            f"skipped({len(skipped_rows)}) + duplicates({duplicate_count}) = "
            f"{actual_sum} != total entries({total_entries}). "
            f"Input: {entries}"
        )


# ---------------------------------------------------------------------------
# Property 14: Migration atomicity
# Feature: multi-team-profiles, Property 14: Migration atomicity
# ---------------------------------------------------------------------------


class FailingConnectionProxy:
    """A proxy around sqlite3.Connection that raises after a specified number of execute calls.

    Transaction management statements (BEGIN, ROLLBACK, COMMIT) are always
    passed through so the migration's rollback logic can function normally.
    """

    def __init__(self, real_conn: sqlite3.Connection, fail_at_step: int):
        self._conn = real_conn
        self._fail_at_step = fail_at_step
        self._call_count = 0

    def execute(self, sql, *args, **kwargs):
        sql_upper = sql.strip().upper()
        # Always allow transaction control statements through
        if sql_upper.startswith(("BEGIN", "ROLLBACK", "COMMIT")):
            return self._conn.execute(sql, *args, **kwargs)
        self._call_count += 1
        if self._call_count >= self._fail_at_step:
            raise RuntimeError(
                f"Simulated failure at execute call #{self._call_count}"
            )
        return self._conn.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        """Delegate all other attribute access to the real connection."""
        return getattr(self._conn, name)


@settings(max_examples=100)
@given(state=initial_db_state(), fail_at_step=st.integers(min_value=1, max_value=10))
def test_migration_atomicity(state, fail_at_step):
    """Property 14: Migration atomicity.

    **Validates: Requirements 7.6**

    For any database state, if the Migration_Service encounters a failure at any
    step during execution, it SHALL roll back all changes so that the database
    remains in its original pre-migration state with no partial data.
    """
    # Feature: multi-team-profiles, Property 14: Migration atomicity

    # Create a fresh database with seeded state
    conn = create_test_db(state)

    # Take a snapshot of the pre-migration state
    pre_migration_snapshot = snapshot_db(conn)

    # Create a proxy that will fail at the designated step
    proxy = FailingConnectionProxy(conn, fail_at_step)

    # Run the migration — should raise MigrationError due to our injected failure
    with pytest.raises(MigrationError):
        run_migration(proxy)

    # Verify: database state is identical to pre-migration snapshot (no partial data)
    post_failure_snapshot = snapshot_db(conn)

    assert pre_migration_snapshot == post_failure_snapshot, (
        f"Database state changed after failed migration!\n"
        f"Failed at step {fail_at_step}.\n"
        f"Pre-migration: {pre_migration_snapshot}\n"
        f"Post-failure:  {post_failure_snapshot}"
    )

    conn.close()
