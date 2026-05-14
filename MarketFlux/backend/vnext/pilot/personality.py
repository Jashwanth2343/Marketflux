"""Personality: an AI Portfolio Manager you can hire.

A Personality is a named, structured policy object that the Pilot orchestrator
reads before every decision. It bundles:

  - mandate: one paragraph of plain English the Lead PM agent re-reads on
    every cycle. Drives style and conviction.
  - signal_weights: overrides for signal_engine.py CATEGORY_WEIGHTS. Keys must
    sum to ~1.0; the engine renormalizes on load.
  - risk_policy: maps directly to vnext/policy_engine.py params.
  - universe: explicit ticker list (V1 keeps it concrete; later we can support
    presets like 'sp500_top100').
  - cadence: how often the Pilot scans this personality.
  - paused: master kill flag.
  - overrides: per-ticker blocks and date blackouts ("don't touch NVDA",
    "no trades next Tuesday").

Seed personalities (Atlas, Sage, Vega) are stored as `user_id="system"` and
clonable by any user.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

PERSONALITY_COLLECTION = "pilot_personalities"
SYSTEM_USER_ID = "system"

CADENCES = {"intraday", "daily", "weekly"}


@dataclass
class PersonalityRiskPolicy:
    """Risk parameters that flow into vnext/policy_engine.py evaluations.

    Field names mirror the rule_types in policy_engine.evaluate_paper_trade()
    so we can serialize this object straight into the policy's
    `effective_policies` dict.
    """
    max_position_pct: float = 8.0           # % of book per single position
    max_gross_exposure_pct: float = 100.0   # % of book invested at once
    max_single_name_concentration: float = 15.0
    max_open_trades: int = 10
    min_confidence_to_trade: float = 60.0   # composite score floor
    block_during_earnings_window: bool = True
    earnings_blackout_days_before: int = 2
    earnings_blackout_days_after: int = 1
    daily_loss_circuit_breaker_pct: float = 3.0  # halt new trades after -X% day
    vix_max_for_new_trades: float = 40.0
    no_live_trading: bool = True            # paper-only enforcement

    def to_policy_engine_dict(self) -> Dict[str, Dict[str, Any]]:
        """Render for policy_engine.evaluate_paper_trade()'s effective_policies."""
        return {
            "max_position_pct": {
                "enabled": True,
                "params": {"value": self.max_position_pct},
            },
            "max_gross_exposure_pct": {
                "enabled": True,
                "params": {"value": self.max_gross_exposure_pct},
            },
            "max_single_name_concentration": {
                "enabled": True,
                "params": {"value": self.max_single_name_concentration},
            },
            "max_open_trades": {
                "enabled": True,
                "params": {"value": self.max_open_trades},
            },
            "min_confidence_to_trade": {
                "enabled": True,
                "params": {"value": self.min_confidence_to_trade},
            },
            "block_during_earnings_window": {
                "enabled": self.block_during_earnings_window,
                "params": {
                    "days_before": self.earnings_blackout_days_before,
                    "days_after": self.earnings_blackout_days_after,
                },
            },
            "no_live_trading": {
                "enabled": self.no_live_trading,
                "params": {},
            },
        }


