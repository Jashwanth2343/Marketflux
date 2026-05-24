"""Trading tools for the MarketFlux Copilot agent.

These wrap vnext.alpaca_client so the conversational agent can actually inspect
the paper account and execute trades. Every function is a plain sync callable
with a descriptive docstring — that docstring becomes the tool description the
LLM sees, so it must read like an instruction manual for the model.

ALL trading is on the Alpaca PAPER account (no real money). Guardrails here are
a defense-in-depth layer; Alpaca itself also rejects orders over buying power.
"""
from __future__ import annotations

import logging
import os

from vnext import alpaca_client

logger = logging.getLogger(__name__)

# Soft ceiling on a single order's notional value. Prevents the agent from
# fat-fingering an absurd order even on paper. Override via env if desired.
MAX_ORDER_NOTIONAL = float(os.getenv("COPILOT_MAX_ORDER_NOTIONAL", "60000"))


def _err(message: str, **extra) -> dict:
    return {"ok": False, "error": message, **extra}


def _clean(value):
    """Normalize Alpaca enum reprs like 'PositionSide.LONG' -> 'long'."""
    if value is None:
        return None
    s = str(value)
    if "." in s and s.split(".")[0][:1].isupper():
        s = s.split(".", 1)[1]
    return s.lower() if s.isupper() else s


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

def get_account_summary() -> dict:
    """Get the live paper-trading account: equity, cash, buying power, and P&L
    since yesterday. Call this BEFORE buying so you know how much capital is
    available, and to report the portfolio's overall value to the user."""
    acct = alpaca_client.get_account()
    if not acct:
        return _err("Alpaca account unavailable. The broker may be unconfigured.")
    try:
        equity = float(acct.get("equity") or 0)
        last_equity = float(acct.get("last_equity") or 0)
        day_pl = equity - last_equity
        day_pl_pct = (day_pl / last_equity * 100) if last_equity else 0.0
    except (TypeError, ValueError):
        day_pl = day_pl_pct = 0.0
    return {
        "ok": True,
        "status": _clean(acct.get("status")),
        "equity": acct.get("equity"),
        "cash": acct.get("cash"),
        "buying_power": acct.get("buying_power"),
        "portfolio_value": acct.get("portfolio_value"),
        "day_pl": round(day_pl, 2),
        "day_pl_pct": round(day_pl_pct, 2),
        "currency": acct.get("currency", "USD"),
    }


def get_open_positions() -> dict:
    """List every stock currently held in the paper portfolio, with quantity,
    average entry price, current price, market value, and unrealized P&L. Call
    this to see what's already owned before adding to a position or trimming."""
    positions = alpaca_client.get_positions()
    cleaned = []
    for p in positions:
        cleaned.append({
            "symbol": p.get("symbol"),
            "qty": p.get("qty"),
            "side": _clean(p.get("side")),
            "avg_entry_price": p.get("avg_entry_price"),
            "current_price": p.get("current_price"),
            "market_value": p.get("market_value"),
            "unrealized_pl": p.get("unrealized_pl"),
            "unrealized_pl_pct": _pct(p.get("unrealized_plpc")),
        })
    return {"ok": True, "count": len(cleaned), "positions": cleaned}


def get_orders(status: str = "all", limit: int = 20) -> dict:
    """List recent orders on the paper account. status is "open" (still working),
    "closed" (filled/cancelled), or "all". Use this to check whether a trade you
    placed actually filled, or to review recent activity."""
    status = (status or "all").lower()
    if status not in ("open", "closed", "all"):
        status = "all"
    orders = alpaca_client.list_orders(status=status, limit=min(max(int(limit), 1), 100))
    cleaned = [{
        "symbol": o.get("symbol"),
        "side": _clean(o.get("side")),
        "qty": o.get("qty"),
        "filled_qty": o.get("filled_qty"),
        "type": _clean(o.get("type")),
        "status": _clean(o.get("status")),
        "filled_avg_price": o.get("filled_avg_price"),
        "limit_price": o.get("limit_price"),
        "submitted_at": o.get("submitted_at"),
    } for o in orders]
    return {"ok": True, "count": len(cleaned), "orders": cleaned}


def get_market_clock() -> dict:
    """Check whether the US stock market is currently open, and when it next opens
    or closes. Market orders placed while closed will queue until the next open —
    mention this to the user if relevant."""
    clock = alpaca_client.get_clock()
    if not clock:
        return _err("Could not fetch market clock.")
    return {"ok": True, **clock}


def get_portfolio_history(period: str = "1M", timeframe: str = "1D") -> dict:
    """Get the paper account's equity curve over time, for reviewing performance.
    period is one of 1D, 1W, 1M, 3M, 6M, 1A, all. timeframe is 1Min, 5Min, 15Min,
    1H, or 1D."""
    hist = alpaca_client.get_portfolio_history(period=period, timeframe=timeframe)
    if not hist:
        return _err("No portfolio history available.")
    equity = hist.get("equity") or []
    start = equity[0] if equity else 0
    end = equity[-1] if equity else 0
    change = end - start if (start and end) else 0
    return {
        "ok": True,
        "period": period,
        "points": len(equity),
        "start_equity": start,
        "end_equity": end,
        "change": round(change, 2),
        "change_pct": round((change / start * 100), 2) if start else 0,
    }


# ---------------------------------------------------------------------------
# Write tools (these actually execute)
# ---------------------------------------------------------------------------

