"""Property-based tests for override behaviour (Properties 9, 10, 5).

Uses Hypothesis to verify that overrides take precedence over computed
assignments, that removing overrides reverts to computed values, and that
deleting a teammate causes affected slots to show "nobody".
"""

from datetime import date

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from dc_shiftmaster.models import Teammate, ShiftWindow, Override
from dc_shiftmaster.scheduling import SchedulingEngine
from dc_shiftmaster.database import DatabaseManager

from tests.conftest import valid_year, valid_teammate, valid_override

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_engine = SchedulingEngine()

_default_shift_windows: dict[str, ShiftWindow] = {
    "day": ShiftWindow(shift_type="day", start_time="06:00", end_time="18:30"),
    "night": ShiftWindow(shift_type="night", start_time="18:00", end_time="06:30"),
}

_ALL_SHIFT_TYPES = ["FHD", "FHN", "BHD", "BHN"]


def _make_teammates() -> list[Teammate]:
    """Return one teammate per shift type with deterministic names."""
    return [
        Teammate(id=1, name="Alice", shift_type="FHD"),
        Teammate(id=2, name="Bob", shift_type="FHN"),
        Teammate(id=3, name="Carol", shift_type="BHD"),
        Teammate(id=4, name="Dave", shift_type="BHN"),
    ]


# ---------------------------------------------------------------------------
# Property 9: Override takes precedence over computed assignment
# Feature: dc-shiftmaster-pro, Property 9: Override takes precedence over computed assignment
# Validates: Requirements 5.3, 6.7
# ---------------------------------------------------------------------------


@given(year=valid_year(), override=st.data())
@settings(max_examples=100)
def test_override_takes_precedence(year: int, override: st.DataObject):
    """For any annual schedule with at least one override, the schedule slot
    matching the override's date and shift type should contain the override's
    name, not the computed teammate name.

    **Validates: Requirements 5.3, 6.7**
    """
    # Draw a valid override within the year
    ovr = override.draw(valid_override(year=year))
    ovr_date_str, ovr_shift_type, ovr_name = ovr

    teammates = _make_teammates()
    overrides = [Override(date=ovr_date_str, shift_type=ovr_shift_type, name=ovr_name)]

    schedule = _engine.compute_annual_schedule(
        year, teammates, _default_shift_windows, overrides
    )

    ovr_date = date.fromisoformat(ovr_date_str)

    # Find the matching slot
    matching = [
        s for s in schedule
        if s.date == ovr_date and s.shift_type == ovr_shift_type
    ]
    assert len(matching) == 1, (
        f"Expected exactly 1 slot for {ovr_date_str} {ovr_shift_type}, found {len(matching)}"
    )

    slot = matching[0]
    expected_names = [n.strip() for n in ovr_name.split(',') if n.strip()]
    if not expected_names:
        expected_names = ['nobody']
    assert slot.teammates == expected_names, (
        f"Override not applied: expected {expected_names!r}, got {slot.teammates!r} "
        f"on {ovr_date_str} {ovr_shift_type}"
    )
    assert slot.is_override is True, (
        f"Slot should be marked as override for {ovr_date_str} {ovr_shift_type}"
    )


# ---------------------------------------------------------------------------
# Property 10: Override removal reverts to computed assignment
# Feature: dc-shiftmaster-pro, Property 10: Override removal reverts to computed assignment
# Validates: Requirements 5.4, 5.6
# ---------------------------------------------------------------------------


