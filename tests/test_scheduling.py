"""Property-based tests for SchedulingEngine (Properties 6 and 7).

Uses Hypothesis to verify the weekday-based ownership logic and
shift-type teammate assignment across many random inputs.
"""

from datetime import date, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from dc_shiftmaster.models import Teammate, ShiftWindow, ScheduleSlot
from dc_shiftmaster.scheduling import (
    SchedulingEngine,
    FRONT_HALF_WEEKDAYS,
    BACK_HALF_WEEKDAYS,
    WEDNESDAY,
    CYCLE_LENGTH,
)

from tests.conftest import valid_year, valid_teammate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_engine = SchedulingEngine()

_default_shift_windows = {
    "day": ShiftWindow(shift_type="day", start_time="06:00", end_time="18:30"),
    "night": ShiftWindow(shift_type="night", start_time="18:00", end_time="06:30"),
}


# ---------------------------------------------------------------------------
# Property 6: Weekday-based ownership correctness
# Feature: dc-shiftmaster-pro, Property 6: 14-day cycle ownership correctness
# Validates: Requirements 3.1, 3.2, 3.3, 3.4
# ---------------------------------------------------------------------------


@given(year=valid_year())
@settings(max_examples=100)
def test_cycle_day_determines_owner(year: int):
    """For any year and any date within that year, the weekday should
    determine the owner: Sun/Mon/Tue → front_half, Thu/Fri/Sat → back_half,
    Wed → alternates based on 14-day cycle position.

    **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
    """
    jan1 = date(year, 1, 1)
    dec31 = date(year, 12, 31)
    num_days = (dec31 - jan1).days + 1

    for day_offset in range(num_days):
        d = jan1 + timedelta(days=day_offset)
        cycle_day = _engine.get_cycle_day(d)

        assert 0 <= cycle_day <= 13, f"Cycle day {cycle_day} out of range for {d}"

        owner = _engine.get_day_owner(d)
        wd = d.weekday()

        if wd in FRONT_HALF_WEEKDAYS:
            assert owner == "front_half", (
                f"{d} weekday={wd} expected front_half, got {owner}"
            )
        elif wd in BACK_HALF_WEEKDAYS:
            assert owner == "back_half", (
                f"{d} weekday={wd} expected back_half, got {owner}"
            )
        else:
            # Wednesday — alternates based on cycle position
            assert wd == WEDNESDAY
            if cycle_day < 7:
                assert owner == "front_half", (
                    f"{d} Wed cycle_day={cycle_day} expected front_half, got {owner}"
                )
            else:
                assert owner == "back_half", (
                    f"{d} Wed cycle_day={cycle_day} expected back_half, got {owner}"
                )


@given(
    year=valid_year(),
    day_offset=st.integers(min_value=0, max_value=350),
)
@settings(max_examples=100)
def test_owner_repeats_every_14_days(year: int, day_offset: int):
    """For any date D, the owner of D should equal the owner of D + 14 days
    (if D + 14 is in the same year).

    **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
    """
    jan1 = date(year, 1, 1)
    dec31 = date(year, 12, 31)
    num_days = (dec31 - jan1).days + 1

    if day_offset >= num_days:
        return  # skip if offset exceeds year length

    d = jan1 + timedelta(days=day_offset)
    d_plus_14 = d + timedelta(days=14)

    if d_plus_14.year == year:
        assert _engine.get_day_owner(d) == _engine.get_day_owner(d_plus_14), (
            f"Owner mismatch: {d} vs {d_plus_14}"
        )


# ---------------------------------------------------------------------------
# Property 7: Shift type teammate assignment
# Feature: dc-shiftmaster-pro, Property 7: Shift type teammate assignment
# Validates: Requirements 3.5, 3.6, 4.4
# ---------------------------------------------------------------------------


@given(
    year=valid_year(),
    fhd=valid_teammate(),
    fhn=valid_teammate(),
    bhd=valid_teammate(),
    bhn=valid_teammate(),
)
@settings(max_examples=100)
def test_shift_type_teammate_assignment(
    year: int,
    fhd: tuple[str, str],
    fhn: tuple[str, str],
    bhd: tuple[str, str],
    bhn: tuple[str, str],
):
    """For any date in the annual schedule, if the date is owned by Front Half,
    the Day slot should contain the FHD teammate and the Night slot should
    contain the FHN teammate. If owned by Back Half, the Day slot should
    contain the BHD teammate and the Night slot should contain the BHN
    teammate. If no teammate is assigned for a shift type, the slot should
    contain "nobody".

    **Validates: Requirements 3.5, 3.6, 4.4**
    """
    # Build teammates with forced shift types (ignore the generated shift_type)
    teammates = [
        Teammate(id=1, name=fhd[0], shift_type="FHD"),
        Teammate(id=2, name=fhn[0], shift_type="FHN"),
        Teammate(id=3, name=bhd[0], shift_type="BHD"),
        Teammate(id=4, name=bhn[0], shift_type="BHN"),
    ]

    schedule = _engine.compute_annual_schedule(
        year, teammates, _default_shift_windows, []
    )

    # Walk pairs (day slot, night slot)
    for i in range(0, len(schedule), 2):
        day_slot = schedule[i]
        night_slot = schedule[i + 1]

        owner = _engine.get_day_owner(day_slot.date)

        if owner == "front_half":
            assert fhd[0] in day_slot.teammates, (
                f"{day_slot.date} front_half day slot: expected {fhd[0]!r} in {day_slot.teammates!r}"
            )
            assert fhn[0] in night_slot.teammates, (
                f"{night_slot.date} front_half night slot: expected {fhn[0]!r} in {night_slot.teammates!r}"
            )
        else:
            assert bhd[0] in day_slot.teammates, (
                f"{day_slot.date} back_half day slot: expected {bhd[0]!r} in {day_slot.teammates!r}"
            )
            assert bhn[0] in night_slot.teammates, (
                f"{night_slot.date} back_half night slot: expected {bhn[0]!r} in {night_slot.teammates!r}"
            )


@given(year=valid_year())
@settings(max_examples=100)
def test_no_teammates_all_nobody(year: int):
    """When no teammates are assigned, every slot should contain "nobody".

    **Validates: Requirements 3.5, 3.6, 4.4**
    """
    schedule = _engine.compute_annual_schedule(
        year, [], _default_shift_windows, []
    )

    for slot in schedule:
        assert slot.teammates == ["nobody"], (
            f"{slot.date} {slot.shift_type}: expected ['nobody'], got {slot.teammates!r}"
        )
