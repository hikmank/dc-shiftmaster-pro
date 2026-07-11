# Implementation Plan: Delete Schedule Overrides

## Overview

Implement bulk-delete capabilities for schedule overrides in DC-ShiftMaster Pro. This adds new DatabaseManager methods for bulk operations, a `DELETE /api/overrides/bulk` endpoint with preview support, and an Override Panel UI on the Team Management page with date-range filtering, year-wide clearing, and individual selection deletion modes.

## Tasks

- [x] 1. Implement bulk-delete database methods
  - [x] 1.1 Add `count_overrides_in_range`, `bulk_delete_overrides_by_range`, `bulk_delete_overrides_by_keys`, and `bulk_delete_overrides_by_year` methods to `DatabaseManager` in `dc_shiftmaster/database.py`
    - `count_overrides_in_range(start_date, end_date, team_id)` returns count of matching overrides
    - `bulk_delete_overrides_by_range(start_date, end_date, team_id)` deletes overrides within inclusive date range, returns deleted count
    - `bulk_delete_overrides_by_keys(keys, team_id)` deletes overrides matching specific (date, shift_type) pairs, returns deleted count
    - `bulk_delete_overrides_by_year(year, team_id)` deletes all overrides for a year, returns deleted count
    - All operations execute within a single database transaction (BEGIN...COMMIT with rollback on error)
    - Scope all queries by `team_id` parameter
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

  - [x] 1.2 Write property test for range delete correctness
    - **Property 3: Range Delete Correctness**
    - **Validates: Requirements 2.1, 5.1**
    - Test file: `tests/test_bulk_delete_props.py`
    - Generate random override sets and date ranges; verify overrides inside the range are deleted and overrides outside are preserved

  - [x] 1.3 Write property test for year delete correctness
    - **Property 5: Year Delete Correctness**
    - **Validates: Requirements 3.1**
    - Test file: `tests/test_bulk_delete_props.py`
    - Generate multi-year override sets and target year; verify only target year overrides are deleted

  - [x] 1.4 Write property test for keys delete correctness
    - **Property 6: Keys Delete Correctness**
    - **Validates: Requirements 4.3, 5.2**
    - Test file: `tests/test_bulk_delete_props.py`
    - Generate override sets and random subsets of keys; verify exactly selected overrides are removed

  - [x] 1.5 Write property test for deleted count accuracy
    - **Property 7: Deleted Count Accuracy**
    - **Validates: Requirements 5.3**
    - Test file: `tests/test_bulk_delete_props.py`
    - For all three modes, verify `deleted_count` equals actual rows removed (count_before − count_after)

  - [x] 1.6 Write property test for team isolation
    - **Property 9: Team Isolation**
    - **Validates: Requirements 5.5**
    - Test file: `tests/test_bulk_delete_props.py`
    - Two-team scenarios: bulk-delete for team A leaves team B overrides completely unchanged

