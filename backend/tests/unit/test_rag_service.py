import pytest
from fastapi import HTTPException

from app.models.schemas import SearchResult
from app.services.rag_service import NO_CONTEXT_ANSWER, RAGService


class FakeEmbedder:
    async def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


def _make_result(
    title: str = "FIFA サッカー競技規則",
    content: str = "オフサイドに関する説明",
    organization: str = "FIFA",
    source_url: str = "https://example.com/rules.pdf",
    similarity: float = 0.88,
) -> SearchResult:
    return SearchResult(
        document_id="550e8400-e29b-41d4-a716-446655440001",
        title=title,
        source_url=source_url,
        organization=organization,
        authority_score=0.95,
        chunk_index=2,
        similarity=similarity,
        content=content,
    )


class FakeVectorStore:
    def __init__(self, results: list[SearchResult] | None = None):
        self.results: list[SearchResult] = results if results is not None else [_make_result()]
        self.last_top_k: int | None = None
        self.saved: dict | None = None

    async def search(
        self, query_embedding, top_k, min_similarity=0.0, min_authority_score=0.0
    ) -> list[SearchResult]:
        self.last_top_k = top_k
        return self.results

    async def save_chat_history(self, session_id, query, response, sources) -> None:
        self.saved = {
            "session_id": session_id,
            "query": query,
            "response": response,
            "sources": sources,
        }


class FailingHistoryVectorStore(FakeVectorStore):
    async def save_chat_history(self, session_id, query, response, sources) -> None:
        raise RuntimeError("history failed")


class FakeLLM:
    """呼び出し引数を記録するフェイク LLM。"""

    def __init__(self, return_value: str = "コンテキストに基づく回答です。"):
        self.last_system_prompt = ""
        self.last_user_message = ""
        self.return_value = return_value

    async def generate(
        self, system_prompt: str, user_message: str, max_tokens: int = 1000, temperature: float = 0.1
    ) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_message = user_message
        return self.return_value


class FailingEmbedder:
    async def embed(self, text: str) -> list[float]:
        raise RuntimeError("embedding failed")


class FailingLLM:
    async def generate(
        self, system_prompt: str, user_message: str, max_tokens: int = 1000, temperature: float = 0.1
    ) -> str:
        raise RuntimeError("llm failed")


@pytest.mark.asyncio
async def test_chat_returns_answer_and_sources():
    vector_store = FakeVectorStore()
    llm = FakeLLM()
    service = RAGService(FakeEmbedder(), vector_store, llm)

    response = await service.chat("オフサイドとは？", "session-1", 5)

    assert response.answer == "コンテキストに基づく回答です。"
    assert response.session_id == "session-1"
    assert response.sources[0].title == "FIFA サッカー競技規則"
    assert vector_store.saved["session_id"] == "session-1"
    assert "オフサイドに関する説明" in llm.last_system_prompt
    assert llm.last_user_message == "オフサイドとは？"


@pytest.mark.asyncio
async def test_chat_returns_answer_when_history_save_fails():
    service = RAGService(FakeEmbedder(), FailingHistoryVectorStore(), FakeLLM())

    response = await service.chat("オフサイドとは？", "session-1", 5)

    assert response.answer == "コンテキストに基づく回答です。"
    assert response.sources[0].title == "FIFA サッカー競技規則"


@pytest.mark.asyncio
async def test_chat_wraps_search_errors():
    service = RAGService(FailingEmbedder(), FakeVectorStore(), FakeLLM())

    with pytest.raises(HTTPException) as exc_info:
        await service.chat("オフサイドとは？", "session-1", 5)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail["code"] == "SEARCH_ERROR"


@pytest.mark.asyncio
async def test_chat_wraps_llm_errors():
    service = RAGService(FakeEmbedder(), FakeVectorStore(), FailingLLM())

    with pytest.raises(HTTPException) as exc_info:
        await service.chat("オフサイドとは？", "session-1", 5)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail["code"] == "LLM_ERROR"


@pytest.mark.asyncio
async def test_chat_empty_search_results_returns_fixed_message_without_llm():
    vector_store = FakeVectorStore(results=[])
    llm = FakeLLM()
    service = RAGService(FakeEmbedder(), vector_store, llm)

    response = await service.chat("存在しない質問", "session-1", 5)

    assert response.answer == NO_CONTEXT_ANSWER
    assert response.sources == []
    assert llm.last_user_message == ""
    assert vector_store.saved["response"] == NO_CONTEXT_ANSWER


