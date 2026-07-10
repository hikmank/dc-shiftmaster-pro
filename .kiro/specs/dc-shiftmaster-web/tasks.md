# Implementation Plan: DC-ShiftMaster Web

## Overview

Migrate DC-ShiftMaster Pro from CustomTkinter to a Flet web application. The existing backend modules (`models.py`, `scheduling.py`, `csv_export.py`, `excel_export.py`, `validation.py`) are preserved unchanged. A new `dc_shiftmaster_web/` package provides the Flet UI, a `StorageAdapter` replacing SQLite with browser localStorage, and an S3-deployable static build. Tasks follow a bottom-up approach: data layer first, then shared components, then pages, then wiring and deployment.

## Tasks

- [x] 1. Project setup and package structure
  - Create `dc_shiftmaster_web/` directory with `__init__.py`, `main.py`, `storage.py`, `theme.py`
  - Create `dc_shiftmaster_web/pages/` with `__init__.py`, `calendar.py`, `team.py`, `settings.py`, `export.py`
  - Create `dc_shiftmaster_web/components/` with `__init__.py`, `calendar_card.py`, `shift_pill.py`, `header_bar.py`, `nav_rail.py`
  - Add `flet` dependency to project requirements (pyproject.toml or requirements.txt)
  - _Requirements: 1.5, 8.1_

- [x] 2. Implement StorageAdapter
  - [x] 2.1 Create `dc_shiftmaster_web/storage.py` with the `StorageAdapter` class
    - Implement `__init__` accepting a Flet `page` reference, reading from `page.client_storage`
    - Implement default seed data logic: when no `dcshift.shift_windows` key exists, write default day (06:00–18:30) and night (18:00–06:30) windows
    - Implement JSON serialization/deserialization helpers for Teammate, Override, and ShiftWindow
    - Implement `get_teammates`, `add_teammate` (with max-ID-plus-one strategy), `update_teammate`, `delete_teammate`
    - Implement `get_shift_windows`, `update_shift_window`
    - Implement `get_overrides(year)` with year-prefix filtering, `set_override`, `remove_override`
    - Implement `get_year`/`set_year`, `get_region`/`set_region`
    - Reject empty/whitespace-only teammate names with `ValueError`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 5.4_

  - [x] 2.2 Write property test: Teammate serialization round-trip
    - **Property 1: Teammate serialization round-trip**
    - **Validates: Requirements 2.7**

  - [x] 2.3 Write property test: Override serialization round-trip
    - **Property 2: Override serialization round-trip**
    - **Validates: Requirements 2.8**

  - [x] 2.4 Write property test: Shift window serialization round-trip
    - **Property 3: Shift window serialization round-trip**
    - **Validates: Requirements 2.9**

  - [x] 2.5 Write property test: Teammate ID auto-increment
    - **Property 4: Teammate ID auto-increment**
    - **Validates: Requirements 2.5**

  - [x] 2.6 Write property test: Override year filtering
    - **Property 5: Override year filtering**
    - **Validates: Requirements 2.6**

  - [x] 2.7 Write property test: Empty/whitespace name rejection
    - **Property 6: Empty/whitespace name rejection**
    - **Validates: Requirements 5.4**

  - [x] 2.8 Write property test: Teammate add-then-read
    - **Property 7: Teammate add-then-read**
    - **Validates: Requirements 5.3**

  - [x] 2.9 Write property test: Teammate delete-then-read
    - **Property 8: Teammate delete-then-read**
    - **Validates: Requirements 5.7**

- [x] 3. Checkpoint — Verify StorageAdapter
  - Ensure all StorageAdapter tests pass, ask the user if questions arise.

- [x] 4. Theme configuration
  - [x] 4.1 Create `dc_shiftmaster_web/theme.py`
    - Define `DEEPEST_NAVY` theme with `ColorScheme` (background `#020617`, surface `#1E293B`, primary `#3B82F6`, secondary `#F59E0B`, error `#EF4444`)
    - Define `SHIFT_COLORS` dict with day (`#FFD966`), night (`#4472C4`), override (`#EF4444`) color constants
    - _Requirements: 1.1_

