# SPEC-01 — Functional Specification
### Starbucks Nutrition Intelligence | AMARIS Technical Test
**Version 1.0 · Stephen Baraik**

---

## 1. Purpose and scope

A prototype nutrition analysis tool over the Starbucks drinks and food menus. Users upload two CSVs, explore descriptive statistics and charts, filter items, and read LLM-generated summaries of the findings.

**In scope:** CSV ingestion with column resolution, descriptive and comparative analytics, filtering, visualisation, LLM summarisation, natural language querying, a Streamlit interface.

**Out of scope:** persistence, authentication, multi-user state, nutrition advice or health claims, external nutrition APIs, and any inference of values not present in the source data.

## 2. Governing principle

> pandas computes every number. The LLM writes every sentence. Neither does the other's job.

Every requirement below inherits this. Any output containing a figure the analytics layer did not produce is a defect, regardless of how plausible it reads.

## 3. Data constraints

Verified against the supplied files (see `docs/DATA_NOTES.md`). These are facts about the input, not design choices.

| ID | Constraint |
|---|---|
| DC-1 | The food CSV is UTF-16 LE with BOM. A default `read_csv()` fails. |
| DC-2 | The drinks CSV encodes missing values as a bare hyphen, forcing object dtype and masking nulls from `isna()`. |
| DC-3 | 85 of 177 drink rows carry no nutrition data. 74 rows survive cleaning. |
| DC-4 | Neither file contains sugar, caffeine, or saturated fat. |
| DC-5 | Sodium exists in drinks only. |
| DC-6 | The two files spell protein differently (`Protein` vs `Protein (g)`). |
| DC-7 | Drinks are per prepared serving; food is per item. The two are not directly comparable. |

## 4. Functional requirements

Priority: **M** must have, **S** should have, **C** could have. IDs are referenced by SPEC-02 and by the test suite.

### 4.1 Ingestion

| ID | Requirement | Pri | Acceptance criteria | Brief ref |
|---|---|---|---|---|
| FR-01 | Load CSVs regardless of text encoding | M | Both supplied files load; food resolves as UTF-16; an unreadable file raises `UnreadableFileError` naming the attempts | Part 1.1 |
| FR-02 | Resolve arbitrary headers to a canonical schema | M | `Protein`, `Protein (g)`, `PROTEIN` and `Total Protein` all map to `protein_g`; unrecognised columns are dropped, not guessed | Part 1.1 |
| FR-03 | Identify the item name column without relying on its header | M | A column headed `Unnamed: 0` is correctly identified on both files | Part 1.1 |
| FR-04 | Detect declared units and convert where they differ | S | `Sodium (g)` produces a x1000 conversion to `sodium_mg`, recorded in the report | Part 1.1 |
| FR-05 | Treat sentinel values as null | M | `-`, empty string, `N/A` and `varies` become NaN; the count per column appears in the report | Part 1.1 |
| FR-06 | Exclude rows with no nutrition data from analytics | M | 85 drink rows excluded; the count is reported, not silently dropped | Part 1.1 |
| FR-07 | Resolve duplicates under a stated policy | M | Exact duplicates removed silently; name conflicts resolved by `DUPLICATE_POLICY` with each conflict logged | Part 1.1 |
| FR-08 | Produce a data quality report per source | M | Report carries rows in/out, retention %, encoding, sentinel counts, duplicates, conflicts, absent nutrients, and free-text notes | Part 1.1 |
| FR-09 | Let users correct any column mapping | S | A mapping panel appears when confidence is below threshold; user overrides always beat resolver output | Bonus 2 |

### 4.2 Capability detection

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-10 | Report which nutrients each source carries | M | `capabilities()` returns per-source sets, the comparable intersection, single-source columns, and the unavailable list |
| FR-11 | Never assume a nutrient column exists | M | No module raises `KeyError` when sugar or caffeine is requested; the absence is reported instead |
| FR-12 | Unlock features when richer data arrives | S | Uploading a CSV containing sugar makes sugar filters, charts and comparisons available with no code change |

