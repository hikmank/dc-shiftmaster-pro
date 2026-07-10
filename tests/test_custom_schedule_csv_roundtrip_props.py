"""Property-based tests for CSV export/import round-trip (custom-schedule-shift).

Feature: custom-schedule-shift
Property 3: CSV export/import round-trip for custom days
**Validates: Requirements 5.1, 5.3**

Uses Hypothesis to generate Custom teammates with random non-empty day subsets,
export to CSV (matching the team.js format), import the CSV via the API,
and assert the resulting custom_days sets are identical (order-independent).
"""

import io

from hypothesis import given, settings
from hypothesis import strategies as st

from dc_shiftmaster_html.server import create_app


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@st.composite
def non_empty_day_subset(draw: st.DrawFn) -> list[str]:
    """Generate a random non-empty subset of {Mon, Tue, Wed, Thu, Fri, Sat, Sun}."""
    return draw(
        st.lists(st.sampled_from(ALL_DAYS), min_size=1, max_size=7, unique=True)
    )


@st.composite
def teammate_name_for_csv(draw: st.DrawFn) -> str:
    """Generate a valid teammate name safe for CSV round-tripping.

    Uses alphanumeric characters to avoid CSV quoting edge cases unrelated
    to the property we're testing (semicolon day encoding/decoding).
    """
    return draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=20,
        ).filter(lambda s: s.strip())
    )


# ---------------------------------------------------------------------------
# Property 3: CSV export/import round-trip for custom days
# Feature: custom-schedule-shift, Property 3: CSV export/import round-trip
# **Validates: Requirements 5.1, 5.3**
# ---------------------------------------------------------------------------


@given(
    name=teammate_name_for_csv(),
    custom_days=non_empty_day_subset(),
)
@settings(max_examples=100, deadline=None)
def test_csv_export_import_round_trip_custom_days(name, custom_days, tmp_path_factory):
    """For any Custom teammate with a non-empty custom_days list, exporting to CSV
    and then importing that CSV SHALL produce a teammate record with the same
    custom_days set (order-independent).

    Strategy:
    1. Build a CSV row matching the team.js export format:
       name,shift_type,custom_start,custom_days (semicolon-separated days)
    2. Upload via POST /api/teammates/import-csv
    3. GET /api/teammates and verify the custom_days match (as sets)
    """
    tmp_path = tmp_path_factory.mktemp("db")
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    with app.test_client() as client:
        # Build the CSV string matching team.js export format:
        # Header: name,shift_type,custom_start,custom_days
        # Row: "name",Custom,,Mon;Wed;Fri
        days_csv_value = ";".join(custom_days)
        # Quote the name the same way team.js does (double-quote with escaped internal quotes)
        escaped_name = name.replace('"', '""')
        csv_content = (
            f"name,shift_type,custom_start,custom_days\n"
            f'"{escaped_name}",Custom,,{days_csv_value}\n'
        )

        # Import via multipart file upload
        data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "team.csv")}
        import_resp = client.post(
            "/api/teammates/import-csv",
            data=data,
            content_type="multipart/form-data",
        )

        assert import_resp.status_code == 200, (
            f"Import failed with status {import_resp.status_code}: "
            f"{import_resp.get_json()}"
        )
        import_result = import_resp.get_json()

        # The header row might be counted — check that at least 1 was imported
        # The CSV reader will see row 1 as header "name,shift_type,custom_start,custom_days"
        # which has name="name" and shift_type="shift_type" — this would be skipped as invalid.
        # Row 2 is the actual data row.
        assert import_result["imported_count"] >= 1, (
            f"Expected at least 1 imported teammate, got "
            f"imported_count={import_result['imported_count']}, "
            f"skipped_rows={import_result['skipped_rows']}"
        )

        # Retrieve teammates and find the imported one
        get_resp = client.get("/api/teammates")
        assert get_resp.status_code == 200
        teammates = get_resp.get_json()

        # Find our teammate by name
        matching = [t for t in teammates if t["name"] == name]
        assert len(matching) >= 1, (
            f"Expected to find teammate '{name}' after import, "
            f"but found: {[t['name'] for t in teammates]}"
        )

        imported_teammate = matching[0]
        assert imported_teammate["shift_type"] == "Custom", (
            f"Expected shift_type='Custom', got '{imported_teammate['shift_type']}'"
        )

        # The core property: custom_days sets must be identical (order-independent)
        assert set(imported_teammate["custom_days"]) == set(custom_days), (
            f"Custom days mismatch after CSV round-trip!\n"
            f"Original days: {sorted(custom_days)}\n"
            f"Imported days: {sorted(imported_teammate['custom_days'])}\n"
            f"CSV value used: '{days_csv_value}'"
        )
