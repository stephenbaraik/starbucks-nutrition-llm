"""
Cross-source comparison views.

Raw and per-100-kcal views point opposite ways on the supplied data (food
wins on absolute calories, drinks win on carb/protein density), which is
exactly why both are computed rather than one being picked as "the" view.
"""

from __future__ import annotations

import pandas as pd

from src.config import NUTRIENT_LABELS


def raw_comparison(datasets: dict, comparable: list[str]) -> pd.DataFrame:
    """Mean and median per nutrient per source, plus non-null coverage.

    "Raw" means exactly what's in the file — a drink's serving-size number
    sitting next to a food item's per-item number, with no adjustment for
    the fact that those aren't really the same unit of comparison. That's
    why comparison_caveat() exists and is always shown alongside this.
    """
    rows = []
    for nutrient in comparable:
        row = {"nutrient": NUTRIENT_LABELS.get(nutrient, nutrient)}
        for source, dataset in datasets.items():
            s = dataset.frame[nutrient]
            row[f"{source}_mean"] = s.mean()
            row[f"{source}_median"] = s.median()
            row[f"{source}_n"] = int(s.notna().sum())
        rows.append(row)
    return pd.DataFrame(rows)


def normalised_comparison(datasets: dict, comparable: list[str]) -> pd.DataFrame:
    """Grams (or mg) per 100 kcal per nutrient per source. calories excluded.

    This is the fairer comparison: dividing every nutrient by that row's own
    calorie count puts drinks and food on the same footing regardless of
    serving size. Rows with zero calories are excluded from the denominator
    (`.where(... != 0)`) instead of producing a division-by-zero inf/NaN.
    """
    rows = []
    for nutrient in comparable:
        if nutrient == "calories":
            continue
        row = {"nutrient": NUTRIENT_LABELS.get(nutrient, nutrient)}
        for source, dataset in datasets.items():
            df = dataset.frame
            den = df["calories"].where(df["calories"] != 0)
            per_100kcal = (df[nutrient] / den * 100)
            row[f"{source}_per_100kcal"] = per_100kcal.mean()
        rows.append(row)
    return pd.DataFrame(rows)


def comparison_caveat() -> str:
    """One line the LLM is required to attach to any drinks-vs-food comparison.

    Without this, a raw calorie comparison reads as apples-to-apples when
    it isn't — drinks are measured per prepared serving, food per item.
    """
    return "Drinks are per prepared serving; food is per item. The two are not directly comparable on raw totals."
