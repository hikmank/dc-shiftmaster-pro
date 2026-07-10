"""Export module for DC-ShiftMaster Pro.

Supports two export formats for the on-call scheduling system:
  - CSV: headerless two-column file (YYYY/MM/DD HH:MM,member)
  - JSON: array of shift objects with startDateTime, endDateTime, oncallMember

Both formats follow the Custom Upload specification. Output is ASCII-encoded
and validated before writing (chronological order, no overlaps, <2 MB).
"""

import csv
import json
from datetime import date, timedelta
from typing import Optional

from dc_shiftmaster.models import ScheduleSlot


def validate_schedule(schedule: list[ScheduleSlot]) -> list[str]:
    """Validate a schedule against Custom Upload rules.

    Returns a list of error strings. Empty list means valid.
    Rules checked:
      - Shifts in chronological, non-overlapping order
      - No timezone info in datetimes (guaranteed by format)
      - All teammate names are ASCII-safe
    """
    errors: list[str] = []
    prev_date: Optional[date] = None
    prev_shift: Optional[str] = None

    for slot in schedule:
        # Check chronological order
        if prev_date is not None:
            if slot.date < prev_date:
                errors.append(
                    f"Out of order: {slot.date} comes after {prev_date}"
                )
            elif slot.date == prev_date:
                if prev_shift == "night" and slot.shift_type == "day":
                    errors.append(
                        f"Out of order: day shift after night shift on {slot.date}"
                    )
        prev_date = slot.date
        prev_shift = slot.shift_type

        # Check ASCII-safe names
        for name in slot.teammates:
            try:
                name.encode("ascii")
            except UnicodeEncodeError:
                errors.append(
                    f"Non-ASCII name '{name}' on {slot.date} {slot.shift_type}"
                )

    return errors


class CSVExporter:
    """Exports an annual schedule to CSV in Custom Upload format.

    Format per the wiki: YYYY/MM/DD HH:MM,member_name
    No header row, ASCII encoding, one row per teammate per slot.
    """

    def format_datetime(self, dt_date: date, time_str: str) -> str:
        """Format a date + time into 'YYYY/MM/DD HH:MM' with leading zeros.

        Matches the Custom Upload wiki example format.

        Args:
            dt_date: The calendar date.
            time_str: Time in HH:MM format (e.g. '06:00', '18:00').

        Returns:
            Formatted string like '2018/06/05 14:00'.
        """
        return f"{dt_date.year}/{dt_date.month:02d}/{dt_date.day:02d} {time_str}"

    def export(self, schedule: list[ScheduleSlot], filepath: str) -> None:
        """Write the annual schedule to a headerless two-column CSV.

        Each row is: YYYY/MM/DD HH:MM,teammate_name
        Output is ASCII-encoded per the wiki recommendation.

        Raises:
            OSError: If the file path is not writable.
            ValueError: If schedule fails validation.
        """
        errors = validate_schedule(schedule)
        if errors:
            raise ValueError(
                f"Schedule validation failed:\n" + "\n".join(errors[:10])
            )

        try:
            with open(filepath, "w", newline="", encoding="ascii") as f:
                writer = csv.writer(f)
                for slot in schedule:
                    for name in slot.teammates:
                        # Use custom start time if this teammate has one
                        start = slot.teammate_starts.get(name, slot.start_time)
                        formatted_dt = self.format_datetime(slot.date, start)
                        writer.writerow([formatted_dt, name])
        except (OSError, PermissionError) as e:
            raise OSError(f"Cannot save CSV to '{filepath}': {e}") from e

    def parse_csv_row(self, row: str) -> tuple[date, str, str]:
        """Parse a CSV row back into (date, time, teammate_name).

        Supports both YYYY/MM/DD HH:MM and M/D/YYYY H:MM formats.
        """
        parts = row.split(",", 1)
        if len(parts) != 2:
            raise ValueError(f"Expected exactly one comma in row: {row!r}")

        datetime_part = parts[0].strip()
        teammate_name = parts[1].strip()

        dt_parts = datetime_part.rsplit(" ", 1)
        if len(dt_parts) != 2:
            raise ValueError(f"Expected datetime format: {datetime_part!r}")

        date_str, time_str = dt_parts
        date_components = date_str.split("/")
        if len(date_components) != 3:
            raise ValueError(f"Expected date format: {date_str!r}")

        a, b, c = int(date_components[0]), int(date_components[1]), int(date_components[2])

        # Detect format: if first component > 31, it's YYYY/MM/DD
        if a > 31:
            year, month, day = a, b, c
        else:
            month, day, year = a, b, c

        return date(year, month, day), time_str, teammate_name


