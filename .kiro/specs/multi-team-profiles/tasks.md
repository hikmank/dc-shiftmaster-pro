# Implementation Plan: Multi-Team Profiles

## Overview

This plan converts DC-ShiftMaster Pro from a single-team application into a multi-tenant system where multiple warehouse teams operate isolated dashboards from one instance. Implementation proceeds from database schema and migration, through backend services, to frontend components, wiring everything together with team-scoped middleware.

## Tasks

- [x] 1. Database schema and migration
  - [x] 1.1 Create team tables and add team_id foreign keys to existing tables
    - Add `team_profiles`, `team_members`, and `migrations_applied` tables to `DatabaseManager._create_tables()`
    - Add `team_id` column (FK to `team_profiles.id` with ON DELETE CASCADE) to `teammates`, `overrides`, `coverage_requests`, `shift_windows` tables via `_migrate()`
    - Add site_code UNIQUE constraint and role CHECK constraint (`role IN ('admin', 'member')`)
    - Add UNIQUE(team_id, user_id) constraint on `team_members`
    - _Requirements: 1.1, 1.4, 2.1, 3.1, 3.2, 3.3, 3.4_

  - [x] 1.2 Implement MigrationService in `dc_shiftmaster/migration.py`
    - Create idempotent migration script that creates ATL069 team profile
    - Assign all existing data rows (teammates, overrides, coverage_requests, shift_windows) to ATL069
    - Assign all existing users as ATL069 members with admin role
    - Use `migrations_applied` table to track which migrations have run (idempotency)
    - Wrap ALL operations in a single `BEGIN IMMEDIATE` transaction — if ANY step fails, execute `ROLLBACK` so no partial data remains
    - Raise `MigrationError` with details on rollback
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [x] 1.3 Write property test for migration atomicity
    - **Property 14: Migration atomicity**
    - Simulate failures at each step and verify the database remains in its original pre-migration state after rollback
    - **Validates: Requirements 7.6**

  - [x] 1.4 Write property test for migration idempotence
    - **Property 15: Migration idempotence**
    - Run migration twice and verify identical database state
    - **Validates: Requirements 7.7**

  - [x] 1.5 Write unit tests for migration
    - Test ATL069 team creation with all existing teammates, overrides, coverage requests, shift windows
    - Test re-run produces same state (idempotency)
    - Test rollback on simulated IO failure leaves DB unchanged
    - Test all users assigned as ATL069 members
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

