"""Tests for dc_shiftmaster_html.server — Flask app factory and CLI."""

import os
import sys

import pytest

from dc_shiftmaster_html.server import create_app, main
from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster.scheduling import SchedulingEngine


class TestCreateApp:
    """Tests for the create_app factory function."""

    def test_returns_flask_app(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        app = create_app(db_path=db_path)
        assert app is not None
        assert app.name == "dc_shiftmaster_html.server"

    def test_stores_database_manager_on_config(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        app = create_app(db_path=db_path)
        assert isinstance(app.config["db"], DatabaseManager)

    def test_stores_scheduling_engine_on_config(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        app = create_app(db_path=db_path)
        assert isinstance(app.config["engine"], SchedulingEngine)

    def test_stores_host_and_port_on_config(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        app = create_app(db_path=db_path, host="0.0.0.0", port=8080)
        assert app.config["HOST"] == "0.0.0.0"
        assert app.config["PORT"] == 8080

    def test_default_host_and_port(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        app = create_app(db_path=db_path)
        assert app.config["HOST"] == "127.0.0.1"
        assert app.config["PORT"] == 5000

    def test_serves_index_html_on_root(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        app = create_app(db_path=db_path)
        app.config["TESTING"] = True
        with app.test_client() as client:
            resp = client.get("/")
            assert resp.status_code == 200
            assert b"DC-ShiftMaster Pro" in resp.data

    def test_exits_on_invalid_db_path(self):
        with pytest.raises(SystemExit) as exc_info:
            # A path inside a non-existent directory should fail
            create_app(db_path="/nonexistent_dir/sub/test.db")
        assert exc_info.value.code == 1

    def test_static_files_served(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        app = create_app(db_path=db_path)
        with app.test_client() as client:
            resp = client.get("/static/index.html")
            assert resp.status_code == 200

    def test_websocket_coverage_route_registered(self, tmp_path):
        """Verify the /ws/coverage WebSocket route is registered on the app."""
        db_path = str(tmp_path / "test.db")
        app = create_app(db_path=db_path)
        url_rules = [rule.rule for rule in app.url_map.iter_rules()]
        assert "/ws/coverage" in url_rules


class TestMainCLI:
    """Tests for the main() CLI entry point argument parsing."""

    def test_cli_custom_args(self, tmp_path, monkeypatch, capsys):
        """main() should parse --host, --port, --db-path and print the URL."""
        db_path = str(tmp_path / "cli_test.db")

        # Patch app.run so we don't actually start a server
        started = {}

        def fake_run(self_app, host=None, port=None, **kwargs):
            started["host"] = host
            started["port"] = port

        from dc_shiftmaster_html import server as srv_mod

        monkeypatch.setattr("flask.Flask.run", fake_run)

        main(["--host", "0.0.0.0", "--port", "9999", "--db-path", db_path])

        assert started["host"] == "0.0.0.0"
        assert started["port"] == 9999
        captured = capsys.readouterr()
        assert "http://0.0.0.0:9999" in captured.out

    def test_cli_env_var_fallback(self, tmp_path, monkeypatch, capsys):
        """main() should fall back to environment variables when no CLI args given."""
        db_path = str(tmp_path / "env_test.db")

        monkeypatch.setenv("SHIFTMASTER_HOST", "10.0.0.1")
        monkeypatch.setenv("SHIFTMASTER_PORT", "7777")
        monkeypatch.setenv("SHIFTMASTER_DB_PATH", db_path)

        started = {}

        def fake_run(self_app, host=None, port=None, **kwargs):
            started["host"] = host
            started["port"] = port

        monkeypatch.setattr("flask.Flask.run", fake_run)

        main([])

        assert started["host"] == "10.0.0.1"
        assert started["port"] == 7777
        captured = capsys.readouterr()
        assert "http://10.0.0.1:7777" in captured.out

    def test_cli_defaults(self, tmp_path, monkeypatch, capsys):
        """main() should use defaults when no args or env vars are set."""
        db_path = str(tmp_path / "default_test.db")

        # Clear any env vars that might be set
        monkeypatch.delenv("SHIFTMASTER_HOST", raising=False)
        monkeypatch.delenv("SHIFTMASTER_PORT", raising=False)
        monkeypatch.delenv("SHIFTMASTER_DB_PATH", raising=False)

        started = {}

        def fake_run(self_app, host=None, port=None, **kwargs):
            started["host"] = host
            started["port"] = port

        monkeypatch.setattr("flask.Flask.run", fake_run)

        # Pass --db-path so it uses a temp file instead of cwd
        main(["--db-path", db_path])

        assert started["host"] == "127.0.0.1"
        assert started["port"] == 5000
        captured = capsys.readouterr()
        assert "http://127.0.0.1:5000" in captured.out


class TestHealthEndpoint:
    """Tests for the GET /health endpoint (Requirements 11.2, 11.3)."""

    def test_health_returns_200_when_db_healthy(self, tmp_path):
        db_path = str(tmp_path / "health_test.db")
        app = create_app(db_path=db_path)
        app.config["TESTING"] = True
        with app.test_client() as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.get_json() == {"status": "healthy"}

    def test_health_returns_503_when_db_unavailable(self, tmp_path):
        db_path = str(tmp_path / "health_test.db")
        app = create_app(db_path=db_path)
        app.config["TESTING"] = True
        # Break the DB connection so SELECT 1 raises
        app.config["db"].conn.close()
        with app.test_client() as client:
            resp = client.get("/health")
            assert resp.status_code == 503
            data = resp.get_json()
            assert data["status"] == "unhealthy"
            assert data["reason"] == "database unavailable"


class TestRateLimiting:
    """Tests for rate limiting on auth endpoints (Requirements 7.1, 7.2, 7.3)."""

    def _make_app(self, tmp_path):
        """Create app with rate limiter enabled."""
        db_path = str(tmp_path / "rate_test.db")
        app = create_app(db_path=db_path)
        app.config["TESTING"] = True
        # Re-enable the limiter for rate limit testing
        from dc_shiftmaster_html.extensions import limiter
        limiter.enabled = True
        return app, limiter

    def test_login_rate_limit_429_after_10_requests(self, tmp_path):
        """Exceeding 10 requests/min on /api/auth/login returns 429."""
        app, limiter_inst = self._make_app(tmp_path)
        try:
            with app.test_client() as client:
                for i in range(10):
                    resp = client.post(
                        "/api/auth/login",
                        json={"username": "test", "password": "test"},
                    )
                    assert resp.status_code != 429, (
                        f"Request {i + 1} returned 429 unexpectedly"
                    )

                # 11th request should be rate-limited
                resp = client.post(
                    "/api/auth/login",
                    json={"username": "test", "password": "test"},
                )
                assert resp.status_code == 429
                assert resp.get_json() == {"error": "Rate limit exceeded"}
        finally:
            limiter_inst.enabled = False
            limiter_inst.reset()

    def test_register_rate_limit_429_after_5_requests(self, tmp_path):
        """Exceeding 5 requests/min on /api/auth/register returns 429."""
        app, limiter_inst = self._make_app(tmp_path)
        try:
            with app.test_client() as client:
                for i in range(5):
                    resp = client.post(
                        "/api/auth/register",
                        json={
                            "username": "test",
                            "password": "test",
                            "display_name": "Test",
                        },
                    )
                    assert resp.status_code != 429, (
                        f"Request {i + 1} returned 429 unexpectedly"
                    )

                # 6th request should be rate-limited
                resp = client.post(
                    "/api/auth/register",
                    json={
                        "username": "test",
                        "password": "test",
                        "display_name": "Test",
                    },
                )
                assert resp.status_code == 429
                assert resp.get_json() == {"error": "Rate limit exceeded"}
        finally:
            limiter_inst.enabled = False
            limiter_inst.reset()


class TestTeammatesEndpointSecurity:
    """Tests for teammates endpoint security (Requirements 8.1, 8.2, 8.3, 8.4)."""

    def _make_app(self, tmp_path):
        """Create app WITHOUT TESTING=True so auth gate is active."""
        db_path = str(tmp_path / "security_test.db")
        app = create_app(db_path=db_path)
        # Do NOT set TESTING=True — we want the auth gate active
        return app

    def test_unauthenticated_get_teammates_returns_401(self, tmp_path):
        """Unauthenticated GET /api/teammates returns 401 with error JSON."""
        app = self._make_app(tmp_path)
        with app.test_client() as client:
            resp = client.get("/api/teammates")
            assert resp.status_code == 401
            assert resp.get_json() == {"error": "Not authenticated"}

    def test_public_teammate_names_returns_names_without_auth(self, tmp_path):
        """GET /api/public/teammate-names returns JSON array of name strings without auth."""
        app = self._make_app(tmp_path)
        # Seed some teammates directly via the DatabaseManager
        db = app.config["db"]
        db.add_teammate("Alice", "FHD", "")
        db.add_teammate("Bob", "BHN", "")
        with app.test_client() as client:
            resp = client.get("/api/public/teammate-names")
            assert resp.status_code == 200
            data = resp.get_json()
            assert isinstance(data, list)
            assert "Alice" in data
            assert "Bob" in data
            # Verify only strings (no dicts with IDs or shift types)
            for item in data:
                assert isinstance(item, str)
