"""Token management API routes for DC-ShiftMaster HTML.

Provides endpoints for creating, listing, and revoking API tokens.
All endpoints require session authentication (not bearer token auth).
"""

from flask import Blueprint, current_app, jsonify, request, session

from dc_shiftmaster_html.extensions import limiter
from dc_shiftmaster_html.token_service import TokenService

tokens_bp = Blueprint("tokens", __name__, url_prefix="/api/auth/tokens")


def _get_token_service() -> TokenService:
    """Return a TokenService instance using the app's DatabaseManager."""
    db = current_app.config["db"]
    return TokenService(db)


def _require_session_auth():
    """Check session authentication and return user_id or a 401 response tuple.

    Returns:
        int: The authenticated user_id if session is valid.
        tuple: A (response, status_code) tuple if not authenticated.
    """
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return user_id


@tokens_bp.route("", methods=["POST"])
@limiter.limit("5/minute", key_func=lambda: str(session.get("user_id", "anonymous")))
def create_token():
    """Create a new API token. Rate limited: 5 per minute per user."""
    user_id = _require_session_auth()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    label = data.get("label")
    expires_in_days = data.get("expires_in_days")

    if label is None:
        return jsonify({"error": "Label must be between 1 and 128 non-whitespace-only characters"}), 400

    service = _get_token_service()

    try:
        result = service.create_token(
            user_id=user_id,
            label=label,
            expires_in_days=expires_in_days,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(result), 201


@tokens_bp.route("", methods=["GET"])
def list_tokens():
    """List all tokens for the authenticated user."""
    user_id = _require_session_auth()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    service = _get_token_service()
    tokens = service.list_tokens(user_id)

    return jsonify({
        "data": tokens,
        "meta": {"total": len(tokens)},
    }), 200


@tokens_bp.route("/<int:token_id>", methods=["DELETE"])
def revoke_token(token_id: int):
    """Revoke a specific token by ID."""
    user_id = _require_session_auth()
    if user_id is None:
        return jsonify({"error": "Not authenticated"}), 401

    service = _get_token_service()

    try:
        service.revoke_token(user_id=user_id, token_id=token_id)
    except ValueError as exc:
        error_msg = str(exc)
        if "not found" in error_msg.lower():
            return jsonify({"error": error_msg}), 404
        return jsonify({"error": error_msg}), 400
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403

    return "", 204
