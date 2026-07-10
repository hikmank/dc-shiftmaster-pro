"""Tests for auth API routes (routes_auth.py)."""

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
    """Helper to register a user."""
    return client.post("/api/auth/register", json={
        "username": username,
        "password": password,
        "display_name": display_name,
        "teammate_name": teammate_name,
    })


class TestRegister:
    def test_register_success(self, client):
        resp = _register(client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["username"] == "alice"
        assert data["display_name"] == "Alice"
        assert "password_hash" not in data
        assert "id" in data

    def test_register_sets_session(self, client):
        _register(client)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.get_json()["username"] == "alice"

    def test_register_with_teammate_name(self, client):
        resp = _register(client, teammate_name="Alice T")
        assert resp.status_code == 201
        assert resp.get_json()["teammate_name"] == "Alice T"

    def test_register_duplicate_username(self, client):
        _register(client, username="bob")
        resp = _register(client, username="bob")
        assert resp.status_code == 400
        assert "already exists" in resp.get_json()["error"]

    def test_register_missing_username(self, client):
        resp = client.post("/api/auth/register", json={
            "password": "secret", "display_name": "X",
        })
        assert resp.status_code == 400
        assert "username" in resp.get_json()["error"]

    def test_register_missing_password(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "bob", "display_name": "Bob",
        })
        assert resp.status_code == 400
        assert "password" in resp.get_json()["error"]

    def test_register_missing_display_name(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "bob", "password": "secret",
        })
        assert resp.status_code == 400
        assert "display_name" in resp.get_json()["error"]

    def test_register_no_json_body(self, client):
        resp = client.post("/api/auth/register", data="not json")
        assert resp.status_code == 400


class TestLogin:
    def test_login_success(self, client):
        _register(client, username="carol", password="pass123", display_name="Carol")
        # Logout first so we test login independently
        client.post("/api/auth/logout")
        resp = client.post("/api/auth/login", json={
            "username": "carol", "password": "pass123",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["username"] == "carol"
        assert "password_hash" not in data

    def test_login_wrong_password(self, client):
        _register(client, username="dave", password="correct")
        client.post("/api/auth/logout")
        resp = client.post("/api/auth/login", json={
            "username": "dave", "password": "wrong",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "nobody", "password": "x",
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/auth/login", json={"username": "x"})
        assert resp.status_code == 400

    def test_login_no_json_body(self, client):
        resp = client.post("/api/auth/login", data="not json")
        assert resp.status_code == 400

    def test_login_sets_session(self, client):
        _register(client, username="eve", password="pw")
        client.post("/api/auth/logout")
        client.post("/api/auth/login", json={"username": "eve", "password": "pw"})
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.get_json()["username"] == "eve"


class TestLogout:
    def test_logout_clears_session(self, client):
        _register(client)
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 204
        me_resp = client.get("/api/auth/me")
        assert me_resp.status_code == 401


class TestMe:
    def test_me_authenticated(self, client):
        _register(client, username="frank", display_name="Frank")
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["username"] == "frank"
        assert data["display_name"] == "Frank"
        assert "password_hash" not in data

    def test_me_not_authenticated(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401
