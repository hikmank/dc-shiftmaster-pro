"""Property-based tests for ICS Calendar Export & Import feature.

Uses Hypothesis to verify correctness properties defined in the design document.
"""

import io
import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from flask import Flask
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster.ics_export import ICSExporter
from dc_shiftmaster.ics_parser import ICSParser
from dc_shiftmaster.json_schedule_import import JSONScheduleImporter
from dc_shiftmaster.models import ScheduleSlot, ShiftWindow
from dc_shiftmaster_html.routes_ics import ics_bp
from tests.conftest import valid_time, valid_shift_windows


# ===========================================================================
# Custom Hypothesis Strategies
# ===========================================================================


@st.composite
def schedule_slot_strategy(draw: st.DrawFn) -> ScheduleSlot:
    """Generate a random ScheduleSlot with non-'nobody' teammates.

    Produces slots suitable for ICS export testing: valid dates,
    shift_types ('day' or 'night'), HH:MM start times, and at least
    one real teammate name (no 'nobody').
    """
    d = draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))
    shift_type = draw(st.sampled_from(["day", "night"]))
    start_time = draw(valid_time())
    # Generate non-empty teammate names using only letters (no commas, no newlines)
    # to keep SUMMARY line parseable and avoid CRLF issues
    teammates = draw(
        st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N")),
                min_size=1,
                max_size=20,
            ).filter(lambda s: s.strip()),
            min_size=1,
            max_size=3,
        )
    )
    return ScheduleSlot(
        date=d,
        shift_type=shift_type,
        start_time=start_time,
        teammates=teammates,
        is_override=draw(st.booleans()),
    )


@st.composite
def shift_windows_strategy(draw: st.DrawFn) -> dict[str, ShiftWindow]:
    """Generate a dict with 'day' and 'night' ShiftWindow for ICS export.

    Ensures start_time != end_time for each window so DTSTART != DTEND.
    """
    day_start = draw(valid_time())
    day_end = draw(valid_time().filter(lambda t: t != day_start))
    night_start = draw(valid_time())
    night_end = draw(valid_time().filter(lambda t: t != night_start))
    return {
        "day": ShiftWindow(shift_type="day", start_time=day_start, end_time=day_end),
        "night": ShiftWindow(shift_type="night", start_time=night_start, end_time=night_end),
    }


@st.composite
def json_entry_strategy(draw: st.DrawFn) -> dict:
    """Generate a valid JSON schedule entry with date, shift_type, and name.

    Valid entries have:
    - date: YYYY-MM-DD string with plausible month (01-12) and day (01-28)
    - shift_type: "day" or "night"
    - name: non-empty alphanumeric string
    """
    year = draw(st.integers(min_value=2020, max_value=2030))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=28))
    date_str = f"{year:04d}-{month:02d}-{day:02d}"
    shift_type = draw(st.sampled_from(["day", "night"]))
    name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=30,
        ).filter(lambda s: s.strip())
    )
    return {"date": date_str, "shift_type": shift_type, "name": name}


@st.composite
def json_export_entry_strategy(draw: st.DrawFn) -> dict:
    """Generate a JSON schedule entry in the full export format.

    Includes all fields produced by /api/export/<year>/json:
    date, shift_type, name, start_time, end_time, teammates, is_override.
    The importer should ignore everything except date, shift_type, and name.
    """
    year = draw(st.integers(min_value=2020, max_value=2030))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=28))
    date_str = f"{year:04d}-{month:02d}-{day:02d}"
    shift_type = draw(st.sampled_from(["day", "night"]))
    name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=30,
        ).filter(lambda s: s.strip())
    )
    # Extra fields present in the export format that should be ignored on import
    start_hour = draw(st.integers(min_value=0, max_value=23))
    start_min = draw(st.integers(min_value=0, max_value=59))
    start_time = f"{start_hour:02d}:{start_min:02d}"
    end_hour = draw(st.integers(min_value=0, max_value=23))
    end_min = draw(st.integers(min_value=0, max_value=59))
    end_time = f"{end_hour:02d}:{end_min:02d}"
    teammates = draw(
        st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N")),
                min_size=1,
                max_size=15,
            ).filter(lambda s: s.strip()),
            min_size=1,
            max_size=4,
        )
    )
    is_override = draw(st.booleans())

    return {
        "date": date_str,
        "shift_type": shift_type,
        "name": name,
        "start_time": start_time,
        "end_time": end_time,
        "teammates": teammates,
        "is_override": is_override,
    }


