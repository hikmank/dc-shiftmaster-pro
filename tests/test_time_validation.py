"""Unit tests for validate_time_format (task 3.1)."""

from dc_shiftmaster.validation import validate_time_format


class TestValidTimeFormats:
    """Valid HH:MM strings should be accepted."""

    def test_midnight(self):
        assert validate_time_format("00:00") == (True, "")

    def test_end_of_day(self):
        assert validate_time_format("23:59") == (True, "")

    def test_noon(self):
        assert validate_time_format("12:00") == (True, "")

    def test_default_day_start(self):
        assert validate_time_format("06:00") == (True, "")

    def test_default_night_end(self):
        assert validate_time_format("06:30") == (True, "")

    def test_hour_boundary_19(self):
        assert validate_time_format("19:45") == (True, "")


class TestInvalidTimeFormats:
    """Invalid strings should be rejected with a clear error message."""

    def test_empty_string(self):
        valid, msg = validate_time_format("")
        assert not valid
        assert msg

    def test_no_colon(self):
        valid, msg = validate_time_format("1234")
        assert not valid
        assert "HH:MM" in msg or "format" in msg.lower()

    def test_hour_24(self):
        valid, msg = validate_time_format("24:00")
        assert not valid

    def test_minute_60(self):
        valid, msg = validate_time_format("12:60")
        assert not valid

    def test_single_digit_hour(self):
        valid, msg = validate_time_format("6:00")
        assert not valid

    def test_single_digit_minute(self):
        valid, msg = validate_time_format("06:0")
        assert not valid

    def test_three_digit_hour(self):
        valid, msg = validate_time_format("006:00")
        assert not valid

    def test_letters_in_hour(self):
        valid, msg = validate_time_format("ab:00")
        assert not valid

    def test_letters_in_minute(self):
        valid, msg = validate_time_format("12:xy")
        assert not valid

    def test_extra_colon(self):
        valid, msg = validate_time_format("12:00:00")
        assert not valid

    def test_whitespace(self):
        valid, msg = validate_time_format(" 12:00")
        assert not valid

    def test_negative_hour(self):
        valid, msg = validate_time_format("-1:00")
        assert not valid

    def test_random_text(self):
        valid, msg = validate_time_format("hello")
        assert not valid
