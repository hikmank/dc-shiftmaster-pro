"""ShiftPill — teammate assignment Chip component, color-coded by shift type."""

from __future__ import annotations

import flet as ft

from dc_shiftmaster_web.theme import SHIFT_COLORS


class ShiftPill(ft.Chip):
    """Teammate assignment chip within a CalendarCard.

    Color coding:
      - Day shift: amber/gold (#FFD966)
      - Night shift: blue (#4472C4)

    Displays teammate name, optional custom start time suffix,
    and override indicator border when *is_override* is True.
    """

    def __init__(
        self,
        name: str,
        shift_type: str,
        custom_start: str = "",
        is_override: bool = False,
        **kwargs,
    ):
        label_text = f"{name} ({custom_start})" if custom_start else name
        color = SHIFT_COLORS.get(shift_type, SHIFT_COLORS["day"])

        # Dark text on the bright amber day chip, white on the darker night chip
        text_color = "#000000" if shift_type == "day" else "#FFFFFF"

        super().__init__(
            label=ft.Text(label_text, size=12, color=text_color),
            bgcolor=color,
            border_side=(
                ft.BorderSide(2, SHIFT_COLORS["override"])
                if is_override
                else None
            ),
            **kwargs,
        )
