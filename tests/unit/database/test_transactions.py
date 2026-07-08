"""Unit tests for backend.shared.database.transactions."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestTransaction:
    @pytest.mark.asyncio
    async def test_commits_on_success(self):
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        from backend.shared.database.transactions import transaction
        async with transaction(mock_pool) as conn:
            assert conn is mock_conn
            await conn.execute("INSERT INTO test VALUES (1)")

        mock_conn.execute.assert_any_call("BEGIN")
        mock_conn.execute.assert_any_call("COMMIT")
        mock_conn.execute.assert_any_call("INSERT INTO test VALUES (1)")

    @pytest.mark.asyncio
    async def test_rolls_back_on_exception(self):
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        from backend.shared.database.transactions import transaction
        with pytest.raises(ValueError, match="test error"):
            async with transaction(mock_pool) as conn:
                raise ValueError("test error")

        mock_conn.execute.assert_any_call("BEGIN")
        mock_conn.execute.assert_any_call("ROLLBACK")
