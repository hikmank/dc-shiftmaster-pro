# Implementation Plan: ICS Calendar Export & Import

## Overview

Implement ICS (iCalendar RFC 5545) export and import capabilities plus JSON schedule import for DC-ShiftMaster Pro. This adds a new Flask blueprint with three endpoints, three core Python modules (ICSExporter, ICSParser, JSONScheduleImporter), and frontend UI extensions to the Export and Team Management pages. The implementation reuses the existing `_compute_and_validate()` helper pattern and `DatabaseManager.set_override()` for data persistence.

## Tasks

- [x] 1. Implement ICS Exporter module
  - [x] 1.1 Create `dc_shiftmaster/ics_export.py` with `ICSExporter` class
    - Implement `export(schedule, shift_windows)` method returning complete ICS text
    - Implement `_format_vevent(slot, shift_windows, dtstamp)` for individual VEVENT components
    - Implement `_fold_line(line)` for RFC 5545 75-octet line folding
    - Implement `_format_datetime(d, time_str)` for YYYYMMDDTHHMMSS formatting
    - Handle night shift DTEND on next calendar day when end_time < start_time
    - Produce VCALENDAR with VERSION:2.0, PRODID:-//DC-ShiftMaster Pro//EN, CALSCALE:GREGORIAN
    - Use CRLF line endings throughout, generate deterministic UIDs as `{date}-{shift_type}@dc-shiftmaster`
    - Set SUMMARY as `{shift_type} Shift - {comma-separated teammate names}`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 1.2 Write property tests for ICS Exporter (Properties 3, 4, 5)
    - **Property 3: Valid VCALENDAR Structure** — for any list of ScheduleSlots, output begins with BEGIN:VCALENDAR, ends with END:VCALENDAR, contains VERSION:2.0, PRODID, CALSCALE
    - **Property 4: CRLF Line Endings** — every line ends with CRLF, no bare LF exists
    - **Property 5: Line Folding Compliance** — no content line exceeds 75 octets after unfolding
    - Create `tests/test_ics_properties.py` with Hypothesis strategies: `schedule_slot_strategy()`, `shift_windows_strategy()`
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

- [x] 2. Implement ICS Parser module
  - [x] 2.1 Create `dc_shiftmaster/ics_parser.py` with dataclasses and `ICSParser` class
    - Define `ParsedEvent` dataclass (dtstart, dtend, summary, uid)
    - Define `ParseResult` dataclass (events, skipped, errors)
    - Implement `parse(ics_text)` method extracting VEVENT components
    - Implement `_unfold_lines(text)` for CRLF+whitespace continuation unfolding
    - Implement `_extract_vevents(lines)` for extracting property dicts from VEVENT blocks
    - Raise ValueError if text does not begin with BEGIN:VCALENDAR
    - Skip VEVENTs missing DTSTART or DTEND, add to skipped list
    - _Requirements: 4.2, 4.3, 4.4_

  - [x] 2.2 Write property test for ICS Export-Import Round-Trip (Property 1)
    - **Property 1: ICS Export-Import Round-Trip** — for any valid ScheduleSlots, export then parse produces equivalent date, shift_type, start_time, end_time, and teammate assignments
    - **Validates: Requirements 7.1, 3.1, 3.2, 3.3, 3.5**

  - [x] 2.3 Write property test for ICS Format Round-Trip (Property 2)
    - **Property 2: ICS Format Round-Trip** — for any ICS text from ICSExporter, parse then re-export (same DTSTAMP) produces byte-equivalent output
    - **Validates: Requirements 7.2**

- [x] 3. Implement JSON Schedule Importer module
  - [x] 3.1 Create `dc_shiftmaster/json_schedule_import.py` with dataclasses and `JSONScheduleImporter` class
    - Define `JSONImportEntry` dataclass (date, shift_type, name)
    - Define `JSONImportResult` dataclass (entries, errors)
    - Implement `parse(json_text)` method validating each entry
    - Raise ValueError if text is not valid JSON or not an array
    - Validate date format (YYYY-MM-DD), shift_type ("day"/"night"), name non-empty
    - Skip invalid entries with descriptive errors, continue processing remaining
    - Ignore extra fields beyond date, shift_type, name (accept export format)
    - _Requirements: 11.2, 11.3, 11.4, 11.5, 13.1, 13.2_

  - [x] 3.2 Write property test for Invalid JSON Entries Rejected (Property 9)
    - **Property 9: Invalid JSON Entries Rejected** — any entry with missing/invalid date, invalid shift_type, or missing/empty name is rejected with a descriptive error
    - Create `json_entry_strategy()` and `invalid_json_entry_strategy()` Hypothesis strategies
    - **Validates: Requirements 11.3, 11.4, 11.5**

  - [x] 3.3 Write property test for JSON Export-Import Round-Trip (Property 10)
    - **Property 10: JSON Export-Import Round-Trip** — for any valid schedule JSON export, importing produces equivalent override entries
    - **Validates: Requirements 13.1, 13.2, 13.3**

