"""facts -> prose. Thin glue: the client and prompts do the real work."""

from __future__ import annotations

from src.llm.client import LLMClient
from src.llm.facts import data_briefing
from src.llm.prompts import (
    QUALITY_SYSTEM_V1,
    SUMMARY_SYSTEM_V1,
    quality_user_prompt,
    summary_user_prompt,
)


def summarise(facts: dict, client: LLMClient) -> str:
    """The LLM's EDA table+narration over the whole dataset. No fallback
    here — chat_briefing() below is what adds the offline fallback for the
    one caller (the opening chat message) that needs to always show
    something even without a Groq key."""
    return client.complete(SUMMARY_SYSTEM_V1, summary_user_prompt(facts))


def quality_briefing(reports: dict, client: LLMClient) -> str:
    """The LLM's narration of how dirty the uploaded data was, shown right
    after upload. If disabled/erroring, client.complete() already returns
    a plain notice string, so no extra fallback is needed here."""
    return client.complete(QUALITY_SYSTEM_V1, quality_user_prompt(reports))


def chat_briefing(facts: dict, client: LLMClient) -> str:
    """Return a data-only opening message, with a deterministic fallback.

    Unlike quality_briefing, this one can't just show client.complete()'s
    generic notice — the chat needs a real opening message even with no
    API key, so it falls back to facts.data_briefing() (built with plain
    string formatting, no LLM involved) whenever the LLM path comes back
    empty or errored.
    """
    if not client.enabled:
        return data_briefing(facts)

    summary = summarise(facts, client)
    if summary.startswith("The summary service returned an error"):
        return data_briefing(facts)
    return summary
