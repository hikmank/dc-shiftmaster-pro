"""Authentication API routes for DC-ShiftMaster HTML.

Provides user registration, login, logout, and current-user endpoints.
Uses werkzeug.security for password hashing and Flask sessions for state.
"""

from flask import Blueprint, current_app, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from dc_shiftmaster_html.email_service import validate_email
from dc_shiftmaster_html.extensions import limiter

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _user_info(user):
    """Return a JSON-safe dict of user fields (excludes password_hash)."""
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "teammate_name": user.teammate_name,
        "email": user.email,
        "email_notifications_enabled": user.email_notifications_enabled,
    }


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("5/minute")
def register():
    """Create a new user account.

    Expects JSON body with: username, password, display_name,
    and optionally teammate_name.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or "").strip()
    teammate_name = (data.get("teammate_name") or "").strip()
    email = (data.get("email") or "").strip()

    if not username:
        return jsonify({"error": "username is required"}), 400
    if not password:
        return jsonify({"error": "password is required"}), 400
    if not display_name:
        return jsonify({"error": "display_name is required"}), 400

    if email and not validate_email(email):
        return jsonify({"error": "Invalid email address format"}), 400

    db = current_app.config["db"]
    password_hash = generate_password_hash(password)

    try:
        user_id = db.create_user(username, password_hash, display_name, teammate_name, email=email)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    user = db.get_user_by_id(user_id)
    session["user_id"] = user.id
    return jsonify(_user_info(user)), 201


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("10/minute")
def login():
    """Authenticate a user and create a session.

    Expects JSON body with: username, password.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username:
        return jsonify({"error": "username is required"}), 400
    if not password:
        return jsonify({"error": "password is required"}), 400

    db = current_app.config["db"]
    user = db.get_user_by_username(username)

    if user is None or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid username or password"}), 401

    session["user_id"] = user.id
    return jsonify(_user_info(user)), 200


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Clear the current session."""
    session.clear()
    return "", 204


@auth_bp.route("/me", methods=["GET"])
def me():
    """Return the currently logged-in user's info, or 401."""
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    db = current_app.config["db"]
    user = db.get_user_by_id(user_id)

    if user is None:
        session.clear()
        return jsonify({"error": "Not authenticated"}), 401

    return jsonify(_user_info(user)), 200


@auth_bp.route("/profile", methods=["PUT"])
def update_profile():
    """Update the authenticated user's email and/or notification preference."""
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    db = current_app.config["db"]
    user = db.get_user_by_id(user_id)
    if user is None:
        session.clear()
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    email = data.get("email", user.email)
    notifications_enabled = data.get("email_notifications_enabled", user.email_notifications_enabled)

    # Validate email format if a non-empty email is provided
    if email and not validate_email(email):
        return jsonify({"error": "Invalid email address format"}), 400

    # Reject enabling notifications when email is empty
    if notifications_enabled and not email:
        return jsonify({"error": "Email address is required to enable notifications"}), 400

    db.update_user_profile(user_id, email, notifications_enabled)
    user = db.get_user_by_id(user_id)
    return jsonify(_user_info(user)), 200
