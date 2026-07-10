"""Unit tests for broadcast integration in coverage mutation routes.

Verifies that broadcast_coverage_event is called with the correct event type
and request ID after each coverage mutation endpoint (create, claim, unclaim, cancel).

Validates: Requirements 2.1, 2.2, 2.3, 2.4
"""

from unittest.mock import patch

import pytest

from dc_shiftmaster_html.server import create_app


@pytest.fixture
def app(tmp_path):
    """Create a Flask test app with a fresh temp database."""
    db_path = str(tmp_path / "test_broadcast.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _create_user(app, username, display_name):
    """Helper: create a user directly via the DB and return the user ID."""
    db = app.config["db"]
    return db.create_user(username, "hash", display_name, display_name)


def _login(client, user_id):
    """Helper: set session user_id for authenticated requests."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


class TestBroadcastOnCreate:
    """After POST /api/coverage (create), broadcast is called with ("created", req_id)."""

    @patch("dc_shiftmaster_html.routes_coverage.broadcast_coverage_event")
    def test_create_broadcasts_created_event(self, mock_broadcast, app, client):
        user_id = _create_user(app, "alice", "Alice")
        _login(client, user_id)

        resp = client.post("/api/coverage", json={
            "date": "2025-06-01",
            "shift_type": "day",
            "note": "PTO",
        })
        assert resp.status_code == 201

        req_id = resp.get_json()["id"]
        mock_broadcast.assert_called_once_with("created", req_id)


class TestBroadcastOnClaim:
    """After POST /api/coverage/<id>/claim, broadcast is called with ("claimed", req_id)."""

    @patch("dc_shiftmaster_html.routes_coverage.broadcast_coverage_event")
    def test_claim_broadcasts_claimed_event(self, mock_broadcast, app, client):
        requester_id = _create_user(app, "alice", "Alice")
        claimer_id = _create_user(app, "bob", "Bob")

        # Create a coverage request as alice
        _login(client, requester_id)
        resp = client.post("/api/coverage", json={
            "date": "2025-06-01",
            "shift_type": "day",
        })
        assert resp.status_code == 201
        req_id = resp.get_json()["id"]
        mock_broadcast.reset_mock()

        # Claim as bob
        _login(client, claimer_id)
        resp = client.post(f"/api/coverage/{req_id}/claim")
        assert resp.status_code == 200

        mock_broadcast.assert_called_once_with("claimed", req_id)


class TestBroadcastOnUnclaim:
    """After POST /api/coverage/<id>/unclaim, broadcast is called with ("unclaimed", req_id)."""

    @patch("dc_shiftmaster_html.routes_coverage.broadcast_coverage_event")
    def test_unclaim_broadcasts_unclaimed_event(self, mock_broadcast, app, client):
        requester_id = _create_user(app, "alice", "Alice")
        claimer_id = _create_user(app, "bob", "Bob")

        # Create and claim
        _login(client, requester_id)
        resp = client.post("/api/coverage", json={
            "date": "2025-06-01",
            "shift_type": "day",
        })
        req_id = resp.get_json()["id"]

        _login(client, claimer_id)
        client.post(f"/api/coverage/{req_id}/claim")
        mock_broadcast.reset_mock()

        # Unclaim as bob (the claimer)
        resp = client.post(f"/api/coverage/{req_id}/unclaim")
        assert resp.status_code == 200

        mock_broadcast.assert_called_once_with("unclaimed", req_id)


class TestBroadcastOnCancel:
    """After POST /api/coverage/<id>/cancel, broadcast is called with ("cancelled", req_id)."""

    @patch("dc_shiftmaster_html.routes_coverage.broadcast_coverage_event")
    def test_cancel_broadcasts_cancelled_event(self, mock_broadcast, app, client):
        requester_id = _create_user(app, "alice", "Alice")

        # Create a coverage request
        _login(client, requester_id)
        resp = client.post("/api/coverage", json={
            "date": "2025-06-01",
            "shift_type": "day",
        })
        req_id = resp.get_json()["id"]
        mock_broadcast.reset_mock()

        # Cancel as the requester
        resp = client.post(f"/api/coverage/{req_id}/cancel")
        assert resp.status_code == 200

        mock_broadcast.assert_called_once_with("cancelled", req_id)
