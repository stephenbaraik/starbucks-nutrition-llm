"""
Streamlit UI. The landing tab is a data-grounded chat; the remaining tabs
hold data quality, exploration, and charts. pandas computes every number;
the LLM only narrates a facts payload or creates a validated query plan.
"""

from __future__ import annotations

import hashlib
import json

import streamlit as st

from src.analytics.compare import normalised_comparison, raw_comparison
from src.analytics.stats import derived_ratios, describe
from src.config import NUTRIENT_LABELS
from src.ingestion.pipeline import capabilities, combined_frame, load_all
from src.llm.client import LLMClient
from src.llm.executor import answer
from src.llm.facts import build_facts, facts_digest
from src.llm.summarizer import chat_briefing, quality_briefing
from src.viz.charts import macro_composition, top_n_bar

st.set_page_config(page_title="Starbucks Nutrition Intelligence", layout="wide")

st.markdown(
    """
    <style>
    /* User turns: compact bubble, right-aligned, like any messaging app. */
    [data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {
        flex-direction: row-reverse;
    }
    [data-testid="stChatMessageContent"][aria-label="Chat message from user"] {
        flex-grow: 0;
        max-width: 75%;
        margin-right: 0;
        margin-left: auto;
        background: #00704A;
        border-radius: 14px;
        padding: 0.6rem 1rem;
    }
    /* Assistant turns: no bubble, full width — content is often a table or a
       long analysis, and a narrow colored box makes both unreadable. */
    [data-testid="stChatMessageContent"][aria-label="Chat message from assistant"] {
        max-width: 100%;
        padding: 0.2rem 0;
    }
    /* The LLM often replies with a markdown table (stats, cleaning report) —
       style it so it's actually readable on a dark background, since
       Streamlit's default table styling is built for the light theme. */
    [data-testid="stMarkdownContainer"] table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
        margin: 0.5rem 0 1rem;
    }
    [data-testid="stMarkdownContainer"] th,
    [data-testid="stMarkdownContainer"] td {
        border: 1px solid rgba(255, 255, 255, 0.12);
        padding: 0.4rem 0.6rem;
        text-align: left;
    }
    [data-testid="stMarkdownContainer"] th {
        background: #1B2420;
        font-weight: 600;
    }
    [data-testid="stMarkdownContainer"] tr:nth-child(even) td {
        background: rgba(255, 255, 255, 0.03);
    }
    /* Pin the question box to the bottom-center of the screen, like a real
       chat app, instead of Streamlit's default (bottom of the column, which
       drifts as messages pile up). */
    [data-testid="stChatInput"] {
        position: fixed;
        bottom: 1.5rem;
        left: 50%;
        transform: translateX(-50%);
        width: min(60%, 700px);
        z-index: 1000;
    }
    [data-testid="stBottomBlockContainer"] {
        padding-bottom: 6rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# Streamlit reruns this whole script on every interaction, so caching is what
# stops us re-reading and re-cleaning the same CSVs (or re-calling Groq) on
# every click. _load keyed on the file bytes; _client is a single shared
# instance for the whole session.
@st.cache_data(show_spinner="Loading and cleaning menus...")
def _load(drinks_bytes, food_bytes):
    return load_all(drinks_bytes, food_bytes)


@st.cache_resource
def _client():
    return LLMClient()


def _classify(files):
    """Guess which uploaded file is drinks vs food from its filename."""
    drinks = next((f for f in files if "drink" in f.name.lower()), None)
    food = next((f for f in files if "food" in f.name.lower()), None)
    if drinks and food and drinks is not food:
        return drinks, food
    return None, None


st.title("Starbucks Nutrition Intelligence")

# Upload gate: nothing below this block renders until we have both files.
# Users drop both CSVs into one uploader; we guess which is which from the
# filename, and only fall back to asking the user when that guess is
# ambiguous (e.g. neither name contains "drink" or "food").
with st.expander("Upload menu CSVs", expanded="datasets" not in st.session_state):
    uploads = st.file_uploader(
        "Upload the drinks and food nutrition CSVs together",
        type="csv",
        accept_multiple_files=True,
    )
    if uploads and len(uploads) >= 2:
        drinks_upload, food_upload = _classify(uploads)
        if drinks_upload is None:
            names = [f.name for f in uploads]
            col1, col2 = st.columns(2)
            drinks_name = col1.selectbox("Which file is drinks?", names, key="drinks_pick")
            food_name = col2.selectbox("Which file is food?", names, index=min(1, len(names) - 1), key="food_pick")
            if drinks_name == food_name:
                st.warning("Pick two different files.")
                st.stop()
            drinks_upload = next(f for f in uploads if f.name == drinks_name)
            food_upload = next(f for f in uploads if f.name == food_name)
        st.session_state.datasets = _load(drinks_upload, food_upload)
    elif uploads:
        st.info("Upload both the drinks and food CSVs to continue.")

# Still no data? Stop here rather than let the rest of the script crash on
# an empty `datasets` — the user just sees the upload prompt and nothing else.
if "datasets" not in st.session_state:
    st.info("Waiting for the drinks and food nutrition CSVs.")
    st.stop()

datasets = st.session_state.datasets

# Data cleaning report: the first thing a user sees after uploading is how
# dirty their file actually was and what the pipeline did about it. Cached
# by a hash of the report content, so re-running the script (e.g. clicking a
# chart dropdown) doesn't re-call the LLM for the same report.
reports = {name: dataset.report.__dict__ for name, dataset in datasets.items()}
report_id = hashlib.sha256(json.dumps(reports, sort_keys=True, default=str).encode()).hexdigest()
if st.session_state.get("quality_id") != report_id:
    st.session_state.quality_id = report_id
    with st.spinner("Checking how clean the uploaded data is..."):
        st.session_state.quality_report = quality_briefing(reports, _client())

st.subheader("Data cleaning report")
st.write(st.session_state.quality_report)
st.divider()

# caps records which nutrients are actually usable (present, non-empty) so
# the rest of the app — chat, stats, charts — never has to guess or invent
# a value for something the source data simply doesn't have.
caps = capabilities(datasets)
combined = combined_frame(datasets)
facts = build_facts(datasets, caps)

# Same caching idea as the quality report: only ask the LLM for a fresh
# opening summary when the underlying data has actually changed.
data_id = facts_digest(facts)
if st.session_state.get("chat_data_id") != data_id:
    st.session_state.chat_data_id = data_id
    st.session_state.chat_messages = [{
        "role": "assistant",
        "content": chat_briefing(facts, _client()),
    }]

tab_chat, tab_stats, tab_charts = st.tabs(["Chat", "Data & Stats", "Charts"])

# Chat tab: replay the conversation so far, then handle a new question.
# Every question goes question -> LLM-proposed plan -> pandas execution ->
# LLM narration, so the numbers in the answer always come from pandas, never
# from the model doing arithmetic in its head.
with tab_chat:
    st.subheader("Ask about the loaded menu data")
    st.caption("Answers use only values available in the loaded CSV files.")
    avatars = {"user": "🙂", "assistant": "☕"}
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"], avatar=avatars[message["role"]]):
            st.write(message["content"])

    question = st.chat_input("For example: Which food item has the most protein?")
    if question:
        st.session_state.chat_messages.append({"role": "user", "content": question})
        with st.chat_message("user", avatar=avatars["user"]):
            st.write(question)

        with st.chat_message("assistant", avatar=avatars["assistant"]):
            with st.spinner("Checking the loaded data..."):
                result = answer(question, datasets, caps, _client())
            if result["status"] == "unsupported":
                response = "I cannot answer that from the loaded data: " + result["reason"]
            else:
                response = result["narrative"]
            st.write(response)
        st.session_state.chat_messages.append({"role": "assistant", "content": response})

# Data & Stats tab: the raw pandas output, unfiltered — the full table,
# descriptive statistics, ratios, and a drinks-vs-food comparison shown both
# as raw totals and normalised per 100 kcal (raw totals alone are
# misleading since drinks are per serving and food is per item).
with tab_stats:
    st.subheader("All items")
    st.dataframe(combined)

    st.subheader("Descriptive statistics")
    st.dataframe(describe(combined, caps["comparable"]))

    st.subheader("Fat-to-protein and other ratios")
    st.dataframe(derived_ratios(combined))

    st.subheader("Compare: drinks vs food")
    if caps["unavailable_labels"]:
        st.caption("Not present in the source data: " + ", ".join(caps["unavailable_labels"]))
    st.dataframe(raw_comparison(datasets, caps["comparable"]))
    st.caption("Same metrics, normalised per 100 kcal so drinks and food are comparable:")
    st.dataframe(normalised_comparison(datasets, caps["comparable"]))

# Charts tab: two plots, both driven by whichever nutrient the user picks —
# a bar chart of the top items, and a grouped comparison of macro
# composition between drinks and food (per 100 kcal, for the same
# apples-to-apples reason as the comparison table above).
with tab_charts:
    nutrient = st.selectbox("Nutrient", caps["comparable"], format_func=lambda c: NUTRIENT_LABELS.get(c, c))
    st.plotly_chart(top_n_bar(combined, nutrient), width="stretch")
    st.plotly_chart(macro_composition(normalised_comparison(datasets, caps["comparable"])), width="stretch")
