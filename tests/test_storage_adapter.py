"""Unit tests for StorageAdapter (dc_shiftmaster_web.storage)."""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from hypothesis import given, settings, strategies as st

from dc_shiftmaster.models import Override, ShiftWindow, Teammate
from dc_shiftmaster_web.storage import StorageAdapter
from tests.conftest import VALID_SHIFT_TYPES, valid_teammate, valid_time


# ------------------------------------------------------------------ #
# Mock client_storage
# ------------------------------------------------------------------ #

class MockClientStorage:
    """Dict-backed mock of Flet's client_storage for testing."""

    def __init__(self):
        self._data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def remove(self, key: str) -> None:
        self._data.pop(key, None)


def _make_page(storage=None):
    """Create a mock page with shared_preferences."""
    if storage is None:
        storage = MockClientStorage()
    return SimpleNamespace(shared_preferences=storage)


@pytest.fixture
def adapter():
    """Fresh StorageAdapter backed by mock storage."""
    page = _make_page()
    return StorageAdapter(page)


# ------------------------------------------------------------------ #
# Default seed data
# ------------------------------------------------------------------ #

class TestSeedDefaults:
    def test_default_shift_windows_created(self, adapter):
        windows = adapter.get_shift_windows()
        assert "day" in windows
        assert "night" in windows

    def test_default_day_window_values(self, adapter):
        day = adapter.get_shift_windows()["day"]
        assert day.start_time == "06:00"
        assert day.end_time == "18:30"

    def test_default_night_window_values(self, adapter):
        night = adapter.get_shift_windows()["night"]
        assert night.start_time == "18:00"
        assert night.end_time == "06:30"

    def test_seed_does_not_overwrite_existing(self):
        mock = MockClientStorage()
        custom = json.dumps({
            "day": {"shift_type": "day", "start_time": "07:00", "end_time": "19:00"},
            "night": {"shift_type": "night", "start_time": "19:00", "end_time": "07:00"},
        })
        mock.set("dcshift.shift_windows", custom)
        page = _make_page(mock)
        sa = StorageAdapter(page)
        assert sa.get_shift_windows()["day"].start_time == "07:00"


# ------------------------------------------------------------------ #
# Teammates CRUD
# ------------------------------------------------------------------ #

class TestTeammates:
    def test_empty_initially(self, adapter):
        assert adapter.get_teammates() == []

    def test_add_returns_id_1_when_empty(self, adapter):
        new_id = adapter.add_teammate("Alice", "FHD")
        assert new_id == 1

    def test_add_increments_id(self, adapter):
        adapter.add_teammate("Alice", "FHD")
        second = adapter.add_teammate("Bob", "BHN")
        assert second == 2

    def test_add_then_read(self, adapter):
        adapter.add_teammate("Alice", "FHD", "07:00")
        teammates = adapter.get_teammates()
        assert len(teammates) == 1
        assert teammates[0].name == "Alice"
        assert teammates[0].shift_type == "FHD"
        assert teammates[0].custom_start == "07:00"

    def test_update_teammate(self, adapter):
        tid = adapter.add_teammate("Alice", "FHD")
        adapter.update_teammate(tid, "Alicia", "BHN", "19:00")
        t = adapter.get_teammates()[0]
        assert t.name == "Alicia"
        assert t.shift_type == "BHN"
        assert t.custom_start == "19:00"

    def test_delete_teammate(self, adapter):
        tid = adapter.add_teammate("Alice", "FHD")
        adapter.delete_teammate(tid)
        assert adapter.get_teammates() == []

    def test_delete_preserves_others(self, adapter):
        adapter.add_teammate("Alice", "FHD")
        tid2 = adapter.add_teammate("Bob", "BHN")
        adapter.delete_teammate(tid2)
        remaining = adapter.get_teammates()
        assert len(remaining) == 1
        assert remaining[0].name == "Alice"

    def test_id_after_delete_uses_max(self, adapter):
        adapter.add_teammate("Alice", "FHD")  # id=1
        tid2 = adapter.add_teammate("Bob", "BHN")  # id=2
        adapter.delete_teammate(tid2)
        tid3 = adapter.add_teammate("Charlie", "FHN")  # should be 2 (max=1, +1=2)
        assert tid3 == 2


# ------------------------------------------------------------------ #
# Name validation
# ------------------------------------------------------------------ #

