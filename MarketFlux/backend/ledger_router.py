"""FastAPI router for the Conviction Ledger. Mounted at /api/ledger.

Read endpoints resolve the user like the rest of the app (anonymous local use
falls back to the shared id); writes require auth in production. The grading
endpoint is machine-facing: it's called by the nightly GitHub Actions cron and
is gated by a shared-secret header instead of a user session.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

import conviction_ledger as ledger

logger = logging.getLogger(__name__)

_ANON_ID = "local-copilot"


class ThesisCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    direction: str = Field(default="long")
    rationale: str = Field(min_length=5, max_length=8000)
    agent_id: str = Field(default="human", max_length=64)
    entry_price: Optional[float] = Field(default=None, gt=0)
    composite_score: Optional[float] = None
    price_target: Optional[float] = Field(default=None, gt=0)
    invalidation_price: Optional[float] = Field(default=None, gt=0)
    invalidation_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    invalidation_score_floor: Optional[float] = None
    invalidation_notes: str = Field(default="", max_length=1000)


def build_ledger_router(db, get_current_user: Callable[[Request], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/ledger", tags=["ledger"])

    async def _resolve_user_id_required(request: Request) -> str:
        """Reads AND writes require auth in production: theses are personal
        records, and letting anonymous traffic share the local fallback id
        would leak one anonymous user's ledger to another. Local/dev keeps
        the shared id so the app works without login."""
        user = await get_current_user(request)
        if user:
            return user["user_id"]
        # Require auth by default; only allow the anon fallback when explicitly
        # running in local dev mode so a missing NODE_ENV in a deployed env never
        # leaks one anonymous user's ledger to another.
        if os.environ.get("NODE_ENV", "").lower() not in ("development", "dev"):
            raise HTTPException(401, "Authentication required for this endpoint.")
        return _ANON_ID

    @router.get("/theses")
    async def theses_list(request: Request, status: Optional[str] = None,
                          agent_id: Optional[str] = None, limit: int = 200):
        user_id = await _resolve_user_id_required(request)
        items = await ledger.list_theses(db, user_id, status=status,
                                         agent_id=agent_id, limit=limit)
        return {"items": items, "count": len(items)}

    @router.post("/theses")
    async def thesis_create(payload: ThesisCreate, request: Request):
        user_id = await _resolve_user_id_required(request)
        res = await ledger.create_thesis(
            db, user_id=user_id, agent_id=payload.agent_id, ticker=payload.ticker,
            direction=payload.direction, rationale=payload.rationale, source="manual",
            entry_price=payload.entry_price, composite_score=payload.composite_score,
            price_target=payload.price_target,
            invalidation_price=payload.invalidation_price,
            invalidation_date=payload.invalidation_date,
            invalidation_score_floor=payload.invalidation_score_floor,
            invalidation_notes=payload.invalidation_notes,
        )
        if not res.get("ok"):
            raise HTTPException(400, res.get("error", "Could not create thesis."))
        return res

    @router.post("/theses/{thesis_id}/close")
    async def thesis_close(thesis_id: str, request: Request):
        user_id = await _resolve_user_id_required(request)
        res = await ledger.close_thesis(db, user_id, thesis_id, reason="manual")
        if not res.get("ok"):
            raise HTTPException(400, res.get("error", "Could not close thesis."))
        return res

    @router.get("/stats")
    async def ledger_stats(request: Request):
        user_id = await _resolve_user_id_required(request)
        return await ledger.get_stats(db, user_id)

    @router.get("/audit/{thesis_id}")
    async def thesis_audit(thesis_id: str, request: Request):
        user_id = await _resolve_user_id_required(request)
        t = await db[ledger.COLLECTION].find_one({"id": thesis_id, "user_id": user_id})
        if not t:
            raise HTTPException(404, "thesis not found")
        rows = await db[ledger.AUDIT_COLLECTION].find(
            {"thesis_id": thesis_id}, {"_id": 0}).sort("at", 1).to_list(200)
        return {"items": rows}

    @router.post("/grade")
    async def ledger_grade(x_grade_token: str = Header(default="")):
        """Nightly grading chokepoint (machine-facing, cron-called).

        Gated by the X-Grade-Token shared secret. In production a missing
        LEDGER_GRADE_TOKEN env means the endpoint is disabled outright rather
        than open. Local/dev without the env var allows manual runs.
        """
        expected = os.environ.get("LEDGER_GRADE_TOKEN", "")
        prod = os.environ.get("NODE_ENV", "").lower() == "production"
        if expected:
            if x_grade_token != expected:
                raise HTTPException(401, "bad grade token")
        elif prod:
            raise HTTPException(503, "LEDGER_GRADE_TOKEN is not configured.")
        return await ledger.grade_all(db)

    return router
