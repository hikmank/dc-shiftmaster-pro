"""Unit tests for bulk-delete API route handlers.

Verifies correct HTTP status codes (200, 400, 500) and response shapes
for DELETE /api/overrides/bulk and POST /api/overrides/bulk/preview endpoints.

Validates: Requirements 5.1, 5.2, 5.3, 5.4
"""

import pytest

from dc_shiftmaster_html.server import create_app


@pytest.fixture
def app(tmp_path):
    """Create a Flask test app with a fresh temp database."""
    db_path = str(tmp_path / "test_bulk_api.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _seed_overrides(app, overrides):
    """Seed overrides into the test database via the DatabaseManager."""
    db = app.config["db"]
    for date_str, shift_type, name in overrides:
        db.set_override(date_str, shift_type, name)


# ── Valid range delete ────────────────────────────────────────────────


class TestBulkDeleteRangeMode:
    """Valid range delete → 200, {"deleted_count": N}"""

    def test_valid_range_delete(self, app, client):
        _seed_overrides(app, [
            ("2025-01-15", "day", "Alice"),
            ("2025-01-20", "night", "Bob"),
            ("2025-02-01", "day", "Charlie"),
        ])
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "range", "start_date": "2025-01-01", "end_date": "2025-01-31"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"deleted_count": 2}

    def test_range_delete_zero_overrides(self, client):
        """Edge case: delete 0 overrides returns {deleted_count: 0}, not an error."""
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "range", "start_date": "2025-06-01", "end_date": "2025-06-30"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"deleted_count": 0}


# ── Valid keys delete ─────────────────────────────────────────────────


class TestBulkDeleteKeysMode:
    """Valid keys delete → 200, {"deleted_count": N}"""

    def test_valid_keys_delete(self, app, client):
        _seed_overrides(app, [
            ("2025-01-15", "day", "Alice"),
            ("2025-01-15", "night", "Bob"),
            ("2025-01-20", "day", "Charlie"),
        ])
        resp = client.delete(
            "/api/overrides/bulk",
            json={
                "mode": "keys",
                "keys": [
                    {"date": "2025-01-15", "day": "day", "shift_type": "day"},
                    {"date": "2025-01-20", "shift_type": "day"},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"deleted_count": 2}

    def test_keys_delete_nonexistent_keys(self, client):
        """Delete with keys that don't exist returns deleted_count: 0."""
        resp = client.delete(
            "/api/overrides/bulk",
            json={
                "mode": "keys",
                "keys": [{"date": "2025-09-01", "shift_type": "day"}],
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"deleted_count": 0}


# ── Valid year delete ─────────────────────────────────────────────────


class TestBulkDeleteYearMode:
    """Valid year delete → 200, {"deleted_count": N}"""

    def test_valid_year_delete(self, app, client):
        _seed_overrides(app, [
            ("2025-01-15", "day", "Alice"),
            ("2025-06-20", "night", "Bob"),
            ("2026-01-01", "day", "Charlie"),
        ])
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "year", "year": 2025},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"deleted_count": 2}

    def test_year_delete_zero_overrides(self, client):
        """Edge case: delete 0 overrides for year returns {deleted_count: 0}."""
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "year", "year": 2030},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"deleted_count": 0}


# ── Preview endpoints ─────────────────────────────────────────────────


