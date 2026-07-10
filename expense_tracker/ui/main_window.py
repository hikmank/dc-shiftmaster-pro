"""Main application window with sidebar navigation."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QMainWindow, QPushButton, QStatusBar, QHBoxLayout, QVBoxLayout,
    QWidget, QLabel, QStackedWidget, QFrame, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt, QSize
from database import Database
from ui.dashboard import DashboardWidget
from ui.transactions import TransactionsWidget
from ui.import_dialog import ImportDialog
from ui.report_dialog import ReportDialog


SIDEBAR_STYLE_NORMAL = """
    QPushButton {
        background: transparent;
        color: #8b949e;
        border: none;
        border-radius: 10px;
        padding: 12px 18px;
        font-size: 14px;
        font-weight: 500;
        text-align: left;
    }
    QPushButton:hover {
        background-color: #1c2333;
        color: #e6edf3;
    }
"""
SIDEBAR_STYLE_ACTIVE = """
    QPushButton {
        background-color: rgba(56, 139, 253, 0.15);
        color: #58a6ff;
        border: none;
        border-left: 3px solid #58a6ff;
        border-radius: 10px;
        padding: 12px 18px;
        font-size: 14px;
        font-weight: 600;
        text-align: left;
    }
"""


class SidebarButton(QPushButton):
    def __init__(self, icon_text: str, label: str):
        super().__init__(f"  {icon_text}   {label}")
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.set_active(False)

    def set_active(self, active: bool):
        self.setChecked(active)
        self.setStyleSheet(SIDEBAR_STYLE_ACTIVE if active else SIDEBAR_STYLE_NORMAL)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.setWindowTitle("ExpenseTracker Pro")
        self.setMinimumSize(1200, 750)
        self.resize(1400, 850)
        self._nav_buttons = []
        self._build_ui()
        self._navigate(0)
        self._refresh_all()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ──
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(4)

        # Logo
        logo_label = QLabel("💰 ExpenseTracker")
        logo_label.setStyleSheet(
            "font-size: 16px; font-weight: 700; color: #58a6ff; "
            "padding: 8px 4px 20px 4px; background: transparent;"
        )
        sidebar_layout.addWidget(logo_label)

        # Nav items
        nav_items = [
            ("📊", "Dashboard"),
            ("💳", "Transactions"),
        ]
        for icon, label in nav_items:
            btn = SidebarButton(icon, label)
            idx = len(self._nav_buttons)
            btn.clicked.connect(lambda checked, i=idx: self._navigate(i))
            sidebar_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        sidebar_layout.addSpacerItem(QSpacerItem(0, 24, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        # Separator label
        section_label = QLabel("  ACTIONS")
        section_label.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #484f58; "
            "letter-spacing: 1px; padding: 4px 0; background: transparent;"
        )
        sidebar_layout.addWidget(section_label)

        # Action buttons
        import_btn = QPushButton("  📥   Import CSV")
        import_btn.setStyleSheet(SIDEBAR_STYLE_NORMAL)
        import_btn.setFixedHeight(44)
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(self._import_csv)
        sidebar_layout.addWidget(import_btn)

        report_btn = QPushButton("  📄   Generate Report")
        report_btn.setStyleSheet(SIDEBAR_STYLE_NORMAL)
        report_btn.setFixedHeight(44)
        report_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        report_btn.clicked.connect(self._generate_report)
        sidebar_layout.addWidget(report_btn)

        sidebar_layout.addStretch()

        # Version footer
        version_label = QLabel("v1.0.0")
        version_label.setStyleSheet(
            "font-size: 11px; color: #30363d; padding: 8px; background: transparent;"
        )
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(version_label)

        root.addWidget(sidebar)

        # ── Content area ──
        content_area = QVBoxLayout()
        content_area.setContentsMargins(0, 0, 0, 0)
        content_area.setSpacing(0)

        # Top bar
        top_bar = QFrame()
        top_bar.setFixedHeight(52)
        top_bar.setStyleSheet(
            "QFrame { background-color: #0d1117; border-bottom: 1px solid #21262d; }"
        )
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(24, 0, 24, 0)

        self.page_title = QLabel("Dashboard")
        self.page_title.setStyleSheet(
            "font-size: 16px; font-weight: 600; color: #e6edf3; background: transparent;"
        )
        top_layout.addWidget(self.page_title)
        top_layout.addStretch()

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet(
            "font-size: 12px; color: #8b949e; background: transparent;"
        )
        top_layout.addWidget(self.summary_label)

        content_area.addWidget(top_bar)

        # Stacked pages
        self.stack = QStackedWidget()
        self.dashboard = DashboardWidget(self.db)
        self.transactions = TransactionsWidget(self.db)
        self.transactions.data_changed.connect(self._refresh_all)
        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.transactions)
        content_area.addWidget(self.stack)

        root.addLayout(content_area, 1)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")

    def _navigate(self, index: int):
        self.stack.setCurrentIndex(index)
        titles = ["Dashboard", "Transactions"]
        self.page_title.setText(titles[index])
        for i, btn in enumerate(self._nav_buttons):
            btn.set_active(i == index)

    def _refresh_all(self):
        self.dashboard.refresh()
        self.transactions.refresh()
        summary = self.db.get_summary()
        self.summary_label.setText(
            f"{summary['transaction_count']} transactions  ·  "
            f"${summary['business_total']:,.2f} business  ·  "
            f"${summary['personal_total']:,.2f} personal"
        )
        self.status.showMessage(
            f"Needs review: ${summary['unclassified_total']:,.2f} across "
            f"{summary['transaction_count']} transactions"
        )

    def _import_csv(self):
        dlg = ImportDialog(self.db, self)
        dlg.exec()
        if dlg.imported_count > 0:
            self._refresh_all()
            self._navigate(1)  # Jump to transactions after import

    def _generate_report(self):
        dlg = ReportDialog(self.db, self)
        dlg.exec()

    def closeEvent(self, event):
        self.db.close()
        event.accept()
