"""
Ingestion tests.

Two kinds here. Unit tests build tiny synthetic frames so a failure points at
one function. Contract tests assert facts about the supplied files, so if a
future file swap changes the shape of the data the suite says so loudly
instead of the app quietly producing different numbers.
"""

import numpy as np
import pandas as pd
import pytest

from src.config import NUTRIENT_ALIASES
from src.ingestion.cleaner import (
    DataQualityReport, apply_schema, coerce_numeric,
    drop_empty_rows, resolve_duplicates, infer_caffeine,
)
from src.ingestion.loader import read_csv_resilient, UnreadableFileError
from src.ingestion.pipeline import load_all, capabilities


# ---------------------------------------------------------------- unit tests

def test_apply_schema_strips_header_whitespace():
    df = pd.DataFrame({"Unnamed: 0": ["x"], " Calories ": ["10"], " Fat (g)": ["1"]})
    # apply_schema receives an already-resolved mapping; the resolver is tested separately
    rep = DataQualityReport(source="t")
    out = apply_schema(df, {'Unnamed: 0': 'item_name', 'Calories': 'calories', 'Fat (g)': 'total_fat_g'}, rep)
    assert "calories" in out.columns and "total_fat_g" in out.columns
    assert any("Stripped whitespace" in n for n in rep.notes)


def test_apply_schema_drops_unmapped_columns():
    df = pd.DataFrame({"Unnamed: 0": ["x"], "Calories": ["10"], "Mystery": ["?"]})
    rep = DataQualityReport(source="t")
    out = apply_schema(df, {'Unnamed: 0': 'item_name', 'Calories': 'calories', 'Fat (g)': 'total_fat_g'}, rep)
    assert "Mystery" not in out.columns
    assert rep.columns_dropped == ["Mystery"]


def test_hyphen_sentinel_becomes_null_and_is_counted():
    """The drinks file marks missing values with '-', which pandas reads as a
    string. Without this step isna() reports zero nulls on a half-empty file."""
    df = pd.DataFrame({"calories": ["45", "-", "80"], "protein_g": ["0", "-", "1"]})
    rep = DataQualityReport(source="t")
    out = coerce_numeric(df, rep)
    assert out["calories"].isna().sum() == 1
    assert rep.sentinel_cells["calories"] == 1
    assert out["calories"].dtype.kind == "f"


def test_drop_empty_rows_removes_only_fully_empty():
    df = pd.DataFrame({
        "item_name": ["keep", "drop", "partial"],
        "calories": [10.0, np.nan, np.nan],
        "protein_g": [1.0, np.nan, 2.0],
    })
    rep = DataQualityReport(source="t")
    out = drop_empty_rows(df, rep)
    assert set(out["item_name"]) == {"keep", "partial"}
    assert rep.rows_no_nutrition == 1


def test_exact_duplicates_dropped_silently():
    df = pd.DataFrame({"item_name": ["a", "a"], "calories": [10.0, 10.0]})
    rep = DataQualityReport(source="t")
    out = resolve_duplicates(df, rep)
    assert len(out) == 1
    assert rep.exact_duplicates_removed == 1
    assert rep.name_conflicts_resolved == 0


def test_name_conflict_keeps_more_complete_row():
    df = pd.DataFrame({
        "item_name": ["Iced Coffee", "Iced Coffee"],
        "calories": [0.0, 5.0],
        "sodium_mg": [np.nan, 5.0],
    })
    rep = DataQualityReport(source="t")
    out = resolve_duplicates(df, rep)
    assert len(out) == 1
    assert out.iloc[0]["calories"] == 5.0
    assert rep.name_conflicts_resolved == 1


@pytest.mark.parametrize("name,expected", [
    ("Caffè Latte", True),
    ("Pike Place® Roast", True),
    ("Decaf Pike Place Roast", False),
    ("Vanilla Crème", False),
    ("Tazo® Bottled Iced Passion", False),
    ("Tazo® Bottled Black Mango", True),
])
def test_caffeine_inference(name, expected):
    assert infer_caffeine(name) is expected


def test_loader_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        read_csv_resilient("does/not/exist.csv")


# ------------------------------------------------------------ contract tests

@pytest.fixture(scope="module")
def datasets():
    return load_all()


def test_food_file_is_utf16_and_still_loads(datasets):
    """A plain pd.read_csv() on this file raises UnicodeDecodeError at byte 0."""
    assert datasets["food"].report.encoding.startswith("utf-16")
    assert len(datasets["food"].frame) == 113


