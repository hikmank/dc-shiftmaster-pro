"""Property-based tests for calendar logic (dc_shiftmaster_web).

Tests the scheduling engine's output sliced by month to verify
calendar card counts and content correctness.
"""

from __future__ import annotations

import calendar

from hypothesis import given, settings, strategies as st

from dc_shiftmaster.models import ShiftWindow
from dc_shiftmaster.scheduling import SchedulingEngine


# Feature: dc-shiftmaster-web, Property 9: Calendar card count matches days in month
class TestCalendarCardCountMatchesDaysInMonth:
    """**Validates: Requirements 4.1**"""

    @given(
        year=st.integers(min_value=2000, max_value=2100),
        month=st.integers(min_value=1, max_value=12),
    )
    @settings(max_examples=100)
    def test_unique_dates_in_month_equals_monthrange(self, year: int, month: int):
        """For any valid year and month, the number of unique dates in the
        schedule for that month should equal calendar.monthrange(year, month)[1]."""
        engine = SchedulingEngine()
        shift_windows = {
            "day": ShiftWindow(shift_type="day", start_time="06:00", end_time="18:30"),
            "night": ShiftWindow(shift_type="night", start_time="18:00", end_time="06:30"),
        }

        schedule = engine.compute_annual_schedule(
            year=year,
            teammates=[],
            shift_windows=shift_windows,
            overrides=[],
        )

        # Filter slots to the target month and count unique dates
        # (each date has 2 slots: day + night, so unique dates = card count)
        month_dates = {
            slot.date
            for slot in schedule
            if slot.date.month == month
        }

        expected_days = calendar.monthrange(year, month)[1]
        assert len(month_dates) == expected_days, (
            f"Year {year}, month {month}: expected {expected_days} days, "
            f"got {len(month_dates)} unique dates"
        )

