"""Unit tests for CalendarCard component."""

from __future__ import annotations

import pytest

ft = pytest.importorskip("flet", reason="flet not installed")

from dc_shiftmaster_web.components.calendar_card import CalendarCard  # noqa: E402
from dc_shiftmaster_web.components.shift_pill import ShiftPill  # noqa: E402


class TestCalendarCardConstruction:
    """Verify CalendarCard builds the correct control tree."""

    def test_basic_attributes(self):
        card = CalendarCard(day_number=15, day_abbr="Mon", owner_label="F")
        assert card.day_number == 15
        assert card.day_abbr == "Mon"
        assert card.owner_label == "F"

    def test_default_hover_state(self):
        card = CalendarCard(day_number=1, day_abbr="Tue", owner_label="B")
        assert card.scale == 1.0
        assert card.opacity == 0.9

    def test_animation_properties_set(self):
        card = CalendarCard(day_number=1, day_abbr="Wed", owner_label="F")
        assert card.animate_scale is not None
        assert card.animate_opacity is not None

    def test_day_pills_created(self):
        teammates = [("Alice", "", False), ("Bob", "07:00", True)]
        card = CalendarCard(
            day_number=5, day_abbr="Thu", owner_label="F",
            day_teammates=teammates,
        )
        inner_card: ft.Card = card.content
        card_container: ft.Container = inner_card.content
        main_col: ft.Column = card_container.content
        shifts_col: ft.Column = main_col.controls[1]
        assert len(shifts_col.controls) == 1
        day_col = shifts_col.controls[0]
        assert len(day_col.controls) == 2
        assert all(isinstance(p, ShiftPill) for p in day_col.controls)

    def test_night_pills_created(self):
        teammates = [("Charlie", "", False)]
        card = CalendarCard(
            day_number=10, day_abbr="Fri", owner_label="B",
            night_teammates=teammates,
        )
        inner_card: ft.Card = card.content
        card_container: ft.Container = inner_card.content
        main_col: ft.Column = card_container.content
        shifts_col: ft.Column = main_col.controls[1]
        assert len(shifts_col.controls) == 1
        night_col = shifts_col.controls[0]
        assert len(night_col.controls) == 1
        assert isinstance(night_col.controls[0], ShiftPill)

    def test_both_shifts_present(self):
        card = CalendarCard(
            day_number=20, day_abbr="Sat", owner_label="F",
            day_teammates=[("Alice", "", False)],
            night_teammates=[("Bob", "", False)],
        )
        inner_card: ft.Card = card.content
        card_container: ft.Container = inner_card.content
        main_col: ft.Column = card_container.content
        shifts_col: ft.Column = main_col.controls[1]
        assert len(shifts_col.controls) == 2

    def test_empty_teammates(self):
        card = CalendarCard(day_number=1, day_abbr="Sun", owner_label="B")
        inner_card: ft.Card = card.content
        card_container: ft.Container = inner_card.content
        main_col: ft.Column = card_container.content
        shifts_col: ft.Column = main_col.controls[1]
        assert len(shifts_col.controls) == 0

    def test_owner_label_f_uses_blue_badge(self):
        card = CalendarCard(day_number=1, day_abbr="Mon", owner_label="F")
        inner_card: ft.Card = card.content
        card_container: ft.Container = inner_card.content
        main_col: ft.Column = card_container.content
        header_row: ft.Row = main_col.controls[0]
        badge: ft.Container = header_row.controls[1]
        assert badge.bgcolor == "#3B82F6"

    def test_owner_label_b_uses_amber_badge(self):
        card = CalendarCard(day_number=1, day_abbr="Mon", owner_label="B")
        inner_card: ft.Card = card.content
        card_container: ft.Container = inner_card.content
        main_col: ft.Column = card_container.content
        header_row: ft.Row = main_col.controls[0]
        badge: ft.Container = header_row.controls[1]
        assert badge.bgcolor == "#F59E0B"
