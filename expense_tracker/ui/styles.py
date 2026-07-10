"""Application theming and styles — modern dark UI."""

DARK_THEME = """
/* ── Global font ── */
* {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

/* ── Top-level windows only ── */
QMainWindow {
    background-color: #0d1117;
    color: #e6edf3;
}
QDialog {
    background-color: #0d1117;
    color: #e6edf3;
}

/* ── Labels ── */
QLabel {
    color: #e6edf3;
    background: transparent;
}

/* ── Sidebar ── */
QFrame#sidebar {
    background-color: #161b22;
    border-right: 1px solid #21262d;
}
QFrame#sidebar QLabel {
    background: transparent;
}
QFrame#sidebar QPushButton {
    background: transparent;
    color: #8b949e;
    border: none;
    border-radius: 10px;
    padding: 12px 18px;
    font-size: 14px;
    font-weight: 500;
    text-align: left;
}
QFrame#sidebar QPushButton:hover {
    background-color: #1c2333;
    color: #e6edf3;
}

/* ── Stat cards ── */
QFrame#stat-card {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 14px;
}
QFrame#stat-card-green {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #161b22, stop:1 #0d2818);
    border: 1px solid #238636;
    border-radius: 14px;
}
QFrame#stat-card-red {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #161b22, stop:1 #2d1117);
    border: 1px solid #da3633;
    border-radius: 14px;
}
QFrame#stat-card-amber {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #161b22, stop:1 #2b1d0e);
    border: 1px solid #d29922;
    border-radius: 14px;
}
QFrame#stat-card-blue {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #161b22, stop:1 #0c2d4a);
    border: 1px solid #388bfd;
    border-radius: 14px;
}
QFrame#stat-card QLabel, QFrame#stat-card-green QLabel,
QFrame#stat-card-red QLabel, QFrame#stat-card-amber QLabel,
QFrame#stat-card-blue QLabel {
    background: transparent;
}

QFrame#chart-card {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 14px;
}
QFrame#chart-card QLabel {
    background: transparent;
}
QFrame#filter-bar {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 12px;
}
QFrame#filter-bar QLabel {
    background: transparent;
}
QFrame#classify-bar {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 12px;
}
QFrame#classify-bar QLabel {
    background: transparent;
}

/* ── Stacked widget & pages ── */
QStackedWidget {
    background-color: #0d1117;
}
QStackedWidget > QWidget {
    background-color: #0d1117;
}

/* ── Buttons ── */
QPushButton {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #30363d;
    border-color: #484f58;
}
QPushButton:pressed {
    background-color: #1c2128;
}
QPushButton#primary {
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
    font-weight: 600;
}
QPushButton#primary:hover {
    background-color: #2ea043;
    border-color: #3fb950;
}
QPushButton#primary:disabled {
    background-color: #1c2128;
    color: #484f58;
    border-color: #30363d;
}
QPushButton#danger {
    background-color: #da3633;
    color: #ffffff;
    border: 1px solid #f85149;
}
QPushButton#danger:hover {
    background-color: #f85149;
}
QPushButton#business-btn {
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
    font-weight: 600;
    border-radius: 8px;
    padding: 8px 20px;
}
QPushButton#business-btn:hover {
    background-color: #2ea043;
}
QPushButton#personal-btn {
    background-color: #da3633;
    color: #ffffff;
    border: 1px solid #f85149;
    font-weight: 600;
    border-radius: 8px;
    padding: 8px 20px;
}
QPushButton#personal-btn:hover {
    background-color: #f85149;
}

/* ── Table ── */
QTableWidget {
    background-color: #0d1117;
    alternate-background-color: #0d1117;
    border: 1px solid #21262d;
    border-radius: 12px;
    gridline-color: transparent;
    selection-background-color: rgba(56, 139, 253, 0.15);
    selection-color: #e6edf3;
    color: #e6edf3;
    outline: none;
}
QTableWidget::item {
    padding: 10px 12px;
    border-bottom: 1px solid #161b22;
    background-color: #0d1117;
    color: #e6edf3;
}
QTableWidget::item:selected {
    background-color: rgba(56, 139, 253, 0.15);
    color: #e6edf3;
}
QTableWidget::item:hover {
    background-color: #161b22;
}
QHeaderView {
    background-color: #161b22;
}
QHeaderView::section {
    background-color: #161b22;
    color: #8b949e;
    padding: 12px 12px;
    border: none;
    border-bottom: 2px solid #21262d;
    font-weight: 600;
    font-size: 11px;
}
QTableCornerButton::section {
    background-color: #161b22;
    border: none;
}

/* ── Inputs — the critical fix ── */
QLineEdit {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 8px 12px;
    color: #e6edf3;
    font-size: 13px;
    selection-background-color: #264f78;
    selection-color: #e6edf3;
}
QLineEdit:focus {
    border-color: #58a6ff;
}
QLineEdit:read-only {
    color: #8b949e;
}

QTextEdit {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 8px 12px;
    color: #e6edf3;
    font-size: 13px;
    selection-background-color: #264f78;
    selection-color: #e6edf3;
}
QTextEdit:focus {
    border-color: #58a6ff;
}

QComboBox {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 8px 12px;
    color: #e6edf3;
    font-size: 13px;
    min-height: 20px;
}
QComboBox:focus, QComboBox:on {
    border-color: #58a6ff;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border: none;
}
QComboBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #8b949e;
}
QComboBox QAbstractItemView {
    background-color: #161b22;
    border: 1px solid #30363d;
    color: #e6edf3;
    selection-background-color: #21262d;
    selection-color: #e6edf3;
    padding: 4px;
    outline: none;
}
QComboBox QAbstractItemView::item {
    padding: 6px 12px;
    min-height: 24px;
    color: #e6edf3;
    background-color: #161b22;
}
QComboBox QAbstractItemView::item:hover {
    background-color: #21262d;
}
QComboBox QAbstractItemView::item:selected {
    background-color: rgba(56, 139, 253, 0.15);
    color: #58a6ff;
}

QDateEdit {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 8px 12px;
    color: #e6edf3;
    font-size: 13px;
    selection-background-color: #264f78;
    selection-color: #e6edf3;
}
QDateEdit:focus {
    border-color: #58a6ff;
}
QDateEdit::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border: none;
}
QDateEdit::down-arrow {
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #8b949e;
}

/* ── Calendar popup ── */
QCalendarWidget {
    background-color: #161b22;
    color: #e6edf3;
}
QCalendarWidget QWidget {
    background-color: #161b22;
    color: #e6edf3;
}
QCalendarWidget QToolButton {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 4px 8px;
}
QCalendarWidget QToolButton:hover {
    background-color: #30363d;
}
QCalendarWidget QMenu {
    background-color: #161b22;
    color: #e6edf3;
}
QCalendarWidget QSpinBox {
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    selection-background-color: #264f78;
    selection-color: #e6edf3;
}
QCalendarWidget QAbstractItemView {
    background-color: #161b22;
    color: #e6edf3;
    selection-background-color: #238636;
    selection-color: #ffffff;
}

/* ── Scrollbar ── */
QScrollBar:vertical {
    background-color: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #30363d;
    border-radius: 4px;
    min-height: 40px;
}
QScrollBar::handle:vertical:hover {
    background-color: #484f58;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background-color: transparent;
    height: 8px;
}
QScrollBar::handle:horizontal {
    background-color: #30363d;
    border-radius: 4px;
    min-width: 40px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}

/* ── Status bar ── */
QStatusBar {
    background-color: #161b22;
    color: #8b949e;
    border-top: 1px solid #21262d;
    font-size: 12px;
    padding: 4px 12px;
}
QStatusBar QLabel {
    background: transparent;
}

/* ── Context menu ── */
QMenu {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 6px;
    color: #e6edf3;
}
QMenu::item {
    padding: 8px 24px 8px 12px;
    border-radius: 6px;
    color: #e6edf3;
    background: transparent;
}
QMenu::item:selected {
    background-color: rgba(56, 139, 253, 0.15);
    color: #58a6ff;
}
QMenu::separator {
    height: 1px;
    background-color: #21262d;
    margin: 4px 8px;
}

/* ── Message boxes ── */
QMessageBox {
    background-color: #0d1117;
    color: #e6edf3;
}
QMessageBox QLabel {
    color: #e6edf3;
    background: transparent;
}

/* ── Tooltip ── */
QToolTip {
    background-color: #1c2128;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}

/* ── Form layout labels in dialogs ── */
QFormLayout QLabel {
    background: transparent;
}
"""