- [x] 4. Checkpoint - Ensure all core module tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement ICS routes blueprint
  - [x] 5.1 Create `dc_shiftmaster_html/routes_ics.py` with `ics_bp` Flask blueprint
    - Implement `export_ics(year)` GET route at `/api/export/<int:year>/ics`
    - Reuse `_compute_and_validate()` from routes_export for schedule computation and date filtering
    - Set Content-Type to `text/calendar; charset=utf-8` and Content-Disposition with filename `{REGION}_{YEAR}_schedule.ics`
    - Return ICS text from ICSExporter in response body
    - Handle errors: 400 for no teammates/invalid dates, 500 for internal errors
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 8.1, 8.2, 8.3_

  - [x] 5.2 Implement `import_ics()` POST route at `/api/import/ics`
    - Validate file upload present, check 5 MB size limit (return 413)
    - Parse file via ICSParser (return 400 if invalid ICS format)
    - Determine shift_type from DTSTART hour (05-13 = day, else night)
    - Resolve teammate name from SUMMARY against current team roster
    - Check for conflicts with existing overrides (skip or overwrite based on `overwrite` query param)
    - Create overrides via `DatabaseManager.set_override()` scoped to active team
    - Return JSON response with imported_count, skipped_count, conflicts, errors
    - Return 422 if no events imported, 200 otherwise
    - _Requirements: 4.1, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 5.3 Implement `import_schedule_json()` POST route at `/api/import/schedule-json`
    - Validate file upload present, check 5 MB size limit (return 413)
    - Parse file via JSONScheduleImporter (return 400 if invalid JSON/not array)
    - Check for conflicts with existing overrides (skip or overwrite based on `overwrite` query param)
    - Create overrides via `DatabaseManager.set_override()` scoped to active team
    - Return JSON response with imported_count, skipped_count, conflicts, errors
    - Return 422 if no entries imported, 200 otherwise
    - _Requirements: 11.1, 11.6, 11.7, 11.8, 11.9, 11.10, 11.11_

  - [x] 5.4 Register `ics_bp` blueprint in `dc_shiftmaster_html/server.py`
    - Import and register the ics_bp blueprint alongside existing export_bp and import_bp
    - _Requirements: 1.1, 4.1, 11.1_

  - [x] 5.5 Write property tests for shift type classification and name resolution (Properties 7, 8)
    - **Property 7: Shift Type Classification from Hour** — for any hour 0-23, returns "day" if 5-13 inclusive, "night" otherwise
    - **Property 8: Name Resolution from SUMMARY** — if SUMMARY contains a roster name, that name is used; otherwise full SUMMARY text is used
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [x] 5.6 Write property test for Conflict Detection and Overwrite (Property 11)
    - **Property 11: Conflict Detection and Overwrite** — without overwrite=true conflicting entries are skipped and reported; with overwrite=true imported values replace existing overrides
    - **Validates: Requirements 5.5, 11.6, 11.7**

  - [x] 5.7 Write property test for Date Range Filtering (Property 6)
    - **Property 6: Date Range Filtering** — filtering by from/to dates includes only slots within range, excludes none that belong
    - **Validates: Requirements 1.2, 1.3**

- [x] 6. Checkpoint - Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement frontend ICS export integration
  - [x] 7.1 Add ICS export button to `dc_shiftmaster_html/static/js/export.js`
    - Add "ICS Calendar" button alongside existing CSV, JSON, Excel export options
    - On click, initiate download request to `/api/export/<year>/ics` with active date filters
    - Show loading indicator on button while request is in progress
    - Handle error responses with user notification
    - _Requirements: 9.1, 9.2, 9.3_

- [x] 8. Implement frontend import integration
  - [x] 8.1 Add ICS and JSON schedule import buttons to `dc_shiftmaster_html/static/js/team.js`
    - Add "Import ICS" button alongside existing import buttons, with file picker filtered to `.ics`
    - Add "Import Schedule" button alongside existing import buttons, with file picker filtered to `.json`
    - On file selection, upload to respective endpoint and display result summary (imported_count, skipped_count, conflicts, errors)
    - When conflicts are reported, display confirmation dialog offering re-import with `overwrite=true`
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 12.1, 12.2, 12.3, 12.4_

- [x] 9. Write unit tests for routes and edge cases
  - [x] 9.1 Create `tests/test_ics_unit.py` with unit tests
    - Test export response headers (Content-Type: text/calendar, Content-Disposition filename)
    - Test DTSTAMP uses current UTC time (mocked)
    - Test UID determinism (same input produces same UID)
    - Test file size limit returns 413
    - Test empty schedule export produces valid ICS with no VEVENTs
    - Test invalid date params return 400
    - Test import with no teammates configured returns 400 for export
    - Test conflict detection and overwrite behavior
    - Test team_id scoping for both export and import
    - _Requirements: 1.4, 3.6, 3.7, 4.5, 8.1, 8.2, 8.3, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (11 properties total)
- Unit tests validate specific examples and edge cases
- The design uses Python with Flask + Hypothesis — all code tasks use this stack
- ICS export reuses `_compute_and_validate()` from existing `routes_export.py`
- Import operations create overrides via `DatabaseManager.set_override(date, shift_type, name, team_id=)`
- Blueprint registration follows the existing pattern in `server.py`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "3.1"] },
    { "id": 1, "tasks": ["1.2", "2.1", "3.2", "3.3"] },
    { "id": 2, "tasks": ["2.2", "2.3", "5.1", "5.2", "5.3"] },
    { "id": 3, "tasks": ["5.4", "5.5", "5.6", "5.7"] },
    { "id": 4, "tasks": ["7.1", "8.1", "9.1"] }
  ]
}
```
