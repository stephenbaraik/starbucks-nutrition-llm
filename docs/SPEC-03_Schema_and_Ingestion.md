# SPEC-03 — Schema and Ingestion Specification
### Starbucks Nutrition Intelligence | AMARIS Technical Test
**Version 1.0 · Stephen Baraik**

---

## 1. The problem

The brief asks for a web interface where users upload the CSVs. That single line changes the ingestion contract. If headers are known in advance, a lookup table is fine. If a user can upload anything, the table becomes a defect: an upload with `Total Fat (g)` instead of `Fat (g)` silently loses a column, and the app reports a mean over data that is not there.

The first version of this project shipped exactly that mistake:

```python
DRINKS_MAP = {"Fat (g)": "total_fat_g", "Protein": "protein_g", ...}
```

It resolved the two supplied files perfectly and nothing else.

## 2. What not to build

The tempting overcorrection is full auto-detection: infer the schema from values, no headers needed. It does not work, and the reasons are worth stating because a reviewer may ask.

Given two integer columns both ranging 0 to 500, no statistic distinguishes sodium in milligrams from calories. Given two text columns, none distinguishes item name from category. Ranges overlap, distributions overlap, and correlation tells you they are related without telling you which is which. Any system claiming otherwise is guessing with extra steps, and a confident wrong mapping is worse than an admitted unknown, because the user never sees it happen.

The design principle:

> Resolve confidently where the header supports it. Ask the user where it does not. Never guess silently.

## 3. Canonical schema

The internal contract every downstream module codes against.

| Column | Type | Unit | In drinks | In food |
|---|---|---|---|---|
| `item_id` | str | | derived | derived |
| `item_name` | str | | yes | yes |
| `source` | str | | derived | derived |
| `calories` | float | kcal | yes | yes |
| `total_fat_g` | float | g | yes | yes |
| `saturated_fat_g` | float | g | no | no |
| `total_carbs_g` | float | g | yes | yes |
| `fiber_g` | float | g | yes | yes |
| `sugars_g` | float | g | no | no |
| `protein_g` | float | g | yes | yes |
| `sodium_mg` | float | mg | yes | no |
| `caffeine_mg` | float | mg | no | no |
| `caffeine_inferred` | bool | | derived | n/a |

The schema is deliberately wider than the supplied data. Columns nothing populates stay declared, so a richer upload lights up features with no code change (FR-12). Downstream code never assumes presence; it asks `capabilities()`.

## 4. Resolution algorithm

### 4.1 Normalisation

Every header reduces to a comparable token string before matching.

```
lowercase
strip whitespace
remove ® ™ ©
strip unit parentheticals:  (g) (mg) (kcal) (kJ) (%DV) ...   [captured separately]
"Unnamed: N" -> "unnamed 0"
non-alphanumeric -> space
collapse whitespace
```

| Raw | Normalised |
|---|---|
| `  Protein (g) ` | `protein` |
| `Protein` | `protein` |
| `Carb. (g)` | `carb` |
| `Total Carbohydrates (g)` | `total carbohydrates` |
| `Starbucks® Calories` | `starbucks calories` |
| `Unnamed: 0` | `unnamed 0` |

The first two rows are the point. The supplied files spell the same quantity two different ways, and normalisation collapses them before any matching happens.

### 4.2 Alias table

`config.NUTRIENT_ALIASES` maps each canonical column to accepted normalised forms. Current coverage:

| Canonical | Aliases |
|---|---|
| `calories` | calories, calorie, cal, kcal, energy, energy kcal |
| `total_fat_g` | fat, total fat, fat total, lipids, total lipid |
| `saturated_fat_g` | saturated fat, sat fat, saturates, saturated |
| `trans_fat_g` | trans fat, trans fatty acids, trans |
| `cholesterol_mg` | cholesterol, chol |
| `total_carbs_g` | carb, carbs, carbohydrate, carbohydrates, total carbohydrate(s), total carbs |
| `fiber_g` | fiber, fibre, dietary fiber, dietary fibre |
| `sugars_g` | sugar, sugars, total sugars, of which sugars |
| `protein_g` | protein, proteins, total protein |
| `sodium_mg` | sodium, salt, na |
| `caffeine_mg` | caffeine |

Both spellings of fibre are present deliberately. So is the UK/US split on `of which sugars`, which appears on European nutrition panels.

### 4.3 Scoring

For each header, score against every alias and keep the best:

