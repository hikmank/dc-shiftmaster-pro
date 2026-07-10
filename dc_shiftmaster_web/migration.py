"""Database migration — import existing teammates.db into StorageAdapter."""

from __future__ import annotations

import sqlite3
import tempfile

from dc_shiftmaster.models import Override, ShiftWindow, Teammate
from dc_shiftmaster_web.storage import StorageAdapter


def import_database(file_bytes: bytes, storage: StorageAdapter) -> str:
    """Read a teammates.db file and import records into StorageAdapter.

    Uses Python's built-in sqlite3 module to open the binary database
    via a temporary file, extract records, and merge them into the
    StorageAdapter (imported values win on conflict).

    Parameters
    ----------
    file_bytes:
        Raw bytes of the .db file.
    storage:
        Target StorageAdapter to write into.

    Returns
    -------
    str
        Summary message like "Imported 12 teammates, 2 shift windows, 5 overrides."

    Raises
    ------
    ValueError
        If the file is not a valid SQLite database or lacks expected tables.
    """
    # Write bytes to a temp file so sqlite3 can open it
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        conn = sqlite3.connect(tmp_path)
    except Exception as exc:
        raise ValueError(
            "Invalid database file. Expected teammates.db format."
        ) from exc

    try:
        cursor = conn.cursor()

        # Verify expected tables exist
        try:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        except Exception as exc:
            raise ValueError(
                "Invalid database file. Expected teammates.db format."
            ) from exc
        tables = {row[0] for row in cursor.fetchall()}
        required = {"teammates", "shift_windows", "overrides"}
        if not required.issubset(tables):
            raise ValueError(
                "Invalid database file. Expected teammates.db format."
            )

        # --- Import teammates ---
        cursor.execute("PRAGMA table_info(teammates)")
        columns = [row[1] for row in cursor.fetchall()]
        has_custom_start = "custom_start" in columns

        if has_custom_start:
            cursor.execute(
                "SELECT id, name, shift_type, custom_start FROM teammates"
            )
        else:
            cursor.execute("SELECT id, name, shift_type FROM teammates")

        imported_teammates: list[Teammate] = []
        for row in cursor.fetchall():
            cs = row[3] if has_custom_start and len(row) > 3 else ""
            imported_teammates.append(
                Teammate(id=row[0], name=row[1], shift_type=row[2], custom_start=cs or "")
            )

        # --- Import shift windows ---
        cursor.execute(
            "SELECT shift_type, start_time, end_time FROM shift_windows"
        )
        imported_windows: dict[str, ShiftWindow] = {}
        for row in cursor.fetchall():
            imported_windows[row[0]] = ShiftWindow(
                shift_type=row[0], start_time=row[1], end_time=row[2]
            )

        # --- Import overrides ---
        cursor.execute("SELECT date, shift_type, name FROM overrides")
        imported_overrides: list[Override] = []
        for row in cursor.fetchall():
            imported_overrides.append(
                Override(date=row[0], shift_type=row[1], name=row[2])
            )

    finally:
        conn.close()

    # --- Merge into StorageAdapter (imported values win) ---
    _merge_teammates(storage, imported_teammates)
    _merge_shift_windows(storage, imported_windows)
    _merge_overrides(storage, imported_overrides)

    return (
        f"Imported {len(imported_teammates)} teammates, "
        f"{len(imported_windows)} shift windows, "
        f"{len(imported_overrides)} overrides."
    )


def _merge_teammates(
    storage: StorageAdapter, imported: list[Teammate]
) -> None:
    """Merge imported teammates — imported values win for same ID."""
    existing = {t.id: t for t in storage.get_teammates()}
    for t in imported:
        existing[t.id] = t
    # Rewrite the full list
    all_teammates = list(existing.values())
    storage._storage.set(
        "dcshift.teammates",
        StorageAdapter._serialize_teammates(all_teammates),
    )


def _merge_shift_windows(
    storage: StorageAdapter, imported: dict[str, ShiftWindow]
) -> None:
    """Merge imported shift windows — imported values win."""
    existing = storage.get_shift_windows()
    existing.update(imported)
    storage._storage.set(
        "dcshift.shift_windows",
        StorageAdapter._serialize_shift_windows(existing),
    )


def _merge_overrides(
    storage: StorageAdapter, imported: list[Override]
) -> None:
    """Merge imported overrides — imported values win for same date+shift_type."""
    existing = {(o.date, o.shift_type): o for o in storage._get_all_overrides()}
    for o in imported:
        existing[(o.date, o.shift_type)] = o
    all_overrides = list(existing.values())
    storage._storage.set(
        "dcshift.overrides",
        StorageAdapter._serialize_overrides(all_overrides),
    )
