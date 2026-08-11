"""
Groq wrapper. Behaviour contract (SPEC-02 §4.6):

- No GROQ_API_KEY -> enabled is False, complete() returns a notice, no
  exception (FR-30).
- Any SDK exception -> a formatted notice naming the error type, no
  traceback reaches the user (FR-31).
- Identical (model, system, user, json_mode) -> served from a disk cache,
  no second API call in-session (FR-32).
"""

from __future__ import annotations

import hashlib
import json
import os

from src.config import CACHE_DIR, LLM_MAX_TOKENS, LLM_MODEL_SUMMARY, LLM_TEMPERATURE
from src.utils.logging import get_logger

logger = get_logger(__name__)

NO_KEY_NOTICE = "Summaries are unavailable: no GROQ_API_KEY is configured. Statistics, filters and charts are unaffected."


class LLMClient:
    def __init__(self, model: str = LLM_MODEL_SUMMARY):
        self.model = model
        self._api_key = os.environ.get("GROQ_API_KEY")
        self._client = None
        if self._api_key:
            from groq import Groq
            self._client = Groq(api_key=self._api_key)
        CACHE_DIR.mkdir(exist_ok=True)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def _cache_key(self, system: str, user: str, json_mode: bool) -> str:
        raw = f"{self.model}|{system}|{user}|{json_mode}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _cache_path(self, key: str):
        return CACHE_DIR / f"{key}.json"

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        if not self.enabled:
            return NO_KEY_NOTICE

        key = self._cache_key(system, user, json_mode)
        path = self._cache_path(key)
        if path.exists():
            return json.loads(path.read_text())["response"]

        try:
            kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
                **kwargs,
            )
            text = resp.choices[0].message.content
        except Exception as exc:  # Groq SDK errors, network errors, rate limits
            logger.exception("Groq call failed (model=%s, json_mode=%s)", self.model, json_mode)
            return f"The summary service returned an error ({type(exc).__name__}). Please try again later."

        path.write_text(json.dumps({"response": text}))
        return text
