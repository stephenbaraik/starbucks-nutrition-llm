"""
Redirect app logging to a throwaway directory for the whole test session,
before any src module is imported. get_logger() is idempotent per logger
name, so this has to happen before the first `logger = get_logger(__name__)`
at module import time, not inside a per-test fixture.

Without this, running pytest writes test-simulated errors (e.g. the
RuntimeError in test_llm_client.py) into the committed logs/app.log,
mixing them with real run history.
"""

from pathlib import Path

import src.utils.logging as _logging

_logging.LOG_DIR = Path(__file__).parent / ".test_logs"
_logging.LOG_FILE = _logging.LOG_DIR / "app.log"
