"""Shared Hypothesis strategies and pytest fixtures for DC-ShiftMaster Pro tests."""

from datetime import date

import pytest
from hypothesis import strategies as st

from dc_shiftmaster.database import DatabaseManager

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

VALID_SHIFT_TYPES = ["FHD", "FHN", "BHD", "BHN"]


@st.composite
def valid_time(draw: st.DrawFn) -> str:
    """Generate a valid HH:MM 24-hour time string (hours 00-23, minutes 00-59)."""
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    return f"{hour:02d}:{minute:02d}"


@st.composite
def invalid_time(draw: st.DrawFn) -> str:
    """Generate a string that does NOT match HH:MM 24-hour format."""
    strategy = draw(
        st.sampled_from(
            [
                "out_of_range_hour",
                "out_of_range_minute",
                "missing_colon",
                "extra_colon",
                "single_digit",
                "non_numeric",
                "empty",
                "wrong_length",
            ]
        )
    )
    if strategy == "out_of_range_hour":
        hour = draw(st.integers(min_value=24, max_value=99))
        minute = draw(st.integers(min_value=0, max_value=59))
        return f"{hour:02d}:{minute:02d}"
    elif strategy == "out_of_range_minute":
        hour = draw(st.integers(min_value=0, max_value=23))
        minute = draw(st.integers(min_value=60, max_value=99))
        return f"{hour:02d}:{minute:02d}"
    elif strategy == "missing_colon":
        hour = draw(st.integers(min_value=0, max_value=23))
        minute = draw(st.integers(min_value=0, max_value=59))
        return f"{hour:02d}{minute:02d}"
    elif strategy == "extra_colon":
        hour = draw(st.integers(min_value=0, max_value=23))
        minute = draw(st.integers(min_value=0, max_value=59))
        return f"{hour:02d}:{minute:02d}:00"
    elif strategy == "single_digit":
        hour = draw(st.integers(min_value=0, max_value=9))
        minute = draw(st.integers(min_value=0, max_value=9))
        return f"{hour}:{minute}"
    elif strategy == "non_numeric":
        text = draw(st.text(min_size=1, max_size=5, alphabet="abcXYZ!@#"))
        return text
    elif strategy == "empty":
        return ""
    else:  # wrong_length — 3 or 6+ char strings with a colon
        length = draw(st.sampled_from([3, 4, 6, 7, 8]))
        text = draw(st.text(min_size=length, max_size=length, alphabet="0123456789:"))
        return text


def _is_valid_time(s: str) -> bool:
    """Check if a string is a valid HH:MM 24-hour time (used for filtering)."""
    if len(s) != 5 or s[2] != ":":
        return False
    try:
        h, m = int(s[:2]), int(s[3:])
        return 0 <= h <= 23 and 0 <= m <= 59
    except (ValueError, IndexError):
        return False


@st.composite
def valid_teammate(draw: st.DrawFn) -> tuple[str, str]:
    """Generate a (name, shift_type) tuple with a non-empty name and valid shift type."""
    name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
            min_size=1,
            max_size=50,
        ).filter(lambda s: s.strip())
    )
    shift_type = draw(st.sampled_from(VALID_SHIFT_TYPES))
    return (name, shift_type)


@st.composite
def valid_override(draw: st.DrawFn, year: int | None = None) -> tuple[str, str, str]:
    """Generate a (date_str, shift_type, name) tuple for an override within a year.

    Args:
        year: If provided, constrains the date to this year.
              If None, draws a year from valid_year().
    """
    if year is None:
        yr = draw(valid_year())
    else:
        yr = year
    d = draw(st.dates(min_value=date(yr, 1, 1), max_value=date(yr, 12, 31)))
    date_str = d.isoformat()  # 'YYYY-MM-DD'
    shift_type = draw(st.sampled_from(["day", "night"]))
    name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
            min_size=1,
            max_size=30,
        ).filter(lambda s: s.strip())
    )
    return (date_str, shift_type, name)


@st.composite
def valid_year(draw: st.DrawFn) -> int:
    """Generate a year in the range 2000-2100."""
    return draw(st.integers(min_value=2000, max_value=2100))


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db(tmp_path):
    """Provide a fresh DatabaseManager backed by a temp-file database.

    The database file is automatically cleaned up when the temp directory
    is removed after the test.
    """
    db_path = str(tmp_path / "test_teammates.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.conn.close()


# ---------------------------------------------------------------------------
# Web-specific: MockClientStorage and additional strategies
# ---------------------------------------------------------------------------


class MockClientStorage:
    """Dict-backed mock of Flet's client_storage for testing StorageAdapter."""

    def __init__(self):
        self._data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def remove(self, key: str) -> None:
        self._data.pop(key, None)


@st.composite
def valid_shift_windows(draw: st.DrawFn) -> dict:
    """Generate a dict with 'day' and 'night' ShiftWindow-like dicts."""
    from dc_shiftmaster.models import ShiftWindow

    day_start = draw(valid_time())
    day_end = draw(valid_time())
    night_start = draw(valid_time())
    night_end = draw(valid_time())
    return {
        "day": ShiftWindow(shift_type="day", start_time=day_start, end_time=day_end),
        "night": ShiftWindow(shift_type="night", start_time=night_start, end_time=night_end),
    }


@st.composite
def valid_csv_row(draw: st.DrawFn) -> str:
    """Generate a valid CSV row: ``name,shift_type[,custom_start]``."""
    name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=20,
        )
    )
    shift_type = draw(st.sampled_from(VALID_SHIFT_TYPES))
    include_custom = draw(st.booleans())
    if include_custom:
        custom = draw(valid_time())
        return f"{name},{shift_type},{custom}"
    return f"{name},{shift_type}"


@st.composite
def whitespace_string(draw: st.DrawFn) -> str:
    """Generate a string composed entirely of whitespace (spaces, tabs, newlines)."""
    return draw(
        st.text(
            alphabet=st.sampled_from([" ", "\t", "\n", "\r"]),
            min_size=0,
            max_size=10,
        )
    )


@st.composite
def valid_region(draw: st.DrawFn) -> str:
    """Generate a DC site code string."""
    return draw(
        st.sampled_from([
            "ATL68", "ATL78", "CMH68", "CMH78", "DUB31",
            "IAD77", "IAD89", "NRT51", "PDX1", "SFO5",
        ])
    )


@pytest.fixture
def mock_client_storage():
    """Provide a fresh MockClientStorage instance."""
    return MockClientStorage()
