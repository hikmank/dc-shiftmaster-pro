"""Property-based tests for Custom Schedule Shift feature.

Uses Hypothesis to verify persistence and validation properties
for the Custom shift type and custom_days field.
"""

import io
import tempfile
import os

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster_html.server import create_app


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@st.composite
def non_empty_day_subset(draw: st.DrawFn) -> list[str]:
    """Generate a random non-empty subset of {Mon, Tue, Wed, Thu, Fri, Sat, Sun}."""
    subset = draw(
        st.lists(st.sampled_from(ALL_DAYS), min_size=1, max_size=7, unique=True)
    )
    return subset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db():
    """Create a fresh DatabaseManager backed by a temp file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return DatabaseManager(path), path


def _cleanup_db(db, path):
    """Close the database and remove the temp file."""
    db.conn.close()
    try:
        os.unlink(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Property 1: Custom days persistence round-trip
# Feature: custom-schedule-shift, Property 1: Custom days persistence round-trip
# **Validates: Requirements 3.1, 3.2, 3.3**
# ---------------------------------------------------------------------------


@given(custom_days=non_empty_day_subset())
@settings(max_examples=100, deadline=None)
def test_custom_days_persistence_round_trip(custom_days):
    """For any valid non-empty subset of days from {Mon, Tue, Wed, Thu, Fri, Sat, Sun},
    saving a Custom teammate with those days and then retrieving the teammate record
    SHALL produce the same set of days in custom_days."""
    db, path = _make_db()
    try:
        # Save a Custom teammate with the generated days
        new_id = db.add_teammate("TestUser", "Custom", custom_start="", custom_days=custom_days)

        # Retrieve the teammate
        teammates = db.get_teammates()
        match = [t for t in teammates if t.id == new_id]

        assert len(match) == 1
        retrieved = match[0]
        assert retrieved.shift_type == "Custom"
        # Compare as sets — order does not matter
        assert set(retrieved.custom_days) == set(custom_days)
    finally:
        _cleanup_db(db, path)


# ---------------------------------------------------------------------------
# Property 2: Empty custom_days validation rejection
# Feature: custom-schedule-shift, Property 2: Empty custom_days validation rejection
# **Validates: Requirements 3.4**
# ---------------------------------------------------------------------------


@st.composite
def teammate_name(draw: st.DrawFn) -> str:
    """Generate a valid non-empty teammate name."""
    name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=30,
        ).filter(lambda s: s.strip())
    )
    return name


@given(name=teammate_name())
@settings(max_examples=100, deadline=None)
def test_empty_custom_days_validation_rejection(name, tmp_path_factory):
    """For any teammate data with shift_type 'Custom' and an empty custom_days array,
    the API SHALL reject the request with a 400 status and the teammate SHALL NOT
    be persisted."""
    # Create a fresh app with a temp database for each example
    tmp_path = tmp_path_factory.mktemp("db")
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    with app.test_client() as client:
        # Attempt to create a Custom teammate with empty custom_days
        resp = client.post(
            "/api/teammates",
            json={
                "name": name,
                "shift_type": "Custom",
                "custom_days": [],
            },
        )

        # API must reject with 400
        assert resp.status_code == 400, (
            f"Expected 400 for Custom with empty custom_days, got {resp.status_code}"
        )

        error_data = resp.get_json()
        assert "error" in error_data
        assert "day" in error_data["error"].lower() or "custom_days" in error_data["error"].lower()

        # Verify no teammate was persisted
        get_resp = client.get("/api/teammates")
        assert get_resp.status_code == 200
        teammates = get_resp.get_json()
        assert len(teammates) == 0, (
            f"Expected no teammates persisted, but found {len(teammates)}"
        )


# ---------------------------------------------------------------------------
# Property 6: Custom teammates scheduled only on their specified weekdays
# Feature: custom-schedule-shift, Property 6: Custom teammates scheduled only on specified weekdays
# **Validates: Requirements 6.1, 6.3**
# ---------------------------------------------------------------------------

from datetime import date
from dc_shiftmaster.scheduling import SchedulingEngine, WEEKDAY_ABBREVS
from dc_shiftmaster.models import Teammate, ShiftWindow


@st.composite
def custom_teammate_and_year(draw: st.DrawFn):
    """Generate a Custom teammate with random non-empty day subset and a random year."""
    days = draw(
        st.lists(st.sampled_from(ALL_DAYS), min_size=1, max_size=7, unique=True)
    )
    year = draw(st.integers(min_value=2020, max_value=2030))
    return days, year


@given(data=custom_teammate_and_year())
@settings(max_examples=100, deadline=None)
def test_custom_teammates_scheduled_only_on_specified_weekdays(data):
    """For any Custom teammate, they appear in a day slot if and only if
    the slot's date falls on a weekday contained in custom_days."""
    custom_days, year = data

    teammate = Teammate(
        id=1,
        name="CustomWorker",
        shift_type="Custom",
        custom_start="",
        custom_days=custom_days,
    )

    shift_windows = {
        "day": ShiftWindow("day", "06:00", "18:30"),
        "night": ShiftWindow("night", "18:00", "06:30"),
    }

    engine = SchedulingEngine()
    slots = engine.compute_annual_schedule(
        year=year,
        teammates=[teammate],
        shift_windows=shift_windows,
        overrides=[],
    )

    # Check every day slot in the year
    day_slots = [s for s in slots if s.shift_type == "day"]

    for slot in day_slots:
        day_abbrev = WEEKDAY_ABBREVS[slot.date.weekday()]
        is_custom_day = day_abbrev in custom_days
        teammate_present = "CustomWorker" in slot.teammates

        if is_custom_day:
            assert teammate_present, (
                f"CustomWorker should appear on {slot.date} ({day_abbrev}) "
                f"which is in custom_days={custom_days}, but was not found. "
                f"Slot teammates: {slot.teammates}"
            )
        else:
            assert not teammate_present, (
                f"CustomWorker should NOT appear on {slot.date} ({day_abbrev}) "
                f"which is not in custom_days={custom_days}, but was found. "
                f"Slot teammates: {slot.teammates}"
            )


