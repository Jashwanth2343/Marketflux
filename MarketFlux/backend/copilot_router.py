"""FastAPI router for the Trading Copilot — the conversational, autonomous
paper-trading agent. Mounted at /api/copilot.

Auth is optional (like /api/ai/chat): logged-in users get persistent per-user
history; anonymous local use falls back to a shared id. All trading is on the
shared Alpaca PAPER account.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from copilot_agent import run_copilot_agent

logger = logging.getLogger(__name__)

_ANON_ID = "local-copilot"


class CopilotChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = None
    model: Optional[str] = None
    confirm: bool = True  # confirm-before-execute (safe default); false = autonomous


class StandingAgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    instruction: str = Field(min_length=5, max_length=1500)
    interval_minutes: int = Field(default=60, ge=5, le=10080)
    model: Optional[str] = None


class StandingAgentUpdate(BaseModel):
    name: Optional[str] = None
    instruction: Optional[str] = None
    interval_minutes: Optional[int] = None
    status: Optional[str] = None
    model: Optional[str] = None


def build_copilot_router(db, get_current_user: Callable[[Request], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/copilot", tags=["copilot"])

    async def _resolve_user_id(request: Request) -> str:
        user = await get_current_user(request)
        return user["user_id"] if user else _ANON_ID

    async def _resolve_user_id_required(request: Request) -> str:
        """Like _resolve_user_id but raises 401 for unauthenticated requests.

        Used on all write endpoints (chat/stream, trade approve/reject, agents
        CRUD) to prevent anonymous callers from sharing the 'local-copilot'
        namespace and approving each other's staged trades.
        """
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required for this endpoint.")
        return user["user_id"]

    @router.get("/status")
    async def copilot_status():
        from vnext.alpaca_client import is_alpaca_configured
        return {
            "ok": True,
            "service": "trading-copilot",
            "paper_only": True,
            "alpaca_configured": is_alpaca_configured(),
            "disclaimer": "Paper trading only. Educational simulation, not investment advice.",
        }

    @router.post("/chat/stream")
    async def copilot_chat_stream(payload: CopilotChatRequest, request: Request):
        message = "".join(c for c in payload.message if c.isprintable() or c in "\n\t\r")
        user_id = await _resolve_user_id_required(request)
        # Enforce confirm mode for safety — autonomous mode is an opt-in
        # that requires an authenticated user whose identity can be audited.
        if not user_id or user_id == _ANON_ID:
            payload = payload.model_copy(update={"confirm": True})
        session_id = payload.session_id or str(uuid.uuid4())

        history = await db.copilot_messages.find(
            {"user_id": user_id, "session_id": session_id}
        ).sort("created_at", -1).limit(8).to_list(8)
        history.reverse()

        async def _stream_with_disconnect_guard():
            """Wrap the agent generator so we stop as soon as the client disconnects.

            Without this guard the Gemini/OpenAI tool loop keeps running — and
            spending API quota — after the user closes the tab or navigates away.
            We check ``request.is_disconnected()`` before each event rather than
            polling in a background task so there is no threading overhead.
            """
            gen = run_copilot_agent(
                message=message,
                history=history,
                db=db,
                user_id=user_id,
                session_id=session_id,
                model=payload.model,
                confirm=payload.confirm,
            )
            async for chunk in gen:
                if await request.is_disconnected():
                    logger.info("copilot SSE: client disconnected, aborting stream for user %s", user_id)
                    break
                yield chunk

        return StreamingResponse(
            _stream_with_disconnect_guard(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @router.get("/account")
    async def copilot_account():
        """Read-only paper account snapshot. No auth required — it's the shared
        paper account the copilot operates, so the UI can always display it."""
        from vnext.alpaca_client import get_account, is_alpaca_configured
        if not is_alpaca_configured():
            raise HTTPException(503, "Alpaca is not configured.")
        acct = await asyncio.to_thread(get_account)
        if not acct:
            raise HTTPException(502, "Unable to fetch account from Alpaca.")
        return {"item": acct}

    @router.get("/positions")
    async def copilot_positions():
        """Read-only open positions for the shared paper account."""
        from vnext.alpaca_client import get_positions
        positions = await asyncio.to_thread(get_positions)
        return {"items": positions, "total": len(positions)}

    @router.get("/positions/enriched")
    async def copilot_positions_enriched():
        """Positions enriched with sector, analyst consensus, % of equity, and a
        short price history for a sparkline."""
        import copilot_enrich
        return await copilot_enrich.enrich_positions()

    @router.post("/trades/{pid}/approve")
    async def copilot_trade_approve(pid: str, request: Request):
        """Execute a staged trade after explicit user approval (confirm mode)."""
        import copilot_trades
        user_id = await _resolve_user_id_required(request)
        result = await copilot_trades.execute_pending(db, user_id, pid)
        return {"item": result}

    @router.post("/trades/{pid}/reject")
    async def copilot_trade_reject(pid: str, request: Request):
        import copilot_trades
        user_id = await _resolve_user_id_required(request)
        return await copilot_trades.reject_pending(db, user_id, pid)

    @router.get("/models")
    async def copilot_models_list():
        """Selectable models, gated by which provider keys are configured."""
        import copilot_models
        return {"items": copilot_models.available_models(), "default": copilot_models.DEFAULT_KEY}

    @router.get("/memory")
    async def copilot_memory_list(request: Request):
        """What the agent remembers about this user (long-term, cross-session)."""
        import copilot_memory
        user_id = await _resolve_user_id_required(request)
        items = await copilot_memory.get_all(user_id)
        return {"items": items}

    @router.delete("/memory")
    async def copilot_memory_clear(request: Request):
        import copilot_memory
        user_id = await _resolve_user_id_required(request)
        ok = await copilot_memory.delete_all(user_id)
        return {"ok": ok}

    @router.delete("/memory/{mem_id}")
    async def copilot_memory_forget(mem_id: str, request: Request):
        import copilot_memory
        user_id = await _resolve_user_id_required(request)
        ok = await copilot_memory.delete(user_id, mem_id)
        return {"ok": ok}

    # ------------------------------------------------------------------
    # Standing agents (scheduled autonomous runs)
    # ------------------------------------------------------------------
    @router.get("/agents")
    async def standing_list(request: Request):
        import copilot_standing
        user_id = await _resolve_user_id(request)
        return {"items": await copilot_standing.list_agents(db, user_id),
                "max_active": copilot_standing.MAX_ACTIVE_PER_USER}

    @router.post("/agents")
    async def standing_create(payload: StandingAgentCreate, request: Request):
        import copilot_standing
        user_id = await _resolve_user_id_required(request)
        res = await copilot_standing.create_agent(
            db, user_id, name=payload.name, instruction=payload.instruction,
            interval_minutes=payload.interval_minutes, model=payload.model)
        if not res.get("ok"):
            raise HTTPException(400, res.get("error", "Could not create agent."))
        return res

    @router.put("/agents/{agent_id}")
    async def standing_update(agent_id: str, payload: StandingAgentUpdate, request: Request):
        import copilot_standing
        user_id = await _resolve_user_id_required(request)
        return await copilot_standing.update_agent(db, user_id, agent_id, payload.model_dump(exclude_none=True))

    @router.delete("/agents/{agent_id}")
    async def standing_delete(agent_id: str, request: Request):
        import copilot_standing
        user_id = await _resolve_user_id_required(request)
        return await copilot_standing.delete_agent(db, user_id, agent_id)

    @router.post("/agents/{agent_id}/run")
    async def standing_run_now(agent_id: str, request: Request):
        import copilot_standing
        user_id = await _resolve_user_id_required(request)
        return await copilot_standing.run_now(db, user_id, agent_id)

    @router.get("/trades")
    async def copilot_trades(request: Request, limit: int = 25):
        """Recent trades the agent has executed (for the activity history)."""
        user_id = await _resolve_user_id(request)
        rows = await db.copilot_trade_log.find(
            {"user_id": user_id}, {"_id": 0}
        ).sort("timestamp", -1).limit(min(limit, 100)).to_list(min(limit, 100))
        return {"items": rows}

    return router
