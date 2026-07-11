"""Token Service for API token authentication.

Handles token generation, validation, and lifecycle management for
long-lived API tokens used by automated processes to authenticate
against the REST API.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster.models import User


class TokenService:
    """Handles token generation, validation, and lifecycle management."""

    MAX_ACTIVE_TOKENS = 10

    def __init__(self, db: DatabaseManager):
        self.db = db

    @staticmethod
    def generate_token() -> str:
        """Generate a cryptographically random token (32 bytes, hex-encoded = 64 chars)."""
        return secrets.token_hex(32)

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Compute SHA-256 hex digest of raw token for storage/lookup."""
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def create_token(
        self, user_id: int, label: str, expires_in_days: int | None = None
    ) -> dict:
        """Generate a new API token for the user.

        Returns dict with: id, token (plaintext, shown once), label, created_at, expires_at
        Raises ValueError for invalid label, limit reached, etc.
        """
        # Validate label
        if not label or not label.strip():
            raise ValueError(
                "Label must be between 1 and 128 non-whitespace-only characters"
            )
        if len(label) > 128:
            raise ValueError(
                "Label must be between 1 and 128 non-whitespace-only characters"
            )

        # Validate expires_in_days
        if expires_in_days is not None:
            if not isinstance(expires_in_days, int) or isinstance(expires_in_days, bool):
                raise ValueError(
                    "Expiration must be an integer between 1 and 365 days"
                )
            if expires_in_days < 1 or expires_in_days > 365:
                raise ValueError(
                    "Expiration must be an integer between 1 and 365 days"
                )

        # Check active token count limit
        active_count = self.count_active_tokens(user_id)
        if active_count >= self.MAX_ACTIVE_TOKENS:
            raise ValueError("Maximum of 10 active tokens reached")

        # Generate token and compute hash
        raw_token = self.generate_token()
        token_hash = self.hash_token(raw_token)

        # Compute expiration timestamp
        now_utc = datetime.now(timezone.utc)
        expires_at = None
        if expires_in_days is not None:
            expires_at = (now_utc + timedelta(days=expires_in_days)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        # Store in database
        token_id = self.db.create_api_token(
            user_id=user_id,
            token_hash=token_hash,
            label=label,
            expires_at=expires_at,
        )

        # Retrieve the created record to get the created_at timestamp
        token_record = self.db.get_api_token_by_hash(token_hash)

        return {
            "id": token_id,
            "token": raw_token,
            "label": label,
            "created_at": token_record["created_at"] if token_record else now_utc.strftime("%Y-%m-%d %H:%M:%S"),
            "expires_at": expires_at,
        }

    def validate_token(self, raw_token: str) -> User | None:
        """Validate a bearer token and return the owning User, or None.

        Uses timing-safe hash comparison. Updates last_used_at on success.
        Returns None for invalid, expired, or revoked tokens.
        """
        user, _reason = self.validate_token_with_reason(raw_token)
        return user

    def validate_token_with_reason(self, raw_token: str) -> tuple[User | None, str | None]:
        """Validate a bearer token and return (User, None) on success or (None, reason) on failure.

        Uses timing-safe hash comparison. Updates last_used_at on success.
        Returns a tuple where:
          - On success: (User, None)
          - On failure: (None, error_reason_string)

        Possible error reasons:
          - "Invalid API token" — token hash not found in DB
          - "Token has been revoked" — token exists but is revoked
          - "Token has expired" — token exists but has passed its expiry
        """
        # Hash the incoming token
        computed_hash = self.hash_token(raw_token)

        # Look up token record by hash
        token_record = self.db.get_api_token_by_hash(computed_hash)
        if token_record is None:
            return None, "Invalid API token"

        # Timing-safe comparison of the computed hash with stored hash
        if not hmac.compare_digest(computed_hash, token_record["token_hash"]):
            return None, "Invalid API token"

        # Check if revoked
        if token_record["revoked"]:
            return None, "Token has been revoked"

        # Check if expired
        if token_record["expires_at"] is not None:
            expires_at = datetime.strptime(
                token_record["expires_at"], "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= expires_at:
                return None, "Token has expired"

        # Update last_used_at on successful validation
        self.db.update_token_last_used(token_record["id"])

        # Return the owning user
        user = self.db.get_user_by_id(token_record["user_id"])
        if user is None:
            return None, "Invalid API token"
        return user, None

    def list_tokens(self, user_id: int) -> list[dict]:
        """Return metadata for all tokens owned by the user (no secrets).

        Sorted by created_at descending, capped at 100 records.
        """
        tokens = self.db.get_api_tokens_for_user(user_id)
        # Exclude token_hash from the response
        result = []
        for token in tokens:
            result.append({
                "id": token["id"],
                "label": token["label"],
                "created_at": token["created_at"],
                "expires_at": token["expires_at"],
                "revoked": bool(token["revoked"]),
                "last_used_at": token["last_used_at"],
            })
        return result

    def revoke_token(self, user_id: int, token_id: int) -> None:
        """Mark a token as revoked.

        Raises ValueError if token not found.
        Raises PermissionError if user doesn't own the token.
        """
        # Look up the token to verify it exists and check ownership
        tokens = self.db.get_api_tokens_for_user(user_id)
        # We need to find the token by ID across all users, so query by hash won't work.
        # Instead, check all tokens for this user first, then check across all.
        # Actually, we need to look up the specific token to check ownership.
        # The DB doesn't have a get_by_id method, so we look through the user's tokens.

        # First, check if the token exists at all by looking at the user's tokens
        user_token = None
        for t in tokens:
            if t["id"] == token_id:
                user_token = t
                break

        if user_token is not None:
            # User owns this token, revoke it
            self.db.revoke_api_token(token_id)
            return

        # Token not found in user's list - could be non-existent or owned by another user
        # We need to check if the token exists at all
        # Use a direct DB query to check existence
        cursor = self.db.conn.cursor()
        cursor.execute(
            "SELECT id, user_id FROM api_tokens WHERE id = ?", (token_id,)
        )
        row = cursor.fetchone()

        if row is None:
            raise ValueError("Token not found")

        # Token exists but belongs to another user
        if row[1] != user_id:
            raise PermissionError("You do not own this token")

        # This shouldn't be reached, but just in case
        raise ValueError("Token not found")

    def count_active_tokens(self, user_id: int) -> int:
        """Return the number of active (non-revoked, non-expired) tokens for user."""
        return self.db.count_active_api_tokens(user_id)
