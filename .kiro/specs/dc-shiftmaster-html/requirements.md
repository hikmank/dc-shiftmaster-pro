# Requirements Document

## Introduction

DC-ShiftMaster Pro is a shift rotation management tool for AWS data center sites. The current Flet-based web application (`dc_shiftmaster_web/`) suffers from compatibility issues with Flet 0.84 and is being replaced by a vanilla HTML/CSS/JS frontend backed by a Python web server (Flask or FastAPI). The existing backend modules — `models.py`, `scheduling.py`, `csv_export.py`, `excel_export.py`, `validation.py`, and `DatabaseManager` — are preserved unchanged and exposed through a REST API. The frontend uses the "Deepest Navy" dark theme (`#020617` background, `#1E293B` surface) and communicates with the server via JSON endpoints. The application is deployable as a single Python process serving both the API and static assets.

## Glossary

- **Web_Server**: The Python web server (Flask or FastAPI) that serves the REST API and static HTML/CSS/JS assets.
- **REST_API**: The set of HTTP JSON endpoints exposed by the Web_Server for CRUD operations on teammates, shift windows, overrides, schedules, and exports.
- **Frontend**: The vanilla HTML/CSS/JS single-page application rendered in the browser, communicating with the REST_API via `fetch` calls.
- **Dashboard_View**: The calendar page displaying the monthly shift schedule grid with day cards showing teammate assignments.
- **Team_Page**: The page for managing teammate records (add, edit, delete, CSV import).
- **Settings_Page**: The page for configuring shift window times, year, region, and importing legacy `.db` files.
- **Export_Page**: The page for triggering CSV, JSON, and Excel schedule exports as browser downloads.
- **Database_Manager**: The existing `DatabaseManager` class providing SQLite persistence for teammates, shift windows, and overrides on the server side.
- **Scheduling_Engine**: The existing `SchedulingEngine` class computing the deterministic 14-day shift rotation cycle.
- **Day_Card**: An HTML element representing a single day in the calendar grid, containing shift assignment pills and date metadata.
- **Shift_Pill**: An inline HTML element within a Day_Card showing a teammate name, color-coded by shift type (day or night).
- **Toast_Notification**: A transient message element displayed to the user for feedback on actions (success, error, validation).
- **Override**: A manual per-slot assignment replacing the computed teammate for a specific date and shift type.
- **Front_Half**: The shift group owning cycle days 0–3 and 7–9 within the 14-day rotation.
- **Back_Half**: The shift group owning cycle days 4–6 and 10–13 within the 14-day rotation.

## Requirements

### Requirement 1: Python Web Server and Static Asset Serving

**User Story:** As a DC employee, I want to run a single Python command to start the application, so that I can access the shift scheduler from any browser without complex setup.

#### Acceptance Criteria

1. THE Web_Server SHALL be implemented using Flask or FastAPI and serve both the REST_API endpoints and the static Frontend assets (HTML, CSS, JS) from a single process.
2. WHEN the Web_Server is started, THE Web_Server SHALL listen on a configurable host and port (defaulting to `127.0.0.1:5000`).
3. WHEN a browser requests the root URL (`/`), THE Web_Server SHALL serve the `index.html` file from the static assets directory.
4. THE Web_Server SHALL initialize a single Database_Manager instance using a configurable SQLite database path (defaulting to `teammates.db`).
5. THE Web_Server SHALL initialize a single Scheduling_Engine instance shared across all API requests.
6. IF the Web_Server fails to open or create the SQLite database file, THEN THE Web_Server SHALL log the error and exit with a non-zero status code.

### Requirement 2: REST API — Schedule Endpoints

**User Story:** As a DC employee, I want the frontend to fetch the computed schedule from the server, so that the calendar displays accurate shift assignments.

#### Acceptance Criteria

