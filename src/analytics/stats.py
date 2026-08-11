"""
Descriptive statistics and derived ratios.

Every function is restricted to the nutrients it is handed. Callers pass
`capabilities()["comparable"]` or a per-source list, never a literal column
name, so a nutrient absent from the frame is never silently assumed present.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from src.config import NUTRIENT_LABELS


def describe(df: pd.DataFrame, nutrients: Iterable[str]) -> pd.DataFrame:
    """Mean, median, std, min, max and non-null count per nutrient.

    One row per nutrient. This is the table both the Data & Stats tab and
    the LLM's opening summary are built from, so its shape (nutrient, mean,
    median, std, min, max, n) is what the LLM prompt asks for by name.
    """
    rows = []
    for col in nutrients:
        # Skip rather than error — a caller might pass the full comparable
        # list even for a source that's missing one of those nutrients.
        if col not in df.columns:
            continue
        s = df[col]
        rows.append({
            "nutrient": NUTRIENT_LABELS.get(col, col),
            "mean": s.mean(),
            "median": s.median(),
            "std": s.std(),
            "min": s.min(),
            "max": s.max(),
            "n": int(s.notna().sum()),
        })
    return pd.DataFrame(rows)


def coverage(df: pd.DataFrame, nutrients: Iterable[str]) -> dict[str, str]:
    """Non-null count over row count per nutrient, e.g. {"protein_g": "74/74"}."""
    total = len(df)
    return {
        col: f"{int(df[col].notna().sum())}/{total}"
        for col in nutrients
        if col in df.columns
    }


def safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    """num / den, NaN where den is zero or null. Never inf.

    Plain division would produce inf for a zero-calorie item and NaN would
    silently propagate anyway for a null — this just makes the zero case
    explicit instead of leaving an inf to break a mean() or a chart later.
    """
    den_safe = den.where(den != 0)
    return num / den_safe


def derived_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """fat_to_protein, carbs/protein/fiber per 100 kcal, all via safe_ratio.

    Each ratio only gets computed if both of its input columns actually
    exist — a food-only nutrient shouldn't produce a column of nothing but
    NaN for the drinks frame.
    """
    out = pd.DataFrame(index=df.index)
    out["item_name"] = df.get("item_name")
    if {"total_fat_g", "protein_g"}.issubset(df.columns):
        out["fat_to_protein"] = safe_ratio(df["total_fat_g"], df["protein_g"])
    if {"total_carbs_g", "calories"}.issubset(df.columns):
        out["carbs_per_100kcal"] = safe_ratio(df["total_carbs_g"] * 100, df["calories"])
    if {"protein_g", "calories"}.issubset(df.columns):
        out["protein_per_100kcal"] = safe_ratio(df["protein_g"] * 100, df["calories"])
    if {"fiber_g", "calories"}.issubset(df.columns):
        out["fiber_per_100kcal"] = safe_ratio(df["fiber_g"] * 100, df["calories"])
    return out


def top_n(df: pd.DataFrame, nutrient: str, n: int = 10, ascending: bool = False) -> pd.DataFrame:
    """Top n rows by nutrient, nulls excluded.

    Used both by the Charts tab (top-N bar chart) and by the chat's "which
    item has the most/least X" query path (via QueryPlan.op == "top_n").
    """
    return df.dropna(subset=[nutrient]).sort_values(nutrient, ascending=ascending).head(n)
