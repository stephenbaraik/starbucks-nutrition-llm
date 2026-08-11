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
    """Get (or create) a module logger with both handlers attached.

    Call this once per module, right after the imports (`logger =
    get_logger(__name__)`), the same way `logging.getLogger` is normally
    used. Safe to call more than once for the same name — Python's own
    logger registry means every get_logger("x") returns the same object,
    so the early return below just stops us attaching a second console/
    file handler pair and doubling every log line.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    # DEBUG at the logger level so nothing is filtered out before it even
    # reaches a handler — the actual filtering happens per-handler below.
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    formatter = logging.Formatter(_FORMAT)

    # What the developer sees live in the terminal — quieter by default
    # (INFO), overridable via the LOG_LEVEL env var for local debugging.
    console = logging.StreamHandler()
    console.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    console.setFormatter(formatter)
    logger.addHandler(console)

    # The permanent record — always DEBUG, rotated at 1MB so it can't grow
    # unbounded, with 3 backups kept before the oldest is discarded.
    LOG_DIR.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
