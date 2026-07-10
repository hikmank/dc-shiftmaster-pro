"""Flet entry point."""
from __future__ import annotations
import flet as ft
from dc_shiftmaster.scheduling import SchedulingEngine
from dc_shiftmaster_web.components.header_bar import build_header_bar
from dc_shiftmaster_web.components.nav_rail import build_nav_rail
from dc_shiftmaster_web.pages.calendar import CalendarPage
from dc_shiftmaster_web.pages.export import ExportPage
from dc_shiftmaster_web.pages.settings import SettingsPage
from dc_shiftmaster_web.pages.team import TeamPage
from dc_shiftmaster_web.storage import StorageAdapter
from dc_shiftmaster_web.theme import DEEPEST_NAVY


async def main(page: ft.Page) -> None:
    page.title = "DC-ShiftMaster Pro"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = DEEPEST_NAVY

    storage_warning = False
    try:
        storage = await StorageAdapter.async_init(page)
    except Exception:
        storage_warning = True
        storage = StorageAdapter.__new__(StorageAdapter)
        storage._storage = page.shared_preferences
        storage._cache = {}
        storage._async_mode = True
        storage._seed_defaults()

    engine = SchedulingEngine()

    calendar_page = CalendarPage(storage=storage, engine=engine, page=page)
    team_page = TeamPage(storage=storage, page=page)
    settings_page = SettingsPage(storage=storage, page=page)
    export_page = ExportPage(storage=storage, engine=engine, page=page)
    pages = [calendar_page, team_page, settings_page, export_page]

    content_area = ft.Container(content=calendar_page, expand=True)
    header = build_header_bar(year=storage.get_year(), region=storage.get_region())

    def _on_nav_change(e):
        idx = e.control.selected_index
        selected = pages[idx] if idx < len(pages) else calendar_page
        if hasattr(selected, "refresh"):
            selected.refresh()
        content_area.content = selected
        content_area.update()

    nav_rail = build_nav_rail(on_change=_on_nav_change)

    def _on_resize(_e=None):
        width = page.width or 1024
        nav_rail.extended = width >= 1024
        try:
            nav_rail.update()
        except Exception:
            pass

    page.on_resize = _on_resize
    page.add(ft.Column(controls=[header, ft.Row(controls=[nav_rail, content_area], expand=True)], expand=True))
    _on_resize()

    if storage_warning:
        snack = ft.SnackBar(content=ft.Text("Browser storage unavailable. Data will not persist between sessions."), open=True)
        page.overlay.append(snack)
        page.update()


ft.run(main, view=ft.AppView.WEB_BROWSER)
