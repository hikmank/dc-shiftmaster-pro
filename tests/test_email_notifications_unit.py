"""Unit tests for the email notification feature.

Covers validate_email, profile update endpoint, _build_email_body,
GET /api/auth/me new fields, database migration, and get_notification_recipients.
"""

import json
from types import SimpleNamespace

import pytest

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster_html.email_service import _build_email_body, validate_email
from dc_shiftmaster_html.server import create_app


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def app(tmp_path):
    """Create a Flask test app with a fresh temp database."""
    db_path = str(tmp_path / "test.db")
    application = create_app(db_path=db_path)
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def _register_user(client, username="alice", password="pass123",
                    display_name="Alice", teammate_name="Alice A", email=""):
    """Helper to register a user and return the response."""
    payload = {
        "username": username,
        "password": password,
        "display_name": display_name,
        "teammate_name": teammate_name,
    }
    if email:
        payload["email"] = email
    return client.post("/api/auth/register",
                       data=json.dumps(payload),
                       content_type="application/json")


def _login_session(client, app, user_id):
    """Set up an authenticated session for the given user_id."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


# ── 8.1 validate_email unit tests ────────────────────────────────────


class TestValidateEmail:
    """Unit tests for validate_email with known valid/invalid inputs.

    Requirements: 1.4
    """

    def test_empty_string(self):
        assert validate_email("") is False

    def test_missing_at(self):
        assert validate_email("userexample.com") is False

    def test_multiple_at(self):
        assert validate_email("user@@example.com") is False
        assert validate_email("a@b@c.com") is False

    def test_valid_format(self):
        assert validate_email("user@example.com") is True

    def test_whitespace_only(self):
        assert validate_email("   ") is False

    def test_no_local_part(self):
        assert validate_email("@example.com") is False

    def test_no_domain_part(self):
        assert validate_email("user@") is False

    def test_simple_valid(self):
        assert validate_email("a@b") is True


# ── 8.2 Profile update endpoint unit tests ───────────────────────────


class TestProfileUpdateEndpoint:
    """Unit tests for PUT /api/auth/profile.

    Requirements: 6.1, 6.2, 6.3, 2.3
    """

    def test_success_update_email(self, client, app):
        resp = _register_user(client)
        user_id = resp.get_json()["id"]
        _login_session(client, app, user_id)

        resp = client.put("/api/auth/profile",
                          data=json.dumps({"email": "alice@example.com",
                                           "email_notifications_enabled": False}),
                          content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["email"] == "alice@example.com"
        assert data["email_notifications_enabled"] is False

    def test_success_enable_notifications(self, client, app):
        resp = _register_user(client)
        user_id = resp.get_json()["id"]
        _login_session(client, app, user_id)

        # First set email
        client.put("/api/auth/profile",
                   data=json.dumps({"email": "alice@example.com"}),
                   content_type="application/json")
        # Then enable notifications
        resp = client.put("/api/auth/profile",
                          data=json.dumps({"email": "alice@example.com",
                                           "email_notifications_enabled": True}),
                          content_type="application/json")
        assert resp.status_code == 200
        assert resp.get_json()["email_notifications_enabled"] is True

    def test_invalid_email_returns_400(self, client, app):
        resp = _register_user(client)
        user_id = resp.get_json()["id"]
        _login_session(client, app, user_id)

        resp = client.put("/api/auth/profile",
                          data=json.dumps({"email": "not-an-email"}),
                          content_type="application/json")
        assert resp.status_code == 400
        assert "Invalid email" in resp.get_json()["error"]

    def test_enable_without_email_returns_400(self, client, app):
        resp = _register_user(client)
        user_id = resp.get_json()["id"]
        _login_session(client, app, user_id)

        resp = client.put("/api/auth/profile",
                          data=json.dumps({"email": "",
                                           "email_notifications_enabled": True}),
                          content_type="application/json")
        assert resp.status_code == 400
        assert "required" in resp.get_json()["error"].lower()

    def test_unauthenticated_returns_401(self, client):
        resp = client.put("/api/auth/profile",
                          data=json.dumps({"email": "a@b.com"}),
                          content_type="application/json")
        assert resp.status_code == 401


# ── 8.3 _build_email_body unit tests ─────────────────────────────────


class TestBuildEmailBody:
    """Unit tests for _build_email_body with specific event types.

    Requirements: 3.3, 3.4, 4.2, 4.3
    """

    def _make_request(self, **kwargs):
        defaults = {
            "id": 1, "requester_id": 1, "date": "2025-04-01",
            "shift_type": "day", "note": "", "status": "open",
            "claimer_id": None, "created_at": "2025-04-01T00:00:00",
            "claimed_at": None,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def _make_user(self, **kwargs):
        defaults = {
            "id": 1, "username": "alice", "password_hash": "hash",
            "display_name": "Alice", "teammate_name": "Alice A",
            "created_at": "2025-01-01", "email": "alice@example.com",
            "email_notifications_enabled": True,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_created_subject_contains_requester_name(self):
        req = self._make_request()
        requester = self._make_user(display_name="Alice")
        subject, _ = _build_email_body("created", req, requester)
        assert "Alice" in subject
        assert "[ShiftMaster]" in subject

    def test_created_body_contains_details(self):
        req = self._make_request(date="2025-04-01", shift_type="night", note="PTO")
        requester = self._make_user(display_name="Alice")
        _, body = _build_email_body("created", req, requester)
        assert "Alice" in body
        assert "2025-04-01" in body
        assert "night" in body
        assert "PTO" in body

    def test_created_body_without_note(self):
        req = self._make_request(note="")
        requester = self._make_user(display_name="Alice")
        _, body = _build_email_body("created", req, requester)
        assert "Note" not in body

    def test_claimed_subject_format(self):
        req = self._make_request()
        requester = self._make_user(display_name="Alice")
        claimer = self._make_user(id=2, display_name="Bob")
        subject, _ = _build_email_body("claimed", req, requester, claimer)
        assert "[ShiftMaster]" in subject
        assert "Claimed" in subject

    def test_claimed_body_contains_claimer_and_details(self):
        req = self._make_request(date="2025-05-10", shift_type="day")
        requester = self._make_user(display_name="Alice")
        claimer = self._make_user(id=2, display_name="Bob")
        _, body = _build_email_body("claimed", req, requester, claimer)
        assert "Bob" in body
        assert "2025-05-10" in body
        assert "day" in body

    def test_claimed_without_claimer_falls_back_to_someone(self):
        req = self._make_request(date="2025-06-01", shift_type="evening")
        requester = self._make_user(display_name="Alice")
        _, body = _build_email_body("claimed", req, requester, claimer=None)
        assert "Someone" in body
        assert "evening" in body
        assert "2025-06-01" in body

    def test_created_subject_identifies_new_request(self):
        """Req 3.4: subject identifies the message as a new coverage request notification."""
        req = self._make_request()
        requester = self._make_user(display_name="Carol")
        subject, _ = _build_email_body("created", req, requester)
        assert subject == "[ShiftMaster] New Coverage Request from Carol"

    def test_claimed_subject_identifies_claimed_notification(self):
        """Req 4.3: subject identifies the message as a coverage request claimed notification."""
        req = self._make_request()
        requester = self._make_user(display_name="Alice")
        claimer = self._make_user(id=2, display_name="Bob")
        subject, _ = _build_email_body("claimed", req, requester, claimer)
        assert subject == "[ShiftMaster] Your Coverage Request Was Claimed"

    def test_unknown_event_type_returns_empty(self):
        req = self._make_request()
        requester = self._make_user(display_name="Alice")
        subject, body = _build_email_body("unknown", req, requester)
        assert subject == ""
        assert body == ""


# ── 8.4 GET /api/auth/me includes new fields ─────────────────────────


class TestMeEndpointFields:
    """Unit tests for GET /api/auth/me including email fields.

    Requirements: 6.4, 2.4
    """

    def test_me_includes_email_fields(self, client, app):
        resp = _register_user(client, email="alice@example.com")
        user_id = resp.get_json()["id"]
        _login_session(client, app, user_id)

        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "email" in data
        assert "email_notifications_enabled" in data
        assert data["email"] == "alice@example.com"
        assert data["email_notifications_enabled"] is False

    def test_me_default_email_fields(self, client, app):
        resp = _register_user(client)
        user_id = resp.get_json()["id"]
        _login_session(client, app, user_id)

        resp = client.get("/api/auth/me")
        data = resp.get_json()
        assert data["email"] == ""
        assert data["email_notifications_enabled"] is False

    def test_me_reflects_profile_update(self, client, app):
        """After PUT /api/auth/profile, GET /me returns the updated values."""
        resp = _register_user(client)
        user_id = resp.get_json()["id"]
        _login_session(client, app, user_id)

        # Update profile with email and enable notifications
        resp = client.put("/api/auth/profile",
                          data=json.dumps({"email": "updated@example.com",
                                           "email_notifications_enabled": True}),
                          content_type="application/json")
        assert resp.status_code == 200

        # GET /me should reflect the updated values
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["email"] == "updated@example.com"
        assert data["email_notifications_enabled"] is True


# ── 8.5 Database migration unit tests ────────────────────────────────


class TestDatabaseMigration:
    """Unit tests for database migration adding email columns.

    Requirements: 1.1, 2.1
    """

    def test_email_column_exists(self, db):
        cursor = db.conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "email" in columns

    def test_email_notifications_enabled_column_exists(self, db):
        cursor = db.conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "email_notifications_enabled" in columns

    def test_default_values(self, db):
        uid = db.create_user("testuser", "hash", "Test User")
        user = db.get_user_by_id(uid)
        assert user.email == ""
        assert user.email_notifications_enabled is False


# ── 8.6 get_notification_recipients unit tests ───────────────────────


class TestGetNotificationRecipients:
    """Unit tests for get_notification_recipients.

    Requirements: 3.2, 4.1
    """

    def test_excludes_users_without_email(self, db):
        uid1 = db.create_user("alice", "hash", "Alice")
        db.update_user_profile(uid1, "", True)  # no email, enabled
        recipients = db.get_notification_recipients()
        assert len(recipients) == 0

    def test_excludes_users_with_notifications_disabled(self, db):
        uid1 = db.create_user("alice", "hash", "Alice", email="alice@example.com")
        db.update_user_profile(uid1, "alice@example.com", False)
        recipients = db.get_notification_recipients()
        assert len(recipients) == 0

    def test_includes_eligible_users(self, db):
        uid1 = db.create_user("alice", "hash", "Alice", email="alice@example.com")
        db.update_user_profile(uid1, "alice@example.com", True)
        recipients = db.get_notification_recipients()
        assert len(recipients) == 1
        assert recipients[0].id == uid1

    def test_excludes_specific_user(self, db):
        uid1 = db.create_user("alice", "hash", "Alice", email="alice@example.com")
        uid2 = db.create_user("bob", "hash", "Bob", email="bob@example.com")
        db.update_user_profile(uid1, "alice@example.com", True)
        db.update_user_profile(uid2, "bob@example.com", True)
        recipients = db.get_notification_recipients(exclude_user_id=uid1)
        assert len(recipients) == 1
        assert recipients[0].id == uid2

    def test_mixed_users(self, db):
        uid1 = db.create_user("alice", "hash", "Alice", email="alice@example.com")
        uid2 = db.create_user("bob", "hash", "Bob")  # no email
        uid3 = db.create_user("carol", "hash", "Carol", email="carol@example.com")
        db.update_user_profile(uid1, "alice@example.com", True)
        db.update_user_profile(uid2, "", True)  # no email
        db.update_user_profile(uid3, "carol@example.com", False)  # disabled
        recipients = db.get_notification_recipients()
        assert len(recipients) == 1
        assert recipients[0].id == uid1
