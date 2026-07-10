"""Unit tests for CSVExporter, JSONExporter, and validate_schedule."""

import json
import os
import tempfile
from datetime import date

import pytest

from dc_shiftmaster.csv_export import CSVExporter, JSONExporter, validate_schedule
from dc_shiftmaster.models import ScheduleSlot


class TestFormatDatetime:
    """Tests for CSVExporter.format_datetime — YYYY/MM/DD HH:MM with leading zeros."""

    def setup_method(self):
        self.exporter = CSVExporter()

    def test_leading_zeros_month_day(self):
        # June 5 at 06:00 → "2018/06/05 06:00"
        result = self.exporter.format_datetime(date(2018, 6, 5), "06:00")
        assert result == "2018/06/05 06:00"

    def test_double_digit_month_day_hour(self):
        # December 25 at 18:00 → "2018/12/25 18:00"
        result = self.exporter.format_datetime(date(2018, 12, 25), "18:00")
        assert result == "2018/12/25 18:00"

    def test_single_digit_month_and_day(self):
        # January 1 at 06:00 → "2025/01/01 06:00"
        result = self.exporter.format_datetime(date(2025, 1, 1), "06:00")
        assert result == "2025/01/01 06:00"

    def test_midnight_hour(self):
        # Midnight → "2025/03/15 00:30"
        result = self.exporter.format_datetime(date(2025, 3, 15), "00:30")
        assert result == "2025/03/15 00:30"

    def test_afternoon_time(self):
        result = self.exporter.format_datetime(date(2025, 11, 9), "14:00")
        assert result == "2025/11/09 14:00"

    def test_leap_year_feb29(self):
        result = self.exporter.format_datetime(date(2024, 2, 29), "18:00")
        assert result == "2024/02/29 18:00"


