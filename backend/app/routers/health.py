import asyncio
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)

LLM_HEALTH_CACHE_TTL_SECONDS = 30
LLM_HEALTH_TIMEOUT_SECONDS = 2


@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    database_status = "degraded"
    pool = getattr(request.app.state, "db_pool", None)
    if getattr(request.app.state, "db_startup_error", None):
        database_status = "error"
    elif pool is not None:
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            database_status = "ok"
        except Exception:
            database_status = "error"
    llm_status = "degraded"
    llm = getattr(request.app.state, "llm", None)
    if llm is not None:
        now = time.monotonic()
        cached_at = getattr(request.app.state, "llm_health_checked_at", 0.0)
        cached_status = getattr(request.app.state, "llm_health_status", None)
        if cached_status is not None and now - cached_at <= LLM_HEALTH_CACHE_TTL_SECONDS:
            llm_status = cached_status
        else:
            try:
                await asyncio.wait_for(
                    llm.generate("Return ok.", "ping", max_tokens=1, temperature=0.0),
                    timeout=LLM_HEALTH_TIMEOUT_SECONDS,
                )
                llm_status = "ok"
                request.app.state.llm_health_status = llm_status
                request.app.state.llm_health_checked_at = now
            except Exception:
                logger.exception("LLM health check failed.")
                llm_status = "error"
    services = {
        "database": database_status,
        "llm": llm_status,
    }
    values = list(services.values())
    if any(v == "error" for v in values):
        overall = "error"
    elif all(v == "ok" for v in values):
        overall = "ok"
    else:
        overall = "degraded"
    response_body = HealthResponse(status=overall, version="0.1.0", services=services)
    if overall == "error":
        return JSONResponse(status_code=503, content=response_body.model_dump())
    return response_body
