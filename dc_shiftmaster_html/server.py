"""Flask web server for DC-ShiftMaster Pro.

Serves the REST API and static HTML/CSS/JS frontend from a single process.
Uses the existing backend modules (DatabaseManager, SchedulingEngine) unchanged.
"""

import argparse
import logging
import os
import secrets
import sys

from flask import Flask, g, redirect, request, send_from_directory, session, url_for
from flask_sock import Sock

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster.scheduling import SchedulingEngine

logger = logging.getLogger(__name__)


def create_app(
    db_path: str = "teammates.db",
    host: str = "127.0.0.1",
    port: int = 5000,
    password: str = "shiftmaster",
) -> Flask:
    """Create and configure the Flask application.

    Initialises DatabaseManager and SchedulingEngine as app-level
    singletons and registers the route to serve the frontend.

    Args:
        db_path: Path to the SQLite database file.
        host: Host the server will bind to (stored for reference).
        port: Port the server will listen on (stored for reference).
        password: Shared team password for authentication.

    Returns:
        A configured Flask application instance.
    """
    static_dir = os.path.join(os.path.dirname(__file__), "static")

    app = Flask(
        __name__,
        static_folder=static_dir,
        static_url_path="/static",
    )

    secret_key = os.environ.get("SECRET_KEY")
    if secret_key:
        app.secret_key = secret_key
    else:
        app.secret_key = secrets.token_hex(32)
        logger.warning("SECRET_KEY not set — generated a random key. Sessions will not persist across restarts.")

    # Session cookie configuration — ensure cookies work on plain HTTP deployments
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    # Only set Secure=True when HTTPS is available
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("HTTPS_ENABLED", "").lower() == "true"

    # Store host/port for reference by callers
    app.config["HOST"] = host
    app.config["PORT"] = port
    app.config["PASSWORD"] = password

    # --- Initialise backend singletons ---
    try:
        db = DatabaseManager(db_path)
    except Exception as exc:
        logger.error("Failed to open database '%s': %s", db_path, exc)
        sys.exit(1)

    engine = SchedulingEngine()

    app.config["db"] = db
    app.config["engine"] = engine
    app.config["region"] = ""

    # --- Run multi-team migration (idempotent) ---
    from dc_shiftmaster.migration import run_migration, MigrationError

    try:
        result = run_migration(db.conn)
        if result["status"] == "success":
            logger.info("Multi-team migration applied successfully (team_id=%s)", result["team_id"])
    except MigrationError as exc:
        logger.error("Multi-team migration failed: %s", exc)

    # --- Initialise Flask-Limiter ---
    from dc_shiftmaster_html.extensions import limiter

    limiter.init_app(app)
    if app.config.get("TESTING"):
        limiter.enabled = False

    # --- Register API blueprints ---
    from dc_shiftmaster_html.routes_schedule import schedule_bp
    from dc_shiftmaster_html.routes_teammates import teammates_bp
    from dc_shiftmaster_html.routes_overrides import overrides_bp
    from dc_shiftmaster_html.routes_settings import settings_bp
    from dc_shiftmaster_html.routes_export import export_bp
    from dc_shiftmaster_html.routes_import import import_bp
    from dc_shiftmaster_html.routes_ics import ics_bp
    from dc_shiftmaster_html.routes_auth import auth_bp
    from dc_shiftmaster_html.routes_coverage import coverage_bp
    from dc_shiftmaster_html.routes_tokens import tokens_bp
    from dc_shiftmaster_html.routes_profile import profile_bp

    app.register_blueprint(schedule_bp)
    app.register_blueprint(teammates_bp)
    app.register_blueprint(overrides_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(ics_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(coverage_bp)
    app.register_blueprint(tokens_bp)
    app.register_blueprint(profile_bp)

    # --- Register team context middleware (after blueprints) ---
    from dc_shiftmaster_html.team_middleware import team_context_middleware

    # --- Initialise WebSocket support ---
    from dc_shiftmaster_html.ws_routes import init_websocket_routes

    sock = Sock(app)
    init_websocket_routes(sock)

    # --- Global error handler for unhandled exceptions ---
    @app.errorhandler(Exception)
    def handle_exception(exc):
        """Catch any unhandled exception and return a JSON error response."""
        from flask import jsonify as _jsonify

        logger.exception("Unhandled exception: %s", exc)
        return _jsonify({"error": f"Internal server error: {exc}"}), 500

    @app.errorhandler(404)
    def handle_not_found(exc):
        from flask import jsonify as _jsonify

        return _jsonify({"error": "Not found"}), 404

    @app.errorhandler(429)
    def handle_rate_limit(exc):
        from flask import jsonify as _jsonify

        return _jsonify({"error": "Rate limit exceeded"}), 429

    # --- Authentication gate ---
    @app.before_request
    def require_login():
        """Redirect unauthenticated requests to the login page.

        Accepts either the new per-user session (``user_id``) or the
        legacy shared-password session (``authenticated``) so that
        existing sessions keep working after the upgrade.

        Also accepts Bearer token authentication via the Authorization header.
        Session cookies take precedence over bearer tokens when both are present.

        API routes (``/api/``) receive a JSON 401 instead of a redirect
        so that the frontend fetch wrapper can handle it properly.
        """
        from flask import jsonify as _jsonify

        if app.config.get("TESTING"):
            # In test mode, still process bearer tokens if present to allow
            # auth gate tests, but skip session-only enforcement
            auth_header = request.headers.get("Authorization")
            if auth_header:
                result = _process_bearer_auth(auth_header)
                if result is not None:
                    return result
            return  # skip auth in test mode

        allowed = ("/login", "/static/", "/api/auth/login", "/api/auth/register", "/api/public/", "/health")
        if any(request.path == p or request.path.startswith(p) for p in allowed):
            return

        # Check session cookie first (takes precedence per Req 7.3)
        if session.get("user_id") or session.get("authenticated"):
            return

        # No valid session — check for Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header:
            result = _process_bearer_auth(auth_header)
            if result is not None:
                return result
            # If _process_bearer_auth returned None, auth was successful
            # and g.current_user has been set
            return

        # No session and no Authorization header — reject
        if request.path.startswith("/api/"):
            return _jsonify({"error": "Not authenticated"}), 401
        return redirect(url_for("login"))

    def _process_bearer_auth(auth_header: str):
        """Process an Authorization header for bearer token authentication.

        Returns None on success (g.current_user is set).
        Returns a Flask response tuple on failure (401 JSON error).
        """
        from flask import jsonify as _jsonify
        from dc_shiftmaster_html.token_service import TokenService

        # Parse scheme and value
        parts = auth_header.split(None, 1)
        if not parts:
            return _jsonify({"error": "Authentication scheme not supported"}), 401

        scheme = parts[0]

        # Case-insensitive "Bearer" scheme check (Req 7.1)
        if scheme.lower() != "bearer":
            return _jsonify({"error": "Authentication scheme not supported"}), 401

        # Check for empty/whitespace token value (Req 7.4)
        if len(parts) < 2 or not parts[1].strip():
            return _jsonify({"error": "Bearer token value is missing"}), 401

        raw_token = parts[1].strip()

        # Validate the token via TokenService
        token_service = TokenService(app.config["db"])
        user, error_reason = token_service.validate_token_with_reason(raw_token)

        if user is None:
            return _jsonify({"error": error_reason}), 401

        # On valid token: set g.current_user with user info (Req 2.5)
        g.current_user = {
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": "user",  # Default role; model has no role field yet
        }
        return None  # Success — request proceeds

    # --- Register team context middleware (runs AFTER require_login) ---
    app.before_request(team_context_middleware)

    @app.route("/login", methods=["GET"])
    def login():
        """Serve the SPA — the frontend auth.js module handles the login/register UI."""
        return send_from_directory(static_dir, "index.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # --- Serve index.html on GET / ---
    @app.route("/")
    def index():
        return send_from_directory(static_dir, "index.html")

    # --- Public API endpoints (no auth required) ---
    @app.route("/api/public/teammate-names", methods=["GET"])
    def public_teammate_names():
        """Return a JSON array of teammate name strings only (no auth required)."""
        from flask import jsonify as _jsonify

        try:
            db = app.config["db"]
            teammates = db.get_teammates()
            return _jsonify([t.name for t in teammates])
        except Exception as exc:
            return _jsonify({"error": f"Failed to get teammate names: {exc}"}), 500

    # --- Health check endpoint ---
    @app.route("/health", methods=["GET"])
    def health():
        """Return application health status based on database connectivity."""
        from flask import jsonify as _jsonify

        try:
            db = app.config["db"]
            db.conn.execute("SELECT 1")
            return _jsonify({"status": "healthy"}), 200
        except Exception:
            return _jsonify({"status": "unhealthy", "reason": "database unavailable"}), 503

    return app


def main(args: list[str] | None = None) -> None:
    """Parse CLI arguments (with env-var fallbacks) and start the Flask server."""
    parser = argparse.ArgumentParser(
        description="DC-ShiftMaster Pro — HTML/Flask server",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("SHIFTMASTER_HOST", "127.0.0.1"),
        help="Host to bind to (env: SHIFTMASTER_HOST, default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("SHIFTMASTER_PORT", "5000")),
        help="Port to listen on (env: SHIFTMASTER_PORT, default: 5000)",
    )
    parser.add_argument(
        "--db-path",
        dest="db_path",
        default=os.environ.get("SHIFTMASTER_DB_PATH", "teammates.db"),
        help="Path to SQLite database file (env: SHIFTMASTER_DB_PATH, default: teammates.db)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("SHIFTMASTER_PASSWORD", "shiftmaster"),
        help="Shared team password (env: SHIFTMASTER_PASSWORD, default: shiftmaster)",
    )
    parsed = parser.parse_args(args)

    app = create_app(
        db_path=parsed.db_path,
        host=parsed.host,
        port=parsed.port,
        password=parsed.password,
    )
    url = f"http://{parsed.host}:{parsed.port}"
    logger.info("Running on %s", url)
    print(f"Running on {url}")
    app.run(host=parsed.host, port=parsed.port, debug=False)


if __name__ == "__main__":
    main()
