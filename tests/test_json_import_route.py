"""Quick integration tests for the /api/import/schedule-json route."""

import io
import json

import pytest
from flask import Flask, g

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster_html.routes_ics import ics_bp


@pytest.fixture
def app():
    """Create a test Flask app with ics_bp registered."""
    app = Flask(__name__)
    db = DatabaseManager(":memory:")
    app.config["db"] = db
    app.register_blueprint(ics_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _upload(client, data_bytes, filename="test.json", query=""):
    """Helper to POST a file to /api/import/schedule-json."""
    url = f"/api/import/schedule-json{query}"
    return client.post(
        url,
        data={"file": (io.BytesIO(data_bytes), filename)},
        content_type="multipart/form-data",
    )


class TestNoFile:
    def test_no_file_returns_400(self, client):
        resp = client.post("/api/import/schedule-json")
        assert resp.status_code == 400
        assert "No file uploaded" in resp.get_json()["error"]


class TestFileTooLarge:
    def test_exceeds_5mb_returns_413(self, client):
        big = b"x" * (5 * 1024 * 1024 + 1)
        resp = _upload(client, big)
        assert resp.status_code == 413
        assert "too large" in resp.get_json()["error"].lower()


class TestInvalidJSON:
    def test_not_json_returns_400(self, client):
        resp = _upload(client, b"not json at all")
        assert resp.status_code == 400

    def test_not_array_returns_400(self, client):
        resp = _upload(client, json.dumps({"key": "val"}).encode())
        assert resp.status_code == 400
        assert "array" in resp.get_json()["error"].lower()


class TestSuccessfulImport:
    def test_valid_entries_return_200(self, client):
        data = json.dumps([
            {"date": "2025-03-15", "shift_type": "day", "name": "Alice"},
            {"date": "2025-03-16", "shift_type": "night", "name": "Bob"},
        ]).encode()
        resp = _upload(client, data)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["imported_count"] == 2
        assert body["skipped_count"] == 0
        assert body["conflicts"] == []
        assert body["errors"] == []


class TestConflictDetection:
    def test_conflict_without_overwrite_returns_422(self, app, client):
        data = json.dumps([
            {"date": "2025-06-01", "shift_type": "day", "name": "Alice"},
        ]).encode()
        # First import succeeds
        resp = _upload(client, data)
        assert resp.status_code == 200

        # Second import conflicts
        resp = _upload(client, data)
        assert resp.status_code == 422
        body = resp.get_json()
        assert body["imported_count"] == 0
        assert body["skipped_count"] == 1
        assert len(body["conflicts"]) == 1
        assert body["conflicts"][0]["date"] == "2025-06-01"
        assert body["conflicts"][0]["shift_type"] == "day"
        assert body["conflicts"][0]["existing_name"] == "Alice"

    def test_overwrite_true_replaces_existing(self, client):
        data = json.dumps([
            {"date": "2025-07-01", "shift_type": "night", "name": "Alice"},
        ]).encode()
        # First import
        resp = _upload(client, data)
        assert resp.status_code == 200

        # Overwrite with new name
        new_data = json.dumps([
            {"date": "2025-07-01", "shift_type": "night", "name": "Charlie"},
        ]).encode()
        resp = _upload(client, new_data, query="?overwrite=true")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["imported_count"] == 1
        assert body["skipped_count"] == 0
        assert body["conflicts"] == []


class TestPartialImport:
    def test_mix_of_valid_and_invalid_entries(self, client):
        data = json.dumps([
            {"date": "2025-08-01", "shift_type": "day", "name": "Alice"},
            {"date": "bad-date", "shift_type": "day", "name": "Bob"},
            {"date": "2025-08-02", "shift_type": "invalid", "name": "Charlie"},
        ]).encode()
        resp = _upload(client, data)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["imported_count"] == 1
        assert len(body["errors"]) == 2


class TestAllInvalid:
    def test_all_invalid_returns_422(self, client):
        data = json.dumps([
            {"date": "bad", "shift_type": "day", "name": "Alice"},
            {"shift_type": "night", "name": "Bob"},
        ]).encode()
        resp = _upload(client, data)
        assert resp.status_code == 422
        body = resp.get_json()
        assert body["imported_count"] == 0
        assert len(body["errors"]) >= 2
