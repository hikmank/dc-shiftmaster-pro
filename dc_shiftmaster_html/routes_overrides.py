"""Override API routes for DC-ShiftMaster HTML."""

import re
from datetime import date as date_type

from flask import Blueprint, current_app, g, jsonify, request

from dc_shiftmaster.compliance import ComplianceValidator
from dc_shiftmaster.database import CrossTeamAccessError

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

overrides_bp = Blueprint("overrides", __name__)


@overrides_bp.route("/api/overrides/<int:year>")
def get_overrides(year: int):
    """Return all overrides for a given year as JSON array."""
    try:
        db = current_app.config["db"]
        team_id = getattr(g, 'team_id', None)
        overrides = db.get_overrides(year, team_id=team_id)
        return jsonify([
            {
                "date": o.date,
                "shift_type": o.shift_type,
                "name": o.name,
            }
            for o in overrides
        ])
    except Exception as exc:
        return jsonify({"error": f"Failed to get overrides: {exc}"}), 500


@overrides_bp.route("/api/overrides", methods=["POST"])
def set_override():
    """Set an override with compliance validation.

    Request body:
        date: str (YYYY-MM-DD)
        shift_type: str ('day' or 'night')
        name: str (teammate name or 'nobody')
        acknowledge_violations: bool (optional, default False)

    Returns:
        201: Override applied successfully
        422: Compliance violations detected (with violation details)
        500: Internal error
    """
    data = request.get_json(force=True)
    date_str = data.get("date", "")
    shift_type = data.get("shift_type", "")
    name = data.get("name", "")
    acknowledge_violations = data.get("acknowledge_violations", False)

    if acknowledge_violations:
        # Skip validation and persist the override directly
        try:
            db = current_app.config["db"]
            team_id = getattr(g, 'team_id', None)
            db.set_override(date_str, shift_type, name, team_id=team_id)
            return jsonify({
                "date": date_str,
                "shift_type": shift_type,
                "name": name,
                "acknowledged_violations": True,
            }), 201
        except Exception as exc:
            return jsonify({"error": f"Failed to set override: {exc}"}), 500

    # Perform compliance validation
    try:
        db = current_app.config["db"]
        engine = current_app.config["engine"]
        team_id = getattr(g, 'team_id', None)

        # Parse the override date
        override_date = date_type.fromisoformat(date_str)
        year = override_date.year

        # Gather data for validation
        shift_windows = db.get_shift_windows(team_id=team_id)
        teammates = db.get_teammates(team_id=team_id)
        existing_overrides = db.get_overrides(year, team_id=team_id)

        # Run compliance validation
        validator = ComplianceValidator()
        result = validator.validate(
            teammate_name=name,
            override_date=override_date,
            override_shift_type=shift_type,
            shift_windows=shift_windows,
            teammates=teammates,
            existing_overrides=existing_overrides,
            proposed_override_name=name,
            scheduling_engine=engine,
            year=year,
        )

        if not result.passed:
            # Return 422 with violation details
            violations_payload = [
                {
                    "rule": v.rule,
                    "projected": v.projected,
                    "limit": v.limit,
                    "window_start": v.window_start,
                    "window_end": v.window_end,
                }
                for v in result.violations
            ]
            return jsonify({
                "status": "compliance_warning",
                "violations": violations_payload,
            }), 422

        # No violations — persist the override
        db.set_override(date_str, shift_type, name, team_id=team_id)
        return jsonify({
            "date": date_str,
            "shift_type": shift_type,
            "name": name,
        }), 201

    except Exception as exc:
        return jsonify({"error": f"Compliance validation failed: {exc}"}), 500


@overrides_bp.route("/api/overrides", methods=["DELETE"])
def remove_override():
    """Remove an override. Returns 204."""
    data = request.get_json(force=True)
    date_str = data.get("date", "")
    shift_type = data.get("shift_type", "")

    try:
        db = current_app.config["db"]
        team_id = getattr(g, 'team_id', None)
        db.remove_override(date_str, shift_type, team_id=team_id)
        return "", 204
    except Exception as exc:
        return jsonify({"error": f"Failed to remove override: {exc}"}), 500


def _validate_date(value: str) -> bool:
    """Return True if value is a valid YYYY-MM-DD date string."""
    if not _DATE_RE.match(value):
        return False
    try:
        date_type.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False


