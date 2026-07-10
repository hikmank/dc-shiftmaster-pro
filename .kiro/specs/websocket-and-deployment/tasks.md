# Implementation Plan: WebSocket Notifications & Production Deployment

## Overview

Bottom-up implementation: dependencies and shared modules first, then backend WebSocket layer, then frontend integration, then deployment/infrastructure hardening. Each task builds on the previous so there is no orphaned code.

## Tasks

- [x] 1. Update dependencies and create shared backend modules
  - [x] 1.1 Add new packages to `requirements-html.txt`
    - Add `flask-sock`, `flask-limiter`, `gunicorn`, `gevent` to `requirements-html.txt`
    - _Requirements: 1.5, 5.3, 7.1, 7.2_

  - [x] 1.2 Create `dc_shiftmaster_html/broadcast.py` with Connected_Client_Set and broadcast function
    - Implement a module-level `set` guarded by `threading.Lock`
    - Implement `add_client(ws)`, `remove_client(ws)`, and `broadcast_coverage_event(event_type, request_id)` functions
    - `broadcast_coverage_event` builds a JSON message with event type, request ID, and ISO timestamp, iterates the client set, sends to each, and removes any that raise on send
    - _Requirements: 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 1.3 Write unit tests for `broadcast.py`
    - Test `add_client` / `remove_client` correctly modify the set
    - Test `broadcast_coverage_event` sends JSON with correct fields to all clients
    - Test that a failing client is removed during broadcast and remaining clients still receive the message
    - _Requirements: 2.5, 2.6_

- [x] 2. Implement backend WebSocket handler
  - [x] 2.1 Create `dc_shiftmaster_html/ws_routes.py` with the `/ws/coverage` WebSocket endpoint
    - Use `flask_sock.Sock` to define a WebSocket route at `/ws/coverage`
    - On connection open, call `add_client(ws)`; on close/error, call `remove_client(ws)`
    - Keep the connection alive by looping on `ws.receive()` until disconnect
    - _Requirements: 1.1, 1.2, 1.3, 1.5_

  - [x] 2.2 Register WebSocket routes and flask-sock in `dc_shiftmaster_html/server.py`
    - Import and initialise `Sock(app)` in `create_app`
    - Import and register the ws_routes blueprint
    - _Requirements: 1.1, 1.2_

  - [x] 2.3 Write unit tests for WebSocket route registration
    - Verify the `/ws/coverage` route is registered on the app
    - _Requirements: 1.1_

- [x] 3. Add broadcast calls to coverage mutation routes
  - [x] 3.1 Call `broadcast_coverage_event` after each successful mutation in `dc_shiftmaster_html/routes_coverage.py`
    - After `create_coverage` succeeds, call `broadcast_coverage_event("created", req_id)`
    - After `claim_coverage` succeeds, call `broadcast_coverage_event("claimed", req_id)`
    - After `unclaim_coverage` succeeds, call `broadcast_coverage_event("unclaimed", req_id)`
    - After `cancel_coverage` succeeds, call `broadcast_coverage_event("cancelled", req_id)`
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.2 Write unit tests for broadcast integration in coverage routes
    - Mock `broadcast_coverage_event` and verify it is called with correct event type and request ID after each mutation endpoint
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 4. Checkpoint — Backend WebSocket complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Create frontend WebSocket client and integrate with views
  - [x] 5.1 Create `dc_shiftmaster_html/static/js/ws.js` — shared WebSocket client module
    - Implement a `WS` IIFE module that opens a WebSocket to `ws(s)://<host>/ws/coverage`
    - On message received, parse JSON and invoke registered callbacks
    - On close/error, set a 3-second reconnect timeout
    - Expose `WS.onCoverageEvent(callback)` for views to register refresh handlers
    - Add/remove a visual connection-status indicator (CSS class or small DOM element) when connected/disconnected
    - _Requirements: 1.1, 1.4, 3.1, 3.2, 3.3, 3.4_

  - [x] 5.2 Add `ws.js` script tag to `dc_shiftmaster_html/static/index.html`
    - Insert `<script src="/static/js/ws.js"></script>` before the existing script tags (after `api.js` and `toast.js`, before `state.js`)
    - _Requirements: 1.1_

  - [x] 5.3 Integrate WebSocket refresh in `dc_shiftmaster_html/static/js/coverage.js`
    - At the end of the `Coverage` IIFE (or in `render`), register a `WS.onCoverageEvent` callback that calls `Coverage.loadRequests()`
    - _Requirements: 3.1_

  - [x] 5.4 Integrate WebSocket refresh in `dc_shiftmaster_html/static/js/personal-dashboard.js`
    - Register a `WS.onCoverageEvent` callback that calls `PersonalDashboard.loadAll()`
    - _Requirements: 3.2_

