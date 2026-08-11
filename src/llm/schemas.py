"""Pydantic shapes for the NL query plan. Field names are validated against
capabilities() at execution time, not here, since the available set depends
on what was uploaded."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# One filter condition inside a QueryPlan, e.g. {"field": "calories", "op": "<", "value": 500}.
# The op is a closed Literal, not a free string, so pydantic itself rejects
# anything the LLM might invent outside the six allowed comparisons.
class Filter(BaseModel):
    field: str
    op: Literal[">", ">=", "<", "<=", "==", "!="]
    value: float


# What the LLM produces from a natural-language question, and what
# executor.execute() actually runs. `metric`/`group_by`/filter fields are
# left as plain str here — they get checked against the real available
# columns in executor.py, since that depends on what CSVs were uploaded and
# this schema has no way to know that ahead of time.
class QueryPlan(BaseModel):
    dataset: Literal["drinks", "food", "both"]
    metric: str
    op: Literal["mean", "median", "max", "min", "sum", "count", "top_n"]
    filters: list[Filter] = []
    group_by: str | None = None
    limit: int | None = Field(None, ge=1, le=50)


# What the LLM returns instead of a plan when a question can't be answered
# (subjective, missing field, not a data question at all).
class PlanError(BaseModel):
    error: str
