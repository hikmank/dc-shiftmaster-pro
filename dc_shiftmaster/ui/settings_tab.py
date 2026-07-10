"""Settings tab for configuring Day and Night shift windows.

Provides time-entry fields for start/end times of each shift,
validates HH:MM format, persists changes to the database, and
notifies other tabs via an optional callback.
"""

from typing import Callable, Optional

import customtkinter as ctk

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster.validation import validate_time_format


class SettingsTab(ctk.CTkFrame):
    """Shift window configuration UI.

    Displays two sections (Day Shift, Night Shift) each with start/end
    time entry fields. Loads current values from the database on init,
    validates on save, and persists valid changes.

    Args:
        parent: The parent CTk frame (tab content area).
        db: The shared DatabaseManager instance.
        on_change: Optional callback invoked after successful save.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        db: DatabaseManager,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.on_change = on_change
        self.pack(fill="both", expand=True, padx=20, pady=20)

        self._entries: dict[str, ctk.CTkEntry] = {}
        self._error_labels: dict[str, ctk.CTkLabel] = {}

        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        """Construct the form layout with grid-based fields."""
        title = ctk.CTkLabel(self, text="Shift Window Settings", font=("", 20, "bold"))
        title.grid(row=0, column=0, columnspan=3, pady=(0, 20), sticky="w")

        self._build_section("Day Shift", "day", start_row=1)
        self._build_section("Night Shift", "night", start_row=5)

        self.save_btn = ctk.CTkButton(self, text="Save", command=self._on_save, width=120)
        self.save_btn.grid(row=9, column=0, columnspan=3, pady=(20, 0), sticky="w")

    def _build_section(self, label: str, shift_type: str, start_row: int) -> None:
        """Build a labeled section with start/end time entries.

        Args:
            label: Section heading text.
            shift_type: 'day' or 'night' key for entries dict.
            start_row: Grid row to begin placing widgets.
        """
        heading = ctk.CTkLabel(self, text=label, font=("", 16, "bold"))
        heading.grid(row=start_row, column=0, columnspan=3, pady=(10, 5), sticky="w")

        # Start Time
        start_label = ctk.CTkLabel(self, text="Start Time (HH:MM):")
        start_label.grid(row=start_row + 1, column=0, padx=(0, 10), pady=5, sticky="w")

        start_entry = ctk.CTkEntry(self, width=120, placeholder_text="HH:MM")
        start_entry.grid(row=start_row + 1, column=1, pady=5, sticky="w")
        self._entries[f"{shift_type}_start"] = start_entry

        start_err = ctk.CTkLabel(self, text="", text_color="red", font=("", 12))
        start_err.grid(row=start_row + 1, column=2, padx=(10, 0), pady=5, sticky="w")
        self._error_labels[f"{shift_type}_start"] = start_err

        # End Time
        end_label = ctk.CTkLabel(self, text="End Time (HH:MM):")
        end_label.grid(row=start_row + 2, column=0, padx=(0, 10), pady=5, sticky="w")

        end_entry = ctk.CTkEntry(self, width=120, placeholder_text="HH:MM")
        end_entry.grid(row=start_row + 2, column=1, pady=5, sticky="w")
        self._entries[f"{shift_type}_end"] = end_entry

        end_err = ctk.CTkLabel(self, text="", text_color="red", font=("", 12))
        end_err.grid(row=start_row + 2, column=2, padx=(10, 0), pady=5, sticky="w")
        self._error_labels[f"{shift_type}_end"] = end_err

    def _load_values(self) -> None:
        """Populate entries with current shift window values from the database."""
        windows = self.db.get_shift_windows()
        for shift_type in ("day", "night"):
            if shift_type in windows:
                sw = windows[shift_type]
                start_entry = self._entries[f"{shift_type}_start"]
                end_entry = self._entries[f"{shift_type}_end"]
                start_entry.insert(0, sw.start_time)
                end_entry.insert(0, sw.end_time)

    def _on_save(self) -> None:
        """Validate all entries and persist valid changes."""
        # Clear previous errors
        for err_label in self._error_labels.values():
            err_label.configure(text="")

        has_errors = False
        values: dict[str, str] = {}

        for key, entry in self._entries.items():
            value = entry.get().strip()
            is_valid, error_msg = validate_time_format(value)
            if not is_valid:
                self._error_labels[key].configure(text=error_msg)
                has_errors = True
            else:
                values[key] = value

        if has_errors:
            return

        # Persist to database
        self.db.update_shift_window("day", values["day_start"], values["day_end"])
        self.db.update_shift_window("night", values["night_start"], values["night_end"])

        # Notify listeners
        if self.on_change is not None:
            self.on_change()
