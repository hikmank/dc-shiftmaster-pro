"""Team context middleware for Flask before_request hook.

Reads the active_team_id from the session, validates user membership,
and attaches g.team_id to the request context. Returns 403 for
team-scoped endpoints that lack valid team context.

Requirements: 8.1, 8.2, 8.3, 8.4
"""

from flask import current_app, g, jsonify, request, session

TEAM_EXEMPT_PREFIXES = (
    "/api/auth/",
    "/api/teams",
    "/login",
    "/static/",
    "/health",
    "/api/public/",
)


def team_context_middleware():
    """Inject team_id into request context for team-scoped endpoints.

    Exempt paths (auth, teams management, login, static, health, public)
    pass through without team context validation. The root path '/' is
    also exempt since it serves the SPA HTML.

    In TESTING mode, if no active_team_id is in the session the middleware
    allows the request through without enforcement (matching the auth gate
    pattern). If a test explicitly sets active_team_id, the middleware
    validates it normally.

    For all other endpoints:
    - If no active_team_id in session: returns 403 with NO_TEAM code
    - If user is not a member of the active team: clears session,
      returns 403 with INVALID_TEAM code
    - Otherwise: attaches team_id to g for downstream route handlers
    """
    # Exempt the root path (serves the SPA)
    if request.path == "/":
        return None

    # Exempt configured prefixes
    if any(request.path.startswith(p) for p in TEAM_EXEMPT_PREFIXES):
        return None

    # Check for active team in session
    active_team_id = session.get("active_team_id")

    if not active_team_id:
        # In TESTING mode, allow requests without team context (backward compat)
        if current_app.config.get("TESTING"):
            return None
        return jsonify({"error": "No team selected", "code": "NO_TEAM"}), 403

    # Validate user still belongs to the active team
    db = current_app.config["db"]
    user_id = session.get("user_id")
    if not db.is_team_member(user_id, active_team_id):
        session.pop("active_team_id", None)
        return jsonify({"error": "Team membership invalid", "code": "INVALID_TEAM"}), 403

    # Attach team context to request
    g.team_id = active_team_id
    return None
