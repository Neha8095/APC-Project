"""Library business rules and transactional database operations."""

import logging
import math
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from config.settings import (
    DATABASE_PATH,
    DEFAULT_FINE_PER_DAY,
    DEFAULT_LOAN_PERIOD_DAYS,
    DATE_FORMAT,
)
from database.connection import get_connection, initialize_database
from utils.exceptions import (
    InventoryError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from utils.validation import (
    positive_or_zero_integer,
    required_text,
    validate_email,
    validate_isbn,
    validate_phone,
)

logger = logging.getLogger(__name__)


def _date_value(value: str, label: str) -> date:
    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except (TypeError, ValueError) as error:
        raise ValidationError(f"{label} must use YYYY-MM-DD format.") from error


class LibraryService:
    def __init__(self, database_path: str | Path = DATABASE_PATH) -> None:
        self.database_path = str(initialize_database(database_path))
        self._initialize_settings()

    def _initialize_settings(self) -> None:
        with get_connection(self.database_path) as connection:
            connection.executemany(
                "INSERT OR IGNORE INTO settings (setting_key, setting_value) VALUES (?, ?)",
                [
                    ("loan_period_days", str(DEFAULT_LOAN_PERIOD_DAYS)),
                    ("fine_per_day", str(DEFAULT_FINE_PER_DAY)),
                ],
            )

    def _require_librarian(self, user: Any) -> None:
        if user is None or getattr(user, "role", None) != "librarian":
            raise PermissionDeniedError("A signed-in librarian is required.")

    def _rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with get_connection(self.database_path) as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def list_books(self, search: str = "") -> list[dict[str, Any]]:
        term = f"%{search.strip()}%"
        return self._rows(
            """
            SELECT * FROM books
            WHERE isbn LIKE ? OR title LIKE ? OR author LIKE ? OR category LIKE ?
            ORDER BY title COLLATE NOCASE
            """,
            (term, term, term, term),
        )

    def add_book(self, user: Any, data: dict[str, Any]) -> int:
        self._require_librarian(user)
        isbn = validate_isbn(str(data.get("isbn", "")))
        title = required_text(str(data.get("title", "")), "Title")
        author = required_text(str(data.get("author", "")), "Author")
        publisher = str(data.get("publisher", "")).strip()
        category = str(data.get("category", "")).strip()
        total = positive_or_zero_integer(data.get("total_quantity"), "Total quantity")
        year_text = str(data.get("publication_year", "")).strip()
        year = positive_or_zero_integer(year_text, "Publication year") if year_text else None
        if year is not None and year > 9999:
            raise ValidationError("Publication year must be at most four digits.")
        try:
            with get_connection(self.database_path) as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO books
                        (isbn, title, author, publisher, category, publication_year,
                         total_quantity, available_quantity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (isbn, title, author, publisher, category, year, total, total),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as error:
            raise ValidationError(f"Could not add book: {error}") from error

    def update_book(self, user: Any, book_id: int, data: dict[str, Any]) -> None:
        self._require_librarian(user)
        total = positive_or_zero_integer(data.get("total_quantity"), "Total quantity")
        year_text = str(data.get("publication_year", "")).strip()
        year = positive_or_zero_integer(year_text, "Publication year") if year_text else None
        if year is not None and year > 9999:
            raise ValidationError("Publication year must be at most four digits.")
        try:
            with get_connection(self.database_path) as connection:
                connection.execute("BEGIN IMMEDIATE")
                old = connection.execute(
                    "SELECT total_quantity, available_quantity FROM books WHERE book_id = ?",
                    (book_id,),
                ).fetchone()
                if old is None:
                    raise NotFoundError("Book not found.")
                checked_out = old["total_quantity"] - old["available_quantity"]
                if total < checked_out:
                    raise InventoryError(
                        f"Total quantity cannot be below {checked_out} currently issued copies."
                    )
                available = total - checked_out
                connection.execute(
                    """
                    UPDATE books
                    SET isbn = ?, title = ?, author = ?, publisher = ?, category = ?,
                        publication_year = ?, total_quantity = ?, available_quantity = ?
                    WHERE book_id = ?
                    """,
                    (
                        validate_isbn(str(data.get("isbn", ""))),
                        required_text(str(data.get("title", "")), "Title"),
                        required_text(str(data.get("author", "")), "Author"),
                        str(data.get("publisher", "")).strip(),
                        str(data.get("category", "")).strip(),
                        year,
                        total,
                        available,
                        book_id,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ValidationError(f"Could not update book: {error}") from error

    def delete_book(self, user: Any, book_id: int) -> None:
        self._require_librarian(user)
        try:
            with get_connection(self.database_path) as connection:
                cursor = connection.execute("DELETE FROM books WHERE book_id = ?", (book_id,))
                if cursor.rowcount == 0:
                    raise NotFoundError("Book not found.")
        except sqlite3.IntegrityError as error:
            raise InventoryError("A book with loan history cannot be deleted.") from error

    def list_members(self, search: str = "") -> list[dict[str, Any]]:
        term = f"%{search.strip()}%"
        return self._rows(
            """
            SELECT * FROM members
            WHERE name LIKE ? OR email LIKE ? OR phone LIKE ?
            ORDER BY name COLLATE NOCASE
            """,
            (term, term, term),
        )

    def add_member(self, user: Any, data: dict[str, Any]) -> int:
        self._require_librarian(user)
        name = required_text(str(data.get("name", "")), "Name")
        email = validate_email(str(data.get("email", "")))
        phone = validate_phone(str(data.get("phone", "")))
        registered = date.today().strftime(DATE_FORMAT)
        try:
            with get_connection(self.database_path) as connection:
                cursor = connection.execute(
                    "INSERT INTO members (name, email, phone, registered_on) VALUES (?, ?, ?, ?)",
                    (name, email, phone, registered),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as error:
            raise ValidationError(f"Could not add member: {error}") from error

    def update_member(self, user: Any, member_id: int, data: dict[str, Any]) -> None:
        self._require_librarian(user)
        try:
            with get_connection(self.database_path) as connection:
                cursor = connection.execute(
                    "UPDATE members SET name = ?, email = ?, phone = ? WHERE member_id = ?",
                    (
                        required_text(str(data.get("name", "")), "Name"),
                        validate_email(str(data.get("email", ""))),
                        validate_phone(str(data.get("phone", ""))),
                        member_id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError("Member not found.")
        except sqlite3.IntegrityError as error:
            raise ValidationError(f"Could not update member: {error}") from error

    def delete_member(self, user: Any, member_id: int) -> None:
        self._require_librarian(user)
        try:
            with get_connection(self.database_path) as connection:
                cursor = connection.execute(
                    "DELETE FROM members WHERE member_id = ?", (member_id,)
                )
                if cursor.rowcount == 0:
                    raise NotFoundError("Member not found.")
        except sqlite3.IntegrityError as error:
            raise InventoryError("A member with loan history cannot be deleted.") from error

    def issue_book(
        self, user: Any, book_id: int, member_id: int, issue_date: str | None = None
    ) -> int:
        self._require_librarian(user)
        today = date.today()
        issue = _date_value(issue_date, "Issue date") if issue_date else today
        if issue > today:
            raise ValidationError("Issue date cannot be in the future.")
        try:
            with get_connection(self.database_path) as connection:
                connection.execute("BEGIN IMMEDIATE")
                period_row = connection.execute(
                    "SELECT setting_value FROM settings WHERE setting_key = ?",
                    ("loan_period_days",),
                ).fetchone()
                if period_row is None:
                    raise NotFoundError("Setting 'loan_period_days' not found.")
                try:
                    period = int(period_row["setting_value"])
                except (TypeError, ValueError) as error:
                    raise ValidationError("Loan period setting is invalid.") from error
                due = issue + timedelta(days=period)
                book = connection.execute(
                    "SELECT available_quantity FROM books WHERE book_id = ?", (book_id,)
                ).fetchone()
                if book is None:
                    raise NotFoundError("Book not found.")
                member = connection.execute(
                    "SELECT 1 FROM members WHERE member_id = ?", (member_id,)
                ).fetchone()
                if member is None:
                    raise NotFoundError("Member not found.")
                changed = connection.execute(
                    "UPDATE books SET available_quantity = available_quantity - 1 "
                    "WHERE book_id = ? AND available_quantity > 0",
                    (book_id,),
                ).rowcount
                if changed != 1:
                    raise InventoryError("No copies of this book are currently available.")
                cursor = connection.execute(
                    """
                    INSERT INTO loans (book_id, member_id, issue_date, due_date)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        book_id,
                        member_id,
                        issue.strftime(DATE_FORMAT),
                        due.strftime(DATE_FORMAT),
                    ),
                )
                return int(cursor.lastrowid)
        except sqlite3.Error:
            logger.exception("Book issue failed")
            raise

    def return_book(
        self, user: Any, loan_id: int, return_date: str | None = None
    ) -> float:
        self._require_librarian(user)
        returned = _date_value(return_date, "Return date") if return_date else date.today()
        if returned > date.today():
            raise ValidationError("Return date cannot be in the future.")
        with get_connection(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            rate_row = connection.execute(
                "SELECT setting_value FROM settings WHERE setting_key = ?",
                ("fine_per_day",),
            ).fetchone()
            if rate_row is None:
                raise NotFoundError("Setting 'fine_per_day' not found.")
            try:
                rate = float(rate_row["setting_value"])
            except (TypeError, ValueError) as error:
                raise ValidationError("Fine rate setting is invalid.") from error
            loan = connection.execute(
                "SELECT * FROM loans WHERE loan_id = ?", (loan_id,)
            ).fetchone()
            if loan is None:
                raise NotFoundError("Loan not found.")
            if loan["status"] == "returned":
                raise InventoryError("This loan has already been returned.")
            if returned < _date_value(loan["issue_date"], "Stored issue date"):
                raise ValidationError("Return date cannot be before the issue date.")
            late_days = max(
                0, (returned - _date_value(loan["due_date"], "Stored due date")).days
            )
            fine = round(late_days * rate, 2)
            changed = connection.execute(
                "UPDATE loans SET return_date = ?, status = 'returned' "
                "WHERE loan_id = ? AND status = 'issued'",
                (returned.strftime(DATE_FORMAT), loan_id),
            ).rowcount
            if changed != 1:
                raise InventoryError("This loan has already been returned.")
            changed = connection.execute(
                "UPDATE books SET available_quantity = available_quantity + 1 "
                "WHERE book_id = ? AND available_quantity < total_quantity",
                (loan["book_id"],),
            ).rowcount
            if changed != 1:
                raise InventoryError("Inventory is inconsistent; return was not processed.")
            if fine > 0:
                connection.execute(
                    """
                    INSERT INTO fines (loan_id, amount, assessed_on)
                    VALUES (?, ?, ?)
                    """,
                    (loan_id, fine, returned.strftime(DATE_FORMAT)),
                )
        return fine

    def list_loans(self, active_only: bool = False) -> list[dict[str, Any]]:
        condition = "WHERE l.status = 'issued'" if active_only else ""
        today = date.today().strftime(DATE_FORMAT)
        fine_rate = float(self.get_setting("fine_per_day"))
        return self._rows(
            f"""
            SELECT l.loan_id, l.book_id, b.title, b.isbn, b.category,
                   b.available_quantity, l.member_id, m.name AS member_name,
                   l.issue_date, l.due_date, l.return_date, l.status,
                   CASE WHEN l.status = 'issued' AND l.due_date < ?
                        THEN 1 ELSE 0 END AS is_overdue,
                   CASE WHEN l.status = 'issued' AND l.due_date < ?
                        THEN CAST(julianday(?) - julianday(l.due_date) AS INTEGER) * ?
                        ELSE 0 END AS estimated_fine
            FROM loans l
            JOIN books b ON b.book_id = l.book_id
            JOIN members m ON m.member_id = l.member_id
            {condition}
            ORDER BY l.due_date
            """,
            (today, today, today, fine_rate),
        )

    def list_fines(self) -> list[dict[str, Any]]:
        return self._rows(
            """
            SELECT f.fine_id, f.loan_id, f.amount, f.payment_status, f.assessed_on,
                   f.paid_at, m.name AS member_name, b.title
            FROM fines f
            JOIN loans l ON l.loan_id = f.loan_id
            JOIN members m ON m.member_id = l.member_id
            JOIN books b ON b.book_id = l.book_id
            ORDER BY f.assessed_on DESC
            """
        )

    def mark_fine_paid(self, user: Any, fine_id: int) -> None:
        self._require_librarian(user)
        with get_connection(self.database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE fines SET payment_status = 'paid', paid_at = ?
                WHERE fine_id = ? AND payment_status = 'unpaid'
                """,
                (date.today().strftime(DATE_FORMAT), fine_id),
            )
            if cursor.rowcount == 0:
                raise NotFoundError("Unpaid fine not found.")

    def get_setting(self, key: str) -> str:
        with get_connection(self.database_path) as connection:
            row = connection.execute(
                "SELECT setting_value FROM settings WHERE setting_key = ?", (key,)
            ).fetchone()
        if row is None:
            raise NotFoundError(f"Setting {key!r} not found.")
        return str(row["setting_value"])

    def update_settings(self, user: Any, loan_days: int, fine_per_day: float) -> None:
        self._require_librarian(user)
        try:
            days = int(loan_days)
            numeric_days = float(loan_days)
            rate = float(fine_per_day)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValidationError("Loan period and fine rate must be numeric.") from error
        if isinstance(loan_days, bool) or numeric_days != days:
            raise ValidationError("Loan period must be a whole number of days.")
        if days < 1 or days > 365:
            raise ValidationError("Loan period must be between 1 and 365 days.")
        if not math.isfinite(rate) or rate < 0 or rate > 1_000_000:
            raise ValidationError("Fine rate must be between 0 and 1,000,000.")
        with get_connection(self.database_path) as connection:
            connection.executemany(
                "INSERT INTO settings (setting_key, setting_value) VALUES (?, ?) "
                "ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value",
                [
                    ("loan_period_days", str(days)),
                    ("fine_per_day", f"{rate:.2f}"),
                ],
            )

    def dashboard_statistics(self) -> dict[str, int | float]:
        today = date.today().strftime(DATE_FORMAT)
        with get_connection(self.database_path) as connection:
            books = connection.execute(
                "SELECT COUNT(*) AS titles, COALESCE(SUM(total_quantity), 0) AS copies, "
                "COALESCE(SUM(available_quantity), 0) AS available FROM books"
            ).fetchone()
            members = connection.execute("SELECT COUNT(*) AS count FROM members").fetchone()
            active = connection.execute(
                "SELECT COUNT(*) AS count FROM loans WHERE status = 'issued'"
            ).fetchone()
            overdue = connection.execute(
                "SELECT COUNT(*) AS count FROM loans "
                "WHERE status = 'issued' AND due_date < ?",
                (today,),
            ).fetchone()
            fines = connection.execute(
                "SELECT COALESCE(SUM(amount), 0) AS amount FROM fines "
                "WHERE payment_status = 'unpaid'"
            ).fetchone()
            overdue_dates = connection.execute(
                "SELECT due_date FROM loans WHERE status = 'issued' AND due_date < ?",
                (today,),
            ).fetchall()
        today_date = date.today()
        accrued = sum(
            (today_date - _date_value(row["due_date"], "Stored due date")).days
            for row in overdue_dates
        ) * float(self.get_setting("fine_per_day"))
        return {
            "titles": int(books["titles"]),
            "copies": int(books["copies"]),
            "available": int(books["available"]),
            "issued": int(active["count"]),
            "members": int(members["count"]),
            "overdue": int(overdue["count"]),
            "outstanding_fines": round(float(fines["amount"]) + accrued, 2),
        }
