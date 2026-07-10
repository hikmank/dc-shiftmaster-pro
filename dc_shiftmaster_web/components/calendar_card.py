"""CalendarCard — single-day Card component for the calendar grid."""

from __future__ import annotations

from typing import Callable

import flet as ft

from dc_shiftmaster_web.components.shift_pill import ShiftPill
from dc_shiftmaster_web.theme import SHIFT_COLORS


class CalendarCard(ft.Container):
    """Single day in the calendar grid.

    Wraps an ``ft.Card`` inside an ``ft.Container`` so that hover-driven
    ``animate_scale`` (1.0 → 1.02) and ``animate_opacity`` (0.9 → 1.0)
    transitions can be applied.

    Parameters
    ----------
    day_number:
        Calendar day (1-31).
    day_abbr:
        Three-letter weekday abbreviation, e.g. "Mon".
    owner_label:
        "F" (Front Half) or "B" (Back Half).
    day_teammates:
        List of ``(name, custom_start, is_override)`` tuples for day shift.
    night_teammates:
        List of ``(name, custom_start, is_override)`` tuples for night shift.
    on_override:
        Optional callback ``(day_number, shift_type) -> None`` invoked when
        the user requests an override via right-click or long-press.
    """

    def __init__(
        self,
        day_number: int,
        day_abbr: str,
        owner_label: str,
        day_teammates: list[tuple[str, str, bool]] | None = None,
        night_teammates: list[tuple[str, str, bool]] | None = None,
        on_override: Callable[[int, str], None] | None = None,
        **kwargs,
    ):
        self.day_number = day_number
        self.day_abbr = day_abbr
        self.owner_label = owner_label
        self._day_teammates = day_teammates or []
        self._night_teammates = night_teammates or []
        self._on_override = on_override

        # Build pill lists
        day_pills = [
            ShiftPill(name=n, shift_type="day", custom_start=cs, is_override=ov)
            for n, cs, ov in self._day_teammates
        ]
        night_pills = [
            ShiftPill(name=n, shift_type="night", custom_start=cs, is_override=ov)
            for n, cs, ov in self._night_teammates
        ]

        # Owner label colour: primary blue for F, secondary amber for B
        owner_color = "#3B82F6" if owner_label == "F" else "#F59E0B"

        # Header row: day number + abbr on the left, owner badge on the right
        header = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(str(day_number), size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(day_abbr, size=12, opacity=0.7),
                    ],
                    spacing=4,
                ),
                ft.Container(
                    content=ft.Text(owner_label, size=11, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                    bgcolor=owner_color,
                    border_radius=4,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # Shift sections
        shifts_column = ft.Column(spacing=4, controls=[])
        if day_pills:
            shifts_column.controls.append(
                ft.Column(spacing=2, controls=day_pills)
            )
        if night_pills:
            shifts_column.controls.append(
                ft.Column(spacing=2, controls=night_pills)
            )

        card = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[header, shifts_column],
                    spacing=6,
                ),
                padding=8,
            ),
            elevation=2,
        )

        # Wrap card in GestureDetector for right-click / long-press override menu
        if on_override is not None:
            gesture_content = ft.GestureDetector(
                content=card,
                on_secondary_tap=lambda e: self._show_override_menu(e),
                on_long_press_start=lambda e: self._show_override_menu(e),
            )
        else:
            gesture_content = card

        super().__init__(
            content=gesture_content,
            scale=1.0,
            opacity=0.9,
            animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
            on_hover=self._on_hover,
            **kwargs,
        )

    def _show_override_menu(self, e) -> None:
        """Trigger the override callback for this card's day."""
        if self._on_override is not None:
            # Pass day_number and let the parent decide which shift_type to ask about
            self._on_override(self.day_number, "both")

    def _on_hover(self, e: ft.ControlEvent) -> None:
        """Scale up and brighten on hover, revert on leave."""
        if e.data == "true":
            self.scale = 1.02
            self.opacity = 1.0
        else:
            self.scale = 1.0
            self.opacity = 0.9
        self.update()
