"""Property-based tests for bulk-delete DatabaseManager methods.

Feature: delete-schedule-overrides
Uses hypothesis library to validate correctness properties from the design document.
"""

from datetime import date

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster_html.server import create_app


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

SHIFT_TYPES = ["day", "night"]


@st.composite
def override_entry(draw: st.DrawFn) -> tuple[str, str, str]:
    """Generate a (date_str, shift_type, name) tuple for an override."""
    d = draw(st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31)))
    date_str = d.isoformat()
    shift_type = draw(st.sampled_from(SHIFT_TYPES))
    name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=20,
        )
    )
    return (date_str, shift_type, name)


@st.composite
def override_set(draw: st.DrawFn) -> list[tuple[str, str, str]]:
    """Generate a list of unique overrides (unique by date+shift_type key)."""
    entries = draw(st.lists(override_entry(), min_size=0, max_size=20))
    # Deduplicate by (date, shift_type) key since that's the primary key
    seen = set()
    unique = []
    for date_str, shift_type, name in entries:
        key = (date_str, shift_type)
        if key not in seen:
            seen.add(key)
            unique.append((date_str, shift_type, name))
    return unique


@st.composite
def date_range(draw: st.DrawFn) -> tuple[str, str]:
    """Generate a valid date range [start, end] where start <= end."""
    d1 = draw(st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31)))
    d2 = draw(st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31)))
    start = min(d1, d2)
    end = max(d1, d2)
    return (start.isoformat(), end.isoformat())


@st.composite
def multi_year_override_set(draw: st.DrawFn) -> tuple[list[tuple[str, str, str]], list[int]]:
    """Generate a set of overrides spanning multiple years with unique (date, shift_type) keys.

    Returns a tuple of (overrides_list, years_list) where overrides span at least 2 years.
    """
    # Pick 2-4 distinct years
    years = draw(st.lists(
        st.integers(min_value=2000, max_value=2100),
        min_size=2, max_size=4, unique=True
    ))
    overrides = []
    seen_keys = set()
    # Generate at least 1 override per year to ensure multi-year coverage
    for year in years:
        num = draw(st.integers(min_value=1, max_value=6))
        for _ in range(num):
            month = draw(st.integers(min_value=1, max_value=12))
            day = draw(st.integers(min_value=1, max_value=28))
            shift_type = draw(st.sampled_from(SHIFT_TYPES))
            date_str = f"{year}-{month:02d}-{day:02d}"
            key = (date_str, shift_type)
            if key not in seen_keys:
                seen_keys.add(key)
                name = draw(st.text(
                    alphabet=st.characters(whitelist_categories=("L", "N")),
                    min_size=1,
                    max_size=10,
                ))
                overrides.append((date_str, shift_type, name))
    return overrides, years


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_team(tmp_path):
    """Provide a fresh DatabaseManager with a team created."""
    db_path = str(tmp_path / "test_props.db")
    manager = DatabaseManager(db_path)
    user_id = manager.create_user("propuser", "hash", "Prop User")
    team = manager.create_team("PRP001", "Prop Team", user_id)
    yield manager, team["id"]
    manager.conn.close()


def _seed(db: DatabaseManager, team_id: int, overrides: list[tuple[str, str, str]]):
    """Insert overrides for a team."""
    for date_str, shift_type, name in overrides:
        db.set_override(date_str, shift_type, name, team_id=team_id)


def _get_all_overrides(db: DatabaseManager, team_id: int) -> set[tuple[str, str, str]]:
    """Get all overrides for a team across all years as a set of (date, shift_type, name)."""
    results = set()
    for year in range(2000, 2101):
        for o in db.get_overrides(year, team_id=team_id):
            results.add((o.date, o.shift_type, o.name))
    return results


def _get_overrides_fast(db: DatabaseManager, team_id: int) -> set[tuple[str, str, str]]:
    """Get all overrides for a team using a direct query (faster than year iteration)."""
    cursor = db.conn.cursor()
    cursor.execute(
        "SELECT date, shift_type, name FROM overrides WHERE team_id = ?",
        (team_id,),
    )
    return {(row[0], row[1], row[2]) for row in cursor.fetchall()}


# ---------------------------------------------------------------------------
# Property 3: Range Delete Correctness
# Tag: "Feature: delete-schedule-overrides, Property 3: Range Delete Correctness"
# ---------------------------------------------------------------------------


