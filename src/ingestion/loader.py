"""
File reading with encoding detection.

Kept separate from cleaning so that "could we read the file at all" is a
distinct failure mode from "was the content usable".
"""

from pathlib import Path
from typing import IO

import pandas as pd

from src.config import ENCODINGS
from src.utils.logging import get_logger

logger = get_logger(__name__)


class UnreadableFileError(RuntimeError):
    """Raised when no candidate encoding produces a parseable CSV."""


def read_csv_resilient(path_or_buffer: str | Path | IO) -> tuple[pd.DataFrame, str]:
    """
    Read a CSV, trying each candidate encoding in turn.

    Accepts a filesystem path or a file-like object (e.g. Streamlit's
    UploadedFile), which is why this doesn't unconditionally wrap the input
    in Path() — that raises TypeError on anything without __fspath__.

    Returns the DataFrame and the encoding that worked, so the caller can
    record it in the data quality report. Everything is read as string first;
    type coercion is the cleaner's job, not the reader's. Reading as string
    also stops pandas from silently turning a sentinel-heavy column into
    something surprising.
    """
    # Anything with a .read() method (Streamlit's UploadedFile, a BytesIO,
    # ...) is treated as a buffer; anything else is assumed to be a path.
    is_buffer = hasattr(path_or_buffer, "read")
    if is_buffer:
        name = getattr(path_or_buffer, "name", "uploaded file")
    else:
        path_or_buffer = Path(path_or_buffer)
        if not path_or_buffer.exists():
            raise FileNotFoundError(f"No such file: {path_or_buffer}")
        name = path_or_buffer.name

    attempts: list[str] = []
    for enc in ENCODINGS:
        # A buffer's read position stays wherever the previous failed
        # attempt left it — rewind before every retry or the next encoding
        # would be reading from the middle of the file, not the start.
        if is_buffer:
            path_or_buffer.seek(0)
        try:
            df = pd.read_csv(path_or_buffer, encoding=enc, dtype=str, keep_default_na=False)
        except (UnicodeDecodeError, UnicodeError) as exc:
            attempts.append(f"{enc}: {type(exc).__name__}")
            continue
        except pd.errors.ParserError as exc:
            attempts.append(f"{enc}: ParserError {exc}")
            continue

        # A wrong-but-decodable encoding often yields one giant column of
        # mojibake. Treat a single-column result as a failed attempt.
        if df.shape[1] < 2:
            attempts.append(f"{enc}: parsed to {df.shape[1]} column(s)")
            continue

        logger.debug("Read %s as %s", name, enc)
        return df, enc

    logger.error("Could not read %s with any encoding. Attempts: %s", name, attempts)
    raise UnreadableFileError(
        f"Could not read {name} with any of {ENCODINGS}. Attempts: {attempts}"
    )
