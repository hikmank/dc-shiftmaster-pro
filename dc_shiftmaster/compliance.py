"""Compliance validation module for DC-ShiftMaster Pro.

Provides pre-override safety checks against labor compliance limits:
- Weekly hours limit (60 hours in any rolling 7-day window)
- Weekly days limit (6 days in any rolling 7-day window)
- Daily hours limit (12 hours in a single calendar day)

The ComplianceValidator is a stateless class with pure methods that accept
schedule data and return violation results without side effects.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass
class ComplianceViolation:
    """A single compliance rule violation detected during validation.

    Attributes:
        rule: The violated rule ('weekly_hours', 'weekly_days', or 'daily_hours').
        projected: The projected value that exceeds the limit.
        limit: The applicable limit (60, 6, or 12).
        window_start: Start of the violating 7-day window (YYYY-MM-DD), None for daily.
        window_end: End of the violating 7-day window (YYYY-MM-DD), None for daily.
    """

    rule: str
    projected: float
    limit: float
    window_start: str | None
    window_end: str | None


@dataclass
class ComplianceResult:
    """Aggregate result of all compliance checks for a proposed override.

    Attributes:
        passed: True if no violations were found.
        violations: List of violations (empty if passed).
    """

    passed: bool
    violations: list[ComplianceViolation] = field(default_factory=list)


class ComplianceValidator:
    """Validates proposed overrides against labor compliance limits.

    All methods are pure functions — they accept schedule data as arguments
    and return results without database access or side effects.
    """

    WEEKLY_HOURS_LIMIT = 60.0
    WEEKLY_DAYS_LIMIT = 6
    DAILY_HOURS_LIMIT = 12.0

    def validate(
        self,
        teammate_name: str,
        override_date: date,
        override_shift_type: str,
        shift_windows: dict,
        teammates: list,
        existing_overrides: list,
        proposed_override_name: str,
        scheduling_engine,
        year: int,
    ) -> ComplianceResult:
        """Run all compliance checks for a proposed override.

        Orchestrates the full validation flow:
        1. Determine the date range covering all possible 7-day rolling windows
           that include the override date (override_date - 6 through override_date + 6).
        2. Resolve the teammate's current projected schedule within that range.
        3. Add the proposed override to the schedule (avoiding double-counting
           if the teammate is already assigned to that slot).
        4. Run all three compliance checks (weekly hours, weekly days, daily hours).
        5. Collect all violations and return a ComplianceResult.

        Args:
            teammate_name: The name of the teammate being moved INTO the slot.
            override_date: The date of the proposed override.
            override_shift_type: 'day' or 'night'.
            shift_windows: Current shift window configuration.
            teammates: All teammate records (for custom_start lookup).
            existing_overrides: All overrides in the relevant date range.
            proposed_override_name: The name being assigned in the override.
            scheduling_engine: SchedulingEngine instance for computing base assignments.
            year: The calendar year for schedule computation.

        Returns:
            ComplianceResult with passed=True if no violations, or
            passed=False with a list of violations.
        """
        # Step 1: Determine the date range for the rolling window.
        # We need override_date - 6 through override_date + 6 to cover
        # all possible 7-day windows that include the override date.
        date_range = [
            override_date + timedelta(days=offset)
            for offset in range(-6, 7)
        ]

        # Step 2: Resolve the teammate's current projected schedule.
        schedule = self.resolve_teammate_schedule(
            teammate_name=teammate_name,
            date_range=date_range,
            shift_windows=shift_windows,
            teammates=teammates,
            existing_overrides=existing_overrides,
            scheduling_engine=scheduling_engine,
            year=year,
        )

        # Step 3: Add the proposed override to the schedule.
        # Avoid double-counting: only add if (override_date, override_shift_type)
        # is not already in the schedule (per Requirement 3.5).
        proposed_entry = (override_date, override_shift_type)
        if proposed_entry not in schedule:
            schedule.append(proposed_entry)

        # Step 4: Run all three compliance checks.
        weekly_hours_violations = self.check_weekly_hours(
            teammate_name=teammate_name,
            override_date=override_date,
            schedule_with_override=schedule,
            shift_windows=shift_windows,
            teammates=teammates,
        )

        weekly_days_violations = self.check_weekly_days(
            override_date=override_date,
            schedule_with_override=schedule,
        )

        daily_hours_violations = self.check_daily_hours(
            teammate_name=teammate_name,
            override_date=override_date,
            schedule_with_override=schedule,
            shift_windows=shift_windows,
            teammates=teammates,
        )

        # Step 5: Collect all violations.
        all_violations = (
            weekly_hours_violations
            + weekly_days_violations
            + daily_hours_violations
        )

        if all_violations:
            return ComplianceResult(passed=False, violations=all_violations)

        return ComplianceResult(passed=True, violations=[])

    def compute_shift_duration(
        self,
        effective_start: str,
        shift_end: str,
    ) -> float:
        """Calculate shift duration in hours from start to end time.

        Handles overnight shifts by adding 24h when end < start.
        Returns 0.0 when start == end.

        Args:
            effective_start: HH:MM start time.
            shift_end: HH:MM end time.

        Returns:
            Duration in hours as a float.
        """
        if effective_start == shift_end:
            return 0.0

        start_parts = effective_start.split(":")
        start_hours = int(start_parts[0])
        start_minutes = int(start_parts[1])
        start_total_minutes = start_hours * 60 + start_minutes

        end_parts = shift_end.split(":")
        end_hours = int(end_parts[0])
        end_minutes = int(end_parts[1])
        end_total_minutes = end_hours * 60 + end_minutes

        if end_total_minutes < start_total_minutes:
            # Overnight shift: add 24 hours (1440 minutes) to end time
            end_total_minutes += 1440

        duration_minutes = end_total_minutes - start_total_minutes
        return duration_minutes / 60.0

    def get_effective_start(
        self,
        teammate_name: str,
        shift_type: str,
        teammates: list,
        shift_windows: dict,
    ) -> str:
        """Resolve the effective start time for a teammate on a shift type.

        Uses custom_start if the teammate has one configured (non-empty),
        otherwise falls back to the shift window default start time.

        Args:
            teammate_name: The teammate's name.
            shift_type: 'day' or 'night'.
            teammates: All teammate records.
            shift_windows: Shift window configuration mapping shift_type to ShiftWindow.

        Returns:
            HH:MM time string.
        """
        # Look up teammate by name in the teammates list
        for teammate in teammates:
            if teammate.name == teammate_name:
                if teammate.custom_start:
                    return teammate.custom_start
                break

        # Fall back to the shift window's default start_time
        return shift_windows[shift_type].start_time

    def resolve_teammate_schedule(
        self,
        teammate_name: str,
        date_range: list[date],
        shift_windows: dict,
        teammates: list,
        existing_overrides: list,
        scheduling_engine,
        year: int,
    ) -> list[tuple[date, str]]:
        """Resolve all (date, shift_type) pairs where the teammate works.

        Computes the base schedule from the scheduling engine for the date
        range, then applies existing overrides on top to determine the
        teammate's actual working days.

        An override "assigns" the teammate if override.name == teammate_name.
        An override "removes" the teammate if the teammate was the computed
        assignee but override.name is a different name or "nobody".

        Args:
            teammate_name: The name of the teammate to resolve schedule for.
            date_range: List of dates to check.
            shift_windows: Shift window configuration mapping shift_type to ShiftWindow.
            teammates: All teammate records.
            existing_overrides: All overrides that may affect the schedule.
            scheduling_engine: SchedulingEngine instance for computing base assignments.
            year: The calendar year for schedule computation.

        Returns:
            List of (date, shift_type) tuples where the teammate is assigned.
        """
        # Compute the base annual schedule without any overrides to get
        # the computed (rotation-based) assignments
        base_slots = scheduling_engine.compute_annual_schedule(
            year=year,
            teammates=teammates,
            shift_windows=shift_windows,
            overrides=[],  # No overrides — pure rotation schedule
        )

        # Build a lookup: (date, shift_type) -> list of computed teammate names
        base_schedule: dict[tuple[date, str], list[str]] = {}
        for slot in base_slots:
            base_schedule[(slot.date, slot.shift_type)] = slot.teammates

        # Build override lookup: (date_str, shift_type) -> override name
        override_map: dict[tuple[str, str], str] = {}
        for o in existing_overrides:
            override_map[(o.date, o.shift_type)] = o.name

        result: list[tuple[date, str]] = []

        for d in date_range:
            date_str = d.isoformat()
            for shift_type in shift_windows:
                key = (date_str, shift_type)

                if key in override_map:
                    # An override exists for this slot
                    override_name = override_map[key]
                    # Parse comma-separated names (overrides can have multiple)
                    override_names = [
                        n.strip() for n in override_name.split(",") if n.strip()
                    ]
                    if not override_names:
                        override_names = ["nobody"]

                    # Include this shift if the override assigns the teammate
                    if teammate_name in override_names:
                        result.append((d, shift_type))
                    # Otherwise the override replaces the teammate — exclude
                else:
                    # No override — use the base computed schedule
                    computed_names = base_schedule.get((d, shift_type), [])
                    if teammate_name in computed_names:
                        result.append((d, shift_type))

        return result

    def check_weekly_days(
        self,
        override_date: date,
        schedule_with_override: list[tuple[date, str]],
    ) -> list[ComplianceViolation]:
        """Check all 7-day rolling windows for weekly days violations.

        Evaluates up to 7 overlapping windows that include the override date.
        Each window is 7 consecutive calendar days. Windows start from
        (override_date - 6 days) through override_date.

        For each window, counts distinct calendar dates where the teammate
        has at least one shift. If the count exceeds 6, a violation is reported.

        Args:
            override_date: The date of the proposed override.
            schedule_with_override: List of (date, shift_type) tuples representing
                the teammate's projected schedule including the proposed override.

        Returns:
            List of ComplianceViolation objects for each window where day count
            exceeds 6 (empty if compliant).
        """
        violations: list[ComplianceViolation] = []

        # Evaluate up to 7 overlapping windows that include the override date.
        # window_start ranges from (override_date - 6) through override_date.
        for offset in range(7):
            window_start = override_date - timedelta(days=6 - offset)
            window_end = window_start + timedelta(days=6)

            # Count distinct calendar dates with at least one shift in this window
            distinct_dates: set[date] = set()
            for shift_date, shift_type in schedule_with_override:
                if window_start <= shift_date <= window_end:
                    distinct_dates.add(shift_date)

            day_count = len(distinct_dates)
            if day_count > self.WEEKLY_DAYS_LIMIT:
                violations.append(
                    ComplianceViolation(
                        rule="weekly_days",
                        projected=day_count,
                        limit=self.WEEKLY_DAYS_LIMIT,
                        window_start=window_start.isoformat(),
                        window_end=window_end.isoformat(),
                    )
                )

        return violations

    def check_daily_hours(
        self,
        teammate_name: str,
        override_date: date,
        schedule_with_override: list[tuple[date, str]],
        shift_windows: dict,
        teammates: list,
    ) -> list[ComplianceViolation]:
        """Check that total hours on the override date don't exceed 12.

        Sums durations of all shifts assigned to the teammate on that date.
        The schedule_with_override already has duplicates removed by the caller,
        so no double-counting occurs when the proposed override assigns the
        same teammate already in the slot.

        Args:
            teammate_name: The name of the teammate being checked.
            override_date: The date of the proposed override.
            schedule_with_override: List of (date, shift_type) tuples representing
                the teammate's projected schedule including the proposed override.
            shift_windows: Shift window configuration mapping shift_type to ShiftWindow.
            teammates: All teammate records (for custom_start lookup).

        Returns:
            List with one ComplianceViolation if total hours exceed 12,
            or empty list if compliant.
        """
        total_hours = 0.0

        for shift_date, shift_type in schedule_with_override:
            if shift_date == override_date:
                effective_start = self.get_effective_start(
                    teammate_name, shift_type, teammates, shift_windows
                )
                end_time = shift_windows[shift_type].end_time
                total_hours += self.compute_shift_duration(
                    effective_start, end_time
                )

        if total_hours > self.DAILY_HOURS_LIMIT:
            return [
                ComplianceViolation(
                    rule="daily_hours",
                    projected=total_hours,
                    limit=self.DAILY_HOURS_LIMIT,
                    window_start=None,
                    window_end=None,
                )
            ]

        return []

    def check_weekly_hours(
        self,
        teammate_name: str,
        override_date: date,
        schedule_with_override: list[tuple[date, str]],
        shift_windows: dict,
        teammates: list,
    ) -> list[ComplianceViolation]:
        """Check all 7-day rolling windows for weekly hours violations.

        Evaluates up to 7 overlapping windows that include the override date.
        Each window is 7 consecutive calendar days. Windows start from
        (override_date - 6 days) through override_date.

        For each window, filters the schedule to shifts within that window,
        sums durations using compute_shift_duration with effective start times,
        and reports a violation if the total exceeds 60 hours.

        Args:
            teammate_name: The name of the teammate being checked.
            override_date: The date of the proposed override.
            schedule_with_override: List of (date, shift_type) tuples representing
                the teammate's projected schedule including the proposed override.
            shift_windows: Shift window configuration mapping shift_type to ShiftWindow.
            teammates: All teammate records (for custom_start lookup).

        Returns:
            List of ComplianceViolation objects for each window where total
            hours exceed 60 (empty if compliant).
        """
        violations: list[ComplianceViolation] = []

        # Evaluate up to 7 overlapping windows that include the override date.
        # window_start ranges from (override_date - 6) through override_date.
        for offset in range(7):
            window_start = override_date - timedelta(days=6 - offset)
            window_end = window_start + timedelta(days=6)

            # Sum shift durations for all shifts within this window
            total_hours = 0.0
            for shift_date, shift_type in schedule_with_override:
                if window_start <= shift_date <= window_end:
                    effective_start = self.get_effective_start(
                        teammate_name, shift_type, teammates, shift_windows
                    )
                    end_time = shift_windows[shift_type].end_time
                    total_hours += self.compute_shift_duration(
                        effective_start, end_time
                    )

            if total_hours > self.WEEKLY_HOURS_LIMIT:
                violations.append(
                    ComplianceViolation(
                        rule="weekly_hours",
                        projected=total_hours,
                        limit=self.WEEKLY_HOURS_LIMIT,
                        window_start=window_start.isoformat(),
                        window_end=window_end.isoformat(),
                    )
                )

        return violations
