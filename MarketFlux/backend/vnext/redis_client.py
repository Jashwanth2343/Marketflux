import redis.asyncio as redis
from typing import Optional, Any
import json

from redis_settings import build_redis_url, redis_client_kwargs

class FundOSRedisClient:
    def __init__(self):
        self.r = redis.from_url(build_redis_url("0"), **redis_client_kwargs())

    def _namespace(self, user_id: str, session_id: str, key: str) -> str:
        return f"fundos:{user_id}:{session_id}:{key}"

    async def get(self, user_id: str, session_id: str, key: str) -> Optional[Any]:
        ns_key = self._namespace(user_id, session_id, key)
        val = await self.r.get(ns_key)
        if val:
            try:
                return json.loads(val)
            except (TypeError, ValueError):
                return val
        return None

    async def set(self, user_id: str, session_id: str, key: str, value: Any, ex: int = 3600):
        ns_key = self._namespace(user_id, session_id, key)
        val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        await self.r.set(ns_key, val_str, ex=ex)

    async def delete(self, user_id: str, session_id: str, key: str):
        ns_key = self._namespace(user_id, session_id, key)
        await self.r.delete(ns_key)

fundos_redis = FundOSRedisClient()
