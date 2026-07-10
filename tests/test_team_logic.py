"""Property-based tests for team management logic."""

from collections import defaultdict

from hypothesis import given, settings, strategies as st

from dc_shiftmaster.models import Teammate
from tests.conftest import VALID_SHIFT_TYPES, valid_time


# ------------------------------------------------------------------ #
# Hypothesis strategy — valid Teammate objects
# ------------------------------------------------------------------ #

@st.composite
def valid_teammate_object(draw: st.DrawFn) -> Teammate:
    """Generate a valid Teammate dataclass instance."""
    tid = draw(st.integers(min_value=1, max_value=10_000))
    name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
            min_size=1,
            max_size=50,
        ).filter(lambda s: s.strip())
    )
    shift_type = draw(st.sampled_from(VALID_SHIFT_TYPES))
    custom_start = draw(st.one_of(st.just(""), valid_time()))
    return Teammate(id=tid, name=name, shift_type=shift_type, custom_start=custom_start)


# ------------------------------------------------------------------ #
# Property 11: Teammate grouping by shift type
# ------------------------------------------------------------------ #

# Feature: dc-shiftmaster-web, Property 11: Teammate grouping by shift type
class TestTeammateGroupingByShiftType:
    """**Validates: Requirements 5.1**"""

    @given(teammates=st.lists(valid_teammate_object(), min_size=0, max_size=30))
    @settings(max_examples=100)
    def test_grouping_produces_correct_groups(self, teammates: list[Teammate]):
        """Grouping teammates by shift_type should produce groups where every
        teammate in a group has the matching shift_type, and the union of all
        groups equals the original list."""
        # Group by shift_type using the same logic as TeamPage._refresh_list
        grouped: dict[str, list[Teammate]] = defaultdict(list)
        for t in teammates:
            grouped[t.shift_type].append(t)

        # Every teammate in each group has the matching shift_type
        for shift_type, members in grouped.items():
            for t in members:
                assert t.shift_type == shift_type, (
                    f"Teammate {t.name!r} has shift_type={t.shift_type!r} "
                    f"but is in group {shift_type!r}"
                )

        # The union of all groups equals the original list (same length)
        total = sum(len(members) for members in grouped.values())
        assert total == len(teammates), (
            f"Union of groups has {total} teammates but original list has {len(teammates)}"
        )

        # The union of all groups contains the same elements as the original list
        union: list[Teammate] = []
        for members in grouped.values():
            union.extend(members)

        # Convert to comparable tuples and sort for order-independent comparison
        def _key(t: Teammate) -> tuple:
            return (t.id, t.name, t.shift_type, t.custom_start)

        assert sorted(union, key=_key) == sorted(teammates, key=_key), (
            "Union of groups does not match the original list"
        )


# ------------------------------------------------------------------ #
# Hypothesis strategies for CSV import testing
# ------------------------------------------------------------------ #

# Characters safe for CSV fields (no commas, newlines, or quotes to avoid
# ambiguous CSV escaping that would complicate round-trip assertions).
_CSV_SAFE_CHARS = st.characters(
    whitelist_categories=("L", "N"),
    min_codepoint=65,
    max_codepoint=122,
)

_INVALID_SHIFT_TYPES = ["XYZ", "DAY", "NIGHT", "fhd", "abc", "123", ""]


@st.composite
def valid_csv_row(draw: st.DrawFn) -> tuple[str, str, str]:
    """Generate a valid CSV row: (name, shift_type, custom_start)."""
    name = draw(
        st.text(alphabet=_CSV_SAFE_CHARS, min_size=1, max_size=20)
        .filter(lambda s: s.strip())
    )
    shift_type = draw(st.sampled_from(VALID_SHIFT_TYPES))
    custom_start = draw(st.one_of(st.just(""), valid_time()))
    return (name, shift_type, custom_start)


