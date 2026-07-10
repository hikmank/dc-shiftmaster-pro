"""Input validation utilities for DC-ShiftMaster Pro."""

import re

# Precompiled pattern: exactly HH:MM where HH is 00-23 and MM is 00-59.
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def validate_time_format(time_str: str) -> tuple[bool, str]:
    """Validate that a string is in HH:MM 24-hour format.

    Accepts hours 00-23 and minutes 00-59, with mandatory two-digit
    zero-padded values separated by a colon.

    Args:
        time_str: The string to validate.

    Returns:
        A tuple of (is_valid, error_message).
        If valid, returns (True, "").
        If invalid, returns (False, <descriptive error message>).
    """
    if not isinstance(time_str, str):
        return False, "Time must be a string."

    if not time_str:
        return False, "Time must not be empty."

    if ":" not in time_str:
        return False, f"Invalid time format '{time_str}'. Expected HH:MM (e.g. '06:00')."

    parts = time_str.split(":")
    if len(parts) != 2:
        return False, f"Invalid time format '{time_str}'. Expected exactly one colon in HH:MM."

    hours_str, minutes_str = parts

    if len(hours_str) != 2 or len(minutes_str) != 2:
        return False, f"Invalid time format '{time_str}'. Hours and minutes must each be two digits."

    if not hours_str.isdigit() or not minutes_str.isdigit():
        return False, f"Invalid time format '{time_str}'. Hours and minutes must be numeric."

    hours, minutes = int(hours_str), int(minutes_str)

    if hours > 23:
        return False, f"Invalid hour {hours_str}. Must be between 00 and 23."

    if minutes > 59:
        return False, f"Invalid minute {minutes_str}. Must be between 00 and 59."

    return True, ""
