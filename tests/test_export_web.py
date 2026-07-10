"""Property tests for the web export page (Properties 13 & 14).

Feature: dc-shiftmaster-web
"""

from __future__ import annotations

import re
from datetime import date

from hypothesis import given, settings, strategies as st

from dc_shiftmaster.csv_export import validate_schedule
from dc_shiftmaster.models import ScheduleSlot
from dc_shiftmaster_web.pages.export import generate_export_filename


# ------------------------------------------------------------------ #
# Property 13: Export filename pattern
# ------------------------------------------------------------------ #

class TestExportFilenamePattern:
    """Property 13: For any region and year, the filename matches
    ``{region}_{year}_schedule.{ext}``."""

    @settings(max_examples=100)
    @given(
        region=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=10,
        ),
        year=st.integers(min_value=2000, max_value=2100),
        ext=st.sampled_from(["csv", "json", "xlsx"]),
    )
    def test_filename_matches_pattern(self, region: str, year: int, ext: str):
        filename = generate_export_filename(region, year, ext)
        assert filename == f"{region}_{year}_schedule.{ext}"
        # Also verify via regex
        pattern = re.compile(r"^.+_\d{4,}_schedule\.(csv|json|xlsx)$")
        assert pattern.match(filename)

    def test_empty_region_defaults_to_site(self):
        filename = generate_export_filename("", 2025, "csv")
        assert filename == "SITE_2025_schedule.csv"


# ------------------------------------------------------------------ #
# Property 14: Invalid schedule blocks export
# ------------------------------------------------------------------ #

class TestInvalidScheduleBlocksExport:
    """Property 14: A schedule that fails validate_schedule should produce
    errors, blocking export."""

    @settings(max_examples=100)
    @given(
        bad_name=st.text(
            alphabet=st.characters(
                whitelist_categories=("L",),
                whitelist_characters="àéîöü",
            ),
            min_size=1,
            max_size=5,
        ),
    )
    def test_non_ascii_name_fails_validation(self, bad_name: str):
        """A schedule with non-ASCII teammate names should fail validation."""
        # Ensure the name actually has non-ASCII chars
        try:
            bad_name.encode("ascii")
            return  # skip if hypothesis generated an ASCII-only string
        except UnicodeEncodeError:
            pass

        schedule = [
            ScheduleSlot(
                date=date(2025, 1, 1),
                shift_type="day",
                start_time="06:00",
                teammates=[bad_name],
                is_override=False,
            ),
        ]
        errors = validate_schedule(schedule)
        assert len(errors) > 0
        assert "Non-ASCII" in errors[0]

    def test_out_of_order_fails_validation(self):
        """A schedule with dates out of order should fail validation."""
        schedule = [
            ScheduleSlot(
                date=date(2025, 1, 2),
                shift_type="day",
                start_time="06:00",
                teammates=["Alice"],
                is_override=False,
            ),
            ScheduleSlot(
                date=date(2025, 1, 1),
                shift_type="day",
                start_time="06:00",
                teammates=["Bob"],
                is_override=False,
            ),
        ]
        errors = validate_schedule(schedule)
        assert len(errors) > 0
        assert "Out of order" in errors[0]
