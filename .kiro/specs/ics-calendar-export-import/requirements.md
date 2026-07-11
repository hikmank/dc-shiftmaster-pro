# Requirements Document

## Introduction

This feature adds ICS (iCalendar RFC 5545) export and import capabilities, plus JSON schedule import, to DC-ShiftMaster Pro. Users will be able to export their shift schedules as `.ics` files compatible with Google Calendar, Microsoft Outlook, Apple Calendar, and other standards-compliant calendar applications. Additionally, users will be able to import `.ics` files and JSON schedule files to load shift data into DC-ShiftMaster Pro as overrides. This extends the existing export module (CSV, JSON, Excel) with a widely-supported calendar interchange format and adds re-import capability for the existing JSON export.

## Glossary

- **ICS_Exporter**: The server-side component responsible for converting ScheduleSlot data into RFC 5545 compliant iCalendar format files.
- **ICS_Parser**: The server-side component responsible for parsing uploaded `.ics` files and extracting shift event data for import into the application.
- **ICS_Formatter**: The component responsible for serializing internal shift event representations back into valid `.ics` text output (pretty printer).
- **JSON_Schedule_Importer**: The server-side component responsible for parsing uploaded `.json` schedule files and creating override entries from the data.
- **VEVENT**: An iCalendar component representing a single calendar event, used to represent one shift assignment.
- **VCALENDAR**: The top-level iCalendar container component that wraps one or more VEVENT components.
- **ScheduleSlot**: An existing dataclass representing a single shift assignment (date, shift_type, start_time, teammates, is_override).
- **ShiftWindow**: An existing dataclass defining start and end times for day or night shifts.
- **Export_API**: The Flask route handler serving ICS file downloads at `/api/export/<year>/ics`.
- **Import_API**: The Flask route handler accepting file uploads at `/api/import/ics` (ICS) and `/api/import/schedule-json` (JSON schedules).
- **Team_Context**: The currently active team profile scope used to filter schedule data for export and target data for import.

## Requirements

### Requirement 1: ICS Export Endpoint

**User Story:** As a shift worker, I want to export my team's shift schedule as an ICS file, so that I can import it into my personal calendar application.

#### Acceptance Criteria

1. WHEN a GET request is made to `/api/export/<year>/ics`, THE Export_API SHALL compute the schedule for the specified year and return a valid `.ics` file as a download response.
2. WHEN the `from` query parameter is provided, THE Export_API SHALL include only ScheduleSlots where any part of the shift overlaps the filter range, checking both start_time and end_time against the `from` date.
3. WHEN the `to` query parameter is provided, THE Export_API SHALL include only ScheduleSlots where any part of the shift overlaps the filter range, checking both start_time and end_time against the `to` date.
4. THE Export_API SHALL set the Content-Type header to `text/calendar; charset=utf-8` and include a Content-Disposition header with the filename `{REGION}_{YEAR}_schedule.ics`.
5. WHILE a Team_Context is active, THE Export_API SHALL export only schedule data belonging to the active team.

### Requirement 2: ICS VCALENDAR Structure

**User Story:** As a shift worker, I want the exported ICS file to be standards-compliant, so that any calendar application can read it without errors.

#### Acceptance Criteria

1. THE ICS_Exporter SHALL produce output beginning with `BEGIN:VCALENDAR` and ending with `END:VCALENDAR`.
2. THE ICS_Exporter SHALL include the properties `VERSION:2.0`, `PRODID:-//DC-ShiftMaster Pro//EN`, and `CALSCALE:GREGORIAN` in the VCALENDAR header.
3. THE ICS_Exporter SHALL use CRLF (`\r\n`) line endings as required by RFC 5545.
4. THE ICS_Exporter SHALL fold content lines longer than 75 octets by inserting a CRLF followed by a single whitespace character at the fold point.

### Requirement 3: ICS VEVENT Generation

**User Story:** As a shift worker, I want each shift to appear as a distinct calendar event with clear details, so that I can see who is working and when.

#### Acceptance Criteria

1. WHEN a ScheduleSlot is exported, THE ICS_Exporter SHALL generate one VEVENT component per ScheduleSlot.
2. THE ICS_Exporter SHALL set the VEVENT DTSTART property to the shift start date and time using the format `DTSTART:YYYYMMDDTHHMMSS`.
3. THE ICS_Exporter SHALL set the VEVENT DTEND property to the shift end date and time using the format `DTEND:YYYYMMDDTHHMMSS`.
4. WHEN a night shift crosses midnight (end_time < start_time numerically), THE ICS_Exporter SHALL set DTEND to the following calendar day. WHEN a shift spans multiple days (duration exceeds 24 hours), THE ICS_Exporter SHALL set DTEND to exactly 24 hours after DTSTART, creating multiple single-day events for shifts exceeding one day.
5. THE ICS_Exporter SHALL set the VEVENT SUMMARY property to `{shift_type} Shift - {comma-separated teammate names}`.
6. THE ICS_Exporter SHALL generate a deterministic UID for each VEVENT using the format `{date}-{shift_type}@dc-shiftmaster`.
7. THE ICS_Exporter SHALL set the DTSTAMP property to the current UTC datetime at the time of export.

