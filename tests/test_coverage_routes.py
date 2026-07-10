"""Tests for coverage API routes (routes_coverage.py)."""

import pytest

from dc_shiftmaster_html.server import create_app


@pytest.fixture
def app(tmp_path):
    """Create a Flask test app with a fresh temp database."""
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _register(client, username="alice", password="secret123", display_name="Alice",
              teammate_name=""):
    """Helper to register a user and return the response."""
    return client.post("/api/auth/register", json={
        "username": username,
        "password": password,
        "display_name": display_name,
        "teammate_name": teammate_name,
    })


def _login(client, username, password="secret123"):
    """Helper to log in an existing user."""
    return client.post("/api/auth/login", json={
        "username": username,
        "password": password,
    })


def _create_coverage(client, date="2025-03-15", shift_type="day", note="Need off"):
    """Helper to create a coverage request."""
    return client.post("/api/coverage", json={
        "date": date,
        "shift_type": shift_type,
        "note": note,
    })


class TestCreateCoverage:
    """POST /api/coverage — create a coverage request."""

    def test_create_success(self, client):
        _register(client)
        resp = _create_coverage(client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["date"] == "2025-03-15"
        assert data["shift_type"] == "day"
        assert data["note"] == "Need off"
        assert data["status"] == "open"
        assert data["claimer_id"] is None
        assert "id" in data

    def test_create_missing_date(self, client):
        _register(client)
        resp = client.post("/api/coverage", json={
            "shift_type": "day",
        })
        assert resp.status_code == 400
        assert "date" in resp.get_json()["error"]

    def test_create_missing_shift_type(self, client):
        _register(client)
        resp = client.post("/api/coverage", json={
            "date": "2025-03-15",
        })
        assert resp.status_code == 400
        assert "shift_type" in resp.get_json()["error"]

    def test_create_invalid_shift_type(self, client):
        _register(client)
        resp = client.post("/api/coverage", json={
            "date": "2025-03-15",
            "shift_type": "evening",
        })
        assert resp.status_code == 400
        assert "shift_type" in resp.get_json()["error"]

    def test_create_unauthenticated(self, client):
        resp = _create_coverage(client)
        assert resp.status_code == 401

    def test_create_no_json_body(self, client):
        _register(client)
        resp = client.post("/api/coverage", data="not json")
        assert resp.status_code == 400


class TestListCoverage:
    """GET /api/coverage — list coverage requests."""

    def test_list_empty(self, client):
        resp = client.get("/api/coverage")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_all(self, client):
        _register(client)
        _create_coverage(client, date="2025-03-15")
        _create_coverage(client, date="2025-03-16")
        resp = client.get("/api/coverage")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 2

    def test_filter_by_status_open(self, client):
        _register(client, username="alice")
        _create_coverage(client, date="2025-03-15")
        _create_coverage(client, date="2025-03-16")
        resp = client.get("/api/coverage?status=open")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2
        assert all(r["status"] == "open" for r in data)

    def test_filter_by_status_claimed(self, client):
        _register(client, username="alice")
        _create_coverage(client, date="2025-03-15")
        resp = client.get("/api/coverage?status=claimed")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 0


class TestClaimCoverage:
    """POST /api/coverage/<id>/claim — claim a coverage request."""

    def test_claim_success(self, client):
        # Alice creates, Bob claims
        _register(client, username="alice")
        resp = _create_coverage(client)
        req_id = resp.get_json()["id"]
        client.post("/api/auth/logout")

        _register(client, username="bob", display_name="Bob")
        resp = client.post(f"/api/coverage/{req_id}/claim")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "claimed"
        assert data["claimer_id"] is not None

    def test_cannot_claim_own_request(self, client):
        _register(client, username="alice")
        resp = _create_coverage(client)
        req_id = resp.get_json()["id"]
        resp = client.post(f"/api/coverage/{req_id}/claim")
        assert resp.status_code == 400
        assert "own" in resp.get_json()["error"].lower()

    def test_claim_already_claimed(self, client):
        _register(client, username="alice")
        resp = _create_coverage(client)
        req_id = resp.get_json()["id"]
        client.post("/api/auth/logout")

        _register(client, username="bob", display_name="Bob")
        client.post(f"/api/coverage/{req_id}/claim")
        # Try claiming again
        resp = client.post(f"/api/coverage/{req_id}/claim")
        assert resp.status_code == 400

    def test_claim_unauthenticated(self, client):
        _register(client, username="alice")
        resp = _create_coverage(client)
        req_id = resp.get_json()["id"]
        client.post("/api/auth/logout")

        resp = client.post(f"/api/coverage/{req_id}/claim")
        assert resp.status_code == 401

    def test_claim_nonexistent(self, client):
        _register(client, username="bob", display_name="Bob")
        resp = client.post("/api/coverage/9999/claim")
        assert resp.status_code == 404


class TestUnclaimCoverage:
    """POST /api/coverage/<id>/unclaim — unclaim a coverage request."""

    def test_unclaim_success(self, client):
        _register(client, username="alice")
        resp = _create_coverage(client)
        req_id = resp.get_json()["id"]
        client.post("/api/auth/logout")

        _register(client, username="bob", display_name="Bob")
        client.post(f"/api/coverage/{req_id}/claim")
        resp = client.post(f"/api/coverage/{req_id}/unclaim")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "open"
        assert data["claimer_id"] is None

    def test_only_claimer_can_unclaim(self, client):
        _register(client, username="alice")
        resp = _create_coverage(client)
        req_id = resp.get_json()["id"]
        client.post("/api/auth/logout")

        _register(client, username="bob", display_name="Bob")
        client.post(f"/api/coverage/{req_id}/claim")
        client.post("/api/auth/logout")

        # Carol tries to unclaim Bob's claim
        _register(client, username="carol", display_name="Carol")
        resp = client.post(f"/api/coverage/{req_id}/unclaim")
        assert resp.status_code == 403
        assert "claimer" in resp.get_json()["error"].lower()

    def test_unclaim_unauthenticated(self, client):
        _register(client, username="alice")
        resp = _create_coverage(client)
        req_id = resp.get_json()["id"]
        client.post("/api/auth/logout")

        resp = client.post(f"/api/coverage/{req_id}/unclaim")
        assert resp.status_code == 401


class TestCancelCoverage:
    """POST /api/coverage/<id>/cancel — cancel a coverage request."""

    def test_cancel_success(self, client):
        _register(client, username="alice")
        resp = _create_coverage(client)
        req_id = resp.get_json()["id"]
        resp = client.post(f"/api/coverage/{req_id}/cancel")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "cancelled"

    def test_only_requester_can_cancel(self, client):
        _register(client, username="alice")
        resp = _create_coverage(client)
        req_id = resp.get_json()["id"]
        client.post("/api/auth/logout")

        _register(client, username="bob", display_name="Bob")
        resp = client.post(f"/api/coverage/{req_id}/cancel")
        assert resp.status_code == 403
        assert "requester" in resp.get_json()["error"].lower()

    def test_cancel_unauthenticated(self, client):
        _register(client, username="alice")
        resp = _create_coverage(client)
        req_id = resp.get_json()["id"]
        client.post("/api/auth/logout")

        resp = client.post(f"/api/coverage/{req_id}/cancel")
        assert resp.status_code == 401


class TestMyRequests:
    """GET /api/coverage/my-requests — current user's requests."""

    def test_returns_own_requests_only(self, client):
        _register(client, username="alice")
        _create_coverage(client, date="2025-03-15")
        _create_coverage(client, date="2025-03-16")
        client.post("/api/auth/logout")

        _register(client, username="bob", display_name="Bob")
        _create_coverage(client, date="2025-03-17")

        resp = client.get("/api/coverage/my-requests")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["date"] == "2025-03-17"

    def test_my_requests_unauthenticated(self, client):
        resp = client.get("/api/coverage/my-requests")
        assert resp.status_code == 401

    def test_my_requests_empty(self, client):
        _register(client, username="alice")
        resp = client.get("/api/coverage/my-requests")
        assert resp.status_code == 200
        assert resp.get_json() == []
