# SPEC-02 — Technical Specification
### Starbucks Nutrition Intelligence | AMARIS Technical Test
**Version 1.0 · Stephen Baraik**

---

## 1. Stack

| Layer | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 / 3.12 | Widest wheel availability; the reviewer runs this locally |
| Data | pandas, numpy | Named in the brief; 187 rows |
| LLM | `groq` official SDK | Named in the brief; raw SDK, no framework |
| Validation | pydantic v2 | Validates LLM query plans with usable errors; pairs with Groq JSON mode |
| UI | Streamlit | `st.file_uploader` satisfies Bonus 2 in one line |
| Charts | plotly | Renders `®`/`™` correctly without font fallback work |
| Config | python-dotenv | Shared by CLI and app |
| Test | pytest | 38 tests currently passing |
| Lint | ruff | Replaces black, flake8 and isort |

## 2. Module map

```
src/
├── config.py                  schema, aliases, units, tokens, model IDs
├── ingestion/
│   ├── loader.py              encoding fallback              [BUILT]
│   ├── resolver.py            header resolution              [BUILT]
│   ├── cleaner.py             coercion, dedup, audit         [BUILT]
│   └── pipeline.py            orchestration + capabilities   [BUILT]
├── analytics/
│   ├── stats.py               descriptives, ratios           [TODO]
│   ├── compare.py             cross-source views             [TODO]
│   └── filters.py             predicate engine               [TODO]
├── viz/charts.py              figure builders                [TODO]
├── llm/
│   ├── facts.py               DataFrame -> JSON payload      [TODO]
│   ├── prompts.py             versioned templates            [TODO]
│   ├── client.py              Groq wrapper, retry, cache     [TODO]
│   ├── summarizer.py          facts -> prose                 [TODO]
│   ├── schemas.py             pydantic QueryPlan             [TODO]
│   ├── planner.py             question -> plan               [TODO]
│   └── executor.py            plan -> result                 [TODO]
└── utils/logging.py                                          [TODO]
```

**Import rules, enforced by review:**

- `analytics/*` and `viz/*` must not import from `llm/*`
- `viz/charts.py` must not import `streamlit`
- `ingestion/*` must not import from `analytics/*`, `viz/*` or `llm/*`
- `llm/executor.py` reuses `analytics/filters.py`; it does not reimplement filtering

## 3. Built modules

### 3.1 `ingestion/loader.py`

```python
def read_csv_resilient(path: str | Path | IO) -> tuple[pd.DataFrame, str]
```

Tries `ENCODINGS` in order, returns the frame and the encoding that worked. Reads everything as `dtype=str` with `keep_default_na=False`, leaving coercion to the cleaner. A decodable-but-wrong encoding usually yields one column of mojibake, so a result with fewer than two columns counts as a failed attempt. Raises `UnreadableFileError` listing every attempt, or `FileNotFoundError`.

### 3.2 `ingestion/resolver.py`

```python
def normalise(header: str) -> str
def extract_unit(header: str) -> str | None
def resolve_columns(df: pd.DataFrame) -> ResolutionReport
def apply_overrides(rep: ResolutionReport, overrides: dict[str, str | None]) -> dict[str, str]
```

Full design in SPEC-03. Four confidence tiers: `EXACT`, `FUZZY`, `SUGGEST`, `NONE`. Only `EXACT` and `FUZZY` map automatically. `ColumnMatch` and `ResolutionReport` are the return types.

### 3.3 `ingestion/cleaner.py`

```python
@dataclass
class DataQualityReport:
    source, encoding, rows_read, rows_retained,
    exact_duplicates_removed, name_conflicts_resolved, rows_no_nutrition,
    sentinel_cells, unparseable_cells, columns_dropped, absent_nutrients,
    columns_resolved, columns_needing_confirmation, unit_conversions, notes

def apply_schema(df, mapping, rep) -> pd.DataFrame
def coerce_numeric(df, rep, conversions=None) -> pd.DataFrame
def drop_empty_rows(df, rep) -> pd.DataFrame
def resolve_duplicates(df, rep, policy=DUPLICATE_POLICY) -> pd.DataFrame
def finalise(df, source, rep) -> pd.DataFrame
def infer_caffeine(name: str) -> bool | None
```

Stages run in that order. `apply_schema` restrips mapping keys because the resolver keys on raw headers while the frame's headers get stripped, and the supplied food file carries a leading space on all five nutrient columns.

### 3.4 `ingestion/pipeline.py`

```python
def inspect_source(path_or_buffer, source) -> tuple[pd.DataFrame, str, ResolutionReport]
def load_source(path_or_buffer, source, overrides=None) -> Dataset
def load_all(drinks_path=None, food_path=None, overrides=None) -> dict[str, Dataset]
def available_nutrients(df) -> set[str]
def capabilities(datasets) -> dict
def combined_frame(datasets) -> pd.DataFrame
```

`inspect_source` exists so Streamlit can render the mapping panel before committing to a full ingest. `Dataset.needs_user_mapping` drives whether that panel appears.

