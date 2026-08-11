"""
Central configuration: canonical schema, source column mappings, constants.

The canonical schema is deliberately wider than what these two files supply.
Columns the source data does not carry (sugars, caffeine, saturated fat) stay
declared but unpopulated, so adding a richer CSV later is a mapping change
rather than a refactor. Downstream code never assumes a column exists; it asks
the capability registry (see ingestion.capabilities).
"""

from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_RAW = PROJECT_ROOT / "data" / "raw"

DRINKS_FILE = DATA_RAW / "starbucks-menu-nutrition-drinks.csv"
FOOD_FILE = DATA_RAW / "starbucks-menu-nutrition-food.csv"

# --------------------------------------------------------------------------
# Canonical schema
# --------------------------------------------------------------------------

IDENTITY_COLS = ["item_id", "item_name", "source"]

NUTRIENT_COLS = [
    "calories",         # kcal
    "total_fat_g",
    "saturated_fat_g",  # not in these files
    "total_carbs_g",
    "fiber_g",
    "sugars_g",         # not in these files
    "protein_g",
    "sodium_mg",        # drinks only
    "caffeine_mg",      # not in these files
]

CANONICAL = IDENTITY_COLS + NUTRIENT_COLS

# Human-readable labels with units, for charts and LLM prompts.
NUTRIENT_LABELS = {
    "calories": "Calories (kcal)",
    "total_fat_g": "Total fat (g)",
    "saturated_fat_g": "Saturated fat (g)",
    "total_carbs_g": "Carbohydrates (g)",
    "fiber_g": "Fibre (g)",
    "sugars_g": "Sugars (g)",
    "protein_g": "Protein (g)",
    "sodium_mg": "Sodium (mg)",
    "caffeine_mg": "Caffeine (mg)",
}

# --------------------------------------------------------------------------
# Source column mappings
#
# Verified against the supplied files on 2026-08-11. Keys are the raw headers
# AFTER whitespace stripping. Note the two files disagree on the protein header
# ("Protein" vs "Protein (g)"), which is exactly why this mapping layer exists.
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Column resolution
#
# Because the Streamlit UI lets users upload their own CSVs, the ingestion
# layer cannot key on exact raw headers. It resolves each incoming header
# against these aliases instead. Aliases are matched AFTER normalisation
# (lowercase, symbols and punctuation to spaces, unit parentheticals
# stripped), so "Protein", "Protein (g)", " protein_g " and "PROTEIN" all
# land on the same canonical column.
#
# The supplied files are the reason this exists: they spell the same
# quantity two different ways ("Protein" vs "Protein (g)").
# --------------------------------------------------------------------------

NUTRIENT_ALIASES: dict[str, list[str]] = {
    "calories": ["calories", "calorie", "cal", "kcal", "energy", "energy kcal"],
    "total_fat_g": ["fat", "total fat", "fat total", "lipids", "total lipid"],
    "saturated_fat_g": ["saturated fat", "sat fat", "saturates", "saturated"],
    "trans_fat_g": ["trans fat", "trans fatty acids", "trans"],
    "cholesterol_mg": ["cholesterol", "chol"],
    "total_carbs_g": [
        "carb", "carbs", "carbohydrate", "carbohydrates",
        "total carbohydrate", "total carbohydrates", "total carbs",
    ],
    "fiber_g": ["fiber", "fibre", "dietary fiber", "dietary fibre"],
    "sugars_g": ["sugar", "sugars", "total sugars", "of which sugars"],
    "protein_g": ["protein", "proteins", "total protein"],
    "sodium_mg": ["sodium", "salt", "na"],
    "caffeine_mg": ["caffeine"],
}

ITEM_NAME_ALIASES = [
    "item", "item name", "name", "product", "product name", "menu item",
    "beverage", "food", "description", "unnamed 0", "",
]

# Expected unit per canonical column. Used to detect a header that declares a
# different unit (e.g. "Sodium (g)") so the value can be converted rather than
# silently misread by a factor of 1000.
EXPECTED_UNITS = {
    "calories": "kcal",
    "total_fat_g": "g",
    "saturated_fat_g": "g",
    "trans_fat_g": "g",
    "cholesterol_mg": "mg",
    "total_carbs_g": "g",
    "fiber_g": "g",
    "sugars_g": "g",
    "protein_g": "g",
    "sodium_mg": "mg",
    "caffeine_mg": "mg",
}

UNIT_CONVERSIONS = {
    ("g", "mg"): 1000.0,
    ("mg", "g"): 0.001,
    ("kg", "g"): 1000.0,
    ("oz", "g"): 28.3495,
}

# Below this ratio, a fuzzy match is treated as a suggestion needing user
# confirmation rather than an automatic mapping.
FUZZY_ACCEPT_RATIO = 0.86
FUZZY_SUGGEST_RATIO = 0.62


# The food CSV is UTF-16 LE with a BOM. A plain read_csv() raises
# UnicodeDecodeError on byte 0. Order matters: utf-8-sig first so a normal
# BOM-prefixed UTF-8 file is handled, then the UTF-16 variants.
ENCODINGS = ["utf-8-sig", "utf-8", "utf-16", "utf-16-le", "latin-1", "cp1252"]

# Values that mean "no data" in these files. The drinks CSV uses a bare hyphen,
# which is why every one of its columns reads as object dtype and why
# df.isna().sum() reports zero nulls on a file that is 48% empty.
NULL_SENTINELS = ["-", "", "N/A", "n/a", "NA", "varies", "Varies", "--"]

# --------------------------------------------------------------------------
# Duplicate resolution policy
# --------------------------------------------------------------------------
# "completeness"  keep the row with the most non-null nutrients; tiebreak on
#                 highest calories (conservative for a nutrition tool)
# "first"         keep first occurrence
# "keep_all"      retain every row, disambiguate item_id with a suffix
DUPLICATE_POLICY = "completeness"

# --------------------------------------------------------------------------
# Caffeine inference
# --------------------------------------------------------------------------
# Neither file carries a caffeine column, but the brief asks for a
# "drinks with caffeine" filter. These tokens drive an INFERRED flag which is
# always surfaced to the user as inferred, never as measured.
CAFFEINE_TOKENS = [
    "coffee", "espresso", "latte", "mocha", "macchiato", "americano",
    "cappuccino", "cold brew", "doubleshot", "frappuccino", "tea",
    "matcha", "chai", "refresher", "clover", "flat white", "cortado",
    "roast", "tazo", "pike place", "blonde", "caffè", "caffe",
]

# Checked BEFORE the caffeinated list, so a decaf latte resolves correctly.
# "crème" covers the Starbucks steamed-milk drinks; "passion" covers the
# herbal Tazo bottles that would otherwise match on "tazo".
CAFFEINE_FREE_TOKENS = [
    "decaf", "herbal", "hot chocolate", "steamed milk", "smoothie",
    "lemonade", "limeade", "juice", "water", "hibiscus", "tranquility",
    "mint majesty", "passion", "crème", "creme", "chocolate milk",
]

# --------------------------------------------------------------------------
# LLM
# --------------------------------------------------------------------------
# Groq deprecates model IDs on a rolling basis. Confirm against
# GET https://api.groq.com/openai/v1/models before submitting.
LLM_MODEL_SUMMARY = "llama-3.3-70b-versatile"
LLM_MODEL_PLANNER = "llama-3.1-8b-instant"
LLM_TEMPERATURE = 0.2
LLM_MAX_TOKENS = 800
CACHE_DIR = PROJECT_ROOT / ".cache"
