# Smart Library Management System

A desktop library application for a TY CSE Python mini project. It uses Python,
Tkinter/ttk, SQLite, CSV/JSON, NumPy, Pandas, Matplotlib, regular expressions,
and Python's PBKDF2 password hashing.

## Features in this project

- First-run creation of a librarian login; passwords are salted PBKDF2 hashes.
- Librarian login and service-layer role checks.
- Book and member add, edit, delete, and search.
- Issue and return transactions, copy tracking, due dates, overdue status, and
  fine calculation.
- Fine payment status and adjustable loan/fine settings.
- Streaming book import from CSV and `.xlsx`, JSON import, duplicate ISBN
  detection, and row-level error counts.
- Re-importing an existing ISBN updates descriptive fields only; it does not
  overwrite existing copy quantities.
- CSV and JSON exports for books, members, loans, and fines, using the same report-specific fields in both formats.
- Dashboard statistics, Pandas/NumPy borrowing summaries, and an interactive
  four-panel Matplotlib analytics view with category, monthly, inventory, and
  fine charts.
- A two-panel, first-run/login screen with account setup, password visibility,
  and a clear librarian sign-in flow.
- Resizable, color-coded tables with alternating rows, readable status labels,
  clear empty states, and a maximized startup window.
- SQLite constraints, indexes, foreign keys, logging, input validation, and
  automated unit tests.

Django and machine-learning prediction are optional future extensions, not
required to run the desktop application.

## Architecture and project files

```text
SmartLibraryManagementSystem/
├── main.py                    # Starts the desktop application
├── requirements.txt           # Third-party package list
├── README.md                  # Setup, usage, schema, and project notes
├── .gitignore
├── config/
│   ├── __init__.py
│   └── settings.py            # Paths, date format, default loan/fine settings
├── database/
│   ├── __init__.py
│   └── connection.py          # Connections, schema, database initialization
├── models/
│   ├── __init__.py
│   └── entities.py            # User, Librarian, Member, Book, Transaction
├── services/
│   ├── __init__.py
│   ├── auth_service.py        # First-run account setup and sign-in
│   ├── file_service.py        # CSV/Excel/JSON import and report export
│   └── library_service.py     # CRUD, issue/return, fine, settings, statistics
├── gui/
│   ├── __init__.py
│   ├── login.py               # First-run setup and librarian login
│   └── main_window.py         # Dashboard and librarian tabs
├── analytics/
│   ├── __init__.py
│   └── reports.py             # Pandas/NumPy summaries and chart generation
├── utils/
│   ├── __init__.py
│   ├── exceptions.py          # Expected application errors
│   ├── logging_config.py      # Rotating file logging
│   ├── security.py            # PBKDF2 password hashing and verification
│   └── validation.py          # Regex and field validation
├── data/                      # Automatically generated library.db
├── reports/                   # Exported CSV, JSON, and chart files
├── logs/                      # Rotating application log
└── tests/
    ├── __init__.py
    ├── test_database.py
    └── test_services.py
```

The GUI calls services; services validate inputs and perform parameterized
database operations. Keeping those responsibilities separate makes business
rules testable without opening a window.

See [docs/project-report.md](./docs/project-report.md) for the abstract,
objectives, methodology, architecture/database diagrams, syllabus mapping,
demo checklist, limitations, and viva questions.

## Database schema

The SQLite database is automatically created at `data/library.db` on startup.
The schema is in `database/connection.py`.

| Table | Purpose and relationships |
|---|---|
| `users` | Unique login name, PBKDF2 hash, role, and optional member link |
| `books` | One catalogue row per ISBN, with total and available copies |
| `members` | Member name, unique email, phone, and registration date |
| `loans` | Issue/return row referencing one book and one member |
| `fines` | Fine and payment state, with at most one fine per loan |
| `settings` | Configurable loan period and daily fine rate |

Foreign keys and check constraints protect references, quantities, dates,
roles, and payment states. Foreign-key checks are enabled per connection.
Issuing and returning a book updates the loan and inventory in one transaction.

## VS Code and Python setup

Install Python 3.10 or newer and these VS Code extensions:

- Python (Microsoft)
- Python Debugger (Microsoft)
- Pylance (Microsoft)

Open the project folder in VS Code and run these commands in its PowerShell
terminal:

```powershell
py --version
py -c "import sqlite3, tkinter; print('SQLite and Tkinter are available')"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Choose `.venv` through **Python: Select Interpreter**. If PowerShell blocks
environment activation, call the interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Tkinter and SQLite are part of the Python installation. The pip requirements
are NumPy, Pandas, Matplotlib, and openpyxl (for streaming `.xlsx` import).
Password hashing uses Python's standard-library PBKDF2 implementation.

## Run and use the application

```powershell
python main.py
```

On first launch, create a librarian account in the setup screen. No username or
password is preconfigured. Later launches show the sign-in screen. After
login, use the tabs to manage catalogues, members, loans, fines, reports, and
settings. To add a book or member, fill in the form and choose the add button.
Select a table row to edit or delete it. Issue a book by choosing an available
copy and a member; select an active loan to return it.

The default loan period is 14 days and the default fine rate is 5.00 currency
units per overdue day. Adjust both in **Settings**. A returned overdue loan
stores its calculated fine; active overdue loans show an accruing estimate in
the loan table and dashboard. Fines are marked paid from the **Fines** tab.

The book import columns required are `isbn`, `title`, `author`, and
`total_quantity`. `publisher`, `category`, and `publication_year` are
optional. The importer processes CSV and `.xlsx` rows incrementally. A
repeated ISBN in the same import is rejected. Existing ISBN rows update
descriptive data only; their inventory quantities are preserved. Exported
reports are written to `reports/` or a path chosen in the save dialog.
For a quick demo, import the fictional examples in `data/sample_books.csv`;
these examples are not inserted into the database automatically.

## Tests

Run the automated tests from the project root:

```powershell
python -m unittest discover -s tests -v
```

The suite exercises schema constraints, login/password verification, book
issue/return inventory changes, fine calculations, and duplicate import
handling. Tests use temporary SQLite files; they do not rely on application
records in `data/library.db`.

## GitHub setup

Create an empty repository on GitHub, then from this project folder run:

```powershell
git init
git add .
git status
git commit -m "Initial smart library project"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Replace the remote URL with your repository URL. Review `git status` before
committing: `.gitignore` excludes the local database, logs, and generated
reports. Do not commit real member data, passwords, or private exports.

## Troubleshooting

- **`py` not found:** install Python and its launcher, then reopen VS Code.
- **Tkinter import fails:** install a Python distribution that includes Tcl/Tk.
- **An import cannot be resolved:** select the project `.venv` interpreter and
  install `requirements.txt`.
- **PowerShell activation is blocked:** use the direct `.venv` interpreter
  commands shown above.
- **Forgot the librarian password:** there is no default or plaintext copy.
  Back up any required database first; account recovery can be added as a
  controlled admin feature.
- **Database appears empty:** this project starts with no fabricated library
  records; add them in the UI or import a catalogue.

## Project scope and future work

This desktop version demonstrates Python fundamentals, collections and
functions, OOP models, custom exceptions, regular expressions, file handling,
SQLite connectivity, Tkinter event handling, Pandas/NumPy analysis, charting,
and unit testing. Optional future work can add a Django web client, more
member-specific permissions, machine-learning demand prediction using
historical loans, backups, and additional integration tests.
#   A P C - P r o j e c t  
 