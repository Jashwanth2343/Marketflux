from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from market_data import search_all_stocks


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fundos_store_configured() -> bool:
    return bool(os.getenv("FUNDOS_DATABASE_URL"))


def _strategy_row_from_run(run: Dict[str, Any]) -> Dict[str, Any]:
    strategy = run.get("strategy") or {}
    tickers = strategy.get("tickers") or run.get("tickers") or []
    primary_ticker = tickers[0] if tickers else "--"
    created_at = run.get("created_at") or _utcnow_iso()
    execution_status = run.get("execution_status") or "generated"
    return {
        "strategy_id": run.get("strategy_run_id"),
        "ticker": primary_ticker,
        "tickers": tickers,
        "title": strategy.get("title") or "Strategy",
        "strategy_type": strategy.get("strategy_type") or run.get("mode") or "strategy",
        "confidence": strategy.get("confidence") or 0,
        "created_at": created_at,
        "status": execution_status,
    }


async def build_strategy_queue(db, user: Optional[Dict[str, Any]], limit: int = 50) -> Dict[str, Any]:
    from .fundos_pg_client import get_pg_connection
    user_id = user.get("user_id") if user else None
    items = []
    
    try:
        conn = await get_pg_connection()
        if user_id:
            rows = await conn.fetch("SELECT * FROM strategy_proposals WHERE owner_user_id = $1 ORDER BY created_at DESC LIMIT $2", user_id, limit)
        else:
            rows = await conn.fetch("SELECT * FROM strategy_proposals ORDER BY created_at DESC LIMIT $1", limit)
            
        for row in rows:
            items.append({
                "strategy_id": str(row["id"]),
                "ticker": row["ticker"] or "--",
                "tickers": row["tickers"] or [],
                "title": row["title"],
                "strategy_type": row["strategy_type"],
                "confidence": row["confidence"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else _utcnow_iso(),
                "status": row["execution_status"],
            })
        await conn.close()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Postgres queue fetch failed: {e}")
        
    return {
        "as_of": _utcnow_iso(),
        "items": items,
        "total": len(items),
    }


async def build_fundos_overview(db, user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    queue = await build_strategy_queue(db, user, limit=10)
    return {
        "as_of": queue["as_of"],
        "strategy_queue_count": queue["total"],
        "has_runs": bool(queue["items"]),
        "latest_run_at": queue["items"][0]["created_at"] if queue["items"] else None,
        "paper_portfolio_configured": fundos_store_configured(),
        "terminal_status": "pending_openclaw",
    }


async def search_fundos(db, user: Optional[Dict[str, Any]], query: str, limit: int = 8) -> Dict[str, Any]:
    cleaned = query.strip()
    if not cleaned:
        return {"query": "", "results": []}

    stock_results = await search_all_stocks(cleaned)
    stocks = []
    for item in stock_results[:limit]:
        stocks.append(
            {
                "id": item.get("symbol"),
                "kind": "security",
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "exchange": item.get("exchange"),
                "type": item.get("type") or "Equity",
            }
        )

    strategy_results: List[Dict[str, Any]] = []
    user_id = user.get("user_id") if user else None
    if user_id:
        regex = re.compile(re.escape(cleaned), re.IGNORECASE)
        cursor = (
            db.strategy_runs.find(
                {
                    "owner_user_id": user_id,
                    "$or": [
                        {"strategy.title": regex},
                        {"prompt": regex},
                        {"tickers": {"$in": [cleaned.upper()]}},
                        {"strategy.tickers": {"$in": [cleaned.upper()]}},
                    ],
                },
                {"_id": 0},
            )
            .sort("created_at", -1)
            .limit(limit)
        )
        for run in await cursor.to_list(limit):
            row = _strategy_row_from_run(run)
            strategy_results.append(
                {
                    "id": row["strategy_id"],
                    "kind": "strategy",
                    "title": row["title"],
                    "ticker": row["ticker"],
                    "tickers": row["tickers"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "confidence": row["confidence"],
                }
            )

    return {
        "query": cleaned,
        "results": stocks + strategy_results,
    }


async def build_paper_portfolio(user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "as_of": _utcnow_iso(),
        "configured": fundos_store_configured(),
        "positions": [],
        "message": "Paper portfolio will become active once the isolated Fund OS store is configured."
        if not fundos_store_configured()
        else None,
        "owner_user_id": user.get("user_id") if user else None,
    }


async def build_audit_feed(db, user: Optional[Dict[str, Any]], limit: int = 20) -> Dict[str, Any]:
    queue = await build_strategy_queue(db, user, limit=limit)
    items = [
        {
            "event_type": "strategy_generated",
            "timestamp": item["created_at"],
            "strategy_id": item["strategy_id"],
            "summary": f"{item['title']} created for {item['ticker']}.",
        }
        for item in queue["items"]
    ]
    return {"as_of": queue["as_of"], "items": items}
