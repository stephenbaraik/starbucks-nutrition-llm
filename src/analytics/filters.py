"""
Predicate engine for numeric filtering.

Validation happens against the `available` set from capabilities(), before
anything touches the frame. The LLM executor calls this exact function
rather than reimplementing filtering, which is also why validation lives
here instead of in the UI.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass

import pandas as pd

# The only comparison operators a filter is allowed to use — deliberately a
# closed set, not an arbitrary Python expression, so a user's (or the LLM's)
# filter request can never turn into code execution.
ALLOWED_OPS = {">", ">=", "<", "<=", "==", "!="}

# Maps each allowed operator string to the actual function that runs it.
_OPS = {
    ">": operator.gt, ">=": operator.ge,
    "<": operator.lt, "<=": operator.le,
    "==": operator.eq, "!=": operator.ne,
}


class FilterError(ValueError):
    pass


# One condition: "field op value", e.g. calories < 500. This is what the LLM
# planner produces from a natural-language question like "food items under
# 500 calories" — it never gets to filter the frame directly, only to
# describe conditions like this one, which we then validate and run.
@dataclass
class Predicate:
    field: str
    op: str
    value: float


def validate_predicate(p: Predicate, available: set[str]) -> None:
    """Reject anything the LLM might invent: an unknown column or operator."""
    if p.field not in available:
        raise FilterError(f"'{p.field}' is not an available nutrient.")
    if p.op not in ALLOWED_OPS:
        raise FilterError(f"'{p.op}' is not a supported operator. Use one of {sorted(ALLOWED_OPS)}.")


def apply_predicates(df: pd.DataFrame, predicates: list[Predicate], available: set[str]) -> pd.DataFrame:
    """Validate then apply each predicate in turn, narrowing the frame as we go."""
    for p in predicates:
        validate_predicate(p, available)
        df = df[_OPS[p.op](df[p.field], p.value)]
    return df
