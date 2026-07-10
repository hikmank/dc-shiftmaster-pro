"""Teammates tab for managing team members and their shift assignments.

Provides a table view of all teammates with add, edit, and delete
operations. Validates empty names and notifies other tabs via an
optional callback when data changes.
"""

from typing import Callable, Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster.models import Teammate

SHIFT_TYPES = ["FHD", "FHN", "BHD", "BHN"]


class TeammatesTab(ctk.CTkFrame):
    """Teammate management UI with table view and CRUD operations.

    Displays all teammates in a scrollable list with name and shift type
    columns. Provides an add form at the top and inline edit/delete
    buttons per row.

    Args:
        parent: The parent CTk frame (tab content area).
        db: The shared DatabaseManager instance.
        on_change: Optional callback invoked after any add/edit/delete.
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

        self._edit_state: Optional[int] = None  # teammate id being edited
        self._row_widgets: list[list[ctk.CTkBaseClass]] = []

        self._build_ui()
        self._refresh_table()

    def _build_ui(self) -> None:
        """Construct the add form and scrollable teammate table."""
        # --- Title ---
        title = ctk.CTkLabel(self, text="Teammate Management", font=("", 20, "bold"))
        title.grid(row=0, column=0, columnspan=4, pady=(0, 15), sticky="w")

        # --- Add Teammate Form ---
        form_frame = ctk.CTkFrame(self, fg_color="transparent")
        form_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 5))

        name_label = ctk.CTkLabel(form_frame, text="Name:")
        name_label.grid(row=0, column=0, padx=(0, 5), sticky="w")

        self.name_entry = ctk.CTkEntry(form_frame, width=200, placeholder_text="Teammate name")
        self.name_entry.grid(row=0, column=1, padx=(0, 10), sticky="w")

        shift_label = ctk.CTkLabel(form_frame, text="Shift Type:")
        shift_label.grid(row=0, column=2, padx=(0, 5), sticky="w")

        self.shift_menu = ctk.CTkOptionMenu(form_frame, values=SHIFT_TYPES, width=100)
        self.shift_menu.grid(row=0, column=3, padx=(0, 10), sticky="w")

        self.add_btn = ctk.CTkButton(form_frame, text="Add", command=self._on_add, width=80)
        self.add_btn.grid(row=0, column=4, sticky="w")

        self.import_btn = ctk.CTkButton(
            form_frame, text="Import CSV", command=self._on_import, width=100
        )
        self.import_btn.grid(row=0, column=5, padx=(10, 0), sticky="w")

        self.export_teammates_btn = ctk.CTkButton(
            form_frame, text="Export CSV", command=self._on_export_teammates, width=100
        )
        self.export_teammates_btn.grid(row=0, column=6, padx=(5, 0), sticky="w")

        # --- Error label ---
        self.error_label = ctk.CTkLabel(self, text="", text_color="red", font=("", 12))
        self.error_label.grid(row=2, column=0, columnspan=4, sticky="w", pady=(0, 5))

        # --- Table header ---
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(5, 0))

        ctk.CTkLabel(header_frame, text="Name", font=("", 14, "bold"), width=200).grid(
            row=0, column=0, padx=(5, 10), sticky="w"
        )
        ctk.CTkLabel(header_frame, text="Shift Type", font=("", 14, "bold"), width=100).grid(
            row=0, column=1, padx=(0, 10), sticky="w"
        )
        ctk.CTkLabel(header_frame, text="Custom Start", font=("", 14, "bold"), width=100).grid(
            row=0, column=2, padx=(0, 10), sticky="w"
        )
        ctk.CTkLabel(header_frame, text="Actions", font=("", 14, "bold"), width=160).grid(
            row=0, column=3, sticky="w"
        )

        # --- Scrollable teammate list ---
        self.table_frame = ctk.CTkScrollableFrame(self, height=400)
        self.table_frame.grid(row=4, column=0, columnspan=4, sticky="nsew", pady=(5, 0))

        # Let the table expand
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def _clear_error(self) -> None:
        """Clear the error label text."""
        self.error_label.configure(text="")

    def _show_error(self, message: str) -> None:
        """Display an error message below the add form."""
        self.error_label.configure(text=message)

    def _on_add(self) -> None:
        """Handle the Add button click."""
        self._clear_error()
        name = self.name_entry.get().strip()
        shift_type = self.shift_menu.get()

        if not name:
            self._show_error("Name cannot be empty.")
            return

        try:
            self.db.add_teammate(name, shift_type)
        except ValueError as exc:
            self._show_error(str(exc))
            return

        # Clear the form
        self.name_entry.delete(0, "end")
        self._refresh_table()
        self._notify_change()

    def _on_import(self) -> None:
        """Import teammates from a CSV file.

        Expected format: one row per teammate, two columns:
          alias,shift_type
        e.g.:
          jsmith,FHD
          bjones,BHN

        Lines starting with # are treated as comments. Blank lines are skipped.
        If a line has only one column (no comma), it's treated as an alias
        and the user is prompted to assign a default shift type.
        """
        self._clear_error()
        filepath = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt"), ("All files", "*.*")],
            title="Import Teammates from CSV",
        )
        if not filepath:
            return

        try:
            with open(filepath, encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as e:
            self._show_error(f"Cannot read file: {e}")
            return

        added = 0
        skipped = 0
        errors: list[str] = []

        for line_num, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = [p.strip() for p in line.split(",")]
            name = parts[0]

            if not name:
                skipped += 1
                continue

            if len(parts) >= 2 and parts[1].upper() in SHIFT_TYPES:
                shift_type = parts[1].upper()
            else:
                errors.append(f"Line {line_num}: '{line}' — missing or invalid shift type")
                skipped += 1
                continue

            try:
                self.db.add_teammate(name, shift_type)
                added += 1
            except ValueError as exc:
                errors.append(f"Line {line_num}: {exc}")
                skipped += 1

        self._refresh_table()
        if added > 0:
            self._notify_change()

        msg = f"Imported {added} teammate(s)."
        if skipped > 0:
            msg += f"\nSkipped {skipped} line(s)."
        if errors:
            msg += "\n\nErrors:\n" + "\n".join(errors[:10])

        messagebox.showinfo("Import Complete", msg)

    def _on_export_teammates(self) -> None:
        """Export the current teammate list to a CSV file.

        Format: name,shift_type (one per line), e.g.:
          alice,FHD
          bob,BHN
        """
        self._clear_error()
        teammates = self.db.get_teammates()
        if not teammates:
            self._show_error("No teammates to export.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt"), ("All files", "*.*")],
            title="Export Teammates to CSV",
        )
        if not filepath:
            return

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                for t in teammates:
                    f.write(f"{t.name},{t.shift_type}\n")
            messagebox.showinfo(
                "Export Complete",
                f"Exported {len(teammates)} teammate(s) to:\n{filepath}",
            )
        except OSError as e:
            self._show_error(f"Cannot save file: {e}")

    def _refresh_table(self) -> None:
        """Reload teammates from the database and rebuild the table rows."""
        # Destroy existing row widgets
        for row_widgets in self._row_widgets:
            for widget in row_widgets:
                widget.destroy()
        self._row_widgets.clear()
        self._edit_state = None

        teammates = self.db.get_teammates()

        for idx, teammate in enumerate(teammates):
            self._build_row(idx, teammate)

    def _build_row(self, idx: int, teammate: Teammate) -> None:
        """Build a single teammate row in the table.

        Args:
            idx: Row index in the scrollable frame.
            teammate: The Teammate data to display.
        """
        widgets: list[ctk.CTkBaseClass] = []

        name_label = ctk.CTkLabel(self.table_frame, text=teammate.name, width=200, anchor="w")
        name_label.grid(row=idx, column=0, padx=(5, 10), pady=3, sticky="w")
        widgets.append(name_label)

        shift_label = ctk.CTkLabel(self.table_frame, text=teammate.shift_type, width=100, anchor="w")
        shift_label.grid(row=idx, column=1, padx=(0, 10), pady=3, sticky="w")
        widgets.append(shift_label)

        custom_text = teammate.custom_start if teammate.custom_start else "—"
        custom_label = ctk.CTkLabel(self.table_frame, text=custom_text, width=100, anchor="w")
        custom_label.grid(row=idx, column=2, padx=(0, 10), pady=3, sticky="w")
        widgets.append(custom_label)

        btn_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        btn_frame.grid(row=idx, column=3, pady=3, sticky="w")
        widgets.append(btn_frame)

        edit_btn = ctk.CTkButton(
            btn_frame,
            text="Edit",
            width=60,
            command=lambda t=teammate: self._on_edit(t),
        )
        edit_btn.grid(row=0, column=0, padx=(0, 5))

        delete_btn = ctk.CTkButton(
            btn_frame,
            text="Delete",
            width=60,
            fg_color="#d9534f",
            hover_color="#c9302c",
            command=lambda t=teammate: self._on_delete(t),
        )
        delete_btn.grid(row=0, column=1)

        self._row_widgets.append(widgets)

    def _on_edit(self, teammate: Teammate) -> None:
        """Open an edit dialog for the given teammate.

        Args:
            teammate: The Teammate record to edit.
        """
        self._clear_error()
        dialog = _EditDialog(self, teammate)
        self.wait_window(dialog)

        if dialog.result is not None:
            new_name, new_shift, new_custom = dialog.result
            if not new_name.strip():
                self._show_error("Name cannot be empty.")
                return
            try:
                self.db.update_teammate(teammate.id, new_name.strip(), new_shift,
                                        custom_start=new_custom)
            except ValueError as exc:
                self._show_error(str(exc))
                return
            self._refresh_table()
            self._notify_change()

    def _on_delete(self, teammate: Teammate) -> None:
        """Delete a teammate after confirmation.

        Args:
            teammate: The Teammate record to delete.
        """
        self._clear_error()
        dialog = _ConfirmDialog(
            self,
            title="Delete Teammate",
            message=f"Delete '{teammate.name}' ({teammate.shift_type})?",
        )
        self.wait_window(dialog)

        if dialog.confirmed:
            self.db.delete_teammate(teammate.id)
            self._refresh_table()
            self._notify_change()

    def _notify_change(self) -> None:
        """Invoke the on_change callback if set."""
        if self.on_change is not None:
            self.on_change()


class _EditDialog(ctk.CTkToplevel):
    """Modal dialog for editing a teammate's name and shift type.

    Args:
        parent: The parent widget.
        teammate: The Teammate record being edited.
    """

    def __init__(self, parent: ctk.CTkBaseClass, teammate: Teammate) -> None:
        super().__init__(parent)
        self.title("Edit Teammate")
        self.geometry("400x260")
        self.resizable(False, False)
        self.result: Optional[tuple[str, str, str]] = None

        self.transient(parent)
        self.grab_set()

        # Name
        ctk.CTkLabel(self, text="Name:").grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")
        self.name_entry = ctk.CTkEntry(self, width=200)
        self.name_entry.grid(row=0, column=1, padx=(0, 15), pady=(15, 5), sticky="w")
        self.name_entry.insert(0, teammate.name)

        # Shift Type
        ctk.CTkLabel(self, text="Shift Type:").grid(row=1, column=0, padx=15, pady=5, sticky="w")
        self.shift_menu = ctk.CTkOptionMenu(self, values=SHIFT_TYPES, width=120)
        self.shift_menu.grid(row=1, column=1, padx=(0, 15), pady=5, sticky="w")
        self.shift_menu.set(teammate.shift_type)

        # Custom Start Time
        ctk.CTkLabel(self, text="Custom Start:").grid(row=2, column=0, padx=15, pady=5, sticky="w")
        self.custom_entry = ctk.CTkEntry(self, width=120, placeholder_text="HH:MM (optional)")
        self.custom_entry.grid(row=2, column=1, padx=(0, 15), pady=5, sticky="w")
        if teammate.custom_start:
            self.custom_entry.insert(0, teammate.custom_start)

        # Error label
        self.error_label = ctk.CTkLabel(self, text="", text_color="red", font=("", 12))
        self.error_label.grid(row=3, column=0, columnspan=2, padx=15, pady=(5, 0), sticky="w")

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, columnspan=2, pady=15)

        ctk.CTkButton(btn_frame, text="Save", width=80, command=self._on_save).grid(
            row=0, column=0, padx=(0, 10)
        )
        ctk.CTkButton(btn_frame, text="Cancel", width=80, command=self.destroy).grid(
            row=0, column=1
        )

    def _on_save(self) -> None:
        """Validate and store the result."""
        name = self.name_entry.get().strip()
        if not name:
            self.error_label.configure(text="Name cannot be empty.")
            return
        custom = self.custom_entry.get().strip()
        # Validate custom start if provided
        if custom:
            from dc_shiftmaster.validation import validate_time_format
            valid, err = validate_time_format(custom)
            if not valid:
                self.error_label.configure(text=f"Custom start: {err}")
                return
        self.result = (name, self.shift_menu.get(), custom)
        self.destroy()


class _ConfirmDialog(ctk.CTkToplevel):
    """Simple yes/no confirmation dialog.

    Args:
        parent: The parent widget.
        title: Dialog window title.
        message: Confirmation message text.
    """

    def __init__(self, parent: ctk.CTkBaseClass, title: str, message: str) -> None:
        super().__init__(parent)
        self.title(title)
        self.geometry("350x140")
        self.resizable(False, False)
        self.confirmed = False

        self.transient(parent)
        self.grab_set()

        ctk.CTkLabel(self, text=message, wraplength=300).pack(padx=20, pady=(20, 15))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(0, 15))

        ctk.CTkButton(btn_frame, text="Yes", width=80, command=self._on_yes).grid(
            row=0, column=0, padx=(0, 10)
        )
        ctk.CTkButton(btn_frame, text="No", width=80, command=self.destroy).grid(
            row=0, column=1
        )

    def _on_yes(self) -> None:
        """Confirm and close."""
        self.confirmed = True
        self.destroy()
