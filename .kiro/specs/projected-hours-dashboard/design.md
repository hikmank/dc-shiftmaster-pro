# Design Document: Projected Hours Dashboard

## Overview

The Projected Hours Dashboard adds a proactive labor compliance visibility layer to DC-ShiftMaster Pro. Rather than only surfacing compliance violations reactively (when an override is submitted), this feature computes and displays projected weekly hours, days worked, and maximum daily hours for every teammate on the Team Management page. It also provides an impact preview when a manager changes a teammate's rotation group, a daily breakdown detail view, real-time updates via WebSocket, and a rotation group compliance summary.

The design reuses the existing `ComplianceValidator` logic from `dc_shiftmaster/compliance.py` and the `SchedulingEngine` from `dc_shiftmaster/scheduling.py` to ensure projection calculations are consistent with enforcement. A new backend route module (`routes_projections.py`) exposes the Projection API, and a new frontend module (`projections.js`) renders the dashboard UI.

### Key Design Decisions

1. **Reuse ComplianceValidator** — The projection engine delegates shift duration calculation and schedule resolution to the existing `ComplianceValidator` class rather than reimplementing that logic. This guarantees consistency between what the dashboard shows and what the override validation enforces.

2. **Dedicated route module** — A new `routes_projections.py` blueprint keeps projection endpoints separate from the existing override, teammate, and schedule routes, following the established pattern.

3. **WebSocket channel extension** — The existing `/ws/coverage` WebSocket is extended to a general `/ws/updates` channel that broadcasts schedule-change events (overrides, teammate edits, shift window changes) in addition to coverage events. The frontend subscribes to relevant event types.

4. **Stateless computation** — All projection calculations are stateless and computed on-demand from the database. No projection cache is stored, keeping the system simple and avoiding stale-data bugs.

5. **Batch endpoint for group summary** — A single `/api/projections/summary` endpoint returns all teammates' projections grouped by rotation group, avoiding N+1 API calls on page load.

## Architecture

```mermaid
graph TD
    subgraph Frontend
        A[projections.js] -->|fetch| B[API.getProjections]
        A -->|fetch| C[API.getProjectionForTeammate]
        A -->|fetch| D[API.getProjectionPreview]
        E[ws.js] -->|WebSocket| F[/ws/updates]
        E -->|notify| A
    end

    subgraph Backend
        G[routes_projections.py] -->|uses| H[ProjectionService]
        H -->|delegates| I[ComplianceValidator]
        H -->|delegates| J[SchedulingEngine]
        H -->|reads| K[DatabaseManager]
        L[broadcast.py] -->|sends| F
    end

    G -->|JSON response| B
    G -->|JSON response| C
    G -->|JSON response| D
```

### Request Flow

1. **Page load**: Frontend calls `GET /api/projections/summary` → `routes_projections.py` → `ProjectionService.compute_all_projections()` → returns grouped data.
2. **Teammate detail**: Frontend calls `GET /api/projections/<teammate_id>` → returns daily breakdown.
3. **Impact preview**: Frontend calls `GET /api/projections/<teammate_id>/preview?proposed_group=BHD` → returns current vs. proposed comparison.
4. **Real-time update**: Override/teammate/settings change triggers `broadcast_schedule_event()` → WebSocket message → frontend re-fetches affected projections.

## Components and Interfaces

### Backend Components

#### 1. `ProjectionService` (new class in `dc_shiftmaster_html/projection_service.py`)

Orchestrates projection computation by composing the existing `ComplianceValidator` and `SchedulingEngine`.