@dataclass
class Personality:
    """A single AI portfolio manager. Owned by `user_id` (or 'system' for seeds)."""
    id: str
    user_id: str
    name: str
    mandate: str
    universe: List[str]
    signal_weights: Dict[str, float]
    risk_policy: PersonalityRiskPolicy
    cadence: str = "daily"
    initial_capital_usd: float = 25_000.0
    paused: bool = False
    blocked_tickers: List[str] = field(default_factory=list)
    blackout_dates: List[str] = field(default_factory=list)
    user_notes: List[str] = field(default_factory=list)
    avatar_glyph: str = "circle"          # UI hint
    accent_color: str = "#22c55e"         # UI hint (tailwind green-500)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_seed: bool = False
    version: int = 1

    def __post_init__(self) -> None:
        if self.cadence not in CADENCES:
            raise ValueError(f"cadence must be one of {sorted(CADENCES)}; got {self.cadence!r}")
        self.universe = sorted({t.strip().upper() for t in self.universe if t and t.strip()})
        self.blocked_tickers = sorted({t.strip().upper() for t in self.blocked_tickers if t and t.strip()})
        s = sum(self.signal_weights.values()) or 1.0
        self.signal_weights = {k: round(v / s, 4) for k, v in self.signal_weights.items()}

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["risk_policy"] = asdict(self.risk_policy)
        return d

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Personality":
        rp_data = data.get("risk_policy") or {}
        rp = PersonalityRiskPolicy(**{k: v for k, v in rp_data.items() if k in PersonalityRiskPolicy.__dataclass_fields__})
        return Personality(
            id=str(data.get("id") or uuid.uuid4()),
            user_id=str(data.get("user_id", SYSTEM_USER_ID)),
            name=str(data["name"]).strip(),
            mandate=str(data["mandate"]).strip(),
            universe=list(data.get("universe") or []),
            signal_weights=dict(data.get("signal_weights") or {}),
            risk_policy=rp,
            cadence=str(data.get("cadence", "daily")),
            initial_capital_usd=float(data.get("initial_capital_usd", 25_000.0)),
            paused=bool(data.get("paused", False)),
            blocked_tickers=list(data.get("blocked_tickers") or []),
            blackout_dates=list(data.get("blackout_dates") or []),
            user_notes=list(data.get("user_notes") or []),
            avatar_glyph=str(data.get("avatar_glyph", "circle")),
            accent_color=str(data.get("accent_color", "#22c55e")),
            created_at=str(data.get("created_at") or datetime.now(timezone.utc).isoformat()),
            updated_at=str(data.get("updated_at") or datetime.now(timezone.utc).isoformat()),
            is_seed=bool(data.get("is_seed", False)),
            version=int(data.get("version", 1)),
        )

    def is_blocked(self, ticker: str) -> bool:
        return ticker.upper() in self.blocked_tickers

    def is_blackout_today(self, today_iso: Optional[str] = None) -> bool:
        today = today_iso or datetime.now(timezone.utc).date().isoformat()
        return today in self.blackout_dates


# ---------------------------------------------------------------------------
# Seed personalities (the three pre-built PMs at launch)
# ---------------------------------------------------------------------------
def _seed(
    *,
    id_: str,
    name: str,
    mandate: str,
    universe: Sequence[str],
    signal_weights: Dict[str, float],
    risk_policy: PersonalityRiskPolicy,
    cadence: str = "daily",
    accent_color: str = "#22c55e",
    avatar_glyph: str = "circle",
) -> Personality:
    return Personality(
        id=id_,
        user_id=SYSTEM_USER_ID,
        name=name,
        mandate=mandate,
        universe=list(universe),
        signal_weights=signal_weights,
        risk_policy=risk_policy,
        cadence=cadence,
        accent_color=accent_color,
        avatar_glyph=avatar_glyph,
        is_seed=True,
    )


ATLAS = _seed(
    id_="seed_atlas",
    name="Atlas",
    mandate=(
        "You are Atlas, a concentrated tech-growth portfolio manager. You run a "
        "5-to-10-name book of secular growth companies with durable competitive "
        "moats. You favor names with strong revenue acceleration, expanding margins, "
        "and rising analyst estimates. You cut losers fast (8% stop) and let winners "
        "run. You hate leverage. You respect drawdown discipline: 12% peak-to-trough "
        "max. You write a candid daily journal that admits when you were wrong."
    ),
    universe=(
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "TSM", "ASML",
        "CRM", "AMD", "ADBE", "NOW", "PANW", "CRWD", "SHOP", "SNOW", "MDB",
        "NET", "DDOG", "ABNB", "UBER", "LLY", "INTU", "ORCL",
    ),
    signal_weights={
        "momentum": 0.30,
        "quality": 0.25,
        "technical": 0.20,
        "sentiment": 0.15,
        "valuation": 0.05,
        "macro": 0.05,
    },
    risk_policy=PersonalityRiskPolicy(
        max_position_pct=12.0,
        max_gross_exposure_pct=100.0,
        max_single_name_concentration=18.0,
        max_open_trades=10,
        min_confidence_to_trade=55.0,
        block_during_earnings_window=False,  # Atlas opts in to earnings setups
        daily_loss_circuit_breaker_pct=3.5,
        vix_max_for_new_trades=45.0,
    ),
    accent_color="#22c55e",
    avatar_glyph="triangle",
)

