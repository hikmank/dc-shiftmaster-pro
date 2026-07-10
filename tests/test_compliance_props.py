"""Property-based tests for DC-ShiftMaster Pro labor compliance validation.

Uses Hypothesis to verify correctness properties defined in the design document.
All 7 properties are tested with custom strategies and @settings(max_examples=100).
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from dc_shiftmaster.compliance import ComplianceValidator
from dc_shiftmaster.models import Override, ScheduleSlot, ShiftWindow, Teammate


# ===========================================================================
# Custom Hypothesis Strategies
# ===========================================================================


@st.composite
def valid_time(draw: st.DrawFn) -> str:
    """Generate a valid HH:MM 24-hour time string (hours 00-23, minutes 00-59)."""
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    return f"{hour:02d}:{minute:02d}"


@st.composite
def valid_time_pair(draw: st.DrawFn) -> tuple[str, str]:
    """Generate a pair of valid HH:MM times for duration testing.

    Returns:
        A tuple of (start_time, end_time) where both are valid HH:MM strings.
    """
    start = draw(valid_time())
    end = draw(valid_time())
    return (start, end)


@st.composite
def teammate_schedule(draw: st.DrawFn) -> list[tuple[date, str]]:
    """Generate a list of (date, shift_type) tuples representing a teammate's schedule.

    Produces a schedule within a 13-day window (to cover all rolling 7-day windows).
    Each entry is a unique (date, shift_type) pair.

    Returns:
        List of (date, shift_type) tuples.
    """
    start_date = draw(st.dates(min_value=date(2025, 1, 7), max_value=date(2025, 12, 25)))
    date_range = [start_date + timedelta(days=i) for i in range(13)]
    all_possible_slots = [(d, st_type) for d in date_range for st_type in ["day", "night"]]
    num_shifts = draw(st.integers(min_value=0, max_value=len(all_possible_slots)))
    schedule = draw(
        st.lists(
            st.sampled_from(all_possible_slots),
            min_size=num_shifts,
            max_size=num_shifts,
            unique=True,
        )
    )
    return schedule


@st.composite
def compliance_scenario(draw: st.DrawFn) -> dict:
    """Generate a complete validation scenario for compliance testing.

    Produces:
        - teammate_name: A non-empty alphanumeric name
        - teammate: A Teammate object with optional custom_start
        - shift_windows: Day and night ShiftWindow objects
        - schedule: List of (date, shift_type) tuples within a 13-day window
        - override_date: A date within the schedule window
        - override_shift_type: 'day' or 'night'

    Returns:
        Dict with all scenario components.
    """
    # Generate shift window times
    day_start = draw(valid_time())
    day_end = draw(valid_time().filter(lambda t: t != day_start))
    night_start = draw(valid_time())
    night_end = draw(valid_time().filter(lambda t: t != night_start))

    shift_windows = {
        "day": ShiftWindow(shift_type="day", start_time=day_start, end_time=day_end),
        "night": ShiftWindow(shift_type="night", start_time=night_start, end_time=night_end),
    }

    # Generate a teammate with optional custom_start
    custom_start = draw(st.one_of(st.just(""), valid_time()))
    teammate_name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=2,
            max_size=10,
        )
    )
    teammate = Teammate(id=1, name=teammate_name, shift_type="FHD", custom_start=custom_start)

    # Generate a date range and schedule
    start_date = draw(st.dates(min_value=date(2025, 1, 7), max_value=date(2025, 12, 25)))
    date_range = [start_date + timedelta(days=i) for i in range(13)]
    all_possible_slots = [(d, st_type) for d in date_range for st_type in ["day", "night"]]
    num_shifts = draw(st.integers(min_value=0, max_value=len(all_possible_slots)))
    schedule = draw(
        st.lists(
            st.sampled_from(all_possible_slots),
            min_size=num_shifts,
            max_size=num_shifts,
            unique=True,
        )
    )

    # Override date is within the date range (middle portion for full window coverage)
    override_date = draw(st.sampled_from(date_range[6:]))
    override_shift_type = draw(st.sampled_from(["day", "night"]))

    return {
        "teammate_name": teammate_name,
        "teammate": teammate,
        "shift_windows": shift_windows,
        "schedule": schedule,
        "override_date": override_date,
        "override_shift_type": override_shift_type,
        "date_range": date_range,
    }


@st.composite
def schedule_resolution_scenario(draw: st.DrawFn):
    """Generate a scenario for testing schedule resolution with overrides.

    Produces:
        - A teammate name
        - A date range (7 consecutive days)
        - Shift windows
        - A list of overrides that either assign the teammate or replace them
    """
    # Generate a teammate name (simple alphanumeric)
    teammate_name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=2,
            max_size=10,
        )
    )

    # Generate a different name for replacement overrides
    other_name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=2,
            max_size=10,
        ).filter(lambda n: n != teammate_name)
    )

    # Generate a start date in 2025
    start_date = draw(st.dates(min_value=date(2025, 1, 1), max_value=date(2025, 12, 25)))
    date_range = [start_date + timedelta(days=i) for i in range(7)]

    # Shift windows with fixed times for determinism
    shift_windows = {
        "day": ShiftWindow(shift_type="day", start_time="06:00", end_time="18:00"),
        "night": ShiftWindow(shift_type="night", start_time="18:00", end_time="06:00"),
    }

    # Generate overrides: each override targets a random date in the range
    # and a random shift type, and either assigns the teammate or replaces them
    num_overrides = draw(st.integers(min_value=0, max_value=7))
    overrides = []
    override_keys_used = set()  # Track (date, shift_type) to avoid duplicates

    for _ in range(num_overrides):
        override_date = draw(st.sampled_from(date_range))
        override_shift_type = draw(st.sampled_from(["day", "night"]))
        override_key = (override_date.isoformat(), override_shift_type)

        # Skip duplicate keys (only one override per slot)
        if override_key in override_keys_used:
            continue
        override_keys_used.add(override_key)

        # Decide: assign the teammate, replace with other name, or replace with "nobody"
        action = draw(st.sampled_from(["assign", "replace_other", "replace_nobody"]))
        if action == "assign":
            override_name = teammate_name
        elif action == "replace_other":
            override_name = other_name
        else:
            override_name = "nobody"

        overrides.append(
            Override(
                date=override_date.isoformat(),
                shift_type=override_shift_type,
                name=override_name,
            )
        )

    return {
        "teammate_name": teammate_name,
        "date_range": date_range,
        "shift_windows": shift_windows,
        "overrides": overrides,
        "other_name": other_name,
    }


@st.composite
def weekly_hours_scenario(draw: st.DrawFn):
    """Generate a scenario for testing weekly hours violation detection.

    Produces:
        - A teammate with optional custom_start
        - Shift windows with valid start/end times
        - A schedule of (date, shift_type) tuples within a 7-day window
        - An override_date within the window
    """
    # Generate shift window times (ensuring non-zero durations for meaningful tests)
    day_start = draw(valid_time())
    day_end = draw(valid_time().filter(lambda t: t != day_start))
    night_start = draw(valid_time())
    night_end = draw(valid_time().filter(lambda t: t != night_start))

    shift_windows = {
        "day": ShiftWindow(shift_type="day", start_time=day_start, end_time=day_end),
        "night": ShiftWindow(shift_type="night", start_time=night_start, end_time=night_end),
    }

    # Generate a teammate with optional custom_start
    custom_start = draw(st.one_of(st.just(""), valid_time()))
    teammate_name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=2,
            max_size=10,
        )
    )
    teammate = Teammate(id=1, name=teammate_name, shift_type="FHD", custom_start=custom_start)

    # Generate a start date for the 7-day window
    start_date = draw(st.dates(min_value=date(2025, 1, 7), max_value=date(2025, 12, 25)))
    date_range = [start_date + timedelta(days=i) for i in range(7)]

    # Generate a schedule: random subset of (date, shift_type) pairs within the window
    all_possible_slots = [(d, st_type) for d in date_range for st_type in ["day", "night"]]
    # Draw a random subset (0 to all 14 possible slots)
    num_shifts = draw(st.integers(min_value=0, max_value=len(all_possible_slots)))
    schedule = draw(
        st.lists(
            st.sampled_from(all_possible_slots),
            min_size=num_shifts,
            max_size=num_shifts,
            unique=True,
        )
    )

    # The override_date is one of the dates in the window
    override_date = draw(st.sampled_from(date_range))

    return {
        "teammate_name": teammate_name,
        "teammate": teammate,
        "shift_windows": shift_windows,
        "schedule": schedule,
        "override_date": override_date,
        "date_range": date_range,
    }


@st.composite
def weekly_days_scenario(draw: st.DrawFn):
    """Generate a scenario for testing weekly days violation detection.

    Produces:
        - A schedule of (date, shift_type) tuples within a date range
        - An override_date within the range
    """
    # Generate a start date in 2025 (leave room for 7-day windows)
    start_date = draw(st.dates(min_value=date(2025, 1, 7), max_value=date(2025, 12, 25)))
    # Use a 13-day range to cover all possible 7-day windows around the override_date
    date_range = [start_date + timedelta(days=i) for i in range(13)]

    # Generate a schedule: random subset of (date, shift_type) pairs within the range
    all_possible_slots = [(d, st_type) for d in date_range for st_type in ["day", "night"]]
    num_shifts = draw(st.integers(min_value=0, max_value=len(all_possible_slots)))
    schedule = draw(
        st.lists(
            st.sampled_from(all_possible_slots),
            min_size=num_shifts,
            max_size=num_shifts,
            unique=True,
        )
    )

    # The override_date is one of the dates in the middle of the range
    # (offset 6 ensures all 7 windows fit within the date_range)
    override_date = draw(st.sampled_from(date_range[6:]))

    return {
        "schedule": schedule,
        "override_date": override_date,
    }


@st.composite
def daily_hours_scenario(draw: st.DrawFn):
    """Generate a scenario for testing daily hours violation detection.

    Produces:
        - A teammate with optional custom_start
        - Shift windows with valid start/end times (non-zero durations)
        - A schedule of (date, shift_type) tuples on the override_date (1 or 2 shifts)
        - An override_date
    """
    # Generate shift window times (ensuring non-zero durations for meaningful tests)
    day_start = draw(valid_time())
    day_end = draw(valid_time().filter(lambda t: t != day_start))
    night_start = draw(valid_time())
    night_end = draw(valid_time().filter(lambda t: t != night_start))

    shift_windows = {
        "day": ShiftWindow(shift_type="day", start_time=day_start, end_time=day_end),
        "night": ShiftWindow(shift_type="night", start_time=night_start, end_time=night_end),
    }

    # Generate a teammate with optional custom_start
    custom_start = draw(st.one_of(st.just(""), valid_time()))
    teammate_name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=2,
            max_size=10,
        )
    )
    teammate = Teammate(id=1, name=teammate_name, shift_type="FHD", custom_start=custom_start)

    # Generate the override date
    override_date = draw(st.dates(min_value=date(2025, 1, 1), max_value=date(2025, 12, 31)))

    # Generate a schedule on the override_date: 1 or 2 shifts of type 'day' and/or 'night'
    num_shifts = draw(st.integers(min_value=1, max_value=2))
    if num_shifts == 1:
        shift_type = draw(st.sampled_from(["day", "night"]))
        schedule = [(override_date, shift_type)]
    else:
        # 2 shifts: both day and night on the same date
        schedule = [(override_date, "day"), (override_date, "night")]

    return {
        "teammate_name": teammate_name,
        "teammate": teammate,
        "shift_windows": shift_windows,
        "schedule": schedule,
        "override_date": override_date,
    }


@st.composite
def override_request_with_acknowledgment(draw: st.DrawFn):
    """Generate a random override request with acknowledge_violations=True.

    Produces:
        - date: A valid YYYY-MM-DD date string in 2025
        - shift_type: 'day' or 'night'
        - name: A non-empty alphanumeric teammate name
    """
    # Generate a date in 2025
    d = draw(st.dates(min_value=date(2025, 1, 1), max_value=date(2025, 12, 31)))
    date_str = d.isoformat()

    # Generate shift type
    shift_type = draw(st.sampled_from(["day", "night"]))

    # Generate a non-empty teammate name (alphanumeric)
    name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=20,
        )
    )

    return {
        "date": date_str,
        "shift_type": shift_type,
        "name": name,
    }


# ===========================================================================
# Helper Classes
# ===========================================================================


class MockSchedulingEngine:
    """A deterministic mock SchedulingEngine for testing schedule resolution.

    Returns a fixed base schedule where the target teammate is assigned to
    every day and night shift in the date range (simulating a simple rotation).
    """

    def __init__(self, teammate_name: str, date_range: list[date], shift_windows: dict):
        self._teammate_name = teammate_name
        self._date_range = date_range
        self._shift_windows = shift_windows

    def compute_annual_schedule(
        self,
        year: int,
        teammates: list,
        shift_windows: dict,
        overrides: list,
    ) -> list[ScheduleSlot]:
        """Return a deterministic schedule: teammate assigned to all shifts."""
        slots = []
        for d in self._date_range:
            for shift_type in ["day", "night"]:
                sw = self._shift_windows.get(shift_type)
                start_time = sw.start_time if sw else "06:00"
                slots.append(
                    ScheduleSlot(
                        date=d,
                        shift_type=shift_type,
                        start_time=start_time,
                        teammates=[self._teammate_name],
                        is_override=False,
                    )
                )
        return slots


# ===========================================================================
# Property Tests (Properties 1-7)
# ===========================================================================


# Feature: labor-compliance-validation, Property 1: Shift duration calculation correctness
# **Validates: Requirements 1.2, 3.2, 4.3, 4.4**
@settings(max_examples=100)
@given(time_pair=valid_time_pair())
def test_shift_duration_calculation_correctness(time_pair: tuple[str, str]):
    """Property 1: Shift duration calculation correctness.

    For any pair of valid HH:MM times (effective_start, shift_end), the computed
    shift duration SHALL equal (shift_end - effective_start) in hours when
    shift_end >= effective_start, and (shift_end - effective_start + 24) in hours
    when shift_end < effective_start (overnight shift). When effective_start equals
    shift_end, the duration SHALL be 0.

    **Validates: Requirements 1.2, 3.2, 4.3, 4.4**
    """
    effective_start, shift_end = time_pair
    validator = ComplianceValidator()
    result = validator.compute_shift_duration(effective_start, shift_end)

    # Parse times into total minutes
    start_h, start_m = int(effective_start[:2]), int(effective_start[3:])
    end_h, end_m = int(shift_end[:2]), int(shift_end[3:])
    start_total = start_h * 60 + start_m
    end_total = end_h * 60 + end_m

    if effective_start == shift_end:
        # When start equals end, duration is 0
        assert result == 0.0, (
            f"Expected 0.0 when start == end, got {result} "
            f"for start={effective_start}, end={shift_end}"
        )
    elif end_total >= start_total:
        # Normal shift: duration = (end - start) in hours
        expected = (end_total - start_total) / 60.0
        assert result == expected, (
            f"Expected {expected}h for normal shift, got {result}h "
            f"(start={effective_start}, end={shift_end})"
        )
    else:
        # Overnight shift: duration = (end - start + 24h) in hours
        expected = (end_total - start_total + 1440) / 60.0
        assert result == expected, (
            f"Expected {expected}h for overnight shift, got {result}h "
            f"(start={effective_start}, end={shift_end})"
        )

    # Duration must always be non-negative
    assert result >= 0.0, f"Duration must be non-negative, got {result}"

    # Duration must be less than 24 hours (max possible is 23h59m)
    assert result < 24.0, f"Duration must be < 24h, got {result}"


# Feature: labor-compliance-validation, Property 2: Effective start time resolution
# **Validates: Requirements 4.1, 4.2**
@settings(max_examples=100)
@given(
    teammate_name=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=30,
    ),
    custom_start=st.one_of(st.just(""), valid_time()),
    shift_type=st.sampled_from(["day", "night"]),
    default_start=valid_time(),
)
def test_effective_start_time_resolution(
    teammate_name: str,
    custom_start: str,
    shift_type: str,
    default_start: str,
):
    """Property 2: Effective start time resolution.

    For any teammate and shift type, the effective start time SHALL equal the
    teammate's custom_start value when it is non-empty, and SHALL equal the
    shift window's default start time when custom_start is empty. The resolved
    effective start time must always be a valid HH:MM string.

    **Validates: Requirements 4.1, 4.2**
    """
    # Arrange
    validator = ComplianceValidator()

    teammate = Teammate(id=1, name=teammate_name, shift_type="FHD", custom_start=custom_start)
    teammates = [teammate]

    shift_windows = {
        "day": ShiftWindow(shift_type="day", start_time=default_start, end_time="18:30"),
        "night": ShiftWindow(shift_type="night", start_time=default_start, end_time="06:30"),
    }

    # Act
    result = validator.get_effective_start(
        teammate_name=teammate_name,
        shift_type=shift_type,
        teammates=teammates,
        shift_windows=shift_windows,
    )

    # Assert: when custom_start is non-empty, result equals custom_start
    if custom_start:
        assert result == custom_start, (
            f"Expected custom_start '{custom_start}' but got '{result}'"
        )
    else:
        # When custom_start is empty, result equals shift window's default start_time
        assert result == default_start, (
            f"Expected default start '{default_start}' but got '{result}'"
        )

    # Assert: the resolved effective start time is always a valid HH:MM string
    assert re.match(r"^\d{2}:\d{2}$", result), (
        f"Result '{result}' is not a valid HH:MM format"
    )
    hours, minutes = result.split(":")
    assert 0 <= int(hours) <= 23, f"Hours {hours} out of range"
    assert 0 <= int(minutes) <= 59, f"Minutes {minutes} out of range"


# Feature: labor-compliance-validation, Property 3: Weekly hours violation if and only if exceeds 60
# **Validates: Requirements 1.1, 1.3, 1.4**
@settings(max_examples=100)
@given(scenario=weekly_hours_scenario())
def test_weekly_hours_violation_iff_exceeds_60(scenario):
    """Property 3: Weekly hours violation if and only if exceeds 60.

    For any teammate schedule and proposed override, the Compliance_Validator
    SHALL return a weekly_hours violation for a rolling window if and only if
    the sum of shift durations for that teammate within that 7-day window
    exceeds 60 hours. The projected value in the violation SHALL equal the
    computed total hours for that window.

    **Validates: Requirements 1.1, 1.3, 1.4**
    """
    teammate_name = scenario["teammate_name"]
    teammate = scenario["teammate"]
    shift_windows = scenario["shift_windows"]
    schedule = scenario["schedule"]
    override_date = scenario["override_date"]

    validator = ComplianceValidator()
    teammates = [teammate]

    # Act: call check_weekly_hours
    violations = validator.check_weekly_hours(
        teammate_name=teammate_name,
        override_date=override_date,
        schedule_with_override=schedule,
        shift_windows=shift_windows,
        teammates=teammates,
    )

    # Build a set of violating windows from the result
    violation_windows = set()
    for v in violations:
        assert v.rule == "weekly_hours", f"Expected rule 'weekly_hours', got '{v.rule}'"
        assert v.limit == 60.0, f"Expected limit 60.0, got {v.limit}"
        violation_windows.add((v.window_start, v.window_end))

    # Independently compute expected violations for each of the 7 rolling windows
    for offset in range(7):
        window_start = override_date - timedelta(days=6 - offset)
        window_end = window_start + timedelta(days=6)

        # Sum shift durations for shifts within this window
        total_hours = 0.0
        for shift_date, shift_type in schedule:
            if window_start <= shift_date <= window_end:
                effective_start = validator.get_effective_start(
                    teammate_name, shift_type, teammates, shift_windows
                )
                end_time = shift_windows[shift_type].end_time
                total_hours += validator.compute_shift_duration(effective_start, end_time)

        window_key = (window_start.isoformat(), window_end.isoformat())

        if total_hours > 60.0:
            # A violation MUST exist for this window
            assert window_key in violation_windows, (
                f"Expected a weekly_hours violation for window "
                f"{window_start} to {window_end} (total={total_hours}h > 60h) "
                f"but none was returned"
            )
            # The projected value must equal the computed total
            matching = [
                v for v in violations
                if v.window_start == window_key[0] and v.window_end == window_key[1]
            ]
            assert len(matching) == 1, (
                f"Expected exactly 1 violation for window {window_key}, got {len(matching)}"
            )
            assert matching[0].projected == total_hours, (
                f"Expected projected={total_hours} for window {window_key}, "
                f"got {matching[0].projected}"
            )
        else:
            # No violation should exist for this window
            assert window_key not in violation_windows, (
                f"Unexpected weekly_hours violation for window "
                f"{window_start} to {window_end} (total={total_hours}h <= 60h)"
            )


# Feature: labor-compliance-validation, Property 4: Weekly days violation if and only if exceeds 6
# **Validates: Requirements 2.1, 2.2, 2.3**
@settings(max_examples=100)
@given(scenario=weekly_days_scenario())
def test_weekly_days_violation_iff_exceeds_6(scenario):
    """Property 4: Weekly days violation if and only if exceeds 6.

    For any teammate schedule and proposed override, the Compliance_Validator
    SHALL return a weekly_days violation for a rolling window if and only if
    the count of distinct calendar dates on which the teammate is scheduled to
    work within that 7-day window exceeds 6. The projected value SHALL equal
    the day count for that window.

    **Validates: Requirements 2.1, 2.2, 2.3**
    """
    schedule = scenario["schedule"]
    override_date = scenario["override_date"]

    validator = ComplianceValidator()

    # Act: call check_weekly_days
    violations = validator.check_weekly_days(
        override_date=override_date,
        schedule_with_override=schedule,
    )

    # Build a set of violating windows from the result
    violation_windows = set()
    for v in violations:
        assert v.rule == "weekly_days", f"Expected rule 'weekly_days', got '{v.rule}'"
        assert v.limit == 6, f"Expected limit 6, got {v.limit}"
        violation_windows.add((v.window_start, v.window_end))

    # Independently compute expected violations for each of the 7 rolling windows
    for offset in range(7):
        window_start = override_date - timedelta(days=6 - offset)
        window_end = window_start + timedelta(days=6)

        # Count distinct calendar dates with at least one shift in this window
        distinct_dates: set[date] = set()
        for shift_date, shift_type in schedule:
            if window_start <= shift_date <= window_end:
                distinct_dates.add(shift_date)

        day_count = len(distinct_dates)
        window_key = (window_start.isoformat(), window_end.isoformat())

        if day_count > 6:
            # A violation MUST exist for this window
            assert window_key in violation_windows, (
                f"Expected a weekly_days violation for window "
                f"{window_start} to {window_end} (day_count={day_count} > 6) "
                f"but none was returned"
            )
            # The projected value must equal the day count
            matching = [
                v for v in violations
                if v.window_start == window_key[0] and v.window_end == window_key[1]
            ]
            assert len(matching) == 1, (
                f"Expected exactly 1 violation for window {window_key}, got {len(matching)}"
            )
            assert matching[0].projected == day_count, (
                f"Expected projected={day_count} for window {window_key}, "
                f"got {matching[0].projected}"
            )
        else:
            # No violation should exist for this window
            assert window_key not in violation_windows, (
                f"Unexpected weekly_days violation for window "
                f"{window_start} to {window_end} (day_count={day_count} <= 6)"
            )


# Feature: labor-compliance-validation, Property 5: Daily hours violation if and only if exceeds 12
# **Validates: Requirements 3.1, 3.3, 3.4, 3.5**
@settings(max_examples=100)
@given(scenario=daily_hours_scenario())
def test_daily_hours_violation_iff_exceeds_12(scenario):
    """Property 5: Daily hours violation if and only if exceeds 12.

    For any teammate schedule and proposed override, the Compliance_Validator
    SHALL return a daily_hours violation if and only if the sum of all shift
    durations assigned to the teammate on the override date exceeds 12 hours.
    When the proposed override assigns the same teammate already in the slot,
    the duration SHALL NOT be double-counted.

    **Validates: Requirements 3.1, 3.3, 3.4, 3.5**
    """
    teammate_name = scenario["teammate_name"]
    teammate = scenario["teammate"]
    shift_windows = scenario["shift_windows"]
    schedule = scenario["schedule"]
    override_date = scenario["override_date"]

    validator = ComplianceValidator()
    teammates = [teammate]

    # Act: call check_daily_hours
    violations = validator.check_daily_hours(
        teammate_name=teammate_name,
        override_date=override_date,
        schedule_with_override=schedule,
        shift_windows=shift_windows,
        teammates=teammates,
    )

    # Independently compute expected total hours on the override_date
    total_hours = 0.0
    for shift_date, shift_type in schedule:
        if shift_date == override_date:
            effective_start = validator.get_effective_start(
                teammate_name, shift_type, teammates, shift_windows
            )
            end_time = shift_windows[shift_type].end_time
            total_hours += validator.compute_shift_duration(effective_start, end_time)

    # Assert: violation IFF total_hours > 12
    if total_hours > 12.0:
        # A violation MUST exist
        assert len(violations) == 1, (
            f"Expected exactly 1 daily_hours violation when total={total_hours}h > 12h, "
            f"but got {len(violations)} violations"
        )
        v = violations[0]
        assert v.rule == "daily_hours", f"Expected rule 'daily_hours', got '{v.rule}'"
        assert v.limit == 12.0, f"Expected limit 12.0, got {v.limit}"
        assert v.projected == total_hours, (
            f"Expected projected={total_hours}, got {v.projected}"
        )
        assert v.window_start is None, (
            f"Expected window_start=None for daily violation, got {v.window_start}"
        )
        assert v.window_end is None, (
            f"Expected window_end=None for daily violation, got {v.window_end}"
        )
    else:
        # No violation should exist
        assert len(violations) == 0, (
            f"Expected no daily_hours violation when total={total_hours}h <= 12h, "
            f"but got {len(violations)} violations"
        )


# Feature: labor-compliance-validation, Property 6: Schedule resolution includes and excludes overrides correctly
# **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
@settings(max_examples=100)
@given(scenario=schedule_resolution_scenario())
def test_schedule_resolution_includes_and_excludes_overrides(scenario):
    """Property 6: Schedule resolution includes and excludes overrides correctly.

    For any teammate and set of existing overrides within the rolling window,
    the resolved projected schedule SHALL include shifts where an existing
    override assigns the teammate by name, SHALL exclude shifts where an
    existing override replaces the teammate with a different name or "nobody",
    and SHALL count a date as a scheduled day if and only if the teammate
    retains at least one shift assignment on that date after all existing
    overrides are applied.

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """
    teammate_name = scenario["teammate_name"]
    date_range = scenario["date_range"]
    shift_windows = scenario["shift_windows"]
    overrides = scenario["overrides"]

    # Create a teammate record (no custom_start for simplicity)
    teammate = Teammate(id=1, name=teammate_name, shift_type="FHD", custom_start="")
    teammates = [teammate]

    # Create mock scheduling engine that assigns the teammate to all shifts
    mock_engine = MockSchedulingEngine(teammate_name, date_range, shift_windows)

    validator = ComplianceValidator()
    year = date_range[0].year

    # Act: resolve the schedule
    resolved = validator.resolve_teammate_schedule(
        teammate_name=teammate_name,
        date_range=date_range,
        shift_windows=shift_windows,
        teammates=teammates,
        existing_overrides=overrides,
        scheduling_engine=mock_engine,
        year=year,
    )

    # Build override lookup for verification
    override_map = {}
    for o in overrides:
        override_map[(o.date, o.shift_type)] = o.name

    # Assert Property 6 conditions:

    # 1. Overrides assigning the teammate ARE included in the resolved schedule
    for o in overrides:
        if o.name == teammate_name:
            o_date = date.fromisoformat(o.date)
            assert (o_date, o.shift_type) in resolved, (
                f"Override assigning '{teammate_name}' on {o.date} {o.shift_type} "
                f"should be INCLUDED in resolved schedule but was not found"
            )

    # 2. Overrides replacing the teammate with another name or "nobody" ARE excluded
    for o in overrides:
        if o.name != teammate_name:
            o_date = date.fromisoformat(o.date)
            assert (o_date, o.shift_type) not in resolved, (
                f"Override replacing '{teammate_name}' with '{o.name}' on {o.date} "
                f"{o.shift_type} should be EXCLUDED from resolved schedule but was found"
            )

    # 3. A date is a scheduled day iff the teammate retains at least one shift on that date
    for d in date_range:
        date_shifts_in_resolved = [(rd, rs) for (rd, rs) in resolved if rd == d]
        has_shift_on_date = len(date_shifts_in_resolved) > 0

        # Compute expected: for each shift_type, check if teammate should be assigned
        expected_shifts_on_date = 0
        for shift_type in ["day", "night"]:
            key = (d.isoformat(), shift_type)
            if key in override_map:
                # Override exists: teammate is assigned only if override name matches
                override_names = [
                    n.strip() for n in override_map[key].split(",") if n.strip()
                ]
                if not override_names:
                    override_names = ["nobody"]
                if teammate_name in override_names:
                    expected_shifts_on_date += 1
            else:
                # No override: base schedule assigns the teammate (mock always assigns)
                expected_shifts_on_date += 1

        expected_has_shift = expected_shifts_on_date > 0

        assert has_shift_on_date == expected_has_shift, (
            f"Date {d}: expected teammate to {'have' if expected_has_shift else 'not have'} "
            f"shifts, but resolved schedule shows "
            f"{'shifts present' if has_shift_on_date else 'no shifts'}. "
            f"Overrides on this date: "
            f"{[(k, v) for k, v in override_map.items() if k[0] == d.isoformat()]}"
        )


# Feature: labor-compliance-validation, Property 7: Acknowledged override always persists
# **Validates: Requirements 6.2**
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(override_data=override_request_with_acknowledgment())
def test_acknowledged_override_always_persists(tmp_path_factory, override_data):
    """Property 7: Acknowledged override always persists.

    For any override request submitted with acknowledge_violations set to true,
    the override SHALL be applied and persisted regardless of whether compliance
    violations exist. The resulting schedule SHALL reflect the overridden assignment.

    **Validates: Requirements 6.2**
    """
    from dc_shiftmaster_html.server import create_app

    # Create a fresh app with a temp database for each test iteration
    tmp_path = tmp_path_factory.mktemp("prop7")
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    with app.test_client() as client:
        # Act: POST override with acknowledge_violations=True
        payload = {
            "date": override_data["date"],
            "shift_type": override_data["shift_type"],
            "name": override_data["name"],
            "acknowledge_violations": True,
        }
        resp = client.post("/api/overrides", json=payload)

        # Assert: response is always 201 (never 422 or other error)
        assert resp.status_code == 201, (
            f"Expected 201 for acknowledged override, got {resp.status_code}. "
            f"Response: {resp.get_json()}. "
            f"Payload: {payload}"
        )

        # Assert: response body confirms the override was applied
        resp_data = resp.get_json()
        assert resp_data["date"] == override_data["date"]
        assert resp_data["shift_type"] == override_data["shift_type"]
        assert resp_data["name"] == override_data["name"]
        assert resp_data.get("acknowledged_violations") is True

        # Assert: the override is persisted (GET /api/overrides/{year} returns it)
        year = int(override_data["date"][:4])
        get_resp = client.get(f"/api/overrides/{year}")
        assert get_resp.status_code == 200

        overrides_list = get_resp.get_json()
        # Find our override in the list
        matching = [
            o for o in overrides_list
            if o["date"] == override_data["date"]
            and o["shift_type"] == override_data["shift_type"]
            and o["name"] == override_data["name"]
        ]
        assert len(matching) == 1, (
            f"Expected override to be persisted but not found in GET response. "
            f"Looking for date={override_data['date']}, "
            f"shift_type={override_data['shift_type']}, "
            f"name={override_data['name']}. "
            f"Got overrides: {overrides_list}"
        )