```python
class ProjectionService:
    """Computes projected hours, days, and compliance status for teammates."""

    WEEKLY_HOURS_LIMIT = 60.0
    WEEKLY_DAYS_LIMIT = 6
    DAILY_HOURS_LIMIT = 12.0
    APPROACHING_THRESHOLD = 0.9  # 90% of limit

    def __init__(self, db: DatabaseManager, engine: SchedulingEngine):
        self.db = db
        self.engine = engine
        self.validator = ComplianceValidator()

    def compute_projection(
        self,
        teammate: Teammate,
        override_group: str | None = None,
    ) -> ProjectionResult:
        """Compute projected hours for a single teammate.

        Args:
            teammate: The teammate record.
            override_group: If provided, compute as if teammate were in this group.

        Returns:
            ProjectionResult with weekly_hours, days_worked, max_daily_hours,
            and compliance_status for each metric.
        """
        ...

    def compute_daily_breakdown(
        self,
        teammate: Teammate,
    ) -> list[DailyBreakdownEntry]:
        """Compute per-day detail for the evaluation period."""
        ...

    def compute_all_projections(self) -> dict[str, list[ProjectionResult]]:
        """Compute projections for all teammates, grouped by rotation group."""
        ...

    def compute_group_summary(self) -> dict[str, GroupSummary]:
        """Compute compliance summary per rotation group."""
        ...
```

#### 2. `routes_projections.py` (new Flask Blueprint)

```python
projections_bp = Blueprint("projections", __name__)

# GET /api/projections/summary
#   Returns all teammates' projections grouped by rotation group + group summaries

# GET /api/projections/<int:teammate_id>
#   Returns daily breakdown for a specific teammate

# GET /api/projections/<int:teammate_id>/preview?proposed_group=<group>
#   Returns current vs. proposed projection comparison
```

#### 3. `broadcast.py` (extended)

Add a new `broadcast_schedule_event()` function alongside the existing `broadcast_coverage_event()`:

```python
def broadcast_schedule_event(event_type: str, details: dict) -> None:
    """Broadcast a schedule-change event to all connected WebSocket clients.

    Event types: 'override_changed', 'teammate_updated', 'shift_window_updated'
    """
    ...
```

### Frontend Components

#### 4. `projections.js` (new module)

```javascript
var Projections = (function () {
    // Renders the Hours Dashboard panel on the Team Management page
    // Handles:
    //   - Rotation group summary bars
    //   - Per-teammate projected hours row
    //   - Daily breakdown detail view (expandable)
    //   - Impact preview during rotation group edit

    function load() { /* fetch /api/projections/summary and render */ }
    function showDetail(teammateId) { /* fetch daily breakdown */ }
    function showPreview(teammateId, proposedGroup) { /* fetch preview */ }
    function hidePreview() { /* dismiss impact preview */ }
    function refresh(teammateIds) { /* re-fetch specific teammates */ }

    return { load, showDetail, showPreview, hidePreview, refresh };
})();
```

#### 5. `ws.js` (extended)

Extend the WebSocket module to handle a new `/ws/updates` endpoint (or extend the existing `/ws/coverage` to accept schedule events):

```javascript
// Add schedule event listener registration
function onScheduleEvent(callback) { ... }
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projections/summary` | All projections + group summaries |
| GET | `/api/projections/<teammate_id>` | Daily breakdown for one teammate |
| GET | `/api/projections/<teammate_id>/preview?proposed_group=<group>` | Impact preview |

### Response Schemas

**GET /api/projections/summary**
```json
{
  "projections": {
    "FHD": [
      {
        "teammate_id": 1,
        "teammate_name": "John Smith",
        "weekly_hours": 48.5,
        "days_worked": 4,
        "max_daily_hours": 12.5,
        "weekly_hours_status": "compliant",
        "days_worked_status": "compliant",
        "daily_hours_status": "exceeding"
      }
    ],
    "FHN": [...],
    "BHD": [...],
    "BHN": [...]
  },
  "group_summaries": {
    "FHD": {
      "compliant_count": 3,
      "approaching_count": 1,
      "exceeding_count": 0,
      "overall_status": "warning"
    },
    ...
  }
}
```

