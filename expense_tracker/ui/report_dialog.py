"""PDF report generation dialog — redesigned."""
import os
import sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QDateEdit, QLineEdit, QMessageBox, QFormLayout
)
from PyQt6.QtCore import QDate, Qt
from utils.pdf_export import generate_report


class ReportDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Generate Report")
        self.setMinimumWidth(480)
        self.setMinimumHeight(360)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 24)

        title = QLabel("📄  Generate PDF Report")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #e6edf3; background: transparent;"
        )
        layout.addWidget(title)

        sub = QLabel("Create a professional expense report for your tax professional.")
        sub.setStyleSheet("font-size: 12px; color: #8b949e; background: transparent;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        label_style = "font-size: 12px; font-weight: 600; color: #8b949e; background: transparent;"

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.title_edit = QLineEdit("Expense Report")
        self.title_edit.setPlaceholderText("Report title")

        self.type_combo = QComboBox()
        self.type_combo.addItems(["All Expenses", "Business Only", "Personal Only"])

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate(datetime.now().year, 1, 1))

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())

        for lbl_text, widget in [
            ("Title", self.title_edit),
            ("Include", self.type_combo),
            ("From", self.date_from),
            ("To", self.date_to),
        ]:
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(label_style)
            form.addRow(lbl, widget)

        layout.addLayout(form)
        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        gen_btn = QPushButton("📄  Generate PDF")
        gen_btn.setObjectName("primary")
        gen_btn.setMinimumWidth(140)
        gen_btn.clicked.connect(self._generate)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(gen_btn)
        layout.addLayout(btn_layout)

    def _generate(self):
        df = self.date_from.date()
        dt = self.date_to.date()
        date_from = f"{df.year():04d}-{df.month():02d}-{df.day():02d}"
        date_to = f"{dt.year():04d}-{dt.month():02d}-{dt.day():02d}"

        type_map = {"All Expenses": None, "Business Only": "Business", "Personal Only": "Personal"}
        expense_type = type_map[self.type_combo.currentText()]

        transactions = self.db.get_all_transactions(
            expense_type=expense_type,
            date_from=date_from,
            date_to=date_to,
        )

        if not transactions:
            QMessageBox.warning(self, "No Data",
                               "No transactions found for the selected filters.")
            return

        default_name = f"expense_report_{date_from}_to_{date_to}.pdf"
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Report", os.path.join(desktop, default_name),
            "PDF Files (*.pdf)"
        )
        if not filepath:
            return

        try:
            date_range = f"{df.toString('MMM d, yyyy')} — {dt.toString('MMM d, yyyy')}"
            generate_report(filepath, transactions, self.title_edit.text(), date_range)
            QMessageBox.information(self, "Done",
                                   f"Report saved to:\n{filepath}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate report:\n{str(e)}")
