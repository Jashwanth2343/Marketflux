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
from datetime import datetime, timezone
from typing import Any, Dict

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
    pid = str(uuid.uuid4())
    pv = preview(name, args)
    await db[COLLECTION].insert_one({
        "id": pid,
        "user_id": user_id,
        "tool": name,
        "args": args,
        "preview": pv,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {
        "ok": True,
        "staged": True,
        "proposal_id": pid,
        "message": "Trade staged — awaiting the user's approval. Tell them what you prepared and why.",
        **pv,
    }


async def execute_pending(db, user_id: str, pid: str) -> Dict[str, Any]:
    """Approve + execute a staged trade against the paper account."""
    doc = await db[COLLECTION].find_one({"id": pid, "user_id": user_id})
    if not doc:
        return {"ok": False, "error": "Trade not found."}
    if doc.get("status") != "pending":
        return {"ok": False, "error": f"Trade already {doc.get('status')}."}

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

    await db[COLLECTION].update_one(
        {"id": pid},
        {"$set": {
            "status": "executed" if result.get("ok") else "failed",
            "result": result,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return result


async def reject_pending(db, user_id: str, pid: str) -> Dict[str, Any]:
    res = await db[COLLECTION].update_one(
        {"id": pid, "user_id": user_id, "status": "pending"},
        {"$set": {"status": "rejected", "rejected_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": res.modified_count > 0}
