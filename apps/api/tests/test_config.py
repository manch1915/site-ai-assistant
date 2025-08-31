import pytest

from app.config import Settings


def test_openai_style_variable_names_are_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://llm.example/v1")

    settings = Settings(_env_file=None)

    assert settings.llm_api_key == "sk-test"
    assert settings.llm_base_url == "https://llm.example/v1"
    assert settings.llm_enabled


def test_own_variable_names_win(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-own")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-other")

    assert Settings(_env_file=None).llm_api_key == "sk-own"
