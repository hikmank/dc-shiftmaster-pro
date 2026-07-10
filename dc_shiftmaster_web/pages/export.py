"""Export page — CSV, JSON, and Excel browser downloads."""

from __future__ import annotations

import base64
import io
import tempfile

import flet as ft

from dc_shiftmaster.csv_export import CSVExporter, JSONExporter, validate_schedule
from dc_shiftmaster.excel_export import ExcelExporter
from dc_shiftmaster.scheduling import SchedulingEngine
from dc_shiftmaster_web.storage import StorageAdapter


def generate_export_filename(region: str, year: int, ext: str) -> str:
    """Build the export filename: ``{region}_{year}_schedule.{ext}``."""
    region = region or "SITE"
    return f"{region}_{year}_schedule.{ext}"


class ExportPage(ft.Column):
    """Export page with three download buttons (CSV, JSON, Excel).

    Parameters
    ----------
    storage:
        StorageAdapter for reading schedule data.
    engine:
        SchedulingEngine for computing the annual schedule.
    page:
        Flet page reference for snack bars and downloads.
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

        self._csv_btn = ft.Button(
            "Export CSV",
            icon=ft.Icons.TABLE_CHART,
            on_click=self._export_csv,
        )
        self._json_btn = ft.Button(
            "Export JSON",
            icon=ft.Icons.DATA_OBJECT,
            on_click=self._export_json,
        )
        self._excel_btn = ft.Button(
            "Export Excel",
            icon=ft.Icons.GRID_ON,
            on_click=self._export_excel,
        )

        self._progress = ft.ProgressRing(visible=False, width=24, height=24)

        self.controls = [
            ft.Text("Export Schedule", size=24, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Download the current schedule in CSV, JSON, or Excel format.",
                opacity=0.7,
            ),
            ft.Row(
                controls=[self._csv_btn, self._json_btn, self._excel_btn, self._progress],
                spacing=12,
            ),
        ]
        self.spacing = 16

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _set_buttons_disabled(self, disabled: bool) -> None:
        self._csv_btn.disabled = disabled
        self._json_btn.disabled = disabled
        self._excel_btn.disabled = disabled
        self._progress.visible = disabled
        try:
            self._csv_btn.update()
            self._json_btn.update()
            self._excel_btn.update()
            self._progress.update()
        except Exception:
            pass

    def _show_toast(self, message: str) -> None:
        if self._page is None:
            return
        snack = ft.SnackBar(content=ft.Text(message))
        self._page.overlay.append(snack)
        snack.open = True
        self._page.update()

    def _compute_schedule(self):
        """Compute the annual schedule and validate it.

        Returns the schedule list, or None if validation fails.
        """
        year = self._storage.get_year()
        teammates = self._storage.get_teammates()
        shift_windows = self._storage.get_shift_windows()
        overrides = self._storage.get_overrides(year)

        schedule = self._engine.compute_annual_schedule(
            year, teammates, shift_windows, overrides,
        )

        errors = validate_schedule(schedule)
        if errors:
            self._show_toast(errors[0])
            return None
        return schedule

    # ------------------------------------------------------------------ #
    # Export handlers
    # ------------------------------------------------------------------ #

    def _export_csv(self, _e: ft.ControlEvent | None = None) -> None:
        self._set_buttons_disabled(True)
        try:
            schedule = self._compute_schedule()
            if schedule is None:
                return

            # Write to temp file, read back as bytes
            with tempfile.NamedTemporaryFile(
                suffix=".csv", delete=False, mode="w", encoding="ascii"
            ) as tmp:
                tmp_path = tmp.name
            CSVExporter().export(schedule, tmp_path)
            with open(tmp_path, "rb") as f:
                content = f.read()

            filename = generate_export_filename(
                self._storage.get_region(), self._storage.get_year(), "csv"
            )
            self._trigger_download(content, filename, "text/csv")
        except Exception as exc:
            self._show_toast(str(exc))
        finally:
            self._set_buttons_disabled(False)

    def _export_json(self, _e: ft.ControlEvent | None = None) -> None:
        self._set_buttons_disabled(True)
        try:
            schedule = self._compute_schedule()
            if schedule is None:
                return

            with tempfile.NamedTemporaryFile(
                suffix=".json", delete=False, mode="w", encoding="ascii"
            ) as tmp:
                tmp_path = tmp.name
            JSONExporter().export(schedule, tmp_path)
            with open(tmp_path, "rb") as f:
                content = f.read()

            filename = generate_export_filename(
                self._storage.get_region(), self._storage.get_year(), "json"
            )
            self._trigger_download(content, filename, "application/json")
        except Exception as exc:
            self._show_toast(str(exc))
        finally:
            self._set_buttons_disabled(False)

    def _export_excel(self, _e: ft.ControlEvent | None = None) -> None:
        self._set_buttons_disabled(True)
        try:
            schedule = self._compute_schedule()
            if schedule is None:
                return

            year = self._storage.get_year()
            shift_windows = self._storage.get_shift_windows()

            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp_path = tmp.name
            ExcelExporter().export(year, schedule, self._engine, tmp_path, shift_windows)
            with open(tmp_path, "rb") as f:
                content = f.read()

            filename = generate_export_filename(
                self._storage.get_region(), year, "xlsx"
            )
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            self._trigger_download(content, filename, mime)
        except Exception as exc:
            self._show_toast(str(exc))
        finally:
            self._set_buttons_disabled(False)

    def _trigger_download(self, content: bytes, filename: str, mime: str) -> None:
        """Trigger a browser download via data URI."""
        if self._page is None:
            return
        b64 = base64.b64encode(content).decode()
        data_uri = f"data:{mime};base64,{b64}"
        self._page.launch_url(data_uri)