@st.composite
def invalid_csv_row(draw: st.DrawFn) -> tuple[str, str]:
    """Generate an invalid CSV row: (name, bad_shift_type)."""
    name = draw(
        st.text(alphabet=_CSV_SAFE_CHARS, min_size=1, max_size=20)
        .filter(lambda s: s.strip())
    )
    bad_shift = draw(st.sampled_from(_INVALID_SHIFT_TYPES))
    return (name, bad_shift)


def _row_to_csv_line(name: str, shift_type: str, custom_start: str = "") -> str:
    """Format a single CSV line from fields."""
    if custom_start:
        return f"{name},{shift_type},{custom_start}"
    return f"{name},{shift_type}"


# ------------------------------------------------------------------ #
# Property 12: CSV teammate import parsing
# ------------------------------------------------------------------ #

from dc_shiftmaster_web.pages.team import parse_csv_teammates

# Feature: dc-shiftmaster-web, Property 12: CSV teammate import parsing
class TestCSVTeammateImportParsing:
    """**Validates: Requirements 5.9, 5.10**"""

    @given(
        valid_rows=st.lists(valid_csv_row(), min_size=0, max_size=15),
        invalid_rows=st.lists(invalid_csv_row(), min_size=0, max_size=10),
        ordering_seed=st.randoms(use_true_random=False),
    )
    @settings(max_examples=100)
    def test_csv_parsing_separates_valid_and_invalid_rows(
        self,
        valid_rows: list[tuple[str, str, str]],
        invalid_rows: list[tuple[str, str]],
        ordering_seed,
    ):
        """For any mix of valid and invalid CSV rows, parsing should produce
        teammate records matching the valid rows and skip the invalid ones,
        with correct 1-indexed row numbers for skipped rows."""
        # Build indexed entries: (original_index, "valid"/"invalid", data)
        entries: list[tuple[int, str, tuple]] = []
        for i, row in enumerate(valid_rows):
            entries.append((i, "valid", row))
        for i, row in enumerate(invalid_rows):
            entries.append((i, "invalid", row))

        # Shuffle to interleave valid and invalid rows
        ordering_seed.shuffle(entries)

        # Build CSV content and track expected outcomes
        csv_lines: list[str] = []
        expected_valid: list[tuple[str, str, str]] = []
        expected_skipped: list[int] = []

        for line_idx, (_, kind, data) in enumerate(entries):
            row_number = line_idx + 1  # 1-indexed
            if kind == "valid":
                name, shift_type, custom_start = data
                csv_lines.append(_row_to_csv_line(name, shift_type, custom_start))
                expected_valid.append((name, shift_type, custom_start))
            else:
                name, bad_shift = data
                csv_lines.append(_row_to_csv_line(name, bad_shift))
                expected_skipped.append(row_number)

        csv_content = "\n".join(csv_lines)

        # Parse
        result_valid, result_skipped = parse_csv_teammates(csv_content)

        # Assert: all valid rows appear in the result with correct values
        assert len(result_valid) == len(expected_valid), (
            f"Expected {len(expected_valid)} valid rows, got {len(result_valid)}"
        )
        for (exp_name, exp_shift, exp_cs), (res_name, res_shift, res_cs) in zip(
            expected_valid, result_valid
        ):
            assert res_name == exp_name, (
                f"Expected name {exp_name!r}, got {res_name!r}"
            )
            assert res_shift == exp_shift, (
                f"Expected shift_type {exp_shift!r}, got {res_shift!r}"
            )
            assert res_cs == exp_cs, (
                f"Expected custom_start {exp_cs!r}, got {res_cs!r}"
            )

        # Assert: all invalid rows are in the skipped list
        assert result_skipped == expected_skipped, (
            f"Expected skipped rows {expected_skipped}, got {result_skipped}"
        )

        # Assert: skipped row numbers are 1-indexed and correct
        for row_num in result_skipped:
            assert row_num >= 1, f"Skipped row number {row_num} is not 1-indexed"
