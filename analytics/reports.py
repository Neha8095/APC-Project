"""Data summaries and charts based on actual library records."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def borrowing_analytics(
    loans: Sequence[dict[str, Any]],
    books: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    frame = pd.DataFrame(loans)
    if frame.empty:
        return {
            "popular_books": pd.DataFrame(columns=["title", "borrow_count"]),
            "popular_categories": pd.DataFrame(columns=["category", "borrow_count"]),
            "monthly_issues": pd.DataFrame(columns=["month", "issue_count"]),
            "monthly_returns": pd.DataFrame(columns=["month", "return_count"]),
            "inventory_distribution": np.asarray(
                [book["available_quantity"] for book in books], dtype=int
            ),
            "overdue_count": 0,
        }

    returned_or_issued = frame.copy()
    popular_books = (
        returned_or_issued.groupby("title", dropna=False)
        .size()
        .rename("borrow_count")
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )
    if "category" in returned_or_issued:
        popular_categories = (
            returned_or_issued.groupby("category", dropna=False)
            .size()
            .rename("borrow_count")
            .sort_values(ascending=False)
            .reset_index()
        )
    else:
        popular_categories = pd.DataFrame(columns=["category", "borrow_count"])
    dates = pd.to_datetime(returned_or_issued["issue_date"], errors="coerce")
    monthly = dates.dropna().dt.to_period("M").astype(str).value_counts().sort_index()
    monthly_issues = monthly.rename_axis("month").rename("issue_count").reset_index()
    overdue = (
        int(pd.to_numeric(frame["is_overdue"], errors="coerce").fillna(0).sum())
        if "is_overdue" in frame
        else 0
    )
    inventory_distribution = np.asarray(
        [book["available_quantity"] for book in books], dtype=int
    )
    return_dates = pd.to_datetime(frame.get("return_date", pd.Series(dtype=str)), errors="coerce")
    monthly_returns = (
        return_dates.dropna().dt.to_period("M").astype(str).value_counts().sort_index()
    )
    return {
        "popular_books": popular_books,
        "popular_categories": popular_categories,
        "monthly_issues": monthly_issues,
        "monthly_returns": monthly_returns.rename_axis("month")
        .rename("return_count")
        .reset_index(),
        "inventory_distribution": inventory_distribution,
        "overdue_count": overdue,
    }


def build_analytics_figure(
    loans: Sequence[dict[str, Any]],
    books: Sequence[dict[str, Any]],
    fines: Sequence[dict[str, Any]],
):
    """Build a four-panel Matplotlib figure from real library records."""
    from matplotlib.figure import Figure

    analytics = borrowing_analytics(loans, books)
    figure = Figure(figsize=(12, 4.4), dpi=100, facecolor="#f1f5f9")
    axes = figure.subplots(2, 2)
    figure.subplots_adjust(
        left=0.09, right=0.96, top=0.87, bottom=0.12, hspace=0.48, wspace=0.27
    )

    def style_axis(axis: Any, title: str) -> None:
        axis.set_facecolor("#ffffff")
        axis.set_title(title, loc="left", fontsize=11, fontweight="bold", color="#1e293b", pad=12)
        axis.grid(axis="x", color="#e2e8f0", linewidth=0.8)
        axis.set_axisbelow(True)
        for edge in ("top", "right", "left"):
            axis.spines[edge].set_visible(False)
        axis.spines["bottom"].set_color("#cbd5e1")
        axis.tick_params(axis="both", colors="#64748b", labelsize=8, length=0)

    popular_categories = analytics["popular_categories"].head(6)
    axis = axes[0, 0]
    style_axis(axis, "Borrowing by category")
    if popular_categories.empty:
        axis.text(0.5, 0.5, "No borrowing records yet", ha="center", va="center", color="#64748b")
        axis.set_axis_off()
    else:
        items = popular_categories.iloc[::-1]
        labels = items["category"].fillna("Uncategorized").astype(str)
        bars = axis.barh(labels, items["borrow_count"], color="#3b82f6", height=0.62)
        axis.bar_label(bars, padding=4, fontsize=8, color="#334155")
        axis.set_xlabel("Number of loans", fontsize=8, color="#64748b")
        axis.margins(x=0.18)

    monthly_issues = analytics["monthly_issues"].tail(8)
    monthly_returns = analytics["monthly_returns"].tail(8)
    axis = axes[0, 1]
    style_axis(axis, "Monthly issues and returns")
    if monthly_issues.empty and monthly_returns.empty:
        axis.text(0.5, 0.5, "No monthly activity yet", ha="center", va="center", color="#64748b")
        axis.set_axis_off()
    else:
        months = sorted(
            set(monthly_issues["month"].astype(str))
            | set(monthly_returns["month"].astype(str))
        )[-8:]
        issue_counts = monthly_issues.set_index("month")["issue_count"].to_dict()
        return_counts = monthly_returns.set_index("month")["return_count"].to_dict()
        positions = np.arange(len(months))
        bar_width = 0.36
        axis.bar(
            positions - bar_width / 2,
            [int(issue_counts.get(month, 0)) for month in months],
            width=bar_width,
            color="#2563eb",
            label="Issued",
        )
        axis.bar(
            positions + bar_width / 2,
            [int(return_counts.get(month, 0)) for month in months],
            width=bar_width,
            color="#10b981",
            label="Returned",
        )
        axis.set_xticks(positions, months, rotation=25, ha="right")
        axis.set_ylabel("Transactions", fontsize=8, color="#64748b")
        axis.legend(frameon=False, fontsize=8, loc="upper left")

    inventory_axis = axes[1, 0]
    style_axis(inventory_axis, "Inventory availability by category")
    inventory: dict[str, list[int]] = {}
    for book in books:
        category = str(book.get("category") or "Uncategorized")
        totals = inventory.setdefault(category, [0, 0])
        total = int(book.get("total_quantity") or 0)
        available = int(book.get("available_quantity") or 0)
        totals[0] += available
        totals[1] += max(total - available, 0)
    if not inventory:
        inventory_axis.text(
            0.5, 0.5, "No inventory records yet", ha="center", va="center", color="#64748b"
        )
        inventory_axis.set_axis_off()
    else:
        inventory_items = sorted(
            inventory.items(), key=lambda item: sum(item[1]), reverse=True
        )[:7]
        labels = [item[0] for item in inventory_items][::-1]
        available_values = [item[1][0] for item in inventory_items][::-1]
        issued_values = [item[1][1] for item in inventory_items][::-1]
        inventory_axis.barh(labels, available_values, color="#10b981", label="Available")
        inventory_axis.barh(
            labels,
            issued_values,
            left=available_values,
            color="#f59e0b",
            label="Issued",
        )
        inventory_axis.set_xlabel("Physical copies", fontsize=8, color="#64748b")
        inventory_axis.legend(frameon=False, fontsize=8, loc="lower right")

    fine_axis = axes[1, 1]
    style_axis(fine_axis, "Fine balance: paid vs outstanding")
    fine_totals = {"Paid": 0.0, "Unpaid": 0.0}
    for fine in fines:
        status = "Paid" if fine.get("payment_status") == "paid" else "Unpaid"
        fine_totals[status] += float(fine.get("amount") or 0)
    fine_totals["Unpaid"] += sum(
        float(loan.get("estimated_fine") or 0)
        for loan in loans
        if loan.get("status") == "issued"
    )
    amounts = [fine_totals["Paid"], fine_totals["Unpaid"]]
    if sum(amounts) <= 0:
        fine_axis.text(
            0.5, 0.5, "No fine payments recorded", ha="center", va="center", color="#64748b"
        )
    else:
        bars = fine_axis.barh(
            ["Paid", "Outstanding"],
            amounts,
            color=("#10b981", "#f97316"),
            height=0.5,
        )
        fine_axis.bar_label(
            bars, labels=[f"{amount:,.2f}" for amount in amounts], padding=5, fontsize=8
        )
        fine_axis.set_xlabel("Fine amount", fontsize=8, color="#64748b")
        fine_axis.set_xlim(0, max(amounts) * 1.25)
    return figure


def save_borrowing_chart(
    loans: Sequence[dict[str, Any]], destination: str
) -> str:
    """Save a chart image; Matplotlib is imported only when a chart is requested."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    summary = borrowing_analytics(loans)["popular_books"]
    figure, axis = plt.subplots(figsize=(9, 5))
    if summary.empty:
        axis.text(0.5, 0.5, "No borrowing records yet", ha="center", va="center")
        axis.set_axis_off()
    else:
        axis.barh(summary["title"].astype(str), summary["borrow_count"])
        axis.invert_yaxis()
        axis.set_xlabel("Number of loans")
        axis.set_title("Most borrowed books")
    figure.tight_layout()
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination)
    plt.close(figure)
    return destination
