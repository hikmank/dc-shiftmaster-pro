"""MigrationService for DC-ShiftMaster Pro Multi-Team Profiles.

Provides an idempotent, atomic migration that converts the existing single-team
database into a multi-tenant schema by:
1. Creating the team_profiles, team_members, and migrations_applied tables (if needed)
2. Creating the ATL069 team profile
3. Associating all existing data rows with ATL069
4. Assigning all existing users as ATL069 members with admin role
5. Recording the migration in migrations_applied for idempotency

The entire operation is wrapped in a single BEGIN IMMEDIATE transaction.
If ANY step fails, a ROLLBACK is executed and MigrationError is raised.
"""

import sqlite3
from datetime import datetime, timezone


class MigrationError(Exception):
    """Raised when the migration fails after a rollback."""

    pass


MIGRATION_NAME = "001_create_atl069_team_profile"


def run_migration(db) -> dict:
    """Execute the ATL069 team profile migration atomically.

    This migration is idempotent — if it has already been applied, it returns
    immediately with status 'already_applied'. All operations run inside a
    single BEGIN IMMEDIATE transaction. On any failure, the transaction is
    rolled back and MigrationError is raised.

    Args:
        db: A sqlite3.Connection object (or compatible) with an execute method.

    Returns:
        dict with keys:
            - "status": "success" or "already_applied"
            - "team_id": The ATL069 team profile ID (only when status is "success")

    Raises:
        MigrationError: If any step fails. The database is left unchanged.
    """
    try:
        print(f"[Migration] Starting migration: {MIGRATION_NAME}")
        db.execute("BEGIN IMMEDIATE")

        # Step 1: Check idempotency
        if _migration_already_applied(db):
            print("[Migration] Migration already applied, skipping.")
            db.execute("ROLLBACK")
            return {"status": "already_applied"}

        # Step 2: Ensure required tables exist
        print("[Migration] Creating tables if needed...")
        _create_tables(db)

        # Step 3: Ensure team_id columns exist on data tables
        print("[Migration] Ensuring team_id columns exist on data tables...")
        _ensure_team_id_columns(db)

        # Step 4: Create ATL069 team profile
        print("[Migration] Creating ATL069 team profile...")
        team_id = _create_atl069_profile(db)
        print(f"[Migration] ATL069 team profile created with id={team_id}")

        # Step 5: Associate all existing data with ATL069
        print("[Migration] Associating existing data rows with ATL069...")
        _associate_existing_data(db, team_id)

        # Step 6: Assign all existing users as ATL069 members
        print("[Migration] Assigning all users as ATL069 members (admin role)...")
        _assign_users_as_members(db, team_id)

        # Step 7: Record migration
        print("[Migration] Recording migration in migrations_applied...")
        _record_migration(db)

        db.execute("COMMIT")
        print(f"[Migration] Migration completed successfully. team_id={team_id}")
        return {"status": "success", "team_id": team_id}

    except Exception as e:
        try:
            db.execute("ROLLBACK")
        except Exception:
            pass  # ROLLBACK best-effort if connection is broken
        raise MigrationError(
            f"Migration failed, all changes rolled back: {e}"
        ) from e


def _migration_already_applied(db) -> bool:
    """Check if this migration has already been recorded."""
    # First check if the migrations_applied table exists
    cursor = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations_applied'"
    )
    if cursor.fetchone() is None:
        return False

    cursor = db.execute(
        "SELECT 1 FROM migrations_applied WHERE migration_name = ?",
        (MIGRATION_NAME,),
    )
    return cursor.fetchone() is not None


def _create_tables(db) -> None:
    """Create team_profiles, team_members, and migrations_applied tables if needed."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS team_profiles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            site_code   TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS team_members (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id   INTEGER NOT NULL REFERENCES team_profiles(id) ON DELETE CASCADE,
            user_id   INTEGER NOT NULL REFERENCES users(id),
            role      TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('admin', 'member')),
            joined_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(team_id, user_id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS migrations_applied (
            migration_name TEXT PRIMARY KEY,
            applied_at     TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def _ensure_team_id_columns(db) -> None:
    """Add team_id FK columns to existing data tables if they don't exist."""
    tables = ["teammates", "overrides", "coverage_requests", "shift_windows"]
    for table in tables:
        cursor = db.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        if "team_id" not in columns:
            db.execute(
                f"ALTER TABLE {table} ADD COLUMN team_id INTEGER "
                f"REFERENCES team_profiles(id) ON DELETE CASCADE"
            )


def _create_atl069_profile(db) -> int:
    """Create the ATL069 team profile and return its ID."""
    cursor = db.execute(
        "INSERT INTO team_profiles (site_code, display_name) VALUES (?, ?)",
        ("ATL069", "ATL069"),
    )
    return cursor.lastrowid


def _associate_existing_data(db, team_id: int) -> None:
    """Update all existing data rows to reference the ATL069 team."""
    # Update teammates
    cursor = db.execute(
        "UPDATE teammates SET team_id = ? WHERE team_id IS NULL",
        (team_id,),
    )
    print(f"[Migration]   - teammates updated: {cursor.rowcount} rows")

    # Update overrides
    cursor = db.execute(
        "UPDATE overrides SET team_id = ? WHERE team_id IS NULL",
        (team_id,),
    )
    print(f"[Migration]   - overrides updated: {cursor.rowcount} rows")

    # Update coverage_requests
    cursor = db.execute(
        "UPDATE coverage_requests SET team_id = ? WHERE team_id IS NULL",
        (team_id,),
    )
    print(f"[Migration]   - coverage_requests updated: {cursor.rowcount} rows")

    # Update shift_windows
    cursor = db.execute(
        "UPDATE shift_windows SET team_id = ? WHERE team_id IS NULL",
        (team_id,),
    )
    print(f"[Migration]   - shift_windows updated: {cursor.rowcount} rows")


def _assign_users_as_members(db, team_id: int) -> None:
    """Create team_members entries for all existing users with admin role."""
    cursor = db.execute("SELECT id FROM users")
    users = cursor.fetchall()
    count = 0
    for row in users:
        user_id = row[0]
        db.execute(
            "INSERT INTO team_members (team_id, user_id, role) VALUES (?, ?, ?)",
            (team_id, user_id, "admin"),
        )
        count += 1
    print(f"[Migration]   - users assigned as ATL069 admins: {count}")


def _record_migration(db) -> None:
    """Record this migration as applied."""
    db.execute(
        "INSERT INTO migrations_applied (migration_name) VALUES (?)",
        (MIGRATION_NAME,),
    )
