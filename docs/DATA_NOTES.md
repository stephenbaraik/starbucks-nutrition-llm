# Data audit — supplied CSVs

Findings from profiling the two provided files. Everything below is reproduced
by `pytest tests/test_ingestion.py` as contract tests, so a file swap breaks the
suite rather than silently changing the numbers.

## File-level

| | drinks | food |
|---|---|---|
| Encoding | UTF-8 | **UTF-16 LE with BOM** |
| Raw rows | 177 | 113 |
| Retained | **74 (42%)** | 113 (100%) |
| Item column header | `Unnamed: 0` | `Unnamed: 0` |
| Header whitespace | none | **leading space on all 5 nutrient headers** |
| Missing-value marker | **bare hyphen `-`** | none |
| Exact duplicate rows | 17 | 0 |
| Name conflicts | 1 (`Iced Coffee`) | 0 |
| Rows with no nutrition at all | **85** | 0 |

A default `pd.read_csv()` on the food file raises `UnicodeDecodeError` at byte 0.
A default read of the drinks file succeeds but types every nutrient column as
`object`, because `-` is a string. `df.isna().sum()` then returns zero for a
file that is 48% empty.

## Column coverage

| Canonical | drinks | food |
|---|---|---|
| `calories` | yes | yes |
| `total_fat_g` | yes | yes |
| `total_carbs_g` | yes | yes |
| `fiber_g` | yes | yes |
| `protein_g` | yes (header: `Protein`) | yes (header: `Protein (g)`) |
| `sodium_mg` | yes (header: `Sodium`) | **absent** |
| `sugars_g` | **absent** | **absent** |
| `caffeine_mg` | **absent** | **absent** |
| `saturated_fat_g` | **absent** | **absent** |

Comparable across both sources: calories, fat, carbs, fibre, protein.
Drinks-only: sodium.

The two files use different protein headers for the same quantity, which is the
concrete reason the mapping layer exists.

## Consequences for the brief

The brief names four example analyses. Two of them cannot be answered from
measured values in these files:

- *"which drink items have the highest sugar content"* — no sugar column
- *"show only drinks with caffeine"* — no caffeine column

Handling, in order of preference:

1. Detect the gap through the capability registry rather than hardcoding it.
2. Say so plainly in the UI and in every generated summary.
3. Where a defensible proxy exists, offer it and label it. Carbohydrate content
   stands in loosely for sugar in beverages, since most drink carbohydrate here
   comes from syrup and lactose. It is a proxy, never relabelled as sugar.
4. Caffeine is inferred from the item name (`config.CAFFEINE_TOKENS`), which
   currently resolves all 74 retained drinks to a True/False verdict. Always
   presented as inferred.

## Verified headline figures

Computed on the retained rows after cleaning.

| Metric | drinks (n=74) | food (n=113) |
|---|---|---|
| Mean calories | 138.7 | 356.6 |
| Median calories | 130 | 360 |
| Max calories | 430 (Starbucks® Signature Hot Chocolate) | 650 (Lentils & Vegetable Protein Bowl) |
| Mean fat (g) | 2.71 | 16.35 |
| Mean carbs (g) | 24.26 | 41.49 |
| Mean fibre (g) | 0.55 | 2.85 |
| Mean protein (g) | 4.80 | 11.47 |
| Mean sodium (mg) | 64.86 | not available |

Food items average 2.57x the calories of drinks. Normalised per 100 kcal the
ordering flips on carbohydrate: drinks carry 17.3 g per 100 kcal against 12.0 g
for food, and drinks edge food on protein density too (3.63 vs 3.08). The raw
comparison and the normalised one tell different stories, which is why the app
shows both.

## Edge cases that will bite the analytics layer

- 31 of 74 drinks have protein = 0, so a fat-to-protein ratio is undefined for
  42% of the drinks menu. Return null and report coverage; do not fill zeros.
- 1 drink has calories = 0, which breaks any per-100-kcal normalisation.
- Item names contain `®`, `™`, `è`, `é`, `ñ`. Fine in pandas and Streamlit;
  check them in matplotlib output and in the PowerPoint export.
- `Iced Coffee` appears twice with different values (0 kcal / 0 mg sodium and
  5 kcal / 5 mg sodium), most likely two sizes flattened to one name. Resolved
  by the `completeness` policy, which keeps the 5 kcal row.
