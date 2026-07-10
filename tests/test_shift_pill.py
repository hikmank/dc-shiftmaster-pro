"""Unit tests for ShiftPill component."""

from dc_shiftmaster_web.components.shift_pill import ShiftPill
from dc_shiftmaster_web.theme import SHIFT_COLORS


class TestShiftPill:
    def test_day_shift_color(self):
        pill = ShiftPill(name="Alice", shift_type="day")
        assert pill.bgcolor == SHIFT_COLORS["day"]

    def test_night_shift_color(self):
        pill = ShiftPill(name="Bob", shift_type="night")
        assert pill.bgcolor == SHIFT_COLORS["night"]

    def test_label_without_custom_start(self):
        pill = ShiftPill(name="Alice", shift_type="day")
        assert pill.label.value == "Alice"

    def test_label_with_custom_start(self):
        pill = ShiftPill(name="Alice", shift_type="day", custom_start="07:00")
        assert pill.label.value == "Alice (07:00)"

    def test_no_border_when_not_override(self):
        pill = ShiftPill(name="Alice", shift_type="day", is_override=False)
        assert pill.border_side is None

    def test_red_border_when_override(self):
        pill = ShiftPill(name="Alice", shift_type="day", is_override=True)
        assert pill.border_side is not None
        assert pill.border_side.width == 2
        assert pill.border_side.color == SHIFT_COLORS["override"]

    def test_unknown_shift_type_defaults_to_day_color(self):
        pill = ShiftPill(name="Charlie", shift_type="unknown")
        assert pill.bgcolor == SHIFT_COLORS["day"]