1. WHEN the REST_API receives a `GET /api/schedule/{year}/{month}` request, THE REST_API SHALL invoke `SchedulingEngine.compute_annual_schedule` with the current teammates, shift windows, and overrides from the Database_Manager, and return the schedule slots for the requested month as a JSON array.
2. THE REST_API schedule response SHALL include for each slot: `date` (ISO format), `shift_type` ("day" or "night"), `start_time`, `teammates` (array of names), `is_override` (boolean), and `teammate_starts` (object mapping names to custom start times).
3. WHEN the REST_API receives a `GET /api/schedule/{year}/{month}` request with an invalid year or month, THE REST_API SHALL return HTTP 400 with a JSON error message.
4. THE REST_API SHALL invoke the existing `SchedulingEngine.compute_annual_schedule` method from `scheduling.py` without modification.

### Requirement 3: REST API — Teammate Endpoints

**User Story:** As a DC employee, I want to manage teammates through the web interface, so that the schedule reflects the current team roster.

#### Acceptance Criteria

1. WHEN the REST_API receives a `GET /api/teammates` request, THE REST_API SHALL return all teammate records from the Database_Manager as a JSON array with fields `id`, `name`, `shift_type`, and `custom_start`.
2. WHEN the REST_API receives a `POST /api/teammates` request with a JSON body containing `name`, `shift_type`, and optional `custom_start`, THE REST_API SHALL invoke `Database_Manager.add_teammate` and return the new teammate record with HTTP 201.
3. WHEN the REST_API receives a `PUT /api/teammates/{id}` request with a JSON body containing `name`, `shift_type`, and optional `custom_start`, THE REST_API SHALL invoke `Database_Manager.update_teammate` and return the updated record.
4. WHEN the REST_API receives a `DELETE /api/teammates/{id}` request, THE REST_API SHALL invoke `Database_Manager.delete_teammate` and return HTTP 204.
5. IF the `POST /api/teammates` or `PUT /api/teammates/{id}` request contains an empty or whitespace-only `name`, THEN THE REST_API SHALL return HTTP 400 with the error message "Teammate name must not be empty."
6. IF the `POST /api/teammates` or `PUT /api/teammates/{id}` request contains a `custom_start` value that fails `validate_time_format`, THEN THE REST_API SHALL return HTTP 400 with the validation error message.
7. WHEN the REST_API receives a `POST /api/teammates/import-csv` request with a CSV file upload, THE REST_API SHALL parse each row as `name,shift_type[,custom_start]`, add valid rows via the Database_Manager, skip rows with invalid shift types, and return a JSON summary with `imported_count` and `skipped_rows` (array of row numbers).

### Requirement 4: REST API — Override Endpoints

**User Story:** As a DC employee, I want to set and remove shift overrides through the web interface, so that I can handle schedule exceptions.

#### Acceptance Criteria

1. WHEN the REST_API receives a `GET /api/overrides/{year}` request, THE REST_API SHALL return all overrides for the given year from the Database_Manager as a JSON array with fields `date`, `shift_type`, and `name`.
2. WHEN the REST_API receives a `POST /api/overrides` request with a JSON body containing `date`, `shift_type`, and `name`, THE REST_API SHALL invoke `Database_Manager.set_override` and return the override record with HTTP 201.
3. WHEN the REST_API receives a `DELETE /api/overrides` request with a JSON body containing `date` and `shift_type`, THE REST_API SHALL invoke `Database_Manager.remove_override` and return HTTP 204.

### Requirement 5: REST API — Settings Endpoints

**User Story:** As a DC employee, I want to configure shift window times and application preferences through the web interface, so that the schedule matches my site's operating parameters.

#### Acceptance Criteria

1. WHEN the REST_API receives a `GET /api/settings/shift-windows` request, THE REST_API SHALL return the current shift windows from the Database_Manager as a JSON object keyed by "day" and "night", each with `shift_type`, `start_time`, and `end_time`.
2. WHEN the REST_API receives a `PUT /api/settings/shift-windows/{shift_type}` request with a JSON body containing `start_time` and `end_time`, THE REST_API SHALL validate both times using `validate_time_format` and, if valid, invoke `Database_Manager.update_shift_window`.
3. IF either `start_time` or `end_time` fails `validate_time_format`, THEN THE REST_API SHALL return HTTP 400 with the validation error message and not persist the change.