class TestNameValidation:
    def test_empty_name_raises(self, adapter):
        with pytest.raises(ValueError, match="empty"):
            adapter.add_teammate("", "FHD")

    def test_whitespace_name_raises(self, adapter):
        with pytest.raises(ValueError, match="empty"):
            adapter.add_teammate("   ", "FHD")

    def test_tab_name_raises(self, adapter):
        with pytest.raises(ValueError, match="empty"):
            adapter.add_teammate("\t\n", "FHD")

    def test_update_empty_name_raises(self, adapter):
        tid = adapter.add_teammate("Alice", "FHD")
        with pytest.raises(ValueError, match="empty"):
            adapter.update_teammate(tid, "", "FHD")

    def test_update_whitespace_name_raises(self, adapter):
        tid = adapter.add_teammate("Alice", "FHD")
        with pytest.raises(ValueError, match="empty"):
            adapter.update_teammate(tid, "  ", "FHD")


# ------------------------------------------------------------------ #
# Shift Windows
# ------------------------------------------------------------------ #

class TestShiftWindows:
    def test_update_shift_window(self, adapter):
        adapter.update_shift_window("day", "07:00", "19:00")
        day = adapter.get_shift_windows()["day"]
        assert day.start_time == "07:00"
        assert day.end_time == "19:00"

    def test_update_preserves_other_window(self, adapter):
        adapter.update_shift_window("day", "07:00", "19:00")
        night = adapter.get_shift_windows()["night"]
        assert night.start_time == "18:00"
        assert night.end_time == "06:30"


# ------------------------------------------------------------------ #
# Overrides
# ------------------------------------------------------------------ #

class TestOverrides:
    def test_empty_initially(self, adapter):
        assert adapter.get_overrides(2025) == []

    def test_set_and_get(self, adapter):
        adapter.set_override("2025-03-15", "day", "Charlie")
        overrides = adapter.get_overrides(2025)
        assert len(overrides) == 1
        assert overrides[0].date == "2025-03-15"
        assert overrides[0].name == "Charlie"

    def test_year_filtering(self, adapter):
        adapter.set_override("2025-01-01", "day", "A")
        adapter.set_override("2024-12-31", "night", "B")
        assert len(adapter.get_overrides(2025)) == 1
        assert len(adapter.get_overrides(2024)) == 1

    def test_set_replaces_existing(self, adapter):
        adapter.set_override("2025-03-15", "day", "Charlie")
        adapter.set_override("2025-03-15", "day", "Dave")
        overrides = adapter.get_overrides(2025)
        assert len(overrides) == 1
        assert overrides[0].name == "Dave"

    def test_remove_override(self, adapter):
        adapter.set_override("2025-03-15", "day", "Charlie")
        adapter.remove_override("2025-03-15", "day")
        assert adapter.get_overrides(2025) == []

    def test_remove_preserves_others(self, adapter):
        adapter.set_override("2025-03-15", "day", "Charlie")
        adapter.set_override("2025-03-15", "night", "Dave")
        adapter.remove_override("2025-03-15", "day")
        overrides = adapter.get_overrides(2025)
        assert len(overrides) == 1
        assert overrides[0].shift_type == "night"


# ------------------------------------------------------------------ #
# Year / Region settings
# ------------------------------------------------------------------ #

class TestSettings:
    def test_year_defaults_to_current(self, adapter):
        assert adapter.get_year() == datetime.now().year

    def test_set_and_get_year(self, adapter):
        adapter.set_year(2030)
        assert adapter.get_year() == 2030

    def test_region_defaults_to_empty(self, adapter):
        assert adapter.get_region() == ""

    def test_set_and_get_region(self, adapter):
        adapter.set_region("ATL68")
        assert adapter.get_region() == "ATL68"


# ------------------------------------------------------------------ #
# Hypothesis strategies for StorageAdapter property tests
# ------------------------------------------------------------------ #

@st.composite
def valid_teammate_object(draw: st.DrawFn) -> Teammate:
    """Generate a valid Teammate dataclass instance."""
    tid = draw(st.integers(min_value=1, max_value=10_000))
    name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
            min_size=1,
            max_size=50,
        ).filter(lambda s: s.strip())
    )
    shift_type = draw(st.sampled_from(VALID_SHIFT_TYPES))
    custom_start = draw(st.one_of(st.just(""), valid_time()))
    return Teammate(id=tid, name=name, shift_type=shift_type, custom_start=custom_start)


# ------------------------------------------------------------------ #
# Property-based tests
# ------------------------------------------------------------------ #

# Feature: dc-shiftmaster-web, Property 1: Teammate serialization round-trip
class TestTeammateSerializationRoundTrip:
    """**Validates: Requirements 2.7**"""

    @given(teammates=st.lists(valid_teammate_object(), min_size=0, max_size=20))
    @settings(max_examples=100)
    def test_serialize_deserialize_round_trip(self, teammates: list[Teammate]):
        """Serializing then deserializing a list of Teammates produces equivalent objects."""
        json_str = StorageAdapter._serialize_teammates(teammates)
        result = StorageAdapter._deserialize_teammates(json_str)

        assert len(result) == len(teammates)
        for original, restored in zip(teammates, result):
            assert restored.id == original.id
            assert restored.name == original.name
            assert restored.shift_type == original.shift_type
            assert restored.custom_start == original.custom_start


