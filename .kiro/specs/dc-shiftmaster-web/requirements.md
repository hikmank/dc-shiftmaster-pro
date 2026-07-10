# Requirements Document

## Introduction

DC-ShiftMaster Pro is currently a CustomTkinter desktop application for managing on-call shift rotations at AWS data center sites. This feature migrates the application to a Flet-based web application that compiles to static web assets and is hosted on Amazon S3. The existing backend logic (scheduling engine, models, validation, exporters) is preserved unchanged. The SQLite persistence layer is replaced with browser localStorage via Flet's `client_storage` API. The web application uses a Material 3 dark theme ("Deepest Navy") and is designed for use by data center employees across multiple sites.

## Glossary

- **Flet_App**: The Flet web application entry point that initializes the page, theme, and routing.
- **Navigation_Rail**: The Flet `NavigationRail` sidebar component providing page-level navigation between Dashboard, Team, Settings, and Export views.
- **Calendar_View**: The page displaying the annual shift schedule as a grid of Card components, one per day, with Chip components representing shift assignments.
- **Team_Page**: The page for managing teammate records (add, edit, delete, import from CSV).
- **Settings_Page**: The page for configuring shift windows (day/night start and end times) and application preferences such as year and region.
- **Export_Page**: The page for triggering CSV, JSON, and Excel exports that download via the browser.
- **Storage_Adapter**: The persistence layer that replaces `DatabaseManager` by reading and writing JSON-serialized data to Flet `client_storage` (browser localStorage).
- **Scheduling_Engine**: The existing `SchedulingEngine` class that computes the deterministic 14-day shift rotation cycle (preserved unchanged).
- **Toast_Notification**: A Flet `SnackBar` component used to display transient feedback messages to the user.
- **Shift_Pill**: A Flet `Chip` component representing a single teammate assignment within a calendar day card, color-coded by shift type.
- **Calendar_Card**: A Flet `Card` component representing a single day in the Calendar_View, containing Shift_Pill components and date metadata.
- **Header_Bar**: A semi-transparent bar at the top of the page displaying the current year, region label, and navigation context.
- **Override**: A manual per-slot assignment replacing the computed teammate for a specific date and shift type.
- **Front_Half**: The shift group owning cycle days 0-3 and 7-9 within the 14-day rotation.
- **Back_Half**: The shift group owning cycle days 4-6 and 10-13 within the 14-day rotation.

## Requirements

### Requirement 1: Flet App Initialization and Theming

**User Story:** As a DC employee, I want the web application to load with a consistent Material 3 dark theme, so that the interface is visually comfortable during long shifts.

#### Acceptance Criteria

1. WHEN the Flet_App is loaded in a browser, THE Flet_App SHALL initialize the page with `theme_mode` set to `ft.ThemeMode.DARK` and a Material 3 `ColorScheme` using background color `#020617` and surface color `#1E293B`.
2. THE Flet_App SHALL set the page title to "DC-ShiftMaster Pro".
3. THE Flet_App SHALL render a Header_Bar at the top of the page with a semi-transparent background using `blur` and `opacity` properties, displaying the selected year and region label.
4. WHEN the Flet_App finishes initialization, THE Flet_App SHALL display the Calendar_View as the default landing page.
5. THE Flet_App SHALL compile to static web assets (HTML, CSS, JS) suitable for hosting without a backend server.
6. IF the browser does not support localStorage, THEN THE Flet_App SHALL display a Toast_Notification with the message "Browser storage unavailable. Data will not persist between sessions."

### Requirement 2: Storage Adapter (localStorage Replacement for SQLite)

**User Story:** As a DC employee, I want my teammate and schedule data to persist in the browser, so that I do not lose configuration between sessions.

#### Acceptance Criteria

