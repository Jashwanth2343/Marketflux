"""Pilot Memory Agent: layered institutional knowledge for the AI trading copilot.

Architecture:
  HOT layer  — Redis (TTL-based, sub-second reads, regime context, intraday signals)
  WARM layer — Supabase Postgres + pgvector (trade outcomes, patterns, 30d decay)
  COLD layer — Supabase Postgres + pgvector (permanent lessons, user notes)

Retrieval uses pgvector semantic similarity when embeddings are available,
with exponential decay scoring as a fallback/boost factor.

Falls back gracefully to MongoDB if Supabase is not configured (transition period).
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

HOT_TTL_SECONDS = 86400      # 24h
WARM_TTL_SECONDS = 2592000   # 30d

# Memory categories
CATEGORY_TRADE_OUTCOME = "trade_outcome"
CATEGORY_REGIME_CONTEXT = "regime_context"
CATEGORY_LESSON_LEARNED = "lesson_learned"
CATEGORY_USER_NOTE = "user_note"
CATEGORY_REFLECTION = "reflection"
CATEGORY_PATTERN = "pattern"
CATEGORY_DEBATE_INSIGHT = "debate_insight"


# ---------------------------------------------------------------------------
# Redis connection (hot layer)
# ---------------------------------------------------------------------------

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        password = os.getenv("REDIS_PASSWORD") or None
        _redis_client = redis.Redis(host=host, port=port, password=password, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception as exc:
        logger.debug(f"Redis unavailable, hot memory will fall back to Supabase: {exc}")
        return None


def _hot_key(personality_id: str, user_id: str, category: str, entry_id: str) -> str:
    return f"pilot:memory:hot:{user_id}:{personality_id}:{category}:{entry_id}"


def _hot_index_key(personality_id: str, user_id: str) -> str:
    return f"pilot:memory:hot:idx:{user_id}:{personality_id}"


# ---------------------------------------------------------------------------
# Supabase connection (warm/cold layers)
# ---------------------------------------------------------------------------

def _get_supabase():
    try:
        from vnext.supabase_client import get_service_client, is_supabase_configured
        if not is_supabase_configured():
            return None
        return get_service_client()
    except Exception:
        return None


async def _generate_embedding(text: str) -> Optional[List[float]]:
    try:
        from vnext.supabase_client import generate_embedding
        return await generate_embedding(text)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

async def record_trade_outcome(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
    ticker: str,
    side: str,
    entry_price: float,
    exit_price: Optional[float] = None,
    pnl: Optional[float] = None,
    pnl_pct: Optional[float] = None,
    thesis: str = "",
    outcome_notes: str = "",
    regime_at_entry: Optional[str] = None,
    conviction: int = 0,
) -> str:
    """Record a completed trade into WARM memory."""
    won = (pnl or 0) > 0
    importance = min(1.0, 0.4 + abs(pnl_pct or 0) * 2) if pnl_pct else 0.5

    content = (
        f"{'WIN' if won else 'LOSS'} {side.upper()} {ticker} | "
        f"Entry ${entry_price:.2f}"
        f"{f' Exit ${exit_price:.2f}' if exit_price else ''}"
        f"{f' PnL {pnl_pct*100:+.1f}%' if pnl_pct else ''}"
        f"{f' | Regime: {regime_at_entry}' if regime_at_entry else ''}"
        f"{f' | Thesis: {thesis[:200]}' if thesis else ''}"
        f"{f' | Notes: {outcome_notes[:300]}' if outcome_notes else ''}"
    )

    metadata = {
        "side": side,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "won": won,
        "regime_at_entry": regime_at_entry,
        "conviction": conviction,
    }

    return await _store_memory(
        db=db,
        user_id=user_id,
        personality_id=personality_id,
        layer="warm",
        category=CATEGORY_TRADE_OUTCOME,
        ticker=ticker,
        content=content,
        importance=importance,
        metadata=metadata,
    )


async def record_regime_context(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
    regime_label: str,
    details: str = "",
    tickers_affected: Optional[List[str]] = None,
) -> str:
    """Record a market regime observation into HOT memory (Redis)."""
    content = f"REGIME: {regime_label} | {details}"
    metadata = {"regime_label": regime_label, "tickers_affected": tickers_affected or []}

    return await _store_hot(
        user_id=user_id,
        personality_id=personality_id,
        category=CATEGORY_REGIME_CONTEXT,
        content=content,
        importance=0.7,
        metadata=metadata,
        db=db,
    )


async def record_lesson(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
    lesson: str,
    ticker: Optional[str] = None,
    source: str = "reflection",
) -> str:
    """Persist a permanent lesson into COLD memory."""
    return await _store_memory(
        db=db,
        user_id=user_id,
        personality_id=personality_id,
        layer="cold",
        category=CATEGORY_LESSON_LEARNED,
        ticker=ticker,
        content=lesson,
        importance=0.8,
        metadata={"source": source},
    )


async def record_user_note(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
    note: str,
    ticker: Optional[str] = None,
) -> str:
    """User-documented error or observation → COLD memory."""
    return await _store_memory(
        db=db,
        user_id=user_id,
        personality_id=personality_id,
        layer="cold",
        category=CATEGORY_USER_NOTE,
        ticker=ticker,
        content=note,
        importance=0.9,
        metadata={},
    )


async def record_reflection(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
    reflection: str,
    tickers: Optional[List[str]] = None,
) -> str:
    """Post-trade reflection → WARM memory."""
    return await _store_memory(
        db=db,
        user_id=user_id,
        personality_id=personality_id,
        layer="warm",
        category=CATEGORY_REFLECTION,
        content=reflection,
        importance=0.6,
        metadata={"tickers": tickers or []},
    )


async def record_debate_insight(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
    ticker: str,
    insight: str,
    conviction: int = 0,
    verdict: str = "",
) -> str:
    """Key takeaway from an adversarial swarm debate → WARM memory."""
    content = f"{verdict.upper()} {ticker} (conv={conviction}): {insight[:500]}"
    return await _store_memory(
        db=db,
        user_id=user_id,
        personality_id=personality_id,
        layer="warm",
        category=CATEGORY_DEBATE_INSIGHT,
        ticker=ticker,
        content=content,
        importance=min(1.0, 0.3 + conviction * 0.07),
        metadata={"conviction": conviction, "verdict": verdict},
    )


# ---------------------------------------------------------------------------
# Read / retrieval
# ---------------------------------------------------------------------------

async def retrieve_context(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
    ticker: Optional[str] = None,
    categories: Optional[List[str]] = None,
    query_text: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Retrieve relevant memories across all layers.

    Uses pgvector semantic search when query_text is provided and embeddings exist.
    Falls back to recency * importance scoring.
    """
    results: List[Dict[str, Any]] = []

    # 1. Hot layer (Redis)
    hot_entries = await _retrieve_hot(user_id=user_id, personality_id=personality_id, limit=limit)
    for entry in hot_entries:
        if ticker and entry.get("ticker") and entry["ticker"] != ticker:
            continue
        if categories and entry.get("category") not in categories:
            continue
        results.append(entry)

    # 2. Warm + Cold layers (Supabase pgvector or MongoDB fallback)
    supabase = _get_supabase()
    if supabase:
        query_embedding = None
        if query_text:
            query_embedding = await _generate_embedding(query_text)

        try:
            rpc_result = supabase.rpc("retrieve_memory", {
                "p_user_id": user_id,
                "p_personality_id": personality_id,
                "p_query_embedding": query_embedding,
                "p_ticker": ticker,
                "p_categories": categories,
                "p_limit": limit,
            }).execute()
            for row in (rpc_result.data or []):
                results.append(row)
        except Exception as exc:
            logger.warning(f"Supabase retrieve_memory failed, trying simple query: {exc}")
            results.extend(await _retrieve_supabase_simple(
                supabase, user_id=user_id, personality_id=personality_id,
                ticker=ticker, categories=categories, limit=limit
            ))
    elif db is not None:
        # MongoDB fallback (transition period)
        results.extend(await _retrieve_mongo_fallback(
            db, user_id=user_id, personality_id=personality_id,
            ticker=ticker, categories=categories, limit=limit
        ))

    # Deduplicate and trim
    seen_ids = set()
    deduped = []
    for r in results:
        rid = r.get("id", str(id(r)))
        if rid not in seen_ids:
            seen_ids.add(rid)
            deduped.append(r)

    return deduped[:limit]


