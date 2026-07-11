"""DatabaseManager for DC-ShiftMaster Pro.

Manages all SQLite operations against the teammates.db database,
including schema creation, default seeding, and CRUD for shift windows,
teammates, overrides, and API tokens.
"""

import json
import re
import sqlite3
from datetime import datetime, timezone

from dc_shiftmaster.models import CoverageRequest, Override, ShiftWindow, Teammate, User


class TeamMembershipError(Exception):
    """Raised when a team membership operation fails with a structured error code.

    Attributes:
        code: Machine-readable error code (e.g., 'ALREADY_MEMBER', 'PERMISSION_DENIED').
        message: Human-readable error description.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class CrossTeamAccessError(Exception):
    """Raised when a query attempts to access data belonging to a different team.

    Attributes:
        table: The table where the access violation occurred.
        resource_id: The ID of the resource being accessed.
        expected_team_id: The team_id the caller is operating under.
        actual_team_id: The team_id the resource actually belongs to.
    """

    def __init__(self, table: str, resource_id: int,
                 expected_team_id: int, actual_team_id: int | None) -> None:
        self.table = table
        self.resource_id = resource_id
        self.expected_team_id = expected_team_id
        self.actual_team_id = actual_team_id
        super().__init__(
            f"Cross-team access denied: {table} row {resource_id} belongs to "
            f"team {actual_team_id}, not team {expected_team_id}"
        )


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
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()
        self._migrate()
        self._seed_defaults()

    def _create_tables(self) -> None:
        """Create the database tables if they do not already exist."""
        cursor = self.conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS team_profiles (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                site_code    TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS team_members (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id     INTEGER NOT NULL REFERENCES team_profiles(id) ON DELETE CASCADE,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                role        TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('admin', 'member')),
                joined_at   TEXT NOT NULL DEFAULT (datetime('now')),
                selected_at TEXT,
                UNIQUE(team_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS migrations_applied (
                migration_name TEXT PRIMARY KEY,
                applied_at     TEXT NOT NULL DEFAULT (datetime('now'))
            );

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

            CREATE TABLE IF NOT EXISTS api_tokens (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash    TEXT NOT NULL UNIQUE,
                label         TEXT NOT NULL CHECK(length(label) <= 128),
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at    TEXT,
                revoked       INTEGER NOT NULL DEFAULT 0,
                last_used_at  TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash);
            CREATE INDEX IF NOT EXISTS idx_api_tokens_user_id ON api_tokens(user_id);
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

        # --- Multi-team migration: add team_id FK to existing tables ---
        # Add team_id column to teammates if it doesn't exist
        cursor.execute("PRAGMA table_info(teammates)")
        teammates_cols = [row[1] for row in cursor.fetchall()]
        if "team_id" not in teammates_cols:
            cursor.execute(
                "ALTER TABLE teammates ADD COLUMN team_id INTEGER REFERENCES team_profiles(id) ON DELETE CASCADE"
            )
            self.conn.commit()

        # Add team_id column to overrides if it doesn't exist
        cursor.execute("PRAGMA table_info(overrides)")
        overrides_cols = [row[1] for row in cursor.fetchall()]
        if "team_id" not in overrides_cols:
            cursor.execute(
                "ALTER TABLE overrides ADD COLUMN team_id INTEGER REFERENCES team_profiles(id) ON DELETE CASCADE"
            )
            self.conn.commit()

        # Add team_id column to coverage_requests if it doesn't exist
        cursor.execute("PRAGMA table_info(coverage_requests)")
        coverage_cols = [row[1] for row in cursor.fetchall()]
        if "team_id" not in coverage_cols:
            cursor.execute(
                "ALTER TABLE coverage_requests ADD COLUMN team_id INTEGER REFERENCES team_profiles(id) ON DELETE CASCADE"
            )
            self.conn.commit()

        # Add team_id column to shift_windows if it doesn't exist
        cursor.execute("PRAGMA table_info(shift_windows)")
        shift_cols = [row[1] for row in cursor.fetchall()]
        if "team_id" not in shift_cols:
            cursor.execute(
                "ALTER TABLE shift_windows ADD COLUMN team_id INTEGER REFERENCES team_profiles(id) ON DELETE CASCADE"
            )
            self.conn.commit()

        # Migrate shift_windows to composite PK (shift_type, team_id) for multi-team support
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='shift_windows'"
        )
        sw_row = cursor.fetchone()
        if sw_row and "PRIMARY KEY (shift_type, team_id)" not in sw_row[0]:
            cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS shift_windows_new (
                    shift_type TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time   TEXT NOT NULL,
                    team_id    INTEGER REFERENCES team_profiles(id) ON DELETE CASCADE,
                    PRIMARY KEY (shift_type, team_id)
                );
                INSERT OR IGNORE INTO shift_windows_new (shift_type, start_time, end_time, team_id)
                    SELECT shift_type, start_time, end_time, team_id FROM shift_windows;
                DROP TABLE shift_windows;
                ALTER TABLE shift_windows_new RENAME TO shift_windows;
                """
            )
            self.conn.commit()

    def _seed_defaults(self) -> None:
        """Seed default shift windows on first run (when table is empty)."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM shift_windows")
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute(
                "INSERT INTO shift_windows (shift_type, start_time, end_time) VALUES ('day', '06:00', '18:30')"
            )
            cursor.execute(
                "INSERT INTO shift_windows (shift_type, start_time, end_time) VALUES ('night', '18:00', '06:30')"
            )
            self.conn.commit()

    # -- Resource ownership validation --

    def validate_resource_ownership(self, table: str, resource_id: int, team_id: int) -> None:
        """Verify that a resource belongs to the specified team.

        For any row-level operation by ID, checks that the row's team_id matches
        the expected team_id. Raises CrossTeamAccessError if mismatched (active
        rejection per Req 3.1).

        Args:
            table: The database table name (e.g., 'teammates', 'overrides', 'coverage_requests').
            resource_id: The row ID to validate.
            team_id: The expected team_id the resource should belong to.

        Raises:
            CrossTeamAccessError: If the resource belongs to a different team.
            ValueError: If the resource does not exist.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT team_id FROM {table} WHERE id = ?",
            (resource_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Resource {resource_id} not found in {table}.")
        actual_team_id = row[0]
        if actual_team_id != team_id:
            raise CrossTeamAccessError(table, resource_id, team_id, actual_team_id)

    # -- Shift Window methods --

    def get_shift_windows(self, team_id: int = None) -> dict[str, ShiftWindow]:
        """Return {'day': ShiftWindow, 'night': ShiftWindow}.

        When team_id is provided, scopes the query to that team and implements
        lazy shift window initialization (retry mechanism per Req 1.4).
        When team_id is None, returns all shift windows (legacy behavior).
        """
        cursor = self.conn.cursor()
        if team_id is not None:
            cursor.execute(
                "SELECT shift_type, start_time, end_time FROM shift_windows WHERE team_id = ?",
                (team_id,),
            )
            rows = cursor.fetchall()

            # Lazy retry: if no shift windows exist for this team, create defaults
            if not rows:
                try:
                    cursor.execute(
                        "INSERT INTO shift_windows (shift_type, start_time, end_time, team_id) "
                        "VALUES ('day', '06:00', '18:30', ?)",
                        (team_id,),
                    )
                    cursor.execute(
                        "INSERT INTO shift_windows (shift_type, start_time, end_time, team_id) "
                        "VALUES ('night', '18:00', '06:30', ?)",
                        (team_id,),
                    )
                    self.conn.commit()
                    cursor.execute(
                        "SELECT shift_type, start_time, end_time FROM shift_windows WHERE team_id = ?",
                        (team_id,),
                    )
                    rows = cursor.fetchall()
                except Exception:
                    return {}
        else:
            cursor.execute("SELECT shift_type, start_time, end_time FROM shift_windows")
            rows = cursor.fetchall()

        return {
            row[0]: ShiftWindow(shift_type=row[0], start_time=row[1], end_time=row[2])
            for row in rows
        }

    def update_shift_window(self, shift_type: str, start: str, end: str,
                           team_id: int = None) -> None:
        """Persist updated start/end times for a shift type.

        When team_id is provided, scopes the update to that team.
        When team_id is None, updates global shift windows (legacy behavior).
        """
        cursor = self.conn.cursor()
        if team_id is not None:
            cursor.execute(
                "UPDATE shift_windows SET start_time = ?, end_time = ? "
                "WHERE shift_type = ? AND team_id = ?",
                (start, end, shift_type, team_id),
            )
        else:
            cursor.execute(
                "UPDATE shift_windows SET start_time = ?, end_time = ? WHERE shift_type = ?",
                (start, end, shift_type),
            )
        self.conn.commit()

    # -- Teammate methods --

    def get_teammates(self, team_id: int = None) -> list[Teammate]:
        """Return all teammate records.

        When team_id is provided, scopes the query to that team.
        When team_id is None, returns all teammates (legacy behavior).
        """
        cursor = self.conn.cursor()
        if team_id is not None:
            cursor.execute(
                "SELECT id, name, shift_type, custom_start, custom_days "
                "FROM teammates WHERE team_id = ?",
                (team_id,),
            )
        else:
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
                     custom_days: list[str] | None = None,
                     team_id: int = None) -> int:
        """Insert a teammate, return the new row ID.

        Args:
            name: The teammate's name.
            shift_type: One of 'FHD', 'FHN', 'BHD', 'BHN', or 'Custom'.
            custom_start: Optional HH:MM start time override.
            custom_days: List of day abbreviations for Custom shift type.
            team_id: The team to add the teammate to (None for legacy behavior).

        Raises:
            ValueError: If name is empty or whitespace-only.
        """
        if not name or not name.strip():
            raise ValueError("Teammate name must not be empty or whitespace-only.")
        if custom_days is None:
            custom_days = []
        custom_days_json = json.dumps(custom_days) if custom_days else ""
        cursor = self.conn.cursor()
        if team_id is not None:
            cursor.execute(
                "INSERT INTO teammates (name, shift_type, custom_start, custom_days, team_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, shift_type, custom_start, custom_days_json, team_id),
            )
        else:
            cursor.execute(
                "INSERT INTO teammates (name, shift_type, custom_start, custom_days) VALUES (?, ?, ?, ?)",
                (name, shift_type, custom_start, custom_days_json),
            )
        self.conn.commit()
        return cursor.lastrowid

    def update_teammate(self, teammate_id: int, name: str, shift_type: str,
                        custom_start: str = "",
                        custom_days: list[str] | None = None,
                        team_id: int = None) -> None:
        """Update an existing teammate's name, shift type, custom start, or custom days.

        When team_id is provided, validates resource ownership before updating.

        Args:
            teammate_id: The database row ID of the teammate.
            name: The teammate's name.
            shift_type: One of 'FHD', 'FHN', 'BHD', 'BHN', or 'Custom'.
            custom_start: Optional HH:MM start time override.
            custom_days: List of day abbreviations for Custom shift type.
            team_id: The team context for ownership validation (None for legacy behavior).

        Raises:
            ValueError: If name is empty or whitespace-only.
            CrossTeamAccessError: If the teammate belongs to a different team.
        """
        if not name or not name.strip():
            raise ValueError("Teammate name must not be empty or whitespace-only.")
        if team_id is not None:
            self.validate_resource_ownership("teammates", teammate_id, team_id)
        if custom_days is None:
            custom_days = []
        custom_days_json = json.dumps(custom_days) if custom_days else ""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE teammates SET name = ?, shift_type = ?, custom_start = ?, custom_days = ? WHERE id = ?",
            (name, shift_type, custom_start, custom_days_json, teammate_id),
        )
        self.conn.commit()

    def delete_teammate(self, teammate_id: int, team_id: int = None) -> None:
        """Remove a teammate record.

        When team_id is provided, validates resource ownership before deleting.

        Args:
            teammate_id: The database row ID of the teammate.
            team_id: The team context for ownership validation (None for legacy behavior).

        Raises:
            CrossTeamAccessError: If the teammate belongs to a different team.
        """
        if team_id is not None:
            self.validate_resource_ownership("teammates", teammate_id, team_id)
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM teammates WHERE id = ?", (teammate_id,))
        self.conn.commit()

    def clear_all_teammates(self, team_id: int = None) -> int:
        """Delete all teammate records, optionally scoped to a team.

        Args:
            team_id: If provided, only deletes teammates for this team.
                     If None, deletes ALL teammate records (legacy behavior).

        Returns:
            The number of rows deleted.

        Raises:
            Exception: If the database operation fails (transaction is rolled back).
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("BEGIN")
            if team_id is not None:
                cursor.execute(
                    "DELETE FROM teammates WHERE team_id = ?", (team_id,)
                )
            else:
                cursor.execute("DELETE FROM teammates")
            deleted_count = cursor.rowcount
            cursor.execute("COMMIT")
            return deleted_count
        except Exception:
            cursor.execute("ROLLBACK")
            raise

    # -- Override methods --

    def get_overrides(self, year: int, team_id: int = None) -> list[Override]:
        """Return all overrides for a given year.

        When team_id is provided, scopes the query to that team.
        When team_id is None, returns all overrides for the year (legacy behavior).
        """
        cursor = self.conn.cursor()
        if team_id is not None:
            cursor.execute(
                "SELECT date, shift_type, name FROM overrides "
                "WHERE date LIKE ? AND team_id = ?",
                (f"{year}-%", team_id),
            )
        else:
            cursor.execute(
                "SELECT date, shift_type, name FROM overrides WHERE date LIKE ?",
                (f"{year}-%",),
            )
        return [
            Override(date=row[0], shift_type=row[1], name=row[2])
            for row in cursor.fetchall()
        ]

    def set_override(self, date: str, shift_type: str, name: str,
                     team_id: int = None) -> None:
        """Insert or update an override for a specific date+shift.

        When team_id is provided, includes team_id in the insert/replace.
        When team_id is None, uses legacy behavior without team scoping.
        """
        cursor = self.conn.cursor()
        if team_id is not None:
            cursor.execute(
                "INSERT OR REPLACE INTO overrides (date, shift_type, name, team_id) "
                "VALUES (?, ?, ?, ?)",
                (date, shift_type, name, team_id),
            )
        else:
            cursor.execute(
                "INSERT OR REPLACE INTO overrides (date, shift_type, name) VALUES (?, ?, ?)",
                (date, shift_type, name),
            )
        self.conn.commit()

    def remove_override(self, date: str, shift_type: str, team_id: int = None) -> None:
        """Delete an override, reverting to computed assignment.

        When team_id is provided, scopes the delete to that team.
        When team_id is None, uses legacy behavior without team scoping.
        """
        cursor = self.conn.cursor()
        if team_id is not None:
            cursor.execute(
                "DELETE FROM overrides WHERE date = ? AND shift_type = ? AND team_id = ?",
                (date, shift_type, team_id),
            )
        else:
            cursor.execute(
                "DELETE FROM overrides WHERE date = ? AND shift_type = ?",
                (date, shift_type),
            )
        self.conn.commit()

    # -- Bulk Override methods --

    def count_overrides_in_range(self, start_date: str, end_date: str,
                                  team_id: int = None) -> int:
        """Count overrides between start_date and end_date (inclusive).

        Args:
            start_date: The start date in YYYY-MM-DD format (inclusive).
            end_date: The end date in YYYY-MM-DD format (inclusive).
            team_id: Scope the count to a specific team. None for legacy behavior.

        Returns:
            The number of overrides within the date range for the specified team.
        """
        cursor = self.conn.cursor()
        if team_id is not None:
            cursor.execute(
                "SELECT COUNT(*) FROM overrides "
                "WHERE date >= ? AND date <= ? AND team_id = ?",
                (start_date, end_date, team_id),
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM overrides WHERE date >= ? AND date <= ?",
                (start_date, end_date),
            )
        return cursor.fetchone()[0]

    def bulk_delete_overrides_by_range(self, start_date: str, end_date: str,
                                       team_id: int = None) -> int:
        """Delete all overrides in [start_date, end_date] within a transaction.

        Args:
            start_date: The start date in YYYY-MM-DD format (inclusive).
            end_date: The end date in YYYY-MM-DD format (inclusive).
            team_id: Scope the deletion to a specific team. None for legacy behavior.

        Returns:
            The number of overrides deleted.

        Raises:
            Exception: If the database operation fails (transaction is rolled back).
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("BEGIN")
            if team_id is not None:
                cursor.execute(
                    "DELETE FROM overrides "
                    "WHERE date >= ? AND date <= ? AND team_id = ?",
                    (start_date, end_date, team_id),
                )
            else:
                cursor.execute(
                    "DELETE FROM overrides WHERE date >= ? AND date <= ?",
                    (start_date, end_date),
                )
            deleted_count = cursor.rowcount
            cursor.execute("COMMIT")
            return deleted_count
        except Exception:
            cursor.execute("ROLLBACK")
            raise

    def bulk_delete_overrides_by_keys(self, keys: list[tuple[str, str]],
                                      team_id: int = None) -> int:
        """Delete overrides matching specific (date, shift_type) pairs within a transaction.

        Args:
            keys: List of (date, shift_type) tuples identifying overrides to delete.
            team_id: Scope the deletion to a specific team. None for legacy behavior.

        Returns:
            The number of overrides deleted.

        Raises:
            Exception: If the database operation fails (transaction is rolled back).
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("BEGIN")
            deleted_count = 0
            for date, shift_type in keys:
                if team_id is not None:
                    cursor.execute(
                        "DELETE FROM overrides "
                        "WHERE date = ? AND shift_type = ? AND team_id = ?",
                        (date, shift_type, team_id),
                    )
                else:
                    cursor.execute(
                        "DELETE FROM overrides WHERE date = ? AND shift_type = ?",
                        (date, shift_type),
                    )
                deleted_count += cursor.rowcount
            cursor.execute("COMMIT")
            return deleted_count
        except Exception:
            cursor.execute("ROLLBACK")
            raise

    def bulk_delete_overrides_by_year(self, year: int, team_id: int = None) -> int:
        """Delete all overrides for a given year within a transaction.

        Args:
            year: The 4-digit year to clear overrides for.
            team_id: Scope the deletion to a specific team. None for legacy behavior.

        Returns:
            The number of overrides deleted.

        Raises:
            Exception: If the database operation fails (transaction is rolled back).
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("BEGIN")
            if team_id is not None:
                cursor.execute(
                    "DELETE FROM overrides WHERE date LIKE ? AND team_id = ?",
                    (f"{year}-%", team_id),
                )
            else:
                cursor.execute(
                    "DELETE FROM overrides WHERE date LIKE ?",
                    (f"{year}-%",),
                )
            deleted_count = cursor.rowcount
            cursor.execute("COMMIT")
            return deleted_count
        except Exception:
            cursor.execute("ROLLBACK")
            raise

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
                                note: str = "", team_id: int = None) -> int:
        """Insert a coverage request, return the new row ID.

        When team_id is provided, includes team_id in the insert and scopes
        the duplicate check to that team.

        Raises:
            ValueError: If a request already exists for this date/shift/requester.
        """
        cursor = self.conn.cursor()
        if team_id is not None:
            cursor.execute(
                "SELECT id FROM coverage_requests "
                "WHERE requester_id = ? AND date = ? AND shift_type = ? "
                "AND status != 'cancelled' AND team_id = ?",
                (requester_id, date, shift_type, team_id),
            )
        else:
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
        if team_id is not None:
            cursor.execute(
                "INSERT INTO coverage_requests (requester_id, date, shift_type, note, team_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (requester_id, date, shift_type, note, team_id),
            )
        else:
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

    def get_coverage_requests(self, status: str = None,
                              team_id: int = None) -> list[CoverageRequest]:
        """Return coverage requests, optionally filtered by status.

        When team_id is provided, scopes the query to that team.
        When team_id is None, returns all coverage requests (legacy behavior).
        """
        cursor = self.conn.cursor()
        if team_id is not None and status is not None:
            cursor.execute(
                "SELECT id, requester_id, date, shift_type, note, status, "
                "claimer_id, created_at, claimed_at "
                "FROM coverage_requests WHERE status = ? AND team_id = ?",
                (status, team_id),
            )
        elif team_id is not None:
            cursor.execute(
                "SELECT id, requester_id, date, shift_type, note, status, "
                "claimer_id, created_at, claimed_at "
                "FROM coverage_requests WHERE team_id = ?",
                (team_id,),
            )
        elif status is not None:
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

    # -- API Token methods --

    def create_api_token(self, user_id: int, token_hash: str, label: str,
                         expires_at: str | None = None) -> int:
        """Insert a token record, return the new row ID.

        Args:
            user_id: The owning user's ID.
            token_hash: SHA-256 hex digest of the plaintext token.
            label: Human-readable label for the token (1-128 chars).
            expires_at: Optional ISO-format expiry timestamp, or None for non-expiring.

        Returns:
            The auto-incremented row ID of the new token record.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO api_tokens (user_id, token_hash, label, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, token_hash, label, expires_at),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_api_token_by_hash(self, token_hash: str) -> dict | None:
        """Look up a token record by its hash.

        Args:
            token_hash: The SHA-256 hex digest to look up.

        Returns:
            A dict with column names as keys, or None if not found.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, user_id, token_hash, label, created_at, expires_at, "
            "revoked, last_used_at FROM api_tokens WHERE token_hash = ?",
            (token_hash,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "token_hash": row[2],
            "label": row[3],
            "created_at": row[4],
            "expires_at": row[5],
            "revoked": row[6],
            "last_used_at": row[7],
        }

    def get_api_tokens_for_user(self, user_id: int) -> list[dict]:
        """Return all token records for a user, sorted by created_at DESC, max 100.

        Args:
            user_id: The owning user's ID.

        Returns:
            List of dicts with column names as keys, newest first, capped at 100.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, user_id, token_hash, label, created_at, expires_at, "
            "revoked, last_used_at FROM api_tokens "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
            (user_id,),
        )
        return [
            {
                "id": row[0],
                "user_id": row[1],
                "token_hash": row[2],
                "label": row[3],
                "created_at": row[4],
                "expires_at": row[5],
                "revoked": row[6],
                "last_used_at": row[7],
            }
            for row in cursor.fetchall()
        ]

    def revoke_api_token(self, token_id: int) -> None:
        """Set revoked=1 on the given token.

        Args:
            token_id: The token record's ID.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE api_tokens SET revoked = 1 WHERE id = ?",
            (token_id,),
        )
        self.conn.commit()

    def update_token_last_used(self, token_id: int) -> None:
        """Update last_used_at to current UTC time.

        Args:
            token_id: The token record's ID.
        """
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE api_tokens SET last_used_at = ? WHERE id = ?",
            (now_utc, token_id),
        )
        self.conn.commit()

    def count_active_api_tokens(self, user_id: int) -> int:
        """Count tokens where revoked=0 AND (expires_at IS NULL OR expires_at > now).

        Args:
            user_id: The owning user's ID.

        Returns:
            The number of active (non-revoked, non-expired) tokens for the user.
        """
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM api_tokens "
            "WHERE user_id = ? AND revoked = 0 "
            "AND (expires_at IS NULL OR expires_at > ?)",
            (user_id, now_utc),
        )
        return cursor.fetchone()[0]

    # -- Team Membership methods --

    def join_team(self, user_id: int, team_id: int) -> dict:
        """Add a user as a member of a team.

        Creates a team_members record with role='member' and joined_at timestamp.

        Args:
            user_id: The ID of the user joining the team.
            team_id: The ID of the team to join.

        Returns:
            A dict with the membership details (user_id, team_id, role, joined_at).

        Raises:
            TeamMembershipError: With code 'ALREADY_MEMBER' if the user is
                already a member of the team.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO team_members (team_id, user_id, role, joined_at) "
                "VALUES (?, ?, 'member', datetime('now'))",
                (team_id, user_id),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise TeamMembershipError(
                "ALREADY_MEMBER",
                "You are already a member of this team",
            )
        # Fetch the inserted record to return joined_at
        cursor.execute(
            "SELECT role, joined_at FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, user_id),
        )
        row = cursor.fetchone()
        return {
            "user_id": user_id,
            "team_id": team_id,
            "role": row[0],
            "joined_at": row[1],
        }

    def remove_member(self, team_id: int, user_id: int, requesting_user_id: int) -> None:
        """Remove a user from a team. Only admins can perform this action.

        Args:
            team_id: The team to remove the member from.
            user_id: The user to be removed.
            requesting_user_id: The user requesting the removal (must be admin).

        Raises:
            TeamMembershipError: With code 'PERMISSION_DENIED' if requesting user
                is not an admin.
            TeamMembershipError: With code 'NOT_A_MEMBER' if target user is not
                a member of the team.
            TeamMembershipError: With code 'SOLE_ADMIN' if the requesting user
                is trying to remove themselves and they are the only admin.
        """
        # 1. Check requesting user has admin role
        requester_role = self.get_user_role(requesting_user_id, team_id)
        if requester_role != "admin":
            raise TeamMembershipError(
                "PERMISSION_DENIED",
                "Only team admins can perform this action",
            )

        # 2. Check target user is actually a member
        if not self.is_team_member(user_id, team_id):
            raise TeamMembershipError(
                "NOT_A_MEMBER",
                "User is not a member of this team",
            )

        # 3. If removing self and sole admin, reject
        if user_id == requesting_user_id:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM team_members WHERE team_id = ? AND role = 'admin'",
                (team_id,),
            )
            admin_count = cursor.fetchone()[0]
            if admin_count <= 1:
                raise TeamMembershipError(
                    "SOLE_ADMIN",
                    "Cannot remove the only admin. Promote another member first.",
                )

        # 4. Delete the membership
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, user_id),
        )
        self.conn.commit()

    def is_team_member(self, user_id: int, team_id: int) -> bool:
        """Check if a user is a member of a team.

        Args:
            user_id: The user to check.
            team_id: The team to check membership in.

        Returns:
            True if the user is a member of the team, False otherwise.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, user_id),
        )
        return cursor.fetchone() is not None

    def get_team_members(self, team_id: int) -> list[dict]:
        """List all members of a team with their roles and user details.

        Args:
            team_id: The team to list members for.

        Returns:
            List of dicts with user_id, username, display_name, role, joined_at.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT tm.user_id, u.username, u.display_name, tm.role, tm.joined_at "
            "FROM team_members tm "
            "JOIN users u ON tm.user_id = u.id "
            "WHERE tm.team_id = ?",
            (team_id,),
        )
        return [
            {
                "user_id": row[0],
                "username": row[1],
                "display_name": row[2],
                "role": row[3],
                "joined_at": row[4],
            }
            for row in cursor.fetchall()
        ]

    def get_user_role(self, user_id: int, team_id: int) -> str | None:
        """Get the role of a user in a team.

        Args:
            user_id: The user to check.
            team_id: The team to check role in.

        Returns:
            'admin' or 'member' if the user is in the team, None otherwise.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT role FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, user_id),
        )
        row = cursor.fetchone()
        return row[0] if row is not None else None

    # -- Team Profile CRUD methods --

    SITE_CODE_PATTERN = r"^[A-Z]{3}[0-9]{3}$"

    def _validate_site_code(self, site_code: str) -> None:
        """Validate that site_code matches the required pattern.

        Args:
            site_code: The site code to validate.

        Raises:
            ValueError: If the site code does not match ^[A-Z]{3}[0-9]{3}$.
        """
        if not site_code:
            raise ValueError(
                "Site code must not be empty. "
                "Expected format: 3 uppercase letters followed by 3 digits (e.g., ATL069)."
            )
        if not re.match(self.SITE_CODE_PATTERN, site_code):
            raise ValueError(
                f"Invalid site code '{site_code}'. "
                "Site code must be exactly 3 uppercase letters followed by 3 digits "
                "(e.g., ATL069, CMH078)."
            )

    def create_team(self, site_code: str, display_name: str,
                    creator_user_id: int) -> dict:
        """Create a new team profile with admin membership and default shift windows.

        Validates the site code format, creates the team_profiles row, adds the
        creator as an admin member, and attempts to initialize default shift windows.
        If shift window creation fails, the team is still created with a pending
        shift_init_status (resilient initialization per Req 1.4).

        Args:
            site_code: The team's site code (must match ^[A-Z]{3}[0-9]{3}$).
            display_name: Human-readable team name.
            creator_user_id: The user ID of the team creator (becomes admin).

        Returns:
            A dict with keys: id, site_code, display_name, created_at, role,
            shift_init_status ('ok' or 'pending').

        Raises:
            ValueError: If site_code is invalid.
            sqlite3.IntegrityError: If site_code already exists.
        """
        self._validate_site_code(site_code)

        cursor = self.conn.cursor()

        # Create team profile
        cursor.execute(
            "INSERT INTO team_profiles (site_code, display_name) VALUES (?, ?)",
            (site_code, display_name),
        )
        team_id = cursor.lastrowid

        # Add creator as admin member
        cursor.execute(
            "INSERT INTO team_members (team_id, user_id, role) VALUES (?, ?, 'admin')",
            (team_id, creator_user_id),
        )
        self.conn.commit()

        # Attempt to initialize default shift windows (resilient)
        shift_init_status = "ok"
        try:
            cursor.execute(
                "INSERT INTO shift_windows (shift_type, start_time, end_time, team_id) "
                "VALUES ('day', '06:00', '18:30', ?)",
                (team_id,),
            )
            cursor.execute(
                "INSERT INTO shift_windows (shift_type, start_time, end_time, team_id) "
                "VALUES ('night', '18:00', '06:30', ?)",
                (team_id,),
            )
            self.conn.commit()
        except Exception:
            # Shift init failed — allow team creation to succeed with pending status
            shift_init_status = "pending"

        # Fetch the created_at timestamp
        cursor.execute(
            "SELECT created_at FROM team_profiles WHERE id = ?", (team_id,)
        )
        created_at = cursor.fetchone()[0]

        return {
            "id": team_id,
            "site_code": site_code,
            "display_name": display_name,
            "created_at": created_at,
            "role": "admin",
            "shift_init_status": shift_init_status,
        }

    def delete_team(self, team_id: int) -> None:
        """Delete a team profile and all associated data via CASCADE.

        Args:
            team_id: The team profile ID to delete.
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM team_profiles WHERE id = ?", (team_id,))
        self.conn.commit()

    def get_teams_for_user(self, user_id: int) -> list[dict]:
        """Return all teams a user belongs to with role and joined_at.

        Args:
            user_id: The user's ID.

        Returns:
            List of dicts with keys: id, site_code, display_name, created_at,
            role, joined_at.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT tp.id, tp.site_code, tp.display_name, tp.created_at, "
            "tm.role, tm.joined_at "
            "FROM team_profiles tp "
            "JOIN team_members tm ON tp.id = tm.team_id "
            "WHERE tm.user_id = ?",
            (user_id,),
        )
        return [
            {
                "id": row[0],
                "site_code": row[1],
                "display_name": row[2],
                "created_at": row[3],
                "role": row[4],
                "joined_at": row[5],
            }
            for row in cursor.fetchall()
        ]

    def get_team_by_site_code(self, site_code: str) -> dict | None:
        """Look up a team profile by site code.

        Args:
            site_code: The site code to search for.

        Returns:
            A dict with keys: id, site_code, display_name, created_at,
            or None if not found.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, site_code, display_name, created_at "
            "FROM team_profiles WHERE site_code = ?",
            (site_code,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "site_code": row[1],
            "display_name": row[2],
            "created_at": row[3],
        }

    def get_shift_windows_for_team(self, team_id: int) -> dict[str, ShiftWindow]:
        """Return shift windows for a specific team, with lazy retry initialization.

        If no shift windows exist for the team (e.g., due to a failed initial
        creation), this method automatically creates the defaults (lazy retry
        per Req 1.4).

        Args:
            team_id: The team profile ID.

        Returns:
            Dict mapping shift_type to ShiftWindow (e.g., {'day': ..., 'night': ...}).
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT shift_type, start_time, end_time FROM shift_windows WHERE team_id = ?",
            (team_id,),
        )
        rows = cursor.fetchall()

        # Lazy retry: if no shift windows exist for this team, create defaults
        if not rows:
            try:
                cursor.execute(
                    "INSERT INTO shift_windows (shift_type, start_time, end_time, team_id) "
                    "VALUES ('day', '06:00', '18:30', ?)",
                    (team_id,),
                )
                cursor.execute(
                    "INSERT INTO shift_windows (shift_type, start_time, end_time, team_id) "
                    "VALUES ('night', '18:00', '06:30', ?)",
                    (team_id,),
                )
                self.conn.commit()
                cursor.execute(
                    "SELECT shift_type, start_time, end_time FROM shift_windows WHERE team_id = ?",
                    (team_id,),
                )
                rows = cursor.fetchall()
            except Exception:
                # If lazy retry also fails, return empty
                return {}

        return {
            row[0]: ShiftWindow(shift_type=row[0], start_time=row[1], end_time=row[2])
            for row in rows
        }
