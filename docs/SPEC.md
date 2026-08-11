# Spec

Source: AMARIS technical test instructions. Verbatim below, unchanged. Everything this
codebase does is scoped to this document — nothing more, nothing less.

## Overview

The objective of this technical test is to evaluate your ability to apply large language
models (LLMs) to a real-world task, handle data efficiently in Python, and demonstrate good
software design practices. You will build a simple LLM-powered application using provided
datasets and handle a data processing challenge as part of this test.

## Scenario

You are tasked with building a prototype of an "LLM-powered nutrition analysis tool" for
Starbucks' menu. The tool should load two datasets (one for drinks, one for food), process the
data, and generate natural language summaries of key nutritional insights using the Groq LLM
API.

You can use Groq's free LLM API to interact with the model. For more details, refer to the Groq
Quickstart documentation.

## Datasets

You will be provided with two CSV files:

1. Starbucks Drink Nutrition Data
2. Starbucks Food Nutrition Data

Your task is to process these datasets and extract meaningful insights about the nutrition
content of Starbucks menu items.

## Requirements

### Part 1: Data Loading and Processing

**1. CSV Data Ingestion**
- Create a Python script that loads the provided Starbucks drink and food CSVs into memory
  using `pandas`.
- Ensure the program can handle common CSV formatting issues (e.g., missing data, inconsistent
  entries).

**2. Data Processing**
- Provide basic descriptive statistics for both the drink and food datasets (e.g., total
  calories, average sugar content, fat-to-protein ratio).
- Compare and contrast key metrics across the two datasets (e.g., average calorie comparison
  between drinks and food items).
- Generate a visualization (e.g., bar chart, pie chart) comparing key nutritional aspects like
  calories, sugars, or fats between different menu items.

**3. Handling Datasets**
- Implement basic handling for datasets by allowing users to filter data based on certain
  criteria (e.g., show only drinks with caffeine, or food items under 500 calories).

### Part 2: LLM-based Summarization

**1. Nutritional Summarization**
- Use the Groq LLM API to implement a feature that summarizes nutritional insights from both
  datasets.
- For example, the LLM could generate a summary about which drink items have the highest sugar
  content or which food items are most calorie-dense.

### Part 3: Code Quality & Documentation

**1. Modular Code**
- Structure your code into well-organized functions and modules. Ensure separation of concerns
  between data loading, processing, and summarization.
- Ensure the code is easy to follow and can be extended in the future.

**2. Documentation**
- Provide clear documentation on how to run the program, including any installation
  requirements.
- Comment your code sufficiently to explain your logic and reasoning.

### Bonus (Optional)

**1. LLM-Driven Queries**
- Implement an extra feature where users can input natural language queries about the Starbucks
  menu data, and the LLM provides an answer (e.g., "What's the average caffeine content for
  drinks?").

**2. Web Interface**
- If you have additional time, create a simple web interface using `Flask` or `Streamlit` that
  allows users to upload the CSVs and interact with the tool through their browser.

## Where each requirement is satisfied

| Requirement | Where |
|---|---|
| CSV ingestion, handles missing/inconsistent data | [src/ingestion/loader.py](../src/ingestion/loader.py), [src/ingestion/cleaner.py](../src/ingestion/cleaner.py), [src/ingestion/resolver.py](../src/ingestion/resolver.py) |
| Descriptive statistics | `describe()` in [src/analytics/stats.py](../src/analytics/stats.py), shown in the Data & Stats tab and in the LLM's opening summary table |
| Fat-to-protein and other ratios | `derived_ratios()` in [src/analytics/stats.py](../src/analytics/stats.py) |
| Compare drinks vs food | `raw_comparison()` / `normalised_comparison()` in [src/analytics/compare.py](../src/analytics/compare.py) |
| Visualization (bar/pie) | [src/viz/charts.py](../src/viz/charts.py), Charts tab in [app.py](../app.py) |
| Filtering (caffeine, calorie threshold, etc.) | Natural-language, through Chat — e.g. "show food items under 500 calories" is parsed into a `QueryPlan` with `Predicate` filters by [src/llm/planner.py](../src/llm/planner.py) and applied by `apply_predicates()` in [src/analytics/filters.py](../src/analytics/filters.py) via [src/llm/executor.py](../src/llm/executor.py). No static filter widgets. |
| LLM nutritional summarization (Groq) | [src/llm/summarizer.py](../src/llm/summarizer.py), [src/llm/facts.py](../src/llm/facts.py) — pandas computes the numbers, the LLM renders a markdown stats table plus prose narration |
| Modular code / separation of concerns | `src/ingestion/`, `src/analytics/`, `src/llm/`, `src/viz/` are independent layers; `app.py` only wires them together |
| Documentation | [README.md](../README.md) |
| Bonus: LLM-driven natural language queries | [src/llm/planner.py](../src/llm/planner.py) (question → validated query plan) + [src/llm/executor.py](../src/llm/executor.py) (plan → pandas result → LLM narration), Chat tab in [app.py](../app.py) |
| Bonus: web interface | [app.py](../app.py) (Streamlit) |

## Current system design

**Upload gate.** The app shows nothing but a single combined file uploader until both CSVs are
present (`app.py`). Files are matched to "drinks" / "food" by filename; if that's ambiguous the
user is asked to map them explicitly. There is no default/bundled dataset silently pre-loaded —
the tool always asks for the data first.

**Data cleaning report.** Immediately after both files load, the app shows what the ingestion
pipeline actually did to the data: a markdown table (rows read, rows retained, retention %,
duplicates removed, name conflicts resolved, rows with no nutrition data, per source) plus an
LLM narration of how dirty each source was and what was cleaned out of it (sentinel cells,
unparseable cells, absent columns, unit conversions). Source: `DataQualityReport` in
`src/ingestion/cleaner.py`, narrated by `quality_briefing()` in `src/llm/summarizer.py`.

**Chat (landing tab).** Opens with an LLM-written EDA summary of the whole dataset: a markdown
table of mean/median/std/min/max/coverage per nutrient per source, followed by a short prose
narration (standout items, fat-to-protein ratio interpretation, drinks-vs-food comparison with
the per-serving/per-item caveat). The user can then ask follow-up questions in natural language;
each question goes through `propose_plan()` (LLM → validated `QueryPlan`) → `execute()` (pandas,
never the LLM) → narration (LLM, grounded in the executed result only).

**Data & Stats tab.** Unfiltered pandas output: the full combined table, descriptive statistics,
derived ratios, and the drinks-vs-food comparison (raw and per-100-kcal normalised). No filter
controls — filtering lives in the chat, as natural language.

**Charts tab.** Two visualizations: a bar chart of the top items by a chosen nutrient, and a
grouped bar chart comparing macro composition (per 100 kcal) between drinks and food.

**Chat UI.** User turns render as a compact right-aligned bubble (Starbucks green). Assistant
turns render full-width with no bubble, since replies are often a markdown table plus prose and
a narrow colored box makes both unreadable — this matches the ChatGPT/Claude convention of
reserving the bubble for short human turns only.

## Design principle

The LLM never computes numbers — it only narrates numbers pandas already computed. This is
deliberate: LLMs are unreliable at arithmetic, and grounding every sentence in a real computed
fact avoids hallucinated statistics. See `src/llm/facts.py` (analysis narration) and
`src/llm/executor.py` (chat query narration) for the two places this boundary is enforced.
