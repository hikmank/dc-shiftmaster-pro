# Implementation Plan: DC-ShiftMaster Pro

## Overview

Build a desktop Python application for 14-day shift rotation scheduling with CustomTkinter UI, SQLite persistence, and CSV export in Custom Upload format. Implementation proceeds bottom-up: data models → database → scheduling engine → CSV exporter → UI tabs → integration and wiring.

## Tasks

- [x] 1. Set up project structure and data models
  - [x] 1.1 Create the `dc_shiftmaster/` package directory structure with `__init__.py` files
    - Create `dc_shiftmaster/`, `dc_shiftmaster/ui/`, and `tests/` directories
    - Create `dc_shiftmaster/requirements.txt` with dependencies: `customtkinter`, `hypothesis`, `pytest`, `pyinstaller`
    - _Requirements: 9.2, 10.1_
  - [x] 1.2 Implement data model classes in `dc_shiftmaster/models.py`
    - Define `ShiftWindow`, `Teammate`, `Override`, and `ScheduleSlot` dataclasses
    - Include type annotations and docstrings matching the design document
    - _Requirements: 1.1, 2.1, 5.2_

- [x] 2. Implement DatabaseManager
  - [x] 2.1 Create `dc_shiftmaster/database.py` with SQLite schema initialization
    - Implement `DatabaseManager.__init__` that creates/opens `teammates.db`
    - Create `shift_windows`, `teammates`, and `overrides` tables per the design schema
    - Seed default shift windows (day: 06:00–18:30, night: 18:00–06:30) on first run
    - _Requirements: 8.1, 8.3, 1.2_
  - [x] 2.2 Implement shift window CRUD methods
    - `get_shift_windows()` → returns dict of ShiftWindow objects
    - `update_shift_window(shift_type, start, end)` → persists updated times
    - _Requirements: 1.1, 1.3_
  - [x] 2.3 Implement teammate CRUD methods
    - `get_teammates()`, `add_teammate(name, shift_type)`, `update_teammate(id, name, shift_type)`, `delete_teammate(id)`
    - Validate non-empty name before insert/update
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 2.4 Implement override CRUD methods
    - `get_overrides(year)`, `set_override(date, shift_type, name)`, `remove_override(date, shift_type)`
    - _Requirements: 5.2, 5.5, 5.6_
  - [x] 2.5 Write property tests for DatabaseManager (`tests/test_database.py`)
    - **Property 1: Shift window storage round-trip**
    - **Property 3: Teammate CRUD round-trip**
    - **Property 4: Empty name rejection**
    - **Property 8: Override storage round-trip**
    - **Property 15: Database state round-trip**
    - **Validates: Requirements 1.1, 1.3, 2.1, 2.2, 2.3, 2.5, 5.2, 5.5, 8.2**

- [x] 3. Implement input validation
  - [x] 3.1 Create time format validation in `dc_shiftmaster/database.py` or a shared utility
    - Validate HH:MM 24-hour format (hours 00-23, minutes 00-59)
    - Return clear error messages for invalid input
    - _Requirements: 1.5_
  - [x] 3.2 Add empty-name validation to teammate operations
    - Reject names that are empty or whitespace-only
    - _Requirements: 2.5_
  - [x] 3.3 Write property tests for validation (`tests/test_validation.py`)
    - **Property 2: Time format validation**
    - **Property 4: Empty name rejection** (if not covered in 2.5)
    - **Validates: Requirements 1.5, 2.5**

- [x] 4. Checkpoint — Ensure data layer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement SchedulingEngine
  - [x] 5.1 Create `dc_shiftmaster/scheduling.py` with cycle computation
    - Implement `get_cycle_day(date)` — returns 0-based index within the 14-day cycle from Jan 1
    - Implement `get_day_owner(date)` — returns 'front_half' or 'back_half' based on cycle day (0-3, 7-9 → front; 4-6, 10-13 → back)
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - [x] 5.2 Implement `compute_annual_schedule` method
    - Generate 2 ScheduleSlots per day (Day then Night) for the full year
    - Map front_half → FHD/FHN teammates, back_half → BHD/BHN teammates
    - Use "nobody" when no teammate is assigned for a shift type
    - Apply overrides on top of computed assignments
    - _Requirements: 3.5, 3.6, 3.7, 4.3, 4.4, 5.3, 5.6_
  - [x] 5.3 Write property tests for SchedulingEngine (`tests/test_scheduling.py`)
    - **Property 6: 14-day cycle ownership correctness**
    - **Property 7: Shift type teammate assignment**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.4**
  - [x] 5.4 Write property tests for overrides (`tests/test_overrides.py`)
    - **Property 9: Override takes precedence over computed assignment**
    - **Property 10: Override removal reverts to computed assignment**
    - **Property 5: Deleted teammate becomes "nobody"**
    - **Validates: Requirements 2.4, 5.3, 5.4, 5.6, 6.7**

