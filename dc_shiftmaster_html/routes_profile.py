"""Profile and team management API routes for DC-ShiftMaster HTML.

Handles team CRUD, membership, and session-based team selection.
"""

import json
import sqlite3

from flask import Blueprint, current_app, g, jsonify, request, session

from dc_shiftmaster.database import TeamMembershipError

profile_bp = Blueprint("profile", __name__)


def _require_auth():
    """Check that the user is authenticated via session.

    Returns:
        The user_id if authenticated, or a tuple (response, status_code) on failure.
    """
    user_id = session.get("user_id")
    if not user_id:
        return None
    return user_id


@profile_bp.route("/api/teams", methods=["GET"])
def list_teams():
    """List all teams the current user belongs to."""
    user_id = _require_auth()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        db = current_app.config["db"]
        teams = db.get_teams_for_user(user_id)
        return jsonify(teams)
    except Exception as exc:
        return jsonify({"error": f"Failed to list teams: {exc}"}), 500


@profile_bp.route("/api/teams", methods=["POST"])
def create_team():
    """Create a new team profile.

    Expects JSON body with site_code and display_name.
    Returns 201 with the created team details.
    """
    user_id = _require_auth()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON body"}), 400

    site_code = data.get("site_code", "")
    display_name = data.get("display_name", "")

    if not display_name or not display_name.strip():
        return jsonify({"error": "Display name is required"}), 400

    db = current_app.config["db"]

    try:
        result = db.create_team(site_code, display_name.strip(), user_id)
        return jsonify(result), 201
    except ValueError as exc:
        return jsonify({"error": str(exc), "code": "INVALID_SITE_CODE"}), 400
    except sqlite3.IntegrityError:
        return jsonify({
            "error": f"Site code '{site_code}' is already in use.",
            "code": "SITE_CODE_EXISTS",
        }), 409


@profile_bp.route("/api/teams/<int:team_id>", methods=["DELETE"])
def delete_team(team_id: int):
    """Delete a team profile. Only admins can perform this action."""
    user_id = _require_auth()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    db = current_app.config["db"]

    # Verify user is admin of this team
    role = db.get_user_role(user_id, team_id)
    if role is None:
        return jsonify({"error": "Team not found", "code": "TEAM_NOT_FOUND"}), 404
    if role != "admin":
        return jsonify({
            "error": "Only team admins can delete a team.",
            "code": "PERMISSION_DENIED",
        }), 403

    try:
        db.delete_team(team_id)
        return "", 204
    except Exception as exc:
        return jsonify({"error": f"Failed to delete team: {exc}"}), 500


@profile_bp.route("/api/teams/<int:team_id>/join", methods=["POST"])
def join_team(team_id: int):
    """Join a team by site code.

    Expects JSON body with site_code. The team_id in the URL is ignored
    in favor of looking up the team by site_code from the request body.
    """
    user_id = _require_auth()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON body"}), 400

    site_code = data.get("site_code", "")
    if not site_code:
        return jsonify({"error": "site_code is required"}), 400

    db = current_app.config["db"]

    # Look up team by site code
    team = db.get_team_by_site_code(site_code)
    if team is None:
        return jsonify({"error": "Team not found", "code": "TEAM_NOT_FOUND"}), 404

    try:
        membership = db.join_team(user_id, team["id"])
        return jsonify(membership), 200
    except TeamMembershipError as exc:
        return jsonify({"error": exc.message, "code": exc.code}), 409


@profile_bp.route("/api/teams/<int:team_id>/members", methods=["GET"])
def list_members(team_id: int):
    """List all members of a team with their roles."""
    user_id = _require_auth()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    db = current_app.config["db"]

    # Verify the user is a member of this team
    if not db.is_team_member(user_id, team_id):
        return jsonify({"error": "Team not found", "code": "TEAM_NOT_FOUND"}), 404

    try:
        members = db.get_team_members(team_id)
        return jsonify(members)
    except Exception as exc:
        return jsonify({"error": f"Failed to list members: {exc}"}), 500


@profile_bp.route("/api/teams/<int:team_id>/members/<int:target_user_id>", methods=["DELETE"])
def remove_member(team_id: int, target_user_id: int):
    """Remove a member from a team. Only admins can perform this action."""
    user_id = _require_auth()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    db = current_app.config["db"]

    try:
        db.remove_member(team_id, target_user_id, user_id)
        return "", 204
    except TeamMembershipError as exc:
        if exc.code == "PERMISSION_DENIED":
            return jsonify({"error": exc.message, "code": exc.code}), 403
        elif exc.code == "NOT_A_MEMBER":
            return jsonify({"error": exc.message, "code": exc.code}), 400
        elif exc.code == "SOLE_ADMIN":
            return jsonify({"error": exc.message, "code": exc.code}), 400
        else:
            return jsonify({"error": exc.message, "code": exc.code}), 400