def test_drinks_retention_is_low_and_explained(datasets):
    rep = datasets["drinks"].report
    assert rep.rows_read == 177
    assert rep.rows_retained == 74
    assert rep.rows_no_nutrition == 85     # items listed with no published values
    assert rep.exact_duplicates_removed == 17
    assert rep.retention_pct < 50


def test_no_measured_sugar_or_caffeine_anywhere(datasets):
    """The brief asks for sugar rankings and a caffeine filter. Neither file
    supplies those columns. The app must detect this rather than assume."""
    caps = capabilities(datasets)
    assert "sugars_g" in caps["unavailable"]
    assert "caffeine_mg" in caps["unavailable"]


def test_sodium_is_drinks_only(datasets):
    caps = capabilities(datasets)
    assert caps["single_source_only"]["drinks"] == ["sodium_mg"]
    assert "sodium_mg" not in caps["comparable"]


def test_comparable_set_is_the_five_shared_nutrients(datasets):
    caps = capabilities(datasets)
    assert set(caps["comparable"]) == {
        "calories", "total_fat_g", "total_carbs_g", "fiber_g", "protein_g",
    }


def test_item_ids_are_unique_within_source(datasets):
    for ds in datasets.values():
        assert ds.frame["item_id"].is_unique


def test_every_drink_has_a_caffeine_verdict(datasets):
    assert datasets["drinks"].frame["caffeine_inferred"].notna().all()


# ------------------------------------------------------- resolver / upload

from src.ingestion.resolver import resolve_columns, normalise, apply_overrides


@pytest.mark.parametrize("raw,expected", [
    ("  Protein (g) ", "protein"),
    ("Protein", "protein"),
    ("Carb. (g)", "carb"),
    ("Total Carbohydrates (g)", "total carbohydrates"),
    ("Unnamed: 0", "unnamed 0"),
    ("Starbucks® Calories", "starbucks calories"),
])
def test_normalise(raw, expected):
    assert normalise(raw) == expected


def test_resolver_maps_both_protein_spellings_to_one_column():
    """The whole reason a mapping layer exists: the two supplied files spell
    the same quantity differently."""
    a = resolve_columns(pd.DataFrame({"Item": ["x"], "Protein": [1]}))
    b = resolve_columns(pd.DataFrame({"Item": ["x"], "Protein (g)": [1]}))
    assert a.mapping["Protein"] == "protein_g"
    assert b.mapping["Protein (g)"] == "protein_g"


@pytest.mark.parametrize("header,canonical", [
    ("Energy (kcal)", "calories"),
    ("Total Fat (g)", "total_fat_g"),
    ("Dietary Fibre (g)", "fiber_g"),
    ("Total Sugars (g)", "sugars_g"),
    ("Caffeine (mg)", "caffeine_mg"),
    ("PROTEIN", "protein_g"),
])
def test_resolver_handles_header_variants(header, canonical):
    df = pd.DataFrame({"Item": ["x"], header: [1]})
    assert resolve_columns(df).mapping.get(header) == canonical


def test_resolver_detects_unit_mismatch_and_offers_conversion():
    """Sodium declared in grams must be scaled, not read 1000x too small."""
    r = resolve_columns(pd.DataFrame({"Item": ["x"], "Sodium (g)": [1]}))
    assert r.conversions["Sodium (g)"] == 1000.0


def test_resolver_drops_unrecognised_columns():
    r = resolve_columns(pd.DataFrame({"Item": ["x"], "Random Notes": ["y"], "Calories": [1]}))
    assert "Random Notes" not in r.mapping
    assert any(m.raw == "Random Notes" and m.confidence == "NONE" for m in r.matches)


def test_resolver_finds_item_column_without_a_header():
    r = resolve_columns(pd.DataFrame({"Unnamed: 0": ["Latte", "Mocha"], "Calories": [1, 2]}))
    assert r.item_name_column == "Unnamed: 0"


def test_user_overrides_beat_the_resolver():
    r = resolve_columns(pd.DataFrame({"Item": ["x"], "Calories": [1], "Notes": ["y"]}))
    merged = apply_overrides(r, {"Notes": "sugars_g", "Calories": None})
    assert merged["Notes"] == "sugars_g"
    assert "Calories" not in merged


def test_both_supplied_files_resolve_with_no_confirmation_needed(datasets):
    for ds in datasets.values():
        assert not ds.needs_user_mapping
        assert ds.resolution.item_name_column == "Unnamed: 0"
