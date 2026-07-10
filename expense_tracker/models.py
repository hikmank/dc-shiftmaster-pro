"""Data models for the expense tracker."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Transaction:
    id: Optional[int] = None
    date: datetime = field(default_factory=datetime.now)
    description: str = ""
    amount: float = 0.0
    category: str = "Uncategorized"
    expense_type: str = "Unclassified"  # "Business", "Personal", "Unclassified"
    account: str = ""
    receipt_path: Optional[str] = None
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)
