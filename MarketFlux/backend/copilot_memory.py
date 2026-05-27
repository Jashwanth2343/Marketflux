"""Long-term memory for the Copilot agent — Mem0 over the existing Supabase pgvector.

Mem0 auto-extracts durable facts from each conversation turn (preferences, risk
limits, constraints, theses, goals) and stores them as embeddings in the existing
Supabase Postgres. On each new turn we recall the most *relevant* memories
(semantic search) and inject them into the agent's context, so the copilot stays
continuous across sessions.

Design choices:
- Gemini powers both the embedder and Mem0's extraction LLM (key already present).
- Heavy init (Mem0 build + DB connect) runs in a worker thread so it never blocks
  the event loop. Memory writes are fire-and-forget background tasks so they never
  add latency to the chat response.
- Everything is guarded: if Mem0 / its deps / the DB are unavailable, the copilot
  keeps working — just without long-term recall.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_COLLECTION = "copilot_memories"
_memory = None            # cached Mem0 instance
_init_attempted = False   # so we don't retry a failed init every call
_bg_tasks: set = set()    # keep refs to fire-and-forget add() tasks


def _dsn() -> Optional[str]:
    return os.getenv("SUPABASE_DB_URL") or os.getenv("MARKETFLUX_VNEXT_DATABASE_URL") or os.getenv("FUNDOS_DATABASE_URL")


def _build_config() -> Optional[dict]:
    dsn = _dsn()
    gem = os.getenv("GEMINI_API_KEY")
    if not dsn or not gem:
        return None
    return {
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "connection_string": dsn,
                "collection_name": _COLLECTION,
                "embedding_model_dims": 768,
                "hnsw": True,
            },
        },
        "llm": {
            "provider": "gemini",
            "config": {"model": "gemini-2.5-flash", "api_key": gem, "temperature": 0.1},
        },
        "embedder": {
            "provider": "gemini",
            "config": {"model": "models/gemini-embedding-001", "embedding_dims": 768, "api_key": gem},
        },
    }


def _get_memory_sync():
    """Build (once) and return the Mem0 instance, or None if unavailable. Heavy."""
    global _memory, _init_attempted
    if _memory is not None or _init_attempted:
        return _memory
    _init_attempted = True
    cfg = _build_config()
    if not cfg:
        logger.info("copilot memory disabled (missing Supabase DSN or GEMINI_API_KEY)")
        return None
    try:
        from mem0 import Memory
        _memory = Memory.from_config(cfg)
        logger.info("copilot Mem0 memory ready (pgvector/%s)", _COLLECTION)
    except Exception as exc:
        logger.error("copilot Mem0 init failed; memory disabled: %s", exc)
        _memory = None
    return _memory


async def _memory_async():
    return await asyncio.to_thread(_get_memory_sync)


def _normalize(res: Any) -> List[Dict[str, Any]]:
    if isinstance(res, dict):
        res = res.get("results", [])
    out = []
    for r in res or []:
        if not isinstance(r, dict):
            continue
        out.append({
            "id": r.get("id"),
            "memory": r.get("memory") or r.get("text") or r.get("data") or "",
            "category": (r.get("metadata") or {}).get("category"),
            "score": r.get("score"),
            "created_at": r.get("created_at"),
        })
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def is_enabled() -> bool:
    return (await _memory_async()) is not None


async def recall(user_id: str, query: str, limit: int = 6) -> List[Dict[str, Any]]:
    mem = await _memory_async()
    if not mem or not (query or "").strip():
        return []
    try:
        res = await asyncio.to_thread(lambda: mem.search(query=query, filters={"user_id": user_id}, top_k=limit))
        return _normalize(res)
    except Exception as exc:
        logger.warning("memory recall failed: %s", exc)
        return []


async def get_all(user_id: str) -> List[Dict[str, Any]]:
    mem = await _memory_async()
    if not mem:
        return []
    try:
        res = await asyncio.to_thread(lambda: mem.get_all(filters={"user_id": user_id}, top_k=100))
        return _normalize(res)
    except Exception as exc:
        logger.warning("memory get_all failed: %s", exc)
        return []


async def add_turn(user_id: str, user_message: str, assistant_message: str) -> None:
    mem = await _memory_async()
    if not mem:
        return
    messages = [
        {"role": "user", "content": (user_message or "")[:4000]},
        {"role": "assistant", "content": (assistant_message or "")[:4000]},
    ]
    try:
        await asyncio.to_thread(lambda: mem.add(messages, user_id=user_id))
    except Exception as exc:
        logger.warning("memory add failed: %s", exc)


def schedule_add_turn(user_id: str, user_message: str, assistant_message: str) -> None:
    """Fire-and-forget memory write — never blocks the chat response."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(add_turn(user_id, user_message, assistant_message))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


async def delete(user_id: str, mem_id: str) -> bool:
    mem = await _memory_async()
    if not mem:
        return False
    try:
        await asyncio.to_thread(lambda: mem.delete(memory_id=mem_id))
        return True
    except Exception as exc:
        logger.warning("memory delete failed: %s", exc)
        return False


async def delete_all(user_id: str) -> bool:
    mem = await _memory_async()
    if not mem:
        return False
    try:
        await asyncio.to_thread(lambda: mem.delete_all(user_id=user_id))
        return True
    except Exception as exc:
        logger.warning("memory delete_all failed: %s", exc)
        return False


async def memory_context_block(user_id: str, query: str) -> str:
    """Relevant memories rendered as a prompt block for the agent, or ''."""
    mems = await recall(user_id, query, limit=6)
    texts = [m["memory"] for m in mems if m.get("memory")]
    if not texts:
        return ""
    lines = ["=== RELEVANT LONG-TERM MEMORY ABOUT THIS USER ==="]
    lines += [f"- {t}" for t in texts]
    lines.append("Honor these preferences/constraints when researching and sizing trades.")
    return "\n".join(lines)