**GET /api/projections/<teammate_id>**
```json
{
  "teammate_id": 1,
  "teammate_name": "John Smith",
  "evaluation_period_start": "2026-01-05",
  "evaluation_period_end": "2026-01-11",
  "daily_breakdown": [
    {
      "date": "2026-01-05",
      "shift_type": "day",
      "effective_start": "06:00",
      "shift_end": "18:30",
      "duration_hours": 12.50,
      "is_override": false,
      "is_rest_day": false,
      "rolling_7day_total": 37.50,
      "daily_hours_exceeds": true,
      "rolling_total_exceeds": false
    },
    {
      "date": "2026-01-06",
      "shift_type": null,
      "effective_start": null,
      "shift_end": null,
      "duration_hours": 0.0,
      "is_override": false,
      "is_rest_day": true,
      "rolling_7day_total": 37.50,
      "rolling_total_exceeds": false
    }
  ]
}
```

**GET /api/projections/<teammate_id>/preview?proposed_group=BHD**
```json
{
  "teammate_id": 1,
  "teammate_name": "John Smith",
  "current": {
    "weekly_hours": 48.5,
    "days_worked": 4,
    "max_daily_hours": 12.5,
    "weekly_hours_status": "compliant",
    "days_worked_status": "compliant",
    "daily_hours_status": "exceeding"
  },
  "proposed": {
    "weekly_hours": 60.0,
    "days_worked": 5,
    "max_daily_hours": 12.5,
    "weekly_hours_status": "exceeding",
    "days_worked_status": "approaching",
    "daily_hours_status": "exceeding"
  }
}
```

## Data Models

### New Dataclasses (in `dc_shiftmaster_html/projection_service.py`)

```python
from dataclasses import dataclass


@dataclass
class ProjectionResult:
    """Projection computation result for a single teammate."""
    teammate_id: int
    teammate_name: str
    weekly_hours: float          # Rounded to 1 decimal
    days_worked: int             # Whole number
    max_daily_hours: float       # Rounded to 1 decimal
    weekly_hours_status: str     # 'compliant' | 'approaching' | 'exceeding'
    days_worked_status: str      # 'compliant' | 'approaching' | 'exceeding'
    daily_hours_status: str      # 'compliant' | 'approaching' | 'exceeding'


@dataclass
class DailyBreakdownEntry:
    """One day's projection detail within the evaluation period."""
    date: str                    # YYYY-MM-DD
    shift_type: str | None       # 'day' | 'night' | None (rest day)
    effective_start: str | None  # HH:MM or None
    shift_end: str | None        # HH:MM or None
    duration_hours: float        # Rounded to 2 decimal places
    is_override: bool
    is_rest_day: bool
    rolling_7day_total: float    # Cumulative 7-day window total ending on this day
    daily_hours_exceeds: bool    # duration > 12
    rolling_total_exceeds: bool  # rolling_7day_total > 60


@dataclass
class GroupSummary:
    """Compliance summary for one rotation group."""
    compliant_count: int
    approaching_count: int
    exceeding_count: int
    overall_status: str          # 'compliant' | 'warning' | 'non_compliant'


@dataclass
class ImpactPreview:
    """Before/after comparison for a rotation group change."""
    teammate_id: int
    teammate_name: str
    current: ProjectionResult
    proposed: ProjectionResult
```

### Compliance Status Classification Logic

```python
def classify_status(value: float, limit: float) -> str:
    """Classify a projected value relative to its compliance limit.

    Returns:
        'exceeding' if value > limit
        'approaching' if value > limit * 0.9 and value <= limit
        'compliant' otherwise
    """
    if value > limit:
        return "exceeding"
    if value > limit * 0.9:
        return "approaching"
    return "compliant"
```

For the days-worked metric (integer), "approaching" is defined as exactly 5 days (the nearest whole number below the 6-day limit per Requirement 6.3).

### Evaluation Period

