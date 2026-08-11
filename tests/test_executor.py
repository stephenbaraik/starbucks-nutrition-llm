import pandas as pd
import pytest
from dataclasses import dataclass

from src.llm.executor import PlanValidationError, execute
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


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
