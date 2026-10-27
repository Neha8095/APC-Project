"""Small domain objects used by the service and GUI layers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    user_id: int
    username: str
    role: str


@dataclass(frozen=True)
class Member(User):
    member_id: int
    name: str
    email: str
    phone: str


@dataclass(frozen=True)
class Librarian(User):
    pass


@dataclass(frozen=True)
class Book:
    book_id: int
    isbn: str
    title: str
    author: str
    publisher: str
    category: str
    publication_year: int | None
    total_quantity: int
    available_quantity: int


@dataclass(frozen=True)
class Transaction:
    loan_id: int
    book_id: int
    member_id: int
    issue_date: str
    due_date: str
    return_date: str | None
    status: str
