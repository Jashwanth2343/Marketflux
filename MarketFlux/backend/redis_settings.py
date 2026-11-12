"""One Redis connection string for every client.

REDIS_URL is the source of truth and may be a TLS URL (`rediss://`).
REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, and REDIS_DB are only a fallback for
older local .env files. redis-py enables TLS when the scheme is rediss.
"""
from __future__ import annotations

import os
from urllib.parse import quote


def build_redis_url(default_db: str = "0") -> str:
    url = os.getenv("REDIS_URL", "").strip()
    if url:
        return url
    host = os.getenv("REDIS_HOST", "localhost").strip() or "localhost"
    port = os.getenv("REDIS_PORT", "6379").strip() or "6379"
    password = os.getenv("REDIS_PASSWORD", "").strip()
    db = os.getenv("REDIS_DB", default_db).strip() or default_db
    auth = f":{quote(password, safe='')}@" if password else ""
    return f"redis://{auth}{host}:{port}/{db}"


def redis_client_kwargs() -> dict:
    return {
        "decode_responses": True,
        "socket_connect_timeout": 1,
        "socket_timeout": 1,
    }