class TestRangeDeleteCorrectness:
    """**Validates: Requirements 2.1, 5.1**

    For any set of overrides and any valid date range [start, end] where start <= end,
    after a bulk-delete-by-range operation:
    (a) no overrides with dates within the range SHALL remain in the database for the
        current team, and
    (b) all overrides with dates outside the range SHALL be preserved unchanged.
    """

    @settings(max_examples=100)
    @given(overrides=override_set(), range_dates=date_range())
    def test_range_delete_correctness(self, overrides, range_dates, tmp_path_factory):
        """Property 3: Range Delete Correctness.

        Feature: delete-schedule-overrides, Property 3: Range Delete Correctness
        """
        # Setup: fresh DB per example
        tmp_path = tmp_path_factory.mktemp("range_del")
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)
        user_id = db.create_user("user", "hash", "User")
        team = db.create_team("TST001", "Team", user_id)
        team_id = team["id"]

        # Seed overrides
        _seed(db, team_id, overrides)

        start_date, end_date = range_dates

        # Partition overrides into inside/outside the range
        inside = {
            (d, st_, n) for d, st_, n in overrides
            if start_date <= d <= end_date
        }
        outside = {
            (d, st_, n) for d, st_, n in overrides
            if not (start_date <= d <= end_date)
        }

        # Execute the bulk delete
        db.bulk_delete_overrides_by_range(start_date, end_date, team_id=team_id)

        # Get remaining overrides
        remaining = _get_overrides_fast(db, team_id)

        # (a) No overrides with dates within the range shall remain
        remaining_inside = {
            (d, st_, n) for d, st_, n in remaining
            if start_date <= d <= end_date
        }
        assert remaining_inside == set(), (
            f"Overrides within range [{start_date}, {end_date}] should be deleted, "
            f"but found: {remaining_inside}"
        )

        # (b) All overrides with dates outside the range shall be preserved unchanged
        assert remaining == outside, (
            f"Overrides outside range [{start_date}, {end_date}] should be preserved. "
            f"Expected: {outside}, Got: {remaining}"
        )

        db.conn.close()


# ---------------------------------------------------------------------------
# Property 5: Year Delete Correctness
# Tag: "Feature: delete-schedule-overrides, Property 5: Year Delete Correctness"
# ---------------------------------------------------------------------------


class TestYearDeleteCorrectness:
    """**Validates: Requirements 3.1**

    For any set of overrides spanning multiple years and any target year,
    after a clear-all-year operation:
    (a) no overrides for the target year SHALL remain for the current team, and
    (b) all overrides for other years SHALL be preserved unchanged.
    """

    @settings(max_examples=100)
    @given(data=st.data())
    def test_year_delete_correctness(self, data, tmp_path_factory):
        """Property 5: Year Delete Correctness.

        Feature: delete-schedule-overrides, Property 5: Year Delete Correctness
        """
        # Generate multi-year overrides and pick a target year
        overrides, years = data.draw(multi_year_override_set())
        assume(len(overrides) > 0)

        target_year = data.draw(st.sampled_from(years))

        # Setup: fresh DB per example
        tmp_path = tmp_path_factory.mktemp("year_del")
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)
        user_id = db.create_user("user", "hash", "User")
        team = db.create_team("TST001", "Team", user_id)
        team_id = team["id"]

        # Seed overrides
        _seed(db, team_id, overrides)

        # Partition overrides: target year vs other years
        target_prefix = f"{target_year}-"
        expected_remaining = {
            (d, st_, n) for d, st_, n in overrides
            if not d.startswith(target_prefix)
        }

        # Execute the year delete
        db.bulk_delete_overrides_by_year(target_year, team_id=team_id)

        # Get remaining overrides
        remaining = _get_overrides_fast(db, team_id)

        # (a) No overrides for the target year SHALL remain
        remaining_target = {
            (d, st_, n) for d, st_, n in remaining
            if d.startswith(target_prefix)
        }
        assert remaining_target == set(), (
            f"Overrides for target year {target_year} should all be deleted, "
            f"but found: {remaining_target}"
        )

        # (b) All overrides for other years SHALL be preserved unchanged
        assert remaining == expected_remaining, (
            f"Overrides for other years should be preserved unchanged. "
            f"Missing: {expected_remaining - remaining}, "
            f"Extra: {remaining - expected_remaining}"
        )

        db.conn.close()


# ---------------------------------------------------------------------------
# Property 9: Team Isolation
# Tag: "Feature: delete-schedule-overrides, Property 9: Team Isolation"
# ---------------------------------------------------------------------------


