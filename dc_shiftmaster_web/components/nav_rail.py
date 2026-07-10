"""NavigationRail wrapper — four-destination sidebar navigation."""

from __future__ import annotations

from typing import Callable

import flet as ft


def build_nav_rail(on_change: Callable) -> ft.NavigationRail:
    """Build the sidebar navigation rail with four destinations.

    Parameters
    ----------
    on_change:
        Callback invoked when the user selects a destination.
        Receives a Flet ``ControlEvent`` whose ``control.selected_index``
        indicates the chosen page (0=Dashboard, 1=Team, 2=Settings, 3=Export).

    Returns
    -------
    ft.NavigationRail
        A configured navigation rail with Dashboard, Team, Settings, and
        Export destinations.  Defaults to the Dashboard (index 0).
    """
    return ft.NavigationRail(
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.CALENDAR_MONTH, label="Dashboard"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.PEOPLE, label="Team"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SETTINGS, label="Settings"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.DOWNLOAD, label="Export"
            ),
        ],
        selected_index=0,
        on_change=on_change,
        min_width=80,
        min_extended_width=200,
        extended=True,
    )
