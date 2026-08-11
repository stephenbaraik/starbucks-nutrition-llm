"""CLI entrypoints for the bundled files: a data quality report, or a generated summary."""

from __future__ import annotations

import argparse
import json

from src.ingestion.pipeline import capabilities, load_all
from src.llm.client import LLMClient
from src.llm.facts import build_facts
from src.llm.summarizer import summarise


def main() -> None:
    parser = argparse.ArgumentParser(description="Starbucks Nutrition Intelligence CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--report", action="store_true", help="Print the data quality report for both sources")
    group.add_argument("--summary", action="store_true", help="Print an LLM-generated nutritional summary")
    args = parser.parse_args()

    datasets = load_all()
    caps = capabilities(datasets)

    if args.report:
        for name, dataset in datasets.items():
            print(f"\n=== {name} ===")
            print(json.dumps(dataset.report.__dict__, indent=2, default=str))
        return

    facts = build_facts(datasets, caps)
    print(summarise(facts, LLMClient()))


if __name__ == "__main__":
    main()
