"""question -> QueryPlan, via the LLM in JSON mode. One retry on validation failure."""

from __future__ import annotations

import json

from pydantic import ValidationError

from src.config import LLM_MODEL_PLANNER
from src.llm.client import LLMClient
from src.llm.schemas import PlanError, QueryPlan

PLANNER_SYSTEM = """You translate a question about a nutrition dataset into a JSON query plan.

Available fields: {available}

Return ONLY a JSON object shaped like:
{{"dataset": "drinks"|"food"|"both", "metric": "<field>", "op": "mean"|"median"|"max"|"min"|"sum"|"count"|"top_n", "filters": [{{"field": "<field>", "op": ">"|">="|"<"|"<="|"=="|"!=", "value": <number>}}], "group_by": "<field>"|null, "limit": <int>|null}}

Rules:
- metric, group_by, and every filter field MUST be one of the available fields, or a question about
  an absent field must be declined by returning {{"error": "<reason naming the missing field>"}}.
- A subjective question ("healthiest", "best") is not computable. Return {{"error": "<reason>"}}.
- No prose, no markdown, JSON only."""


def propose_plan(question: str, available: set[str], previous_error: str | None = None) -> QueryPlan | PlanError:
    client = LLMClient(model=LLM_MODEL_PLANNER)
    system = PLANNER_SYSTEM.format(available=sorted(available))
    user = question
    if previous_error:
        user = f"{question}\n\nThe previous plan was invalid: {previous_error}\nTry again."

    raw = client.complete(system, user, json_mode=True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return PlanError(error="The planner did not return valid JSON.")

    if "error" in data:
        return PlanError(**data)

    try:
        return QueryPlan(**data)
    except ValidationError as exc:
        return PlanError(error=str(exc))