def place_order(
    symbol: str,
    quantity: float,
    side: str,
    order_type: str = "market",
    limit_price: float = 0.0,
    time_in_force: str = "day",
) -> dict:
    """EXECUTE a real paper-trading order on the user's Alpaca paper account. This
    actually buys or sells stock — only call it when the user wants to trade or
    after you've decided a trade is warranted and explained your reasoning.

    Args:
        symbol: Stock ticker, e.g. "NVDA".
        quantity: Number of shares (whole numbers are safest; fractional is allowed
            for market orders). Must be greater than 0.
        side: "buy" or "sell".
        order_type: "market" (fills immediately at the current price, the default)
            or "limit".
        limit_price: Required only for limit orders — the worst price you'll accept
            (max for a buy, min for a sell). Leave at 0 for market orders.
        time_in_force: "day" (default) or "gtc" (good-till-cancelled).

    Returns the submitted order with its status and fill price, or an error dict.
    """
    symbol = (symbol or "").strip().upper()
    side = (side or "").strip().lower()
    order_type = (order_type or "market").strip().lower()
    time_in_force = (time_in_force or "day").strip().lower()

    if not symbol:
        return _err("symbol is required.")
    if side not in ("buy", "sell"):
        return _err("side must be 'buy' or 'sell'.")
    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        return _err("quantity must be a number.")
    if quantity <= 0:
        return _err("quantity must be greater than 0.")
    if order_type not in ("market", "limit"):
        return _err("order_type must be 'market' or 'limit'.")

    if not alpaca_client.is_alpaca_configured():
        return _err("Alpaca is not configured; cannot place orders.")

    if order_type == "limit":
        try:
            limit_price = float(limit_price)
        except (TypeError, ValueError):
            return _err("limit_price must be a number for limit orders.")
        if limit_price <= 0:
            return _err("limit_price must be greater than 0 for a limit order.")
        notional = quantity * limit_price
        if notional > MAX_ORDER_NOTIONAL:
            return _err(
                f"Order notional ${notional:,.0f} exceeds the per-order safety cap "
                f"of ${MAX_ORDER_NOTIONAL:,.0f}. Reduce the size.",
                notional=round(notional, 2),
                cap=MAX_ORDER_NOTIONAL,
            )
        order = alpaca_client.submit_limit_order(
            symbol=symbol, qty=quantity, side=side,
            limit_price=limit_price, time_in_force=time_in_force,
        )
    else:
        current_price = _estimate_price(symbol)
        if current_price > 0:
            est_notional = quantity * current_price
            if est_notional > MAX_ORDER_NOTIONAL:
                return _err(
                    f"Estimated market order notional ~${est_notional:,.0f} exceeds the "
                    f"per-order safety cap of ${MAX_ORDER_NOTIONAL:,.0f}. Reduce the size.",
                    notional=round(est_notional, 2),
                    cap=MAX_ORDER_NOTIONAL,
                )
        order = alpaca_client.submit_market_order(
            symbol=symbol, qty=quantity, side=side, time_in_force=time_in_force,
        )

    if not order:
        return _err(
            f"Order rejected by broker. Common causes: insufficient buying power, "
            f"invalid/non-tradable symbol ({symbol}), or fractional shares on a limit order."
        )
    return {
        "ok": True,
        "executed": True,
        "order_id": order.get("order_id"),
        "symbol": order.get("symbol"),
        "side": _clean(order.get("side")),
        "qty": order.get("qty"),
        "order_type": _clean(order.get("type")),
        "status": _clean(order.get("status")),
        "filled_avg_price": order.get("filled_avg_price"),
        "submitted_at": order.get("submitted_at"),
    }


def close_position(symbol: str) -> dict:
    """Fully exit a holding — sells the entire position in `symbol` at market.
    Use when the user wants out of a name, or to take profit / cut a loss."""
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return _err("symbol is required.")
    if not alpaca_client.is_alpaca_configured():
        return _err("Alpaca is not configured; cannot close positions.")
    order = alpaca_client.close_position(symbol)
    if not order:
        return _err(f"Could not close {symbol}. There may be no open position in it.")
    return {
        "ok": True,
        "executed": True,
        "closed_symbol": symbol,
        "order_id": order.get("order_id"),
        "side": _clean(order.get("side")),
        "qty": order.get("qty"),
        "status": _clean(order.get("status")),
    }


def cancel_all_open_orders() -> dict:
    """Cancel every currently open (unfilled) order on the paper account. Does not
    affect positions that have already filled."""
    if not alpaca_client.is_alpaca_configured():
        return _err("Alpaca is not configured.")
    ok = alpaca_client.cancel_all_orders()
    return {"ok": bool(ok), "cancelled_all_open_orders": bool(ok)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _estimate_price(symbol: str) -> float:
    """Best-effort current price for notional cap checks on market orders."""
    for pos in alpaca_client.get_positions():
        if pos.get("symbol", "").upper() == symbol:
            try:
                return float(pos["current_price"])
            except (KeyError, TypeError, ValueError):
                pass
    try:
        import yfinance as yf
        tick = yf.Ticker(symbol)
        info = tick.fast_info
        return float(getattr(info, "last_price", 0) or 0)
    except Exception:
        return 0.0


def _pct(raw) -> float:
    """Alpaca returns unrealized_plpc as a fraction string (e.g. '0.0123'). To %."""
    try:
        return round(float(raw) * 100, 2)
    except (TypeError, ValueError):
        return 0.0


# Tools the Copilot agent is allowed to call (name -> callable).
TRADING_TOOLS = {
    "get_account_summary": get_account_summary,
    "get_open_positions": get_open_positions,
    "get_orders": get_orders,
    "get_market_clock": get_market_clock,
    "get_portfolio_history": get_portfolio_history,
    "place_order": place_order,
    "close_position": close_position,
    "cancel_all_open_orders": cancel_all_open_orders,
}

# Names that mutate the account — used by the agent loop to emit "trade" events.
EXECUTION_TOOLS = {"place_order", "close_position", "cancel_all_open_orders"}