@st.composite
def two_team_override_sets(draw: st.DrawFn) -> tuple[
    list[tuple[str, str, str]], list[tuple[str, str, str]]
]:
    """Generate two disjoint override sets for two different teams.

    Since the PK is (date, shift_type) without team_id, we must ensure
    team A and team B use non-overlapping (date, shift_type) keys.
    We achieve this by giving team A only 'day' shifts and team B only 'night' shifts.
    """
    names = st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=15,
    )

    # Team A gets 'day' shift overrides
    team_a_dates = draw(
        st.lists(
            st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
            min_size=1,
            max_size=10,
            unique=True,
        )
    )
    team_a_overrides = []
    for d in team_a_dates:
        name = draw(names)
        team_a_overrides.append((d.isoformat(), "day", name))

    # Team B gets 'night' shift overrides
    team_b_dates = draw(
        st.lists(
            st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
            min_size=1,
            max_size=10,
            unique=True,
        )
    )
    team_b_overrides = []
    for d in team_b_dates:
        name = draw(names)
        team_b_overrides.append((d.isoformat(), "night", name))

    return (team_a_overrides, team_b_overrides)


@st.composite
def delete_mode(draw: st.DrawFn, team_a_overrides: list[tuple[str, str, str]]) -> tuple[str, dict]:
    """Generate a random delete mode and parameters applicable to team A's overrides."""
    mode = draw(st.sampled_from(["range", "keys", "year"]))

    if mode == "range":
        # Generate a date range that covers some or all of team A's dates
        d1 = draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))
        d2 = draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))
        start = min(d1, d2)
        end = max(d1, d2)
        return ("range", {"start_date": start.isoformat(), "end_date": end.isoformat()})

    elif mode == "keys":
        # Select a random subset of team A's keys
        if team_a_overrides:
            keys_to_delete = draw(
                st.lists(
                    st.sampled_from([(d, st_) for d, st_, _ in team_a_overrides]),
                    min_size=1,
                    max_size=len(team_a_overrides),
                    unique=True,
                )
            )
        else:
            keys_to_delete = []
        return ("keys", {"keys": keys_to_delete})

    else:  # year
        # Pick a year from team A's dates or a random year
        if team_a_overrides:
            years = list({int(d[:4]) for d, _, _ in team_a_overrides})
            year = draw(st.sampled_from(years))
        else:
            year = draw(st.integers(min_value=2020, max_value=2030))
        return ("year", {"year": year})


class TestTeamIsolation:
    """**Validates: Requirements 5.5**

    For any bulk-delete operation executed in the context of team A,
    all overrides belonging to team B (where B != A) SHALL remain completely
    unchanged regardless of the deletion mode or parameters.
    """

    @settings(max_examples=100)
    @given(data=st.data(), team_sets=two_team_override_sets())
    def test_team_isolation(self, data, team_sets, tmp_path_factory):
        """Property 9: Team Isolation.

        Feature: delete-schedule-overrides, Property 9: Team Isolation
        """
        team_a_overrides, team_b_overrides = team_sets

        # Setup: fresh DB per example
        tmp_path = tmp_path_factory.mktemp("team_iso")
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)
        user_id = db.create_user("user", "hash", "User")
        team_a = db.create_team("TMA001", "Team A", user_id)
        team_b = db.create_team("TMB001", "Team B", user_id)
        team_a_id = team_a["id"]
        team_b_id = team_b["id"]

        # Seed overrides for both teams
        _seed(db, team_a_id, team_a_overrides)
        _seed(db, team_b_id, team_b_overrides)

        # Snapshot team B's overrides before deletion
        team_b_before = _get_overrides_fast(db, team_b_id)

        # Generate and execute a random delete mode targeting team A
        mode, params = data.draw(delete_mode(team_a_overrides))

        if mode == "range":
            db.bulk_delete_overrides_by_range(
                params["start_date"], params["end_date"], team_id=team_a_id
            )
        elif mode == "keys":
            db.bulk_delete_overrides_by_keys(params["keys"], team_id=team_a_id)
        else:  # year
            db.bulk_delete_overrides_by_year(params["year"], team_id=team_a_id)

        # Verify team B's overrides are completely unchanged
        team_b_after = _get_overrides_fast(db, team_b_id)
        assert team_b_after == team_b_before, (
            f"Team B overrides were modified by team A's {mode} delete. "
            f"Before: {team_b_before}, After: {team_b_after}"
        )

        db.conn.close()


