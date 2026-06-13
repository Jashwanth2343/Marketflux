"""Persistence for the copilot trust path: pending trades, chat history, trade log.

Supabase Postgres is the primary store (DSN from SUPABASE_DB_URL /
MARKETFLUX_VNEXT_DATABASE_URL / FUNDOS_DATABASE_URL). The legacy Mongo handle
is used only when no Postgres DSN is configured; that path exists for
not-yet-migrated local setups and is slated for deletion.

Every function takes the Mongo ``db`` handle as its first argument purely for
the fallback — callers don't choose the backend, this module does.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from vnext.fundos_pg_client import get_pg_pool, is_pg_configured

logger = logging.getLogger(__name__)

_MONGO_PENDING = "copilot_pending_trades"
_SCHEMA_APPLIED = False


def _jsonb(value: Any) -> str:
    return json.dumps(value or {}, default=str)


def _loadj(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


async def ensure_schema() -> None:
    """Apply the copilot Postgres schema once per process (idempotent SQL)."""
    global _SCHEMA_APPLIED
    if _SCHEMA_APPLIED or not is_pg_configured():
        return
    sql = (Path(__file__).parent / "sql" / "copilot_core_schema.sql").read_text()
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(sql)
    _SCHEMA_APPLIED = True
    logger.info("copilot_store: Postgres schema ensured")


# ---------------------------------------------------------------------------
# Pending trades
# ---------------------------------------------------------------------------
async def insert_pending(db, doc: Dict[str, Any]) -> None:
    if is_pg_configured():
        await ensure_schema()
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO copilot_pending_trades (id, user_id, tool, args, preview, status, created_at)
                   VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, $7)""",
                doc["id"], doc["user_id"], doc["tool"], _jsonb(doc.get("args")),
                _jsonb(doc.get("preview")), doc.get("status", "pending"), doc["created_at"],
            )
        return
    await db[_MONGO_PENDING].insert_one(doc)


async def claim_pending(db, user_id: str, pid: str, cutoff: datetime) -> Optional[Dict[str, Any]]:
    """Atomically transition pending → executing. Returns the claimed doc or None."""
    if is_pg_configured():
        await ensure_schema()
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """UPDATE copilot_pending_trades SET status = 'executing'
                   WHERE id = $1::uuid AND user_id = $2 AND status = 'pending' AND created_at >= $3
                   RETURNING id, tool, args, preview, created_at""",
                pid, user_id, cutoff,
            )
        if not row:
            return None
        return {"id": str(row["id"]), "tool": row["tool"], "args": _loadj(row["args"]),
                "preview": _loadj(row["preview"]), "created_at": row["created_at"]}
    return await db[_MONGO_PENDING].find_one_and_update(
        {"id": pid, "user_id": user_id, "status": "pending", "created_at": {"$gte": cutoff}},
        {"$set": {"status": "executing"}},
        return_document=True,
    )


async def get_pending_meta(db, user_id: str, pid: str) -> Optional[Dict[str, Any]]:
    """Status + created_at for a proposal — used to explain why a claim failed."""
    if is_pg_configured():
        await ensure_schema()
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status, created_at FROM copilot_pending_trades WHERE id = $1::uuid AND user_id = $2",
                pid, user_id,
            )
        return {"status": row["status"], "created_at": row["created_at"]} if row else None
    return await db[_MONGO_PENDING].find_one(
        {"id": pid, "user_id": user_id}, {"status": 1, "created_at": 1})