### Requirement 4: ICS File Parsing

**User Story:** As a team lead, I want to import an ICS file containing shift events, so that I can load externally-created schedules into DC-ShiftMaster Pro.

#### Acceptance Criteria

1. WHEN a POST request with a `.ics` file is made to `/api/import/ics`, THE Import_API SHALL parse the file and extract shift event data.
2. THE ICS_Parser SHALL extract the DTSTART, DTEND, and SUMMARY properties from each VEVENT component in the uploaded file.
3. WHEN a VEVENT lacks a DTSTART or DTEND property, THE ICS_Parser SHALL skip that event and include it in a list of skipped events returned to the client.
4. IF the uploaded file exceeds 5 MB in size, THEN THE Import_API SHALL return HTTP 413 with an error message indicating the file is too large, regardless of format validity (size is validated before format).
5. IF the uploaded file does not begin with `BEGIN:VCALENDAR` or does not contain a valid ICS structure, THEN THE Import_API SHALL return HTTP 400 with an error message indicating invalid ICS format. THE ICS_Parser SHALL validate the full ICS structure before processing any events.

### Requirement 5: ICS Import Data Mapping

**User Story:** As a team lead, I want imported ICS events to be correctly mapped to shift overrides, so that the schedule reflects the imported data.

#### Acceptance Criteria

1. WHEN a VEVENT is successfully parsed, THE Import_API SHALL determine the shift_type as `day` if DTSTART hour is between 05:00 and 13:00 inclusive (hours 05 through 13), and `night` otherwise (including hour 14:00 and above).
2. WHEN a VEVENT SUMMARY contains a recognizable teammate name from the current team roster, THE Import_API SHALL use that name for the override assignment.
3. WHEN a VEVENT SUMMARY does not match any known teammate, THE Import_API SHALL use the full SUMMARY text as the override name.
4. THE Import_API SHALL create override entries for each successfully mapped event in the active Team_Context.
5. WHEN an imported event conflicts with an existing override on the same date and shift_type, THE Import_API SHALL return the conflict in the response and skip that event unless the `overwrite` query parameter is set to `true`. WHEN `overwrite=true` is set and a conflict exists, THE Import_API SHALL overwrite the existing override with the imported event data.

### Requirement 6: ICS Import Response

**User Story:** As a team lead, I want clear feedback on the import result, so that I know which events were imported and which had issues.

#### Acceptance Criteria

1. WHEN import completes, THE Import_API SHALL return a JSON response with the fields `imported_count`, `skipped_count`, `conflicts`, and `errors`.
2. THE Import_API SHALL include in the `conflicts` array each event that was skipped due to an existing override, with the date, shift_type, and existing assignee name.
3. THE Import_API SHALL include in the `errors` array a description of each event that could not be parsed or mapped.
4. WHEN all events in the file are successfully imported without any skips or errors, THE Import_API SHALL return HTTP 200.
5. WHEN some events are skipped but at least one is imported, THE Import_API SHALL return HTTP 207 with the partial result summary.
6. IF no events can be imported from the file, THEN THE Import_API SHALL return HTTP 422 with the error details.
7. IF the file contains no VEVENT components (empty ICS file), THEN THE Import_API SHALL return HTTP 422 with an error indicating no events found.

### Requirement 7: ICS Round-Trip Integrity

**User Story:** As a developer, I want to verify that exporting and re-importing a schedule produces equivalent data, so that no information is lost in the conversion process.

#### Acceptance Criteria

1. FOR ALL valid ScheduleSlot lists, exporting to ICS via the ICS_Exporter then parsing via the ICS_Parser SHALL produce event records with equivalent date, shift_type, start_time, end_time, and teammate assignments as the original ScheduleSlots.
2. FOR ALL valid ICS text produced by the ICS_Formatter, parsing via the ICS_Parser then formatting via the ICS_Formatter SHALL produce output equivalent to the original ICS text (round-trip property).

### Requirement 8: ICS Export Error Handling

**User Story:** As a shift worker, I want clear error messages when export fails, so that I can understand what went wrong.

#### Acceptance Criteria

1. IF the specified year cannot produce a valid schedule (no teammates configured), THEN THE Export_API SHALL return HTTP 400 with a descriptive error message.
2. IF an invalid date format is provided in the `from` or `to` query parameters, THEN THE Export_API SHALL always return HTTP 400 with an error message indicating the invalid date format, regardless of the cause of the format error.
3. IF an internal error occurs during ICS generation, THEN THE Export_API SHALL return HTTP 500 with a generic error message and log the exception details.

