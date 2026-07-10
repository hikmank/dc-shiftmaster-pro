# Requirements Document

## Introduction

The Proactive Hours Warning feature adds a client-side pre-submission warning layer that displays a teammate's current weekly hours and projected hours whenever a manager is about to assign or move that teammate to a shift. Unlike the existing compliance warning modal (which reacts to a 422 response after submission), this feature proactively calculates and presents hours information before the manager confirms the assignment. The warning appears in two contexts: the override modal on the dashboard and the team management section when assigning shifts. It uses the existing WeeklySummary module's computation logic to determine current hours, projects the additional hours from the pending assignment, and color-codes the result using the established compliance thresholds (green < 50h, yellow 50–59h, red ≥ 60h).

## Glossary

- **Hours_Warning_Banner**: A color-coded inline element displayed within the assignment UI that shows a teammate's current weekly hours, projected hours after the pending assignment, and compliance status
- **WeeklySummary_Module**: The existing `WeeklySummary` JavaScript module in `weekly-summary.js` that computes per-teammate weekly hours and days from schedule slot data
- **Override_Modal**: The existing modal dialog on the dashboard that allows managers to assign teammates to a specific date and shift type via `POST /api/overrides`
- **Team_Assignment_Section**: The team management view in `team.js` where managers can assign or move teammates between shift groups
- **Projected_Hours**: The sum of a teammate's current weekly hours plus the duration of the pending shift assignment
- **Compliance_Threshold**: The color-coded hour boundaries used to indicate compliance risk: green (below 50 hours), yellow (50 to 59 hours inclusive), red (60 hours or above)
- **Days_Threshold**: The compliance boundary for weekly days worked: green (below 6 days), red (6 or more days)
- **Pending_Assignment**: A shift assignment that the manager has selected but not yet confirmed or submitted
- **Shift_Duration**: The length of a shift in hours, computed as end_time minus start_time (adding 24 hours for overnight shifts) minus the 30-minute FHD/BHD handoff deduction
- **Work_Week**: A seven-day period starting on Sunday and ending on Saturday, used as the compliance evaluation window

## Requirements

### Requirement 1: Compute Current Weekly Hours for Selected Teammate

**User Story:** As a manager, I want the system to calculate a teammate's current weekly hours when I select them for an assignment, so that I can see their existing workload before confirming.

#### Acceptance Criteria

1. WHEN a manager selects a teammate checkbox in the Override_Modal, THE Hours_Warning_Banner SHALL compute that teammate's total hours for the Work_Week containing the selected override date
2. WHEN a manager initiates a shift assignment in the Team_Assignment_Section, THE Hours_Warning_Banner SHALL compute that teammate's total hours for the current Work_Week
3. THE WeeklySummary_Module SHALL provide the computation logic for current weekly hours, reusing the existing `computeDuration` function and shift window configuration
4. THE Hours_Warning_Banner SHALL compute hours using the same schedule slot data already loaded on the dashboard without making additional API requests
5. WHEN the schedule data is not yet loaded, THE Hours_Warning_Banner SHALL display a loading indicator until computation completes

### Requirement 2: Compute Projected Hours After Pending Assignment

**User Story:** As a manager, I want to see what the teammate's total weekly hours would be after the new assignment, so that I can determine whether the assignment would push them over compliance limits.

#### Acceptance Criteria

1. WHEN a teammate is selected for an override assignment, THE Hours_Warning_Banner SHALL compute the Projected_Hours by adding the Shift_Duration of the pending shift to the teammate's current weekly hours
2. THE Hours_Warning_Banner SHALL compute Shift_Duration using the shift window start and end times for the selected shift type (day or night), subtracting the 30-minute FHD/BHD handoff
3. WHEN the teammate has a custom_start time, THE Hours_Warning_Banner SHALL use the custom_start time instead of the shift window default start time for the duration calculation
4. THE Hours_Warning_Banner SHALL display both the current weekly hours and the Projected_Hours as separate labeled values

### Requirement 3: Display Color-Coded Compliance Status

**User Story:** As a manager, I want the hours warning to be color-coded based on compliance thresholds, so that I can quickly assess the risk level at a glance.

#### Acceptance Criteria

1. WHEN the Projected_Hours are below 50, THE Hours_Warning_Banner SHALL display the hours value with a green color indicator
2. WHEN the Projected_Hours are between 50 and 59 (inclusive), THE Hours_Warning_Banner SHALL display the hours value with a yellow color indicator
3. WHEN the Projected_Hours are 60 or above, THE Hours_Warning_Banner SHALL display the hours value with a red color indicator
4. WHEN the teammate's projected weekly days worked (including the pending assignment day) are 6 or more, THE Hours_Warning_Banner SHALL display the days count with a red color indicator
5. THE Hours_Warning_Banner SHALL use the same CSS color classes as the existing Weekly_Summary_Row (compliance-green, compliance-yellow, compliance-red)

