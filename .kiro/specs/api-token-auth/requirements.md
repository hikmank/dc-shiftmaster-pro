# Requirements Document

## Introduction

DC ShiftMaster Pro currently authenticates users via session cookies backed by username/password login. This works for interactive browser sessions but does not support unattended or scheduled automation (e.g., cron-based schedule refreshes, CI pipelines, or background scripts) because those processes cannot perform an interactive login flow. This feature adds long-lived API tokens that authenticated users can generate, manage, and revoke — enabling automated processes to call the REST API without human interaction.

## Glossary

- **Token_Service**: The server-side component responsible for generating, validating, storing, and revoking API tokens.
- **API_Token**: A cryptographically random bearer credential issued to a user for programmatic access to the REST API without a session cookie.
- **Token_Owner**: The authenticated user who created a given API token.
- **Auth_Gate**: The existing `before_request` middleware that enforces authentication on protected routes.
- **Token_Store**: The database table that persists API token metadata (hashed values, labels, expiration, revocation status).

## Requirements

### Requirement 1: Token Generation

**User Story:** As an authenticated user, I want to generate a new API token, so that I can use it in automated scripts and background processes to access the API without a browser session.

#### Acceptance Criteria

1. WHEN an authenticated user sends a POST request to the token creation endpoint with a label, THE Token_Service SHALL return a newly generated API token value exactly once in the response body.
2. THE Token_Service SHALL generate each API token using a cryptographically secure random generator producing at least 32 bytes of entropy.
3. THE Token_Service SHALL store only a one-way hash of the token value in the Token_Store, not the plaintext token.
4. IF an authenticated user provides a label that is empty, whitespace-only, or exceeds 128 characters, THEN THE Token_Service SHALL reject the request with a 400 status code and an error message indicating the label must be between 1 and 128 non-whitespace-only characters.
5. WHEN an authenticated user provides an expiration duration, THE Token_Service SHALL validate that the value is an integer between 1 and 365 days inclusive and record the computed expiry timestamp on the token record.
6. WHEN no expiration duration is provided, THE Token_Service SHALL create a non-expiring token.
7. IF an authenticated user already has 10 active tokens, THEN THE Token_Service SHALL reject the token creation request with a 400 status code and an error message indicating the maximum token limit has been reached.

### Requirement 2: Token Authentication

**User Story:** As an automated process, I want to authenticate API requests using a token in the Authorization header, so that I can access protected endpoints without an interactive login.

#### Acceptance Criteria

1. WHEN a request includes an Authorization header with the scheme "Bearer" followed by a valid API token (recognized, not revoked, and not expired), THE Auth_Gate SHALL authenticate the request as the Token_Owner and allow it to proceed.
2. WHEN a request includes an Authorization header with an invalid or unrecognized token, THE Auth_Gate SHALL reject the request with a 401 status code and a JSON error body containing an "error" field with a machine-readable reason.
3. WHEN a request includes an Authorization header with a revoked token, THE Auth_Gate SHALL reject the request with a 401 status code and a JSON error body indicating the token has been revoked.
4. WHEN a request includes an Authorization header with an expired token, THE Auth_Gate SHALL reject the request with a 401 status code and a JSON error body indicating the token has expired.
5. WHILE a valid token is used for authentication, THE Auth_Gate SHALL make the Token_Owner's user ID, username, display name, and role available to downstream request handlers in the same manner as session-based authentication.
6. THE Auth_Gate SHALL continue to accept session cookie authentication for browser-based users unchanged.
7. WHEN a request includes an Authorization header with the "Bearer" scheme but the token value is empty or contains only whitespace, THE Auth_Gate SHALL reject the request with a 401 status code and a JSON error body indicating a missing token value.

### Requirement 3: Token Management

**User Story:** As an authenticated user, I want to list and view metadata about my tokens, so that I can audit which tokens exist and when they were last used.

#### Acceptance Criteria

1. WHEN an authenticated user sends a GET request to the token listing endpoint, THE Token_Service SHALL return a list of all tokens (active, revoked, and expired) owned by that user including token ID, label, creation timestamp, expiry timestamp, revocation status, and last-used timestamp, sorted by creation timestamp in descending order (newest first).
2. THE Token_Service SHALL exclude plaintext token values and token hashes from the listing response.
3. WHEN an authenticated user has no tokens, THE Token_Service SHALL return a standard response wrapper with an empty data array and metadata (including pagination info) with a 200 status code.
4. THE Token_Service SHALL return at most 100 token records per listing request.

### Requirement 4: Token Revocation

**User Story:** As an authenticated user, I want to revoke a token I previously created, so that compromised or unneeded tokens can no longer access the API.

#### Acceptance Criteria

