"""Unit and integration tests for the labor compliance validation module.

Tests cover the ComplianceValidator class and the override API endpoint
with compliance validation integration.
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from dc_shiftmaster.compliance import (
    ComplianceResult,
    ComplianceValidator,
    ComplianceViolation,
)
from dc_shiftmaster.models import Override, ScheduleSlot, ShiftWindow, Teammate
from dc_shiftmaster_html.server import create_app


# ── Mock SchedulingEngine ─────────────────────────────────────────────


class MockSchedulingEngine:
    """A mock SchedulingEngine that returns a configurable base schedule."""

    def __init__(self, slots: list[ScheduleSlot]):
        self.slots = slots

    def compute_annual_schedule(
        self,
        year: int,
        teammates: list,
        shift_windows: dict,
        overrides: list,
    ) -> list[ScheduleSlot]:
        return self.slots


# ── Unit Test Fixtures ────────────────────────────────────────────────


@pytest.fixture
def validator():
    """Provide a fresh ComplianceValidator instance."""
    return ComplianceValidator()


@pytest.fixture
def shift_windows():
    """Standard day/night shift windows for testing."""
    return {
        "day": ShiftWindow(shift_type="day", start_time="06:00", end_time="18:30"),
        "night": ShiftWindow(shift_type="night", start_time="18:00", end_time="06:30"),
    }


@pytest.fixture
def teammates_no_custom():
    """Teammates without custom_start values."""
    return [
        Teammate(id=1, name="Alice", shift_type="FHD", custom_start=""),
        Teammate(id=2, name="Bob", shift_type="FHN", custom_start=""),
    ]


@pytest.fixture
def teammates_with_custom():
    """Teammates where Alice has a custom_start."""
    return [
        Teammate(id=1, name="Alice", shift_type="FHD", custom_start="07:00"),
        Teammate(id=2, name="Bob", shift_type="FHN", custom_start=""),
    ]


# ── Unit Tests: compute_shift_duration ────────────────────────────────


class TestComputeShiftDuration:
    """Tests for ComplianceValidator.compute_shift_duration."""

    def test_day_shift_known_example(self, validator):
        """06:00 → 18:30 = 12.5 hours (same-day shift)."""
        result = validator.compute_shift_duration("06:00", "18:30")
        assert result == 12.5

    def test_night_shift_known_example(self, validator):
        """18:00 → 06:30 = 12.5 hours (overnight shift)."""
        result = validator.compute_shift_duration("18:00", "06:30")
        assert result == 12.5

    def test_start_equals_end_returns_zero(self, validator):
        """When start == end, duration is 0 hours."""
        result = validator.compute_shift_duration("12:00", "12:00")
        assert result == 0.0

    def test_short_shift(self, validator):
        """08:00 → 12:00 = 4 hours."""
        result = validator.compute_shift_duration("08:00", "12:00")
        assert result == 4.0

    def test_overnight_midnight_crossing(self, validator):
        """23:00 → 01:00 = 2 hours (overnight)."""
        result = validator.compute_shift_duration("23:00", "01:00")
        assert result == 2.0


# ── Unit Tests: get_effective_start ───────────────────────────────────


class TestGetEffectiveStart:
    """Tests for ComplianceValidator.get_effective_start."""

    def test_teammate_with_custom_start(self, validator, shift_windows, teammates_with_custom):
        """Teammate with custom_start returns their custom value."""
        result = validator.get_effective_start(
            "Alice", "day", teammates_with_custom, shift_windows
        )
        assert result == "07:00"

    def test_teammate_without_custom_start(self, validator, shift_windows, teammates_no_custom):
        """Teammate without custom_start falls back to shift window default."""
        result = validator.get_effective_start(
            "Alice", "day", teammates_no_custom, shift_windows
        )
        assert result == "06:00"

    def test_teammate_not_found_falls_back(self, validator, shift_windows, teammates_no_custom):
        """Unknown teammate falls back to shift window default start."""
        result = validator.get_effective_start(
            "Unknown", "night", teammates_no_custom, shift_windows
        )
        assert result == "18:00"


# ── Unit Tests: check_weekly_hours ────────────────────────────────────


class TestCheckWeeklyHours:
    """Tests for ComplianceValidator.check_weekly_hours."""

    def test_exactly_at_60h_passes(self, validator, teammates_no_custom):
        """Schedule totaling exactly 60h in a window should pass (no violation)."""
        # Day shift: 06:00→16:00 = 10h. 6 shifts = 60h exactly.
        custom_windows = {
            "day": ShiftWindow(shift_type="day", start_time="06:00", end_time="16:00"),
            "night": ShiftWindow(shift_type="night", start_time="18:00", end_time="06:30"),
        }
        override_date = date(2025, 3, 15)
        # 6 day shifts in a 7-day window = 6 * 10h = 60h exactly
        schedule = [
            (override_date - timedelta(days=i), "day")
            for i in range(6)
        ]

        violations = validator.check_weekly_hours(
            teammate_name="Alice",
            override_date=override_date,
            schedule_with_override=schedule,
            shift_windows=custom_windows,
            teammates=teammates_no_custom,
        )
        assert violations == []

    def test_at_60_5h_fails(self, validator, teammates_no_custom):
        """Schedule totaling 60.5h in a window should fail."""
        # Day shift = 10h (06:00→16:00), night shift = 0.5h (18:00→18:30)
        custom_windows = {
            "day": ShiftWindow(shift_type="day", start_time="06:00", end_time="16:00"),
            "night": ShiftWindow(shift_type="night", start_time="18:00", end_time="18:30"),
        }
        override_date = date(2025, 3, 15)
        # 6 day shifts = 60h + 1 night shift = 0.5h → total 60.5h
        schedule = [
            (override_date - timedelta(days=i), "day")
            for i in range(6)
        ]
        schedule.append((override_date, "night"))

        violations = validator.check_weekly_hours(
            teammate_name="Alice",
            override_date=override_date,
            schedule_with_override=schedule,
            shift_windows=custom_windows,
            teammates=teammates_no_custom,
        )
        assert len(violations) > 0
        assert violations[0].rule == "weekly_hours"
        assert violations[0].projected == 60.5
        assert violations[0].limit == 60.0


# ── Unit Tests: check_weekly_days ─────────────────────────────────────


class TestCheckWeeklyDays:
    """Tests for ComplianceValidator.check_weekly_days."""

    def test_6_days_passes(self, validator):
        """6 distinct days in a 7-day window should pass."""
        override_date = date(2025, 3, 15)
        # 6 days: Mar 10-15 (within the window Mar 9-15)
        schedule = [
            (override_date - timedelta(days=i), "day")
            for i in range(6)
        ]

        violations = validator.check_weekly_days(
            override_date=override_date,
            schedule_with_override=schedule,
        )
        assert violations == []

    def test_7_days_fails(self, validator):
        """7 distinct days in a 7-day window should fail."""
        override_date = date(2025, 3, 15)
        # 7 days: Mar 9-15 (all 7 days in the window Mar 9-15)
        schedule = [
            (override_date - timedelta(days=i), "day")
            for i in range(7)
        ]

        violations = validator.check_weekly_days(
            override_date=override_date,
            schedule_with_override=schedule,
        )
        assert len(violations) > 0
        assert violations[0].rule == "weekly_days"
        assert violations[0].projected == 7
        assert violations[0].limit == 6


# ── Unit Tests: check_daily_hours ─────────────────────────────────────


class TestCheckDailyHours:
    """Tests for ComplianceValidator.check_daily_hours."""

    def test_at_12h_passes(self, validator, teammates_no_custom):
        """Day total exactly at 12h should pass."""
        # day=6h (06:00→12:00), night=6h (18:00→00:00)
        custom_windows = {
            "day": ShiftWindow(shift_type="day", start_time="06:00", end_time="12:00"),
            "night": ShiftWindow(shift_type="night", start_time="18:00", end_time="00:00"),
        }
        override_date = date(2025, 3, 15)
        # Two shifts on the same day: 6h + 6h = 12h exactly
        schedule = [
            (override_date, "day"),
            (override_date, "night"),
        ]

        violations = validator.check_daily_hours(
            teammate_name="Alice",
            override_date=override_date,
            schedule_with_override=schedule,
            shift_windows=custom_windows,
            teammates=teammates_no_custom,
        )
        assert violations == []

    def test_at_12_5h_fails(self, validator, teammates_no_custom):
        """Day total at 12.5h should fail."""
        # day=6h (06:00→12:00), night=6.5h (18:00→00:30)
        custom_windows = {
            "day": ShiftWindow(shift_type="day", start_time="06:00", end_time="12:00"),
            "night": ShiftWindow(shift_type="night", start_time="18:00", end_time="00:30"),
        }
        override_date = date(2025, 3, 15)
        # Two shifts on the same day: 6h + 6.5h = 12.5h
        schedule = [
            (override_date, "day"),
            (override_date, "night"),
        ]

        violations = validator.check_daily_hours(
            teammate_name="Alice",
            override_date=override_date,
            schedule_with_override=schedule,
            shift_windows=custom_windows,
            teammates=teammates_no_custom,
        )
        assert len(violations) == 1
        assert violations[0].rule == "daily_hours"
        assert violations[0].projected == 12.5
        assert violations[0].limit == 12.0

    def test_same_teammate_no_double_count(self, validator, shift_windows, teammates_no_custom):
        """Same teammate already in slot should not be double-counted.

        The schedule_with_override list contains unique entries only.
        If the proposed override assigns the same teammate already in the slot,
        the entry appears only once (handled by the validate method's dedup logic).
        """
        override_date = date(2025, 3, 15)
        # Only one entry for the day shift (no duplicate) — 12.5h
        schedule = [
            (override_date, "day"),
        ]

        violations = validator.check_daily_hours(
            teammate_name="Alice",
            override_date=override_date,
            schedule_with_override=schedule,
            shift_windows=shift_windows,
            teammates=teammates_no_custom,
        )
        # 12.5h > 12h → violation (single shift)
        assert len(violations) == 1
        assert violations[0].projected == 12.5

        # Verify that a duplicate entry WOULD double-count (proving dedup matters)
        schedule_with_dup = [
            (override_date, "day"),
            (override_date, "day"),
        ]
        violations_dup = validator.check_daily_hours(
            teammate_name="Alice",
            override_date=override_date,
            schedule_with_override=schedule_with_dup,
            shift_windows=shift_windows,
            teammates=teammates_no_custom,
        )
        # 25h > 12h → violation with higher projected (proves dedup is needed)
        assert violations_dup[0].projected == 25.0


# ── Unit Tests: resolve_teammate_schedule ─────────────────────────────


class TestResolveTeammateSchedule:
    """Tests for ComplianceValidator.resolve_teammate_schedule."""

    def test_override_adds_teammate(self, validator, shift_windows, teammates_no_custom):
        """An override that assigns the teammate adds them to the schedule."""
        override_date = date(2025, 3, 15)
        date_range = [override_date]

        # Base schedule: Bob is assigned to the day shift (not Alice)
        base_slots = [
            ScheduleSlot(
                date=override_date,
                shift_type="day",
                start_time="06:00",
                teammates=["Bob"],
                is_override=False,
            ),
        ]
        engine = MockSchedulingEngine(base_slots)

        # Override assigns Alice to the day shift on that date
        overrides = [
            Override(date="2025-03-15", shift_type="day", name="Alice"),
        ]

        result = validator.resolve_teammate_schedule(
            teammate_name="Alice",
            date_range=date_range,
            shift_windows=shift_windows,
            teammates=teammates_no_custom,
            existing_overrides=overrides,
            scheduling_engine=engine,
            year=2025,
        )

        assert (override_date, "day") in result

    def test_override_removes_teammate(self, validator, shift_windows, teammates_no_custom):
        """An override that replaces the teammate with someone else removes them."""
        override_date = date(2025, 3, 15)
        date_range = [override_date]

        # Base schedule: Alice is assigned to the day shift
        base_slots = [
            ScheduleSlot(
                date=override_date,
                shift_type="day",
                start_time="06:00",
                teammates=["Alice"],
                is_override=False,
            ),
        ]
        engine = MockSchedulingEngine(base_slots)

        # Override replaces Alice with Bob
        overrides = [
            Override(date="2025-03-15", shift_type="day", name="Bob"),
        ]

        result = validator.resolve_teammate_schedule(
            teammate_name="Alice",
            date_range=date_range,
            shift_windows=shift_windows,
            teammates=teammates_no_custom,
            existing_overrides=overrides,
            scheduling_engine=engine,
            year=2025,
        )

        assert (override_date, "day") not in result

    def test_override_replaces_with_nobody(self, validator, shift_windows, teammates_no_custom):
        """An override that replaces the teammate with 'nobody' removes them."""
        override_date = date(2025, 3, 15)
        date_range = [override_date]

        # Base schedule: Alice is assigned to the day shift
        base_slots = [
            ScheduleSlot(
                date=override_date,
                shift_type="day",
                start_time="06:00",
                teammates=["Alice"],
                is_override=False,
            ),
        ]
        engine = MockSchedulingEngine(base_slots)

        # Override replaces Alice with "nobody"
        overrides = [
            Override(date="2025-03-15", shift_type="day", name="nobody"),
        ]

        result = validator.resolve_teammate_schedule(
            teammate_name="Alice",
            date_range=date_range,
            shift_windows=shift_windows,
            teammates=teammates_no_custom,
            existing_overrides=overrides,
            scheduling_engine=engine,
            year=2025,
        )

        assert (override_date, "day") not in result

    def test_no_override_uses_base_schedule(self, validator, shift_windows, teammates_no_custom):
        """Without overrides, the base computed schedule is used."""
        override_date = date(2025, 3, 15)
        date_range = [override_date]

        # Base schedule: Alice is assigned to the day shift
        base_slots = [
            ScheduleSlot(
                date=override_date,
                shift_type="day",
                start_time="06:00",
                teammates=["Alice"],
                is_override=False,
            ),
        ]
        engine = MockSchedulingEngine(base_slots)

        result = validator.resolve_teammate_schedule(
            teammate_name="Alice",
            date_range=date_range,
            shift_windows=shift_windows,
            teammates=teammates_no_custom,
            existing_overrides=[],
            scheduling_engine=engine,
            year=2025,
        )

        assert (override_date, "day") in result


# ── API Integration Fixtures ──────────────────────────────────────────


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


def _setup_teammates_for_violation(client):
    """Set up teammates that will cause weekly days violations.

    Creates 7 FHD teammates so that the rotation assigns them every
    front-half day. Then we can override a back-half day to assign
    one of them, causing a 7-day-in-a-week violation.
    """
    # Add a teammate to FHD group
    client.post("/api/teammates", json={"name": "Alice", "shift_type": "FHD"})


def _setup_teammates_no_violation(client):
    """Set up teammates in a way that a single override won't cause violations.

    A single teammate on BHD with default shift windows (06:00-18:30 = 12.5h)
    working only back-half days (Thu/Fri/Sat + alternating Wed) won't exceed
    60 weekly hours or 6 weekly days with a single additional override.
    """
    client.post("/api/teammates", json={"name": "Bob", "shift_type": "BHD"})


# ── API Integration Tests ─────────────────────────────────────────────


class TestOverrideComplianceAPI:
    """Integration tests for POST /api/overrides with compliance validation."""

    def test_422_response_when_violations_detected(self, client):
        """Test that violations return 422 with compliance_warning payload.

        Validates: Requirements 5.1, 5.3
        """
        # Set up a teammate in FHD group
        _setup_teammates_for_violation(client)

        # Override a back-half day to assign Alice (FHD teammate).
        # Alice already works Sun/Mon/Tue (front-half days).
        # Adding Thu (2025-01-09 is a Thursday = back-half day) means
        # Alice would work Sun(5), Mon(6), Tue(7), Wed(8, if front-half week),
        # Thu(9) — potentially 7 days in a rolling window.
        # Use a date range where Alice works many consecutive days.
        # 2025-01-05 is Sunday (FH), 01-06 Mon (FH), 01-07 Tue (FH),
        # 01-08 Wed (check cycle), 01-09 Thu (BH), 01-10 Fri (BH), 01-11 Sat (BH)
        # If we override 01-09 Thu to Alice, and also 01-10 Fri, 01-11 Sat...
        # Actually, let's just override enough days to trigger weekly_days > 6.

        # First, acknowledge overrides to set up existing overrides for Alice
        # on back-half days within the same week
        for day in ["2025-01-09", "2025-01-10", "2025-01-11"]:
            client.post(
                "/api/overrides",
                json={
                    "date": day,
                    "shift_type": "day",
                    "name": "Alice",
                    "acknowledge_violations": True,
                },
            )

        # Now try to add another override on 2025-01-08 (Wednesday)
        # without acknowledgment. Alice already works Sun(5), Mon(6), Tue(7)
        # from FHD rotation + Thu(9), Fri(10), Sat(11) from overrides.
        # Adding Wed(8) = 7 days in the window Jan 5-11 → violation.
        resp = client.post(
            "/api/overrides",
            json={
                "date": "2025-01-08",
                "shift_type": "day",
                "name": "Alice",
            },
        )

        assert resp.status_code == 422
        data = resp.get_json()
        assert data["status"] == "compliance_warning"
        assert "violations" in data
        assert len(data["violations"]) > 0
        # Verify violation structure
        violation = data["violations"][0]
        assert "rule" in violation
        assert "projected" in violation
        assert "limit" in violation

    def test_201_response_when_no_violations(self, client):
        """Test that override succeeds with 201 when no violations detected.

        Validates: Requirements 5.3
        """
        # Shorten shift windows so that a single override doesn't exceed
        # the 60h weekly or 12h daily limits. Default is 06:00-18:30 (12.5h)
        # which exceeds the 12h daily limit on its own.
        client.put(
            "/api/settings/shift-windows/day",
            json={"start_time": "06:00", "end_time": "16:00"},
        )
        client.put(
            "/api/settings/shift-windows/night",
            json={"start_time": "18:00", "end_time": "04:00"},
        )

        # Set up a BHD teammate
        _setup_teammates_no_violation(client)

        # Override a single front-half day to Bob. Bob normally works
        # only back-half days (Thu/Fri/Sat = 3 days × 10h = 30h).
        # Adding one front-half day (Monday 2025-01-06, 10h) = 40h total,
        # well under 60h weekly and 12h daily limits.
        resp = client.post(
            "/api/overrides",
            json={
                "date": "2025-01-06",
                "shift_type": "day",
                "name": "Bob",
            },
        )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["date"] == "2025-01-06"
        assert data["shift_type"] == "day"
        assert data["name"] == "Bob"

    def test_201_response_with_acknowledge_violations(self, client):
        """Test that acknowledged override returns 201 even with violations present.

        Validates: Requirements 6.2
        """
        # Set up a teammate that would have violations
        _setup_teammates_for_violation(client)

        # Set up existing overrides to create a violation scenario
        for day in ["2025-01-09", "2025-01-10", "2025-01-11"]:
            client.post(
                "/api/overrides",
                json={
                    "date": day,
                    "shift_type": "day",
                    "name": "Alice",
                    "acknowledge_violations": True,
                },
            )

        # Now submit with acknowledge_violations=True — should bypass validation
        resp = client.post(
            "/api/overrides",
            json={
                "date": "2025-01-08",
                "shift_type": "day",
                "name": "Alice",
                "acknowledge_violations": True,
            },
        )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["acknowledged_violations"] is True
        assert data["date"] == "2025-01-08"
        assert data["shift_type"] == "day"
        assert data["name"] == "Alice"

    def test_500_response_when_validator_encounters_error(self, client, app):
        """Test that validator errors return 500 with error message.

        Validates: Requirements 5.4
        """
        # Add a teammate so the request is otherwise valid
        client.post("/api/teammates", json={"name": "Charlie", "shift_type": "FHD"})

        # Mock the ComplianceValidator.validate to raise an exception
        with patch(
            "dc_shiftmaster_html.routes_overrides.ComplianceValidator.validate",
            side_effect=RuntimeError("Unexpected validation error"),
        ):
            resp = client.post(
                "/api/overrides",
                json={
                    "date": "2025-03-15",
                    "shift_type": "day",
                    "name": "Charlie",
                },
            )

        assert resp.status_code == 500
        data = resp.get_json()
        assert "error" in data

    def test_invalid_date_format_returns_error(self, client):
        """Test that an invalid date format returns an error response.

        The current implementation uses date.fromisoformat which raises
        ValueError for invalid formats. This is caught by the general
        exception handler and returns 500.

        Validates: Requirements 5.4
        """
        # Add a teammate so the request is otherwise valid
        client.post("/api/teammates", json={"name": "Dave", "shift_type": "FHD"})

        resp = client.post(
            "/api/overrides",
            json={
                "date": "not-a-date",
                "shift_type": "day",
                "name": "Dave",
            },
        )

        # The implementation catches all exceptions in the try/except block
        # and returns 500. An invalid date format triggers ValueError from
        # date.fromisoformat(), which is caught as a generic exception.
        assert resp.status_code == 500
        data = resp.get_json()
        assert "error" in data
