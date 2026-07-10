# Requirements Document

## Introduction

Labor Compliance Validation adds pre-override safety checks to DC-ShiftMaster Pro. When a manager moves a teammate from one rotation group to another (e.g., Front Half Day to Back Half Day) via the override system, the application validates that the resulting schedule does not violate labor compliance limits. The three limits enforced are: no more than 60 hours worked in any rolling 7-day window, no more than 6 days worked in any rolling 7-day window, and no more than 12 hours worked in a single calendar day. If a violation would occur, the manager receives a warning but may still acknowledge and proceed with the override.

## Glossary

- **Compliance_Validator**: The module responsible for computing projected hours and days worked for a teammate and determining whether a proposed override would violate labor limits.
- **Override_API**: The existing Flask route (`POST /api/overrides`) that creates or updates a manual shift override.
- **Rolling_Window**: A consecutive 7-day period anchored to the override date, spanning 3 days before through 3 days after the target date.
- **Shift_Duration**: The number of hours a teammate works on a given day, calculated from their effective start time to the shift window end time.
- **Effective_Start_Time**: The teammate's custom start time if one is configured, otherwise the default shift window start time.
- **Compliance_Violation**: A condition where a proposed override would cause a teammate to exceed one or more labor limits (60 weekly hours, 6 weekly days, or 12 daily hours).
- **Manager**: The user performing the override action in the scheduling interface.
- **Acknowledgment**: An explicit confirmation from the Manager that they accept the compliance warning and wish to proceed with the override.

## Requirements

### Requirement 1: Validate Weekly Hours Limit

**User Story:** As a manager, I want the system to check that moving a teammate to a different shift will not cause them to exceed 60 hours in any rolling 7-day window, so that I can avoid scheduling labor violations.

#### Acceptance Criteria

1. WHEN a Manager submits an override request, THE Compliance_Validator SHALL compute the total Shift_Duration for the affected teammate by summing all scheduled shifts and the proposed override shift across every Rolling_Window (any consecutive 7-calendar-day period) that includes the override date.
2. THE Compliance_Validator SHALL calculate Shift_Duration for each shift as the elapsed time in hours between the Shift_Window start time and end time, accounting for overnight spans (e.g., 18:00–06:30 equals 12.5 hours).
3. IF the computed total hours for any Rolling_Window would exceed 60 hours, THEN THE Compliance_Validator SHALL reject the override request and return a violation result that includes the projected total hours and identifies which Rolling_Window exceeded the 60-hour limit.
4. IF the computed total hours for all Rolling_Windows remain at or below 60 hours, THEN THE Compliance_Validator SHALL return a passing result permitting the override to proceed.
5. IF the Compliance_Validator cannot retrieve the teammate's existing shift data for the relevant Rolling_Windows, THEN THE Compliance_Validator SHALL reject the override request and return an error result indicating that validation could not be completed.
6. WHEN a Manager submits an override request, THE Compliance_Validator SHALL return the validation result within 2 seconds.

### Requirement 2: Validate Weekly Days Limit

**User Story:** As a manager, I want the system to check that moving a teammate to a different shift will not cause them to work more than 6 days in any rolling 7-day window, so that I can ensure teammates get adequate rest.

#### Acceptance Criteria

1. WHEN a Manager submits an override request, THE Compliance_Validator SHALL identify every Rolling_Window (each consecutive span of 7 calendar days) that includes the override date — up to 7 overlapping windows — and count the number of distinct days the affected teammate is scheduled to work within each window, treating any day where the teammate holds at least one assigned Slot (computed or overridden) as a scheduled day.
2. IF the count of scheduled days in any Rolling_Window would exceed 6 days after applying the proposed override, THEN THE Compliance_Validator SHALL reject the override request and return a violation result that includes the specific Rolling_Window start and end dates, the projected day count (7), and the maximum allowed (6).
3. IF the count of scheduled days in all Rolling_Windows remains at or below 6 days after applying the proposed override, THEN THE Compliance_Validator SHALL approve the override request and return a passing result with no violations.
4. WHEN the Compliance_Validator rejects an override request due to a weekly days limit violation, THE Application SHALL display the violation details to the Manager and SHALL NOT persist the override to the database.

### Requirement 3: Validate Daily Hours Limit

**User Story:** As a manager, I want the system to check that a teammate will not work more than 12 hours in a single calendar day as a result of an override, so that I can prevent excessive daily workloads.

#### Acceptance Criteria