@st.composite
def invalid_json_entry_strategy(draw: st.DrawFn) -> dict:
    """Generate a JSON schedule entry with at least one validation failure.

    Produces entries with one of:
    - Missing date field
    - Non-string date value
    - Invalid date format (not YYYY-MM-DD)
    - Invalid shift_type (not "day" or "night")
    - Missing name field
    - Empty name (whitespace only)
    """
    failure_type = draw(
        st.sampled_from([
            "missing_date",
            "non_string_date",
            "invalid_date_format",
            "invalid_shift_type",
            "missing_name",
            "empty_name",
        ])
    )

    # Start with a valid base entry
    entry = {}

    if failure_type == "missing_date":
        # No date field at all
        entry["shift_type"] = draw(st.sampled_from(["day", "night"]))
        entry["name"] = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N")),
                min_size=1,
                max_size=20,
            ).filter(lambda s: s.strip())
        )

    elif failure_type == "non_string_date":
        # date is not a string (integer, list, None, bool)
        entry["date"] = draw(
            st.one_of(
                st.integers(min_value=0, max_value=99999),
                st.lists(st.integers(), max_size=3),
                st.none(),
                st.booleans(),
            )
        )
        entry["shift_type"] = draw(st.sampled_from(["day", "night"]))
        entry["name"] = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N")),
                min_size=1,
                max_size=20,
            ).filter(lambda s: s.strip())
        )

    elif failure_type == "invalid_date_format":
        # date is a string but not YYYY-MM-DD
        bad_date = draw(
            st.one_of(
                # Wrong separators
                st.from_regex(r"\d{4}/\d{2}/\d{2}", fullmatch=True),
                # Wrong length
                st.text(
                    alphabet=st.characters(whitelist_categories=("N",)),
                    min_size=1,
                    max_size=6,
                ),
                # Random text
                st.text(
                    alphabet=st.characters(whitelist_categories=("L",)),
                    min_size=1,
                    max_size=10,
                ),
                # Missing parts
                st.from_regex(r"\d{4}-\d{2}", fullmatch=True),
            )
        )
        entry["date"] = bad_date
        entry["shift_type"] = draw(st.sampled_from(["day", "night"]))
        entry["name"] = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N")),
                min_size=1,
                max_size=20,
            ).filter(lambda s: s.strip())
        )

    elif failure_type == "invalid_shift_type":
        # shift_type is not "day" or "night"
        year = draw(st.integers(min_value=2020, max_value=2030))
        month = draw(st.integers(min_value=1, max_value=12))
        day = draw(st.integers(min_value=1, max_value=28))
        entry["date"] = f"{year:04d}-{month:02d}-{day:02d}"
        bad_shift = draw(
            st.one_of(
                st.text(
                    alphabet=st.characters(whitelist_categories=("L",)),
                    min_size=1,
                    max_size=15,
                ).filter(lambda s: s.lower() not in ("day", "night")),
                st.just(""),
                st.just("DAY"),
                st.just("NIGHT"),
                st.just("morning"),
                st.just("evening"),
            )
        )
        entry["shift_type"] = bad_shift
        entry["name"] = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N")),
                min_size=1,
                max_size=20,
            ).filter(lambda s: s.strip())
        )

    elif failure_type == "missing_name":
        # No name field at all
        year = draw(st.integers(min_value=2020, max_value=2030))
        month = draw(st.integers(min_value=1, max_value=12))
        day = draw(st.integers(min_value=1, max_value=28))
        entry["date"] = f"{year:04d}-{month:02d}-{day:02d}"
        entry["shift_type"] = draw(st.sampled_from(["day", "night"]))

    elif failure_type == "empty_name":
        # name is empty or whitespace-only
        year = draw(st.integers(min_value=2020, max_value=2030))
        month = draw(st.integers(min_value=1, max_value=12))
        day = draw(st.integers(min_value=1, max_value=28))
        entry["date"] = f"{year:04d}-{month:02d}-{day:02d}"
        entry["shift_type"] = draw(st.sampled_from(["day", "night"]))
        entry["name"] = draw(
            st.text(
                alphabet=st.sampled_from([" ", "\t", "\n", "\r"]),
                min_size=0,
                max_size=5,
            )
        )

    return entry


# ===========================================================================
# Feature: ics-calendar-export-import, Property 2: ICS Format Round-Trip
# ===========================================================================


