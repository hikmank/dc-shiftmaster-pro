"""Unit tests for the api_tokens table schema, indexes, and constraints.

Validates Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6 of the API Token Authentication spec.
"""

import os
import tempfile

import pytest

from dc_shiftmaster.database import DatabaseManager


def _make_db():
    """Create a fresh DatabaseManager backed by a temp file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return DatabaseManager(path), path


def _cleanup_db(db, path):
    """Close the database and remove the temp file."""
    db.conn.close()
    try:
        os.unlink(path)
    except OSError:
        pass


class TestApiTokensTableExists:
    """Req 6.1, 6.3: The api_tokens table is created automatically."""

    def test_table_exists(self):
        db, path = _make_db()
        try:
            cursor = db.conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='api_tokens'"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "api_tokens"
        finally:
            _cleanup_db(db, path)

    def test_idempotent_creation(self):
        """Table creation is idempotent — re-initializing doesn't fail."""
        db, path = _make_db()
        try:
            # Call _create_tables again (simulates restart)
            db._create_tables()
            cursor = db.conn.cursor()
            cursor.execute(
                "SELECT count(*) FROM sqlite_master "
                "WHERE type='table' AND name='api_tokens'"
            )
            assert cursor.fetchone()[0] == 1
        finally:
            _cleanup_db(db, path)


class TestApiTokensColumns:
    """Req 6.2: Correct columns with expected types and defaults."""

    def test_columns_present(self):
        db, path = _make_db()
        try:
            cursor = db.conn.cursor()
            cursor.execute("PRAGMA table_info(api_tokens)")
            columns = {row[1]: row for row in cursor.fetchall()}
            expected = [
                "id", "user_id", "token_hash", "label",
                "created_at", "expires_at", "revoked", "last_used_at",
            ]
            for col in expected:
                assert col in columns, f"Column '{col}' missing from api_tokens"
        finally:
            _cleanup_db(db, path)

    def test_revoked_defaults_to_zero(self):
        """revoked column defaults to 0 (false)."""
        db, path = _make_db()
        try:
            # Insert a user first
            cursor = db.conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, display_name) "
                "VALUES ('testuser', 'hash123', 'Test User')"
            )
            user_id = cursor.lastrowid
            # Insert a token with minimal fields
            cursor.execute(
                "INSERT INTO api_tokens (user_id, token_hash, label) "
                "VALUES (?, 'abc123hash', 'My Token')",
                (user_id,),
            )
            db.conn.commit()
            cursor.execute("SELECT revoked FROM api_tokens WHERE token_hash='abc123hash'")
            assert cursor.fetchone()[0] == 0
        finally:
            _cleanup_db(db, path)


class TestApiTokensIndexes:
    """Req 6.6: Indexes on token_hash and user_id."""

    def test_token_hash_index_exists(self):
        db, path = _make_db()
        try:
            cursor = db.conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name='idx_api_tokens_hash'"
            )
            assert cursor.fetchone() is not None
        finally:
            _cleanup_db(db, path)

    def test_user_id_index_exists(self):
        db, path = _make_db()
        try:
            cursor = db.conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name='idx_api_tokens_user_id'"
            )
            assert cursor.fetchone() is not None
        finally:
            _cleanup_db(db, path)


class TestApiTokensUniqueConstraint:
    """Req 6.5: Unique constraint on token_hash."""

    def test_duplicate_token_hash_rejected(self):
        db, path = _make_db()
        try:
            cursor = db.conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, display_name) "
                "VALUES ('user1', 'hash1', 'User One')"
            )
            user_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO api_tokens (user_id, token_hash, label) "
                "VALUES (?, 'same_hash', 'Token A')",
                (user_id,),
            )
            db.conn.commit()
            with pytest.raises(Exception):
                cursor.execute(
                    "INSERT INTO api_tokens (user_id, token_hash, label) "
                    "VALUES (?, 'same_hash', 'Token B')",
                    (user_id,),
                )
                db.conn.commit()
        finally:
            _cleanup_db(db, path)


class TestApiTokensForeignKey:
    """Req 6.4: CASCADE delete — removing a user removes their tokens."""

    def test_cascade_delete(self):
        db, path = _make_db()
        try:
            cursor = db.conn.cursor()
            # Ensure foreign keys are enforced
            cursor.execute("PRAGMA foreign_keys")
            assert cursor.fetchone()[0] == 1

            # Create a user and a token
            cursor.execute(
                "INSERT INTO users (username, password_hash, display_name) "
                "VALUES ('cascade_user', 'hash', 'Cascade User')"
            )
            user_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO api_tokens (user_id, token_hash, label) "
                "VALUES (?, 'token_for_cascade', 'Cascade Token')",
                (user_id,),
            )
            db.conn.commit()

            # Verify token exists
            cursor.execute(
                "SELECT COUNT(*) FROM api_tokens WHERE user_id = ?", (user_id,)
            )
            assert cursor.fetchone()[0] == 1

            # Delete the user
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            db.conn.commit()

            # Token should be gone due to CASCADE
            cursor.execute(
                "SELECT COUNT(*) FROM api_tokens WHERE user_id = ?", (user_id,)
            )
            assert cursor.fetchone()[0] == 0
        finally:
            _cleanup_db(db, path)


class TestApiTokensLabelConstraint:
    """Req 6.2: Label CHECK constraint — max 128 characters."""

    def test_label_over_128_chars_rejected(self):
        db, path = _make_db()
        try:
            cursor = db.conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, display_name) "
                "VALUES ('label_user', 'hash', 'Label User')"
            )
            user_id = cursor.lastrowid
            long_label = "x" * 129
            with pytest.raises(Exception):
                cursor.execute(
                    "INSERT INTO api_tokens (user_id, token_hash, label) "
                    "VALUES (?, 'hash_long_label', ?)",
                    (user_id, long_label),
                )
                db.conn.commit()
        finally:
            _cleanup_db(db, path)

    def test_label_exactly_128_chars_accepted(self):
        db, path = _make_db()
        try:
            cursor = db.conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, display_name) "
                "VALUES ('label_user2', 'hash', 'Label User 2')"
            )
            user_id = cursor.lastrowid
            label_128 = "y" * 128
            cursor.execute(
                "INSERT INTO api_tokens (user_id, token_hash, label) "
                "VALUES (?, 'hash_128_label', ?)",
                (user_id, label_128),
            )
            db.conn.commit()
            cursor.execute(
                "SELECT label FROM api_tokens WHERE token_hash='hash_128_label'"
            )
            assert cursor.fetchone()[0] == label_128
        finally:
            _cleanup_db(db, path)