SAGE = _seed(
    id_="seed_sage",
    name="Sage",
    mandate=(
        "You are Sage, a value-with-catalysts portfolio manager in the tradition "
        "of Joel Greenblatt and Seth Klarman. You run a 15-to-25-name diversified "
        "book of high-quality businesses trading below intrinsic value, with a "
        "near-term re-rating catalyst (earnings beat, spin-off, activist filing, "
        "guidance reset, regulatory clearance). You respect earnings windows and "
        "always wait to see the print. You hold for months, not days. Drawdown "
        "discipline: 10% peak-to-trough."
    ),
    universe=(
        "BRK.B", "JPM", "BAC", "WFC", "CVX", "XOM", "JNJ", "PFE", "MRK", "UNH",
        "HD", "LOW", "WMT", "COST", "PG", "KO", "PEP", "DIS", "MCD", "VZ",
        "T", "CAT", "DE", "BA", "GE", "RTX", "HON", "MMM", "PHM", "DHI",
    ),
    signal_weights={
        "valuation": 0.30,
        "quality": 0.25,
        "fundamentals": 0.20,
        "macro": 0.10,
        "sentiment": 0.10,
        "technical": 0.05,
    },
    risk_policy=PersonalityRiskPolicy(
        max_position_pct=7.0,
        max_gross_exposure_pct=95.0,
        max_single_name_concentration=10.0,
        max_open_trades=20,
        min_confidence_to_trade=60.0,
        block_during_earnings_window=True,
        earnings_blackout_days_before=3,
        earnings_blackout_days_after=2,
        daily_loss_circuit_breaker_pct=2.5,
        vix_max_for_new_trades=40.0,
    ),
    accent_color="#0ea5e9",
    avatar_glyph="square",
)

VEGA = _seed(
    id_="seed_vega",
    name="Vega",
    mandate=(
        "You are Vega, a defensive income portfolio manager. You run a low-beta "
        "book of dividend aristocrats, utility-like compounders, and treasury or "
        "investment-grade-credit-proxy ETFs. You prioritize capital preservation "
        "and a 4%+ portfolio yield over growth. You will not chase momentum. You "
        "trim positions that breach 12-month relative-strength downtrend versus "
        "the S&P 500. Drawdown discipline: 6% peak-to-trough."
    ),
    universe=(
        "JNJ", "PG", "KO", "PEP", "WMT", "MCD", "MMM", "T", "VZ", "SO", "DUK",
        "NEE", "AEP", "D", "ED", "XEL", "WEC", "ES", "O", "WPC", "OHI",
        "TLT", "IEF", "LQD", "VYM", "SCHD",
    ),
    signal_weights={
        "quality": 0.30,
        "fundamentals": 0.25,
        "macro": 0.20,
        "valuation": 0.15,
        "technical": 0.05,
        "sentiment": 0.05,
    },
    risk_policy=PersonalityRiskPolicy(
        max_position_pct=6.0,
        max_gross_exposure_pct=85.0,
        max_single_name_concentration=8.0,
        max_open_trades=25,
        min_confidence_to_trade=65.0,
        block_during_earnings_window=True,
        earnings_blackout_days_before=2,
        earnings_blackout_days_after=1,
        daily_loss_circuit_breaker_pct=1.5,
        vix_max_for_new_trades=30.0,
    ),
    accent_color="#f59e0b",
    avatar_glyph="hexagon",
)

SEED_PERSONALITIES: List[Personality] = [ATLAS, SAGE, VEGA]


# ---------------------------------------------------------------------------
# Mongo CRUD
# ---------------------------------------------------------------------------
async def ensure_seed_personalities(db: Any) -> None:
    """Idempotent: insert seed personalities if not present."""
    coll = db[PERSONALITY_COLLECTION]
    for seed in SEED_PERSONALITIES:
        existing = await coll.find_one({"id": seed.id})
        if existing is None:
            await coll.insert_one(seed.to_dict())
            logger.info(f"Seeded personality: {seed.name}")


