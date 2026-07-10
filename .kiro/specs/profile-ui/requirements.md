# Requirements Document

## Introduction

This specification covers the frontend Profile UI for DC-ShiftMaster Pro. The backend already supports user profile management via `PUT /api/auth/profile` and `GET /api/auth/me` (returning `email` and `email_notifications_enabled` fields), but there is no frontend interface for users to view or update these settings. This feature adds a Profile view to the application where users can enter or update their email address, toggle email notifications on or off, and see their current profile settings. The Profile view follows the same vanilla HTML/CSS/JS patterns used by existing views (Dashboard, Team, Settings, etc.).

## Glossary

- **App**: The DC-ShiftMaster Pro HTML/CSS/JS single-page web application
- **Profile_View**: The new view section in the App where users manage their email and notification preferences
- **Router**: The client-side view-switching module (`router.js`) that shows/hides view sections and calls loader functions
- **API_Module**: The client-side fetch wrapper (`api.js`) that provides methods for calling backend endpoints
- **Toast**: The notification system that displays success and error messages to the user
- **Sidebar**: The left-side navigation panel containing links to all views
- **Bottom_Nav**: The mobile bottom navigation bar shown on small screens
- **Profile_Form**: The form within the Profile_View containing the email input and notification toggle
- **Notification_Toggle**: A checkbox or toggle control that represents the `email_notifications_enabled` preference

## Requirements

### Requirement 1: Profile View Navigation

**User Story:** As a user, I want to access a Profile view from the app navigation, so that I can find and manage my profile settings.

#### Acceptance Criteria

1. THE App SHALL include a "Profile" navigation item in the Sidebar between the "My Shifts" item and the bottom of the navigation list
2. THE App SHALL include a "Profile" navigation item in the Bottom_Nav for mobile screens
3. WHEN a user clicks the Profile navigation item, THE Router SHALL display the Profile_View and hide all other views
4. WHEN the Profile_View is displayed, THE Router SHALL highlight the Profile navigation item as active in both the Sidebar and Bottom_Nav
5. WHEN the Profile_View is displayed, THE Router SHALL call a loader function that populates the Profile_View with current user data

### Requirement 2: Display Current Profile Data

**User Story:** As a user, I want to see my current email address and notification preference when I open the Profile view, so that I know my current settings.

#### Acceptance Criteria

1. WHEN the Profile_View loads, THE App SHALL fetch the current user data from the `GET /api/auth/me` endpoint
2. WHEN user data is received, THE Profile_Form SHALL display the user's current email address in the email input field
3. WHEN user data is received, THE Profile_Form SHALL display the current state of the Notification_Toggle matching the `email_notifications_enabled` value
4. WHEN user data is received, THE Profile_View SHALL display the user's display name and username as read-only information
5. IF the `GET /api/auth/me` request fails, THEN THE App SHALL display an error message via the Toast system

### Requirement 3: Update Email Address

**User Story:** As a user, I want to enter or change my email address in the Profile view, so that the system can send me email notifications.

#### Acceptance Criteria

1. THE Profile_Form SHALL include a text input field for the email address with an appropriate label
2. WHEN the user submits the Profile_Form with a new email address, THE API_Module SHALL send a `PUT /api/auth/profile` request with the `email` field
3. WHEN the profile update succeeds, THE App SHALL display a success message via the Toast system
4. IF the backend returns a validation error for the email format, THEN THE App SHALL display the error message via the Toast system
5. THE email input field SHALL use `type="email"` for basic browser-level input assistance

### Requirement 4: Toggle Email Notifications

**User Story:** As a user, I want to toggle email notifications on or off in the Profile view, so that I control whether I receive coverage event emails.

#### Acceptance Criteria

1. THE Profile_Form SHALL include a Notification_Toggle control with a label indicating its purpose
2. WHEN the user submits the Profile_Form with a changed notification preference, THE API_Module SHALL send a `PUT /api/auth/profile` request with the `email_notifications_enabled` field
3. IF the backend returns an error because notifications cannot be enabled without an email address, THEN THE App SHALL display the error message via the Toast system
4. WHEN the profile update succeeds and the notification preference changed, THE App SHALL display a success message via the Toast system

### Requirement 5: Profile Form Submission

**User Story:** As a user, I want to save my profile changes with a single action, so that both email and notification preference are updated together.

#### Acceptance Criteria

1. THE Profile_Form SHALL include a "Save" button that submits both the email address and the Notification_Toggle value in a single `PUT /api/auth/profile` request
2. WHILE the profile update request is in progress, THE Save button SHALL be disabled to prevent duplicate submissions
3. WHEN the profile update request completes (success or failure), THE Save button SHALL be re-enabled
4. WHEN the profile update succeeds, THE App SHALL update the locally cached user data in `AppState.user` with the new email and notification preference values

### Requirement 6: API Module Extension

**User Story:** As a developer, I want the API module to include a method for updating the user profile, so that the Profile_View can call the backend endpoint.

#### Acceptance Criteria

1. THE API_Module SHALL provide an `updateProfile` method that sends a `PUT` request to `/api/auth/profile` with a JSON body
2. THE `updateProfile` method SHALL accept an object with optional `email` and `email_notifications_enabled` fields
3. THE `updateProfile` method SHALL follow the same request/response pattern as other API_Module methods (using the shared `json` helper)

### Requirement 7: Consistent Styling

**User Story:** As a user, I want the Profile view to look consistent with the rest of the application, so that the experience feels cohesive.

#### Acceptance Criteria

1. THE Profile_View SHALL use the existing `settings-section` CSS class for grouping form elements
2. THE Profile_View SHALL use the existing `form-group`, `form-control`, and `btn` CSS classes for form elements
3. THE Profile_View SHALL be responsive, adapting layout for desktop, tablet, and mobile screen sizes using the existing responsive breakpoints
