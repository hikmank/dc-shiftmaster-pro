"""Unit tests for TeamPage (dc_shiftmaster_web.pages.team)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import flet as ft

from dc_shiftmaster.models import Teammate
from dc_shiftmaster_web.pages.team import TeamPage, _SHIFT_TYPES
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


def _make_page():
    """Create a mock page with shared_preferences."""
    return SimpleNamespace(shared_preferences=MockClientStorage())


@pytest.fixture
def storage():
    """Fresh StorageAdapter backed by mock storage."""
    page = _make_page()
    return StorageAdapter(page)


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #

class TestTeamPageGrouping:
    """Verify teammates are listed grouped by shift type."""

    def test_empty_list_shows_all_groups(self, storage):
        tp = TeamPage(storage=storage, page=None)
        # _list_container should have 4 sections (one per shift type)
        assert len(tp._list_container.controls) == 4

    def test_teammates_grouped_correctly(self, storage):
        storage.add_teammate("Alice", "FHD")
        storage.add_teammate("Bob", "BHN")
        storage.add_teammate("Carol", "FHD")

        tp = TeamPage(storage=storage, page=None)
        sections = tp._list_container.controls

        # FHD section (index 0) should have header + 2 members = 3 controls
        fhd_section = sections[0]
        assert fhd_section.controls[0].value == "FHD"
        # Alice and Carol
        assert len(fhd_section.controls) == 3  # header + 2 members

        # BHN section (index 3) should have header + 1 member = 2 controls
        bhn_section = sections[3]
        assert bhn_section.controls[0].value == "BHN"
        assert len(bhn_section.controls) == 2  # header + 1 member

    def test_custom_start_displayed(self, storage):
        storage.add_teammate("Dave", "FHN", "07:30")
        tp = TeamPage(storage=storage, page=None)

        # FHN is index 1
        fhn_section = tp._list_container.controls[1]
        # Member row is an ft.Row; the text label is the first control
        member_row = fhn_section.controls[1]
        member_text = member_row.controls[0].value
        assert "Dave" in member_text
        assert "07:30" in member_text

    def test_refresh_updates_list(self, storage):
        tp = TeamPage(storage=storage, page=None)
        # Initially empty
        fhd_section = tp._list_container.controls[0]
        assert len(fhd_section.controls) == 2  # header + "No teammates"

        # Add a teammate and refresh
        storage.add_teammate("Eve", "FHD")
        tp.refresh()

        fhd_section = tp._list_container.controls[0]
        assert len(fhd_section.controls) == 2  # header + 1 member
        # Member row is an ft.Row; the text label is the first control
        assert "Eve" in fhd_section.controls[1].controls[0].value

    def test_member_row_has_edit_and_delete_icons(self, storage):
        """Each teammate row should have edit (pencil) and delete (trash) icons."""
        storage.add_teammate("Zara", "FHD")
        tp = TeamPage(storage=storage, page=None)

        fhd_section = tp._list_container.controls[0]
        member_row = fhd_section.controls[1]

        # Row should have 3 controls: text, edit icon, delete icon
        assert len(member_row.controls) == 3
        assert member_row.controls[1].icon == ft.Icons.EDIT
        assert member_row.controls[2].icon == ft.Icons.DELETE


# ------------------------------------------------------------------ #
# Mock page for dialog tests
# ------------------------------------------------------------------ #

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


# ------------------------------------------------------------------ #
# Edit / Delete dialog tests
# ------------------------------------------------------------------ #

class TestTeamPageEditDelete:
    """Verify inline edit and delete dialogs."""

    def test_edit_dialog_opens_with_prepopulated_values(self, storage):
        """Edit icon should open a dialog pre-populated with current values."""
        mock_page = _make_mock_page()
        storage_with_page = StorageAdapter(mock_page)
        storage_with_page.add_teammate("Alice", "FHD", "07:00")

        tp = TeamPage(storage=storage_with_page, page=mock_page)

        # Simulate clicking the edit icon on Alice's row
        fhd_section = tp._list_container.controls[0]
        member_row = fhd_section.controls[1]
        edit_btn = member_row.controls[1]

        # Create a mock event with the control's data
        event = SimpleNamespace(control=edit_btn)
        tp._open_edit_dialog(event)

        # A dialog should have been appended to overlay
        # overlay[0] is the FilePicker, overlay[1] is the dialog
        assert len(mock_page.overlay) == 2
        dlg = mock_page.overlay[1]
        assert dlg.title.value == "Edit Teammate"

        # Content fields should be pre-populated
        fields = dlg.content.controls
        assert fields[0].value == "Alice"       # name
        assert fields[1].value == "FHD"         # shift type
        assert fields[2].value == "07:00"       # custom start

    def test_delete_dialog_shows_confirmation(self, storage):
        """Delete icon should open a confirmation dialog with teammate name."""
        mock_page = _make_mock_page()
        storage_with_page = StorageAdapter(mock_page)
        storage_with_page.add_teammate("Bob", "BHN")

        tp = TeamPage(storage=storage_with_page, page=mock_page)

        # BHN is index 3
        bhn_section = tp._list_container.controls[3]
        member_row = bhn_section.controls[1]
        delete_btn = member_row.controls[2]

        event = SimpleNamespace(control=delete_btn)
        tp._open_delete_dialog(event)

        assert len(mock_page.overlay) == 2
        dlg = mock_page.overlay[1]
        assert "Bob" in dlg.title.value

    def test_delete_confirm_removes_teammate(self, storage):
        """Confirming delete should remove the teammate from storage."""
        mock_page = _make_mock_page()
        storage_with_page = StorageAdapter(mock_page)
        storage_with_page.add_teammate("Carol", "FHN")

        tp = TeamPage(storage=storage_with_page, page=mock_page)

        # FHN is index 1
        fhn_section = tp._list_container.controls[1]
        member_row = fhn_section.controls[1]
        delete_btn = member_row.controls[2]

        event = SimpleNamespace(control=delete_btn)
        tp._open_delete_dialog(event)

        dlg = mock_page.overlay[1]  # overlay[0] is FilePicker
        # Simulate clicking the "Delete" (confirm) button
        confirm_btn = dlg.actions[1]
        confirm_btn.on_click(None)

        # Carol should be gone
        teammates = storage_with_page.get_teammates()
        assert len(teammates) == 0

    def test_edit_save_updates_teammate(self, storage):
        """Saving the edit dialog should update the teammate in storage."""
        mock_page = _make_mock_page()
        storage_with_page = StorageAdapter(mock_page)
        storage_with_page.add_teammate("Dave", "BHD", "08:00")

        tp = TeamPage(storage=storage_with_page, page=mock_page)

        # BHD is index 2
        bhd_section = tp._list_container.controls[2]
        member_row = bhd_section.controls[1]
        edit_btn = member_row.controls[1]

        event = SimpleNamespace(control=edit_btn)
        tp._open_edit_dialog(event)

        dlg = mock_page.overlay[1]  # overlay[0] is FilePicker
        fields = dlg.content.controls

        # Modify the values
        fields[0].value = "David"
        fields[1].value = "FHD"
        fields[2].value = "09:00"

        # Simulate clicking "Save"
        save_btn = dlg.actions[1]
        save_btn.on_click(None)

        # Verify the teammate was updated
        teammates = storage_with_page.get_teammates()
        assert len(teammates) == 1
        assert teammates[0].name == "David"
        assert teammates[0].shift_type == "FHD"
        assert teammates[0].custom_start == "09:00"
