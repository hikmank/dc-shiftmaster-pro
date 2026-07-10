# Implementation Plan: Profile UI

## Overview

Add a Profile view to the DC-ShiftMaster Pro HTML frontend, following the existing IIFE module pattern. The implementation modifies four files (`api.js`, `index.html`, `router.js`) and creates one new file (`profile.js`). Each task builds incrementally so the feature is wirable and testable at each step.

## Tasks

- [x] 1. Add `updateProfile` method to `api.js`
  - Add `updateProfile: function (data) { return json('PUT', '/api/auth/profile', data); }` to the returned object, inside the `/* --- Auth --- */` section after `getCurrentUser`
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 2. Add Profile view section, nav items, and script tag to `index.html`
  - [x] 2.1 Add sidebar nav item for Profile
    - Add `<li class="nav-item" data-view="profile">` with a person/profile icon and label "Profile" after the "My Shifts" `<li>` in the sidebar `<ul class="nav-list">`
    - _Requirements: 1.1_
  - [x] 2.2 Add bottom nav item for Profile
    - Add `<li class="bottom-nav-item" data-view="profile">` with icon and label "Profile" at the end of `<ul class="bottom-nav-list">`
    - _Requirements: 1.2_
  - [x] 2.3 Add Profile view section in main content
    - Add `<section id="profile-view" class="view" hidden></section>` after the `my-shifts-view` section and before the `login-view` section
    - _Requirements: 1.3, 7.3_
  - [x] 2.4 Add `profile.js` script tag
    - Add `<script src="/static/js/profile.js"></script>` before the closing `</body>` tag, after `personal-dashboard.js` and before `touch.js` (so it loads before `router.js`)
    - _Requirements: 1.5_

- [x] 3. Register Profile view in `router.js`
  - Add `'profile'` to the `views` array
  - Add `profile: function () { if (typeof loadProfile === 'function') loadProfile(); }` to the `loaders` object
  - _Requirements: 1.3, 1.4, 1.5_

- [x] 4. Create `profile.js` module
  - [x] 4.1 Create the Profile IIFE module and `loadProfile` global function
    - Create `dc_shiftmaster_html/static/js/profile.js`
    - Implement `var Profile = (function () { ... })();` with a `load()` function and expose `function loadProfile() { Profile.load(); }`
    - In `load()`: render HTML into `#profile-view` with an `<h2>Profile</h2>`, a read-only `settings-section` showing display name and username, an editable `settings-section` with email input (`type="email"`, `id="profile-email"`, class `form-control`) and notification checkbox (`id="profile-notifications"`), and a Save button (`id="profile-save"`, classes `btn btn-primary`)
    - Use existing CSS classes: `settings-section`, `form-group`, `form-control`, `btn`, `btn-primary`
    - _Requirements: 2.4, 3.1, 3.5, 4.1, 5.1, 7.1, 7.2_
  - [x] 4.2 Implement data population from `API.getCurrentUser()`
    - Call `API.getCurrentUser()` after rendering HTML
    - Populate `#profile-email` value with `user.email`, set `#profile-notifications` checked state from `user.email_notifications_enabled`, and fill read-only display name and username spans
    - On fetch failure, call `Toast.show(err.message, 'error')`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 4.3 Implement Save button handler
    - Attach click handler to `#profile-save`
    - On click: disable the button, read email from `#profile-email` and checked state from `#profile-notifications`, call `API.updateProfile({email, email_notifications_enabled})`
    - On success: call `Toast.show('Profile updated', 'success')`, update `AppState.user` with the response data
    - On error: call `Toast.show(err.message, 'error')`
    - In finally: re-enable the Save button
    - _Requirements: 3.2, 3.3, 3.4, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4_

- [x] 5. Checkpoint — Verify integration
  - Ensure all files are saved and consistent: `api.js` has `updateProfile`, `index.html` has the nav items + section + script tag, `router.js` registers `profile`, and `profile.js` renders and submits correctly
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Write property-based tests for Profile UI
  - [x] 6.1 Write property test: Router view switching
    - **Property 1: Router view switching shows exactly one view and activates correct nav items**
    - Using fast-check, generate a random view name from the registered views list (including `'profile'`), call `Router.show()`, assert exactly one section is visible and the correct nav items have the `active` class
    - **Validates: Requirements 1.3, 1.4**
  - [x] 6.2 Write property test: Profile data population
    - **Property 2: Profile data population matches user object**
    - Using fast-check, generate random user objects with arbitrary `display_name`, `username`, `email` strings and random `email_notifications_enabled` booleans, mock `API.getCurrentUser()` to return them, load profile, assert form fields match
    - **Validates: Requirements 2.2, 2.3, 2.4**
  - [x] 6.3 Write property test: Form submission payload
    - **Property 3: Form submission sends correct payload**
    - Using fast-check, generate random email strings and random booleans, set form input values, trigger Save, intercept the fetch call, assert the request body matches `{email, email_notifications_enabled}`
    - **Validates: Requirements 3.2, 4.2, 5.1, 6.2**
  - [x] 6.4 Write property test: AppState update on save
    - **Property 4: Successful save updates AppState.user**
    - Using fast-check, generate random response objects with `email` and `email_notifications_enabled` fields, mock a successful PUT response, trigger Save, assert `AppState.user` fields match the response
    - **Validates: Requirements 5.4**

- [x] 7. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The design uses vanilla JavaScript — no framework or build step needed
- All CSS classes already exist in `theme.css`; no new styles required
- The backend endpoints (`GET /api/auth/me`, `PUT /api/auth/profile`) already exist
- Property tests use the fast-check library for JavaScript PBT
