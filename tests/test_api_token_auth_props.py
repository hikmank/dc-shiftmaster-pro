"""Property-based tests for API Token Authentication - Auth Gate Properties.

# Feature: api-token-auth, Property 5: Valid token authenticates as the token owner
# Feature: api-token-auth, Property 10: Bearer scheme is case-insensitive and non-bearer schemes are rejected

Uses Hypothesis to verify auth gate behavior across many input variations.
"""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from dc_shiftmaster_html.server import create_app
from dc_shiftmaster_html.token_service import TokenService


# ---------------------------------------------------------------------------
# Property 5: Valid token authenticates as the token owner
# **Validates: Requirements 2.1, 2.5**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(
    username=st.text(
        min_size=3, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))
    ),
    display_name=st.text(
        min_size=3, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))
    ),
)
def test_valid_token_authenticates_as_token_owner(username, display_name, tmp_path_factory):
    """For any user with a valid token, Bearer auth returns the correct identity.

    Create a user with a generated username/display_name, create a token for them,
    send a request with Authorization: Bearer <token>, and assert:
    - The response is 200 (auth succeeded)
    - g.current_user contains the correct user_id, username, display_name, role

    # Feature: api-token-auth, Property 5: Valid token authenticates as the token owner
    **Validates: Requirements 2.1, 2.5**
    """
    # 1. Create a fresh app + database for each example
    db_path = str(tmp_path_factory.mktemp("data") / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    db = app.config["db"]

    # 2. Create a user with the Hypothesis-generated username/display_name
    user_id = db.create_user(
        username=username,
        password_hash="fakehash",
        display_name=display_name,
    )

    # 3. Create a token for that user
    token_service = TokenService(db)
    result = token_service.create_token(user_id=user_id, label="prop-test-token")
    raw_token = result["token"]

    # 4. Add a test route that returns g.current_user info
    @app.route("/api/test-identity")
    def test_identity():
        from flask import g, jsonify
        current_user = getattr(g, "current_user", None)
        if current_user:
            return jsonify(current_user)
        return jsonify({"error": "No current_user set"}), 500

    # 5. Make a request with Authorization: Bearer <token>
    with app.test_client() as client:
        resp = client.get(
            "/api/test-identity",
            headers={"Authorization": f"Bearer {raw_token}"},
        )

        # 6. Assert the response is successful (200)
        assert resp.status_code == 200, (
            f"Expected 200 but got {resp.status_code}: {resp.get_json()}"
        )

        data = resp.get_json()

        # 7. Assert g.current_user contains the correct identity
        assert data["user_id"] == user_id, (
            f"Expected user_id={user_id}, got {data['user_id']}"
        )
        assert data["username"] == username, (
            f"Expected username='{username}', got '{data['username']}'"
        )
        assert data["display_name"] == display_name, (
            f"Expected display_name='{display_name}', got '{data['display_name']}'"
        )
        assert data["role"] == "user", (
            f"Expected role='user', got '{data['role']}'"
        )


# ---------------------------------------------------------------------------
# Custom strategy: random case variations of "bearer"
# ---------------------------------------------------------------------------

@st.composite
def bearer_case_variation(draw):
    """Generate a random case variation of the word 'bearer'.

    Each character is independently randomized to upper or lower case,
    producing strings like 'BEARER', 'bearer', 'BeArEr', 'bEaReR', etc.
    """
    base = "bearer"
    result = []
    for char in base:
        upper = draw(st.booleans())
        result.append(char.upper() if upper else char.lower())
    return "".join(result)


# ---------------------------------------------------------------------------
# Property 10: Bearer scheme is case-insensitive and non-bearer schemes are rejected
# **Validates: Requirements 7.1, 7.2**
# ---------------------------------------------------------------------------


class TestBearerSchemeCaseInsensitiveProperty:
    """Property 10: Bearer scheme is case-insensitive and non-bearer schemes are rejected.

    For any case variation of the string "Bearer" (e.g., "bearer", "BEARER", "BeArEr"),
    the auth gate SHALL accept it as a valid scheme. For any string that is not a
    case-insensitive match for "Bearer", the auth gate SHALL reject the request with
    401 indicating an unsupported scheme.

    # Feature: api-token-auth, Property 10: Bearer scheme is case-insensitive and non-bearer schemes are rejected
    **Validates: Requirements 7.1, 7.2**
    """

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        """Set up a Flask app with a test user and a valid token for each test."""
        db_path = str(tmp_path / "prop10_test.db")
        self.app = create_app(db_path=db_path)
        self.app.config["TESTING"] = True

        db = self.app.config["db"]
        from werkzeug.security import generate_password_hash

        password_hash = generate_password_hash("testpass")
        cursor = db.conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, display_name, teammate_name) "
            "VALUES (?, ?, ?, ?)",
            ("prop10user", password_hash, "Property 10 User", ""),
        )
        db.conn.commit()
        self.user_id = cursor.lastrowid

        token_service = TokenService(db)
        result = token_service.create_token(self.user_id, "prop10-token")
        self.valid_token = result["token"]

    @given(scheme=bearer_case_variation())
    @settings(max_examples=100)
    def test_case_insensitive_bearer_accepted(self, scheme):
        """Random case variations of 'bearer' are accepted as a valid scheme.

        # Feature: api-token-auth, Property 10: Bearer scheme is case-insensitive and non-bearer schemes are rejected
        **Validates: Requirements 7.1, 7.2**
        """
        with self.app.test_client() as client:
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": f"{scheme} {self.valid_token}"},
            )
            # The request should NOT be rejected with "Authentication scheme not supported"
            # It should either succeed (200) or fail for other reasons (not scheme rejection)
            if resp.status_code == 401:
                error_msg = resp.get_json().get("error", "")
                assert error_msg != "Authentication scheme not supported", (
                    f"Scheme '{scheme}' was incorrectly rejected as unsupported"
                )

    @given(
        scheme=st.text(
            min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L",))
        )
    )
    @settings(max_examples=100)
    def test_non_bearer_schemes_rejected(self, scheme):
        """Random non-bearer scheme strings are rejected with 401 and proper error.

        # Feature: api-token-auth, Property 10: Bearer scheme is case-insensitive and non-bearer schemes are rejected
        **Validates: Requirements 7.1, 7.2**
        """
        assume(scheme.lower() != "bearer")

        with self.app.test_client() as client:
            resp = client.get(
                "/api/teammates",
                headers={"Authorization": f"{scheme} sometoken"},
            )
            assert resp.status_code == 401, (
                f"Expected 401 for unsupported scheme '{scheme}', got {resp.status_code}"
            )
            error_msg = resp.get_json()["error"]
            assert error_msg == "Authentication scheme not supported", (
                f"Expected 'Authentication scheme not supported' for scheme '{scheme}', "
                f"got '{error_msg}'"
            )


