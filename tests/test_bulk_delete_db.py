"""Unit tests for bulk-delete DatabaseManager methods.

Verifies count_overrides_in_range, bulk_delete_overrides_by_range,
bulk_delete_overrides_by_keys, and bulk_delete_overrides_by_year.
"""

import pytest

from dc_shiftmaster.database import DatabaseManager


@pytest.fixture
def db_with_team(tmp_path):
    """Provide a fresh DatabaseManager with a team created."""
    db_path = str(tmp_path / "test_bulk.db")
    manager = DatabaseManager(db_path)
    # Create a user and team
    user_id = manager.create_user("testuser", "hash", "Test User")
    team = manager.create_team("TST001", "Test Team", user_id)
    yield manager, team["id"]
    manager.conn.close()


def _seed_overrides(db, team_id, overrides):
    """Helper to insert overrides for a team."""
    for date, shift_type, name in overrides:
        db.set_override(date, shift_type, name, team_id=team_id)


class TestCountOverridesInRange:
    def test_counts_overrides_within_range(self, db_with_team):
        db, team_id = db_with_team
        _seed_overrides(db, team_id, [
            ("2025-01-15", "day", "Alice"),
            ("2025-01-20", "night", "Bob"),
            ("2025-02-01", "day", "Charlie"),
        ])
        count = db.count_overrides_in_range("2025-01-01", "2025-01-31", team_id=team_id)
        assert count == 2

    def test_count_zero_when_no_match(self, db_with_team):
        db, team_id = db_with_team
        _seed_overrides(db, team_id, [
            ("2025-03-01", "day", "Alice"),
        ])
        count = db.count_overrides_in_range("2025-01-01", "2025-01-31", team_id=team_id)
        assert count == 0

    def test_inclusive_boundaries(self, db_with_team):
        db, team_id = db_with_team
        _seed_overrides(db, team_id, [
            ("2025-01-01", "day", "Alice"),
            ("2025-01-31", "night", "Bob"),
        ])
        count = db.count_overrides_in_range("2025-01-01", "2025-01-31", team_id=team_id)
        assert count == 2


class TestBulkDeleteByRange:
    def test_deletes_overrides_in_range(self, db_with_team):
        db, team_id = db_with_team
        _seed_overrides(db, team_id, [
            ("2025-01-15", "day", "Alice"),
            ("2025-01-20", "night", "Bob"),
            ("2025-02-01", "day", "Charlie"),
        ])
        deleted = db.bulk_delete_overrides_by_range("2025-01-01", "2025-01-31", team_id=team_id)
        assert deleted == 2
        # Verify remaining
        remaining = db.get_overrides(2025, team_id=team_id)
        assert len(remaining) == 1
        assert remaining[0].name == "Charlie"

    def test_returns_zero_for_empty_range(self, db_with_team):
        db, team_id = db_with_team
        deleted = db.bulk_delete_overrides_by_range("2025-01-01", "2025-01-31", team_id=team_id)
        assert deleted == 0

    def test_preserves_overrides_outside_range(self, db_with_team):
        db, team_id = db_with_team
        _seed_overrides(db, team_id, [
            ("2025-01-15", "day", "Alice"),
            ("2025-03-01", "day", "Bob"),
            ("2025-06-15", "night", "Charlie"),
        ])
        db.bulk_delete_overrides_by_range("2025-01-01", "2025-01-31", team_id=team_id)
        remaining = db.get_overrides(2025, team_id=team_id)
        assert len(remaining) == 2


class TestBulkDeleteByKeys:
    def test_deletes_specific_keys(self, db_with_team):
        db, team_id = db_with_team
        _seed_overrides(db, team_id, [
            ("2025-01-15", "day", "Alice"),
            ("2025-01-15", "night", "Bob"),
            ("2025-01-20", "day", "Charlie"),
        ])
        deleted = db.bulk_delete_overrides_by_keys(
            [("2025-01-15", "day"), ("2025-01-20", "day")],
            team_id=team_id,
        )
        assert deleted == 2
        remaining = db.get_overrides(2025, team_id=team_id)
        assert len(remaining) == 1
        assert remaining[0].shift_type == "night"

    def test_returns_zero_for_nonexistent_keys(self, db_with_team):
        db, team_id = db_with_team
        deleted = db.bulk_delete_overrides_by_keys(
            [("2025-01-15", "day")],
            team_id=team_id,
        )
        assert deleted == 0

    def test_empty_keys_list(self, db_with_team):
        db, team_id = db_with_team
        _seed_overrides(db, team_id, [
            ("2025-01-15", "day", "Alice"),
        ])
        deleted = db.bulk_delete_overrides_by_keys([], team_id=team_id)
        assert deleted == 0
        remaining = db.get_overrides(2025, team_id=team_id)
        assert len(remaining) == 1


class TestBulkDeleteByYear:
    def test_deletes_all_overrides_for_year(self, db_with_team):
        db, team_id = db_with_team
        _seed_overrides(db, team_id, [
            ("2025-01-15", "day", "Alice"),
            ("2025-06-20", "night", "Bob"),
            ("2026-01-01", "day", "Charlie"),
        ])
        deleted = db.bulk_delete_overrides_by_year(2025, team_id=team_id)
        assert deleted == 2
        # 2026 should still be there
        remaining_2026 = db.get_overrides(2026, team_id=team_id)
        assert len(remaining_2026) == 1
        assert remaining_2026[0].name == "Charlie"

    def test_returns_zero_for_empty_year(self, db_with_team):
        db, team_id = db_with_team
        deleted = db.bulk_delete_overrides_by_year(2025, team_id=team_id)
        assert deleted == 0


class TestTeamIsolation:
    def test_bulk_delete_does_not_affect_other_teams(self, tmp_path):
        db_path = str(tmp_path / "test_isolation.db")
        db = DatabaseManager(db_path)
        # Create two teams
        user_id = db.create_user("testuser", "hash", "Test User")
        team_a = db.create_team("TMA001", "Team A", user_id)
        team_b = db.create_team("TMB001", "Team B", user_id)
        team_a_id = team_a["id"]
        team_b_id = team_b["id"]

        # Use non-overlapping dates to avoid PK conflicts (PK is date+shift_type)
        _seed_overrides(db, team_a_id, [
            ("2025-01-15", "day", "Alice"),
            ("2025-01-20", "night", "Bob"),
        ])
        _seed_overrides(db, team_b_id, [
            ("2025-02-15", "day", "Charlie"),
            ("2025-02-20", "night", "Dave"),
        ])

        # Delete from team A (range covers only team A's dates)
        deleted = db.bulk_delete_overrides_by_range("2025-01-01", "2025-01-31", team_id=team_a_id)
        assert deleted == 2

        # Team B is untouched
        team_b_overrides = db.get_overrides(2025, team_id=team_b_id)
        assert len(team_b_overrides) == 2
        db.conn.close()