### Requirement 9: Frontend ICS Export Integration

**User Story:** As a shift worker, I want to export ICS files from the Export page, so that I can access the feature from the existing UI.

#### Acceptance Criteria

1. THE Export page SHALL display an "ICS Calendar" export button alongside the existing CSV, JSON, and Excel export options.
2. WHEN the user clicks the "ICS Calendar" button, THE Export page SHALL initiate a download request to `/api/export/<year>/ics` with any active date filters applied.
3. WHILE an ICS export request is in progress, THE Export page SHALL display a loading indicator on the ICS button.

### Requirement 10: Frontend ICS Import Integration

**User Story:** As a team lead, I want to import ICS files from the Team Management page, so that I can load external schedules alongside the existing CSV and JSON import options.

#### Acceptance Criteria

1. THE Team Management page SHALL display an "Import ICS" button alongside the existing "Import CSV" and "Import JSON" buttons.
2. WHEN the user clicks "Import ICS", THE Team Management page SHALL open a file picker dialog filtered to `.ics` files.
3. WHEN a file is selected, THE Team Management page SHALL upload the file to `/api/import/ics` and display the result summary (imported count, skipped count, conflicts, errors).
4. WHEN conflicts are reported in the import response, THE Team Management page SHALL first display the full import summary (imported count, skipped count, errors), then offer a "Resolve Conflicts" action that shows the conflict list and allows the user to re-import with the `overwrite=true` option.

### Requirement 11: JSON Schedule Import Endpoint

**User Story:** As a team lead, I want to import a JSON schedule file containing shift assignments, so that I can load externally-created or previously-exported schedules into DC-ShiftMaster Pro as overrides.

#### Acceptance Criteria

1. WHEN a POST request with a `.json` file is made to `/api/import/schedule-json`, THE Import_API SHALL parse the file and create override entries for the active team.
2. THE Import_API SHALL accept JSON files containing an array of schedule objects with fields: `date` (YYYY-MM-DD), `shift_type` ("day" or "night"), `name` (teammate name for the override).
3. WHEN a schedule entry has a missing or invalid `date` field, THE Import_API SHALL skip that entry and include it in a list of errors returned to the client.
4. WHEN a schedule entry has an invalid `shift_type` (not "day" or "night"), THE Import_API SHALL skip that entry and report it in errors.
5. WHEN a schedule entry has a missing or empty `name` field, THE Import_API SHALL skip that entry and report it in errors.
6. WHEN an imported entry conflicts with an existing override on the same date and shift_type, THE Import_API SHALL skip that entry and report it in the `conflicts` array unless the `overwrite` query parameter is set to `true`.
7. WHEN `overwrite=true` is set, THE Import_API SHALL replace existing overrides with the imported values.
8. THE Import_API SHALL return a JSON response with `imported_count`, `skipped_count`, `conflicts`, and `errors` following the same structure as the ICS import response.
9. IF the uploaded file exceeds 5 MB in size, THEN THE Import_API SHALL return HTTP 413 with an error message.
10. IF the file is not valid JSON or is not an array, THEN THE Import_API SHALL return HTTP 400 with a descriptive error message.
11. WHILE a Team_Context is active, THE Import_API SHALL create overrides scoped to the active team only.

### Requirement 12: Frontend JSON Schedule Import Integration

**User Story:** As a team lead, I want to import JSON schedule files from the Team Management page, so that I can restore previously-exported schedules alongside other import options.

#### Acceptance Criteria

1. THE Team Management page SHALL display an "Import Schedule" button (or dropdown option) alongside the existing import buttons.
2. WHEN the user clicks "Import Schedule", THE Team Management page SHALL open a file picker dialog filtered to `.json` files.
3. WHEN a file is selected, THE Team Management page SHALL upload the file to `/api/import/schedule-json` and display the result summary (imported count, skipped count, conflicts, errors).
4. WHEN conflicts are reported in the import response, THE Team Management page SHALL display a confirmation dialog listing the conflicts and offering to re-import with the `overwrite=true` option.

### Requirement 13: JSON Schedule Import Round-Trip

**User Story:** As a developer, I want to verify that the existing JSON export format is compatible with the JSON schedule import, so that exports can be re-imported without data loss.

#### Acceptance Criteria

1. THE Import_API SHALL accept JSON files in the format produced by the existing `/api/export/<year>/json` endpoint (array of objects with `date`, `shift_type`, `name`, `start_time`, `end_time`, `teammates`, `is_override` fields).
2. WHEN extra fields beyond `date`, `shift_type`, and `name` are present in an entry, THE Import_API SHALL ignore those fields without error.
3. FOR ALL valid schedule exports, importing the exported JSON file SHALL produce override entries equivalent to the non-computed assignments in the original schedule.
