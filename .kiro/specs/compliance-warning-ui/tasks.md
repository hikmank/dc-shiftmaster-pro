# Implementation Plan: Compliance Warning UI

## Overview

This plan implements two major frontend capabilities: (1) a Compliance Warning Modal that intercepts 422 compliance responses from `POST /api/overrides` and lets managers acknowledge or cancel, and (2) a Dashboard Weekly Compliance Summary that shows per-teammate hours/days with color-coded thresholds. Implementation uses vanilla JavaScript with the existing IIFE module pattern, modifying `dashboard.js` and `api.js` while adding two new modules (`compliance-modal.js` and `weekly-summary.js`).

## Tasks

- [x] 1. Add API raw override method and compliance modal HTML structure
  - [x] 1.1 Add `setOverrideRaw` method to the API module
    - Add a new `setOverrideRaw` function to `dc_shiftmaster_html/static/js/api.js` that calls `POST /api/overrides` and returns `{status, body}` without throwing on 422
    - The method uses `fetch` directly, parses JSON, and returns the status code alongside the body
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 1.2 Add compliance modal HTML markup to `index.html`
    - Add a hidden modal container with `id="compliance-modal"`, `role="dialog"`, `aria-modal="true"`, `aria-labelledby="compliance-heading"`
    - Include a heading "Compliance Warning", a violations container div, "Acknowledge & Proceed" button, and "Cancel" button
    - Add `aria-label` attributes to both buttons with descriptive context
    - Add CSS styles for the modal overlay, violation cards, color-coded thresholds, and loading state
    - _Requirements: 2.1, 2.2, 2.8, 6.1, 6.2, 6.5, 6.6_

- [x] 2. Implement ComplianceModal module
  - [x] 2.1 Create `dc_shiftmaster_html/static/js/compliance-modal.js` with core modal logic
    - Implement the IIFE module pattern exposing `show`, `close`, `ruleLabel`, and `renderViolationCard`
    - `show(options)` accepts `{violations, overrideData, onSuccess}`, renders violation cards, and displays the modal
    - `close()` hides the modal, clears content, and restores focus to the previously focused element
    - `ruleLabel(rule)` maps `weekly_hours` → "Weekly Hours Exceeded", `weekly_days` → "Weekly Days Exceeded", `daily_hours` → "Daily Hours Exceeded"
    - `renderViolationCard(violation)` creates a DOM element with `role="alert"` showing label, projected/limit values, and optional date range
    - Handle missing/malformed violation fields with fallback text ("Unknown Rule", "N/A")
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [x] 2.2 Implement focus management and keyboard handling in ComplianceModal
    - On `show()`, move focus to the first focusable element inside the modal
    - Implement focus trapping: Tab and Shift+Tab cycle through modal elements only
    - Close modal on Escape key press (when not in loading state)
    - _Requirements: 6.3, 6.4, 4.3_

  - [x] 2.3 Implement acknowledgment resubmission and loading state in ComplianceModal
    - "Acknowledge & Proceed" click handler calls `API.setOverrideRaw` with original data plus `acknowledge_violations: true`
    - During request: disable both buttons, change "Acknowledge & Proceed" text to "Submitting..."
    - On 201 success: close modal, call `onSuccess` callback, show success toast "Override saved"
    - On error: close modal, show error toast with server error message
    - On completion (success or error): re-enable buttons and restore default label
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 5.1, 5.2, 5.3_

  - [x] 2.4 Implement cancel behavior in ComplianceModal
    - "Cancel" button click closes modal without sending any API requests
    - Leave the override modal in its current state so manager can adjust selections
    - _Requirements: 4.1, 4.2_

  - [x] 2.5 Write property test for compliance response interception (Property 1)
    - **Property 1: Compliance response interception prevents error toast**
    - **Validates: Requirements 1.1, 1.2**

  - [x] 2.6 Write property test for violation card rendering (Property 2)
    - **Property 2: Violation card rendering matches violation data**
    - **Validates: Requirements 2.3, 2.4, 2.5, 2.6, 2.7**

  - [x] 2.7 Write property test for acknowledgment payload (Property 3)
    - **Property 3: Acknowledgment resubmission sends correct payload**
    - **Validates: Requirements 3.1**

  - [x] 2.8 Write property test for error propagation (Property 4)
    - **Property 4: Error message propagation after acknowledgment failure**
    - **Validates: Requirements 3.4**

