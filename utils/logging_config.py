"""Central application logging setup."""

import logging
from logging.handlers import RotatingFileHandler

from config.settings import LOGS_DIRECTORY


def configure_logging() -> None:
    LOGS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    handler = RotatingFileHandler(
        LOGS_DIRECTORY / "library.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
