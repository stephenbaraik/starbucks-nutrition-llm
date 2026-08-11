import ast
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from src.viz.charts import macro_composition, top_n_bar


def _combined():
    return pd.DataFrame({
        "item_name": ["Latte", "Bagel", "Mocha"],
        "source": ["drinks", "food", "drinks"],
        "calories": [190.0, 300.0, 290.0],
        "protein_g": [10.0, 8.0, 12.0],
    })


def test_no_streamlit_import():
    tree = ast.parse(Path("src/viz/charts.py").read_text())
    names = {n.name for node in ast.walk(tree) if isinstance(node, ast.Import) for n in node.names}
    modules = names | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "streamlit" not in modules


def test_top_n_bar_returns_figure():
    fig = top_n_bar(_combined(), "calories", n=2)
    assert isinstance(fig, go.Figure)


def test_macro_composition_returns_figure():
    normalised = pd.DataFrame({
        "nutrient": ["Protein (g)"],
        "drinks_per_100kcal": [3.63],
        "food_per_100kcal": [3.08],
    })
    fig = macro_composition(normalised)
    assert isinstance(fig, go.Figure)


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
