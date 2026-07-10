# Requirements Document

## Introduction

This specification covers two complementary areas for DC-ShiftMaster Pro's HTML/Flask application: real-time WebSocket notifications for coverage request events, and production deployment readiness for hosting on AWS EC2. The WebSocket feature replaces the current manual-refresh approach so that all connected clients see coverage changes instantly. The deployment readiness work hardens the application for production use with persistent sessions, a production WSGI server, containerization, rate limiting, endpoint security, TLS documentation, environment configuration, and health checks.

## Glossary

- **App**: The DC-ShiftMaster Pro HTML/Flask web application
- **WebSocket_Server**: The server-side component that manages WebSocket connections and broadcasts messages to connected clients, implemented using flask-sock
- **WebSocket_Client**: The browser-side JavaScript code that opens and maintains a WebSocket connection to the WebSocket_Server
- **Coverage_Event**: A state change in the coverage request system — specifically a create, claim, unclaim, or cancel action
- **Connected_Client_Set**: The server-side collection of active WebSocket connections maintained by the WebSocket_Server
- **Notification_Message**: A JSON-formatted message broadcast by the WebSocket_Server to all entries in the Connected_Client_Set when a Coverage_Event occurs
- **Gunicorn**: A production-grade Python WSGI HTTP server used to serve the App instead of Flask's built-in development server
- **Rate_Limiter**: A middleware component that restricts the number of requests a single client can make to specific endpoints within a time window
- **Health_Endpoint**: A lightweight HTTP endpoint that returns the operational status of the App for use by load balancers
- **Teammates_Endpoint**: The `/api/teammates` HTTP endpoint that returns teammate data
- **Auth_Endpoints**: The `/api/auth/login` and `/api/auth/register` HTTP endpoints
- **Secret_Key**: The Flask session signing key used to secure session cookies
- **Env_Config**: Environment variable-based configuration for deployment settings

## Requirements

### Requirement 1: WebSocket Connection Lifecycle

**User Story:** As a user, I want my browser to maintain a persistent WebSocket connection to the server, so that I can receive real-time updates without refreshing the page.

#### Acceptance Criteria

1. WHEN a user loads the coverage view or personal dashboard view, THE WebSocket_Client SHALL open a WebSocket connection to the WebSocket_Server at the `/ws/coverage` path
2. WHEN a WebSocket connection is established, THE WebSocket_Server SHALL add the connection to the Connected_Client_Set
3. WHEN a WebSocket connection is closed or errors, THE WebSocket_Server SHALL remove the connection from the Connected_Client_Set
4. IF the WebSocket connection drops unexpectedly, THEN THE WebSocket_Client SHALL attempt to reconnect after a delay of 3 seconds
5. THE WebSocket_Server SHALL accept concurrent connections from all active clients without blocking request handling

### Requirement 2: Coverage Event Broadcasting

**User Story:** As a user, I want all connected clients to be notified in real-time when a coverage request is created, claimed, unclaimed, or cancelled, so that everyone sees the latest state without refreshing.

#### Acceptance Criteria

1. WHEN a coverage request is created, THE WebSocket_Server SHALL broadcast a Notification_Message with event type "created" to all entries in the Connected_Client_Set
2. WHEN a coverage request is claimed, THE WebSocket_Server SHALL broadcast a Notification_Message with event type "claimed" to all entries in the Connected_Client_Set
3. WHEN a coverage request is unclaimed, THE WebSocket_Server SHALL broadcast a Notification_Message with event type "unclaimed" to all entries in the Connected_Client_Set
4. WHEN a coverage request is cancelled, THE WebSocket_Server SHALL broadcast a Notification_Message with event type "cancelled" to all entries in the Connected_Client_Set
5. THE Notification_Message SHALL contain the fields: event type, coverage request ID, and a timestamp
6. IF a connection in the Connected_Client_Set fails during broadcast, THEN THE WebSocket_Server SHALL remove that connection from the Connected_Client_Set and continue broadcasting to remaining connections

### Requirement 3: Frontend Real-Time UI Update

**User Story:** As a user, I want the coverage board and my personal dashboard to update automatically when a WebSocket notification arrives, so that I always see current data.

#### Acceptance Criteria

1. WHEN the WebSocket_Client receives a Notification_Message, THE coverage view SHALL re-fetch the coverage request list from the API and re-render the display
2. WHEN the WebSocket_Client receives a Notification_Message, THE personal dashboard view SHALL re-fetch the user's requests, claimed shifts, and upcoming shifts from the API and re-render the display
3. WHILE the WebSocket connection is active, THE WebSocket_Client SHALL display no manual refresh prompt to the user
4. WHILE the WebSocket connection is disconnected, THE WebSocket_Client SHALL display a visual indicator that real-time updates are unavailable

### Requirement 4: Persistent Secret Key

**User Story:** As an operator, I want session cookies to survive application restarts, so that users are not logged out every time the server restarts.

#### Acceptance Criteria

