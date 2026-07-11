"""Coverage request API routes for DC-ShiftMaster HTML.

Provides endpoints for creating, listing, claiming, unclaiming, and
cancelling coverage requests, plus personal shift/request views.
"""

import logging
from datetime import date

from flask import Blueprint, current_app, g, jsonify, request, session

from dc_shiftmaster.database import CrossTeamAccessError
from dc_shiftmaster_html.broadcast import broadcast_coverage_event
from dc_shiftmaster_html.email_service import send_coverage_email

logger = logging.getLogger(__name__)

coverage_bp = Blueprint("coverage", __name__, url_prefix="/api/coverage")


def _require_login():
    """Return the logged-in user_id, or (error_response, status_code) if not authenticated."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return user_id


def _coverage_to_dict(cr, db=None):
    """Convert a CoverageRequest dataclass to a JSON-safe dict.

    When *db* is provided, resolves requester and claimer display names.
    """
    d = {
        "id": cr.id,
        "requester_id": cr.requester_id,
        "date": cr.date,
        "shift_type": cr.shift_type,
        "note": cr.note,
        "status": cr.status,
        "claimer_id": cr.claimer_id,
        "created_at": cr.created_at,
        "claimed_at": cr.claimed_at,
        "requester_display_name": None,
        "claimer_display_name": None,
    }
    if db is not None:
        requester = db.get_user_by_id(cr.requester_id)
        d["requester_display_name"] = requester.display_name if requester else None
        if cr.claimer_id:
            claimer = db.get_user_by_id(cr.claimer_id)
            d["claimer_display_name"] = claimer.display_name if claimer else None
    return d


@coverage_bp.route("", methods=["GET"])
def list_coverage():
    """List coverage requests, optionally filtered by ?status=open|claimed|cancelled."""
    db = current_app.config["db"]
    status = request.args.get("status")
    team_id = getattr(g, 'team_id', None)
    reqs = db.get_coverage_requests(status=status, team_id=team_id)
    return jsonify([_coverage_to_dict(r, db) for r in reqs]), 200


@coverage_bp.route("", methods=["POST"])
def create_coverage():
    """Create a new coverage request. Requires logged-in user."""
    user_id = _require_login()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    req_date = (data.get("date") or "").strip()
    shift_type = (data.get("shift_type") or "").strip()
    note = (data.get("note") or "").strip()

    if not req_date:
        return jsonify({"error": "date is required"}), 400
    if not shift_type:
        return jsonify({"error": "shift_type is required"}), 400
    if shift_type not in ("day", "night"):
        return jsonify({"error": "shift_type must be 'day' or 'night'"}), 400

    db = current_app.config["db"]
    team_id = getattr(g, 'team_id', None)
    try:
        req_id = db.create_coverage_request(user_id, req_date, shift_type, note, team_id=team_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    cr = db.get_coverage_requests(team_id=team_id)
    created = next((r for r in cr if r.id == req_id), None)
    try:
        broadcast_coverage_event("created", req_id)
    except Exception:
        logger.exception("Failed to broadcast coverage created event for request %d", req_id)
    try:
        send_coverage_email("created", req_id, db)
    except Exception:
        logger.exception("Failed to send coverage created email for request %d", req_id)
    return jsonify(_coverage_to_dict(created, db)), 201


@coverage_bp.route("/<int:req_id>/claim", methods=["POST"])
def claim_coverage(req_id):
    """Claim a coverage request. Logged-in user becomes the claimer.

    Users cannot claim their own requests.
    """
    user_id = _require_login()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    db = current_app.config["db"]

    # Fetch the request to check ownership
    reqs = db.get_coverage_requests()
    target = next((r for r in reqs if r.id == req_id), None)
    if target is None:
        return jsonify({"error": "Coverage request not found"}), 404

    if target.requester_id == user_id:
        return jsonify({"error": "Cannot claim your own request"}), 400

    try:
        db.claim_coverage_request(req_id, user_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # Return updated request
    reqs = db.get_coverage_requests()
    updated = next((r for r in reqs if r.id == req_id), None)
    try:
        broadcast_coverage_event("claimed", req_id)
    except Exception:
        logger.exception("Failed to broadcast coverage claimed event for request %d", req_id)
    try:
        send_coverage_email("claimed", req_id, db)
    except Exception:
        logger.exception("Failed to send coverage claimed email for request %d", req_id)
    return jsonify(_coverage_to_dict(updated, db)), 200


@coverage_bp.route("/<int:req_id>/unclaim", methods=["POST"])
def unclaim_coverage(req_id):
    """Unclaim a coverage request. Only the claimer can unclaim."""
    user_id = _require_login()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    db = current_app.config["db"]

    # Fetch the request to check claimer
    reqs = db.get_coverage_requests()
    target = next((r for r in reqs if r.id == req_id), None)
    if target is None:
        return jsonify({"error": "Coverage request not found"}), 404

    if target.claimer_id != user_id:
        return jsonify({"error": "Only the claimer can unclaim"}), 403

    try:
        db.unclaim_coverage_request(req_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    reqs = db.get_coverage_requests()
    updated = next((r for r in reqs if r.id == req_id), None)
    try:
        broadcast_coverage_event("unclaimed", req_id)
    except Exception:
        logger.exception("Failed to broadcast coverage unclaimed event for request %d", req_id)
    return jsonify(_coverage_to_dict(updated, db)), 200


@coverage_bp.route("/<int:req_id>/cancel", methods=["POST"])
def cancel_coverage(req_id):
    """Cancel a coverage request. Only the requester can cancel."""
    user_id = _require_login()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    db = current_app.config["db"]

    # Fetch the request to check ownership
    reqs = db.get_coverage_requests()
    target = next((r for r in reqs if r.id == req_id), None)
    if target is None:
        return jsonify({"error": "Coverage request not found"}), 404

    if target.requester_id != user_id:
        return jsonify({"error": "Only the requester can cancel"}), 403

    try:
        db.cancel_coverage_request(req_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    reqs = db.get_coverage_requests()
    updated = next((r for r in reqs if r.id == req_id), None)
    try:
        broadcast_coverage_event("cancelled", req_id)
    except Exception:
        logger.exception("Failed to broadcast coverage cancelled event for request %d", req_id)
    return jsonify(_coverage_to_dict(updated, db)), 200


@coverage_bp.route("/my-requests", methods=["GET"])
def my_requests():
    """Get the current user's posted coverage requests."""
    user_id = _require_login()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    db = current_app.config["db"]
    reqs = db.get_coverage_requests_for_user(user_id)
    return jsonify([_coverage_to_dict(r, db) for r in reqs]), 200


