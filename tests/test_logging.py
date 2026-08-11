import logging
import logging.handlers

from src.utils.logging import LOG_FILE, get_logger


def test_get_logger_is_idempotent():
    a = get_logger("test.idempotent")
    b = get_logger("test.idempotent")
    assert a is b
    assert len(a.handlers) == 2  # console + rotating file, not stacked


def test_get_logger_writes_to_rotating_file():
    logger = get_logger("test.writes")
    logger.error("boom-marker-12345")
    for handler in logger.handlers:
        handler.flush()
    assert LOG_FILE.exists()
    assert "boom-marker-12345" in LOG_FILE.read_text()


def test_file_handler_captures_debug_even_when_console_is_info():
    logger = get_logger("test.debug_level")
    file_handler = next(h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler))
    assert file_handler.level == logging.DEBUG


if __name__ == "__main__":
    import sys

    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