- [x] 2. Checkpoint - Ensure migration tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Team profile CRUD and membership in DatabaseManager
  - [x] 3.1 Add team profile CRUD methods to DatabaseManager
    - `create_team(site_code, display_name, creator_user_id)` — validates site_code against `^[A-Z]{3}[0-9]{3}$`, creates team + admin membership + default shift windows (day: 06:00–18:30, night: 18:00–06:30)
    - Implement resilient shift initialization: if shift window INSERT fails after profile creation, allow creation to succeed and set `shift_init_status` to "pending"; retry on next `get_shift_windows()` call (lazy retry per Req 1.4)
    - `delete_team(team_id)` — cascading delete of all team data and memberships (relies on ON DELETE CASCADE)
    - `get_teams_for_user(user_id)` — returns all teams user belongs to with role and `joined_at`
    - `get_team_by_site_code(site_code)` — lookup by site code
    - Return descriptive validation errors for invalid site code format
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.3, 2.4_

  - [x] 3.2 Add team membership methods to DatabaseManager
    - `join_team(user_id, team_id)` — creates member record with `joined_at` timestamp; reject with `ALREADY_MEMBER` if membership exists
    - `remove_member(team_id, user_id, requesting_user_id)` — admin-only removal; reject non-admins with `PERMISSION_DENIED`; reject removal of non-members with `NOT_A_MEMBER` error (Req 6.4); prevent sole-admin self-removal with `SOLE_ADMIN` error
    - `is_team_member(user_id, team_id)` — boolean membership check
    - `get_team_members(team_id)` — list all members with roles
    - `get_user_role(user_id, team_id)` — returns 'admin' or 'member'
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4_

  - [x] 3.3 Refactor existing query methods to accept team_id and enforce active cross-team validation
    - Update `get_teammates()`, `add_teammate()`, `update_teammate()`, `delete_teammate()` to require `team_id` parameter
    - Update `get_overrides()`, `set_override()`, `remove_override()` to require `team_id` parameter
    - Update `get_coverage_requests()`, `create_coverage_request()` to require `team_id` parameter
    - Update `get_shift_windows()`, `update_shift_window()` to require `team_id` parameter
    - Implement `validate_resource_ownership(table, resource_id, team_id)` — for any row-level operation by ID, verify `team_id` matches; raise `CrossTeamAccessError` if resource belongs to a different team (active rejection, not silent filtering per Req 3.1)
    - Implement lazy shift window initialization in `get_shift_windows(team_id)` — if no shift windows exist for the team, create defaults (retry mechanism for Req 1.4)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 1.4_

  - [x] 3.4 Write property test for site code validation
    - **Property 1: Site code validation accepts only valid codes**
    - Generate random strings and verify acceptance iff matching `^[A-Z]{3}[0-9]{3}$`
    - **Validates: Requirements 1.3, 1.5**

  - [x] 3.5 Write property test for team creation with resilient shift initialization
    - **Property 2: Team creation assigns creator as admin with resilient shift initialization**
    - Verify creator always gets admin role; verify shift windows are (day, night) on success; simulate shift init failure and verify profile still exists and shifts initialize on next access
    - **Validates: Requirements 1.1, 1.4**

  - [x] 3.6 Write property test for site code uniqueness
    - **Property 3: Site code uniqueness**
    - Create a team then attempt duplicate creation — verify rejection
    - **Validates: Requirements 1.2**

  - [x] 3.7 Write property test for team deletion cascade
    - **Property 4: Team deletion cascades all associated data but preserves users**
    - Create team with data, delete team, verify all associated data removed but user accounts remain
    - **Validates: Requirements 2.1, 2.3, 2.4**

  - [x] 3.8 Write property test for data isolation with active cross-team rejection
    - **Property 6: Data isolation with active cross-team rejection**
    - Create two teams with data; query from team A context returns only team A data; attempt to access team B resource by ID from team A context raises `CrossTeamAccessError`
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

  - [x] 3.9 Write property test for join and duplicate join
    - **Property 9: Join creates membership; duplicate join is rejected**
    - Join produces membership with timestamp; second join raises ALREADY_MEMBER
    - **Validates: Requirements 5.1, 5.2, 5.4**

  - [x] 3.10 Write property test for multi-team membership
    - **Property 10: Multi-team membership**
    - A single user can hold simultaneous membership in multiple teams
    - **Validates: Requirements 5.3**

  - [x] 3.11 Write property test for member removal
    - **Property 11: Member removal revokes access**
    - After removal, member no longer in team list and team no longer in user's team list
    - **Validates: Requirements 6.1, 6.5**

  - [x] 3.12 Write property test for non-member removal rejection
    - **Property 12: Non-member removal rejection**
    - Attempting to remove a user who is NOT a member returns `NOT_A_MEMBER` error
    - **Validates: Requirements 6.4**

  - [x] 3.13 Write property test for sole admin self-removal prevention
    - **Property 13: Sole admin self-removal prevention**
    - Sole admin cannot remove themselves; if two admins exist, an admin can remove themselves
    - **Validates: Requirements 6.3**

