# Starbucks Nutrition Intelligence

LLM-powered nutrition analysis over the Starbucks drinks and food menus.
Statistics are computed in pandas; the LLM only narrates values it is handed.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then paste your Groq key into .env
```

The app runs without a Groq key. Statistics, filters and charts all work;
the generated summaries are replaced with a notice.

## Run

```bash
streamlit run app.py        # web interface
python main.py --report     # CLI: data quality report
python main.py --summary    # CLI: generated nutritional summary
pytest -q                   # tests
```

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
- [x] Test suite (65 tests)

## Data notes

See `docs/DATA_NOTES.md` for what the audit found in the supplied CSVs,
including which nutrients the source data does not carry.
