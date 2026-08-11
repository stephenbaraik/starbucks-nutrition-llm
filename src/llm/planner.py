"""question -> QueryPlan, via the LLM in JSON mode. One retry on validation failure."""

from __future__ import annotations

import json

from pydantic import ValidationError

from src.config import LLM_MODEL_PLANNER
from src.llm.client import LLMClient
from src.llm.schemas import PlanError, QueryPlan
from src.utils.logging import get_logger

logger = get_logger(__name__)

PLANNER_SYSTEM = """You translate a question about a nutrition dataset into a JSON query plan.

Available fields: {available}

Return ONLY a JSON object shaped like:
{{"dataset": "drinks"|"food"|"both", "metric": "<field>", "op": "mean"|"median"|"max"|"min"|"sum"|"count"|"top_n", "filters": [{{"field": "<field>", "op": ">"|">="|"<"|"<="|"=="|"!=", "value": <number>}}], "group_by": "<field>"|null, "limit": <int>|null}}

Rules:
- A question asking WHICH item/drink/food has the most/least/highest/lowest value of a field
  (i.e. it wants an item name, not just a number) MUST use op="top_n" with limit=1, never "max"/"min".
  "max"/"min" are only for questions asking for the bare number itself, with no item name wanted.
  Example: "Which food has the most protein?" -> {{"dataset": "food", "metric": "protein_g", "op": "top_n", "filters": [], "group_by": null, "limit": 1}}
  Example: "What is the maximum protein in food?" -> {{"dataset": "food", "metric": "protein_g", "op": "max", "filters": [], "group_by": null, "limit": null}}
- metric, group_by, and every filter field MUST be one of the available fields, or a question about
  an absent field must be declined by returning {{"error": "<reason naming the missing field>"}}.
- A subjective question ("healthiest", "best") is not computable. Return {{"error": "<reason>"}}.
- A greeting, small talk, or a request unrelated to the dataset is not a data query. Return
  {{"error": "<reason>"}} and do not choose a default metric.
- If the question does not clearly request a calculation, ranking, count, grouping, or filter over
  an available field, return {{"error": "<reason>"}} rather than guessing what to analyse.
- No prose, no markdown, JSON only."""


def propose_plan(question: str, available: set[str], previous_error: str | None = None) -> QueryPlan | PlanError:
    """Ask the LLM to turn a natural-language question into a QueryPlan.

    Returns either a validated QueryPlan (ready for executor.execute) or a
    PlanError explaining why it couldn't — the caller (executor.answer)
    decides whether to retry with the error fed back in, or give up.
    """
    # A smaller, faster model than the one used for narration — this call
    # only needs to produce constrained JSON, not write good prose.
    client = LLMClient(model=LLM_MODEL_PLANNER)
    system = PLANNER_SYSTEM.format(available=sorted(available))
    user = question
    if previous_error:
        # Second attempt: tell the model exactly what was wrong last time
        # instead of just asking again and hoping for something different.
        user = f"{question}\n\nThe previous plan was invalid: {previous_error}\nTry again."

    raw = client.complete(system, user, json_mode=True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # The model didn't follow the "JSON only" instruction — treat that
        # as a plan failure rather than letting json.loads's exception
        # propagate up.
        logger.warning("Planner returned non-JSON output: %r", raw[:200])
        return PlanError(error="The planner did not return valid JSON.")

    # The model explicitly declined (subjective question, missing field,
    # small talk, ...) — trust that decision, don't second-guess it.
    if "error" in data:
        return PlanError(**data)

    try:
        # Pydantic re-validates the shape here regardless of what the
        # prompt asked for — the prompt is a request, not a guarantee.
        return QueryPlan(**data)
    except ValidationError as exc:
        logger.warning("Planner returned an invalid plan shape: %s", exc)
        return PlanError(error=str(exc))
