"""Team management page — add, edit, delete, and import teammates."""

from __future__ import annotations

import csv
import io
from collections import defaultdict

import flet as ft

from dc_shiftmaster.validation import validate_time_format
from dc_shiftmaster_web.storage import StorageAdapter

# Shift type groups displayed in order
_SHIFT_TYPES = ["FHD", "FHN", "BHD", "BHN"]


def parse_csv_teammates(
    csv_content: str,
) -> tuple[list[tuple[str, str, str]], list[int]]:
    """Parse CSV content into valid teammate rows and skipped row numbers.

    Each row is expected as ``name,shift_type[,custom_start]``.
    Rows whose shift_type is not in ``_SHIFT_TYPES`` are skipped.

    Parameters
    ----------
    csv_content:
        Raw CSV text (may include trailing newlines).

    Returns
    -------
    tuple
        ``(valid_rows, skipped_row_numbers)`` where *valid_rows* is a list of
        ``(name, shift_type, custom_start)`` tuples and *skipped_row_numbers*
        is a 1-indexed list of row numbers that were skipped.
    """
    valid_rows: list[tuple[str, str, str]] = []
    skipped: list[int] = []

    reader = csv.reader(io.StringIO(csv_content))
    for row_idx, row in enumerate(reader, start=1):
        if not row or all(cell.strip() == "" for cell in row):
            skipped.append(row_idx)
            continue

        name = row[0].strip()
        shift_type = row[1].strip() if len(row) > 1 else ""
        custom_start = row[2].strip() if len(row) > 2 else ""

        if shift_type not in _SHIFT_TYPES:
            skipped.append(row_idx)
            continue

        valid_rows.append((name, shift_type, custom_start))

    return valid_rows, skipped


