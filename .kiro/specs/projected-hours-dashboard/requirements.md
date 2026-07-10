# Requirements Document

## Introduction

The Projected Hours Dashboard adds a visible UI panel to DC-ShiftMaster Pro that displays a teammate's projected weekly hours, days worked, and daily hours relative to labor compliance limits. Currently, compliance validation only fires as a backend check when submitting an override. This feature surfaces that information proactively — managers can see projected hours when viewing the Team Management page, and critically, can preview the impact on hours before and after changing a teammate's rotation group (e.g., moving from FHD to BHD). The dashboard provides at-a-glance visibility into the 60-hour weekly limit, 6-day weekly limit, and 12-hour daily limit for each teammate's current projected schedule.

## Glossary

- **Hours_Dashboard**: The UI panel that displays a teammate's projected hours, days worked, and compliance status relative to labor limits.
- **Projected_Schedule**: The computed schedule for a teammate based on their rotation group assignment, shift windows, custom start times, and any existing overrides applied within the evaluation period.
- **Compliance_Limits**: The three labor limits enforced: 60 hours per rolling 7-day window, 6 days per rolling 7-day window, and 12 hours per single calendar day.
- **Rotation_Group**: One of four shift patterns a teammate can be assigned to: FHD (Front Half Day), FHN (Front Half Night), BHD (Back Half Day), or BHN (Back Half Night).
- **Impact_Preview**: A comparison view showing projected hours and days before and after a proposed rotation group change, displayed prior to committing the change.
- **Compliance_Status**: A visual indicator showing whether a teammate's projected schedule is within, approaching, or exceeding a compliance limit.
- **Evaluation_Period**: The current week (rolling 7-day window anchored to today) used for computing projected hours and days.
- **Manager**: The user viewing team schedules and making rotation group changes in the scheduling interface.
- **Projection_API**: The backend endpoint that computes and returns projected hours, days, and compliance status for a given teammate and rotation group configuration.

## Requirements

### Requirement 1: Display Projected Hours Panel on Team Management Page

**User Story:** As a manager, I want to see each teammate's projected weekly hours, days worked, and daily hours on the Team Management page, so that I have immediate visibility into their workload relative to compliance limits.

#### Acceptance Criteria

1. WHEN a Manager navigates to the Team Management page, THE Hours_Dashboard SHALL display for each teammate: the projected total weekly hours rounded to one decimal place, the projected number of days worked as a whole number in the current Evaluation_Period, and the maximum daily hours rounded to one decimal place within the Evaluation_Period.
2. WHEN a Manager navigates to the Team Management page, THE Hours_Dashboard SHALL display the applicable Compliance_Limits alongside each projected value (60 hours weekly, 6 days weekly, 12 hours daily).
3. WHEN the projected weekly hours for a teammate exceed 60 hours, THE Hours_Dashboard SHALL display a Compliance_Status indicator marking the weekly hours value as exceeding the limit.
4. WHEN the projected days worked for a teammate exceed 6 days in any rolling 7-day window, THE Hours_Dashboard SHALL display a Compliance_Status indicator marking the weekly days value as exceeding the limit.
5. WHEN the projected maximum daily hours for a teammate exceed 12 hours, THE Hours_Dashboard SHALL display a Compliance_Status indicator marking the daily hours value as exceeding the limit.
6. WHEN all projected values for a teammate remain at or below their respective Compliance_Limits, THE Hours_Dashboard SHALL display a Compliance_Status indicator marking the teammate as compliant.
7. IF the Projection_API returns an error or is unavailable for a teammate, THEN THE Hours_Dashboard SHALL display a message indicating that projected hours are unavailable for that teammate, in place of the numeric values.
8. WHEN a Manager navigates to the Team Management page, THE Hours_Dashboard SHALL display the projected values for all teammates within 3 seconds of the page load completing.

### Requirement 2: Provide Rotation Group Change Impact Preview

**User Story:** As a manager, I want to see the projected hours impact before and after changing a teammate's rotation group, so that I can understand how the change affects their workload before committing it.

#### Acceptance Criteria