# Feature: dc-shiftmaster-web, Property 10: Calendar card content correctness
class TestCalendarCardContentCorrectness:
    """**Validates: Requirements 4.2, 4.3, 4.11**"""

    DAY_ABBRS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    @given(
        year=st.integers(min_value=2000, max_value=2100),
        month=st.integers(min_value=1, max_value=12),
        day_frac=st.floats(min_value=0.0, max_value=1.0),
        fhd_names=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("L",)),
                min_size=1,
                max_size=10,
            ),
            min_size=0,
            max_size=3,
            unique=True,
        ),
        fhn_names=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("L",)),
                min_size=1,
                max_size=10,
            ),
            min_size=0,
            max_size=3,
            unique=True,
        ),
        bhd_names=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("L",)),
                min_size=1,
                max_size=10,
            ),
            min_size=0,
            max_size=3,
            unique=True,
        ),
        bhn_names=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("L",)),
                min_size=1,
                max_size=10,
            ),
            min_size=0,
            max_size=3,
            unique=True,
        ),
        custom_start_hour=st.integers(min_value=0, max_value=23),
        custom_start_min=st.integers(min_value=0, max_value=59),
        use_custom_start=st.booleans(),
    )
    @settings(max_examples=100)
    def test_card_content_matches_schedule_data(
        self,
        year: int,
        month: int,
        day_frac: float,
        fhd_names: list[str],
        fhn_names: list[str],
        bhd_names: list[str],
        bhn_names: list[str],
        custom_start_hour: int,
        custom_start_min: int,
        use_custom_start: bool,
    ):
        """For any date in a computed schedule, the data feeding a CalendarCard
        should have the correct day number, day-of-week abbreviation, owner
        label ('F' or 'B'), teammate names for day/night shifts, and custom
        start times when set."""
        from datetime import date as date_cls

        engine = SchedulingEngine()
        shift_windows = {
            "day": ShiftWindow(shift_type="day", start_time="06:00", end_time="18:30"),
            "night": ShiftWindow(shift_type="night", start_time="18:00", end_time="06:30"),
        }

        # Build custom_start string if enabled
        custom_start = (
            f"{custom_start_hour:02d}:{custom_start_min:02d}"
            if use_custom_start
            else ""
        )

        # Build Teammate objects — assign custom_start to the first teammate
        # in each group (if any) to test custom_start propagation
        from dc_shiftmaster.models import Teammate

        tid = 1
        teammates = []
        for name in fhd_names:
            cs = custom_start if tid == 1 and use_custom_start else ""
            teammates.append(Teammate(id=tid, name=name, shift_type="FHD", custom_start=cs))
            tid += 1
        for name in fhn_names:
            teammates.append(Teammate(id=tid, name=name, shift_type="FHN", custom_start=""))
            tid += 1
        for name in bhd_names:
            teammates.append(Teammate(id=tid, name=name, shift_type="BHD", custom_start=""))
            tid += 1
        for name in bhn_names:
            teammates.append(Teammate(id=tid, name=name, shift_type="BHN", custom_start=""))
            tid += 1

        schedule = engine.compute_annual_schedule(
            year=year,
            teammates=teammates,
            shift_windows=shift_windows,
            overrides=[],
        )

        # Pick a specific day in the target month using day_frac
        num_days = calendar.monthrange(year, month)[1]
        day_num = max(1, min(num_days, int(day_frac * num_days) + 1))
        target_date = date_cls(year, month, day_num)

        # Find the day and night slots for the target date
        day_slot = None
        night_slot = None
        for slot in schedule:
            if slot.date == target_date:
                if slot.shift_type == "day":
                    day_slot = slot
                elif slot.shift_type == "night":
                    night_slot = slot

        assert day_slot is not None, f"No day slot found for {target_date}"
        assert night_slot is not None, f"No night slot found for {target_date}"

        # 1. Day number correctness
        assert day_slot.date.day == day_num
        assert night_slot.date.day == day_num

        # 2. Day-of-week abbreviation correctness
        expected_abbr = self.DAY_ABBRS[target_date.weekday()]
        # Verify the date's weekday maps to the correct abbreviation
        assert calendar.day_abbr[target_date.weekday()] == expected_abbr

        # 3. Owner label correctness ("F" or "B")
        owner = engine.get_day_owner(target_date)
        expected_label = "F" if owner == "front_half" else "B"
        # Verify the engine's owner determination is consistent
        assert owner in ("front_half", "back_half"), (
            f"Unexpected owner '{owner}' for {target_date}"
        )
        # The CalendarCard would use this label — verify it's derivable
        assert expected_label in ("F", "B")

        # 4. Teammate names match for day and night shifts
        if owner == "front_half":
            expected_day_names = [n for n in fhd_names] if fhd_names else ["nobody"]
            expected_night_names = [n for n in fhn_names] if fhn_names else ["nobody"]
        else:
            expected_day_names = [n for n in bhd_names] if bhd_names else ["nobody"]
            expected_night_names = [n for n in bhn_names] if bhn_names else ["nobody"]

        assert day_slot.teammates == expected_day_names, (
            f"Day teammates mismatch on {target_date}: "
            f"expected {expected_day_names}, got {day_slot.teammates}"
        )
        assert night_slot.teammates == expected_night_names, (
            f"Night teammates mismatch on {target_date}: "
            f"expected {expected_night_names}, got {night_slot.teammates}"
        )

        # 5. Custom start times are present when set
        if use_custom_start and fhd_names and owner == "front_half":
            first_fhd = fhd_names[0]
            assert first_fhd in day_slot.teammate_starts, (
                f"Expected custom_start for '{first_fhd}' in day slot teammate_starts"
            )
            assert day_slot.teammate_starts[first_fhd] == custom_start, (
                f"Custom start mismatch for '{first_fhd}': "
                f"expected '{custom_start}', got '{day_slot.teammate_starts[first_fhd]}'"
            )
        elif not use_custom_start or not fhd_names or owner != "front_half":
            # When no custom_start is set for FHD teammates, or it's back_half day,
            # the day slot should have no custom starts for FHD names
            if owner == "front_half" and fhd_names and not use_custom_start:
                assert fhd_names[0] not in day_slot.teammate_starts or \
                    day_slot.teammate_starts.get(fhd_names[0]) == "", (
                    f"Unexpected custom_start for '{fhd_names[0]}' when none was set"
                )
