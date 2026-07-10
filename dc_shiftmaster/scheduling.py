"""Scheduling engine for DC-ShiftMaster Pro.

Computes the shift rotation based on actual weekdays and generates
annual schedules with Front Half / Back Half ownership assignments.

Ownership rules (based on actual day of week):
  - Sunday, Monday, Tuesday → always Front Half
  - Thursday, Friday, Saturday → always Back Half
  - Wednesday → alternates every week (Front on odd ISO weeks, Back on even,
    or vice-versa — the key is it flips each week)
"""

from datetime import date, timedelta
import calendar

from dc_shiftmaster.models import Teammate, ShiftWindow, Override, ScheduleSlot

# Python weekday(): Mon=0 .. Sun=6
# Front Half fixed days: Sun(6), Mon(0), Tue(1)
# Back Half fixed days: Thu(3), Fri(4), Sat(5)
# Wednesday(2) alternates every week

FRONT_HALF_WEEKDAYS = {6, 0, 1}  # Sun, Mon, Tue
BACK_HALF_WEEKDAYS = {3, 4, 5}   # Thu, Fri, Sat
WEDNESDAY = 2

CYCLE_LENGTH = 14

WEEKDAY_ABBREVS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class SchedulingEngine:
    """Computes the weekday-based shift rotation for a full year.

    Front Half owns Sun/Mon/Tue + every other Wednesday.
    Back Half owns Thu/Fri/Sat + the alternating Wednesdays.
    """

    def get_cycle_day(self, d: date) -> int:
        """Return the 0-based day index within a 14-day cycle (0-13).

        The cycle is anchored to actual weeks: it starts from the Sunday
        on or before January 1 of the date's year, so that the 14-day
        pattern aligns with real weekdays.
        """
        jan1 = date(d.year, 1, 1)
        # Find the Sunday on or before Jan 1
        jan1_weekday = jan1.weekday()  # Mon=0..Sun=6
        days_since_sunday = (jan1_weekday + 1) % 7  # Sun=0
        cycle_start = jan1 - timedelta(days=days_since_sunday)
        offset = (d - cycle_start).days
        return offset % CYCLE_LENGTH

    def get_day_owner(self, d: date) -> str:
        """Determine if a date belongs to 'front_half' or 'back_half'.

        Based on actual weekday:
        - Sun, Mon, Tue → front_half (always)
        - Thu, Fri, Sat → back_half (always)
        - Wed → alternates every week (front_half in week 1 of cycle,
          back_half in week 2, repeating)
        """
        wd = d.weekday()  # Mon=0..Sun=6

        if wd in FRONT_HALF_WEEKDAYS:
            return "front_half"
        if wd in BACK_HALF_WEEKDAYS:
            return "back_half"

        # Wednesday — alternates based on which week of the 2-week cycle
        cycle_day = self.get_cycle_day(d)
        # cycle_day 0-6 = week 1, 7-13 = week 2
        if cycle_day < 7:
            return "front_half"  # Week 1 Wednesday → Front
        return "back_half"       # Week 2 Wednesday → Back

    def compute_annual_schedule(
        self,
        year: int,
        teammates: list[Teammate],
        shift_windows: dict[str, ShiftWindow],
        overrides: list[Override],
    ) -> list[ScheduleSlot]:
        """Compute the full annual schedule for the given year.

        Generates two ScheduleSlot objects per day (Day then Night) for
        every day from January 1 to December 31. Overrides are applied
        on top of computed assignments.

        Args:
            year: The calendar year to generate the schedule for.
            teammates: All teammate records from the database.
            shift_windows: Dict keyed by 'day'/'night' with ShiftWindow values.
            overrides: List of manual overrides to apply.

        Returns:
            A list of ScheduleSlot objects (2 per day), sorted
            chronologically with Day before Night for each date.
        """
        # Build teammate lookup: shift_type -> list of Teammate objects
        teammate_map: dict[str, list[Teammate]] = {}
        for t in teammates:
            teammate_map.setdefault(t.shift_type, []).append(t)

        # Build override lookup: (YYYY-MM-DD, shift_type) -> name
        override_map: dict[tuple[str, str], str] = {}
        for o in overrides:
            override_map[(o.date, o.shift_type)] = o.name

        day_start = shift_windows["day"].start_time if "day" in shift_windows else "06:00"
        night_start = shift_windows["night"].start_time if "night" in shift_windows else "18:00"

        num_days = 366 if calendar.isleap(year) else 365
        current = date(year, 1, 1)
        slots: list[ScheduleSlot] = []

        for _ in range(num_days):
            owner = self.get_day_owner(current)
            date_str = current.isoformat()

            if owner == "front_half":
                day_team = teammate_map.get("FHD", [])
                night_team = teammate_map.get("FHN", [])
            else:
                day_team = teammate_map.get("BHD", [])
                night_team = teammate_map.get("BHN", [])

            day_names = [t.name for t in day_team] if day_team else ["nobody"]
            night_names = [t.name for t in night_team] if night_team else ["nobody"]

            # Custom teammates: add to day shift if today's weekday is in their custom_days
            custom_teammates = teammate_map.get("Custom", [])
            for t in custom_teammates:
                day_abbrev = WEEKDAY_ABBREVS[current.weekday()]
                if day_abbrev in t.custom_days:
                    if day_names == ["nobody"]:
                        day_names = [t.name]
                    else:
                        day_names.append(t.name)

            # Build per-teammate custom start times
            day_starts: dict[str, str] = {}
            for t in day_team:
                if t.custom_start:
                    day_starts[t.name] = t.custom_start

            # Include custom start times for Custom teammates added to day shift
            for t in custom_teammates:
                day_abbrev = WEEKDAY_ABBREVS[current.weekday()]
                if day_abbrev in t.custom_days and t.custom_start:
                    day_starts[t.name] = t.custom_start

            night_starts: dict[str, str] = {}
            for t in night_team:
                if t.custom_start:
                    night_starts[t.name] = t.custom_start

            # Apply overrides (override replaces the entire list)
            day_key = (date_str, "day")
            night_key = (date_str, "night")
            day_is_override = day_key in override_map
            night_is_override = night_key in override_map

            if day_is_override:
                raw = override_map[day_key]
                day_names = [n.strip() for n in raw.split(',') if n.strip()]
                if not day_names:
                    day_names = ['nobody']
                day_starts = {}
            if night_is_override:
                raw = override_map[night_key]
                night_names = [n.strip() for n in raw.split(',') if n.strip()]
                if not night_names:
                    night_names = ['nobody']
                night_starts = {}

            slots.append(ScheduleSlot(
                date=current,
                shift_type="day",
                start_time=day_start,
                teammates=day_names,
                is_override=day_is_override,
                teammate_starts=day_starts,
            ))
            slots.append(ScheduleSlot(
                date=current,
                shift_type="night",
                start_time=night_start,
                teammates=night_names,
                is_override=night_is_override,
                teammate_starts=night_starts,
            ))

            current += timedelta(days=1)

        return slots