`capabilities()` returns:

```python
{
  "per_source":         {"drinks": [...], "food": [...]},
  "comparable":         ["calories", "fiber_g", "protein_g", "total_carbs_g", "total_fat_g"],
  "single_source_only": {"drinks": ["sodium_mg"]},
  "unavailable":        ["caffeine_mg", "saturated_fat_g", "sugars_g"],
  "unavailable_labels": ["Caffeine (mg)", "Saturated fat (g)", "Sugars (g)"],
  "caffeine_is_inferred": True,
}
```

## 4. Modules to build

### 4.1 `analytics/stats.py`

```python
def describe(df: pd.DataFrame, nutrients: Iterable[str]) -> pd.DataFrame
def coverage(df: pd.DataFrame, nutrients: Iterable[str]) -> dict[str, str]
def safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series
def derived_ratios(df: pd.DataFrame) -> pd.DataFrame
def top_n(df: pd.DataFrame, nutrient: str, n: int = 10, ascending: bool = False) -> pd.DataFrame
```

`describe` returns mean, median, std, min, max and a non-null count per nutrient, restricted to the nutrients passed in (always from `capabilities()`, never a literal list).

`safe_ratio` is the guard for FR-14. It returns `NaN` where the denominator is zero or null, never `inf`. This is not optional: 31 of 74 drinks have protein = 0, and one has calories = 0.

`derived_ratios` produces `fat_to_protein`, `carbs_per_100kcal`, `protein_per_100kcal`, `fiber_per_100kcal`, all through `safe_ratio`.

### 4.2 `analytics/compare.py`

```python
def raw_comparison(datasets: dict[str, Dataset], comparable: list[str]) -> pd.DataFrame
def normalised_comparison(datasets: dict[str, Dataset], comparable: list[str]) -> pd.DataFrame
def comparison_caveat() -> str
```

`raw_comparison` gives mean and median per nutrient per source, plus a coverage count. `normalised_comparison` gives grams per 100 kcal. Both iterate `comparable` only.

Expected output on the supplied data, which doubles as a regression fixture:

| view | finding |
|---|---|
| raw | food 356.6 kcal vs drinks 138.7 kcal, a 2.57x gap |
| per 100 kcal | drinks 17.3 g carbs vs food 12.0 g; drinks 3.63 g protein vs food 3.08 g |

The two views point opposite ways. Both are shown.

### 4.3 `analytics/filters.py`

```python
ALLOWED_OPS = {">", ">=", "<", "<=", "==", "!="}

@dataclass
class Predicate:
    field: str
    op: str
    value: float

def validate_predicate(p: Predicate, available: set[str]) -> None   # raises FilterError
def apply_predicates(df, predicates, available) -> pd.DataFrame
def apply_text_filter(df, query: str) -> pd.DataFrame
def apply_caffeine_filter(df, caffeinated: bool | None) -> pd.DataFrame
```

Validation happens against the `available` set from `capabilities()`, before anything touches the frame. The LLM executor calls these exact functions, which is why they are validated here rather than in the UI.

### 4.4 `viz/charts.py`

```python
def top_n_bar(df, nutrient, n=10) -> go.Figure
def distribution_by_source(combined, nutrient="calories") -> go.Figure
def macro_composition(normalised) -> go.Figure
def scatter(combined, x, y) -> go.Figure
```

Returns plotly figures. No Streamlit import. Axis labels come from `NUTRIENT_LABELS` so units are always shown.

### 4.5 `llm/facts.py`

```python
def build_facts(datasets, capabilities, top_n=5) -> dict
def facts_digest(facts: dict) -> str      # sha256 of canonical JSON, for cache keys
```

Target payload under 1000 tokens regardless of row count. Shape:

```json
{
  "sources": {
    "drinks": {
      "n_items": 74,
      "rows_excluded_no_data": 85,
      "metrics": {
        "calories": {"mean": 138.7, "median": 130, "max": 430, "coverage": "74/74"}
      },
      "top_by_calories": [{"item": "...", "calories": 430}]
    }
  },
  "comparison": {"raw": {...}, "per_100_kcal": {...}},
  "unavailable_nutrients": ["Sugars (g)", "Caffeine (mg)", "Saturated fat (g)"],
  "inferred_fields": ["caffeine (from item name, not measured)"],
  "caveats": ["Drinks are per prepared serving; food is per item."]
}
```

`unavailable_nutrients` and `inferred_fields` are mandatory keys. They are what makes FR-28 achievable.

### 4.6 `llm/client.py`

```python
class LLMClient:
    def __init__(self, model: str = LLM_MODEL_SUMMARY)
    @property
    def enabled(self) -> bool
    def complete(self, system: str, user: str, json_mode: bool = False) -> str
```

Behaviour contract:

- No `GROQ_API_KEY` → `enabled` is False, `complete` returns a notice string. No exception (FR-30)
- Cache key is `sha256(model | system | user | json_mode)`, persisted to `.cache/` so Streamlit reruns are free (FR-32, FR-43)
- Any `Exception` from the SDK → returns a formatted notice naming the error type. No traceback reaches the user (FR-31)
- `temperature=0.2`, `max_tokens=800`