class TestICSFormatRoundTrip:
    """Property 2: ICS Format Round-Trip.

    *For any* valid ICS text produced by the ICSExporter, parsing via ICSParser
    then re-exporting via ICSExporter (with the same DTSTAMP) SHALL produce
    output byte-equivalent to the original ICS text.

    **Validates: Requirements 7.2**
    """

    @given(
        slots=st.lists(schedule_slot_strategy(), min_size=1, max_size=5),
        shift_windows=shift_windows_strategy(),
    )
    @settings(max_examples=100)
    def test_format_round_trip_byte_equivalent(self, slots, shift_windows):
        """Export → parse → re-export (same DTSTAMP) produces identical output.

        **Validates: Requirements 7.2**
        """
        exporter = ICSExporter()
        parser = ICSParser()

        # Fix DTSTAMP to a deterministic value for both export passes
        fixed_dtstamp = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

        with patch("dc_shiftmaster.ics_export.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_dtstamp
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            # First export
            ics_text_1 = exporter.export(slots, shift_windows)

        # Parse the exported ICS
        parse_result = parser.parse(ics_text_1)

        # Reconstruct ScheduleSlots from parsed events for re-export
        reconstructed_slots = []
        for event in parse_result.events:
            # Extract date from DTSTART (YYYYMMDDTHHMMSS)
            dtstart_str = event.dtstart
            slot_date = date(
                int(dtstart_str[0:4]),
                int(dtstart_str[4:6]),
                int(dtstart_str[6:8]),
            )

            # Extract start_time from DTSTART
            start_hour = int(dtstart_str[9:11])
            start_min = int(dtstart_str[11:13])
            start_time = f"{start_hour:02d}:{start_min:02d}"

            # Extract shift_type and teammates from SUMMARY
            # Format: "{shift_type} Shift - {comma-separated names}"
            summary = event.summary
            dash_idx = summary.find(" Shift - ")
            if dash_idx >= 0:
                shift_type = summary[:dash_idx]
                names_str = summary[dash_idx + len(" Shift - "):]
                teammates = [n.strip() for n in names_str.split(",")]
            else:
                # Fallback — shouldn't happen with our exporter output
                shift_type = "day"
                teammates = [summary]

            # Determine is_override — doesn't affect ICS output
            reconstructed_slots.append(
                ScheduleSlot(
                    date=slot_date,
                    shift_type=shift_type,
                    start_time=start_time,
                    teammates=teammates,
                    is_override=False,
                )
            )

        # Re-export with the same fixed DTSTAMP
        with patch("dc_shiftmaster.ics_export.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_dtstamp
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            ics_text_2 = exporter.export(reconstructed_slots, shift_windows)

        # The two ICS outputs must be byte-equivalent
        assert ics_text_1 == ics_text_2, (
            f"Round-trip produced different output.\n"
            f"--- Original (first 500 chars) ---\n{ics_text_1[:500]}\n"
            f"--- Re-exported (first 500 chars) ---\n{ics_text_2[:500]}"
        )


# ===========================================================================
# Feature: ics-calendar-export-import, Property 9: Invalid JSON Entries Rejected
# ===========================================================================


class TestInvalidJSONEntriesRejected:
    """Property 9: Invalid JSON Entries Rejected.

    *For any* JSON schedule entry where the `date` field is missing or not a valid
    YYYY-MM-DD string, OR the `shift_type` is not "day" or "night", OR the `name`
    field is missing or empty, the JSONScheduleImporter SHALL reject that entry and
    include a descriptive error, while still processing remaining valid entries.

    **Validates: Requirements 11.3, 11.4, 11.5**
    """

    @given(invalid_entry=invalid_json_entry_strategy())
    @settings(max_examples=100)
    def test_single_invalid_entry_is_rejected(self, invalid_entry):
        """Any single invalid entry is rejected with a descriptive error."""
        importer = JSONScheduleImporter()
        json_text = json.dumps([invalid_entry])
        result = importer.parse(json_text)

        # The invalid entry should NOT appear in entries
        assert len(result.entries) == 0, (
            f"Invalid entry was incorrectly accepted: {invalid_entry}"
        )
        # There should be at least one error describing the rejection
        assert len(result.errors) >= 1, (
            f"No error reported for invalid entry: {invalid_entry}"
        )
        # The error message should be descriptive (non-empty)
        for error in result.errors:
            assert len(error) > 0, "Error message should not be empty"

    @given(
        valid_entries=st.lists(json_entry_strategy(), min_size=1, max_size=5),
        invalid_entries=st.lists(invalid_json_entry_strategy(), min_size=1, max_size=5),
    )
    @settings(max_examples=100)
    def test_invalid_entries_do_not_block_valid_ones(
        self, valid_entries, invalid_entries
    ):
        """Valid entries are still processed when mixed with invalid ones.

        **Validates: Requirements 11.3, 11.4, 11.5**
        """
        importer = JSONScheduleImporter()
        # Interleave valid and invalid entries
        all_entries = valid_entries + invalid_entries
        json_text = json.dumps(all_entries)
        result = importer.parse(json_text)

        # All valid entries should be accepted
        assert len(result.entries) == len(valid_entries), (
            f"Expected {len(valid_entries)} valid entries, got {len(result.entries)}. "
            f"Errors: {result.errors}"
        )
        # All invalid entries should produce errors
        assert len(result.errors) >= len(invalid_entries), (
            f"Expected at least {len(invalid_entries)} errors, got {len(result.errors)}"
        )

    @given(valid_entries=st.lists(json_entry_strategy(), min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_all_valid_entries_produce_no_errors(self, valid_entries):
        """A list of only valid entries produces zero errors.

        **Validates: Requirements 11.3, 11.4, 11.5**
        """
        importer = JSONScheduleImporter()
        json_text = json.dumps(valid_entries)
        result = importer.parse(json_text)

        assert len(result.entries) == len(valid_entries), (
            f"Expected {len(valid_entries)} entries, got {len(result.entries)}. "
            f"Errors: {result.errors}"
        )
        assert len(result.errors) == 0, (
            f"Unexpected errors for valid entries: {result.errors}"
        )


# ===========================================================================
# Feature: ics-calendar-export-import, Property 10: JSON Export-Import Round-Trip
# ===========================================================================


class TestJSONExportImportRoundTrip:
    """Property 10: JSON Export-Import Round-Trip.

    *For any* valid schedule exported via the existing `/api/export/<year>/json`
    endpoint, importing that JSON file via JSONScheduleImporter SHALL produce
    override entries equivalent to the shift assignments in the original schedule
    (matching date, shift_type, and name for each entry).

    **Validates: Requirements 13.1, 13.2, 13.3**
    """

    @given(entries=st.lists(json_export_entry_strategy(), min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_round_trip_preserves_date_shift_type_name(self, entries):
        """Importing JSON export entries produces equivalent override entries.

        For each exported entry with all fields (date, shift_type, name,
        start_time, end_time, teammates, is_override), the importer extracts
        only date, shift_type, and name — matching the original values exactly.

        **Validates: Requirements 13.1, 13.2, 13.3**
        """
        importer = JSONScheduleImporter()
        json_text = json.dumps(entries)
        result = importer.parse(json_text)

        # All entries should be accepted without errors
        assert len(result.errors) == 0, (
            f"Unexpected errors during import: {result.errors}"
        )
        assert len(result.entries) == len(entries), (
            f"Expected {len(entries)} entries, got {len(result.entries)}"
        )

        # Each imported entry must match the original date, shift_type, and name
        for original, imported in zip(entries, result.entries):
            assert imported.date == original["date"], (
                f"Date mismatch: expected {original['date']}, got {imported.date}"
            )
            assert imported.shift_type == original["shift_type"], (
                f"Shift type mismatch: expected {original['shift_type']}, "
                f"got {imported.shift_type}"
            )
            assert imported.name == original["name"], (
                f"Name mismatch: expected {original['name']}, got {imported.name}"
            )

    @given(entries=st.lists(json_export_entry_strategy(), min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_extra_fields_are_ignored(self, entries):
        """Extra fields in the export format do not cause errors or affect results.

        The importer must silently ignore start_time, end_time, teammates,
        is_override, and any other fields beyond the required date, shift_type,
        and name.

        **Validates: Requirements 13.1, 13.2, 13.3**
        """
        importer = JSONScheduleImporter()
        json_text = json.dumps(entries)
        result = importer.parse(json_text)

        # No errors — extra fields should not trigger validation failures
        assert len(result.errors) == 0, (
            f"Extra fields caused errors: {result.errors}"
        )
        # All entries accepted
        assert len(result.entries) == len(entries)

    @given(entries=st.lists(json_export_entry_strategy(), min_size=0, max_size=10))
    @settings(max_examples=100)
    def test_round_trip_entry_count_matches(self, entries):
        """The number of imported entries equals the number of exported entries.

        **Validates: Requirements 13.1, 13.2, 13.3**
        """
        importer = JSONScheduleImporter()
        json_text = json.dumps(entries)
        result = importer.parse(json_text)

        assert len(result.entries) == len(entries), (
            f"Entry count mismatch: exported {len(entries)}, "
            f"imported {len(result.entries)}. Errors: {result.errors}"
        )
        assert len(result.errors) == 0


# ===========================================================================
# Feature: ics-calendar-export-import, Property 1: ICS Export-Import Round-Trip
# ===========================================================================


class TestICSExportImportRoundTrip:
    """Property 1: ICS Export-Import Round-Trip.

    *For any* valid list of ScheduleSlots (with non-"nobody" teammates),
    exporting via ICSExporter then parsing via ICSParser SHALL produce event
    records with equivalent date, shift_type, start_time, end_time, and
    teammate assignments as the original ScheduleSlots.

    **Validates: Requirements 7.1, 3.1, 3.2, 3.3, 3.5**
    """

    @given(
        slots=st.lists(schedule_slot_strategy(), min_size=1, max_size=5),
        shift_windows=shift_windows_strategy(),
    )
    @settings(max_examples=100)
    def test_round_trip_preserves_date_shift_type_times_teammates(
        self, slots, shift_windows
    ):
        """Export ScheduleSlots → ICS text → parse back → verify fields match.


        For each slot, the parsed event must have:
        - DTSTART date+time matching slot.date + ShiftWindow.start_time
        - DTEND date+time matching slot.date + ShiftWindow.end_time
          (with next-day for night shifts where end_time < start_time)
        - SUMMARY containing shift_type and comma-separated teammate names

        **Validates: Requirements 7.1, 3.1, 3.2, 3.3, 3.5**
        """
        exporter = ICSExporter()
        parser = ICSParser()

        # Export schedule slots to ICS text
        ics_text = exporter.export(slots, shift_windows)

        # Parse the ICS text back
        parse_result = parser.parse(ics_text)

        # Should have no errors and same number of events as slots
        assert len(parse_result.errors) == 0, (
            f"Unexpected parse errors: {parse_result.errors}"
        )
        assert len(parse_result.skipped) == 0, (
            f"Unexpected skipped events: {parse_result.skipped}"
        )
        assert len(parse_result.events) == len(slots), (
            f"Expected {len(slots)} events, got {len(parse_result.events)}"
        )

        # Verify each parsed event matches the corresponding slot
        for slot, event in zip(slots, parse_result.events):
            window = shift_windows[slot.shift_type]

            # Verify DTSTART matches slot.date + window.start_time
            start_parts = window.start_time.split(":")
            start_hour = int(start_parts[0])
            start_min = int(start_parts[1])
            expected_dtstart = (
                f"{slot.date.strftime('%Y%m%d')}T{start_hour:02d}{start_min:02d}00"
            )
            assert event.dtstart == expected_dtstart, (
                f"DTSTART mismatch for {slot.date}/{slot.shift_type}: "
                f"expected {expected_dtstart}, got {event.dtstart}"
            )

            # Verify DTEND matches slot.date + window.end_time
            # (with next-day handling for night shifts)
            end_parts = window.end_time.split(":")
            end_hour = int(end_parts[0])
            end_min = int(end_parts[1])
            end_date = slot.date
            if window.end_time < window.start_time:
                # Night shift crosses midnight — DTEND is next day
                end_date = slot.date + timedelta(days=1)
            expected_dtend = (
                f"{end_date.strftime('%Y%m%d')}T{end_hour:02d}{end_min:02d}00"
            )
            assert event.dtend == expected_dtend, (
                f"DTEND mismatch for {slot.date}/{slot.shift_type}: "
                f"expected {expected_dtend}, got {event.dtend}"
            )

            # Verify SUMMARY contains shift_type and teammate names
            # Format: "{shift_type} Shift - {comma-separated names}"
            expected_summary_prefix = f"{slot.shift_type} Shift - "
            assert event.summary.startswith(expected_summary_prefix), (
                f"SUMMARY prefix mismatch: expected to start with "
                f"'{expected_summary_prefix}', got '{event.summary}'"
            )

            # Extract teammate names from SUMMARY and compare
            names_str = event.summary[len(expected_summary_prefix):]
            parsed_teammates = [n.strip() for n in names_str.split(",")]
            assert parsed_teammates == slot.teammates, (
                f"Teammates mismatch for {slot.date}/{slot.shift_type}: "
                f"expected {slot.teammates}, got {parsed_teammates}"
            )

            # Verify UID format: {date}-{shift_type}@dc-shiftmaster
            expected_uid = (
                f"{slot.date.isoformat()}-{slot.shift_type}@dc-shiftmaster"
            )
            assert event.uid == expected_uid, (
                f"UID mismatch: expected {expected_uid}, got {event.uid}"
            )


# ===========================================================================
# Feature: ics-calendar-export-import, Property 7: Shift Type Classification from Hour
# ===========================================================================


class TestShiftTypeClassificationFromHour:
    """Property 7: Shift Type Classification from Hour.

    *For any* DTSTART hour value, the shift type classification SHALL return
    `day` if the hour is between 5 and 13 inclusive, and `night` otherwise.
    This mapping SHALL be deterministic and total (defined for all 24 hours).

    **Validates: Requirements 5.1**
    """

    @given(hour=st.integers(min_value=0, max_value=23))
    @settings(max_examples=100, deadline=None)
    def test_shift_type_day_for_hours_5_to_13(self, hour):
        """For any hour 0-23, classification returns 'day' iff 5 <= hour <= 13.

        **Validates: Requirements 5.1**
        """
        from dc_shiftmaster_html.routes_ics import _determine_shift_type

        # Build a DTSTART string like "20250315T{HH}0000"
        dtstart = f"20250315T{hour:02d}0000"
        result = _determine_shift_type(dtstart)

        if 5 <= hour <= 13:
            assert result == "day", (
                f"Hour {hour:02d} should classify as 'day', got '{result}'"
            )
        else:
            assert result == "night", (
                f"Hour {hour:02d} should classify as 'night', got '{result}'"
            )

    @given(
        hour=st.integers(min_value=0, max_value=23),
        year=st.integers(min_value=2020, max_value=2030),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),
        minute=st.integers(min_value=0, max_value=59),
        second=st.integers(min_value=0, max_value=59),
    )
    @settings(max_examples=100, deadline=None)
    def test_shift_type_deterministic_across_dates(
        self, hour, year, month, day, minute, second
    ):
        """Classification depends only on hour, not on date, minute, or second.

        **Validates: Requirements 5.1**
        """
        from dc_shiftmaster_html.routes_ics import _determine_shift_type

        dtstart = f"{year:04d}{month:02d}{day:02d}T{hour:02d}{minute:02d}{second:02d}"
        result = _determine_shift_type(dtstart)

        expected = "day" if 5 <= hour <= 13 else "night"
        assert result == expected, (
            f"For DTSTART '{dtstart}', expected '{expected}' but got '{result}'"
        )


# ===========================================================================
# Feature: ics-calendar-export-import, Property 8: Name Resolution from SUMMARY
# ===========================================================================


class TestNameResolutionFromSummary:
    """Property 8: Name Resolution from SUMMARY.

    *For any* VEVENT SUMMARY string and any team roster, if the SUMMARY
    contains a teammate name from the roster, that name SHALL be used for
    the override. If no roster name matches, the full SUMMARY text SHALL
    be used as the override name.

    **Validates: Requirements 5.2, 5.3**
    """

    @given(
        shift_type=st.sampled_from(["day", "night"]),
        roster_name=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=20,
        ).filter(lambda s: s.strip() and "," not in s and " - " not in s),
        extra_names=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N")),
                min_size=1,
                max_size=20,
            ).filter(lambda s: s.strip() and "," not in s and " - " not in s),
            min_size=0,
            max_size=3,
        ),
    )
    @settings(max_examples=100, deadline=None)
    def test_roster_name_in_summary_is_resolved(
        self, shift_type, roster_name, extra_names
    ):
        """When SUMMARY contains a roster name, that name is returned.

        **Validates: Requirements 5.2**
        """
        from dc_shiftmaster_html.routes_ics import _resolve_name_from_summary

        # Build SUMMARY in standard format: "{shift_type} Shift - {name1, name2...}"
        all_names = [roster_name] + extra_names
        summary = f"{shift_type} Shift - {', '.join(all_names)}"
        roster = [roster_name]

        result = _resolve_name_from_summary(summary, roster)
        assert result == roster_name, (
            f"Expected roster name '{roster_name}' to be resolved from "
            f"SUMMARY '{summary}', but got '{result}'"
        )

    @given(
        summary_text=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
            min_size=1,
            max_size=50,
        ).filter(lambda s: s.strip() and " - " not in s),
        roster_names=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("L",)),
                min_size=5,
                max_size=20,
            ).filter(lambda s: s.strip()),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=100, deadline=None)
    def test_no_roster_match_returns_full_summary(self, summary_text, roster_names):
        """When no roster name matches SUMMARY, full SUMMARY text is returned.

        **Validates: Requirements 5.3**
        """
        from dc_shiftmaster_html.routes_ics import _resolve_name_from_summary

        # Ensure no roster name appears in the summary text
        assume(all(name not in summary_text for name in roster_names))

        result = _resolve_name_from_summary(summary_text, roster_names)
        assert result == summary_text, (
            f"Expected full SUMMARY '{summary_text}' when no roster match, "
            f"but got '{result}'"
        )

    @given(
        shift_type=st.sampled_from(["day", "night"]),
        name=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=20,
        ).filter(lambda s: s.strip() and "," not in s and " - " not in s),
    )
    @settings(max_examples=100, deadline=None)
    def test_no_roster_match_with_standard_format_returns_full_summary(
        self, shift_type, name
    ):
        """When SUMMARY has standard format but name is not in roster, full SUMMARY is returned.

        **Validates: Requirements 5.3**
        """
        from dc_shiftmaster_html.routes_ics import _resolve_name_from_summary

        summary = f"{shift_type} Shift - {name}"
        # Provide a roster that does NOT contain the name in the SUMMARY
        roster = ["CompletelyDifferentPerson123"]
        assume(name != "CompletelyDifferentPerson123")
        assume("CompletelyDifferentPerson123" not in summary)

        result = _resolve_name_from_summary(summary, roster)
        assert result == summary, (
            f"Expected full SUMMARY '{summary}' when roster doesn't match, "
            f"but got '{result}'"
        )