# ---------------------------------------------------------------------------
# Property 7: Standard teammates unaffected by Custom teammates
# Feature: custom-schedule-shift, Property 7: Standard teammates unaffected by Custom teammates
# **Validates: Requirements 6.2**
# ---------------------------------------------------------------------------

from datetime import date
from dc_shiftmaster.models import Teammate, ShiftWindow
from dc_shiftmaster.scheduling import SchedulingEngine


@st.composite
def standard_teammates_list(draw: st.DrawFn) -> list[Teammate]:
    """Generate a list of standard teammates with at least one per shift type."""
    teammates = []
    next_id = 1
    # Ensure at least one of each standard type
    for shift_type in ["FHD", "FHN", "BHD", "BHN"]:
        name = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("L",)),
                min_size=2,
                max_size=10,
            ).filter(lambda s: s.strip())
        )
        teammates.append(Teammate(id=next_id, name=f"{name}_{shift_type}", shift_type=shift_type))
        next_id += 1

    # Optionally add more standard teammates
    extra_count = draw(st.integers(min_value=0, max_value=4))
    for _ in range(extra_count):
        shift_type = draw(st.sampled_from(["FHD", "FHN", "BHD", "BHN"]))
        name = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("L",)),
                min_size=2,
                max_size=10,
            ).filter(lambda s: s.strip())
        )
        teammates.append(Teammate(id=next_id, name=f"{name}_extra_{next_id}", shift_type=shift_type))
        next_id += 1

    return teammates


@st.composite
def custom_teammates_list(draw: st.DrawFn) -> list[Teammate]:
    """Generate a list of Custom teammates (1 to 4) with random days."""
    count = draw(st.integers(min_value=1, max_value=4))
    teammates = []
    for i in range(count):
        name = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("L",)),
                min_size=2,
                max_size=10,
            ).filter(lambda s: s.strip())
        )
        days = draw(
            st.lists(st.sampled_from(ALL_DAYS), min_size=1, max_size=7, unique=True)
        )
        teammates.append(
            Teammate(
                id=100 + i,
                name=f"Custom_{name}_{i}",
                shift_type="Custom",
                custom_days=days,
            )
        )
    return teammates


