"""Export API routes for DC-ShiftMaster HTML."""

import os
import tempfile
from datetime import date

from flask import Blueprint, Response, current_app, g, jsonify, request

from dc_shiftmaster.csv_export import CSVExporter, JSONExporter, validate_schedule
from dc_shiftmaster.excel_export import ExcelExporter

export_bp = Blueprint("export", __name__)


def _compute_and_validate(year: int):
    try:
        db = current_app.config["db"]
        engine = current_app.config["engine"]
        team_id = getattr(g, 'team_id', None)
        teammates = db.get_teammates(team_id=team_id)
        shift_windows = db.get_shift_windows(team_id=team_id)
        overrides = db.get_overrides(year, team_id=team_id)
        schedule = engine.compute_annual_schedule(year, teammates, shift_windows, overrides)

        # Apply date range filter if provided
        from_str = request.args.get("from")
        to_str = request.args.get("to")
        if from_str:
            from_date = date.fromisoformat(from_str)
            schedule = [s for s in schedule if s.date >= from_date]
        if to_str:
            to_date = date.fromisoformat(to_str)
            schedule = [s for s in schedule if s.date <= to_date]

        errors = validate_schedule(schedule)
        if errors:
            return None, shift_windows, (jsonify({"error": errors[0]}), 400)
        return schedule, shift_windows, None
    except ValueError as exc:
        return None, {}, (jsonify({"error": f"Invalid date format: {exc}"}), 400)
    except Exception as exc:
        return None, {}, (jsonify({"error": f"Failed to compute schedule: {exc}"}), 500)


def _get_filename(year: int, ext: str) -> str:
    """Build export filename using region (default 'SITE')."""
    region = current_app.config.get("region", "") or "SITE"
    return f"{region}_{year}_schedule.{ext}"


def _file_response(tmp_path: str, mimetype: str, download_name: str):
    """Read a temp file into memory, delete it, and return a Response."""
    with open(tmp_path, "rb") as f:
        data = f.read()
    os.unlink(tmp_path)
    return Response(
        data,
        mimetype=mimetype,
        headers={"Content-Disposition": f"attachment; filename={download_name}"},
    )


@export_bp.route("/api/export/<int:year>/csv")
def export_csv(year: int):
    """Export schedule as CSV download."""
    schedule, shift_windows, err = _compute_and_validate(year)
    if err:
        return err

    fd, tmp_path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        CSVExporter().export(schedule, tmp_path)
        return _file_response(tmp_path, "text/csv", _get_filename(year, "csv"))
    except Exception as exc:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return jsonify({"error": f"CSV export failed: {exc}"}), 500


@export_bp.route("/api/export/<int:year>/json")
def export_json(year: int):
    """Export schedule as JSON download."""
    schedule, shift_windows, err = _compute_and_validate(year)
    if err:
        return err

    fd, tmp_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        JSONExporter().export(schedule, tmp_path)
        return _file_response(tmp_path, "application/json", _get_filename(year, "json"))
    except Exception as exc:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return jsonify({"error": f"JSON export failed: {exc}"}), 500


@export_bp.route("/api/export/<int:year>/xlsx")
def export_xlsx(year: int):
    """Export schedule as Excel download."""
    schedule, shift_windows, err = _compute_and_validate(year)
    if err:
        return err

    engine = current_app.config["engine"]

    fd, tmp_path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        ExcelExporter().export(year, schedule, engine, tmp_path, shift_windows=shift_windows)
        return _file_response(
            tmp_path,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            _get_filename(year, "xlsx"),
        )
    except Exception as exc:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return jsonify({"error": f"Excel export failed: {exc}"}), 500
