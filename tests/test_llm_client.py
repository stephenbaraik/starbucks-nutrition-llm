import json

from src.llm.client import LLMClient, NO_KEY_NOTICE


def test_disabled_without_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    client = LLMClient()
    assert client.enabled is False
    assert client.complete("sys", "user") == NO_KEY_NOTICE


def test_cache_hit_skips_the_sdk_call(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    monkeypatch.setattr("src.llm.client.CACHE_DIR", tmp_path)

    class ExplodingClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise AssertionError("SDK should not be called on a cache hit")

    client = LLMClient()
    client._client = ExplodingClient()
    key = client._cache_key("sys", "user", False)
    (tmp_path / f"{key}.json").write_text(json.dumps({"response": "cached answer"}))

    assert client.complete("sys", "user") == "cached answer"


def test_sdk_exception_returns_notice_not_traceback(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    monkeypatch.setattr("src.llm.client.CACHE_DIR", tmp_path)

    class FailingClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise RuntimeError("boom")

    client = LLMClient()
    client._client = FailingClient()
    result = client.complete("sys", "user")
    assert "error" in result.lower()
    assert "RuntimeError" in result


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
