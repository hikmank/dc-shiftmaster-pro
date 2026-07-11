# Implementation Plan: API Token Authentication

## Overview

This plan implements long-lived API token authentication for DC ShiftMaster Pro. The implementation follows a bottom-up approach: database layer first, then the token service, auth gate enhancement, and finally the routes blueprint — wiring everything together at the end.

## Tasks

- [x] 1. Set up database schema and token store methods
  - [x] 1.1 Add `api_tokens` table creation to the database migration
    - Add CREATE TABLE IF NOT EXISTS for `api_tokens` with all columns (id, user_id, token_hash, label, created_at, expires_at, revoked, last_used_at)
    - Add CREATE INDEX statements for token_hash and user_id
    - Ensure foreign key constraint with CASCADE delete references users(id)
    - Integrate into the existing `init_db()` or migration path in `dc_shiftmaster/database.py`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 1.2 Implement token CRUD methods on DatabaseManager
    - Add `create_api_token(user_id, token_hash, label, expires_at)` → returns new row ID
    - Add `get_api_token_by_hash(token_hash)` → returns dict or None
    - Add `get_api_tokens_for_user(user_id)` → returns list of dicts sorted by created_at DESC, max 100
    - Add `revoke_api_token(token_id)` → sets revoked=1
    - Add `update_token_last_used(token_id)` → sets last_used_at to current UTC
    - Add `count_active_api_tokens(user_id)` → count where revoked=0 and not expired
    - _Requirements: 6.1, 6.2, 6.6_

  - [x] 1.3 Write unit tests for database token methods
    - Test create_api_token inserts correctly and returns ID
    - Test get_api_token_by_hash returns correct record and None for missing
    - Test get_api_tokens_for_user returns sorted results capped at 100
    - Test revoke_api_token sets revoked flag
    - Test count_active_api_tokens excludes revoked and expired
    - Test CASCADE delete removes tokens when user is deleted
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 2. Implement TokenService class
  - [x] 2.1 Create `dc_shiftmaster_html/token_service.py` with TokenService class
    - Implement `generate_token()` static method using `secrets.token_hex(32)` (64 hex chars)
    - Implement `hash_token(raw_token)` static method using SHA-256 hex digest
    - Implement `create_token(user_id, label, expires_in_days)` with validation:
      - Validate label (non-empty, non-whitespace-only, ≤128 chars)
      - Validate expires_in_days (None or integer 1–365)
      - Check active token count ≤ 10
      - Generate token, hash it, store via DatabaseManager, return plaintext once
    - Implement `validate_token(raw_token)` with timing-safe comparison via `hmac.compare_digest`
      - Hash incoming token, look up in DB
      - Check not revoked, not expired
      - Update last_used_at on success
      - Return user info or None
    - Implement `list_tokens(user_id)` delegating to DB method
    - Implement `revoke_token(user_id, token_id)` with ownership check
    - Implement `count_active_tokens(user_id)` delegating to DB method
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.1, 2.3, 2.4, 3.1, 3.2, 4.1, 4.2, 5.1, 5.2, 5.4, 5.6_

  - [x] 2.2 Write property test: Token generation produces unique, correctly-sized tokens
    - **Property 1: Token generation produces unique, correctly-sized tokens**
    - Generate N tokens, assert all are exactly 64 hex characters and all are distinct
    - **Validates: Requirements 1.1, 1.2, 5.6**

  - [x] 2.3 Write property test: Token hash storage round-trip
    - **Property 2: Token hash storage round-trip**
    - Create token, read DB row, assert stored hash == SHA-256(plaintext) and hash ≠ plaintext
    - Validate that `validate_token(plaintext)` locates the correct record
    - **Validates: Requirements 1.3, 5.1**

  - [x] 2.4 Write property test: Invalid labels are rejected
    - **Property 3: Invalid labels are rejected**
    - Generate empty strings, whitespace-only strings, and strings >128 chars
    - Assert 400 response and token count unchanged
    - **Validates: Requirements 1.4**

  - [x] 2.5 Write property test: Expiration duration produces correct expiry timestamp
    - **Property 4: Expiration duration produces correct expiry timestamp**
    - For N in [1, 365], assert expires_at == created_at + N days
    - For invalid values (0, negative, >365, non-integer), assert rejection
    - **Validates: Requirements 1.5**

