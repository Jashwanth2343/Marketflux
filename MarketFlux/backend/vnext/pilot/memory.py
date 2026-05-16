"""Pilot Memory Agent: layered institutional knowledge for the AI trading copilot.

Architecture (inspired by FinMem + TradingGPT):

  HOT layer   — recent trades, live regime context, intraday signals (TTL: 24h)
  WARM layer  — weekly patterns, trade outcomes, personality performance (TTL: 30d)
  COLD layer  — long-horizon lessons, regime transitions, user-documented errors (permanent)

All agents in the swarm can query memory via retrieve_context(). The memory curator
scores entries for relevance and importance, applying exponential decay so recent
insights carry more weight while permanent lessons persist.

Mongo collections:
  pilot_memory_hot   — high-frequency, short-lived context
  pilot_memory_warm  — medium-term trade outcomes and patterns
  pilot_memory_cold  — permanent institutional knowledge
"""
from __future__ import annotations

import math
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

HOT_COLLECTION = "pilot_memory_hot"
WARM_COLLECTION = "pilot_memory_warm"
COLD_COLLECTION = "pilot_memory_cold"

HOT_TTL_HOURS = 24
WARM_TTL_DAYS = 30


# ---------------------------------------------------------------------------
# Memory entry types
# ---------------------------------------------------------------------------

