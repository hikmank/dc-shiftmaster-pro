"""Dashboard widget with summary cards and donut charts."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import numpy as np


class StatCard(QFrame):
    """A summary stat card with emoji icon, label, and value."""
    def __init__(self, emoji: str, label: str, value: str, accent: str, card_id: str):
        super().__init__()
        self.setObjectName(card_id)
        self.setMinimumHeight(130)
        self.setMaximumHeight(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(6)

        # Top row: emoji + label
        top = QHBoxLayout()
        icon = QLabel(emoji)
        icon.setStyleSheet("font-size: 22px; background: transparent;")
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: #8b949e; "
            f"letter-spacing: 1.2px; background: transparent;"
        )
        top.addWidget(icon)
        top.addWidget(lbl)
        top.addStretch()
        layout.addLayout(top)

        # Value
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(
            f"font-size: 30px; font-weight: 700; color: {accent}; "
            f"background: transparent; padding-top: 4px;"
        )
        layout.addWidget(self.value_label)
        layout.addStretch()

    def set_value(self, text: str):
        self.value_label.setText(text)


class DonutChart(FigureCanvasQTAgg):
    """A donut chart with a center label."""
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(4, 3.5), dpi=100, facecolor="#161b22")
        super().__init__(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.setMinimumHeight(300)
        self.setStyleSheet("background-color: #161b22; border: none;")

    def update_chart(self, data: list, center_text: str = "", center_sub: str = ""):
        self.ax.clear()
        self.ax.set_facecolor("#161b22")

        if not data:
            self.ax.text(0.5, 0.55, "📭", ha="center", va="center",
                        fontsize=36, transform=self.ax.transAxes)
            self.ax.text(0.5, 0.38, "No data yet", ha="center", va="center",
                        color="#484f58", fontsize=12, transform=self.ax.transAxes,
                        fontfamily="Segoe UI")
            self.ax.set_xlim(-1.2, 1.2)
            self.ax.set_ylim(-1.2, 1.2)
            self.ax.set_aspect("equal")
            self.ax.axis("off")
            self.draw()
            return

        labels = [d[0] for d in data]
        values = [d[1] for d in data]
        palette = ["#3fb950", "#f85149", "#d29922", "#58a6ff", "#bc8cff",
                   "#ff7b72", "#79c0ff", "#56d364", "#e3b341", "#a5d6ff"]
        colors = [palette[i % len(palette)] for i in range(len(labels))]

        wedges, texts, autotexts = self.ax.pie(
            values, labels=None, autopct="%1.0f%%", colors=colors,
            textprops={"color": "#e6edf3", "fontsize": 10, "fontweight": "bold",
                       "fontfamily": "Segoe UI"},
            pctdistance=0.78, startangle=90,
            wedgeprops={"width": 0.42, "edgecolor": "#161b22", "linewidth": 2}
        )

        # Center text
        if center_text:
            self.ax.text(0, 0.06, center_text, ha="center", va="center",
                        fontsize=18, fontweight="bold", color="#e6edf3",
                        fontfamily="Segoe UI")
        if center_sub:
            self.ax.text(0, -0.12, center_sub, ha="center", va="center",
                        fontsize=9, color="#8b949e", fontfamily="Segoe UI")

        # Legend
        self.ax.legend(
            labels, loc="upper center", bbox_to_anchor=(0.5, -0.02),
            fontsize=9, facecolor="#161b22", edgecolor="#21262d",
            labelcolor="#8b949e", ncol=min(3, len(labels)),
            framealpha=0.9, borderpad=0.8,
            prop={"family": "Segoe UI"}
        )
        self.fig.subplots_adjust(bottom=0.18, top=0.95, left=0.05, right=0.95)
        self.draw()


class DashboardWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(28, 24, 28, 24)

        # Welcome / section header
        header = QLabel("Overview")
        header.setStyleSheet(
            "font-size: 22px; font-weight: 700; color: #e6edf3; background: transparent;"
        )
        sub = QLabel("Your expense summary at a glance")
        sub.setStyleSheet(
            "font-size: 13px; color: #8b949e; background: transparent; margin-bottom: 4px;"
        )
        layout.addWidget(header)
        layout.addWidget(sub)

        # ── Stat cards row ──
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)

        self.biz_card = StatCard("📈", "Business", "$0.00", "#3fb950", "stat-card-green")
        self.per_card = StatCard("🏠", "Personal", "$0.00", "#f85149", "stat-card-red")
        self.unc_card = StatCard("⚠️", "Needs Review", "$0.00", "#d29922", "stat-card-amber")
        self.cnt_card = StatCard("📋", "Transactions", "0", "#58a6ff", "stat-card-blue")

        cards_row.addWidget(self.biz_card)
        cards_row.addWidget(self.per_card)
        cards_row.addWidget(self.unc_card)
        cards_row.addWidget(self.cnt_card)
        layout.addLayout(cards_row)

        # ── Charts row ──
        charts_row = QHBoxLayout()
        charts_row.setSpacing(16)

        # Type breakdown
        type_card = QFrame()
        type_card.setObjectName("chart-card")
        type_vbox = QVBoxLayout(type_card)
        type_vbox.setContentsMargins(20, 16, 20, 12)
        type_title = QLabel("Expense Breakdown")
        type_title.setStyleSheet(
            "font-size: 14px; font-weight: 600; color: #e6edf3; background: transparent;"
        )
        type_sub = QLabel("Business vs Personal vs Unclassified")
        type_sub.setStyleSheet("font-size: 11px; color: #484f58; background: transparent;")
        self.type_chart = DonutChart()
        type_vbox.addWidget(type_title)
        type_vbox.addWidget(type_sub)
        type_vbox.addWidget(self.type_chart)
        charts_row.addWidget(type_card)

        # Category breakdown
        cat_card = QFrame()
        cat_card.setObjectName("chart-card")
        cat_vbox = QVBoxLayout(cat_card)
        cat_vbox.setContentsMargins(20, 16, 20, 12)
        cat_title = QLabel("Business by Category")
        cat_title.setStyleSheet(
            "font-size: 14px; font-weight: 600; color: #e6edf3; background: transparent;"
        )
        cat_sub = QLabel("Top spending categories for tax prep")
        cat_sub.setStyleSheet("font-size: 11px; color: #484f58; background: transparent;")
        self.cat_chart = DonutChart()
        cat_vbox.addWidget(cat_title)
        cat_vbox.addWidget(cat_sub)
        cat_vbox.addWidget(self.cat_chart)
        charts_row.addWidget(cat_card)

        layout.addLayout(charts_row, 1)

    def refresh(self):
        summary = self.db.get_summary()

        self.biz_card.set_value(f"${summary['business_total']:,.2f}")
        self.per_card.set_value(f"${summary['personal_total']:,.2f}")
        self.unc_card.set_value(f"${summary['unclassified_total']:,.2f}")
        self.cnt_card.set_value(str(summary['transaction_count']))

        # Type donut
        total = summary["business_total"] + summary["personal_total"] + summary["unclassified_total"]
        type_data = []
        if summary["business_total"] > 0:
            type_data.append(("Business", summary["business_total"]))
        if summary["personal_total"] > 0:
            type_data.append(("Personal", summary["personal_total"]))
        if summary["unclassified_total"] > 0:
            type_data.append(("Unclassified", summary["unclassified_total"]))
        self.type_chart.update_chart(
            type_data,
            center_text=f"${total:,.0f}" if total > 0 else "",
            center_sub="Total" if total > 0 else ""
        )

        # Category donut (business)
        cat_data = {}
        for cat, etype, amt in summary["by_category"]:
            if etype == "Business" and amt > 0:
                cat_data[cat] = cat_data.get(cat, 0) + amt
        biz_total = summary["business_total"]
        self.cat_chart.update_chart(
            list(cat_data.items()),
            center_text=f"${biz_total:,.0f}" if biz_total > 0 else "",
            center_sub="Business" if biz_total > 0 else ""
        )
