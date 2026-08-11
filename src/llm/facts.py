"""
DataFrame -> compact JSON facts payload.

The LLM only ever sees this payload, never raw rows (FR-26), so prompt size
stays independent of row count. `unavailable_nutrients` and `inferred_fields`
are mandatory keys — they are what makes the model state gaps (FR-28) instead
of working around them.
"""

from __future__ import annotations

import hashlib
import json

from src.analytics.compare import comparison_caveat, normalised_comparison, raw_comparison
from src.analytics.stats import describe, top_n
from src.config import NUTRIENT_LABELS


def build_facts(datasets: dict, capabilities: dict, top_n_count: int = 5) -> dict:
    sources = {}
    for name, dataset in datasets.items():
        df = dataset.frame
        available = capabilities["per_source"][name]
        metrics = {}
        for row in describe(df, available).to_dict("records"):
            col = next(c for c in available if NUTRIENT_LABELS.get(c, c) == row["nutrient"])
            metrics[col] = {
                "mean": round(row["mean"], 2) if row["mean"] == row["mean"] else None,
                "median": row["median"],
                "max": row["max"],
                "coverage": f"{row['n']}/{len(df)}",
            }
        top = top_n(df, "calories", n=top_n_count) if "calories" in df.columns else df.head(0)
        sources[name] = {
            "n_items": len(df),
            "rows_excluded_no_data": dataset.report.rows_no_nutrition,
            "metrics": metrics,
            "top_by_calories": [
                {"item": r["item_name"], "calories": r["calories"]}
                for r in top.to_dict("records")
            ],
        }

    comparable = capabilities["comparable"]
    return {
        "sources": sources,
        "comparison": {
            "raw": raw_comparison(datasets, comparable).to_dict("records"),
            "per_100_kcal": normalised_comparison(datasets, comparable).to_dict("records"),
        },
        "unavailable_nutrients": capabilities["unavailable_labels"],
        "inferred_fields": (
            ["caffeine (from item name, not measured)"]
            if capabilities.get("caffeine_is_inferred") else []
        ),
        "caveats": [comparison_caveat()],
    }


def facts_digest(facts: dict) -> str:
    """sha256 of canonical JSON, for cache keys."""
    canonical = json.dumps(facts, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
