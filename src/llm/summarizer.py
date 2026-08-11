"""facts -> prose. Thin glue: the client and prompts do the real work."""

from __future__ import annotations

from src.llm.client import LLMClient
from src.llm.prompts import SUMMARY_SYSTEM_V1, summary_user_prompt


def summarise(facts: dict, client: LLMClient) -> str:
    return client.complete(SUMMARY_SYSTEM_V1, summary_user_prompt(facts))
