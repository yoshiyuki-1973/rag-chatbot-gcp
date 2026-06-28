import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

import asyncpg


@dataclass(frozen=True)
class SourceConfig:
    path: str
    title: str
    source_url: str
    file_type: str
    organization: str | None
    authority_score: float
    content_date: str | None


class IngestRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    async def check_ready(self) -> None:
        """DB接続とIngestに必要なテーブルの存在を処理開始前に確認する。"""
        conn = await asyncpg.connect(self.database_url)
        try:
            required_tables = ("documents", "document_chunks")
            missing_tables = []
            for table_name in required_tables:
                relation = await conn.fetchval(
                    "SELECT to_regclass($1)",
                    f"public.{table_name}",
                )
                if relation is None:
                    missing_tables.append(table_name)

            if missing_tables:
                joined_names = ", ".join(missing_tables)
                raise RuntimeError(f"Required database tables are missing: {joined_names}")
        finally:
            await conn.close()

    async def upsert_document_with_chunks(
        self,
        source: SourceConfig,
        chunks: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        token_counts: Sequence[int],
    ) -> str:
        conn = await asyncpg.connect(self.database_url)
        try:
            async with conn.transaction():
                document_id = await conn.fetchval(
                    """
                    INSERT INTO documents (
                        title, source_url, file_type, organization, authority_score, content_date
                    )
                    VALUES ($1, $2, $3, $4, $5, $6::date)
                    ON CONFLICT (source_url)
                    DO UPDATE SET
                        title = EXCLUDED.title,
                        file_type = EXCLUDED.file_type,
                        organization = EXCLUDED.organization,
                        authority_score = EXCLUDED.authority_score,
                        content_date = EXCLUDED.content_date
                    RETURNING id
                    """,
                    source.title,
                    source.source_url,
                    source.file_type,
                    source.organization,
                    source.authority_score,
                    source.content_date,
                )
                await conn.execute("DELETE FROM document_chunks WHERE document_id = $1", document_id)
                await conn.executemany(
                    """
                    INSERT INTO document_chunks (
                        document_id, chunk_index, content, embedding, token_count
                    )
                    VALUES ($1, $2, $3, $4::vector, $5)
                    """,
                    [
                        (
                            document_id,
                            index,
                            chunk,
                            "[" + ",".join(str(value) for value in embedding) + "]",
                            token_counts[index],
                        )
                        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True))
                    ],
                )
                return str(document_id)
        finally:
            await conn.close()


def run_async(coro):
    return asyncio.run(coro)