- [x] 2. Implement bulk-delete API routes
  - [x] 2.1 Add `POST /api/overrides/bulk/preview` and `DELETE /api/overrides/bulk` routes in `dc_shiftmaster_html/routes_overrides.py`
    - Parse request body to determine mode: "range", "keys", or "year"
    - Validate inputs: date format (YYYY-MM-DD), start ≤ end for ranges, non-empty keys list, 4-digit year
    - Return 400 with descriptive error messages for invalid requests
    - Preview endpoint returns `{count: N}` via the count method
    - Delete endpoint calls the appropriate bulk-delete method and returns `{deleted_count: N}`
    - Use `g.team_id` for team scoping
    - _Requirements: 2.1, 2.2, 3.1, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 2.2 Write property test for invalid range rejection
    - **Property 4: Invalid Range Rejection**
    - **Validates: Requirements 2.2**
    - Test file: `tests/test_bulk_delete_props.py`
    - Generate date pairs where start > end; verify 400 response and no deletions occur

  - [x] 2.3 Write property test for all-or-nothing rejection
    - **Property 8: Invalid Request All-or-Nothing Rejection**
    - **Validates: Requirements 5.4**
    - Test file: `tests/test_bulk_delete_props.py`
    - Generate requests with mixed valid/invalid keys; verify 400 and zero deletions

  - [x] 2.4 Write unit tests for API route handlers
    - Test file: `tests/test_bulk_delete_api.py`
    - Verify correct HTTP status codes (200, 400, 500) and response shapes for each mode
    - Test specific invalid payloads return 400 with expected error messages
    - Test edge case: deletion of zero overrides returns `{deleted_count: 0}`, not an error
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 3. Checkpoint - Backend verification
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement Override Panel UI
  - [x] 4.1 Create `dc_shiftmaster_html/static/js/overrides-panel.js` module
    - Render override list grouped by month using data from `GET /api/overrides/<year>`
    - Display date, shift type, and assigned name for each override entry
    - Show "no overrides" message when list is empty; hide it when overrides exist
    - Provide year selector that refreshes the override list on change
    - Add date range inputs (start date, end date) with client-side validation (start ≤ end)
    - Add checkbox per override entry and "Select All" toggle
    - Add "Clear All Overrides" button for year-wide deletion
    - Add "Delete Selected" button (disabled when no overrides selected)
    - Add "Delete by Range" button
    - Wire API calls: `POST /api/overrides/bulk/preview` for counts, `DELETE /api/overrides/bulk` for deletion
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 3.1, 4.1, 4.2, 4.3, 4.4_

  - [x] 4.2 Implement confirmation dialog for bulk deletions
    - Show override count from preview endpoint before proceeding
    - For "Clear All Year" mode: require user to type confirmation phrase ("DELETE ALL") before enabling confirm button
    - Block deletion if dialog fails to render (fail-safe)
    - For date-range and selective modes: standard confirm/cancel dialog with count display
    - _Requirements: 2.3, 3.2, 4.2_

  - [x] 4.3 Add Override Panel section to the Team Management view in `dc_shiftmaster_html/static/index.html`
    - Add the Override Panel container element inside the team-view section
    - Include `overrides-panel.js` script tag
    - _Requirements: 1.1_

  - [x] 4.4 Write property test for override display completeness
    - **Property 1: Override Display Completeness**
    - **Validates: Requirements 1.1, 1.2**
    - Test file: `dc_shiftmaster_html/static/js/__tests__/overrides-panel.property.test.js`
    - Use fast-check to generate random override sets; verify grouping places every override into the correct month, loses none, adds no duplicates

  - [x] 4.5 Write property test for empty state biconditional
    - **Property 2: Empty State Biconditional**
    - **Validates: Requirements 1.3**
    - Test file: `dc_shiftmaster_html/static/js/__tests__/overrides-panel.property.test.js`
    - Use fast-check to verify "no overrides" message appears iff override list is empty

- [x] 5. Implement post-deletion UI feedback and dashboard refresh
  - [x] 5.1 Add success/error toast notifications and dashboard calendar refresh after bulk-delete operations in `overrides-panel.js`
    - On success: show toast with "N overrides removed" (including when N = 0)
    - On error: show error toast with failure description
    - After any successful deletion: refresh the Override Panel list and trigger dashboard calendar refresh
    - Add `API.bulkDeleteOverrides(payload)` and `API.previewBulkDelete(payload)` helper methods
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 5.2 Write Jest tests for Override Panel
    - Test file: `dc_shiftmaster_html/static/js/__tests__/overrides-panel.test.js`
    - Test grouped-by-month rendering, checkbox states, select-all behavior
    - Test confirmation dialog: shows correct count, phrase validation for clear-all
    - Test correct API payloads sent for each deletion mode
    - Test toast feedback: success/error messages rendered correctly
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 6. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit/integration tests validate specific examples and edge cases
- Backend uses Python (pytest + hypothesis); frontend uses JavaScript (Jest + fast-check)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "1.5", "1.6", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4"] },
    { "id": 3, "tasks": ["4.1", "4.3"] },
    { "id": 4, "tasks": ["4.2", "4.4", "4.5"] },
    { "id": 5, "tasks": ["5.1"] },
    { "id": 6, "tasks": ["5.2"] }
  ]
}
```
