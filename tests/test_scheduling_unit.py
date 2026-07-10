"""Unit tests for SchedulingEngine cycle computation (task 5.1)."""

from datetime import date, timedelta

from dc_shiftmaster.scheduling import (
    SchedulingEngine,
    FRONT_HALF_WEEKDAYS,
    BACK_HALF_WEEKDAYS,
    WEDNESDAY,
    CYCLE_LENGTH,
)


class TestGetCycleDay:
    """Tests for SchedulingEngine.get_cycle_day().

    The cycle is anchored to the Sunday on or before Jan 1 of the year.
    """

    def setup_method(self):
        self.engine = SchedulingEngine()

    def test_jan1_2024_cycle_day(self):
        """Jan 1, 2024 = Monday. Sunday before = Dec 31, 2023. offset=1."""
        assert self.engine.get_cycle_day(date(2024, 1, 1)) == 1

    def test_jan1_2025_cycle_day(self):
        """Jan 1, 2025 = Wednesday. Sunday before = Dec 29, 2024. offset=3."""
        assert self.engine.get_cycle_day(date(2025, 1, 1)) == 3

    def test_jan1_2000_cycle_day(self):
        """Jan 1, 2000 = Saturday. Sunday before = Dec 26, 1999. offset=6."""
        assert self.engine.get_cycle_day(date(2000, 1, 1)) == 6

    def test_jan2_2024_cycle_day(self):
        """Jan 2, 2024 = Tuesday. offset from Dec 31, 2023 = 2."""
        assert self.engine.get_cycle_day(date(2024, 1, 2)) == 2

    def test_jan14_2024_cycle_day(self):
        """Jan 14, 2024 = Sunday. offset from Dec 31, 2023 = 14. 14 % 14 = 0."""
        assert self.engine.get_cycle_day(date(2024, 1, 14)) == 0

    def test_jan15_2024_cycle_day(self):
        """Jan 15, 2024 = Monday. offset from Dec 31, 2023 = 15. 15 % 14 = 1."""
        assert self.engine.get_cycle_day(date(2024, 1, 15)) == 1

    def test_cycle_repeats_every_14_days(self):
        """Cycle day should be the same for dates 14 days apart."""
        base = date(2024, 3, 10)
        for offset in range(0, 14):
            d = base + timedelta(days=offset)
            d_plus_14 = d + timedelta(days=14)
            assert self.engine.get_cycle_day(d) == self.engine.get_cycle_day(d_plus_14)

    def test_range_is_0_to_13(self):
        """All cycle days for a full year should be in range [0, 13]."""
        d = date(2024, 1, 1)
        for i in range(366):  # 2024 is a leap year
            cycle_day = self.engine.get_cycle_day(d + timedelta(days=i))
            assert 0 <= cycle_day <= 13

    def test_leap_year_feb29(self):
        """Feb 29, 2024 (Thu). offset from Dec 31, 2023 = 60. 60 % 14 = 4."""
        cycle_day = self.engine.get_cycle_day(date(2024, 2, 29))
        assert cycle_day == 60 % CYCLE_LENGTH  # 60 % 14 = 4


