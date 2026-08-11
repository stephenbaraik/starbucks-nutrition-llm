import json

from src.ingestion.pipeline import capabilities, load_all
from src.llm.facts import build_facts, facts_digest


def test_facts_has_mandatory_keys():
    datasets = load_all()
    caps = capabilities(datasets)
    facts = build_facts(datasets, caps)
    assert "unavailable_nutrients" in facts
    assert "inferred_fields" in facts
    assert "sources" in facts and set(facts["sources"]) == {"drinks", "food"}


def test_facts_names_absent_nutrients():
    datasets = load_all()
    caps = capabilities(datasets)
    facts = build_facts(datasets, caps)
    assert "Sugars (g)" in facts["unavailable_nutrients"]
    assert "Caffeine (mg)" in facts["unavailable_nutrients"]


def test_facts_payload_size_independent_of_row_count():
    datasets = load_all()
    caps = capabilities(datasets)
    facts = build_facts(datasets, caps)
    # ~4 chars/token is a safe overestimate; payload must stay well under 1000 tokens.
    assert len(json.dumps(facts)) < 4000


def test_facts_digest_stable_for_same_input():
    datasets = load_all()
    caps = capabilities(datasets)
    facts = build_facts(datasets, caps)
    assert facts_digest(facts) == facts_digest(facts)


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
