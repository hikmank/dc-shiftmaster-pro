"""Data model classes for DC-ShiftMaster Pro.

Defines the core dataclasses used throughout the application for
shift windows, teammates, overrides, and schedule slots.
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class ShiftWindow:
    """A named time range defining when a shift starts and ends.

    Represents either a Day or Night shift window with configurable
    start and end times in HH:MM 24-hour format.

    Attributes:
        shift_type: The type of shift, either 'day' or 'night'.
        start_time: Shift start time in HH:MM format (e.g. '06:00').
        end_time: Shift end time in HH:MM format (e.g. '18:30').
    """

    shift_type: str
    start_time: str
    end_time: str


@dataclass
class Teammate:
    """A team member assigned to a specific shift rotation group.

    Each teammate is stored in the SQLite database with a unique row ID
    and assigned to one of the shift type groups.

    Attributes:
        id: Unique database row identifier.
        name: The teammate's name or alias.
        shift_type: One of 'FHD', 'FHN', 'BHD', 'BHN', or 'Custom'.
        custom_start: Optional HH:MM override for this person's start time.
        custom_days: List of day abbreviations for Custom shift type,
            e.g. ["Mon", "Wed", "Fri"]. Empty list for standard shift types.
    """

    id: int
    name: str
    shift_type: str
    custom_start: str = ""  # Optional HH:MM override for this person's start time
    custom_days: list[str] = field(default_factory=list)  # e.g. ["Mon", "Wed", "Fri"]


@dataclass
class Override:
    """A manual per-slot assignment replacing the computed teammate.

    Overrides allow managers to substitute a different person (or 'nobody')
    for a specific date and shift type, taking precedence over the
    scheduling engine's computed assignment.

    Attributes:
        date: The override date in 'YYYY-MM-DD' format.
        shift_type: The shift type, either 'day' or 'night'.
        name: The replacement name, or 'nobody' for unassigned.
    """

    date: str
    shift_type: str
    name: str


@dataclass
class ScheduleSlot:
    """A single shift assignment for one date and shift type.

    Represents one cell in the calendar view — either the Day or Night
    slot for a given date, populated by the scheduling engine or an override.

    Attributes:
        date: The calendar date for this slot.
        shift_type: The shift type, either 'day' or 'night'.
        start_time: The shift start time from the ShiftWindow (e.g. '6:00').
        teammates: List of assigned teammate names. Contains ["nobody"] if
            no teammates are assigned for this shift type.
        is_override: True if this slot was manually overridden.
    """

    date: date
    shift_type: str
    start_time: str
    teammates: list[str]
    is_override: bool
    teammate_starts: dict[str, str] = None  # name -> custom start time (if any)

    def __post_init__(self):
        if self.teammate_starts is None:
            self.teammate_starts = {}


@dataclass
class User:
    """An individual user account for authentication and shift ownership.

    Each user has a unique username and is optionally linked to a Teammate
    record via the teammate_name field for shift matching.

    Attributes:
        id: Unique database row identifier.
        username: Unique login name.
        password_hash: Hashed password (werkzeug format).
        display_name: Human-readable name shown in the UI.
        teammate_name: Links to Teammate.name for shift matching.
        created_at: ISO datetime string of account creation.
        email: User's email address for notifications.
        email_notifications_enabled: Whether the user has opted in to email notifications.
    """

    id: int
    username: str
    password_hash: str
    display_name: str
    teammate_name: str
    created_at: str
    email: str = ""
    email_notifications_enabled: bool = False


@dataclass
class CoverageRequest:
    """A request from a user to have one of their shifts covered.

    When claimed, the system creates an override replacing the original
    assignee with the claimant on the specified date and shift.

    Attributes:
        id: Unique database row identifier.
        requester_id: Foreign key to the User who posted the request.
        date: The shift date in 'YYYY-MM-DD' format.
        shift_type: The shift type, either 'day' or 'night'.
        note: Optional message from the requester.
        status: One of 'open', 'claimed', or 'cancelled'.
        claimer_id: Foreign key to the User who claimed the request, or None.
        created_at: ISO datetime string of request creation.
        claimed_at: ISO datetime string when claimed, or None.
    """

    id: int
    requester_id: int
    date: str
    shift_type: str
    note: str
    status: str
    claimer_id: int | None
    created_at: str
    claimed_at: str | None
