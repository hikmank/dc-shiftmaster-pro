"""HeaderBar — semi-transparent top bar with year and region display."""

from __future__ import annotations

import flet as ft


def build_header_bar(year: int, region: str) -> ft.Container:
    """Build the header bar pinned to the top of the viewport.

    Parameters
    ----------
    year:
        The currently selected schedule year.
    region:
        The DC site code (e.g. "ATL68").  May be empty.

    Returns
    -------
    ft.Container
        A semi-transparent container with blur displaying the app title
        and the year/region context.
    """
    region_label = region if region else "—"
    return ft.Container(
        content=ft.Row(
            [
                ft.Text(
                    "DC-ShiftMaster Pro",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(
                    f"{region_label} — {year}",
                    size=14,
                    opacity=0.7,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=ft.Colors.with_opacity(0.8, "#1E293B"),
        blur=ft.Blur(10, 10),
        padding=ft.padding.symmetric(horizontal=20, vertical=10),
    )
