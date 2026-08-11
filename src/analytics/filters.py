"""
Predicate engine for numeric, text, and caffeine filtering.

Validation happens against the `available` set from capabilities(), before
anything touches the frame. The LLM executor calls these exact functions
rather than reimplementing filtering, which is also why validation lives
here instead of in the UI.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass

import pandas as pd

ALLOWED_OPS = {">", ">=", "<", "<=", "==", "!="}

_OPS = {
    ">": operator.gt, ">=": operator.ge,
    "<": operator.lt, "<=": operator.le,
    "==": operator.eq, "!=": operator.ne,
}


class FilterError(ValueError):
    pass


@dataclass
class Predicate:
    field: str
    op: str
    value: float


def validate_predicate(p: Predicate, available: set[str]) -> None:
    if p.field not in available:
        raise FilterError(f"'{p.field}' is not an available nutrient.")
    if p.op not in ALLOWED_OPS:
        raise FilterError(f"'{p.op}' is not a supported operator. Use one of {sorted(ALLOWED_OPS)}.")


def apply_predicates(df: pd.DataFrame, predicates: list[Predicate], available: set[str]) -> pd.DataFrame:
    for p in predicates:
        validate_predicate(p, available)
        df = df[_OPS[p.op](df[p.field], p.value)]
    return df


def apply_text_filter(df: pd.DataFrame, query: str) -> pd.DataFrame:
    if not query:
        return df
    return df[df["item_name"].str.contains(query, case=False, na=False)]


def apply_caffeine_filter(df: pd.DataFrame, caffeinated: bool | None) -> pd.DataFrame:
    if caffeinated is None or "caffeine_inferred" not in df.columns:
        return df
    return df[df["caffeine_inferred"] == caffeinated]