# ===========================================================================
# Feature: ics-calendar-export-import, Property 6: Date Range Filtering
# ===========================================================================


class TestDateRangeFiltering:
    """Property 6: Date Range Filtering.

    *For any* list of ScheduleSlots and any valid `from` and `to` dates,
    filtering the schedule by date range SHALL produce a result where every
    slot's date is >= `from` and <= `to`, and no slot from the original list
    falling within the range is excluded.

    **Validates: Requirements 1.2, 1.3**
    """

    @staticmethod
    def _filter_by_date_range(
        schedule: list, from_date: date | None, to_date: date | None
    ) -> list:
        """Replicate the date range filtering logic from routes_export._compute_and_validate."""
        if from_date:
            schedule = [s for s in schedule if s.date >= from_date]
        if to_date:
            schedule = [s for s in schedule if s.date <= to_date]
        return schedule

    @given(
        slots=st.lists(schedule_slot_strategy(), min_size=0, max_size=15),
        from_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
        to_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
    )
    @settings(max_examples=100)
    def test_filtered_slots_are_within_range(self, slots, from_date, to_date):
        """All slots in the filtered result have date >= from_date and date <= to_date.

        **Validates: Requirements 1.2, 1.3**
        """
        # Ensure from_date <= to_date for a valid range
        assume(from_date <= to_date)

        filtered = self._filter_by_date_range(slots, from_date, to_date)

        # Every slot in the result must fall within [from_date, to_date]
        for slot in filtered:
            assert slot.date >= from_date, (
                f"Slot date {slot.date} is before from_date {from_date}"
            )
            assert slot.date <= to_date, (
                f"Slot date {slot.date} is after to_date {to_date}"
            )

    @given(
        slots=st.lists(schedule_slot_strategy(), min_size=0, max_size=15),
        from_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
        to_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
    )
    @settings(max_examples=100)
    def test_no_in_range_slot_excluded(self, slots, from_date, to_date):
        """No slot from the original list that falls within [from_date, to_date] is excluded.

        **Validates: Requirements 1.2, 1.3**
        """
        # Ensure from_date <= to_date for a valid range
        assume(from_date <= to_date)

        filtered = self._filter_by_date_range(slots, from_date, to_date)

        # Collect all original slots that are within the range
        expected_in_range = [
            s for s in slots if from_date <= s.date <= to_date
        ]

        # Every slot that should be in range must appear in the filtered result
        assert len(filtered) == len(expected_in_range), (
            f"Expected {len(expected_in_range)} slots in range "
            f"[{from_date}, {to_date}], got {len(filtered)}"
        )
        for slot in expected_in_range:
            assert slot in filtered, (
                f"Slot {slot.date}/{slot.shift_type} is within range "
                f"[{from_date}, {to_date}] but was excluded from results"
            )

    @given(
        slots=st.lists(schedule_slot_strategy(), min_size=0, max_size=15),
        from_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
    )
    @settings(max_examples=100)
    def test_from_only_filter(self, slots, from_date):
        """When only from_date is provided, all slots with date >= from_date are included.

        **Validates: Requirements 1.2, 1.3**
        """
        filtered = self._filter_by_date_range(slots, from_date, None)

        # All filtered slots must have date >= from_date
        for slot in filtered:
            assert slot.date >= from_date, (
                f"Slot date {slot.date} is before from_date {from_date}"
            )

        # All original slots with date >= from_date must be present
        expected = [s for s in slots if s.date >= from_date]
        assert len(filtered) == len(expected), (
            f"Expected {len(expected)} slots with date >= {from_date}, "
            f"got {len(filtered)}"
        )

    @given(
        slots=st.lists(schedule_slot_strategy(), min_size=0, max_size=15),
        to_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
    )
    @settings(max_examples=100)
    def test_to_only_filter(self, slots, to_date):
        """When only to_date is provided, all slots with date <= to_date are included.

        **Validates: Requirements 1.2, 1.3**
        """
        filtered = self._filter_by_date_range(slots, None, to_date)

        # All filtered slots must have date <= to_date
        for slot in filtered:
            assert slot.date <= to_date, (
                f"Slot date {slot.date} is after to_date {to_date}"
            )

        # All original slots with date <= to_date must be present
        expected = [s for s in slots if s.date <= to_date]
        assert len(filtered) == len(expected), (
            f"Expected {len(expected)} slots with date <= {to_date}, "
            f"got {len(filtered)}"
        )