- [x] 6. Checkpoint — WebSocket end-to-end wired
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Harden server.py — secret key, health endpoint, auth gate, and rate limiting
  - [x] 7.1 Update `dc_shiftmaster_html/server.py` secret key handling
    - Read `SECRET_KEY` from `os.environ`; if not set, generate a random key and log a warning
    - Remove the current unconditional `secrets.token_hex(32)` call
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 7.2 Add `/health` endpoint to `dc_shiftmaster_html/server.py`
    - Add a `GET /health` route (no auth required) that queries the DB (e.g., `SELECT 1`) and returns `{"status": "healthy"}` / 200 or `{"status": "unhealthy", "reason": "database unavailable"}` / 503
    - Add `/health` to the auth-gate allow list
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [x] 7.3 Secure the teammates endpoint and add public teammate-names route
    - Remove `/api/teammates` from the `allowed` tuple in `require_login`
    - Add a new route `GET /api/public/teammate-names` (in server.py or a small blueprint) that returns a JSON array of teammate name strings only
    - Add `/api/public/` to the auth-gate allow list
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 7.4 Initialise Flask-Limiter and apply rate limits to auth endpoints
    - Initialise `Flask-Limiter` in `create_app` with `key_func` that respects `X-Forwarded-For`
    - Apply `10/minute` limit to `/api/auth/login`
    - Apply `5/minute` limit to `/api/auth/register`
    - Ensure 429 responses return JSON `{"error": "Rate limit exceeded"}`
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 7.5 Write unit tests for health endpoint
    - Test 200 response with healthy DB
    - Test 503 response when DB query fails
    - _Requirements: 11.2, 11.3_

  - [x] 7.6 Write unit tests for rate limiting on auth endpoints
    - Test that exceeding 10 requests/min on `/api/auth/login` returns 429
    - Test that exceeding 5 requests/min on `/api/auth/register` returns 429
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 7.7 Write unit tests for teammates endpoint security
    - Test that unauthenticated GET `/api/teammates` returns 401
    - Test that GET `/api/public/teammate-names` returns only name strings without auth
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 8. Checkpoint — Server hardening complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Create deployment and infrastructure files
  - [x] 9.1 Create `gunicorn.conf.py` at the repository root
    - Configure `bind` from `SHIFTMASTER_HOST` and `SHIFTMASTER_PORT` env vars (defaults `0.0.0.0:5000`)
    - Set `worker_class = "gevent"` for WebSocket support
    - Set reasonable `workers` count and logging settings
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 9.2 Create `Dockerfile` at the repository root
    - Base image `python:3.11-slim`
    - Copy source and install dependencies from `requirements-html.txt`
    - Expose port 5000
    - Set entrypoint to start via Gunicorn with `gunicorn.conf.py`
    - Do not include the SQLite database file (add to `.dockerignore` if needed)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 9.3 Create `.env.example` at the repository root
    - List `SECRET_KEY`, `SHIFTMASTER_HOST`, `SHIFTMASTER_PORT`, `SHIFTMASTER_DB_PATH`, `SHIFTMASTER_PASSWORD` with descriptive comments and safe defaults
    - Include any rate-limiting configuration variables
    - _Requirements: 10.1, 10.2, 10.3_

  - [x] 9.4 Create `docs/deployment.md` — TLS/Nginx documentation
    - Describe TLS termination via Nginx reverse proxy with a sample config including WebSocket `Upgrade` support
    - Describe the alternative of using an AWS Application Load Balancer for TLS termination
    - _Requirements: 9.1, 9.2, 9.3_

- [x] 10. Final checkpoint — All tasks complete
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirement acceptance criteria numbers for traceability
- Backend WebSocket (tasks 1–4) is completed before frontend integration (task 5) to avoid orphaned code
- Deployment files (task 9) are last since they depend on all application code being in place
- Property-based tests are not included because the feature is primarily integration/IO-bound; unit tests cover the testable pure logic in broadcast.py