@given(
    standard_teammates=standard_teammates_list(),
    custom_teammates=custom_teammates_list(),
    year=st.integers(min_value=2020, max_value=2030),
)
@settings(max_examples=100, deadline=None)
def test_standard_teammates_unaffected_by_custom_teammates(
    standard_teammates, custom_teammates, year
):
    """For any standard teammate, the set of schedule slots containing that name
    SHALL be identical regardless of whether Custom teammates exist in the teammate list."""
    engine = SchedulingEngine()
    shift_windows = {
        "day": ShiftWindow("day", "06:00", "18:30"),
        "night": ShiftWindow("night", "18:00", "06:30"),
    }

    # Compute schedule WITHOUT Custom teammates
    schedule_without_custom = engine.compute_annual_schedule(
        year=year,
        teammates=standard_teammates,
        shift_windows=shift_windows,
        overrides=[],
    )

    # Compute schedule WITH Custom teammates added
    all_teammates = standard_teammates + custom_teammates
    schedule_with_custom = engine.compute_annual_schedule(
        year=year,
        teammates=all_teammates,
        shift_windows=shift_windows,
        overrides=[],
    )

    # For each standard teammate, verify they appear in exactly the same slots
    for std_teammate in standard_teammates:
        name = std_teammate.name

        # Get slots containing this standard teammate from schedule without custom
        slots_without = [
            (slot.date, slot.shift_type)
            for slot in schedule_without_custom
            if name in slot.teammates
        ]

        # Get slots containing this standard teammate from schedule with custom
        slots_with = [
            (slot.date, slot.shift_type)
            for slot in schedule_with_custom
            if name in slot.teammates
        ]

        assert set(slots_without) == set(slots_with), (
            f"Standard teammate '{name}' (shift_type={std_teammate.shift_type}) "
            f"has different slots when Custom teammates are present.\n"
            f"Slots only in without-custom: {set(slots_without) - set(slots_with)}\n"
            f"Slots only in with-custom: {set(slots_with) - set(slots_without)}"
        )


# ---------------------------------------------------------------------------
# Property 5: CSV import rejects invalid custom_days for Custom rows
# Feature: custom-schedule-shift, Property 5: CSV import rejects invalid custom_days
# **Validates: Requirements 5.4**
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Property 4: CSV export produces empty custom_days for standard teammates
# Feature: custom-schedule-shift, Property 4: CSV export produces empty custom_days for standard teammates
# **Validates: Requirements 5.2**
# ---------------------------------------------------------------------------


@st.composite
def standard_shift_type(draw: st.DrawFn) -> str:
    """Generate a random standard shift type from {FHD, FHN, BHD, BHN}."""
    return draw(st.sampled_from(["FHD", "FHN", "BHD", "BHN"]))


@st.composite
def standard_teammate_name(draw: st.DrawFn) -> str:
    """Generate a valid teammate name (ASCII letters/digits, non-empty)."""
    return draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), max_codepoint=127),
            min_size=1,
            max_size=30,
        ).filter(lambda s: s.strip())
    )


