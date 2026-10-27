"""Tests for authentication, loans, fines, and file import rules."""

import csv
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import date, timedelta
from pathlib import Path

from database.connection import get_connection
from models.entities import Librarian
from services.auth_service import AuthService
from services.file_service import FileService
from services.library_service import LibraryService
from utils.exceptions import (
    AuthenticationError,
    InventoryError,
    PermissionDeniedError,
    ValidationError,
)


class LibraryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "library.db"
        self.service = LibraryService(self.database_path)
        self.user = Librarian(1, "librarian", "librarian")
        self.book_id = self.service.add_book(
            self.user,
            {
                "isbn": "9780000000001",
                "title": "Test Book",
                "author": "Test Author",
                "publisher": "",
                "category": "Computing",
                "publication_year": "2020",
                "total_quantity": "1",
            },
        )
        self.member_id = self.service.add_member(
            self.user,
            {
                "name": "Test Member",
                "email": "reader@example.com",
                "phone": "1234567890",
            },
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_issue_decrements_inventory_and_return_restores_it(self) -> None:
        loan_id = self.service.issue_book(self.user, self.book_id, self.member_id)
        self.assertEqual(self.service.list_books()[0]["available_quantity"], 0)
        self.assertEqual(self.service.list_loans(active_only=True)[0]["loan_id"], loan_id)

        fine = self.service.return_book(self.user, loan_id)

        self.assertEqual(fine, 0)
        self.assertEqual(self.service.list_books()[0]["available_quantity"], 1)
        self.assertEqual(self.service.list_loans(active_only=True), [])

    def test_cannot_issue_when_no_copies_are_available(self) -> None:
        self.service.issue_book(self.user, self.book_id, self.member_id)
        with self.assertRaises(InventoryError):
            self.service.issue_book(self.user, self.book_id, self.member_id)

    def test_late_return_records_fine_and_duplicate_return_fails(self) -> None:
        self.service.update_settings(self.user, 1, 5.0)
        old_issue_date = (date.today() - timedelta(days=4)).strftime("%Y-%m-%d")
        loan_id = self.service.issue_book(
            self.user, self.book_id, self.member_id, old_issue_date
        )
        self.assertEqual(self.service.list_loans(active_only=True)[0]["estimated_fine"], 15.0)
        self.assertEqual(self.service.dashboard_statistics()["outstanding_fines"], 15.0)

        fine = self.service.return_book(self.user, loan_id)

        self.assertEqual(fine, 15.0)
        self.assertEqual(self.service.list_fines()[0]["amount"], 15.0)
        self.assertEqual(self.service.dashboard_statistics()["outstanding_fines"], 15.0)
        with self.assertRaises(InventoryError):
            self.service.return_book(self.user, loan_id)

    def test_concurrent_issues_cannot_overdraw_inventory(self) -> None:
        barrier = Barrier(2)

        def issue() -> int | InventoryError:
            barrier.wait()
            try:
                return self.service.issue_book(self.user, self.book_id, self.member_id)
            except InventoryError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: issue(), range(2)))

        self.assertEqual(sum(isinstance(result, int) for result in results), 1)
        self.assertEqual(sum(isinstance(result, InventoryError) for result in results), 1)
        self.assertEqual(self.service.list_books()[0]["available_quantity"], 0)
        self.assertEqual(len(self.service.list_loans(active_only=True)), 1)

    def test_concurrent_returns_restore_inventory_only_once(self) -> None:
        loan_id = self.service.issue_book(self.user, self.book_id, self.member_id)
        barrier = Barrier(2)

        def return_loan() -> float | InventoryError:
            barrier.wait()
            try:
                return self.service.return_book(self.user, loan_id)
            except InventoryError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: return_loan(), range(2)))

        self.assertEqual(sum(isinstance(result, float) for result in results), 1)
        self.assertEqual(sum(isinstance(result, InventoryError) for result in results), 1)
        self.assertEqual(self.service.list_books()[0]["available_quantity"], 1)
        self.assertEqual(self.service.list_loans(active_only=True), [])

    def test_return_rolls_back_loan_state_when_inventory_is_inconsistent(self) -> None:
        loan_id = self.service.issue_book(self.user, self.book_id, self.member_id)
        with get_connection(self.database_path) as connection:
            connection.execute(
                "UPDATE books SET available_quantity = total_quantity WHERE book_id = ?",
                (self.book_id,),
            )

        with self.assertRaises(InventoryError):
            self.service.return_book(self.user, loan_id)

        self.assertEqual(self.service.list_loans(active_only=True)[0]["loan_id"], loan_id)
        with get_connection(self.database_path) as connection:
            connection.execute(
                "UPDATE books SET available_quantity = 0 WHERE book_id = ?",
                (self.book_id,),
            )
        self.assertEqual(self.service.return_book(self.user, loan_id), 0)

    def test_book_quantity_edits_preserve_outstanding_copies(self) -> None:
        self.service.issue_book(self.user, self.book_id, self.member_id)
        data = {
            "isbn": "9780000000001",
            "title": "Test Book",
            "author": "Test Author",
            "publisher": "",
            "category": "Computing",
            "publication_year": "2020",
            "total_quantity": "3",
        }
        self.service.update_book(self.user, self.book_id, data)
        book = self.service.list_books()[0]
        self.assertEqual((book["total_quantity"], book["available_quantity"]), (3, 2))

        data["total_quantity"] = "0"
        with self.assertRaises(InventoryError):
            self.service.update_book(self.user, self.book_id, data)
        book = self.service.list_books()[0]
        self.assertEqual((book["total_quantity"], book["available_quantity"]), (3, 2))

    def test_issue_and_return_dates_are_checked_before_inventory_changes(self) -> None:
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        with self.assertRaises(ValidationError):
            self.service.issue_book(self.user, self.book_id, self.member_id, tomorrow)
        self.assertEqual(self.service.list_books()[0]["available_quantity"], 1)

        issue_date = date.today().strftime("%Y-%m-%d")
        loan_id = self.service.issue_book(
            self.user, self.book_id, self.member_id, issue_date
        )
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        with self.assertRaises(ValidationError):
            self.service.return_book(self.user, loan_id, yesterday)
        self.assertEqual(self.service.list_books()[0]["available_quantity"], 0)
        self.assertEqual(len(self.service.list_loans(active_only=True)), 1)

    def test_member_update_validates_fields_and_unique_email(self) -> None:
        other_member = self.service.add_member(
            self.user,
            {"name": "Other", "email": "other@example.com", "phone": "1234567890"},
        )
        with self.assertRaises(ValidationError):
            self.service.update_member(
                self.user,
                other_member,
                {"name": "Other", "email": "reader@example.com", "phone": "1234567890"},
            )
        self.service.update_member(
            self.user,
            other_member,
            {"name": "  Updated  ", "email": "UPDATED@example.com", "phone": "1234567890"},
        )
        member = next(row for row in self.service.list_members() if row["member_id"] == other_member)
        self.assertEqual(member["name"], "Updated")
        self.assertEqual(member["email"], "updated@example.com")

    def test_fine_rate_must_be_finite(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.update_settings(self.user, 14, float("nan"))

    def test_non_librarian_cannot_change_library_records(self) -> None:
        from models.entities import User

        with self.assertRaises(PermissionDeniedError):
            self.service.add_book(
                User(2, "reader", "member"),
                {
                    "isbn": "9780000000002",
                    "title": "Restricted",
                    "author": "Author",
                    "total_quantity": 1,
                },
            )


class AuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "auth.db"
        self.auth = AuthService(str(self.database_path))
        from database.connection import initialize_database

        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_first_setup_and_login_use_password_hash(self) -> None:
        self.assertTrue(self.auth.needs_setup())
        self.auth.create_first_librarian("librarian", "correct-horse-battery")
        self.assertFalse(self.auth.needs_setup())
        user = self.auth.login("LIBRARIAN", "correct-horse-battery")
        self.assertEqual(user.role, "librarian")
        with self.assertRaises(AuthenticationError):
            self.auth.login("librarian", "wrong-password")


class FileServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "imports.db"
        self.service = LibraryService(self.database_path)
        self.files = FileService(self.database_path)
        self.user = Librarian(1, "librarian", "librarian")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_csv_import_rejects_duplicate_isbn_and_preserves_existing_quantity(self) -> None:
        with tempfile.TemporaryDirectory() as import_directory:
            csv_path = Path(import_directory) / "books.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=[
                        "isbn", "title", "author", "total_quantity",
                        "publisher", "category", "publication_year",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "isbn": "9780000000001",
                        "title": "Original",
                        "author": "Author",
                        "total_quantity": 5,
                    }
                )
                writer.writerow(
                    {
                        "isbn": "9780000000001",
                        "title": "Duplicate row",
                        "author": "Author",
                        "total_quantity": 50,
                    }
                )

            result = self.files.import_books(self.user, csv_path)

        self.assertEqual(result["successful"], 1)
        self.assertEqual(result["rejected"], 1)
        book = self.service.list_books()[0]
        self.assertEqual(book["total_quantity"], 5)
        self.assertEqual(book["title"], "Original")

    def test_json_import_normalizes_isbn_and_accepts_integral_quantities(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as import_directory:
            json_path = Path(import_directory) / "books.json"
            json_path.write_text(
                json.dumps(
                    [
                        {
                            "isbn": "978-000-0000001",
                            "title": "Imported",
                            "author": "Author",
                            "total_quantity": 2.0,
                        },
                        {
                            "isbn": "9780000000001",
                            "title": "Duplicate",
                            "author": "Author",
                            "total_quantity": 5,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            result = self.files.import_books(self.user, json_path)

        self.assertEqual((result["successful"], result["rejected"]), (1, 1))
        self.assertEqual(self.service.list_books()[0]["total_quantity"], 2)
        self.assertIn("Duplicate ISBN", result["errors"][0])

    def test_csv_extra_values_are_reported_without_aborting_import(self) -> None:
        with tempfile.TemporaryDirectory() as import_directory:
            csv_path = Path(import_directory) / "books.csv"
            csv_path.write_text(
                "isbn,title,author,total_quantity\n"
                "9780000000001,Malformed,Author,1,unexpected\n"
                "9780000000002,Valid,Author,2\n",
                encoding="utf-8",
            )
            result = self.files.import_books(self.user, csv_path)

        self.assertEqual(result["successful"], 1)
        self.assertEqual(result["rejected"], 1)
        self.assertIn("more values than the header", result["errors"][0])
        self.assertEqual(self.service.list_books()[0]["title"], "Valid")

    def test_excel_import_streams_more_than_one_thousand_records(self) -> None:
        from openpyxl import Workbook

        with tempfile.TemporaryDirectory() as import_directory:
            excel_path = Path(import_directory) / "catalogue.xlsx"
            workbook = Workbook(write_only=True)
            sheet = workbook.create_sheet("Books")
            sheet.append(
                ["isbn", "title", "author", "total_quantity", "publisher", "category"]
            )
            for index in range(1001):
                sheet.append(
                    [
                        f"978{index:010d}",
                        f"Book {index}",
                        "Author",
                        2,
                        "",
                        "Computing",
                    ]
                )
            workbook.save(excel_path)

            result = self.files.import_books(self.user, excel_path)

        self.assertEqual(result["successful"], 1001)
        self.assertEqual(result["rejected"], 0)
        self.assertEqual(len(self.service.list_books()), 1001)

    def test_csv_and_json_exports_write_records(self) -> None:
        with tempfile.TemporaryDirectory() as output_directory:
            csv_path = Path(output_directory) / "books.csv"
            json_path = Path(output_directory) / "books.json"
            record = {
                "isbn": "9780000000001",
                "title": "Exported",
                "unexpected": "not included in the report schema",
            }
            self.files.export_report(
                self.user, "books", [record], "csv", destination=csv_path
            )
            self.files.export_report(
                self.user, "books", [record], "json", destination=json_path
            )

            with csv_path.open(encoding="utf-8-sig", newline="") as file:
                exported_csv = list(csv.DictReader(file))
            import json

            exported_json = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertEqual(exported_csv[0]["title"], "Exported")
        self.assertEqual(exported_json[0]["title"], "Exported")
        self.assertNotIn("unexpected", exported_json[0])
        self.assertEqual(
            set(exported_json[0]),
            {
                "book_id", "isbn", "title", "author", "publisher", "category",
                "publication_year", "total_quantity", "available_quantity",
            },
        )


if __name__ == "__main__":
    unittest.main()
