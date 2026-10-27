"""Application settings and paths."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIRECTORY = PROJECT_ROOT / "data"
REPORTS_DIRECTORY = PROJECT_ROOT / "reports"
LOGS_DIRECTORY = PROJECT_ROOT / "logs"
DATABASE_PATH = DATA_DIRECTORY / "library.db"

DEFAULT_LOAN_PERIOD_DAYS = 14
DEFAULT_FINE_PER_DAY = 5.0
DATE_FORMAT = "%Y-%m-%d"
