# Requirements Document

## Introduction

DC-ShiftMaster Pro is a desktop-based Data Center Shift Scheduler built with Python. It manages a repeating 14-day shift rotation cycle for data center teams, stores teammate assignments in an SQLite database, provides an interactive calendar GUI for viewing and overriding shifts, and exports the full annual schedule to CSV. The exported CSV is designed for direct upload to an on-call scheduling system via its "Custom Upload" feature, so the format must be strictly compatible with that system's import requirements. The application supports configurable shift windows (Day/Night) and targets Windows deployment via PyInstaller.

## Glossary

- **Application**: The DC-ShiftMaster Pro desktop application
- **Scheduling_Engine**: The module responsible for computing the 14-day repeating shift rotation for a given year
- **Settings_Manager**: The component that stores and applies shift window configurations (start/end times)
- **Teammate_Database**: The SQLite-backed store (`teammates.db`) holding teammate names and their assigned shift types
- **Calendar_View**: The interactive yearly calendar grid displaying day and night shift assignments per day
- **CSV_Exporter**: The module that generates a headerless two-column CSV file of the full annual schedule, formatted for direct upload to the on-call scheduling system's "Custom Upload" feature
- **Custom_Upload_Format**: The CSV format required by the on-call scheduling system — two columns, no headers, Column A is date/time in `M/D/YYYY H:MM` format (no leading zeros), Column B is the member login/alias or the keyword "nobody" for unassigned slots
- **Shift_Window**: A named time range defining when a shift starts and ends (e.g., Day Shift 06:00–18:30)
- **14_Day_Cycle**: The repeating two-week rotation pattern that determines which shift group owns each day
- **Front_Half_Day (FHD)**: The day-shift group covering Front Half days
- **Front_Half_Night (FHN)**: The night-shift group covering Front Half days
- **Back_Half_Day (BHD)**: The day-shift group covering Back Half days
- **Back_Half_Night (BHN)**: The night-shift group covering Back Half days
- **Swing_Day**: Wednesday — owned by Front Half in Week 1 and Back Half in Week 2 of each 14-day cycle
- **Override**: A manual per-slot assignment that replaces the auto-populated teammate for a specific day and shift
- **Slot**: A single shift assignment cell on the calendar, representing either the Day or Night shift for one date

## Requirements

### Requirement 1: Shift Window Configuration

**User Story:** As a manager, I want to define and update the Day and Night shift start/end times, so that the schedule reflects our operational hours.

#### Acceptance Criteria

1. THE Settings_Manager SHALL store a Day Shift_Window and a Night Shift_Window, each defined by a start time and an end time in HH:MM format.
2. THE Settings_Manager SHALL default the Day Shift_Window to 06:00–18:30 and the Night Shift_Window to 18:00–06:30 when no prior configuration exists.
3. WHEN a manager updates a Shift_Window's start or end time, THE Settings_Manager SHALL persist the new values to the SQLite database.
4. WHEN a Shift_Window is updated, THE Calendar_View SHALL re-render all Slots for the displayed year using the updated times within 2 seconds.
5. IF a manager enters a time value that does not match HH:MM 24-hour format, THEN THE Settings_Manager SHALL display an inline validation error and reject the input.

### Requirement 2: Teammate Management

**User Story:** As a manager, I want to add, edit, and remove teammates and assign each to a shift type, so that the scheduler knows who works which rotation.

#### Acceptance Criteria

1. THE Teammate_Database SHALL store each teammate record with a name (text) and an assigned shift type (one of FHD, FHN, BHD, BHN).
2. WHEN a manager adds a new teammate with a name and shift type, THE Teammate_Database SHALL insert the record and THE Calendar_View SHALL update to reflect the new assignment.
3. WHEN a manager edits an existing teammate's name or shift type, THE Teammate_Database SHALL update the record and THE Calendar_View SHALL re-render affected Slots.
4. WHEN a manager deletes a teammate, THE Teammate_Database SHALL remove the record and THE Calendar_View SHALL replace that teammate's name with "nobody" in all affected Slots.
5. IF a manager attempts to add a teammate with an empty name, THEN THE Application SHALL display a validation error and reject the entry.
6. THE Application SHALL display all teammates in a table view showing name and assigned shift type.

### Requirement 3: 14-Day Cycle Scheduling Engine

**User Story:** As a manager, I want the schedule to auto-populate based on a 14-day rotation starting January 1, so that shift coverage follows our standard pattern without manual entry.

#### Acceptance Criteria

1. THE Scheduling_Engine SHALL compute a repeating 14_Day_Cycle starting from January 1 of the selected year.
2. THE Scheduling_Engine SHALL assign Front Half days as follows: Week 1 — Sunday, Monday, Tuesday, Wednesday; Week 2 — Sunday, Monday, Tuesday.
3. THE Scheduling_Engine SHALL assign Back Half days as follows: Week 1 — Thursday, Friday, Saturday; Week 2 — Wednesday, Thursday, Friday, Saturday.
4. THE Scheduling_Engine SHALL treat Wednesday as the Swing_Day, assigning it to Front Half in Week 1 and to Back Half in Week 2 of each 14_Day_Cycle.
5. FOR each day assigned to Front Half, THE Scheduling_Engine SHALL populate the Day Slot with the FHD teammate and the Night Slot with the FHN teammate.
6. FOR each day assigned to Back Half, THE Scheduling_Engine SHALL populate the Day Slot with the BHD teammate and the Night Slot with the BHN teammate.
7. WHEN the selected year changes, THE Scheduling_Engine SHALL recompute the full annual schedule starting from January 1 of the new year.

