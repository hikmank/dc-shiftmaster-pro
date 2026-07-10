# Implementation Plan: Labor Compliance Validation

## Overview

This plan implements pre-override compliance validation for DC-ShiftMaster Pro. The approach creates a pure `ComplianceValidator` class in `dc_shiftmaster/compliance.py`, integrates it into the existing `POST /api/overrides` endpoint with a two-phase acknowledgment flow, and validates correctness through unit tests and Hypothesis property-based tests.

## Tasks

- [x] 1. Create ComplianceValidator module with data classes and duration logic
  - [x] 1.1 Create `dc_shiftmaster/compliance.py` with `ComplianceViolation` and `ComplianceResult` dataclasses, class constants, and the `compute_shift_duration` method
    - Define `ComplianceViolation` dataclass with fields: rule, projected, limit, window_start, window_end
    - Define `ComplianceResult` dataclass with fields: passed, violations
    - Implement `ComplianceValidator` class with constants: WEEKLY_HOURS_LIMIT=60.0, WEEKLY_DAYS_LIMIT=6, DAILY_HOURS_LIMIT=12.0
    - Implement `compute_shift_duration(effective_start, shift_end)` — returns hours as float, handles overnight (end < start → add 24h), returns 0 when start == end
    - _Requirements: 1.2, 4.3, 4.4_

  - [x] 1.2 Implement `get_effective_start` method on `ComplianceValidator`
    - Look up teammate by name in the teammates list
    - Return teammate's `custom_start` if non-empty, otherwise return shift window's default `start_time` for the given shift_type
    - _Requirements: 4.1, 4.2_

  - [x] 1.3 Write property test for shift duration calculation (Property 1)
    - **Property 1: Shift duration calculation correctness**
    - **Validates: Requirements 1.2, 3.2, 4.3, 4.4**

  - [x] 1.4 Write property test for effective start time resolution (Property 2)
    - **Property 2: Effective start time resolution**
    - **Validates: Requirements 4.1, 4.2**

- [x] 2. Implement schedule resolution and weekly hours check
  - [x] 2.1 Implement `resolve_teammate_schedule` method on `ComplianceValidator`
    - Accept teammate_name, date_range, shift_windows, teammates, existing_overrides, scheduling_engine, year
    - Compute the base schedule from the scheduling engine for the date range
    - Apply existing overrides: include shifts where override assigns the teammate, exclude shifts where override replaces the teammate with another name or "nobody"
    - Return list of (date, shift_type) tuples representing the teammate's actual working days
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 2.2 Implement `check_weekly_hours` method on `ComplianceValidator`
    - Evaluate up to 7 overlapping 7-day windows that include the override date (windows starting from override_date-6 through override_date)
    - For each window, sum shift durations using `compute_shift_duration` with effective start times
    - Return a `ComplianceViolation` for each window where total exceeds 60 hours
    - _Requirements: 1.1, 1.3, 1.4_

  - [x] 2.3 Write property test for schedule resolution (Property 6)
    - **Property 6: Schedule resolution includes and excludes overrides correctly**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**

  - [x] 2.4 Write property test for weekly hours violation (Property 3)
    - **Property 3: Weekly hours violation if and only if exceeds 60**
    - **Validates: Requirements 1.1, 1.3, 1.4**

- [x] 3. Implement weekly days check and daily hours check
  - [x] 3.1 Implement `check_weekly_days` method on `ComplianceValidator`
    - Evaluate up to 7 overlapping 7-day windows that include the override date
    - For each window, count distinct calendar dates where the teammate has at least one shift
    - Return a `ComplianceViolation` for each window where day count exceeds 6
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.2 Implement `check_daily_hours` method on `ComplianceValidator`
    - Sum all shift durations assigned to the teammate on the override date
    - Use effective start times for each shift
    - Do not double-count when the proposed override assigns the same teammate already in the slot
    - Return a `ComplianceViolation` if total exceeds 12 hours
    - _Requirements: 3.1, 3.3, 3.4, 3.5_

  - [x] 3.3 Write property test for weekly days violation (Property 4)
    - **Property 4: Weekly days violation if and only if exceeds 6**
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [x] 3.4 Write property test for daily hours violation (Property 5)
    - **Property 5: Daily hours violation if and only if exceeds 12**
    - **Validates: Requirements 3.1, 3.3, 3.4, 3.5**

