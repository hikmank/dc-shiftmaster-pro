"""Unit tests for API token CRUD methods on DatabaseManager.

Tests the create_api_token, get_api_token_by_hash, get_api_tokens_for_user,
revoke_api_token, update_token_last_used, and count_active_api_tokens methods.
"""

import hashlib
import time
from datetime import datetime, timedelta, timezone

import pytest

from dc_shiftmaster.database import DatabaseManager


@pytest.fixture
def db(tmp_path):
    """Provide a fresh DatabaseManager backed by a temp-file database."""
    db_path = str(tmp_path / "test_tokens.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.conn.close()


@pytest.fixture
def user_id(db):
    """Create a test user and return their ID."""
    return db.create_user("testuser", "hashed_pw", "Test User")


def _hash_token(raw: str) -> str:
    """Helper to compute SHA-256 hex digest."""
    return hashlib.sha256(raw.encode()).hexdigest()


class TestCreateApiToken:
    """Tests for create_api_token."""

    def test_creates_token_and_returns_id(self, db, user_id):
        token_hash = _hash_token("token_abc")
        row_id = db.create_api_token(user_id, token_hash, "My Token")
        assert isinstance(row_id, int)
        assert row_id > 0

    def test_creates_token_with_expires_at(self, db, user_id):
        token_hash = _hash_token("token_exp")
        expires = "2025-06-01 12:00:00"
        row_id = db.create_api_token(user_id, token_hash, "Expiring", expires_at=expires)
        token = db.get_api_token_by_hash(token_hash)
        assert token is not None
        assert token["expires_at"] == expires

    def test_creates_token_without_expires_at(self, db, user_id):
        token_hash = _hash_token("token_noexp")
        row_id = db.create_api_token(user_id, token_hash, "No Expiry")
        token = db.get_api_token_by_hash(token_hash)
        assert token is not None
        assert token["expires_at"] is None

    def test_duplicate_hash_raises_integrity_error(self, db, user_id):
        token_hash = _hash_token("dup_token")
        db.create_api_token(user_id, token_hash, "First")
        with pytest.raises(Exception):  # sqlite3.IntegrityError
            db.create_api_token(user_id, token_hash, "Second")


class TestGetApiTokenByHash:
    """Tests for get_api_token_by_hash."""

    def test_returns_dict_for_existing_token(self, db, user_id):
        token_hash = _hash_token("lookup_token")
        row_id = db.create_api_token(user_id, token_hash, "Lookup Test")
        result = db.get_api_token_by_hash(token_hash)
        assert result is not None
        assert result["id"] == row_id
        assert result["user_id"] == user_id
        assert result["token_hash"] == token_hash
        assert result["label"] == "Lookup Test"
        assert result["revoked"] == 0
        assert result["last_used_at"] is None

    def test_returns_none_for_nonexistent_hash(self, db):
        result = db.get_api_token_by_hash("nonexistent_hash_value")
        assert result is None


class TestGetApiTokensForUser:
    """Tests for get_api_tokens_for_user."""

    def test_returns_empty_list_for_user_with_no_tokens(self, db, user_id):
        result = db.get_api_tokens_for_user(user_id)
        assert result == []

    def test_returns_tokens_sorted_by_created_at_desc(self, db, user_id):
        # Insert tokens with explicit created_at ordering
        cursor = db.conn.cursor()
        cursor.execute(
            "INSERT INTO api_tokens (user_id, token_hash, label, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, _hash_token("oldest"), "Oldest", "2025-01-01 00:00:00"),
        )
        cursor.execute(
            "INSERT INTO api_tokens (user_id, token_hash, label, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, _hash_token("newest"), "Newest", "2025-03-01 00:00:00"),
        )
        cursor.execute(
            "INSERT INTO api_tokens (user_id, token_hash, label, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, _hash_token("middle"), "Middle", "2025-02-01 00:00:00"),
        )
        db.conn.commit()

        result = db.get_api_tokens_for_user(user_id)
        assert len(result) == 3
        assert result[0]["label"] == "Newest"
        assert result[1]["label"] == "Middle"
        assert result[2]["label"] == "Oldest"

    def test_returns_max_100_tokens(self, db, user_id):
        # Insert 105 tokens
        cursor = db.conn.cursor()
        for i in range(105):
            cursor.execute(
                "INSERT INTO api_tokens (user_id, token_hash, label) VALUES (?, ?, ?)",
                (user_id, _hash_token(f"token_{i}"), f"Token {i}"),
            )
        db.conn.commit()

        result = db.get_api_tokens_for_user(user_id)
        assert len(result) == 100

    def test_does_not_return_other_users_tokens(self, db, user_id):
        other_user_id = db.create_user("otheruser", "pw", "Other")
        db.create_api_token(user_id, _hash_token("mine"), "Mine")
        db.create_api_token(other_user_id, _hash_token("theirs"), "Theirs")

        my_tokens = db.get_api_tokens_for_user(user_id)
        assert len(my_tokens) == 1
        assert my_tokens[0]["label"] == "Mine"


class TestRevokeApiToken:
    """Tests for revoke_api_token."""

    def test_sets_revoked_to_1(self, db, user_id):
        token_hash = _hash_token("revoke_me")
        row_id = db.create_api_token(user_id, token_hash, "To Revoke")
        db.revoke_api_token(row_id)
        token = db.get_api_token_by_hash(token_hash)
        assert token["revoked"] == 1

    def test_revoke_idempotent(self, db, user_id):
        token_hash = _hash_token("revoke_twice")
        row_id = db.create_api_token(user_id, token_hash, "Revoke Twice")
        db.revoke_api_token(row_id)
        db.revoke_api_token(row_id)  # Should not raise
        token = db.get_api_token_by_hash(token_hash)
        assert token["revoked"] == 1


class TestUpdateTokenLastUsed:
    """Tests for update_token_last_used."""

    def test_sets_last_used_at(self, db, user_id):
        token_hash = _hash_token("use_me")
        row_id = db.create_api_token(user_id, token_hash, "Use Me")
        # Initially None
        token = db.get_api_token_by_hash(token_hash)
        assert token["last_used_at"] is None

        db.update_token_last_used(row_id)
        token = db.get_api_token_by_hash(token_hash)
        assert token["last_used_at"] is not None
        # Should be a valid datetime string
        parsed = datetime.strptime(token["last_used_at"], "%Y-%m-%d %H:%M:%S")
        # Should be within last few seconds
        now = datetime.now(timezone.utc)
        diff = abs((now - parsed.replace(tzinfo=timezone.utc)).total_seconds())
        assert diff < 5


class TestCountActiveApiTokens:
    """Tests for count_active_api_tokens."""

    def test_counts_zero_for_no_tokens(self, db, user_id):
        assert db.count_active_api_tokens(user_id) == 0

    def test_counts_active_non_revoked_tokens(self, db, user_id):
        db.create_api_token(user_id, _hash_token("active1"), "Active 1")
        db.create_api_token(user_id, _hash_token("active2"), "Active 2")
        assert db.count_active_api_tokens(user_id) == 2

    def test_excludes_revoked_tokens(self, db, user_id):
        db.create_api_token(user_id, _hash_token("keep"), "Keep")
        revoke_id = db.create_api_token(user_id, _hash_token("revoke"), "Revoke")
        db.revoke_api_token(revoke_id)
        assert db.count_active_api_tokens(user_id) == 1

    def test_excludes_expired_tokens(self, db, user_id):
        # Active token (no expiry)
        db.create_api_token(user_id, _hash_token("no_expiry"), "No Expiry")
        # Expired token
        past = "2020-01-01 00:00:00"
        db.create_api_token(user_id, _hash_token("expired"), "Expired", expires_at=past)
        assert db.count_active_api_tokens(user_id) == 1

    def test_includes_future_expiry_tokens(self, db, user_id):
        future = (datetime.now(timezone.utc) + timedelta(days=30)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        db.create_api_token(user_id, _hash_token("future"), "Future", expires_at=future)
        assert db.count_active_api_tokens(user_id) == 1

    def test_does_not_count_other_users_tokens(self, db, user_id):
        other_id = db.create_user("other", "pw", "Other")
        db.create_api_token(user_id, _hash_token("mine"), "Mine")
        db.create_api_token(other_id, _hash_token("theirs"), "Theirs")
        assert db.count_active_api_tokens(user_id) == 1
