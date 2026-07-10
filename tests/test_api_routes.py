"""Tests for all DC-ShiftMaster HTML API route blueprints."""

import io
import json
import os
import sqlite3

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


# ── Schedule endpoints (4.1) ──────────────────────────────────────────


class TestScheduleAPI:
    def test_get_schedule_valid(self, client):
        resp = client.get("/api/schedule/2025/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        # January has 31 days, 2 slots per day = 62
        assert len(data) == 62

    def test_get_schedule_fields(self, client):
        resp = client.get("/api/schedule/2025/6")
        data = resp.get_json()
        slot = data[0]
        assert "date" in slot
        assert "shift_type" in slot
        assert "start_time" in slot
        assert "teammates" in slot
        assert "is_override" in slot
        assert "teammate_starts" in slot

    def test_get_schedule_invalid_year_low(self, client):
        resp = client.get("/api/schedule/1800/1")
        assert resp.status_code == 400

    def test_get_schedule_invalid_year_high(self, client):
        resp = client.get("/api/schedule/2200/1")
        assert resp.status_code == 400

    def test_get_schedule_invalid_month_zero(self, client):
        resp = client.get("/api/schedule/2025/0")
        assert resp.status_code == 400

    def test_get_schedule_invalid_month_13(self, client):
        resp = client.get("/api/schedule/2025/13")
        assert resp.status_code == 400

    def test_get_schedule_february_leap_year(self, client):
        resp = client.get("/api/schedule/2024/2")
        assert resp.status_code == 200
        data = resp.get_json()
        # 2024 is leap year, Feb has 29 days -> 58 slots
        assert len(data) == 58


# ── Teammate endpoints (5.1–5.5) ─────────────────────────────────────


class TestTeammateAPI:
    def test_get_teammates_empty(self, client):
        resp = client.get("/api/teammates")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_add_teammate(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "Alice", "shift_type": "FHD"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Alice"
        assert data["shift_type"] == "FHD"
        assert data["id"] is not None

    def test_add_teammate_with_custom_start(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "Bob", "shift_type": "BHN", "custom_start": "07:30"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["custom_start"] == "07:30"

    def test_add_teammate_empty_name(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "", "shift_type": "FHD"},
        )
        assert resp.status_code == 400
        assert "empty" in resp.get_json()["error"].lower()

    def test_add_teammate_whitespace_name(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "   ", "shift_type": "FHD"},
        )
        assert resp.status_code == 400

    def test_add_teammate_invalid_custom_start(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "Eve", "shift_type": "FHD", "custom_start": "25:00"},
        )
        assert resp.status_code == 400

    def test_get_teammates_after_add(self, client):
        client.post("/api/teammates", json={"name": "Alice", "shift_type": "FHD"})
        resp = client.get("/api/teammates")
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "Alice"

    def test_update_teammate(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "Alice", "shift_type": "FHD"},
        )
        tid = resp.get_json()["id"]
        resp = client.put(
            f"/api/teammates/{tid}",
            json={"name": "Alice B", "shift_type": "BHD"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Alice B"
        assert resp.get_json()["shift_type"] == "BHD"

    def test_update_teammate_empty_name(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "Alice", "shift_type": "FHD"},
        )
        tid = resp.get_json()["id"]
        resp = client.put(
            f"/api/teammates/{tid}",
            json={"name": "", "shift_type": "FHD"},
        )
        assert resp.status_code == 400

    def test_update_teammate_invalid_custom_start(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "Alice", "shift_type": "FHD"},
        )
        tid = resp.get_json()["id"]
        resp = client.put(
            f"/api/teammates/{tid}",
            json={"name": "Alice", "shift_type": "FHD", "custom_start": "bad"},
        )
        assert resp.status_code == 400

    def test_delete_teammate(self, client):
        resp = client.post(
            "/api/teammates",
            json={"name": "Alice", "shift_type": "FHD"},
        )
        tid = resp.get_json()["id"]
        resp = client.delete(f"/api/teammates/{tid}")
        assert resp.status_code == 204

        # Verify deleted
        resp = client.get("/api/teammates")
        assert resp.get_json() == []

    def test_import_csv(self, client):
        csv_content = "Alice,FHD\nBob,BHN,07:30\nCharlie,INVALID\n"
        data = {"file": (io.BytesIO(csv_content.encode()), "team.csv")}
        resp = client.post(
            "/api/teammates/import-csv",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["imported_count"] == 2
        assert 3 in result["skipped_rows"]

    def test_import_csv_no_file(self, client):
        resp = client.post("/api/teammates/import-csv")
        assert resp.status_code == 400


# ── Override endpoints (6.1–6.3) ─────────────────────────────────────


class TestOverrideAPI:
    def test_get_overrides_empty(self, client):
        resp = client.get("/api/overrides/2025")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_set_override(self, client):
        resp = client.post(
            "/api/overrides",
            json={"date": "2025-03-15", "shift_type": "day", "name": "Alice",
                  "acknowledge_violations": True},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["date"] == "2025-03-15"
        assert data["name"] == "Alice"

    def test_get_overrides_after_set(self, client):
        client.post(
            "/api/overrides",
            json={"date": "2025-03-15", "shift_type": "day", "name": "Alice",
                  "acknowledge_violations": True},
        )
        resp = client.get("/api/overrides/2025")
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "Alice"

    def test_remove_override(self, client):
        client.post(
            "/api/overrides",
            json={"date": "2025-03-15", "shift_type": "day", "name": "Alice",
                  "acknowledge_violations": True},
        )
        resp = client.delete(
            "/api/overrides",
            json={"date": "2025-03-15", "shift_type": "day"},
        )
        assert resp.status_code == 204

        resp = client.get("/api/overrides/2025")
        assert resp.get_json() == []

    def test_override_year_filtering(self, client):
        client.post(
            "/api/overrides",
            json={"date": "2025-06-01", "shift_type": "day", "name": "A",
                  "acknowledge_violations": True},
        )
        client.post(
            "/api/overrides",
            json={"date": "2024-06-01", "shift_type": "day", "name": "B",
                  "acknowledge_violations": True},
        )
        resp = client.get("/api/overrides/2025")
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "A"


# ── Settings endpoints (7.1–7.2) ─────────────────────────────────────


class TestSettingsAPI:
    def test_get_shift_windows(self, client):
        resp = client.get("/api/settings/shift-windows")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "day" in data
        assert "night" in data
        assert data["day"]["start_time"] == "06:00"

    def test_update_shift_window(self, client):
        resp = client.put(
            "/api/settings/shift-windows/day",
            json={"start_time": "07:00", "end_time": "19:00"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["start_time"] == "07:00"

        # Verify persisted
        resp = client.get("/api/settings/shift-windows")
        assert resp.get_json()["day"]["start_time"] == "07:00"

    def test_update_shift_window_invalid_start(self, client):
        resp = client.put(
            "/api/settings/shift-windows/day",
            json={"start_time": "25:00", "end_time": "19:00"},
        )
        assert resp.status_code == 400

    def test_update_shift_window_invalid_end(self, client):
        resp = client.put(
            "/api/settings/shift-windows/day",
            json={"start_time": "07:00", "end_time": "bad"},
        )
        assert resp.status_code == 400

    def test_get_region_default(self, client):
        resp = client.get("/api/settings/region")
        assert resp.status_code == 200
        assert resp.get_json()["region"] == ""

    def test_set_region(self, client):
        resp = client.put(
            "/api/settings/region",
            json={"region": "ATL68"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["region"] == "ATL68"

        resp = client.get("/api/settings/region")
        assert resp.get_json()["region"] == "ATL68"


# ── Export endpoints (8.1–8.3) ────────────────────────────────────────


class TestExportAPI:
    def test_export_csv(self, client):
        resp = client.get("/api/export/2025/csv")
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/csv")
        # Default region is SITE
        assert "SITE_2025_schedule.csv" in resp.headers.get("Content-Disposition", "")

    def test_export_json(self, client):
        resp = client.get("/api/export/2025/json")
        assert resp.status_code == 200
        assert "SITE_2025_schedule.json" in resp.headers.get("Content-Disposition", "")

    def test_export_xlsx(self, client):
        resp = client.get("/api/export/2025/xlsx")
        assert resp.status_code == 200
        assert "SITE_2025_schedule.xlsx" in resp.headers.get("Content-Disposition", "")

    def test_export_csv_with_region(self, app):
        app.config["region"] = "ATL68"
        with app.test_client() as client:
            resp = client.get("/api/export/2025/csv")
            assert "ATL68_2025_schedule.csv" in resp.headers.get("Content-Disposition", "")

    def test_export_csv_empty_region_defaults_to_site(self, app):
        app.config["region"] = ""
        with app.test_client() as client:
            resp = client.get("/api/export/2025/csv")
            assert "SITE_2025_schedule.csv" in resp.headers.get("Content-Disposition", "")


# ── Import DB endpoint (9.1) ─────────────────────────────────────────


class TestImportDBAPI:
    def _make_test_db(self, path):
        """Create a valid teammates.db file for import testing."""
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE teammates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                shift_type TEXT NOT NULL,
                custom_start TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE shift_windows (
                shift_type TEXT PRIMARY KEY,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL
            );
            CREATE TABLE overrides (
                date TEXT NOT NULL,
                shift_type TEXT NOT NULL,
                name TEXT NOT NULL,
                PRIMARY KEY (date, shift_type)
            );
            INSERT INTO teammates (name, shift_type) VALUES ('ImportAlice', 'FHD');
            INSERT INTO teammates (name, shift_type) VALUES ('ImportBob', 'BHN');
            INSERT INTO shift_windows VALUES ('day', '07:00', '19:00');
            INSERT INTO shift_windows VALUES ('night', '19:00', '07:00');
            INSERT INTO overrides VALUES ('2025-06-01', 'day', 'ImportAlice');
        """)
        conn.commit()
        conn.close()

    def test_import_db_success(self, client, tmp_path):
        db_file = str(tmp_path / "import.db")
        self._make_test_db(db_file)

        with open(db_file, "rb") as f:
            data = {"file": (f, "import.db")}
            resp = client.post(
                "/api/import-db",
                data=data,
                content_type="multipart/form-data",
            )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["teammates_count"] == 2
        assert result["shift_windows_count"] == 2
        assert result["overrides_count"] == 1

    def test_import_db_no_file(self, client):
        resp = client.post("/api/import-db")
        assert resp.status_code == 400

    def test_import_db_invalid_file(self, client, tmp_path):
        bad_file = tmp_path / "bad.db"
        bad_file.write_text("this is not sqlite")

        with open(str(bad_file), "rb") as f:
            data = {"file": (f, "bad.db")}
            resp = client.post(
                "/api/import-db",
                data=data,
                content_type="multipart/form-data",
            )
        assert resp.status_code == 400
        assert "Invalid" in resp.get_json()["error"]

    def test_import_db_missing_tables(self, client, tmp_path):
        db_file = str(tmp_path / "partial.db")
        conn = sqlite3.connect(db_file)
        conn.execute("CREATE TABLE teammates (id INTEGER PRIMARY KEY, name TEXT, shift_type TEXT)")
        conn.commit()
        conn.close()

        with open(db_file, "rb") as f:
            data = {"file": (f, "partial.db")}
            resp = client.post(
                "/api/import-db",
                data=data,
                content_type="multipart/form-data",
            )
        assert resp.status_code == 400

    def test_import_db_merges_teammates(self, client, tmp_path):
        """Imported teammates should be added alongside existing ones."""
        # Add an existing teammate first
        client.post("/api/teammates", json={"name": "Existing", "shift_type": "FHD"})

        db_file = str(tmp_path / "import.db")
        self._make_test_db(db_file)

        with open(db_file, "rb") as f:
            data = {"file": (f, "import.db")}
            client.post(
                "/api/import-db",
                data=data,
                content_type="multipart/form-data",
            )

        resp = client.get("/api/teammates")
        names = [t["name"] for t in resp.get_json()]
        assert "Existing" in names
        assert "ImportAlice" in names
        assert "ImportBob" in names
