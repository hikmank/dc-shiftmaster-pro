"""Unit tests for team profile CRUD methods in DatabaseManager.

Tests create_team, delete_team, get_teams_for_user, get_team_by_site_code,
get_shift_windows_for_team, and site code validation.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.3, 2.4
"""

import sqlite3

import pytest

from dc_shiftmaster.database import DatabaseManager


@pytest.fixture
def db(tmp_path):
    """Provide a fresh DatabaseManager with a temp database."""
    db_path = str(tmp_path / "test_team.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.conn.close()


@pytest.fixture
def db_with_user(db):
    """Provide a DatabaseManager with a pre-created user."""
    user_id = db.create_user("testuser", "hash123", "Test User")
    return db, user_id


class TestSiteCodeValidation:
    """Tests for site code format validation (Req 1.3, 1.5)."""

    def test_valid_site_codes(self, db_with_user):
        """Valid site codes should be accepted."""
        db, user_id = db_with_user
        valid_codes = ["ATL069", "CMH078", "NRT001", "ZZZ999", "ABC123"]
        for code in valid_codes:
            result = db.create_team(code, f"Team {code}", user_id)
            assert result["site_code"] == code

    def test_empty_site_code_raises(self, db_with_user):
        """Empty site code should raise ValueError."""
        db, user_id = db_with_user
        with pytest.raises(ValueError, match="must not be empty"):
            db.create_team("", "My Team", user_id)

    def test_lowercase_letters_rejected(self, db_with_user):
        """Lowercase letters in site code should be rejected."""
        db, user_id = db_with_user
        with pytest.raises(ValueError, match="Invalid site code"):
            db.create_team("atl069", "My Team", user_id)

    def test_too_short_rejected(self, db_with_user):
        """Site codes shorter than 6 chars should be rejected."""
        db, user_id = db_with_user
        with pytest.raises(ValueError, match="Invalid site code"):
            db.create_team("AT069", "My Team", user_id)

    def test_too_long_rejected(self, db_with_user):
        """Site codes longer than 6 chars should be rejected."""
        db, user_id = db_with_user
        with pytest.raises(ValueError, match="Invalid site code"):
            db.create_team("ATLA0690", "My Team", user_id)

    def test_letters_in_digit_positions_rejected(self, db_with_user):
        """Letters in the digit positions should be rejected."""
        db, user_id = db_with_user
        with pytest.raises(ValueError, match="Invalid site code"):
            db.create_team("ATLXYZ", "My Team", user_id)

    def test_digits_in_letter_positions_rejected(self, db_with_user):
        """Digits in the letter positions should be rejected."""
        db, user_id = db_with_user
        with pytest.raises(ValueError, match="Invalid site code"):
            db.create_team("123069", "My Team", user_id)

    def test_special_chars_rejected(self, db_with_user):
        """Special characters should be rejected."""
        db, user_id = db_with_user
        with pytest.raises(ValueError, match="Invalid site code"):
            db.create_team("AT!069", "My Team", user_id)


class TestCreateTeam:
    """Tests for create_team method (Req 1.1, 1.2, 1.4)."""

    def test_creates_team_with_correct_fields(self, db_with_user):
        """create_team should return dict with all expected fields."""
        db, user_id = db_with_user
        result = db.create_team("ATL069", "ATL069 Day Crew", user_id)
        assert result["site_code"] == "ATL069"
        assert result["display_name"] == "ATL069 Day Crew"
        assert result["role"] == "admin"
        assert result["shift_init_status"] == "ok"
        assert "id" in result
        assert "created_at" in result

    def test_creator_is_admin_member(self, db_with_user):
        """Creator should be added as an admin member of the team."""
        db, user_id = db_with_user
        result = db.create_team("ATL069", "Team", user_id)
        teams = db.get_teams_for_user(user_id)
        assert len(teams) == 1
        assert teams[0]["role"] == "admin"
        assert teams[0]["id"] == result["id"]

    def test_default_shift_windows_created(self, db_with_user):
        """Default shift windows (day/night) should be created for the team."""
        db, user_id = db_with_user
        result = db.create_team("ATL069", "Team", user_id)
        shifts = db.get_shift_windows_for_team(result["id"])
        assert "day" in shifts
        assert "night" in shifts
        assert shifts["day"].start_time == "06:00"
        assert shifts["day"].end_time == "18:30"
        assert shifts["night"].start_time == "18:00"
        assert shifts["night"].end_time == "06:30"

    def test_duplicate_site_code_raises_integrity_error(self, db_with_user):
        """Duplicate site code should raise IntegrityError."""
        db, user_id = db_with_user
        db.create_team("ATL069", "Team 1", user_id)
        with pytest.raises(sqlite3.IntegrityError):
            db.create_team("ATL069", "Team 2", user_id)

    def test_team_id_auto_increments(self, db_with_user):
        """Each new team should get a unique auto-incremented ID."""
        db, user_id = db_with_user
        t1 = db.create_team("ATL069", "Team 1", user_id)
        t2 = db.create_team("CMH078", "Team 2", user_id)
        assert t2["id"] > t1["id"]


class TestDeleteTeam:
    """Tests for delete_team method (Req 2.1, 2.3, 2.4)."""

    def test_delete_removes_team(self, db_with_user):
        """delete_team should remove the team profile."""
        db, user_id = db_with_user
        result = db.create_team("ATL069", "Team", user_id)
        db.delete_team(result["id"])
        assert db.get_team_by_site_code("ATL069") is None

    def test_delete_cascades_membership(self, db_with_user):
        """Deleting a team should remove all team memberships."""
        db, user_id = db_with_user
        result = db.create_team("ATL069", "Team", user_id)
        db.delete_team(result["id"])
        teams = db.get_teams_for_user(user_id)
        assert len(teams) == 0

    def test_delete_cascades_shift_windows(self, db_with_user):
        """Deleting a team should remove its shift windows."""
        db, user_id = db_with_user
        result = db.create_team("ATL069", "Team", user_id)
        db.delete_team(result["id"])
        # get_shift_windows_for_team will try lazy retry, but let's check raw
        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM shift_windows WHERE team_id = ?",
            (result["id"],),
        )
        assert cursor.fetchone()[0] == 0

    def test_delete_preserves_user_accounts(self, db_with_user):
        """Deleting a team should preserve the user accounts."""
        db, user_id = db_with_user
        result = db.create_team("ATL069", "Team", user_id)
        db.delete_team(result["id"])
        user = db.get_user_by_id(user_id)
        assert user is not None
        assert user.username == "testuser"

    def test_delete_nonexistent_team_is_noop(self, db_with_user):
        """Deleting a non-existent team should not raise."""
        db, user_id = db_with_user
        db.delete_team(99999)  # Should not raise