1. THE Storage_Adapter SHALL implement the same read/write interface as `DatabaseManager` for teammates, shift windows, and overrides.
2. THE Storage_Adapter SHALL serialize all data as JSON strings and store each collection under a namespaced key in Flet `client_storage` (e.g., `dcshift.teammates`, `dcshift.shift_windows`, `dcshift.overrides`).
3. WHEN the Storage_Adapter is initialized and no existing data is found, THE Storage_Adapter SHALL seed default shift windows with day start `06:00`, day end `18:30`, night start `18:00`, and night end `06:30`.
4. WHEN the Storage_Adapter reads teammate records, THE Storage_Adapter SHALL deserialize JSON into `Teammate` dataclass instances with `id`, `name`, `shift_type`, and `custom_start` fields.
5. WHEN the Storage_Adapter writes a new teammate, THE Storage_Adapter SHALL assign a unique integer ID by incrementing the maximum existing ID.
6. WHEN the Storage_Adapter reads override records for a given year, THE Storage_Adapter SHALL return only overrides whose date string starts with that year prefix.
7. FOR ALL valid teammate lists, serializing to JSON then deserializing back SHALL produce an equivalent list of Teammate objects (round-trip property).
8. FOR ALL valid override lists, serializing to JSON then deserializing back SHALL produce an equivalent list of Override objects (round-trip property).
9. FOR ALL valid shift window dicts, serializing to JSON then deserializing back SHALL produce an equivalent dict of ShiftWindow objects (round-trip property).

### Requirement 3: Navigation and Routing

**User Story:** As a DC employee, I want a sidebar navigation to switch between pages, so that I can quickly access different features of the application.

#### Acceptance Criteria

1. THE Navigation_Rail SHALL display four destinations: Dashboard (calendar icon), Team (people icon), Settings (gear icon), and Export (download icon).
2. THE Navigation_Rail SHALL be rendered as a Flet `NavigationRail` component on the left side of the page.
3. WHEN the user selects a destination on the Navigation_Rail, THE Flet_App SHALL display the corresponding page (Calendar_View, Team_Page, Settings_Page, or Export_Page) without a full page reload.
4. THE Navigation_Rail SHALL visually indicate the currently active destination using the Material 3 selected indicator style.
5. WHILE the Flet_App is displaying any page, THE Header_Bar SHALL remain visible at the top of the viewport.

### Requirement 4: Calendar / Dashboard View

**User Story:** As a DC employee, I want to see the shift schedule displayed as a calendar grid, so that I can quickly identify who is on-call for any given day.

#### Acceptance Criteria

1. WHEN the Calendar_View is displayed, THE Calendar_View SHALL render a grid of Calendar_Card components for every day in the selected month.
2. THE Calendar_Card SHALL display the day number, the day-of-week abbreviation, and the Front_Half or Back_Half ownership label ("F" or "B").
3. THE Calendar_Card SHALL contain one Shift_Pill per assigned teammate for both day and night shifts, color-coded by shift type (distinct colors for day vs. night).
4. WHEN the user hovers over a Calendar_Card, THE Calendar_Card SHALL apply `animate_scale` and `animate_opacity` transitions to provide visual feedback.
5. WHEN the user right-clicks (desktop) or long-presses (mobile) a Calendar_Card, THE Calendar_View SHALL display a context menu allowing the user to set an Override for the day shift, night shift, or both.
6. WHEN the user selects an Override from the context menu, THE Calendar_View SHALL present a dropdown of all teammate names plus a "nobody" option, and persist the selection via the Storage_Adapter.
7. WHEN an Override is active for a slot, THE Shift_Pill SHALL display a visual indicator (e.g., border or icon) distinguishing the overridden assignment from the computed assignment.
8. THE Calendar_View SHALL display month navigation controls (previous month, next month) and a year selector allowing the user to change the displayed year.
9. WHEN the user changes the year or month, THE Calendar_View SHALL recompute the schedule using the Scheduling_Engine with the current teammates, shift windows, and overrides from the Storage_Adapter.
10. THE Calendar_View SHALL invoke `SchedulingEngine.compute_annual_schedule` from the existing `scheduling.py` module without modification.
11. WHEN the Calendar_View renders Shift_Pill components for teammates with a non-empty `custom_start` field, THE Shift_Pill SHALL display the custom start time next to the teammate name.