# ===========================================================================
# Feature: ics-calendar-export-import, Property 11: Conflict Detection and Overwrite
# ===========================================================================


@st.composite
def conflicting_entries_strategy(draw: st.DrawFn) -> list[dict]:
    """Generate a list of valid JSON schedule entries with unique (date, shift_type) keys.

    Each entry has a unique (date, shift_type) combination so they can be used
    as pre-existing overrides and conflicting import entries.
    """
    count = draw(st.integers(min_value=1, max_value=5))
    entries = []
    seen_keys = set()
    for _ in range(count):
        year = draw(st.integers(min_value=2020, max_value=2030))
        month = draw(st.integers(min_value=1, max_value=12))
        day = draw(st.integers(min_value=1, max_value=28))
        shift_type = draw(st.sampled_from(["day", "night"]))
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        key = (date_str, shift_type)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        name = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N")),
                min_size=1,
                max_size=20,
            ).filter(lambda s: s.strip())
        )
        entries.append({"date": date_str, "shift_type": shift_type, "name": name})
    assume(len(entries) >= 1)
    return entries


@st.composite
def replacement_name_strategy(draw: st.DrawFn) -> str:
    """Generate a replacement name that is non-empty alphanumeric."""
    return draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=20,
        ).filter(lambda s: s.strip())
    )


