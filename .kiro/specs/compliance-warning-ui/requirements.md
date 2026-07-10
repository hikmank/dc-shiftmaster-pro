# Requirements Document

## Introduction

The Compliance Warning UI adds a frontend layer that intercepts compliance violation responses from the override API and presents them to the manager in a clear, actionable modal dialog. When a manager submits a shift override that would violate labor compliance rules (weekly hours, weekly days, or daily hours limits), the system displays the specific violations and offers the manager a choice to acknowledge and proceed or cancel the override. This feature bridges the existing backend compliance validation with a user-facing warning experience in the vanilla JavaScript frontend.

## Glossary

- **Compliance_Warning_Modal**: A modal dialog element displayed over the page content that presents compliance violation details and action buttons to the manager
- **Override_Submission_Handler**: The JavaScript function responsible for sending override requests to `POST /api/overrides` and handling responses
- **Violation_Card**: A styled block within the Compliance_Warning_Modal that displays a single violation's rule name, projected value, and limit
- **Acknowledgment_Resubmission**: A second `POST /api/overrides` request that includes `acknowledge_violations: true` to force the override through despite violations
- **Toast_Notification**: The existing toast message system (`Toast.show`) used for success and error feedback
- **API_Module**: The existing `API` object in `api.js` that wraps fetch calls to the backend
- **Weekly_Summary_Row**: A horizontal row rendered below each calendar week (Sunday–Saturday) that displays per-teammate hours and days worked with color-coded compliance thresholds
- **Work_Week**: A seven-day period starting on Sunday and ending on Saturday, used as the compliance evaluation window on the dashboard
- **Duration_Calculator**: A client-side JavaScript function that computes shift duration in hours from start and end times, handling overnight shifts

## Requirements

### Requirement 1: Detect Compliance Violation Response

**User Story:** As a manager, I want the system to detect when my override request triggers compliance violations, so that I am informed before the override is silently rejected.

#### Acceptance Criteria

1. WHEN the `POST /api/overrides` endpoint returns HTTP status 422 with a JSON body containing `status: "compliance_warning"`, THE Override_Submission_Handler SHALL intercept the response and prevent the default error toast from displaying
2. WHEN the `POST /api/overrides` endpoint returns HTTP status 422 with a JSON body containing a `violations` array, THE Override_Submission_Handler SHALL extract the violations array from the response body
3. IF the `POST /api/overrides` endpoint returns HTTP status 422 without a `violations` array, THEN THE Override_Submission_Handler SHALL display the default error toast with the response error message

### Requirement 2: Display Compliance Warning Modal

**User Story:** As a manager, I want to see a clear summary of which compliance rules would be violated, so that I can make an informed decision about whether to proceed.

#### Acceptance Criteria

1. WHEN compliance violations are detected from the override response, THE Compliance_Warning_Modal SHALL become visible as an overlay on top of the page content
2. THE Compliance_Warning_Modal SHALL display a warning heading that reads "Compliance Warning"
3. THE Compliance_Warning_Modal SHALL display one Violation_Card for each violation object in the violations array
4. WHEN a violation has rule value "weekly_hours", THE Violation_Card SHALL display the label "Weekly Hours Exceeded", the projected value, and the limit value
5. WHEN a violation has rule value "weekly_days", THE Violation_Card SHALL display the label "Weekly Days Exceeded", the projected value, and the limit value
6. WHEN a violation has rule value "daily_hours", THE Violation_Card SHALL display the label "Daily Hours Exceeded", the projected value, and the limit value
7. WHEN a violation includes non-null `window_start` and `window_end` values, THE Violation_Card SHALL display the date range in the format "window_start – window_end"
8. THE Compliance_Warning_Modal SHALL display an "Acknowledge & Proceed" button and a "Cancel" button below the violation list

### Requirement 3: Acknowledge and Resubmit Override

**User Story:** As a manager, I want to acknowledge the compliance warnings and proceed with the override when I determine it is necessary, so that I am not blocked from making legitimate scheduling decisions.

#### Acceptance Criteria

