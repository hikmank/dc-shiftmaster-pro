"""Unit tests for API Token Routes.

Tests specific examples and edge cases for the token management endpoints.
Requirements: 1.6, 3.3, 4.3, 4.5, 5.5, 7.3
"""

import pytest

from dc_shiftmaster_html.server import create_app


@pytest.fixture
def app(tmp_path):
    """Create a Flask test app with a fresh temp database."""
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    # Register the tokens blueprint (not yet wired in server.py per task 6.1)
    from dc_shiftmaster_html.routes_tokens import tokens_bp

    if "tokens" not in app.blueprints:
        app.register_blueprint(tokens_bp)

    return app


@pytest.fixture
def client(app):
    """Return a test client for the app."""
    return app.test_client()


@pytest.fixture
def authenticated_user(app, client):
    """Create a user and set up a session-authenticated client.

    Returns the user_id for reference.
    """
    db = app.config["db"]
    user_id = db.create_user(
        username="testuser",
        password_hash="fakehash",
        display_name="Test User",
    )
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    return user_id


class TestCreateTokenNoExpiration:
    """Test: Create token with no expiration returns expires_at null (Req 1.6)."""

    def test_create_token_no_expiration_returns_null_expires_at(
        self, client, authenticated_user
    ):
        """WHEN no expiration duration is provided, the token SHALL have expires_at null."""
        resp = client.post(
            "/api/auth/tokens",
            json={"label": "my-automation-token"},
        )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["expires_at"] is None
        # Ensure other fields are present
        assert "id" in data
        assert "token" in data
        assert "label" in data
        assert data["label"] == "my-automation-token"
        assert "created_at" in data


class TestEmptyTokenList:
    """Test: User with no tokens gets empty list with 200 (Req 3.3)."""

    def test_user_with_no_tokens_gets_empty_list(self, client, authenticated_user):
        """WHEN an authenticated user has no tokens, return empty data array with 200."""
        resp = client.get("/api/auth/tokens")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"data": [], "meta": {"total": 0}}


class TestRevokeNonExistent:
    """Test: Revoking non-existent token ID returns 404 (Req 4.3)."""

    def test_revoke_nonexistent_token_returns_404(self, client, authenticated_user):
        """IF token ID does not exist, return 404 with 'Token not found' error."""
        resp = client.delete("/api/auth/tokens/99999")

        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data
        assert "not found" in data["error"].lower()


class TestUnauthenticatedRevocation:
    """Test: Unauthenticated revocation attempt returns 401 (Req 4.5)."""

    def test_unauthenticated_revoke_returns_401(self, client):
        """IF an unauthenticated request is sent to revoke, return 401."""
        # Do NOT set up a session — the client is unauthenticated
        resp = client.delete("/api/auth/tokens/1")

        assert resp.status_code == 401
        data = resp.get_json()
        assert "error" in data
        assert "not authenticated" in data["error"].lower()


class TestSessionPrecedenceOverBearer:
    """Test: Session cookie takes precedence over bearer token (Req 7.3)."""

    def test_session_cookie_takes_precedence_over_invalid_bearer(self, tmp_path):
        """WHEN both a valid session cookie and an invalid Bearer token are present,
        the session cookie SHALL be used for authentication and the token ignored.

        This test uses a non-TESTING app to exercise the full auth gate logic,
        since TESTING mode skips session checks and processes bearer tokens directly.
        """
        from dc_shiftmaster_html.routes_tokens import tokens_bp

        db_path = str(tmp_path / "precedence_test.db")
        precedence_app = create_app(db_path=db_path)
        # Do NOT set TESTING = True — we need the full auth gate logic

        if "tokens" not in precedence_app.blueprints:
            precedence_app.register_blueprint(tokens_bp)

        with precedence_app.test_client() as precedence_client:
            db = precedence_app.config["db"]
            user_id = db.create_user(
                username="sessionuser",
                password_hash="fakehash",
                display_name="Session User",
            )

            # Set up session authentication
            with precedence_client.session_transaction() as sess:
                sess["user_id"] = user_id

            # Send request with both session cookie AND an invalid Bearer token
            resp = precedence_client.get(
                "/api/auth/tokens",
                headers={"Authorization": "Bearer invalid_token_value_here"},
            )

            # Should succeed because session cookie takes precedence (Req 7.3)
            assert resp.status_code == 200, (
                f"Expected 200 (session precedence), got {resp.status_code}: "
                f"{resp.get_json()}"
            )
            data = resp.get_json()
            assert "data" in data


class TestRateLimiting:
    """Test: 6th request within 60s returns 429 (Req 5.5)."""

    def test_rate_limit_on_6th_token_creation(self, app, tmp_path):
        """IF more than 5 token creation requests within 60s, the 6th returns 429."""
        # Create a separate app with rate limiting enabled (not TESTING mode)
        db_path = str(tmp_path / "rate_limit_test.db")
        rate_app = create_app(db_path=db_path)
        # Do NOT set TESTING = True so rate limiter stays enabled
        # But we need to bypass auth gate for the test
        rate_app.config["TESTING"] = True

        from dc_shiftmaster_html.extensions import limiter
        from dc_shiftmaster_html.routes_tokens import tokens_bp

        if "tokens" not in rate_app.blueprints:
            rate_app.register_blueprint(tokens_bp)

        # Explicitly enable the limiter (TESTING=True disables it)
        limiter.enabled = True

        try:
            with rate_app.test_client() as rate_client:
                db = rate_app.config["db"]
                user_id = db.create_user(
                    username="ratelimituser",
                    password_hash="fakehash",
                    display_name="Rate Limit User",
                )

                with rate_client.session_transaction() as sess:
                    sess["user_id"] = user_id

                # Send 5 requests (should all succeed)
                for i in range(5):
                    resp = rate_client.post(
                        "/api/auth/tokens",
                        json={"label": f"rate-limit-token-{i}"},
                    )
                    assert resp.status_code == 201, (
                        f"Request {i + 1} failed with status {resp.status_code}: "
                        f"{resp.get_json()}"
                    )

                # 6th request should be rate limited
                resp = rate_client.post(
                    "/api/auth/tokens",
                    json={"label": "rate-limit-token-6"},
                )
                assert resp.status_code == 429, (
                    f"Expected 429 on 6th request, got {resp.status_code}: "
                    f"{resp.get_json()}"
                )
        finally:
            # Reset limiter to disabled so other tests aren't affected
            limiter.enabled = False
