"""Property-based tests for API Token Authentication.

# Feature: api-token-auth, Property 2: Token hash storage round-trip

Uses Hypothesis to verify token hash storage invariants across many inputs.
"""

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster_html.token_service import TokenService


# ---------------------------------------------------------------------------
# Property 2: Token hash storage round-trip
# **Validates: Requirements 1.3, 5.1**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(
    label=st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(whitelist_categories=("L", "N")),
    )
)
def test_token_hash_storage_round_trip(label, tmp_path_factory):
    """For any created token, the stored hash equals SHA-256(plaintext) and hash ≠ plaintext.

    Additionally, validate_token(plaintext) locates the correct record.

    # Feature: api-token-auth, Property 2: Token hash storage round-trip
    **Validates: Requirements 1.3, 5.1**
    """
    # Set up a fresh database for each example
    db_path = str(tmp_path_factory.mktemp("data") / "test.db")
    db = DatabaseManager(db_path)

    try:
        # Create a test user
        user_id = db.create_user(
            username="testuser",
            password_hash="fakehash",
            display_name="Test User",
        )

        # Create a token via TokenService
        service = TokenService(db)
        result = service.create_token(user_id=user_id, label=label)

        plaintext = result["token"]

        # Compute the expected hash
        expected_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()

        # Read the DB row directly to verify stored hash
        token_record = db.get_api_token_by_hash(expected_hash)

        # Assert stored hash matches SHA-256(plaintext)
        assert token_record is not None, "Token record not found by expected hash"
        assert token_record["token_hash"] == expected_hash

        # Assert hash ≠ plaintext (one-way hashing)
        assert token_record["token_hash"] != plaintext

        # Validate that validate_token(plaintext) locates the correct record
        user = service.validate_token(plaintext)
        assert user is not None, "validate_token should return the owning user"
        assert user.id == user_id
    finally:
        db.conn.close()


