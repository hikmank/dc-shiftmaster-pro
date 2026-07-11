"""ICS calendar export and import API routes for DC-ShiftMaster HTML."""

from flask import Blueprint, Response, current_app, g, jsonify, request

from dc_shiftmaster.ics_export import ICSExporter
from dc_shiftmaster.ics_parser import ICSParser
from dc_shiftmaster.json_schedule_import import JSONScheduleImporter
from dc_shiftmaster_html.routes_export import _compute_and_validate, _get_filename

ics_bp = Blueprint("ics", __name__)

# 5 MB file size limit
_MAX_FILE_SIZE = 5 * 1024 * 1024


@ics_bp.route("/api/export/<int:year>/ics")
def export_ics(year: int):
    """Export schedule as ICS calendar file download."""
    schedule, shift_windows, err = _compute_and_validate(year)
    if err:
        return err

    try:
        exporter = ICSExporter()
        ics_text = exporter.export(schedule, shift_windows)
        filename = _get_filename(year, "ics")
        return Response(
            ics_text,
            mimetype="text/calendar; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as exc:
        return jsonify({"error": f"ICS export failed: {exc}"}), 500


def _determine_shift_type(dtstart: str) -> str:
    """Determine shift type from DTSTART hour.

    Hours 05-13 inclusive → 'day', otherwise → 'night'.

    Args:
        dtstart: DTSTART value in YYYYMMDDTHHMMSS format.

    Returns:
        'day' or 'night'.
    """
    try:
        t_idx = dtstart.index("T")
        hour = int(dtstart[t_idx + 1 : t_idx + 3])
    except (ValueError, IndexError):
        return "night"
    return "day" if 5 <= hour <= 13 else "night"


def _resolve_name_from_summary(summary: str, roster_names: list[str]) -> str:
    """Resolve teammate name from SUMMARY against the team roster.

    SUMMARY format: "{shift_type} Shift - {name1, name2...}"
    If a roster name is found in the names portion, return it.
    Otherwise return the full SUMMARY text.

    Args:
        summary: The VEVENT SUMMARY string.
        roster_names: List of teammate names from the current team roster.

    Returns:
        Matched roster name, or full SUMMARY if no match.
    """
    if not summary:
        return summary

    # Try to extract names after " - " separator
    separator = " - "
    if separator in summary:
        names_part = summary.split(separator, 1)[1]
        extracted_names = [n.strip() for n in names_part.split(",")]

        # Check each extracted name against the roster
        for name in extracted_names:
            if name in roster_names:
                return name

    # If no separator match, check if any roster name appears in summary
    for roster_name in roster_names:
        if roster_name in summary:
            return roster_name

    # No match found - return full SUMMARY
    return summary


@ics_bp.route("/api/import/ics", methods=["POST"])
def import_ics():
    """Import an ICS file, creating overrides from VEVENT components.

    Validates file upload, parses ICS content, determines shift types,
    resolves teammate names, detects conflicts, and creates overrides.

    Query params:
        overwrite: If 'true', overwrite existing overrides on conflict.

    Returns:
        JSON with imported_count, skipped_count, conflicts, errors.
        HTTP 413 if file too large.
        HTTP 400 if invalid ICS format or no file.
        HTTP 422 if no events imported.
        HTTP 200 on success.
    """
    # Check file upload present
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"error": "No file uploaded."}), 400

    # Read file content and check size limit
    file_content = uploaded.read()
    if len(file_content) > _MAX_FILE_SIZE:
        return jsonify({"error": "File too large. Maximum size is 5 MB."}), 413

    # Decode file content
    try:
        ics_text = file_content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            ics_text = file_content.decode("latin-1")
        except Exception:
            return jsonify({"error": "Unable to decode file content."}), 400

    # Parse ICS file
    parser = ICSParser()
    try:
        parse_result = parser.parse(ics_text)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # Get team context and database
    team_id = getattr(g, "team_id", None)
    db = current_app.config["db"]

    # Get current team roster for name resolution
    teammates = db.get_teammates(team_id=team_id)
    roster_names = [t.name for t in teammates]

    # Check overwrite parameter
    overwrite = request.args.get("overwrite", "").lower() == "true"

    # Collect results
    imported_count = 0
    skipped_count = 0
    conflicts = []
    errors = list(parse_result.errors)

    # Add parser-skipped events to skipped count and errors
    for skipped_desc in parse_result.skipped:
        errors.append(skipped_desc)
        skipped_count += 1

    # If no events parsed and no skipped, report empty file
    if not parse_result.events and not errors:
        return jsonify({
            "imported_count": 0,
            "skipped_count": 0,
            "conflicts": [],
            "errors": ["No VEVENT components found in ICS file."],
        }), 422

    # Build cache of existing overrides for conflict detection
    existing_overrides: dict[tuple[str, str], str] = {}
    years_seen: set[int] = set()
    for event in parse_result.events:
        try:
            years_seen.add(int(event.dtstart[:4]))
        except (ValueError, IndexError):
            pass

    for year in years_seen:
        for ovr in db.get_overrides(year, team_id=team_id):
            existing_overrides[(ovr.date, ovr.shift_type)] = ovr.name

    # Process each parsed event
    for event in parse_result.events:
        # Determine shift_type from DTSTART hour
        shift_type = _determine_shift_type(event.dtstart)

        # Extract date from DTSTART (YYYYMMDD portion)
        try:
            date_str = f"{event.dtstart[:4]}-{event.dtstart[4:6]}-{event.dtstart[6:8]}"
            # Validate the date components are numeric
            int(event.dtstart[:4])
            int(event.dtstart[4:6])
            int(event.dtstart[6:8])
        except (ValueError, IndexError):
            errors.append(f"Invalid DTSTART format: {event.dtstart}")
            skipped_count += 1
            continue

        # Resolve name from SUMMARY
        name = _resolve_name_from_summary(event.summary, roster_names)
        if not name:
            name = event.summary if event.summary else "Unknown"

        # Check for conflicts
        key = (date_str, shift_type)
        if key in existing_overrides:
            if overwrite:
                # Overwrite existing override
                db.set_override(date_str, shift_type, name, team_id=team_id)
                imported_count += 1
                existing_overrides[key] = name
            else:
                # Skip and report conflict
                conflicts.append({
                    "date": date_str,
                    "shift_type": shift_type,
                    "existing_name": existing_overrides[key],
                })
                skipped_count += 1
        else:
            # No conflict, create override
            db.set_override(date_str, shift_type, name, team_id=team_id)
            imported_count += 1
            # Track in cache for duplicate detection within same file
            existing_overrides[key] = name

    # Build response
    response_data = {
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "conflicts": conflicts,
        "errors": errors,
    }

    if imported_count == 0:
        return jsonify(response_data), 422

    return jsonify(response_data), 200


