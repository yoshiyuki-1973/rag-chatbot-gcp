import logging

from fastapi import HTTPException, status

from app.adapters.llm.base import BaseLLMClient
from app.adapters.vector_store.base import BaseVectorStore
from app.models.schemas import ChatResponse, SearchResponse, SearchResult, Source
from app.services.embedder import EmbeddingClient

SYSTEM_PROMPT = """あなたはスポーツに関する質問に答えるアシスタントです。以下のルールに従ってください。
1. 必ず提供されたコンテキストの情報のみを使用して回答してください。
2. コンテキストは検索で取得された文書の抜粋であり、文書全体ではない場合があります。
3. 質問が広すぎてコンテキスト内の情報だけでは全体像を網羅できない場合は、回答の冒頭で「検索された範囲では」と明記してください。
4. コンテキストに情報がない場合は、「提供された情報の中には該当する情報が見つかりませんでした。」と回答してください。
5. 回答は日本語で行ってください。
6. 推測や創作は行わないでください。
7. 回答の根拠となったドキュメントは別途出典として提示されます。

コンテキスト:
{context}
"""

logger = logging.getLogger(__name__)

TOPIC_KEYWORDS = {
    "サッカー": ("サッカー", "soccer", "football", "fifa", "jfa"),
    "ホッケー": ("ホッケー", "hockey", "fih"),
    "空手": ("空手", "karate", "wkf", "全空連"),
}
MIN_CHAT_SIMILARITY = 0.65
NO_CONTEXT_ANSWER = "提供された情報の中には該当する情報が見つかりませんでした。"


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

        guarded_results = self._apply_chat_guards(query, search_response.results)
        if isinstance(guarded_results, str):
            await self._save_history_safely(
                session_id=session_id,
                query=query,
                answer=guarded_results,
                sources=[],
            )
            return ChatResponse(answer=guarded_results, sources=[], session_id=session_id)

        context = self._build_context(guarded_results)
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
            for result in guarded_results
        ]
        await self._save_history_safely(
            session_id=session_id,
            query=query,
            answer=answer,
            sources=[source.model_dump() for source in sources],
        )
        return ChatResponse(answer=answer, sources=sources, session_id=session_id)

    def _build_context(self, chunks: list[SearchResult]) -> str:
        if not chunks:
            return ""
        return "\n\n---\n\n".join(
            f"[出典: {chunk.title}]\n{chunk.content}" for chunk in chunks
        )

    async def _save_history_safely(
        self,
        session_id: str | None,
        query: str,
        answer: str,
        sources: list[dict],
    ) -> None:
        try:
            await self.vector_store.save_chat_history(
                session_id=session_id,
                query=query,
                response=answer,
                sources=sources,
            )
        except Exception:
            logger.warning("Failed to save chat history", exc_info=True)

    def _apply_chat_guards(
        self,
        query: str,
        results: list[SearchResult],
    ) -> list[SearchResult] | str:
        relevant_results = [
            result for result in results if result.similarity >= MIN_CHAT_SIMILARITY
        ]
        if not relevant_results:
            return NO_CONTEXT_ANSWER

        query_topics = self._detect_query_topics(query)
        if query_topics:
            topic_results = [
                result
                for result in relevant_results
                if self._detect_topics(result) & query_topics
            ]
            if topic_results:
                return topic_results
            topic_list = "、".join(sorted(query_topics))
            return f"{topic_list}に関する情報は、検索された範囲では見つかりませんでした。"

        result_topics = sorted(
            {topic for result in relevant_results for topic in self._detect_topics(result)}
        )
        if len(result_topics) > 1:
            topic_list = "、".join(result_topics)
            return (
                f"検索結果に複数の競技（{topic_list}）が含まれています。"
                "どの競技について知りたいかを指定して質問してください。\n\n"
                "例: 「ホッケーではどんな行為が反則ですか？」"
            )

        return relevant_results

    def _detect_topics(self, result: SearchResult) -> set[str]:
        haystack = " ".join(
            value
            for value in [result.title, result.organization or "", result.source_url]
            if value
        ).lower()
        return {
            topic
            for topic, keywords in TOPIC_KEYWORDS.items()
            if any(keyword.lower() in haystack for keyword in keywords)
        }

    def _detect_query_topics(self, query: str) -> set[str]:
        query_lower = query.lower()
        return {
            topic
            for topic, keywords in TOPIC_KEYWORDS.items()
            if any(keyword.lower() in query_lower for keyword in keywords)
        }