# ---------------------------------------------------------------------------
# Property 6: Revocation invalidates authentication
# **Validates: Requirements 2.3, 4.1, 4.4**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(
    label=st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(whitelist_categories=("L", "N")),
    )
)
def test_revocation_invalidates_authentication(label, tmp_path_factory):
    """For any token that has been revoked, auth attempts return 401 with revocation message.

    Create a user, create a token with a generated label, revoke it via
    TokenService.revoke_token(), then attempt authentication with the revoked token.
    Assert:
    - The response is 401
    - The error message is "Token has been revoked"

    # Feature: api-token-auth, Property 6: Revocation invalidates authentication
    **Validates: Requirements 2.3, 4.1, 4.4**
    """
    # 1. Create a fresh app + database for each example
    db_path = str(tmp_path_factory.mktemp("data") / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    db = app.config["db"]

    # 2. Create a user
    user_id = db.create_user(
        username="revokeuser",
        password_hash="fakehash",
        display_name="Revoke User",
    )

    # 3. Create a token with the Hypothesis-generated label
    token_service = TokenService(db)
    result = token_service.create_token(user_id=user_id, label=label)
    raw_token = result["token"]
    token_id = result["id"]

    # 4. Revoke the token
    token_service.revoke_token(user_id=user_id, token_id=token_id)

    # 5. Attempt to authenticate with the revoked token
    with app.test_client() as client:
        resp = client.get(
            "/api/teammates",
            headers={"Authorization": f"Bearer {raw_token}"},
        )

        # 6. Assert response is 401
        assert resp.status_code == 401, (
            f"Expected 401 but got {resp.status_code}: {resp.get_json()}"
        )

        # 7. Assert error message indicates revocation
        data = resp.get_json()
        assert data["error"] == "Token has been revoked", (
            f"Expected error 'Token has been revoked', got '{data['error']}'"
        )