1. WHEN the `SECRET_KEY` environment variable is set, THE App SHALL use that value as the Flask secret key
2. WHEN the `SECRET_KEY` environment variable is not set, THE App SHALL generate a random secret key and log a warning that sessions will not persist across restarts
3. THE App SHALL use the Secret_Key exclusively from environment configuration or a generated fallback, and SHALL NOT hard-code a secret key value in source code

### Requirement 5: Gunicorn Production Server

**User Story:** As an operator, I want to run the application with a production-grade WSGI server, so that the app can handle concurrent requests reliably.

#### Acceptance Criteria

1. THE App SHALL include a `gunicorn.conf.py` configuration file specifying worker count, bind address, and logging settings
2. THE `gunicorn.conf.py` SHALL configure the bind address from the `SHIFTMASTER_HOST` and `SHIFTMASTER_PORT` environment variables with defaults of `0.0.0.0` and `5000`
3. THE `gunicorn.conf.py` SHALL configure the worker class to support WebSocket connections (using a gevent or threaded worker)
4. WHEN deployed in production, THE App SHALL be started via Gunicorn using the configuration file instead of `app.run()`

### Requirement 6: Dockerfile for Containerized Deployment

**User Story:** As an operator, I want a Dockerfile to build a container image of the application, so that I can deploy it consistently on EC2 or any container host.

#### Acceptance Criteria

1. THE App SHALL include a Dockerfile that builds a container image with all Python dependencies installed
2. THE Dockerfile SHALL use a minimal Python base image
3. THE Dockerfile SHALL expose the application port (default 5000)
4. THE Dockerfile SHALL set the entrypoint to start the App via Gunicorn
5. THE Dockerfile SHALL not include the SQLite database file in the image, allowing it to be mounted as a volume at runtime

### Requirement 7: Rate Limiting on Auth Endpoints

**User Story:** As an operator, I want login and registration endpoints to be rate-limited, so that brute-force and credential-stuffing attacks are mitigated.

#### Acceptance Criteria

1. THE Rate_Limiter SHALL restrict requests to `/api/auth/login` to a maximum of 10 requests per minute per client IP address
2. THE Rate_Limiter SHALL restrict requests to `/api/auth/register` to a maximum of 5 requests per minute per client IP address
3. WHEN a client exceeds the rate limit, THE Rate_Limiter SHALL return HTTP status 429 with a JSON error message indicating the limit has been exceeded
4. THE Rate_Limiter SHALL identify clients by IP address, respecting the `X-Forwarded-For` header when the App is behind a reverse proxy

### Requirement 8: Teammates Endpoint Security

**User Story:** As an operator, I want the teammates endpoint to not expose full teammate data to unauthenticated users, so that internal team information is protected.

#### Acceptance Criteria

1. THE App SHALL remove `/api/teammates` from the list of endpoints allowed without authentication
2. THE App SHALL provide a new public endpoint `/api/public/teammate-names` that returns only teammate names (no IDs, shift types, or custom start times)
3. WHEN an unauthenticated user accesses `/api/public/teammate-names`, THE App SHALL return a JSON array of teammate name strings
4. WHEN an unauthenticated user accesses `/api/teammates`, THE App SHALL return HTTP status 401

### Requirement 9: TLS/HTTPS Configuration Documentation

**User Story:** As an operator, I want documentation on how to configure TLS termination, so that all traffic to the application is encrypted in transit.

#### Acceptance Criteria

1. THE App SHALL include documentation describing TLS termination via an Nginx reverse proxy configuration
2. THE documentation SHALL include a sample Nginx configuration file that proxies HTTPS traffic to the Gunicorn backend, including WebSocket upgrade support
3. THE documentation SHALL describe the alternative of using an AWS Application Load Balancer for TLS termination

### Requirement 10: Environment Configuration Template

**User Story:** As an operator, I want a `.env.example` file listing all configurable environment variables, so that I can set up the application without reading source code.

#### Acceptance Criteria

1. THE App SHALL include a `.env.example` file in the repository root
2. THE `.env.example` file SHALL list every configurable environment variable with a descriptive comment and a safe default value
3. THE `.env.example` file SHALL include at minimum: `SECRET_KEY`, `SHIFTMASTER_HOST`, `SHIFTMASTER_PORT`, `SHIFTMASTER_DB_PATH`, `SHIFTMASTER_PASSWORD`, and any rate-limiting configuration variables

### Requirement 11: Health Check Endpoint

**User Story:** As an operator, I want a health check endpoint, so that load balancers and monitoring tools can verify the application is running.

#### Acceptance Criteria

1. THE App SHALL expose a `GET /health` endpoint that does not require authentication
2. WHEN the App is running and the database connection is functional, THE Health_Endpoint SHALL return HTTP status 200 with a JSON body containing `{"status": "healthy"}`
3. IF the database connection is not functional, THEN THE Health_Endpoint SHALL return HTTP status 503 with a JSON body containing `{"status": "unhealthy", "reason": "database unavailable"}`
4. THE Health_Endpoint SHALL respond within 5 seconds under normal operating conditions
