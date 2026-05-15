"""TradeProposal lifecycle: the heart of the human-in-the-loop pattern.

A TradeProposal is produced by pilot_engine and stored in Mongo. It carries
the full glass-box trace — debate transcript, signal scores at proposal time,
risk verdict, catalyst stress test if any — so the UI can render every reason
the AI gave for wanting this trade.

States:
    pending      -> waiting for the user to approve / reject (auto-expires at end of NY trading day)
    approved     -> user clicked Approve; pilot_engine will submit the order
    executed     -> Alpaca fill confirmed
    rejected     -> user clicked Reject (with optional reason)
    expired      -> deadline passed before user acted
    failed       -> approved but Alpaca order failed (network, rejected, etc.)

Audit events are appended to `pilot_audit_events` on every transition.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROPOSAL_COLLECTION = "pilot_trade_proposals"
AUDIT_COLLECTION = "pilot_audit_events"


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTED = "executed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


# Terminal states cannot be changed
TERMINAL_STATES = {
    ProposalStatus.EXECUTED,
    ProposalStatus.REJECTED,
    ProposalStatus.EXPIRED,
    ProposalStatus.FAILED,
}


@dataclass
class TradeProposal:
    """One proposed trade with its full reasoning trace."""
    id: str
    user_id: str
    personality_id: str
    personality_name: str

    # Order intent
    ticker: str
    side: str                          # "buy" | "sell"
    qty: float
    order_type: str = "market"         # "market" | "limit"
    limit_price: Optional[float] = None
    time_in_force: str = "day"

    # Pricing context at proposal time
    quote_price: float = 0.0
    proposed_notional: float = 0.0
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None

    # Reasoning trace
    thesis: str = ""
    conviction: int = 0                # 1..10
    debate_transcript: List[Dict[str, Any]] = field(default_factory=list)
    signal_snapshot: Dict[str, Any] = field(default_factory=dict)
    risk_verdict: Dict[str, Any] = field(default_factory=dict)
    policy_verdict: Dict[str, Any] = field(default_factory=dict)
    catalyst_stress_test: Optional[Dict[str, Any]] = None
    agent_trace: List[Dict[str, Any]] = field(default_factory=list)
    invalidation: str = ""             # condition that kills the thesis
    dissent_summary: str = ""

    # Lifecycle
    status: str = ProposalStatus.PENDING.value
    status_reason: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = ""
    decided_at: Optional[str] = None
    decided_by: Optional[str] = None
    executed_at: Optional[str] = None

    # Execution result
    alpaca_account_id: Optional[str] = None
    alpaca_order_id: Optional[str] = None
    fill_price: Optional[float] = None
    fill_qty: Optional[float] = None

    # Replay
    spec_hash: Optional[str] = None    # If this proposal came from a backtested spec

    def __post_init__(self) -> None:
        self.ticker = (self.ticker or "").strip().upper()
        if self.side not in {"buy", "sell"}:
            raise ValueError(f"side must be 'buy' or 'sell'; got {self.side!r}")
        if self.qty <= 0:
            raise ValueError(f"qty must be positive; got {self.qty}")
        if not self.expires_at:
            self.expires_at = default_expiry_iso()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "TradeProposal":
        return TradeProposal(**{k: v for k, v in data.items() if k in TradeProposal.__dataclass_fields__})

    @property
    def is_terminal(self) -> bool:
        return ProposalStatus(self.status) in TERMINAL_STATES


def default_expiry_iso() -> str:
    """End of US trading day in UTC, or 24h from now if it's already past close.

    Crude heuristic — we don't ship a holiday calendar in V1, so weekends just
    fall through to 24h. Good enough for paper-mode V1.
    """
    now = datetime.now(timezone.utc)
    # NY market closes at 16:00 ET. In UTC during EDT that's 20:00; during EST 21:00.
    # We pick 21:00 UTC as the safe-side cutoff.
    today_close = now.replace(hour=21, minute=0, second=0, microsecond=0)
    if now >= today_close - timedelta(minutes=5):
        return (now + timedelta(hours=24)).isoformat()
    return today_close.isoformat()


# ---------------------------------------------------------------------------
# CRUD + lifecycle
# ---------------------------------------------------------------------------
async def create_proposal(db: Any, proposal: TradeProposal) -> TradeProposal:
    coll = db[PROPOSAL_COLLECTION]
    if not proposal.id:
        proposal.id = str(uuid.uuid4())
    await coll.insert_one(proposal.to_dict())
    await _audit(db, proposal, "created", {"actor": "pilot_engine"})
    return proposal


async def get_proposal(db: Any, proposal_id: str) -> Optional[TradeProposal]:
    coll = db[PROPOSAL_COLLECTION]
    doc = await coll.find_one({"id": proposal_id})
    if not doc:
        return None
    doc.pop("_id", None)
    return TradeProposal.from_dict(doc)


async def list_proposals(
    db: Any,
    *,
    user_id: Optional[str] = None,
    personality_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[TradeProposal]:
    coll = db[PROPOSAL_COLLECTION]
    query: Dict[str, Any] = {}
    if user_id:
        query["user_id"] = user_id
    if personality_id:
        query["personality_id"] = personality_id
    if status:
        query["status"] = status
    cursor = coll.find(query).sort("created_at", -1).limit(limit)
    items: List[TradeProposal] = []
    async for doc in cursor:
        doc.pop("_id", None)
        try:
            items.append(TradeProposal.from_dict(doc))
        except Exception as exc:
            logger.warning(f"Skipping malformed proposal {doc.get('id')!r}: {exc}")
    return items


async def update_proposal_status(
    db: Any,
    proposal_id: str,
    *,
    new_status: ProposalStatus,
    actor: str,
    reason: Optional[str] = None,
    alpaca_order_id: Optional[str] = None,
    fill_price: Optional[float] = None,
    fill_qty: Optional[float] = None,
) -> Optional[TradeProposal]:
    """Transition a proposal. Terminal states cannot be re-transitioned.

    Returns the updated proposal, or None if not found / illegal transition.
    """
    proposal = await get_proposal(db, proposal_id)
    if proposal is None:
        return None
    current = ProposalStatus(proposal.status)
    if current in TERMINAL_STATES:
        logger.info(f"Refusing to transition terminal proposal {proposal_id} ({current.value} -> {new_status.value})")
        return proposal

    now_iso = datetime.now(timezone.utc).isoformat()
    update: Dict[str, Any] = {
        "status": new_status.value,
        "status_reason": reason,
    }

    if new_status in {ProposalStatus.APPROVED, ProposalStatus.REJECTED}:
        update["decided_at"] = now_iso
        update["decided_by"] = actor
    if new_status == ProposalStatus.EXECUTED:
        update["executed_at"] = now_iso
        if alpaca_order_id:
            update["alpaca_order_id"] = alpaca_order_id
        if fill_price is not None:
            update["fill_price"] = fill_price
        if fill_qty is not None:
            update["fill_qty"] = fill_qty
    if new_status == ProposalStatus.FAILED:
        update["decided_at"] = now_iso
        update["decided_by"] = actor

    coll = db[PROPOSAL_COLLECTION]
    await coll.update_one({"id": proposal_id}, {"$set": update})

    refreshed = await get_proposal(db, proposal_id)
    if refreshed is None:
        return None
    await _audit(
        db,
        refreshed,
        f"status:{new_status.value}",
        {"actor": actor, "reason": reason, "alpaca_order_id": alpaca_order_id},
    )
    return refreshed


async def expire_overdue_proposals(db: Any) -> int:
    """Sweep: any pending proposal past its expiry becomes EXPIRED. Idempotent."""
    coll = db[PROPOSAL_COLLECTION]
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor = coll.find({"status": ProposalStatus.PENDING.value, "expires_at": {"$lt": now_iso}})
    expired_ids: List[str] = []
    async for doc in cursor:
        expired_ids.append(doc["id"])
    for pid in expired_ids:
        await update_proposal_status(
            db,
            pid,
            new_status=ProposalStatus.EXPIRED,
            actor="system:expiry_sweep",
            reason="Approval window elapsed.",
        )
    return len(expired_ids)


# ---------------------------------------------------------------------------
# Audit log (immutable, append-only)
# ---------------------------------------------------------------------------
async def _audit(
    db: Any,
    proposal: TradeProposal,
    event_type: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    coll = db[AUDIT_COLLECTION]
    event = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "proposal_id": proposal.id,
        "user_id": proposal.user_id,
        "personality_id": proposal.personality_id,
        "ticker": proposal.ticker,
        "event_type": event_type,
        "status": proposal.status,
        "payload": payload or {},
    }
    try:
        await coll.insert_one(event)
    except Exception as exc:
        logger.error(f"Audit write failed (this should never happen): {exc}")


async def list_audit_events_for_proposal(db: Any, proposal_id: str) -> List[Dict[str, Any]]:
    coll = db[AUDIT_COLLECTION]
    cursor = coll.find({"proposal_id": proposal_id}).sort("timestamp", 1)
    events: List[Dict[str, Any]] = []
    async for doc in cursor:
        doc.pop("_id", None)
        events.append(doc)
    return events