@coverage_bp.route("/my-shifts", methods=["GET"])
def my_shifts():
    """Get the current user's upcoming shifts.

    Looks up the user's teammate_name, then filters the schedule
    to find shifts where that name appears in the teammates list.
    Only returns shifts from today onward.
    """
    user_id = _require_login()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    db = current_app.config["db"]
    user = db.get_user_by_id(user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404

    if not user.teammate_name:
        return jsonify([]), 200

    engine = current_app.config["engine"]
    today = date.today()
    year = today.year

    team_id = getattr(g, 'team_id', None)
    teammates = db.get_teammates(team_id=team_id)
    shift_windows = db.get_shift_windows(team_id=team_id)
    overrides = db.get_overrides(year, team_id=team_id)

    slots = engine.compute_annual_schedule(year, teammates, shift_windows, overrides)

    # Filter to upcoming slots where this user is assigned
    result = []
    for s in slots:
        if s.date >= today and user.teammate_name in s.teammates:
            day_end = shift_windows.get("day")
            night_end = shift_windows.get("night")
            result.append({
                "date": s.date.isoformat(),
                "shift_type": s.shift_type,
                "start_time": s.start_time,
                "end_time": (day_end.end_time if s.shift_type == "day" else night_end.end_time)
                if day_end and night_end else "",
                "teammates": s.teammates,
                "is_override": s.is_override,
            })

    return jsonify(result), 200