class TestExport:
    """Tests for CSVExporter.export — CSV file output."""

    def setup_method(self):
        self.exporter = CSVExporter()

    def _make_slots(self, d, day_name="Alice", night_name="Bob"):
        return [
            ScheduleSlot(date=d, shift_type="day", start_time="06:00",
                         teammates=[day_name], is_override=False),
            ScheduleSlot(date=d, shift_type="night", start_time="18:00",
                         teammates=[night_name], is_override=False),
        ]

    def test_basic_export_two_rows_per_day(self):
        slots = self._make_slots(date(2025, 1, 1))
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            path = f.name
        try:
            self.exporter.export(slots, path)
            with open(path) as f:
                lines = f.read().strip().split("\n")
            assert len(lines) == 2
            assert lines[0] == "2025/01/01 06:00,Alice"
            assert lines[1] == "2025/01/01 18:00,Bob"
        finally:
            os.unlink(path)

    def test_no_header_row(self):
        slots = self._make_slots(date(2025, 6, 15))
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            path = f.name
        try:
            self.exporter.export(slots, path)
            with open(path) as f:
                first_line = f.readline().strip()
            # First line should be data, not a header
            assert "date" not in first_line.lower()
            assert "time" not in first_line.lower()
            assert first_line == "2025/06/15 06:00,Alice"
        finally:
            os.unlink(path)

    def test_nobody_for_unassigned(self):
        slots = self._make_slots(date(2025, 1, 1), day_name="nobody", night_name="nobody")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            path = f.name
        try:
            self.exporter.export(slots, path)
            with open(path) as f:
                lines = f.read().strip().split("\n")
            assert lines[0] == "2025/01/01 06:00,nobody"
            assert lines[1] == "2025/01/01 18:00,nobody"
        finally:
            os.unlink(path)

    def test_chronological_order_day_before_night(self):
        slots = (
            self._make_slots(date(2025, 1, 1))
            + self._make_slots(date(2025, 1, 2), "Carol", "Dave")
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            path = f.name
        try:
            self.exporter.export(slots, path)
            with open(path) as f:
                lines = f.read().strip().split("\n")
            assert len(lines) == 4
            assert lines[0].startswith("2025/01/01 06:00")
            assert lines[1].startswith("2025/01/01 18:00")
            assert lines[2].startswith("2025/01/02 06:00")
            assert lines[3].startswith("2025/01/02 18:00")
        finally:
            os.unlink(path)

    def test_non_writable_path_raises_oserror(self):
        slots = self._make_slots(date(2025, 1, 1))
        bad_path = "/nonexistent_dir_xyz/schedule.csv"
        with pytest.raises(OSError, match="Cannot save CSV"):
            self.exporter.export(slots, bad_path)

    def test_overrides_appear_in_export(self):
        slots = [
            ScheduleSlot(date=date(2025, 3, 10), shift_type="day",
                         start_time="06:00", teammates=["Override_Person"],
                         is_override=True),
            ScheduleSlot(date=date(2025, 3, 10), shift_type="night",
                         start_time="18:00", teammates=["Bob"], is_override=False),
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            path = f.name
        try:
            self.exporter.export(slots, path)
            with open(path) as f:
                lines = f.read().strip().split("\n")
            assert lines[0] == "2025/03/10 06:00,Override_Person"
        finally:
            os.unlink(path)


class TestParseCsvRow:
    """Tests for CSVExporter.parse_csv_row — round-trip parsing."""

    def setup_method(self):
        self.exporter = CSVExporter()

    def test_basic_parse(self):
        d, time_str, name = self.exporter.parse_csv_row("6/5/2018 14:00,Alice")
        assert d == date(2018, 6, 5)
        assert time_str == "14:00"
        assert name == "Alice"

    def test_single_digit_month_day_hour(self):
        d, time_str, name = self.exporter.parse_csv_row("1/1/2025 6:00,Bob")
        assert d == date(2025, 1, 1)
        assert time_str == "6:00"
        assert name == "Bob"

    def test_nobody_value(self):
        d, time_str, name = self.exporter.parse_csv_row("3/15/2025 18:00,nobody")
        assert d == date(2025, 3, 15)
        assert time_str == "18:00"
        assert name == "nobody"

    def test_midnight_hour(self):
        d, time_str, name = self.exporter.parse_csv_row("3/15/2025 0:30,Carol")
        assert d == date(2025, 3, 15)
        assert time_str == "0:30"
        assert name == "Carol"

    def test_leap_year_feb29(self):
        d, time_str, name = self.exporter.parse_csv_row("2/29/2024 18:00,Dave")
        assert d == date(2024, 2, 29)
        assert time_str == "18:00"
        assert name == "Dave"

    def test_round_trip_with_format_datetime(self):
        """Export a datetime then parse it back — values should match."""
        original_date = date(2025, 7, 4)
        original_time = "06:00"
        original_name = "TestUser"

        formatted = self.exporter.format_datetime(original_date, original_time)
        row = f"{formatted},{original_name}"
        parsed_date, parsed_time, parsed_name = self.exporter.parse_csv_row(row)

        assert parsed_date == original_date
        assert parsed_name == original_name
        # format_datetime now preserves HH:MM with leading zeros
        assert parsed_time == "06:00"

    def test_name_with_comma_not_split(self):
        """Name containing a comma should be kept intact after the first comma split."""
        d, time_str, name = self.exporter.parse_csv_row("2025/01/01 06:00,Last, First")
        assert d == date(2025, 1, 1)
        assert time_str == "06:00"
        assert name == "Last, First"

    def test_invalid_row_no_comma(self):
        with pytest.raises(ValueError, match="Expected exactly one comma"):
            self.exporter.parse_csv_row("no comma here")

    def test_invalid_row_bad_date(self):
        with pytest.raises(ValueError):
            self.exporter.parse_csv_row("not-a-date 6:00,Alice")

    def test_parse_new_format(self):
        """parse_csv_row handles the new YYYY/MM/DD HH:MM format."""
        d, time_str, name = self.exporter.parse_csv_row("2025/01/01 06:00,Alice")
        assert d == date(2025, 1, 1)
        assert time_str == "06:00"
        assert name == "Alice"

    def test_parse_old_format_still_works(self):
        """parse_csv_row auto-detects the old M/D/YYYY H:MM format."""
        d, time_str, name = self.exporter.parse_csv_row("6/5/2018 14:00,Alice")
        assert d == date(2018, 6, 5)
        assert time_str == "14:00"
        assert name == "Alice"


class TestValidateSchedule:
    """Tests for validate_schedule — schedule validation before export."""

    def test_valid_schedule_returns_no_errors(self):
        slots = [
            ScheduleSlot(date=date(2025, 1, 1), shift_type="day",
                         start_time="06:00", teammates=["Alice"], is_override=False),
            ScheduleSlot(date=date(2025, 1, 1), shift_type="night",
                         start_time="18:00", teammates=["Bob"], is_override=False),
        ]
        errors = validate_schedule(slots)
        assert errors == []

    def test_out_of_order_dates_detected(self):
        slots = [
            ScheduleSlot(date=date(2025, 1, 2), shift_type="day",
                         start_time="06:00", teammates=["Alice"], is_override=False),
            ScheduleSlot(date=date(2025, 1, 1), shift_type="day",
                         start_time="06:00", teammates=["Bob"], is_override=False),
        ]
        errors = validate_schedule(slots)
        assert len(errors) >= 1
        assert "Out of order" in errors[0]

    def test_night_before_day_same_date_detected(self):
        slots = [
            ScheduleSlot(date=date(2025, 1, 1), shift_type="night",
                         start_time="18:00", teammates=["Alice"], is_override=False),
            ScheduleSlot(date=date(2025, 1, 1), shift_type="day",
                         start_time="06:00", teammates=["Bob"], is_override=False),
        ]
        errors = validate_schedule(slots)
        assert len(errors) >= 1
        assert "day shift after night shift" in errors[0]

    def test_non_ascii_name_detected(self):
        slots = [
            ScheduleSlot(date=date(2025, 1, 1), shift_type="day",
                         start_time="06:00", teammates=["Ålice"], is_override=False),
        ]
        errors = validate_schedule(slots)
        assert len(errors) >= 1
        assert "Non-ASCII" in errors[0]

    def test_export_raises_on_invalid_schedule(self):
        """CSVExporter.export raises ValueError for invalid schedules."""
        slots = [
            ScheduleSlot(date=date(2025, 1, 2), shift_type="day",
                         start_time="06:00", teammates=["Alice"], is_override=False),
            ScheduleSlot(date=date(2025, 1, 1), shift_type="day",
                         start_time="06:00", teammates=["Bob"], is_override=False),
        ]
        exporter = CSVExporter()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            path = f.name
        try:
            with pytest.raises(ValueError, match="Schedule validation failed"):
                exporter.export(slots, path)
        finally:
            os.unlink(path)


class TestJSONExporter:
    """Tests for JSONExporter — JSON export format."""

    def setup_method(self):
        self.exporter = JSONExporter()

    def _make_slots(self):
        return [
            ScheduleSlot(date=date(2025, 1, 1), shift_type="day",
                         start_time="06:00", teammates=["Alice"], is_override=False),
            ScheduleSlot(date=date(2025, 1, 1), shift_type="night",
                         start_time="18:00", teammates=["Bob"], is_override=False),
        ]

    def test_basic_json_export(self):
        slots = self._make_slots()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            self.exporter.export(slots, path)
            with open(path) as f:
                data = json.load(f)
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["oncallMember"] == ["Alice"]
            assert data[1]["oncallMember"] == ["Bob"]
        finally:
            os.unlink(path)

    def test_json_skips_nobody_slots(self):
        slots = [
            ScheduleSlot(date=date(2025, 1, 1), shift_type="day",
                         start_time="06:00", teammates=["nobody"], is_override=False),
            ScheduleSlot(date=date(2025, 1, 1), shift_type="night",
                         start_time="18:00", teammates=["Bob"], is_override=False),
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            self.exporter.export(slots, path)
            with open(path) as f:
                data = json.load(f)
            # "nobody" slot should be skipped
            assert len(data) == 1
            assert data[0]["oncallMember"] == ["Bob"]
        finally:
            os.unlink(path)

    def test_json_api_format(self):
        slots = self._make_slots()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            self.exporter.export(slots, path, use_api_format=True)
            with open(path) as f:
                data = json.load(f)
            # API format: YYYY-MM-DDTHH:MM:00
            assert data[0]["startDateTime"] == "2025-01-01T06:00:00"
        finally:
            os.unlink(path)

    def test_json_raises_on_invalid_schedule(self):
        slots = [
            ScheduleSlot(date=date(2025, 1, 2), shift_type="day",
                         start_time="06:00", teammates=["Alice"], is_override=False),
            ScheduleSlot(date=date(2025, 1, 1), shift_type="day",
                         start_time="06:00", teammates=["Bob"], is_override=False),
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            with pytest.raises(ValueError, match="Schedule validation failed"):
                self.exporter.export(slots, path)
        finally:
            os.unlink(path)

    def test_json_non_writable_path_raises_oserror(self):
        slots = self._make_slots()
        bad_path = "/nonexistent_dir_xyz/schedule.json"
        with pytest.raises(OSError):
            self.exporter.export(slots, bad_path)