### 4.3 Analytics

| ID | Requirement | Pri | Acceptance criteria | Brief ref |
|---|---|---|---|---|
| FR-13 | Descriptive statistics per source | M | Mean, median, min, max, std and non-null coverage for every available nutrient | Part 1.2 |
| FR-14 | Derived ratios | M | Fat-to-protein, carbs per 100 kcal, protein per 100 kcal, calorie density. Undefined cases return null, never `inf` | Part 1.2 |
| FR-15 | Cross-source comparison | M | Comparison table restricted to `capabilities()["comparable"]`; single-source nutrients labelled unavailable rather than omitted | Part 1.2 |
| FR-16 | Normalised comparison view | S | A per-100-kcal composition view accompanies the raw view, carrying the DC-7 caveat | Part 1.2 |
| FR-17 | Filter by numeric predicate | M | Composable predicates on any available nutrient; unknown columns rejected with a clear error | Part 1.3 |
| FR-18 | Filter by inferred caffeine | S | Drinks filterable by caffeine verdict, labelled "inferred from item name" everywhere it appears | Part 1.3 |
| FR-19 | Filter by text and by source | S | Case-insensitive substring match on item name; source toggle | Part 1.3 |

### 4.4 Visualisation

| ID | Requirement | Pri | Acceptance criteria | Brief ref |
|---|---|---|---|---|
| FR-20 | Top-N items by selected nutrient | M | Horizontal bar, N configurable, units in the axis label | Part 1.2 |
| FR-21 | Calorie distribution across sources | M | Box or overlaid histogram showing both sources | Part 1.2 |
| FR-22 | Macro composition per 100 kcal | S | Stacked bar carrying the FR-16 finding | Part 1.2 |
| FR-23 | Scatter of two nutrients, coloured by source | C | Axes selectable from available nutrients | Part 1.2 |
| FR-24 | Chart functions are UI-agnostic | M | `viz/charts.py` contains no Streamlit import and returns figure objects | Part 3.1 |

### 4.5 LLM summarisation

| ID | Requirement | Pri | Acceptance criteria | Brief ref |
|---|---|---|---|---|
| FR-25 | Summarise nutritional insights across both datasets | M | Summary references high-calorie items, cross-source comparison, and at least one derived ratio | Part 2.1 |
| FR-26 | Send facts, never raw rows | M | Prompt payload is a JSON facts object; payload size is independent of row count | Part 2.1 |
| FR-27 | Every figure traceable to the payload | M | Spot-check of ten generated figures against pandas shows zero discrepancies | Part 2.1 |
| FR-28 | State data gaps explicitly | M | Summary names sugar and caffeine as unavailable rather than working around the absence | Part 2.1 |
| FR-29 | Carry the comparability caveat | S | Any drinks-vs-food calorie claim is qualified per DC-7 | Part 2.1 |
| FR-30 | Degrade without an API key | M | With `GROQ_API_KEY` unset, statistics, filters and charts work; summaries show a notice | Part 3.2 |
| FR-31 | Survive API failure | M | A network or rate-limit error yields a user-facing message, not a traceback |  |
| FR-32 | Cache responses | S | An identical facts payload does not trigger a second API call within a session |  |

### 4.6 Natural language querying

| ID | Requirement | Pri | Acceptance criteria | Brief ref |
|---|---|---|---|---|
| FR-33 | Answer questions about the menu data | S | Five known-answer questions return correct figures | Bonus 1 |
| FR-34 | Execute plans, not generated code | M | No `eval`, `exec` or dynamic attribute access anywhere in the query path | Bonus 1 |
| FR-35 | Validate plans against a whitelist | M | A plan naming an unknown column or operator is rejected before touching the data | Bonus 1 |
| FR-36 | Decline unanswerable questions | M | "Which drink has the most sugar?" returns a clarification citing the missing column, not a number | Bonus 1 |
| FR-37 | Decline subjective questions | S | "Which item is healthiest?" explains that the question is not computable from the available fields | Bonus 1 |
| FR-38 | Retry once on invalid plans | C | A malformed plan triggers one re-prompt carrying the validation error before giving up | Bonus 1 |