- [x] 5. Shared components
  - [x] 5.1 Implement `ShiftPill` component in `dc_shiftmaster_web/components/shift_pill.py`
    - Flet `Chip` subclass color-coded by shift type (day=amber, night=blue)
    - Display teammate name, optional custom start time suffix
    - Override indicator border when `is_override=True`
    - _Requirements: 4.3, 4.7, 4.11_

  - [x] 5.2 Implement `CalendarCard` component in `dc_shiftmaster_web/components/calendar_card.py`
    - Flet `Card` displaying day number, day-of-week abbreviation, "F"/"B" ownership label
    - Contain `ShiftPill` instances for day and night shift teammates
    - `animate_scale` (1.0→1.02) and `animate_opacity` (0.9→1.0) on hover
    - _Requirements: 4.2, 4.3, 4.4, 4.7_

  - [x] 5.3 Implement `HeaderBar` component in `dc_shiftmaster_web/components/header_bar.py`
    - Semi-transparent bar with blur, displaying "DC-ShiftMaster Pro", year, and region
    - _Requirements: 1.3, 3.5_

  - [x] 5.4 Implement `NavigationRail` wrapper in `dc_shiftmaster_web/components/nav_rail.py`
    - Four destinations: Dashboard (calendar icon), Team (people icon), Settings (gear icon), Export (download icon)
    - `on_change` callback for routing
    - _Requirements: 3.1, 3.2, 3.4_

  - [x] 5.5 Write property test: Calendar card count matches days in month
    - **Property 9: Calendar card count matches days in month**
    - **Validates: Requirements 4.1**

  - [x] 5.6 Write property test: Calendar card content correctness
    - **Property 10: Calendar card content correctness**
    - **Validates: Requirements 4.2, 4.3, 4.11**

- [x] 6. Calendar / Dashboard page
  - [x] 6.1 Implement `dc_shiftmaster_web/pages/calendar.py`
    - Render monthly grid of `CalendarCard` components using `ft.ResponsiveRow` with `columns=7`
    - Month navigation (previous/next `IconButton`) and year `Dropdown`
    - Call `SchedulingEngine.compute_annual_schedule()` on year/month change, cache annual schedule
    - Slice cached schedule by month for display
    - _Requirements: 4.1, 4.8, 4.9, 4.10_

  - [x] 6.2 Implement override context menu on CalendarCard
    - Right-click (desktop) / long-press (mobile) gesture detector
    - Dropdown of all teammate names plus "nobody" option
    - Persist override via `StorageAdapter.set_override` and refresh card
    - _Requirements: 4.5, 4.6_

- [x] 7. Team management page
  - [x] 7.1 Implement `dc_shiftmaster_web/pages/team.py`
    - List teammates grouped by shift type (FHD, FHN, BHD, BHN)
    - "Add Teammate" button opening a form with name, shift type dropdown, optional custom start time
    - Validate name (non-empty) and custom start time (`validate_time_format`)
    - Persist via `StorageAdapter.add_teammate`, refresh list
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 7.2 Implement inline edit and delete for teammates
    - Edit icon → inline form pre-populated with current values
    - Delete icon → confirmation dialog, then `StorageAdapter.delete_teammate`
    - _Requirements: 5.6, 5.7_

  - [x] 7.3 Implement CSV import for teammates
    - "Import CSV" button opening `ft.FilePicker` for `.csv` files
    - Parse rows as `name,shift_type[,custom_start]`, skip invalid shift types
    - Display Toast listing skipped row numbers
    - _Requirements: 5.8, 5.9, 5.10_

  - [x] 7.4 Write property test: Teammate grouping by shift type
    - **Property 11: Teammate grouping by shift type**
    - **Validates: Requirements 5.1**

  - [x] 7.5 Write property test: CSV teammate import parsing
    - **Property 12: CSV teammate import parsing**
    - **Validates: Requirements 5.9, 5.10**

- [x] 8. Settings page
  - [x] 8.1 Implement `dc_shiftmaster_web/pages/settings.py`
    - Editable fields for day/night shift start and end times, pre-populated from StorageAdapter
    - Validate with `validate_time_format`, persist via `StorageAdapter.update_shift_window`
    - Region selector dropdown (DC site codes), year selector
    - Persist region/year via StorageAdapter, display Toast on save
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

