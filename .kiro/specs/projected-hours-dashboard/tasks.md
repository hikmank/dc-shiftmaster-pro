# Implementation Plan: Projected Hours Dashboard

## Overview

This plan implements the Projected Hours Dashboard feature incrementally, starting with the core computation layer (ProjectionService), then the API routes, then the WebSocket broadcast extension, and finally the frontend module. Property-based tests validate each computation layer using Hypothesis, ensuring correctness properties hold across all valid inputs.

## Tasks

- [ ] 1. Implement ProjectionService core computation
  - [ ] 1.1 Create ProjectionService class with data models and classify_status function
    - Create `dc_shiftmaster_html/projection_service.py`
    - Define dataclasses: `ProjectionResult`, `DailyBreakdownEntry`, `GroupSummary`, `ImpactPreview`
    - Implement `classify_status(value, limit)` function with thresholds (exceeding > limit, approaching > limit × 0.9, compliant otherwise)
    - Implement `ProjectionService.__init__` accepting `DatabaseManager` and `SchedulingEngine`
    - Define class constants: `WEEKLY_HOURS_LIMIT = 60.0`, `WEEKLY_DAYS_LIMIT = 6`, `DAILY_HOURS_LIMIT = 12.0`, `APPROACHING_THRESHOLD = 0.9`
    - _Requirements: 1.3, 1.4, 1.5, 1.6, 6.2, 6.3, 6.4_

  - [ ]* 1.2 Write property test for classify_status (Property 1)
    - **Property 1: Compliance Status Classification**
    - **Validates: Requirements 1.3, 1.4, 1.5, 1.6, 2.3, 2.4, 6.2, 6.3, 6.4, 6.6**

  - [ ] 1.3 Implement compute_projection method for weekly hours, days worked, and max daily hours
    - Implement `compute_projection(teammate, override_group=None)` method
    - Compute all rolling 7-day windows that include today (today-6 through today+6)
    - For each window: sum shift durations using SchedulingEngine and ComplianceValidator logic
    - Return maximum weekly hours (1 decimal), maximum days worked (integer), maximum daily hours (1 decimal)
    - Apply `classify_status` to each metric and include in `ProjectionResult`
    - Support `override_group` parameter to compute as if teammate were in a different rotation group while preserving existing overrides
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 1.4 Write property test for weekly hours computation (Property 2)
    - **Property 2: Maximum Weekly Hours Computation**
    - **Validates: Requirements 3.1, 3.2**

  - [ ]* 1.5 Write property test for weekly days computation (Property 3)
    - **Property 3: Maximum Weekly Days Computation**
    - **Validates: Requirements 3.3**

  - [ ]* 1.6 Write property test for max daily hours computation (Property 4)
    - **Property 4: Maximum Daily Hours Computation**
    - **Validates: Requirements 3.4**

  - [ ]* 1.7 Write property test for alternate group projection with override preservation (Property 5)
    - **Property 5: Alternate Group Projection Preserves Overrides**
    - **Validates: Requirements 3.5**

  - [ ]* 1.8 Write property test for invalid group rejection (Property 6)
    - **Property 6: Invalid Group Rejection**
    - **Validates: Requirements 3.8**

