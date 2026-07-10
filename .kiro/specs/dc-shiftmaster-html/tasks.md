# Implementation Plan: DC-ShiftMaster HTML (Flask + Vanilla JS)

## Overview

Replace the Flet-based web app with a Flask backend serving REST API endpoints and vanilla HTML/CSS/JS static assets. The existing backend modules (`models.py`, `scheduling.py`, `csv_export.py`, `excel_export.py`, `validation.py`, `database.py`) are preserved unchanged. The Flask app wraps `DatabaseManager` and `SchedulingEngine` as shared instances, exposes JSON endpoints, and serves a single-page frontend with client-side view switching.

## Tasks

- [x] 1. Project setup and package structure
  - [x] 1.1 Create `dc_shiftmaster_html/` package directory with `__init__.py`
    - Create `dc_shiftmaster_html/__init__.py`
    - Create `dc_shiftmaster_html/static/` directory for frontend assets
    - Create `dc_shiftmaster_html/static/css/`, `dc_shiftmaster_html/static/js/` subdirectories
    - _Requirements: 1.1, 15.2_

  - [x] 1.2 Create `requirements-html.txt` with Flask and dependencies
    - List Flask, openpyxl, and any other required packages
    - _Requirements: 15.4_

- [x] 2. Flask app factory and configuration
  - [x] 2.1 Create `dc_shiftmaster_html/server.py` with Flask app factory
    - Implement `create_app(db_path, host, port)` factory function
    - Initialize `DatabaseManager` and `SchedulingEngine` as app-level singletons stored on `app.config` or `g`
    - Serve static files from `static/` directory
    - Serve `index.html` on `GET /`
    - Accept command-line arguments or environment variables for host, port, and db path
    - Log the URL on startup (e.g., "Running on http://127.0.0.1:5000")
    - Exit with non-zero status if SQLite database cannot be opened
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 15.1, 15.2, 15.3, 15.5_

  - [x] 2.2 Create `dc_shiftmaster_html/__main__.py` entry point
    - Enable `python -m dc_shiftmaster_html` to start the server
    - Parse CLI args for host, port, db_path
    - _Requirements: 15.1, 15.3_

- [x] 3. Checkpoint — Verify server starts and serves index placeholder
  - Ensure the Flask app starts, serves a placeholder `index.html` on `/`, and logs the URL. Ask the user if questions arise.

- [x] 4. REST API routes — Schedule endpoints
  - [x] 4.1 Implement `GET /api/schedule/{year}/{month}` route
    - Validate year (1900–2100) and month (1–12), return HTTP 400 on invalid input
    - Call `SchedulingEngine.compute_annual_schedule` with teammates, shift windows, and overrides from `DatabaseManager`
    - Filter slots to the requested month
    - Return JSON array with `date`, `shift_type`, `start_time`, `teammates`, `is_override`, `teammate_starts` per slot
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 4.2 Write property test: schedule endpoint returns correct slot count for any valid year/month
    - **Property 9: Calendar card count matches days in month**
    - **Validates: Requirements 2.1**