class TestPreviewEndpoint:
    """Preview endpoints → 200, {"count": N}"""

    def test_preview_range(self, app, client):
        _seed_overrides(app, [
            ("2025-01-15", "day", "Alice"),
            ("2025-01-20", "night", "Bob"),
            ("2025-02-01", "day", "Charlie"),
        ])
        resp = client.post(
            "/api/overrides/bulk/preview",
            json={"mode": "range", "start_date": "2025-01-01", "end_date": "2025-01-31"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"count": 2}

    def test_preview_keys(self, app, client):
        _seed_overrides(app, [
            ("2025-01-15", "day", "Alice"),
            ("2025-01-15", "night", "Bob"),
        ])
        resp = client.post(
            "/api/overrides/bulk/preview",
            json={
                "mode": "keys",
                "keys": [
                    {"date": "2025-01-15", "shift_type": "day"},
                    {"date": "2025-01-15", "shift_type": "night"},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "count" in data
        assert isinstance(data["count"], int)

    def test_preview_year(self, app, client):
        _seed_overrides(app, [
            ("2025-03-01", "day", "Alice"),
            ("2025-07-15", "night", "Bob"),
            ("2026-01-01", "day", "Charlie"),
        ])
        resp = client.post(
            "/api/overrides/bulk/preview",
            json={"mode": "year", "year": 2025},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"count": 2}

    def test_preview_zero_count(self, client):
        """Preview returns count: 0 when no overrides match, not an error."""
        resp = client.post(
            "/api/overrides/bulk/preview",
            json={"mode": "range", "start_date": "2030-01-01", "end_date": "2030-12-31"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"count": 0}


# ── Invalid mode ──────────────────────────────────────────────────────


class TestInvalidMode:
    """Invalid mode → 400, error message."""

    def test_invalid_mode_string(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "invalid"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Invalid mode. Must be 'range', 'keys', or 'year'."

    def test_missing_mode(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Invalid mode. Must be 'range', 'keys', or 'year'."

    def test_invalid_mode_preview(self, client):
        resp = client.post(
            "/api/overrides/bulk/preview",
            json={"mode": "all"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Invalid mode. Must be 'range', 'keys', or 'year'."


# ── Range validation errors ───────────────────────────────────────────


class TestRangeValidationErrors:
    """Range-mode validation → 400 with expected error messages."""

    def test_start_after_end(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "range", "start_date": "2025-03-15", "end_date": "2025-01-01"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "start_date must be on or before end_date."

    def test_invalid_start_date_format(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "range", "start_date": "2025/01/01", "end_date": "2025-01-31"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Invalid date format. Use YYYY-MM-DD."

    def test_invalid_end_date_format(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "range", "start_date": "2025-01-01", "end_date": "Jan-31-2025"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Invalid date format. Use YYYY-MM-DD."

    def test_nonsense_date(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "range", "start_date": "not-a-date", "end_date": "2025-01-31"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Invalid date format. Use YYYY-MM-DD."


# ── Keys validation errors ────────────────────────────────────────────


class TestKeysValidationErrors:
    """Keys-mode validation → 400 with expected error messages."""

    def test_empty_keys_list(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "keys", "keys": []},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "keys array must not be empty."

    def test_invalid_key_missing_date(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "keys", "keys": [{"shift_type": "day"}]},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Invalid key at index 0: missing 'date' or 'shift_type'."

    def test_invalid_key_missing_shift_type(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "keys", "keys": [{"date": "2025-01-15"}]},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Invalid key at index 0: missing 'date' or 'shift_type'."

    def test_invalid_key_at_index_1(self, client):
        """Error message references the correct index."""
        resp = client.delete(
            "/api/overrides/bulk",
            json={
                "mode": "keys",
                "keys": [
                    {"date": "2025-01-15", "shift_type": "day"},
                    {"date": "2025-01-20"},  # missing shift_type
                ],
            },
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Invalid key at index 1: missing 'date' or 'shift_type'."

    def test_invalid_date_in_key(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={
                "mode": "keys",
                "keys": [{"date": "2025-13-01", "shift_type": "day"}],
            },
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Invalid date format. Use YYYY-MM-DD."

    def test_invalid_date_format_in_key(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={
                "mode": "keys",
                "keys": [{"date": "01/15/2025", "shift_type": "day"}],
            },
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Invalid date format. Use YYYY-MM-DD."

    def test_keys_not_a_list(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "keys", "keys": "not-a-list"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "keys array must not be empty."


# ── Year validation errors ────────────────────────────────────────────


class TestYearValidationErrors:
    """Year-mode validation → 400 with expected error messages."""

    def test_non_integer_year(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "year", "year": "twenty-five"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "year must be a 4-digit integer."

    def test_two_digit_year(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "year", "year": 25},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "year must be a 4-digit integer."

    def test_year_too_large(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "year", "year": 10000},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "year must be a 4-digit integer."

    def test_year_float(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "year", "year": 2025.5},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "year must be a 4-digit integer."


# ── Edge case: delete zero overrides ──────────────────────────────────


class TestEdgeCaseZeroDeletes:
    """Edge case: deletion of zero overrides returns {deleted_count: 0}, not an error."""

    def test_range_no_matches(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "range", "start_date": "2099-01-01", "end_date": "2099-12-31"},
        )
        assert resp.status_code == 200
        assert resp.get_json() == {"deleted_count": 0}

    def test_keys_no_matches(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={
                "mode": "keys",
                "keys": [{"date": "2099-01-01", "shift_type": "day"}],
            },
        )
        assert resp.status_code == 200
        assert resp.get_json() == {"deleted_count": 0}

    def test_year_no_matches(self, client):
        resp = client.delete(
            "/api/overrides/bulk",
            json={"mode": "year", "year": 2099},
        )
        assert resp.status_code == 200
        assert resp.get_json() == {"deleted_count": 0}