async def retrieve_for_ticker(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
    ticker: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    return await retrieve_context(
        db, personality_id=personality_id, user_id=user_id,
        ticker=ticker, query_text=f"trading {ticker}", limit=limit,
    )


async def retrieve_lessons(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    return await retrieve_context(
        db, personality_id=personality_id, user_id=user_id,
        categories=[CATEGORY_LESSON_LEARNED, CATEGORY_USER_NOTE], limit=limit,
    )


async def get_current_regime(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
) -> Optional[Dict[str, Any]]:
    """Get the most recent regime context (from Redis hot layer)."""
    r = _get_redis()
    if r:
        index_key = _hot_index_key(personality_id, user_id)
        try:
            members = r.zrevrange(index_key, 0, 20, withscores=True)
            for member_key, _ in members:
                raw = r.get(member_key)
                if not raw:
                    continue
                entry = json.loads(raw)
                if entry.get("category") == CATEGORY_REGIME_CONTEXT:
                    return entry
        except Exception as exc:
            logger.debug(f"Redis get_current_regime failed: {exc}")

    # Supabase fallback
    supabase = _get_supabase()
    if supabase:
        try:
            result = (
                supabase.table("pilot_memory")
                .select("*")
                .eq("user_id", user_id)
                .eq("personality_id", personality_id)
                .eq("category", CATEGORY_REGIME_CONTEXT)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]
        except Exception:
            pass

    # Mongo fallback
    if db is not None:
        try:
            doc = await db["pilot_memory_hot"].find_one(
                {"personality_id": personality_id, "user_id": user_id, "category": CATEGORY_REGIME_CONTEXT},
                sort=[("created_at", -1)],
            )
            if doc:
                doc.pop("_id", None)
                return doc
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# Memory stats (for UI)
# ---------------------------------------------------------------------------

async def get_memory_stats(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
) -> Dict[str, Any]:
    counts = {"hot": 0, "warm": 0, "cold": 0}

    r = _get_redis()
    if r:
        try:
            index_key = _hot_index_key(personality_id, user_id)
            counts["hot"] = r.zcard(index_key)
        except Exception:
            pass

    supabase = _get_supabase()
    if supabase:
        try:
            for layer in ["warm", "cold"]:
                result = (
                    supabase.table("pilot_memory")
                    .select("id", count="exact")
                    .eq("user_id", user_id)
                    .eq("personality_id", personality_id)
                    .eq("layer", layer)
                    .execute()
                )
                counts[layer] = result.count or 0
        except Exception as exc:
            logger.debug(f"memory stats from Supabase failed: {exc}")

    return {"layers": counts, "total": sum(counts.values())}


# ---------------------------------------------------------------------------
# Internal: store operations
# ---------------------------------------------------------------------------

async def _store_memory(
    *,
    db: Any,
    user_id: str,
    personality_id: str,
    layer: str,
    category: str,
    content: str,
    ticker: Optional[str] = None,
    importance: float = 0.5,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Store to Supabase (primary) with MongoDB fallback."""
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    expires_at = None
    if layer == "warm":
        expires_at = (now + timedelta(seconds=WARM_TTL_SECONDS)).isoformat()

    # Generate embedding for semantic retrieval
    embedding = await _generate_embedding(content)

    # Try Supabase first
    supabase = _get_supabase()
    if supabase:
        try:
            data = {
                "id": entry_id,
                "user_id": user_id,
                "personality_id": personality_id,
                "layer": layer,
                "category": category,
                "ticker": ticker,
                "content": content,
                "importance": importance,
                "metadata": metadata or {},
                "expires_at": expires_at,
            }
            if embedding:
                data["embedding"] = embedding
            supabase.table("pilot_memory").insert(data).execute()
            return entry_id
        except Exception as exc:
            logger.warning(f"Supabase store_memory failed, falling back to Mongo: {exc}")

    # MongoDB fallback
    if db is not None:
        coll_name = {"hot": "pilot_memory_hot", "warm": "pilot_memory_warm", "cold": "pilot_memory_cold"}.get(layer, "pilot_memory_warm")
        try:
            await db[coll_name].insert_one({
                "id": entry_id,
                "user_id": user_id,
                "personality_id": personality_id,
                "layer": layer,
                "category": category,
                "ticker": ticker,
                "content": content,
                "importance": importance,
                "metadata": metadata or {},
                "created_at": now.isoformat(),
                "expires_at": expires_at,
            })
        except Exception as exc:
            logger.error(f"Mongo fallback store_memory failed: {exc}")

    return entry_id


async def _store_hot(
    *,
    user_id: str,
    personality_id: str,
    category: str,
    content: str,
    importance: float = 0.5,
    metadata: Optional[Dict[str, Any]] = None,
    db: Any = None,
) -> str:
    """Store to Redis hot layer with TTL auto-expiry."""
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    entry = {
        "id": entry_id,
        "user_id": user_id,
        "personality_id": personality_id,
        "layer": "hot",
        "category": category,
        "content": content,
        "importance": importance,
        "metadata": metadata or {},
        "created_at": now.isoformat(),
    }

    r = _get_redis()
    if r:
        try:
            key = _hot_key(personality_id, user_id, category, entry_id)
            r.setex(key, HOT_TTL_SECONDS, json.dumps(entry))
            # Add to sorted set index (score = timestamp for ordering)
            index_key = _hot_index_key(personality_id, user_id)
            r.zadd(index_key, {key: now.timestamp()})
            r.expire(index_key, HOT_TTL_SECONDS * 2)
            return entry_id
        except Exception as exc:
            logger.warning(f"Redis store_hot failed: {exc}")

    # Fallback: store in Supabase with short expiry
    supabase = _get_supabase()
    if supabase:
        try:
            expires = (now + timedelta(seconds=HOT_TTL_SECONDS)).isoformat()
            supabase.table("pilot_memory").insert({
                **entry,
                "expires_at": expires,
            }).execute()
            return entry_id
        except Exception:
            pass

    # Mongo fallback
    if db is not None:
        try:
            entry["expires_at"] = (now + timedelta(seconds=HOT_TTL_SECONDS)).isoformat()
            await db["pilot_memory_hot"].insert_one(entry)
        except Exception:
            pass

    return entry_id


# ---------------------------------------------------------------------------
# Internal: retrieval helpers
# ---------------------------------------------------------------------------

async def _retrieve_hot(*, user_id: str, personality_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve hot entries from Redis."""
    r = _get_redis()
    if not r:
        return []

    try:
        index_key = _hot_index_key(personality_id, user_id)
        member_keys = r.zrevrange(index_key, 0, limit - 1)
        results = []
        for key in member_keys:
            raw = r.get(key)
            if raw:
                results.append(json.loads(raw))
        return results
    except Exception as exc:
        logger.debug(f"Redis retrieve_hot failed: {exc}")
        return []


async def _retrieve_supabase_simple(
    supabase,
    *,
    user_id: str,
    personality_id: str,
    ticker: Optional[str] = None,
    categories: Optional[List[str]] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Simple Supabase query without RPC (fallback)."""
    try:
        query = (
            supabase.table("pilot_memory")
            .select("*")
            .eq("user_id", user_id)
            .eq("personality_id", personality_id)
            .in_("layer", ["warm", "cold"])
            .order("created_at", desc=True)
            .limit(limit)
        )
        if ticker:
            query = query.or_(f"ticker.eq.{ticker},ticker.is.null")
        if categories:
            query = query.in_("category", categories)
        result = query.execute()
        return result.data or []
    except Exception as exc:
        logger.debug(f"Supabase simple retrieval failed: {exc}")
        return []


async def _retrieve_mongo_fallback(
    db: Any,
    *,
    user_id: str,
    personality_id: str,
    ticker: Optional[str] = None,
    categories: Optional[List[str]] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """MongoDB fallback retrieval (transition period)."""
    import math

    now = datetime.now(timezone.utc)
    query: Dict[str, Any] = {"personality_id": personality_id, "user_id": user_id}
    if ticker:
        query["$or"] = [{"ticker": ticker}, {"ticker": None}]
    if categories:
        query["category"] = {"$in": categories}

    results: List[Dict[str, Any]] = []
    for coll_name in ["pilot_memory_hot", "pilot_memory_warm", "pilot_memory_cold"]:
        try:
            cursor = db[coll_name].find(query).sort("created_at", -1).limit(limit)
            async for doc in cursor:
                doc.pop("_id", None)
                expires = doc.get("expires_at")
                if expires:
                    try:
                        exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                        if exp_dt < now:
                            continue
                    except (ValueError, TypeError):
                        pass
                results.append(doc)
        except Exception:
            continue

    return results[:limit]


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

async def ensure_indexes(db: Any) -> None:
    """Create MongoDB indexes (transition period). Supabase indexes are in schema.sql."""
    for coll_name in ["pilot_memory_hot", "pilot_memory_warm"]:
        coll = db[coll_name]
        await coll.create_index("expires_at", expireAfterSeconds=0)
        await coll.create_index([("personality_id", 1), ("user_id", 1), ("created_at", -1)])

    cold = db["pilot_memory_cold"]
    await cold.create_index([("personality_id", 1), ("user_id", 1), ("created_at", -1)])