- [x] 3. Checkpoint - Ensure compliance modal tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement WeeklySummary module
  - [x] 4.1 Create `dc_shiftmaster_html/static/js/weekly-summary.js` with computation logic
    - Implement the IIFE module pattern exposing `computeDuration`, `getEffectiveStart`, `hoursColorClass`, `daysColorClass`, `computeWeeklySummaries`, and `render`
    - `computeDuration(startTime, endTime)` calculates hours between HH:MM strings, adding 24h for overnight shifts (end ≤ start)
    - `getEffectiveStart(teammate, shiftType, shiftWindows)` returns `custom_start` if available, otherwise the shift window default start
    - `hoursColorClass(hours)` returns `compliance-green` for <50, `compliance-yellow` for 50–59, `compliance-red` for ≥60
    - `daysColorClass(days)` returns `compliance-red` for ≥6, `compliance-green` otherwise
    - _Requirements: 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

  - [x] 4.2 Implement `computeWeeklySummaries` in WeeklySummary module
    - Accept `slots`, `teammates`, `shiftWindows`, `year`, `month` parameters
    - Determine all Sunday–Saturday week spans that overlap with the given month
    - For each week, compute per-teammate total hours (sum of shift durations) and total days (count of distinct dates)
    - Return array of week summary objects with teammate data and color classes
    - _Requirements: 7.1, 7.2, 7.9_

  - [x] 4.3 Implement `render` method in WeeklySummary module
    - Accept summaries array and the calendar grid container element
    - Insert a summary row after each week's day cards in the grid
    - Each row displays teammate names with their hours and days, color-coded per threshold
    - _Requirements: 7.1, 7.2, 7.5, 7.6, 7.7, 7.8_

  - [x] 4.4 Write property test for duration calculation (Property 5)
    - **Property 5: Duration calculation correctness**
    - **Validates: Requirements 7.3, 7.4**

  - [x] 4.5 Write property test for weekly summary row count (Property 6)
    - **Property 6: Weekly summary row count matches calendar weeks**
    - **Validates: Requirements 7.1**

  - [x] 4.6 Write property test for weekly summary aggregation (Property 7)
    - **Property 7: Weekly summary aggregation correctness**
    - **Validates: Requirements 7.2**

  - [x] 4.7 Write property test for compliance threshold colors (Property 8)
    - **Property 8: Compliance threshold color-coding**
    - **Validates: Requirements 7.5, 7.6, 7.7, 7.8**

- [x] 5. Checkpoint - Ensure weekly summary tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Integrate modules into Dashboard and wire everything together
  - [x] 6.1 Modify Dashboard override submission to use compliance interception
    - Update the `override-submit` click handler in `dc_shiftmaster_html/static/js/dashboard.js`
    - Replace `API.setOverride` call with `API.setOverrideRaw` and handle the response:
      - 201: success path (unchanged behavior)
      - 422 with `status: "compliance_warning"`: call `ComplianceModal.show` with violations, overrideData, and onSuccess callback
      - 422 without violations array: show default error toast
      - Other errors: show error toast
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 6.2 Integrate WeeklySummary rendering into Dashboard render cycle
    - After rendering day cards in `Dashboard.render()`, call `WeeklySummary.computeWeeklySummaries` with current slots, teammates, shift windows, year, and month
    - Call `WeeklySummary.render` to insert summary rows into the calendar grid
    - Ensure summary rows re-render on month change and calendar refresh
    - _Requirements: 7.1, 7.9, 7.10_

  - [x] 6.3 Add script tags for new modules in `index.html`
    - Add `<script src="js/compliance-modal.js"></script>` and `<script src="js/weekly-summary.js"></script>` before `dashboard.js` in the HTML
    - _Requirements: All (wiring)_

  - [x] 6.4 Write unit tests for Dashboard integration
    - Test that 422 compliance_warning response triggers ComplianceModal.show
    - Test that 422 without violations shows error toast
    - Test that WeeklySummary rows render after calendar load
    - Test that summary rows re-render on month change
    - _Requirements: 1.1, 1.2, 1.3, 7.10_

- [x] 7. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All JavaScript follows the existing IIFE module pattern (`var ModuleName = (function() { ... })()`)
- Test file location: `dc_shiftmaster_html/static/js/__tests__/compliance-warning-ui.property.test.js`
- Testing uses Jest with fast-check (already configured in the project)
- No additional API calls are needed for the weekly summary — it uses already-loaded schedule data

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "4.2"] },
    { "id": 3, "tasks": ["2.5", "2.6", "2.7", "2.8", "4.3"] },
    { "id": 4, "tasks": ["4.4", "4.5", "4.6", "4.7"] },
    { "id": 5, "tasks": ["6.1", "6.2", "6.3"] },
    { "id": 6, "tasks": ["6.4"] }
  ]
}
```