- [x] 5. REST API routes — Teammate endpoints
  - [x] 5.1 Implement `GET /api/teammates` route
    - Return all teammates as JSON array with `id`, `name`, `shift_type`, `custom_start`
    - _Requirements: 3.1_

  - [x] 5.2 Implement `POST /api/teammates` route
    - Accept JSON body with `name`, `shift_type`, optional `custom_start`
    - Validate name is non-empty, validate `custom_start` with `validate_time_format` if provided
    - Call `DatabaseManager.add_teammate`, return new record with HTTP 201
    - Return HTTP 400 with error message on validation failure
    - _Requirements: 3.2, 3.5, 3.6_

  - [x] 5.3 Implement `PUT /api/teammates/{id}` route
    - Accept JSON body with `name`, `shift_type`, optional `custom_start`
    - Same validation as POST
    - Call `DatabaseManager.update_teammate`, return updated record
    - _Requirements: 3.3, 3.5, 3.6_

  - [x] 5.4 Implement `DELETE /api/teammates/{id}` route
    - Call `DatabaseManager.delete_teammate`, return HTTP 204
    - _Requirements: 3.4_

  - [x] 5.5 Implement `POST /api/teammates/import-csv` route
    - Accept CSV file upload, parse rows as `name,shift_type[,custom_start]`
    - Skip rows with invalid shift types (not FHD, FHN, BHD, BHN)
    - Return JSON summary with `imported_count` and `skipped_rows`
    - _Requirements: 3.7_

  - [ ]* 5.6 Write property test: empty/whitespace name rejection
    - **Property 6: Empty/whitespace name rejection**
    - **Validates: Requirements 3.5**

  - [ ]* 5.7 Write property test: teammate add-then-read consistency
    - **Property 7: Teammate add-then-read**
    - **Validates: Requirements 3.2**

  - [ ]* 5.8 Write property test: teammate delete-then-read consistency
    - **Property 8: Teammate delete-then-read**
    - **Validates: Requirements 3.4**

- [x] 6. REST API routes — Override endpoints
  - [x] 6.1 Implement `GET /api/overrides/{year}` route
    - Return all overrides for the year as JSON array with `date`, `shift_type`, `name`
    - _Requirements: 4.1_

  - [x] 6.2 Implement `POST /api/overrides` route
    - Accept JSON body with `date`, `shift_type`, `name`
    - Call `DatabaseManager.set_override`, return record with HTTP 201
    - _Requirements: 4.2_

  - [x] 6.3 Implement `DELETE /api/overrides` route
    - Accept JSON body with `date` and `shift_type`
    - Call `DatabaseManager.remove_override`, return HTTP 204
    - _Requirements: 4.3_

  - [ ]* 6.4 Write property test: override year filtering
    - **Property 5: Override year filtering**
    - **Validates: Requirements 4.1**

- [x] 7. REST API routes — Settings endpoints
  - [x] 7.1 Implement `GET /api/settings/shift-windows` route
    - Return shift windows as JSON object keyed by "day" and "night"
    - _Requirements: 5.1_

  - [x] 7.2 Implement `PUT /api/settings/shift-windows/{shift_type}` route
    - Accept JSON body with `start_time` and `end_time`
    - Validate both with `validate_time_format`, return HTTP 400 on failure
    - Call `DatabaseManager.update_shift_window` on success
    - _Requirements: 5.2, 5.3_

- [x] 8. REST API routes — Export endpoints
  - [x] 8.1 Implement `GET /api/export/{year}/csv` route
    - Compute annual schedule, validate with `validate_schedule`
    - Write to temp file via `CSVExporter.export`, return as download
    - Filename: `{region}_{year}_schedule.csv` (default region "SITE")
    - Return HTTP 400 if validation fails
    - _Requirements: 6.1, 6.4, 6.5, 6.6_

  - [x] 8.2 Implement `GET /api/export/{year}/json` route
    - Same pattern as CSV using `JSONExporter.export`
    - Filename: `{region}_{year}_schedule.json`
    - _Requirements: 6.2, 6.4, 6.5, 6.6_

  - [x] 8.3 Implement `GET /api/export/{year}/xlsx` route
    - Same pattern using `ExcelExporter.export`
    - Filename: `{region}_{year}_schedule.xlsx`
    - _Requirements: 6.3, 6.4, 6.5, 6.6_

  - [ ]* 8.4 Write property test: export filename pattern
    - **Property 13: Export filename pattern**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.6**

  - [ ]* 8.5 Write property test: invalid schedule blocks export
    - **Property 14: Invalid schedule blocks export**
    - **Validates: Requirements 6.4**

- [x] 9. REST API routes — Database import endpoint
  - [x] 9.1 Implement `POST /api/import-db` route
    - Accept `.db` file upload
    - Open as SQLite, read `teammates`, `shift_windows`, `overrides` tables
    - Merge into active `DatabaseManager`: teammates added with new IDs, shift windows overwritten, overrides with same key take imported values
    - Return JSON summary with `teammates_count`, `shift_windows_count`, `overrides_count`
    - Return HTTP 400 if file is not valid SQLite or lacks expected tables
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 9.2 Write property test: database import merge with conflict resolution
    - **Property 15: Database import merge with conflict resolution**
    - **Validates: Requirements 7.2, 7.3**

