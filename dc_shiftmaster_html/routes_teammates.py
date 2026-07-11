"""Teammate API routes for DC-ShiftMaster HTML."""

import csv
import io

from flask import Blueprint, current_app, g, jsonify, request

from dc_shiftmaster.database import CrossTeamAccessError
from dc_shiftmaster.validation import validate_time_format

teammates_bp = Blueprint("teammates", __name__)

VALID_SHIFT_TYPES = {"FHD", "FHN", "BHD", "BHN", "Custom"}
VALID_DAYS = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}


@teammates_bp.route("/api/teammates", methods=["GET"])
def get_teammates():
    """Return all teammates as JSON array."""
    try:
        db = current_app.config["db"]
        team_id = getattr(g, 'team_id', None)
        teammates = db.get_teammates(team_id=team_id)
        return jsonify([
            {
                "id": t.id,
                "name": t.name,
                "shift_type": t.shift_type,
                "custom_start": t.custom_start,
                "custom_days": t.custom_days if t.custom_days else [],
            }
            for t in teammates
        ])
    except Exception as exc:
        return jsonify({"error": f"Failed to get teammates: {exc}"}), 500


@teammates_bp.route("/api/teammates", methods=["POST"])
def add_teammate():
    """Add a new teammate. Returns 201 on success, 400 on validation error."""
    try:
        data = request.get_json(force=True)
        name = data.get("name", "")
        shift_type = data.get("shift_type", "FHD")
        custom_start = data.get("custom_start", "")
        custom_days = data.get("custom_days", [])

        if not name or not name.strip():
            return jsonify({"error": "Teammate name must not be empty."}), 400

        if shift_type not in VALID_SHIFT_TYPES:
            return jsonify({"error": "Invalid shift type. Must be one of: FHD, FHN, BHD, BHN, Custom."}), 400

        if shift_type == "Custom":
            if not custom_days or not isinstance(custom_days, list) or len(custom_days) == 0:
                return jsonify({"error": "At least one day must be selected for Custom shift type."}), 400
            invalid_days = set(custom_days) - VALID_DAYS
            if invalid_days:
                return jsonify({"error": "Invalid day(s) in custom_days. Valid values: Mon, Tue, Wed, Thu, Fri, Sat, Sun."}), 400
        else:
            custom_days = []

        if custom_start:
            valid, err = validate_time_format(custom_start)
            if not valid:
                return jsonify({"error": err}), 400

        db = current_app.config["db"]
        team_id = getattr(g, 'team_id', None)
        new_id = db.add_teammate(name.strip(), shift_type, custom_start, custom_days, team_id=team_id)
        return jsonify({
            "id": new_id,
            "name": name.strip(),
            "shift_type": shift_type,
            "custom_start": custom_start,
            "custom_days": custom_days,
        }), 201
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@teammates_bp.route("/api/teammates/all", methods=["DELETE"])
def clear_all_teammates():
    """Delete all teammates for the current team. Returns deleted count."""
    try:
        db = current_app.config["db"]
        team_id = getattr(g, 'team_id', None)
        deleted = db.clear_all_teammates(team_id)
        return jsonify({"deleted": deleted}), 200
    except Exception as exc:
        return jsonify({"error": f"Failed to clear teammates: {exc}"}), 500


@teammates_bp.route("/api/teammates/<int:tid>", methods=["PUT"])
def update_teammate(tid: int):
    """Update an existing teammate. Returns 400 on validation error."""
    try:
        data = request.get_json(force=True)
        name = data.get("name", "")
        shift_type = data.get("shift_type", "FHD")
        custom_start = data.get("custom_start", "")
        custom_days = data.get("custom_days", [])

        if not name or not name.strip():
            return jsonify({"error": "Teammate name must not be empty."}), 400

        if shift_type not in VALID_SHIFT_TYPES:
            return jsonify({"error": "Invalid shift type. Must be one of: FHD, FHN, BHD, BHN, Custom."}), 400

        if shift_type == "Custom":
            if not custom_days or not isinstance(custom_days, list) or len(custom_days) == 0:
                return jsonify({"error": "At least one day must be selected for Custom shift type."}), 400
            invalid_days = set(custom_days) - VALID_DAYS
            if invalid_days:
                return jsonify({"error": "Invalid day(s) in custom_days. Valid values: Mon, Tue, Wed, Thu, Fri, Sat, Sun."}), 400
        else:
            custom_days = []

        if custom_start:
            valid, err = validate_time_format(custom_start)
            if not valid:
                return jsonify({"error": err}), 400

        db = current_app.config["db"]
        team_id = getattr(g, 'team_id', None)
        db.update_teammate(tid, name.strip(), shift_type, custom_start, custom_days, team_id=team_id)
        return jsonify({
            "id": tid,
            "name": name.strip(),
            "shift_type": shift_type,
            "custom_start": custom_start,
            "custom_days": custom_days,
        })
    except CrossTeamAccessError:
        return jsonify({"error": "Access denied: resource belongs to a different team", "code": "CROSS_TEAM_ACCESS"}), 403
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@teammates_bp.route("/api/teammates/<int:tid>", methods=["DELETE"])
def delete_teammate(tid: int):
    """Delete a teammate. Returns 204."""
    try:
        db = current_app.config["db"]
        team_id = getattr(g, 'team_id', None)
        db.delete_teammate(tid, team_id=team_id)
        return "", 204
    except CrossTeamAccessError:
        return jsonify({"error": "Access denied: resource belongs to a different team", "code": "CROSS_TEAM_ACCESS"}), 403
    except Exception as exc:
        return jsonify({"error": f"Failed to delete teammate: {exc}"}), 500


@teammates_bp.route("/api/teammates/import-csv", methods=["POST"])
def import_csv():
    """Import teammates from a CSV file upload.

    Each row: name,shift_type[,custom_start[,custom_days]]
    custom_days is semicolon-separated day abbreviations (e.g., Mon;Wed;Fri).
    Skips rows with invalid shift types or invalid custom_days for Custom type.
    Returns JSON summary with imported_count and skipped_rows.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    try:
        file = request.files["file"]
        content = file.read().decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(content))

        db = current_app.config["db"]
        team_id = getattr(g, 'team_id', None)
        imported_count = 0
        skipped_rows = []

        for row_num, row in enumerate(reader, start=1):
            if not row or not row[0].strip():
                skipped_rows.append(row_num)
                continue

            name = row[0].strip()
            raw_shift = row[1].strip() if len(row) > 1 else ""
            custom_start = row[2].strip() if len(row) > 2 else ""
            raw_days = row[3].strip() if len(row) > 3 else ""

            # Normalize shift_type: uppercase for standard types, title-case for Custom
            if raw_shift.upper() == "CUSTOM":
                shift_type = "Custom"
            else:
                shift_type = raw_shift.upper()

            if shift_type not in VALID_SHIFT_TYPES:
                skipped_rows.append(row_num)
                continue

            # Parse custom_days for Custom shift type
            custom_days = []
            if shift_type == "Custom":
                if not raw_days:
                    skipped_rows.append(row_num)
                    continue
                parsed_days = [d.strip() for d in raw_days.split(";") if d.strip()]
                if not parsed_days or not all(d in VALID_DAYS for d in parsed_days):
                    skipped_rows.append(row_num)
                    continue
                custom_days = parsed_days

            db.add_teammate(name, shift_type, custom_start, custom_days, team_id=team_id)
            imported_count += 1

        return jsonify({
            "imported_count": imported_count,
            "skipped_rows": skipped_rows,
        })
    except Exception as exc:
        return jsonify({"error": f"CSV import failed: {exc}"}), 500
