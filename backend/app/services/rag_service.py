import logging

from fastapi import HTTPException, status

from app.adapters.llm.base import BaseLLMClient
from app.adapters.vector_store.base import BaseVectorStore
from app.models.schemas import ChatResponse, SearchResponse, SearchResult, Source
from app.services.embedder import EmbeddingClient

SYSTEM_PROMPT = """あなたはスポーツに関する質問に答えるアシスタントです。
以下のルールに従ってください。

1. 必ず提供されたコンテキストの情報のみを使用して回答してください。
2. コンテキストに情報がない場合は「提供された情報の中には該当する情報が見つかりませんでした」と回答してください。
3. 回答は日本語で行ってください。
4. 推測や創作は行わないでください。
5. 回答の根拠となったドキュメントは別途出典として提示されます。

コンテキスト:
{context}
"""

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(
        self,
        embedder: EmbeddingClient,
        vector_store: BaseVectorStore,
        llm: BaseLLMClient,
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.llm = llm

    async def search(
        self,
        query: str,
        top_k: int,
        min_similarity: float = 0.0,
        min_authority_score: float = 0.0,
    ) -> SearchResponse:
        query_embedding = await self.embedder.embed(query)
        results = await self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            min_similarity=min_similarity,
            min_authority_score=min_authority_score,
        )
        return SearchResponse(results=results, total=len(results))

    async def chat(self, query: str, session_id: str | None, top_k: int) -> ChatResponse:
        try:
            search_response = await self.search(query=query, top_k=top_k)
        except Exception as exc:
            logger.exception("Vector search failed.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": "SEARCH_ERROR",
                    "message": "ベクトル検索に失敗しました。しばらく後にお試しください。",
                },
            ) from exc
        context = self._build_context(search_response.results)
        try:
            answer = await self.llm.generate(SYSTEM_PROMPT.format(context=context), query)
        except Exception as exc:
            logger.exception("LLM generation failed.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": "LLM_ERROR",
                    "message": "LLM サービスへの接続に失敗しました。しばらく後にお試しください。",
                },
            ) from exc
        sources = [
            Source(
                document_id=result.document_id,
                title=result.title,
                source_url=result.source_url,
                organization=result.organization,
                authority_score=result.authority_score,
                chunk_index=result.chunk_index,
                similarity=result.similarity,
            )
            for result in search_response.results
        ]
        try:
            await self.vector_store.save_chat_history(
                session_id=session_id,
                query=query,
                response=answer,
                sources=[source.model_dump() for source in sources],
            )
        except Exception:
            logger.warning("Failed to save chat history", exc_info=True)
        return ChatResponse(answer=answer, sources=sources, session_id=session_id)

    def _build_context(self, chunks: list[SearchResult]) -> str:
        if not chunks:
            return ""
        return "\n\n---\n\n".join(
            f"[出典: {chunk.title}]\n{chunk.content}" for chunk in chunks
        )