- [x] 4. Implement top-level validate method
  - [x] 4.1 Implement `validate` method on `ComplianceValidator`
    - Orchestrate the full validation flow: resolve schedule, then run all three checks (weekly hours, weekly days, daily hours)
    - Collect all violations from all checks into a single `ComplianceResult`
    - Return `ComplianceResult(passed=True, violations=[])` when no violations found
    - Return `ComplianceResult(passed=False, violations=[...])` when any violations found
    - _Requirements: 1.1, 2.1, 3.1, 5.1_

- [x] 5. Checkpoint - Ensure all compliance module tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Integrate compliance validation into the override API
  - [x] 6.1 Modify `POST /api/overrides` in `dc_shiftmaster_html/routes_overrides.py` to add compliance validation
    - Parse `acknowledge_violations` boolean from request body (default False)
    - When `acknowledge_violations` is False: instantiate `ComplianceValidator`, call `validate()` with schedule data from DatabaseManager and SchedulingEngine
    - If violations found: return 422 response with `{"status": "compliance_warning", "violations": [...]}` payload
    - If no violations: proceed to persist the override as before
    - When `acknowledge_violations` is True: skip validation and persist the override directly, include `"acknowledged_violations": true` in the 201 response
    - Handle validation errors: return 500 with error message if validator raises an exception
    - _Requirements: 5.1, 5.3, 5.4, 6.2, 6.3_

  - [x] 6.2 Write property test for acknowledged override persistence (Property 7)
    - **Property 7: Acknowledged override always persists**
    - **Validates: Requirements 6.2**

- [x] 7. Write unit tests for compliance validation
  - [x] 7.1 Create `tests/test_compliance.py` with unit tests for the ComplianceValidator
    - Test `compute_shift_duration`: known examples (06:00→18:30 = 12.5h, 18:00→06:30 = 12.5h, start==end = 0h)
    - Test `get_effective_start`: teammate with custom_start, teammate without custom_start
    - Test `check_weekly_hours`: schedule exactly at 60h (pass), schedule at 60.5h (fail)
    - Test `check_weekly_days`: schedule with 6 days (pass), schedule with 7 days (fail)
    - Test `check_daily_hours`: day total at 12h (pass), day total at 12.5h (fail), same-teammate no double-count
    - Test `resolve_teammate_schedule`: override adds teammate, override removes teammate, override replaces with "nobody"
    - _Requirements: 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 3.1, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 7.1, 7.2, 7.3, 7.4_

  - [x] 7.2 Add API integration tests to `tests/test_compliance.py` for the override endpoint
    - Test 422 response when violations detected (no acknowledgment)
    - Test 201 response when no violations detected
    - Test 201 response when `acknowledge_violations=true` with violations present
    - Test 500 response when validator encounters an error
    - Test request with invalid date format returns 400
    - _Requirements: 5.1, 5.3, 5.4, 6.2_

- [x] 8. Create property-based test file with Hypothesis strategies
  - [x] 8.1 Create `tests/test_compliance_props.py` with custom Hypothesis strategies and all property tests
    - Add `valid_time_pair()` strategy for duration testing (reuse `valid_time` from conftest.py)
    - Add `teammate_schedule()` strategy generating list of (date, shift_type) tuples
    - Add `compliance_scenario()` strategy generating complete validation scenarios
    - Implement all 7 property tests with `@settings(max_examples=100)` and proper tagging
    - Each test tagged: `# Feature: labor-compliance-validation, Property N: {title}`
    - _Requirements: 1.1, 1.2, 2.1, 3.1, 4.1, 4.3, 6.2, 7.1_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (Properties 1-7)
- Unit tests validate specific examples and edge cases
- The `ComplianceValidator` is a pure module with no database dependencies, making it straightforward to test in isolation
- The existing `valid_time` strategy in `conftest.py` is reused for property tests
- Hypothesis is already configured in this project (`.hypothesis/` directory exists)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "1.4"] },
    { "id": 3, "tasks": ["2.1"] },
    { "id": 4, "tasks": ["2.2", "2.3"] },
    { "id": 5, "tasks": ["2.4", "3.1", "3.2"] },
    { "id": 6, "tasks": ["3.3", "3.4", "4.1"] },
    { "id": 7, "tasks": ["6.1"] },
    { "id": 8, "tasks": ["6.2", "7.1", "7.2"] },
    { "id": 9, "tasks": ["8.1"] }
  ]
}
```
