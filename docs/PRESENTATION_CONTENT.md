# Presentation content — Starbucks Nutrition Intelligence

Use this as the content for a 7-slide PowerPoint deck. Apply your own template,
branding, and layout.

## Slide 1 — Title

**Starbucks Nutrition Intelligence**
AMARIS Technical Test

An LLM-powered nutrition exploration tool for Starbucks drinks and food menus.

**Design principle:** pandas computes every number; the LLM only narrates verified facts —
never asked to do arithmetic.

Stack: Streamlit · pandas · Plotly · Groq

## Slide 2 — Approach

**A layered pipeline keeps results trustworthy.**

1. **Upload** — the app asks for both CSVs first; nothing else renders until they're in.
2. **Ingest & clean** — resolve inconsistent headers, coerce nutrition values, drop empty rows,
   resolve duplicates.
3. **Report** — tell the user exactly how dirty the data was and what got cleaned, in a table
   plus plain language.
4. **Analyse** — compute statistics, ratios, and comparisons in pandas.
5. **Explain** — send a compact facts payload to Groq for natural-language narration; the user
   can then ask follow-up questions in the same chat.

Key controls:

- The LLM never receives raw rows or calculates nutrition figures.
- A capability registry prevents requests against unavailable nutrients.
- Generated query plans are validated against a fixed whitelist before pandas executes them.

Suggested visual: `Upload → Ingest/Clean → Report → Analyse → Explain` pipeline diagram.

## Slide 3 — Data handling

**The supplied files require active cleaning.**

### Drinks CSV

- 177 raw rows; 74 retained for analysis (41.8% retention).
- 85 rows contain no nutrition values, with sentinel cells across calories, fat, sodium, etc.
- Bare `-` values mask missing data from default pandas null checks.
- 17 exact duplicates and one item-name conflict are resolved.

### Food CSV

- UTF-16 LE with BOM; a default read can fail.
- 113 rows retained — 100% retention, no duplicates or conflicts.
- Nutrient headers have leading whitespace.
- Protein uses a different header: `Protein (g)` rather than `Protein`.

### Result

The app doesn't just clean silently — the first thing a user sees after uploading is a
data-cleaning report: a table of rows read/retained/dropped per source, plus an LLM narration of
what specifically was cleaned and whether the data can be trusted as-is.

## Slide 4 — Insights and data limitations

**Headline comparison**

- Mean calories: **356.6 kcal per food item** versus **138.7 kcal per drink**.
- Food averages **2.57×** the calories of drinks on a per-item/serving basis.
- The app also provides per-100-kcal views to avoid misleading raw comparisons.
- Fat-to-protein ratio: **0.68** for drinks vs **2.49** for food — drinks skew protein-leaning,
  food skews fat-leaning.

**Important limitations**

- Neither source contains measured sugar, caffeine, or saturated-fat data.
- Sodium is present for drinks only.
- Caffeine status is inferred from item names and is explicitly labelled as inferred.
- Missing nutrients are reported instead of fabricated by the application or LLM.

## Slide 5 — Product tour

**A three-tab Streamlit interface, gated behind a single upload step.**

- **Upload gate:** one combined uploader for both CSVs — nothing else shows until both are in.
- **Data cleaning report:** shown immediately after upload, above the tabs.
- **Chat (landing tab):** opens with an LLM-written EDA summary — a markdown stats table plus a
  natural-language narration of what stands out. The user then asks follow-up questions in plain
  English (including filtering: "show food items under 500 calories"), each answered by a
  validated pandas query plan, narrated by the LLM.
- **Data & Stats:** full data table, descriptive statistics, derived ratios, drinks-vs-food
  comparison — unfiltered pandas output.
- **Charts:** top-N nutrient bar chart, macro-composition comparison.

Chat bubbles follow the ChatGPT/Claude convention: the user's short turns get a compact colored
bubble, the assistant's replies (often a table plus prose) render full-width with no bubble, so
tables stay readable.

Suggested visual: screenshot of the Chat tab showing the opening EDA table + narration.

## Slide 6 — How to run

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
# Optional: set GROQ_API_KEY=gsk_...

streamlit run app.py
python -m pytest -q
```

Upload the two Starbucks CSVs when prompted. Without a Groq key, ingestion, cleaning, and stats
still work; LLM narration and chat display a clear availability notice instead of failing.

## Slide 7 — Design decisions and trade-offs

### Included

- pandas for deterministic, reproducible figures — the LLM only narrates them
- compact LLM facts payloads rather than raw datasets
- disk caching for repeated LLM responses
- one retry for invalid LLM query plans
- filtering expressed as natural language through chat, not static widgets
- 78 automated tests across ingestion, analytics, LLM safety, charts, and the app itself

### Deliberately excluded

- database/authentication for a 187-row prototype
- RAG or vector store without a document corpus
- agent framework for a small, whitelisted workflow
- imputation of absent nutrition values
- static sidebar filter widgets — natural-language filtering through chat covers the same
  requirement with less UI surface

**Outcome:** a modular, fast, inspectable app where every reported figure is traceable to
pandas, not model guesses — scoped tightly to what the AMARIS brief actually asked for.
