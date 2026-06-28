import unittest
from unittest.mock import AsyncMock, patch

from db import IngestRepository


class IngestRepositoryReadinessTest(unittest.IsolatedAsyncioTestCase):
    async def test_check_ready_succeeds_when_required_tables_exist(self):
        connection = AsyncMock()
        connection.fetchval.side_effect = ["documents", "document_chunks"]

        with patch("db.asyncpg.connect", AsyncMock(return_value=connection)):
            repository = IngestRepository("postgresql://example")
            await repository.check_ready()

        self.assertEqual(connection.fetchval.await_count, 2)
        connection.close.assert_awaited_once()

    async def test_check_ready_reports_missing_tables(self):
        connection = AsyncMock()
        connection.fetchval.side_effect = ["documents", None]

        with patch("db.asyncpg.connect", AsyncMock(return_value=connection)):
            repository = IngestRepository("postgresql://example")

            with self.assertRaisesRegex(RuntimeError, "document_chunks"):
                await repository.check_ready()

        connection.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