### Requirement 6: REST API — Export Endpoints

**User Story:** As a DC employee, I want to export the shift schedule in CSV, JSON, and Excel formats, so that I can upload it to other systems or share it with my team.

#### Acceptance Criteria

1. WHEN the REST_API receives a `GET /api/export/{year}/csv` request, THE REST_API SHALL compute the annual schedule, invoke `CSVExporter.export` from the existing `csv_export.py` module writing to a temporary file, and return the file content as a download with Content-Disposition filename `{region}_{year}_schedule.csv`.
2. WHEN the REST_API receives a `GET /api/export/{year}/json` request, THE REST_API SHALL compute the annual schedule, invoke `JSONExporter.export` from the existing `csv_export.py` module writing to a temporary file, and return the file content as a download with Content-Disposition filename `{region}_{year}_schedule.json`.
3. WHEN the REST_API receives a `GET /api/export/{year}/xlsx` request, THE REST_API SHALL compute the annual schedule, invoke `ExcelExporter.export` from the existing `excel_export.py` module writing to a temporary file, and return the file content as a download with Content-Disposition filename `{region}_{year}_schedule.xlsx`.
4. IF the schedule fails `validate_schedule` during any export, THEN THE REST_API SHALL return HTTP 400 with the first validation error message and not produce a download.
5. THE REST_API SHALL invoke the existing exporter classes (`CSVExporter`, `JSONExporter`, `ExcelExporter`) without modification, using temporary files as intermediaries.
6. WHEN the region is not set or is empty, THE REST_API SHALL use "SITE" as the default region prefix in export filenames.

### Requirement 7: REST API — Database Import Endpoint

**User Story:** As a DC employee migrating from the desktop app, I want to import my existing `teammates.db` file through the web interface, so that I do not have to re-enter all data.

#### Acceptance Criteria

1. WHEN the REST_API receives a `POST /api/import-db` request with a `.db` file upload, THE REST_API SHALL open the uploaded file as a SQLite database, read the `teammates`, `shift_windows`, and `overrides` tables, and merge the records into the active Database_Manager.
2. WHEN importing data, THE REST_API SHALL merge imported records with existing data: for teammates, imported records are added with new IDs; for shift windows, imported values overwrite existing values; for overrides with the same date and shift_type, imported values take precedence.
3. WHEN the import completes successfully, THE REST_API SHALL return a JSON summary with `teammates_count`, `shift_windows_count`, and `overrides_count`.
4. IF the uploaded file is not a valid SQLite database or lacks the expected tables (`teammates`, `shift_windows`, `overrides`), THEN THE REST_API SHALL return HTTP 400 with the message "Invalid database file. Expected teammates.db format."

### Requirement 8: Frontend — Application Shell and Theme

**User Story:** As a DC employee, I want the web application to have a consistent dark theme and clear navigation, so that the interface is visually comfortable during long shifts.

#### Acceptance Criteria

1. THE Frontend SHALL be implemented as vanilla HTML, CSS, and JavaScript without framework dependencies (no React, Vue, or Angular).
2. THE Frontend SHALL apply the "Deepest Navy" dark theme with background color `#020617`, surface/card color `#1E293B`, primary accent `#3B82F6`, and text color `#F8FAFC`.
3. THE Frontend SHALL render a sidebar navigation with four items: Dashboard (calendar icon), Team (people icon), Settings (gear icon), and Export (download icon).
4. WHEN the user clicks a navigation item, THE Frontend SHALL display the corresponding view (Dashboard_View, Team_Page, Settings_Page, or Export_Page) without a full page reload, using client-side view switching.
5. THE Frontend SHALL render a header bar at the top of the page displaying the application title "DC-ShiftMaster Pro" and the currently selected year and region.
6. WHEN the Frontend is loaded, THE Frontend SHALL display the Dashboard_View as the default landing page.
7. THE Frontend SHALL visually indicate the currently active navigation item using a highlighted background or accent color.

