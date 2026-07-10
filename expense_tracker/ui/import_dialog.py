"""CSV import dialog — redesigned."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QLineEdit, QTextEdit, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from utils.csv_parser import parse_csv


class ImportDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Import Statement")
        self.setMinimumSize(560, 440)
        self._imported_count = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 24)

        title = QLabel("📥  Import CSV Statement")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #e6edf3; background: transparent;"
        )
        layout.addWidget(title)

        info = QLabel(
            "Import a CSV exported from your bank or credit card provider.\n"
            "Columns for date, description, and amount are auto-detected."
        )
        info.setStyleSheet("font-size: 12px; color: #8b949e; background: transparent;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # File picker
        file_frame = QFrame()
        file_frame.setObjectName("filter-bar")
        file_layout = QHBoxLayout(file_frame)
        file_layout.setContentsMargins(12, 8, 12, 8)
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("No file selected...")
        self.file_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        file_layout.addWidget(self.file_edit, 1)
        file_layout.addWidget(browse_btn)
        layout.addWidget(file_frame)

        # Account name
        acct_layout = QHBoxLayout()
        acct_lbl = QLabel("Account:")
        acct_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #8b949e; background: transparent;")
        self.account_edit = QLineEdit()
        self.account_edit.setPlaceholderText("e.g. Chase Visa, BofA Checking")
        acct_layout.addWidget(acct_lbl)
        acct_layout.addWidget(self.account_edit, 1)
        layout.addLayout(acct_layout)

        # Log output
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        self.log.setStyleSheet(
            "QTextEdit { background-color: #0d1117; border: 1px solid #21262d; "
            "border-radius: 8px; color: #8b949e; font-family: 'Cascadia Code', 'Consolas', monospace; "
            "font-size: 11px; padding: 8px; }"
        )
        self.log.setPlaceholderText("Import log will appear here...")
        layout.addWidget(self.log)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        self.import_btn = QPushButton("📥  Import")
        self.import_btn.setObjectName("primary")
        self.import_btn.setEnabled(False)
        self.import_btn.setMinimumWidth(120)
        self.import_btn.clicked.connect(self._do_import)
        btn_layout.addWidget(close_btn)
        btn_layout.addWidget(self.import_btn)
        layout.addLayout(btn_layout)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv);;All Files (*)"
        )
        if path:
            self.file_edit.setText(path)
            self.import_btn.setEnabled(True)

    def _do_import(self):
        filepath = self.file_edit.text()
        account = self.account_edit.text().strip()
        if not filepath:
            return

        self.log.clear()
        self.log.append(f"⏳ Parsing {os.path.basename(filepath)}...")

        transactions, errors = parse_csv(filepath, account)

        if errors:
            self.log.append(f"\n⚠️  {len(errors)} warning(s):")
            for e in errors[:15]:
                self.log.append(f"   {e}")
            if len(errors) > 15:
                self.log.append(f"   ... and {len(errors) - 15} more")

        if transactions:
            count = self.db.add_transactions_bulk(transactions)
            self._imported_count = count
            self.log.append(f"\n✅ Imported {count} transactions.")
            QMessageBox.information(
                self, "Import Complete",
                f"Successfully imported {count} transactions\nfrom {account or 'unknown account'}."
            )
        else:
            self.log.append("\n❌ No transactions found. Check the file format.")

    @property
    def imported_count(self):
        return self._imported_count
