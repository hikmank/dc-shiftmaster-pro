"""Tests for the bearer token authentication gate in server.py.

Validates Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 7.1, 7.2, 7.3, 7.4
"""

from datetime import datetime, timedelta, timezone

import pytest

from dc_shiftmaster_html.server import create_app
from dc_shiftmaster_html.token_service import TokenService


@pytest.fixture
def app_with_user(tmp_path):
    """Create an app with a registered user and return (app, user, db)."""
    db_path = str(tmp_path / "auth_test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    db = app.config["db"]
    # Register a user
    from werkzeug.security import generate_password_hash

    password_hash = generate_password_hash("testpass")
    cursor = db.conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password_hash, display_name, teammate_name) "
        "VALUES (?, ?, ?, ?)",
        ("testuser", password_hash, "Test User", ""),
    )
    db.conn.commit()
    user_id = cursor.lastrowid

    user_info = {
        "id": user_id,
        "username": "testuser",
        "display_name": "Test User",
    }

    return app, user_info, db


@pytest.fixture
def token_for_user(app_with_user):
    """Create a valid token for the test user and return (app, token, user_info)."""
    app, user_info, db = app_with_user
    token_service = TokenService(db)
    result = token_service.create_token(user_info["id"], "test-token")
    return app, result["token"], user_info


class TestBearerSchemeValidation:
    """Tests for Authorization header scheme parsing (Req 7.1, 7.2)."""

    def test_bearer_lowercase_accepted(self, token_for_user):
        """'bearer' (lowercase) is accepted as a valid scheme."""
        app, token, user_info = token_for_user
        with app.test_client() as client:
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": f"bearer {token}"},
            )
            # Should not get 401 for unsupported scheme
            assert resp.status_code != 401 or "scheme not supported" not in resp.get_json().get("error", "")

    def test_bearer_uppercase_accepted(self, token_for_user):
        """'BEARER' (uppercase) is accepted as a valid scheme."""
        app, token, user_info = token_for_user
        with app.test_client() as client:
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": f"BEARER {token}"},
            )
            assert resp.status_code != 401 or "scheme not supported" not in resp.get_json().get("error", "")

    def test_bearer_mixed_case_accepted(self, token_for_user):
        """'BeArEr' (mixed case) is accepted as a valid scheme."""
        app, token, user_info = token_for_user
        with app.test_client() as client:
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": f"BeArEr {token}"},
            )
            assert resp.status_code != 401 or "scheme not supported" not in resp.get_json().get("error", "")

    def test_unsupported_scheme_basic_rejected(self, app_with_user):
        """'Basic' scheme is rejected with 401 and proper error."""
        app, user_info, db = app_with_user
        with app.test_client() as client:
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": "Basic dXNlcjpwYXNz"},
            )
            assert resp.status_code == 401
            assert resp.get_json()["error"] == "Authentication scheme not supported"

    def test_unsupported_scheme_digest_rejected(self, app_with_user):
        """'Digest' scheme is rejected with 401 and proper error."""
        app, user_info, db = app_with_user
        with app.test_client() as client:
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": "Digest username=test"},
            )
            assert resp.status_code == 401
            assert resp.get_json()["error"] == "Authentication scheme not supported"

    def test_unsupported_scheme_random_rejected(self, app_with_user):
        """A completely random scheme is rejected with 401."""
        app, user_info, db = app_with_user
        with app.test_client() as client:
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": "CustomScheme abc123"},
            )
            assert resp.status_code == 401
            assert resp.get_json()["error"] == "Authentication scheme not supported"


class TestBearerTokenValueValidation:
    """Tests for empty/whitespace token value (Req 7.4, 2.7)."""

    def test_empty_bearer_value_rejected(self, app_with_user):
        """'Bearer ' with no token value is rejected."""
        app, user_info, db = app_with_user
        with app.test_client() as client:
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": "Bearer "},
            )
            assert resp.status_code == 401
            assert resp.get_json()["error"] == "Bearer token value is missing"

    def test_bearer_only_no_space_rejected(self, app_with_user):
        """'Bearer' with no trailing space or value is rejected."""
        app, user_info, db = app_with_user
        with app.test_client() as client:
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": "Bearer"},
            )
            assert resp.status_code == 401
            assert resp.get_json()["error"] == "Bearer token value is missing"

    def test_bearer_whitespace_only_value_rejected(self, app_with_user):
        """'Bearer    ' with only whitespace value is rejected."""
        app, user_info, db = app_with_user
        with app.test_client() as client:
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": "Bearer    "},
            )
            assert resp.status_code == 401
            assert resp.get_json()["error"] == "Bearer token value is missing"


class TestValidTokenAuthentication:
    """Tests for valid token authentication (Req 2.1, 2.5)."""

    def test_valid_token_sets_g_current_user(self, token_for_user):
        """A valid bearer token authenticates the request and sets g.current_user."""
        app, token, user_info = token_for_user

        # Use a simple route to test that auth passes
        @app.route("/api/test-auth-info")
        def test_auth_info():
            from flask import g, jsonify
            current_user = getattr(g, "current_user", None)
            if current_user:
                return jsonify(current_user)
            return jsonify({"error": "No current_user"}), 500

        with app.test_client() as client:
            resp = client.get(
                "/api/test-auth-info",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["user_id"] == user_info["id"]
            assert data["username"] == user_info["username"]
            assert data["display_name"] == user_info["display_name"]
            assert data["role"] == "user"

    def test_valid_token_allows_api_access(self, token_for_user):
        """A valid bearer token allows access to protected API endpoints."""
        app, token, user_info = token_for_user
        with app.test_client() as client:
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": f"Bearer {token}"},
            )
            # Should get 200 (empty list) not 401
            assert resp.status_code == 200