### 4.7 Interface

| ID | Requirement | Pri | Acceptance criteria | Brief ref |
|---|---|---|---|---|
| FR-39 | Upload both CSVs through the browser | M | `st.file_uploader` accepts each file; bundled files load as the default | Bonus 2 |
| FR-40 | Show the data quality report | M | Report visible in an expander including retention rate and resolution decisions | Part 1.1 |
| FR-41 | Interactive filtering | S | Filter widgets restricted to available nutrients; results update without a full reload | Part 1.3 |
| FR-42 | Ask questions in the UI | S | Free-text input routed through the query path with the answer and the executed plan both shown | Bonus 1 |
| FR-43 | Cache across reruns | M | Widget interaction does not reload CSVs or re-issue an API call for a cached payload | Bonus 2 |

### 4.8 Quality and documentation

| ID | Requirement | Pri | Acceptance criteria | Brief ref |
|---|---|---|---|---|
| FR-44 | Separation of concerns | M | Analytics modules import no LLM client; viz imports no Streamlit; ingestion knows nothing of either | Part 3.1 |
| FR-45 | Install and run documentation | M | A clean clone plus README steps produces a running app | Part 3.2 |
| FR-46 | Test coverage of ingestion and query validation | M | `pytest -q` passes; contract tests pin the supplied files' properties | Part 3.1 |
| FR-47 | Documented design decisions | M | Deck covers approach, run instructions, decisions and trade-offs, with screenshots | Submission |

## 5. Non-functional requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-01 | Cold start to interactive | Under 3 seconds on the supplied files |
| NFR-02 | LLM payload size | Independent of row count; under 1000 tokens |
| NFR-03 | Cached summary retrieval | Under 100 ms |
| NFR-04 | No secrets in source control | `.env` git-ignored; `.env.example` committed |
| NFR-05 | No arbitrary code execution | No `eval`/`exec` on any model output |
| NFR-06 | Python compatibility | 3.11 and 3.12 |
| NFR-07 | Unicode integrity | `®`, `™`, `è`, `é`, `ñ` render correctly in UI, charts and exports |

## 6. Traceability against the brief

| Brief section | Requirements | Status |
|---|---|---|
| Part 1.1 CSV ingestion | FR-01 to FR-09 | Built |
| Part 1.2 Data processing | FR-13 to FR-16, FR-20 to FR-23 | Pending |
| Part 1.3 Dataset handling | FR-17 to FR-19 | Pending |
| Part 2.1 LLM summarisation | FR-25 to FR-32 | Pending |
| Part 3.1 Modular code | FR-44, FR-46 | Partial |
| Part 3.2 Documentation | FR-45, FR-47 | Partial |
| Bonus 1 LLM queries | FR-33 to FR-38 | Pending |
| Bonus 2 Web interface | FR-09, FR-39 to FR-43 | Pending |

## 7. Deliberate exclusions

Each of these is a decision, not an oversight, and each appears on the trade-offs slide.

| Excluded | Reason |
|---|---|
| Agent framework (LangGraph, LangChain) | Three single-shot LLM calls and one two-iteration retry. Framework orchestration would add dependency weight while undercutting the whitelisted executor |
| Database layer | 187 usable rows |
| Vector store / RAG | No document corpus; the facts payload fits in a prompt |
| Value-based column inference | Two integer columns in the same range cannot be told apart by statistics. Ask the user instead |
| Imputation of missing nutrients | A fabricated calorie count is worse than a visible gap |
| Sugar figures | Not present in either source. Carbohydrate offered as a labelled proxy only |
| Measured caffeine | Not present. Inferred from item name, labelled as inference wherever shown |
