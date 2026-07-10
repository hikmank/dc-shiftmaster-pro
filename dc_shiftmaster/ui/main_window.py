"""Main application window — premium sidebar layout with stats header.

Uses the Midnight Deep theme from theme.py. Sidebar navigation with
icon-only buttons, stats bar at top, and content area for tabs.
"""

import customtkinter as ctk
from datetime import date, datetime

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster.scheduling import SchedulingEngine
from dc_shiftmaster.ui.theme import COLORS, FONTS, SPACING


class MainWindow:
    """Root window with sidebar nav, stats header, and content panels."""

    def __init__(self, root: ctk.CTk, db: DatabaseManager) -> None:
        self.root = root
        self.db = db
        self.engine = SchedulingEngine()

        self.root.minsize(1280, 720)
        self.root.configure(fg_color=COLORS["bg"])

        self._active_page = None
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._pages: dict[str, ctk.CTkFrame] = {}

        self._build_layout()
        self._build_sidebar()
        self._build_stats_header()
        self._build_pages()
        self._show_page("calendar")

    def _build_layout(self) -> None:
        # Sidebar (left)
        self.sidebar = ctk.CTkFrame(
            self.root, width=SPACING["sidebar_width"],
            fg_color=COLORS["sidebar_bg"], corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Right area (header + content)
        self.right = ctk.CTkFrame(self.root, fg_color=COLORS["bg"], corner_radius=0)
        self.right.pack(side="left", fill="both", expand=True)

        # Stats header
        self.header = ctk.CTkFrame(
            self.right, height=SPACING["header_height"],
            fg_color=COLORS["surface"], corner_radius=0)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        # Content area
        self.content = ctk.CTkFrame(self.right, fg_color=COLORS["bg"], corner_radius=0)
        self.content.pack(fill="both", expand=True)

    def _build_sidebar(self) -> None:
        # Logo area
        logo = ctk.CTkLabel(
            self.sidebar, text="SM", font=("Consolas", 18, "bold"),
            text_color=COLORS["primary"], width=SPACING["sidebar_width"])
        logo.pack(pady=(16, 24))

        # Nav buttons
        nav_items = [
            ("calendar", "📅", "Calendar"),
            ("teammates", "👥", "Teammates"),
            ("settings", "⚙", "Settings"),
        ]

        for page_id, icon, tooltip in nav_items:
            btn = ctk.CTkButton(
                self.sidebar, text=icon, width=40, height=40,
                fg_color="transparent", hover_color=COLORS["sidebar_active"],
                text_color=COLORS["sidebar_icon"],
                font=("", 18),
                command=lambda p=page_id: self._show_page(p))
            btn.pack(pady=4)
            self._nav_buttons[page_id] = btn

        # Spacer
        spacer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # DB status indicator
        self.status_dot = ctk.CTkLabel(
            self.sidebar, text="●", font=("", 12),
            text_color=COLORS["success"])
        self.status_dot.pack(pady=(0, 12))

    def _build_stats_header(self) -> None:
        """Build the manager's dashboard stats bar."""
        pad = SPACING["pad_md"]

        # Get current data
        teammates = self.db.get_teammates()
        headcount = len(teammates)
        shift_windows = self.db.get_shift_windows()

        today = date.today()
        owner = self.engine.get_day_owner(today)
        current_shift_label = "Front Half" if owner == "front_half" else "Back Half"

        night_start = shift_windows.get("night")
        handover = night_start.start_time if night_start else "18:00"

        # Stats
        stats = [
            ("HEADCOUNT", str(headcount), COLORS["text"]),
            ("CURRENT ROTATION", current_shift_label,
             COLORS["front_half"] if owner == "front_half" else COLORS["back_half"]),
            ("NEXT HANDOVER", handover, COLORS["secondary"]),
            ("YEAR", str(today.year), COLORS["text_secondary"]),
        ]

        for label_text, value_text, value_color in stats:
            frame = ctk.CTkFrame(self.header, fg_color="transparent")
            frame.pack(side="left", padx=pad, pady=6)

            ctk.CTkLabel(
                frame, text=label_text,
                font=FONTS["stat_label"],
                text_color=COLORS["text_muted"]).pack(anchor="w")
            ctk.CTkLabel(
                frame, text=value_text,
                font=FONTS["stat_value"] if label_text == "NEXT HANDOVER" else FONTS["h3"],
                text_color=value_color).pack(anchor="w")

        # Separator line
        sep = ctk.CTkFrame(self.header, fg_color=COLORS["surface_border"],
                           height=1, corner_radius=0)
        sep.place(relx=0, rely=1.0, relwidth=1, anchor="sw")

    def _build_pages(self) -> None:
        """Create all page frames (lazy-loaded into content area)."""
        from dc_shiftmaster.ui.calendar_tab import CalendarTab
        from dc_shiftmaster.ui.settings_tab import SettingsTab
        from dc_shiftmaster.ui.teammates_tab import TeammatesTab

        # Calendar page
        cal_frame = ctk.CTkFrame(self.content, fg_color=COLORS["bg"], corner_radius=0)
        self.calendar_tab = CalendarTab(cal_frame, self.db)
        self._pages["calendar"] = cal_frame

        # Teammates page
        team_frame = ctk.CTkFrame(self.content, fg_color=COLORS["bg"], corner_radius=0)
        self.teammates_tab = TeammatesTab(
            team_frame, self.db, on_change=self._on_data_change)
        self._pages["teammates"] = team_frame

        # Settings page
        settings_frame = ctk.CTkFrame(self.content, fg_color=COLORS["bg"], corner_radius=0)
        self.settings_tab = SettingsTab(
            settings_frame, self.db, on_change=self._on_data_change)
        self._pages["settings"] = settings_frame

    def _show_page(self, page_id: str) -> None:
        """Switch to the given page, updating sidebar highlights."""
        # Hide current
        if self._active_page and self._active_page in self._pages:
            self._pages[self._active_page].pack_forget()

        # Show new
        self._pages[page_id].pack(fill="both", expand=True)
        self._active_page = page_id

        # Update nav button colors
        for pid, btn in self._nav_buttons.items():
            if pid == page_id:
                btn.configure(
                    fg_color=COLORS["sidebar_active"],
                    text_color=COLORS["sidebar_icon_active"])
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=COLORS["sidebar_icon"])

    def _on_data_change(self) -> None:
        """Called when teammates or settings change — refresh calendar."""
        self.calendar_tab.refresh()
        self._refresh_stats()

    def _refresh_stats(self) -> None:
        """Rebuild the stats header with fresh data."""
        for widget in self.header.winfo_children():
            widget.destroy()
        self._build_stats_header()
