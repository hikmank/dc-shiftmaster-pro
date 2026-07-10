"""ExpenseTracker Pro - Desktop expense tracking application."""
import sys
import os

# Ensure the app root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow
from ui.styles import DARK_THEME


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ExpenseTracker Pro")
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_THEME)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
