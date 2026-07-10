"""Property-based tests for email notification features.

Feature: email-notifications
Properties 1, 3, 4, 5
"""

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster.models import User
from dc_shiftmaster_html.server import create_app


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Non-empty text without '@' for local/domain parts of email addresses
_no_at_text = st.text(
    alphabet=st.characters(blacklist_characters="@", blacklist_categories=("Cs",)),
    min_size=1,
    max_size=30,
).filter(lambda s: len(s) > 0)

# Strategy for valid email addresses: local@domain
_valid_email = st.builds(lambda l, d: f"{l}@{d}", _no_at_text, _no_at_text)

# Strategy for notification preference boolean
_notif_pref = st.booleans()

# Unique username counter (thread-local via Hypothesis)
_username_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=3,
    max_size=20,
).filter(lambda s: s.strip())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path):
    """Create a Flask test app with a fresh temp database."""
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True
    # Ensure rate limiter is fully disabled for property tests
    from dc_shiftmaster_html.extensions import limiter
    limiter.enabled = False
    return app


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Property 1: Profile update round-trip
# Feature: email-notifications, Property 1: Profile update round-trip
# ---------------------------------------------------------------------------
class TestProfileUpdateRoundTripProperty:
    """For any valid email and boolean preference, update_user_profile followed by get_user_by_id returns the same values."""

    @given(email=_valid_email, notifications_enabled=_notif_pref)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_profile_round_trip(self, db, email: str, notifications_enabled: bool):
        """**Validates: Requirements 1.1, 1.3, 2.2, 6.2**

        Write email and notification preference via update_user_profile,
        read back via get_user_by_id, assert equality.
        """
        user_id = db.create_user("testuser", "hash", "Test User")
        db.update_user_profile(user_id, email, notifications_enabled)
        user = db.get_user_by_id(user_id)

        assert user is not None
        assert user.email == email
        assert user.email_notifications_enabled == notifications_enabled

        # Clean up for next iteration (Hypothesis reuses the fixture)
        db.conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.conn.commit()


# ---------------------------------------------------------------------------
# Property 3: Enabling notifications requires an email address
# Feature: email-notifications, Property 3: Enabling notifications requires email
# ---------------------------------------------------------------------------
class TestEnableNotificationsRequiresEmailProperty:
    """For users with empty email, enabling notifications via the profile endpoint returns an error."""

    _counter = 0

    @given(
        display_name=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=20,
        ).filter(lambda s: s.strip()),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.filter_too_much])
    def test_enable_without_email_returns_400(self, app, client, display_name: str):
        """**Validates: Requirements 2.3**

        Register a user without email, then attempt to enable notifications.
        Assert HTTP 400 and preference remains False.
        """
        TestEnableNotificationsRequiresEmailProperty._counter += 1
        username = f"propuser_{TestEnableNotificationsRequiresEmailProperty._counter}"

        # Register a user (no email)
        reg_resp = client.post("/api/auth/register", json={
            "username": username,
            "password": "testpass123",
            "display_name": display_name,
        })
        assert reg_resp.status_code == 201

        user_id = reg_resp.get_json()["id"]

        # Attempt to enable notifications without providing email
        resp = client.put("/api/auth/profile", json={
            "email_notifications_enabled": True,
        })
        assert resp.status_code == 400
        assert "email" in resp.get_json()["error"].lower()

        # Verify preference is still False
        db = app.config["db"]
        user = db.get_user_by_id(user_id)
        assert user.email_notifications_enabled is False

        # Logout for next iteration
        client.post("/api/auth/logout")


