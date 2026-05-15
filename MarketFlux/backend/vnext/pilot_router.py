"""FastAPI router for the Pilot subsystem (AI Portfolio Manager).

Endpoints follow existing MarketFlux conventions:
  - Mounted with prefix /api/pilot
  - Auth via `get_current_user(request)` -> user dict (or None)
  - Mongo `db` passed in at construction

The router is intentionally thin: it delegates all logic to pilot/* modules.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

from .alpaca_client import create_trading_account, is_alpaca_configured
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
)
from .pilot.trade_proposals import (
    AUDIT_COLLECTION,
    get_proposal,
    list_audit_events_for_proposal,
    list_proposals,
    update_proposal_status,
)

logger = logging.getLogger(__name__)

CONSENT_COLLECTION = "pilot_user_consent"
PROPOSALS_COLLECTION = "pilot_trade_proposals"


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

    async def _require_owned_mutable_personality(personality_id: str, user_id: str) -> Personality:
        """Return a personality only if this user may mutate it.

        Seed personalities are shared system records, so user-specific controls
        like pause/resume/override/kill must be performed on a clone instead.
        """
        p = await get_personality(db, personality_id)
        if not p:
            raise HTTPException(404, "Personality not found.")
        if p.is_seed or p.user_id == SYSTEM_USER_ID:
            raise HTTPException(403, "Cannot mutate a seed personality. Clone it first.")
        if p.user_id != user_id:
            raise HTTPException(403, "Not your personality.")
        return p

    async def _get_or_create_alpaca_account(user: dict) -> str:
        """Get or provision the user's Alpaca paper account before approval.

        Uses $setOnInsert to guard against concurrent first-time provisioning:
        only the first writer wins; subsequent concurrent calls will find the
        already-written account_id on re-fetch.
        """
        user_id = user["user_id"]

        # Fast path: already provisioned.
        user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "alpaca_account_id": 1})
        alpaca_account_id = (user_doc or {}).get("alpaca_account_id")
        if alpaca_account_id:
            return alpaca_account_id

        if not is_alpaca_configured():
            raise HTTPException(
                503,
                "Alpaca Broker API is not configured. Contact support to enable paper trading.",
            )

        # Build name parts — handle single-name or missing name gracefully.
        name_parts = str(user.get("name") or "").split()
        given_name = name_parts[0] if name_parts else "Paper"
        # For single-name users, use the same value for family_name rather than a
        # hardcoded placeholder that could confuse Alpaca's KYC process.
        family_name = name_parts[-1] if len(name_parts) > 1 else given_name
        email = user.get("email") or f"{user_id}@marketflux.paper"

        try:
            result = await asyncio.to_thread(
                create_trading_account,
                given_name=given_name,
                family_name=family_name,
                email=email,
            )
        except Exception as exc:
            logger.error("Alpaca create_trading_account raised for user %s: %s", user_id, exc, exc_info=True)
            raise HTTPException(503, "Could not reach Alpaca Broker API. Please retry.")

        if not result or not result.get("account_id"):
            raise HTTPException(
                503,
                "Alpaca account creation failed (no account_id returned). Please retry approval.",
            )

        new_account_id = result["account_id"]

        # Use $setOnInsert so concurrent first-time calls don't clobber each other.
        # If another request already wrote the account_id, find_one_and_update returns
        # the existing doc and we discard new_account_id safely.
        final_doc = await db.users.find_one_and_update(
            {"user_id": user_id, "alpaca_account_id": {"$exists": False}},
            {"$set": {"alpaca_account_id": new_account_id}},
            upsert=False,
            return_document=True,
        )

        if final_doc is None:
            # Another concurrent request already wrote an account_id — re-fetch it.
            user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "alpaca_account_id": 1})
            alpaca_account_id = (user_doc or {}).get("alpaca_account_id")
            if not alpaca_account_id:
                # Extremely unlikely — upsert the one we just created.
                await db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"alpaca_account_id": new_account_id}},
                    upsert=True,
                )
                return new_account_id
            return alpaca_account_id

        return new_account_id

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
        await _require_owned_mutable_personality(personality_id, user["user_id"])
        p = await set_paused(db, personality_id, True)
        return {"item": p.to_dict() if p else None}

    @router.post("/personalities/{personality_id}/resume")
    async def personalities_resume(personality_id: str, request: Request):
        user = await require_user(request)
        await _require_consent(user["user_id"])
        await _require_owned_mutable_personality(personality_id, user["user_id"])
        p = await set_paused(db, personality_id, False)
        return {"item": p.to_dict() if p else None}

    @router.post("/personalities/{personality_id}/override")
    async def personalities_override(personality_id: str, request: Request, payload: OverrideRequest):
        user = await require_user(request)
        await _require_consent(user["user_id"])
        await _require_owned_mutable_personality(personality_id, user["user_id"])
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

        user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "alpaca_account_id": 1})
        alpaca_account_id = (user_doc or {}).get("alpaca_account_id")
        if alpaca_account_id is None:
            logger.warning(
                "personalities_kill called for user %s with no alpaca_account_id; "
                "emergency_stop will proceed without cancelling broker orders.",
                user["user_id"],
            )

        return await emergency_stop(
            db,
            personality_id,
            user["user_id"],
            alpaca_account_id=alpaca_account_id,
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

        # Provision the paper account before the atomic status transition.
        # If account creation fails, the proposal stays PENDING and the user can retry.
        alpaca_account_id = await _get_or_create_alpaca_account(user)

        # FIX: Use an atomic compare-and-swap via find_one_and_update to prevent
        # double-execution from concurrent approve requests. update_proposal_status
        # must perform this atomically; if it returns None the race was lost.
        updated = await update_proposal_status(
            db,
            proposal_id,
            new_status=ProposalStatus.APPROVED,
            actor=f"user:{user['user_id']}",
            reason=payload.reason,
            # Guard: only update if still PENDING (atomic CAS)
            current_status=ProposalStatus.PENDING.value,
        )

        # FIX: If update_proposal_status returns None, the proposal was already
        # transitioned by a concurrent request — do not dispatch execution again.
        if not updated:
            raise HTTPException(
                409,
                "Proposal was already approved by a concurrent request. "
                "Check /api/pilot/proposals/{id} for current status.",
            )

        # FIX: Consolidate the alpaca_account_id write into the same logical
        # operation by updating the proposal doc we just approved.
        await db[PROPOSALS_COLLECTION].update_one(
            {"id": proposal_id},
            {"$set": {"alpaca_account_id": alpaca_account_id}},
        )

        background.add_task(_safe_execute, db, proposal_id, user["user_id"], alpaca_account_id)

        return {"item": updated.to_dict(), "execution_dispatched": True}

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

    return router


async def _safe_execute(db, proposal_id: str, user_id: str, alpaca_account_id: Optional[str]) -> None:
    """Background task wrapper that swallows + logs exceptions."""
    try:
        await execute_approved(db, proposal_id, user_id, alpaca_account_id=alpaca_account_id)
    except Exception as exc:
        logger.exception("pilot background execute failed for proposal %s: %s", proposal_id, exc)