class TestConflictDetectionAndOverwrite:
    """Property 11: Conflict Detection and Overwrite.

    *For any* set of valid entries that overlap with existing overrides:
    - Without overwrite: conflicting entries are skipped, added to conflicts array,
      imported_count does not include them
    - With overwrite=true: conflicting entries replace existing overrides, are counted
      in imported_count

    **Validates: Requirements 5.5, 11.6, 11.7**
    """

    def _create_app(self):
        """Create a Flask test app with in-memory database."""
        app = Flask(__name__)
        db = DatabaseManager(":memory:")
        app.config["db"] = db
        app.register_blueprint(ics_bp)
        return app, db

    def _upload(self, client, entries, overwrite=False):
        """Helper to POST JSON entries to /api/import/schedule-json."""
        data = json.dumps(entries).encode("utf-8")
        query = "?overwrite=true" if overwrite else ""
        return client.post(
            f"/api/import/schedule-json{query}",
            data={"file": (io.BytesIO(data), "schedule.json")},
            content_type="multipart/form-data",
        )

    @given(entries=conflicting_entries_strategy())
    @settings(max_examples=100)
    def test_without_overwrite_conflicts_are_skipped(self, entries):
        """Without overwrite=true, conflicting entries are skipped and reported.

        Pre-seeds the database with overrides matching the entries' (date, shift_type).
        Then imports the same entries. All should be reported as conflicts with
        imported_count=0.

        **Validates: Requirements 5.5, 11.6, 11.7**
        """
        app, db = self._create_app()

        # Pre-seed existing overrides in the database
        for entry in entries:
            db.set_override(entry["date"], entry["shift_type"], entry["name"])

        # Now import entries that target the same (date, shift_type)
        # Use different names to make it clear these are new imports
        import_entries = [
            {"date": e["date"], "shift_type": e["shift_type"], "name": e["name"] + "NEW"}
            for e in entries
        ]

        with app.test_client() as client:
            resp = self._upload(client, import_entries, overwrite=False)
            body = resp.get_json()

            # All entries should be conflicts since they overlap existing overrides
            assert body["imported_count"] == 0, (
                f"Expected imported_count=0, got {body['imported_count']}. "
                f"Conflicts should not be imported without overwrite=true."
            )
            assert body["skipped_count"] == len(entries), (
                f"Expected skipped_count={len(entries)}, got {body['skipped_count']}"
            )
            assert len(body["conflicts"]) == len(entries), (
                f"Expected {len(entries)} conflicts, got {len(body['conflicts'])}"
            )

            # Each conflict should reference the existing override's name
            conflict_keys = {(c["date"], c["shift_type"]) for c in body["conflicts"]}
            for entry in entries:
                key = (entry["date"], entry["shift_type"])
                assert key in conflict_keys, (
                    f"Expected conflict for {key} not found in response"
                )

            # Verify existing overrides are unchanged in the database
            for entry in entries:
                year = int(entry["date"][:4])
                overrides = db.get_overrides(year)
                matching = [
                    o for o in overrides
                    if o.date == entry["date"] and o.shift_type == entry["shift_type"]
                ]
                assert len(matching) == 1
                # Original name should be preserved (not the NEW name)
                assert matching[0].name == entry["name"], (
                    f"Override was modified without overwrite=true: "
                    f"expected '{entry['name']}', got '{matching[0].name}'"
                )

    @given(
        entries=conflicting_entries_strategy(),
        new_names=st.lists(replacement_name_strategy(), min_size=5, max_size=10),
    )
    @settings(max_examples=100)
    def test_with_overwrite_conflicts_are_replaced(self, entries, new_names):
        """With overwrite=true, conflicting entries replace existing overrides.

        Pre-seeds overrides, then imports with overwrite=true. The imported values
        should replace existing ones and be counted in imported_count.

        **Validates: Requirements 5.5, 11.6, 11.7**
        """
        app, db = self._create_app()

        # Pre-seed existing overrides
        for entry in entries:
            db.set_override(entry["date"], entry["shift_type"], entry["name"])

        # Create import entries with new names (different from existing)
        import_entries = []
        for i, entry in enumerate(entries):
            new_name = new_names[i % len(new_names)]
            # Ensure new_name is different from existing to prove overwrite works
            if new_name == entry["name"]:
                new_name = new_name + "X"
            import_entries.append({
                "date": entry["date"],
                "shift_type": entry["shift_type"],
                "name": new_name,
            })

        with app.test_client() as client:
            resp = self._upload(client, import_entries, overwrite=True)
            body = resp.get_json()

            # All entries should be imported (overwrite replaces conflicts)
            assert body["imported_count"] == len(entries), (
                f"Expected imported_count={len(entries)}, got {body['imported_count']}. "
                f"With overwrite=true, conflicts should be replaced."
            )
            assert body["skipped_count"] == 0, (
                f"Expected skipped_count=0, got {body['skipped_count']}"
            )
            assert len(body["conflicts"]) == 0, (
                f"Expected no conflicts with overwrite=true, got {body['conflicts']}"
            )

            # Verify the overrides in the database now have the new names
            for i, entry in enumerate(entries):
                year = int(entry["date"][:4])
                overrides = db.get_overrides(year)
                matching = [
                    o for o in overrides
                    if o.date == entry["date"] and o.shift_type == entry["shift_type"]
                ]
                assert len(matching) == 1
                expected_name = import_entries[i]["name"]
                assert matching[0].name == expected_name, (
                    f"Override not updated with overwrite=true: "
                    f"expected '{expected_name}', got '{matching[0].name}'"
                )

    @given(
        existing_entries=conflicting_entries_strategy(),
        new_entries=conflicting_entries_strategy(),
    )
    @settings(max_examples=100)
    def test_non_conflicting_entries_imported_alongside_conflicts(
        self, existing_entries, new_entries
    ):
        """Non-conflicting entries are imported even when other entries conflict.

        Some entries conflict with existing overrides (skipped without overwrite),
        while new entries with different keys are imported normally.

        **Validates: Requirements 5.5, 11.6, 11.7**
        """
        app, db = self._create_app()

        # Pre-seed existing overrides
        for entry in existing_entries:
            db.set_override(entry["date"], entry["shift_type"], entry["name"])

        # Identify which new_entries actually conflict with existing ones
        existing_keys = {(e["date"], e["shift_type"]) for e in existing_entries}
        non_conflicting = [
            e for e in new_entries
            if (e["date"], e["shift_type"]) not in existing_keys
        ]
        conflicting = [
            e for e in new_entries
            if (e["date"], e["shift_type"]) in existing_keys
        ]

        with app.test_client() as client:
            resp = self._upload(client, new_entries, overwrite=False)
            body = resp.get_json()

            # Non-conflicting entries should be imported
            assert body["imported_count"] == len(non_conflicting), (
                f"Expected imported_count={len(non_conflicting)}, "
                f"got {body['imported_count']}"
            )
            # Conflicting entries should be skipped
            assert body["skipped_count"] == len(conflicting), (
                f"Expected skipped_count={len(conflicting)}, "
                f"got {body['skipped_count']}"
            )
            assert len(body["conflicts"]) == len(conflicting), (
                f"Expected {len(conflicting)} conflicts, "
                f"got {len(body['conflicts'])}"
            )