- [ ] 2. Implement daily breakdown and group summary computation
  - [ ] 2.1 Implement compute_daily_breakdown method
    - Implement `compute_daily_breakdown(teammate)` returning `list[DailyBreakdownEntry]`
    - Generate one entry per calendar day in the evaluation period (today-6 through today+6, 13 days)
    - Each entry includes: date, shift_type, effective_start, shift_end, duration_hours (2 decimals), is_override, is_rest_day
    - Compute `rolling_7day_total` as sum of duration_hours from day N-6 through day N
    - Set `daily_hours_exceeds = duration_hours > 12` and `rolling_total_exceeds = rolling_7day_total > 60`
    - Entries ordered chronologically
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 2.2 Write property test for daily breakdown chronological order and completeness (Property 7)
    - **Property 7: Daily Breakdown Chronological Order and Completeness**
    - **Validates: Requirements 4.1**

  - [ ]* 2.3 Write property test for rolling 7-day total computation (Property 8)
    - **Property 8: Rolling 7-Day Total Computation**
    - **Validates: Requirements 4.3**

  - [ ]* 2.4 Write property test for daily breakdown flags correctness (Property 9)
    - **Property 9: Daily Breakdown Flags Correctness**
    - **Validates: Requirements 4.2, 4.4, 4.5**

  - [ ] 2.5 Implement compute_all_projections and compute_group_summary methods
    - Implement `compute_all_projections()` returning `dict[str, list[ProjectionResult]]` grouped by rotation group
    - Implement `compute_group_summary()` returning `dict[str, GroupSummary]`
    - GroupSummary: count compliant, approaching, exceeding teammates per group
    - Derive `overall_status`: "non_compliant" if any exceeding, "warning" if any approaching, "compliant" otherwise
    - Use most severe classification per teammate when multiple limits triggered
    - _Requirements: 6.1, 6.5, 6.6, 6.7, 6.8_

  - [ ]* 2.6 Write property test for group overall status derivation (Property 10)
    - **Property 10: Group Overall Status Derivation**
    - **Validates: Requirements 6.1, 6.5, 6.7, 6.8**

- [ ] 3. Checkpoint - Ensure all backend computation tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement Projection API routes
  - [ ] 4.1 Create routes_projections.py Blueprint with summary endpoint
    - Create `dc_shiftmaster_html/routes_projections.py`
    - Define `projections_bp = Blueprint("projections", __name__)`
    - Implement `GET /api/projections/summary` endpoint
    - Instantiate `ProjectionService` from `current_app.config["db"]` and `current_app.config["engine"]`
    - Call `compute_all_projections()` and `compute_group_summary()`
    - Return JSON with `projections` (grouped by rotation group) and `group_summaries`
    - Handle errors: 500 for missing shift windows or database errors
    - _Requirements: 1.1, 1.2, 1.8, 6.1_

  - [ ] 4.2 Implement teammate detail and preview endpoints
    - Implement `GET /api/projections/<int:teammate_id>` endpoint
    - Call `compute_daily_breakdown(teammate)` and return JSON with daily breakdown
    - Return 404 if teammate_id not found
    - Implement `GET /api/projections/<int:teammate_id>/preview?proposed_group=<group>` endpoint
    - Validate `proposed_group` is one of FHD, FHN, BHD, BHN (return 400 if invalid)
    - Call `compute_projection` with current group and proposed group
    - Return JSON with `current` and `proposed` ProjectionResult objects
    - Return 404 if teammate_id not found
    - _Requirements: 2.1, 3.5, 3.7, 3.8, 4.1, 4.6_

  - [ ]* 4.3 Write property test for impact preview consistency (Property 11)
    - **Property 11: Impact Preview Consistency**
    - **Validates: Requirements 2.1**

  - [ ] 4.4 Register projections blueprint in server.py
    - Import `projections_bp` from `dc_shiftmaster_html.routes_projections`
    - Register blueprint in `create_app()` function alongside existing blueprints
    - _Requirements: 1.1, 3.1_

  - [ ]* 4.5 Write unit tests for API endpoint responses
    - Test GET /api/projections/summary returns correct JSON structure
    - Test GET /api/projections/<id> returns 404 for non-existent teammate
    - Test GET /api/projections/<id>/preview returns 400 for invalid group
    - Test error responses for missing shift windows
    - _Requirements: 1.7, 2.7, 3.7, 3.8_