@st.composite
def valid_shift_window_dict(draw: st.DrawFn) -> dict[str, ShiftWindow]:
    """Generate a valid dict of ShiftWindow objects keyed by 'day' and 'night'."""
    day_start = draw(valid_time())
    day_end = draw(valid_time())
    night_start = draw(valid_time())
    night_end = draw(valid_time())
    return {
        "day": ShiftWindow(shift_type="day", start_time=day_start, end_time=day_end),
        "night": ShiftWindow(shift_type="night", start_time=night_start, end_time=night_end),
    }


@st.composite
def valid_override_object(draw: st.DrawFn) -> Override:
    """Generate a valid Override dataclass instance."""
    from datetime import date as dt_date

    yr = draw(st.integers(min_value=2000, max_value=2100))
    d = draw(st.dates(min_value=dt_date(yr, 1, 1), max_value=dt_date(yr, 12, 31)))
    date_str = d.isoformat()
    shift_type = draw(st.sampled_from(["day", "night"]))
    name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
            min_size=1,
            max_size=30,
        ).filter(lambda s: s.strip())
    )
    return Override(date=date_str, shift_type=shift_type, name=name)


# Feature: dc-shiftmaster-web, Property 2: Override serialization round-trip
class TestOverrideSerializationRoundTrip:
    """**Validates: Requirements 2.8**"""

    @given(overrides=st.lists(valid_override_object(), min_size=0, max_size=20))
    @settings(max_examples=100)
    def test_serialize_deserialize_round_trip(self, overrides: list[Override]):
        """Serializing then deserializing a list of Overrides produces equivalent objects."""
        json_str = StorageAdapter._serialize_overrides(overrides)
        result = StorageAdapter._deserialize_overrides(json_str)

        assert len(result) == len(overrides)
        for original, restored in zip(overrides, result):
            assert restored.date == original.date
            assert restored.shift_type == original.shift_type
            assert restored.name == original.name


# Feature: dc-shiftmaster-web, Property 3: Shift window serialization round-trip
class TestShiftWindowSerializationRoundTrip:
    """**Validates: Requirements 2.9**"""

    @given(windows=valid_shift_window_dict())
    @settings(max_examples=100)
    def test_serialize_deserialize_round_trip(self, windows: dict[str, ShiftWindow]):
        """Serializing then deserializing a dict of ShiftWindows produces equivalent objects."""
        json_str = StorageAdapter._serialize_shift_windows(windows)
        result = StorageAdapter._deserialize_shift_windows(json_str)

        assert set(result.keys()) == set(windows.keys())
        for key in windows:
            assert result[key].shift_type == windows[key].shift_type
            assert result[key].start_time == windows[key].start_time
            assert result[key].end_time == windows[key].end_time