### Requirement 4: Display Warning in Override Modal

**User Story:** As a manager, I want to see the hours warning inside the override modal when I select teammates, so that I am informed before submitting the override.

#### Acceptance Criteria

1. WHEN one or more teammate checkboxes are checked in the Override_Modal, THE Hours_Warning_Banner SHALL appear below the teammate selection list showing hours information for each selected teammate
2. WHEN a teammate checkbox is unchecked in the Override_Modal, THE Hours_Warning_Banner SHALL remove that teammate's hours information from the display
3. WHEN no teammate checkboxes are checked, THE Hours_Warning_Banner SHALL be hidden
4. THE Hours_Warning_Banner SHALL display each selected teammate's name, current weekly hours, projected hours, and compliance color on a separate line
5. WHEN the Projected_Hours reach the red threshold (60 or above), THE Hours_Warning_Banner SHALL display a text warning message stating "Projected hours exceed compliance limit"

### Requirement 5: Display Warning in Team Assignment Section

**User Story:** As a manager, I want to see the hours warning in the team management section when assigning teammates to shifts, so that I have the same compliance visibility regardless of which interface I use.

#### Acceptance Criteria

1. WHEN a manager initiates a shift assignment action for a teammate in the Team_Assignment_Section, THE Hours_Warning_Banner SHALL appear showing that teammate's current weekly hours and projected hours
2. THE Hours_Warning_Banner in the Team_Assignment_Section SHALL use the current calendar week (Sunday through Saturday containing today's date) for the hours computation
3. THE Hours_Warning_Banner SHALL fetch the current month's schedule data to compute weekly hours if the data is not already available in the Team_Assignment_Section context
4. WHEN the team list is refreshed or a different teammate is selected, THE Hours_Warning_Banner SHALL update to reflect the newly selected teammate's hours

### Requirement 6: Allow Manager to Proceed or Cancel

**User Story:** As a manager, I want to be able to proceed with the assignment despite the warning or cancel it, so that I retain full control over scheduling decisions.

#### Acceptance Criteria

1. THE Hours_Warning_Banner SHALL not block or prevent the manager from submitting the assignment regardless of the compliance color status
2. WHEN the Projected_Hours reach the red threshold, THE Hours_Warning_Banner SHALL display the warning prominently but SHALL still allow the submit action to proceed
3. THE Hours_Warning_Banner SHALL serve as an informational display only and SHALL not require explicit acknowledgment before submission
4. WHEN the manager cancels the assignment (closes the modal or clicks cancel), THE Hours_Warning_Banner SHALL be dismissed along with the parent UI element

### Requirement 7: Handle Multiple Teammate Selections

**User Story:** As a manager, I want to see hours warnings for all selected teammates when assigning multiple people to the same shift, so that I can assess compliance risk for the entire group.

#### Acceptance Criteria

1. WHEN multiple teammate checkboxes are checked in the Override_Modal, THE Hours_Warning_Banner SHALL display a separate hours summary line for each selected teammate
2. THE Hours_Warning_Banner SHALL sort teammate entries by Projected_Hours in descending order so the highest-risk teammates appear first
3. WHEN any selected teammate has Projected_Hours at the red threshold (60 or above), THE Hours_Warning_Banner SHALL display a summary count indicating how many teammates would exceed compliance limits
4. THE Hours_Warning_Banner SHALL update in real-time as checkboxes are checked or unchecked without requiring a page refresh or additional user action

### Requirement 8: Accessibility of Hours Warning Banner

**User Story:** As a manager using assistive technology, I want the hours warning to be accessible, so that I can understand the compliance information using a screen reader.

#### Acceptance Criteria

1. THE Hours_Warning_Banner SHALL have `role="status"` and `aria-live="polite"` attributes so screen readers announce updates when teammate selections change
2. THE Hours_Warning_Banner SHALL include `aria-label` text that describes the compliance status in words (for example "teammate name: 52 hours this week, projected 64 hours, exceeds compliance limit")
3. THE color-coded indicators SHALL not rely solely on color to convey compliance status; each indicator SHALL include a text label ("OK", "Caution", or "Over Limit") alongside the color
4. WHEN the Hours_Warning_Banner updates due to a selection change, THE screen reader announcement SHALL include the teammate name and projected hours status

