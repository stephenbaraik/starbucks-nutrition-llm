"""
DataFrame -> compact JSON facts payload.

The LLM only ever sees this payload, never raw rows, so the prompt stays a
fixed, small size no matter how many menu items are loaded — 74 drinks or
7,400 would cost the same number of tokens. `unavailable_nutrients` and
`inferred_fields` are always included (even when empty) so the LLM's
narration prompt can be written to always check them, which is what makes
the model state a gap in the data instead of quietly working around it.
"""

from __future__ import annotations

import hashlib
import json

from src.analytics.compare import comparison_caveat, normalised_comparison, raw_comparison
from src.analytics.stats import derived_ratios, describe, top_n
from src.config import NUTRIENT_LABELS


def build_facts(datasets: dict, capabilities: dict, top_n_count: int = 3) -> dict:
    """Build the one JSON object the opening chat summary is generated from.

    Everything in here is something pandas already computed — mean/median/
    std/min/max per nutrient, the standout items by calories, the
    fat-to-protein ratio, and a drinks-vs-food comparison. The LLM's only
    job is to turn these numbers into readable prose; it never sees
    anything it could compute (or miscompute) itself.
    """
    sources = {}
    for name, dataset in datasets.items():
        df = dataset.frame
        available = capabilities["per_source"][name]
        # One metrics block per nutrient this source actually has —
        # describe() already skips anything missing, so this loop only
        # ever sees real columns.
        metrics = {}
        for row in describe(df, available).to_dict("records"):
            col = next(c for c in available if NUTRIENT_LABELS.get(c, c) == row["nutrient"])
            metrics[col] = {
                "mean": round(row["mean"], 2) if row["mean"] == row["mean"] else None,  # NaN check
                "median": row["median"],
                "std": round(row["std"], 2) if row["std"] == row["std"] else None,
                "min": row["min"],
                "max": row["max"],
                "coverage": f"{row['n']}/{len(df)}",
            }
        # A few named standout items give the LLM something concrete to
        # talk about instead of only abstract statistics.
        top = top_n(df, "calories", n=top_n_count) if "calories" in df.columns else df.head(0)
        ratios = derived_ratios(df)
        mean_fat_to_protein = ratios["fat_to_protein"].mean() if "fat_to_protein" in ratios else None
        has_ratio = mean_fat_to_protein is not None and mean_fat_to_protein == mean_fat_to_protein
        sources[name] = {
            "n_items": len(df),
            "rows_excluded_no_data": dataset.report.rows_no_nutrition,
            "metrics": metrics,
            "mean_fat_to_protein_ratio": round(mean_fat_to_protein, 2) if has_ratio else None,
            "top_by_calories": [
                {"item": r["item_name"], "calories": r["calories"]}
                for r in top.to_dict("records")
            ],
        }

    comparable = capabilities["comparable"]
    return {
        "sources": sources,
        # Both the raw and per-100-kcal comparisons are included — see
        # analytics/compare.py for why neither one alone is the full story.
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
    """sha256 of canonical JSON, for cache keys.

    app.py uses this to detect "did the data actually change" and only
    re-ask the LLM for a new opening summary when it did — sort_keys=True
    makes the hash independent of dict ordering.
    """
    canonical = json.dumps(facts, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def data_briefing(facts: dict) -> str:
    """Create a natural-language opening message from the pandas facts only.

    This is the deterministic fallback used when there's no Groq key (or
    the call fails) — simpler and shorter than the LLM version, built with
    plain string formatting, but still a real sentence-by-sentence summary
    rather than an error message.
    """
    sources = facts["sources"]
    drinks = sources.get("drinks")
    food = sources.get("food")
    sentences = []

    counts = []
    if drinks:
        counts.append(f"{drinks['n_items']} drinks")
    if food:
        counts.append(f"{food['n_items']} food items")
    if counts:
        sentences.append("The loaded menu data contains " + " and ".join(counts) + ".")

    if drinks and food:
        drink_calories = drinks["metrics"].get("calories", {}).get("mean")
        food_calories = food["metrics"].get("calories", {}).get("mean")
        if drink_calories is not None and food_calories is not None:
            sentences.append(
                "Mean calories are "
                f"{drink_calories:g} kcal for drinks and {food_calories:g} kcal for food items."
            )

    unavailable = facts.get("unavailable_nutrients", [])
    if unavailable:
        sentences.append("The loaded files do not contain " + ", ".join(unavailable) + ".")

    if facts.get("inferred_fields"):
        sentences.append("Caffeine status is inferred from the item name, not measured.")

    caveats = facts.get("caveats", [])
    if caveats:
        sentences.append(caveats[0])
    return " ".join(sentences)
