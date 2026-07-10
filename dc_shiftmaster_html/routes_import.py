"""Database import API route for DC-ShiftMaster HTML."""

import os
import sqlite3
import tempfile

from flask import Blueprint, current_app, jsonify, request

import_bp = Blueprint("import_db", __name__)


@import_bp.route("/api/import-db", methods=["POST"])
def import_db():
    """Import a .db file, merging its data into the active DatabaseManager.

    Teammates are added with new IDs. Shift windows are overwritten.
    Overrides with the same key take imported values.
    Returns JSON summary with counts. Returns 400 if invalid file.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    file = request.files["file"]

    # Save uploaded file to a temp location
    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = None
    try:
        file.save(tmp_path)

        # Try to open as SQLite and read expected tables
        try:
            conn = sqlite3.connect(tmp_path)
            conn.execute("SELECT 1")
        except Exception:
            if conn:
                conn.close()
                conn = None
            return jsonify({"error": "Invalid database file. Expected teammates.db format."}), 400

        # Check that expected tables exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        required = {"teammates", "shift_windows", "overrides"}
        if not required.issubset(tables):
            conn.close()
            conn = None
            return jsonify({"error": "Invalid database file. Expected teammates.db format."}), 400

        try:
            db = current_app.config["db"]

            # Check if custom_start column exists in imported db
            cursor.execute("PRAGMA table_info(teammates)")
            cols = [row[1] for row in cursor.fetchall()]
            has_custom_start = "custom_start" in cols

            # Import teammates (add with new IDs)
            if has_custom_start:
                cursor.execute("SELECT name, shift_type, custom_start FROM teammates")
            else:
                cursor.execute("SELECT name, shift_type FROM teammates")
            teammate_rows = cursor.fetchall()

            teammates_count = 0
            for row in teammate_rows:
                name = row[0]
                shift_type = row[1]
                custom_start = row[2] if has_custom_start and len(row) > 2 and row[2] else ""
                db.add_teammate(name, shift_type, custom_start)
                teammates_count += 1

            # Import shift windows (overwrite existing)
            cursor.execute("SELECT shift_type, start_time, end_time FROM shift_windows")
            sw_rows = cursor.fetchall()
            shift_windows_count = 0
            for row in sw_rows:
                db.update_shift_window(row[0], row[1], row[2])
                shift_windows_count += 1

            # Import overrides (same key = imported wins)
            cursor.execute("SELECT date, shift_type, name FROM overrides")
            ov_rows = cursor.fetchall()
            overrides_count = 0
            for row in ov_rows:
                db.set_override(row[0], row[1], row[2])
                overrides_count += 1

            conn.close()
            conn = None

            return jsonify({
                "teammates_count": teammates_count,
                "shift_windows_count": shift_windows_count,
                "overrides_count": overrides_count,
            })

        except Exception:
            if conn:
                conn.close()
                conn = None
            return jsonify({"error": "Invalid database file. Expected teammates.db format."}), 400

    finally:
        if conn:
            conn.close()
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass  # Windows may still hold the file briefly
