"""SQLite database layer for expense tracker."""
import sqlite3
import os
from datetime import datetime
from typing import List, Optional, Tuple
from models import Transaction


DB_PATH = os.path.join(os.path.expanduser("~"), ".expense_tracker", "expenses.db")

CATEGORIES = [
    "Uncategorized",
    "Advertising & Marketing",
    "Car & Truck Expenses",
    "Commissions & Fees",
    "Contract Labor",
    "Employee Benefits",
    "Insurance",
    "Interest (Mortgage/Other)",
    "Legal & Professional Services",
    "Office Supplies",
    "Rent or Lease",
    "Repairs & Maintenance",
    "Meals & Entertainment",
    "Taxes & Licenses",
    "Travel",
    "Utilities",
    "Wages",
    "Software & Subscriptions",
    "Equipment",
    "Shipping & Postage",
    "Training & Education",
    "Groceries",
    "Personal Care",
    "Clothing",
    "Entertainment",
    "Healthcare",
    "Other",
]


class Database:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT DEFAULT 'Uncategorized',
                expense_type TEXT DEFAULT 'Unclassified',
                account TEXT DEFAULT '',
                receipt_path TEXT,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def add_transaction(self, t: Transaction) -> int:
        cursor = self.conn.execute(
            """INSERT INTO transactions (date, description, amount, category, expense_type, account, receipt_path, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (t.date.isoformat(), t.description, t.amount, t.category,
             t.expense_type, t.account, t.receipt_path, t.notes,
             datetime.now().isoformat()),
        )
        self.conn.commit()
        return cursor.lastrowid

    def add_transactions_bulk(self, transactions: List[Transaction]) -> int:
        rows = [
            (t.date.isoformat(), t.description, t.amount, t.category,
             t.expense_type, t.account, t.receipt_path, t.notes,
             datetime.now().isoformat())
            for t in transactions
        ]
        self.conn.executemany(
            """INSERT INTO transactions (date, description, amount, category, expense_type, account, receipt_path, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def update_transaction(self, t: Transaction):
        self.conn.execute(
            """UPDATE transactions SET date=?, description=?, amount=?, category=?,
               expense_type=?, account=?, receipt_path=?, notes=? WHERE id=?""",
            (t.date.isoformat(), t.description, t.amount, t.category,
             t.expense_type, t.account, t.receipt_path, t.notes, t.id),
        )
        self.conn.commit()

    def delete_transaction(self, transaction_id: int):
        self.conn.execute("DELETE FROM transactions WHERE id=?", (transaction_id,))
        self.conn.commit()

    def get_all_transactions(self, expense_type: Optional[str] = None,
                              category: Optional[str] = None,
                              date_from: Optional[str] = None,
                              date_to: Optional[str] = None,
                              search: Optional[str] = None) -> List[Transaction]:
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []
        if expense_type and expense_type != "All":
            query += " AND expense_type = ?"
            params.append(expense_type)
        if category and category != "All":
            query += " AND category = ?"
            params.append(category)
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date <= ?"
            params.append(date_to)
        if search:
            query += " AND (description LIKE ? OR notes LIKE ? OR account LIKE ?)"
            params.extend([f"%{search}%"] * 3)
        query += " ORDER BY date DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_transaction(r) for r in rows]

    def get_summary(self, date_from: Optional[str] = None,
                    date_to: Optional[str] = None) -> dict:
        base = "SELECT {} FROM transactions WHERE 1=1"
        params = []
        date_filter = ""
        if date_from:
            date_filter += " AND date >= ?"
            params.append(date_from)
        if date_to:
            date_filter += " AND date <= ?"
            params.append(date_to)

        total_biz = self.conn.execute(
            base.format("COALESCE(SUM(amount),0)") + date_filter + " AND expense_type='Business'", params
        ).fetchone()[0]
        total_personal = self.conn.execute(
            base.format("COALESCE(SUM(amount),0)") + date_filter + " AND expense_type='Personal'", params
        ).fetchone()[0]
        total_unclassified = self.conn.execute(
            base.format("COALESCE(SUM(amount),0)") + date_filter + " AND expense_type='Unclassified'", params
        ).fetchone()[0]
        count = self.conn.execute(
            base.format("COUNT(*)") + date_filter, params
        ).fetchone()[0]

        cat_rows = self.conn.execute(
            "SELECT category, expense_type, COALESCE(SUM(amount),0) as total FROM transactions WHERE 1=1"
            + date_filter + " GROUP BY category, expense_type ORDER BY total DESC", params
        ).fetchall()

        return {
            "business_total": abs(total_biz),
            "personal_total": abs(total_personal),
            "unclassified_total": abs(total_unclassified),
            "transaction_count": count,
            "by_category": [(r["category"], r["expense_type"], abs(r["total"])) for r in cat_rows],
        }

    def _row_to_transaction(self, row) -> Transaction:
        return Transaction(
            id=row["id"],
            date=datetime.fromisoformat(row["date"]),
            description=row["description"],
            amount=row["amount"],
            category=row["category"],
            expense_type=row["expense_type"],
            account=row["account"],
            receipt_path=row["receipt_path"],
            notes=row["notes"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def close(self):
        self.conn.close()
