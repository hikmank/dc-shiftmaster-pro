"""Unit tests for Custom shift type API validation in routes_teammates.py.

Tests cover:
- Adding/updating teammates with Custom shift type and valid custom_days
- Validation rejection when custom_days is empty or missing for Custom type
- Validation rejection when custom_days contains invalid day values
- Standard shift types ignore/clear custom_days
- GET response includes custom_days field
- Invalid shift type error message includes Custom
"""

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


class TestCustomShiftTypePost:
    """Tests for POST /api/teammates with Custom shift type."""

    def test_add_custom_teammate_valid_days(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "Alice", "shift_type": "Custom", "custom_days": ["Mon", "Wed", "Fri"]},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["shift_type"] == "Custom"
        assert set(data["custom_days"]) == {"Mon", "Wed", "Fri"}

    def test_add_custom_teammate_all_days(self, client):
        all_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        resp = client.post(
            "/api/teammates",
            json={"name": "Bob", "shift_type": "Custom", "custom_days": all_days},
        )
        assert resp.status_code == 201
        assert set(resp.get_json()["custom_days"]) == set(all_days)

    def test_add_custom_teammate_single_day(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "Carol", "shift_type": "Custom", "custom_days": ["Sat"]},
        )
        assert resp.status_code == 201
        assert resp.get_json()["custom_days"] == ["Sat"]

    def test_add_custom_teammate_empty_days_rejected(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "Dave", "shift_type": "Custom", "custom_days": []},
        )
        assert resp.status_code == 400
        assert "At least one day must be selected" in resp.get_json()["error"]

    def test_add_custom_teammate_missing_days_rejected(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "Eve", "shift_type": "Custom"},
        )
        assert resp.status_code == 400
        assert "At least one day must be selected" in resp.get_json()["error"]

    def test_add_custom_teammate_invalid_day_rejected(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "Frank", "shift_type": "Custom", "custom_days": ["Mon", "InvalidDay"]},
        )
        assert resp.status_code == 400
        assert "Invalid day(s)" in resp.get_json()["error"]

    def test_add_standard_shift_ignores_custom_days(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "Grace", "shift_type": "FHD", "custom_days": ["Mon", "Tue"]},
        )
        assert resp.status_code == 201
        assert resp.get_json()["custom_days"] == []

    def test_add_invalid_shift_type_includes_custom_in_message(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "Hank", "shift_type": "INVALID"},
        )
        assert resp.status_code == 400
        assert "Custom" in resp.get_json()["error"]


class TestCustomShiftTypePut:
    """Tests for PUT /api/teammates/<id> with Custom shift type."""

    def _create_teammate(self, client, name="Test", shift_type="FHD", custom_days=None):
        payload = {"name": name, "shift_type": shift_type}
        if custom_days:
            payload["custom_days"] = custom_days
        resp = client.post("/api/teammates", json=payload)
        return resp.get_json()["id"]

    def test_update_to_custom_valid_days(self, client):
        tid = self._create_teammate(client)
        resp = client.put(
            f"/api/teammates/{tid}",
            json={"name": "Test", "shift_type": "Custom", "custom_days": ["Tue", "Thu"]},
        )
        assert resp.status_code == 200
        assert set(resp.get_json()["custom_days"]) == {"Tue", "Thu"}

    def test_update_custom_empty_days_rejected(self, client):
        tid = self._create_teammate(client, shift_type="Custom", custom_days=["Mon"])
        resp = client.put(
            f"/api/teammates/{tid}",
            json={"name": "Test", "shift_type": "Custom", "custom_days": []},
        )
        assert resp.status_code == 400
        assert "At least one day must be selected" in resp.get_json()["error"]

    def test_update_custom_invalid_day_rejected(self, client):
        tid = self._create_teammate(client, shift_type="Custom", custom_days=["Mon"])
        resp = client.put(
            f"/api/teammates/{tid}",
            json={"name": "Test", "shift_type": "Custom", "custom_days": ["Monday"]},
        )
        assert resp.status_code == 400
        assert "Invalid day(s)" in resp.get_json()["error"]

    def test_update_from_custom_to_standard_clears_days(self, client):
        tid = self._create_teammate(client, shift_type="Custom", custom_days=["Mon", "Fri"])
        resp = client.put(
            f"/api/teammates/{tid}",
            json={"name": "Test", "shift_type": "BHD", "custom_days": ["Mon", "Fri"]},
        )
        assert resp.status_code == 200
        assert resp.get_json()["custom_days"] == []

    def test_update_invalid_shift_type_includes_custom(self, client):
        tid = self._create_teammate(client)
        resp = client.put(
            f"/api/teammates/{tid}",
            json={"name": "Test", "shift_type": "BAD"},
        )
        assert resp.status_code == 400
        assert "Custom" in resp.get_json()["error"]


class TestCustomShiftTypeGet:
    """Tests for GET /api/teammates returning custom_days."""

    def test_get_includes_custom_days_for_custom_teammate(self, client):
        client.post(
            "/api/teammates",
            json={"name": "Alice", "shift_type": "Custom", "custom_days": ["Mon", "Wed"]},
        )
        resp = client.get("/api/teammates")
        data = resp.get_json()
        assert len(data) == 1
        assert "custom_days" in data[0]
        assert set(data[0]["custom_days"]) == {"Mon", "Wed"}

    def test_get_includes_empty_custom_days_for_standard_teammate(self, client):
        client.post(
            "/api/teammates",
            json={"name": "Bob", "shift_type": "FHD"},
        )
        resp = client.get("/api/teammates")
        data = resp.get_json()
        assert len(data) == 1
        assert "custom_days" in data[0]
        assert data[0]["custom_days"] == []

    def test_get_multiple_teammates_mixed_types(self, client):
        client.post(
            "/api/teammates",
            json={"name": "Alice", "shift_type": "Custom", "custom_days": ["Sat", "Sun"]},
        )
        client.post(
            "/api/teammates",
            json={"name": "Bob", "shift_type": "FHN"},
        )
        resp = client.get("/api/teammates")
        data = resp.get_json()
        assert len(data) == 2
        custom_teammate = next(t for t in data if t["name"] == "Alice")
        standard_teammate = next(t for t in data if t["name"] == "Bob")
        assert set(custom_teammate["custom_days"]) == {"Sat", "Sun"}
        assert standard_teammate["custom_days"] == []
