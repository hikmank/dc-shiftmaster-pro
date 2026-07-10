# Implementation Plan: Proactive Hours Warning

## Overview

Implement a client-side `HoursWarningBanner` IIFE module that proactively displays a teammate's current and projected weekly hours before shift assignment confirmation. The module integrates into the Override Modal and Team Assignment Section, reuses `WeeklySummary` computation functions, and applies compliance color thresholds. All implementation is in vanilla JavaScript with Jest/jsdom tests and fast-check property-based tests.

## Tasks

- [x] 1. Create HoursWarningBanner module with core computation functions
  - [x] 1.1 Create `dc_shiftmaster_html/static/js/hours-warning-banner.js` with the IIFE module skeleton and implement `getWeekForDate(dateStr)` that returns `{start, end}` Sunday–Saturday boundaries for any given date
    - Implement date parsing and day-of-week calculation
    - Return `{start: 'YYYY-MM-DD', end: 'YYYY-MM-DD'}` where start is Sunday and end is Saturday
    - _Requirements: 1.1, 5.2_

  - [x] 1.2 Implement `computeTeammateWeeklyHours(teammateName, weekStart, weekEnd, slots, teammate, shiftWindows)` that filters slots within the week for the given teammate and sums durations using `WeeklySummary.computeDuration`
    - Filter slots by date range and teammate name
    - Use `WeeklySummary.getEffectiveStart` for each slot's start time
    - Return `{currentHours, currentDays}` where currentDays is distinct date count
    - _Requirements: 1.1, 1.3, 1.4_

  - [x] 1.3 Implement `computeProjectedHours(currentHours, shiftType, teammate, shiftWindows)` that adds the pending shift duration to current hours
    - Use `WeeklySummary.getEffectiveStart(teammate, shiftType, shiftWindows)` for effective start
    - Use `WeeklySummary.computeDuration(effectiveStart, shiftWindows[shiftType].end)` for shift duration
    - Return `currentHours + shiftDuration`
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 1.4 Implement `colorToLabel(colorClass)` that maps compliance CSS classes to text labels
    - Return 'OK' for 'compliance-green', 'Caution' for 'compliance-yellow', 'Over Limit' for 'compliance-red'
    - _Requirements: 8.3_

  - [x] 1.5 Write property test for week boundary computation (Property 1)
    - **Property 1: Week boundary computation is correct**
    - Generate arbitrary valid date strings, verify start is Sunday ≤ date ≤ end Saturday, and end - start == 6 days
    - **Validates: Requirements 1.1, 5.2**

  - [x] 1.6 Write property test for projected hours computation (Property 3)
    - **Property 3: Projected hours equals current hours plus shift duration**
    - Generate arbitrary currentHours (≥ 0), shiftType, teammate (with/without custom_start), and shiftWindows; verify result equals currentHours + computeDuration(effectiveStart, end)
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [x] 1.7 Write property test for color classification thresholds (Property 4)
    - **Property 4: Color classification matches compliance thresholds**
    - Generate arbitrary non-negative hours/days values; verify hoursColorClass and daysColorClass return correct classes per threshold boundaries
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

- [x] 2. Checkpoint - Ensure core computation tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Implement banner rendering and DOM integration
  - [x] 3.1 Implement internal `renderBanner(container, entries)` function that creates the banner DOM structure with accessibility attributes
    - Create a container div with `role="status"`, `aria-live="polite"`, and class `hours-warning-banner`
    - For each entry, render name, current hours, projected hours, color indicator, and text label
    - Each entry gets an `aria-label` with format: "{name}: {currentHours}h this week, projected {projectedHours}h, {label}"
    - Sort entries by projectedHours descending before rendering
    - If any entry has projectedHours ≥ 60, append a summary warning line with count
    - _Requirements: 3.5, 4.4, 7.2, 7.3, 8.1, 8.2, 8.3_

  - [x] 3.2 Implement `updateOverrideModal(options)` that computes hours for each selected teammate and renders the banner
    - Accept `{selectedNames, date, shiftType, slots, teammates, shiftWindows, container}`
    - Call `getWeekForDate(date)` to determine week boundaries
    - For each selected name, find teammate object, call `computeTeammateWeeklyHours`, then `computeProjectedHours`
    - Compute projectedDays (currentDays + 1 if date not already in scheduled dates)
    - Build entries array with hoursColor from `WeeklySummary.hoursColorClass(projectedHours)` and daysColor from `WeeklySummary.daysColorClass(projectedDays)`
    - Call `renderBanner(container, entries)`
    - If selectedNames is empty, call `clear(container)`
    - _Requirements: 1.1, 2.1, 2.4, 4.1, 4.2, 4.3, 4.5, 7.1, 7.4_

  - [x] 3.3 Implement `updateTeamAssignment(options)` that computes hours for a single teammate and renders the banner
    - Accept `{teammate, shiftType, container}`
    - Determine current week using `getWeekForDate` with today's date
    - If schedule data not available, call `API.getSchedule()` to fetch current month's slots
    - Compute hours and render single-entry banner
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 3.4 Implement `clear(container)` that removes the banner element from the given container
    - Remove any element with class `hours-warning-banner` from the container
    - _Requirements: 4.3, 6.4_

  - [x] 3.5 Write property test for rendered entries matching selections (Property 5)
    - **Property 5: Rendered entries match selected teammates**
    - Generate arbitrary non-empty sets of teammate names with schedule data; verify banner renders exactly one entry per name with correct values
    - **Validates: Requirements 4.2, 4.4, 7.1**

  - [x] 3.6 Write property test for sort order (Property 6)
    - **Property 6: Entries are sorted by projected hours descending**
    - Generate lists of 2+ teammate entries; verify rendered order has each entry's projectedHours ≥ next entry's projectedHours
    - **Validates: Requirements 7.2**

  - [x] 3.7 Write property test for red threshold warning count (Property 7)
    - **Property 7: Red threshold warning count is accurate**
    - Generate sets of entries with varying projectedHours; verify displayed count equals number of entries with projectedHours ≥ 60
    - **Validates: Requirements 4.5, 7.3**

  - [x] 3.8 Write property test for accessibility labels (Property 8)
    - **Property 8: Accessibility labels contain name and compliance status**
    - Generate teammate entries; verify each rendered element has aria-label containing name, projected hours, and correct text label
    - **Validates: Requirements 8.2, 8.3, 8.4**