1. WHEN a Manager submits an override request, THE Compliance_Validator SHALL compute the total Shift_Duration for the affected teammate on the override date by summing the duration of the proposed override shift and the duration of any other shift assigned to the same teammate on the same calendar date, where each Shift_Duration is calculated from the Effective_Start_Time to the shift window end time for the corresponding shift type.
2. WHEN computing total daily hours for a night shift (where the shift window end time is past midnight), THE Compliance_Validator SHALL attribute the full Shift_Duration to the calendar date on which the shift starts.
3. IF the total Shift_Duration on the override date would exceed 12 hours, THEN THE Compliance_Validator SHALL return a violation result specifying the rule violated as daily hours limit, the projected total hours as a numeric value, and the limit of 12 hours.
4. WHEN the total Shift_Duration on the override date remains at or equal to 12 hours, THE Compliance_Validator SHALL return a passing result with no violations.
5. WHEN the proposed override assigns the same teammate who is already assigned to the target slot, THE Compliance_Validator SHALL compute the daily total based on the resulting schedule without double-counting the unchanged assignment.

### Requirement 4: Use Effective Start Times for Duration Calculation

**User Story:** As a manager, I want the compliance check to account for each teammate's custom start time when calculating shift duration, so that the validation reflects actual working hours.

#### Acceptance Criteria

1. WHEN computing Shift_Duration for a teammate who has a non-empty custom_start value in HH:MM format, THE Compliance_Validator SHALL use the custom_start value as the shift start time instead of the default shift window start time.
2. WHEN computing Shift_Duration for a teammate whose custom_start value is empty, THE Compliance_Validator SHALL use the default shift window start time as the Effective_Start_Time.
3. THE Compliance_Validator SHALL calculate Shift_Duration in hours as the elapsed time from the Effective_Start_Time to the shift window end time for the corresponding shift type, adding 24 hours to the end time when the end time is earlier than the Effective_Start_Time to account for overnight shifts.
4. IF the Effective_Start_Time equals the shift window end time for the corresponding shift type, THEN THE Compliance_Validator SHALL compute the Shift_Duration as 0 hours.

### Requirement 5: Display Compliance Warning to Manager

**User Story:** As a manager, I want to see a clear warning when a proposed override would violate labor limits, so that I can make an informed decision before proceeding.

#### Acceptance Criteria

1. WHEN the Compliance_Validator returns one or more violations, THE Override_API SHALL respond with a warning payload containing the list of violations, each specifying the rule violated (weekly hours, weekly days, or daily hours), the projected value as a number, and the applicable limit as a number.
2. WHEN the Override_API responds with a compliance warning, THE scheduling interface SHALL display each violation's rule name, projected value, and limit to the Manager, and SHALL NOT apply the override until the Manager explicitly acknowledges or dismisses the warning.
3. WHEN no violations are detected, THE Override_API SHALL proceed to apply the override without displaying a warning.
4. IF the Compliance_Validator encounters an error during validation, THEN THE Override_API SHALL respond with an error indication and SHALL NOT apply the override.

### Requirement 6: Allow Override with Acknowledgment

**User Story:** As a manager, I want the option to proceed with an override even when a compliance warning is raised, so that I can handle exceptional situations where the override is still necessary.

#### Acceptance Criteria

1. WHEN the Manager receives a compliance warning, THE scheduling interface SHALL present two distinct options: one to acknowledge the warning and proceed with the override, and one to cancel and return to the previous state without applying the override.
2. WHEN the Manager submits the override request with an Acknowledgment flag set, THE Override_API SHALL apply the override regardless of compliance violations, record the override with an acknowledged-violation indicator, and THE scheduling interface SHALL display a confirmation indicating the override was applied.
3. WHEN the Manager selects the cancel option or closes the warning dialog without acknowledging, THE Override_API SHALL not apply the override and the schedule SHALL remain unchanged.
4. IF the Override_API fails to apply an acknowledged override due to a non-compliance error (e.g., invalid date, missing teammate), THEN THE scheduling interface SHALL display an error message indicating the reason for failure and the schedule SHALL remain unchanged.

### Requirement 7: Include Existing Overrides in Compliance Calculation

**User Story:** As a manager, I want the compliance check to consider all existing overrides for the teammate within the rolling window, so that the validation accounts for previously scheduled moves.

#### Acceptance Criteria

1. WHEN computing hours and days for the Rolling_Window, THE Compliance_Validator SHALL include any shift within the Rolling_Window where an existing override assigns the affected teammate by name, in addition to shifts assigned through the teammate's regular rotation schedule.
2. WHEN an existing override on a date and shift where the teammate is the computed rotation assignee assigns a different name or "nobody," THE Compliance_Validator SHALL exclude that shift from the teammate's projected schedule for the Rolling_Window.
3. WHEN a teammate retains at least one shift assignment on a given date after applying existing overrides, THE Compliance_Validator SHALL count that date as a scheduled day for the weekly days limit calculation.
4. THE Compliance_Validator SHALL resolve the teammate's complete projected schedule for the Rolling_Window by applying all existing overrides before adding the proposed new override, then evaluate compliance limits against the resulting combined schedule.
