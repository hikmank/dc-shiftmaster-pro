"""Transaction list and management widget."""
import os
import shutil
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QLineEdit, QHeaderView, QAbstractItemView,
    QFileDialog, QMessageBox, QMenu, QDialog, QFormLayout, QDateEdit,
    QTextEdit, QFrame, QSizePolicy, QStyledItemDelegate
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QRect
from PyQt6.QtGui import QAction, QColor, QPainter, QBrush, QPen, QFont
from PyQt6.QtWidgets import QStyle
from database import CATEGORIES
from models import Transaction

RECEIPT_DIR = os.path.join(os.path.expanduser("~"), ".expense_tracker", "receipts")

TYPE_COLORS = {
    "Business": ("#238636", "#2ea043", "#0d2818"),
    "Personal": ("#da3633", "#f85149", "#2d1117"),
    "Unclassified": ("#9e6a03", "#d29922", "#2b1d0e"),
}


class BadgeDelegate(QStyledItemDelegate):
    """Renders expense type as a colored badge."""
    def paint(self, painter, option, index):
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if text in TYPE_COLORS:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            fg, border, bg = TYPE_COLORS[text]
            rect = option.rect
            badge_w = min(100, rect.width() - 16)
            badge_h = 26
            x = rect.x() + (rect.width() - badge_w) // 2
            y = rect.y() + (rect.height() - badge_h) // 2
            badge_rect = QRect(x, y, badge_w, badge_h)

            # Selected row background
            if option.state & QStyle.StateFlag.State_Selected:
                painter.fillRect(rect, QColor(56, 139, 253, 38))

            painter.setBrush(QBrush(QColor(bg)))
            painter.setPen(QPen(QColor(border), 1))
            painter.drawRoundedRect(badge_rect, 6, 6)

            painter.setPen(QColor(fg))
            font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)
            painter.restore()
        else:
            super().paint(painter, option, index)


class ReceiptDelegate(QStyledItemDelegate):
    """Renders receipt status as a colored dot."""
    def paint(self, painter, option, index):
        text = index.data(Qt.ItemDataRole.DisplayRole)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, QColor(56, 139, 253, 38))

        if text == "✓":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#3fb950")))
            cx = rect.x() + rect.width() // 2
            cy = rect.y() + rect.height() // 2
            painter.drawEllipse(cx - 5, cy - 5, 10, 10)
        else:
            painter.setPen(QColor("#30363d"))
            font = QFont("Segoe UI", 9)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "—")
        painter.restore()


class TransactionEditDialog(QDialog):
    def __init__(self, transaction: Transaction = None, parent=None):
        super().__init__(parent)
        self.transaction = transaction or Transaction()
        self.setWindowTitle("Edit Transaction" if transaction and transaction.id else "New Transaction")
        self.setMinimumWidth(500)
        self.setMinimumHeight(480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 24)

        # Title
        title = QLabel(self.windowTitle())
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #e6edf3; background: transparent;")
        layout.addWidget(title)

        # Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        label_style = "font-size: 12px; font-weight: 600; color: #8b949e; background: transparent;"

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate(
            self.transaction.date.year,
            self.transaction.date.month,
            self.transaction.date.day
        ))

        self.desc_edit = QLineEdit(self.transaction.description)
        self.desc_edit.setPlaceholderText("e.g. Office Depot supplies")

        self.amount_edit = QLineEdit(str(abs(self.transaction.amount)) if self.transaction.amount else "")
        self.amount_edit.setPlaceholderText("0.00")

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Unclassified", "Business", "Personal"])
        self.type_combo.setCurrentText(self.transaction.expense_type)

        self.category_combo = QComboBox()
        self.category_combo.addItems(CATEGORIES)
        if self.transaction.category in CATEGORIES:
            self.category_combo.setCurrentText(self.transaction.category)

        self.account_edit = QLineEdit(self.transaction.account)
        self.account_edit.setPlaceholderText("e.g. Chase Visa")

        self.notes_edit = QTextEdit(self.transaction.notes)
        self.notes_edit.setMaximumHeight(70)
        self.notes_edit.setPlaceholderText("Optional notes...")

        for lbl_text, widget in [
            ("Date", self.date_edit), ("Description", self.desc_edit),
            ("Amount ($)", self.amount_edit), ("Type", self.type_combo),
            ("Category", self.category_combo), ("Account", self.account_edit),
            ("Notes", self.notes_edit),
        ]:
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(label_style)
            form.addRow(lbl, widget)

        # Receipt row
        receipt_row = QHBoxLayout()
        self.receipt_label = QLabel(
            os.path.basename(self.transaction.receipt_path) if self.transaction.receipt_path else "No receipt attached"
        )
        self.receipt_label.setStyleSheet("font-size: 12px; color: #8b949e; background: transparent;")
        receipt_btn = QPushButton("📎 Attach")
        receipt_btn.setFixedWidth(100)
        receipt_btn.clicked.connect(self._attach_receipt)
        receipt_row.addWidget(self.receipt_label, 1)
        receipt_row.addWidget(receipt_btn)
        rlbl = QLabel("Receipt")
        rlbl.setStyleSheet(label_style)
        form.addRow(rlbl, receipt_row)

        layout.addLayout(form)
        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("💾  Save")
        save_btn.setObjectName("primary")
        save_btn.setMinimumWidth(120)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        self._new_receipt_path = self.transaction.receipt_path

    def _attach_receipt(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Receipt", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;PDF (*.pdf);;All Files (*)"
        )
        if path:
            os.makedirs(RECEIPT_DIR, exist_ok=True)
            dest = os.path.join(RECEIPT_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(path)}")
            shutil.copy2(path, dest)
            self._new_receipt_path = dest
            self.receipt_label.setText(f"✓ {os.path.basename(path)}")
            self.receipt_label.setStyleSheet("font-size: 12px; color: #3fb950; background: transparent;")

    def get_transaction(self) -> Transaction:
        d = self.date_edit.date()
        try:
            amount = float(self.amount_edit.text().replace("$", "").replace(",", ""))
        except ValueError:
            amount = 0.0
        self.transaction.date = datetime(d.year(), d.month(), d.day())
        self.transaction.description = self.desc_edit.text()
        self.transaction.amount = -abs(amount)
        self.transaction.category = self.category_combo.currentText()
        self.transaction.expense_type = self.type_combo.currentText()
        self.transaction.account = self.account_edit.text()
        self.transaction.notes = self.notes_edit.toPlainText()
        self.transaction.receipt_path = self._new_receipt_path
        return self.transaction