@pytest.mark.asyncio
async def test_chat_passes_top_k_to_vector_store():
    vector_store = FakeVectorStore()
    service = RAGService(FakeEmbedder(), vector_store, FakeLLM())

    await service.chat("オフサイドとは？", None, top_k=3)

    assert vector_store.last_top_k == 3


@pytest.mark.asyncio
async def test_chat_builds_context_from_multiple_chunks():
    results = [
        _make_result(title="ドキュメントA", content="Aの内容"),
        _make_result(title="ドキュメントB", content="Bの内容"),
    ]
    vector_store = FakeVectorStore(results=results)
    llm = FakeLLM()
    service = RAGService(FakeEmbedder(), vector_store, llm)

    await service.chat("テスト質問", "session-1", 5)

    assert "Aの内容" in llm.last_system_prompt
    assert "Bの内容" in llm.last_system_prompt
    assert "ドキュメントA" in llm.last_system_prompt
    assert "ドキュメントB" in llm.last_system_prompt


@pytest.mark.asyncio
async def test_chat_asks_for_topic_when_multiple_sports_match_ambiguous_query():
    results = [
        _make_result(
            title="FIH Rules of Hockey 2026",
            organization="FIH",
            source_url="local://FIH_Rules_of_Hockey_2026_EN.pdf",
            content="Players must not obstruct an opponent.",
        ),
        _make_result(
            title="全空連 競技規定変更概要 2026",
            organization="全空連",
            source_url="local://全空連_競技規定変更概要_2026.pdf",
            content="反則注意からの累積による反則。",
        ),
    ]
    vector_store = FakeVectorStore(results=results)
    llm = FakeLLM()
    service = RAGService(FakeEmbedder(), vector_store, llm)

    response = await service.chat("どんな行為が反則？", "session-1", 10)

    assert "複数の競技" in response.answer
    assert "ホッケー" in response.answer
    assert "空手" in response.answer
    assert response.sources == []
    assert llm.last_user_message == ""
    assert vector_store.saved["response"] == response.answer


@pytest.mark.asyncio
async def test_chat_answers_when_topic_is_specified_even_if_multiple_sports_match():
    results = [
        _make_result(
            title="FIH Rules of Hockey 2026",
            organization="FIH",
            source_url="local://FIH_Rules_of_Hockey_2026_EN.pdf",
            content="Players must not obstruct an opponent.",
        ),
        _make_result(
            title="全空連 競技規定変更概要 2026",
            organization="全空連",
            source_url="local://全空連_競技規定変更概要_2026.pdf",
            content="反則注意からの累積による反則。",
        ),
    ]
    llm = FakeLLM(return_value="検索された範囲では、ホッケーの反則は...。")
    service = RAGService(FakeEmbedder(), FakeVectorStore(results=results), llm)

    response = await service.chat("ホッケーではどんな行為が反則？", "session-1", 10)

    assert response.answer == "検索された範囲では、ホッケーの反則は...。"
    assert len(response.sources) == 1
    assert response.sources[0].title == "FIH Rules of Hockey 2026"
    assert llm.last_user_message == "ホッケーではどんな行為が反則？"
    assert "全空連" not in llm.last_system_prompt


@pytest.mark.asyncio
async def test_chat_returns_topic_no_context_when_specified_topic_has_no_match():
    results = [
        _make_result(
            title="FIH Rules of Hockey 2026",
            organization="FIH",
            source_url="local://FIH_Rules_of_Hockey_2026_EN.pdf",
            content="Players must not obstruct an opponent.",
        )
    ]
    llm = FakeLLM()
    service = RAGService(FakeEmbedder(), FakeVectorStore(results=results), llm)

    response = await service.chat("空手ではどんな行為が反則？", "session-1", 10)

    assert response.answer == "空手に関する情報は、検索された範囲では見つかりませんでした。"
    assert response.sources == []
    assert llm.last_user_message == ""


@pytest.mark.asyncio
async def test_chat_returns_fixed_message_without_llm_when_similarity_is_too_low():
    result = _make_result(similarity=0.2)
    llm = FakeLLM()
    service = RAGService(FakeEmbedder(), FakeVectorStore(results=[result]), llm)

    response = await service.chat("ホッケーではどんな行為が反則？", "session-1", 10)

    assert response.answer == NO_CONTEXT_ANSWER
    assert response.sources == []
    assert llm.last_user_message == ""