| Condition | Score |
|---|---|
| Normalised header equals an alias | 1.00 |
| Alias is a whole token within the header, or vice versa | 0.95 |
| Alias is a substring of the header, or vice versa | 0.90 |
| Otherwise | `SequenceMatcher` ratio |

Containment rules matter more than the fuzzy fallback. They handle `total fat g` against `fat`, and `dietary fibre` against `fibre`, without needing an exhaustive alias list.

### 4.4 Confidence tiers

| Tier | Score | Behaviour |
|---|---|---|
| `EXACT` | 1.00 | Map automatically |
| `FUZZY` | ≥ 0.86 | Map automatically, record in the report |
| `SUGGEST` | ≥ 0.62 | Do not map. Show as a pre-selected suggestion in the UI |
| `NONE` | < 0.62 | Do not map. Show as unmapped, user may assign |

Thresholds live in `config.py` as `FUZZY_ACCEPT_RATIO` and `FUZZY_SUGGEST_RATIO`. They are tunable and should be defended as tuned rather than arbitrary: 0.86 keeps real variants in while keeping unrelated headers out.

### 4.5 Item name column

Headers for this column are frequently missing or meaningless, so resolution runs in two passes.

**Pass 1, alias match.** Normalised header in `ITEM_NAME_ALIASES`: `item`, `item name`, `name`, `product`, `menu item`, `beverage`, `food`, `description`, `unnamed 0`, and empty string. Both supplied files hit this on `Unnamed: 0`.

**Pass 2, heuristic.** Among columns not claimed as nutrients, score each:

```
score = 0.7 * (1 - fraction parseable as numeric) + 0.3 * (unique values / row count)
```

Highest score wins. Below 0.5, return no candidate and require the user to select one. A menu file always has exactly one such column, and it is usually first, but "usually" is not a contract, so the fallback is an explicit ask.

### 4.6 Unit handling

Units are extracted from the header before normalisation strips them, then compared to `EXPECTED_UNITS`.

| Case | Action |
|---|---|
| Declared matches expected | Proceed |
| No unit declared | Assume expected, note the assumption |
| Declared differs, conversion known | Convert, record the factor in the report |
| Declared differs, no conversion | Leave as-is, warn |

Known conversions: g↔mg, kg→g, oz→g.

This is not hypothetical. `Sodium (g)` against a canonical `sodium_mg` is a factor of 1000. Without detection, every sodium figure in the app would be wrong by three orders of magnitude, and it would look plausible.

### 4.7 Collisions

Two headers resolving to the same canonical column is a real possibility on user uploads (`Fat` and `Total Fat` in one file). First match wins automatically; the second is demoted to `SUGGEST` with a warning, so the user chooses.

## 5. User override contract

```python
overrides = {
    "Random Notes": "sugars_g",   # assign an unmapped column
    "Calories": None,             # ignore a column the resolver mapped
}
mapping = apply_overrides(resolution_report, overrides)
```

User choices always win, including over `EXACT` matches. Someone correcting a confident-but-wrong guess must be able to.

The Streamlit panel renders when `Dataset.needs_user_mapping` is True, which happens if the item column is unidentified or any column sits at `SUGGEST` or `NONE`. One selectbox per unresolved column, options being the canonical list plus "ignore", pre-selected to the suggestion where one exists.

Both supplied files resolve with `needs_user_mapping` False, so the panel stays hidden on the default path. It exists for uploads that need it.

## 6. Pipeline order

```
read_csv_resilient        encoding fallback, everything as str
  ↓
resolve_columns           headers -> canonical, confidence tiers, units
  ↓
apply_overrides           user choices merged in
  ↓
apply_schema              strip headers, rename, drop unmapped
  ↓
coerce_numeric            sentinels -> NaN, to float, apply unit conversions
  ↓
drop_empty_rows           remove rows with no nutrition at all
  ↓
resolve_duplicates        exact dupes, then name conflicts by policy
  ↓
finalise                  item_id, source, inferred caffeine, sort
  ↓
capabilities              what this data can answer
```

Order is load-bearing in two places.

`apply_schema` before `coerce_numeric`, because conversions are keyed by canonical name and the rename must have happened. `drop_empty_rows` before `resolve_duplicates`, because the drinks file contains duplicate rows that are entirely empty, and removing the empties first drops the duplicate count from 22 to 17 without any special-casing.

