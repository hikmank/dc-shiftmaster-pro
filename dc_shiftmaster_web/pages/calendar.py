"""Calendar / Dashboard view — monthly grid of CalendarCard components."""

from __future__ import annotations

import calendar
from datetime import date

import flet as ft

from dc_shiftmaster.models import ScheduleSlot
from dc_shiftmaster.scheduling import SchedulingEngine
from dc_shiftmaster_web.components.calendar_card import CalendarCard
from dc_shiftmaster_web.storage import StorageAdapter

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

DAY_ABBRS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class CalendarPage(ft.Column):
    """Monthly calendar grid with navigation and cached annual schedule.

    Parameters
    ----------
    storage:
        StorageAdapter for reading teammates, shift windows, overrides.
    engine:
        SchedulingEngine for computing the annual schedule.
    page:
        Flet page reference for displaying dialogs.
    """

    def __init__(
        self,
        storage: StorageAdapter,
        engine: SchedulingEngine,
        page: ft.Page | None = None,
        **kwargs,
    ):
        super().__init__(expand=True, **kwargs)
        self._storage = storage
        self._engine = engine
        self._page = page

        # Current view state
        today = date.today()
        self._year = storage.get_year() or today.year
        self._month = today.month

        # Cached annual schedule keyed by year
        self._cached_year: int | None = None
        self._cached_schedule: list[ScheduleSlot] = []

        # Build UI controls
        self._month_label = ft.Text(
            self._format_title(), size=20, weight=ft.FontWeight.BOLD
        )

        self._year_dropdown = ft.Dropdown(
            value=str(self._year),
            options=[ft.dropdown.Option(str(y)) for y in range(2000, 2101)],
            width=100,
            on_select=self._on_year_change,
            dense=True,
        )

        nav_row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.CHEVRON_LEFT,
                    tooltip="Previous month",
                    on_click=self._prev_month,
                ),
                self._month_label,
                ft.IconButton(
                    icon=ft.Icons.CHEVRON_RIGHT,
                    tooltip="Next month",
                    on_click=self._next_month,
                ),
                self._year_dropdown,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Grid container — populated by _refresh_grid
        self._grid = ft.ResponsiveRow(columns=7, spacing=4, run_spacing=4)

        self.controls = [nav_row, self._grid]

        # Initial render
        self._refresh_grid()

    # ------------------------------------------------------------------ #
    # Navigation handlers
    # ------------------------------------------------------------------ #

    def _prev_month(self, _e: ft.ControlEvent | None = None) -> None:
        if self._month == 1:
            self._month = 12
            self._year -= 1
            self._year_dropdown.value = str(self._year)
        else:
            self._month -= 1
        self._refresh_grid()

    def _next_month(self, _e: ft.ControlEvent | None = None) -> None:
        if self._month == 12:
            self._month = 1
            self._year += 1
            self._year_dropdown.value = str(self._year)
        else:
            self._month += 1
        self._refresh_grid()

    def _on_year_change(self, e: ft.ControlEvent) -> None:
        self._year = int(e.control.value)
        self._refresh_grid()

    # ------------------------------------------------------------------ #
    # Schedule computation & caching
    # ------------------------------------------------------------------ #

    def _ensure_schedule(self) -> None:
        """Compute and cache the annual schedule if the year changed."""
        if self._cached_year == self._year:
            return
        teammates = self._storage.get_teammates()
        shift_windows = self._storage.get_shift_windows()
        overrides = self._storage.get_overrides(self._year)
        self._cached_schedule = self._engine.compute_annual_schedule(
            self._year, teammates, shift_windows, overrides,
        )
        self._cached_year = self._year

    def _get_month_slots(self) -> dict[int, tuple[ScheduleSlot | None, ScheduleSlot | None]]:
        """Slice the cached schedule by the current month.

        Returns a dict mapping day-of-month → (day_slot, night_slot).
        """
        self._ensure_schedule()
        result: dict[int, tuple[ScheduleSlot | None, ScheduleSlot | None]] = {}
        for slot in self._cached_schedule:
            if slot.date.month != self._month:
                continue
            day_num = slot.date.day
            existing = result.get(day_num, (None, None))
            if slot.shift_type == "day":
                result[day_num] = (slot, existing[1])
            else:
                result[day_num] = (existing[0], slot)
        return result

    # ------------------------------------------------------------------ #
    # Grid rendering
    # ------------------------------------------------------------------ #

    def _refresh_grid(self) -> None:
        """Rebuild the calendar grid for the current month/year."""
        self._month_label.value = self._format_title()
        month_slots = self._get_month_slots()
        num_days = calendar.monthrange(self._year, self._month)[1]

        cards: list[CalendarCard] = []
        for day_num in range(1, num_days + 1):
            d = date(self._year, self._month, day_num)
            day_abbr = DAY_ABBRS[d.weekday()]

            owner = self._engine.get_day_owner(d)
            owner_label = "F" if owner == "front_half" else "B"

            day_slot, night_slot = month_slots.get(day_num, (None, None))

            day_teammates = self._build_teammate_tuples(day_slot)
            night_teammates = self._build_teammate_tuples(night_slot)

            card = CalendarCard(
                day_number=day_num,
                day_abbr=day_abbr,
                owner_label=owner_label,
                day_teammates=day_teammates,
                night_teammates=night_teammates,
                on_override=self._on_override_request,
                col={"xs": 12, "sm": 6, "md": 1},
            )
            cards.append(card)

        self._grid.controls = cards
        try:
            self._grid.update()
            self._month_label.update()
            self._year_dropdown.update()
        except Exception:
            # Controls not yet mounted — initial build, no update needed
            pass

    @staticmethod
    def _build_teammate_tuples(
        slot: ScheduleSlot | None,
    ) -> list[tuple[str, str, bool]]:
        """Convert a ScheduleSlot into (name, custom_start, is_override) tuples."""
        if slot is None:
            return []
        result: list[tuple[str, str, bool]] = []
        for name in slot.teammates:
            custom_start = ""
            if slot.teammate_starts:
                custom_start = slot.teammate_starts.get(name, "")
            result.append((name, custom_start, slot.is_override))
        return result

    def _format_title(self) -> str:
        return f"{MONTH_NAMES[self._month - 1]} {self._year}"

    def invalidate_cache(self) -> None:
        """Force schedule recomputation on next refresh (e.g. after override)."""
        self._cached_year = None

    def refresh(self) -> None:
        """Public method to recompute and re-render the grid."""
        self.invalidate_cache()
        self._refresh_grid()

    # ------------------------------------------------------------------ #
    # Override context menu
    # ------------------------------------------------------------------ #

    def _on_override_request(self, day_number: int, _shift_hint: str) -> None:
        """Handle an override request from a CalendarCard.

        Opens a dialog letting the user pick a shift type (day/night)
        and a teammate (or "nobody") to assign as an override.
        """
        if self._page is None:
            return

        # Build teammate name options
        teammates = self._storage.get_teammates()
        name_options = ["nobody"] + sorted({t.name for t in teammates})

        # State holders for the dialog selections
        selected_shift_type = {"value": "day"}
        selected_name = {"value": "nobody"}

        shift_dropdown = ft.Dropdown(
            label="Shift type",
            value="day",
            options=[
                ft.dropdown.Option("day", "Day shift"),
                ft.dropdown.Option("night", "Night shift"),
            ],
            width=200,
            on_select=lambda e: selected_shift_type.update(value=e.control.value),
        )

        name_dropdown = ft.Dropdown(
            label="Assign to",
            value="nobody",
            options=[ft.dropdown.Option(n) for n in name_options],
            width=200,
            on_select=lambda e: selected_name.update(value=e.control.value),
        )

        date_str = date(self._year, self._month, day_number).isoformat()

        def _on_save(e):
            self._storage.set_override(
                date_str, selected_shift_type["value"], selected_name["value"]
            )
            dlg.open = False
            self._page.update()
            self.refresh()

        def _on_remove(e):
            self._storage.remove_override(date_str, selected_shift_type["value"])
            dlg.open = False
            self._page.update()
            self.refresh()

        def _on_cancel(e):
            dlg.open = False
            self._page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Override — {MONTH_NAMES[self._month - 1]} {day_number}"),
            content=ft.Column(
                controls=[shift_dropdown, name_dropdown],
                tight=True,
                spacing=12,
            ),
            actions=[
                ft.TextButton("Remove override", on_click=_on_remove),
                ft.TextButton("Cancel", on_click=_on_cancel),
                ft.Button("Set override", on_click=_on_save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self._page.overlay.append(dlg)
        dlg.open = True
        self._page.update()