# ---------------------------------------------------------------------------
# Property 4: Invalid Range Rejection
# Tag: "Feature: delete-schedule-overrides, Property 4: Invalid Range Rejection"
# ---------------------------------------------------------------------------


@st.composite
def invalid_date_range(draw: st.DrawFn) -> tuple[str, str]:
    """Generate a date pair where start_date > end_date."""
    d1 = draw(st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31)))
    d2 = draw(st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31)))
    assume(d1 != d2)
    start = max(d1, d2)
    end = min(d1, d2)
    # start > end guaranteed
    return (start.isoformat(), end.isoformat())


class TestInvalidRangeRejection:
    """**Validates: Requirements 2.2**

    For any pair of dates where start_date > end_date, the bulk-delete endpoint
    SHALL return a 400 error and SHALL NOT delete any overrides from the database.
    """

    @settings(max_examples=100, deadline=None)
    @given(overrides=override_set(), dates=invalid_date_range())
    def test_invalid_range_rejection(self, overrides, dates, tmp_path_factory):
        """Property 4: Invalid Range Rejection.

        Feature: delete-schedule-overrides, Property 4: Invalid Range Rejection
        """
        # Setup: fresh app and DB per example
        tmp_path = tmp_path_factory.mktemp("inv_range")
        db_path = str(tmp_path / "test.db")
        app = create_app(db_path=db_path)
        app.config["TESTING"] = True

        # Get the database and the team created by migration
        db = app.config["db"]
        cursor = db.conn.cursor()
        cursor.execute("SELECT id FROM team_profiles LIMIT 1")
        row = cursor.fetchone()
        team_id = row[0]

        _seed(db, team_id, overrides)

        # Snapshot overrides before the request
        overrides_before = _get_overrides_fast(db, team_id)

        start_date, end_date = dates

        # Make the DELETE request with the invalid range (start > end)
        with app.test_client() as client:
            resp = client.delete(
                "/api/overrides/bulk",
                json={
                    "mode": "range",
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )

        # (a) SHALL return a 400 error
        assert resp.status_code == 400, (
            f"Expected 400 for invalid range [{start_date}, {end_date}], "
            f"got {resp.status_code}"
        )

        # (b) SHALL NOT delete any overrides from the database
        overrides_after = _get_overrides_fast(db, team_id)
        assert overrides_after == overrides_before, (
            f"No overrides should be deleted for invalid range [{start_date}, {end_date}]. "
            f"Before: {len(overrides_before)}, After: {len(overrides_after)}"
        )

        db.conn.close()


# ---------------------------------------------------------------------------
# Property 8: Invalid Request All-or-Nothing Rejection
# Tag: "Feature: delete-schedule-overrides, Property 8: Invalid Request All-or-Nothing Rejection"
# ---------------------------------------------------------------------------


@st.composite
def valid_override_key(draw: st.DrawFn) -> dict:
    """Generate a valid override key dict with date and shift_type."""
    d = draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))
    shift_type = draw(st.sampled_from(SHIFT_TYPES))
    return {"date": d.isoformat(), "shift_type": shift_type}


@st.composite
def invalid_override_key(draw: st.DrawFn) -> dict:
    """Generate an invalid override key (missing date, missing shift_type, or malformed date)."""
    kind = draw(st.sampled_from(["missing_date", "missing_shift_type", "malformed_date"]))

    if kind == "missing_date":
        # Has shift_type but no date key
        shift_type = draw(st.sampled_from(SHIFT_TYPES))
        return {"shift_type": shift_type}
    elif kind == "missing_shift_type":
        # Has date but no shift_type key
        d = draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))
        return {"date": d.isoformat()}
    else:
        # Malformed date format
        malformed = draw(st.sampled_from([
            "not-a-date",
            "2025-13-45",
            "20250101",
            "01/15/2025",
            "2025/03/15",
            "abcd-ef-gh",
            "",
        ]))
        shift_type = draw(st.sampled_from(SHIFT_TYPES))
        return {"date": malformed, "shift_type": shift_type}


@st.composite
def mixed_keys_with_at_least_one_invalid(draw: st.DrawFn) -> list[dict]:
    """Generate a keys list containing at least one invalid key mixed with valid ones."""
    valid_keys = draw(st.lists(valid_override_key(), min_size=1, max_size=5))
    invalid_keys = draw(st.lists(invalid_override_key(), min_size=1, max_size=3))
    all_keys = valid_keys + invalid_keys
    # Shuffle so invalid keys aren't always at the end
    shuffled = draw(st.permutations(all_keys))
    return list(shuffled)


