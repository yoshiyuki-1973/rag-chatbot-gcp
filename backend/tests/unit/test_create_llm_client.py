import pytest

from app.adapters.llm.gemini import GeminiLLMClient
from app.main import _create_llm_client
from app.settings import Settings


def test_create_llm_client_returns_gemini_instance_by_default():
    settings = Settings(
        GEMINI_API_KEY="gemini-test",
        _env_file=None,
    )
    client = _create_llm_client(settings)
    assert isinstance(client, GeminiLLMClient)


def test_create_llm_client_raises_for_unknown_provider():
    settings = Settings(
        GEMINI_API_KEY="gemini-test",
        LLM_PROVIDER="unknown",
        _env_file=None,
    )
    with pytest.raises(RuntimeError, match="Unsupported LLM_PROVIDER"):
        _create_llm_client(settings)


def test_create_llm_client_error_message_includes_provider_name():
    settings = Settings(
        GEMINI_API_KEY="gemini-test",
        LLM_PROVIDER="openai",
        _env_file=None,
    )
    with pytest.raises(RuntimeError, match="'openai'"):
        _create_llm_client(settings)
