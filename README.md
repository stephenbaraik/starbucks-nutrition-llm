# Starbucks Nutrition Intelligence

LLM-powered nutrition analysis over the Starbucks drinks and food menus.
Statistics are computed in pandas; the LLM only narrates values it is handed.

Anyone can run this — no coding needed beyond the setup commands below.

## Install

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

A Groq key is optional. Without one, statistics, filters and charts all
work; generated summaries and the "Ask" tab show a notice instead. To
enable them, get a free key at [console.groq.com](https://console.groq.com/keys):

```bash
cp .env.example .env         # Windows: copy .env.example .env
# then paste your key into .env: GROQ_API_KEY=gsk_...
```

## Run

```bash
streamlit run app.py        # web interface — open the printed localhost URL
python main.py --report     # CLI: data quality report
python main.py --summary    # CLI: generated nutritional summary
pytest -q                   # tests
```

## Using the web app

Two Starbucks menu CSVs (drinks, food) load automatically on start — no
upload required to try it. To use your own data, drop CSVs into the sidebar
uploaders; unrecognised column headers get a mapping prompt instead of being
silently guessed.

- **Overview** — data quality report, what nutrients each file actually has, headline comparison, LLM summary
- **Explore** — filtered table and derived ratios (fat-to-protein, per-100-kcal macros)
- **Charts** — top items by nutrient, calorie distribution, macro composition, scatter
- **Ask** — type a question in plain English ("which food item has the most protein?"); it's answered by running real pandas against the data, not by the LLM guessing numbers. Unanswerable questions (missing data, subjective) are declined with a reason, not a made-up figure.

Sidebar filters (nutrient range, text search, caffeine) apply across all four tabs.

## Specifications

| Doc | Covers |
|---|---|
| `docs/SPEC-01_Functional.md` | Requirements FR-01..FR-47, acceptance criteria, traceability to the brief |
| `docs/SPEC-02_Technical.md` | Stack, module contracts, function signatures, error handling, test strategy |
| `docs/SPEC-03_Schema_and_Ingestion.md` | Canonical schema, column resolution for uploads, units, duplicates, inferred fields |
| `docs/DATA_NOTES.md` | Audit findings for the supplied CSVs |

## Status

- [x] Ingestion layer with encoding fallback, sentinel handling, dedup, audit trail
- [x] Column resolver (uploads with unknown headers)
- [x] Capability registry
- [x] Analytics layer (descriptive stats, null-safe ratios, comparison, filters)
- [x] Charts (top-N, distribution, macro composition, scatter)
- [x] LLM summarisation (facts payload, Groq client, cache, error containment)
- [x] NL query planner (plan -> validate -> execute -> narrate, one retry)
- [x] Streamlit UI (overview, explore, charts, ask)
- [x] Test suite (68 tests)

## Data notes

See `docs/DATA_NOTES.md` for what the audit found in the supplied CSVs,
including which nutrients the source data does not carry.
