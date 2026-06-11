"""Pre-trade compliance & risk-control engine for the MarketFlux Copilot.

This is the institutional guardrail layer every order passes through *before* it
is staged or sent to the broker. It is deliberately a **pure** module: it takes
the proposed order plus a snapshot of the account and positions and returns a
structured decision. No network, no I/O, no global state — so it is fast,
deterministic, and trivially unit-testable.

The agent calls it as a tool (`compliance_precheck`) to reason about an order,
and the agent loop also runs it as a hard chokepoint: a ``BLOCK`` decision means
the order is never staged or executed, even in autonomous mode and even if the
model was prompt-injected. This mirrors how a real fund's OMS enforces pre-trade
checks independent of the PM's intent.

Everything here governs an Alpaca **paper** account. The rules encoded are
modelled on real-world controls (Reg-T buying power, FINRA pattern-day-trader
equity floor, single-name concentration limits, short-sale flags, penny-stock
liquidity, wash-sale awareness) so the behaviour transfers to a live deployment.

Decision levels
---------------
* ``PASS``  — clears all controls; safe to proceed.
* ``WARN``  — proceed allowed, but the user should be told (e.g. PDT exposure,
              wash-sale window, concentrated add). Advisory, not blocking.
* ``BLOCK`` — hard stop. The order violates a hard limit (insufficient buying
              power, over the per-order notional cap, or over the hard
              single-name concentration ceiling).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Configurable limits (env-overridable; defaults are sensible for paper book)
# ---------------------------------------------------------------------------
MAX_ORDER_NOTIONAL = float(os.getenv("COPILOT_MAX_ORDER_NOTIONAL", "60000"))
# Single-name concentration: warn early, block at the hard ceiling.
WARN_POSITION_PCT = float(os.getenv("COPILOT_WARN_POSITION_PCT", "18"))
MAX_POSITION_PCT = float(os.getenv("COPILOT_MAX_POSITION_PCT", "30"))
# FINRA pattern-day-trader equity floor (fixed by regulation).
PDT_EQUITY_FLOOR = 25_000.0
# Below this share price we treat the name as a low-liquidity / penny risk.
PENNY_PRICE = float(os.getenv("COPILOT_PENNY_PRICE", "1.0"))

DISCLOSURE = (
    "Paper/simulated account. Educational simulation, not investment advice. "
    "All controls run against simulated buying power and positions."
)

PASS, WARN, BLOCK = "PASS", "WARN", "BLOCK"
_SEVERITY = {PASS: 0, WARN: 1, BLOCK: 2}


@dataclass
class Check:
    rule: str
    status: str  # "pass" | "warn" | "block"
    detail: str
    metrics: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"rule": self.rule, "status": self.status, "detail": self.detail, **({"metrics": self.metrics} if self.metrics else {})}


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def pre_trade_check(
    *,
    symbol: str,
    side: str,
    quantity: float,
    est_price: float,
    order_type: str = "market",
    limit_price: float = 0.0,
    account: Optional[Dict[str, Any]] = None,
    positions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run all pre-trade controls and return a structured decision.

    Args:
        symbol: ticker (upper-cased internally).
        side: "buy" or "sell".
        quantity: shares.
        est_price: best-estimate current price (for notional/concentration math).
        order_type: "market" or "limit".
        limit_price: limit price when order_type == "limit".
        account: {"equity","cash","buying_power"} from the broker (strings ok).
        positions: list of {"symbol","qty","market_value","unrealized_pl",...}.

    Returns a dict with: decision, checks[], summary, disclosures[], and the
    derived order economics (notional, projected_weight_pct).
    """
    symbol = (symbol or "").strip().upper()
    side = (side or "").strip().lower()
    order_type = (order_type or "market").strip().lower()
    account = account or {}
    positions = positions or []

    checks: List[Check] = []

    # Price used for economics: limit price if a valid limit order, else estimate.
    px = limit_price if (order_type == "limit" and limit_price and limit_price > 0) else est_price
    px = _f(px)
    qty = _f(quantity)
    notional = qty * px if px > 0 else 0.0

    equity = _f(account.get("equity"))
    buying_power = _f(account.get("buying_power"))

    # Find any existing position in this name.
    held = next((p for p in positions if (p.get("symbol") or "").upper() == symbol), None)
    held_qty = _f(held.get("qty")) if held else 0.0
    held_mv = abs(_f(held.get("market_value"))) if held else 0.0

    # --- 1. Order sanity -----------------------------------------------------
    if not symbol:
        checks.append(Check("order_sanity", "block", "Missing symbol."))
    elif side not in ("buy", "sell"):
        checks.append(Check("order_sanity", "block", f"Invalid side {side!r} (expected buy/sell)."))
    elif qty <= 0:
        checks.append(Check("order_sanity", "block", "Quantity must be greater than zero."))
    elif order_type == "limit" and (not limit_price or limit_price <= 0):
        checks.append(Check("order_sanity", "block", "Limit order requires a positive limit price."))
    else:
        checks.append(Check("order_sanity", "pass", f"{side.upper()} {qty:g} {symbol} {order_type}."))

    # If the order is structurally invalid, stop here — the rest is meaningless.
    if any(c.status == "block" for c in checks):
        return _assemble(symbol, side, qty, notional, 0.0, checks)

    # --- 2. Per-order notional cap (fat-finger guard) ------------------------
    if notional > MAX_ORDER_NOTIONAL:
        checks.append(Check(
            "notional_cap", "block",
            f"Order notional ${notional:,.0f} exceeds the per-order cap of ${MAX_ORDER_NOTIONAL:,.0f}.",
            {"notional": round(notional, 2), "cap": MAX_ORDER_NOTIONAL},
        ))
    elif notional > 0:
        checks.append(Check("notional_cap", "pass", f"Order notional ${notional:,.0f} within the ${MAX_ORDER_NOTIONAL:,.0f} cap."))

    # --- 3. Buying power (buys only) -----------------------------------------
    if side == "buy" and notional > 0 and buying_power > 0:
        # Small tolerance: prices drift between estimate and fill.
        if notional > buying_power * 1.001:
            checks.append(Check(
                "buying_power", "block",
                f"Order needs ~${notional:,.0f} but buying power is ${buying_power:,.0f}.",
                {"required": round(notional, 2), "available": round(buying_power, 2)},
            ))
        else:
            checks.append(Check(
                "buying_power", "pass",
                f"${notional:,.0f} of ${buying_power:,.0f} buying power ({notional / buying_power * 100:.0f}%).",
            ))

    # --- 4. Single-name concentration (buys/adds) ---------------------------
    projected_weight = 0.0
    if side == "buy" and equity > 0:
        projected_mv = held_mv + notional
        projected_weight = projected_mv / equity * 100.0
        if projected_weight > MAX_POSITION_PCT:
            checks.append(Check(
                "concentration", "block",
                f"{symbol} would be {projected_weight:.0f}% of equity — over the {MAX_POSITION_PCT:.0f}% hard ceiling. "
                f"Reduce size to stay diversified.",
                {"projected_weight_pct": round(projected_weight, 1), "hard_limit_pct": MAX_POSITION_PCT},
            ))
        elif projected_weight > WARN_POSITION_PCT:
            checks.append(Check(
                "concentration", "warn",
                f"{symbol} would be {projected_weight:.0f}% of equity (soft limit {WARN_POSITION_PCT:.0f}%). "
                f"Concentrated, but allowed.",
                {"projected_weight_pct": round(projected_weight, 1), "soft_limit_pct": WARN_POSITION_PCT},
            ))
        else:
            checks.append(Check(
                "concentration", "pass",
                f"{symbol} would be {projected_weight:.0f}% of equity — well diversified.",
                {"projected_weight_pct": round(projected_weight, 1)},
            ))

    # --- 5. Short-sale / over-sell flag (sells) -----------------------------
    if side == "sell":
        if qty > held_qty + 1e-9:
            short_qty = qty - held_qty
            checks.append(Check(
                "short_sale", "warn",
                f"Selling {qty:g} but only {held_qty:g} {symbol} held — {short_qty:g} would open a SHORT. "
                f"Confirm shorting is intended (many mandates forbid it).",
                {"held": held_qty, "selling": qty, "short_qty": short_qty},
            ))
        else:
            checks.append(Check("short_sale", "pass", f"Sell {qty:g} of {held_qty:g} held — long-only, no short created."))

        # Wash-sale awareness: closing a loser may trigger a wash sale if rebought ≤30d.
        if held and _f(held.get("unrealized_pl")) < 0:
            checks.append(Check(
                "wash_sale", "warn",
                f"{symbol} is held at a loss (${_f(held.get('unrealized_pl')):,.0f}). "
                f"Re-buying within 30 days would be a wash sale (loss disallowed for tax).",
            ))

    # --- 6. PDT (pattern day trader) equity floor ---------------------------
    if equity > 0 and equity < PDT_EQUITY_FLOOR:
        checks.append(Check(
            "pattern_day_trader", "warn",
            f"Account equity ${equity:,.0f} is below the $25,000 PDT floor. "
            f"Four+ day-trades in 5 business days would flag a Pattern Day Trader restriction.",
            {"equity": round(equity, 2), "floor": PDT_EQUITY_FLOOR},
        ))

    # --- 7. Liquidity / penny-stock risk ------------------------------------
    if 0 < px < PENNY_PRICE:
        checks.append(Check(
            "liquidity", "warn",
            f"{symbol} trades at ${px:.2f} (< ${PENNY_PRICE:.0f}) — penny/low-liquidity risk: wide spreads, gap risk.",
        ))

    return _assemble(symbol, side, qty, notional, projected_weight, checks)


def _assemble(symbol: str, side: str, qty: float, notional: float,
              projected_weight: float, checks: List[Check]) -> Dict[str, Any]:
    decision = PASS
    for c in checks:
        sev = {"pass": PASS, "warn": WARN, "block": BLOCK}[c.status]
        if _SEVERITY[sev] > _SEVERITY[decision]:
            decision = sev

    blocks = [c for c in checks if c.status == "block"]
    warns = [c for c in checks if c.status == "warn"]
    if decision == BLOCK:
        summary = "BLOCKED — " + "; ".join(c.detail for c in blocks)
    elif decision == WARN:
        summary = f"Cleared with {len(warns)} advisory note(s): " + "; ".join(c.detail for c in warns)
    else:
        summary = f"All {len(checks)} pre-trade controls passed."

    return {
        "ok": decision != BLOCK,
        "decision": decision,
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "notional": round(notional, 2),
        "projected_weight_pct": round(projected_weight, 1),
        "checks": [c.as_dict() for c in checks],
        "summary": summary,
        "disclosures": [DISCLOSURE],
    }
