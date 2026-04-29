from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.main as _main
from app.main import app
from app.settings import get_settings

_FAKE_ENV = {
    "DATABASE_URL": "postgresql://test:test@localhost/test",
    "OPENAI_API_KEY": "sk-test",
    "GEMINI_API_KEY": "gemini-test",
    "LLM_PROVIDER": "gemini",
}


def _make_mock_pool(db_ok: bool = True) -> MagicMock:
    """asyncpg.Pool のモックを生成する。"""
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1) if db_ok else AsyncMock(side_effect=Exception("connection refused"))
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = cm
    mock_pool.close = AsyncMock()
    return mock_pool


class _FakeLLM:
    def __init__(self):
        self.calls = 0

    async def generate(self, system_prompt, user_message, max_tokens=1000, temperature=0.1):
        self.calls += 1
        return "ok"


class _FailingLLM:
    def __init__(self):
        self.calls = 0

    async def generate(self, system_prompt, user_message, max_tokens=1000, temperature=0.1):
        self.calls += 1
        raise RuntimeError("llm unavailable")


def _make_test_client(db_ok: bool = True, llm=None, db_startup_error: bool = False):
    mock_pool = _make_mock_pool(db_ok=db_ok)
    llm = llm or _FakeLLM()
    with patch.dict("os.environ", _FAKE_ENV):
        get_settings.cache_clear()
        get_settings()  # キャッシュをフェイク環境変数で事前生成
        create_pool = AsyncMock(side_effect=OSError("network is unreachable")) if db_startup_error else AsyncMock(return_value=mock_pool)
        with (
            patch("app.main.asyncpg.create_pool", create_pool),
            patch.object(_main, "_create_llm_client", return_value=llm),
            patch("app.services.embedder.AsyncOpenAI"),
        ):
            with TestClient(app) as client:
                client.app.state.test_llm = llm
                yield client
    for key in ("db_pool", "db_startup_error", "llm_health_status", "llm_health_checked_at", "test_llm"):
        if hasattr(app.state, key):
            delattr(app.state, key)
    get_settings.cache_clear()


@pytest.fixture
def test_client():
    yield from _make_test_client()


@pytest.fixture
def db_error_client():
    yield from _make_test_client(db_ok=False)


@pytest.fixture
def db_startup_error_client():
    yield from _make_test_client(db_startup_error=True)


@pytest.fixture
def llm_error_client():
    yield from _make_test_client(llm=_FailingLLM())
