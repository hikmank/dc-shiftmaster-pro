# Requirements Document

## Introduction

Multi-Team Profiles adds multi-tenancy to DC-ShiftMaster Pro so that multiple warehouse teams (identified by site codes such as ATL068, ATL069, ATL070) can each operate their own isolated dashboard. Each team profile owns its own teammates, schedules, overrides, coverage requests, and settings. Teams can create and delete their own profiles. The existing ATL069 data is preserved through migration into the new schema.

## Glossary

- **Team_Profile**: A logical tenant representing a single warehouse team, identified by a unique site code (e.g., ATL069). Owns all associated data.
- **Site_Code**: An alphanumeric identifier for a team (e.g., ATL068, ATL069). Follows the pattern of 3 uppercase letters followed by 3 digits.
- **Team_Admin**: A user who created a Team_Profile or has been granted admin privileges for that team. Can manage team settings and delete the profile.
- **Team_Member**: A user who has joined a Team_Profile and can view and interact with that team's dashboard.
- **Profile_Service**: The backend service responsible for creating, deleting, and listing Team_Profiles.
- **Data_Isolation_Layer**: The mechanism that ensures queries and mutations for one team do not read or write data belonging to another team.
- **Migration_Service**: The one-time process that converts the existing single-team database into the multi-tenant schema, preserving all current ATL069 data.
- **Landing_Page**: The initial page shown to authenticated users where they can select, create, or join a team.

## Requirements

### Requirement 1: Team Profile Creation

**User Story:** As a team lead, I want to create a new team profile using my site code, so that my team has its own isolated workspace.

#### Acceptance Criteria

1. WHEN a user submits a valid Site_Code and team display name, THE Profile_Service SHALL create a new Team_Profile and assign the creating user as Team_Admin.
2. WHEN a user submits a Site_Code that already exists, THE Profile_Service SHALL reject the request and return an error indicating the code is already in use.
3. THE Profile_Service SHALL validate that the Site_Code matches the pattern of 3 uppercase letters followed by 3 digits (e.g., ATL069).
4. WHEN a Team_Profile is created, THE Profile_Service SHALL initialize default shift windows (day: 06:00–18:30, night: 18:00–06:30) for that team. IF shift initialization fails after the profile is already created, THEN THE Profile_Service SHALL allow the profile creation to succeed and retry shift initialization on next access.
5. IF the Site_Code contains invalid characters or does not match the required format, THEN THE Profile_Service SHALL return a descriptive validation error.

### Requirement 2: Team Profile Deletion

**User Story:** As a team admin, I want to delete my team's profile, so that we can remove unused teams and free resources.

#### Acceptance Criteria

1. WHEN a Team_Admin requests deletion of a Team_Profile, THE Profile_Service SHALL remove the Team_Profile and all associated data (teammates, overrides, coverage requests, settings, users membership).
2. IF a non-admin user attempts to delete a Team_Profile, THEN THE Profile_Service SHALL reject the request and return a permission error.
3. WHEN a Team_Profile is deleted, THE Profile_Service SHALL remove all team membership associations for users in that team.
4. WHEN a Team_Profile is deleted, THE Profile_Service SHALL preserve the user accounts themselves so they can join or create other teams.

### Requirement 3: Data Isolation

**User Story:** As a team member, I want my team's data to be completely separate from other teams, so that we don't accidentally see or modify another team's schedules.

#### Acceptance Criteria

1. THE Data_Isolation_Layer SHALL scope all teammate queries to the active Team_Profile of the requesting user and SHALL actively validate and reject any query that would access cross-team data.
2. THE Data_Isolation_Layer SHALL scope all override queries to the active Team_Profile of the requesting user.
3. THE Data_Isolation_Layer SHALL scope all coverage request queries to the active Team_Profile of the requesting user.
4. THE Data_Isolation_Layer SHALL scope all settings (shift windows) queries to the active Team_Profile of the requesting user.
5. IF a request references data belonging to a different Team_Profile, THEN THE Data_Isolation_Layer SHALL reject the request and return an authorization error.

### Requirement 4: Team Selection and Landing Page

**User Story:** As a user who belongs to multiple teams, I want to select which team I'm working with, so that I see the correct dashboard.

#### Acceptance Criteria

1. WHEN an authenticated user has no active team selected, THE Landing_Page SHALL display a list of teams the user belongs to plus options to create or join a team. IF the display fails to load, THEN THE Landing_Page SHALL fall back to automatically selecting the user's most recently active team.
2. WHEN a user selects a team from the Landing_Page, THE Profile_Service SHALL set that team as the user's active Team_Profile for the session.
3. WHEN a user selects a team, THE application SHALL load the dashboard with that team's data (teammates, schedules, overrides, coverage requests).
4. THE Landing_Page SHALL display each team's Site_Code and display name.
5. WHILE a user has an active team selected, THE application header SHALL display the active team's Site_Code.