1. WHEN a Manager selects a new Rotation_Group that differs from the teammate's current Rotation_Group in the edit form, THE Hours_Dashboard SHALL display an Impact_Preview within 2 seconds showing the projected weekly hours, days worked, and maximum daily hours for both the current Rotation_Group assignment and the proposed new Rotation_Group assignment.
2. WHEN the Impact_Preview is displayed, THE Hours_Dashboard SHALL label the current values as "Current" and the proposed values as "Projected" to distinguish between the before and after states.
3. WHEN the proposed Rotation_Group change would cause any projected value to exceed its corresponding Compliance_Limit, THE Hours_Dashboard SHALL display a Compliance_Status indicator in the "Projected" column marking the exceeding value as non-compliant.
4. WHEN the proposed Rotation_Group change would reduce a projected value that currently exceeds a Compliance_Limit to within the limit, THE Hours_Dashboard SHALL display a Compliance_Status indicator in the "Projected" column marking the improved value as compliant.
5. WHEN the Manager cancels the edit without saving, THE Hours_Dashboard SHALL dismiss the Impact_Preview and revert to displaying only the current projected values.
6. WHEN the Manager saves the Rotation_Group change, THE Hours_Dashboard SHALL dismiss the Impact_Preview and update to reflect the new projected values based on the saved Rotation_Group assignment.
7. IF the Projection_API fails to return projected values for the proposed Rotation_Group, THEN THE Hours_Dashboard SHALL display an error indication within the Impact_Preview area stating that the projection is unavailable, and SHALL NOT prevent the Manager from saving or canceling the edit.

### Requirement 3: Compute Projected Hours via Backend API

**User Story:** As a manager, I want the projected hours to be computed accurately using the same logic as the compliance validator, so that the dashboard values match what would be enforced during an override.

#### Acceptance Criteria

1. WHEN the Hours_Dashboard requests projected hours for a teammate, THE Projection_API SHALL compute the Projected_Schedule using the same Compliance_Validator logic that evaluates shift durations, effective start times, and existing overrides, and SHALL return the result within 2 seconds.
2. WHEN computing projected weekly hours, THE Projection_API SHALL evaluate all rolling 7-day windows (up to 7 overlapping windows) that include the current date, include all existing overrides that assign or remove the teammate within those windows, and return the maximum total hours across those windows rounded to one decimal place.
3. WHEN computing projected days worked, THE Projection_API SHALL evaluate all rolling 7-day windows (up to 7 overlapping windows) that include the current date, include all existing overrides that assign or remove the teammate within those windows, and return the maximum distinct day count across those windows as a whole number.
4. WHEN computing projected maximum daily hours, THE Projection_API SHALL calculate the total shift duration for the teammate on each day within the Evaluation_Period, include any existing overrides on those days, and return the highest single-day total rounded to one decimal place.
5. WHEN the Projection_API receives a request with an alternate Rotation_Group parameter, THE Projection_API SHALL compute the projected values as if the teammate were assigned to the specified Rotation_Group instead of their current assignment, while still applying any existing overrides that explicitly assign or remove the teammate by name within the Evaluation_Period.
6. WHEN the Projection_API successfully computes projected hours, THE Projection_API SHALL return a response containing the teammate identifier, the projected weekly hours, the projected days worked, the projected maximum daily hours, and the Compliance_Status for each value relative to its corresponding Compliance_Limit.
7. IF the Projection_API cannot compute projected hours because the teammate has no configured shift windows or the teammate identifier does not match any known teammate, THEN THE Projection_API SHALL return an error response indicating the specific reason projection is unavailable.
8. IF the Projection_API receives a request with a Rotation_Group value that is not one of the four defined groups (FHD, FHN, BHD, BHN), THEN THE Projection_API SHALL return an error response indicating that the specified Rotation_Group is invalid.

### Requirement 4: Display Projected Hours for Individual Teammate Detail

**User Story:** As a manager, I want to click on a teammate and see a detailed breakdown of their projected hours by day, so that I can identify which specific days contribute to high workload.

#### Acceptance Criteria