class MemoryEntry:
    __slots__ = (
        "id", "personality_id", "user_id", "layer", "category",
        "ticker", "content", "importance", "created_at", "expires_at",
        "metadata",
    )

    def __init__(
        self,
        *,
        personality_id: str,
        user_id: str,
        layer: str,
        category: str,
        content: str,
        ticker: Optional[str] = None,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.id = str(uuid.uuid4())
        self.personality_id = personality_id
        self.user_id = user_id
        self.layer = layer
        self.category = category
        self.ticker = ticker
        self.content = content
        self.importance = max(0.0, min(1.0, importance))
        self.created_at = datetime.now(timezone.utc)
        self.metadata = metadata or {}

        if layer == "hot":
            self.expires_at = self.created_at + timedelta(hours=HOT_TTL_HOURS)
        elif layer == "warm":
            self.expires_at = self.created_at + timedelta(days=WARM_TTL_DAYS)
        else:
            self.expires_at = None

    def to_doc(self) -> Dict[str, Any]:
        doc = {
            "id": self.id,
            "personality_id": self.personality_id,
            "user_id": self.user_id,
            "layer": self.layer,
            "category": self.category,
            "ticker": self.ticker,
            "content": self.content,
            "importance": self.importance,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
        }
        return doc


# ---------------------------------------------------------------------------
# Memory categories
# ---------------------------------------------------------------------------

CATEGORY_TRADE_OUTCOME = "trade_outcome"
CATEGORY_REGIME_CONTEXT = "regime_context"
CATEGORY_LESSON_LEARNED = "lesson_learned"
CATEGORY_USER_NOTE = "user_note"
CATEGORY_REFLECTION = "reflection"
CATEGORY_PATTERN = "pattern"
CATEGORY_DEBATE_INSIGHT = "debate_insight"


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
    """Record a completed trade into WARM memory with outcome analysis."""
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

    entry = MemoryEntry(
        personality_id=personality_id,
        user_id=user_id,
        layer="warm",
        category=CATEGORY_TRADE_OUTCOME,
        ticker=ticker,
        content=content,
        importance=importance,
        metadata={
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "won": won,
            "regime_at_entry": regime_at_entry,
            "conviction": conviction,
        },
    )
    await db[WARM_COLLECTION].insert_one(entry.to_doc())
    return entry.id


async def record_regime_context(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
    regime_label: str,
    details: str = "",
    tickers_affected: Optional[List[str]] = None,
) -> str:
    """Record a market regime observation into HOT memory."""
    content = f"REGIME: {regime_label} | {details}"
    entry = MemoryEntry(
        personality_id=personality_id,
        user_id=user_id,
        layer="hot",
        category=CATEGORY_REGIME_CONTEXT,
        content=content,
        importance=0.7,
        metadata={
            "regime_label": regime_label,
            "tickers_affected": tickers_affected or [],
        },
    )
    await db[HOT_COLLECTION].insert_one(entry.to_doc())
    return entry.id


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
    entry = MemoryEntry(
        personality_id=personality_id,
        user_id=user_id,
        layer="cold",
        category=CATEGORY_LESSON_LEARNED,
        ticker=ticker,
        content=lesson,
        importance=0.8,
        metadata={"source": source},
    )
    await db[COLD_COLLECTION].insert_one(entry.to_doc())
    return entry.id


async def record_user_note(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
    note: str,
    ticker: Optional[str] = None,
) -> str:
    """User-documented error, preference, or observation → COLD memory."""
    entry = MemoryEntry(
        personality_id=personality_id,
        user_id=user_id,
        layer="cold",
        category=CATEGORY_USER_NOTE,
        ticker=ticker,
        content=note,
        importance=0.9,
        metadata={},
    )
    await db[COLD_COLLECTION].insert_one(entry.to_doc())
    return entry.id


async def record_reflection(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
    reflection: str,
    tickers: Optional[List[str]] = None,
) -> str:
    """Post-trade reflection / self-critique → WARM memory."""
    entry = MemoryEntry(
        personality_id=personality_id,
        user_id=user_id,
        layer="warm",
        category=CATEGORY_REFLECTION,
        content=reflection,
        importance=0.6,
        metadata={"tickers": tickers or []},
    )
    await db[WARM_COLLECTION].insert_one(entry.to_doc())
    return entry.id


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
    entry = MemoryEntry(
        personality_id=personality_id,
        user_id=user_id,
        layer="warm",
        category=CATEGORY_DEBATE_INSIGHT,
        ticker=ticker,
        content=f"{verdict.upper()} {ticker} (conv={conviction}): {insight[:500]}",
        importance=min(1.0, 0.3 + conviction * 0.07),
        metadata={"conviction": conviction, "verdict": verdict},
    )
    await db[WARM_COLLECTION].insert_one(entry.to_doc())
    return entry.id


# ---------------------------------------------------------------------------
# Read / retrieval
# ---------------------------------------------------------------------------

def _decay_score(created_at_iso: str, importance: float, half_life_days: float = 7.0) -> float:
    """Exponential decay scoring: recent + important memories rank higher."""
    try:
        created = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        created = datetime.now(timezone.utc)
    age_days = (datetime.now(timezone.utc) - created).total_seconds() / 86400
    decay = math.exp(-0.693 * age_days / half_life_days)
    return importance * decay


async def retrieve_context(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
    ticker: Optional[str] = None,
    categories: Optional[List[str]] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Retrieve relevant memories across all layers, ranked by decay-weighted importance.

    This is the primary function the swarm calls to get institutional context.
    """
    now = datetime.now(timezone.utc)
    query: Dict[str, Any] = {
        "personality_id": personality_id,
        "user_id": user_id,
    }
    if ticker:
        query["$or"] = [{"ticker": ticker}, {"ticker": None}]
    if categories:
        query["category"] = {"$in": categories}

    results: List[Dict[str, Any]] = []

    for coll_name in [HOT_COLLECTION, WARM_COLLECTION, COLD_COLLECTION]:
        coll = db[coll_name]
        cursor = coll.find(query).sort("created_at", -1).limit(limit * 2)
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
            half_life = {"hot": 1.0, "warm": 7.0, "cold": 90.0}.get(doc.get("layer", "warm"), 7.0)
            doc["_score"] = _decay_score(doc.get("created_at", ""), doc.get("importance", 0.5), half_life)
            results.append(doc)

    results.sort(key=lambda d: d.get("_score", 0), reverse=True)
    for r in results:
        r.pop("_score", None)
    return results[:limit]


async def retrieve_for_ticker(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
    ticker: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Retrieve memories specifically about a ticker — used during per-candidate decisions."""
    return await retrieve_context(
        db,
        personality_id=personality_id,
        user_id=user_id,
        ticker=ticker,
        limit=limit,
    )


async def retrieve_lessons(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    """Get permanent lessons and user notes — the institutional knowledge base."""
    return await retrieve_context(
        db,
        personality_id=personality_id,
        user_id=user_id,
        categories=[CATEGORY_LESSON_LEARNED, CATEGORY_USER_NOTE],
        limit=limit,
    )


async def get_current_regime(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
) -> Optional[Dict[str, Any]]:
    """Get the most recent regime context entry (if any, and not expired)."""
    now = datetime.now(timezone.utc)
    doc = await db[HOT_COLLECTION].find_one(
        {
            "personality_id": personality_id,
            "user_id": user_id,
            "category": CATEGORY_REGIME_CONTEXT,
        },
        sort=[("created_at", -1)],
    )
    if not doc:
        return None
    doc.pop("_id", None)
    expires = doc.get("expires_at")
    if expires:
        try:
            if datetime.fromisoformat(expires.replace("Z", "+00:00")) < now:
                return None
        except (ValueError, TypeError):
            pass
    return doc


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

async def promote_warm_to_cold(
    db: Any,
    *,
    min_importance: float = 0.75,
    min_age_days: int = 14,
) -> int:
    """Promote high-importance warm memories to cold (permanent) before they expire."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=min_age_days)).isoformat()
    cursor = db[WARM_COLLECTION].find({
        "importance": {"$gte": min_importance},
        "created_at": {"$lte": cutoff},
    })
    promoted = 0
    async for doc in cursor:
        doc.pop("_id", None)
        doc["layer"] = "cold"
        doc["expires_at"] = None
        doc["promoted_from"] = "warm"
        await db[COLD_COLLECTION].insert_one(doc)
        await db[WARM_COLLECTION].delete_one({"id": doc["id"]})
        promoted += 1
    return promoted


async def cleanup_expired(db: Any) -> Dict[str, int]:
    """Remove expired entries from hot and warm layers."""
    now = datetime.now(timezone.utc).isoformat()
    hot_result = await db[HOT_COLLECTION].delete_many({"expires_at": {"$lt": now}})
    warm_result = await db[WARM_COLLECTION].delete_many({"expires_at": {"$lt": now}})
    return {
        "hot_deleted": hot_result.deleted_count,
        "warm_deleted": warm_result.deleted_count,
    }


async def get_memory_stats(
    db: Any,
    *,
    personality_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Memory layer statistics for the UI dashboard."""
    counts = {}
    for layer, coll_name in [("hot", HOT_COLLECTION), ("warm", WARM_COLLECTION), ("cold", COLD_COLLECTION)]:
        counts[layer] = await db[coll_name].count_documents({
            "personality_id": personality_id,
            "user_id": user_id,
        })
    return {
        "layers": counts,
        "total": sum(counts.values()),
    }


async def ensure_indexes(db: Any) -> None:
    """Create TTL and query indexes for memory collections."""
    for coll_name in [HOT_COLLECTION, WARM_COLLECTION]:
        coll = db[coll_name]
        await coll.create_index("expires_at", expireAfterSeconds=0)
        await coll.create_index([("personality_id", 1), ("user_id", 1), ("created_at", -1)])
        await coll.create_index([("personality_id", 1), ("user_id", 1), ("ticker", 1)])
        await coll.create_index([("personality_id", 1), ("user_id", 1), ("category", 1)])

    cold = db[COLD_COLLECTION]
    await cold.create_index([("personality_id", 1), ("user_id", 1), ("created_at", -1)])
    await cold.create_index([("personality_id", 1), ("user_id", 1), ("ticker", 1)])
    await cold.create_index([("personality_id", 1), ("user_id", 1), ("category", 1)])
