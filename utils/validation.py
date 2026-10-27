"""Reusable input validation helpers."""

import math
import re

from utils.exceptions import ValidationError

EMAIL_PATTERN = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"^[0-9+() .-]{7,20}$")
ISBN_PATTERN = re.compile(r"^(?:97[89])?[0-9Xx -]{10,17}$")


def required_text(value: str, label: str) -> str:
    result = value.strip()
    if not result:
        raise ValidationError(f"{label} is required.")
    return result


def validate_email(value: str) -> str:
    result = required_text(value, "Email")
    if not EMAIL_PATTERN.fullmatch(result):
        raise ValidationError("Enter a valid email address.")
    return result.lower()


def validate_phone(value: str) -> str:
    result = required_text(value, "Phone number")
    if not PHONE_PATTERN.fullmatch(result):
        raise ValidationError("Enter a valid phone number.")
    return result


def validate_isbn(value: str) -> str:
    result = required_text(value, "ISBN").replace("-", "").replace(" ", "")
    if not ISBN_PATTERN.fullmatch(result):
        raise ValidationError("Enter an ISBN-10 or ISBN-13 value.")
    return result


def positive_or_zero_integer(value: object, label: str) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError
        if isinstance(value, float):
            if not math.isfinite(value) or not value.is_integer():
                raise ValueError
            result = int(value)
        else:
            result = int(str(value).strip())
    except (TypeError, ValueError, OverflowError) as error:
        raise ValidationError(f"{label} must be a whole number.") from error
    if result < 0:
        raise ValidationError(f"{label} cannot be negative.")
    return result
