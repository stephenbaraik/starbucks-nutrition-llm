"""
plan -> pandas result, via the exact functions in analytics/filters.py — the
query path never reimplements filtering. No eval, exec, or getattr on
model-supplied names anywhere here; every op the LLM can request is one of a
fixed set of branches below, never an arbitrary string it invented.
"""

from __future__ import annotations

import math
import re

from src.analytics.filters import FilterError, Predicate, apply_predicates
from src.analytics.stats import top_n
from src.config import NUTRIENT_LABELS
from src.ingestion.pipeline import combined_frame
from src.llm.planner import propose_plan
from src.llm.prompts import NARRATE_SYSTEM_V1, narrate_user_prompt
from src.llm.schemas import PlanError, QueryPlan
from src.utils.logging import get_logger

logger = get_logger(__name__)

_AGG_OPS = {"mean", "median", "max", "min", "sum", "count"}


class PlanValidationError(ValueError):
    pass


# Small talk ("hi", "thanks", "what can I ask") is answered directly here
# instead of being sent to the query planner — there's no data question to
# plan for, and it saves an LLM call.
_GREETING = re.compile(
    r"^(?:hi|hello|hey|good morning|good afternoon|good evening)(?:\s+there)?[!,.\s]*$",
    re.IGNORECASE,
)
_THANKS = re.compile(r"^(?:thanks|thank you|thx)[!,.\s]*$", re.IGNORECASE)
_HELP = re.compile(r"^(?:what can (?:you|i) ask|help|what can you do)[?.!\s]*$", re.IGNORECASE)


def conversational_reply(question: str, capabilities: dict) -> str | None:
    """Handle basic chat without sending small talk to the data-query planner."""
    text = question.strip()
    available = ", ".join(
        NUTRIENT_LABELS.get(field, field) for field in capabilities.get("comparable", [])
    )
    unavailable = ", ".join(capabilities.get("unavailable_labels", []))
    prompt = f"You can ask about {available}." if available else "Ask a question about the loaded menu data."

    if _GREETING.fullmatch(text):
        return f"Hello! I can help you explore the loaded menu data. {prompt}"
    if _THANKS.fullmatch(text):
        return f"You're welcome. {prompt}"
    if _HELP.fullmatch(text):
        limitation = f" The loaded files do not contain {unavailable}." if unavailable else ""
        return f"I can answer questions about {available} in the loaded menu data.{limitation}"
    return None


def _source_label(dataset: str) -> str:
    return {"drinks": "drinks", "food": "food items", "both": "drinks and food items"}[dataset]


def _field_label(field: str) -> str:
    return NUTRIENT_LABELS.get(field, field.replace("_", " "))


def _format_value(value) -> str:
    """Format a pandas scalar for prose without changing its value."""
    value = value.item() if hasattr(value, "item") else value
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def narrate_result(plan: QueryPlan, result: dict) -> str:
    """Turn an already executed pandas result into data-only natural language.

    This is the deterministic fallback narration — used when the LLM is
    disabled or errors out (see answer() below), so the user still gets a
    real, plain-English answer even with no API key configured.
    """
    source = _source_label(plan.dataset)
    metric = _field_label(plan.metric)
    qualifier = " for items matching the requested conditions" if plan.filters else ""

    if plan.op == "top_n":
        rows = result.get("rows", [])
        if not rows:
            return f"No {source} in the loaded data have a recorded {metric}{qualifier}."
        items = "; ".join(
            f"{row['item_name']} ({_format_value(row[plan.metric])})" for row in rows
        )
        return f"The highest {metric} values among the loaded {source}{qualifier} are: {items}."

    value = result.get("result")
    if plan.group_by and isinstance(value, dict):
        grouped = "; ".join(f"{group}: {_format_value(amount)}" for group, amount in value.items())
        operation = {"mean": "mean", "median": "median", "max": "maximum", "min": "minimum", "sum": "total", "count": "count"}[plan.op]
        return f"The {operation} {metric} for the loaded {source}{qualifier}, grouped by {plan.group_by}, is: {grouped}."

    if value is None:
        return f"No {source} in the loaded data have a recorded {metric}{qualifier}."
    if plan.op == "count":
        return f"There are {_format_value(value)} loaded {source} with a recorded {metric}{qualifier}."

    operation = {"mean": "mean", "median": "median", "max": "maximum", "min": "minimum", "sum": "total"}[plan.op]
    return f"The {operation} {metric} for the loaded {source}{qualifier} is {_format_value(value)}."


