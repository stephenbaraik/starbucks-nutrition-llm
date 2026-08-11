from dataclasses import dataclass

import pandas as pd
import pytest

from src.llm.executor import PlanValidationError, answer, execute, narrate_result
from src.llm.schemas import Filter, QueryPlan


@dataclass
class _Dataset:
    frame: pd.DataFrame


def _datasets():
    drinks = pd.DataFrame({
        "item_name": ["Latte", "Mocha", "Iced Tea"],
        "source": ["drinks", "drinks", "drinks"],
        "calories": [190.0, 290.0, 80.0],
        "protein_g": [10.0, 12.0, 0.0],
    })
    return {"drinks": _Dataset(frame=drinks)}


AVAILABLE = {"calories", "protein_g"}
CAPABILITIES = {
    "comparable": ["calories", "protein_g"],
    "per_source": {"drinks": ["calories", "protein_g"]},
    "unavailable_labels": ["Sugars (g)"],
}


def test_execute_mean_over_dataset():
    plan = QueryPlan(dataset="drinks", metric="calories", op="mean")
    out = execute(plan, _datasets(), AVAILABLE)
    assert out["status"] == "ok"
    assert round(out["result"], 2) == 186.67


def test_execute_applies_filters_via_shared_predicate_engine():
    plan = QueryPlan(
        dataset="drinks", metric="calories", op="max",
        filters=[Filter(field="calories", op="<", value=200)],
    )
    out = execute(plan, _datasets(), AVAILABLE)
    assert out["result"] == 190.0


def test_execute_rejects_unknown_metric_before_touching_frame():
    plan = QueryPlan(dataset="drinks", metric="sugars_g", op="mean")
    with pytest.raises(PlanValidationError):
        execute(plan, _datasets(), AVAILABLE)


def test_execute_top_n():
    plan = QueryPlan(dataset="drinks", metric="calories", op="top_n", limit=2)
    out = execute(plan, _datasets(), AVAILABLE)
    assert [r["item_name"] for r in out["rows"]] == ["Mocha", "Latte"]


def test_narrate_result_uses_the_executed_top_n_rows_only():
    plan = QueryPlan(dataset="drinks", metric="calories", op="top_n", limit=2)
    result = execute(plan, _datasets(), AVAILABLE)
    prose = narrate_result(plan, result)
    assert prose == "The highest Calories (kcal) values among the loaded drinks are: Mocha (290); Latte (190)."


def test_narrate_result_describes_a_scalar_value_naturally():
    plan = QueryPlan(dataset="drinks", metric="calories", op="mean")
    result = execute(plan, _datasets(), AVAILABLE)
    prose = narrate_result(plan, result)
    assert prose == "The mean Calories (kcal) for the loaded drinks is 186.67."


class _FakeClient:
    enabled = True

    def __init__(self, response):
        self.response = response

    def complete(self, system, user, json_mode=False):
        return self.response


def test_answer_uses_llm_narration_when_a_client_is_present(monkeypatch):
    def fake_plan(question, available, previous_error=None):
        return QueryPlan(dataset="drinks", metric="calories", op="mean")

    monkeypatch.setattr("src.llm.executor.propose_plan", fake_plan)
    result = answer(
        "What is the average calories of drinks?",
        _datasets(),
        CAPABILITIES,
        client=_FakeClient("The drinks average about 187 calories."),
    )
    assert result["status"] == "ok"
    assert result["narrative"] == "The drinks average about 187 calories."


def test_answer_falls_back_to_template_when_llm_errors(monkeypatch):
    def fake_plan(question, available, previous_error=None):
        return QueryPlan(dataset="drinks", metric="calories", op="mean")

    monkeypatch.setattr("src.llm.executor.propose_plan", fake_plan)
    result = answer(
        "What is the average calories of drinks?",
        _datasets(),
        CAPABILITIES,
        client=_FakeClient("The summary service returned an error (RateLimitError). Please try again later."),
    )
    assert result["status"] == "ok"
    assert result["narrative"] == "The mean Calories (kcal) for the loaded drinks is 186.67."


def test_answer_handles_a_greeting_without_planning(monkeypatch):
    def planner_should_not_run(*args, **kwargs):
        raise AssertionError("Small talk must not reach the query planner")

    monkeypatch.setattr("src.llm.executor.propose_plan", planner_should_not_run)
    result = answer("hello", _datasets(), CAPABILITIES)
    assert result["status"] == "ok"
    assert result["narrative"].startswith("Hello!")
    assert "Calories (kcal)" in result["narrative"]


def test_answer_explains_what_the_loaded_data_can_answer():
    result = answer("what can you do?", _datasets(), CAPABILITIES)
    assert result["status"] == "ok"
    assert "Protein (g)" in result["narrative"]
    assert "Sugars (g)" in result["narrative"]


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
