"""Unit tests for DatabaseManager user CRUD methods."""

import pytest

from dc_shiftmaster.models import User


class TestCreateUser:
    """Tests for DatabaseManager.create_user."""

    def test_create_user_returns_id(self, db):
        uid = db.create_user("alice", "hash123", "Alice A")
        assert isinstance(uid, int)
        assert uid > 0

    def test_create_user_with_teammate_name(self, db):
        uid = db.create_user("bob", "hash456", "Bob B", teammate_name="Bob")
        user = db.get_user_by_id(uid)
        assert user.teammate_name == "Bob"

    def test_create_user_default_teammate_name_empty(self, db):
        uid = db.create_user("carol", "hash789", "Carol C")
        user = db.get_user_by_id(uid)
        assert user.teammate_name == ""

    def test_create_user_empty_username_raises(self, db):
        with pytest.raises(ValueError):
            db.create_user("", "hash", "Display")

    def test_create_user_whitespace_username_raises(self, db):
        with pytest.raises(ValueError):
            db.create_user("   ", "hash", "Display")

    def test_create_user_duplicate_username_raises(self, db):
        db.create_user("alice", "hash1", "Alice One")
        with pytest.raises(ValueError, match="already exists"):
            db.create_user("alice", "hash2", "Alice Two")


class TestGetUserByUsername:
    """Tests for DatabaseManager.get_user_by_username."""

    def test_returns_user_when_exists(self, db):
        db.create_user("alice", "hash123", "Alice A", teammate_name="Alice")
        user = db.get_user_by_username("alice")
        assert user is not None
        assert isinstance(user, User)
        assert user.username == "alice"
        assert user.password_hash == "hash123"
        assert user.display_name == "Alice A"
        assert user.teammate_name == "Alice"
        assert user.created_at is not None

    def test_returns_none_when_missing(self, db):
        result = db.get_user_by_username("nonexistent")
        assert result is None


class TestGetUserById:
    """Tests for DatabaseManager.get_user_by_id."""

    def test_returns_user_when_exists(self, db):
        uid = db.create_user("alice", "hash123", "Alice A")
        user = db.get_user_by_id(uid)
        assert user is not None
        assert user.id == uid
        assert user.username == "alice"

    def test_returns_none_when_missing(self, db):
        result = db.get_user_by_id(99999)
        assert result is None


class TestGetAllUsers:
    """Tests for DatabaseManager.get_all_users."""

    def test_empty_initially(self, db):
        users = db.get_all_users()
        assert users == []

    def test_returns_all_created_users(self, db):
        db.create_user("alice", "h1", "Alice")
        db.create_user("bob", "h2", "Bob")
        db.create_user("carol", "h3", "Carol")
        users = db.get_all_users()
        assert len(users) == 3
        usernames = {u.username for u in users}
        assert usernames == {"alice", "bob", "carol"}
