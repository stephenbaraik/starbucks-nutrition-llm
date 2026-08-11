"""CLI entrypoints for the bundled files: a data quality report, or a generated summary."""

from __future__ import annotations

import argparse
import json

from src.ingestion.pipeline import capabilities, load_all
from src.llm.client import LLMClient
from src.llm.facts import build_facts
from src.llm.summarizer import summarise


def main() -> None:
    # Two mutually exclusive modes: dump the raw cleaning report, or ask the
    # LLM for a narrated summary. Exactly one must be picked.
    parser = argparse.ArgumentParser(description="Starbucks Nutrition Intelligence CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--report", action="store_true", help="Print the data quality report for both sources")
    group.add_argument("--summary", action="store_true", help="Print an LLM-generated nutritional summary")
    args = parser.parse_args()

    # Always load the bundled default CSVs — this CLI has no upload step,
    # it's just a quick way to check the pipeline without starting Streamlit.
    datasets = load_all()
    caps = capabilities(datasets)

    if args.report:
        # Just the pandas-computed cleaning facts, no LLM call involved.
        for name, dataset in datasets.items():
            print(f"\n=== {name} ===")
            print(json.dumps(dataset.report.__dict__, indent=2, default=str))
        return

    # --summary: build the same facts payload the Streamlit chat uses, and
    # let the LLM narrate it.
    facts = build_facts(datasets, caps)
    print(summarise(facts, LLMClient()))


if __name__ == "__main__":
    main()
