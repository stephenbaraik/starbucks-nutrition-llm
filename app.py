"""
Streamlit UI. Sidebar drives uploads and filters; tabs cover overview,
exploration, charts, and the NL query path. pandas computes every number
shown here; the LLM only narrates it.
"""

from __future__ import annotations

import streamlit as st

from src.analytics.compare import normalised_comparison, raw_comparison
from src.analytics.filters import Predicate, apply_caffeine_filter, apply_predicates, apply_text_filter
from src.analytics.stats import derived_ratios, describe
from src.config import NUTRIENT_LABELS
from src.ingestion.pipeline import capabilities, combined_frame, load_all
from src.llm.client import LLMClient
from src.llm.executor import answer
from src.llm.facts import build_facts
from src.llm.summarizer import summarise
from src.viz.charts import distribution_by_source, macro_composition, scatter, top_n_bar

st.set_page_config(page_title="Starbucks Nutrition Intelligence", layout="wide")


@st.cache_data(show_spinner="Loading and cleaning menus...")
def _load(drinks_bytes, food_bytes):
    return load_all(drinks_bytes, food_bytes)


@st.cache_resource
def _client():
    return LLMClient()


st.sidebar.header("Data")
drinks_upload = st.sidebar.file_uploader("Drinks CSV", type="csv")
food_upload = st.sidebar.file_uploader("Food CSV", type="csv")

datasets = _load(drinks_upload, food_upload)
caps = capabilities(datasets)
combined = combined_frame(datasets)

st.sidebar.header("Filters")
source_choice = st.sidebar.multiselect("Source", ["drinks", "food"], default=["drinks", "food"])
text_query = st.sidebar.text_input("Search item name")
caffeine_choice = st.sidebar.selectbox(
    "Caffeine", ["Any", "Caffeinated", "Caffeine-free"],
    disabled=not caps["caffeine_is_inferred"],
)
caffeinated = {"Any": None, "Caffeinated": True, "Caffeine-free": False}[caffeine_choice]

nutrient_filters: list[Predicate] = []
for nutrient in caps["comparable"]:
    lo, hi = float(combined[nutrient].min()), float(combined[nutrient].max())
    if lo == hi:
        continue
    chosen = st.sidebar.slider(NUTRIENT_LABELS.get(nutrient, nutrient), lo, hi, (lo, hi))
    if chosen[0] > lo:
        nutrient_filters.append(Predicate(nutrient, ">=", chosen[0]))
    if chosen[1] < hi:
        nutrient_filters.append(Predicate(nutrient, "<=", chosen[1]))

filtered = combined[combined["source"].isin(source_choice)]
filtered = apply_text_filter(filtered, text_query)
filtered = apply_caffeine_filter(filtered, caffeinated)
available = set(caps["comparable"]) | {c for cols in caps["per_source"].values() for c in cols}
filtered = apply_predicates(filtered, nutrient_filters, available)

tab_overview, tab_explore, tab_charts, tab_ask = st.tabs(["Overview", "Explore", "Charts", "Ask"])

with tab_overview:
    st.subheader("Data quality")
    for name, dataset in datasets.items():
        with st.expander(f"{name.title()} report"):
            st.json(dataset.report.__dict__, expanded=False)

    st.subheader("Capabilities")
    st.write("Comparable across sources:", ", ".join(NUTRIENT_LABELS.get(c, c) for c in caps["comparable"]))
    if caps["unavailable_labels"]:
        st.warning("Not present in the source data: " + ", ".join(caps["unavailable_labels"]))

    st.subheader("Headline comparison")
    st.dataframe(raw_comparison(datasets, caps["comparable"]))
    st.dataframe(normalised_comparison(datasets, caps["comparable"]))

    st.subheader("Summary")
    facts = build_facts(datasets, caps)
    st.write(summarise(facts, _client()))

with tab_explore:
    st.dataframe(filtered)
    st.subheader("Derived ratios")
    st.dataframe(derived_ratios(filtered))
    st.subheader("Descriptive statistics")
    st.dataframe(describe(filtered, caps["comparable"]))

with tab_charts:
    nutrient = st.selectbox("Nutrient", caps["comparable"], format_func=lambda c: NUTRIENT_LABELS.get(c, c))
    st.plotly_chart(top_n_bar(filtered, nutrient), use_container_width=True)
    st.plotly_chart(distribution_by_source(filtered, nutrient), use_container_width=True)
    st.plotly_chart(macro_composition(normalised_comparison(datasets, caps["comparable"])), use_container_width=True)
    x, y = st.columns(2)
    x_axis = x.selectbox("X axis", caps["comparable"], format_func=lambda c: NUTRIENT_LABELS.get(c, c), key="x")
    y_axis = y.selectbox("Y axis", caps["comparable"], format_func=lambda c: NUTRIENT_LABELS.get(c, c), key="y")
    st.plotly_chart(scatter(filtered, x_axis, y_axis), use_container_width=True)

with tab_ask:
    question = st.text_input("Ask a question about the menu data")
    if question:
        result = answer(question, datasets, caps, _client())
        if result["status"] == "unsupported":
            st.info(result["reason"])
        else:
            st.json(result.get("plan", {}))
            st.write(result.get("result", result.get("rows")))