- [x] 3. Checkpoint - Core service layer validation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Enhance the auth gate to support bearer token authentication
  - [x] 4.1 Extend `before_request` auth logic in `server.py`
    - Check session cookie first (existing behavior, precedence)
    - If no session, parse `Authorization` header
    - Case-insensitive "Bearer" scheme check
    - Reject unsupported schemes with 401 JSON
    - Reject empty/whitespace token value with 401 JSON
    - Call `TokenService.validate_token(raw_token)` for valid bearer values
    - On valid token: set `g.current_user` with user_id, username, display_name, role
    - On invalid/revoked/expired: return 401 JSON with specific error reason
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 7.1, 7.2, 7.3, 7.4_

  - [x] 4.2 Write property test: Valid token authenticates as the token owner
    - **Property 5: Valid token authenticates as the token owner**
    - Create user + token, send request with Bearer header, assert correct identity in response
    - **Validates: Requirements 2.1, 2.5**

  - [x] 4.3 Write property test: Revocation invalidates authentication
    - **Property 6: Revocation invalidates authentication**
    - Create token, revoke it, attempt auth, assert 401 with revocation message
    - **Validates: Requirements 2.3, 4.1, 4.4**

  - [x] 4.4 Write property test: Expired tokens are rejected
    - **Property 7: Expired tokens are rejected**
    - Create token with past expiry, attempt auth, assert 401 with expiration message
    - **Validates: Requirements 2.4**

  - [x] 4.5 Write property test: Bearer scheme case-insensitive and non-bearer rejected
    - **Property 10: Bearer scheme is case-insensitive and non-bearer schemes are rejected**
    - Generate random case variations of "bearer" → accepted
    - Generate random non-bearer scheme strings → rejected with 401
    - **Validates: Requirements 7.1, 7.2**

- [x] 5. Implement token routes Blueprint
  - [x] 5.1 Create `dc_shiftmaster_html/routes_tokens.py` with token management endpoints
    - Create `tokens_bp` Blueprint with url_prefix `/api/auth/tokens`
    - Implement POST `/api/auth/tokens` (create token):
      - Require session authentication
      - Parse JSON body for `label` and optional `expires_in_days`
      - Delegate to TokenService.create_token()
      - Return 201 with token data (plaintext shown once)
      - Apply rate limit: 5/minute per user
    - Implement GET `/api/auth/tokens` (list tokens):
      - Require session authentication
      - Delegate to TokenService.list_tokens()
      - Return 200 with data array and meta object
    - Implement DELETE `/api/auth/tokens/<token_id>` (revoke token):
      - Require session authentication
      - Validate token_id format
      - Delegate to TokenService.revoke_token()
      - Return 204 on success
      - Handle 403 (not owner), 404 (not found)
    - _Requirements: 1.1, 1.4, 1.5, 1.6, 1.7, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.5, 4.6, 5.3, 5.5_

  - [x] 5.2 Write property test: Token listing excludes secrets and maintains sort order
    - **Property 8: Token listing excludes secrets and maintains sort order**
    - Create multiple tokens for a user, list them, assert no `token` or `token_hash` fields, assert sorted by created_at DESC
    - **Validates: Requirements 3.1, 3.2**

  - [x] 5.3 Write property test: Ownership enforcement on revocation
    - **Property 9: Ownership enforcement on revocation**
    - Create two users, create token for user A, attempt revoke as user B, assert 403 and token remains active
    - **Validates: Requirements 4.2**

  - [x] 5.4 Write unit tests for token routes
    - Test create token with no expiration returns expires_at null (Req 1.6)
    - Test user with no tokens gets empty list with 200 (Req 3.3)
    - Test revoking non-existent token ID returns 404 (Req 4.3)
    - Test unauthenticated revocation attempt returns 401 (Req 4.5)
    - Test session cookie takes precedence over bearer token (Req 7.3)
    - Test rate limiting: 6th request within 60s returns 429 (Req 5.5)
    - _Requirements: 1.6, 3.3, 4.3, 4.5, 5.5, 7.3_

- [x] 6. Register Blueprint and wire components together
  - [x] 6.1 Register the tokens Blueprint in the Flask application
    - Import `tokens_bp` in server.py
    - Register blueprint with the Flask app
    - Initialize TokenService with the app's DatabaseManager instance
    - Ensure rate limiter (flask-limiter) is configured for the tokens blueprint
    - Verify the auth gate can access the TokenService instance
    - _Requirements: 1.1, 2.1, 5.5_

  - [x] 6.2 Write integration tests for end-to-end token flows
    - Test create token → use token for API call → verify access
    - Test create token → revoke token → attempt API call → verify 401
    - Test database migration creates table and indexes idempotently (Req 6.3)
    - _Requirements: 1.1, 2.1, 2.3, 4.1, 6.3_

- [x] 7. Final checkpoint - Full validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation language is Python (Flask/SQLite) matching the existing codebase
- Rate limiting uses flask-limiter (already in the project or to be added as dependency)
- All token operations use the existing DatabaseManager pattern

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "2.5"] },
    { "id": 4, "tasks": ["4.1", "5.1"] },
    { "id": 5, "tasks": ["4.2", "4.3", "4.4", "4.5", "5.2", "5.3", "5.4"] },
    { "id": 6, "tasks": ["6.1"] },
    { "id": 7, "tasks": ["6.2"] }
  ]
}
```
