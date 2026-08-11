"""
Orchestration: file in, clean canonical DataFrame plus report out.

Works on both the bundled files and arbitrary user uploads. Column mapping
comes from the resolver rather than a hardcoded table, so an uploaded CSV with
different headers still lands on the canonical schema. Where the resolver is
not confident, the caller (Streamlit) collects a manual mapping and passes it
back through `overrides`.

Also defines the capability registry, which is how the rest of the app avoids
assuming which nutrients exist. Neither supplied file carries sugar or
caffeine, so any code that assumes those columns will break. Code that asks
the registry will not.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.config import DRINKS_FILE, FOOD_FILE, NUTRIENT_COLS, NUTRIENT_LABELS
from src.ingestion.loader import read_csv_resilient
from src.ingestion.resolver import ResolutionReport, resolve_columns, apply_overrides
from src.ingestion.cleaner import (
    DataQualityReport, apply_schema, coerce_numeric,
    drop_empty_rows, resolve_duplicates, finalise,
)


@dataclass
class Dataset:
    frame: pd.DataFrame
    report: DataQualityReport
    resolution: ResolutionReport

    @property
    def name(self) -> str:
        return self.report.source

    @property
    def needs_user_mapping(self) -> bool:
        """True when the UI should show the manual column mapping panel."""
        return self.resolution.item_name_column is None or bool(self.resolution.unresolved)


def inspect_source(path_or_buffer, source: str):
    """
    Read and resolve without cleaning.

    Streamlit calls this first so it can render the mapping panel before
    committing to a full ingest.
    """
    raw, encoding = read_csv_resilient(path_or_buffer)
    return raw, encoding, resolve_columns(raw)


def load_source(path_or_buffer, source: str, overrides: dict | None = None) -> Dataset:
    """
    Run one file through the full ingestion pipeline.

    `overrides` maps a raw header to a canonical column, or to None to ignore
    it. User choices always win over the resolver's guesses.
    """
    raw, encoding, res = inspect_source(path_or_buffer, source)

    rep = DataQualityReport(source=source)
    rep.encoding = encoding
    rep.rows_read = len(raw)
    if encoding not in ("utf-8", "utf-8-sig"):
        rep.notes.append(
            f"File is not UTF-8. A default read_csv() raises UnicodeDecodeError "
            f"here; decoded as {encoding} by the fallback chain."
        )

    mapping = apply_overrides(res, overrides or {})
    rep.columns_resolved = dict(mapping)
    rep.columns_needing_confirmation = [m.raw for m in res.unresolved]
    for w in res.warnings:
        rep.notes.append(f"Column resolution: {w}")

    if "item_name" not in mapping.values():
        raise ValueError(
            f"No item name column could be identified for '{source}'. "
            f"Supply one via overrides."
        )

    # Conversions keyed by canonical name, since apply_schema renames first.
    conversions = {mapping[raw]: f for raw, f in res.conversions.items() if raw in mapping}

    # The five-stage cleaning pipeline, in order: rename to canonical
    # headers, coerce strings to numbers, drop rows with no data at all,
    # resolve duplicate/conflicting rows, then finalise (IDs, sort,
    # caffeine inference). Each stage appends to the same report so the
    # UI can show exactly what happened and in what order.
    df = apply_schema(raw, mapping, rep)
    df = coerce_numeric(df, rep, conversions=conversions)
    df = drop_empty_rows(df, rep)
    df = resolve_duplicates(df, rep)
    df = finalise(df, source, rep)
    return Dataset(frame=df, report=rep, resolution=res)


def load_all(drinks_path=None, food_path=None, overrides=None) -> dict[str, Dataset]:
    """Load both sources. Paths accept file-like objects from st.file_uploader."""
    overrides = overrides or {}
    return {
        "drinks": load_source(drinks_path or DRINKS_FILE, "drinks", overrides.get("drinks")),
        "food": load_source(food_path or FOOD_FILE, "food", overrides.get("food")),
    }


# --------------------------------------------------------------------------
# Capability registry
# --------------------------------------------------------------------------

def available_nutrients(df: pd.DataFrame) -> set[str]:
    """Nutrients present in the frame with at least one real value."""
    return {c for c in NUTRIENT_COLS if c in df.columns and df[c].notna().any()}


def capabilities(datasets: dict[str, Dataset]) -> dict:
    """
    What this data can and cannot answer.

    Drives the UI (hide impossible filters), the analytics layer (compare only
    the intersection), and the LLM prompts (state the gap rather than invent
    around it). Recomputed on every upload, so a richer CSV automatically
    unlocks the filters and comparisons its extra columns support.
    """
    per_source = {k: available_nutrients(v.frame) for k, v in datasets.items()}
    # "present anywhere" (union) vs "present in every source" (intersection)
    # are different questions: the first drives what's missing entirely,
    # the second drives what's safe to put in a cross-source comparison.
    all_present = set().union(*per_source.values()) if per_source else set()
    comparable = set.intersection(*per_source.values()) if per_source else set()

    return {
        "per_source": {k: sorted(v) for k, v in per_source.items()},
        "comparable": sorted(comparable),
        "single_source_only": {
            k: sorted(v - comparable) for k, v in per_source.items() if v - comparable
        },
        "unavailable": sorted(set(NUTRIENT_COLS) - all_present),
        "unavailable_labels": [
            NUTRIENT_LABELS[c] for c in sorted(set(NUTRIENT_COLS) - all_present)
        ],
        "caffeine_is_inferred": any(
            "caffeine_inferred" in v.frame.columns for v in datasets.values()
        ),
    }


def combined_frame(datasets: dict[str, Dataset]) -> pd.DataFrame:
    """Long-format union of all sources, for cross-dataset charting."""
    return pd.concat([d.frame for d in datasets.values()], ignore_index=True)
