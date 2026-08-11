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
    """Mean, median, std, min, max and non-null count per nutrient."""
    rows = []
    for col in nutrients:
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
    """num / den, NaN where den is zero or null. Never inf."""
    den_safe = den.where(den != 0)
    return num / den_safe


def derived_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """fat_to_protein, carbs/protein/fiber per 100 kcal, all via safe_ratio."""
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
    """Top n rows by nutrient, nulls excluded."""
    return df.dropna(subset=[nutrient]).sort_values(nutrient, ascending=ascending).head(n)
