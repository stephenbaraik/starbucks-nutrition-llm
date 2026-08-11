"""
plan -> pandas result, via the exact functions in analytics/filters.py — the
query path never reimplements filtering. No eval, exec, or getattr on
model-supplied names anywhere here (NFR-05); every op is a fixed branch.
"""

from __future__ import annotations

from src.analytics.filters import FilterError, Predicate, apply_predicates
from src.analytics.stats import top_n
from src.ingestion.pipeline import combined_frame
from src.llm.planner import propose_plan
from src.llm.schemas import PlanError, QueryPlan

_AGG_OPS = {"mean", "median", "max", "min", "sum", "count"}


class PlanValidationError(ValueError):
    pass


def _select_frame(plan: QueryPlan, datasets: dict):
    if plan.dataset == "both":
        return combined_frame(datasets)
    return datasets[plan.dataset].frame


def _validate_fields(plan: QueryPlan, available: set[str]) -> None:
    if plan.metric not in available:
        raise PlanValidationError(f"'{plan.metric}' is not an available field.")
    if plan.group_by is not None and plan.group_by not in available | {"source"}:
        raise PlanValidationError(f"'{plan.group_by}' is not an available field.")


def execute(plan: QueryPlan, datasets: dict, available: set[str]) -> dict:
    _validate_fields(plan, available)
    df = _select_frame(plan, datasets)

    predicates = [Predicate(f.field, f.op, f.value) for f in plan.filters]
    df = apply_predicates(df, predicates, available)

    if plan.op == "top_n":
        result = top_n(df, plan.metric, n=plan.limit or 5)
        return {"status": "ok", "rows": result[["item_name", plan.metric]].to_dict("records")}

    series = df[plan.metric]
    if plan.group_by:
        agg = series.groupby(df[plan.group_by]).agg(plan.op)
        return {"status": "ok", "result": agg.to_dict()}

    value = series.agg(plan.op)
    return {"status": "ok", "result": None if value != value else value}  # NaN -> None


def answer(question: str, datasets: dict, capabilities: dict, client=None) -> dict:
    """The whole loop: plan -> validate -> execute -> narrate. One retry on failure."""
    available = set(capabilities["comparable"]) | {
        c for cols in capabilities["per_source"].values() for c in cols
    }

    previous_error = None
    for attempt in range(2):
        plan = propose_plan(question, available, previous_error)
        if isinstance(plan, PlanError):
            previous_error = plan.error
            continue
        try:
            result = execute(plan, datasets, available)
            result["plan"] = plan.model_dump()
            return result
        except (PlanValidationError, FilterError) as exc:
            previous_error = str(exc)

    return {"status": "unsupported", "reason": previous_error or "Could not build a valid plan for this question."}
