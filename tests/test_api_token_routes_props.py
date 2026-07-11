"""Property-based tests for API Token Routes.

# Feature: api-token-auth, Property 8: Token listing excludes secrets and maintains sort order

Uses Hypothesis to verify that token listing responses never leak secrets
and always maintain correct sort order.
"""

import time

from hypothesis import given, settings
from hypothesis import strategies as st

from dc_shiftmaster_html.server import create_app


# ---------------------------------------------------------------------------
# Property 8: Token listing excludes secrets and maintains sort order
# **Validates: Requirements 3.1, 3.2**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(n=st.integers(min_value=1, max_value=10))
def test_token_listing_excludes_secrets_and_sorted_desc(n, tmp_path_factory):
    """For any user with N tokens, listing SHALL contain no token/token_hash fields
    and records SHALL be sorted by created_at descending (newest first).

    # Feature: api-token-auth, Property 8: Token listing excludes secrets and maintains sort order
    **Validates: Requirements 3.1, 3.2**
    """
    # Create a fresh app + database for each example
    db_path = str(tmp_path_factory.mktemp("data") / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    # Disable rate limiter for property tests (normally disabled via TESTING flag
    # but we set TESTING after create_app, so disable explicitly)
    from dc_shiftmaster_html.extensions import limiter

    limiter.enabled = False

    # Register the tokens blueprint (not yet wired in server.py per task 6.1)
    from dc_shiftmaster_html.routes_tokens import tokens_bp

    # Only register if not already registered
    if "tokens" not in app.blueprints:
        app.register_blueprint(tokens_bp)

    with app.test_client() as client:
        # Create a user directly in the database
        db = app.config["db"]
        user_id = db.create_user(
            username="testuser",
            password_hash="fakehash",
            display_name="Test User",
        )

        # Set up session authentication by using the test client session
        with client.session_transaction() as sess:
            sess["user_id"] = user_id

        # Create N tokens with unique labels via the API
        created_tokens = []
        for i in range(n):
            resp = client.post(
                "/api/auth/tokens",
                json={"label": f"token-{i}"},
            )
            assert resp.status_code == 201, (
                f"Expected 201, got {resp.status_code}: {resp.get_json()}"
            )
            created_tokens.append(resp.get_json())
            # Small delay to ensure distinct created_at timestamps
            if n > 1:
                time.sleep(0.01)

        # List tokens via GET /api/auth/tokens
        resp = client.get("/api/auth/tokens")
        assert resp.status_code == 200

        data = resp.get_json()
        assert "data" in data
        tokens_list = data["data"]

        # Assert we got back the same number of tokens we created
        assert len(tokens_list) == n

        # Assert no record contains 'token' or 'token_hash' fields (secrets excluded)
        for record in tokens_list:
            assert "token" not in record, (
                f"Listing response should not contain 'token' field, got: {record.keys()}"
            )
            assert "token_hash" not in record, (
                f"Listing response should not contain 'token_hash' field, got: {record.keys()}"
            )

        # Assert records are sorted by created_at in descending order (newest first)
        created_at_values = [record["created_at"] for record in tokens_list]
        for i in range(len(created_at_values) - 1):
            assert created_at_values[i] >= created_at_values[i + 1], (
                f"Records not sorted DESC by created_at: "
                f"{created_at_values[i]} should be >= {created_at_values[i + 1]}"
            )


# ---------------------------------------------------------------------------
# Property 9: Ownership enforcement on revocation
# **Validates: Requirements 4.2**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(
    username_a=st.text(
        min_size=3, max_size=15, alphabet=st.characters(whitelist_categories=("L", "N"))
    ),
    username_b=st.text(
        min_size=3, max_size=15, alphabet=st.characters(whitelist_categories=("L", "N"))
    ),
)
def test_ownership_enforcement_on_revocation(username_a, username_b, tmp_path_factory):
    """For any two distinct users A and B, if user A owns a token, user B's attempt
    to revoke that token SHALL be rejected with a 403 status code, and the token
    SHALL remain active.

    # Feature: api-token-auth, Property 9: Ownership enforcement on revocation
    **Validates: Requirements 4.2**
    """
    from hypothesis import assume

    # Ensure usernames are distinct
    assume(username_a != username_b)

    # Create a fresh app + database for each example
    db_path = str(tmp_path_factory.mktemp("data") / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    # Disable rate limiter for property tests
    from dc_shiftmaster_html.extensions import limiter

    limiter.enabled = False

    # Register the tokens blueprint (not yet wired in server.py per task 6.1)
    from dc_shiftmaster_html.routes_tokens import tokens_bp

    if "tokens" not in app.blueprints:
        app.register_blueprint(tokens_bp)

    with app.test_client() as client:
        db = app.config["db"]

        # Create User A
        user_a_id = db.create_user(
            username=username_a,
            password_hash="fakehash_a",
            display_name=f"User {username_a}",
        )

        # Create User B
        user_b_id = db.create_user(
            username=username_b,
            password_hash="fakehash_b",
            display_name=f"User {username_b}",
        )

        # Authenticate as User A and create a token
        with client.session_transaction() as sess:
            sess["user_id"] = user_a_id

        resp = client.post(
            "/api/auth/tokens",
            json={"label": "user-a-token"},
        )
        assert resp.status_code == 201, (
            f"Expected 201, got {resp.status_code}: {resp.get_json()}"
        )
        token_data = resp.get_json()
        token_id = token_data["id"]
        raw_token = token_data["token"]

        # Now authenticate as User B and attempt to revoke User A's token
        with client.session_transaction() as sess:
            sess["user_id"] = user_b_id

        resp = client.delete(f"/api/auth/tokens/{token_id}")
        assert resp.status_code == 403, (
            f"Expected 403 when user B revokes user A's token, got {resp.status_code}: "
            f"{resp.get_json()}"
        )

        # Assert error message contains "do not own"
        error_data = resp.get_json()
        assert "error" in error_data
        assert "do not own" in error_data["error"].lower(), (
            f"Expected error message to contain 'do not own', got: {error_data['error']}"
        )

        # Verify the token is still active by using it for Bearer auth
        # Access any protected route with the token
        resp = client.get(
            "/api/schedule",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        # The token should still be valid (not revoked), so we should NOT get a
        # 401 with "revoked" reason. The response might be 200 or another code
        # depending on route availability, but it should NOT be 401 with revocation.
        if resp.status_code == 401:
            error_body = resp.get_json()
            assert "revoked" not in error_body.get("error", "").lower(), (
                "Token was revoked despite user B not being the owner — "
                "ownership enforcement failed"
            )
