import logging
import os
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

_POOL: Optional[asyncpg.Pool] = None


def get_pg_dsn() -> Optional[str]:
    return os.getenv("MARKETFLUX_VNEXT_DATABASE_URL") or os.getenv("FUNDOS_DATABASE_URL")


def is_pg_configured() -> bool:
    return bool(get_pg_dsn())


class PooledConnection:
    def __init__(self, pool: asyncpg.Pool, connection: asyncpg.Connection):
        self._pool = pool
        self._connection = connection
        self._released = False

    def __getattr__(self, item):
        return getattr(self._connection, item)

    async def close(self):
        if not self._released:
            await self._pool.release(self._connection)
            self._released = True


async def get_pg_pool() -> asyncpg.Pool:
    global _POOL

    if _POOL is not None:
        return _POOL

    db_url = get_pg_dsn()
    if not db_url:
        raise ValueError("MARKETFLUX_VNEXT_DATABASE_URL or FUNDOS_DATABASE_URL must be set")

    _POOL = await asyncpg.create_pool(db_url, min_size=1, max_size=5)
    logger.info("Initialized shared Postgres pool for vNext/FundOS services.")
    return _POOL


async def get_pg_connection() -> PooledConnection:
    pool = await get_pg_pool()
    connection = await pool.acquire()
    return PooledConnection(pool, connection)


async def close_pg_pool() -> None:
    global _POOL

    if _POOL is not None:
        await _POOL.close()
        _POOL = None
        logger.info("Closed shared Postgres pool.")