class TestGetDayOwner:
    """Tests for SchedulingEngine.get_day_owner().

    Ownership is based on actual weekday:
    - Sun(6), Mon(0), Tue(1) → always front_half
    - Thu(3), Fri(4), Sat(5) → always back_half
    - Wed(2) → alternates: front_half in week 1 (cycle_day < 7),
      back_half in week 2 (cycle_day >= 7)
    """

    def setup_method(self):
        self.engine = SchedulingEngine()

    def test_sunday_is_front_half(self):
        """Sunday is always front_half."""
        # Jan 7, 2024 = Sunday
        assert self.engine.get_day_owner(date(2024, 1, 7)) == "front_half"

    def test_monday_is_front_half(self):
        """Monday is always front_half."""
        # Jan 1, 2024 = Monday
        assert self.engine.get_day_owner(date(2024, 1, 1)) == "front_half"

    def test_tuesday_is_front_half(self):
        """Tuesday is always front_half."""
        # Jan 2, 2024 = Tuesday
        assert self.engine.get_day_owner(date(2024, 1, 2)) == "front_half"

    def test_thursday_is_back_half(self):
        """Thursday is always back_half."""
        # Jan 4, 2024 = Thursday
        assert self.engine.get_day_owner(date(2024, 1, 4)) == "back_half"

    def test_friday_is_back_half(self):
        """Friday is always back_half."""
        # Jan 5, 2024 = Friday
        assert self.engine.get_day_owner(date(2024, 1, 5)) == "back_half"

    def test_saturday_is_back_half(self):
        """Saturday is always back_half."""
        # Jan 6, 2024 = Saturday
        assert self.engine.get_day_owner(date(2024, 1, 6)) == "back_half"

    def test_wednesday_week1_is_front_half(self):
        """Wednesday in week 1 of cycle (cycle_day < 7) is front_half."""
        # Jan 3, 2024 = Wednesday, cycle_day = 3 (< 7)
        assert self.engine.get_day_owner(date(2024, 1, 3)) == "front_half"

    def test_wednesday_week2_is_back_half(self):
        """Wednesday in week 2 of cycle (cycle_day >= 7) is back_half."""
        # Jan 10, 2024 = Wednesday, cycle_day = 10 (>= 7)
        assert self.engine.get_day_owner(date(2024, 1, 10)) == "back_half"

    def test_owner_repeats_every_14_days(self):
        """Owner should be the same for dates 14 days apart within the same year."""
        base = date(2024, 2, 1)
        for offset in range(14):
            d = base + timedelta(days=offset)
            d_plus_14 = d + timedelta(days=14)
            if d_plus_14.year == d.year:
                assert self.engine.get_day_owner(d) == self.engine.get_day_owner(d_plus_14)

    def test_full_cycle_pattern_2024(self):
        """Verify the complete 14-day pattern from Jan 1, 2024 (Monday).

        Jan 1 Mon=front, Jan 2 Tue=front, Jan 3 Wed(w1)=front,
        Jan 4 Thu=back, Jan 5 Fri=back, Jan 6 Sat=back,
        Jan 7 Sun=front, Jan 8 Mon=front, Jan 9 Tue=front,
        Jan 10 Wed(w2)=back, Jan 11 Thu=back, Jan 12 Fri=back,
        Jan 13 Sat=back, Jan 14 Sun=front
        """
        expected = [
            "front_half",  # Jan 1  Mon
            "front_half",  # Jan 2  Tue
            "front_half",  # Jan 3  Wed (week 1, cycle_day=3)
            "back_half",   # Jan 4  Thu
            "back_half",   # Jan 5  Fri
            "back_half",   # Jan 6  Sat
            "front_half",  # Jan 7  Sun
            "front_half",  # Jan 8  Mon
            "front_half",  # Jan 9  Tue
            "back_half",   # Jan 10 Wed (week 2, cycle_day=10)
            "back_half",   # Jan 11 Thu
            "back_half",   # Jan 12 Fri
            "back_half",   # Jan 13 Sat
            "front_half",  # Jan 14 Sun
        ]
        for i, exp in enumerate(expected):
            d = date(2024, 1, 1) + timedelta(days=i)
            assert self.engine.get_day_owner(d) == exp, (
                f"Day {i} ({d}, {d.strftime('%a')}): expected {exp}"
            )


class TestConstants:
    """Verify module-level constants are correct."""

    def test_front_half_weekdays(self):
        """Front half weekdays are Sun(6), Mon(0), Tue(1)."""
        assert FRONT_HALF_WEEKDAYS == {6, 0, 1}

    def test_back_half_weekdays(self):
        """Back half weekdays are Thu(3), Fri(4), Sat(5)."""
        assert BACK_HALF_WEEKDAYS == {3, 4, 5}

    def test_wednesday(self):
        """Wednesday constant is 2."""
        assert WEDNESDAY == 2

    def test_front_back_and_wednesday_cover_all_weekdays(self):
        """Front, back, and Wednesday should cover all 7 weekdays."""
        assert FRONT_HALF_WEEKDAYS | BACK_HALF_WEEKDAYS | {WEDNESDAY} == set(range(7))

    def test_front_and_back_are_disjoint(self):
        assert FRONT_HALF_WEEKDAYS & BACK_HALF_WEEKDAYS == set()

    def test_wednesday_not_in_either_fixed_set(self):
        assert WEDNESDAY not in FRONT_HALF_WEEKDAYS
        assert WEDNESDAY not in BACK_HALF_WEEKDAYS

    def test_cycle_length(self):
        assert CYCLE_LENGTH == 14


from dc_shiftmaster.models import Teammate, ShiftWindow, Override, ScheduleSlot


