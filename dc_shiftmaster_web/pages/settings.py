"""Settings page — shift window times, region, year, and database migration."""

from __future__ import annotations

import flet as ft

from dc_shiftmaster.validation import validate_time_format
from dc_shiftmaster_web.migration import import_database
from dc_shiftmaster_web.storage import StorageAdapter

# DC site codes for the region selector
_DC_SITE_CODES = [
    "ATL68",
    "ATL78",
    "CMH68",
    "CMH78",
    "DUB31",
    "IAD77",
    "IAD89",
    "NRT51",
    "PDX1",
    "SFO5",
]

# Year range for the year selector
_YEAR_MIN = 2000
_YEAR_MAX = 2100


class SettingsPage(ft.Column):
    """Settings page for configuring shift windows, region, and year.

    Parameters
    ----------
    storage:
        StorageAdapter for reading/writing settings.
    page:
        Flet page reference for snack bars.
    """

    def __init__(
        self,
        storage: StorageAdapter,
        page: ft.Page | None = None,
        **kwargs,
    ):
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, **kwargs)
        self._storage = storage
        self._page = page

        # --- Shift Windows section ---
        windows = self._storage.get_shift_windows()
        day_win = windows.get("day")
        night_win = windows.get("night")

        self._day_start = ft.TextField(
            label="Day shift start",
            value=day_win.start_time if day_win else "",
            hint_text="HH:MM",
            width=200,
        )
        self._day_end = ft.TextField(
            label="Day shift end",
            value=day_win.end_time if day_win else "",
            hint_text="HH:MM",
            width=200,
        )
        self._night_start = ft.TextField(
            label="Night shift start",
            value=night_win.start_time if night_win else "",
            hint_text="HH:MM",
            width=200,
        )
        self._night_end = ft.TextField(
            label="Night shift end",
            value=night_win.end_time if night_win else "",
            hint_text="HH:MM",
            width=200,
        )

        save_shifts_btn = ft.Button(
            "Save Shift Windows",
            icon=ft.Icons.SAVE,
            on_click=self._save_shift_windows,
        )

        shift_section = ft.Column(
            controls=[
                ft.Text("Shift Windows", size=24, weight=ft.FontWeight.BOLD),
                ft.Row(
                    controls=[self._day_start, self._day_end],
                    spacing=16,
                ),
                ft.Row(
                    controls=[self._night_start, self._night_end],
                    spacing=16,
                ),
                save_shifts_btn,
            ],
            spacing=12,
        )

        # --- Region section ---
        current_region = self._storage.get_region()
        self._region_dropdown = ft.Dropdown(
            label="Region",
            value=current_region if current_region in _DC_SITE_CODES else None,
            options=[ft.dropdown.Option(code) for code in _DC_SITE_CODES],
            width=200,
            on_select=self._on_region_change,
        )

        region_section = ft.Column(
            controls=[
                ft.Text("Region", size=24, weight=ft.FontWeight.BOLD),
                self._region_dropdown,
            ],
            spacing=12,
        )

        # --- Year section ---
        current_year = self._storage.get_year()
        self._year_dropdown = ft.Dropdown(
            label="Year",
            value=str(current_year),
            options=[
                ft.dropdown.Option(str(y))
                for y in range(_YEAR_MIN, _YEAR_MAX + 1)
            ],
            width=200,
            on_select=self._on_year_change,
        )

        year_section = ft.Column(
            controls=[
                ft.Text("Year", size=24, weight=ft.FontWeight.BOLD),
                self._year_dropdown,
            ],
            spacing=12,
        )

        # --- Migration section ---
        import_db_btn = ft.Button(
            "Import Database",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=self._import_database,
        )

        migration_section = ft.Column(
            controls=[
                ft.Text("Data Migration", size=24, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Import an existing teammates.db file from the desktop app.",
                    opacity=0.7,
                ),
                import_db_btn,
            ],
            spacing=12,
        )

        self.controls = [shift_section, region_section, year_section, migration_section]
        self.spacing = 24

    # ------------------------------------------------------------------ #
    # Shift windows save
    # ------------------------------------------------------------------ #

    def _save_shift_windows(self, _e: ft.ControlEvent | None = None) -> None:
        """Validate all four shift window fields and persist if valid."""
        fields = [
            self._day_start,
            self._day_end,
            self._night_start,
            self._night_end,
        ]

        all_valid = True
        for field in fields:
            value = (field.value or "").strip()
            valid, err_msg = validate_time_format(value)
            if not valid:
                field.error_text = err_msg
                all_valid = False
            else:
                field.error_text = None
            try:
                field.update()
            except Exception:
                pass

        if not all_valid:
            return

        # Persist
        day_start = (self._day_start.value or "").strip()
        day_end = (self._day_end.value or "").strip()
        night_start = (self._night_start.value or "").strip()
        night_end = (self._night_end.value or "").strip()

        self._storage.update_shift_window("day", day_start, day_end)
        self._storage.update_shift_window("night", night_start, night_end)

        self._show_toast("Shift windows saved.")

    # ------------------------------------------------------------------ #
    # Region change
    # ------------------------------------------------------------------ #

    def _on_region_change(self, e: ft.ControlEvent) -> None:
        """Persist region selection and show toast."""
        value = e.control.value
        if value:
            self._storage.set_region(value)
            self._show_toast("Region saved.")

    # ------------------------------------------------------------------ #
    # Year change
    # ------------------------------------------------------------------ #

    def _on_year_change(self, e: ft.ControlEvent) -> None:
        """Persist year selection and show toast."""
        value = e.control.value
        if value:
            self._storage.set_year(int(value))
            self._show_toast("Year saved.")

    # ------------------------------------------------------------------ #
    # Database import
    # ------------------------------------------------------------------ #

    def _import_database(self, _e: ft.ControlEvent | None = None) -> None:
        """Open a file picker for .db files and import the selected file."""
        files = ft.FilePicker().pick_files(
            dialog_title="Select teammates.db file",
            allowed_extensions=["db"],
            allow_multiple=False,
        )

        if not files:
            return

        picked = files[0]
        try:
            with open(picked.path, "rb") as fh:
                file_bytes = fh.read()
        except Exception:
            self._show_toast("Could not read the selected file.")
            return

        try:
            summary = import_database(file_bytes, self._storage)
            self._show_toast(summary)
            self.refresh()
        except ValueError as exc:
            self._show_toast(str(exc))

    # ------------------------------------------------------------------ #
    # Toast helper
    # ------------------------------------------------------------------ #

    def _show_toast(self, message: str) -> None:
        """Display a SnackBar toast notification."""
        if self._page is None:
            return
        snack = ft.SnackBar(content=ft.Text(message))
        self._page.overlay.append(snack)
        snack.open = True
        self._page.update()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def refresh(self) -> None:
        """Re-read settings from storage and update field values."""
        windows = self._storage.get_shift_windows()
        day_win = windows.get("day")
        night_win = windows.get("night")

        self._day_start.value = day_win.start_time if day_win else ""
        self._day_end.value = day_win.end_time if day_win else ""
        self._night_start.value = night_win.start_time if night_win else ""
        self._night_end.value = night_win.end_time if night_win else ""

        current_region = self._storage.get_region()
        self._region_dropdown.value = (
            current_region if current_region in _DC_SITE_CODES else None
        )

        self._year_dropdown.value = str(self._storage.get_year())

        try:
            self.update()
        except Exception:
            pass