The evaluation period is the set of all rolling 7-day windows that include today's date. This means the date range spans from `today - 6` through `today + 6` (13 days total), matching the same window logic used by `ComplianceValidator.validate()`. The maximum values across all overlapping windows are reported.

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Compliance Status Classification

*For any* numeric value and its corresponding compliance limit (60 hours weekly, 6 days weekly, 12 hours daily), the `classify_status` function SHALL return "exceeding" when value > limit, "approaching" when value > limit × 0.9 and value ≤ limit (or exactly 5 for days), and "compliant" otherwise. For a teammate with multiple metrics, the most severe classification across all metrics SHALL determine the teammate's aggregate classification.

**Validates: Requirements 1.3, 1.4, 1.5, 1.6, 2.3, 2.4, 6.2, 6.3, 6.4, 6.6**

### Property 2: Maximum Weekly Hours Computation

*For any* teammate with a valid schedule (rotation group assignment, shift windows, and zero or more overrides), the projected weekly hours SHALL equal the maximum sum of shift durations across all rolling 7-day windows that include today, rounded to one decimal place. The shift duration for each day SHALL be computed using the teammate's effective start time (custom_start if set, otherwise shift window default) to the shift window end time.

**Validates: Requirements 3.1, 3.2**

### Property 3: Maximum Weekly Days Computation

*For any* teammate with a valid schedule, the projected days worked SHALL equal the maximum count of distinct calendar dates with at least one assigned shift across all rolling 7-day windows that include today, returned as a whole number.

**Validates: Requirements 3.3**

### Property 4: Maximum Daily Hours Computation

*For any* teammate with a valid schedule, the projected maximum daily hours SHALL equal the highest single-day total shift duration across all days in the evaluation period, rounded to one decimal place.

**Validates: Requirements 3.4**

### Property 5: Alternate Group Projection Preserves Overrides

*For any* teammate and any valid alternate rotation group (FHD, FHN, BHD, BHN), computing the projection with the alternate group SHALL use the alternate group's schedule while still applying all existing overrides that explicitly assign or remove the teammate by name. Days where an override assigns the teammate SHALL appear in the projected schedule regardless of the alternate group, and days where an override removes the teammate SHALL be excluded regardless of the alternate group.

**Validates: Requirements 3.5**

### Property 6: Invalid Group Rejection

*For any* string that is not one of the four defined rotation groups (FHD, FHN, BHD, BHN), the Projection API SHALL return an error response indicating the group is invalid, and SHALL NOT return projection values.

**Validates: Requirements 3.8**

### Property 7: Daily Breakdown Chronological Order and Completeness

*For any* teammate with a valid schedule, the daily breakdown SHALL contain exactly one entry per calendar day in the evaluation period, ordered chronologically. Each entry SHALL contain the date, shift type (or null for rest days), effective start time, shift end time, and duration rounded to 2 decimal places.

**Validates: Requirements 4.1**

### Property 8: Rolling 7-Day Total Computation

*For any* daily breakdown sequence, the `rolling_7day_total` for day N SHALL equal the sum of `duration_hours` values from day N-6 through day N (inclusive). If fewer than 7 days precede day N in the evaluation period, the sum SHALL include all available preceding days.

**Validates: Requirements 4.3**

### Property 9: Daily Breakdown Flags Correctness

*For any* daily breakdown entry, `daily_hours_exceeds` SHALL be true if and only if `duration_hours` > 12, `rolling_total_exceeds` SHALL be true if and only if `rolling_7day_total` > 60, `is_rest_day` SHALL be true if and only if `duration_hours` == 0 and no shift is assigned, and `is_override` SHALL be true if and only if an override exists in the database for that date and shift type affecting the teammate.

**Validates: Requirements 4.2, 4.4, 4.5**

### Property 10: Group Overall Status Derivation

