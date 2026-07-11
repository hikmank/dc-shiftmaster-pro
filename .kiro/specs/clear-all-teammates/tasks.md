# Implementation Plan: Clear All Teammates

## Overview

Add a bulk-delete capability to remove all teammates from a team's roster in one operation. Implementation proceeds bottom-up: database method first, then the API route, then the frontend button with confirmation dialog, then property-based and unit tests.

## Tasks

- [x] 1. Implement backend database method and API route
  - [x] 1.1 Add `clear_all_teammates` method to `DatabaseManager` in `dc_shiftmaster/database.py`
    - Add method with signature `def clear_all_teammates(self, team_id: int = None) -> int`
    - When `team_id` is provided, execute `DELETE FROM teammates WHERE team_id = ?`
    - When `team_id` is None, execute `DELETE FROM teammates` (legacy unscoped behavior)
    - Return `cursor.rowcount` as the count of deleted rows
    - Execute within a single transaction (commit after delete)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 1.2 Add `DELETE /api/teammates/all` route in `dc_shiftmaster_html/routes_teammates.py`
    - Register route BEFORE `<int:tid>` routes to avoid Flask matching "all" as a path parameter
    - Extract `team_id` from `g.team_id` (if present) for multi-team scoping
    - Call `db.clear_all_teammates(team_id)` and return `200 {"deleted": <count>}`
    - Wrap in try/except to catch database errors and return `500 {"error": "<message>"}`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2_

- [x] 2. Implement frontend Clear All button and confirmation
  - [x] 2.1 Add `clearAllTeammates` helper to the API module in `dc_shiftmaster_html/static/js/api.js`
    - Add method: `clearAllTeammates: function() { return fetch('/api/teammates/all', { method: 'DELETE' }).then(handleResponse); }`
    - _Requirements: 1.1_

  - [x] 2.2 Add "Clear All" button and confirmation logic to `dc_shiftmaster_html/static/js/team.js`
    - Add a "Clear All" button with `btn-danger` class in the DOMContentLoaded event listener, alongside existing Add/Import/Export buttons
    - Store reference to current teammates list to enable/disable button (disabled when list is empty)
    - On click: show `confirm("Remove all N teammates? This cannot be undone.")` with the current count
    - On confirm: call `API.clearAllTeammates()`, show success toast with deleted count, reload list
    - On cancel: take no action
    - On API error: show error toast with message
    - After successful load, update button disabled state based on teammate count
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3_

- [x] 3. Checkpoint - Verify backend and frontend integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Write tests for clear all teammates
  - [x] 4.1 Write unit tests for `clear_all_teammates` in `tests/test_clear_all_teammates.py`
    - Test: empty team returns 0 deleted count
    - Test: team with N teammates returns N and list is empty after
    - Test: legacy unscoped clear removes all records across teams
    - Test: database error in route returns 500 with error message
    - Test: route returns HTTP 200 on success
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 2.2, 6.3_

  - [x] 4.2 Write property test: clear removes all and returns correct count
    - **Property 1: Clear removes all teammates and returns correct count**
    - Use Hypothesis to generate random teammate lists (varying count 0–50, random names and shift types)
    - Insert N teammates for a team, call `clear_all_teammates(team_id)`, assert return value == N and `get_teammates(team_id)` returns empty list
    - **Validates: Requirements 1.1, 1.2, 1.3, 6.2, 6.4**

  - [x] 4.3 Write property test: team isolation
    - **Property 2: Team isolation — clearing one team preserves others**
    - Use Hypothesis to generate two distinct teams with arbitrary teammate lists
    - Insert teammates for both teams, call `clear_all_teammates(team_id=A)`, assert team B's teammates are unchanged (same count, IDs, names, shift types)
    - **Validates: Requirements 2.1, 2.3**

- [x] 5. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The route MUST be registered before `<int:tid>` routes in the blueprint to avoid Flask route conflicts

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["4.1", "4.2", "4.3"] }
  ]
}
```
