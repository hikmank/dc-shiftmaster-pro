"""DatabaseManager for DC-ShiftMaster Pro.

Manages all SQLite operations against the teammates.db database,
including schema creation, default seeding, and CRUD for shift windows,
teammates, and overrides.
"""

import json
import sqlite3

from dc_shiftmaster.models import CoverageRequest, Override, ShiftWindow, Teammate, User


class DatabaseManager:
    """Manages SQLite persistence for shift windows, teammates, and overrides.

    On initialization, creates or opens the database file, ensures all
    required tables exist, and seeds default shift window values if the
    shift_windows table is empty (first run).

    Args:
        db_path: Path to the SQLite database file. Defaults to 'teammates.db'.
    """

    def __init__(self, db_path: str = "teammates.db") -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        self._migrate()
        self._seed_defaults()

    def _create_tables(self) -> None:
        """Create the database tables if they do not already exist."""
        cursor = self.conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS shift_windows (
                shift_type TEXT PRIMARY KEY,
                start_time TEXT NOT NULL,
                end_time   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS teammates (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                shift_type TEXT NOT NULL CHECK(shift_type IN ('FHD','FHN','BHD','BHN','Custom')),
                custom_start TEXT NOT NULL DEFAULT '',
                custom_days TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS overrides (
                date       TEXT NOT NULL,
                shift_type TEXT NOT NULL,
                name       TEXT NOT NULL,
                PRIMARY KEY (date, shift_type)
            );

            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name  TEXT NOT NULL,
                teammate_name TEXT NOT NULL DEFAULT '',
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS coverage_requests (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                requester_id  INTEGER NOT NULL REFERENCES users(id),
                date          TEXT NOT NULL,
                shift_type    TEXT NOT NULL CHECK(shift_type IN ('day', 'night')),
                note          TEXT NOT NULL DEFAULT '',
                status        TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'claimed', 'cancelled')),
                claimer_id    INTEGER REFERENCES users(id),
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                claimed_at    TEXT
            );
            """
        )
        self.conn.commit()

    def _migrate(self) -> None:
        """Run schema migrations for new columns."""
        cursor = self.conn.cursor()
        # Check current teammates columns
        cursor.execute("PRAGMA table_info(teammates)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add custom_start column if it doesn't exist
        if "custom_start" not in columns:
            cursor.execute(
                "ALTER TABLE teammates ADD COLUMN custom_start TEXT NOT NULL DEFAULT ''"
            )
            self.conn.commit()
            # Refresh columns list
            cursor.execute("PRAGMA table_info(teammates)")
            columns = [row[1] for row in cursor.fetchall()]

        # Add custom_days column if it doesn't exist
        if "custom_days" not in columns:
            cursor.execute(
                "ALTER TABLE teammates ADD COLUMN custom_days TEXT NOT NULL DEFAULT ''"
            )
            self.conn.commit()

        # Recreate teammates table to update CHECK constraint to allow 'Custom'
        # SQLite doesn't support ALTER TABLE to modify constraints, so we must
        # recreate the table. We check if 'Custom' is already allowed by
        # inspecting the table SQL.
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='teammates'"
        )
        row = cursor.fetchone()
        if row and "'Custom'" not in row[0]:
            # Table exists but doesn't allow 'Custom' — recreate it
            cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS teammates_new (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       TEXT NOT NULL,
                    shift_type TEXT NOT NULL CHECK(shift_type IN ('FHD','FHN','BHD','BHN','Custom')),
                    custom_start TEXT NOT NULL DEFAULT '',
                    custom_days TEXT NOT NULL DEFAULT ''
                );
                INSERT INTO teammates_new (id, name, shift_type, custom_start, custom_days)
                    SELECT id, name, shift_type, custom_start, custom_days FROM teammates;
                DROP TABLE teammates;
                ALTER TABLE teammates_new RENAME TO teammates;
                """
            )
            self.conn.commit()

        # Add email and email_notifications_enabled columns to users if they don't exist
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [row[1] for row in cursor.fetchall()]
        if "email" not in user_columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''"
            )
        if "email_notifications_enabled" not in user_columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN email_notifications_enabled INTEGER NOT NULL DEFAULT 0"
            )
        self.conn.commit()

    def _seed_defaults(self) -> None:
        """Seed default shift windows on first run (when table is empty)."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM shift_windows")
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute(
                "INSERT INTO shift_windows VALUES ('day', '06:00', '18:30')"
            )
            cursor.execute(
                "INSERT INTO shift_windows VALUES ('night', '18:00', '06:30')"
            )
            self.conn.commit()

    # -- Shift Window methods (to be implemented in task 2.2) --

    def get_shift_windows(self) -> dict[str, ShiftWindow]:
        """Return {'day': ShiftWindow, 'night': ShiftWindow}."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT shift_type, start_time, end_time FROM shift_windows")
        rows = cursor.fetchall()
        return {
            row[0]: ShiftWindow(shift_type=row[0], start_time=row[1], end_time=row[2])
            for row in rows
        }

    def update_shift_window(self, shift_type: str, start: str, end: str) -> None:
        """Persist updated start/end times for a shift type."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE shift_windows SET start_time = ?, end_time = ? WHERE shift_type = ?",
            (start, end, shift_type),
        )
        self.conn.commit()

    # -- Teammate methods (to be implemented in task 2.3) --

    def get_teammates(self) -> list[Teammate]:
        """Return all teammate records."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, shift_type, custom_start, custom_days FROM teammates")
        return [
            Teammate(
                id=row[0],
                name=row[1],
                shift_type=row[2],
                custom_start=row[3] or "",
                custom_days=json.loads(row[4]) if row[4] else [],
            )
            for row in cursor.fetchall()
        ]

    def add_teammate(self, name: str, shift_type: str, custom_start: str = "",
                     custom_days: list[str] | None = None) -> int:
        """Insert a teammate, return the new row ID.

        Args:
            name: The teammate's name.
            shift_type: One of 'FHD', 'FHN', 'BHD', 'BHN', or 'Custom'.
            custom_start: Optional HH:MM start time override.
            custom_days: List of day abbreviations for Custom shift type.

        Raises:
            ValueError: If name is empty or whitespace-only.
        """
        if not name or not name.strip():
            raise ValueError("Teammate name must not be empty or whitespace-only.")
        if custom_days is None:
            custom_days = []
        custom_days_json = json.dumps(custom_days) if custom_days else ""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO teammates (name, shift_type, custom_start, custom_days) VALUES (?, ?, ?, ?)",
            (name, shift_type, custom_start, custom_days_json),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_teammate(self, teammate_id: int, name: str, shift_type: str,
                        custom_start: str = "",
                        custom_days: list[str] | None = None) -> None:
        """Update an existing teammate's name, shift type, custom start, or custom days.

        Args:
            teammate_id: The database row ID of the teammate.
            name: The teammate's name.
            shift_type: One of 'FHD', 'FHN', 'BHD', 'BHN', or 'Custom'.
            custom_start: Optional HH:MM start time override.
            custom_days: List of day abbreviations for Custom shift type.

        Raises:
            ValueError: If name is empty or whitespace-only.
        """
        if not name or not name.strip():
            raise ValueError("Teammate name must not be empty or whitespace-only.")
        if custom_days is None:
            custom_days = []
        custom_days_json = json.dumps(custom_days) if custom_days else ""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE teammates SET name = ?, shift_type = ?, custom_start = ?, custom_days = ? WHERE id = ?",
            (name, shift_type, custom_start, custom_days_json, teammate_id),
        )
        self.conn.commit()

    def delete_teammate(self, teammate_id: int) -> None:
        """Remove a teammate record."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM teammates WHERE id = ?", (teammate_id,))
        self.conn.commit()

    # -- Override methods (to be implemented in task 2.4) --

    def get_overrides(self, year: int) -> list[Override]:
        """Return all overrides for a given year."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT date, shift_type, name FROM overrides WHERE date LIKE ?",
            (f"{year}-%",),
        )
        return [
            Override(date=row[0], shift_type=row[1], name=row[2])
            for row in cursor.fetchall()
        ]

    def set_override(self, date: str, shift_type: str, name: str) -> None:
        """Insert or update an override for a specific date+shift."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO overrides (date, shift_type, name) VALUES (?, ?, ?)",
            (date, shift_type, name),
        )
        self.conn.commit()

    def remove_override(self, date: str, shift_type: str) -> None:
        """Delete an override, reverting to computed assignment."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM overrides WHERE date = ? AND shift_type = ?",
            (date, shift_type),
        )
        self.conn.commit()

    # -- User methods --

    def create_user(self, username: str, password_hash: str, display_name: str,
                    teammate_name: str = "", email: str = "") -> int:
        """Insert a new user, return the new row ID.

        Raises:
            ValueError: If username is empty, whitespace-only, or already exists.
        """
        if not username or not username.strip():
            raise ValueError("Username must not be empty or whitespace-only.")
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, display_name, teammate_name, email) "
                "VALUES (?, ?, ?, ?, ?)",
                (username, password_hash, display_name, teammate_name, email),
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(f"Username '{username}' already exists.")

    def get_user_by_username(self, username: str) -> User | None:
        """Return the User record for the given username, or None."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, display_name, teammate_name, created_at, "
            "email, email_notifications_enabled "
            "FROM users WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return User(
            id=row[0], username=row[1], password_hash=row[2],
            display_name=row[3], teammate_name=row[4], created_at=row[5],
            email=row[6], email_notifications_enabled=bool(row[7]),
        )

    def get_user_by_id(self, user_id: int) -> User | None:
        """Return the User record for the given ID, or None."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, display_name, teammate_name, created_at, "
            "email, email_notifications_enabled "
            "FROM users WHERE id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return User(
            id=row[0], username=row[1], password_hash=row[2],
            display_name=row[3], teammate_name=row[4], created_at=row[5],
            email=row[6], email_notifications_enabled=bool(row[7]),
        )

    def get_all_users(self) -> list[User]:
        """Return all user records."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, display_name, teammate_name, created_at, "
            "email, email_notifications_enabled "
            "FROM users"
        )
        return [
            User(
                id=row[0], username=row[1], password_hash=row[2],
                display_name=row[3], teammate_name=row[4], created_at=row[5],
                email=row[6], email_notifications_enabled=bool(row[7]),
            )
            for row in cursor.fetchall()
        ]

    def get_notification_recipients(self, exclude_user_id: int = None) -> list[User]:
        """Return users with email_notifications_enabled=True and a non-empty email.

        Optionally excludes a specific user (e.g., the requester).
        """
        cursor = self.conn.cursor()
        if exclude_user_id is not None:
            cursor.execute(
                "SELECT id, username, password_hash, display_name, teammate_name, created_at, "
                "email, email_notifications_enabled "
                "FROM users WHERE email != '' AND email_notifications_enabled = 1 AND id != ?",
                (exclude_user_id,),
            )
        else:
            cursor.execute(
                "SELECT id, username, password_hash, display_name, teammate_name, created_at, "
                "email, email_notifications_enabled "
                "FROM users WHERE email != '' AND email_notifications_enabled = 1"
            )
        return [
            User(
                id=row[0], username=row[1], password_hash=row[2],
                display_name=row[3], teammate_name=row[4], created_at=row[5],
                email=row[6], email_notifications_enabled=bool(row[7]),
            )
            for row in cursor.fetchall()
        ]

    def update_user_profile(self, user_id: int, email: str,
                           email_notifications_enabled: bool) -> None:
        """Update a user's email and notification preference."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE users SET email = ?, email_notifications_enabled = ? WHERE id = ?",
            (email, int(email_notifications_enabled), user_id),
        )
        self.conn.commit()

    # -- Coverage Request methods --

    def create_coverage_request(self, requester_id: int, date: str, shift_type: str,
                                note: str = "") -> int:
        """Insert a coverage request, return the new row ID.

        Raises:
            ValueError: If a request already exists for this date/shift/requester.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM coverage_requests "
            "WHERE requester_id = ? AND date = ? AND shift_type = ? AND status != 'cancelled'",
            (requester_id, date, shift_type),
        )
        if cursor.fetchone() is not None:
            raise ValueError(
                f"Coverage request already exists for user {requester_id} "
                f"on {date} ({shift_type})."
            )
        cursor.execute(
            "INSERT INTO coverage_requests (requester_id, date, shift_type, note) "
            "VALUES (?, ?, ?, ?)",
            (requester_id, date, shift_type, note),
        )
        self.conn.commit()
        return cursor.lastrowid

    def _row_to_coverage_request(self, row: tuple) -> CoverageRequest:
        """Convert a database row tuple to a CoverageRequest dataclass."""
        return CoverageRequest(
            id=row[0],
            requester_id=row[1],
            date=row[2],
            shift_type=row[3],
            note=row[4],
            status=row[5],
            claimer_id=row[6],
            created_at=row[7],
            claimed_at=row[8],
        )

    def get_coverage_requests(self, status: str = None) -> list[CoverageRequest]:
        """Return coverage requests, optionally filtered by status."""
        cursor = self.conn.cursor()
        if status is not None:
            cursor.execute(
                "SELECT id, requester_id, date, shift_type, note, status, "
                "claimer_id, created_at, claimed_at "
                "FROM coverage_requests WHERE status = ?",
                (status,),
            )
        else:
            cursor.execute(
                "SELECT id, requester_id, date, shift_type, note, status, "
                "claimer_id, created_at, claimed_at "
                "FROM coverage_requests"
            )
        return [self._row_to_coverage_request(row) for row in cursor.fetchall()]

    def get_coverage_requests_for_user(self, user_id: int) -> list[CoverageRequest]:
        """Return all coverage requests created by a specific user."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, requester_id, date, shift_type, note, status, "
            "claimer_id, created_at, claimed_at "
            "FROM coverage_requests WHERE requester_id = ?",
            (user_id,),
        )
        return [self._row_to_coverage_request(row) for row in cursor.fetchall()]

    def claim_coverage_request(self, request_id: int, claimer_id: int) -> None:
        """Mark a coverage request as claimed by the given user.

        Creates an override via set_override() linking the claimer to the shift.

        Raises:
            ValueError: If the request is already claimed or cancelled, or not found.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, requester_id, date, shift_type, note, status, "
            "claimer_id, created_at, claimed_at "
            "FROM coverage_requests WHERE id = ?",
            (request_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Coverage request {request_id} not found.")
        req = self._row_to_coverage_request(row)
        if req.status != "open":
            raise ValueError(
                f"Coverage request {request_id} cannot be claimed "
                f"(current status: '{req.status}')."
            )

        # Look up the claimer's teammate_name
        claimer = self.get_user_by_id(claimer_id)
        if claimer is None:
            raise ValueError(f"Claimer user {claimer_id} not found.")

        cursor.execute(
            "UPDATE coverage_requests SET status = 'claimed', claimer_id = ?, "
            "claimed_at = datetime('now') WHERE id = ?",
            (claimer_id, request_id),
        )
        self.conn.commit()

        # Create override linking claimer to the shift
        self.set_override(req.date, req.shift_type, claimer.teammate_name)

    def unclaim_coverage_request(self, request_id: int) -> None:
        """Revert a claimed coverage request back to 'open'.

        Removes the associated override.

        Raises:
            ValueError: If the request is not currently claimed, or not found.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, requester_id, date, shift_type, note, status, "
            "claimer_id, created_at, claimed_at "
            "FROM coverage_requests WHERE id = ?",
            (request_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Coverage request {request_id} not found.")
        req = self._row_to_coverage_request(row)
        if req.status != "claimed":
            raise ValueError(
                f"Coverage request {request_id} is not claimed "
                f"(current status: '{req.status}')."
            )

        cursor.execute(
            "UPDATE coverage_requests SET status = 'open', claimer_id = NULL, "
            "claimed_at = NULL WHERE id = ?",
            (request_id,),
        )
        self.conn.commit()

        # Remove the override
        self.remove_override(req.date, req.shift_type)

    def cancel_coverage_request(self, request_id: int) -> None:
        """Mark a coverage request as cancelled. Removes override if claimed.

        Raises:
            ValueError: If the request is not found.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, requester_id, date, shift_type, note, status, "
            "claimer_id, created_at, claimed_at "
            "FROM coverage_requests WHERE id = ?",
            (request_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Coverage request {request_id} not found.")
        req = self._row_to_coverage_request(row)

        # If it was claimed, remove the override
        if req.status == "claimed":
            self.remove_override(req.date, req.shift_type)

        cursor.execute(
            "UPDATE coverage_requests SET status = 'cancelled', claimer_id = NULL, "
            "claimed_at = NULL WHERE id = ?",
            (request_id,),
        )
        self.conn.commit()