- [x] 6. Implement CSVExporter
  - [x] 6.1 Create `dc_shiftmaster/csv_export.py` with export logic
    - Implement `format_datetime(date, time_str)` — format as `M/D/YYYY H:MM` with no leading zeros
    - Implement `export(schedule, filepath)` — write headerless two-column CSV, Day then Night per day, chronological order
    - Handle non-writable path with `OSError`/`PermissionError` and raise descriptive error
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.10_
  - [x] 6.2 Implement `parse_csv_row` for round-trip verification
    - Parse `M/D/YYYY H:MM,name` back into (date, time, teammate_name)
    - _Requirements: 7.1_
  - [x] 6.3 Write property tests for CSVExporter (`tests/test_csv_export.py`)
    - **Property 11: CSV structural invariants**
    - **Property 12: CSV date format — no leading zeros**
    - **Property 13: CSV chronological ordering with day-before-night**
    - **Property 14: CSV export/parse round-trip**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.5, 6.6, 7.1, 7.2**

- [x] 7. Checkpoint — Ensure all core logic tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement shared test fixtures
  - [x] 8.1 Create `tests/conftest.py` with Hypothesis strategies and pytest fixtures
    - Implement `valid_time()`, `invalid_time()`, `valid_teammate()`, `valid_override()`, `valid_year()` strategies
    - Create a fixture for an in-memory or temp-file DatabaseManager
    - _Requirements: 7.2_

- [x] 9. Implement MainWindow and tabbed layout
  - [x] 9.1 Create `dc_shiftmaster/main.py` entry point
    - Initialize CustomTkinter app with dark theme
    - Instantiate DatabaseManager and pass to MainWindow
    - _Requirements: 10.1, 8.2_
  - [x] 9.2 Create `dc_shiftmaster/ui/main_window.py` with tabbed interface
    - Create CTkTabview with Settings, Teammates, and Calendar tabs
    - Set minimum window size to 1280×720
    - Wire tab instances to shared DatabaseManager
    - _Requirements: 10.2, 10.3_

- [x] 10. Implement Settings Tab
  - [x] 10.1 Create `dc_shiftmaster/ui/settings_tab.py`
    - Two time-entry pairs (start/end) for Day and Night shift windows
    - Load current values from DatabaseManager on init
    - Validate HH:MM format on save with inline error display
    - Persist valid changes to database via DatabaseManager
    - Provide a callback/event to notify Calendar tab of changes
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 11. Implement Teammates Tab
  - [x] 11.1 Create `dc_shiftmaster/ui/teammates_tab.py`
    - Table view displaying all teammates (name + shift type)
    - Add teammate form with name entry and shift type dropdown (FHD, FHN, BHD, BHN)
    - Edit and delete buttons per row
    - Empty-name validation with error display
    - Provide a callback/event to notify Calendar tab of changes
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 12. Implement Calendar Tab
  - [x] 12.1 Create `dc_shiftmaster/ui/calendar_tab.py` with yearly grid
    - Render a scrollable grid for the full year (Jan 1 – Dec 31)
    - Each cell shows two slots: Day (color-coded) and Night (color-coded)
    - Auto-populate slots using SchedulingEngine
    - Display "nobody" for unassigned slots
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6_
  - [x] 12.2 Implement year navigation
    - Year selector control to switch between years
    - Recompute schedule via SchedulingEngine on year change
    - _Requirements: 4.5, 3.7_
  - [x] 12.3 Implement right-click override context menu
    - Right-click on a slot opens context menu with name entry and "nobody" option
    - Store override via DatabaseManager on confirm
    - Remove override option to revert to computed assignment
    - Refresh the affected slot display after override change
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  - [x] 12.4 Implement "Generate & Export" button
    - Trigger CSVExporter with current schedule
    - Show file save dialog for export path
    - Display confirmation message with file path on success
    - Display error message if path is not writable
    - _Requirements: 6.1, 6.8, 6.9, 6.10_

- [x] 13. Wire components together and integrate refresh logic
  - [x] 13.1 Connect Settings tab changes to Calendar tab refresh
    - When shift windows are updated, re-render calendar within 2 seconds
    - _Requirements: 1.4_
  - [x] 13.2 Connect Teammates tab changes to Calendar tab refresh
    - When teammates are added/edited/deleted, refresh calendar slots
    - Deleted teammates show as "nobody" in affected slots
    - _Requirements: 2.2, 2.3, 2.4_
  - [x] 13.3 Ensure overrides persist across year changes and recomputation
    - Overrides for the same year are preserved when schedule is recomputed
    - _Requirements: 5.6_

- [x] 14. Checkpoint — Ensure full application runs and all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Desktop packaging setup
  - [x] 15.1 Create `dc_shiftmaster/build.bat` PyInstaller build script
    - Configure PyInstaller for single-file Windows executable
    - Include CustomTkinter assets in the bundle
    - _Requirements: 9.1, 9.3_

- [x] 16. Final checkpoint — Verify complete application
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional property-based test sub-tasks and can be skipped for faster MVP
- Each task references specific requirement clauses for traceability
- The implementation proceeds bottom-up: models → database → engine → exporter → UI → wiring
- All 15 correctness properties from the design are covered by optional test tasks
- Checkpoints at tasks 4, 7, 14, and 16 ensure incremental validation