class TestGetTeamsForUser:
    """Tests for get_teams_for_user method."""

    def test_returns_empty_for_user_with_no_teams(self, db_with_user):
        """User with no team memberships should get empty list."""
        db, user_id = db_with_user
        # Create a second user with no teams
        user2_id = db.create_user("user2", "hash2", "User 2")
        teams = db.get_teams_for_user(user2_id)
        assert teams == []

    def test_returns_all_teams_for_user(self, db_with_user):
        """User who is member of multiple teams should see all."""
        db, user_id = db_with_user
        db.create_team("ATL069", "Team 1", user_id)
        db.create_team("CMH078", "Team 2", user_id)
        teams = db.get_teams_for_user(user_id)
        assert len(teams) == 2
        site_codes = {t["site_code"] for t in teams}
        assert site_codes == {"ATL069", "CMH078"}

    def test_includes_role_and_joined_at(self, db_with_user):
        """Returned team records should include role and joined_at."""
        db, user_id = db_with_user
        db.create_team("ATL069", "Team 1", user_id)
        teams = db.get_teams_for_user(user_id)
        assert teams[0]["role"] == "admin"
        assert teams[0]["joined_at"] is not None


class TestGetTeamBySiteCode:
    """Tests for get_team_by_site_code method."""

    def test_returns_team_when_exists(self, db_with_user):
        """Should return team dict when site code exists."""
        db, user_id = db_with_user
        created = db.create_team("ATL069", "Day Crew", user_id)
        found = db.get_team_by_site_code("ATL069")
        assert found is not None
        assert found["id"] == created["id"]
        assert found["site_code"] == "ATL069"
        assert found["display_name"] == "Day Crew"

    def test_returns_none_when_not_found(self, db_with_user):
        """Should return None when site code doesn't exist."""
        db, user_id = db_with_user
        assert db.get_team_by_site_code("ZZZ999") is None


class TestGetShiftWindowsForTeam:
    """Tests for get_shift_windows_for_team with lazy retry (Req 1.4)."""

    def test_returns_default_shifts_after_creation(self, db_with_user):
        """Shift windows should be available after team creation."""
        db, user_id = db_with_user
        result = db.create_team("ATL069", "Team", user_id)
        shifts = db.get_shift_windows_for_team(result["id"])
        assert "day" in shifts
        assert "night" in shifts

    def test_lazy_retry_creates_defaults_when_missing(self, db_with_user):
        """If shift windows are missing, lazy retry should create defaults."""
        db, user_id = db_with_user
        result = db.create_team("ATL069", "Team", user_id)
        team_id = result["id"]

        # Manually delete shift windows to simulate failed initialization
        cursor = db.conn.cursor()
        cursor.execute("DELETE FROM shift_windows WHERE team_id = ?", (team_id,))
        db.conn.commit()

        # get_shift_windows_for_team should lazy-create them
        shifts = db.get_shift_windows_for_team(team_id)
        assert "day" in shifts
        assert "night" in shifts
        assert shifts["day"].start_time == "06:00"
        assert shifts["day"].end_time == "18:30"
        assert shifts["night"].start_time == "18:00"
        assert shifts["night"].end_time == "06:30"