### Requirement 9: Frontend — Dashboard / Calendar View

**User Story:** As a DC employee, I want to see the shift schedule displayed as a calendar grid, so that I can quickly identify who is on-call for any given day.

#### Acceptance Criteria

1. WHEN the Dashboard_View is displayed, THE Frontend SHALL fetch the schedule for the selected year and month from `GET /api/schedule/{year}/{month}` and render a grid of Day_Card elements for every day in the month.
2. THE Day_Card SHALL display the day number, the day-of-week abbreviation, and the Front_Half or Back_Half ownership label ("F" or "B").
3. THE Day_Card SHALL contain one Shift_Pill per assigned teammate for both day and night shifts, with day shift pills colored amber/gold (`#FFD966`) and night shift pills colored blue (`#4472C4`).
4. WHEN a Shift_Pill represents an overridden assignment, THE Shift_Pill SHALL display a visual indicator (red border or icon) distinguishing the override from the computed assignment.
5. WHEN the user clicks a Day_Card, THE Frontend SHALL display a modal or popover allowing the user to set an Override for the day shift, night shift, or both, with a dropdown of all teammate names plus a "nobody" option.
6. WHEN the user submits an override selection, THE Frontend SHALL send a `POST /api/overrides` request and refresh the calendar to reflect the change.
7. THE Dashboard_View SHALL display month navigation controls (previous month, next month buttons) and a year selector.
8. WHEN the user changes the year or month, THE Frontend SHALL fetch the updated schedule from the REST_API and re-render the calendar grid.
9. WHEN the Dashboard_View renders Shift_Pill elements for teammates with a non-empty `custom_start` field, THE Shift_Pill SHALL display the custom start time next to the teammate name.
10. WHEN the user hovers over a Day_Card, THE Day_Card SHALL apply a subtle scale or elevation transition to provide visual feedback.

### Requirement 10: Frontend — Team Management Page

**User Story:** As a DC employee, I want to add, edit, and remove teammates through the web interface, so that the schedule reflects the current team roster.

#### Acceptance Criteria

1. WHEN the Team_Page is displayed, THE Frontend SHALL fetch teammates from `GET /api/teammates` and display them grouped by shift type (FHD, FHN, BHD, BHN) with each teammate's name and custom start time (if set).
2. WHEN the user clicks the "Add Teammate" button, THE Frontend SHALL display a form with fields for name (text input), shift type (select: FHD, FHN, BHD, BHN), and custom start time (optional text input, HH:MM format).
3. WHEN the user submits the add-teammate form with valid data, THE Frontend SHALL send a `POST /api/teammates` request and refresh the teammate list on success.
4. IF the REST_API returns a validation error for the add or edit request, THEN THE Frontend SHALL display the error message in a Toast_Notification.
5. WHEN the user clicks the edit button on a teammate row, THE Frontend SHALL display an inline edit form pre-populated with the teammate's current values.
6. WHEN the user clicks the delete button on a teammate row, THE Frontend SHALL display a confirmation dialog, and upon confirmation, send a `DELETE /api/teammates/{id}` request and refresh the list.
7. WHEN the user clicks the "Import CSV" button, THE Frontend SHALL open a native browser file input accepting `.csv` files.
8. WHEN a CSV file is selected, THE Frontend SHALL upload the file to `POST /api/teammates/import-csv` and display a Toast_Notification with the import summary (imported count and skipped rows).

### Requirement 11: Frontend — Settings Page

**User Story:** As a DC employee, I want to configure shift window times and select my DC site region, so that the schedule matches my site's operating parameters.

#### Acceptance Criteria

