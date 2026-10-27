"""Tests for chart summaries using saved library-style records."""

import unittest

from analytics.reports import borrowing_analytics, build_analytics_figure


class AnalyticsFigureTests(unittest.TestCase):
    def test_empty_library_renders_chart_panels_without_fake_statistics(self) -> None:
        figure = build_analytics_figure([], [], [])
        try:
            self.assertEqual(len(figure.axes), 4)
            self.assertEqual(
                figure.axes[0].get_title(loc="left"),
                "Borrowing by category",
            )
            self.assertEqual(
                borrowing_analytics([])["overdue_count"],
                0,
            )
        finally:
            figure.clear()

    def test_analytics_calculate_category_month_and_overdue_counts(self) -> None:
        loans = [
            {
                "title": "Python Basics",
                "category": "Programming",
                "issue_date": "2026-05-01",
                "return_date": "2026-05-04",
                "is_overdue": 0,
            },
            {
                "title": "Python Basics",
                "category": "Programming",
                "issue_date": "2026-05-15",
                "return_date": None,
                "is_overdue": 1,
            },
        ]
        summary = borrowing_analytics(loans)
        figure = build_analytics_figure(
            loans,
            [
                {
                    "category": "Programming",
                    "total_quantity": 4,
                    "available_quantity": 2,
                }
            ],
            [{"amount": 10.0, "payment_status": "unpaid"}],
        )
        try:
            self.assertEqual(summary["popular_books"].iloc[0]["borrow_count"], 2)
            self.assertEqual(summary["monthly_issues"].iloc[0]["issue_count"], 2)
            self.assertEqual(summary["monthly_returns"].iloc[0]["return_count"], 1)
            self.assertEqual(summary["overdue_count"], 1)
            self.assertEqual(len(figure.axes), 4)
            self.assertEqual(len(figure.axes[2].patches), 2)
            self.assertGreaterEqual(len(figure.axes[3].patches), 1)
        finally:
            figure.clear()


if __name__ == "__main__":
    unittest.main()
