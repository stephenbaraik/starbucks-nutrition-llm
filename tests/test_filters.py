import pandas as pd
import pytest

from src.analytics.filters import (
    FilterError,
    Predicate,
    apply_predicates,
    validate_predicate,
)


def _frame():
    return pd.DataFrame({
        "item_name": ["Latte", "Iced Tea", "Decaf Latte"],
        "calories": [190.0, 80.0, 150.0],
        "caffeine_inferred": [True, True, False],
    })


def test_validate_predicate_rejects_unknown_field():
    with pytest.raises(FilterError):
        validate_predicate(Predicate("sugars_g", ">", 5), available={"calories"})


def test_validate_predicate_rejects_unknown_op():
    with pytest.raises(FilterError):
        validate_predicate(Predicate("calories", "~=", 5), available={"calories"})


def test_apply_predicates_composes_and_filters():
    df = _frame()
    out = apply_predicates(df, [Predicate("calories", ">", 100)], available={"calories"})
    assert list(out["item_name"]) == ["Latte", "Decaf Latte"]


def test_apply_predicates_raises_before_touching_frame_on_unknown_field():
    df = _frame()
    with pytest.raises(FilterError):
        apply_predicates(df, [Predicate("sugars_g", ">", 5)], available={"calories"})


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
