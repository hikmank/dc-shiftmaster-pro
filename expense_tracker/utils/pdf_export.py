"""PDF expense report generator."""
from datetime import datetime
from typing import List
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from models import Transaction


def generate_report(filepath: str, transactions: List[Transaction],
                    title: str = "Expense Report",
                    date_range: str = "") -> str:
    doc = SimpleDocTemplate(filepath, pagesize=letter,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ReportTitle", parent=styles["Title"],
                                  fontSize=20, textColor=colors.HexColor("#1a1a2e"))
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"],
                                     fontSize=11, textColor=colors.gray)
    section_style = ParagraphStyle("Section", parent=styles["Heading2"],
                                    fontSize=14, textColor=colors.HexColor("#0f3460"),
                                    spaceAfter=10)
    elements = []

    # Header
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", subtitle_style))
    if date_range:
        elements.append(Paragraph(f"Period: {date_range}", subtitle_style))
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", color=colors.HexColor("#0f3460")))
    elements.append(Spacer(1, 12))

    # Summary
    biz = [t for t in transactions if t.expense_type == "Business"]
    personal = [t for t in transactions if t.expense_type == "Personal"]
    unclassified = [t for t in transactions if t.expense_type == "Unclassified"]

    elements.append(Paragraph("Summary", section_style))
    summary_data = [
        ["Category", "Count", "Total"],
        ["Business Expenses", str(len(biz)), f"${sum(abs(t.amount) for t in biz):,.2f}"],
        ["Personal Expenses", str(len(personal)), f"${sum(abs(t.amount) for t in personal):,.2f}"],
        ["Unclassified", str(len(unclassified)), f"${sum(abs(t.amount) for t in unclassified):,.2f}"],
        ["Total", str(len(transactions)), f"${sum(abs(t.amount) for t in transactions):,.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[3*inch, 1.5*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3460")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # Business expenses by category
    if biz:
        elements.append(Paragraph("Business Expenses by Category", section_style))
        cat_totals = {}
        for t in biz:
            cat_totals.setdefault(t.category, 0.0)
            cat_totals[t.category] += abs(t.amount)
        cat_data = [["Category", "Total"]]
        for cat, total in sorted(cat_totals.items(), key=lambda x: -x[1]):
            cat_data.append([cat, f"${total:,.2f}"])
        cat_table = Table(cat_data, colWidths=[4*inch, 2.5*inch])
        cat_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00d4aa")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(cat_table)
        elements.append(Spacer(1, 20))

    # Transaction detail
    elements.append(Paragraph("Transaction Details", section_style))
    detail_data = [["Date", "Description", "Type", "Category", "Amount"]]
    for t in sorted(transactions, key=lambda x: x.date):
        detail_data.append([
            t.date.strftime("%m/%d/%Y"),
            t.description[:40],
            t.expense_type,
            t.category,
            f"${abs(t.amount):,.2f}",
        ])
    detail_table = Table(detail_data, colWidths=[1*inch, 2.2*inch, 1*inch, 1.3*inch, 1*inch])
    detail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3460")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (4, 0), (4, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(detail_table)

    doc.build(elements)
    return filepath
