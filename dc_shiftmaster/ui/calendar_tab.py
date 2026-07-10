"""Calendar tab — month-at-a-time view with large readable cells.

Renders one month at a time in a proper Sun–Sat grid with day/night
shift slots, headcount badges, and right-click override support.
Uses a tkinter Canvas for performance.
"""

import calendar
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from dc_shiftmaster.csv_export import CSVExporter, JSONExporter, validate_schedule
from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster.excel_export import ExcelExporter
from dc_shiftmaster.models import ScheduleSlot
from dc_shiftmaster.scheduling import SchedulingEngine
from dc_shiftmaster.ui.toast import show_toast

# Colors — pulled from theme
from dc_shiftmaster.ui.theme import COLORS, FONTS, SPACING

DAY_COLOR = COLORS["day_shift"]
NIGHT_COLOR = COLORS["night_shift"]
NOBODY_BG = COLORS["nobody_bg"]
NOBODY_FG = COLORS["nobody_fg"]
OVERRIDE_BORDER = COLORS["override_border"]
CELL_BG = COLORS["surface"]
CELL_BORDER = COLORS["surface_border"]
TODAY_BORDER = COLORS["today_border"]
HEADER_BG = COLORS["surface"]
HEADER_FG = COLORS["text_secondary"]
CANVAS_BG = COLORS["canvas_bg"]
WHITE = COLORS["text"]
MUTED = COLORS["text_muted"]
FRONT_COLOR = COLORS["front_half"]
BACK_COLOR = COLORS["back_half"]
WARNING_GLOW = COLORS["warning"]

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
WEEKDAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday",
                 "Thursday", "Friday", "Saturday"]

COLS = 7