One subtlety worth knowing about: the resolver keys its mapping on raw headers, while `apply_schema` strips header whitespace. The supplied food file carries a leading space on all five nutrient headers, so `apply_schema` restrips the mapping keys to keep the handoff intact. Without that line the food file loses every nutrient column and produces an empty frame, which is exactly the silent failure this whole design exists to prevent.

## 7. Missing data policy

| Situation | Policy | Reason |
|---|---|---|
| Sentinel value (`-`, empty, `N/A`, `varies`) | NaN, counted in the report | Real gaps stay visible |
| Some nutrients null, others present | Keep the row | Partial data is still usable |
| Every nutrient null | Exclude from analytics, count in the report | A mean over phantom rows is wrong |
| Nutrient absent from the file entirely | Report as unavailable | Never impute |
| Statistic over a column with nulls | Pairwise exclusion, report coverage | The user sees `74/113` alongside the mean |

Imputation is not used anywhere. A fabricated calorie count is worse than a visible gap, because the gap is honest and the fabrication is not.

## 8. Duplicate policy

Two distinct problems, handled separately.

**Exact duplicate rows** are a data entry artifact. Dropped silently, counted. 17 in the drinks file.

**Name conflicts** are rows sharing a name but disagreeing on values. These need a stated policy, selectable via `DUPLICATE_POLICY`:

| Policy | Behaviour |
|---|---|
| `completeness` (default) | Keep the row with the most non-null nutrients; tiebreak on higher calories |
| `first` | Keep first occurrence |
| `keep_all` | Retain every row, disambiguate `item_id` with a suffix |

The default errs toward overstating intake, which is the conservative direction for a nutrition tool.

The supplied data has exactly one such conflict: `Iced Coffee` appears at 0 kcal / 0 mg sodium and at 5 kcal / 5 mg sodium, almost certainly two sizes flattened into one name. Default policy keeps the 5 kcal row.

Be ready to defend this choice in the interview. It is a judgement call with no objectively correct answer, which makes it exactly the kind of thing worth probing.

## 9. Inferred fields

Neither file carries caffeine, but the brief asks for a caffeine filter. `infer_caffeine()` reads the item name against two token lists, with the caffeine-free list checked first so a decaf latte resolves correctly.

Caffeinated tokens: coffee, espresso, latte, mocha, macchiato, americano, cappuccino, cold brew, doubleshot, frappuccino, tea, matcha, chai, refresher, clover, flat white, cortado, roast, tazo, pike place, blonde, caffè.

Caffeine-free tokens: decaf, herbal, hot chocolate, steamed milk, smoothie, lemonade, limeade, juice, water, hibiscus, tranquility, mint majesty, passion, crème, creme, chocolate milk.

Current coverage: 58 caffeinated, 16 not, 0 unknown across the 74 retained drinks.

The ordering handles the awkward cases. `Tazo® Bottled Iced Passion` matches `passion` before it can match `tazo`, and comes out correctly as herbal. `Cinnamon Dolce Crème` matches `crème` rather than falling through.

**This is an inference, not a measurement.** It must be labelled as such in the column header, the UI tooltip, the LLM prompt, and the deck. A heuristic presented as data is dishonest; a heuristic clearly labelled is a reasonable response to a gap in the source. The difference is entirely in the labelling, and a reviewer will notice which one you did.

## 10. Verification

The resolver was tested against the supplied files and against a deliberately hostile header set.

**Supplied files:** both resolve at `EXACT` on every column, item column found by alias match, zero confirmations needed.

**Hostile set:**

| Header | Resolved | Note |
|---|---|---|
| `Menu Item` | `item_name` | alias |
| `Energy (kcal)` | `calories` | |
| `Total Fat (g)` | `total_fat_g` | |
| `Total Carbohydrates (g)` | `total_carbs_g` | |
| `Dietary Fibre (g)` | `fiber_g` | UK spelling |
| `PROTEIN` | `protein_g` | case |
| `Sodium (g)` | `sodium_mg` | **x1000 conversion flagged** |
| `Total Sugars (g)` | `sugars_g` | unlocks sugar features |
| `Caffeine (mg)` | `caffeine_mg` | unlocks measured caffeine |
| `Random Notes` | none | dropped, `NONE` |

The `Total Sugars` and `Caffeine` rows demonstrate FR-12: upload a richer file and the features the supplied data cannot support become available with no code change.

Covered by 38 passing tests in `tests/test_ingestion.py`.