### Requirement 4: Interactive Calendar View

**User Story:** As a manager, I want to see a visual yearly calendar grid showing day and night shift assignments, so that I can review coverage at a glance.

#### Acceptance Criteria

1. THE Calendar_View SHALL display a grid for the entire selected year (January 1 through December 31).
2. THE Calendar_View SHALL render each day as a cell containing two Slots: one for the Day shift and one for the Night shift.
3. THE Calendar_View SHALL auto-populate each Slot with the teammate name computed by the Scheduling_Engine.
4. WHEN a Slot has no assigned teammate, THE Calendar_View SHALL display "nobody" in that Slot.
5. THE Calendar_View SHALL allow the user to navigate between years to view schedules for different annual periods.
6. THE Calendar_View SHALL visually distinguish Day Slots from Night Slots using color coding or labeling.

### Requirement 5: Manual Shift Override

**User Story:** As a manager, I want to right-click a shift slot and manually assign a different person or mark it as unassigned, so that I can handle overtime, absences, and gaps.

#### Acceptance Criteria

1. WHEN a manager right-clicks a Slot on the Calendar_View, THE Application SHALL display a context menu allowing the manager to enter a replacement name or select "nobody."
2. WHEN a manager confirms an Override, THE Application SHALL store the Override associated with the specific date, shift type, and replacement name.
3. WHEN an Override exists for a Slot, THE Calendar_View SHALL display the Override name instead of the Scheduling_Engine's computed name.
4. WHEN a manager removes an Override, THE Calendar_View SHALL revert the Slot to the Scheduling_Engine's computed assignment.
5. THE Application SHALL persist all Overrides to the SQLite database so they survive application restarts.
6. WHEN the Scheduling_Engine recomputes the schedule (e.g., on year change), THE Application SHALL preserve existing Overrides for the same year.

### Requirement 6: CSV Export

**User Story:** As a manager, I want to export the full annual schedule to a CSV file compatible with the on-call scheduling system's Custom Upload format, so that I can upload it directly without manual editing.

#### Acceptance Criteria

1. WHEN a manager clicks the "Generate & Export" button, THE CSV_Exporter SHALL produce a CSV file covering January 1 through December 31 of the selected year in the Custom_Upload_Format.
2. THE CSV_Exporter SHALL write two columns per row with no header row.
3. THE CSV_Exporter SHALL format Column A as `M/D/YYYY H:MM` using the Shift_Window start time for that Slot, without leading zeros on month, day, or hour (e.g., `6/5/2018 14:00`, not `06/05/2018 14:00`).
4. THE CSV_Exporter SHALL write the assigned teammate login/alias in Column B, or the keyword "nobody" if no teammate is assigned — "nobody" is the specific value recognized by the on-call scheduling system for unassigned shifts.
5. THE CSV_Exporter SHALL output two rows per day: one for the Day shift and one for the Night shift, ordered Day then Night.
6. THE CSV_Exporter SHALL produce rows sorted in chronological date order from January 1 to December 31.
7. THE CSV_Exporter SHALL apply Overrides to the exported data, replacing computed names where Overrides exist.
8. THE CSV_Exporter SHALL produce output that is directly uploadable to the on-call scheduling system's Custom Upload feature without requiring manual editing or reformatting.
9. WHEN the export completes, THE Application SHALL display a confirmation message with the file path of the exported CSV.
10. IF the export target path is not writable, THEN THE Application SHALL display an error message indicating the file could not be saved.

### Requirement 7: CSV Round-Trip Integrity

**User Story:** As a developer, I want to verify that exported CSV data can be re-parsed to reconstruct the same schedule, so that data integrity is maintained.

#### Acceptance Criteria

1. THE CSV_Exporter SHALL produce output where each row can be parsed back into a date, shift start time, and teammate name using the Custom_Upload_Format.
2. FOR ALL valid annual schedules, exporting to CSV and then parsing the CSV SHALL produce a dataset equivalent to the original schedule (round-trip property).

### Requirement 8: Data Persistence

**User Story:** As a manager, I want all my data (teammates, overrides, settings) stored in a local SQLite database, so that nothing is lost between sessions.

#### Acceptance Criteria

1. THE Application SHALL store all teammate records, Shift_Window configurations, and Overrides in a single SQLite database file (`teammates.db`).
2. WHEN the Application starts, THE Application SHALL load all persisted data from the database and restore the previous state.
3. IF the database file does not exist on startup, THEN THE Application SHALL create a new database with default Shift_Window values and empty teammate and override tables.

### Requirement 9: Desktop Packaging

**User Story:** As a manager, I want to run the scheduler as a standalone Windows executable, so that I do not need to install Python.

#### Acceptance Criteria

1. THE Application SHALL be packageable into a single Windows executable using PyInstaller.
2. THE Application SHALL include a `requirements.txt` file listing all Python dependencies.
3. THE Application SHALL function correctly when launched from the packaged executable without a Python installation present.

### Requirement 10: GUI Framework

**User Story:** As a developer, I want the application built with CustomTkinter or PySide6, so that the UI is modern and maintainable.

#### Acceptance Criteria

1. THE Application SHALL use CustomTkinter or PySide6 as the GUI framework.
2. THE Application SHALL present a tabbed interface with at least a Settings tab, a Teammates tab, and a Calendar tab.
3. THE Application SHALL render correctly on Windows 10 and later at a minimum resolution of 1280×720.