- [x] 9. Checkpoint — Verify pages render and interact with StorageAdapter
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Export page with browser downloads
  - [x] 10.1 Implement `dc_shiftmaster_web/pages/export.py`
    - Three export buttons: "Export CSV", "Export JSON", "Export Excel"
    - Compute schedule via `SchedulingEngine`, validate with `validate_schedule`
    - On validation failure, display Toast with first error and cancel download
    - Loading indicator on clicked button, disable all buttons during export
    - _Requirements: 7.1, 7.5, 7.6, 7.7_

  - [x] 10.2 Implement in-memory export wrappers
    - Wrap `CSVExporter.export`, `JSONExporter.export`, `ExcelExporter.export` with `tempfile`/`io.BytesIO` buffers
    - Trigger browser download via `page.launch_url` with data URI or Flet download API
    - Filename pattern: `{region}_{year}_schedule.{csv|json|xlsx}`
    - _Requirements: 7.2, 7.3, 7.4, 7.6_

  - [x] 10.3 Write property test: Export filename pattern
    - **Property 13: Export filename pattern**
    - **Validates: Requirements 7.2, 7.3, 7.4**

  - [x] 10.4 Write property test: Invalid schedule blocks export
    - **Property 14: Invalid schedule blocks export**
    - **Validates: Requirements 7.5**

- [x] 11. Main entry point and routing
  - [x] 11.1 Implement `dc_shiftmaster_web/main.py`
    - Flet entry point: `ft.app(target=main, view=ft.AppView.WEB_BROWSER)`
    - Apply `DEEPEST_NAVY` theme, set `theme_mode=DARK`, page title "DC-ShiftMaster Pro"
    - Instantiate `StorageAdapter` and `SchedulingEngine`
    - Build layout: `HeaderBar` at top, `NavigationRail` + content area in a `Row`
    - Route changes swap content area between Calendar, Team, Settings, Export pages
    - Default to Calendar_View on load
    - Handle missing localStorage: display Toast "Browser storage unavailable. Data will not persist between sessions."
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6, 3.3, 3.5_

- [x] 12. Data migration — Import existing teammates.db
  - [x] 12.1 Add "Import Database" section to Settings page
    - "Import Database" button in a migration section on Settings_Page
    - `ft.FilePicker` accepting `.db` files
    - Read binary file, use SQL.js (or `sqlite3` in Flet's Python runtime) to query teammates, shift_windows, overrides tables
    - Write extracted records into StorageAdapter with merge/conflict resolution (imported values win)
    - Display Toast summarizing imported counts or error for invalid files
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 12.2 Write property test: Database import merge with conflict resolution
    - **Property 15: Database import merge with conflict resolution**
    - **Validates: Requirements 10.3, 10.6**

- [x] 13. Responsive design adjustments
  - [x] 13.1 Implement responsive breakpoints
    - NavigationRail: expanded when viewport ≥ 1024px, icon-only or bottom nav when < 1024px
    - Calendar grid: 7-column `ResponsiveRow` at ≥ 768px, single-column list at < 768px
    - CalendarCard: relative sizing, no horizontal scroll at ≥ 360px
    - Use `page.on_resize` or `ResponsiveRow` `col` breakpoints (`xs`, `sm`, `md`)
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 14. S3 deployment setup
  - [x] 14.1 Create build and deploy script
    - Build script running `flet build web` to produce static assets
    - Deploy instructions/script using `aws s3 sync` to upload to S3 bucket with static website hosting
    - Verify `index.html` entry point is present in build output
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 15. Test infrastructure and shared fixtures
  - [x] 15.1 Create `tests/conftest.py` additions and test files
    - Add `MockClientStorage` dict-backed mock for testing StorageAdapter without a browser
    - Add Hypothesis custom strategies: `valid_teammate`, `valid_override`, `valid_shift_windows`, `valid_csv_row`, `whitespace_string`, `valid_year`, `valid_region`
    - Create test file stubs: `tests/test_storage_adapter.py`, `tests/test_calendar_logic.py`, `tests/test_team_logic.py`, `tests/test_export_web.py`, `tests/test_migration.py`
    - _Requirements: 2.7, 2.8, 2.9_

- [x] 16. Final checkpoint — Full integration verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The existing backend modules (`models.py`, `scheduling.py`, `csv_export.py`, `excel_export.py`, `validation.py`) are not modified — only imported by the new web package
