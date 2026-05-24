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


class CopilotChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = None
    model: Optional[str] = None


def build_copilot_router(db, get_current_user: Callable[[Request], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/copilot", tags=["copilot"])

    async def _resolve_user_id(request: Request) -> str:
        user = await get_current_user(request)
        return user["user_id"] if user else "local-copilot"

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
        message = "".join(c for c in payload.message if c.isprintable())
        user_id = await _resolve_user_id(request)
        session_id = payload.session_id or str(uuid.uuid4())

        history = await db.copilot_messages.find(
            {"user_id": user_id, "session_id": session_id}
        ).sort("created_at", -1).limit(8).to_list(8)
        history.reverse()

        return StreamingResponse(
            run_copilot_agent(
                message=message,
                history=history,
                db=db,
                user_id=user_id,
                session_id=session_id,
                model=payload.model,
            ),
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

    @router.get("/models")
    async def copilot_models_list():
        """Selectable models, gated by which provider keys are configured."""
        import copilot_models
        return {"items": copilot_models.available_models(), "default": copilot_models.DEFAULT_KEY}

    @router.get("/memory")
    async def copilot_memory_list(request: Request):
        """What the agent remembers about this user (long-term, cross-session)."""
        import copilot_memory
        user_id = await _resolve_user_id(request)
        items = await copilot_memory.get_all(user_id)
        return {"items": items}

    @router.delete("/memory")
    async def copilot_memory_clear(request: Request):
        import copilot_memory
        user_id = await _resolve_user_id(request)
        ok = await copilot_memory.delete_all(user_id)
        return {"ok": ok}

    @router.delete("/memory/{mem_id}")
    async def copilot_memory_forget(mem_id: str, request: Request):
        import copilot_memory
        user_id = await _resolve_user_id(request)
        ok = await copilot_memory.delete(user_id, mem_id)
        return {"ok": ok}

    @router.get("/trades")
    async def copilot_trades(request: Request, limit: int = 25):
        """Recent trades the agent has executed (for the activity history)."""
        user_id = await _resolve_user_id(request)
        rows = await db.copilot_trade_log.find(
            {"user_id": user_id}, {"_id": 0}
        ).sort("timestamp", -1).limit(min(limit, 100)).to_list(min(limit, 100))
        return {"items": rows}

    return router
