"""JSON schedule import module for DC-ShiftMaster Pro.

Parses and validates JSON schedule files for import as overrides.
Accepts the format produced by /api/export/<year>/json (objects with
date, shift_type, name, and optional extra fields like start_time,
end_time, teammates, is_override).
"""

import json
import re
from dataclasses import dataclass, field


@dataclass
class JSONImportEntry:
    """A single validated entry from a JSON schedule file.

    Attributes:
        date: The shift date in YYYY-MM-DD format.
        shift_type: The shift type, either 'day' or 'night'.
        name: Teammate name for the override assignment.
    """

    date: str
    shift_type: str
    name: str


@dataclass
class JSONImportResult:
    """Result of parsing a JSON schedule file.

    Attributes:
        entries: List of validated JSONImportEntry objects ready for import.
        errors: List of descriptive error messages for invalid entries.
    """

    entries: list[JSONImportEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Regex for YYYY-MM-DD date format validation
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Valid shift types
_VALID_SHIFT_TYPES = {"day", "night"}


class JSONScheduleImporter:
    """Parses and validates JSON schedule files for import.

    Accepts JSON arrays of schedule objects. Each object must have:
    - date: string in YYYY-MM-DD format
    - shift_type: "day" or "night"
    - name: non-empty string

    Extra fields (start_time, end_time, teammates, is_override, etc.)
    are silently ignored, allowing import of the JSON export format.
    """

    def parse(self, json_text: str) -> JSONImportResult:
        """Parse JSON text and validate each entry.

        Accepts the format produced by /api/export/<year>/json:
        array of objects with at minimum date, shift_type, name fields.
        Extra fields are ignored.

        Args:
            json_text: Raw JSON file content.

        Returns:
            JSONImportResult with valid entries and error descriptions.

        Raises:
            ValueError: If text is not valid JSON or not an array.
        """
        try:
            data = json.loads(json_text)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Invalid JSON: {e}") from e

        if not isinstance(data, list):
            raise ValueError(
                "Invalid format: expected a JSON array of schedule entries"
            )

        result = JSONImportResult()

        for index, item in enumerate(data):
            errors = self._validate_entry(item, index)
            if errors:
                result.errors.extend(errors)
            else:
                result.entries.append(
                    JSONImportEntry(
                        date=item["date"],
                        shift_type=item["shift_type"],
                        name=item["name"],
                    )
                )

        return result

    def _validate_entry(self, item: object, index: int) -> list[str]:
        """Validate a single entry and return a list of error messages.

        Args:
            item: The parsed JSON object to validate.
            index: The zero-based index of the entry in the array.

        Returns:
            List of error strings. Empty list means the entry is valid.
        """
        errors = []

        if not isinstance(item, dict):
            errors.append(f"Entry {index}: expected an object, got {type(item).__name__}")
            return errors

        # Validate date field
        if "date" not in item:
            errors.append(f"Entry {index}: missing required field 'date'")
        elif not isinstance(item["date"], str):
            errors.append(
                f"Entry {index}: 'date' must be a string, got {type(item['date']).__name__}"
            )
        elif not _DATE_PATTERN.match(item["date"]):
            errors.append(
                f"Entry {index}: invalid date format '{item['date']}', expected YYYY-MM-DD"
            )
        else:
            # Additional validation: check that date components are plausible
            parts = item["date"].split("-")
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            if month < 1 or month > 12:
                errors.append(
                    f"Entry {index}: invalid date '{item['date']}', month must be 01-12"
                )
            elif day < 1 or day > 31:
                errors.append(
                    f"Entry {index}: invalid date '{item['date']}', day must be 01-31"
                )

        # Validate shift_type field
        if "shift_type" not in item:
            errors.append(f"Entry {index}: missing required field 'shift_type'")
        elif not isinstance(item["shift_type"], str):
            errors.append(
                f"Entry {index}: 'shift_type' must be a string, got {type(item['shift_type']).__name__}"
            )
        elif item["shift_type"] not in _VALID_SHIFT_TYPES:
            errors.append(
                f"Entry {index}: invalid shift_type '{item['shift_type']}', must be 'day' or 'night'"
            )

        # Validate name field
        if "name" not in item:
            errors.append(f"Entry {index}: missing required field 'name'")
        elif not isinstance(item["name"], str):
            errors.append(
                f"Entry {index}: 'name' must be a string, got {type(item['name']).__name__}"
            )
        elif not item["name"].strip():
            errors.append(f"Entry {index}: 'name' must not be empty")

        return errors