class CalendarTab(ctk.CTkFrame):
    """Month-at-a-time calendar with day/night shift pills."""

    def __init__(self, parent, db: DatabaseManager,
                 on_change: Optional[Callable[[], None]] = None) -> None:
        super().__init__(parent, fg_color=COLORS["bg"])
        self.db = db
        self.on_change = on_change
        self.engine = SchedulingEngine()
        self.year = date.today().year
        self.month = date.today().month
        self.schedule: list[ScheduleSlot] = []
        self._slot_lookup: dict[tuple[str, str], ScheduleSlot] = {}
        self._item_to_slot: dict[int, tuple[str, str]] = {}

        self.pack(fill="both", expand=True)
        self._build_ui()
        self.refresh()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Top bar: navigation + exports
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8, 4))

        # Year nav
        ctk.CTkButton(top, text="◀◀", width=32,
                       command=self._prev_year).pack(side="left", padx=(4, 0))
        # Month nav
        ctk.CTkButton(top, text="◀", width=32,
                       command=self._prev_month).pack(side="left", padx=(4, 0))

        self.title_label = ctk.CTkLabel(top, text="", font=("", 20, "bold"))
        self.title_label.pack(side="left", padx=8)

        ctk.CTkButton(top, text="▶", width=32,
                       command=self._next_month).pack(side="left", padx=(0, 4))
        ctk.CTkButton(top, text="▶▶", width=32,
                       command=self._next_year).pack(side="left", padx=(0, 4))

        ctk.CTkButton(top, text="Today", width=60,
                       command=self._go_today).pack(side="left", padx=8)

        # Export buttons (right side)
        for label, cmd in [("Excel", self._export_excel),
                           ("JSON", self._export_json),
                           ("CSV", self._export_csv)]:
            ctk.CTkButton(top, text=label, width=60,
                           command=cmd).pack(side="right", padx=3)

        # Canvas
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.canvas = tk.Canvas(frame, bg=CANVAS_BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-3>", self._on_right_click)

    # ── Navigation ───────────────────────────────────────────────────

    def _prev_year(self):
        self.year -= 1
        self.refresh()

    def _next_year(self):
        self.year += 1
        self.refresh()

    def _prev_month(self):
        if self.month == 1:
            self.month = 12
            self.year -= 1
        else:
            self.month -= 1
        self.refresh()

    def _next_month(self):
        if self.month == 12:
            self.month = 1
            self.year += 1
        else:
            self.month += 1
        self.refresh()

    def _go_today(self):
        today = date.today()
        self.year = today.year
        self.month = today.month
        self.refresh()

    # ── Data ─────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self.title_label.configure(
            text=f"{MONTH_NAMES[self.month - 1]} {self.year}")
        self._compute_schedule()
        self._render()

    def _compute_schedule(self) -> None:
        teammates = self.db.get_teammates()
        shift_windows = self.db.get_shift_windows()
        overrides = self.db.get_overrides(self.year)
        self.schedule = self.engine.compute_annual_schedule(
            self.year, teammates, shift_windows, overrides)
        self._slot_lookup.clear()
        for slot in self.schedule:
            self._slot_lookup[(slot.date.isoformat(), slot.shift_type)] = slot

    # ── Rendering ────────────────────────────────────────────────────

    def _on_resize(self, _event=None):
        self._render()

    def _render(self) -> None:
        self.canvas.delete("all")
        self._item_to_slot.clear()

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 100 or ch < 100:
            return

        col_w = cw // COLS
        header_h = 28
        today = date.today()

        # Weekday headers
        for i, name in enumerate(WEEKDAY_NAMES):
            x = i * col_w
            self.canvas.create_rectangle(
                x, 0, x + col_w, header_h,
                fill=HEADER_BG, outline=CELL_BORDER)
            self.canvas.create_text(
                x + col_w // 2, header_h // 2,
                text=name, fill=HEADER_FG, font=("", 10, "bold"))

        # Compute grid
        num_days = calendar.monthrange(self.year, self.month)[1]
        first_wday = (calendar.weekday(self.year, self.month, 1) + 1) % 7
        num_rows = (first_wday + num_days + 6) // 7
        row_h = max((ch - header_h) // num_rows, 60)

        for day_num in range(1, num_days + 1):
            d = date(self.year, self.month, day_num)
            col = (first_wday + day_num - 1) % 7
            row = (first_wday + day_num - 1) // 7
            x = col * col_w
            y = header_h + row * row_h
            is_today = (d == today)
            self._draw_cell(x, y, col_w, row_h, d, is_today)

    def _draw_cell(self, x, y, w, h, d, is_today) -> None:
        date_iso = d.isoformat()

        # Check if any slot has "nobody" for amber glow
        day_slot = self._slot_lookup.get((date_iso, "day"))
        night_slot = self._slot_lookup.get((date_iso, "night"))
        day_names = day_slot.teammates if day_slot else ["nobody"]
        night_names = night_slot.teammates if night_slot else ["nobody"]
        has_nobody = day_names == ["nobody"] or night_names == ["nobody"]

        # Cell border
        if is_today:
            border_color = TODAY_BORDER
            border_w = 2
        elif has_nobody:
            border_color = WARNING_GLOW
            border_w = 1
        else:
            border_color = CELL_BORDER
            border_w = 1

        self.canvas.create_rectangle(
            x, y, x + w, y + h,
            fill=CELL_BG, outline=border_color, width=border_w)

        # Date number
        self.canvas.create_text(
            x + 4, y + 3, text=str(d.day),
            fill=WHITE if is_today else MUTED,
            font=("", 11, "bold"), anchor="nw")

        # Owner badge (F/B)
        owner = self.engine.get_day_owner(d)
        badge = "F" if owner == "front_half" else "B"
        badge_color = "#5b9a3a" if owner == "front_half" else "#b8860b"
        self.canvas.create_text(
            x + w - 6, y + 3, text=badge,
            fill=badge_color, font=("", 9, "bold"), anchor="ne")

        # Slots area starts below date row
        slot_y = y + 20
        slot_w = w - 8
        slot_x = x + 4
        available_h = h - 24
        half_h = available_h // 2 - 1

        # Day slot
        self._draw_slot(slot_x, slot_y, slot_w, half_h,
                         date_iso, "day", "D")

        # Night slot
        self._draw_slot(slot_x, slot_y + half_h + 2, slot_w, half_h,
                         date_iso, "night", "N")

    def _draw_slot(self, x, y, w, h, date_iso, shift_type, prefix) -> None:
        slot = self._slot_lookup.get((date_iso, shift_type))
        names = slot.teammates if slot else ["nobody"]
        is_nobody = names == ["nobody"]
        is_override = slot.is_override if slot else False
        count = 0 if is_nobody else len(names)

        bg = NOBODY_BG if is_nobody else (
            COLORS["day_shift_bg"] if shift_type == "day" else COLORS["night_shift_bg"])
        fg = NOBODY_FG if is_nobody else (DAY_COLOR if shift_type == "day" else NIGHT_COLOR)
        outline = OVERRIDE_BORDER if is_override else ""

        r = self.canvas.create_rectangle(
            x, y, x + w, y + h,
            fill=bg, outline=outline, width=2 if is_override else 0)
        self._item_to_slot[r] = (date_iso, shift_type)

        # Header line: "D(2)" or "N(0)"
        header = f"{prefix}({count})"
        t0 = self.canvas.create_text(
            x + 3, y + 2, text=header,
            fill=fg, font=("", 8, "bold"), anchor="nw")
        self._item_to_slot[t0] = (date_iso, shift_type)

        # Name lines (fit as many as space allows)
        line_h = 12
        max_lines = max((h - 14) // line_h, 1)
        custom_starts = slot.teammate_starts if slot else {}
        for i, name in enumerate(names[:max_lines]):
            display = name
            # Show custom start time if this person has one
            if name in custom_starts:
                display = f"{name} @{custom_starts[name]}"
            if i == max_lines - 1 and len(names) > max_lines:
                display = f"{display} +{len(names) - max_lines}"
            t = self.canvas.create_text(
                x + 3, y + 14 + i * line_h,
                text=display, fill=fg, font=("", 8), anchor="nw")
            self._item_to_slot[t] = (date_iso, shift_type)

    # ── Right-click override ─────────────────────────────────────────

    def _on_right_click(self, event) -> None:
        item = self.canvas.find_closest(event.x, event.y)
        if not item:
            return
        slot_key = self._item_to_slot.get(item[0])
        if not slot_key:
            return

        date_iso, shift_type = slot_key
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Set Override...",
                         command=lambda: self._prompt_override(date_iso, shift_type))
        menu.add_command(label="Set to nobody",
                         command=lambda: self._set_override(date_iso, shift_type, "nobody"))

        slot = self._slot_lookup.get((date_iso, shift_type))
        if slot and slot.is_override:
            menu.add_separator()
            menu.add_command(label="Remove Override",
                             command=lambda: self._remove_override(date_iso, shift_type))

        menu.tk_popup(event.x_root, event.y_root)

    def _prompt_override(self, date_iso, shift_type) -> None:
        dialog = ctk.CTkInputDialog(
            text=f"Enter replacement name for {shift_type} shift on {date_iso}:",
            title="Set Override")
        name = dialog.get_input()
        if name and name.strip():
            self._set_override(date_iso, shift_type, name.strip())

    def _set_override(self, date_iso, shift_type, name) -> None:
        self.db.set_override(date_iso, shift_type, name)
        self.refresh()

    def _remove_override(self, date_iso, shift_type) -> None:
        self.db.remove_override(date_iso, shift_type)
        self.refresh()

    # ── Exports ──────────────────────────────────────────────────────

    def _export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
            title="Export CSV")
        if not path:
            return
        try:
            CSVExporter().export(self.schedule, path)
            show_toast(self.winfo_toplevel(), f"CSV saved → {path}", "success")
        except (ValueError, OSError) as e:
            show_toast(self.winfo_toplevel(), str(e), "error", 5000)

    def _export_json(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            title="Export JSON")
        if not path:
            return
        try:
            JSONExporter().export(self.schedule, path)
            show_toast(self.winfo_toplevel(), f"JSON saved → {path}", "success")
        except (ValueError, OSError) as e:
            show_toast(self.winfo_toplevel(), str(e), "error", 5000)

    def _export_excel(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("All", "*.*")],
            title="Export Excel")
        if not path:
            return
        try:
            sw = self.db.get_shift_windows()
            ExcelExporter().export(self.year, self.schedule, self.engine, path,
                                   shift_windows=sw)
            show_toast(self.winfo_toplevel(), f"Excel saved → {path}", "success")
        except OSError as e:
            show_toast(self.winfo_toplevel(), str(e), "error", 5000)

    def get_slot(self, date_iso, shift_type) -> Optional[ScheduleSlot]:
        return self._slot_lookup.get((date_iso, shift_type))