class TransactionsWidget(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 24)

        # Header row
        header_row = QHBoxLayout()
        header = QLabel("All Transactions")
        header.setStyleSheet("font-size: 22px; font-weight: 700; color: #e6edf3; background: transparent;")
        header_row.addWidget(header)
        header_row.addStretch()

        add_btn = QPushButton("＋  New Transaction")
        add_btn.setObjectName("primary")
        add_btn.setMinimumWidth(160)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add_transaction)
        header_row.addWidget(add_btn)
        layout.addLayout(header_row)

        # ── Filter bar ──
        filter_frame = QFrame()
        filter_frame.setObjectName("filter-bar")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(16, 10, 16, 10)
        filter_layout.setSpacing(12)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍  Search transactions...")
        self.search_edit.setMinimumWidth(200)
        self.search_edit.textChanged.connect(self._apply_filters)

        flbl1 = QLabel("Type:")
        flbl1.setStyleSheet("font-size: 12px; color: #8b949e; background: transparent;")
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All", "Business", "Personal", "Unclassified"])
        self.type_filter.setMinimumWidth(120)
        self.type_filter.currentTextChanged.connect(self._apply_filters)

        flbl2 = QLabel("Category:")
        flbl2.setStyleSheet("font-size: 12px; color: #8b949e; background: transparent;")
        self.cat_filter = QComboBox()
        self.cat_filter.addItems(["All"] + CATEGORIES)
        self.cat_filter.setMinimumWidth(160)
        self.cat_filter.currentTextChanged.connect(self._apply_filters)

        filter_layout.addWidget(self.search_edit, 2)
        filter_layout.addWidget(flbl1)
        filter_layout.addWidget(self.type_filter)
        filter_layout.addWidget(flbl2)
        filter_layout.addWidget(self.cat_filter)
        layout.addWidget(filter_frame)

        # ── Table ──
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Description", "Amount", "Type", "Category", "Account", "Receipt"]
        )
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(6, 70)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Custom delegates
        self.table.setItemDelegateForColumn(3, BadgeDelegate(self.table))
        self.table.setItemDelegateForColumn(6, ReceiptDelegate(self.table))

        layout.addWidget(self.table, 1)

        # ── Quick classify bar ──
        classify_frame = QFrame()
        classify_frame.setObjectName("classify-bar")
        classify_layout = QHBoxLayout(classify_frame)
        classify_layout.setContentsMargins(16, 8, 16, 8)
        classify_layout.setSpacing(12)

        clbl = QLabel("Quick classify selected rows:")
        clbl.setStyleSheet("font-size: 12px; color: #8b949e; background: transparent;")
        classify_layout.addWidget(clbl)

        biz_btn = QPushButton("✓  Business")
        biz_btn.setObjectName("business-btn")
        biz_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        biz_btn.clicked.connect(lambda: self._quick_classify("Business"))

        per_btn = QPushButton("✗  Personal")
        per_btn.setObjectName("personal-btn")
        per_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        per_btn.clicked.connect(lambda: self._quick_classify("Personal"))

        classify_layout.addWidget(biz_btn)
        classify_layout.addWidget(per_btn)
        classify_layout.addStretch()

        # Count label
        self.count_label = QLabel("0 transactions")
        self.count_label.setStyleSheet("font-size: 12px; color: #484f58; background: transparent;")
        classify_layout.addWidget(self.count_label)

        layout.addWidget(classify_frame)
        self._transactions = []

    def refresh(self):
        self._apply_filters()

    def _apply_filters(self):
        txns = self.db.get_all_transactions(
            expense_type=self.type_filter.currentText(),
            category=self.cat_filter.currentText(),
            search=self.search_edit.text() or None,
        )
        self._transactions = txns
        self._populate_table(txns)
        self.count_label.setText(f"{len(txns)} transaction{'s' if len(txns) != 1 else ''}")

    def _populate_table(self, transactions):
        self.table.setRowCount(len(transactions))
        for row, t in enumerate(transactions):
            date_item = QTableWidgetItem(t.date.strftime("%m/%d/%Y"))
            date_item.setForeground(QColor("#8b949e"))
            self.table.setItem(row, 0, date_item)

            desc_item = QTableWidgetItem(t.description)
            desc_item.setForeground(QColor("#e6edf3"))
            self.table.setItem(row, 1, desc_item)

            amount_item = QTableWidgetItem(f"${abs(t.amount):,.2f}")
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            amount_item.setForeground(QColor("#e6edf3"))
            font = amount_item.font()
            font.setWeight(QFont.Weight.DemiBold)
            amount_item.setFont(font)
            self.table.setItem(row, 2, amount_item)

            type_item = QTableWidgetItem(t.expense_type)
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, type_item)

            cat_item = QTableWidgetItem(t.category)
            cat_item.setForeground(QColor("#8b949e"))
            self.table.setItem(row, 4, cat_item)

            acct_item = QTableWidgetItem(t.account)
            acct_item.setForeground(QColor("#484f58"))
            self.table.setItem(row, 5, acct_item)

            receipt_item = QTableWidgetItem("✓" if t.receipt_path else "")
            receipt_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 6, receipt_item)

            # Store id
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, t.id)

    def _get_selected_ids(self):
        rows = set(idx.row() for idx in self.table.selectedIndexes())
        ids = []
        for row in rows:
            item = self.table.item(row, 0)
            if item:
                tid = item.data(Qt.ItemDataRole.UserRole)
                if tid:
                    ids.append(tid)
        return ids

    def _quick_classify(self, expense_type: str):
        ids = self._get_selected_ids()
        if not ids:
            QMessageBox.information(self, "Select Rows",
                                   "Select one or more transactions to classify.")
            return
        for tid in ids:
            for t in self._transactions:
                if t.id == tid:
                    t.expense_type = expense_type
                    self.db.update_transaction(t)
                    break
        self.refresh()
        self.data_changed.emit()

    def _add_transaction(self):
        dlg = TransactionEditDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            t = dlg.get_transaction()
            self.db.add_transaction(t)
            self.refresh()
            self.data_changed.emit()

    def _context_menu(self, pos):
        rows = set(idx.row() for idx in self.table.selectedIndexes())
        if not rows:
            return
        menu = QMenu(self)

        edit_action = QAction("✏️  Edit", self)
        edit_action.triggered.connect(self._edit_selected)
        receipt_action = QAction("📎  Attach Receipt", self)
        receipt_action.triggered.connect(self._attach_receipt_selected)
        biz_action = QAction("✓  Mark as Business", self)
        biz_action.triggered.connect(lambda: self._quick_classify("Business"))
        per_action = QAction("✗  Mark as Personal", self)
        per_action.triggered.connect(lambda: self._quick_classify("Personal"))
        delete_action = QAction("🗑  Delete", self)
        delete_action.triggered.connect(self._delete_selected)

        menu.addAction(edit_action)
        menu.addAction(receipt_action)
        menu.addSeparator()
        menu.addAction(biz_action)
        menu.addAction(per_action)
        menu.addSeparator()
        menu.addAction(delete_action)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _edit_selected(self):
        ids = self._get_selected_ids()
        if len(ids) != 1:
            return
        t = next((t for t in self._transactions if t.id == ids[0]), None)
        if not t:
            return
        dlg = TransactionEditDialog(t, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            updated = dlg.get_transaction()
            self.db.update_transaction(updated)
            self.refresh()
            self.data_changed.emit()

    def _delete_selected(self):
        ids = self._get_selected_ids()
        if not ids:
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete {len(ids)} transaction{'s' if len(ids) > 1 else ''}?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            for tid in ids:
                self.db.delete_transaction(tid)
            self.refresh()
            self.data_changed.emit()

    def _attach_receipt_selected(self):
        ids = self._get_selected_ids()
        if len(ids) != 1:
            return
        t = next((t for t in self._transactions if t.id == ids[0]), None)
        if not t:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Receipt", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;PDF (*.pdf);;All Files (*)"
        )
        if path:
            os.makedirs(RECEIPT_DIR, exist_ok=True)
            dest = os.path.join(RECEIPT_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(path)}")
            shutil.copy2(path, dest)
            t.receipt_path = dest
            self.db.update_transaction(t)
            self.refresh()
