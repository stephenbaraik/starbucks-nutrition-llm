import pandas as pd

from src.analytics.stats import coverage, derived_ratios, describe, safe_ratio, top_n


def _frame():
    return pd.DataFrame({
        "item_name": ["a", "b", "c"],
        "calories": [100.0, 0.0, 200.0],
        "protein_g": [0.0, 5.0, 10.0],
        "total_fat_g": [2.0, 4.0, 6.0],
        "total_carbs_g": [10.0, 20.0, 30.0],
        "fiber_g": [1.0, None, 3.0],
    })


def test_safe_ratio_zero_and_null_denominator_is_nan_not_inf():
    num = pd.Series([10.0, 10.0, 10.0])
    den = pd.Series([0.0, None, 5.0])
    result = safe_ratio(num, den)
    assert result.iloc[0] != result.iloc[0]  # NaN
    assert result.iloc[1] != result.iloc[1]  # NaN
    assert result.iloc[2] == 2.0
    assert not (result.abs() == float("inf")).any()


def test_derived_ratios_handles_zero_protein_and_zero_calories():
    ratios = derived_ratios(_frame())
    assert pd.isna(ratios["fat_to_protein"].iloc[0])       # protein 0
    assert pd.isna(ratios["carbs_per_100kcal"].iloc[1])    # calories 0
    assert ratios["protein_per_100kcal"].iloc[2] == 5.0    # 10/200*100


def test_coverage_reports_non_null_over_total():
    cov = coverage(_frame(), ["fiber_g", "calories"])
    assert cov["fiber_g"] == "2/3"
    assert cov["calories"] == "3/3"


def test_describe_restricted_to_requested_nutrients_only():
    out = describe(_frame(), ["calories"])
    assert list(out["nutrient"]) == ["Calories (kcal)"]
    assert out["n"].iloc[0] == 3


def test_top_n_excludes_nulls_and_sorts_descending():
    df = _frame()
    out = top_n(df, "fiber_g", n=2)
    assert list(out["item_name"]) == ["c", "a"]


if __name__ == "__main__":
    import sys

    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
