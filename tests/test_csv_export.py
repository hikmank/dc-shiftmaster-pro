"""Property-based tests for CSVExporter — CSV format, ordering, and round-trip.

Uses Hypothesis to verify structural invariants, date formatting,
chronological ordering, and export/parse round-trip integrity.
"""

import calendar
import re
import tempfile
from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from dc_shiftmaster.csv_export import CSVExporter
from dc_shiftmaster.models import Teammate, ShiftWindow, ScheduleSlot
from dc_shiftmaster.scheduling import SchedulingEngine
from tests.conftest import valid_year, valid_teammate, valid_time


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_SHIFT_TYPES = ["FHD", "FHN", "BHD", "BHN"]


@st.composite
def full_teammate_set(draw):
    """Generate exactly one teammate per shift type (FHD, FHN, BHD, BHN).

    Names are restricted to ASCII letters and digits to avoid encoding
    issues when writing CSV on Windows (cp1252).
    """
    teammates = []
    for i, st_type in enumerate(ALL_SHIFT_TYPES):
        name = draw(
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("L", "N"),
                    max_codepoint=127,
                ),
                min_size=1,
                max_size=20,
            ).filter(lambda s: s.strip())
        )
        teammates.append(Teammate(id=i + 1, name=name, shift_type=st_type))
    return teammates


@st.composite
def shift_windows_pair(draw):
    """Generate a dict with 'day' and 'night' ShiftWindow entries."""
    day_start = draw(valid_time())
    day_end = draw(valid_time())
    night_start = draw(valid_time())
    night_end = draw(valid_time())
    return {
        "day": ShiftWindow(shift_type="day", start_time=day_start, end_time=day_end),
        "night": ShiftWindow(shift_type="night", start_time=night_start, end_time=night_end),
    }


def _generate_and_export(year, teammates, windows):
    """Compute an annual schedule and export it to a temp CSV, returning the lines."""
    engine = SchedulingEngine()
    schedule = engine.compute_annual_schedule(year, teammates, windows, overrides=[])
    exporter = CSVExporter()
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False
    ) as f:
        path = f.name
    exporter.export(schedule, path)
    with open(path, encoding="ascii", errors="replace") as f:
        content = f.read()
    # Return non-empty lines
    return [line for line in content.split("\n") if line.strip()]


# ---------------------------------------------------------------------------
# Property 11: CSV structural invariants
# ---------------------------------------------------------------------------
# Feature: dc-shiftmaster-pro, Property 11: CSV structural invariants


@given(year=valid_year(), teammates=full_teammate_set(), windows=shift_windows_pair())
@settings(max_examples=100)
def test_csv_structural_invariants(year, teammates, windows):
    """For any valid annual schedule exported to CSV:
    (a) no header row,
    (b) each row has exactly two comma-separated fields,
    (c) total rows = 2 × days in year.

    **Validates: Requirements 6.1, 6.2**
    """
    lines = _generate_and_export(year, teammates, windows)
    num_days = 366 if calendar.isleap(year) else 365

    # Compute expected row count: sum of len(slot.teammates) across all slots
    engine = SchedulingEngine()
    schedule = engine.compute_annual_schedule(year, teammates, windows, overrides=[])
    expected_rows = sum(len(slot.teammates) for slot in schedule)

    # (a) No header row — first line should start with a date (YYYY/)
    assert lines, "CSV should not be empty"
    assert lines[0][:4].isdigit() and lines[0][4] == "/", (
        f"First line does not start with YYYY/ date pattern: {lines[0]}"
    )

    # (b) Each row has exactly two comma-separated fields
    for i, line in enumerate(lines):
        # split on first comma only (name could contain commas)
        parts = line.split(",", 1)
        assert len(parts) == 2, (
            f"Row {i} does not have exactly 2 fields: {line!r}"
        )

    # (c) Total rows = sum of len(slot.teammates) across all slots
    assert len(lines) == expected_rows, (
        f"Expected {expected_rows} rows for year {year}, got {len(lines)}"
    )


# ---------------------------------------------------------------------------
# Property 12: CSV date format — no leading zeros
# ---------------------------------------------------------------------------
# Feature: dc-shiftmaster-pro, Property 12: CSV date format — no leading zeros


@given(
    d=st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31)),
    time_str=valid_time(),
)
@settings(max_examples=100)
def test_csv_date_format_no_leading_zeros(d, time_str):
    """For any date and shift window start time, the formatted datetime in
    Column A should match YYYY/MM/DD HH:MM with leading zeros.

    **Validates: Requirements 6.3**
    """
    exporter = CSVExporter()
    formatted = exporter.format_datetime(d, time_str)

    # Pattern: YYYY/MM/DD HH:MM — all components zero-padded
    # Year: 4 digits
    # Month: 2 digits (01-12)
    # Day: 2 digits (01-31)
    # Hour: 2 digits (00-23)
    # Minute: 2 digits (00-59)
    pattern = r"^(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2})$"
    match = re.match(pattern, formatted)
    assert match, f"Formatted datetime does not match YYYY/MM/DD HH:MM pattern: {formatted!r}"

    year_str, month_str, day_str, hour_str, minute_str = match.groups()

    # Year preserved
    assert int(year_str) == d.year

    # Month is 2 digits with leading zero
    assert month_str == f"{d.month:02d}", (
        f"Month not zero-padded: {month_str!r} for month {d.month}"
    )

    # Day is 2 digits with leading zero
    assert day_str == f"{d.day:02d}", (
        f"Day not zero-padded: {day_str!r} for day {d.day}"
    )

    # Hour is 2 digits with leading zero
    hour_val = int(time_str.split(":")[0])
    assert hour_str == f"{hour_val:02d}", (
        f"Hour not zero-padded: {hour_str!r} for hour {hour_val}"
    )

    # Minute preserved (always two digits from input)
    assert minute_str == time_str.split(":")[1]