1. WHEN the manager clicks the "Acknowledge & Proceed" button, THE Override_Submission_Handler SHALL send a new `POST /api/overrides` request with the original override data plus `acknowledge_violations: true`
2. WHEN the Acknowledgment_Resubmission returns HTTP status 201, THE Compliance_Warning_Modal SHALL close and THE Toast_Notification SHALL display a success message "Override saved"
3. WHEN the Acknowledgment_Resubmission returns HTTP status 201, THE Override_Submission_Handler SHALL refresh the calendar view to reflect the new override
4. IF the Acknowledgment_Resubmission returns an error status, THEN THE Compliance_Warning_Modal SHALL close and THE Toast_Notification SHALL display the error message from the response

### Requirement 4: Cancel Override from Warning Modal

**User Story:** As a manager, I want to cancel the override after seeing compliance warnings, so that I can avoid creating a non-compliant schedule.

#### Acceptance Criteria

1. WHEN the manager clicks the "Cancel" button on the Compliance_Warning_Modal, THE Compliance_Warning_Modal SHALL close without sending any additional API requests
2. WHEN the manager clicks the "Cancel" button, THE Override_Submission_Handler SHALL leave the existing override modal in its current state so the manager can adjust selections
3. THE Compliance_Warning_Modal SHALL also close when the manager presses the Escape key

### Requirement 5: Loading State During Acknowledgment

**User Story:** As a manager, I want visual feedback that my acknowledgment is being processed, so that I do not accidentally submit duplicate requests.

#### Acceptance Criteria

1. WHILE the Acknowledgment_Resubmission request is in progress, THE Compliance_Warning_Modal SHALL disable both the "Acknowledge & Proceed" button and the "Cancel" button
2. WHILE the Acknowledgment_Resubmission request is in progress, THE "Acknowledge & Proceed" button SHALL display the text "Submitting..." instead of its default label
3. WHEN the Acknowledgment_Resubmission request completes (success or error), THE Compliance_Warning_Modal SHALL re-enable both buttons and restore the default button label

### Requirement 6: Accessibility of Compliance Warning Modal

**User Story:** As a manager using assistive technology, I want the compliance warning modal to be accessible, so that I can understand and interact with the warnings using a screen reader or keyboard.

#### Acceptance Criteria

1. THE Compliance_Warning_Modal SHALL have `role="dialog"` and `aria-modal="true"` attributes
2. THE Compliance_Warning_Modal SHALL have an `aria-labelledby` attribute referencing the warning heading element
3. WHEN the Compliance_Warning_Modal opens, THE Compliance_Warning_Modal SHALL move keyboard focus to the first focusable element within the modal
4. WHILE the Compliance_Warning_Modal is visible, THE Compliance_Warning_Modal SHALL trap keyboard focus within the modal (Tab and Shift+Tab cycle through modal elements only)
5. THE Violation_Card elements SHALL use `role="alert"` to announce violation details to screen readers
6. THE "Acknowledge & Proceed" button and "Cancel" button SHALL have descriptive `aria-label` attributes that include context about the compliance warning action

### Requirement 7: Dashboard Weekly Compliance Summary Row

**User Story:** As a manager, I want to see each teammate's weekly hours and days worked directly on the calendar dashboard, so that I can identify who is approaching compliance limits before attempting an override.

#### Acceptance Criteria

1. THE Dashboard SHALL display one Weekly_Summary_Row below each calendar week (Sunday through Saturday) within the current month view
2. THE Weekly_Summary_Row SHALL list each teammate who has at least one shift assigned during that Work_Week, showing their total hours and total days worked
3. THE Duration_Calculator SHALL compute shift duration as (end_time - start_time) in hours, adding 24 hours when end_time is less than start_time to handle overnight shifts
4. THE Duration_Calculator SHALL use the teammate's custom_start time when available, falling back to the shift window default start time
5. WHEN a teammate's weekly hours are below 50, THE Weekly_Summary_Row SHALL display that teammate's hours in green
6. WHEN a teammate's weekly hours are between 50 and 59 (inclusive), THE Weekly_Summary_Row SHALL display that teammate's hours in yellow
7. WHEN a teammate's weekly hours are 60 or above, THE Weekly_Summary_Row SHALL display that teammate's hours in red
8. WHEN a teammate's weekly days worked are 6 or more, THE Weekly_Summary_Row SHALL display that teammate's day count in red
9. THE Weekly_Summary_Row SHALL compute totals client-side from the schedule data already loaded on the dashboard without making additional API requests
10. WHEN the calendar view is refreshed or the month changes, THE Weekly_Summary_Row SHALL recalculate and re-render with the updated schedule data
