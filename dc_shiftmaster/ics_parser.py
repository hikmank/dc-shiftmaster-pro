"""ICS (iCalendar RFC 5545) parser module for DC-ShiftMaster Pro.

Parses uploaded .ics files and extracts shift event data for import
into the application as override entries. Handles RFC 5545 line
unfolding, VEVENT extraction, and property parsing.
"""

from dataclasses import dataclass, field


@dataclass
class ParsedEvent:
    """A single calendar event extracted from an ICS file.

    Attributes:
        dtstart: Event start in YYYYMMDDTHHMMSS format.
        dtend: Event end in YYYYMMDDTHHMMSS format.
        summary: Raw SUMMARY property value from the VEVENT.
        uid: Optional UID property value (empty string if not present).
    """

    dtstart: str
    dtend: str
    summary: str
    uid: str = ""


@dataclass
class ParseResult:
    """Aggregated result of ICS file parsing.

    Attributes:
        events: List of successfully parsed events.
        skipped: Descriptions of skipped events (e.g. missing DTSTART/DTEND).
        errors: Descriptions of parse errors encountered.
    """

    events: list[ParsedEvent] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class ICSParser:
    """Parses RFC 5545 ICS files into structured event data."""

    def parse(self, ics_text: str) -> ParseResult:
        """Parse ICS text and extract VEVENT components.

        Args:
            ics_text: Raw ICS file content.

        Returns:
            ParseResult with events, skipped items, and errors.

        Raises:
            ValueError: If text does not begin with BEGIN:VCALENDAR.
        """
        # Strip BOM and leading/trailing whitespace for validation
        stripped = ics_text.lstrip("\ufeff").strip()
        if not stripped.upper().startswith("BEGIN:VCALENDAR"):
            raise ValueError(
                "Invalid ICS format: file does not begin with BEGIN:VCALENDAR"
            )

        lines = self._unfold_lines(ics_text)
        vevent_dicts = self._extract_vevents(lines)

        result = ParseResult()

        for props in vevent_dicts:
            dtstart = props.get("DTSTART", "")
            dtend = props.get("DTEND", "")
            summary = props.get("SUMMARY", "")
            uid = props.get("UID", "")

            if not dtstart or not dtend:
                # Build a description of the skipped event
                desc_parts = []
                if summary:
                    desc_parts.append(f"SUMMARY={summary}")
                if uid:
                    desc_parts.append(f"UID={uid}")
                if not dtstart:
                    desc_parts.append("missing DTSTART")
                if not dtend:
                    desc_parts.append("missing DTEND")
                result.skipped.append(
                    f"Skipped VEVENT: {', '.join(desc_parts)}"
                )
                continue

            result.events.append(
                ParsedEvent(
                    dtstart=dtstart,
                    dtend=dtend,
                    summary=summary,
                    uid=uid,
                )
            )

        return result

    def _unfold_lines(self, text: str) -> list[str]:
        """Unfold continuation lines (CRLF + whitespace) per RFC 5545.

        RFC 5545 Section 3.1: Long content lines are folded by inserting
        a CRLF immediately followed by a single whitespace character (space
        or tab). This method reverses that folding.

        Args:
            text: Raw ICS file content (may use CRLF or LF line endings).

        Returns:
            List of unfolded content lines.
        """
        # Normalize line endings to LF for consistent processing
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Unfold: a line starting with a space or tab is a continuation
        # of the previous line (remove the newline and leading whitespace char)
        unfolded_lines: list[str] = []
        for line in text.split("\n"):
            if line and (line[0] == " " or line[0] == "\t"):
                # Continuation line: append content (minus the leading whitespace)
                if unfolded_lines:
                    unfolded_lines[-1] += line[1:]
                else:
                    # Edge case: file starts with continuation (malformed),
                    # just add as new line without the whitespace
                    unfolded_lines.append(line[1:])
            else:
                unfolded_lines.append(line)

        return unfolded_lines

    def _extract_vevents(self, lines: list[str]) -> list[dict[str, str]]:
        """Extract property key:value dicts from VEVENT blocks.

        Iterates through unfolded lines and collects properties within
        BEGIN:VEVENT / END:VEVENT boundaries.

        Args:
            lines: List of unfolded content lines.

        Returns:
            List of dicts, each mapping property names to their values
            for one VEVENT component.
        """
        vevents: list[dict[str, str]] = []
        current_props: dict[str, str] | None = None

        for line in lines:
            upper_line = line.strip().upper()

            if upper_line == "BEGIN:VEVENT":
                current_props = {}
            elif upper_line == "END:VEVENT":
                if current_props is not None:
                    vevents.append(current_props)
                    current_props = None
            elif current_props is not None:
                # Parse property: NAME;params:VALUE or NAME:VALUE
                # We want the property name (before ; or :) and the value (after first :)
                colon_idx = line.find(":")
                if colon_idx < 0:
                    continue

                # Property name may include parameters (NAME;PARAM=VAL:VALUE)
                name_part = line[:colon_idx]
                value = line[colon_idx + 1:]

                # Extract the base property name (strip parameters)
                semicolon_idx = name_part.find(";")
                if semicolon_idx >= 0:
                    prop_name = name_part[:semicolon_idx].strip().upper()
                else:
                    prop_name = name_part.strip().upper()

                current_props[prop_name] = value.strip()

        return vevents
