"""ICS (iCalendar RFC 5545) export module for DC-ShiftMaster Pro.

Converts ScheduleSlot lists into RFC 5545 compliant ICS text suitable
for import into Google Calendar, Microsoft Outlook, Apple Calendar, and
other standards-compliant calendar applications.
"""

from datetime import date, datetime, timedelta, timezone

from dc_shiftmaster.models import ScheduleSlot, ShiftWindow


class ICSExporter:
    """Converts ScheduleSlot lists to RFC 5545 ICS format."""

    CRLF = "\r\n"
    MAX_LINE_OCTETS = 75

    def export(
        self,
        schedule: list[ScheduleSlot],
        shift_windows: dict[str, ShiftWindow],
    ) -> str:
        """Generate ICS text from schedule slots.

        Args:
            schedule: List of ScheduleSlot objects (already filtered by date range).
            shift_windows: Dict with 'day' and 'night' ShiftWindow for end time
                calculation.

        Returns:
            Complete ICS file content as a string with CRLF line endings.
        """
        dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        lines: list[str] = []
        lines.append("BEGIN:VCALENDAR")
        lines.append("VERSION:2.0")
        lines.append("PRODID:-//DC-ShiftMaster Pro//EN")
        lines.append("CALSCALE:GREGORIAN")

        for slot in schedule:
            vevent_lines = self._format_vevent(slot, shift_windows, dtstamp)
            lines.extend(vevent_lines)

        lines.append("END:VCALENDAR")

        # Fold long lines and join with CRLF
        folded_lines: list[str] = []
        for line in lines:
            folded_lines.append(self._fold_line(line))

        return self.CRLF.join(folded_lines) + self.CRLF

    def _format_vevent(
        self,
        slot: ScheduleSlot,
        shift_windows: dict[str, ShiftWindow],
        dtstamp: str,
    ) -> list[str]:
        """Format a single ScheduleSlot as a VEVENT component.

        Args:
            slot: The schedule slot to format.
            shift_windows: Dict of ShiftWindow objects for end time lookup.
            dtstamp: Pre-formatted DTSTAMP value (UTC).

        Returns:
            List of content lines for the VEVENT (unfolded, no CRLF).
        """
        window = shift_windows[slot.shift_type]

        # Format DTSTART
        dtstart = self._format_datetime(slot.date, window.start_time)

        # Format DTEND - handle night shift crossing midnight
        end_date = slot.date
        if window.end_time < window.start_time:
            # Night shift: end_time is on the next calendar day
            end_date = slot.date + timedelta(days=1)
        dtend = self._format_datetime(end_date, window.end_time)

        # Deterministic UID
        uid = f"{slot.date.isoformat()}-{slot.shift_type}@dc-shiftmaster"

        # SUMMARY with teammate names
        teammates_str = ", ".join(slot.teammates)
        summary = f"{slot.shift_type} Shift - {teammates_str}"

        return [
            "BEGIN:VEVENT",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"DTSTAMP:{dtstamp}",
            f"UID:{uid}",
            f"SUMMARY:{summary}",
            "END:VEVENT",
        ]

    def _fold_line(self, line: str) -> str:
        """Fold content lines longer than 75 octets per RFC 5545.

        RFC 5545 Section 3.1: Lines of text SHOULD NOT be longer than 75
        octets, excluding the line break. Long lines are folded by inserting
        a CRLF immediately followed by a single whitespace character (space
        or tab).

        Args:
            line: A single content line (no CRLF).

        Returns:
            The line folded at 75-octet boundaries with CRLF + space
            continuations.
        """
        encoded = line.encode("utf-8")
        if len(encoded) <= self.MAX_LINE_OCTETS:
            return line

        result_parts: list[str] = []
        remaining = encoded
        first = True

        while len(remaining) > 0:
            if first:
                max_octets = self.MAX_LINE_OCTETS
                first = False
            else:
                # Continuation lines start with a space, so we have
                # 75 - 1 = 74 octets for actual content
                max_octets = self.MAX_LINE_OCTETS - 1

            # Find a safe cut point that doesn't split a multi-byte character
            cut = max_octets
            if cut >= len(remaining):
                # Last chunk
                result_parts.append(remaining.decode("utf-8"))
                break

            # Walk back to avoid splitting a multi-byte UTF-8 character
            while cut > 0 and (remaining[cut] & 0xC0) == 0x80:
                cut -= 1

            chunk = remaining[:cut].decode("utf-8")
            result_parts.append(chunk)
            remaining = remaining[cut:]

        # Join with CRLF + space for continuation lines
        return (self.CRLF + " ").join(result_parts)

    def _format_datetime(self, d: date, time_str: str) -> str:
        """Format date + time as YYYYMMDDTHHMMSS.

        Args:
            d: The calendar date.
            time_str: Time in HH:MM or H:MM format.

        Returns:
            Formatted datetime string like '20250315T060000'.
        """
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return f"{d.strftime('%Y%m%d')}T{hour:02d}{minute:02d}00"
