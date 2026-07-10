"""Property-based tests for the email service module.

Feature: email-notifications
"""

import logging
import os
import threading
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster_html.email_service import (
    _build_email_body,
    send_coverage_email,
    validate_email,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Non-empty text without '@' for local/domain parts
_no_at_text = st.text(
    alphabet=st.characters(blacklist_characters="@", blacklist_categories=("Cs",)),
    min_size=1,
    max_size=30,
).filter(lambda s: len(s) > 0)

_display_name = st.text(min_size=1, max_size=50).filter(lambda s: s.strip())
_date_str = st.dates().map(lambda d: d.isoformat())
_shift_type = st.sampled_from(["day", "night"])
_note = st.text(min_size=0, max_size=200)


# ---------------------------------------------------------------------------
# Property 2: Email validation
# Feature: email-notifications, Property 2: Email validation
# ---------------------------------------------------------------------------
class TestEmailValidationProperty:
    """For any string, validate_email returns True iff exactly one '@' with non-empty local and domain parts."""

    @given(local=_no_at_text, domain=_no_at_text)
    @settings(max_examples=100)
    def test_valid_emails_accepted(self, local: str, domain: str):
        """**Validates: Requirements 1.4**

        Any string with exactly one '@' and non-empty local/domain parts is valid.
        """
        email = f"{local}@{domain}"
        assert validate_email(email) is True, f"Expected valid: {email!r}"

    @given(s=st.text(max_size=100))
    @settings(max_examples=100)
    def test_validation_matches_structural_check(self, s: str):
        """**Validates: Requirements 1.4**

        validate_email agrees with the structural definition: exactly one '@',
        non-empty local part, non-empty domain part.
        """
        parts = s.split("@")
        expected = len(parts) == 2 and len(parts[0]) > 0 and len(parts[1]) > 0
        assert validate_email(s) == expected, f"Mismatch for {s!r}"


# ---------------------------------------------------------------------------
# Property 6: Email body completeness
# Feature: email-notifications, Property 6: Email body completeness
# ---------------------------------------------------------------------------
class TestEmailBodyCompletenessProperty:
    """For any coverage request data, the composed email body contains all required fields."""

    @given(
        requester_name=_display_name,
        claimer_name=_display_name,
        date_str=_date_str,
        shift_type=_shift_type,
        note=_note,
    )
    @settings(max_examples=100)
    def test_created_body_contains_required_fields(
        self, requester_name, claimer_name, date_str, shift_type, note
    ):
        """**Validates: Requirements 3.3, 4.2**

        For "created" events, the body must contain requester name, date,
        shift type, and note (if non-empty).
        """
        from dc_shiftmaster.models import CoverageRequest, User

        requester = User(
            id=1, username="req", password_hash="x",
            display_name=requester_name, teammate_name="", created_at="",
        )
        cr = CoverageRequest(
            id=1, requester_id=1, date=date_str, shift_type=shift_type,
            note=note, status="open", claimer_id=None, created_at="", claimed_at=None,
        )

        subject, body = _build_email_body("created", cr, requester)

        assert requester_name in subject, f"Requester name missing from subject"
        assert requester_name in body, f"Requester name missing from body"
        assert date_str in body, f"Date missing from body"
        assert shift_type in body, f"Shift type missing from body"
        if note:
            assert note in body, f"Note missing from body"

    @given(
        requester_name=_display_name,
        claimer_name=_display_name,
        date_str=_date_str,
        shift_type=_shift_type,
    )
    @settings(max_examples=100)
    def test_claimed_body_contains_required_fields(
        self, requester_name, claimer_name, date_str, shift_type
    ):
        """**Validates: Requirements 3.3, 4.2**

        For "claimed" events, the body must contain claimer name, date,
        and shift type.
        """
        from dc_shiftmaster.models import CoverageRequest, User

        requester = User(
            id=1, username="req", password_hash="x",
            display_name=requester_name, teammate_name="", created_at="",
        )
        claimer = User(
            id=2, username="clm", password_hash="x",
            display_name=claimer_name, teammate_name="", created_at="",
        )
        cr = CoverageRequest(
            id=1, requester_id=1, date=date_str, shift_type=shift_type,
            note="", status="claimed", claimer_id=2, created_at="", claimed_at="",
        )

        subject, body = _build_email_body("claimed", cr, requester, claimer)

        assert claimer_name in body, f"Claimer name missing from body"
        assert date_str in body, f"Date missing from body"
        assert shift_type in body, f"Shift type missing from body"


# ---------------------------------------------------------------------------
# Property 7: Missing sender config disables email
# Feature: email-notifications, Property 7: Missing sender config disables email
# ---------------------------------------------------------------------------
class TestMissingSenderConfigProperty:
    """If SES_SENDER_EMAIL is not set, send_coverage_email sends zero emails and raises no exceptions."""

    @given(
        event_type=st.sampled_from(["created", "claimed"]),
        note=_note,
    )
    @settings(max_examples=100)
    def test_no_ses_calls_when_sender_unset(self, event_type, note):
        """**Validates: Requirements 5.4**

        With SES_SENDER_EMAIL unset, no SES calls are made and no exceptions raised.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")
            db = DatabaseManager(db_path)

            requester_id = db.create_user("requester", "hash", "Requester", email="req@example.com")
            db.update_user_profile(requester_id, "req@example.com", True)

            claimer_id = db.create_user("claimer", "hash", "Claimer", email="clm@example.com")
            db.update_user_profile(claimer_id, "clm@example.com", True)

            req_id = db.create_coverage_request(requester_id, "2025-01-15", "day", note)

            if event_type == "claimed":
                db.claim_coverage_request(req_id, claimer_id)

            # Ensure SES_SENDER_EMAIL is unset
            env = os.environ.copy()
            env.pop("SES_SENDER_EMAIL", None)

            with patch.dict(os.environ, env, clear=True), \
                 patch("dc_shiftmaster_html.email_service.boto3") as mock_boto3:
                send_coverage_email(event_type, req_id, db)
                mock_boto3.client.assert_not_called()

            db.conn.close()


# ---------------------------------------------------------------------------
# Property 8: SES errors do not propagate
# Feature: email-notifications, Property 8: SES errors do not propagate
# ---------------------------------------------------------------------------
class TestSESErrorHandlingProperty:
    """SES errors during send_coverage_email do not propagate as exceptions."""

    @given(
        event_type=st.sampled_from(["created", "claimed"]),
        note=_note,
    )
    @settings(max_examples=100)
    def test_ses_errors_do_not_propagate(self, event_type, note):
        """**Validates: Requirements 5.5, 7.3**

        When SES raises an exception, send_coverage_email completes without raising.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")
            db = DatabaseManager(db_path)

            requester_id = db.create_user("requester", "hash", "Requester", email="req@example.com")
            db.update_user_profile(requester_id, "req@example.com", True)

            claimer_id = db.create_user("claimer", "hash", "Claimer", email="clm@example.com")
            db.update_user_profile(claimer_id, "clm@example.com", True)

            req_id = db.create_coverage_request(requester_id, "2025-01-15", "day", note)

            if event_type == "claimed":
                db.claim_coverage_request(req_id, claimer_id)

            # Mock boto3 to raise an exception on send_email
            mock_ses_client = MagicMock()
            mock_ses_client.send_email.side_effect = Exception("SES failure")

            env_vars = {"SES_SENDER_EMAIL": "sender@example.com", "SES_AWS_REGION": "us-east-1"}

            with patch.dict(os.environ, env_vars), \
                 patch("dc_shiftmaster_html.email_service.boto3") as mock_boto3:
                mock_boto3.client.return_value = mock_ses_client

                # Should not raise
                send_coverage_email(event_type, req_id, db)

                # Wait for daemon threads to finish
                for t in threading.enumerate():
                    if t.daemon and t.is_alive() and t.name != "MainThread":
                        t.join(timeout=5)

            db.conn.close()
