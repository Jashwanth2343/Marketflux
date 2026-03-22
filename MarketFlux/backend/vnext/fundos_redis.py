from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

import redis


def _slugify(value: Optional[str], fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in text)


class FundOSRedisClient:
    """Isolated Redis client for Fund OS state.

    Prefers a dedicated FUNDOS_REDIS_URL. If unavailable, falls back to REDIS_URL
    or legacy host/port settings, but every key remains namespaced.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        *,
        host: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        db: Optional[int] = None,
        namespace: str = "fundos",
    ) -> None:
        self.url = (url or os.getenv("FUNDOS_REDIS_URL") or os.getenv("REDIS_URL") or "").strip()
        self.host = host or os.getenv("FUNDOS_REDIS_HOST") or os.getenv("REDIS_HOST", "localhost")
        self.port = int(port or os.getenv("FUNDOS_REDIS_PORT", 6379))
        self.password = password if password is not None else (os.getenv("FUNDOS_REDIS_PASSWORD") or None)
        self.db = int(db if db is not None else os.getenv("FUNDOS_REDIS_DB", 0))
        self.namespace = namespace
        self._client = self._connect()

    def _connect(self) -> Optional[redis.Redis]:
        try:
            if self.url:
                client = redis.Redis.from_url(
                    self.url,
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                )
            else:
                client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    password=self.password,
                    db=self.db,
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                )
            client.ping()
            return client
        except Exception:
            return None

    @property
    def configured(self) -> bool:
        return self._client is not None

    def health(self) -> Dict[str, Any]:
        return {
            "configured": self.configured,
            "namespace": self.namespace,
            "mode": "dedicated" if os.getenv("FUNDOS_REDIS_URL") else "shared",
        }

    def build_key(self, user_id: Optional[str], session_id: Optional[str], *parts: str) -> str:
        base = [
            self.namespace,
            _slugify(user_id, "anon"),
            _slugify(session_id, "global"),
        ]
        base.extend(_slugify(part, "value") for part in parts if part)
        return ":".join(base)

    def _ensure_client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("Fund OS Redis is not configured.")
        return self._client

    def get_json(self, key: str) -> Optional[Any]:
        client = self._ensure_client()
        value = client.get(key)
        if not value:
            return None
        return json.loads(value)

    def set_json(self, key: str, value: Any, *, ttl: Optional[int] = None) -> None:
        client = self._ensure_client()
        encoded = json.dumps(value, default=str)
        if ttl is None:
            client.set(key, encoded)
        else:
            client.setex(key, ttl, encoded)

    def delete(self, key: str) -> None:
        client = self._ensure_client()
        client.delete(key)

    def scan_keys(self, pattern: str) -> List[str]:
        client = self._ensure_client()
        return list(client.scan_iter(match=pattern))

    async def aget_json(self, key: str) -> Optional[Any]:
        return await asyncio.to_thread(self.get_json, key)

    async def aset_json(self, key: str, value: Any, *, ttl: Optional[int] = None) -> None:
        await asyncio.to_thread(self.set_json, key, value, ttl=ttl)

    async def adelete(self, key: str) -> None:
        await asyncio.to_thread(self.delete, key)

    async def ascan_keys(self, pattern: str) -> List[str]:
        return await asyncio.to_thread(self.scan_keys, pattern)
