"""PilotEngine: the AI Portfolio Manager orchestrator.

For a given Personality, propose_trades() runs the full pipeline:

    1. Hard guards: paused? blackout day? VIX too high? halt new trades.
    2. Scan the personality's universe via signal_engine.scan_universe().
    3. Take the top N candidates above the personality's confidence floor.
    4. For each candidate:
        a. Run the adversarial swarm (bull/bear/value/momentum/risk + PM verdict).
        b. Parse the PM's structured output (VERDICT/CONVICTION/SIZE/STOP/TARGET).
        c. Evaluate against policy_engine.evaluate_paper_trade() — drop or warn.
        d. Pull single-stock risk verdict from risk_engine.
        e. If earnings within 5 trading days, call MiroFish for a stress test.
        f. (Optional) Pipe additional context through NemoClaw bridge.
        g. Materialize a TradeProposal in Mongo.
    5. Return the list of created proposals.

execute_approved() takes a proposal the user has approved and:
    1. Re-checks policy (defense in depth — guards may have changed).
    2. Submits a paper order via alpaca_client.submit_market_order().
    3. Transitions proposal to EXECUTED or FAILED with full audit.

emergency_stop() is the kill switch: pause personality + cancel pending orders.

NOTE: this module deliberately does NOT itself fetch market data. It calls the
existing engines (signal_engine, risk_engine, market_data) so a single source of
truth governs all data behavior. If signal_engine has bugs, we inherit them; if
it gets fixed, we get the fix for free.
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports keep this module importable in environments where the heavy
# market-data deps aren't installed (e.g., unit tests for the DSL).
# ---------------------------------------------------------------------------
def _signal_engine_scan_universe():
    from signal_engine import scan_universe  # type: ignore
    return scan_universe


def _signal_engine_compute_signals():
    from signal_engine import compute_signals  # type: ignore
    return compute_signals


def _risk_engine_single():
    from risk_engine import analyze_single_stock_risk  # type: ignore
    return analyze_single_stock_risk


def _policy_engine_evaluate():
    from vnext.policy_engine import evaluate_paper_trade, get_next_earnings_event  # type: ignore
    return evaluate_paper_trade, get_next_earnings_event


def _strategy_swarm_run():
    from vnext.strategy_swarm import run_swarm  # type: ignore
    return run_swarm


def _mirofish_client():
    from vnext.mirofish_bridge import MirofishBridgeClient  # type: ignore
    return MirofishBridgeClient


def _nemoclaw_client():
    from vnext.nemoclaw_bridge import NemoclawBridgeClient  # type: ignore
    return NemoclawBridgeClient


def _alpaca_submit_market_order():
    from vnext.alpaca_client import submit_market_order  # type: ignore
    return submit_market_order


def _alpaca_cancel_order():
    from vnext.alpaca_client import cancel_order  # type: ignore
    return cancel_order


def _alpaca_get_account():
    from vnext.alpaca_client import get_account  # type: ignore
    return get_account


def _alpaca_list_orders():
    from vnext.alpaca_client import list_orders  # type: ignore
    return list_orders


def _alpaca_get_positions():
    from vnext.alpaca_client import get_positions  # type: ignore
    return get_positions


def _alpaca_is_configured():
    from vnext.alpaca_client import is_alpaca_configured  # type: ignore
    return is_alpaca_configured()


# ---------------------------------------------------------------------------
# Imports from the pilot subpackage
# ---------------------------------------------------------------------------
from .personality import Personality, get_personality, set_paused
from .trade_proposals import (
    PROPOSAL_COLLECTION,
    ProposalStatus,
    TradeProposal,
    create_proposal,
    expire_overdue_proposals,
    get_proposal,
    list_proposals,
    update_proposal_status,
)

# Mongo collection for ad-hoc "agent thoughts" feed (the live activity stream
# the UI shows on the middle column).
ACTIVITY_COLLECTION = "pilot_activity_events"


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _policy_context_from_executed_proposals(
    proposals: List[TradeProposal],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    open_trades: List[Dict[str, Any]] = []
    portfolio_holdings: List[Dict[str, Any]] = []
    for p in proposals:
        if p.side != "buy":
            continue
        qty = _as_float(p.fill_qty if p.fill_qty is not None else p.qty)
        price = _as_float(p.fill_price if p.fill_price is not None else p.quote_price)
        ticker = (p.ticker or "").upper()
        if qty <= 0 or price <= 0 or not ticker:
            continue
        open_trades.append({"ticker": ticker, "size": qty, "entry_price": price, "status": "open"})
        portfolio_holdings.append({"ticker": ticker, "shares": qty, "avg_price": price})
    return open_trades, portfolio_holdings


def _policy_context_from_alpaca(
    *,
    positions: List[Dict[str, Any]],
    open_orders: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    open_trades: List[Dict[str, Any]] = []
    portfolio_holdings: List[Dict[str, Any]] = []

    for pos in positions:
        ticker = str(pos.get("symbol") or "").upper()
        qty = _as_float(pos.get("qty"))
        entry_price = _as_float(pos.get("avg_entry_price")) or _as_float(pos.get("current_price"))
        if not ticker or qty <= 0 or entry_price <= 0:
            continue
        open_trades.append({"ticker": ticker, "size": qty, "entry_price": entry_price, "status": "open"})
        portfolio_holdings.append({"ticker": ticker, "shares": qty, "avg_price": entry_price})

    for order in open_orders:
        ticker = str(order.get("symbol") or "").upper()
        qty = _as_float(order.get("qty"))
        filled_qty = _as_float(order.get("filled_qty"))
        remaining_qty = max(0.0, qty - filled_qty)
        entry_price = (
            _as_float(order.get("limit_price"))
            or _as_float(order.get("filled_avg_price"))
        )
        if not ticker or remaining_qty <= 0 or entry_price <= 0:
            continue
        open_trades.append(
            {
                "ticker": ticker,
                "size": remaining_qty,
                "entry_price": entry_price,
                "status": "open",
            }
        )

    return open_trades, portfolio_holdings


def _policy_evidence_from_proposal(proposal: TradeProposal) -> List[Dict[str, Any]]:
    derived = proposal.policy_verdict.get("derived", {}) if isinstance(proposal.policy_verdict, dict) else {}
    confidence_score = _as_float(derived.get("confidence_score"))
    if confidence_score > 0:
        return [{"confidence": confidence_score}]
    return []


# ===========================================================================
# Public API
# ===========================================================================
async def propose_trades(
    db: Any,
    personality_id: str,
    user_id: str,
    *,
    max_candidates: int = 5,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Run one decision cycle. Returns a summary dict for the API layer.

    `dry_run=True` skips Mongo persistence and external bridges; used by the UI
    "preview" mode and by smoke tests.
    """
    personality = await get_personality(db, personality_id)
    if personality is None:
        return _err("personality_not_found", personality_id=personality_id)

    # ---- Hard guards (kill switches) ----
    if personality.paused:
        await _activity(db, personality_id, "skipped", "Personality is paused.")
        return _err("paused", personality_id=personality_id)

    today_iso = datetime.now(timezone.utc).date().isoformat()
    if personality.is_blackout_today(today_iso):
        await _activity(db, personality_id, "skipped", f"Blackout day: {today_iso}")
        return _err("blackout_day", personality_id=personality_id, date=today_iso)

    await _activity(db, personality_id, "cycle_start", f"Scanning {len(personality.universe)} tickers.")

    # ---- 1. Universe scan ----
    candidates = await _scan_universe(personality, db)
    if not candidates:
        await _activity(db, personality_id, "no_candidates", "Universe scan returned nothing.")
        return _ok(personality_id=personality_id, proposals=[], scanned=len(personality.universe))

    floor = personality.risk_policy.min_confidence_to_trade
    qualifying = [c for c in candidates if c.get("composite_score", 0) >= floor]
    qualifying = [c for c in qualifying if not personality.is_blocked(c["ticker"])]
    qualifying = qualifying[:max_candidates]

    if not qualifying:
        await _activity(
            db,
            personality_id,
            "no_qualifying",
            f"Top score {candidates[0].get('composite_score', 0):.1f} below floor {floor:.0f}.",
        )
        return _ok(personality_id=personality_id, proposals=[], scanned=len(personality.universe))

    await _activity(
        db,
        personality_id,
        "candidates_selected",
        f"{len(qualifying)} candidates above floor {floor:.0f}.",
        payload={"tickers": [c["ticker"] for c in qualifying]},
    )

    # ---- 2. Per-candidate decision pipeline ----
    proposals: List[TradeProposal] = []
    for cand in qualifying:
        ticker = cand["ticker"]
        try:
            proposal = await _decide_for_candidate(
                db=db,
                personality=personality,
                user_id=user_id,
                candidate=cand,
                dry_run=dry_run,
            )
        except Exception as exc:
            logger.exception(f"pilot_engine: candidate {ticker} failed")
            await _activity(db, personality_id, "candidate_error", f"{ticker}: {exc}")
            continue

        if proposal is None:
            continue
        proposals.append(proposal)

    await _activity(
        db,
        personality_id,
        "cycle_end",
        f"{len(proposals)} proposal(s) created.",
        payload={"proposal_ids": [p.id for p in proposals]},
    )
    return _ok(
        personality_id=personality_id,
        proposals=[p.to_dict() for p in proposals],
        scanned=len(personality.universe),
    )