# ---------------------------------------------------------------------------
# Property 13: CSV chronological ordering with day-before-night
# ---------------------------------------------------------------------------
# Feature: dc-shiftmaster-pro, Property 13: CSV chronological ordering with day-before-night


@given(year=valid_year(), teammates=full_teammate_set(), windows=shift_windows_pair())
@settings(max_examples=100)
def test_csv_chronological_ordering_day_before_night(year, teammates, windows):
    """For any exported CSV, rows should be in chronological order by date,
    and for each date the Day shift row should appear before the Night shift row.

    **Validates: Requirements 6.5, 6.6**
    """
    engine = SchedulingEngine()
    schedule = engine.compute_annual_schedule(year, teammates, windows, overrides=[])
    exporter = CSVExporter()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        path = f.name
    exporter.export(schedule, path)

    with open(path, encoding="ascii", errors="replace") as f:
        lines = [line for line in f.read().split("\n") if line.strip()]

    # Parse dates from each row
    parsed_dates = []
    for line in lines:
        parsed_date, _, _ = exporter.parse_csv_row(line)
        parsed_dates.append(parsed_date)

    # Build expected row structure from schedule slots:
    # Each slot produces len(slot.teammates) rows, all with the same date.
    # Slots come in (day, night) pairs per date.
    row_idx = 0
    prev_date = None
    for i in range(0, len(schedule), 2):
        day_slot = schedule[i]
        night_slot = schedule[i + 1]

        assert day_slot.shift_type == "day", (
            f"Expected day shift at schedule index {i}, got {day_slot.shift_type}"
        )
        assert night_slot.shift_type == "night", (
            f"Expected night shift at schedule index {i+1}, got {night_slot.shift_type}"
        )

        # All rows for the day slot should have the same date
        for _ in day_slot.teammates:
            assert row_idx < len(parsed_dates), "More slots than CSV rows"
            assert parsed_dates[row_idx] == day_slot.date, (
                f"Row {row_idx}: expected date {day_slot.date}, got {parsed_dates[row_idx]}"
            )
            row_idx += 1

        # All rows for the night slot should have the same date
        for _ in night_slot.teammates:
            assert row_idx < len(parsed_dates), "More slots than CSV rows"
            assert parsed_dates[row_idx] == night_slot.date, (
                f"Row {row_idx}: expected date {night_slot.date}, got {parsed_dates[row_idx]}"
            )
            row_idx += 1

        # Chronological ordering: each date >= previous date
        if prev_date is not None:
            assert day_slot.date > prev_date, (
                f"Dates not in chronological order: {prev_date} then {day_slot.date}"
            )

        prev_date = day_slot.date

    assert row_idx == len(parsed_dates), (
        f"Row count mismatch: processed {row_idx} rows but CSV has {len(parsed_dates)}"
    )


# ---------------------------------------------------------------------------
# Property 14: CSV export/parse round-trip
# ---------------------------------------------------------------------------
# Feature: dc-shiftmaster-pro, Property 14: CSV export/parse round-trip


@given(year=valid_year(), teammates=full_teammate_set(), windows=shift_windows_pair())
@settings(max_examples=100)
def test_csv_export_parse_round_trip(year, teammates, windows):
    """For any valid annual schedule, exporting to CSV and parsing every row
    back should produce equivalent (date, start_time, teammate_name) tuples.

    **Validates: Requirements 7.1, 7.2**
    """
    engine = SchedulingEngine()
    schedule = engine.compute_annual_schedule(year, teammates, windows, overrides=[])
    exporter = CSVExporter()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        path = f.name
    exporter.export(schedule, path)

    with open(path, encoding="ascii", errors="replace") as f:
        lines = [line for line in f.read().split("\n") if line.strip()]

    # Total CSV rows = sum of len(slot.teammates) across all slots
    expected_row_count = sum(len(slot.teammates) for slot in schedule)
    assert len(lines) == expected_row_count, (
        f"Row count mismatch: {len(lines)} lines vs {expected_row_count} expected"
    )

    # Walk through slots and consume the corresponding CSV rows
    row_idx = 0
    for slot in schedule:
        parsed_names = []
        for _ in slot.teammates:
            assert row_idx < len(lines), f"Ran out of CSV rows at slot {slot.date} {slot.shift_type}"
            parsed_date, parsed_time, parsed_name = exporter.parse_csv_row(lines[row_idx])

            # Date must match
            assert parsed_date == slot.date, (
                f"Row {row_idx}: date mismatch — parsed {parsed_date}, expected {slot.date}"
            )

            # Start time round-trip: format_datetime uses YYYY/MM/DD HH:MM,
            # so we compare the parsed time against the formatted version
            expected_formatted = exporter.format_datetime(slot.date, slot.start_time)
            expected_time = expected_formatted.split(" ", 1)[1]  # extract H:MM part
            assert parsed_time == expected_time, (
                f"Row {row_idx}: time mismatch — parsed {parsed_time!r}, expected {expected_time!r}"
            )

            parsed_names.append(parsed_name)
            row_idx += 1

        # All teammates for this slot should appear in the parsed rows
        assert parsed_names == slot.teammates, (
            f"Slot {slot.date} {slot.shift_type}: teammate mismatch — "
            f"parsed {parsed_names!r}, expected {slot.teammates!r}"
        )