def _parse_and_validate_bulk_request(data: dict):
    """Validate a bulk-delete/preview request body.

    Returns:
        (mode, params) on success where params is mode-specific data.
    Raises:
        ValueError with a descriptive message on validation failure.
    """
    mode = data.get("mode")
    if mode not in ("range", "keys", "year"):
        raise ValueError("Invalid mode. Must be 'range', 'keys', or 'year'.")

    if mode == "range":
        start_date = data.get("start_date", "")
        end_date = data.get("end_date", "")
        if not _validate_date(start_date) or not _validate_date(end_date):
            raise ValueError("Invalid date format. Use YYYY-MM-DD.")
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date.")
        return mode, {"start_date": start_date, "end_date": end_date}

    elif mode == "keys":
        keys = data.get("keys")
        if not isinstance(keys, list) or len(keys) == 0:
            raise ValueError("keys array must not be empty.")
        for i, key in enumerate(keys):
            if not isinstance(key, dict):
                raise ValueError(
                    f"Invalid key at index {i}: missing 'date' or 'shift_type'."
                )
            key_date = key.get("date")
            key_shift = key.get("shift_type")
            if not key_date or not key_shift:
                raise ValueError(
                    f"Invalid key at index {i}: missing 'date' or 'shift_type'."
                )
            if not _validate_date(key_date):
                raise ValueError("Invalid date format. Use YYYY-MM-DD.")
        return mode, {"keys": [(k["date"], k["shift_type"]) for k in keys]}

    else:  # mode == "year"
        year = data.get("year")
        if not isinstance(year, int) or year < 1000 or year > 9999:
            raise ValueError("year must be a 4-digit integer.")
        return mode, {"year": year}


@overrides_bp.route("/api/overrides/bulk/preview", methods=["POST"])
def preview_bulk_delete():
    """Return the count of overrides that would be deleted.

    Request body (one of):
        {"mode": "range", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}
        {"mode": "keys", "keys": [{"date": "...", "shift_type": "..."}]}
        {"mode": "year", "year": 2025}

    Returns:
        200: {"count": N}
        400: {"error": "..."}
    """
    data = request.get_json(force=True)
    try:
        mode, params = _parse_and_validate_bulk_request(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db = current_app.config["db"]
    team_id = getattr(g, 'team_id', None)

    try:
        if mode == "range":
            count = db.count_overrides_in_range(
                params["start_date"], params["end_date"], team_id=team_id
            )
        elif mode == "keys":
            # Count how many of the specified keys actually exist
            count = 0
            for date_val, shift_type in params["keys"]:
                count += db.count_overrides_in_range(
                    date_val, date_val, team_id=team_id
                )
        else:  # year
            year = params["year"]
            count = db.count_overrides_in_range(
                f"{year}-01-01", f"{year}-12-31", team_id=team_id
            )
        return jsonify({"count": count})
    except Exception as exc:
        return jsonify({"error": f"Preview failed: {exc}"}), 500


@overrides_bp.route("/api/overrides/bulk", methods=["DELETE"])
def bulk_delete():
    """Bulk delete overrides.

    Request body (same schema as preview):
        {"mode": "range", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}
        {"mode": "keys", "keys": [{"date": "...", "shift_type": "..."}]}
        {"mode": "year", "year": 2025}

    Returns:
        200: {"deleted_count": N}
        400: {"error": "..."}
        500: {"error": "..."}
    """
    data = request.get_json(force=True)
    try:
        mode, params = _parse_and_validate_bulk_request(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db = current_app.config["db"]
    team_id = getattr(g, 'team_id', None)

    try:
        if mode == "range":
            deleted_count = db.bulk_delete_overrides_by_range(
                params["start_date"], params["end_date"], team_id=team_id
            )
        elif mode == "keys":
            deleted_count = db.bulk_delete_overrides_by_keys(
                params["keys"], team_id=team_id
            )
        else:  # year
            deleted_count = db.bulk_delete_overrides_by_year(
                params["year"], team_id=team_id
            )
        return jsonify({"deleted_count": deleted_count})
    except Exception as exc:
        return jsonify({"error": f"Bulk delete failed: {exc}"}), 500
