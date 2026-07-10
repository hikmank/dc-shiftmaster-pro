"""DC-ShiftMaster Pro — Application entry point.

Initializes the CustomTkinter app with dark theme, creates the
DatabaseManager, and launches the MainWindow.
"""

import os
import sys

import customtkinter as ctk

from dc_shiftmaster.database import DatabaseManager
from dc_shiftmaster.ui.main_window import MainWindow


def _icon_path() -> str:
    """Resolve the app icon path, handling PyInstaller bundles."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(__file__)
    return os.path.join(base, "app_icon.ico")


def main() -> None:
    """Launch the DC-ShiftMaster Pro application."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("DC-ShiftMaster Pro")
    root.configure(fg_color="#020617")  # Deepest Navy background

    icon = _icon_path()
    if os.path.exists(icon):
        root.iconbitmap(icon)

    db = DatabaseManager("teammates.db")
    MainWindow(root, db)

    root.mainloop()


if __name__ == "__main__":
    main()
