from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import get_settings


settings = get_settings()

pool = AsyncConnectionPool(
    conninfo=settings.database_url,
    min_size=1,
    max_size=10,
    kwargs={"row_factory": dict_row},
    open=False,
)


async def open_pool() -> None:
    await pool.open()
    await pool.wait()


async def close_pool() -> None:
    await pool.close()


@asynccontextmanager
async def connection() -> AsyncIterator:
    async with pool.connection() as conn:
        yield conn
