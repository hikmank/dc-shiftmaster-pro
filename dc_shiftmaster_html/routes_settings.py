"""Settings API routes for DC-ShiftMaster HTML."""

from flask import Blueprint, current_app, jsonify, request

from dc_shiftmaster.validation import validate_time_format

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/api/settings/shift-windows")
def get_shift_windows():
    """Return shift windows as JSON object keyed by 'day' and 'night'."""
    try:
        db = current_app.config["db"]
        windows = db.get_shift_windows()
        return jsonify({
            k: {
                "shift_type": v.shift_type,
                "start_time": v.start_time,
                "end_time": v.end_time,
            }
            for k, v in windows.items()
        })
    except Exception as exc:
        return jsonify({"error": f"Failed to get shift windows: {exc}"}), 500


@settings_bp.route("/api/settings/shift-windows/<shift_type>", methods=["PUT"])
def update_shift_window(shift_type: str):
    """Update a shift window's start/end times. Returns 400 on invalid times."""
    data = request.get_json(force=True)
    start_time = data.get("start_time", "")
    end_time = data.get("end_time", "")

    valid, err = validate_time_format(start_time)
    if not valid:
        return jsonify({"error": err}), 400

    valid, err = validate_time_format(end_time)
    if not valid:
        return jsonify({"error": err}), 400

    try:
        db = current_app.config["db"]
        db.update_shift_window(shift_type, start_time, end_time)
        return jsonify({
            "shift_type": shift_type,
            "start_time": start_time,
            "end_time": end_time,
        })
    except Exception as exc:
        return jsonify({"error": f"Failed to update shift window: {exc}"}), 500


@settings_bp.route("/api/settings/region")
def get_region():
    """Return the current region setting."""
    try:
        region = current_app.config.get("region", "")
        return jsonify({"region": region})
    except Exception as exc:
        return jsonify({"error": f"Failed to get region: {exc}"}), 500


@settings_bp.route("/api/settings/region", methods=["PUT"])
def set_region():
    """Update the region setting."""
    try:
        data = request.get_json(force=True)
        region = data.get("region", "")
        current_app.config["region"] = region
        return jsonify({"region": region})
    except Exception as exc:
        return jsonify({"error": f"Failed to set region: {exc}"}), 500