@given(name=standard_teammate_name(), shift_type=standard_shift_type())
@settings(max_examples=100, deadline=None)
def test_csv_export_empty_custom_days_for_standard_teammates(name, shift_type, tmp_path_factory):
    """For any teammate with a standard shift type (FHD, FHN, BHD, or BHN),
    the exported CSV custom_days column SHALL be an empty string.

    **Validates: Requirements 5.2**
    """
    tmp_path = tmp_path_factory.mktemp("db")
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    with app.test_client() as client:
        # Create a standard teammate via the API
        resp = client.post(
            "/api/teammates",
            json={
                "name": name,
                "shift_type": shift_type,
                "custom_start": "",
                "custom_days": [],
            },
        )
        assert resp.status_code == 201, (
            f"Failed to create teammate: {resp.get_json()}"
        )

        # Retrieve teammates via GET and verify custom_days is empty list
        get_resp = client.get("/api/teammates")
        assert get_resp.status_code == 200
        teammates = get_resp.get_json()
        assert len(teammates) == 1
        t = teammates[0]
        assert t["shift_type"] == shift_type
        assert t["custom_days"] == [], (
            f"Expected empty custom_days for {shift_type} teammate, "
            f"got {t['custom_days']}"
        )

        # Simulate the CSV export logic as team.js does it:
        # For standard shift types, custom_days column is empty.
        # CSV format: name,shift_type,custom_start,custom_days
        days_col = ""
        if t["shift_type"] == "Custom" and isinstance(t.get("custom_days"), list) and len(t["custom_days"]) > 0:
            days_col = ";".join(t["custom_days"])

        csv_row = f'"{t["name"]}",{t["shift_type"]},{t["custom_start"]},{days_col}'

        # Verify the custom_days column (4th field) is empty
        fields = csv_row.rsplit(",", 1)  # Split off the last field
        custom_days_field = fields[-1]
        assert custom_days_field == "", (
            f"Expected empty custom_days column for {shift_type} teammate, "
            f"got '{custom_days_field}' in CSV row: {csv_row}"
        )


VALID_DAYS_SET = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}


@st.composite
def invalid_custom_days_csv_value(draw: st.DrawFn) -> str:
    """Generate a custom_days CSV column value that is either empty or contains
    at least one invalid day abbreviation (not in VALID_DAYS).

    Returns a semicolon-separated string suitable for the CSV custom_days column.
    """
    kind = draw(st.sampled_from(["empty", "all_invalid", "mixed_invalid"]))

    if kind == "empty":
        return ""

    # Generate invalid day strings (not in VALID_DAYS_SET)
    invalid_day = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=10,
        ).filter(lambda s: s not in VALID_DAYS_SET)
    )

    if kind == "all_invalid":
        # All values are invalid
        extra_invalid = draw(
            st.lists(
                st.text(
                    alphabet=st.characters(whitelist_categories=("L", "N")),
                    min_size=1,
                    max_size=10,
                ).filter(lambda s: s not in VALID_DAYS_SET),
                min_size=0,
                max_size=3,
            )
        )
        all_vals = [invalid_day] + extra_invalid
        return ";".join(all_vals)

    # mixed_invalid: at least one valid day + at least one invalid day
    valid_days = draw(
        st.lists(st.sampled_from(list(VALID_DAYS_SET)), min_size=1, max_size=3, unique=True)
    )
    all_vals = valid_days + [invalid_day]
    draw(st.randoms()).shuffle(all_vals)
    return ";".join(all_vals)


@given(
    name=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=20,
    ).filter(lambda s: s.strip()),
    invalid_days_value=invalid_custom_days_csv_value(),
)
@settings(max_examples=100, deadline=None)
def test_csv_import_rejects_invalid_custom_days(name, invalid_days_value, tmp_path_factory):
    """For any CSV row with shift_type 'Custom' where the custom_days field is empty
    or contains at least one value not in {Mon, Tue, Wed, Thu, Fri, Sat, Sun},
    the import SHALL skip that row and include its row number in the skipped_rows list."""
    tmp_path = tmp_path_factory.mktemp("db")
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    with app.test_client() as client:
        # Build a CSV with a single Custom row that has invalid custom_days
        csv_content = f"{name},Custom,,{invalid_days_value}\n"
        data = {"file": (io.BytesIO(csv_content.encode()), "team.csv")}
        resp = client.post(
            "/api/teammates/import-csv",
            data=data,
            content_type="multipart/form-data",
        )

        assert resp.status_code == 200
        result = resp.get_json()

        # The row should be skipped (row 1 since it's the first and only data row)
        assert 1 in result["skipped_rows"], (
            f"Expected row 1 in skipped_rows for Custom with invalid days "
            f"'{invalid_days_value}', but got skipped_rows={result['skipped_rows']}"
        )

        # Verify no teammate was imported
        assert result["imported_count"] == 0, (
            f"Expected imported_count=0 for invalid custom_days, "
            f"got {result['imported_count']}"
        )
