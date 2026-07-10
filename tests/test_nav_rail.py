"""Unit tests for the NavigationRail wrapper component."""

from __future__ import annotations

import flet as ft

from dc_shiftmaster_web.components.nav_rail import build_nav_rail


def test_build_nav_rail_returns_navigation_rail():
    """build_nav_rail should return a ft.NavigationRail instance."""
    rail = build_nav_rail(on_change=lambda e: None)
    assert isinstance(rail, ft.NavigationRail)


def test_nav_rail_has_four_destinations():
    """The rail must have exactly four destinations."""
    rail = build_nav_rail(on_change=lambda e: None)
    assert len(rail.destinations) == 4


def test_nav_rail_destination_labels():
    """Destinations should be Dashboard, Team, Settings, Export in order."""
    rail = build_nav_rail(on_change=lambda e: None)
    labels = [d.label for d in rail.destinations]
    assert labels == ["Dashboard", "Team", "Settings", "Export"]


def test_nav_rail_destination_icons():
    """Each destination should use the correct Material icon."""
    rail = build_nav_rail(on_change=lambda e: None)
    icons = [d.icon for d in rail.destinations]
    assert icons == [
        ft.Icons.CALENDAR_MONTH,
        ft.Icons.PEOPLE,
        ft.Icons.SETTINGS,
        ft.Icons.DOWNLOAD,
    ]


def test_nav_rail_defaults_to_dashboard():
    """selected_index should default to 0 (Dashboard)."""
    rail = build_nav_rail(on_change=lambda e: None)
    assert rail.selected_index == 0


def test_nav_rail_dimensions():
    """min_width=80, min_extended_width=200, extended=True."""
    rail = build_nav_rail(on_change=lambda e: None)
    assert rail.min_width == 80
    assert rail.min_extended_width == 200
    assert rail.extended is True


def test_nav_rail_on_change_callback():
    """The on_change callback should be wired to the rail."""
    sentinel = object()
    callback = lambda e: sentinel  # noqa: E731
    rail = build_nav_rail(on_change=callback)
    assert rail.on_change is callback
