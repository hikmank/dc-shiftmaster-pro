"""Property-based tests for input validation (task 3.3).

Feature: dc-shiftmaster-pro, Property 2: Time format validation
Validates: Requirements 1.5
"""

from hypothesis import given, settings

from dc_shiftmaster.validation import validate_time_format
from tests.conftest import valid_time, invalid_time


# Feature: dc-shiftmaster-pro, Property 2: Time format validation
class TestTimeFormatValidationProperty:
    """For any string, validate_time_format should accept it iff it matches HH:MM 24-hour format."""

    @given(time_str=valid_time())
    @settings(max_examples=100)
    def test_valid_times_are_accepted(self, time_str: str):
        """**Validates: Requirements 1.5**

        Any correctly formatted HH:MM string (hours 00-23, minutes 00-59)
        must be accepted by the validator.
        """
        is_valid, error_msg = validate_time_format(time_str)
        assert is_valid, f"Valid time '{time_str}' was rejected: {error_msg}"
        assert error_msg == "", f"Valid time '{time_str}' returned non-empty error: {error_msg}"

    @given(time_str=invalid_time())
    @settings(max_examples=100)
    def test_invalid_times_are_rejected(self, time_str: str):
        """**Validates: Requirements 1.5**

        Any string that does NOT match HH:MM 24-hour format must be rejected
        with a non-empty error message.
        """
        is_valid, error_msg = validate_time_format(time_str)
        assert not is_valid, f"Invalid time '{time_str}' was accepted"
        assert error_msg, f"Invalid time '{time_str}' was rejected but with empty error message"
