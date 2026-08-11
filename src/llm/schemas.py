"""Pydantic shapes for the NL query plan. Field names are validated against
capabilities() at execution time, not here, since the available set depends
on what was uploaded."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Filter(BaseModel):
    field: str
    op: Literal[">", ">=", "<", "<=", "==", "!="]
    value: float


class QueryPlan(BaseModel):
    dataset: Literal["drinks", "food", "both"]
    metric: str
    op: Literal["mean", "median", "max", "min", "sum", "count", "top_n"]
    filters: list[Filter] = []
    group_by: str | None = None
    limit: int | None = Field(None, ge=1, le=50)


class PlanError(BaseModel):
    error: str
