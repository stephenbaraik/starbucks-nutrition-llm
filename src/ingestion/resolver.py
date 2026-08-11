"""
Header resolution for arbitrary uploaded CSVs.

The Streamlit UI accepts user uploads, so ingestion cannot key on exact raw
headers. This module resolves incoming headers to canonical column names
through three tiers, in descending order of confidence:

  EXACT   normalised header matches a known alias outright
  FUZZY   close enough to a known alias to accept automatically
  SUGGEST plausible but below the auto-accept threshold; needs confirmation
  NONE    no candidate; the column is dropped unless the user maps it

Tiers matter because the honest failure mode is a confident wrong mapping.
Anything below FUZZY surfaces in the UI as a dropdown rather than being
guessed at, and every automatic decision lands in the resolution report.

Deliberately not attempted: inferring semantics from values alone. Two
integer columns in the range 0-500 could be sodium and calories in either
order, and no amount of statistics settles it. When the header is unusable,
ask the user.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import re

import pandas as pd

from src.config import (
    NUTRIENT_ALIASES, ITEM_NAME_ALIASES, EXPECTED_UNITS, UNIT_CONVERSIONS,
    FUZZY_ACCEPT_RATIO, FUZZY_SUGGEST_RATIO,
)

UNIT_PATTERN = re.compile(r"\(\s*(kcal|kj|mg|g|kg|oz|ml|l|%\s*dv|%)\s*\)", re.I)

# Reverse index: normalised alias -> canonical column
_ALIAS_INDEX: dict[str, str] = {}
for _canon, _aliases in NUTRIENT_ALIASES.items():
    for _a in _aliases:
        _ALIAS_INDEX[_a] = _canon


# What resolve_columns() decided about a single raw header, and why.
@dataclass
class ColumnMatch:
    raw: str
    canonical: str | None
    confidence: str          # EXACT | FUZZY | SUGGEST | NONE
    score: float = 1.0
    declared_unit: str | None = None
    expected_unit: str | None = None
    conversion_factor: float | None = None
    note: str = ""

    @property
    def needs_confirmation(self) -> bool:
        return self.confidence in ("SUGGEST", "NONE")


# All the ColumnMatch results for one file, plus the item-name column
# (which is chosen separately, see _pick_item_column) and any warnings
# worth surfacing to the user before they trust the mapping.
@dataclass
class ResolutionReport:
    matches: list[ColumnMatch] = field(default_factory=list)
    item_name_column: str | None = None
    item_name_method: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def mapping(self) -> dict[str, str]:
        """Raw header -> canonical, for auto-accepted matches only."""
        m = {c.raw: c.canonical for c in self.matches
             if c.canonical and c.confidence in ("EXACT", "FUZZY")}
        if self.item_name_column is not None:
            m[self.item_name_column] = "item_name"
        return m

    @property
    def unresolved(self) -> list[ColumnMatch]:
        return [c for c in self.matches if c.needs_confirmation]

    @property
    def conversions(self) -> dict[str, float]:
        return {c.raw: c.conversion_factor for c in self.matches
                if c.conversion_factor and c.canonical}

    def summary_line(self) -> str:
        auto = len(self.mapping)
        return (
            f"Resolved {auto} column(s) automatically, "
            f"{len(self.unresolved)} need confirmation"
        )


# --------------------------------------------------------------------------

def normalise(header: str) -> str:
    """
    Reduce a header to a comparable token string.

    "  Protein (g) " -> "protein"
    "Carb. (g)"      -> "carb"
    "Unnamed: 0"     -> "unnamed 0"
    """
    s = str(header).strip().lower()
    s = re.sub(r"[®™©]", "", s)
    s = UNIT_PATTERN.sub(" ", s)
    s = re.sub(r"\bunnamed:\s*\d+\b", "unnamed 0", s)
    s = re.sub(r"[^a-z0-9%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def extract_unit(header: str) -> str | None:
    m = UNIT_PATTERN.search(str(header))
    if not m:
        return None
    return re.sub(r"\s+", "", m.group(1).lower())


def _best_alias(token: str) -> tuple[str | None, float]:
    """Highest-scoring canonical column for a normalised token."""
    if token in _ALIAS_INDEX:
        return _ALIAS_INDEX[token], 1.0

    best, best_score = None, 0.0
    for alias, canon in _ALIAS_INDEX.items():
        # Substring containment handles "total fat g" vs "fat" and
        # "dietary fibre" vs "fibre" without needing an exhaustive alias list.
        if alias in token.split() or token in alias.split():
            score = 0.95
        elif alias in token or token in alias:
            score = 0.90
        else:
            score = SequenceMatcher(None, token, alias).ratio()
        if score > best_score:
            best, best_score = canon, score
    return best, best_score


def _resolve_unit(canonical: str, declared: str | None) -> tuple[float | None, str]:
    """Conversion factor and a note, if the declared unit differs from expected."""
    expected = EXPECTED_UNITS.get(canonical)
    if not declared or not expected or declared == expected:
        return None, ""
    if declared in ("kcal", "kj") and expected == "kcal":
        return None, ""
    factor = UNIT_CONVERSIONS.get((declared, expected))
    if factor:
        return factor, f"declared {declared}, converting to {expected} (x{factor:g})"
    return None, f"declared unit {declared} does not match expected {expected}; left as-is"


def _pick_item_column(df: pd.DataFrame, claimed: set[str]) -> tuple[str | None, str]:
    """
    Choose the item name column from whatever is left.

    Preference order: an explicit alias match, then the unclaimed column with
    the most non-numeric, most-unique values. A menu file always has exactly
    one such column, and it is usually first.
    """
    candidates = [c for c in df.columns if c not in claimed]
    if not candidates:
        return None, "none available"

    for c in candidates:
        if normalise(c) in ITEM_NAME_ALIASES:
            return c, "alias match"

    # No alias matched, so fall back to a heuristic: an item-name column
    # tends to be mostly text (not numbers) and mostly unique (menu items
    # rarely repeat). Weight text-ness higher since a numeric ID column can
    # also be fairly unique.
    best, best_score = None, -1.0
    for c in candidates:
        col = df[c].astype(str)
        non_numeric = 1.0 - pd.to_numeric(col, errors="coerce").notna().mean()
        uniqueness = col.nunique() / max(len(col), 1)
        score = non_numeric * 0.7 + uniqueness * 0.3
        if score > best_score:
            best, best_score = c, score

    if best_score < 0.5:
        return None, f"no confident candidate (best score {best_score:.2f})"
    return best, f"heuristic, score {best_score:.2f}"


def resolve_columns(df: pd.DataFrame) -> ResolutionReport:
    """Resolve every header in an uploaded frame. Mutates nothing."""
    rep = ResolutionReport()
    claimed: set[str] = set()
    taken_canonicals: set[str] = set()

    # Walk every header once, scoring it against the alias table and
    # sorting the result into one of the four confidence tiers described
    # at the top of this file.
    for raw in df.columns:
        token = normalise(raw)
        unit = extract_unit(raw)

        if token in ITEM_NAME_ALIASES:
            continue  # handled by _pick_item_column

        canon, score = _best_alias(token)

        if score >= 1.0:
            conf = "EXACT"
        elif score >= FUZZY_ACCEPT_RATIO:
            conf = "FUZZY"
        elif score >= FUZZY_SUGGEST_RATIO:
            conf = "SUGGEST"
        else:
            canon, conf = None, "NONE"

        # Two headers resolving to the same canonical column is a real
        # possibility on user uploads. First wins, second needs confirmation.
        if canon and canon in taken_canonicals and conf in ("EXACT", "FUZZY"):
            conf = "SUGGEST"
            rep.warnings.append(
                f"'{raw}' also resolves to {canon}, which is already mapped. "
                f"Confirm which column to use."
            )

        factor, unit_note = (None, "")
        if canon and conf in ("EXACT", "FUZZY"):
            factor, unit_note = _resolve_unit(canon, unit)
            if unit_note:
                rep.warnings.append(f"'{raw}': {unit_note}")
            claimed.add(raw)
            taken_canonicals.add(canon)

        rep.matches.append(ColumnMatch(
            raw=str(raw), canonical=canon, confidence=conf, score=round(score, 3),
            declared_unit=unit, expected_unit=EXPECTED_UNITS.get(canon or ""),
            conversion_factor=factor, note=unit_note,
        ))

    item_col, method = _pick_item_column(df, claimed)
    rep.item_name_column, rep.item_name_method = item_col, method
    if item_col is None:
        rep.warnings.append(
            "No item name column identified. Select one before continuing."
        )
    elif not method.startswith("alias"):
        rep.warnings.append(
            f"Item name column '{item_col}' chosen by {method}. Confirm if wrong."
        )

    for m in rep.matches:
        if m.confidence == "SUGGEST":
            rep.warnings.append(
                f"'{m.raw}' looks like {m.canonical} (score {m.score:.2f}) "
                f"but is below the auto-accept threshold."
            )

    return rep


def apply_overrides(rep: ResolutionReport, overrides: dict[str, str | None]) -> dict[str, str]:
    """
    Merge user choices from the Streamlit mapping UI into the final mapping.

    A value of None means "ignore this column". Overrides always win, so a
    user correcting a confident-but-wrong guess is honoured.
    """
    mapping = dict(rep.mapping)
    for raw, canon in overrides.items():
        mapping.pop(raw, None)
        if canon:
            mapping[raw] = canon
    return mapping
