"""
Alpaca Markets paper-trading bridge for FundOS.

Wraps the alpaca-py SDK to provide:
- Account info
- List of open positions and pending orders
- Submitting a new paper order (requires prior human approval gate)
- Getting recent order history

All methods gracefully fall back when ALPACA_API_KEY / ALPACA_SECRET_KEY
environment variables are not configured.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)

_PAPER_BASE_URL = "https://paper-api.alpaca.markets"


def _get_client():
    """Return an alpaca-py TradingClient configured for paper trading, or None."""
    try:
        from alpaca.trading.client import TradingClient  # type: ignore
    except ImportError:
        _log.warning("alpaca-py not installed; Alpaca connectivity disabled")
        return None

    api_key = os.getenv("ALPACA_API_KEY", "")
    secret_key = os.getenv("ALPACA_SECRET_KEY", "")
    if not api_key or not secret_key:
        return None

    return TradingClient(api_key=api_key, secret_key=secret_key, paper=True)


def is_configured() -> bool:
    """Return True when Alpaca credentials are available and the SDK is installed."""
    return _get_client() is not None


def get_account_info() -> Dict[str, Any]:
    """Return paper-trading account summary, or an error dict."""
    client = _get_client()
    if client is None:
        return {"error": "Alpaca not configured"}
    try:
        acct = client.get_account()
        return {
            "id": str(acct.id),
            "status": str(acct.status),
            "equity": float(acct.equity or 0),
            "cash": float(acct.cash or 0),
            "buying_power": float(acct.buying_power or 0),
            "portfolio_value": float(acct.portfolio_value or 0),
            "currency": str(acct.currency or "USD"),
            "pattern_day_trader": bool(acct.pattern_day_trader),
            "trading_blocked": bool(acct.trading_blocked),
            "is_paper": True,
        }
    except Exception as exc:
        _log.error("Alpaca get_account failed", exc_info=True)
        return {"error": str(exc)}


def get_positions() -> List[Dict[str, Any]]:
    """Return open positions in the paper account."""
    client = _get_client()
    if client is None:
        return []
    try:
        positions = client.get_all_positions()
        result = []
        for p in positions:
            result.append({
                "symbol": str(p.symbol),
                "qty": float(p.qty or 0),
                "avg_entry_price": float(p.avg_entry_price or 0),
                "current_price": float(p.current_price or 0),
                "market_value": float(p.market_value or 0),
                "unrealized_pl": float(p.unrealized_pl or 0),
                "unrealized_plpc": float(p.unrealized_plpc or 0),
                "side": str(p.side),
            })
        return result
    except Exception as exc:
        _log.error("Alpaca get_all_positions failed", exc_info=True)
        return []


def get_orders(status: str = "all", limit: int = 20) -> List[Dict[str, Any]]:
    """Return recent orders from the paper account."""
    client = _get_client()
    if client is None:
        return []
    try:
        from alpaca.trading.requests import GetOrdersRequest  # type: ignore
        from alpaca.trading.enums import QueryOrderStatus  # type: ignore

        status_map = {
            "open": QueryOrderStatus.OPEN,
            "closed": QueryOrderStatus.CLOSED,
            "all": QueryOrderStatus.ALL,
        }
        req = GetOrdersRequest(status=status_map.get(status, QueryOrderStatus.ALL), limit=limit)
        orders = client.get_orders(filter=req)
        result = []
        for o in orders:
            result.append({
                "id": str(o.id),
                "client_order_id": str(o.client_order_id),
                "symbol": str(o.symbol),
                "side": str(o.side),
                "type": str(o.type),
                "qty": float(o.qty or 0),
                "filled_qty": float(o.filled_qty or 0),
                "filled_avg_price": float(o.filled_avg_price or 0) if o.filled_avg_price else None,
                "status": str(o.status),
                "submitted_at": o.submitted_at.isoformat() if o.submitted_at else None,
                "filled_at": o.filled_at.isoformat() if o.filled_at else None,
            })
        return result
    except Exception as exc:
        _log.error("Alpaca get_orders failed", exc_info=True)
        return []


def submit_paper_order(
    symbol: str,
    qty: float,
    side: str,
    order_type: str = "market",
    time_in_force: str = "day",
    limit_price: Optional[float] = None,
    strategy_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Submit a paper order to Alpaca.

    This must only be called after the user has explicitly confirmed via the
    human-approval gate in the FundOS UI. It is the caller's responsibility to
    enforce that gate — this function does NOT perform any additional checks.

    Parameters
    ----------
    symbol          Ticker symbol (e.g. "NVDA")
    qty             Number of shares
    side            "buy" | "sell"
    order_type      "market" | "limit"
    time_in_force   "day" | "gtc"
    limit_price     Required when order_type == "limit"
    strategy_id     Arbitrary reference tag stored in client_order_id prefix
    """
    client = _get_client()
    if client is None:
        return {"error": "Alpaca not configured"}

    try:
        from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest  # type: ignore
        from alpaca.trading.enums import OrderSide, TimeInForce  # type: ignore

        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        tif_enum = TimeInForce.DAY if time_in_force.lower() == "day" else TimeInForce.GTC

        tag = f"fundos-{strategy_id}" if strategy_id else "fundos"

        if order_type.lower() == "limit":
            if not limit_price:
                return {"error": "limit_price required for limit orders"}
            req = LimitOrderRequest(
                symbol=symbol.upper(),
                qty=qty,
                side=side_enum,
                time_in_force=tif_enum,
                limit_price=limit_price,
                client_order_id=f"{tag}-{symbol.lower()}-{side.lower()}",
            )
        else:
            req = MarketOrderRequest(
                symbol=symbol.upper(),
                qty=qty,
                side=side_enum,
                time_in_force=tif_enum,
                client_order_id=f"{tag}-{symbol.lower()}-{side.lower()}",
            )

        order = client.submit_order(order_data=req)
        return {
            "id": str(order.id),
            "client_order_id": str(order.client_order_id),
            "symbol": str(order.symbol),
            "side": str(order.side),
            "type": str(order.type),
            "qty": float(order.qty or qty),
            "status": str(order.status),
            "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
            "is_paper": True,
        }
    except Exception as exc:
        _log.error("Alpaca submit_order failed for %s", symbol, exc_info=True)
        return {"error": str(exc)}
