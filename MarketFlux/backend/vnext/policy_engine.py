from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, List, Optional

from agent_tools import get_earnings_calendar


def _rule_value(effective: Dict[str, Dict[str, Any]], rule_type: str, default: float) -> float:
    rule = effective.get(rule_type) or {}
    params = rule.get("params") or {}
    return float(params.get("value", default))


def _rule_enabled(effective: Dict[str, Dict[str, Any]], rule_type: str, default: bool) -> bool:
    rule = effective.get(rule_type)
    if rule is None:
        return default
    return bool(rule.get("enabled", default))


def estimate_capital_base(portfolio_holdings: List[Dict[str, Any]], open_trades: List[Dict[str, Any]]) -> float:
    holdings_cost_basis = 0.0
    for holding in portfolio_holdings:
        try:
            holdings_cost_basis += float(holding.get("shares", 0)) * float(holding.get("avg_price", 0))
        except (TypeError, ValueError):
            continue

    open_notional = 0.0
    for trade in open_trades:
        try:
            open_notional += float(trade.get("size", 0)) * float(trade.get("entry_price", 0))
        except (TypeError, ValueError):
            continue

    return max(holdings_cost_basis + open_notional, 100000.0)


async def get_next_earnings_event(ticker: str) -> Optional[Dict[str, Any]]:
    calendar = await get_earnings_calendar(ticker)
    events = calendar.get("earnings_events") or []
    now = datetime.now(timezone.utc).date()
    nearest: Optional[Dict[str, Any]] = None

    for event in events:
        try:
            event_date = datetime.fromisoformat(event["date"]).date()
        except (KeyError, ValueError, TypeError):
            continue
        if event_date >= now and (nearest is None or event_date < datetime.fromisoformat(nearest["date"]).date()):
            nearest = event

    return nearest


def evaluate_paper_trade(
    *,
    ticker: str,
    proposed_side: str,
    proposed_size: float,
    current_price: float,
    effective_policies: Dict[str, Dict[str, Any]],
    open_trades: List[Dict[str, Any]],
    evidence_blocks: List[Dict[str, Any]],
    portfolio_holdings: List[Dict[str, Any]],
    earnings_event: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    capital_base = estimate_capital_base(portfolio_holdings, open_trades)
    open_gross_notional = sum(float(trade.get("size", 0)) * float(trade.get("entry_price", 0)) for trade in open_trades)
    existing_ticker_exposure = sum(
        float(trade.get("size", 0)) * float(trade.get("entry_price", 0))
        for trade in open_trades
        if trade.get("ticker") == ticker and trade.get("status") == "open"
    )
    proposed_notional = proposed_size * current_price
    violations: List[Dict[str, Any]] = []
    warnings: List[str] = []
    derived = {
        "ticker": ticker,
        "side": proposed_side,
        "current_price": current_price,
        "proposed_notional": proposed_notional,
        "capital_base_usd": capital_base,
    }

    if _rule_enabled(effective_policies, "max_position_pct", True):
        max_position_pct = _rule_value(effective_policies, "max_position_pct", 20)
        position_pct = (proposed_notional / capital_base) * 100
        derived["position_pct"] = position_pct
        if position_pct > max_position_pct:
            violations.append(
                {
                    "rule_type": "max_position_pct",
                    "message": f"Position size {position_pct:.2f}% exceeds the configured maximum of {max_position_pct:.2f}%.",
                }
            )

    if _rule_enabled(effective_policies, "max_gross_exposure_pct", True):
        max_gross_pct = _rule_value(effective_policies, "max_gross_exposure_pct", 100)
        gross_pct = ((open_gross_notional + proposed_notional) / capital_base) * 100
        derived["gross_exposure_pct_after"] = gross_pct
        if gross_pct > max_gross_pct:
            violations.append(
                {
                    "rule_type": "max_gross_exposure_pct",
                    "message": f"Gross exposure would rise to {gross_pct:.2f}% which exceeds the configured maximum of {max_gross_pct:.2f}%.",
                }
            )

    if _rule_enabled(effective_policies, "max_single_name_concentration", True):
        max_single_name = _rule_value(effective_policies, "max_single_name_concentration", 25)
        single_name_pct = ((existing_ticker_exposure + proposed_notional) / capital_base) * 100
        derived["single_name_pct_after"] = single_name_pct
        if single_name_pct > max_single_name:
            violations.append(
                {
                    "rule_type": "max_single_name_concentration",
                    "message": f"{ticker} exposure would rise to {single_name_pct:.2f}% which exceeds the configured maximum of {max_single_name:.2f}%.",
                }
            )

    if _rule_enabled(effective_policies, "max_open_trades", True):
        max_open_trades = int(_rule_value(effective_policies, "max_open_trades", 10))
        open_trade_count = len([trade for trade in open_trades if trade.get("status") == "open"])
        derived["open_trade_count_after"] = open_trade_count + 1
        if open_trade_count + 1 > max_open_trades:
            violations.append(
                {
                    "rule_type": "max_open_trades",
                    "message": f"Opening this trade would bring you to {open_trade_count + 1} open trades, above the configured maximum of {max_open_trades}.",
                }
            )

    if _rule_enabled(effective_policies, "min_confidence_to_trade", True):
        min_confidence = _rule_value(effective_policies, "min_confidence_to_trade", 60)
        confidences = [float(item.get("confidence", 0)) for item in evidence_blocks if item.get("confidence") is not None]
        confidence_score = mean(confidences) if confidences else 0.0
        derived["confidence_score"] = confidence_score
        if confidence_score < min_confidence:
            violations.append(
                {
                    "rule_type": "min_confidence_to_trade",
                    "message": f"Evidence confidence is {confidence_score:.2f}, below the required threshold of {min_confidence:.2f}. Wait for more evidence or revise the thesis.",
                }
            )

    if _rule_enabled(effective_policies, "block_during_earnings_window", False) and earnings_event and earnings_event.get("date"):
        params = (effective_policies.get("block_during_earnings_window") or {}).get("params") or {}
        days_before = int(params.get("days_before", 2))
        days_after = int(params.get("days_after", 1))
        try:
            earnings_date = datetime.fromisoformat(earnings_event["date"]).date()
            delta_days = (earnings_date - datetime.now(timezone.utc).date()).days
            derived["earnings_event_date"] = earnings_event["date"]
            if -days_after <= delta_days <= days_before:
                violations.append(
                    {
                        "rule_type": "block_during_earnings_window",
                        "message": f"{ticker} is inside the configured earnings window around {earnings_event['date']}.",
                    }
                )
        except ValueError:
            warnings.append("Unable to parse the next earnings date for policy checks.")
    elif _rule_enabled(effective_policies, "block_during_earnings_window", False):
        warnings.append("Earnings-window policy is enabled, but no upcoming earnings date was available.")

    if _rule_enabled(effective_policies, "no_live_trading", True):
        warnings.append("Live trading remains disabled by policy. This endpoint only creates simulated paper trades.")

    return {
        "allowed": len(violations) == 0,
        "violations": violations,
        "warnings": warnings,
        "effective_policies": effective_policies,
        "derived": derived,
    }