def _select_frame(plan: QueryPlan, datasets: dict):
    if plan.dataset == "both":
        return combined_frame(datasets)
    return datasets[plan.dataset].frame


def _validate_fields(plan: QueryPlan, available: set[str]) -> None:
    """Reject any field name the LLM invented that isn't actually in the data."""
    if plan.metric not in available:
        raise PlanValidationError(f"'{plan.metric}' is not an available field.")
    if plan.group_by is not None and plan.group_by not in available | {"source"}:
        raise PlanValidationError(f"'{plan.group_by}' is not an available field.")


def execute(plan: QueryPlan, datasets: dict, available: set[str]) -> dict:
    """Run a validated plan against pandas. This is the only place a plan
    actually touches data — the LLM never sees a DataFrame, only this
    function's JSON-safe output.
    """
    _validate_fields(plan, available)
    df = _select_frame(plan, datasets)

    # Any filters in the plan (e.g. "calories < 500") get applied the same
    # way a UI filter would — through the shared, validated Predicate path.
    predicates = [Predicate(f.field, f.op, f.value) for f in plan.filters]
    df = apply_predicates(df, predicates, available)

    if plan.op == "top_n":
        # "which item has the most/least X" — return named rows, not a
        # bare number, so the narration can name the actual item.
        result = top_n(df, plan.metric, n=plan.limit or 5)
        rows = result[["item_name", plan.metric]].to_dict("records")
        return {"status": "ok", "rows": [{k: _to_native(v) for k, v in row.items()} for row in rows]}

    series = df[plan.metric]
    if plan.group_by:
        # "average X by source" — one aggregate per group.
        agg = series.groupby(df[plan.group_by]).agg(plan.op)
        return {"status": "ok", "result": {k: _to_native(v) for k, v in agg.to_dict().items()}}

    # Plain aggregate over the whole (filtered) frame — mean, max, count, etc.
    value = series.agg(plan.op)
    return {"status": "ok", "result": None if isinstance(value, float) and math.isnan(value) else _to_native(value)}


def _to_native(value):
    """pandas/numpy scalars aren't JSON-serializable; unwrap to plain Python types."""
    return value.item() if hasattr(value, "item") else value


def _llm_narration(question: str, plan: QueryPlan, result: dict, client) -> str | None:
    """Ask the LLM to write the answer in its own words, from the executed result only."""
    if client is None or not client.enabled:
        return None
    payload = {
        "dataset": plan.dataset,
        "op": plan.op,
        "metric": _field_label(plan.metric),
        "rows": result.get("rows"),
        "result": result.get("result"),
    }
    text = client.complete(NARRATE_SYSTEM_V1, narrate_user_prompt(question, payload))
    if text.startswith("The summary service returned an error"):
        return None
    return text


def answer(question: str, datasets: dict, capabilities: dict, client=None) -> dict:
    """The whole loop: plan -> validate -> execute -> narrate. One retry on failure."""
    # Greetings/thanks/help never reach the planner at all.
    small_talk = conversational_reply(question, capabilities)
    if small_talk:
        return {"status": "ok", "narrative": small_talk}

    available = set(capabilities["comparable"]) | {
        c for cols in capabilities["per_source"].values() for c in cols
    }

    # Up to two tries: if the first plan is invalid (bad field, bad op,
    # unparseable JSON, ...), feed the error back to the planner once and
    # let it try again before giving up on the question entirely.
    previous_error = None
    for attempt in range(2):
        plan = propose_plan(question, available, previous_error)
        if isinstance(plan, PlanError):
            previous_error = plan.error
            continue
        try:
            result = execute(plan, datasets, available)
            result["plan"] = plan.model_dump()
            # Prefer the LLM's phrasing; fall back to the deterministic
            # narration if the LLM is off or its call failed.
            result["narrative"] = (
                _llm_narration(question, plan, result, client) or narrate_result(plan, result)
            )
            return result
        except (PlanValidationError, FilterError) as exc:
            previous_error = str(exc)

    logger.info("Question declined after retry: %r (reason=%s)", question, previous_error)
    return {"status": "unsupported", "reason": previous_error or "Could not build a valid plan for this question."}