def _get_all_overrides_unscoped(db: DatabaseManager) -> set[tuple[str, str, str]]:
    """Get all overrides regardless of team_id (handles NULL team_id)."""
    cursor = db.conn.cursor()
    cursor.execute("SELECT date, shift_type, name FROM overrides")
    return {(row[0], row[1], row[2]) for row in cursor.fetchall()}


class TestAllOrNothingRejection:
    """**Validates: Requirements 5.4**

    For any bulk-delete request containing invalid override identifiers (missing date,
    missing shift_type, malformed date format, or empty keys list), the system SHALL
    return a 400 status code AND SHALL NOT delete any overrides — even if some keys
    in the request are valid.
    """

    @settings(max_examples=100, deadline=None)
    @given(mixed_keys=mixed_keys_with_at_least_one_invalid())
    def test_invalid_keys_rejected_entirely(self, mixed_keys, tmp_path_factory):
        """Property 8: Invalid Request All-or-Nothing Rejection.

        Feature: delete-schedule-overrides, Property 8: Invalid Request All-or-Nothing Rejection
        """
        from dc_shiftmaster_html.server import create_app

        # Setup: fresh app and DB per example
        tmp_path = tmp_path_factory.mktemp("allornone")
        db_path = str(tmp_path / "test.db")
        app = create_app(db_path=db_path)
        app.config["TESTING"] = True

        db = app.config["db"]

        # Seed some overrides into the database so we can verify none get deleted
        seed_overrides = [
            ("2025-01-15", "day", "Alice"),
            ("2025-02-20", "night", "Bob"),
            ("2025-03-10", "day", "Charlie"),
            ("2025-06-01", "night", "Diana"),
            ("2025-09-25", "day", "Eve"),
        ]
        for date_str, shift_type, name in seed_overrides:
            db.set_override(date_str, shift_type, name)

        # Snapshot overrides before the request
        overrides_before = _get_all_overrides_unscoped(db)

        # Make the bulk delete request with mixed valid/invalid keys
        with app.test_client() as client:
            resp = client.delete(
                "/api/overrides/bulk",
                json={"mode": "keys", "keys": mixed_keys},
            )

        # Verify 400 response
        assert resp.status_code == 400, (
            f"Expected 400 for invalid keys but got {resp.status_code}. "
            f"Keys: {mixed_keys}"
        )

        # Verify no overrides were deleted (all seeded overrides still present)
        overrides_after = _get_all_overrides_unscoped(db)
        assert overrides_after == overrides_before, (
            f"Overrides were modified despite 400 rejection. "
            f"Before: {overrides_before}, After: {overrides_after}"
        )

        db.conn.close()

    @settings(max_examples=100, deadline=None)
    @given(data=st.data())
    def test_empty_keys_list_rejected(self, data, tmp_path_factory):
        """Property 8: Empty keys list is also rejected with 400 and no deletions.

        Feature: delete-schedule-overrides, Property 8: Invalid Request All-or-Nothing Rejection
        """
        from dc_shiftmaster_html.server import create_app

        # Setup: fresh app and DB per example
        tmp_path = tmp_path_factory.mktemp("emptykeys")
        db_path = str(tmp_path / "test.db")
        app = create_app(db_path=db_path)
        app.config["TESTING"] = True

        db = app.config["db"]

        # Seed some overrides
        seed_overrides = [
            ("2025-04-10", "day", "Frank"),
            ("2025-05-20", "night", "Grace"),
        ]
        for date_str, shift_type, name in seed_overrides:
            db.set_override(date_str, shift_type, name)

        # Snapshot overrides before the request
        overrides_before = _get_all_overrides_unscoped(db)

        # Make the bulk delete request with empty keys list
        with app.test_client() as client:
            resp = client.delete(
                "/api/overrides/bulk",
                json={"mode": "keys", "keys": []},
            )

        # Verify 400 response
        assert resp.status_code == 400, (
            f"Expected 400 for empty keys list but got {resp.status_code}."
        )

        # Verify no overrides were deleted
        overrides_after = _get_all_overrides_unscoped(db)
        assert overrides_after == overrides_before, (
            f"Overrides were modified despite 400 rejection for empty keys. "
            f"Before: {overrides_before}, After: {overrides_after}"
        )

        db.conn.close()