class TestInvalidTokenAuthentication:
    """Tests for invalid/revoked/expired tokens (Req 2.2, 2.3, 2.4)."""

    def test_invalid_token_returns_401(self, app_with_user):
        """An unrecognized token returns 401 with 'Invalid API token'."""
        app, user_info, db = app_with_user
        with app.test_client() as client:
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": "Bearer invalidtoken123456"},
            )
            assert resp.status_code == 401
            assert resp.get_json()["error"] == "Invalid API token"

    def test_revoked_token_returns_401(self, app_with_user):
        """A revoked token returns 401 with 'Token has been revoked'."""
        app, user_info, db = app_with_user
        token_service = TokenService(db)
        result = token_service.create_token(user_info["id"], "revoked-token")
        raw_token = result["token"]
        token_service.revoke_token(user_info["id"], result["id"])

        with app.test_client() as client:
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": f"Bearer {raw_token}"},
            )
            assert resp.status_code == 401
            assert resp.get_json()["error"] == "Token has been revoked"

    def test_expired_token_returns_401(self, app_with_user):
        """An expired token returns 401 with 'Token has expired'."""
        app, user_info, db = app_with_user
        token_service = TokenService(db)

        # Create a token and manually set its expiry to the past
        result = token_service.create_token(user_info["id"], "expired-token", expires_in_days=1)
        raw_token = result["token"]

        # Manually update the expires_at to be in the past
        past_expiry = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        cursor = db.conn.cursor()
        cursor.execute(
            "UPDATE api_tokens SET expires_at = ? WHERE id = ?",
            (past_expiry, result["id"]),
        )
        db.conn.commit()

        with app.test_client() as client:
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": f"Bearer {raw_token}"},
            )
            assert resp.status_code == 401
            assert resp.get_json()["error"] == "Token has expired"


class TestSessionPrecedence:
    """Tests for session cookie taking precedence over bearer token (Req 7.3)."""

    def test_session_takes_precedence_over_bearer_in_non_testing_mode(self, tmp_path):
        """When both session and bearer are present, session wins (Req 7.3).

        This test disables TESTING mode to verify full auth gate behavior.
        """
        db_path = str(tmp_path / "precedence_test.db")
        app = create_app(db_path=db_path)
        # NOT setting TESTING=True here to test full auth gate

        db = app.config["db"]
        from werkzeug.security import generate_password_hash

        password_hash = generate_password_hash("testpass")
        cursor = db.conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, display_name, teammate_name) "
            "VALUES (?, ?, ?, ?)",
            ("sessuser", password_hash, "Session User", ""),
        )
        db.conn.commit()
        user_id = cursor.lastrowid

        # Set up team context so team middleware doesn't block
        team_result = db.create_team("TST001", "Test Team", user_id)
        team_id = team_result["id"]

        with app.test_client() as client:
            # Log in to get session cookie
            resp = client.post(
                "/api/auth/login",
                json={"username": "sessuser", "password": "testpass"},
            )
            assert resp.status_code == 200

            # Set active team in session
            with client.session_transaction() as sess:
                sess["active_team_id"] = team_id

            # Now make a request with both session cookie AND an invalid bearer token
            # Session should take precedence, so the invalid bearer should be ignored
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": "Bearer totally_invalid_token"},
            )
            # If session takes precedence, this should succeed (200 not 401)
            assert resp.status_code == 200


class TestExistingBehaviorPreserved:
    """Tests to ensure existing auth behavior is unchanged (Req 2.6)."""

    def test_session_auth_still_works(self, tmp_path):
        """Session-based authentication continues to work unchanged."""
        db_path = str(tmp_path / "existing_test.db")
        app = create_app(db_path=db_path)

        db = app.config["db"]
        from werkzeug.security import generate_password_hash

        password_hash = generate_password_hash("testpass")
        cursor = db.conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, display_name, teammate_name) "
            "VALUES (?, ?, ?, ?)",
            ("existinguser", password_hash, "Existing User", ""),
        )
        db.conn.commit()
        user_id = cursor.lastrowid

        # Set up team context so team middleware doesn't block
        team_result = db.create_team("TST002", "Test Team", user_id)
        team_id = team_result["id"]

        with app.test_client() as client:
            # Log in to get session cookie
            resp = client.post(
                "/api/auth/login",
                json={"username": "existinguser", "password": "testpass"},
            )
            assert resp.status_code == 200

            # Set active team in session
            with client.session_transaction() as sess:
                sess["active_team_id"] = team_id

            # Access protected endpoint with session
            resp = client.get("/api/teammates")
            assert resp.status_code == 200

    def test_unauthenticated_api_request_returns_401(self, tmp_path):
        """API routes without auth return 401 JSON."""
        db_path = str(tmp_path / "noauth_test.db")
        app = create_app(db_path=db_path)
        # NOT setting TESTING=True
        with app.test_client() as client:
            resp = client.get("/api/teammates")
            assert resp.status_code == 401
            assert resp.get_json()["error"] == "Not authenticated"

    def test_public_routes_still_accessible(self, tmp_path):
        """Public routes remain accessible without authentication."""
        db_path = str(tmp_path / "public_test.db")
        app = create_app(db_path=db_path)
        # NOT setting TESTING=True
        with app.test_client() as client:
            resp = client.get("/health")
            assert resp.status_code == 200

            resp = client.get("/api/public/teammate-names")
            assert resp.status_code == 200
