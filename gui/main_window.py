"""Librarian desktop interface built with Tkinter and ttk."""

import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import Any

from analytics.reports import build_analytics_figure, save_borrowing_chart
from config.settings import REPORTS_DIRECTORY
from models.entities import User
from services.file_service import FileService
from services.library_service import LibraryService
from utils.exceptions import LibraryError
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

logger = logging.getLogger(__name__)


class LibraryWindow(ttk.Frame):
    def __init__(self, master: tk.Misc, user: User, service: LibraryService) -> None:
        self._configure_styles(master)
        super().__init__(master, padding=12)
        self.user = user
        self.service = service
        self.files = FileService(service.database_path)
        self._table_empty_labels: dict[ttk.Treeview, ttk.Label] = {}
        self.pack(fill="both", expand=True)
        self._build()
        self.refresh_all()

    @staticmethod
    def _configure_styles(master: tk.Misc) -> None:
        style = ttk.Style(master)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure("TFrame", background="#f1f5f9")
        style.configure("TLabel", background="#f1f5f9", foreground="#1e293b")
        style.configure(
            "TLabelframe",
            background="#f1f5f9",
            bordercolor="#cbd5e1",
            relief="solid",
        )
        style.configure(
            "TLabelframe.Label",
            background="#f1f5f9",
            foreground="#334155",
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "TNotebook",
            background="#e2e8f0",
            borderwidth=0,
            tabmargins=(2, 4, 2, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background="#e2e8f0",
            foreground="#334155",
            padding=(14, 8),
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#1d4ed8"), ("active", "#bfdbfe")],
            foreground=[("selected", "#ffffff"), ("active", "#0f172a")],
        )
        style.configure(
            "TButton",
            background="#e2e8f0",
            foreground="#0f172a",
            borderwidth=0,
            padding=(10, 6),
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "TButton",
            background=[("pressed", "#cbd5e1"), ("active", "#cbd5e1")],
            foreground=[("disabled", "#94a3b8")],
        )
        style.configure(
            "Accent.TButton",
            background="#2563eb",
            foreground="#ffffff",
            padding=(11, 7),
        )
        style.map(
            "Accent.TButton",
            background=[("pressed", "#1e40af"), ("active", "#1d4ed8")],
            foreground=[("disabled", "#dbeafe")],
        )
        style.configure(
            "Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#1e293b",
            rowheight=30,
            borderwidth=0,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Treeview.Heading",
            background="#1e3a8a",
            foreground="#ffffff",
            padding=(8, 8),
            relief="flat",
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Treeview",
            background=[("selected", "#bfdbfe")],
            foreground=[("selected", "#0f172a")],
        )
        style.map(
            "Treeview.Heading",
            background=[("active", "#1d4ed8")],
            foreground=[("active", "#ffffff")],
        )
        style.configure(
            "Library.Vertical.TScrollbar",
            background="#cbd5e1",
            troughcolor="#f1f5f9",
            borderwidth=0,
            arrowsize=12,
        )
        style.configure(
            "Library.Horizontal.TScrollbar",
            background="#cbd5e1",
            troughcolor="#f1f5f9",
            borderwidth=0,
            arrowsize=12,
        )
        style.configure("Empty.TLabel", background="#ffffff", foreground="#64748b")

    def _build(self) -> None:
        header = tk.Frame(self, bg="#0f172a", padx=18, pady=12)
        header.pack(fill="x", pady=(0, 10))
        tk.Label(
            header,
            text="SMART LIBRARY",
            bg="#0f172a",
            fg="#ffffff",
            font=("Segoe UI", 17, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            text=f"LIBRARIAN  •  {self.user.username}",
            bg="#0f172a",
            fg="#bfdbfe",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right", padx=8)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self._build_dashboard()
        self._build_books()
        self._build_members()
        self._build_circulation()
        self._build_fines()
        self._build_reports()
        self._build_settings()

    def _build_dashboard(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="Dashboard")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        heading = ttk.Frame(tab)
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        heading.columnconfigure(0, weight=1)
        ttk.Label(
            heading, text="Library overview", font=("Segoe UI", 18, "bold")
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            heading,
            text="A live summary of your collection, members, and circulation.",
            foreground="#64748b",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Button(
            heading, text="Refresh", command=self.refresh_dashboard
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))

        cards = ttk.Frame(tab)
        cards.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        self.dashboard_values: dict[str, tk.Label] = {}
        for column in range(4):
            cards.columnconfigure(column, weight=1, uniform="dashboard-card")
        for row in range(2):
            cards.rowconfigure(row, weight=1, uniform="dashboard-card-row")

        metrics = (
            ("titles", "Book titles"),
            ("copies", "Physical copies"),
            ("available", "Available"),
            ("issued", "Issued"),
            ("members", "Members"),
            ("overdue", "Overdue"),
            ("outstanding_fines", "Unpaid fines"),
        )
        accents = {
            "titles": "#2563eb",
            "copies": "#7c3aed",
            "available": "#059669",
            "issued": "#d97706",
            "members": "#0891b2",
            "overdue": "#dc2626",
            "outstanding_fines": "#be185d",
        }
        for index, (key, label) in enumerate(metrics):
            card = tk.Frame(
                cards,
                bg="#ffffff",
                highlightbackground="#dbe3ed",
                highlightthickness=1,
                bd=0,
            )
            card.grid(
                row=index // 4,
                column=index % 4,
                padx=(0 if index % 4 == 0 else 6, 0),
                pady=(0, 6 if index < 4 else 0),
                sticky="nsew",
            )
            tk.Frame(card, bg=accents[key], height=4).pack(fill="x")
            content = tk.Frame(card, bg="#ffffff", padx=14, pady=10)
            content.pack(fill="both", expand=True)
            tk.Label(
                content,
                text=label.upper(),
                bg="#ffffff",
                fg="#64748b",
                font=("Segoe UI", 9, "bold"),
                anchor="w",
            ).pack(fill="x")
            value = tk.Label(
                content,
                text="0",
                bg="#ffffff",
                fg="#172033",
                font=("Segoe UI", 22, "bold"),
                anchor="w",
            )
            value.pack(fill="x", pady=(5, 0))
            self.dashboard_values[key] = value

        panels = ttk.Frame(tab)
        panels.grid(row=2, column=0, sticky="nsew")
        panels.columnconfigure(0, weight=3, uniform="dashboard-panel")
        panels.columnconfigure(1, weight=2, uniform="dashboard-panel")
        panels.rowconfigure(0, weight=1)

        recent_panel = ttk.LabelFrame(panels, text="Recent circulation", padding=10)
        recent_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        recent_panel.rowconfigure(0, weight=1)
        recent_panel.columnconfigure(0, weight=1)
        self.recent_loans_table = ttk.Treeview(
            recent_panel,
            columns=("title", "member_name", "issue_date", "due_date", "status"),
            show="headings",
            height=8,
        )
        self.recent_loans_table.tag_configure("even", background="#ffffff")
        self.recent_loans_table.tag_configure("odd", background="#f1f5f9")
        self.recent_loans_table.tag_configure(
            "overdue", background="#fee2e2", foreground="#991b1b"
        )
        for column, heading_text, width in (
            ("title", "Book", 180),
            ("member_name", "Member", 140),
            ("issue_date", "Issued", 95),
            ("due_date", "Due", 95),
            ("status", "Status", 85),
        ):
            self.recent_loans_table.heading(column, text=heading_text)
            self.recent_loans_table.column(column, width=width, anchor="w")
        self.recent_loans_table.grid(row=0, column=0, sticky="nsew")
        recent_scrollbar = ttk.Scrollbar(
            recent_panel, orient="vertical", command=self.recent_loans_table.yview
        )
        recent_scrollbar.grid(row=0, column=1, sticky="ns")
        self.recent_loans_table.configure(yscrollcommand=recent_scrollbar.set)
        self.recent_empty_label = ttk.Label(
            recent_panel,
            text="No loans yet. Issued books will appear here.",
            foreground="#64748b",
        )
        self.recent_empty_label.place(
            in_=self.recent_loans_table, relx=0.5, rely=0.5, anchor="center"
        )

        inventory_panel = ttk.LabelFrame(
            panels, text="Available copies by category", padding=10
        )
        inventory_panel.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        inventory_panel.rowconfigure(0, weight=1)
        inventory_panel.columnconfigure(0, weight=1)
        self.inventory_chart = tk.Canvas(
            inventory_panel,
            background="#ffffff",
            highlightthickness=0,
            height=260,
        )
        self.inventory_chart.grid(row=0, column=0, sticky="nsew")
        self.inventory_chart.bind(
            "<Configure>", lambda _event: self._draw_inventory_chart()
        )
        self._inventory_categories: list[tuple[str, int, int]] = []

    def _build_books(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Books")
        self.book_fields = self._entry_form(
            tab,
            [
                ("isbn", "ISBN"),
                ("title", "Title"),
                ("author", "Author"),
                ("publisher", "Publisher"),
                ("category", "Category"),
                ("publication_year", "Year"),
                ("total_quantity", "Total copies"),
            ],
        )
        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=5)
        ttk.Button(
            actions, text="Add book", style="Accent.TButton", command=self.add_book
        ).pack(side="left", padx=3)
        ttk.Button(actions, text="Update selected", command=self.update_book).pack(
            side="left", padx=3
        )
        ttk.Button(actions, text="Delete selected", command=self.delete_book).pack(
            side="left", padx=3
        )
        ttk.Button(actions, text="Import CSV/JSON", command=self.import_books).pack(
            side="left", padx=3
        )
        ttk.Button(actions, text="Export CSV", command=lambda: self.export("books", "csv")).pack(
            side="left", padx=3
        )
        search = ttk.Frame(tab)
        search.pack(fill="x", pady=(6, 3))
        ttk.Label(search, text="Search").pack(side="left")
        self.book_search = ttk.Entry(search, width=35)
        self.book_search.pack(side="left", padx=6)
        self.book_search.bind("<KeyRelease>", lambda _event: self.refresh_books())
        self.book_table = self._table(
            tab,
            (
                "book_id", "isbn", "title", "author", "publisher", "category",
                "publication_year", "total_quantity", "available_quantity",
            ),
        )
        self.book_table.bind("<<TreeviewSelect>>", self._select_book)

    def _build_members(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Members")
        self.member_fields = self._entry_form(
            tab, [("name", "Name"), ("email", "Email"), ("phone", "Phone")]
        )
        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=5)
        ttk.Button(
            actions,
            text="Add member",
            style="Accent.TButton",
            command=self.add_member,
        ).pack(
            side="left", padx=3
        )
        ttk.Button(actions, text="Update selected", command=self.update_member).pack(
            side="left", padx=3
        )
        ttk.Button(actions, text="Delete selected", command=self.delete_member).pack(
            side="left", padx=3
        )
        ttk.Button(
            actions, text="Export CSV", command=lambda: self.export("members", "csv")
        ).pack(side="left", padx=3)
        search = ttk.Frame(tab)
        search.pack(fill="x", pady=(6, 3))
        ttk.Label(search, text="Search").pack(side="left")
        self.member_search = ttk.Entry(search, width=35)
        self.member_search.pack(side="left", padx=6)
        self.member_search.bind("<KeyRelease>", lambda _event: self.refresh_members())
        self.member_table = self._table(
            tab, ("member_id", "name", "email", "phone", "registered_on")
        )
        self.member_table.bind("<<TreeviewSelect>>", self._select_member)

    def _build_circulation(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Issue / Return")
        form = ttk.Frame(tab)
        form.pack(fill="x", pady=5)
        ttk.Label(form, text="Book").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.issue_book_choice = ttk.Combobox(form, state="readonly", width=42)
        self.issue_book_choice.grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(form, text="Member").grid(row=0, column=2, sticky="w", padx=4, pady=4)
        self.issue_member_choice = ttk.Combobox(form, state="readonly", width=35)
        self.issue_member_choice.grid(row=0, column=3, padx=4, pady=4)
        ttk.Button(
            form, text="Issue book", style="Accent.TButton", command=self.issue_book
        ).grid(
            row=0, column=4, padx=8, pady=4
        )
        action = ttk.Frame(tab)
        action.pack(fill="x", pady=5)
        ttk.Button(action, text="Return selected loan", command=self.return_book).pack(
            side="left", padx=3
        )
        ttk.Button(
            action, text="Export loans CSV", command=lambda: self.export("loans", "csv")
        ).pack(side="left", padx=3)
        self.loan_table = self._table(
            tab,
            (
                "loan_id", "title", "isbn", "member_name", "issue_date",
                "due_date", "return_date", "status", "is_overdue", "estimated_fine",
            ),
        )

    def _build_fines(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Fines")
        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=5)
        ttk.Button(
            actions,
            text="Mark selected fine paid",
            style="Accent.TButton",
            command=self.mark_fine_paid,
        ).pack(
            side="left", padx=3
        )
        ttk.Button(actions, text="Export CSV", command=lambda: self.export("fines", "csv")).pack(
            side="left", padx=3
        )
        self.fine_table = self._table(
            tab,
            (
                "fine_id", "loan_id", "member_name", "title", "amount",
                "payment_status", "assessed_on", "paid_at",
            ),
        )

    def _build_reports(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="Reports")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)

        heading = ttk.Frame(tab)
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(
            heading, text="Reports & analytics", font=("Segoe UI", 18, "bold")
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            heading,
            text="Explore borrowing, inventory, and fine activity from your saved records.",
            foreground="#64748b",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        controls = ttk.Frame(tab)
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(controls, text="Export").pack(side="left", padx=(0, 5))
        self.report_choice = ttk.Combobox(
            controls,
            state="readonly",
            values=("books", "members", "loans", "fines"),
            width=11,
        )
        self.report_choice.set("books")
        self.report_choice.pack(side="left", padx=5)
        self.report_format = ttk.Combobox(
            controls, state="readonly", values=("csv", "json"), width=7
        )
        self.report_format.set("csv")
        self.report_format.pack(side="left", padx=5)
        ttk.Button(
            controls,
            text="Export",
            style="Accent.TButton",
            command=self.export_selected,
        ).pack(
            side="left", padx=(5, 0)
        )
        ttk.Button(
            controls, text="Save chart", command=self.create_chart
        ).pack(side="left", padx=(7, 0))
        ttk.Button(
            controls, text="Refresh analytics", command=self.refresh_analytics
        ).pack(side="left", padx=(7, 0))

        summary_row = ttk.Frame(tab)
        summary_row.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self.report_summary_values: dict[str, tk.Label] = {}
        for column in range(4):
            summary_row.columnconfigure(column, weight=1, uniform="report-summary")
        summary_metrics = (
            ("loans", "TOTAL LOANS", "#2563eb"),
            ("active", "CURRENTLY ISSUED", "#d97706"),
            ("overdue", "OVERDUE", "#dc2626"),
            ("fine_balance", "UNPAID FINES", "#be185d"),
        )
        for index, (key, title, accent) in enumerate(summary_metrics):
            card = tk.Frame(
                summary_row,
                bg="#ffffff",
                highlightbackground="#dbe3ed",
                highlightthickness=1,
            )
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 8, 0))
            tk.Frame(card, bg=accent, height=3).pack(fill="x")
            content = tk.Frame(card, bg="#ffffff", padx=12, pady=8)
            content.pack(fill="x")
            tk.Label(
                content,
                text=title,
                bg="#ffffff",
                fg="#64748b",
                font=("Segoe UI", 8, "bold"),
            ).pack(anchor="w")
            value = tk.Label(
                content,
                text="0",
                bg="#ffffff",
                fg="#0f172a",
                font=("Segoe UI", 17, "bold"),
            )
            value.pack(anchor="w", pady=(2, 0))
            self.report_summary_values[key] = value

        chart_panel = ttk.Frame(tab)
        chart_panel.grid(row=3, column=0, sticky="nsew")
        chart_panel.columnconfigure(0, weight=1)
        chart_panel.rowconfigure(0, weight=1)
        self.analytics_figure = build_analytics_figure([], [], [])
        self.analytics_canvas = FigureCanvasTkAgg(
            self.analytics_figure, master=chart_panel
        )
        self.analytics_canvas_widget = self.analytics_canvas.get_tk_widget()
        self.analytics_canvas_widget.configure(
            background="#f1f5f9", highlightthickness=0, borderwidth=0
        )
        self.analytics_canvas_widget.grid(row=0, column=0, sticky="nsew")
        self.analytics_canvas_widget.bind(
            "<Configure>", self._resize_analytics_figure
        )
        self.analytics_canvas.draw()

    def _resize_analytics_figure(self, event: tk.Event) -> None:
        self._fit_analytics_figure(event.width, event.height)

    def _fit_analytics_figure(self, width: int, height: int) -> None:
        if width < 100 or height < 100:
            return
        dpi = self.analytics_figure.get_dpi()
        self.analytics_figure.set_size_inches(
            width / dpi, height / dpi, forward=False
        )
        self.analytics_canvas.draw_idle()

    def _build_settings(self) -> None:
        tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab, text="Settings")
        ttk.Label(tab, text="Default loan period (days)").grid(
            row=0, column=0, sticky="w", padx=5, pady=6
        )
        self.loan_days = ttk.Entry(tab, width=18)
        self.loan_days.grid(row=0, column=1, padx=5, pady=6)
        ttk.Label(tab, text="Fine per overdue day").grid(
            row=1, column=0, sticky="w", padx=5, pady=6
        )
        self.fine_rate = ttk.Entry(tab, width=18)
        self.fine_rate.grid(row=1, column=1, padx=5, pady=6)
        ttk.Button(tab, text="Save settings", command=self.save_settings).grid(
            row=2, column=1, sticky="e", padx=5, pady=8
        )

    def _entry_form(self, parent: ttk.Frame, fields: list[tuple[str, str]]) -> dict[str, ttk.Entry]:
        frame = ttk.LabelFrame(parent, text="Record details", padding=10)
        frame.pack(fill="x")
        entries: dict[str, ttk.Entry] = {}
        column_count = min(4, len(fields))
        remainder = len(fields) % column_count
        for index, (key, label) in enumerate(fields):
            row, column = divmod(index, column_count)
            cell = ttk.Frame(frame)
            column_span = (
                column_count - column
                if remainder and index >= len(fields) - remainder and index == len(fields) - 1
                else 1
            )
            cell.grid(
                row=row,
                column=column,
                columnspan=column_span,
                sticky="ew",
                padx=6,
                pady=5,
            )
            ttk.Label(cell, text=label, font=("Segoe UI", 9, "bold")).pack(
                anchor="w", pady=(0, 3)
            )
            entry = ttk.Entry(cell, width=22)
            entry.pack(fill="x")
            entries[key] = entry
        for column in range(column_count):
            frame.columnconfigure(column, weight=1)
        return entries

    def _table(self, parent: ttk.Frame, columns: tuple[str, ...]) -> ttk.Treeview:
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill="both", expand=True, pady=4)
        table = ttk.Treeview(wrapper, columns=columns, show="headings", height=13)
        vertical = ttk.Scrollbar(
            wrapper, orient="vertical", command=table.yview, style="Library.Vertical.TScrollbar"
        )
        horizontal = ttk.Scrollbar(
            wrapper,
            orient="horizontal",
            command=table.xview,
            style="Library.Horizontal.TScrollbar",
        )
        table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)
        widths = {
            "book_id": (72, 58, "center"),
            "isbn": (130, 105, "center"),
            "title": (210, 145, "w"),
            "author": (165, 110, "w"),
            "publisher": (145, 95, "w"),
            "category": (135, 95, "w"),
            "publication_year": (100, 75, "center"),
            "total_quantity": (105, 78, "center"),
            "available_quantity": (120, 88, "center"),
            "member_id": (78, 60, "center"),
            "name": (190, 130, "w"),
            "email": (240, 160, "w"),
            "phone": (150, 110, "center"),
            "registered_on": (130, 100, "center"),
            "loan_id": (75, 60, "center"),
            "member_name": (165, 120, "w"),
            "issue_date": (105, 85, "center"),
            "due_date": (105, 85, "center"),
            "return_date": (110, 90, "center"),
            "status": (100, 75, "center"),
            "is_overdue": (95, 70, "center"),
            "estimated_fine": (120, 90, "e"),
            "fine_id": (75, 60, "center"),
            "amount": (105, 80, "e"),
            "payment_status": (125, 100, "center"),
            "assessed_on": (115, 90, "center"),
            "paid_at": (105, 85, "center"),
        }
        heading_names = {
            "publication_year": "Year",
            "total_quantity": "Total copies",
            "available_quantity": "Available copies",
            "member_name": "Member",
            "issue_date": "Issued",
            "due_date": "Due",
            "return_date": "Returned",
            "is_overdue": "Overdue?",
            "estimated_fine": "Est. fine",
            "payment_status": "Payment status",
            "assessed_on": "Assessed",
            "paid_at": "Paid",
        }
        for column in columns:
            width, minimum, anchor = widths.get(
                column, (max(100, min(180, len(column) * 11)), 75, "w")
            )
            table.heading(column, text=heading_names.get(column, column.replace("_", " ").title()))
            table.column(
                column,
                width=width,
                minwidth=minimum,
                anchor=anchor,
                stretch=True,
            )
        table.tag_configure("even", background="#ffffff", foreground="#1e293b")
        table.tag_configure("odd", background="#f1f5f9", foreground="#1e293b")
        table.tag_configure(
            "overdue", background="#fee2e2", foreground="#991b1b", font=("Segoe UI", 9, "bold")
        )
        table.tag_configure(
            "unpaid", background="#fff7ed", foreground="#9a3412", font=("Segoe UI", 9, "bold")
        )
        table.tag_configure("returned", background="#ecfdf5", foreground="#166534")

        empty_label = ttk.Label(
            wrapper,
            text="No records to display.",
            style="Empty.TLabel",
            font=("Segoe UI", 10),
        )
        self._table_empty_labels[table] = empty_label
        return table

    def _fill_table(self, table: ttk.Treeview, rows: list[dict[str, Any]]) -> None:
        table.delete(*table.get_children())
        columns = table["columns"]
        for index, row in enumerate(rows):
            values: list[Any] = []
            for column in columns:
                value = row.get(column, "")
                if value is None and column == "return_date":
                    value = "Not returned"
                elif value is None:
                    value = ""
                elif column == "is_overdue":
                    value = "Yes" if value else "No"
                elif column == "estimated_fine":
                    value = f"{float(value):,.2f}"
                elif column == "amount":
                    value = f"{float(value):,.2f}"
                elif column in {"status", "payment_status"} and value:
                    value = str(value).replace("_", " ").title()
                values.append(value)

            if row.get("is_overdue"):
                tag = "overdue"
            elif row.get("payment_status") == "unpaid":
                tag = "unpaid"
            elif row.get("status") == "returned":
                tag = "returned"
            else:
                tag = "even" if index % 2 == 0 else "odd"
            table.insert("", "end", values=tuple(values), tags=(tag,))

        empty_label = self._table_empty_labels.get(table)
        if empty_label is not None:
            if rows:
                empty_label.place_forget()
            else:
                empty_label.place(relx=0.5, rely=0.5, anchor="center")

    @staticmethod
    def _selected_id(table: ttk.Treeview) -> int:
        selection = table.selection()
        if not selection:
            raise LibraryError("Select a row first.")
        return int(table.item(selection[0], "values")[0])

    @staticmethod
    def _set_fields(fields: dict[str, ttk.Entry], values: dict[str, Any]) -> None:
        for key, entry in fields.items():
            entry.delete(0, "end")
            entry.insert(0, "" if values.get(key) is None else str(values.get(key, "")))

    @staticmethod
    def _get_fields(fields: dict[str, ttk.Entry]) -> dict[str, str]:
        return {key: entry.get() for key, entry in fields.items()}

    def _run(self, action: Any, success_message: str | None = None) -> Any:
        try:
            result = action()
            if success_message:
                messagebox.showinfo("Success", success_message)
            return True if result is None else result
        except LibraryError as error:
            messagebox.showwarning("Please check", str(error))
        except (OSError, ValueError) as error:
            logger.exception("Application operation failed")
            messagebox.showerror("Operation failed", str(error))
        except Exception as error:
            logger.exception("Unexpected application error")
            messagebox.showerror(
                "Unexpected error", f"{error}\n\nDetails were recorded in logs/library.log."
            )
        return None

    def refresh_all(self) -> None:
        self.refresh_dashboard()
        self.refresh_books()
        self.refresh_members()
        self.refresh_loans()
        self.refresh_fines()
        self.refresh_choices()
        self.refresh_settings()
        self.refresh_analytics()

    def refresh_dashboard(self) -> None:
        stats = self.service.dashboard_statistics()
        for key, value in stats.items():
            self.dashboard_values[key].configure(
                text=f"{value:,.2f}" if key == "outstanding_fines" else f"{value:,}"
            )
        loans = sorted(
            self.service.list_loans(),
            key=lambda loan: (loan["issue_date"], loan["loan_id"]),
            reverse=True,
        )[:8]
        self.recent_loans_table.delete(*self.recent_loans_table.get_children())
        for index, loan in enumerate(loans):
            status = "Overdue" if loan["is_overdue"] else loan["status"].title()
            tag = "overdue" if loan["is_overdue"] else ("even" if index % 2 == 0 else "odd")
            self.recent_loans_table.insert(
                "",
                "end",
                values=(
                    loan["title"],
                    loan["member_name"],
                    loan["issue_date"],
                    loan["due_date"],
                    status,
                ),
                tags=(tag,),
            )
        if loans:
            self.recent_empty_label.place_forget()
        else:
            self.recent_empty_label.place(
                in_=self.recent_loans_table, relx=0.5, rely=0.5, anchor="center"
            )

        categories: dict[str, list[int]] = {}
        for book in self.service.list_books():
            category = book["category"].strip() or "Uncategorized"
            counts = categories.setdefault(category, [0, 0])
            counts[0] += int(book["total_quantity"])
            counts[1] += int(book["available_quantity"])
        self._inventory_categories = sorted(
            (
                (name, quantities[0], quantities[1])
                for name, quantities in categories.items()
            ),
            key=lambda item: (-item[1], item[0].casefold()),
        )[:7]
        self._draw_inventory_chart()

    def _draw_inventory_chart(self) -> None:
        canvas = getattr(self, "inventory_chart", None)
        if canvas is None:
            return
        canvas.delete("all")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 60 or height < 60:
            return
        if not self._inventory_categories:
            canvas.create_text(
                width / 2,
                height / 2,
                text="Add books to see inventory here",
                fill="#64748b",
                font=("Segoe UI", 10),
            )
            return

        categories = self._inventory_categories
        row_height = min(38, (height - 16) / max(len(categories), 1))
        label_width = min(135, max(80, int(width * 0.32)))
        value_width = 52
        bar_left = label_width + 8
        bar_right = max(bar_left + 20, width - value_width - 12)
        bar_width = bar_right - bar_left
        max_total = max(total for _, total, _ in categories) or 1

        for index, (name, total, available) in enumerate(categories):
            y = 10 + index * row_height
            label = name if len(name) <= 18 else f"{name[:16]}…"
            canvas.create_text(
                2,
                y + row_height / 2,
                text=label,
                anchor="w",
                fill="#334155",
                font=("Segoe UI", 9),
            )
            canvas.create_rectangle(
                bar_left,
                y + row_height * 0.28,
                bar_right,
                y + row_height * 0.72,
                fill="#e2e8f0",
                outline="",
            )
            fill_width = bar_width * available / max_total
            if fill_width > 0:
                canvas.create_rectangle(
                    bar_left,
                    y + row_height * 0.28,
                    bar_left + fill_width,
                    y + row_height * 0.72,
                    fill="#10b981",
                    outline="",
                )
            canvas.create_text(
                width - 4,
                y + row_height / 2,
                text=f"{available}/{total}",
                anchor="e",
                fill="#475569",
                font=("Segoe UI", 9, "bold"),
            )

    def refresh_books(self) -> None:
        self._fill_table(
            self.book_table, self.service.list_books(self.book_search.get())
        )

    def refresh_members(self) -> None:
        self._fill_table(
            self.member_table, self.service.list_members(self.member_search.get())
        )

    def refresh_loans(self) -> None:
        self._fill_table(self.loan_table, self.service.list_loans())

    def refresh_fines(self) -> None:
        self._fill_table(self.fine_table, self.service.list_fines())

    def refresh_choices(self) -> None:
        books = self.service.list_books()
        members = self.service.list_members()
        self.book_choice_ids = {
            f"{book['book_id']} - {book['title']} ({book['available_quantity']} available)": book[
                "book_id"
            ]
            for book in books
            if book["available_quantity"] > 0
        }
        self.member_choice_ids = {
            f"{member['member_id']} - {member['name']}": member["member_id"]
            for member in members
        }
        self.issue_book_choice["values"] = tuple(self.book_choice_ids)
        self.issue_member_choice["values"] = tuple(self.member_choice_ids)

    def refresh_settings(self) -> None:
        self.loan_days.delete(0, "end")
        self.loan_days.insert(0, self.service.get_setting("loan_period_days"))
        self.fine_rate.delete(0, "end")
        self.fine_rate.insert(0, self.service.get_setting("fine_per_day"))

    def refresh_analytics(self) -> None:
        loans = self.service.list_loans()
        books = self.service.list_books()
        fines = self.service.list_fines()
        stats = self.service.dashboard_statistics()
        self.report_summary_values["loans"].configure(text=f"{len(loans):,}")
        self.report_summary_values["active"].configure(
            text=f"{sum(loan['status'] == 'issued' for loan in loans):,}"
        )
        self.report_summary_values["overdue"].configure(
            text=f"{sum(bool(loan['is_overdue']) for loan in loans):,}"
        )
        self.report_summary_values["fine_balance"].configure(
            text=f"{float(stats['outstanding_fines']):,.2f}"
        )

        new_figure = build_analytics_figure(loans, books, fines)
        old_figure = self.analytics_figure
        self.analytics_canvas.figure = new_figure
        new_figure.set_canvas(self.analytics_canvas)
        self.analytics_figure = new_figure
        self._fit_analytics_figure(
            self.analytics_canvas_widget.winfo_width(),
            self.analytics_canvas_widget.winfo_height(),
        )
        self.analytics_canvas.draw_idle()
        old_figure.clear()

    def add_book(self) -> None:
        result = self._run(
            lambda: self.service.add_book(self.user, self._get_fields(self.book_fields)),
            "Book added.",
        )
        if result is not None:
            self._set_fields(self.book_fields, {})
            self.refresh_all()

    def update_book(self) -> None:
        def action() -> None:
            self.service.update_book(
                self.user, self._selected_id(self.book_table), self._get_fields(self.book_fields)
            )

        if self._run(action, "Book updated.") is not None:
            self.refresh_all()

    def delete_book(self) -> None:
        def action() -> None:
            if messagebox.askyesno("Confirm delete", "Delete the selected book?"):
                self.service.delete_book(self.user, self._selected_id(self.book_table))

        self._run(action)
        self.refresh_all()

    def _select_book(self, _event: tk.Event) -> None:
        selected = self.book_table.selection()
        if not selected:
            return
        values = self.book_table.item(selected[0], "values")
        columns = self.book_table["columns"]
        self._set_fields(self.book_fields, dict(zip(columns, values)))

    def add_member(self) -> None:
        result = self._run(
            lambda: self.service.add_member(self.user, self._get_fields(self.member_fields)),
            "Member added.",
        )
        if result is not None:
            self._set_fields(self.member_fields, {})
            self.refresh_all()

    def update_member(self) -> None:
        def action() -> None:
            self.service.update_member(
                self.user,
                self._selected_id(self.member_table),
                self._get_fields(self.member_fields),
            )

        if self._run(action, "Member updated.") is not None:
            self.refresh_all()

    def delete_member(self) -> None:
        def action() -> None:
            if messagebox.askyesno("Confirm delete", "Delete the selected member?"):
                self.service.delete_member(self.user, self._selected_id(self.member_table))

        self._run(action)
        self.refresh_all()

    def _select_member(self, _event: tk.Event) -> None:
        selected = self.member_table.selection()
        if not selected:
            return
        values = self.member_table.item(selected[0], "values")
        self._set_fields(
            self.member_fields,
            dict(zip(("member_id", "name", "email", "phone", "registered_on"), values)),
        )

    def issue_book(self) -> None:
        def action() -> int:
            book_id = self.book_choice_ids.get(self.issue_book_choice.get())
            member_id = self.member_choice_ids.get(self.issue_member_choice.get())
            if book_id is None or member_id is None:
                raise LibraryError("Choose an available book and a member.")
            return self.service.issue_book(self.user, book_id, member_id)

        if self._run(action, "Book issued.") is not None:
            self.refresh_all()

    def return_book(self) -> None:
        def action() -> float:
            loan_id = self._selected_id(self.loan_table)
            fine = self.service.return_book(self.user, loan_id)
            messagebox.showinfo("Book returned", f"Return recorded. Fine: {fine:.2f}")
            return fine

        if self._run(action) is not None:
            self.refresh_all()

    def mark_fine_paid(self) -> None:
        def action() -> None:
            self.service.mark_fine_paid(self.user, self._selected_id(self.fine_table))

        if self._run(action, "Fine marked as paid.") is not None:
            self.refresh_all()

    def import_books(self) -> None:
        path = filedialog.askopenfilename(
            title="Import book catalogue",
            filetypes=(
                ("Catalogue files", "*.csv *.json *.xlsx"),
                ("CSV files", "*.csv"),
                ("JSON files", "*.json"),
                ("Excel workbooks", "*.xlsx"),
            ),
        )
        if not path:
            return
        result = self._run(lambda: self.files.import_books(self.user, path))
        if result is not None:
            errors = "\n".join(result["errors"][:10])
            message = (
                f"Imported or updated: {result['successful']}\n"
                f"Rejected: {result['rejected']}"
            )
            if errors:
                message += f"\n\nFirst row errors:\n{errors}"
            messagebox.showinfo("Import result", message)
            self.refresh_all()

    def export(self, report_type: str, file_format: str) -> None:
        rows = self._report_rows(report_type)
        path = filedialog.asksaveasfilename(
            title="Save report",
            initialdir=str(REPORTS_DIRECTORY),
            initialfile=f"{report_type}.{file_format}",
            defaultextension=f".{file_format}",
            filetypes=((f"{file_format.upper()} files", f"*.{file_format}"),),
        )
        if not path:
            return
        saved = self._run(
            lambda: self.files.export_report(
                self.user, report_type, rows, file_format, destination=path
            )
        )
        if saved:
            messagebox.showinfo("Export complete", f"Report saved to:\n{saved}")

    def export_selected(self) -> None:
        self.export(self.report_choice.get(), self.report_format.get())

    def _report_rows(self, report_type: str) -> list[dict[str, Any]]:
        if report_type == "books":
            return self.service.list_books()
        if report_type == "members":
            return self.service.list_members()
        if report_type == "loans":
            return self.service.list_loans()
        if report_type == "fines":
            return self.service.list_fines()
        raise LibraryError("Choose a report type.")

    def create_chart(self) -> None:
        REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
        destination = filedialog.asksaveasfilename(
            title="Save borrowing chart",
            initialdir=str(REPORTS_DIRECTORY),
            initialfile="popular_books.png",
            defaultextension=".png",
            filetypes=(("PNG image", "*.png"),),
        )
        if not destination:
            return
        saved = self._run(
            lambda: save_borrowing_chart(self.service.list_loans(), str(Path(destination)))
        )
        if saved:
            messagebox.showinfo("Chart saved", f"Chart saved to:\n{saved}")

    def save_settings(self) -> None:
        def action() -> None:
            try:
                days = int(self.loan_days.get())
                fine = float(self.fine_rate.get())
            except ValueError as error:
                raise LibraryError("Enter a whole number of days and a numeric fine rate.") from error
            self.service.update_settings(self.user, days, fine)

        if self._run(action, "Settings saved.") is not None:
            self.refresh_all()
