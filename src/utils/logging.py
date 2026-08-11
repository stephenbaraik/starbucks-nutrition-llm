"""
Central logger. Console at LOG_LEVEL (default INFO), rotating file at DEBUG
so a report of "it broke" always has the detail even when the console
didn't show it. get_logger is idempotent — safe to call per-module at
import time without stacking duplicate handlers on reload.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from src.config import PROJECT_ROOT

LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "app.log"
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
    console.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    console.setFormatter(formatter)
    logger.addHandler(console)

    LOG_DIR.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