@ics_bp.route("/api/import/schedule-json", methods=["POST"])
def import_schedule_json():
    """Import a JSON schedule file, creating overrides from entries."""
    # Validate file upload
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"error": "No file uploaded."}), 400

    # Read file content and check size limit
    file_content = uploaded.read()
    if len(file_content) > _MAX_FILE_SIZE:
        return jsonify({"error": "File too large. Maximum size is 5 MB."}), 413

    # Parse JSON via JSONScheduleImporter
    importer = JSONScheduleImporter()
    try:
        result = importer.parse(file_content.decode("utf-8"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # Get team context and database
    team_id = getattr(g, "team_id", None)
    db = current_app.config["db"]

    # Check overwrite parameter
    overwrite = request.args.get("overwrite", "").lower() == "true"

    # Gather existing overrides for conflict detection
    # Collect all unique years from entries to query overrides
    years_seen = set()
    for entry in result.entries:
        year_str = entry.date[:4]
        try:
            years_seen.add(int(year_str))
        except ValueError:
            pass

    existing_overrides = {}
    for year in years_seen:
        for ovr in db.get_overrides(year, team_id=team_id):
            key = (ovr.date, ovr.shift_type)
            existing_overrides[key] = ovr.name

    # Process entries: detect conflicts, import or skip
    imported_count = 0
    skipped_count = 0
    conflicts = []
    errors = list(result.errors)  # Start with parse errors

    for entry in result.entries:
        key = (entry.date, entry.shift_type)
        if key in existing_overrides:
            if overwrite:
                # Overwrite existing override
                db.set_override(entry.date, entry.shift_type, entry.name, team_id=team_id)
                imported_count += 1
                # Update local cache so subsequent duplicates in same file are detected
                existing_overrides[key] = entry.name
            else:
                # Skip and report conflict
                conflicts.append({
                    "date": entry.date,
                    "shift_type": entry.shift_type,
                    "existing_name": existing_overrides[key],
                })
                skipped_count += 1
        else:
            # No conflict, create override
            db.set_override(entry.date, entry.shift_type, entry.name, team_id=team_id)
            imported_count += 1
            # Track in local cache for duplicate detection within same file
            existing_overrides[key] = entry.name

    # Build response
    response_data = {
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "conflicts": conflicts,
        "errors": errors,
    }

    if imported_count == 0:
        return jsonify(response_data), 422

    return jsonify(response_data), 200