### 4.7 `llm/schemas.py`

```python
class Filter(BaseModel):
    field: str
    op: Literal[">", ">=", "<", "<=", "==", "!="]
    value: float

class QueryPlan(BaseModel):
    dataset: Literal["drinks", "food", "both"]
    metric: str
    op: Literal["mean", "median", "max", "min", "sum", "count", "top_n"]
    filters: list[Filter] = []
    group_by: str | None = None
    limit: int | None = Field(None, ge=1, le=50)

class PlanError(BaseModel):
    error: str
```

Field names are validated against `capabilities()` at execution time, not in the model, because the available set depends on what was uploaded.

### 4.8 `llm/planner.py` and `llm/executor.py`

```python
def propose_plan(question: str, available: set[str], previous_error: str | None = None) -> QueryPlan | PlanError
def execute(plan: QueryPlan, datasets, available) -> dict
def answer(question: str, datasets, capabilities, client) -> dict
```

`answer` is the whole loop:

```
question
  -> propose_plan            (LLM, JSON mode)
  -> pydantic validation     (shape)
  -> whitelist validation    (field names against `available`)
  -> execute in pandas       (reuses analytics/filters.py)
  -> build result facts
  -> narrate                 (LLM, second call)
```

One retry on validation failure, carrying the error text back into the prompt. On second failure, return `{"status": "unsupported", "reason": ...}`.

Two failure cases must be demonstrable, because they are the strongest moment in the demo:

| Question | Expected |
|---|---|
| "Which drink has the most sugar?" | Declines, citing sugar as absent from the source data |
| "Which item is healthiest?" | Declines, explaining the question is not computable from the available fields |

Forbidden anywhere in this path: `eval`, `exec`, `getattr` on model-supplied names, `pd.eval`, and `df.query` with an unvalidated string.

### 4.9 `app.py`

```
Sidebar          uploaders (drinks, food), source toggle, nutrient filters,
                 caffeine filter, text search
Tab Overview     data quality report, capability summary, headline comparison
Tab Explore      filtered table, derived ratios
Tab Charts       FR-20 to FR-23
Tab Ask          question box, executed plan, answer
```

Caching: `@st.cache_data` on `load_all` keyed by file bytes; `@st.cache_resource` on `LLMClient`; filter state in `st.session_state`. The disk cache in `client.py` covers `st.cache_data` misses.

Mapping panel: when `Dataset.needs_user_mapping` is True, render a selectbox per unresolved column with canonical options plus "ignore", then re-run `load_source` with the overrides.

## 5. Error handling

| Condition | Behaviour | Requirement |
|---|---|---|
| File unreadable in every encoding | `UnreadableFileError` listing attempts | FR-01 |
| No item name column identified | `ValueError` naming the source; UI prompts for selection | FR-03 |
| Column below confidence threshold | Surfaces in the mapping panel; never auto-mapped | FR-02 |
| Unit mismatch with known conversion | Convert and record in the report | FR-04 |
| Unit mismatch without known conversion | Leave as-is, warn in the report | FR-04 |
| Nutrient requested but unavailable | Return "unavailable" | FR-11 |
| Divide by zero in a ratio | Return `NaN` | FR-14 |
| `GROQ_API_KEY` unset | Notice string; app fully usable otherwise | FR-30 |
| Groq API error | Formatted notice naming the error type | FR-31 |
| Invalid query plan after one retry | `{"status": "unsupported"}` with the reason | FR-38 |

## 6. Test strategy

Two kinds, deliberately.

**Unit tests** use small synthetic frames so a failure points at one function.

**Contract tests** pin properties of the supplied files: 177 rows in and 74 out for drinks, food resolves as UTF-16, sugar and caffeine absent, sodium drinks-only. If the data changes shape, the suite fails loudly rather than the app quietly producing different numbers.

Current state: 38 passing across `tests/test_ingestion.py`.

Still to write: `test_stats.py` (ratio null-safety, coverage counts), `test_filters.py` (predicate composition, rejection of unknown fields), `test_executor.py` (plan validation, whitelist enforcement, the two decline cases), `test_facts.py` (mandatory keys present, payload size bound).

## 7. Configuration

| Key | Location | Notes |
|---|---|---|
| `GROQ_API_KEY` | `.env` | Never committed; `.env.example` is |
| `LLM_MODEL_SUMMARY` | `config.py` | Groq deprecates model IDs on a rolling basis. Confirm via `GET /openai/v1/models` and note the check date in the README |
| `LLM_MODEL_PLANNER` | `config.py` | Smaller model is adequate for plan generation |
| `DUPLICATE_POLICY` | `config.py` | `completeness` (default), `first`, `keep_all` |
| `FUZZY_ACCEPT_RATIO` | `config.py` | 0.86 auto-accept threshold |
| `FUZZY_SUGGEST_RATIO` | `config.py` | 0.62 floor for showing a suggestion |
