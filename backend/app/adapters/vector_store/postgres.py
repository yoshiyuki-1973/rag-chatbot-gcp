import json

import asyncpg

from app.adapters.vector_store.base import BaseVectorStore
from app.models.schemas import SearchResult


class PostgreSQLVectorStore(BaseVectorStore):
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def search(
        self,
        query_embedding: list[float],
        top_k: int,
        min_similarity: float = 0.0,
        min_authority_score: float = 0.0,
    ) -> list[SearchResult]:
        vector_literal = "[" + ",".join(str(value) for value in query_embedding) + "]"
        # 内側クエリで IVFFlat インデックスを活用（ORDER BY ... LIMIT パターン）し、
        # コサイン距離は一度だけ評価する。min_similarity フィルターは外側で適用する。
        sql = """
            SELECT *
            FROM (
                SELECT
                    c.document_id::text AS document_id,
                    c.chunk_index,
                    c.content,
                    1 - (c.embedding <=> $1::vector) AS similarity,
                    d.title,
                    d.source_url,
                    d.organization,
                    d.authority_score::float AS authority_score
                FROM document_chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE c.embedding IS NOT NULL
                  AND d.authority_score >= $3
                ORDER BY c.embedding <=> $1::vector
                LIMIT $2
            ) ranked
            WHERE ranked.similarity >= $4
            ORDER BY ranked.similarity DESC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, vector_literal, top_k, min_authority_score, min_similarity)
        return [SearchResult(**dict(row)) for row in rows]

    async def save_chat_history(
        self,
        session_id: str | None,
        query: str,
        response: str,
        sources: list[dict],
    ) -> None:
        if not session_id:
            return
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_history (session_id, query, response, sources)
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                session_id,
                query,
                response,
                json.dumps(sources, ensure_ascii=False),
            )