# Feature: dc-shiftmaster-web, Property 4: Teammate ID auto-increment
class TestTeammateIdAutoIncrement:
    """**Validates: Requirements 2.5**"""

    @given(teammates=st.lists(valid_teammate(), min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_ids_strictly_increasing_and_unique(self, teammates: list[tuple[str, str]]):
        """Adding teammates sequentially produces strictly increasing, unique IDs."""
        page = _make_page()
        adapter = StorageAdapter(page)

        assigned_ids = []
        for name, shift_type in teammates:
            new_id = adapter.add_teammate(name, shift_type)
            assigned_ids.append(new_id)

        # Each ID is strictly greater than all previous IDs
        for i in range(1, len(assigned_ids)):
            assert assigned_ids[i] > assigned_ids[i - 1], (
                f"ID {assigned_ids[i]} at index {i} is not greater than "
                f"previous ID {assigned_ids[i - 1]}"
            )

        # All IDs are unique (no duplicates)
        assert len(set(assigned_ids)) == len(assigned_ids), (
            f"Duplicate IDs found: {assigned_ids}"
        )


# Feature: dc-shiftmaster-web, Property 5: Override year filtering
class TestOverrideYearFiltering:
    """**Validates: Requirements 2.6**"""

    @given(data=st.data())
    @settings(max_examples=100)
    def test_get_overrides_returns_only_matching_year(self, data):
        """Reading overrides for a specific year returns exactly those overrides
        whose date starts with that year's prefix, and no overrides from other years."""
        from tests.conftest import valid_override, valid_year

        # Pick 2-3 distinct years
        num_years = data.draw(st.integers(min_value=2, max_value=3))
        years = data.draw(
            st.lists(
                valid_year(),
                min_size=num_years,
                max_size=num_years,
                unique=True,
            )
        )

        # Generate overrides for each year
        overrides_by_year: dict[int, list[tuple[str, str, str]]] = {}
        for yr in years:
            ovs = data.draw(
                st.lists(valid_override(year=yr), min_size=1, max_size=5)
            )
            overrides_by_year[yr] = ovs

        # Store all overrides in a fresh adapter
        page = _make_page()
        adapter = StorageAdapter(page)

        for yr, ovs in overrides_by_year.items():
            for date_str, shift_type, name in ovs:
                adapter.set_override(date_str, shift_type, name)

        # For each year, verify get_overrides returns exactly the right ones
        for yr in years:
            result = adapter.get_overrides(yr)
            prefix = str(yr)

            # All returned overrides belong to the queried year
            for o in result:
                assert o.date.startswith(prefix), (
                    f"Override date {o.date} does not start with {prefix}"
                )

            # Build expected set: last-write-wins per (date, shift_type)
            expected: dict[tuple[str, str], str] = {}
            for date_str, shift_type, name in overrides_by_year[yr]:
                expected[(date_str, shift_type)] = name

            result_map = {(o.date, o.shift_type): o.name for o in result}
            assert result_map == expected, (
                f"Year {yr}: expected {expected}, got {result_map}"
            )


# Feature: dc-shiftmaster-web, Property 6: Empty/whitespace name rejection
class TestEmptyWhitespaceNameRejection:
    """**Validates: Requirements 5.4**"""

    @given(
        name=st.from_regex(r"^[\s]*$", fullmatch=True).filter(lambda s: len(s) <= 50)
    )
    @settings(max_examples=100)
    def test_whitespace_only_name_rejected_on_add(self, name: str):
        """Adding a teammate with a whitespace-only (or empty) name raises ValueError
        and leaves the teammate list unchanged."""
        page = _make_page()
        adapter = StorageAdapter(page)

        before = adapter.get_teammates()

        with pytest.raises(ValueError):
            adapter.add_teammate(name, "FHD")

        after = adapter.get_teammates()
        assert after == before, (
            f"Teammate list changed after rejected add: before={before}, after={after}"
        )


# Feature: dc-shiftmaster-web, Property 7: Teammate add-then-read
class TestTeammateAddThenRead:
    """**Validates: Requirements 5.3**"""

    @given(
        name=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
            min_size=1,
            max_size=50,
        ).filter(lambda s: s.strip()),
        shift_type=st.sampled_from(VALID_SHIFT_TYPES),
        custom_start=st.one_of(st.just(""), valid_time()),
    )
    @settings(max_examples=100)
    def test_added_teammate_appears_in_read(self, name: str, shift_type: str, custom_start: str):
        """Adding a teammate and then reading all teammates should include a record
        with that exact name, shift type, and custom_start value."""
        page = _make_page()
        adapter = StorageAdapter(page)

        adapter.add_teammate(name, shift_type, custom_start)

        teammates = adapter.get_teammates()
        matching = [
            t for t in teammates
            if t.name == name and t.shift_type == shift_type and t.custom_start == custom_start
        ]
        assert len(matching) >= 1, (
            f"Expected to find teammate with name={name!r}, shift_type={shift_type!r}, "
            f"custom_start={custom_start!r} but got: {teammates}"
        )


# Feature: dc-shiftmaster-web, Property 8: Teammate delete-then-read
class TestTeammateDeleteThenRead:
    """**Validates: Requirements 5.7**"""

    @given(
        teammates=st.lists(valid_teammate(), min_size=1, max_size=20),
        data=st.data(),
    )
    @settings(max_examples=100)
    def test_deleted_teammate_absent_and_others_remain(
        self, teammates: list[tuple[str, str]], data
    ):
        """Deleting a teammate by ID then reading all teammates should not
        include any record with that ID, and all other teammates should
        still be present."""
        page = _make_page()
        adapter = StorageAdapter(page)

        # Add all teammates and track their assigned IDs
        id_map: dict[int, tuple[str, str]] = {}
        for name, shift_type in teammates:
            new_id = adapter.add_teammate(name, shift_type)
            id_map[new_id] = (name, shift_type)

        # Pick one ID to delete
        target_id = data.draw(st.sampled_from(sorted(id_map.keys())))

        # Delete the chosen teammate
        adapter.delete_teammate(target_id)

        # Read back
        remaining = adapter.get_teammates()
        remaining_ids = {t.id for t in remaining}

        # The deleted ID must not appear
        assert target_id not in remaining_ids, (
            f"Deleted teammate ID {target_id} still present in {remaining}"
        )

        # All other IDs must still be present
        expected_remaining_ids = set(id_map.keys()) - {target_id}
        assert remaining_ids == expected_remaining_ids, (
            f"Expected remaining IDs {expected_remaining_ids}, got {remaining_ids}"
        )
