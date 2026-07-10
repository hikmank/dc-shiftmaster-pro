# Implementation Plan: Email Notifications

## Overview

Add email notifications to DC-ShiftMaster Pro so users receive coverage event alerts via AWS SES when offline. Implementation follows bottom-up ordering: database/model changes first, then the email service module, then route integration, then frontend profile UI, then tests.

## Tasks

- [x] 1. Extend User model and database schema
  - [x] 1.1 Add `email` and `email_notifications_enabled` fields to the `User` dataclass in `dc_shiftmaster/models.py`
    - Add `email: str = ""` and `email_notifications_enabled: bool = False` with defaults
    - _Requirements: 1.1, 2.1_

  - [x] 1.2 Add database migration for new columns in `dc_shiftmaster/database.py`
    - In `_migrate()`, add `ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''` and `ALTER TABLE users ADD COLUMN email_notifications_enabled INTEGER NOT NULL DEFAULT 0` if columns don't exist
    - _Requirements: 1.1, 2.1_

  - [x] 1.3 Update all `DatabaseManager` user query methods to include the new columns
    - Update `get_user_by_id`, `get_user_by_username`, `get_all_users`, and `create_user` to read/write `email` and `email_notifications_enabled`
    - _Requirements: 1.1, 1.2, 2.1_

  - [x] 1.4 Add `update_user_profile` method to `DatabaseManager`
    - Accepts `user_id`, `email`, and `email_notifications_enabled`; updates the corresponding row in the `users` table
    - _Requirements: 6.2_

  - [x] 1.5 Add `get_notification_recipients` method to `DatabaseManager`
    - Returns users where `email != ''` and `email_notifications_enabled = 1`, with optional `exclude_user_id` parameter
    - _Requirements: 3.2, 4.1_

- [x] 2. Checkpoint - Verify model and database changes
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Create the email service module
  - [x] 3.1 Create `dc_shiftmaster_html/email_service.py` with `validate_email` function
    - Return `True` if the string contains exactly one `@` with non-empty local and domain parts
    - _Requirements: 1.4_

  - [x] 3.2 Implement `_build_email_body` in `email_service.py`
    - Return `(subject, body)` tuple for "created" and "claimed" event types
    - Created: subject includes requester display name; body includes requester name, date, shift type, note
    - Claimed: subject indicates claim; body includes claimer name, date, shift type
    - _Requirements: 3.3, 3.4, 4.2, 4.3_

  - [x] 3.3 Implement `_send_ses_email` in `email_service.py`
    - Read `SES_SENDER_EMAIL` and `SES_AWS_REGION` from environment variables
    - Use boto3 SES client `send_email` to deliver the message
    - Log errors without raising exceptions
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

  - [x] 3.4 Implement `send_coverage_email` in `email_service.py`
    - Determine recipient set based on event type using `get_notification_recipients`
    - For "created": all opted-in users except the requester
    - For "claimed": only the requester if opted in
    - Dispatch `_send_ses_email` calls in background daemon threads
    - If `SES_SENDER_EMAIL` is not set, log warning and return immediately
    - _Requirements: 3.1, 3.2, 4.1, 5.4, 7.1, 7.2_

  - [x] 3.5 Write property test for email validation (Property 2)
    - **Property 2: Email validation**
    - Generate random strings, assert `validate_email` returns `True` iff exactly one `@` with non-empty local and domain parts
    - **Validates: Requirements 1.4**

  - [x] 3.6 Write property test for email body completeness (Property 6)
    - **Property 6: Email body completeness**
    - Generate random coverage request data, assert all required fields appear in composed email
    - **Validates: Requirements 3.3, 4.2**

  - [x] 3.7 Write property test for missing sender config (Property 7)
    - **Property 7: Missing sender config disables email**
    - Unset `SES_SENDER_EMAIL`, call `send_coverage_email`, assert no SES calls and no exceptions
    - **Validates: Requirements 5.4**

  - [x] 3.8 Write property test for SES error handling (Property 8)
    - **Property 8: SES errors do not propagate**
    - Mock SES to raise exceptions, call `send_coverage_email`, assert no exception propagates
    - **Validates: Requirements 5.5, 7.3**