1. WHEN a Manager selects a teammate row on the Team Management page, THE Hours_Dashboard SHALL display a daily breakdown in chronological order showing each day within the Evaluation_Period, the shift type assigned, the effective start time, the shift end time, and the computed shift duration in hours rounded to 2 decimal places.
2. WHEN displaying the daily breakdown, THE Hours_Dashboard SHALL highlight any day where the computed shift duration exceeds 12 hours with a Compliance_Status indicator, and SHALL highlight any day where the running 7-day total ending on that day exceeds 60 hours with a Compliance_Status indicator.
3. WHEN displaying the daily breakdown, THE Hours_Dashboard SHALL show alongside each day entry the cumulative total hours for the 7-day window ending on that day (inclusive), computed as the sum of shift durations from 6 days prior through that day.
4. WHEN a day within the Evaluation_Period has an existing override applied, THE Hours_Dashboard SHALL indicate that the assignment on that day is an override rather than a rotation-based assignment.
5. WHEN a day within the Evaluation_Period has no shift assigned to the teammate, THE Hours_Dashboard SHALL display that day as a rest day with 0 hours.
6. IF the Projection_API returns an error or projected schedule data is unavailable for the selected teammate, THEN THE Hours_Dashboard SHALL display a message indicating that the daily breakdown cannot be loaded and SHALL not display partial or stale data.

### Requirement 5: Support Real-Time Updates

**User Story:** As a manager, I want the projected hours dashboard to update automatically when schedule changes occur, so that I always see current information without manually refreshing.

#### Acceptance Criteria

1. WHEN an override is applied that affects a teammate's schedule within the Evaluation_Period, THE Hours_Dashboard SHALL refresh the projected values for that teammate within 5 seconds of the change being persisted.
2. WHEN a teammate's Rotation_Group is changed and saved, THE Hours_Dashboard SHALL refresh the projected values for that teammate within 5 seconds of the change being persisted.
3. WHEN a teammate's custom start time is modified and saved, THE Hours_Dashboard SHALL refresh the projected values for that teammate within 5 seconds of the change being persisted.
4. WHEN shift window start or end times are modified and saved in Settings, THE Hours_Dashboard SHALL refresh the projected values for all teammates within 5 seconds of the change being persisted.
5. IF the Hours_Dashboard fails to retrieve updated projected values from the Projection_API during a refresh attempt, THEN THE Hours_Dashboard SHALL display a visual indicator that the displayed values may be stale and SHALL retry the refresh once after 5 seconds.
6. WHILE the Hours_Dashboard is fetching updated projected values after a detected change, THE Hours_Dashboard SHALL display a loading indicator on the affected teammate's projected values until the updated values are rendered or the request fails.

### Requirement 6: Provide Compliance Summary for Rotation Groups

**User Story:** As a manager, I want to see a summary of compliance status across all teammates in a rotation group, so that I can quickly identify groups with workload concerns.

#### Acceptance Criteria

1. WHEN a Manager views the Team Management page, THE Hours_Dashboard SHALL display a summary row for each Rotation_Group showing the count of teammates within compliance, the count approaching a limit (within 90% of any Compliance_Limit), and the count exceeding a limit.
2. WHEN a teammate's projected weekly hours exceed 54 hours (90% of 60) but remain at or below 60 hours, THE Hours_Dashboard SHALL classify that teammate as "approaching" the weekly hours limit in the group summary.
3. WHEN a teammate's projected days worked equal 5 days in any rolling 7-day window (the nearest whole number below the 6-day limit), THE Hours_Dashboard SHALL classify that teammate as "approaching" the weekly days limit in the group summary.
4. WHEN a teammate's projected maximum daily hours exceed 10.8 hours (90% of 12) but remain at or below 12 hours, THE Hours_Dashboard SHALL classify that teammate as "approaching" the daily hours limit in the group summary.
5. WHEN all teammates in a Rotation_Group are within compliance and none are approaching a limit, THE Hours_Dashboard SHALL display the group summary with a compliant Compliance_Status indicator.
6. IF a teammate's projected values exceed any Compliance_Limit and also approach a different Compliance_Limit, THEN THE Hours_Dashboard SHALL classify that teammate only as "exceeding" in the group summary count, using the most severe classification when multiple limits are triggered.
7. IF at least one teammate in a Rotation_Group exceeds any Compliance_Limit, THEN THE Hours_Dashboard SHALL display the group summary with a non-compliant Compliance_Status indicator regardless of other teammates' statuses.
8. IF no teammate in a Rotation_Group exceeds a Compliance_Limit but at least one teammate is classified as "approaching," THEN THE Hours_Dashboard SHALL display the group summary with a warning Compliance_Status indicator.