async def execute_approved(
    db: Any,
    proposal_id: str,
    user_id: str,
    alpaca_account_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Submit a previously approved proposal to Alpaca paper.

    Returns {ok, proposal} or {ok: False, error, ...}.
    """
    proposal = await get_proposal(db, proposal_id)
    if proposal is None:
        return _err("proposal_not_found", proposal_id=proposal_id)
    if proposal.user_id != user_id:
        return _err("not_authorized", proposal_id=proposal_id)
    if proposal.status != ProposalStatus.APPROVED.value:
        return _err("proposal_not_approved", status=proposal.status, proposal_id=proposal_id)

    account_id = alpaca_account_id or proposal.alpaca_account_id
    if not account_id:
        return _err("alpaca_account_missing", proposal_id=proposal_id)

    # Re-evaluate policy at execution time. The world may have moved.
    try:
        evaluate_paper_trade, _ = _policy_engine_evaluate()
        open_trades: List[Dict[str, Any]] = []
        portfolio_holdings: List[Dict[str, Any]] = []
        evidence_blocks = _policy_evidence_from_proposal(proposal)

        executed = await list_proposals(
            db,
            user_id=user_id,
            personality_id=proposal.personality_id,
            status=ProposalStatus.EXECUTED.value,
            limit=500,
        )
        open_trades, portfolio_holdings = _policy_context_from_executed_proposals(executed)

        if _alpaca_is_configured():
            get_positions = _alpaca_get_positions()
            list_orders = _alpaca_list_orders()
            live_positions, live_open_orders = await asyncio.gather(
                asyncio.to_thread(get_positions, account_id),
                asyncio.to_thread(list_orders, account_id, "open", 200),
            )
            # Prefer broker state over proposal history when available; executed
            # proposals are only a fallback when broker integration is unavailable.
            open_trades, portfolio_holdings = _policy_context_from_alpaca(
                positions=live_positions or [],
                open_orders=live_open_orders or [],
            )

        live_check = evaluate_paper_trade(
            ticker=proposal.ticker,
            proposed_side=proposal.side,
            proposed_size=proposal.qty,
            current_price=proposal.quote_price,
            effective_policies=proposal.policy_verdict.get("effective_policies", {}),
            open_trades=open_trades,
            evidence_blocks=evidence_blocks,
            portfolio_holdings=portfolio_holdings,
            earnings_event=None,
        )
        if not live_check.get("allowed", True):
            await update_proposal_status(
                db,
                proposal_id,
                new_status=ProposalStatus.FAILED,
                actor=f"user:{user_id}",
                reason="Policy re-check failed at execution time.",
            )
            return _err("policy_failed_at_execution", details=live_check)
    except Exception as exc:
        logger.warning(f"pilot_engine: policy re-check raised, proceeding anyway: {exc}")

    # Submit order
    submit = _alpaca_submit_market_order()
    try:
        order = await asyncio.to_thread(
            submit,
            account_id,
            proposal.ticker,
            float(proposal.qty),
            proposal.side,
            proposal.time_in_force,
        )
    except Exception as exc:
        logger.exception("pilot_engine: alpaca order submission raised")
        await update_proposal_status(
            db,
            proposal_id,
            new_status=ProposalStatus.FAILED,
            actor=f"user:{user_id}",
            reason=f"Alpaca submission raised: {exc}",
        )
        return _err("alpaca_exception", message=str(exc))

    if not order:
        await update_proposal_status(
            db,
            proposal_id,
            new_status=ProposalStatus.FAILED,
            actor=f"user:{user_id}",
            reason="Alpaca returned no order (likely unconfigured or rejected).",
        )
        return _err("alpaca_no_order")

    fill_price = _parse_fill_price(order)
    refreshed = await update_proposal_status(
        db,
        proposal_id,
        new_status=ProposalStatus.EXECUTED,
        actor=f"user:{user_id}",
        reason=None,
        alpaca_order_id=order.get("id"),
        fill_price=fill_price,
        fill_qty=float(order.get("qty") or proposal.qty),
    )
    return _ok(proposal=refreshed.to_dict() if refreshed else None, order=order)


async def emergency_stop(
    db: Any,
    personality_id: str,
    user_id: str,
    alpaca_account_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Kill switch. Pauses the personality and cancels its pending Alpaca orders."""
    personality = await get_personality(db, personality_id)
    if personality is None:
        return _err("personality_not_found", personality_id=personality_id)

    # Pause first so no new proposals/orders can be created racing this kill.
    await set_paused(db, personality_id, True)
    await _activity(db, personality_id, "kill_switch", "Emergency stop engaged.")

    # Expire all pending proposals for this personality.
    pendings = await list_proposals(
        db,
        user_id=user_id,
        personality_id=personality_id,
        status=ProposalStatus.PENDING.value,
        limit=500,
    )
    expired_ids: List[str] = []
    for p in pendings:
        updated = await update_proposal_status(
            db,
            p.id,
            new_status=ProposalStatus.EXPIRED,
            actor=f"user:{user_id}",
            reason="Kill switch engaged.",
        )
        if updated:
            expired_ids.append(p.id)

    # Cancel any in-flight Alpaca orders for this personality.
    #
    # Do not gate on the local proposal lifecycle state here: proposals are
    # typically transitioned to "executed" immediately after order submission,
    # while the Alpaca order itself may still be open or partially filled and
    # therefore still cancellable. The broker is the source of truth for
    # whether an order can be cancelled, so attempt cancellation for every
    # unique Alpaca order id we have recorded.
    cancelled: List[str] = []
    cancel_order = _alpaca_cancel_order()
    if alpaca_account_id:
        all_for_personality = await list_proposals(
            db,
            user_id=user_id,
            personality_id=personality_id,
            limit=500,
        )
        seen_alpaca_order_ids = set()
        for p in all_for_personality:
            if not p.alpaca_order_id or p.alpaca_order_id in seen_alpaca_order_ids:
                continue
            seen_alpaca_order_ids.add(p.alpaca_order_id)
            try:
                success = await asyncio.to_thread(cancel_order, alpaca_account_id, p.alpaca_order_id)
                if success:
                    cancelled.append(p.alpaca_order_id)
            except Exception as exc:
                logger.warning(f"pilot_engine: cancel_order failed for {p.alpaca_order_id}: {exc}")

    return _ok(
        personality_id=personality_id,
        paused=True,
        expired_proposal_ids=expired_ids,
        cancelled_alpaca_order_ids=cancelled,
    )


# ===========================================================================
# Internals: candidate scan and per-candidate decision
# ===========================================================================
async def _scan_universe(personality: Personality, db: Any) -> List[Dict[str, Any]]:
    """Run signal_engine.scan_universe() with reasonable concurrency.

    Returns list of signal dicts sorted by composite_score desc.
    """
    try:
        scan_universe = _signal_engine_scan_universe()
    except Exception as exc:
        logger.error(f"signal_engine unavailable, returning empty candidates: {exc}")
        return []

    try:
        results = await scan_universe(list(personality.universe), db=db, concurrency=5)
    except Exception as exc:
        logger.exception(f"scan_universe raised: {exc}")
        return []
    return results or []


async def _decide_for_candidate(
    *,
    db: Any,
    personality: Personality,
    user_id: str,
    candidate: Dict[str, Any],
    dry_run: bool,
) -> Optional[TradeProposal]:
    ticker = candidate["ticker"]
    composite = float(candidate.get("composite_score", 0.0))
    current_price = float(candidate.get("current_price") or candidate.get("price") or 0.0)
    if current_price <= 0:
        # No price = can't size. Skip.
        return None

    await _activity(db, personality.id, "swarm_running", f"Debating {ticker}…")

    # ---- Run the adversarial swarm ----
    swarm_result = await _run_swarm_safe(personality, ticker, candidate)
    if swarm_result is None:
        return None
    verdict_struct = _parse_verdict(swarm_result.get("final_strategy") or "")
    if verdict_struct["verdict"] == "PASS" or verdict_struct["conviction"] < _conviction_floor_for_personality(personality):
        await _activity(
            db,
            personality.id,
            "passed",
            f"{ticker} → {verdict_struct['verdict']} @ conviction {verdict_struct['conviction']}",
        )
        return None

    side = "buy" if verdict_struct["verdict"] == "LONG" else "sell"

    # ---- Position sizing ----
    qty, notional, est_stop_pct = _size_position(
        personality=personality,
        current_price=current_price,
        verdict_struct=verdict_struct,
    )
    if qty <= 0:
        await _activity(db, personality.id, "size_zero", f"{ticker} qty=0 from sizing.")
        return None

    # ---- Single-stock risk verdict ----
    risk_verdict: Dict[str, Any] = {}
    try:
        analyze_single_stock_risk = _risk_engine_single()
        risk_verdict = await analyze_single_stock_risk(ticker)
    except Exception as exc:
        logger.warning(f"risk_engine analyze_single_stock_risk failed for {ticker}: {exc}")
        risk_verdict = {"error": str(exc)}

    # ---- Catalyst stress test (earnings-adjacent only) ----
    catalyst_stress: Optional[Dict[str, Any]] = None
    earnings_event: Optional[Dict[str, Any]] = None
    try:
        _, get_next_earnings_event = _policy_engine_evaluate()
        earnings_event = await get_next_earnings_event(ticker)
        if earnings_event and not dry_run:
            catalyst_stress = await _maybe_call_mirofish(personality, ticker, earnings_event, verdict_struct)
    except Exception as exc:
        logger.warning(f"earnings/catalyst lookup failed for {ticker}: {exc}")

    # ---- Policy verdict (paper-trade guardrails) ----
    policy_verdict: Dict[str, Any] = {}
    try:
        evaluate_paper_trade, _ = _policy_engine_evaluate()
        policy_verdict = evaluate_paper_trade(
            ticker=ticker,
            proposed_side=side,
            proposed_size=qty,
            current_price=current_price,
            effective_policies=personality.risk_policy.to_policy_engine_dict(),
            open_trades=[],
            evidence_blocks=[{"confidence": composite}],
            portfolio_holdings=[],
            earnings_event=earnings_event,
        )
    except Exception as exc:
        logger.warning(f"policy_engine evaluation failed for {ticker}: {exc}")
        policy_verdict = {"error": str(exc), "allowed": False}

    if not policy_verdict.get("allowed", False):
        await _activity(
            db,
            personality.id,
            "policy_blocked",
            f"{ticker} blocked: {[v.get('rule_type') for v in policy_verdict.get('violations', [])]}",
            payload={"policy_verdict": policy_verdict},
        )
        return None

    # ---- (Optional) NemoClaw sandbox: extra adversarial signal ----
    nemoclaw_payload: Optional[Dict[str, Any]] = None
    try:
        NemoClient = _nemoclaw_client()
        client = NemoClient()
        if client.configured and not dry_run:
            nemoclaw_payload = await client.analyze({
                "ticker": ticker,
                "personality": personality.name,
                "mandate": personality.mandate,
                "verdict": verdict_struct,
                "signals": candidate,
            })
    except Exception as exc:
        logger.debug(f"nemoclaw_bridge skipped for {ticker}: {exc}")

    # ---- Assemble the TradeProposal ----
    proposal = TradeProposal(
        id=str(uuid.uuid4()),
        user_id=user_id,
        personality_id=personality.id,
        personality_name=personality.name,
        ticker=ticker,
        side=side,
        qty=float(qty),
        order_type="market",
        quote_price=current_price,
        proposed_notional=float(notional),
        stop_loss_price=_stop_price(current_price, est_stop_pct, side),
        take_profit_price=_target_price(current_price, verdict_struct.get("target"), side),
        thesis=verdict_struct.get("thesis", "").strip(),
        conviction=int(verdict_struct.get("conviction", 0)),
        debate_transcript=swarm_result.get("agents_output", []),
        signal_snapshot=candidate,
        risk_verdict=risk_verdict,
        policy_verdict=policy_verdict,
        catalyst_stress_test=catalyst_stress,
        agent_trace=[{
            "stage": "swarm_synthesis",
            "raw": (swarm_result.get("final_strategy") or "")[:4000],
        }, {
            "stage": "nemoclaw",
            "result": nemoclaw_payload,
        }],
        invalidation=verdict_struct.get("invalidation", "").strip(),
        dissent_summary=verdict_struct.get("dissent", "").strip(),
    )

    if dry_run:
        return proposal

    proposal.alpaca_account_id = None  # set by router from user record
    return await create_proposal(db, proposal)


# ===========================================================================
# Helpers
# ===========================================================================
async def _run_swarm_safe(
    personality: Personality,
    ticker: str,
    candidate: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    try:
        run_swarm = _strategy_swarm_run()
    except Exception as exc:
        logger.error(f"strategy_swarm unavailable: {exc}")
        return None

    prompt = (
        f"You are advising portfolio manager '{personality.name}'.\n"
        f"Mandate: {personality.mandate}\n\n"
        f"Ticker under review: {ticker}\n"
        f"Composite signal score (range -100..+100): {candidate.get('composite_score'):.1f} "
        f"({candidate.get('signal_label') or 'unlabeled'})\n"
        f"Category breakdown: {candidate.get('categories') or {}}\n\n"
        f"Decide whether to LONG, SHORT, or PASS, with conviction 1-10, entry price, "
        f"target, stop, sizing, thesis, invalidation, and dissent."
    )

    try:
        result = await run_swarm(
            prompt=prompt,
            regime_context={"source": "pilot_engine", "ticker": ticker},
            tickers=[ticker],
            user_id="pilot",
            yield_callback=None,
        )
        return result
    except Exception as exc:
        logger.exception(f"run_swarm failed for {ticker}: {exc}")
        return None


_VERDICT_LINE = re.compile(r"^\s*(?P<key>VERDICT|CONVICTION|ENTRY|TARGET|STOP|SIZE|THESIS|INVALIDATION|DISSENT)\s*:\s*(?P<value>.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def _parse_verdict(text: str) -> Dict[str, Any]:
    """Parse the Portfolio Manager synthesis into a structured dict.

    Tolerant: missing fields default to safe values; bad numbers default to 0 / pass.
    """
    fields: Dict[str, str] = {}
    for m in _VERDICT_LINE.finditer(text or ""):
        fields[m.group("key").upper()] = m.group("value").strip()

    verdict = (fields.get("VERDICT") or "PASS").upper().split()[0]
    if verdict not in {"LONG", "SHORT", "PASS"}:
        verdict = "PASS"

    conviction_raw = fields.get("CONVICTION", "0")
    conviction = _safe_int(re.search(r"\d+", conviction_raw).group(0)) if re.search(r"\d+", conviction_raw) else 0

    size_raw = fields.get("SIZE", "0")
    size_pct = _safe_float(re.search(r"\d+(?:\.\d+)?", size_raw).group(0)) if re.search(r"\d+(?:\.\d+)?", size_raw) else 0.0

    stop_raw = fields.get("STOP", "")
    stop_pct = _extract_stop_pct(stop_raw)

    target_raw = fields.get("TARGET", "")

    return {
        "verdict": verdict,
        "conviction": conviction,
        "entry": fields.get("ENTRY", ""),
        "target": target_raw,
        "stop": stop_raw,
        "stop_pct": stop_pct,
        "size_pct": size_pct,
        "thesis": fields.get("THESIS", ""),
        "invalidation": fields.get("INVALIDATION", ""),
        "dissent": fields.get("DISSENT", ""),
        "raw_text": text or "",
    }


def _extract_stop_pct(stop_text: str) -> Optional[float]:
    if not stop_text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", stop_text)
    if m:
        return float(m.group(1)) / 100.0
    return None


def _conviction_floor_for_personality(personality: Personality) -> int:
    """Map confidence floor (0-100) to a swarm conviction floor (1-10)."""
    floor = personality.risk_policy.min_confidence_to_trade
    if floor >= 75:
        return 7
    if floor >= 60:
        return 6
    if floor >= 50:
        return 5
    return 4


def _size_position(
    *,
    personality: Personality,
    current_price: float,
    verdict_struct: Dict[str, Any],
) -> Tuple[int, float, Optional[float]]:
    """Position sizing. Honors personality.max_position_pct and swarm SIZE hint.

    Returns (qty_shares, notional_usd, est_stop_pct).
    """
    capital = personality.initial_capital_usd
    cap_pct = personality.risk_policy.max_position_pct
    swarm_pct = verdict_struct.get("size_pct") or 0.0
    target_pct = min(cap_pct, swarm_pct) if swarm_pct else cap_pct
    target_pct = max(min(target_pct, cap_pct), 1.0)  # at least 1%, at most cap
    notional = (target_pct / 100.0) * capital
    if current_price <= 0:
        return 0, 0.0, None
    qty = int(notional // current_price)
    return qty, qty * current_price, verdict_struct.get("stop_pct")


def _stop_price(price: float, stop_pct: Optional[float], side: str) -> Optional[float]:
    if stop_pct is None or price <= 0:
        return None
    if side == "buy":
        return round(price * (1 - stop_pct), 2)
    return round(price * (1 + stop_pct), 2)


def _target_price(price: float, target_raw: Optional[str], side: str) -> Optional[float]:
    if not target_raw:
        return None
    m = re.search(r"\$?\s*(\d+(?:\.\d+)?)", target_raw)
    if not m:
        return None
    try:
        return float(m.group(1))
    except (TypeError, ValueError):
        return None


async def _maybe_call_mirofish(
    personality: Personality,
    ticker: str,
    earnings_event: Dict[str, Any],
    verdict_struct: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    try:
        client_cls = _mirofish_client()
        client = client_cls()
        if not getattr(client, "configured", False):
            return None
        payload = {
            "ticker": ticker,
            "personality": personality.name,
            "thesis": verdict_struct.get("thesis"),
            "earnings_event": earnings_event,
        }
        # MirofishBridgeClient is expected to expose simulate() or analyze();
        # we try both gracefully.
        if hasattr(client, "simulate"):
            return await client.simulate(payload)  # type: ignore[attr-defined]
        if hasattr(client, "analyze"):
            return await client.analyze(payload)  # type: ignore[attr-defined]
        return None
    except Exception as exc:
        logger.debug(f"mirofish_bridge skipped for {ticker}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Activity feed (the live "what the AI is thinking" stream)
# ---------------------------------------------------------------------------
async def _activity(
    db: Any,
    personality_id: str,
    event_type: str,
    message: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        await db[ACTIVITY_COLLECTION].insert_one({
            "id": str(uuid.uuid4()),
            "personality_id": personality_id,
            "event_type": event_type,
            "message": message,
            "payload": payload or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        logger.warning(f"activity feed write failed: {exc}")


async def list_activity_events(
    db: Any,
    personality_id: Optional[str] = None,
    *,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    coll = db[ACTIVITY_COLLECTION]
    query: Dict[str, Any] = {}
    if personality_id:
        query["personality_id"] = personality_id
    cursor = coll.find(query).sort("timestamp", -1).limit(limit)
    items: List[Dict[str, Any]] = []
    async for doc in cursor:
        doc.pop("_id", None)
        items.append(doc)
    return items


# ---------------------------------------------------------------------------
# Tiny utilities
# ---------------------------------------------------------------------------
def _safe_int(s: str, default: int = 0) -> int:
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


def _safe_float(s: str, default: float = 0.0) -> float:
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def _parse_fill_price(order: Dict[str, Any]) -> Optional[float]:
    for key in ("filled_avg_price", "avg_price", "limit_price", "stop_price"):
        v = order.get(key)
        if v:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def _ok(**kwargs: Any) -> Dict[str, Any]:
    return {"ok": True, **kwargs}


def _err(code: str, **kwargs: Any) -> Dict[str, Any]:
    return {"ok": False, "error": code, **kwargs}


# Re-export sweep so the router/scheduler can call it
__all__ = [
    "propose_trades",
    "execute_approved",
    "emergency_stop",
    "list_activity_events",
    "expire_overdue_proposals",
]
