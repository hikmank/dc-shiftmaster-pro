"""Override API routes for DC-ShiftMaster HTML."""

from datetime import date as date_type

from flask import Blueprint, current_app, jsonify, request

from dc_shiftmaster.compliance import ComplianceValidator

overrides_bp = Blueprint("overrides", __name__)


@overrides_bp.route("/api/overrides/<int:year>")
def get_overrides(year: int):
    """Return all overrides for a given year as JSON array."""
    try:
        db = current_app.config["db"]
        overrides = db.get_overrides(year)
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
            db.set_override(date_str, shift_type, name)
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

        # Parse the override date
        override_date = date_type.fromisoformat(date_str)
        year = override_date.year

        # Gather data for validation
        shift_windows = db.get_shift_windows()
        teammates = db.get_teammates()
        existing_overrides = db.get_overrides(year)

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
        db.set_override(date_str, shift_type, name)
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
        db.remove_override(date_str, shift_type)
        return "", 204
    except Exception as exc:
        return jsonify({"error": f"Failed to remove override: {exc}"}), 500
