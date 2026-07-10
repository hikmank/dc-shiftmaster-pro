# Implementation Plan: Coverage Requests & User Accounts

## Overview

Bottom-up implementation adding user accounts, coverage request workflow, and responsive mobile/tablet support to DC-ShiftMaster Pro. Each task builds incrementally — data layer first, then backend routes, then frontend modules, then responsive CSS. All new backend code is Python/Flask; all new frontend code is vanilla JavaScript.

## Tasks

- [x] 1. Data layer — models and database schema
  - [x] 1.1 Add User and CoverageRequest dataclasses to `dc_shiftmaster/models.py`
    - Add `User` dataclass with fields: `id`, `username`, `password_hash`, `display_name`, `teammate_name`, `created_at`
    - Add `CoverageRequest` dataclass with fields: `id`, `requester_id`, `date`, `shift_type`, `note`, `status`, `claimer_id`, `created_at`, `claimed_at`
    - _References: Design — Data Models section_

  - [x] 1.2 Add `users` and `coverage_requests` tables to `dc_shiftmaster/database.py`
    - Add `CREATE TABLE IF NOT EXISTS users` and `CREATE TABLE IF NOT EXISTS coverage_requests` in `_create_tables()`
    - Include `CHECK` constraints for `shift_type IN ('day','night')` and `status IN ('open','claimed','cancelled')`
    - Include `REFERENCES users(id)` foreign key on `requester_id` and `claimer_id`
    - _References: Design — New SQLite Tables section_

  - [x] 1.3 Implement user CRUD methods on `DatabaseManager`
    - `create_user(username, password_hash, display_name, teammate_name) -> int` — raises `ValueError` on empty/duplicate username
    - `get_user_by_username(username) -> User | None`
    - `get_user_by_id(user_id) -> User | None`
    - `get_all_users() -> list[User]`
    - _References: Design — DatabaseManager Extensions (User methods)_

  - [x] 1.4 Implement coverage request CRUD methods on `DatabaseManager`
    - `create_coverage_request(requester_id, date, shift_type, note) -> int` — raises `ValueError` on duplicate date/shift/requester
    - `get_coverage_requests(status=None) -> list[CoverageRequest]`
    - `get_coverage_requests_for_user(user_id) -> list[CoverageRequest]`
    - `claim_coverage_request(request_id, claimer_id)` — sets status to `'claimed'`, calls `set_override()` to link claimer to shift
    - `unclaim_coverage_request(request_id)` — reverts to `'open'`, removes associated override
    - `cancel_coverage_request(request_id)` — sets status to `'cancelled'`, removes override if claimed
    - _References: Design — DatabaseManager Extensions (Coverage Request methods)_

  - [x] 1.5 Write unit tests for User and CoverageRequest database methods
    - Test `create_user` with valid data, duplicate username, empty username
    - Test `get_user_by_username` and `get_user_by_id` for existing and missing users
    - Test `create_coverage_request`, duplicate prevention, status filtering
    - Test `claim_coverage_request` creates override, `unclaim` removes it, `cancel` handles both states
    - _References: Design — DatabaseManager Extensions_

- [x] 2. Checkpoint — Data layer
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Auth backend — `routes_auth.py` blueprint
  - [x] 3.1 Create `dc_shiftmaster_html/routes_auth.py` with auth blueprint
    - `POST /api/auth/register` — validate username/password/display_name, hash password with `werkzeug.security.generate_password_hash`, call `create_user()`, set `session["user_id"]`, return user info JSON
    - `POST /api/auth/login` — look up user by username, verify with `check_password_hash`, set `session["user_id"]`, return user info JSON
    - `POST /api/auth/logout` — clear session, return 204
    - `GET /api/auth/me` — return current user info from `session["user_id"]`, or 401
    - _References: Design — Auth Blueprint section_

  - [x] 3.2 Write unit tests for auth routes
    - Test register with valid data, duplicate username, missing fields
    - Test login with correct/incorrect password, non-existent user
    - Test `/api/auth/me` returns user when logged in, 401 when not
    - Test logout clears session
    - _References: Design — Auth Blueprint section_

