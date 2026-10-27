"""Authentication and first-run librarian setup."""

import sqlite3

from database.connection import get_connection
from models.entities import Librarian, User
from utils.exceptions import AuthenticationError, ValidationError
from utils.security import hash_password, verify_password
from utils.validation import required_text


class AuthService:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def needs_setup(self) -> bool:
        with get_connection(self.database_path) as connection:
            return connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None

    def create_first_librarian(self, username: str, password: str) -> Librarian:
        clean_username = required_text(username, "Username")
        if len(clean_username) < 3:
            raise ValidationError("Username must contain at least 3 characters.")
        encoded = hash_password(password)
        try:
            with get_connection(self.database_path) as connection:
                if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                    raise ValidationError("Initial setup has already been completed.")
                cursor = connection.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'librarian')",
                    (clean_username, encoded),
                )
                user_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as error:
            raise ValidationError("That username is already in use.") from error
        return Librarian(user_id, clean_username, "librarian")

    def login(self, username: str, password: str) -> User:
        with get_connection(self.database_path) as connection:
            row = connection.execute(
                "SELECT user_id, username, password_hash, role FROM users "
                "WHERE username = ? COLLATE NOCASE",
                (username.strip(),),
            ).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            raise AuthenticationError("Incorrect username or password.")
        if row["role"] != "librarian":
            raise AuthenticationError(
                "This desktop interface is for librarian accounts. "
                "Member access is not available in this version."
            )
        return Librarian(int(row["user_id"]), row["username"], row["role"])
