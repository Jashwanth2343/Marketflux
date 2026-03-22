import os
import asyncpg
import logging

logger = logging.getLogger(__name__)

async def get_pg_connection():
    db_url = os.getenv("FUNDOS_DATABASE_URL")
    if not db_url:
        raise ValueError("FUNDOS_DATABASE_URL environment variable is not set")
    return await asyncpg.connect(db_url)
