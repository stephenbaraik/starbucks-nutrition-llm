"""
Figure builders. No Streamlit import here (FR-24) — every function returns a
plotly Figure that any caller can render, test, or export.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.config import NUTRIENT_LABELS


def top_n_bar(df: pd.DataFrame, nutrient: str, n: int = 10) -> go.Figure:
    """Horizontal bar of the top n items by nutrient, units in the axis label."""
    top = df.dropna(subset=[nutrient]).nlargest(n, nutrient)
    label = NUTRIENT_LABELS.get(nutrient, nutrient)
    fig = px.bar(
        top.sort_values(nutrient),
        x=nutrient, y="item_name", orientation="h",
        labels={nutrient: label, "item_name": ""},
        title=f"Top {n} by {label}",
    )
    return fig


def distribution_by_source(combined: pd.DataFrame, nutrient: str = "calories") -> go.Figure:
    """Box plot of a nutrient split by source."""
    label = NUTRIENT_LABELS.get(nutrient, nutrient)
    fig = px.box(
        combined.dropna(subset=[nutrient]),
        x="source", y=nutrient, color="source",
        labels={nutrient: label, "source": "Source"},
        title=f"{label} distribution by source",
    )
    return fig


def macro_composition(normalised: pd.DataFrame) -> go.Figure:
    """Stacked bar of per-100kcal macro composition per source."""
    source_cols = [c for c in normalised.columns if c.endswith("_per_100kcal")]
    fig = go.Figure()
    for col in source_cols:
        source = col.replace("_per_100kcal", "")
        fig.add_bar(name=source, x=normalised["nutrient"], y=normalised[col])
    fig.update_layout(barmode="group", title="Macro composition per 100 kcal", yaxis_title="g per 100 kcal")
    return fig


def scatter(combined: pd.DataFrame, x: str, y: str) -> go.Figure:
    """Scatter of two nutrients, coloured by source."""
    fig = px.scatter(
        combined.dropna(subset=[x, y]),
        x=x, y=y, color="source", hover_name="item_name",
        labels={x: NUTRIENT_LABELS.get(x, x), y: NUTRIENT_LABELS.get(y, y)},
        title=f"{NUTRIENT_LABELS.get(x, x)} vs {NUTRIENT_LABELS.get(y, y)}",
    )
    return fig