# ---------------------------------------------------------------------------
# Property 4: Created event recipient set
# Feature: email-notifications, Property 4: Created event recipient set
# ---------------------------------------------------------------------------
class TestCreatedEventRecipientSetProperty:
    """The recipient set for 'created' events matches users with non-empty email, notifications enabled, excluding the requester."""

    @given(
        user_configs=st.lists(
            st.tuples(
                _valid_email.filter(lambda e: len(e) <= 60) | st.just(""),
                _notif_pref,
            ),
            min_size=2,
            max_size=8,
        ),
        requester_idx=st.integers(min_value=0),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_created_recipient_set(self, db, user_configs, requester_idx: int):
        """**Validates: Requirements 3.1, 3.2**

        Create users with varying email/preference states, pick one as requester,
        assert get_notification_recipients returns exactly the expected set.
        """
        assume(len(user_configs) >= 2)
        requester_idx = requester_idx % len(user_configs)

        user_ids = []
        for i, (email, notif) in enumerate(user_configs):
            uid = db.create_user(f"user_{i}", "hash", f"User {i}")
            db.update_user_profile(uid, email, notif)
            user_ids.append(uid)

        requester_id = user_ids[requester_idx]
        recipients = db.get_notification_recipients(exclude_user_id=requester_id)
        recipient_ids = {r.id for r in recipients}

        # Compute expected set
        expected_ids = set()
        for i, (email, notif) in enumerate(user_configs):
            uid = user_ids[i]
            if uid != requester_id and email != "" and notif:
                expected_ids.add(uid)

        assert recipient_ids == expected_ids

        # Clean up
        db.conn.execute("DELETE FROM users")
        db.conn.commit()


# ---------------------------------------------------------------------------
# Property 5: Claimed event recipient
# Feature: email-notifications, Property 5: Claimed event recipient
# ---------------------------------------------------------------------------
class TestClaimedEventRecipientProperty:
    """For 'claimed' events, only the requester receives email iff they have non-empty email and notifications enabled."""

    @given(
        requester_email=_valid_email.filter(lambda e: len(e) <= 60) | st.just(""),
        requester_notif=_notif_pref,
    )
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_claimed_recipient(self, db, requester_email: str, requester_notif: bool):
        """**Validates: Requirements 4.1**

        Create a requester with given email/preference, plus other opted-in users.
        Call send_coverage_email("claimed", ...) and assert the requester is the
        sole SES recipient when eligible, and no emails are sent otherwise.
        No other users ever receive an email for claimed events.
        """
        import os
        import threading
        from unittest.mock import MagicMock, patch
        from dc_shiftmaster_html.email_service import send_coverage_email

        # Create the requester
        requester_id = db.create_user("requester", "hash", "Requester")
        db.update_user_profile(requester_id, requester_email, requester_notif)

        # Create other opted-in users who should NOT receive claimed emails
        other_id = db.create_user("other", "hash", "Other")
        db.update_user_profile(other_id, "other@example.com", True)

        # Create a coverage request and claim it
        req_id = db.create_coverage_request(requester_id, "2025-06-15", "day", "test")
        claimer_id = db.create_user("claimer", "hash", "Claimer")
        db.update_user_profile(claimer_id, "claimer@example.com", True)
        db.claim_coverage_request(req_id, claimer_id)

        # Mock SES and call send_coverage_email
        mock_ses = MagicMock()
        env_vars = {"SES_SENDER_EMAIL": "sender@example.com", "SES_AWS_REGION": "us-east-1"}

        with patch.dict(os.environ, env_vars), \
             patch("dc_shiftmaster_html.email_service.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_ses

            send_coverage_email("claimed", req_id, db)

            # Wait for background daemon threads to complete
            for t in threading.enumerate():
                if t.daemon and t.is_alive() and t.name != "MainThread":
                    t.join(timeout=5)

            requester_eligible = requester_email != "" and requester_notif

            if requester_eligible:
                # Exactly one email sent, to the requester only
                assert mock_ses.send_email.call_count == 1
                call_args = mock_ses.send_email.call_args
                recipients = call_args[1]["Destination"]["ToAddresses"]
                assert recipients == [requester_email]
            else:
                # No emails sent at all
                mock_ses.send_email.assert_not_called()

        # Clean up
        db.conn.execute("DELETE FROM coverage_requests")
        db.conn.execute("DELETE FROM users")
        db.conn.commit()
