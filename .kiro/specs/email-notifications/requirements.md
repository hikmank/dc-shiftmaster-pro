# Requirements Document

## Introduction

This specification covers adding email notifications to DC-ShiftMaster Pro so that teammates who are not actively using the web application still receive timely alerts about coverage request events. The feature uses AWS Simple Email Service (SES) for delivery, adds an email address field to user profiles, and provides opt-in/opt-out controls for email notifications. Email notifications complement the existing real-time WebSocket notifications by reaching users who are offline.

## Glossary

- **App**: The DC-ShiftMaster Pro HTML/Flask web application
- **Email_Service**: The server-side module responsible for composing and sending email messages via AWS SES
- **SES_Client**: The AWS SES SDK client (boto3) used by the Email_Service to send emails
- **User**: A registered account in the App, represented by the User dataclass
- **Coverage_Event**: A state change in the coverage request system — specifically a create, claim, unclaim, or cancel action
- **Notification_Preference**: A per-user boolean setting indicating whether the user has opted in to receive email notifications
- **Recipient_Set**: The set of users who are eligible to receive an email for a given Coverage_Event, determined by Notification_Preference and event type
- **Email_Template**: A predefined text structure used by the Email_Service to compose the subject and body of a notification email

## Requirements

### Requirement 1: User Email Field

**User Story:** As a user, I want to add an email address to my profile, so that the system can send me email notifications.

#### Acceptance Criteria

1. THE App SHALL store an email address field for each User in the database
2. WHEN a user registers, THE App SHALL accept an optional email address in the registration request
3. WHEN a user updates their profile, THE App SHALL allow the user to set or change their email address
4. WHEN an email address is provided, THE App SHALL validate that the email address contains exactly one "@" character with non-empty local and domain parts
5. THE App SHALL allow the email field to be empty, indicating the user has not provided an email address

### Requirement 2: Email Notification Preference

**User Story:** As a user, I want to opt in or out of email notifications, so that I control whether I receive coverage event emails.

#### Acceptance Criteria

1. THE App SHALL store a Notification_Preference for each User in the database with a default value of false (opted out)
2. WHEN a user updates their profile, THE App SHALL allow the user to toggle their Notification_Preference
3. WHEN a user sets Notification_Preference to true but has no email address stored, THE App SHALL return an error indicating that an email address is required before enabling notifications
4. THE App SHALL expose the current Notification_Preference value in the user profile API response

### Requirement 3: Email Notification on Coverage Request Created

**User Story:** As a teammate, I want to receive an email when a new coverage request is posted, so that I know someone needs shift coverage even when I am not in the app.

#### Acceptance Criteria

1. WHEN a coverage request is created, THE Email_Service SHALL send an email to each User in the Recipient_Set
2. THE Recipient_Set for a "created" event SHALL include all users who have a valid email address, have Notification_Preference set to true, and are not the requester
3. THE email SHALL contain the requester's display name, the shift date, the shift type, and any note provided
4. THE email subject SHALL identify the message as a new coverage request notification

### Requirement 4: Email Notification on Coverage Request Claimed

**User Story:** As a requester, I want to receive an email when someone claims my coverage request, so that I know my shift is covered.

#### Acceptance Criteria

1. WHEN a coverage request is claimed, THE Email_Service SHALL send an email to the requester if the requester has a valid email address and Notification_Preference set to true
2. THE email SHALL contain the claimer's display name, the shift date, and the shift type
3. THE email subject SHALL identify the message as a coverage request claimed notification

### Requirement 5: AWS SES Integration

**User Story:** As an operator, I want the application to send emails through AWS SES, so that email delivery is reliable and scalable.

#### Acceptance Criteria

1. THE Email_Service SHALL use the boto3 SES client to send emails
2. THE Email_Service SHALL read the sender email address from the `SES_SENDER_EMAIL` environment variable
3. THE Email_Service SHALL read the AWS region from the `SES_AWS_REGION` environment variable, defaulting to `us-east-1`
4. IF the `SES_SENDER_EMAIL` environment variable is not set, THEN THE Email_Service SHALL log a warning and skip all email sending without raising errors
5. IF the SES_Client returns an error when sending an email, THEN THE Email_Service SHALL log the error and continue processing without interrupting the coverage request operation
6. THE `.env.example` file SHALL include `SES_SENDER_EMAIL` and `SES_AWS_REGION` with descriptive comments

### Requirement 6: Profile Update API

**User Story:** As a user, I want an API endpoint to update my email address and notification preference, so that I can manage my notification settings.

#### Acceptance Criteria

1. THE App SHALL provide a `PUT /api/auth/profile` endpoint that accepts JSON with optional `email` and `email_notifications_enabled` fields
2. WHEN a valid request is received, THE App SHALL update the authenticated user's email and Notification_Preference in the database
3. WHEN an unauthenticated user accesses the endpoint, THE App SHALL return HTTP status 401
4. THE `GET /api/auth/me` endpoint SHALL include the user's email address and Notification_Preference in the response

### Requirement 7: Asynchronous Email Sending

**User Story:** As a user, I want coverage request operations to respond quickly, so that email sending does not slow down the API.

#### Acceptance Criteria

1. THE Email_Service SHALL send emails in a background thread, separate from the HTTP request handling thread
2. WHEN a Coverage_Event triggers email notifications, THE App SHALL return the API response to the caller without waiting for email delivery to complete
3. IF the background email sending thread encounters an error, THEN THE Email_Service SHALL log the error without affecting the API response
