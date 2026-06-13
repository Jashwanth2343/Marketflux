"""Staged trade proposals for the Copilot's confirm-before-execute mode.

When the user runs the copilot in "Confirm" mode, the agent's execution tools
(place_order / close_position / cancel) DON'T hit the broker. Instead they stage
a pending trade here; the UI shows an Approve / Reject card, and only an explicit
user approval calls the broker via copilot_trading_tools. This is the core safety
gate — even a prompt-injected agent cannot move the (paper) account without a
human click.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

COLLECTION = "copilot_pending_trades"


def preview(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """A compact, human-facing description of what the staged trade will do."""
    if name == "place_order":
        return {
            "action": "order",
            "symbol": (args.get("symbol") or "").upper(),
            "side": (args.get("side") or "").lower(),
            "qty": args.get("quantity"),
            "order_type": (args.get("order_type") or "market").lower(),
            "limit_price": args.get("limit_price") or None,
        }
    if name == "close_position":
        return {"action": "close", "symbol": (args.get("symbol") or "").upper()}
    if name == "cancel_all_open_orders":
        return {"action": "cancel_all"}
    return {"action": name}


async def stage(db, user_id: str, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Record a pending trade and return a 'staged' result for the agent."""
    import copilot_store
    pid = str(uuid.uuid4())
    pv = preview(name, args)
    await copilot_store.insert_pending(db, {
        "id": pid,
        "user_id": user_id,
        "tool": name,
        "args": args,
        "preview": pv,
        "status": "pending",
        # Real datetime: Postgres timestamptz, or the Mongo TTL index on fallback.
        "created_at": datetime.now(timezone.utc),
    })
    return {
        "ok": True,
        "staged": True,
        "proposal_id": pid,
        "message": "Trade staged — awaiting the user's approval. Tell them what you prepared and why.",
        **pv,
    }


async def list_pending(db, user_id: str) -> List[Dict[str, Any]]:
    """Staged trades still awaiting approval — lets the UI rehydrate after a
    page refresh instead of silently losing the approval queue."""
    import copilot_store
    return await copilot_store.list_pending(db, user_id)


async def execute_pending(db, user_id: str, pid: str) -> Dict[str, Any]:
    """Approve + execute a staged trade against the paper account.

    Uses an atomic find_one_and_update to transition status from "pending" →
    "executing" as a mutex, preventing double-execution on rapid double-clicks
    or concurrent tab approvals.
    """
    # Staleness guard: reject proposals older than 1 hour.
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)

    import copilot_store
    doc = await copilot_store.claim_pending(db, user_id, pid, cutoff)
    if not doc:
        # Distinguish expired from not-found/already-processed.
        existing = await copilot_store.get_pending_meta(db, user_id, pid)
        if not existing:
            return {"ok": False, "error": "Trade not found."}
        existing_ts = existing.get("created_at")
        if isinstance(existing_ts, str):
            existing_ts = datetime.fromisoformat(existing_ts)
        # PyMongo decodes BSON dates as naive UTC; cutoff is aware. Normalize
        # so the comparison can't raise TypeError on stale approval clicks.
        if existing_ts is not None and existing_ts.tzinfo is None:
            existing_ts = existing_ts.replace(tzinfo=timezone.utc)
        if existing_ts and existing_ts < cutoff:
            return {"ok": False, "error": "Trade proposal expired (older than 1 hour). Ask the copilot for a fresh recommendation."}
        return {"ok": False, "error": f"Trade already {existing.get('status', 'processed')}."}

    import copilot_trading_tools as t
    name, args = doc["tool"], doc.get("args", {})
    try:
        if name == "place_order":
            result = await asyncio.to_thread(lambda: t.place_order(**args))
        elif name == "close_position":
            result = await asyncio.to_thread(lambda: t.close_position(args.get("symbol", "")))
        elif name == "cancel_all_open_orders":
            result = await asyncio.to_thread(t.cancel_all_open_orders)
        else:
            result = {"ok": False, "error": f"unknown tool {name}"}
    except Exception as exc:
        logger.error(f"execute_pending {pid} failed: {exc}")
        result = {"ok": False, "error": str(exc)}

    await copilot_store.set_pending_result(
        db, pid, "executed" if result.get("ok") else "failed", result)
    return result


async def reject_pending(db, user_id: str, pid: str) -> Dict[str, Any]:
    import copilot_store
    return {"ok": await copilot_store.mark_rejected(db, user_id, pid)}