@profile_bp.route("/api/teams/select", methods=["POST"])
def select_team():
    """Set the active team for the session.

    Expects JSON body with team_id. Verifies the user is a member
    of the team before setting it as active.
    """
    user_id = _require_auth()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON body"}), 400

    team_id = data.get("team_id")
    if team_id is None:
        return jsonify({"error": "team_id is required"}), 400

    db = current_app.config["db"]

    # Verify user is a member of this team
    if not db.is_team_member(user_id, team_id):
        return jsonify({"error": "Team not found or not a member", "code": "TEAM_NOT_FOUND"}), 404

    # Set active team in session
    session["active_team_id"] = team_id

    # Update selected_at timestamp in the database
    try:
        cursor = db.conn.cursor()
        cursor.execute(
            "UPDATE team_members SET selected_at = datetime('now') "
            "WHERE team_id = ? AND user_id = ?",
            (team_id, user_id),
        )
        db.conn.commit()
    except Exception:
        # Non-critical — session is already set
        pass

    return jsonify({"active_team_id": team_id}), 200


VALID_SHIFT_TYPES = {"FHD", "FHN", "BHD", "BHN", "Custom"}
VALID_DAYS = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}


@profile_bp.route("/api/teams/import-json", methods=["POST"])
def import_json():
    """Import teammates from a JSON file into the active team.

    Accepts multipart form data with a 'file' field containing a JSON file.
    The JSON should be an array of teammate objects with fields:
      - name (required)
      - shift_type (required, one of FHD, FHN, BHD, BHN, Custom)
      - custom_start (optional, HH:MM format)
      - custom_days (optional, list of day abbreviations - only valid for Custom shift_type)

    Returns a summary with imported_count, skipped_rows, and duplicate_count.
    Invariant: imported_count + len(skipped_rows) + duplicate_count == total entries
    """
    user_id = _require_auth()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    # Get team_id from middleware context or session (route is middleware-exempt
    # since it falls under /api/teams prefix)
    team_id = getattr(g, "team_id", None) or session.get("active_team_id")
    if team_id is None:
        return jsonify({"error": "No team selected", "code": "NO_TEAM"}), 403

    # Check for file in the request
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Parse JSON content
    try:
        content = file.read().decode("utf-8")
        data = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return jsonify({"error": f"Invalid JSON file: {exc}"}), 400

    if not isinstance(data, list):
        return jsonify({"error": "JSON must be an array of teammate objects"}), 400

    db = current_app.config["db"]

    # Get existing teammate names for duplicate detection
    existing_teammates = db.get_teammates(team_id=team_id)
    existing_names = {t.name.lower() for t in existing_teammates}

    imported_count = 0
    skipped_rows = []
    duplicate_count = 0

    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            skipped_rows.append({"index": index, "reason": "Entry is not an object"})
            continue

        # Validation 1: Missing or empty name
        name = entry.get("name", "")
        if not name or not str(name).strip():
            skipped_rows.append({"index": index, "reason": "Missing name field"})
            continue

        name = str(name).strip()

        # Validation 2: Missing or invalid shift_type
        shift_type = entry.get("shift_type", "")
        if not shift_type or shift_type not in VALID_SHIFT_TYPES:
            skipped_rows.append(
                {"index": index, "reason": f"Invalid shift_type: {shift_type}"}
            )
            continue

        # Validation 5: Non-Custom shift_type with non-empty custom_days field
        # Allow empty custom_days ([] or null) for round-trip compatibility with export format (Req 9.8)
        custom_days_value = entry.get("custom_days", None)
        if shift_type != "Custom" and custom_days_value and isinstance(custom_days_value, list) and len(custom_days_value) > 0:
            skipped_rows.append(
                {
                    "index": index,
                    "reason": "Invalid field combination: custom_days not allowed for non-Custom shift_type",
                }
            )
            continue

        # Validation 3 & 4: Custom shift_type requires valid custom_days
        custom_days = entry.get("custom_days", None)
        if shift_type == "Custom":
            if not custom_days or not isinstance(custom_days, list) or len(custom_days) == 0:
                skipped_rows.append(
                    {"index": index, "reason": "Custom shift_type requires non-empty custom_days"}
                )
                continue

            # Validate day values
            invalid_days = [d for d in custom_days if d not in VALID_DAYS]
            if invalid_days:
                skipped_rows.append(
                    {"index": index, "reason": "Invalid custom_days values"}
                )
                continue

        # Validation 6: Duplicate name check
        if name.lower() in existing_names:
            duplicate_count += 1
            continue

        # Valid entry — insert into database
        custom_start = entry.get("custom_start", "")
        if custom_days is None:
            custom_days = []

        try:
            db.add_teammate(
                name=name,
                shift_type=shift_type,
                custom_start=custom_start,
                custom_days=custom_days,
                team_id=team_id,
            )
            imported_count += 1
            # Add to existing names to catch duplicates within the import file
            existing_names.add(name.lower())
        except Exception as exc:
            skipped_rows.append({"index": index, "reason": f"Database error: {exc}"})

    return jsonify({
        "imported_count": imported_count,
        "skipped_rows": skipped_rows,
        "duplicate_count": duplicate_count,
    }), 200
