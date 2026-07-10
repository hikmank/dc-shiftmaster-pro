# Implementation Plan: Custom Schedule Shift

## Overview

Implement a "Custom" shift type in DC-ShiftMaster Pro that allows teammates to work on individually selected days of the week (Mon–Sun) rather than following a fixed rotation. Changes span the database schema, API layer, scheduling engine, frontend UI, and CSV export/import.

## Tasks

- [x] 1. Database layer — add custom_days column and update CHECK constraint
  - [x] 1.1 Add `custom_days` TEXT column to the `teammates` table and update the CHECK constraint to allow "Custom" shift type
    - In `dc_shiftmaster/database.py`, update the `_create_tables` method so the `teammates` CREATE TABLE statement includes `custom_days TEXT NOT NULL DEFAULT ''` and changes the CHECK to `CHECK(shift_type IN ('FHD','FHN','BHD','BHN','Custom'))`
    - Add a migration step in `_migrate` that ALTERs existing databases: add the `custom_days` column if not present, and recreate the table to update the CHECK constraint (SQLite requires table recreation for CHECK changes)
    - Ensure deserialization of `custom_days` from JSON string to Python list when reading teammates, and serialization from list to JSON string when writing
    - Update all `Teammate` SELECT queries to include the `custom_days` column
    - Update INSERT/UPDATE queries to persist `custom_days`
    - _Requirements: 3.1, 3.2, 6.1_

  - [x] 1.2 Write property test for custom days persistence round-trip
    - **Property 1: Custom days persistence round-trip**
    - **Validates: Requirements 3.1, 3.2, 3.3**
    - Use Hypothesis to generate random non-empty subsets of {Mon, Tue, Wed, Thu, Fri, Sat, Sun}, save a Custom teammate, retrieve it, and assert the custom_days match

  - [x] 1.3 Write property test for empty custom_days validation rejection
    - **Property 2: Empty custom_days validation rejection**
    - **Validates: Requirements 3.4**
    - Use Hypothesis to generate teammate data with shift_type="Custom" and empty custom_days, call the API, and assert 400 status with no persistence

- [x] 2. API layer — validate custom_days and update CRUD endpoints
  - [x] 2.1 Update `routes_teammates.py` to accept and validate `custom_days` in POST/PUT endpoints
    - Add `"Custom"` to `VALID_SHIFT_TYPES` set
    - Define `VALID_DAYS = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}`
    - In POST `/api/teammates` and PUT `/api/teammates/<id>`: when `shift_type == "Custom"`, require `custom_days` to be a non-empty list of valid day abbreviations; return 400 with appropriate error message on failure
    - For standard shift types, ignore/clear any provided `custom_days`
    - Update GET `/api/teammates` to include `custom_days` in each teammate JSON response
    - _Requirements: 3.1, 3.2, 3.4_

  - [x] 2.2 Update CSV import endpoint to parse the `custom_days` column
    - In the CSV import handler, parse a fourth column `custom_days` with semicolon-separated day abbreviations
    - When `shift_type == "Custom"`, validate all day values; skip row if empty or invalid
    - Add skipped row numbers to the `skipped_rows` response list
    - For standard shift types with non-empty custom_days column, ignore the value
    - _Requirements: 5.3, 5.4_

  - [x] 2.3 Write property test for CSV import rejecting invalid custom_days
    - **Property 5: CSV import rejects invalid custom_days for Custom rows**
    - **Validates: Requirements 5.4**
    - Use Hypothesis to generate CSV rows with shift_type "Custom" and invalid/empty day values, import them, and assert they appear in skipped_rows

- [x] 3. Scheduling engine — custom day matching logic
  - [x] 3.1 Add custom day resolution to `compute_annual_schedule` in `dc_shiftmaster/scheduling.py`
    - Define `WEEKDAY_ABBREVS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]`
    - In the schedule loop, handle `shift_type == "Custom"` teammates by checking if the current date's weekday abbreviation is in the teammate's `custom_days` list
    - Custom teammates are added to the day shift slot on their scheduled days
    - Ensure standard shift type teammates continue to use existing rotation logic unchanged
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 3.2 Write property test for custom teammates scheduled only on specified weekdays
    - **Property 6: Custom teammates scheduled only on their specified weekdays**
    - **Validates: Requirements 6.1, 6.3**
    - Use Hypothesis to generate Custom teammates with random day subsets and random date ranges, compute schedule, and assert the teammate appears if and only if the date's weekday is in custom_days

  - [x] 3.3 Write property test for standard teammates unaffected by Custom teammates
    - **Property 7: Standard teammates unaffected by Custom teammates**
    - **Validates: Requirements 6.2**
    - Use Hypothesis to generate a team with standard teammates, compute schedule with and without Custom teammates present, and assert the standard teammates' slots are identical