### Requirement 5: Team Membership

**User Story:** As a user, I want to join an existing team, so that I can view and contribute to that team's schedules.

#### Acceptance Criteria

1. WHEN a user provides a valid Site_Code for an existing Team_Profile, THE Profile_Service SHALL add the user as a Team_Member of that team.
2. WHEN a user attempts to join a team they already belong to, THE Profile_Service SHALL reject the request and return an error indicating existing membership.
3. THE Profile_Service SHALL allow a single user to be a member of multiple Team_Profiles.
4. WHEN a user joins a team, THE Profile_Service SHALL record their membership with a joined timestamp.

### Requirement 6: Team Member Management

**User Story:** As a team admin, I want to manage who is on my team, so that I can remove members who no longer work at our site.

#### Acceptance Criteria

1. WHEN a Team_Admin requests removal of a Team_Member, THE Profile_Service SHALL revoke that user's membership in the Team_Profile.
2. IF a non-admin user attempts to remove a Team_Member, THEN THE Profile_Service SHALL reject the request with a permission error.
3. THE Profile_Service SHALL prevent a Team_Admin from removing themselves if they are the sole admin (the team must have at least one admin).
4. IF a Team_Admin attempts to remove a user who is not a member of the team, THEN THE Profile_Service SHALL reject the request and return an error indicating the user is not a team member.
5. WHEN a Team_Member is removed, THE application SHALL no longer display that team on the removed user's Landing_Page.

### Requirement 7: Existing Data Migration

**User Story:** As the existing ATL069 team, I want my current data preserved when multi-tenancy is added, so that we don't lose our schedules and configuration.

#### Acceptance Criteria

1. WHEN the Migration_Service runs, THE Migration_Service SHALL create a Team_Profile with Site_Code "ATL069" containing all existing teammates.
2. WHEN the Migration_Service runs, THE Migration_Service SHALL associate all existing overrides with the ATL069 Team_Profile.
3. WHEN the Migration_Service runs, THE Migration_Service SHALL associate all existing coverage requests with the ATL069 Team_Profile.
4. WHEN the Migration_Service runs, THE Migration_Service SHALL associate all existing shift window settings with the ATL069 Team_Profile.
5. WHEN the Migration_Service runs, THE Migration_Service SHALL assign all existing user accounts as members of the ATL069 Team_Profile.
6. THE Migration_Service SHALL execute as an atomic operation — IF any step of the migration fails, THEN THE Migration_Service SHALL roll back all changes so that no partial data remains.
7. THE Migration_Service SHALL execute as an idempotent operation (running it multiple times produces the same result as running it once).

### Requirement 8: Team-Scoped Authentication Context

**User Story:** As the system, I need each API request to carry team context, so that the backend can enforce data isolation without requiring team selection on every call.

#### Acceptance Criteria

1. WHILE a user has an active team selected, THE application SHALL include the active team identifier in the user session.
2. WHEN an API request is received without a team context and the endpoint requires one, THE application SHALL return an error directing the user to select a team.
3. THE Profile_Service SHALL validate that the session's team identifier matches a team the user belongs to on each request.
4. IF the session's team identifier references a team the user no longer belongs to, THEN THE application SHALL clear the team context and redirect to the Landing_Page.

### Requirement 9: JSON Schedule Import

**User Story:** As a team admin, I want to import teammates and schedule data from a JSON file, so that I can quickly bootstrap my team's roster without manual data entry.

#### Acceptance Criteria

1. WHEN a Team_Admin uploads a JSON file via the import endpoint, THE application SHALL parse the file and create teammate records in the active Team_Profile.
2. THE application SHALL accept JSON files containing an array of teammate objects with fields: name, shift_type, and optionally custom_start and custom_days.
3. WHEN the JSON file contains invalid entries (missing name, invalid shift_type), THE application SHALL skip those entries and report them in a skipped_rows response list.
4. WHEN the JSON file contains duplicate teammate names that already exist in the team, THE application SHALL skip those entries and report them as duplicates.
5. THE application SHALL validate that shift_type values are one of the valid types (FHD, FHN, BHD, BHN, Custom) for each entry.
6. IF shift_type is "Custom" and custom_days is empty or contains invalid day values, THEN THE application SHALL skip that entry and report it in skipped_rows.
7. IF an entry has a non-Custom shift_type and includes a custom_days field, THEN THE application SHALL reject that entry and report it in skipped_rows as having an invalid field combination.
8. THE application SHALL support importing JSON files exported from the existing schedule API endpoint (round-trip compatibility).
8. WHEN a JSON import completes successfully, THE application SHALL return a summary containing counts of imported, skipped, and duplicate entries.