- [x] 4. Checkpoint - Ensure rendering and property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Integrate banner into Override Modal
  - [x] 5.1 Add the banner container element to the Override Modal HTML in `dc_shiftmaster_html/static/index.html`
    - Add a `<div id="hours-warning-container" class="hours-warning-banner-wrapper"></div>` below the `#override-teammate-list` element inside the override modal
    - _Requirements: 4.1_

  - [x] 5.2 Add a `<script>` tag for `hours-warning-banner.js` in `index.html` after `weekly-summary.js` and before `coverage.js`
    - Ensure the module loads after WeeklySummary (dependency) and before modules that use it
    - _Requirements: 1.3_

  - [x] 5.3 Wire checkbox change events in the Override Modal (in `coverage.js` or inline) to call `HoursWarningBanner.updateOverrideModal()` with current selections, date, shift type, cached slots, teammates, and shift windows
    - Listen for `change` events on checkboxes within `#override-teammate-list`
    - Gather selected names from checked checkboxes
    - Pass the override date from the date input, shift type from the radio/select, and cached schedule data
    - _Requirements: 4.1, 4.2, 4.3, 7.1, 7.4_

  - [x] 5.4 Wire modal close/cancel to call `HoursWarningBanner.clear()` on the banner container
    - On modal dismiss (close button, cancel button, backdrop click), clear the banner
    - _Requirements: 6.4_

  - [x] 5.5 Ensure the submit/save button remains enabled regardless of banner state (informational only, non-blocking)
    - Verify no logic disables the submit button based on banner content
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 6. Integrate banner into Team Assignment Section
  - [x] 6.1 Add a banner container element in the Team Assignment Section markup (in `index.html` or dynamically in `team.js`)
    - Add `<div id="team-hours-warning-container" class="hours-warning-banner-wrapper"></div>` in the team assignment area
    - _Requirements: 5.1_

  - [x] 6.2 Wire the shift assignment action in `team.js` to call `HoursWarningBanner.updateTeamAssignment()` when a manager initiates a shift change for a teammate
    - Pass the teammate object, target shift type, and the container element
    - _Requirements: 5.1, 5.4_

  - [x] 6.3 Wire team list refresh and teammate selection changes to update the banner
    - On teammate selection change or list refresh, call `updateTeamAssignment` with new teammate or `clear` if deselected
    - _Requirements: 5.4_

  - [x] 6.4 Handle loading state: display "Loading hours..." when schedule data is being fetched, and "Hours unavailable" on API failure
    - Show loading indicator while `API.getSchedule()` is in progress
    - Show error message if fetch fails; never block submission
    - _Requirements: 1.5, 5.3_

- [x] 7. Add CSS styles for the Hours Warning Banner
  - [x] 7.1 Add CSS rules for `.hours-warning-banner`, `.hours-warning-entry`, `.hours-warning-label`, and `.hours-warning-summary` in the project's stylesheet
    - Style the banner to be visually distinct but non-intrusive within the modal/section
    - Reuse existing `compliance-green`, `compliance-yellow`, `compliance-red` classes for color indicators
    - Ensure text labels ("OK", "Caution", "Over Limit") are visible alongside color indicators
    - _Requirements: 3.5, 8.3_

- [x] 8. Write integration and unit tests
  - [x] 8.1 Write unit tests for Override Modal integration
    - Test checkbox change triggers banner update
    - Test unchecking removes teammate from banner
    - Test empty selection hides banner
    - Test modal close clears banner
    - Test submit button remains enabled with red-threshold banner
    - _Requirements: 4.1, 4.2, 4.3, 6.1, 6.2_

  - [x] 8.2 Write unit tests for Team Assignment integration
    - Test shift assignment action triggers banner with current week
    - Test loading state appears when data not cached
    - Test error state on API failure
    - Test refresh updates banner
    - _Requirements: 5.1, 5.3, 5.4_

  - [x] 8.3 Write property test for weekly hours summation (Property 2)
    - **Property 2: Weekly hours summation matches slot durations**
    - Generate arbitrary teammate names, week boundaries, and slot arrays; verify computeTeammateWeeklyHours returns sum of computeDuration for matching slots and correct distinct day count
    - **Validates: Requirements 1.1, 2.1**

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The module uses vanilla JavaScript IIFE pattern consistent with existing codebase (WeeklySummary, Team, Coverage modules)
- All property tests use fast-check in Jest/jsdom environment with minimum 100 iterations
- The banner never blocks form submission — it is purely informational

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4"] },
    { "id": 2, "tasks": ["1.5", "1.6", "1.7"] },
    { "id": 3, "tasks": ["3.1"] },
    { "id": 4, "tasks": ["3.2", "3.3", "3.4"] },
    { "id": 5, "tasks": ["3.5", "3.6", "3.7", "3.8"] },
    { "id": 6, "tasks": ["5.1", "5.2", "7.1"] },
    { "id": 7, "tasks": ["5.3", "5.4", "5.5", "6.1"] },
    { "id": 8, "tasks": ["6.2", "6.3", "6.4"] },
    { "id": 9, "tasks": ["8.1", "8.2", "8.3"] }
  ]
}
```