1. WHEN the Settings_Page is displayed, THE Frontend SHALL fetch shift windows from `GET /api/settings/shift-windows` and display editable fields for day shift start time, day shift end time, night shift start time, and night shift end time.
2. WHEN the user modifies a shift window time and clicks "Save", THE Frontend SHALL send a `PUT /api/settings/shift-windows/{shift_type}` request and display a Toast_Notification on success or show the validation error on failure.
3. THE Settings_Page SHALL display a region text input allowing the user to enter a DC site code (e.g., "ATL68").
4. THE Settings_Page SHALL display a year selector (numeric input) defaulting to the current calendar year.
5. WHEN the user changes the year or region, THE Frontend SHALL persist the values using `localStorage` and update the header bar display.
6. THE Settings_Page SHALL display an "Import Database" section with a file input accepting `.db` files.
7. WHEN a `.db` file is selected for import, THE Frontend SHALL upload the file to `POST /api/import-db` and display a Toast_Notification with the import summary or error message.

### Requirement 12: Frontend — Export Page

**User Story:** As a DC employee, I want to export the shift schedule in multiple formats, so that I can share it with my team or upload it to other systems.

#### Acceptance Criteria

1. THE Export_Page SHALL display three export buttons: "Export CSV", "Export JSON", and "Export Excel".
2. WHEN the user clicks "Export CSV", THE Frontend SHALL initiate a browser download by navigating to `GET /api/export/{year}/csv`, triggering the file download.
3. WHEN the user clicks "Export JSON", THE Frontend SHALL initiate a browser download by navigating to `GET /api/export/{year}/json`, triggering the file download.
4. WHEN the user clicks "Export Excel", THE Frontend SHALL initiate a browser download by navigating to `GET /api/export/{year}/xlsx`, triggering the file download.
5. IF the export endpoint returns an error (e.g., schedule validation failure), THEN THE Frontend SHALL display the error message in a Toast_Notification.
6. WHILE an export download is in progress, THE Frontend SHALL display a loading indicator on the clicked button.

### Requirement 13: Frontend — Responsive Layout

**User Story:** As a DC employee, I want the application to be usable on both desktop and tablet screens, so that I can check the schedule from different devices.

#### Acceptance Criteria

1. WHILE the browser viewport width is 1024 pixels or greater, THE Frontend SHALL display the sidebar navigation alongside the main content area.
2. WHILE the browser viewport width is less than 1024 pixels, THE Frontend SHALL collapse the sidebar to icon-only mode or replace it with a bottom navigation bar.
3. WHILE the browser viewport width is less than 768 pixels, THE Dashboard_View SHALL switch from a 7-column calendar grid to a single-column list layout showing one day per row.
4. THE Day_Card elements SHALL use relative sizing (percentages or CSS grid fractions) so that content reflows without horizontal scrolling on viewports 360 pixels wide or greater.

### Requirement 14: Frontend — Toast Notifications

**User Story:** As a DC employee, I want to see feedback messages when I perform actions, so that I know whether my changes were saved successfully.

#### Acceptance Criteria

1. WHEN an action completes successfully (e.g., teammate added, override set, settings saved), THE Frontend SHALL display a Toast_Notification with a success message that auto-dismisses after 3 seconds.
2. WHEN an action fails due to a validation or server error, THE Frontend SHALL display a Toast_Notification with the error message that auto-dismisses after 5 seconds.
3. THE Toast_Notification SHALL be positioned at the bottom-right of the viewport and stack vertically when multiple notifications are active.
4. THE Toast_Notification SHALL use distinct background colors for success (green-tinted) and error (red-tinted) states.

### Requirement 15: Deployment as a Simple Python Web Server

**User Story:** As a DC employee, I want to start the application with a single command, so that I can run it locally or deploy it on a server without complex infrastructure.

#### Acceptance Criteria

1. THE Web_Server SHALL be startable with a single command (e.g., `python -m dc_shiftmaster_html.server` or `python run.py`).
2. THE Web_Server SHALL serve the Frontend static assets from a `static/` directory within the package.
3. THE Web_Server SHALL accept command-line arguments or environment variables for host, port, and database file path.
4. THE Web_Server SHALL include a `requirements.txt` or `pyproject.toml` listing all Python dependencies (Flask or FastAPI, openpyxl, and any other required packages).
5. WHEN the Web_Server is started, THE Web_Server SHALL log the URL where the application is accessible (e.g., "Running on http://127.0.0.1:5000").
