"""
File reading with encoding detection.

Kept separate from cleaning so that "could we read the file at all" is a
distinct failure mode from "was the content usable".
"""

from pathlib import Path
import pandas as pd

from src.config import ENCODINGS


class UnreadableFileError(RuntimeError):
    """Raised when no candidate encoding produces a parseable CSV."""


def read_csv_resilient(path: str | Path) -> tuple[pd.DataFrame, str]:
    """
    Read a CSV, trying each candidate encoding in turn.

    Returns the DataFrame and the encoding that worked, so the caller can
    record it in the data quality report. Everything is read as string first;
    type coercion is the cleaner's job, not the reader's. Reading as string
    also stops pandas from silently turning a sentinel-heavy column into
    something surprising.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {path}")

    attempts: list[str] = []
    for enc in ENCODINGS:
        try:
            df = pd.read_csv(path, encoding=enc, dtype=str, keep_default_na=False)
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

        return df, enc

    raise UnreadableFileError(
        f"Could not read {path.name} with any of {ENCODINGS}. Attempts: {attempts}"
    )
