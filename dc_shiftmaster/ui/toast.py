"""Toast notification system for DC-ShiftMaster Pro.

Displays non-blocking notifications that appear at the bottom-right
of the window and auto-dismiss after a few seconds.
"""

import customtkinter as ctk
from dc_shiftmaster.ui.theme import COLORS, FONTS


class Toast:
    """A toast notification that slides in from the bottom-right."""

    _active_toasts: list["Toast"] = []

    def __init__(self, root: ctk.CTk, message: str,
                 toast_type: str = "success", duration: int = 3000) -> None:
        self.root = root
        self.duration = duration

        colors = {
            "success": (COLORS["success"], "#052E16"),
            "error": (COLORS["danger"], "#450A0A"),
            "warning": (COLORS["warning"], "#422006"),
            "info": (COLORS["primary"], "#1E1B4B"),
        }
        accent, bg = colors.get(toast_type, colors["info"])

        icons = {"success": "✓", "error": "✕", "warning": "⚠", "info": "ℹ"}
        icon = icons.get(toast_type, "ℹ")

        # Position based on active toasts
        offset_y = 20 + len(Toast._active_toasts) * 60

        self.frame = ctk.CTkFrame(
            root, fg_color=bg, corner_radius=8,
            border_width=1, border_color=accent)
        self.frame.place(relx=1.0, rely=1.0, x=-20, y=-offset_y,
                         anchor="se")

        ctk.CTkLabel(
            self.frame, text=f" {icon}  {message}",
            font=FONTS["body"], text_color=COLORS["text"],
        ).pack(padx=16, pady=10)

        Toast._active_toasts.append(self)
        self.root.after(self.duration, self._dismiss)

    def _dismiss(self) -> None:
        if self in Toast._active_toasts:
            Toast._active_toasts.remove(self)
        try:
            self.frame.destroy()
        except Exception:
            pass


def show_toast(root, message, toast_type="success", duration=3000):
    """Convenience function to show a toast notification."""
    Toast(root, message, toast_type, duration)
