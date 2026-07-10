"""Unit tests for CSV teammate import parsing."""

from dc_shiftmaster_web.pages.team import parse_csv_teammates


class TestParseCsvTeammates:
    """Tests for the parse_csv_teammates helper function."""

    def test_all_valid_rows(self):
        csv = "Alice,FHD\nBob,BHN,19:00\nCharlie,FHN\n"
        valid, skipped = parse_csv_teammates(csv)
        assert valid == [
            ("Alice", "FHD", ""),
            ("Bob", "BHN", "19:00"),
            ("Charlie", "FHN", ""),
        ]
        assert skipped == []

    def test_invalid_shift_type_skipped(self):
        csv = "Alice,FHD\nBob,INVALID\nCharlie,BHD\n"
        valid, skipped = parse_csv_teammates(csv)
        assert valid == [("Alice", "FHD", ""), ("Charlie", "BHD", "")]
        assert skipped == [2]

    def test_empty_rows_skipped(self):
        csv = "Alice,FHD\n\nBob,BHN\n"
        valid, skipped = parse_csv_teammates(csv)
        assert valid == [("Alice", "FHD", ""), ("Bob", "BHN", "")]
        assert skipped == [2]

    def test_row_numbers_are_1_indexed(self):
        csv = "bad_row\nAlice,FHD\nanother_bad\n"
        valid, skipped = parse_csv_teammates(csv)
        assert valid == [("Alice", "FHD", "")]
        assert skipped == [1, 3]

    def test_empty_csv(self):
        valid, skipped = parse_csv_teammates("")
        assert valid == []
        assert skipped == []

    def test_case_sensitive_shift_types(self):
        csv = "Alice,fhd\nBob,FHD\n"
        valid, skipped = parse_csv_teammates(csv)
        assert valid == [("Bob", "FHD", "")]
        assert skipped == [1]

    def test_whitespace_stripped(self):
        csv = " Alice , FHD , 07:00 \n"
        valid, skipped = parse_csv_teammates(csv)
        assert valid == [("Alice", "FHD", "07:00")]
        assert skipped == []

    def test_all_four_shift_types(self):
        csv = "A,FHD\nB,FHN\nC,BHD\nD,BHN\n"
        valid, skipped = parse_csv_teammates(csv)
        assert len(valid) == 4
        assert skipped == []

    def test_missing_shift_type_column(self):
        csv = "Alice\n"
        valid, skipped = parse_csv_teammates(csv)
        assert valid == []
        assert skipped == [1]

    def test_toast_message_format_with_skipped(self):
        """Verify the expected toast message can be built from results."""
        csv = "Alice,FHD\nBad,XYZ\nCharlie,BHD\nNope,ZZZ\n"
        valid, skipped = parse_csv_teammates(csv)
        count = len(valid)
        msg = (
            f"Imported {count} teammates. "
            f"Skipped rows: {', '.join(str(r) for r in skipped)}"
        )
        assert msg == "Imported 2 teammates. Skipped rows: 2, 4"

    def test_toast_message_format_no_skipped(self):
        csv = "Alice,FHD\nBob,BHN\n"
        valid, skipped = parse_csv_teammates(csv)
        count = len(valid)
        assert skipped == []
        msg = f"Imported {count} teammates."
        assert msg == "Imported 2 teammates."
