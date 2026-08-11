"""
Figure builders. No Streamlit import here on purpose — every function takes
plain pandas in and returns a plotly Figure out, so any caller (the app, a
script, a test) can render, inspect, or export it without needing a running
Streamlit session.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.config import NUTRIENT_LABELS


def top_n_bar(df: pd.DataFrame, nutrient: str, n: int = 10) -> go.Figure:
    """Horizontal bar of the top n items by nutrient, units in the axis label."""
    # Horizontal orientation so long item names stay readable instead of
    # being crammed and rotated along a vertical x-axis.
    top = df.dropna(subset=[nutrient]).nlargest(n, nutrient)
    label = NUTRIENT_LABELS.get(nutrient, nutrient)
    fig = px.bar(
        top.sort_values(nutrient),  # ascending, so the biggest bar ends up on top
        x=nutrient, y="item_name", orientation="h",
        labels={nutrient: label, "item_name": ""},
        title=f"Top {n} by {label}",
    )
    return fig


def macro_composition(normalised: pd.DataFrame) -> go.Figure:
    """Grouped bar of per-100kcal macro composition per source.

    Takes the output of analytics.compare.normalised_comparison() directly
    — one bar per source, side by side, for each nutrient — so drinks and
    food are compared on the same per-100-kcal footing rather than raw
    totals.
    """
    source_cols = [c for c in normalised.columns if c.endswith("_per_100kcal")]
    fig = go.Figure()
    for col in source_cols:
        source = col.replace("_per_100kcal", "")
        fig.add_bar(name=source, x=normalised["nutrient"], y=normalised[col])
    fig.update_layout(barmode="group", title="Macro composition per 100 kcal", yaxis_title="g per 100 kcal")
    return fig