class TeamPage(ft.Column):
    """Team management page listing teammates grouped by shift type.

    Provides an "Add Teammate" button that opens a dialog with name,
    shift type dropdown, and optional custom start time fields.

    Parameters
    ----------
    storage:
        StorageAdapter for reading/writing teammate records.
    page:
        Flet page reference for dialogs and snack bars.
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

        # Container for the grouped teammate list
        self._list_container = ft.Column(spacing=8)

        # CSV import (FilePicker created on demand)

        add_btn = ft.Button(
            "Add Teammate",
            icon=ft.Icons.PERSON_ADD,
            on_click=self._open_add_dialog,
        )

        import_btn = ft.Button(
            "Import CSV",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=self._import_csv,
        )

        header_row = ft.Row(
            controls=[
                ft.Text("Team", size=24, weight=ft.FontWeight.BOLD),
                ft.Row(controls=[add_btn, import_btn], spacing=8),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.controls = [header_row, self._list_container]
        self._refresh_list()

    # ------------------------------------------------------------------ #
    # List rendering
    # ------------------------------------------------------------------ #

    def _refresh_list(self) -> None:
        """Rebuild the teammate list grouped by shift type."""
        teammates = self._storage.get_teammates()

        grouped: dict[str, list] = defaultdict(list)
        for t in teammates:
            grouped[t.shift_type].append(t)

        sections: list[ft.Control] = []
        for st in _SHIFT_TYPES:
            members = grouped.get(st, [])
            section_controls: list[ft.Control] = [
                ft.Text(st, size=18, weight=ft.FontWeight.W_600),
            ]
            if not members:
                section_controls.append(
                    ft.Text("  No teammates", italic=True, opacity=0.5)
                )
            else:
                for t in members:
                    label = t.name
                    if t.custom_start:
                        label += f"  ({t.custom_start})"
                    section_controls.append(
                        ft.Row(
                            controls=[
                                ft.Text(f"  • {label}", expand=True),
                                ft.IconButton(
                                    icon=ft.Icons.EDIT,
                                    icon_size=18,
                                    tooltip="Edit",
                                    data=t.id,
                                    on_click=self._open_edit_dialog,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE,
                                    icon_size=18,
                                    tooltip="Delete",
                                    data=t,
                                    on_click=self._open_delete_dialog,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.START,
                            spacing=0,
                        )
                    )
            sections.append(ft.Column(controls=section_controls, spacing=2))

        self._list_container.controls = sections
        try:
            self._list_container.update()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Add teammate dialog
    # ------------------------------------------------------------------ #

    def _open_add_dialog(self, _e: ft.ControlEvent | None = None) -> None:
        """Open a dialog to add a new teammate."""
        if self._page is None:
            return

        name_field = ft.TextField(label="Name", autofocus=True)
        shift_dropdown = ft.Dropdown(
            label="Shift type",
            value="FHD",
            options=[ft.dropdown.Option(st) for st in _SHIFT_TYPES],
            width=200,
        )
        custom_start_field = ft.TextField(
            label="Custom start time (optional, HH:MM)",
            hint_text="e.g. 07:00",
        )

        def _on_save(_e: ft.ControlEvent) -> None:
            name = (name_field.value or "").strip()
            shift_type = shift_dropdown.value or "FHD"
            custom_start = (custom_start_field.value or "").strip()

            # Validate name
            if not name:
                self._show_toast("Teammate name must not be empty.")
                return

            # Validate custom start time if provided
            if custom_start:
                valid, err_msg = validate_time_format(custom_start)
                if not valid:
                    custom_start_field.error_text = err_msg
                    custom_start_field.update()
                    return

            # Persist
            try:
                self._storage.add_teammate(name, shift_type, custom_start)
            except ValueError as exc:
                self._show_toast(str(exc))
                return

            dlg.open = False
            self._page.update()
            self._refresh_list()

        def _on_cancel(_e: ft.ControlEvent) -> None:
            dlg.open = False
            self._page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add Teammate"),
            content=ft.Column(
                controls=[name_field, shift_dropdown, custom_start_field],
                tight=True,
                spacing=12,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_on_cancel),
                ft.Button("Add", on_click=_on_save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self._page.overlay.append(dlg)
        dlg.open = True
        self._page.update()

    # ------------------------------------------------------------------ #
    # Edit teammate dialog
    # ------------------------------------------------------------------ #

    def _open_edit_dialog(self, e: ft.ControlEvent) -> None:
        """Open a dialog to edit an existing teammate."""
        if self._page is None:
            return

        teammate_id = e.control.data
        teammates = self._storage.get_teammates()
        teammate = next((t for t in teammates if t.id == teammate_id), None)
        if teammate is None:
            return

        name_field = ft.TextField(label="Name", value=teammate.name, autofocus=True)
        shift_dropdown = ft.Dropdown(
            label="Shift type",
            value=teammate.shift_type,
            options=[ft.dropdown.Option(st) for st in _SHIFT_TYPES],
            width=200,
        )
        custom_start_field = ft.TextField(
            label="Custom start time (optional, HH:MM)",
            hint_text="e.g. 07:00",
            value=teammate.custom_start,
        )

        def _on_save(_e: ft.ControlEvent) -> None:
            name = (name_field.value or "").strip()
            shift_type = shift_dropdown.value or teammate.shift_type
            custom_start = (custom_start_field.value or "").strip()

            # Validate name
            if not name:
                self._show_toast("Teammate name must not be empty.")
                return

            # Validate custom start time if provided
            if custom_start:
                valid, err_msg = validate_time_format(custom_start)
                if not valid:
                    custom_start_field.error_text = err_msg
                    custom_start_field.update()
                    return

            # Persist
            try:
                self._storage.update_teammate(teammate_id, name, shift_type, custom_start)
            except ValueError as exc:
                self._show_toast(str(exc))
                return

            dlg.open = False
            self._page.update()
            self._refresh_list()

        def _on_cancel(_e: ft.ControlEvent) -> None:
            dlg.open = False
            self._page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit Teammate"),
            content=ft.Column(
                controls=[name_field, shift_dropdown, custom_start_field],
                tight=True,
                spacing=12,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_on_cancel),
                ft.Button("Save", on_click=_on_save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self._page.overlay.append(dlg)
        dlg.open = True
        self._page.update()

    # ------------------------------------------------------------------ #
    # Delete teammate dialog
    # ------------------------------------------------------------------ #

    def _open_delete_dialog(self, e: ft.ControlEvent) -> None:
        """Open a confirmation dialog to delete a teammate."""
        if self._page is None:
            return

        teammate = e.control.data

        def _on_confirm(_e: ft.ControlEvent) -> None:
            self._storage.delete_teammate(teammate.id)
            dlg.open = False
            self._page.update()
            self._refresh_list()

        def _on_cancel(_e: ft.ControlEvent) -> None:
            dlg.open = False
            self._page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Delete {teammate.name}?"),
            content=ft.Text(
                f"Are you sure you want to delete {teammate.name}? This cannot be undone."
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_on_cancel),
                ft.Button("Delete", on_click=_on_confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self._page.overlay.append(dlg)
        dlg.open = True
        self._page.update()

    # ------------------------------------------------------------------ #
    # CSV import
    # ------------------------------------------------------------------ #

    def _import_csv(self, _e: ft.ControlEvent | None = None) -> None:
        """Open a file picker for .csv files and import the selected file."""
        files = ft.FilePicker().pick_files(
            dialog_title="Select CSV file",
            allowed_extensions=["csv"],
            allow_multiple=False,
        )

        if not files:
            return

        picked = files[0]
        try:
            with open(picked.path, "r", encoding="utf-8") as fh:
                csv_content = fh.read()
        except Exception:
            self._show_toast("Could not read the selected file.")
            return

        valid_rows, skipped = parse_csv_teammates(csv_content)

        imported_count = 0
        for name, shift_type, custom_start in valid_rows:
            try:
                self._storage.add_teammate(name, shift_type, custom_start)
                imported_count += 1
            except ValueError:
                pass  # skip names that fail validation (e.g. empty after strip)

        # Build toast message
        if skipped:
            msg = (
                f"Imported {imported_count} teammates. "
                f"Skipped rows: {', '.join(str(r) for r in skipped)}"
            )
        else:
            msg = f"Imported {imported_count} teammates."

        self._show_toast(msg)
        self._refresh_list()

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
        """Public method to re-render the teammate list."""
        self._refresh_list()