### Requirement 5: Team Management Page

**User Story:** As a DC employee, I want to add, edit, and remove teammates, so that the schedule reflects the current team roster.

#### Acceptance Criteria

1. WHEN the Team_Page is displayed, THE Team_Page SHALL list all teammates grouped by shift type (FHD, FHN, BHD, BHN) with each teammate's name and custom start time (if set).
2. WHEN the user clicks the "Add Teammate" button, THE Team_Page SHALL display a form with fields for name (text), shift type (dropdown: FHD, FHN, BHD, BHN), and custom start time (optional, HH:MM format).
3. WHEN the user submits the add-teammate form with a valid name, THE Team_Page SHALL persist the new teammate via the Storage_Adapter and refresh the list.
4. IF the user submits the add-teammate form with an empty or whitespace-only name, THEN THE Team_Page SHALL display a Toast_Notification with the message "Teammate name must not be empty."
5. IF the user enters a custom start time that does not match HH:MM 24-hour format, THEN THE Team_Page SHALL display a validation error using `validate_time_format` from the existing `validation.py` module.
6. WHEN the user clicks the edit icon on a teammate row, THE Team_Page SHALL display an inline edit form pre-populated with the teammate's current name, shift type, and custom start time.
7. WHEN the user clicks the delete icon on a teammate row, THE Team_Page SHALL display a confirmation dialog, and upon confirmation, remove the teammate via the Storage_Adapter.
8. WHEN the user clicks the "Import CSV" button, THE Team_Page SHALL open a file picker allowing selection of a CSV file containing teammate records.
9. WHEN a valid CSV file is selected for import, THE Team_Page SHALL parse each row as `name,shift_type[,custom_start]` and add the teammates via the Storage_Adapter.
10. IF the imported CSV contains rows with invalid shift types (not FHD, FHN, BHD, or BHN), THEN THE Team_Page SHALL skip those rows and display a Toast_Notification listing the skipped row numbers.

### Requirement 6: Settings Page

**User Story:** As a DC employee, I want to configure shift window times and select my DC site region, so that the schedule matches my site's operating parameters.

#### Acceptance Criteria

1. WHEN the Settings_Page is displayed, THE Settings_Page SHALL show editable fields for day shift start time, day shift end time, night shift start time, and night shift end time, pre-populated from the Storage_Adapter.
2. WHEN the user modifies a shift window time and clicks "Save", THE Settings_Page SHALL validate the input using `validate_time_format` and persist the updated values via the Storage_Adapter.
3. IF the user enters an invalid time format in any shift window field, THEN THE Settings_Page SHALL display the validation error message returned by `validate_time_format` and prevent saving.
4. THE Settings_Page SHALL display a region selector dropdown populated with DC site codes (e.g., ATL68, ATL78).
5. WHEN the user selects a region, THE Settings_Page SHALL persist the selection via the Storage_Adapter under the key `dcshift.region`.
6. THE Settings_Page SHALL display a year selector (numeric input or dropdown) defaulting to the current calendar year.
7. WHEN the user changes the year, THE Settings_Page SHALL persist the selection via the Storage_Adapter under the key `dcshift.year`.
8. WHEN any setting is saved successfully, THE Settings_Page SHALL display a Toast_Notification confirming the change.

### Requirement 7: Export Page with Browser Downloads

**User Story:** As a DC employee, I want to export the shift schedule in CSV, JSON, and Excel formats, so that I can upload it to other systems or share it with my team.

#### Acceptance Criteria

