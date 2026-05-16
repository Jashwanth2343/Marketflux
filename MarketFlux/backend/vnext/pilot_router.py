"""FastAPI router for the Pilot subsystem (AI Portfolio Manager).

Endpoints follow existing MarketFlux conventions:
  - Mounted with prefix /api/pilot
  - Auth via `get_current_user(request)` -> user dict (or None)
  - Mongo `db` passed in at construction

The router is intentionally thin: it delegates all logic to pilot/* modules.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

from .pilot import (
    Personality,
    PersonalityRiskPolicy,
    ProposalStatus,
    SEED_PERSONALITIES,
    apply_user_override,
    delete_personality,
    expire_overdue_proposals,
    get_personality,
    list_personalities,
    set_paused,
    upsert_personality,
)
from .pilot.pilot_engine import (
    emergency_stop,
    execute_approved,
    list_activity_events,
    propose_trades,
)
from .pilot.personality import (
    PERSONALITY_COLLECTION,
    SYSTEM_USER_ID,
    clone_seed_for_user,
    ensure_seed_personalities,
    get_personality_by_slug,
    set_visibility,
)
from .pilot.trade_proposals import (
    AUDIT_COLLECTION,
    get_proposal,
    list_audit_events_for_proposal,
    list_proposals,
    update_proposal_status,
)
from .pilot.reflection import (
    compute_leaderboard,
    detect_thesis_drift,
    generate_journal_entry,
    list_drift_flags,
    list_journal_entries,
)
from .pilot.memory import (
    get_memory_stats,
    record_lesson,
    record_regime_context,
    record_user_note,
    retrieve_context,
)

logger = logging.getLogger(__name__)

CONSENT_COLLECTION = "pilot_user_consent"


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------
class PersonalityCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    mandate: str = Field(min_length=10, max_length=2000)
    universe: List[str] = Field(min_length=1, max_length=200)
    signal_weights: dict
    risk_policy: dict = Field(default_factory=dict)
    cadence: str = Field(default="daily")
    initial_capital_usd: float = Field(default=25_000.0, gt=0, le=10_000_000)
    accent_color: str = Field(default="#22c55e")
    avatar_glyph: str = Field(default="circle")


class PersonalityUpdateRequest(BaseModel):
    name: Optional[str] = None
    mandate: Optional[str] = None
    universe: Optional[List[str]] = None
    signal_weights: Optional[dict] = None
    risk_policy: Optional[dict] = None
    cadence: Optional[str] = None
    initial_capital_usd: Optional[float] = None
    accent_color: Optional[str] = None
    avatar_glyph: Optional[str] = None


class OverrideRequest(BaseModel):
    block_ticker: Optional[str] = None
    unblock_ticker: Optional[str] = None
    blackout_date: Optional[str] = None
    user_note: Optional[str] = None


class ProposalDecisionRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class ConsentRequest(BaseModel):
    accept_paper_only: bool
    accept_not_advice: bool
    accept_audit_logging: bool
    kill_phrase: Optional[str] = Field(default=None, max_length=80)


class ProposeRequest(BaseModel):
    max_candidates: int = Field(default=5, ge=1, le=20)
    dry_run: bool = Field(default=False)


class VisibilityRequest(BaseModel):
    public: bool


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------
def build_pilot_router(db, get_current_user: Callable[[Request], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/pilot", tags=["pilot"])

    async def require_user(request: Request) -> dict:
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required.")
        return user

    async def _require_consent(user_id: str) -> None:
        doc = await db[CONSENT_COLLECTION].find_one({"user_id": user_id})
        if not doc or not doc.get("accept_paper_only"):
            raise HTTPException(
                403,
                "Pilot consent required. POST /api/pilot/consent before using Pilot endpoints.",
            )

    async def _ensure_seeds_once() -> None:
        # Idempotent; safe to call on every relevant request, but we cache via a flag.
        if not getattr(router.state, "seeded", False):  # type: ignore[attr-defined]
            await ensure_seed_personalities(db)
            router.state.seeded = True  # type: ignore[attr-defined]

    # Provide a Starlette-state-like shim so we can stash a "seeded" flag.
    class _S:
        seeded = False
    router.state = _S()  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Health / status
    # ------------------------------------------------------------------
    @router.get("/status")
    async def pilot_status():
        return {
            "ok": True,
            "service": "pilot",
            "paper_only": True,
            "disclaimer": (
                "Paper trading only. Educational simulation. Not investment advice. "
                "Past simulated performance does not predict real returns."
            ),
        }

    # ------------------------------------------------------------------
    # Consent
    # ------------------------------------------------------------------
    @router.get("/consent")
    async def consent_status(request: Request):
        user = await require_user(request)
        doc = await db[CONSENT_COLLECTION].find_one({"user_id": user["user_id"]})
        if doc:
            doc.pop("_id", None)
        return {"item": doc}

    @router.post("/consent")
    async def grant_consent(request: Request, payload: ConsentRequest):
        user = await require_user(request)
        if not (payload.accept_paper_only and payload.accept_not_advice and payload.accept_audit_logging):
            raise HTTPException(422, "All three consent toggles must be true.")
        record = {
            "user_id": user["user_id"],
            "email": user.get("email"),
            "accept_paper_only": True,
            "accept_not_advice": True,
            "accept_audit_logging": True,
            "kill_phrase": (payload.kill_phrase or "").strip()[:80] or None,
            "granted_at": datetime.now(timezone.utc).isoformat(),
        }
        await db[CONSENT_COLLECTION].update_one(
            {"user_id": user["user_id"]},
            {"$set": record},
            upsert=True,
        )
        return {"item": record}

    # ------------------------------------------------------------------
    # Personalities
    # ------------------------------------------------------------------
    @router.get("/personalities")
    async def personalities_list(request: Request):
        user = await require_user(request)
        await _ensure_seeds_once()
        items = await list_personalities(db, user_id=user["user_id"])
        return {"items": [p.to_dict() for p in items]}

    @router.get("/personalities/{personality_id}")
    async def personalities_get(personality_id: str, request: Request):
        await require_user(request)
        await _ensure_seeds_once()
        p = await get_personality(db, personality_id)
        if not p:
            raise HTTPException(404, "Personality not found.")
        return {"item": p.to_dict()}

    @router.post("/personalities")
    async def personalities_create(request: Request, payload: PersonalityCreateRequest):
        user = await require_user(request)
        await _require_consent(user["user_id"])
        rp_data = payload.risk_policy or {}
        rp = PersonalityRiskPolicy(**{k: v for k, v in rp_data.items() if k in PersonalityRiskPolicy.__dataclass_fields__})
        personality = Personality(
            id="",
            user_id=user["user_id"],
            name=payload.name,
            mandate=payload.mandate,
            universe=payload.universe,
            signal_weights=payload.signal_weights,
            risk_policy=rp,
            cadence=payload.cadence,
            initial_capital_usd=payload.initial_capital_usd,
            accent_color=payload.accent_color,
            avatar_glyph=payload.avatar_glyph,
        )
        import uuid as _uuid
        personality.id = str(_uuid.uuid4())
        saved = await upsert_personality(db, personality)
        return {"item": saved.to_dict()}

    @router.put("/personalities/{personality_id}")
    async def personalities_update(personality_id: str, request: Request, payload: PersonalityUpdateRequest):
        user = await require_user(request)
        existing = await get_personality(db, personality_id)
        if not existing:
            raise HTTPException(404, "Personality not found.")
        if existing.is_seed or existing.user_id == SYSTEM_USER_ID:
            raise HTTPException(403, "Cannot edit a seed personality. Clone it first.")
        if existing.user_id != user["user_id"]:
            raise HTTPException(403, "Not your personality.")

        if payload.name is not None: existing.name = payload.name
        if payload.mandate is not None: existing.mandate = payload.mandate
        if payload.universe is not None: existing.universe = payload.universe
        if payload.signal_weights is not None: existing.signal_weights = payload.signal_weights
        if payload.cadence is not None: existing.cadence = payload.cadence
        if payload.initial_capital_usd is not None: existing.initial_capital_usd = payload.initial_capital_usd
        if payload.accent_color is not None: existing.accent_color = payload.accent_color
        if payload.avatar_glyph is not None: existing.avatar_glyph = payload.avatar_glyph
        if payload.risk_policy:
            rp = existing.risk_policy
            for k, v in payload.risk_policy.items():
                if k in PersonalityRiskPolicy.__dataclass_fields__:
                    setattr(rp, k, v)
            existing.risk_policy = rp

        # Re-run __post_init__ semantics
        existing = Personality.from_dict(existing.to_dict())
        saved = await upsert_personality(db, existing)
        return {"item": saved.to_dict()}

    @router.delete("/personalities/{personality_id}")
    async def personalities_delete(personality_id: str, request: Request):
        user = await require_user(request)
        try:
            ok = await delete_personality(db, personality_id, user_id=user["user_id"])
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        if not ok:
            raise HTTPException(404, "Personality not found.")
        return {"ok": True}

    @router.post("/personalities/{personality_id}/clone")
    async def personalities_clone(personality_id: str, request: Request):
        user = await require_user(request)
        await _require_consent(user["user_id"])
        cloned = await clone_seed_for_user(db, personality_id, user["user_id"])
        if not cloned:
            raise HTTPException(404, "Seed personality not found or not cloneable.")
        return {"item": cloned.to_dict()}

    @router.post("/personalities/{personality_id}/pause")
    async def personalities_pause(personality_id: str, request: Request):
        user = await require_user(request)
        await _require_consent(user["user_id"])
        p = await set_paused(db, personality_id, True)
        if not p:
            raise HTTPException(404, "Personality not found.")
        return {"item": p.to_dict()}

    @router.post("/personalities/{personality_id}/resume")
    async def personalities_resume(personality_id: str, request: Request):
        user = await require_user(request)
        await _require_consent(user["user_id"])
        p = await set_paused(db, personality_id, False)
        if not p:
            raise HTTPException(404, "Personality not found.")
        return {"item": p.to_dict()}

    @router.post("/personalities/{personality_id}/override")
    async def personalities_override(personality_id: str, request: Request, payload: OverrideRequest):
        user = await require_user(request)
        await _require_consent(user["user_id"])
        p = await apply_user_override(
            db,
            personality_id,
            block_ticker=payload.block_ticker,
            unblock_ticker=payload.unblock_ticker,
            blackout_date=payload.blackout_date,
            user_note=payload.user_note,
        )
        if not p:
            raise HTTPException(404, "Personality not found.")
        return {"item": p.to_dict()}

    # ------------------------------------------------------------------
    # Propose / execute / kill
    # ------------------------------------------------------------------
    @router.post("/personalities/{personality_id}/propose")
    async def personalities_propose(personality_id: str, request: Request, payload: ProposeRequest):
        user = await require_user(request)
        await _require_consent(user["user_id"])

        # FIX: Validate personality exists and guard cross-user proposals on
        # non-seed personalities. Seeds remain proposable by any consenting user
        # (they are shared templates), but a user cannot propose against another
        # user's private personality clone.
        p = await get_personality(db, personality_id)
        if not p:
            raise HTTPException(404, "Personality not found.")
        if not p.is_seed and p.user_id != user["user_id"]:
            raise HTTPException(403, "Not your personality.")

        result = await propose_trades(
            db,
            personality_id,
            user["user_id"],
            max_candidates=payload.max_candidates,
            dry_run=payload.dry_run,
        )
        if not result.get("ok"):
            # propose_trades returns ok:False for paused/blackout/etc; that's not an HTTP error.
            return result
        return result

    @router.post("/personalities/{personality_id}/kill")
    async def personalities_kill(personality_id: str, request: Request):
        user = await require_user(request)
        # Kill switch intentionally bypasses consent check — safety must always work.
        # FIX: For seed-based proposals the guard would block kill, so we look up
        # the personality first: seeds allow kill by the proposal's owner (user_id
        # on the proposal, not the personality). The _require_owned_mutable_personality
        # helper is used only for user-owned clones.
        p = await get_personality(db, personality_id)
        if not p:
            raise HTTPException(404, "Personality not found.")

        if not p.is_seed:
            # For cloned personalities, enforce ownership as before.
            if p.user_id == SYSTEM_USER_ID:
                raise HTTPException(403, "Cannot kill a system personality directly.")
            if p.user_id != user["user_id"]:
                raise HTTPException(403, "Not your personality.")

        # For seed personalities, the kill targets proposals scoped to this user —
        # emergency_stop must filter by both personality_id and user_id internally.

        # Kill switch must work even without prior consent — safety first.
        return await emergency_stop(
            db,
            personality_id,
            user["user_id"],
        )

    # ------------------------------------------------------------------
    # Proposals
    # ------------------------------------------------------------------
    @router.get("/proposals")
    async def proposals_list(
        request: Request,
        personality_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ):
        user = await require_user(request)
        items = await list_proposals(
            db,
            user_id=user["user_id"],
            personality_id=personality_id,
            status=status,
            limit=min(limit, 200),
        )
        return {"items": [p.to_dict() for p in items]}

    @router.get("/proposals/{proposal_id}")
    async def proposals_get(proposal_id: str, request: Request):
        user = await require_user(request)
        p = await get_proposal(db, proposal_id)
        if not p:
            raise HTTPException(404, "Proposal not found.")
        if p.user_id != user["user_id"]:
            raise HTTPException(403, "Not your proposal.")
        audit = await list_audit_events_for_proposal(db, proposal_id)
        return {"item": p.to_dict(), "audit": audit}

    @router.post("/proposals/{proposal_id}/approve")
    async def proposals_approve(
        proposal_id: str,
        request: Request,
        background: BackgroundTasks,
        payload: ProposalDecisionRequest = ProposalDecisionRequest(),
    ):
        user = await require_user(request)
        await _require_consent(user["user_id"])
        p = await get_proposal(db, proposal_id)
        if not p:
            raise HTTPException(404, "Proposal not found.")
        if p.user_id != user["user_id"]:
            raise HTTPException(403, "Not your proposal.")
        if p.status != ProposalStatus.PENDING.value:
            raise HTTPException(409, f"Proposal already in terminal state: {p.status}")

        updated = await update_proposal_status(
            db,
            proposal_id,
            new_status=ProposalStatus.APPROVED,
            actor=f"user:{user['user_id']}",
            reason=payload.reason,
        )

        # Dispatch execution in background (TradingClient uses configured paper account)
        background.add_task(_safe_execute, db, proposal_id, user["user_id"])

        return {"item": updated.to_dict() if updated else None, "execution_dispatched": True}

    @router.post("/proposals/{proposal_id}/reject")
    async def proposals_reject(proposal_id: str, request: Request, payload: ProposalDecisionRequest):
        user = await require_user(request)
        p = await get_proposal(db, proposal_id)
        if not p:
            raise HTTPException(404, "Proposal not found.")
        if p.user_id != user["user_id"]:
            raise HTTPException(403, "Not your proposal.")
        if p.status != ProposalStatus.PENDING.value:
            raise HTTPException(409, f"Proposal already in terminal state: {p.status}")
        updated = await update_proposal_status(
            db,
            proposal_id,
            new_status=ProposalStatus.REJECTED,
            actor=f"user:{user['user_id']}",
            reason=payload.reason or "User rejected.",
        )
        return {"item": updated.to_dict() if updated else None}

    @router.post("/sweep")
    async def proposals_sweep(request: Request):
        """Expire-overdue sweep. Idempotent. Safe to schedule on a cron / 5-min loop."""
        await require_user(request)
        count = await expire_overdue_proposals(db)
        return {"expired_count": count}

    # ------------------------------------------------------------------
    # Activity feed
    # ------------------------------------------------------------------
    @router.get("/activity")
    async def activity_list(request: Request, personality_id: Optional[str] = None, limit: int = 50):
        await require_user(request)
        items = await list_activity_events(db, personality_id=personality_id, limit=min(limit, 200))
        return {"items": items}

    # ------------------------------------------------------------------
    # Reflection: journal + drift
    # ------------------------------------------------------------------
    @router.get("/personalities/{personality_id}/journal")
    async def journal_list(personality_id: str, request: Request, limit: int = 30):
        await require_user(request)
        items = await list_journal_entries(db, personality_id=personality_id, limit=min(limit, 90))
        return {"items": items}

    @router.post("/personalities/{personality_id}/journal/generate")
    async def journal_generate(personality_id: str, request: Request):
        """On-demand journal generation (admin / debug). Idempotent per UTC date."""
        user = await require_user(request)
        await _require_consent(user["user_id"])
        entry = await generate_journal_entry(db, personality_id)
        if entry is None:
            raise HTTPException(404, "Personality not found.")
        return {"item": entry}

    @router.get("/personalities/{personality_id}/drift")
    async def drift_list(personality_id: str, request: Request):
        await require_user(request)
        items = await list_drift_flags(db, personality_id=personality_id)
        return {"items": items}

    @router.post("/personalities/{personality_id}/drift/check")
    async def drift_check_now(personality_id: str, request: Request):
        user = await require_user(request)
        await _require_consent(user["user_id"])
        flags = await detect_thesis_drift(db, personality_id)
        return {"items": flags}

    # ------------------------------------------------------------------
    # Visibility + public leaderboard + public profile
    # ------------------------------------------------------------------
    @router.post("/personalities/{personality_id}/visibility")
    async def visibility_toggle(personality_id: str, request: Request, payload: VisibilityRequest):
        user = await require_user(request)
        existing = await get_personality(db, personality_id)
        if not existing:
            raise HTTPException(404, "Personality not found.")
        if existing.is_seed or existing.user_id == SYSTEM_USER_ID:
            raise HTTPException(403, "Seed personalities are always public; can't toggle.")
        if existing.user_id != user["user_id"]:
            raise HTTPException(403, "Not your personality.")
        updated = await set_visibility(db, personality_id, payload.public)
        return {"item": updated.to_dict() if updated else None}

    @router.get("/leaderboard")
    async def leaderboard(days: int = 30, limit: int = 20):
        """Public: anonymous browsers can hit this."""
        days = max(1, min(days, 365))
        limit = max(1, min(limit, 100))
        rows = await compute_leaderboard(db, days=days, limit=limit, include_private=False)
        return {
            "items": rows,
            "window_days": days,
            "disclaimer": (
                "Paper trading only. Past simulated performance does not predict real returns."
            ),
        }

    @router.get("/public/{slug}")
    async def public_profile(slug: str):
        """Public personality profile: holdings preview + recent journal + sparkline."""
        personality = await get_personality_by_slug(db, slug)
        if personality is None:
            raise HTTPException(404, "Personality not found or not public.")
        journals = await list_journal_entries(db, personality_id=personality.id, limit=14)
        # Surface only the audit-safe fields for the public view.
        safe_personality = personality.to_dict()
        safe_personality.pop("user_id", None)
        safe_personality.pop("user_notes", None)
        return {
            "personality": safe_personality,
            "journals": journals,
            "disclaimer": (
                "Paper trading only. Not investment advice. "
                "Past simulated performance does not predict real returns."
            ),
        }

    # ------------------------------------------------------------------
    # Memory (institutional knowledge layer)
    # ------------------------------------------------------------------
    @router.get("/memory/{personality_id}")
    async def memory_retrieve(
        personality_id: str,
        request: Request,
        ticker: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20,
    ):
        user = await require_user(request)
        categories = [category] if category else None
        items = await retrieve_context(
            db,
            personality_id=personality_id,
            user_id=user["user_id"],
            ticker=ticker,
            categories=categories,
            limit=min(limit, 100),
        )
        return {"items": items, "total": len(items)}

    @router.get("/memory/{personality_id}/stats")
    async def memory_stats(personality_id: str, request: Request):
        user = await require_user(request)
        stats = await get_memory_stats(db, personality_id=personality_id, user_id=user["user_id"])
        return stats

    @router.post("/memory/{personality_id}/note")
    async def memory_add_note(personality_id: str, request: Request):
        user = await require_user(request)
        body = await request.json()
        note = body.get("note", "").strip()
        ticker = body.get("ticker")
        if not note:
            raise HTTPException(422, "note field is required.")
        entry_id = await record_user_note(
            db,
            personality_id=personality_id,
            user_id=user["user_id"],
            note=note,
            ticker=ticker,
        )
        return {"id": entry_id, "message": "Note saved to permanent memory."}

    @router.post("/memory/{personality_id}/lesson")
    async def memory_add_lesson(personality_id: str, request: Request):
        user = await require_user(request)
        body = await request.json()
        lesson = body.get("lesson", "").strip()
        ticker = body.get("ticker")
        source = body.get("source", "user")
        if not lesson:
            raise HTTPException(422, "lesson field is required.")
        entry_id = await record_lesson(
            db,
            personality_id=personality_id,
            user_id=user["user_id"],
            lesson=lesson,
            ticker=ticker,
            source=source,
        )
        return {"id": entry_id, "message": "Lesson saved to permanent memory."}

    @router.post("/memory/{personality_id}/regime")
    async def memory_set_regime(personality_id: str, request: Request):
        user = await require_user(request)
        body = await request.json()
        label = body.get("regime_label", "").strip()
        details = body.get("details", "")
        tickers = body.get("tickers_affected")
        if not label:
            raise HTTPException(422, "regime_label field is required.")
        entry_id = await record_regime_context(
            db,
            personality_id=personality_id,
            user_id=user["user_id"],
            regime_label=label,
            details=details,
            tickers_affected=tickers,
        )
        return {"id": entry_id, "message": f"Regime '{label}' recorded."}

    return router


async def _safe_execute(db, proposal_id: str, user_id: str) -> None:
    """Background task wrapper that swallows + logs exceptions."""
    try:
        await execute_approved(db, proposal_id, user_id)
    except Exception as exc:
        logger.exception(f"pilot background execute failed for proposal {proposal_id}: {exc}")
