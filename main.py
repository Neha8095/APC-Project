"""Application entry point for the Smart Library Management System."""

import tkinter as tk
from tkinter import messagebox

from database import initialize_database
from gui.login import LoginScreen
from gui.main_window import LibraryWindow
from models.entities import User
from services.auth_service import AuthService
from services.library_service import LibraryService
from utils.logging_config import configure_logging


def main() -> None:
    """Initialize local storage and start the sign-in or first-run setup screen."""
    configure_logging()
    database_path = initialize_database()
    service = LibraryService(database_path)
    auth_service = AuthService(str(database_path))

    root = tk.Tk()
    root.title("Smart Library Management System")
    root.geometry("1100x720")
    root.minsize(900, 600)
    root.state("zoomed")

    login = None

    def on_login(user: User) -> None:
        nonlocal login
        if login is not None:
            login.destroy()
        LibraryWindow(root, user, service)

    login = LoginScreen(root, auth_service, on_login)
    login.pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as error:
        messagebox.showerror("Application startup failed", str(error))
        raise