1. THE Export_Page SHALL display three export buttons: "Export CSV", "Export JSON", and "Export Excel".
2. WHEN the user clicks "Export CSV", THE Export_Page SHALL invoke `CSVExporter.export` from the existing `csv_export.py` module, generate the file content, and trigger a browser download with filename `{region}_{year}_schedule.csv`.
3. WHEN the user clicks "Export JSON", THE Export_Page SHALL invoke `JSONExporter.export` from the existing `csv_export.py` module, generate the file content, and trigger a browser download with filename `{region}_{year}_schedule.json`.
4. WHEN the user clicks "Export Excel", THE Export_Page SHALL invoke `ExcelExporter.export` from the existing `excel_export.py` module, generate the file content, and trigger a browser download with filename `{region}_{year}_schedule.xlsx`.
5. IF the schedule validation fails during export (as determined by `validate_schedule`), THEN THE Export_Page SHALL display a Toast_Notification with the first validation error and cancel the download.
6. THE Export_Page SHALL use the existing exporter classes without modification, adapting only the file output mechanism to use in-memory buffers and Flet's browser download API instead of direct filesystem writes.
7. WHILE an export is in progress, THE Export_Page SHALL display a loading indicator on the clicked button and disable all export buttons until the operation completes.

### Requirement 8: S3 Static Hosting Deployment

**User Story:** As a DC employee, I want the application deployed as a static website on Amazon S3, so that it is accessible from any browser without installing software.

#### Acceptance Criteria

1. THE Flet_App SHALL be buildable into a self-contained static web bundle using `flet build web`.
2. THE static web bundle SHALL be deployable to an Amazon S3 bucket configured for static website hosting with an `index.html` entry point.
3. THE deployment configuration SHALL include a build script or instructions that produce the static assets and sync them to the S3 bucket using the AWS CLI (`aws s3 sync`).
4. THE static web bundle SHALL function correctly when served from an S3 website endpoint without requiring server-side processing.

### Requirement 9: Responsive Design

**User Story:** As a DC employee, I want the application to be usable on both desktop and tablet screens, so that I can check the schedule from different devices.

#### Acceptance Criteria

1. WHILE the browser viewport width is 1024 pixels or greater, THE Flet_App SHALL display the Navigation_Rail in expanded mode alongside the main content area.
2. WHILE the browser viewport width is less than 1024 pixels, THE Flet_App SHALL collapse the Navigation_Rail to icon-only mode or replace it with a bottom navigation bar.
3. WHILE the browser viewport width is less than 768 pixels, THE Calendar_View SHALL switch from a 7-column grid to a single-column list layout showing one day per row.
4. THE Calendar_Card components SHALL use relative sizing so that content reflows without horizontal scrolling on viewports 360 pixels wide or greater.

### Requirement 10: Data Migration (Import Existing teammates.db)

**User Story:** As a DC employee migrating from the desktop app, I want to import my existing teammates.db data, so that I do not have to re-enter all teammate and override information.

#### Acceptance Criteria

1. THE Settings_Page SHALL display an "Import Database" button in a migration section.
2. WHEN the user clicks "Import Database", THE Settings_Page SHALL open a file picker accepting `.db` files.
3. WHEN a valid SQLite `.db` file is selected, THE Flet_App SHALL read the teammates, shift_windows, and overrides tables using SQL.js (a WebAssembly SQLite implementation) and write the extracted records into the Storage_Adapter.
4. IF the selected file is not a valid SQLite database or lacks the expected tables, THEN THE Flet_App SHALL display a Toast_Notification with the message "Invalid database file. Expected teammates.db format."
5. WHEN the import completes successfully, THE Flet_App SHALL display a Toast_Notification summarizing the imported record counts (e.g., "Imported 12 teammates, 2 shift windows, 5 overrides.").
6. WHEN importing data, THE Flet_App SHALL merge imported records with any existing localStorage data, preferring imported values for conflicting keys (same teammate ID or same override date+shift_type).
