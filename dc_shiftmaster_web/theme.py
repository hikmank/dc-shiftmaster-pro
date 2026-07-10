"""Material 3 dark theme configuration — Deepest Navy color scheme."""

import flet as ft

DEEPEST_NAVY = ft.Theme(
    color_scheme=ft.ColorScheme(
        surface_container_lowest="#020617",  # Deepest navy background
        surface="#1E293B",                   # Slate-800 surface
        primary="#3B82F6",                   # Blue-500 primary accent
        on_primary="#FFFFFF",
        secondary="#F59E0B",                 # Amber-500 for day shifts
        on_secondary="#000000",
        error="#EF4444",                     # Red-500 for errors/gaps
        on_surface="#E2E8F0",                # Slate-200 text on surface
    ),
)

SHIFT_COLORS = {
    "day": "#FFD966",
    "night": "#4472C4",
    "override": "#EF4444",
}