- [x] 4. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Frontend — extend team.js with Custom shift type support
  - [x] 5.1 Extend `SHIFT_TYPES` and update the Add Teammate form in `team.js`
    - Change `SHIFT_TYPES` from `['FHD', 'FHN', 'BHD', 'BHN']` to `['FHD', 'FHN', 'BHD', 'BHN', 'Custom']`
    - In `showAddForm()`, add a day selector container (seven labeled checkboxes: Mon–Sun) below the shift type dropdown, initially hidden
    - Add an event listener on the shift type dropdown: show day selector when "Custom" is selected, hide it otherwise
    - When showing day selector on switch to "Custom", ensure all checkboxes start unchecked
    - On submit, collect checked days into a `custom_days` array and include in the API payload
    - Add client-side validation: if shift_type is "Custom" and no days are checked, show toast error "Please select at least one day" and block save
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 3.1, 3.4_

  - [x] 5.2 Update the inline edit form in `team.js` to support Custom shift type
    - In `showInlineEdit()`, add the day selector checkboxes below the shift type dropdown
    - When editing a Custom teammate, pre-check the checkboxes matching `t.custom_days`
    - Add change listener on shift type select: show/hide day selector, reset checkboxes when switching to Custom
    - On save, include `custom_days` array in the update payload
    - Apply same validation as add form (at least one day required for Custom)
    - _Requirements: 1.3, 2.1, 3.3, 3.4_

  - [x] 5.3 Update `renderList()` to display Custom group section and day labels
    - Add "Custom" to the group iteration so a "Custom (N)" section appears in the team list
    - In `createRow()`, when `t.shift_type === "Custom"` and `t.custom_days` exists, display the days as a comma-separated string next to the teammate name
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 5.4 Update CSV export in `team.js` to include custom_days column
    - Change the CSV header to `name,shift_type,custom_start,custom_days`
    - For Custom teammates, output their custom_days as semicolon-separated values in the fourth column
    - For standard shift type teammates, output an empty fourth column
    - _Requirements: 5.1, 5.2_

  - [x] 5.5 Write unit tests for frontend Custom shift UI behavior
    - Test SHIFT_TYPES array includes all five values
    - Test day selector visibility toggling based on dropdown value
    - Test checkboxes reset when switching to Custom
    - Test edit form pre-checks stored custom_days
    - Test Custom group section renders with correct count
    - Test teammate row displays comma-separated day labels for Custom teammates
    - _Requirements: 1.1, 2.1, 2.4, 4.1, 4.2, 4.3_

- [x] 6. CSV export/import round-trip property tests
  - [x] 6.1 Write property test for CSV export/import round-trip for custom days
    - **Property 3: CSV export/import round-trip for custom days**
    - **Validates: Requirements 5.1, 5.3**
    - Use Hypothesis to generate Custom teammates with random non-empty day subsets, export to CSV, import the CSV, and assert the resulting custom_days sets are identical (order-independent)

  - [x] 6.2 Write property test for CSV export producing empty custom_days for standard teammates
    - **Property 4: CSV export produces empty custom_days for standard teammates**
    - **Validates: Requirements 5.2**
    - Use Hypothesis to generate teammates with standard shift types (FHD/FHN/BHD/BHN), export to CSV, and assert the custom_days column is empty for each row

- [x] 7. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Backend uses Python (Hypothesis for property tests, pytest for unit tests)
- Frontend uses JavaScript (existing team.js patterns)
- Database migration must handle both fresh installs and existing databases with the old CHECK constraint

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.1", "3.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.2", "3.3"] },
    { "id": 3, "tasks": ["5.1", "5.3", "5.4"] },
    { "id": 4, "tasks": ["5.2", "5.5", "6.1", "6.2"] }
  ]
}
```
