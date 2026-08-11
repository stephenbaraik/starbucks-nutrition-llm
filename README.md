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

A Groq key is optional. Without one, ingestion, cleaning, statistics, and
charts all work; generated summaries and chat answers show a plain
availability notice instead. To enable them, get a free key at
[console.groq.com](https://console.groq.com/keys):

```bash
cp .env.example .env         # Windows: copy .env.example .env
# then paste your key into .env: GROQ_API_KEY=gsk_...
```

## Run

```bash
streamlit run app.py        # web interface — open the printed localhost URL
python main.py --report     # CLI: data quality report (bundled sample CSVs)
python main.py --summary    # CLI: generated nutritional summary
pytest -q                   # tests
```

## Using the web app

The app asks for both CSVs (drinks and food) before showing anything else —
drop them together into the single uploader; the app guesses which file is
which from the filename, and asks you to confirm if that's ambiguous.
Unrecognised column headers get a mapping prompt instead of being silently
guessed.

Immediately after upload, a **data cleaning report** shows how dirty each
file was and exactly what got cleaned out (duplicates, missing values,
unparseable cells, absent columns).

Then three tabs:

- **Chat** — opens with an LLM-written EDA summary (a stats table plus
  narration); ask follow-up questions in plain English, including filtering
  ("food items under 500 calories") — each answer is computed by pandas
  first, then narrated by the LLM, never guessed.
- **Data & Stats** — the full data table, descriptive statistics, derived
  ratios (fat-to-protein, per-100-kcal macros), and a drinks-vs-food
  comparison (raw and normalised).
- **Charts** — top items by nutrient, and a macro-composition comparison
  between drinks and food.

Unanswerable questions (missing data, subjective) are declined with a
reason, not a made-up figure.

## Specifications

| Doc | Covers |
|---|---|
| `docs/SPEC.md` | The original brief, verbatim, plus a requirement-to-code traceability table and the current system design |
| `docs/DATA_NOTES.md` | Audit findings for the supplied CSVs |
| `docs/PRESENTATION_CONTENT.md` | Slide-by-slide content for the submission deck |

## Status

- [x] Ingestion layer with encoding fallback, sentinel handling, dedup, audit trail
- [x] Column resolver (uploads with unknown headers)
- [x] Capability registry
- [x] Analytics layer (descriptive stats, null-safe ratios, comparison, predicate filters)
- [x] Charts (top-N bar, macro composition)
- [x] LLM summarisation (facts payload, Groq client, cache, error containment)
- [x] NL query planner (plan -> validate -> execute -> narrate, one retry)
- [x] Data cleaning report, narrated from the real ingestion report
- [x] Streamlit UI (upload gate, chat, data & stats, charts)
- [x] Test suite (74 tests)

## Data notes

See `docs/DATA_NOTES.md` for what the audit found in the supplied CSVs,
including which nutrients the source data does not carry.
