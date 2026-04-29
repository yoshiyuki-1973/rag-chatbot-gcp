import pytest

from app.adapters.llm.grok import GrokLLMClient
from app.main import _create_llm_client
from app.settings import Settings


def test_create_llm_client_returns_grok_instance():
    settings = Settings(
        GROK_API_KEY="xai-test",
        GROK_MODEL="grok-4.20",
        LLM_PROVIDER="grok",
        _env_file=None,
    )
    client = _create_llm_client(settings)
    assert isinstance(client, GrokLLMClient)


def test_create_llm_client_raises_for_unknown_provider():
    settings = Settings(
        GROK_API_KEY="xai-test",
        LLM_PROVIDER="unknown",
        _env_file=None,
    )
    with pytest.raises(RuntimeError, match="Unsupported LLM_PROVIDER"):
        _create_llm_client(settings)


def test_create_llm_client_error_message_includes_provider_name():
    settings = Settings(
        GROK_API_KEY="xai-test",
        LLM_PROVIDER="openai",
        _env_file=None,
    )
    with pytest.raises(RuntimeError, match="'openai'"):
        _create_llm_client(settings)