- [x] 10. Checkpoint — Verify all API routes work
  - Ensure all REST API endpoints return correct responses. Run existing backend tests plus new API route tests. Ask the user if questions arise.

- [x] 11. Frontend — HTML shell and CSS theme
  - [x] 11.1 Create `dc_shiftmaster_html/static/index.html`
    - Single-page app shell with sidebar nav, header bar, and content area
    - Sidebar with 4 nav items: Dashboard (calendar icon), Team (people icon), Settings (gear icon), Export (download icon)
    - Header bar displaying "DC-ShiftMaster Pro" and year/region
    - Content area placeholder for view switching
    - Link to CSS and JS files
    - _Requirements: 8.1, 8.3, 8.5, 8.6_

  - [x] 11.2 Create `dc_shiftmaster_html/static/css/theme.css`
    - Deepest Navy dark theme: background `#020617`, surface `#1E293B`, primary `#3B82F6`, text `#F8FAFC`
    - Sidebar styles, header bar styles, content area layout
    - Day shift pill color `#FFD966`, night shift pill color `#4472C4`
    - Toast notification styles (success green-tinted, error red-tinted)
    - Responsive breakpoints: sidebar collapse at <1024px, calendar list layout at <768px
    - Relative sizing for day cards (no horizontal scroll at 360px+)
    - Active nav item highlight
    - _Requirements: 8.2, 8.4, 8.7, 9.3, 13.1, 13.2, 13.3, 13.4, 14.3, 14.4_

- [x] 12. Frontend — JavaScript core modules
  - [x] 12.1 Create `dc_shiftmaster_html/static/js/api.js`
    - Fetch wrapper module with functions for all API endpoints
    - `getSchedule(year, month)`, `getTeammates()`, `addTeammate(data)`, `updateTeammate(id, data)`, `deleteTeammate(id)`, `importCsv(file)`
    - `getOverrides(year)`, `setOverride(data)`, `removeOverride(data)`
    - `getShiftWindows()`, `updateShiftWindow(type, data)`
    - `importDb(file)`
    - Error handling: parse JSON error responses
    - _Requirements: 2.1, 3.1–3.7, 4.1–4.3, 5.1–5.3, 6.1–6.3, 7.1_

  - [x] 12.2 Create `dc_shiftmaster_html/static/js/router.js`
    - Client-side view switching without page reload
    - Show/hide view containers based on active nav item
    - Persist active view in URL hash or state
    - _Requirements: 8.4, 8.6_

  - [x] 12.3 Create `dc_shiftmaster_html/static/js/toast.js`
    - Toast notification system
    - Success toasts auto-dismiss after 3 seconds
    - Error toasts auto-dismiss after 5 seconds
    - Bottom-right positioning, vertical stacking
    - Green-tinted success, red-tinted error backgrounds
    - _Requirements: 14.1, 14.2, 14.3, 14.4_

  - [x] 12.4 Create `dc_shiftmaster_html/static/js/state.js`
    - Client-side state management for year and region
    - Read/write `localStorage` for year and region persistence
    - Default year to current calendar year
    - Update header bar display on change
    - _Requirements: 11.4, 11.5_

