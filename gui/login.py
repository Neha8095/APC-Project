"""First-run setup and librarian sign-in window."""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from models.entities import User
from services.auth_service import AuthService
from utils.exceptions import LibraryError


class LoginScreen(ttk.Frame):
    def __init__(
        self, master: tk.Misc, auth_service: AuthService, on_login: Callable[[User], None]
    ) -> None:
        style = ttk.Style(master)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Login.TFrame", background="#eaf0f8")
        super().__init__(master, style="Login.TFrame")
        self.auth_service = auth_service
        self.on_login = on_login
        self._build()

    def _build(self) -> None:
        setup = self.auth_service.needs_setup()
        card = tk.Frame(self, bg="#ffffff", highlightbackground="#d7e0ec", highlightthickness=1)
        card.place(relx=0.5, rely=0.49, relwidth=0.78, relheight=0.70, anchor="center")
        card.columnconfigure(0, weight=5, uniform="login-panel")
        card.columnconfigure(1, weight=6, uniform="login-panel")
        card.rowconfigure(0, weight=1)

        hero = tk.Frame(card, bg="#10213d", padx=42, pady=38)
        hero.grid(row=0, column=0, sticky="nsew")
        tk.Label(
            hero,
            text="LIBRARY\nMANAGEMENT",
            bg="#10213d",
            fg="#ffffff",
            font=("Segoe UI", 23, "bold"),
            justify="left",
        ).pack(anchor="w", pady=(10, 14))
        tk.Label(
            hero,
            text="A calmer way to manage your collection, members, and daily circulation.",
            bg="#10213d",
            fg="#cbd8eb",
            font=("Segoe UI", 11),
            justify="left",
            wraplength=340,
        ).pack(anchor="w", pady=(0, 28))

        for title, description in (
            ("01  CATALOGUE", "Find and organize every book in one place."),
            ("02  CIRCULATION", "Track issues, returns, due dates, and fines."),
            ("03  INSIGHTS", "Understand borrowing with clear reports and charts."),
        ):
            item = tk.Frame(hero, bg="#1a3155", padx=13, pady=11)
            item.pack(fill="x", pady=5)
            tk.Label(
                item,
                text=title,
                bg="#1a3155",
                fg="#93c5fd",
                font=("Segoe UI", 9, "bold"),
            ).pack(anchor="w")
            tk.Label(
                item,
                text=description,
                bg="#1a3155",
                fg="#e2e8f0",
                font=("Segoe UI", 9),
                justify="left",
                wraplength=330,
            ).pack(anchor="w", pady=(4, 0))

        tk.Label(
            hero,
            text="SMART LIBRARY  •  DESKTOP EDITION",
            bg="#10213d",
            fg="#8da2c0",
            font=("Segoe UI", 8, "bold"),
        ).pack(side="bottom", anchor="w")

        form_panel = tk.Frame(card, bg="#ffffff", padx=48, pady=38)
        form_panel.grid(row=0, column=1, sticky="nsew")
        form_panel.columnconfigure(0, weight=1)
        tk.Label(
            form_panel,
            text="Welcome back" if not setup else "Get started",
            bg="#ffffff",
            fg="#0f172a",
            font=("Segoe UI", 22, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(8, 4))
        subtitle = (
            "Sign in with your librarian account."
            if not setup
            else "Create the first librarian account to set up your library."
        )
        tk.Label(
            form_panel,
            text=subtitle,
            bg="#ffffff",
            fg="#64748b",
            font=("Segoe UI", 10),
            wraplength=390,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 24))

        tk.Label(
            form_panel,
            text="USERNAME",
            bg="#ffffff",
            fg="#334155",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=2, column=0, sticky="w", pady=(0, 5))
        self.username = tk.Entry(
            form_panel,
            font=("Segoe UI", 11),
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#2563eb",
        )
        self.username.grid(row=3, column=0, sticky="ew", ipady=8, pady=(0, 16))

        tk.Label(
            form_panel,
            text="PASSWORD",
            bg="#ffffff",
            fg="#334155",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=4, column=0, sticky="w", pady=(0, 5))
        self.password = tk.Entry(
            form_panel,
            show="*",
            font=("Segoe UI", 11),
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#2563eb",
        )
        self.password.grid(row=5, column=0, sticky="ew", ipady=8, pady=(0, 14))

        if setup:
            tk.Label(
                form_panel,
                text="CONFIRM PASSWORD",
                bg="#ffffff",
                fg="#334155",
                font=("Segoe UI", 9, "bold"),
            ).grid(row=6, column=0, sticky="w", pady=(0, 5))
            self.confirm = tk.Entry(
                form_panel,
                show="*",
                font=("Segoe UI", 11),
                relief="solid",
                bd=1,
                highlightthickness=1,
                highlightbackground="#cbd5e1",
                highlightcolor="#2563eb",
            )
            self.confirm.grid(row=7, column=0, sticky="ew", ipady=8, pady=(0, 14))
        else:
            self.confirm = None

        self.show_password = tk.BooleanVar(value=False)
        tk.Checkbutton(
            form_panel,
            text="Show password",
            variable=self.show_password,
            command=self._toggle_password,
            bg="#ffffff",
            fg="#475569",
            activebackground="#ffffff",
            selectcolor="#ffffff",
            font=("Segoe UI", 9),
        ).grid(row=8, column=0, sticky="w", pady=(0, 16))

        action_text = "Create librarian account" if setup else "Sign in to library"
        self.submit_button = tk.Button(
            form_panel,
            text=action_text,
            command=lambda: self._submit(setup),
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            pady=11,
        )
        self.submit_button.grid(row=9, column=0, sticky="ew", pady=(0, 14))

        footnote = (
            "Choose a strong password with at least 8 characters."
            if setup
            else "Authorized librarian access only."
        )
        tk.Label(
            form_panel,
            text=footnote,
            bg="#ffffff",
            fg="#64748b",
            font=("Segoe UI", 9),
        ).grid(row=10, column=0, sticky="w")
        self.username.bind("<Return>", lambda _event: self.password.focus_set())
        self.password.bind("<Return>", lambda _event: self._submit(setup))
        if self.confirm is not None:
            self.confirm.bind("<Return>", lambda _event: self._submit(setup))
        self.username.focus_set()

    def _toggle_password(self) -> None:
        show = "" if self.show_password.get() else "*"
        self.password.configure(show=show)
        if self.confirm is not None:
            self.confirm.configure(show=show)

    def _submit(self, setup: bool) -> None:
        try:
            if setup:
                if self.password.get() != self.confirm.get():
                    messagebox.showerror("Password mismatch", "The passwords do not match.")
                    return
                user = self.auth_service.create_first_librarian(
                    self.username.get(), self.password.get()
                )
                messagebox.showinfo(
                    "Account created", "Librarian account created. You are now signed in."
                )
            else:
                user = self.auth_service.login(self.username.get(), self.password.get())
            self.on_login(user)
        except LibraryError as error:
            messagebox.showerror("Sign-in error", str(error))