*For any* rotation group containing one or more teammates with computed projections, the group's `overall_status` SHALL be "non_compliant" if at least one teammate has an "exceeding" classification, "warning" if no teammate is "exceeding" but at least one is "approaching", and "compliant" if all teammates are "compliant". The sum of `compliant_count + approaching_count + exceeding_count` SHALL equal the total number of teammates in the group.

**Validates: Requirements 6.1, 6.5, 6.7, 6.8**

### Property 11: Impact Preview Consistency

*For any* teammate and any valid proposed rotation group different from their current group, the impact preview SHALL return a "current" projection computed with the teammate's actual rotation group and a "proposed" projection computed with the proposed group. Both projections SHALL use the same evaluation period, the same overrides, and the same shift windows.

**Validates: Requirements 2.1**

## Error Handling

### Backend Error Handling

| Error Condition | HTTP Status | Response |
|----------------|-------------|----------|
| Teammate ID not found | 404 | `{"error": "Teammate not found"}` |
| Invalid rotation group parameter | 400 | `{"error": "Invalid rotation group '<value>'. Must be one of: FHD, FHN, BHD, BHN."}` |
| No shift windows configured | 500 | `{"error": "Shift windows not configured. Cannot compute projections."}` |
| Database unavailable | 500 | `{"error": "Failed to compute projections: <detail>"}` |
| Computation timeout (>2s) | 504 | `{"error": "Projection computation timed out"}` |

### Frontend Error Handling

- **API failure on page load**: Display "Projected hours unavailable" placeholder for each teammate row. Do not show partial data.
- **API failure on preview**: Display "Preview unavailable" within the impact preview area. Do not block save/cancel actions.
- **API failure on refresh**: Show stale-data indicator (yellow dot) on affected values. Retry once after 5 seconds. If retry fails, keep stale indicator visible.
- **WebSocket disconnect**: Show disconnected indicator (existing pattern from `ws.js`). Queue refresh for when connection restores.

### Validation Rules

- `proposed_group` query parameter must be one of: FHD, FHN, BHD, BHN
- `teammate_id` path parameter must be a positive integer matching an existing teammate
- All time values in responses use HH:MM 24-hour format
- All date values in responses use YYYY-MM-DD ISO format

## Testing Strategy

### Property-Based Tests (Hypothesis)

The feature's core computation logic is well-suited for property-based testing. The `ProjectionService` is a pure computation layer (given inputs, produces deterministic outputs) with a large input space (various teammate configurations, shift windows, override combinations).

**Library**: `hypothesis` (already used in the project)
**Minimum iterations**: 100 per property test
**Tag format**: `# Feature: projected-hours-dashboard, Property {N}: {title}`

Property tests will cover:
- `classify_status()` function (Property 1)
- `compute_projection()` weekly hours, days, and daily hours (Properties 2, 3, 4)
- Alternate group computation with override preservation (Property 5)
- Invalid group rejection (Property 6)
- Daily breakdown ordering and completeness (Property 7)
- Rolling 7-day total correctness (Property 8)
- Daily breakdown boolean flags (Property 9)
- Group summary aggregation (Property 10)
- Impact preview consistency (Property 11)

### Unit Tests (pytest)

Example-based tests for:
- API endpoint response structure validation
- Error responses for missing teammates, invalid groups
- UI rendering of compliance limits (static values)
- Preview dismiss on cancel/save
- Loading indicator display during fetch
- Stale-data indicator on refresh failure

### Integration Tests

- WebSocket broadcast triggers on override/teammate/settings changes
- End-to-end page load timing (<3 seconds)
- Real-time refresh within 5 seconds of change
- Concurrent projection requests under load

### Test File Organization

```
tests/
  test_projection_service.py          # Unit tests for ProjectionService
  test_projection_service_props.py    # Property-based tests (Properties 1-11)
  test_routes_projections.py          # API endpoint integration tests
dc_shiftmaster_html/static/js/__tests__/
  projections.test.js                 # Frontend unit tests (if test runner available)
```

