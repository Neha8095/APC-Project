"""Tests for SQLite database initialization and schema constraints."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database.connection import get_connection, initialize_database


class DatabaseSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "test_library.db"
        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_initialization_creates_all_required_tables(self) -> None:
        with get_connection(self.database_path) as connection:
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }

        self.assertTrue({"users", "books", "members", "loans", "fines"} <= tables)

    def test_foreign_key_enforcement_is_enabled(self) -> None:
        with get_connection(self.database_path) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO loans
                        (book_id, member_id, issue_date, due_date)
                    VALUES (999, 999, '2026-01-01', '2026-01-15')
                    """
                )

    def test_book_quantity_cannot_exceed_total_or_be_negative(self) -> None:
        with get_connection(self.database_path) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO books
                        (isbn, title, author, total_quantity, available_quantity)
                    VALUES ('9780000000001', 'Example', 'Author', 2, 3)
                    """
                )

    def test_isbn_is_unique(self) -> None:
        with get_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO books
                    (isbn, title, author, total_quantity, available_quantity)
                VALUES ('9780000000001', 'First', 'Author', 1, 1)
                """
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO books
                        (isbn, title, author, total_quantity, available_quantity)
                    VALUES ('9780000000001', 'Second', 'Author', 1, 1)
                    """
                )

    def test_issued_loan_cannot_have_return_date(self) -> None:
        with get_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO books
                    (isbn, title, author, total_quantity, available_quantity)
                VALUES ('9780000000001', 'Example', 'Author', 1, 1)
                """
            )
            connection.execute(
                """
                INSERT INTO members (name, email, phone, registered_on)
                VALUES ('Test Member', 'test@example.com', '1234567890', '2026-01-01')
                """
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO loans
                        (book_id, member_id, issue_date, due_date, return_date, status)
                    VALUES (1, 1, '2026-01-01', '2026-01-15', '2026-01-10', 'issued')
                    """
                )


if __name__ == "__main__":
    unittest.main()
