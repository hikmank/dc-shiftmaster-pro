"""Unit tests for SettingsPage (dc_shiftmaster_web.pages.settings)."""

from types import SimpleNamespace

import pytest

from dc_shiftmaster_web.pages.settings import SettingsPage, _DC_SITE_CODES
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


class MockPage:
    """Minimal mock of ft.Page supporting overlay and update."""

    def __init__(self, client_storage):
        self.shared_preferences = client_storage
        self.overlay = []

    def update(self):
        pass


def _make_mock_page():
    cs = MockClientStorage()
    return MockPage(cs)


@pytest.fixture
def storage():
    """Fresh StorageAdapter backed by mock storage."""
    page = SimpleNamespace(shared_preferences=MockClientStorage())
    return StorageAdapter(page)


# ------------------------------------------------------------------ #
# Shift Windows section tests
# ------------------------------------------------------------------ #

class TestSettingsShiftWindows:
    """Verify shift window fields are pre-populated and save correctly."""

    def test_fields_prepopulated_from_defaults(self, storage):
        sp = SettingsPage(storage=storage, page=None)
        assert sp._day_start.value == "06:00"
        assert sp._day_end.value == "18:30"
        assert sp._night_start.value == "18:00"
        assert sp._night_end.value == "06:30"

    def test_save_valid_shift_windows(self, storage):
        mock_page = _make_mock_page()
        sa = StorageAdapter(mock_page)
        sp = SettingsPage(storage=sa, page=mock_page)

        sp._day_start.value = "07:00"
        sp._day_end.value = "19:00"
        sp._night_start.value = "19:00"
        sp._night_end.value = "07:00"

        sp._save_shift_windows()

        windows = sa.get_shift_windows()
        assert windows["day"].start_time == "07:00"
        assert windows["day"].end_time == "19:00"
        assert windows["night"].start_time == "19:00"
        assert windows["night"].end_time == "07:00"

    def test_save_shows_toast(self, storage):
        mock_page = _make_mock_page()
        sa = StorageAdapter(mock_page)
        sp = SettingsPage(storage=sa, page=mock_page)

        sp._save_shift_windows()

        # A SnackBar should have been appended to overlay
        snacks = [c for c in mock_page.overlay if hasattr(c, "open")]
        assert len(snacks) == 1
        assert snacks[0].content.value == "Shift windows saved."

    def test_save_invalid_time_shows_error(self, storage):
        mock_page = _make_mock_page()
        sa = StorageAdapter(mock_page)
        sp = SettingsPage(storage=sa, page=mock_page)

        sp._day_start.value = "25:00"  # invalid hour
        sp._save_shift_windows()

        # error_text should be set on the invalid field
        assert sp._day_start.error_text is not None
        assert "25" in sp._day_start.error_text

        # No toast should be shown (save was blocked)
        snacks = [c for c in mock_page.overlay if hasattr(c, "open")]
        assert len(snacks) == 0

    def test_save_clears_error_on_valid_input(self, storage):
        mock_page = _make_mock_page()
        sa = StorageAdapter(mock_page)
        sp = SettingsPage(storage=sa, page=mock_page)

        # First save with invalid input
        sp._day_start.value = "bad"
        sp._save_shift_windows()
        assert sp._day_start.error_text is not None

        # Fix and save again
        sp._day_start.value = "06:00"
        sp._save_shift_windows()
        assert sp._day_start.error_text is None


# ------------------------------------------------------------------ #
# Region section tests
# ------------------------------------------------------------------ #

class TestSettingsRegion:
    """Verify region dropdown behavior."""

    def test_region_dropdown_has_all_site_codes(self, storage):
        sp = SettingsPage(storage=storage, page=None)
        option_values = [o.key for o in sp._region_dropdown.options]
        assert option_values == _DC_SITE_CODES

    def test_region_prepopulated_from_storage(self):
        mock_page = _make_mock_page()
        sa = StorageAdapter(mock_page)
        sa.set_region("CMH68")
        sp = SettingsPage(storage=sa, page=None)
        assert sp._region_dropdown.value == "CMH68"

    def test_region_change_persists(self):
        mock_page = _make_mock_page()
        sa = StorageAdapter(mock_page)
        sp = SettingsPage(storage=sa, page=mock_page)

        # Simulate dropdown change event
        event = SimpleNamespace(control=SimpleNamespace(value="IAD77"))
        sp._on_region_change(event)

        assert sa.get_region() == "IAD77"

    def test_region_change_shows_toast(self):
        mock_page = _make_mock_page()
        sa = StorageAdapter(mock_page)
        sp = SettingsPage(storage=sa, page=mock_page)

        event = SimpleNamespace(control=SimpleNamespace(value="ATL68"))
        sp._on_region_change(event)

        snacks = [c for c in mock_page.overlay if hasattr(c, "open")]
        assert len(snacks) == 1
        assert snacks[0].content.value == "Region saved."


# ------------------------------------------------------------------ #
# Year section tests
# ------------------------------------------------------------------ #

class TestSettingsYear:
    """Verify year dropdown behavior."""

    def test_year_dropdown_range(self, storage):
        sp = SettingsPage(storage=storage, page=None)
        option_values = [o.key for o in sp._year_dropdown.options]
        assert option_values[0] == "2000"
        assert option_values[-1] == "2100"
        assert len(option_values) == 101

    def test_year_prepopulated_from_storage(self):
        mock_page = _make_mock_page()
        sa = StorageAdapter(mock_page)
        sa.set_year(2030)
        sp = SettingsPage(storage=sa, page=None)
        assert sp._year_dropdown.value == "2030"

    def test_year_change_persists(self):
        mock_page = _make_mock_page()
        sa = StorageAdapter(mock_page)
        sp = SettingsPage(storage=sa, page=mock_page)

        event = SimpleNamespace(control=SimpleNamespace(value="2050"))
        sp._on_year_change(event)

        assert sa.get_year() == 2050

    def test_year_change_shows_toast(self):
        mock_page = _make_mock_page()
        sa = StorageAdapter(mock_page)
        sp = SettingsPage(storage=sa, page=mock_page)

        event = SimpleNamespace(control=SimpleNamespace(value="2025"))
        sp._on_year_change(event)

        snacks = [c for c in mock_page.overlay if hasattr(c, "open")]
        assert len(snacks) == 1
        assert snacks[0].content.value == "Year saved."


# ------------------------------------------------------------------ #
# Refresh tests
# ------------------------------------------------------------------ #

class TestSettingsRefresh:
    """Verify refresh re-reads from storage."""

    def test_refresh_updates_shift_windows(self):
        mock_page = _make_mock_page()
        sa = StorageAdapter(mock_page)
        sp = SettingsPage(storage=sa, page=None)

        # Externally update storage
        sa.update_shift_window("day", "08:00", "20:00")
        sp.refresh()

        assert sp._day_start.value == "08:00"
        assert sp._day_end.value == "20:00"

    def test_refresh_updates_region(self):
        mock_page = _make_mock_page()
        sa = StorageAdapter(mock_page)
        sp = SettingsPage(storage=sa, page=None)

        sa.set_region("SFO5")
        sp.refresh()

        assert sp._region_dropdown.value == "SFO5"

    def test_refresh_updates_year(self):
        mock_page = _make_mock_page()
        sa = StorageAdapter(mock_page)
        sp = SettingsPage(storage=sa, page=None)

        sa.set_year(2099)
        sp.refresh()

        assert sp._year_dropdown.value == "2099"