- [x] 13. Frontend — Dashboard / Calendar view
  - [x] 13.1 Create `dc_shiftmaster_html/static/js/dashboard.js`
    - Fetch schedule for selected year/month and render calendar grid
    - Generate Day_Card elements for each day: day number, day-of-week abbreviation, "F"/"B" label
    - Render Shift_Pill elements per teammate for day and night shifts
    - Day pills colored amber/gold, night pills colored blue
    - Override pills show red border/icon indicator
    - Display custom start time next to teammate name when set
    - Month navigation (prev/next buttons) and year selector
    - Re-fetch and re-render on year/month change
    - Day_Card hover: subtle scale/elevation transition
    - Click Day_Card to open override modal with teammate dropdown + "nobody" option
    - Submit override via POST /api/overrides, refresh calendar
    - Responsive: 7-column grid on desktop, single-column list at <768px
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9, 9.10, 13.3_

  - [ ]* 13.2 Write property test: calendar card count matches days in month
    - **Property 9: Calendar card count matches days in month**
    - **Validates: Requirements 9.1**

  - [ ]* 13.3 Write property test: calendar card content correctness
    - **Property 10: Calendar card content correctness**
    - **Validates: Requirements 9.2, 9.3, 9.9**

- [x] 14. Frontend — Team management page
  - [x] 14.1 Create `dc_shiftmaster_html/static/js/team.js`
    - Fetch teammates and display grouped by shift type (FHD, FHN, BHD, BHN)
    - Show name and custom start time per teammate
    - "Add Teammate" button opens form: name input, shift type select, optional custom start
    - Submit form via POST /api/teammates, refresh list, show toast
    - Display validation errors from API as toast notifications
    - Edit button: inline edit form pre-populated with current values
    - Delete button: confirmation dialog, then DELETE /api/teammates/{id}
    - "Import CSV" button: file input for .csv, upload to POST /api/teammates/import-csv
    - Show import summary toast (imported count, skipped rows)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8_

  - [ ]* 14.2 Write property test: teammate grouping by shift type
    - **Property 11: Teammate grouping by shift type**
    - **Validates: Requirements 10.1**

  - [ ]* 14.3 Write property test: CSV teammate import parsing
    - **Property 12: CSV teammate import parsing**
    - **Validates: Requirements 10.7, 10.8**

- [x] 15. Frontend — Settings page
  - [x] 15.1 Create `dc_shiftmaster_html/static/js/settings.js`
    - Fetch and display editable shift window fields (day start, day end, night start, night end)
    - Save button sends PUT /api/settings/shift-windows/{type}, shows toast on success/error
    - Region text input, year numeric input — persist to localStorage, update header
    - "Import Database" section: file input for .db files
    - Upload to POST /api/import-db, show toast with summary or error
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

- [x] 16. Frontend — Export page
  - [x] 16.1 Create `dc_shiftmaster_html/static/js/export.js`
    - Three export buttons: "Export CSV", "Export JSON", "Export Excel"
    - Each button triggers browser download via navigating to the export endpoint URL
    - Show loading indicator on button while download is in progress
    - Handle error responses: fetch with error check, show toast on failure
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

- [x] 17. Checkpoint — Verify full frontend works end-to-end
  - Ensure all pages render, API calls succeed, toasts display, and navigation works. Ask the user if questions arise.

- [x] 18. Integration wiring and final tests
  - [x] 18.1 Wire `app.py` or `run.py` convenience entry point
    - Create a top-level `run.py` or ensure `python -m dc_shiftmaster_html` works end-to-end
    - Verify static assets are served correctly
    - Verify all API routes are registered
    - _Requirements: 15.1, 15.2_

  - [ ]* 18.2 Write property test: teammate serialization round-trip via API
    - **Property 1: Teammate serialization round-trip**
    - **Validates: Requirements 3.1, 3.2**

  - [ ]* 18.3 Write property test: override serialization round-trip via API
    - **Property 2: Override serialization round-trip**
    - **Validates: Requirements 4.1, 4.2**

  - [ ]* 18.4 Write property test: shift window serialization round-trip via API
    - **Property 3: Shift window serialization round-trip**
    - **Validates: Requirements 5.1, 5.2**

  - [ ]* 18.5 Write property test: teammate ID auto-increment
    - **Property 4: Teammate ID auto-increment**
    - **Validates: Requirements 3.2**

- [x] 19. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- The existing backend modules (`dc_shiftmaster/`) are used as-is — no modifications
- Frontend is vanilla HTML/CSS/JS with no framework dependencies
- Flask serves both the API and static assets from a single process