class TestComputeAnnualSchedule:
    """Tests for SchedulingEngine.compute_annual_schedule()."""

    def setup_method(self):
        self.engine = SchedulingEngine()
        self.shift_windows = {
            "day": ShiftWindow(shift_type="day", start_time="06:00", end_time="18:30"),
            "night": ShiftWindow(shift_type="night", start_time="18:00", end_time="06:30"),
        }
        self.teammates = [
            Teammate(id=1, name="Alice", shift_type="FHD"),
            Teammate(id=2, name="Bob", shift_type="FHN"),
            Teammate(id=3, name="Charlie", shift_type="BHD"),
            Teammate(id=4, name="Diana", shift_type="BHN"),
        ]

    def test_slot_count_non_leap_year(self):
        """Non-leap year produces 365 * 2 = 730 slots."""
        slots = self.engine.compute_annual_schedule(2025, self.teammates, self.shift_windows, [])
        assert len(slots) == 730

    def test_slot_count_leap_year(self):
        """Leap year produces 366 * 2 = 732 slots."""
        slots = self.engine.compute_annual_schedule(2024, self.teammates, self.shift_windows, [])
        assert len(slots) == 732

    def test_day_before_night_ordering(self):
        """Each pair of slots should be day then night for the same date."""
        slots = self.engine.compute_annual_schedule(2025, self.teammates, self.shift_windows, [])
        for i in range(0, len(slots), 2):
            assert slots[i].shift_type == "day"
            assert slots[i + 1].shift_type == "night"
            assert slots[i].date == slots[i + 1].date

    def test_chronological_order(self):
        """Dates should be in ascending order."""
        slots = self.engine.compute_annual_schedule(2025, self.teammates, self.shift_windows, [])
        dates = [s.date for s in slots[::2]]  # day slots only
        assert dates == sorted(dates)

    def test_front_half_day_assigns_fhd_fhn(self):
        """Jan 1 2025 (Wednesday, week 1 → front_half) should use FHD/FHN."""
        slots = self.engine.compute_annual_schedule(2025, self.teammates, self.shift_windows, [])
        jan1_day = slots[0]
        jan1_night = slots[1]
        assert jan1_day.date == date(2025, 1, 1)
        assert jan1_day.teammates == ["Alice"]
        assert jan1_night.teammates == ["Bob"]

    def test_back_half_day_assigns_bhd_bhn(self):
        """Jan 2 2025 (Thursday → back_half) should use BHD/BHN."""
        slots = self.engine.compute_annual_schedule(2025, self.teammates, self.shift_windows, [])
        # Jan 2 is day index 1 → slot indices 2, 3
        jan2_day = slots[2]
        jan2_night = slots[3]
        assert jan2_day.date == date(2025, 1, 2)
        assert jan2_day.teammates == ["Charlie"]
        assert jan2_night.teammates == ["Diana"]

    def test_sunday_is_front_half_in_schedule(self):
        """Jan 5 2025 (Sunday → front_half) should use FHD/FHN."""
        slots = self.engine.compute_annual_schedule(2025, self.teammates, self.shift_windows, [])
        # Jan 5 is day index 4 → slot indices 8, 9
        jan5_day = slots[8]
        jan5_night = slots[9]
        assert jan5_day.date == date(2025, 1, 5)
        assert jan5_day.teammates == ["Alice"]
        assert jan5_night.teammates == ["Bob"]

    def test_nobody_when_no_teammate(self):
        """Slots with no teammate for a shift type should show 'nobody'."""
        partial = [Teammate(id=1, name="Alice", shift_type="FHD")]
        slots = self.engine.compute_annual_schedule(2025, partial, self.shift_windows, [])
        # Jan 1 2025 = Wed (week 1 → front_half): FHD=Alice, FHN=nobody
        assert slots[0].teammates == ["Alice"]
        assert slots[1].teammates == ["nobody"]
        # Jan 2 2025 = Thu (back_half): BHD=nobody, BHN=nobody
        assert slots[2].teammates == ["nobody"]
        assert slots[3].teammates == ["nobody"]

    def test_empty_teammates_all_nobody(self):
        """With no teammates, every slot should be 'nobody'."""
        slots = self.engine.compute_annual_schedule(2025, [], self.shift_windows, [])
        assert all(s.teammates == ["nobody"] for s in slots)

    def test_override_replaces_computed(self):
        """An override should replace the computed teammate name."""
        overrides = [Override(date="2025-01-01", shift_type="day", name="Override_Person")]
        slots = self.engine.compute_annual_schedule(2025, self.teammates, self.shift_windows, overrides)
        assert slots[0].teammates == ["Override_Person"]
        assert slots[0].is_override is True
        # Night slot for same day should be unaffected
        assert slots[1].teammates == ["Bob"]
        assert slots[1].is_override is False

    def test_start_times_from_shift_windows(self):
        """Slots should use start times from the provided shift windows."""
        slots = self.engine.compute_annual_schedule(2025, self.teammates, self.shift_windows, [])
        assert slots[0].start_time == "06:00"
        assert slots[1].start_time == "18:00"

    def test_first_and_last_dates(self):
        """Schedule should span Jan 1 to Dec 31."""
        slots = self.engine.compute_annual_schedule(2025, self.teammates, self.shift_windows, [])
        assert slots[0].date == date(2025, 1, 1)
        assert slots[-1].date == date(2025, 12, 31)
