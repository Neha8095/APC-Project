"""Streaming catalogue import and CSV/JSON report export."""

import csv
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from config.settings import DATE_FORMAT, REPORTS_DIRECTORY
from database.connection import get_connection
from utils.exceptions import PermissionDeniedError, ValidationError
from utils.validation import positive_or_zero_integer, required_text, validate_isbn

BOOK_COLUMNS = {
    "isbn",
    "title",
    "author",
    "total_quantity",
}
EXPORT_COLUMNS = {
    "books": (
        "book_id", "isbn", "title", "author", "publisher", "category",
        "publication_year", "total_quantity", "available_quantity",
    ),
    "members": ("member_id", "name", "email", "phone", "registered_on"),
    "loans": (
        "loan_id", "book_id", "title", "isbn", "member_id", "member_name",
        "issue_date", "due_date", "return_date", "status", "is_overdue",
        "estimated_fine",
    ),
    "fines": (
        "fine_id", "loan_id", "title", "member_name", "amount",
        "payment_status", "assessed_on", "paid_at",
    ),
}


class FileService:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self.reports_directory = REPORTS_DIRECTORY

    @staticmethod
    def _require_librarian(user: Any) -> None:
        if user is None or getattr(user, "role", None) != "librarian":
            raise PermissionDeniedError("A signed-in librarian is required.")

    def import_books(
        self, user: Any, file_path: str | Path
    ) -> dict[str, Any]:
        self._require_librarian(user)
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return self._import_csv(path)
        if suffix == ".xlsx":
            return self._import_excel(path)
        if suffix == ".json":
            return self._import_json(path)
        raise ValidationError("Choose a CSV, JSON, or .xlsx Excel file.")

    def _import_excel(self, path: Path) -> dict[str, Any]:
        try:
            from openpyxl import load_workbook
        except ImportError as error:
            raise ValidationError(
                "Excel import requires openpyxl. Install project requirements first."
            ) from error
        result = {"successful": 0, "rejected": 0, "errors": [], "_seen": set()}
        try:
            workbook = load_workbook(path, read_only=True, data_only=True)
            try:
                if not workbook.worksheets:
                    raise ValidationError("The Excel workbook does not contain a worksheet.")
                sheet = workbook.worksheets[0]
                iterator = sheet.iter_rows(values_only=True)
                header_row = next(iterator, None)
                headers = [
                    str(value).strip().lower() if value is not None else ""
                    for value in (header_row or ())
                ]
                nonempty_headers = [header for header in headers if header]
                if len(nonempty_headers) != len(set(nonempty_headers)):
                    raise ValidationError("The spreadsheet contains duplicate columns.")
                missing = BOOK_COLUMNS - set(headers)
                if missing:
                    raise ValidationError(
                        "Missing required spreadsheet columns: "
                        + ", ".join(sorted(missing))
                    )
                for row_number, values in enumerate(iterator, start=2):
                    normalized = {
                        header: ("" if value is None else value)
                        for header, value in zip(headers, values)
                        if header
                    }
                    self._record_import_row(result, row_number, normalized)
            finally:
                workbook.close()
        except ValidationError:
            raise
        except Exception as error:
            raise ValidationError(f"Could not read Excel file: {error}") from error
        result.pop("_seen")
        return result

    def _import_csv(self, path: Path) -> dict[str, Any]:
        result = {"successful": 0, "rejected": 0, "errors": [], "_seen": set()}
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as file:
                reader = csv.DictReader(file)
                normalized_headers = [
                    str(name).strip().lower()
                    for name in (reader.fieldnames or [])
                    if name is not None
                ]
                nonempty_headers = [header for header in normalized_headers if header]
                if len(nonempty_headers) != len(set(nonempty_headers)):
                    raise ValidationError("The CSV file contains duplicate columns.")
                headers = set(normalized_headers)
                missing = BOOK_COLUMNS - headers
                if missing:
                    raise ValidationError(
                        "Missing required CSV columns: " + ", ".join(sorted(missing))
                    )
                for row_number, raw_row in enumerate(reader, start=2):
                    if None in raw_row:
                        result["rejected"] += 1
                        result["errors"].append(
                            f"Row {row_number}: contains more values than the header."
                        )
                        continue
                    normalized = {
                        (key or "").strip().lower(): (
                            "" if value is None else str(value).strip()
                        )
                        for key, value in raw_row.items()
                    }
                    self._record_import_row(result, row_number, normalized)
        except OSError as error:
            raise ValidationError(f"Could not read import file: {error}") from error
        except UnicodeError as error:
            raise ValidationError("The import file must be UTF-8 encoded.") from error
        result.pop("_seen")
        return result

    def _import_json(self, path: Path) -> dict[str, Any]:
        result = {"successful": 0, "rejected": 0, "errors": [], "_seen": set()}
        try:
            with path.open("r", encoding="utf-8") as file:
                records = json.load(file)
        except (OSError, json.JSONDecodeError, UnicodeError) as error:
            raise ValidationError(f"Could not read JSON import file: {error}") from error
        if not isinstance(records, list):
            raise ValidationError("JSON import must contain a list of book objects.")
        for row_number, raw_row in enumerate(records, start=1):
            if not isinstance(raw_row, dict):
                result["rejected"] += 1
                result["errors"].append(f"Row {row_number}: expected a JSON object.")
                continue
            normalized = {str(key).strip().lower(): value for key, value in raw_row.items()}
            self._record_import_row(result, row_number, normalized)
        result.pop("_seen")
        return result

    def _record_import_row(
        self, result: dict[str, Any], row_number: int, row: dict[str, Any]
    ) -> None:
        try:
            isbn = validate_isbn(str(row.get("isbn") or ""))
            isbn_key = isbn.casefold()
            if isbn_key in result["_seen"]:
                raise ValidationError(f"Duplicate ISBN {isbn} in this import file.")
            title = required_text(str(row.get("title") or ""), "Title")
            author = required_text(str(row.get("author") or ""), "Author")
            total = positive_or_zero_integer(row.get("total_quantity"), "Total quantity")
            year_text = str(row.get("publication_year", "") or "").strip()
            year = positive_or_zero_integer(year_text, "Publication year") if year_text else None
            if year is not None and year > 9999:
                raise ValidationError("Publication year must be at most four digits.")
            publisher = str(row.get("publisher", "") or "").strip()
            category = str(row.get("category", "") or "").strip()
            result["_seen"].add(isbn_key)
            with get_connection(self.database_path) as connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT book_id FROM books WHERE isbn = ? COLLATE NOCASE", (isbn,)
                ).fetchone()
                if existing:
                    connection.execute(
                        """
                        UPDATE books SET title = ?, author = ?, publisher = ?,
                            category = ?, publication_year = ?
                        WHERE book_id = ?
                        """,
                        (title, author, publisher, category, year, existing["book_id"]),
                    )
                else:
                    connection.execute(
                        """
                        INSERT INTO books
                            (isbn, title, author, publisher, category, publication_year,
                             total_quantity, available_quantity)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (isbn, title, author, publisher, category, year, total, total),
                    )
            result["successful"] += 1
        except (ValidationError, sqlite3.IntegrityError) as error:
            result["rejected"] += 1
            result["errors"].append(f"Row {row_number}: {error}")

    def export_report(
        self,
        user: Any,
        report_type: str,
        rows: Iterable[dict[str, Any]],
        file_format: str = "csv",
        destination: str | Path | None = None,
    ) -> Path:
        self._require_librarian(user)
        report_type = report_type.strip().lower()
        file_format = file_format.strip().lower()
        if report_type not in EXPORT_COLUMNS:
            raise ValidationError("Unknown report type.")
        if file_format not in {"csv", "json"}:
            raise ValidationError("Choose CSV or JSON as the export format.")
        output = Path(destination) if destination else (
            self.reports_directory
            / f"{report_type}_{date.today().strftime(DATE_FORMAT)}.{file_format}"
        )
        try:
            data = [
                {key: row.get(key, "") for key in EXPORT_COLUMNS[report_type]}
                for row in rows
            ]
            output.parent.mkdir(parents=True, exist_ok=True)
            if file_format == "json":
                with output.open("w", encoding="utf-8") as file:
                    json.dump(data, file, indent=2, ensure_ascii=False, default=str)
            else:
                with output.open("w", newline="", encoding="utf-8-sig") as file:
                    writer = csv.DictWriter(file, fieldnames=EXPORT_COLUMNS[report_type])
                    writer.writeheader()
                    writer.writerows(data)
        except (AttributeError, OSError, TypeError, ValueError) as error:
            raise ValidationError(f"Could not export report: {error}") from error
        return output
