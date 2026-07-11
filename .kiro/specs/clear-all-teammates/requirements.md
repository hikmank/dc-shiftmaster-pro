# Requirements Document

## Introduction

The Clear All Teammates feature provides a bulk reset capability for the Team Management page. When a bad import or incorrect setup populates the roster with wrong teammates, the user needs to wipe all teammates at once and start fresh rather than deleting them one by one. Clearing all teammates resets the calendar to a blank state showing "nobody" for all shifts, allowing the user to re-add correct teammates or re-import.

## Glossary

- **Clear_All_Endpoint**: The API route `DELETE /api/teammates/all` that removes every teammate record scoped to the current team.
- **Team_View**: The Team Management section of the DC-ShiftMaster Pro frontend that displays teammates grouped by shift type, with add/edit/delete controls.
- **Confirmation_Dialog**: A browser-native confirmation prompt requiring explicit user approval before the destructive bulk-delete executes.
- **DatabaseManager**: The Python class managing all SQLite operations for teammates, overrides, shift windows, and related entities.
- **Team_ID**: The team_profiles foreign key that scopes all teammate queries to the active team in multi-team deployments.

## Requirements

### Requirement 1: Bulk Delete API Endpoint

**User Story:** As a team administrator, I want a single API call that removes all teammates for my team, so that I can reset the roster without issuing individual delete requests.

#### Acceptance Criteria

1. WHEN a DELETE request is sent to `/api/teammates/all`, THE Clear_All_Endpoint SHALL remove all teammate records belonging to the current Team_ID from the database.
2. WHEN a DELETE request is sent to `/api/teammates/all` and the current team has zero teammates, THE Clear_All_Endpoint SHALL return a successful response with a deleted count of zero.
3. THE Clear_All_Endpoint SHALL return a JSON response containing the count of deleted teammate records.
4. WHEN a DELETE request is sent to `/api/teammates/all` and all teammate records are successfully removed, THE Clear_All_Endpoint SHALL return HTTP status 200 indicating both no database error AND actual teammate removal.
5. IF an internal database error occurs during bulk deletion, THEN THE Clear_All_Endpoint SHALL return HTTP status 500 with an error message.

### Requirement 2: Team Scoping

**User Story:** As a user in a multi-team deployment, I want the clear-all action to only affect my team's teammates, so that other teams' rosters remain untouched.

#### Acceptance Criteria

1. WHEN Team_ID is present in the request context, THE Clear_All_Endpoint SHALL delete only teammate records where team_id matches the current Team_ID.
2. WHEN Team_ID is not present in the request context, THE Clear_All_Endpoint SHALL delete all teammate records without team scoping (legacy single-team behavior).
3. FOR ALL teammate records belonging to other teams, THE Clear_All_Endpoint SHALL leave those records unchanged after execution.

### Requirement 3: Frontend Clear All Button

**User Story:** As a team administrator, I want a visible "Clear All" button on the Team Management page, so that I can initiate a full roster reset with one click.

#### Acceptance Criteria

1. THE Team_View SHALL display a "Clear All" button in the toolbar actions area alongside the existing Add, Import, and Export buttons.
2. WHEN the team roster contains one or more teammates, THE Team_View SHALL enable the "Clear All" button and keep it enabled until a deletion operation fully completes and the count reaches zero.
3. WHEN the team roster contains zero teammates and no deletion is in progress, THE Team_View SHALL disable the "Clear All" button to prevent unnecessary actions.
4. THE "Clear All" button SHALL use a danger styling (btn-danger class) to visually communicate the destructive nature of the action.

### Requirement 4: Confirmation Before Deletion

**User Story:** As a team administrator, I want to confirm before clearing all teammates, so that I do not accidentally destroy the roster.

#### Acceptance Criteria

1. WHEN the user clicks the "Clear All" button and the teammate count is greater than zero, THE Team_View SHALL display a Confirmation_Dialog before executing the deletion.
2. THE Confirmation_Dialog SHALL include the number of teammates that will be deleted in its message text.
3. WHEN the user confirms the Confirmation_Dialog, THE Team_View SHALL call the Clear_All_Endpoint and reload the teammate list on success.
4. WHEN the user cancels the Confirmation_Dialog, THE Team_View SHALL take no action and leave the roster unchanged.

### Requirement 5: User Feedback

**User Story:** As a team administrator, I want clear feedback after the reset operation, so that I know the action completed successfully or failed.

#### Acceptance Criteria

1. WHEN the Clear_All_Endpoint returns success, THE Team_View SHALL display a success toast showing the number of teammates removed.
2. IF the Clear_All_Endpoint returns an error, THEN THE Team_View SHALL display an error toast with the error message.
3. WHEN the Clear_All_Endpoint returns a successful response, THE Team_View SHALL reload the teammate list to reflect the empty state; IF the endpoint returns an error, THEN THE Team_View SHALL NOT reload the list.

### Requirement 6: Database Bulk Delete Method

**User Story:** As a developer, I want a dedicated database method for clearing all teammates, so that the operation executes atomically in a single SQL statement.

#### Acceptance Criteria

1. THE DatabaseManager SHALL provide a `clear_all_teammates` method that accepts an optional team_id parameter.
2. WHEN team_id is provided, THE DatabaseManager SHALL execute a single DELETE statement scoped to that team_id.
3. WHEN team_id is not provided, THE DatabaseManager SHALL execute a single DELETE statement removing all teammate records (legacy behavior).
4. THE DatabaseManager SHALL return the count of rows deleted by the operation.
5. THE DatabaseManager SHALL execute the deletion within a single transaction to maintain atomicity.