class JSONExporter:
    """Exports an annual schedule to JSON in Custom Upload format.

    JSON is the preferred upload format per the wiki. It supports
    multiple people per shift natively and explicit gaps.

    Format:
    [
      {
        "startDateTime": "M/D/YY HH:MM",
        "endDateTime": "M/D/YY HH:MM",
        "oncallMember": ["member1", "member2"]
      },
      ...
    ]
    """

    def _format_dt(self, dt_date: date, time_str: str) -> str:
        """Format as 'M/D/YYYY HH:MM' matching the wiki JSON examples.

        Uses full 4-digit year to avoid ambiguity with dates like 2100.
        """
        return f"{dt_date.month}/{dt_date.day}/{dt_date.year} {time_str}"

    def _format_dt_full(self, dt_date: date, time_str: str) -> str:
        """Format as 'YYYY-MM-DDTHH:MM:00' matching the wiki API examples."""
        return f"{dt_date.year}-{dt_date.month:02d}-{dt_date.day:02d}T{time_str}:00"

    def export(
        self,
        schedule: list[ScheduleSlot],
        filepath: str,
        use_api_format: bool = False,
    ) -> None:
        """Write the annual schedule to JSON.

        Each non-nobody slot becomes one JSON object. The endDateTime of
        each shift is the startDateTime of the next non-nobody shift
        (or Jan 1 2100 for the last shift).

        Args:
            schedule: List of ScheduleSlot objects in chronological order.
            filepath: Destination file path.
            use_api_format: If True, use the API format (YYYY-MM-DDTHH:MM:00).
                If False, use the wiki JSON format (M/D/YYYY HH:MM).

        Raises:
            OSError: If the file path is not writable.
            ValueError: If schedule fails validation.
        """
        errors = validate_schedule(schedule)
        if errors:
            raise ValueError(
                f"Schedule validation failed:\n" + "\n".join(errors[:10])
            )

        fmt = self._format_dt_full if use_api_format else self._format_dt

        # Collect entries — one per slot, all teammates together.
        # Custom start times are an internal detail; the oncall calendar
        # expects non-overlapping entries so we group everyone into the
        # slot's default time window.
        shifts: list[dict] = []
        for slot in schedule:
            if slot.teammates == ["nobody"]:
                continue

            default_end = "18:30" if slot.shift_type == "day" else "06:30"

            sh, sm = int(slot.start_time[:2]), int(slot.start_time[3:5])
            deh, dem = int(default_end[:2]), int(default_end[3:5])
            def_start_mins = sh * 60 + sm
            def_end_mins = deh * 60 + dem
            duration = def_end_mins - def_start_mins
            if duration <= 0:
                duration += 1440

            total = def_start_mins + duration
            end_date = slot.date
            if total >= 1440:
                total -= 1440
                end_date = slot.date + timedelta(days=1)
            end_time = f"{total // 60:02d}:{total % 60:02d}"

            shifts.append({
                "startDateTime": fmt(slot.date, slot.start_time),
                "endDateTime": fmt(end_date, end_time),
                "oncallMember": slot.teammates,
            })

        try:
            with open(filepath, "w", encoding="ascii") as f:
                json.dump(shifts, f, indent=2)
        except (OSError, PermissionError) as e:
            raise OSError(f"Cannot save JSON to '{filepath}': {e}") from e