- [x] 4. Checkpoint - Ensure database layer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Team context middleware and profile routes
  - [x] 5.1 Implement team context middleware in `dc_shiftmaster_html/team_middleware.py`
    - Create `before_request` hook that reads `active_team_id` from session
    - Validate user belongs to active team via `is_team_member()`
    - Attach `g.team_id` to request context
    - Return 403 with `NO_TEAM` code if no team context on team-scoped endpoints
    - Return 403 with `INVALID_TEAM` code, clear `active_team_id` from session, and redirect to landing if membership invalid
    - Exempt `/api/auth/`, `/api/teams`, `/login`, `/static/`, `/health`, `/api/public/` prefixes
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 5.2 Implement ProfileService routes in `dc_shiftmaster_html/routes_profile.py`
    - `GET /api/teams` — list user's teams with site_code, display_name, role
    - `POST /api/teams` — create team (validates site_code format, rejects duplicates, creates admin membership + default shift windows with resilient init)
    - `DELETE /api/teams/<team_id>` — delete team (admin only, rejects non-admins with PERMISSION_DENIED)
    - `POST /api/teams/<team_id>/join` — join by site code (rejects duplicate membership with ALREADY_MEMBER)
    - `GET /api/teams/<team_id>/members` — list members with roles
    - `DELETE /api/teams/<team_id>/members/<user_id>` — remove member (admin only, sole-admin check, rejects non-members with NOT_A_MEMBER error per Req 6.4)
    - `POST /api/teams/select` — set active team in session, update `selected_at` timestamp
    - Register blueprint in app factory
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 4.2, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4_

  - [x] 5.3 Update existing routes to use `g.team_id` from middleware and enforce active isolation
    - Update teammate routes to pass `g.team_id` to DatabaseManager methods
    - Update override routes to pass `g.team_id`
    - Update coverage request routes to pass `g.team_id`
    - Update settings/shift window routes to pass `g.team_id`
    - Ensure all row-level operations (GET by ID, UPDATE, DELETE) call `validate_resource_ownership()` and return 403 `CROSS_TEAM_ACCESS` on mismatch
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 5.4 Write property test for admin-only operations
    - **Property 5: Admin-only operations reject non-admin users**
    - Non-admin users cannot delete teams or remove members
    - **Validates: Requirements 2.2, 6.2**

  - [x] 5.5 Write property test for team selection session context
    - **Property 7: Team selection updates session context**
    - Selecting a team stores `active_team_id` in session; subsequent requests carry that context
    - **Validates: Requirements 4.2, 8.1**

  - [x] 5.6 Write property test for team-scoped endpoint rejection
    - **Property 8: Team-scoped endpoints reject missing or invalid team context**
    - Missing `active_team_id` returns NO_TEAM; invalid team clears session and returns INVALID_TEAM
    - **Validates: Requirements 8.2, 8.3, 8.4**

- [x] 6. Checkpoint - Ensure middleware and route tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. JSON import endpoint
  - [x] 7.1 Implement JSON import handler in `routes_profile.py`
    - `POST /api/teams/import-json` — accepts multipart form with JSON file
    - Parse JSON array, validate each entry against teammate schema
    - Skip entries with missing `name` or invalid `shift_type`
    - Skip entries with `shift_type: "Custom"` and empty/invalid `custom_days`
    - Skip entries with non-Custom `shift_type` that include a `custom_days` field — report as "Invalid field combination: custom_days not allowed for non-Custom shift_type" (Req 9.7)
    - Skip duplicate names already existing in the team — report as duplicates
    - Insert valid entries as teammates for active team
    - Return summary with `imported_count`, `skipped_rows` (with index and reason), `duplicate_count`
    - Enforce invariant: `imported_count + len(skipped_rows) + duplicate_count == total input entries`
    - Support round-trip compatibility with existing schedule export format
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9_

  - [x] 7.2 Write property test for JSON import validation
    - **Property 16: JSON import creates valid entries and filters invalid ones**
    - Generate mixed valid/invalid entries and verify only valid ones are imported; invalid ones reported in skipped_rows
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.5, 9.6, 9.7**

  - [x] 7.3 Write property test for non-Custom shift_type with custom_days rejection
    - **Property 17: Non-Custom shift_type with custom_days is rejected**
    - Generate entries with non-Custom shift_type + custom_days field and verify they are all rejected with appropriate reason
    - **Validates: Requirements 9.7**

  - [x] 7.4 Write property test for JSON import deduplication
    - **Property 18: JSON import deduplication**
    - Pre-populate team with teammates, import JSON with overlapping names, verify duplicates skipped and new names imported
    - **Validates: Requirements 9.4**

  - [x] 7.5 Write property test for JSON export/import round-trip
    - **Property 19: JSON export/import round-trip**
    - Export teammates as JSON, import into fresh team, verify identical records
    - **Validates: Requirements 9.8**

  - [x] 7.6 Write property test for import summary counts invariant
    - **Property 20: Import summary counts invariant**
    - For any import, verify `imported_count + len(skipped_rows) + duplicate_count == total entries`
    - **Validates: Requirements 9.9**