- [x] 4. Coverage backend — `routes_coverage.py` blueprint
  - [x] 4.1 Create `dc_shiftmaster_html/routes_coverage.py` with coverage blueprint
    - `GET /api/coverage` — list coverage requests, optional `?status=open` query param
    - `POST /api/coverage` — create new coverage request (requires logged-in user)
    - `POST /api/coverage/<id>/claim` — claim a request (logged-in user becomes claimer)
    - `POST /api/coverage/<id>/unclaim` — revert a claimed request back to open
    - `POST /api/coverage/<id>/cancel` — cancel a request (only requester can cancel)
    - `GET /api/coverage/my-requests` — get current user's posted requests
    - `GET /api/coverage/my-shifts` — get current user's upcoming shifts (filter schedule by `teammate_name`)
    - _References: Design — Coverage Blueprint section_

  - [x] 4.2 Write unit tests for coverage routes
    - Test create, claim, unclaim, cancel flows
    - Test authorization (only requester can cancel, can't claim own request)
    - Test status filtering and my-requests endpoint
    - _References: Design — Coverage Blueprint section_

- [x] 5. Server modifications — register blueprints and update auth gate
  - [x] 5.1 Update `dc_shiftmaster_html/server.py`
    - Import and register `auth_bp` and `coverage_bp` blueprints
    - Update `require_login` to check `session.get("user_id")` instead of `session.get("authenticated")`
    - Allow `/api/auth/login` and `/api/auth/register` paths without authentication
    - Replace the shared-password login page with a redirect to the new login/register SPA view
    - Keep backward compatibility: if `session["authenticated"]` exists (legacy), still allow access
    - _References: Design — Server Modifications section_

- [x] 6. Checkpoint — Backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Frontend auth — login/register pages and `auth.js`
  - [x] 7.1 Create `dc_shiftmaster_html/static/js/auth.js`
    - Render login form (username + password) and register form (username + password + display name + optional teammate link)
    - On successful login/register, store user info in `AppState`, call `Router.show('dashboard')`
    - Show inline validation errors from API responses
    - Toggle between login and register forms with a link
    - _References: Design — Frontend Modules (auth.js)_

  - [x] 7.2 Add auth API functions to `dc_shiftmaster_html/static/js/api.js`
    - `API.register(data)` — POST `/api/auth/register`
    - `API.login(data)` — POST `/api/auth/login`
    - `API.logout()` — POST `/api/auth/logout`
    - `API.getCurrentUser()` — GET `/api/auth/me`
    - _References: Design — Auth Blueprint endpoints_

  - [x] 7.3 Update `dc_shiftmaster_html/static/index.html` for auth view
    - Add `<section id="login-view" class="view" hidden>` with login/register container
    - Add `<script src="/static/js/auth.js"></script>` before router script
    - Update header logout link to call `API.logout()` then redirect, instead of `/logout`
    - _References: Design — Module Structure_

- [x] 8. Frontend coverage — coverage board and `coverage.js`
  - [x] 8.1 Create `dc_shiftmaster_html/static/js/coverage.js`
    - Render coverage request board: list of open requests with date, shift type, requester name, note
    - "Request Coverage" form: date picker, shift type select, optional note textarea
    - Claim/unclaim buttons on each request card (hide claim on own requests)
    - Visual status indicators: open (blue), claimed (green), cancelled (grey)
    - _References: Design — Frontend Modules (coverage.js)_

  - [x] 8.2 Add coverage API functions to `dc_shiftmaster_html/static/js/api.js`
    - `API.getCoverageRequests(status)` — GET `/api/coverage?status=...`
    - `API.createCoverageRequest(data)` — POST `/api/coverage`
    - `API.claimCoverage(id)` — POST `/api/coverage/{id}/claim`
    - `API.unclaimCoverage(id)` — POST `/api/coverage/{id}/unclaim`
    - `API.cancelCoverage(id)` — POST `/api/coverage/{id}/cancel`
    - `API.getMyCoverageRequests()` — GET `/api/coverage/my-requests`
    - `API.getMyShifts()` — GET `/api/coverage/my-shifts`
    - _References: Design — Coverage Blueprint endpoints_

  - [x] 8.3 Update `dc_shiftmaster_html/static/index.html` for coverage view
    - Add `<section id="coverage-view" class="view" hidden>` with coverage board container
    - Add nav item: `<li class="nav-item" data-view="coverage">` with coverage icon and label
    - Add `<script src="/static/js/coverage.js"></script>`
    - _References: Design — Module Structure_

- [x] 9. Frontend personal dashboard — `personal-dashboard.js`
  - [x] 9.1 Create `dc_shiftmaster_html/static/js/personal-dashboard.js`
    - Show logged-in user's upcoming shifts (filtered from schedule by `teammate_name`)
    - Show user's posted coverage requests with status
    - Show requests the user has claimed
    - _References: Design — Frontend Modules (personal-dashboard.js)_

  - [x] 9.2 Update `dc_shiftmaster_html/static/index.html` for personal dashboard view
    - Add `<section id="my-shifts-view" class="view" hidden>` with personal dashboard container
    - Add nav item: `<li class="nav-item" data-view="my-shifts">` with user icon and label
    - Add `<script src="/static/js/personal-dashboard.js"></script>`
    - _References: Design — Module Structure_

- [x] 10. Update router — wire new views into `router.js`
  - Add `'login'`, `'coverage'`, `'my-shifts'` to the `views` array
  - Add loader functions: `login` → `loadLogin()`, `coverage` → `loadCoverage()`, `my-shifts` → `loadPersonalDashboard()`
  - On init, check `API.getCurrentUser()` — if not authenticated, show login view instead of dashboard
  - _References: Design — Module Structure (router.js)_

- [x] 11. Checkpoint — Frontend features complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Mobile/tablet responsive CSS and touch gestures
  - [x] 12.1 Add responsive breakpoints to `dc_shiftmaster_html/static/css/theme.css`
    - Mobile (< 480px): single-column layout, hide sidebar, show bottom navigation bar, stack calendar to single column
    - Tablet (480–1024px): collapsed sidebar (icon-only, already partially done), 3-column calendar grid
    - Desktop (> 1024px): full sidebar, 7-column calendar grid (existing)
    - Style bottom nav bar for mobile: fixed bottom, horizontal icon row, active indicator
    - Ensure coverage board cards stack vertically on mobile
    - Ensure login/register form is centered and full-width on mobile
    - _References: Design — Responsive Breakpoints table_

  - [x] 12.2 Add touch gesture handlers
    - Swipe left/right between views on mobile (integrate with router)
    - Pull-to-refresh gesture to reload current view data
    - Add touch handlers in a small utility or inline in `router.js`
    - _References: Design — Responsive Breakpoints (Mobile row)_

- [x] 13. Final checkpoint — All features integrated
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Backend uses Python/Flask; frontend uses vanilla JavaScript (no frameworks)
- `werkzeug.security` is already available as a Flask dependency — no new packages needed
- Coverage → Override linkage: claiming a request calls `DatabaseManager.set_override()` to replace the original assignee
- All new API routes live under `/api/auth/` and `/api/coverage/` prefixes