@given(year=valid_year(), override=st.data())
@settings(max_examples=100)
def test_override_removal_reverts_to_computed(year: int, override: st.DataObject):
    """For any slot that has an override, removing the override and recomputing
    should produce the same teammate name as a schedule computed without any
    override for that slot.

    **Validates: Requirements 5.4, 5.6**
    """
    ovr = override.draw(valid_override(year=year))
    ovr_date_str, ovr_shift_type, ovr_name = ovr

    teammates = _make_teammates()

    # Schedule WITHOUT override
    schedule_no_override = _engine.compute_annual_schedule(
        year, teammates, _default_shift_windows, []
    )

    # Schedule WITH override then "remove" it (recompute without it)
    overrides = [Override(date=ovr_date_str, shift_type=ovr_shift_type, name=ovr_name)]
    schedule_with_override = _engine.compute_annual_schedule(
        year, teammates, _default_shift_windows, overrides
    )

    # Now recompute without the override (simulates removal)
    schedule_after_removal = _engine.compute_annual_schedule(
        year, teammates, _default_shift_windows, []
    )

    ovr_date = date.fromisoformat(ovr_date_str)

    # Find the slot in the no-override schedule
    baseline = [
        s for s in schedule_no_override
        if s.date == ovr_date and s.shift_type == ovr_shift_type
    ]
    after = [
        s for s in schedule_after_removal
        if s.date == ovr_date and s.shift_type == ovr_shift_type
    ]

    assert len(baseline) == 1 and len(after) == 1

    assert after[0].teammates == baseline[0].teammates, (
        f"After override removal, expected {baseline[0].teammates!r} "
        f"but got {after[0].teammates!r} on {ovr_date_str} {ovr_shift_type}"
    )
    assert after[0].is_override is False, (
        f"Slot should not be marked as override after removal"
    )


# ---------------------------------------------------------------------------
# Property 5: Deleted teammate becomes "nobody"
# Feature: dc-shiftmaster-pro, Property 5: Deleted teammate becomes "nobody"
# Validates: Requirements 2.4
# ---------------------------------------------------------------------------


@given(
    year=valid_year(),
    shift_type_to_delete=st.sampled_from(_ALL_SHIFT_TYPES),
)
@settings(max_examples=100, deadline=None)
def test_deleted_teammate_becomes_nobody(
    year: int,
    shift_type_to_delete: str,
    tmp_path_factory,
):
    """For any teammate that is deleted, recomputing the annual schedule should
    produce "nobody" in all slots where that teammate was previously assigned
    (assuming no other teammate shares the same shift type).

    **Validates: Requirements 2.4**
    """
    # Use a temp DB for this test
    db_path = str(tmp_path_factory.mktemp("data") / "test.db")
    db = DatabaseManager(db_path)

    try:
        # Add one teammate per shift type
        ids: dict[str, int] = {}
        names = {"FHD": "Alice", "FHN": "Bob", "BHD": "Carol", "BHN": "Dave"}
        for st_type in _ALL_SHIFT_TYPES:
            tid = db.add_teammate(names[st_type], st_type)
            ids[st_type] = tid

        teammates_before = db.get_teammates()
        shift_windows = db.get_shift_windows()

        # Compute schedule BEFORE deletion
        schedule_before = _engine.compute_annual_schedule(
            year, teammates_before, shift_windows, []
        )

        # Identify slots assigned to the teammate we're about to delete
        target_name = names[shift_type_to_delete]
        affected_slots = [
            (s.date, s.shift_type)
            for s in schedule_before
            if target_name in s.teammates
        ]
        # There should be affected slots (the teammate owns some days)
        assert len(affected_slots) > 0, (
            f"Expected {target_name} ({shift_type_to_delete}) to appear in schedule"
        )

        # Delete the teammate
        db.delete_teammate(ids[shift_type_to_delete])

        # Recompute
        teammates_after = db.get_teammates()
        schedule_after = _engine.compute_annual_schedule(
            year, teammates_after, shift_windows, []
        )

        # All previously-affected slots should now be "nobody"
        for slot_date, slot_shift in affected_slots:
            matching = [
                s for s in schedule_after
                if s.date == slot_date and s.shift_type == slot_shift
            ]
            assert len(matching) == 1
            assert matching[0].teammates == ["nobody"], (
                f"After deleting {target_name}, slot {slot_date} {slot_shift} "
                f"should be ['nobody'] but got {matching[0].teammates!r}"
            )
    finally:
        db.conn.close()