- [x] 4. Checkpoint - Verify email service module
  - Ensure all tests pass, ask the user if questions arise.

- [-] 5. Integrate email notifications into routes
  - [x] 5.1 Add `PUT /api/auth/profile` endpoint to `dc_shiftmaster_html/routes_auth.py`
    - Accept JSON with optional `email` and `email_notifications_enabled` fields
    - Validate email format using `validate_email` if provided
    - Reject enabling notifications when email is empty
    - Return 401 for unauthenticated users
    - Return updated user info on success
    - _Requirements: 6.1, 6.2, 6.3, 1.3, 1.4, 2.2, 2.3_

  - [x] 5.2 Extend `_user_info` helper and `GET /api/auth/me` in `routes_auth.py`
    - Include `email` and `email_notifications_enabled` in the returned user dict
    - _Requirements: 6.4, 2.4_

  - [x] 5.3 Update registration endpoint to accept optional email field
    - Pass email through to `create_user` if provided, validate format
    - _Requirements: 1.2_

  - [x] 5.4 Add `send_coverage_email` calls to `routes_coverage.py`
    - Call `send_coverage_email("created", ...)` in `create_coverage` after `broadcast_coverage_event`
    - Call `send_coverage_email("claimed", ...)` in `claim_coverage` after `broadcast_coverage_event`
    - Wrap each call in try/except to prevent email failures from affecting the API response
    - _Requirements: 3.1, 4.1, 7.2, 7.3_

  - [x] 5.5 Write property test for profile update round-trip (Property 1)
    - **Property 1: Profile update round-trip**
    - Generate random email strings and booleans, write via `update_user_profile`, read back, assert equality
    - **Validates: Requirements 1.1, 1.3, 2.2, 6.2**

  - [x] 5.6 Write property test for enabling notifications requires email (Property 3)
    - **Property 3: Enabling notifications requires an email address**
    - For users with empty email, attempt to enable notifications via profile endpoint, assert error and preference unchanged
    - **Validates: Requirements 2.3**

  - [x] 5.7 Write property test for created event recipient set (Property 4)
    - **Property 4: Created event recipient set**
    - Generate random user sets with varying email/preference states, assert recipient set matches filter criteria
    - **Validates: Requirements 3.1, 3.2**

  - [x] 5.8 Write property test for claimed event recipient (Property 5)
    - **Property 5: Claimed event recipient**
    - Generate random requester email/preference states, assert only requester receives email when eligible
    - **Validates: Requirements 4.1**

- [x] 6. Update environment configuration
  - [x] 6.1 Add `SES_SENDER_EMAIL` and `SES_AWS_REGION` to `.env.example`
    - Include descriptive comments explaining each variable
    - _Requirements: 5.6_

- [x] 7. Checkpoint - Verify full integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Add unit tests for email notification feature
  - [x] 8.1 Write unit tests for `validate_email` with known valid/invalid inputs
    - Test empty string, missing `@`, multiple `@`, valid format, whitespace-only
    - _Requirements: 1.4_

  - [x] 8.2 Write unit tests for profile update endpoint
    - Test success case, validation errors (bad email, enable without email), 401 for unauthenticated
    - _Requirements: 6.1, 6.2, 6.3, 2.3_

  - [x] 8.3 Write unit tests for `_build_email_body` with specific event types
    - Test subject line format and body content for "created" and "claimed" events
    - _Requirements: 3.3, 3.4, 4.2, 4.3_

  - [x] 8.4 Write unit tests for `GET /api/auth/me` includes new fields
    - Assert response contains `email` and `email_notifications_enabled`
    - _Requirements: 6.4, 2.4_

  - [x] 8.5 Write unit tests for database migration
    - Verify `email` and `email_notifications_enabled` columns exist after migration
    - _Requirements: 1.1, 2.1_

  - [x] 8.6 Write unit tests for `get_notification_recipients`
    - Test filtering by email presence, notification preference, and user exclusion
    - _Requirements: 3.2, 4.1_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests complement property tests by covering specific examples and edge cases
- The design uses Python throughout — all code examples target Python/Flask/boto3
