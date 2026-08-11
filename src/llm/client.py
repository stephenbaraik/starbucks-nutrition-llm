"""
Groq wrapper. Everything else in the app talks to the LLM only through this
class, so these three behaviours are guaranteed in exactly one place:

- No GROQ_API_KEY -> enabled is False, complete() returns a notice, no
  exception. The rest of the app keeps working without LLM narration.
- Any SDK exception (network error, rate limit, bad key, ...) -> a short
  formatted notice naming the error type. No raw traceback ever reaches
  the user; the real exception is only in the logs.
- Identical (model, system, user, json_mode) -> served from a disk cache,
  so re-running the same prompt in the same session never re-calls the
  API or re-spends a rate-limited quota.
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
        # No key -> leave _client as None. `enabled` below reflects that,
        # and every caller is expected to check it (or just call complete()
        # and get the NO_KEY_NOTICE back).
        if self._api_key:
            from groq import Groq
            self._client = Groq(api_key=self._api_key)
        CACHE_DIR.mkdir(exist_ok=True)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def _cache_key(self, system: str, user: str, json_mode: bool) -> str:
        """One cache entry per distinct prompt — same inputs, same answer."""
        raw = f"{self.model}|{system}|{user}|{json_mode}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _cache_path(self, key: str):
        return CACHE_DIR / f"{key}.json"

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        if not self.enabled:
            return NO_KEY_NOTICE

        # Cache hit: skip the network call entirely.
        key = self._cache_key(system, user, json_mode)
        path = self._cache_path(key)
        if path.exists():
            return json.loads(path.read_text())["response"]

        try:
            # json_mode is used by the query planner, which needs a
            # parseable JSON object back rather than free-form prose.
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
            # Log the real exception for debugging, but hand the user a
            # short, safe message instead of a stack trace.
            logger.exception("Groq call failed (model=%s, json_mode=%s)", self.model, json_mode)
            return f"The summary service returned an error ({type(exc).__name__}). Please try again later."

        path.write_text(json.dumps({"response": text}))
        return text
