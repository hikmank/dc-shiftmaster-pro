"""Integration tests for end-to-end API token authentication flows.

Tests:
  1. Create token → use token for API call → verify access
  2. Create token → revoke token → attempt API call → verify 401
  3. Database migration creates table and indexes idempotently

Validates: Requirements 1.1, 2.1, 2.3, 4.1, 6.3
"""

import pytest

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster_html.server import create_app


@pytest.fixture
def app(tmp_path):
    """Create a Flask test app with a fresh temp database."""
    db_path = str(tmp_path / "test_integration.db")
    application = create_app(db_path=db_path)
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    """Provide a Flask test client."""
    return app.test_client()


@pytest.fixture
def auth_user(app, client):
    """Create a user and return (user_id, client) with session set.

    Registers a user and sets session so token management endpoints work.
    """
    db = app.config["db"]
    # Create a user directly in the database
    from werkzeug.security import generate_password_hash

    password_hash = generate_password_hash("testpass123")
    user_id = db.create_user(
        username="integrationuser",
        password_hash=password_hash,
        display_name="Integration User",
    )

    # Set up the session on the client
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = "integrationuser"
        sess["display_name"] = "Integration User"

    return user_id, client


class TestCreateAndUseToken:
    """Test 1: Create token → use token for API call → verify access."""

    def test_create_token_and_authenticate_api_call(self, app, auth_user):
        """Full flow: create a token, then use it to access a protected endpoint."""
        user_id, client = auth_user

        # Step 1: Create a token via POST /api/auth/tokens
        resp = client.post(
            "/api/auth/tokens",
            json={"label": "CI Token"},
            content_type="application/json",
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"
        data = resp.get_json()
        assert "token" in data
        assert "id" in data
        assert data["label"] == "CI Token"
        plaintext_token = data["token"]
        assert len(plaintext_token) == 64  # 32 bytes hex-encoded

        # Step 2: Use the token to access a protected API endpoint
        # Clear session to ensure we're testing token auth only
        with client.session_transaction() as sess:
            sess.clear()

        # The auth gate in TESTING mode processes bearer tokens via
        # _process_bearer_auth but doesn't enforce session-only login
        resp = client.get(
            "/api/teammates",
            headers={"Authorization": f"Bearer {plaintext_token}"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"


class TestCreateRevokeAndReject:
    """Test 2: Create token → revoke token → attempt API call → verify 401."""

    def test_create_revoke_then_reject(self, app, auth_user):
        """Full flow: create, revoke, then verify the revoked token is rejected."""
        user_id, client = auth_user

        # Step 1: Create a token
        resp = client.post(
            "/api/auth/tokens",
            json={"label": "Revoke Test Token"},
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        plaintext_token = data["token"]
        token_id = data["id"]

        # Step 2: Revoke the token via DELETE /api/auth/tokens/<token_id>
        resp = client.delete(f"/api/auth/tokens/{token_id}")
        assert resp.status_code == 204, f"Expected 204, got {resp.status_code}: {resp.data}"

        # Step 3: Attempt to use the revoked token
        with client.session_transaction() as sess:
            sess.clear()

        resp = client.get(
            "/api/teammates",
            headers={"Authorization": f"Bearer {plaintext_token}"},
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.data}"
        error_data = resp.get_json()
        assert error_data["error"] == "Token has been revoked"


class TestDatabaseMigrationIdempotency:
    """Test 3: Database migration creates table and indexes idempotently."""

    def test_create_tables_idempotent(self, tmp_path):
        """Calling _create_tables() multiple times should not error or lose data."""
        db_path = str(tmp_path / "test_idempotent.db")

        # First creation
        db = DatabaseManager(db_path)

        # Insert a token record to verify data persists
        user_id = db.create_user(
            username="idempotent_user",
            password_hash="hash123",
            display_name="Idempotent User",
        )
        db.create_api_token(
            user_id=user_id,
            token_hash="abc123def456",
            label="Test Token",
        )

        # Call _create_tables() again (simulates app restart)
        db._create_tables()

        # Verify no errors and data still exists
        tokens = db.get_api_tokens_for_user(user_id)
        assert len(tokens) == 1
        assert tokens[0]["label"] == "Test Token"

    def test_api_tokens_table_exists_with_correct_structure(self, tmp_path):
        """Verify the api_tokens table has the correct columns."""
        db_path = str(tmp_path / "test_structure.db")
        db = DatabaseManager(db_path)

        cursor = db.conn.cursor()
        cursor.execute("PRAGMA table_info(api_tokens)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        # Verify expected columns exist
        assert "id" in columns
        assert "user_id" in columns
        assert "token_hash" in columns
        assert "label" in columns
        assert "created_at" in columns
        assert "expires_at" in columns
        assert "revoked" in columns
        assert "last_used_at" in columns

    def test_indexes_exist(self, tmp_path):
        """Verify indexes on token_hash and user_id are present."""
        db_path = str(tmp_path / "test_indexes.db")
        db = DatabaseManager(db_path)

        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='api_tokens'"
        )
        index_names = {row[0] for row in cursor.fetchall()}

        assert "idx_api_tokens_hash" in index_names
        assert "idx_api_tokens_user_id" in index_names

    def test_second_migration_no_error(self, tmp_path):
        """A second DatabaseManager on the same DB should not raise."""
        db_path = str(tmp_path / "test_second.db")

        # First init creates tables
        db1 = DatabaseManager(db_path)
        db1.conn.close()

        # Second init should not raise (IF NOT EXISTS clauses)
        db2 = DatabaseManager(db_path)
        # Verify the table is intact
        cursor = db2.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='api_tokens'"
        )
        assert cursor.fetchone()[0] == 1
        db2.conn.close()
