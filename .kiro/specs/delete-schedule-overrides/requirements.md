# Requirements Document

## Introduction

This feature adds the ability to bulk-delete schedule overrides from the DC-ShiftMaster Pro dashboard UI. Currently, overrides created by ICS or JSON imports can only be removed one at a time via the calendar's override modal. When a bad file import creates many incorrect overrides, users need a way to clear them efficiently — either all overrides for a date range, all overrides for a specific year, or through a list-based selection interface.

## Glossary

- **Override_Manager**: The backend component responsible for querying, filtering, and bulk-deleting overrides from the database.
- **Override_Panel**: The UI component on the Team Management page that displays existing overrides and provides bulk-deletion controls.
- **Dashboard**: The main calendar view of DC-ShiftMaster Pro where overrides are visualized.
- **Date_Range**: A pair of start and end dates (inclusive) used to scope bulk-deletion operations.
- **Bulk_Delete**: An operation that removes multiple overrides in a single action.
- **Confirmation_Dialog**: A modal dialog that requires explicit user confirmation before destructive bulk operations proceed.

## Requirements

### Requirement 1: View Existing Overrides

**User Story:** As a team admin, I want to see a list of all overrides for the current year, so that I can identify which overrides to remove.

#### Acceptance Criteria

1. WHEN the user navigates to the Override_Panel, THE Override_Panel SHALL display all overrides for the currently selected year grouped by month.
2. THE Override_Panel SHALL display the date, shift type, and assigned name for each override.
3. WHEN no overrides exist for the selected year, THE Override_Panel SHALL display a message indicating no overrides are present. THE Override_Panel SHALL only display this message when no overrides actually exist; the message SHALL NOT appear when overrides are present.
4. WHEN the user changes the year selector, THE Override_Panel SHALL refresh the override list to show overrides for the newly selected year.

### Requirement 2: Bulk Delete Overrides by Date Range

**User Story:** As a team admin, I want to delete all overrides within a specific date range, so that I can undo a bad import without affecting overrides outside that range.

#### Acceptance Criteria

1. WHEN the user specifies a start date and end date and confirms the deletion, THE Override_Manager SHALL execute the deletion operation for overrides with dates within that range (inclusive) for the current team, even when zero overrides match the range.
2. IF the start date is after the end date, THEN THE Override_Panel SHALL display a validation error and prevent the deletion request.
3. WHEN the user initiates a date-range deletion, THE Confirmation_Dialog SHALL display the count of overrides that will be deleted before proceeding.
4. IF no overrides exist within the specified date range, THEN THE Override_Panel SHALL inform the user that no overrides match the criteria.

### Requirement 3: Clear All Overrides for a Year

**User Story:** As a team admin, I want to clear all overrides for an entire year, so that I can start fresh after a catastrophic bad import.

#### Acceptance Criteria

1. WHEN the user selects "Clear All Overrides" and confirms via the Confirmation_Dialog, THE Override_Manager SHALL delete all overrides for the selected year for the current team.
2. WHEN the user initiates a clear-all operation, THE Confirmation_Dialog SHALL display the total count of overrides that will be removed and require the user to type a confirmation phrase.
3. WHEN the clear-all operation completes successfully, THE Override_Panel SHALL refresh to show an empty override list regardless of any display lag.

### Requirement 4: Selective Override Deletion

**User Story:** As a team admin, I want to select individual overrides from the list and delete them in batch, so that I can precisely remove only the incorrect overrides.

#### Acceptance Criteria

1. THE Override_Panel SHALL provide a checkbox next to each override entry for selection.
2. WHEN the user selects one or more overrides and clicks the delete button, THE Confirmation_Dialog SHALL display the count of selected overrides before proceeding. IF the Confirmation_Dialog fails to display due to a technical issue, THE system SHALL block the deletion operation.
3. WHEN the user confirms selective deletion, THE Override_Manager SHALL delete only the selected overrides for the current team.
4. THE Override_Panel SHALL provide a "Select All" checkbox that toggles selection of all visible overrides.

### Requirement 5: Backend Bulk Delete API

**User Story:** As a developer, I want a bulk-delete API endpoint, so that the frontend can efficiently remove multiple overrides in a single request.

#### Acceptance Criteria

1. WHEN a DELETE request is sent to the bulk-delete endpoint with a date range, THE Override_Manager SHALL remove all overrides within that date range for the authenticated team.
2. WHEN a DELETE request is sent with a list of specific override keys (date + shift_type pairs), THE Override_Manager SHALL remove only those specified overrides for the authenticated team.
3. THE Override_Manager SHALL return the count of overrides deleted in the response body.
4. IF the request contains no valid override identifiers or date range, THEN THE Override_Manager SHALL return a 400 status code with a descriptive error message. IF any identifier in a list of keys is invalid, THE Override_Manager SHALL reject the entire request rather than processing valid keys partially.
5. THE Override_Manager SHALL scope all delete operations to the current team context, preventing cross-team data deletion.

### Requirement 6: Post-Deletion UI Feedback

**User Story:** As a team admin, I want clear feedback after a bulk delete operation, so that I know the operation succeeded and how many overrides were removed.

#### Acceptance Criteria

1. WHEN a bulk-delete operation completes successfully, THE Override_Panel SHALL display a success toast showing the number of overrides removed, including when zero overrides were deleted.
2. WHEN a bulk-delete operation fails, THE Override_Panel SHALL display an error toast with a description of the failure.
3. WHEN a bulk-delete operation completes, THE Dashboard SHALL refresh the calendar view to reflect the updated override state.