async def set_pending_result(db, pid: str, status: str, result: Dict[str, Any]) -> None:
    now = datetime.now(timezone.utc)
    if is_pg_configured():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE copilot_pending_trades
                   SET status = $2, result = $3::jsonb, executed_at = $4 WHERE id = $1::uuid""",
                pid, status, _jsonb(result), now,
            )
        return
    await db[_MONGO_PENDING].update_one(
        {"id": pid},
        {"$set": {"status": status, "result": result, "executed_at": now.isoformat()}})


async def mark_rejected(db, user_id: str, pid: str) -> bool:
    if is_pg_configured():
        await ensure_schema()
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            tag = await conn.execute(
                """UPDATE copilot_pending_trades SET status = 'rejected', executed_at = now()
                   WHERE id = $1::uuid AND user_id = $2 AND status = 'pending'""",
                pid, user_id,
            )
        return tag.endswith("1")
    res = await db[_MONGO_PENDING].update_one(
        {"id": pid, "user_id": user_id, "status": "pending"},
        {"$set": {"status": "rejected", "rejected_at": datetime.now(timezone.utc).isoformat()}})
    return res.modified_count > 0


async def list_pending(db, user_id: str) -> List[Dict[str, Any]]:
    """Unexpired staged trades, oldest first — feeds the UI rehydrate."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    if is_pg_configured():
        await ensure_schema()
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, user_id, tool, args, preview, status, created_at
                   FROM copilot_pending_trades
                   WHERE user_id = $1 AND status = 'pending' AND created_at >= $2
                   ORDER BY created_at ASC LIMIT 50""",
                user_id, cutoff,
            )
        return [{"id": str(r["id"]), "user_id": r["user_id"], "tool": r["tool"],
                 "args": _loadj(r["args"]), "preview": _loadj(r["preview"]),
                 "status": r["status"], "created_at": r["created_at"].isoformat()} for r in rows]
    return await db[_MONGO_PENDING].find(
        {"user_id": user_id, "status": "pending", "created_at": {"$gte": cutoff}}, {"_id": 0}
    ).sort("created_at", 1).to_list(50)


# ---------------------------------------------------------------------------
# Chat history + budget
# ---------------------------------------------------------------------------
async def insert_message(db, user_id: str, session_id: str, message: str, response: str) -> None:
    if is_pg_configured():
        await ensure_schema()
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO copilot_messages (user_id, session_id, message, response) VALUES ($1, $2, $3, $4)",
                user_id, session_id, message, response)
        return
    await db.copilot_messages.insert_one({
        "user_id": user_id, "session_id": session_id, "message": message,
        "response": response, "created_at": datetime.now(timezone.utc)})


async def count_turns_today(db, user_id: str) -> int:
    midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if is_pg_configured():
        await ensure_schema()
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT count(*) FROM copilot_messages WHERE user_id = $1 AND created_at >= $2",
                user_id, midnight)
    return await db.copilot_messages.count_documents(
        {"user_id": user_id, "created_at": {"$gte": midnight}})


async def recent_history(db, user_id: str, session_id: str, limit: int = 8) -> List[Dict[str, str]]:
    """Last N turns of this session, oldest first."""
    if is_pg_configured():
        await ensure_schema()
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT message, response FROM copilot_messages
                   WHERE user_id = $1 AND session_id = $2
                   ORDER BY created_at DESC LIMIT $3""",
                user_id, session_id, limit)
        return [{"message": r["message"], "response": r["response"]} for r in reversed(rows)]
    history = await db.copilot_messages.find(
        {"user_id": user_id, "session_id": session_id}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    history.reverse()
    return history


# ---------------------------------------------------------------------------
# Trade log
# ---------------------------------------------------------------------------
async def recent_trades(db, user_id: str, limit: int = 25) -> List[Dict[str, Any]]:
    """Most recent executed-trade log entries, newest first."""
    limit = min(limit, 100)
    if is_pg_configured():
        await ensure_schema()
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT ts, payload FROM copilot_trade_log WHERE user_id = $1 ORDER BY ts DESC LIMIT $2",
                user_id, limit)
        return [{"user_id": user_id, "timestamp": r["ts"].isoformat(), **_loadj(r["payload"])} for r in rows]
    return await db.copilot_trade_log.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)


async def log_trade(db, user_id: str, payload: Dict[str, Any]) -> None:
    if is_pg_configured():
        await ensure_schema()
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO copilot_trade_log (user_id, payload) VALUES ($1, $2::jsonb)",
                user_id, _jsonb(payload))
        return
    await db.copilot_trade_log.insert_one({
        "user_id": user_id, "timestamp": datetime.now(timezone.utc).isoformat(), **payload})