async def list_personalities(db: Any, user_id: Optional[str] = None) -> List[Personality]:
    """List personalities visible to a user: their own + seeds."""
    coll = db[PERSONALITY_COLLECTION]
    if user_id is None:
        cursor = coll.find({})
    else:
        cursor = coll.find({"$or": [{"user_id": user_id}, {"user_id": SYSTEM_USER_ID}]})
    items: List[Personality] = []
    async for doc in cursor:
        doc.pop("_id", None)
        try:
            items.append(Personality.from_dict(doc))
        except Exception as exc:
            logger.warning(f"Skipping malformed personality {doc.get('id')!r}: {exc}")
    # Stable order: seeds first, then by name
    items.sort(key=lambda p: (not p.is_seed, p.name.lower()))
    return items


async def get_personality(db: Any, personality_id: str) -> Optional[Personality]:
    coll = db[PERSONALITY_COLLECTION]
    doc = await coll.find_one({"id": personality_id})
    if not doc:
        return None
    doc.pop("_id", None)
    return Personality.from_dict(doc)


async def upsert_personality(db: Any, personality: Personality) -> Personality:
    coll = db[PERSONALITY_COLLECTION]
    personality.updated_at = datetime.now(timezone.utc).isoformat()
    personality.version += 1
    await coll.update_one(
        {"id": personality.id},
        {"$set": personality.to_dict()},
        upsert=True,
    )
    return personality


async def delete_personality(db: Any, personality_id: str, user_id: str) -> bool:
    """Owner-only. Seeds are protected."""
    coll = db[PERSONALITY_COLLECTION]
    doc = await coll.find_one({"id": personality_id})
    if not doc:
        return False
    if doc.get("is_seed") or doc.get("user_id") == SYSTEM_USER_ID:
        raise PermissionError("Cannot delete a seed personality")
    if doc.get("user_id") != user_id:
        raise PermissionError("Cannot delete another user's personality")
    result = await coll.delete_one({"id": personality_id})
    return result.deleted_count > 0


async def set_paused(db: Any, personality_id: str, paused: bool) -> Optional[Personality]:
    coll = db[PERSONALITY_COLLECTION]
    now = datetime.now(timezone.utc).isoformat()
    await coll.update_one(
        {"id": personality_id},
        {"$set": {"paused": paused, "updated_at": now}, "$inc": {"version": 1}},
    )
    return await get_personality(db, personality_id)


async def apply_user_override(
    db: Any,
    personality_id: str,
    *,
    block_ticker: Optional[str] = None,
    unblock_ticker: Optional[str] = None,
    blackout_date: Optional[str] = None,
    user_note: Optional[str] = None,
) -> Optional[Personality]:
    """Idempotent chat-driven overrides ('don't touch NVDA' -> block_ticker='NVDA')."""
    personality = await get_personality(db, personality_id)
    if personality is None:
        return None
    if block_ticker:
        if block_ticker.upper() not in personality.blocked_tickers:
            personality.blocked_tickers.append(block_ticker.upper())
            personality.blocked_tickers.sort()
    if unblock_ticker and unblock_ticker.upper() in personality.blocked_tickers:
        personality.blocked_tickers.remove(unblock_ticker.upper())
    if blackout_date and blackout_date not in personality.blackout_dates:
        personality.blackout_dates.append(blackout_date)
        personality.blackout_dates.sort()
    if user_note:
        personality.user_notes.append(f"{datetime.now(timezone.utc).isoformat()} | {user_note}")
        personality.user_notes = personality.user_notes[-50:]  # cap to last 50
    return await upsert_personality(db, personality)


async def clone_seed_for_user(db: Any, seed_id: str, user_id: str, new_name: Optional[str] = None) -> Optional[Personality]:
    """Fork a seed personality into a user-owned copy they can edit."""
    seed = await get_personality(db, seed_id)
    if seed is None or not seed.is_seed:
        return None
    clone = Personality.from_dict({**seed.to_dict(), "id": str(uuid.uuid4()), "user_id": user_id,
                                    "name": new_name or f"{seed.name} (mine)", "is_seed": False, "version": 1})
    return await upsert_personality(db, clone)