1. WHEN an authenticated user sends a DELETE request to the token revocation endpoint with a valid token ID they own, THE Token_Service SHALL mark the token as revoked and return a 204 status code with no response body.
2. IF an authenticated user attempts to revoke a token they do not own, THEN THE Token_Service SHALL reject the request with a 403 status code and an error message indicating the user lacks ownership of the specified token.
3. IF an authenticated user attempts to revoke a token ID that does not exist, THEN THE Token_Service SHALL return a 404 status code and an error message indicating the token ID was not found.
4. WHEN a token is revoked, THE Auth_Gate SHALL reject any subsequent requests using that token within 5 seconds of revocation (allowing a grace period of up to 5 seconds for propagation), and SHALL continue rejecting the revoked token permanently thereafter, returning a 401 status code and an error message indicating the token has been revoked.
5. IF an unauthenticated request is sent to the token revocation endpoint, THEN THE Token_Service SHALL reject the request with a 401 status code and an error message indicating authentication is required.
6. IF an authenticated user sends a DELETE request with a token ID that is not in a valid identifier format, THEN THE Token_Service SHALL return a 400 status code and an error message indicating the token ID format is invalid.

### Requirement 5: Token Security

**User Story:** As a system administrator, I want API tokens to be secured against common attack vectors, so that unauthorized access via stolen or brute-forced tokens is prevented.

#### Acceptance Criteria

1. THE Token_Service SHALL store tokens in a one-way hashed form such that the original token value cannot be recovered from the stored representation, and SHALL use a timing-safe comparison algorithm during token validation to prevent timing-based side-channel attacks.
2. THE Token_Service SHALL limit the number of active (non-revoked, non-expired) tokens per user to a maximum of 10.
3. WHEN a user already has 10 active tokens and attempts to create another, THE Token_Service SHALL reject the request with a 400 status code and an error message indicating the active token limit has been reached.
4. WHEN a token is successfully used for authentication (full authentication success with no account-level blocks), THE Token_Service SHALL record the last-used timestamp with second-level precision; the timestamp SHALL NOT be updated for failed authentication attempts or when authentication fails for non-token reasons (e.g., account suspension).
5. IF the token creation endpoint receives more than 5 requests within a 60-second sliding window from a single user, THEN THE Token_Service SHALL reject excess requests with a 429 status code and an error message indicating the rate limit and the number of seconds until the next request is permitted.
6. THE Token_Service SHALL generate tokens with a minimum length of 32 cryptographically random bytes to resist brute-force guessing attacks.

### Requirement 6: Token Database Storage

**User Story:** As a developer, I want token data persisted in the existing SQLite database, so that the feature integrates with the current data layer without adding external dependencies.

#### Acceptance Criteria

1. THE Token_Store SHALL persist token records in a new `api_tokens` table within the existing SQLite database.
2. THE Token_Store SHALL store for each token: an auto-increment integer ID, the owning user ID (foreign key to users), the token hash (unique, maximum 128 characters), the label (maximum 128 characters, non-empty), a created-at timestamp (defaulting to the current UTC time on insertion), an optional expires-at timestamp (NULL if non-expiring), a revoked boolean (defaulting to false), and a last-used-at timestamp (NULL until first use).
3. WHEN the application starts and the `api_tokens` table does not exist, THE Token_Store SHALL create it automatically as part of the existing database migration process. WHEN the table already exists, THE Token_Store SHALL skip creation entirely.
4. THE Token_Store SHALL enforce a foreign key relationship between the token's user ID and the users table, with CASCADE deletion so that removing a user also removes all associated token records.
5. THE Token_Store SHALL enforce a unique constraint on the token hash column to prevent duplicate entries.
6. THE Token_Store SHALL create an index on the token hash column and an index on the user ID column to support efficient lookups by hash and by owner.

### Requirement 7: Token Identification in Requests

**User Story:** As an automated process developer, I want a clear, standard mechanism to pass my token with each request, so that integration is straightforward and follows common conventions.

#### Acceptance Criteria

1. THE Auth_Gate SHALL accept API tokens via the HTTP `Authorization` header using the format `Bearer <token>`, where the scheme comparison is case-insensitive (e.g., "bearer", "BEARER", and "Bearer" are all accepted).
2. WHEN the Authorization header is present but uses an unsupported scheme (not "Bearer" case-insensitive), THE Auth_Gate SHALL reject the request with a 401 status code and a JSON error body indicating that the authentication scheme is not supported.
3. WHEN both a valid session cookie and a valid Bearer token are present on the same request, THE Auth_Gate SHALL use the session cookie for authentication and ignore the token. This rule only applies when both credentials are valid; if only a Bearer token is present without a valid session cookie, THE Auth_Gate SHALL authenticate using the Bearer token.
4. IF the Authorization header is present with the Bearer scheme but the token value is empty or contains only whitespace, THEN THE Auth_Gate SHALL reject the request with a 401 status code and a JSON error body indicating that the token value is missing.
