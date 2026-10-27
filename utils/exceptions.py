"""Application-specific errors shown safely to users."""


class LibraryError(Exception):
    """Base class for expected library-operation errors."""


class ValidationError(LibraryError):
    """Raised when user-provided data is invalid."""


class NotFoundError(LibraryError):
    """Raised when the requested database record does not exist."""


class AuthenticationError(LibraryError):
    """Raised when sign-in fails."""


class PermissionDeniedError(LibraryError):
    """Raised when the user lacks permission for an operation."""


class InventoryError(LibraryError):
    """Raised when an inventory or loan rule prevents an operation."""
