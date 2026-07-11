"""Schedule API routes for DC-ShiftMaster HTML."""

from flask import Blueprint, current_app, g, jsonify

schedule_bp = Blueprint("schedule", __name__)


@schedule_bp.route("/api/schedule/<int:year>/<int:month>")
def get_schedule(year: int, month: int):
    """Return schedule slots for a given year/month as JSON array."""
    if year < 1900 or year > 2100:
        return jsonify({"error": f"Invalid year {year}. Must be between 1900 and 2100."}), 400
    if month < 1 or month > 12:
        return jsonify({"error": f"Invalid month {month}. Must be between 1 and 12."}), 400

    try:
        db = current_app.config["db"]
        engine = current_app.config["engine"]
        team_id = getattr(g, 'team_id', None)

        teammates = db.get_teammates(team_id=team_id)
        shift_windows = db.get_shift_windows(team_id=team_id)
        overrides = db.get_overrides(year, team_id=team_id)

        slots = engine.compute_annual_schedule(year, teammates, shift_windows, overrides)

        # Filter to requested month
        month_slots = [s for s in slots if s.date.month == month]

        # Get end times from shift windows
        day_end = shift_windows["day"].end_time if "day" in shift_windows else "18:30"
        night_end = shift_windows["night"].end_time if "night" in shift_windows else "06:30"

        result = []
        for s in month_slots:
            result.append({
                "date": s.date.isoformat(),
                "shift_type": s.shift_type,
                "start_time": s.start_time,
                "end_time": day_end if s.shift_type == "day" else night_end,
                "teammates": s.teammates,
                "is_override": s.is_override,
                "teammate_starts": s.teammate_starts if s.teammate_starts else {},
            })

        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": f"Failed to compute schedule: {exc}"}), 500
