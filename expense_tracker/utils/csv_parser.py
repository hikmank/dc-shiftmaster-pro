"""CSV/bank statement parser with auto-detection of common formats."""
import csv
from datetime import datetime
from typing import List, Tuple, Optional
from models import Transaction


# Common date formats from bank exports
DATE_FORMATS = [
    "%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%d/%m/%Y",
    "%m/%d/%y", "%Y/%m/%d", "%d-%m-%Y", "%m.%d.%Y",
    "%b %d, %Y", "%B %d, %Y", "%d %b %Y",
]


def parse_date(date_str: str) -> Optional[datetime]:
    date_str = date_str.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def detect_columns(headers: List[str]) -> dict:
    """Auto-detect which columns map to date, description, amount."""
    headers_lower = [h.lower().strip() for h in headers]
    mapping = {"date": None, "description": None, "amount": None, "debit": None, "credit": None}

    date_keywords = ["date", "posted", "trans date", "transaction date"]
    desc_keywords = ["description", "memo", "details", "narrative", "payee", "name"]
    amount_keywords = ["amount", "total"]
    debit_keywords = ["debit", "withdrawal", "charge"]
    credit_keywords = ["credit", "deposit", "payment"]

    for i, h in enumerate(headers_lower):
        for kw in date_keywords:
            if kw in h and mapping["date"] is None:
                mapping["date"] = i
        for kw in desc_keywords:
            if kw in h and mapping["description"] is None:
                mapping["description"] = i
        for kw in amount_keywords:
            if kw in h and mapping["amount"] is None:
                mapping["amount"] = i
        for kw in debit_keywords:
            if kw in h and mapping["debit"] is None:
                mapping["debit"] = i
        for kw in credit_keywords:
            if kw in h and mapping["credit"] is None:
                mapping["credit"] = i

    return mapping


def parse_amount(value: str) -> float:
    """Parse amount string, handling parentheses for negatives, currency symbols, etc."""
    value = value.strip().replace("$", "").replace(",", "").replace(" ", "")
    if not value or value == "-":
        return 0.0
    negative = False
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
        negative = True
    if value.startswith("-"):
        value = value[1:]
        negative = True
    try:
        result = float(value)
        return -result if negative else result
    except ValueError:
        return 0.0


def parse_csv(filepath: str, account_name: str = "") -> Tuple[List[Transaction], List[str]]:
    """Parse a CSV bank/credit card statement. Returns (transactions, errors)."""
    transactions = []
    errors = []

    with open(filepath, "r", encoding="utf-8-sig") as f:
        # Try to sniff the dialect
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel

        reader = csv.reader(f, dialect)
        rows = list(reader)

    if len(rows) < 2:
        return [], ["File has fewer than 2 rows"]

    headers = rows[0]
    mapping = detect_columns(headers)

    if mapping["date"] is None:
        errors.append("Could not detect date column")
        return [], errors
    if mapping["description"] is None:
        errors.append("Could not detect description column")
        return [], errors
    if mapping["amount"] is None and mapping["debit"] is None:
        errors.append("Could not detect amount column")
        return [], errors

    for i, row in enumerate(rows[1:], start=2):
        try:
            if len(row) <= max(v for v in mapping.values() if v is not None):
                continue

            date = parse_date(row[mapping["date"]])
            if date is None:
                errors.append(f"Row {i}: Could not parse date '{row[mapping['date']]}'")
                continue

            description = row[mapping["description"]].strip()

            if mapping["amount"] is not None:
                amount = parse_amount(row[mapping["amount"]])
            else:
                debit = parse_amount(row[mapping["debit"]]) if mapping["debit"] is not None else 0.0
                credit = parse_amount(row[mapping["credit"]]) if mapping["credit"] is not None else 0.0
                amount = -(abs(debit)) if debit != 0 else abs(credit)

            transactions.append(Transaction(
                date=date,
                description=description,
                amount=amount,
                account=account_name,
            ))
        except Exception as e:
            errors.append(f"Row {i}: {str(e)}")

    return transactions, errors
