from fastapi import HTTPException, Request

from app.adapters.vector_store.postgres import PostgreSQLVectorStore
from app.services.rag_service import RAGService


def get_rag_service(request: Request) -> RAGService:
    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database is unavailable.")
    return RAGService(
        embedder=request.app.state.embedder,
        vector_store=PostgreSQLVectorStore(db_pool),
        llm=request.app.state.llm,
    )
