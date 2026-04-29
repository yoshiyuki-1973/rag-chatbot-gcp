from contextlib import asynccontextmanager
import logging

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.llm.base import BaseLLMClient
from app.adapters.llm.grok import GrokLLMClient
from app.routers import chat, health, search
from app.services.embedder import EmbeddingClient
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def _create_llm_client(settings: Settings) -> BaseLLMClient:
    """LLM_PROVIDER 設定に基づいて LLM クライアントを生成するファクトリ。
    新しいプロバイダーを追加する場合はここに elif を追加し、対応する Adapter を実装する。"""
    if settings.llm_provider == "grok":
        return GrokLLMClient(settings.grok_api_key, settings.grok_model)
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {settings.llm_provider!r}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    missing = []
    if not settings.database_url:
        missing.append("DATABASE_URL")
    if not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if not settings.grok_api_key:
        missing.append("GROK_API_KEY")
    if missing:
        raise RuntimeError("Required environment variables are missing: " + ", ".join(missing))
    if settings.db_pool_min_size > settings.db_pool_max_size:
        raise RuntimeError("DB_POOL_MIN_SIZE must be less than or equal to DB_POOL_MAX_SIZE")
    try:
        app.state.db_pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
        )
        app.state.db_startup_error = None
    except Exception as exc:
        app.state.db_pool = None
        app.state.db_startup_error = str(exc)
        logger.exception("Database connection pool initialization failed.")
    try:
        app.state.embedder = EmbeddingClient(settings.openai_api_key)
        app.state.llm = _create_llm_client(settings)
        app.state.llm_health_status = None
        app.state.llm_health_checked_at = 0.0
        yield
    finally:
        if app.state.db_pool is not None:
            await app.state.db_pool.close()


app = FastAPI(title="スポーツルールRAGチャットボット API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(search.router)