- [ ] 5. Checkpoint - Ensure all API tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Extend WebSocket broadcast for schedule events
  - [ ] 6.1 Add broadcast_schedule_event function to broadcast.py
    - Add `broadcast_schedule_event(event_type: str, details: dict)` function
    - Event types: `override_changed`, `teammate_updated`, `shift_window_updated`
    - Build JSON message with event_type, details, and ISO timestamp
    - Send to all connected WebSocket clients (reuse existing _clients set and _clients_lock)
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ] 6.2 Integrate broadcast calls into existing route handlers
    - In `routes_overrides.py`: call `broadcast_schedule_event("override_changed", {...})` after successful set/remove override
    - In `routes_teammates.py`: call `broadcast_schedule_event("teammate_updated", {...})` after successful update (shift_type or custom_start change)
    - In settings routes: call `broadcast_schedule_event("shift_window_updated", {...})` after shift window update
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 7. Implement frontend projections module
  - [ ] 7.1 Create projections.js module with load and render functions
    - Create `dc_shiftmaster_html/static/js/projections.js`
    - Implement `Projections` IIFE module matching existing code style (var pattern)
    - Implement `load()`: fetch `GET /api/projections/summary`, render group summary bars and per-teammate projection rows
    - Render compliance status indicators (compliant/approaching/exceeding) with appropriate CSS classes
    - Display compliance limits alongside values (60h weekly, 6 days, 12h daily)
    - Handle API errors: show "Projected hours unavailable" placeholder
    - Display loading indicator during fetch
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 6.1, 6.5, 6.7, 6.8_

  - [ ] 7.2 Implement teammate detail view and impact preview
    - Implement `showDetail(teammateId)`: fetch `GET /api/projections/<id>`, render daily breakdown table
    - Show date, shift type, effective start, shift end, duration, rolling 7-day total per day
    - Highlight days exceeding 12h daily or 60h rolling total
    - Mark override days and rest days distinctly
    - Implement `showPreview(teammateId, proposedGroup)`: fetch preview endpoint, render current vs. proposed comparison
    - Label columns "Current" and "Projected"
    - Show compliance status indicators in both columns
    - Implement `hidePreview()`: dismiss impact preview on cancel/save
    - Handle API errors in preview: show "Preview unavailable" without blocking save/cancel
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ] 7.3 Extend ws.js for schedule event handling and wire real-time refresh
    - Add `onScheduleEvent(callback)` function to WS module
    - Register schedule event listener in `projections.js` that calls `refresh()` on relevant events
    - Implement `refresh(teammateIds)`: re-fetch projections for affected teammates
    - Show stale-data indicator (yellow dot) on refresh failure, retry once after 5 seconds
    - Show loading indicator during refresh
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ] 7.4 Integrate projections module into Team Management page
    - Add `<script src="/static/js/projections.js"></script>` to `index.html`
    - Add Hours Dashboard container HTML to the Team Management section
    - Call `Projections.load()` when Team tab is activated
    - Wire inline edit form's shift_type dropdown change to trigger `Projections.showPreview()`
    - Wire edit save/cancel to call `Projections.hidePreview()`
    - Add API methods to `api.js`: `getProjections()`, `getProjectionForTeammate(id)`, `getProjectionPreview(id, group)`
    - _Requirements: 1.1, 2.1, 2.5, 2.6_

- [ ] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (Properties 1-11)
- Unit tests validate specific examples and edge cases
- The backend uses Python (Flask + Hypothesis for PBT), frontend uses vanilla JavaScript
- All property-based tests go in `tests/test_projection_service_props.py`
- Unit/integration tests go in `tests/test_routes_projections.py`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["1.4", "1.5", "1.6", "1.7", "1.8", "2.1", "2.5"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "2.6"] },
    { "id": 4, "tasks": ["4.1", "4.2"] },
    { "id": 5, "tasks": ["4.3", "4.4", "4.5"] },
    { "id": 6, "tasks": ["6.1"] },
    { "id": 7, "tasks": ["6.2", "7.1"] },
    { "id": 8, "tasks": ["7.2", "7.3"] },
    { "id": 9, "tasks": ["7.4"] }
  ]
}
```