- [x] 8. Checkpoint - Ensure JSON import tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Frontend landing page and team selection
  - [x] 9.1 Create Landing Page view in `dc_shiftmaster_html/static/js/landing.js`
    - Render list of user's teams (site code + display name)
    - Create Team form with site code validation (3 uppercase letters + 3 digits) and display name fields
    - Join Team form with site code input
    - Wire click handlers to call `/api/teams` and `/api/teams/select`
    - Redirect to dashboard on successful team selection
    - Implement fallback behavior (Req 4.1): if landing page fetch fails, automatically select the user's most recently active team (from `lastActiveTeamId` in local storage); if no previous team exists, show error state with retry button
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 9.2 Update state manager in `dc_shiftmaster_html/static/js/state.js`
    - Add `getActiveTeam()` / `setActiveTeam(team)` / `clearActiveTeam()` functions
    - Add `getLastActiveTeam()` — retrieves most recently active team ID from local storage for fallback
    - On team selection, store `lastActiveTeamId` in local storage for fallback recovery
    - On 403 NO_TEAM or INVALID_TEAM response, clear team state and redirect to landing
    - _Requirements: 4.1, 4.2, 8.4_

  - [x] 9.3 Update header and router to show active team site code
    - Display active team's site code in the header-info element alongside the year
    - Update SPA router to show landing page when no team is active
    - _Requirements: 4.5_

  - [x] 9.4 Write frontend unit tests for landing page
    - Test team list rendering
    - Test create team form validates site code format (rejects invalid formats)
    - Test join team form submission
    - Test team selection triggers view switch to dashboard
    - Test fallback to last active team when fetch fails (Req 4.1)
    - _Requirements: 4.1, 4.3, 4.4_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate the 20 universal correctness properties defined in the design
- Unit tests validate specific examples and edge cases
- The migration script (1.2) should be run once during deployment; ensure it logs progress
- All property-based tests use Python `hypothesis` library in `tests/test_multi_team_props.py`
- Frontend tests use Jest in `dc_shiftmaster_html/static/js/__tests__/landing.test.js`
- Key new behaviors covered: resilient shift init with lazy retry (3.1, 3.3, 3.5), active cross-team validation with CrossTeamAccessError (3.3, 3.8, 5.3), landing page fallback (9.1), non-member removal rejection (3.2, 3.12, 5.2), atomic migration rollback (1.2, 1.3), non-Custom+custom_days rejection (7.1, 7.3)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "1.4", "1.5"] },
    { "id": 3, "tasks": ["3.1", "3.2"] },
    { "id": 4, "tasks": ["3.3"] },
    { "id": 5, "tasks": ["3.4", "3.5", "3.6", "3.7", "3.8", "3.9", "3.10", "3.11", "3.12", "3.13"] },
    { "id": 6, "tasks": ["5.1", "5.2"] },
    { "id": 7, "tasks": ["5.3"] },
    { "id": 8, "tasks": ["5.4", "5.5", "5.6"] },
    { "id": 9, "tasks": ["7.1"] },
    { "id": 10, "tasks": ["7.2", "7.3", "7.4", "7.5", "7.6"] },
    { "id": 11, "tasks": ["9.1", "9.2"] },
    { "id": 12, "tasks": ["9.3", "9.4"] }
  ]
}
```