# Feature: api-token-auth, Property 3: Invalid labels are rejected
class TestInvalidLabelsRejectedProperty:
    """Property 3: Invalid labels are rejected.

    For any string that is empty, composed entirely of whitespace characters,
    or longer than 128 characters, attempting to create a token with that string
    as the label SHALL be rejected with a ValueError and the token count SHALL
    remain unchanged.

    **Validates: Requirements 1.4**
    """

    def _make_service(self, tmp_path_factory):
        """Create a fresh TokenService backed by a temp-file database."""
        from dc_shiftmaster.database import DatabaseManager

        db_path = str(tmp_path_factory.mktemp("data") / "test.db")
        db = DatabaseManager(db_path)
        service = TokenService(db)
        user_id = db.create_user("propuser", "hashed_pw", "Property User")
        return service, db, user_id

    @given(
        whitespace_label=st.text(
            alphabet=" \t\n\r", min_size=1, max_size=50
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_whitespace_only_labels_are_rejected(self, whitespace_label, tmp_path_factory):
        """Whitespace-only strings are rejected with ValueError and token count stays 0."""
        service, db, user_id = self._make_service(tmp_path_factory)

        import pytest

        with pytest.raises(ValueError):
            service.create_token(user_id, whitespace_label)

        assert service.count_active_tokens(user_id) == 0

    @given(
        long_label=st.text(min_size=129, max_size=200)
    )
    @settings(max_examples=100, deadline=None)
    def test_labels_longer_than_128_chars_are_rejected(self, long_label, tmp_path_factory):
        """Strings longer than 128 characters are rejected with ValueError and token count stays 0."""
        service, db, user_id = self._make_service(tmp_path_factory)

        import pytest

        with pytest.raises(ValueError):
            service.create_token(user_id, long_label)

        assert service.count_active_tokens(user_id) == 0

    def test_empty_string_label_is_rejected(self, tmp_path_factory):
        """Empty string is rejected with ValueError and token count stays 0."""
        from dc_shiftmaster.database import DatabaseManager

        import pytest

        db_path = str(tmp_path_factory.mktemp("data") / "test.db")
        db = DatabaseManager(db_path)
        service = TokenService(db)
        user_id = db.create_user("emptyuser", "hashed_pw", "Empty User")

        with pytest.raises(ValueError):
            service.create_token(user_id, "")

        assert service.count_active_tokens(user_id) == 0


# ---------------------------------------------------------------------------
# Feature: api-token-auth, Property 4: Expiration duration produces correct expiry timestamp
# ---------------------------------------------------------------------------


class TestExpirationDurationProperty:
    """Property 4: Expiration duration produces correct expiry timestamp.

    For any integer N in [1, 365], creating a token with expires_in_days=N SHALL
    produce an expires_at timestamp that is exactly N days after created_at.
    For any value outside [1, 365] (zero, negative, >365, or non-integer),
    creation SHALL be rejected.

    **Validates: Requirements 1.5**
    """

    def _make_service(self, tmp_path_factory):
        """Create a fresh TokenService backed by a temp-file database."""
        db_path = str(tmp_path_factory.mktemp("data") / "test.db")
        db = DatabaseManager(db_path)
        service = TokenService(db)
        user_id = db.create_user("expuser", "hashed_pw", "Expiry User")
        return service, db, user_id

    @given(n=st.integers(min_value=1, max_value=365))
    @settings(max_examples=100, deadline=None)
    def test_valid_expiration_produces_correct_expiry_timestamp(self, n, tmp_path_factory):
        """For N in [1, 365], expires_at == created_at + N days (within a few seconds tolerance).

        # Feature: api-token-auth, Property 4: Expiration duration produces correct expiry timestamp
        **Validates: Requirements 1.5**
        """
        service, db, user_id = self._make_service(tmp_path_factory)

        try:
            result = service.create_token(user_id=user_id, label="test-token", expires_in_days=n)

            assert result["expires_at"] is not None, "expires_at should not be None for valid N"
            assert result["created_at"] is not None, "created_at should not be None"

            # Parse timestamps
            created_at = datetime.strptime(result["created_at"], "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
            expires_at = datetime.strptime(result["expires_at"], "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )

            # The difference should be exactly N days (within a few seconds tolerance
            # for execution time between created_at and expires_at computation)
            expected_diff = timedelta(days=n)
            actual_diff = expires_at - created_at

            # Allow up to 5 seconds tolerance for execution time
            tolerance = timedelta(seconds=5)
            assert abs(actual_diff - expected_diff) <= tolerance, (
                f"Expected difference of {expected_diff}, got {actual_diff} "
                f"(off by {abs(actual_diff - expected_diff)})"
            )
        finally:
            db.conn.close()

    @given(
        invalid_n=st.one_of(
            st.integers(max_value=0),
            st.integers(min_value=366),
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_invalid_integer_expiration_is_rejected(self, invalid_n, tmp_path_factory):
        """For values outside [1, 365] (zero, negative, >365), creation is rejected with ValueError.

        # Feature: api-token-auth, Property 4: Expiration duration produces correct expiry timestamp
        **Validates: Requirements 1.5**
        """
        service, db, user_id = self._make_service(tmp_path_factory)

        try:
            with pytest.raises(ValueError):
                service.create_token(user_id=user_id, label="test-token", expires_in_days=invalid_n)

            # Token count should remain zero
            assert service.count_active_tokens(user_id) == 0
        finally:
            db.conn.close()

    @given(invalid_float=st.floats())
    @settings(max_examples=100, deadline=None)
    def test_non_integer_expiration_is_rejected(self, invalid_float, tmp_path_factory):
        """Non-integer values (floats) are rejected with ValueError.

        # Feature: api-token-auth, Property 4: Expiration duration produces correct expiry timestamp
        **Validates: Requirements 1.5**
        """
        service, db, user_id = self._make_service(tmp_path_factory)

        try:
            with pytest.raises(ValueError):
                service.create_token(user_id=user_id, label="test-token", expires_in_days=invalid_float)

            # Token count should remain zero
            assert service.count_active_tokens(user_id) == 0
        finally:
            db.conn.close()


# ---------------------------------------------------------------------------
# Feature: api-token-auth, Property 7: Expired tokens are rejected
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(days_in_past=st.integers(min_value=1, max_value=365))
def test_expired_tokens_are_rejected(days_in_past, tmp_path_factory):
    """For any token whose expires_at is in the past, authentication SHALL be rejected
    with a 401 status code and error message "Token has expired".

    # Feature: api-token-auth, Property 7: Expired tokens are rejected
    **Validates: Requirements 2.4**
    """
    from dc_shiftmaster_html.server import create_app

    # Create a fresh app + database for each example
    db_path = str(tmp_path_factory.mktemp("data") / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True
    db = app.config["db"]

    try:
        # Create a test user
        user_id = db.create_user(
            username="tokenuser",
            password_hash="fakehash",
            display_name="Token User",
        )

        # Create a token with a valid expiry (1 day)
        service = TokenService(db)
        result = service.create_token(user_id=user_id, label="test-token", expires_in_days=1)
        raw_token = result["token"]

        # Manually update the expires_at in the database to a past time
        past_time = (
            datetime.now(timezone.utc) - timedelta(days=days_in_past)
        ).strftime("%Y-%m-%d %H:%M:%S")
        db.conn.execute(
            "UPDATE api_tokens SET expires_at = ? WHERE id = ?",
            (past_time, result["id"]),
        )
        db.conn.commit()

        # Attempt to authenticate with the expired token
        with app.test_client() as client:
            response = client.get(
                "/api/schedule/2025/1",
                headers={"Authorization": f"Bearer {raw_token}"},
            )

        # Assert 401 response with expiration message
        assert response.status_code == 401, (
            f"Expected 401 for expired token ({days_in_past} days in past), "
            f"got {response.status_code}"
        )
        data = response.get_json()
        assert data is not None, "Response should be JSON"
        assert data.get("error") == "Token has expired", (
            f"Expected error 'Token has expired', got '{data.get('error')}'"
        )
    finally:
        db.conn.close()
