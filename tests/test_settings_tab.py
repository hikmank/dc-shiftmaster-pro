"""Unit tests for the SettingsTab UI component.

Tests the core logic: loading values from DB, validation on save,
persisting valid changes, and invoking the on_change callback.
These tests use a real DatabaseManager with a temp DB but mock
the CustomTkinter widgets since no display is available in CI.
"""

import unittest
from unittest.mock import MagicMock, patch

import pytest

from dc_shiftmaster.database import DatabaseManager


class FakeEntry:
    """Minimal stand-in for CTkEntry to test SettingsTab logic."""

    def __init__(self):
        self._value = ""

    def insert(self, index, value):
        self._value = value

    def get(self):
        return self._value

    def grid(self, **kwargs):
        pass


class FakeLabel:
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


class TestSettingsTabLogic:
    """Test the SettingsTab's data flow without a real GUI."""

    def _make_tab(self, db, on_change=None):
        """Create a SettingsTab with mocked CTk widgets."""
        # We patch CTk widgets so no display is needed
        with patch("dc_shiftmaster.ui.settings_tab.ctk") as mock_ctk:
            mock_ctk.CTkFrame = MagicMock
            mock_ctk.CTkLabel = lambda master=None, **kw: FakeLabel(**kw)
            mock_ctk.CTkEntry = lambda master=None, **kw: FakeEntry()
            mock_ctk.CTkButton = MagicMock

            # Import here so the patch applies
            from dc_shiftmaster.ui.settings_tab import SettingsTab

            # Bypass CTkFrame.__init__ by calling object.__init__
            tab = object.__new__(SettingsTab)
            tab.db = db
            tab.on_change = on_change
            tab._entries = {}
            tab._error_labels = {}

            # Build UI using our fakes
            tab._build_ui = lambda: None  # skip grid layout
            # Manually create the entry/error pairs
            for key in ("day_start", "day_end", "night_start", "night_end"):
                tab._entries[key] = FakeEntry()
                tab._error_labels[key] = FakeLabel()

            tab._load_values()
            return tab

    def test_loads_default_values(self, db):
        """Entries should be pre-populated with DB defaults."""
        tab = self._make_tab(db)
        assert tab._entries["day_start"].get() == "06:00"
        assert tab._entries["day_end"].get() == "18:30"
        assert tab._entries["night_start"].get() == "18:00"
        assert tab._entries["night_end"].get() == "06:30"

    def test_save_valid_values(self, db):
        """Valid times should be persisted to the database."""
        tab = self._make_tab(db)

        # Change values
        tab._entries["day_start"]._value = "07:00"
        tab._entries["day_end"]._value = "19:00"
        tab._entries["night_start"]._value = "19:00"
        tab._entries["night_end"]._value = "07:00"

        tab._on_save()

        windows = db.get_shift_windows()
        assert windows["day"].start_time == "07:00"
        assert windows["day"].end_time == "19:00"
        assert windows["night"].start_time == "19:00"
        assert windows["night"].end_time == "07:00"

    def test_save_invalid_shows_errors(self, db):
        """Invalid times should produce error text and not persist."""
        tab = self._make_tab(db)

        tab._entries["day_start"]._value = "25:00"
        tab._entries["day_end"]._value = "18:30"
        tab._entries["night_start"]._value = "bad"
        tab._entries["night_end"]._value = "06:30"

        tab._on_save()

        # Errors should be set on invalid fields
        assert tab._error_labels["day_start"]._text != ""
        assert tab._error_labels["night_start"]._text != ""
        # Valid fields should have no error
        assert tab._error_labels["day_end"]._text == ""
        assert tab._error_labels["night_end"]._text == ""

        # DB should still have original defaults
        windows = db.get_shift_windows()
        assert windows["day"].start_time == "06:00"

    def test_save_calls_on_change(self, db):
        """Successful save should invoke the on_change callback."""
        callback = MagicMock()
        tab = self._make_tab(db, on_change=callback)

        tab._on_save()

        callback.assert_called_once()

    def test_save_no_callback_on_error(self, db):
        """on_change should NOT be called when validation fails."""
        callback = MagicMock()
        tab = self._make_tab(db, on_change=callback)

        tab._entries["day_start"]._value = "invalid"

        tab._on_save()

        callback.assert_not_called()

    def test_errors_cleared_on_retry(self, db):
        """Previous error messages should be cleared on each save attempt."""
        tab = self._make_tab(db)

        # First save with invalid value
        tab._entries["day_start"]._value = "99:99"
        tab._on_save()
        assert tab._error_labels["day_start"]._text != ""

        # Fix the value and save again
        tab._entries["day_start"]._value = "06:00"
        tab._on_save()
        assert tab._error_labels["day_start"]._text == ""
