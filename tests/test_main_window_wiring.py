"""Unit tests for MainWindow tab wiring and cross-tab refresh logic.

Verifies that:
- Settings tab changes trigger CalendarTab.refresh (task 13.1)
- Teammates tab changes trigger CalendarTab.refresh (task 13.2)
- Deleted teammates show as 'nobody' in affected slots (task 13.2)
- Overrides persist across year changes and recomputation (task 13.3)
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster.scheduling import SchedulingEngine


@pytest.fixture
def db(tmp_path):
    """Provide a fresh DatabaseManager backed by a temp-file database."""
    db_path = str(tmp_path / "test_wiring.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.conn.close()


@pytest.fixture
def engine():
    return SchedulingEngine()


# ---- Task 13.1: Settings → Calendar refresh ----

class TestSettingsToCalendarRefresh:
    """Settings tab on_change callback should trigger calendar refresh."""

    def test_settings_on_change_callback_is_callable(self, db):
        """SettingsTab accepts an on_change callback and invokes it on save."""
        callback = MagicMock()

        # Build a SettingsTab with mocked widgets (no display needed)
        with patch("dc_shiftmaster.ui.settings_tab.ctk") as mock_ctk:
            mock_ctk.CTkFrame = MagicMock
            mock_ctk.CTkLabel = lambda master=None, **kw: _FakeLabel(**kw)
            mock_ctk.CTkEntry = lambda master=None, **kw: _FakeEntry()
            mock_ctk.CTkButton = MagicMock

            from dc_shiftmaster.ui.settings_tab import SettingsTab

            tab = object.__new__(SettingsTab)
            tab.db = db
            tab.on_change = callback
            tab._entries = {}
            tab._error_labels = {}
            for key in ("day_start", "day_end", "night_start", "night_end"):
                tab._entries[key] = _FakeEntry()
                tab._error_labels[key] = _FakeLabel()
            tab._load_values()

            # Save with valid defaults → should invoke callback
            tab._on_save()
            callback.assert_called_once()

    def test_settings_change_updates_schedule_times(self, db, engine):
        """After updating shift windows, recomputed schedule uses new times."""
        db.add_teammate("Alice", "FHD")

        # Original schedule uses default day start 06:00
        schedule_before = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        jan1_day = schedule_before[0]
        assert jan1_day.start_time == "06:00"

        # Update day shift window
        db.update_shift_window("day", "07:00", "19:00")

        # Recompute (simulates what CalendarTab.refresh does)
        schedule_after = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        jan1_day_after = schedule_after[0]
        assert jan1_day_after.start_time == "07:00"


# ---- Task 13.2: Teammates → Calendar refresh ----

class TestTeammatesToCalendarRefresh:
    """Teammates tab changes should trigger calendar refresh."""

    def test_teammates_on_change_callback_is_callable(self, db):
        """TeammatesTab accepts an on_change callback and invokes it on add."""
        callback = MagicMock()

        from dc_shiftmaster.ui.teammates_tab import TeammatesTab

        tab = object.__new__(TeammatesTab)
        tab.db = db
        tab.on_change = callback
        tab._edit_state = None
        tab._row_widgets = []
        tab.name_entry = _FakeEntry()
        tab.name_entry._value = "Alice"
        tab.shift_menu = _FakeOptionMenu()
        tab.error_label = _FakeLabel()
        tab.table_frame = MagicMock()
        # Mock _refresh_table to avoid building real CTk widgets
        tab._refresh_table = MagicMock()

        tab._on_add()
        callback.assert_called_once()

    def test_add_teammate_updates_schedule(self, db, engine):
        """Adding a teammate and recomputing should populate their slots."""
        # No teammates → all nobody
        schedule = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        assert schedule[0].teammates == ["nobody"]

        # Add FHD teammate
        db.add_teammate("Alice", "FHD")
        schedule = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        # Jan 1 = cycle day 0 = front half → day slot = FHD = Alice
        assert schedule[0].teammates == ["Alice"]

    def test_edit_teammate_updates_schedule(self, db, engine):
        """Editing a teammate name and recomputing should show the new name."""
        tid = db.add_teammate("Alice", "FHD")
        schedule = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        assert schedule[0].teammates == ["Alice"]

        db.update_teammate(tid, "Alicia", "FHD")
        schedule = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        assert schedule[0].teammates == ["Alicia"]

    def test_delete_teammate_shows_nobody(self, db, engine):
        """Deleting a teammate and recomputing should show 'nobody' in their slots."""
        tid = db.add_teammate("Alice", "FHD")
        schedule = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        assert schedule[0].teammates == ["Alice"]

        db.delete_teammate(tid)
        schedule = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        # With no FHD teammate, front half day slots should be "nobody"
        assert schedule[0].teammates == ["nobody"]


# ---- Task 13.3: Overrides persist across year changes ----

class TestOverridesPersistAcrossYearChanges:
    """Overrides stored in DB should survive year navigation and recomputation."""

    def test_overrides_persist_after_year_change_and_back(self, db, engine):
        """Navigating away from a year and back should preserve its overrides."""
        db.add_teammate("Alice", "FHD")
        db.set_override("2025-01-01", "day", "Override Person")

        # Compute 2025 → override applied
        schedule_2025 = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        assert schedule_2025[0].teammates == ["Override Person"]
        assert schedule_2025[0].is_override is True

        # Navigate to 2026
        schedule_2026 = engine.compute_annual_schedule(
            2026, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2026)
        )
        # 2026 should NOT have the 2025 override
        assert schedule_2026[0].teammates == ["Alice"]
        assert schedule_2026[0].is_override is False

        # Navigate back to 2025 → override still there
        schedule_2025_again = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        assert schedule_2025_again[0].teammates == ["Override Person"]
        assert schedule_2025_again[0].is_override is True

    def test_overrides_survive_recomputation_after_teammate_change(self, db, engine):
        """Overrides should persist even when teammates change and schedule is recomputed."""
        db.add_teammate("Alice", "FHD")
        db.set_override("2025-06-15", "day", "Override Person")

        # Recompute after adding another teammate
        db.add_teammate("Bob", "FHN")
        schedule = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )

        # Find the June 15 day slot
        lookup = {(s.date.isoformat(), s.shift_type): s for s in schedule}
        slot = lookup[("2025-06-15", "day")]
        assert slot.teammates == ["Override Person"]
        assert slot.is_override is True

    def test_overrides_survive_recomputation_after_shift_window_change(self, db, engine):
        """Overrides should persist even when shift windows change."""
        db.add_teammate("Alice", "FHD")
        db.set_override("2025-03-01", "day", "Override Person")

        # Change shift windows
        db.update_shift_window("day", "07:00", "19:00")

        schedule = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )

        lookup = {(s.date.isoformat(), s.shift_type): s for s in schedule}
        slot = lookup[("2025-03-01", "day")]
        assert slot.teammates == ["Override Person"]
        assert slot.is_override is True
        # But the start time should reflect the new shift window
        assert slot.start_time == "07:00"

    def test_multiple_overrides_for_same_year(self, db, engine):
        """Multiple overrides for the same year should all persist."""
        db.add_teammate("Alice", "FHD")
        db.set_override("2025-01-01", "day", "Person A")
        db.set_override("2025-06-15", "day", "Person B")
        db.set_override("2025-12-31", "day", "Person C")

        schedule = engine.compute_annual_schedule(
            2025, db.get_teammates(), db.get_shift_windows(), db.get_overrides(2025)
        )
        lookup = {(s.date.isoformat(), s.shift_type): s for s in schedule}

        assert lookup[("2025-01-01", "day")].teammates == ["Person A"]
        assert lookup[("2025-06-15", "day")].teammates == ["Person B"]
        assert lookup[("2025-12-31", "day")].teammates == ["Person C"]


# ---- Helpers ----

class _FakeEntry:
    """Minimal stand-in for CTkEntry."""

    def __init__(self):
        self._value = ""

    def insert(self, index, value):
        self._value = value

    def get(self):
        return self._value

    def delete(self, start, end):
        self._value = ""

    def grid(self, **kwargs):
        pass

    def pack(self, **kwargs):
        pass


class _FakeLabel:
    """Minimal stand-in for CTkLabel."""

    def __init__(self, **kwargs):
        self._text = kwargs.get("text", "")

    def configure(self, **kwargs):
        if "text" in kwargs:
            self._text = kwargs["text"]

    def grid(self, **kwargs):
        pass

    def pack(self, **kwargs):
        pass


class _FakeOptionMenu:
    """Minimal stand-in for CTkOptionMenu."""

    def __init__(self):
        self._value = "FHD"

    def get(self):
        return self._value

    def set(self, value):
        self._value = value

    def grid(self, **kwargs):
        pass

    def pack(self, **kwargs):
        pass
