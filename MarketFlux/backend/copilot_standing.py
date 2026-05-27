"""Standing agents — the copilot's always-on, scheduled autonomous runs.

A standing agent is a saved natural-language instruction that the copilot runs by
itself on an interval (e.g. "every 60 min, check my momentum names and trim any
position down >8%"). This closes the gap to a Public.com-style "agentic
brokerage": agents that monitor + act unattended, not just on demand.

Standing agents run in AUTONOMOUS mode (the act of creating one is the user's
authorization) and are paper-only. They're scoped per user, capped in number,
have a minimum interval, and every run is logged with its outcome + any trades.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

COLLECTION = "copilot_standing_agents"
MAX_ACTIVE_PER_USER = 5
MIN_INTERVAL_MINUTES = 5
MAX_RUNS_KEPT = 15

_scheduler_started = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _public(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
async def list_agents(db, user_id: str) -> List[Dict[str, Any]]:
    cur = db[COLLECTION].find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1)
    return [doc async for doc in cur]


async def create_agent(db, user_id: str, *, name: str, instruction: str,
                       interval_minutes: int, model: Optional[str] = None) -> Dict[str, Any]:
    active = await db[COLLECTION].count_documents({"user_id": user_id, "status": "active"})
    if active >= MAX_ACTIVE_PER_USER:
        return {"ok": False, "error": f"Max {MAX_ACTIVE_PER_USER} active standing agents."}
    interval = max(MIN_INTERVAL_MINUTES, int(interval_minutes or 60))
    now = _now()
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "name": (name or "Untitled agent").strip()[:80],
        "instruction": (instruction or "").strip()[:1500],
        "interval_minutes": interval,
        "model": model,
        "status": "active",
        "created_at": _iso(now),
        "last_run": None,
        "next_run": _iso(now + timedelta(minutes=interval)),
        "runs": [],
    }
    await db[COLLECTION].insert_one(dict(doc))
    return {"ok": True, "item": _public(dict(doc))}


async def update_agent(db, user_id: str, agent_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {k: v for k, v in fields.items()
               if k in {"name", "instruction", "interval_minutes", "status", "model"} and v is not None}
    if "interval_minutes" in allowed:
        allowed["interval_minutes"] = max(MIN_INTERVAL_MINUTES, int(allowed["interval_minutes"]))
    if "status" in allowed and allowed["status"] not in {"active", "paused"}:
        allowed.pop("status")
    if not allowed:
        return {"ok": False, "error": "nothing to update"}
    await db[COLLECTION].update_one({"id": agent_id, "user_id": user_id}, {"$set": allowed})
    doc = await db[COLLECTION].find_one({"id": agent_id, "user_id": user_id}, {"_id": 0})
    return {"ok": bool(doc), "item": doc}


async def delete_agent(db, user_id: str, agent_id: str) -> Dict[str, Any]:
    res = await db[COLLECTION].delete_one({"id": agent_id, "user_id": user_id})
    return {"ok": res.deleted_count > 0}


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
async def _run_instruction(db, user_id: str, name: str, instruction: str,
                           model: Optional[str]) -> Dict[str, Any]:
    """Invoke the conversational agent autonomously and collect its outcome."""
    from copilot_agent import run_copilot_agent

    framed = (
        f"You are running as the scheduled autonomous agent \"{name}\". Execute this "
        f"standing instruction now, using your tools and trading directly as needed:\n\n{instruction}"
    )
    tokens: List[str] = []
    trades: List[Dict[str, Any]] = []
    try:
        async for chunk in run_copilot_agent(
            message=framed, history=[], db=db, user_id=user_id,
            session_id=f"standing:{name}", model=model, confirm=False,
        ):
            line = chunk.strip()
            if not line.startswith("data: "):
                continue
            try:
                ev = json.loads(line[6:])
            except Exception:
                continue
            if ev.get("type") == "token":
                tokens.append(ev.get("content", ""))
            elif ev.get("type") == "trade":
                trades.append({k: v for k, v in ev.items() if k != "type"})
        summary = ("".join(tokens)).strip()[:1200] or "Completed (no summary)."
        return {"summary": summary, "trades": trades}
    except Exception as exc:
        logger.exception("standing agent run failed")
        return {"summary": f"Run error: {exc}", "trades": [], "error": str(exc)}


async def run_agent(db, agent: Dict[str, Any]) -> Dict[str, Any]:
    """Run one standing agent now and record the outcome."""
    result = await _run_instruction(
        db, agent["user_id"], agent.get("name", "agent"),
        agent.get("instruction", ""), agent.get("model"),
    )
    now = _now()
    run_record = {
        "timestamp": _iso(now),
        "summary": result.get("summary", ""),
        "trades": result.get("trades", []),
        "error": result.get("error"),
    }
    await db[COLLECTION].update_one(
        {"id": agent["id"]},
        {
            "$set": {
                "last_run": _iso(now),
                "next_run": _iso(now + timedelta(minutes=int(agent.get("interval_minutes", 60)))),
            },
            "$push": {"runs": {"$each": [run_record], "$slice": -MAX_RUNS_KEPT}},
        },
    )
    return run_record


async def run_now(db, user_id: str, agent_id: str) -> Dict[str, Any]:
    agent = await db[COLLECTION].find_one({"id": agent_id, "user_id": user_id}, {"_id": 0})
    if not agent:
        return {"ok": False, "error": "not found"}
    record = await run_agent(db, agent)
    return {"ok": True, "run": record}


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
async def _due_agents(db) -> List[Dict[str, Any]]:
    now_iso = _iso(_now())
    cur = db[COLLECTION].find(
        {"status": "active", "next_run": {"$lte": now_iso}}, {"_id": 0}
    ).limit(20)
    return [doc async for doc in cur]


async def scheduler_loop(db) -> None:
    """Wake every 60s, run any due standing agents sequentially. Safe to run forever."""
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    logger.info("Copilot standing-agent scheduler started")
    while True:
        try:
            due = await _due_agents(db)
            for agent in due:
                try:
                    logger.info("Standing agent '%s' (%s) is due — running", agent.get("name"), agent["id"])
                    await run_agent(db, agent)
                except Exception as exc:
                    logger.warning("standing agent %s run error: %s", agent.get("id"), exc)
        except Exception as exc:
            logger.warning("standing scheduler tick error: %s", exc)
        await asyncio.sleep(60)
