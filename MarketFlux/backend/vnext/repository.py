from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_daily_brief(db, brief_date: str, user_id: Optional[str]) -> Optional[Dict[str, Any]]:
    return await db.daily_briefs.find_one(
        {"date": brief_date, "user_id": user_id},
        {"_id": 0},
    )


async def save_daily_brief(db, payload: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    doc = dict(payload)
    doc["user_id"] = user_id
    await db.daily_briefs.update_one(
        {"date": doc["date"], "user_id": user_id},
        {"$set": doc},
        upsert=True,
    )
    return doc


async def save_signal_events(db, signals: List[Dict[str, Any]]) -> None:
    if not signals:
        return
    for signal in signals:
        doc = dict(signal)
        doc.setdefault("created_at", _utcnow_iso())
        await db.signal_events.update_one(
            {
                "signal_type": doc.get("signal_type"),
                "title": doc.get("title"),
                "asset_scope": doc.get("asset_scope"),
            },
            {"$set": doc},
            upsert=True,
        )


async def get_recent_signal_events(db, limit: int = 20) -> List[Dict[str, Any]]:
    rows = await db.signal_events.find({}, {"_id": 0}).sort("created_at", -1).limit(limit * 3).to_list(limit * 3)
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        key = (row.get("signal_type"), row.get("title"), row.get("asset_scope"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= limit:
            break
    return deduped


async def get_watchlist_tickers(db, user_id: Optional[str]) -> List[str]:
    if not user_id:
        return []
    watchlist = await db.watchlists.find_one({"user_id": user_id}, {"_id": 0})
    if not watchlist:
        return []
    return [ticker.upper() for ticker in (watchlist.get("tickers") or [])]


async def get_portfolio_holdings(db, user_id: Optional[str]) -> List[Dict[str, Any]]:
    if not user_id:
        return []
    portfolio = await db.portfolios.find_one({"user_id": user_id}, {"_id": 0})
    if not portfolio:
        return []
    return portfolio.get("holdings") or []


async def get_saved_theses(db, user_id: Optional[str], ticker: Optional[str] = None) -> List[Dict[str, Any]]:
    if not user_id:
        return []
    query: Dict[str, Any] = {"owner_user_id": user_id}
    if ticker:
        query["ticker"] = ticker.upper()
    return await db.saved_theses.find(query, {"_id": 0}).sort("updated_at", -1).to_list(50)


async def save_thesis(db, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    now = _utcnow_iso()
    doc = {
        "ticker": payload["ticker"].upper(),
        "thesis_text": payload["thesis_text"],
        "stance": payload["stance"],
        "confidence": payload["confidence"],
        "catalysts": payload.get("catalysts", []),
        "risks": payload.get("risks", []),
        "owner_user_id": user_id,
        "updated_at": now,
        "created_at": now,
    }
    await db.saved_theses.insert_one(doc)
    return doc


async def save_strategy_run(db, user_id: Optional[str], payload: Dict[str, Any]) -> Dict[str, Any]:
    now = _utcnow_iso()
    doc = {
        "strategy_run_id": f"strategy_{uuid.uuid4().hex[:12]}",
        "owner_user_id": user_id,
        "created_at": now,
        "updated_at": now,
        **payload,
    }
    await db.strategy_runs.insert_one(doc)
    return doc


async def get_recent_strategy_runs(db, user_id: Optional[str], limit: int = 5) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"owner_user_id": user_id} if user_id else {"owner_user_id": None}
    return await db.strategy_runs.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
