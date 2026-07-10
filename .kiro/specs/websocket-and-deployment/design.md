# Design Document: WebSocket Notifications & Production Deployment

## Overview

This feature adds two complementary capabilities to DC-ShiftMaster Pro's HTML/Flask application:

1. **Real-time WebSocket notifications** — When any user creates, claims, unclaims, or cancels a coverage request, all connected browsers receive a push notification and automatically refresh their views. This replaces the current manual-refresh model where users must reload the page to see changes made by others.

2. **Production deployment readiness** — The application is hardened for hosting on an EC2 instance (or any container host) with a persistent secret key, Gunicorn with gevent workers, a Dockerfile, rate limiting on auth endpoints, endpoint security for the teammates API, TLS documentation, a `.env.example` template, and a health check endpoint.

### Key Design Decisions

1. **flask-sock for WebSocket support**: Lightweight library that integrates directly with Flask routes. No need for Socket.IO or a separate async framework. Works with Gunicorn's gevent worker class.
2. **Thread-safe Connected_Client_Set**: A Python `set` guarded by `threading.Lock` to track active WebSocket connections. Simple and correct for the expected scale (tens of concurrent users, not thousands).
3. **Broadcast from coverage routes**: After each successful DB mutation in `routes_coverage.py`, the route calls a `broadcast_coverage_event()` function. This keeps the broadcast logic co-located with the business logic that triggers it.
4. **New `ws.js` frontend module**: A single shared WebSocket client module that both `coverage.js` and `personal-dashboard.js` use. Handles connection, reconnection (3-second delay), and dispatching refresh callbacks.
5. **Gunicorn with gevent workers**: The `gevent` worker class supports long-lived WebSocket connections without blocking other requests. Standard sync workers would block on each WebSocket connection.
6. **Flask-Limiter for rate limiting**: Well-maintained library that integrates with Flask. Uses in-memory storage (suitable for single-instance deployment). Respects `X-Forwarded-For` for proxy setups.
7. **Dockerfile based on `python:3.11-slim`**: Minimal image size. Database file is excluded and mounted as a volume at runtime.
8. **Health check in `server.py`**: A simple `/health` endpoint that verifies the database connection is functional. No separate blueprint needed — it's a single route.

## Architecture

The WebSocket layer sits alongside the existing REST API. Coverage routes trigger broadcasts after successful mutations. The frontend WebSocket client receives notifications and triggers view refreshes.

```mermaid
graph TD
    subgraph "Browser Clients"
        WC[ws.js - WebSocket Client]
        CV[coverage.js]
        PD[personal-dashboard.js]
    end

    subgraph "Flask Server"
        WS[ws_routes.py - WebSocket Handler]
        CR[routes_coverage.py - Coverage API]
        AR[routes_auth.py - Auth API]
        SV[server.py - App Factory]
        HL[/health endpoint]
        RL[Flask-Limiter Middleware]
        BC[broadcast.py - Broadcast Function]
        CS[Connected_Client_Set]
    end

    subgraph "Infrastructure"
        GU[Gunicorn + gevent]
        DF[Dockerfile]
        NG[Nginx - TLS termination - documented]
    end

    subgraph "Data"
        DB[(SQLite - WAL mode)]
    end

    WC <-->|WebSocket /ws/coverage| WS
    CV -->|REST API| CR
    PD -->|REST API| CR
    AR -->|rate limited| RL

    WS --> CS
    CR -->|after mutation| BC
    BC --> CS
    CS -->|send to all| WS

    SV --> GU
    GU --> DF
    NG -->|proxy| GU

    CR --> DB
    AR --> DB
    HL --> DB
