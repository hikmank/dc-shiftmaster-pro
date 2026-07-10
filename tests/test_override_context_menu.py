"""Unit tests for the right-click override context menu logic in CalendarTab.

Tests the override set/remove flow through the database and scheduling
engine, verifying that overrides are stored, applied to the schedule,
and correctly removed to revert to computed assignments.
"""

from datetime import date

import pytest

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster.scheduling import SchedulingEngine


@pytest.fixture
def db(tmp_path):
    """Create a temporary DatabaseManager for testing."""
    db_path = str(tmp_path / "test.db")
    return DatabaseManager(db_path)


@pytest.fixture
def engine():
    return SchedulingEngine()


class TestOverrideSetFlow:
    """Test the set-override flow triggered by the context menu."""

    def test_set_override_stores_in_database(self, db):
        """Setting an override should persist it in the database."""
        db.set_override("2025-01-01", "day", "Override Person")
        overrides = db.get_overrides(2025)
        assert len(overrides) == 1
        assert overrides[0].date == "2025-01-01"
        assert overrides[0].shift_type == "day"
        assert overrides[0].name == "Override Person"

    def test_set_override_replaces_computed_assignment(self, db, engine):
        """An override should replace the computed teammate in the schedule."""
        db.add_teammate("Alice", "FHD")
        db.set_override("2025-01-01", "day", "Bob")

        schedule = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        jan1_day = schedule[0]
        assert jan1_day.teammates == ["Bob"]
        assert jan1_day.is_override is True

    def test_set_nobody_override(self, db, engine):
        """Setting override to 'nobody' should show nobody in the slot."""
        db.add_teammate("Alice", "FHD")
        db.set_override("2025-01-01", "day", "nobody")

        schedule = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        jan1_day = schedule[0]
        assert jan1_day.teammates == ["nobody"]
        assert jan1_day.is_override is True

    def test_set_override_on_night_slot(self, db, engine):
        """Override should work on night slots too."""
        db.add_teammate("Charlie", "FHN")
        db.set_override("2025-01-01", "night", "Diana")

        schedule = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        jan1_night = schedule[1]
        assert jan1_night.teammates == ["Diana"]
        assert jan1_night.is_override is True

    def test_set_override_updates_existing(self, db):
        """Setting an override twice for the same slot should update, not duplicate."""
        db.set_override("2025-01-01", "day", "First")
        db.set_override("2025-01-01", "day", "Second")

        overrides = db.get_overrides(2025)
        matching = [o for o in overrides if o.date == "2025-01-01" and o.shift_type == "day"]
        assert len(matching) == 1
        assert matching[0].name == "Second"


class TestOverrideRemoveFlow:
    """Test the remove-override flow triggered by the context menu."""

    def test_remove_override_reverts_to_computed(self, db, engine):
        """Removing an override should revert the slot to the computed assignment."""
        db.add_teammate("Alice", "FHD")
        db.set_override("2025-01-01", "day", "Override Person")

        # Verify override is applied
        schedule = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        assert schedule[0].teammates == ["Override Person"]

        # Remove override
        db.remove_override("2025-01-01", "day")

        # Verify reverted to computed
        schedule = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        assert schedule[0].teammates == ["Alice"]
        assert schedule[0].is_override is False

    def test_remove_override_deletes_from_database(self, db):
        """Removing an override should delete it from the database."""
        db.set_override("2025-01-01", "day", "Override Person")
        assert len(db.get_overrides(2025)) == 1

        db.remove_override("2025-01-01", "day")
        assert len(db.get_overrides(2025)) == 0

    def test_remove_nonexistent_override_is_safe(self, db):
        """Removing an override that doesn't exist should not raise."""
        db.remove_override("2025-01-01", "day")  # no-op, should not raise

    def test_override_persists_across_recomputation(self, db, engine):
        """Overrides should survive schedule recomputation (same year)."""
        db.add_teammate("Alice", "FHD")
        db.set_override("2025-06-15", "day", "Override Person")

        # First computation
        schedule1 = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        lookup1 = {(s.date.isoformat(), s.shift_type): s for s in schedule1}
        assert lookup1[("2025-06-15", "day")].teammates == ["Override Person"]

        # Second computation (simulating refresh)
        schedule2 = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        lookup2 = {(s.date.isoformat(), s.shift_type): s for s in schedule2}
        assert lookup2[("2025-06-15", "day")].teammates == ["Override Person"]
