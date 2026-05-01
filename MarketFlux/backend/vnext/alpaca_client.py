"""Alpaca Trading API client for MarketFlux.

Uses the Trading API (paper or live) for direct trading under a single account.
Supports all order types, retry logic, and structured error handling.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .alpaca_config import AlpacaConfig, get_alpaca_config

logger = logging.getLogger(__name__)

_trading_client = None


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

@dataclass
class AlpacaError:
    code: str
    message: str
    status_code: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"error_code": self.code, "message": self.message, "status_code": self.status_code}


class AlpacaClientError(Exception):
    def __init__(self, error: AlpacaError):
        self.error = error
        super().__init__(error.message)


# ---------------------------------------------------------------------------
# Client Lifecycle
# ---------------------------------------------------------------------------

def _get_trading_client():
    """Lazy-initialize and return the singleton TradingClient."""
    global _trading_client
    if _trading_client is not None:
        return _trading_client

    config = get_alpaca_config()
    if not config:
        return None

    from alpaca.trading.client import TradingClient

    _trading_client = TradingClient(
        api_key=config.api_key,
        secret_key=config.api_secret,
        paper=config.is_paper,
    )
    return _trading_client


def reset_client() -> None:
    global _trading_client
    _trading_client = None


def is_alpaca_configured() -> bool:
    return get_alpaca_config() is not None


def _with_retry(fn, *args, **kwargs) -> Any:
    """Execute fn with retries and exponential backoff."""
    config = get_alpaca_config()
    max_retries = config.max_retries if config else 3
    backoff = config.retry_backoff_seconds if config else 1.0

    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            exc_str = str(exc)
            if "422" in exc_str or "404" in exc_str or "400" in exc_str or "403" in exc_str:
                raise
            if attempt < max_retries:
                wait = backoff * (2 ** attempt)
                logger.warning(f"Alpaca API retry {attempt + 1}/{max_retries} after {wait}s: {exc}")
                time.sleep(wait)
            else:
                logger.error(f"Alpaca API failed after {max_retries} retries: {exc}")
                raise


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

def get_account() -> Optional[Dict[str, Any]]:
    """Get account details: cash, equity, buying power, etc."""
    client = _get_trading_client()
    if not client:
        return None
    try:
        account = _with_retry(client.get_account)
        return {
            "account_id": str(account.id),
            "account_number": account.account_number,
            "status": str(account.status),
            "cash": str(account.cash),
            "buying_power": str(account.buying_power),
            "equity": str(account.equity),
            "portfolio_value": str(account.portfolio_value),
            "last_equity": str(account.last_equity),
            "long_market_value": str(account.long_market_value),
            "short_market_value": str(account.short_market_value),
            "initial_margin": str(account.initial_margin),
            "maintenance_margin": str(account.maintenance_margin),
            "daytrade_count": account.daytrade_count,
            "pattern_day_trader": account.pattern_day_trader,
            "trading_blocked": account.trading_blocked,
            "shorting_enabled": account.shorting_enabled,
            "multiplier": str(account.multiplier),
            "currency": str(account.currency) if account.currency else "USD",
            "created_at": str(account.created_at) if account.created_at else None,
        }
    except Exception as exc:
        logger.error(f"Alpaca get_account failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

def submit_order(
    symbol: str,
    qty: Optional[float] = None,
    notional: Optional[float] = None,
    side: str = "buy",
    order_type: str = "market",
    time_in_force: str = "day",
    limit_price: Optional[float] = None,
    stop_price: Optional[float] = None,
    trail_percent: Optional[float] = None,
    trail_price: Optional[float] = None,
    extended_hours: bool = False,
    client_order_id: Optional[str] = None,
    take_profit_limit_price: Optional[float] = None,
    stop_loss_stop_price: Optional[float] = None,
    stop_loss_limit_price: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Submit any order type."""
    client = _get_trading_client()
    if not client:
        return None

    config = get_alpaca_config()
    from alpaca.trading.enums import OrderSide, TimeInForce

    order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
    tif = _parse_time_in_force(time_in_force)

    if qty and config and qty > config.max_order_qty:
        raise AlpacaClientError(AlpacaError(
            code="ORDER_QTY_EXCEEDED",
            message=f"Order quantity {qty} exceeds maximum {config.max_order_qty}",
        ))

    order_data = _build_order_request(
        symbol=symbol.upper(),
        qty=qty,
        notional=notional,
        side=order_side,
        order_type=order_type,
        time_in_force=tif,
        limit_price=limit_price,
        stop_price=stop_price,
        trail_percent=trail_percent,
        trail_price=trail_price,
        extended_hours=extended_hours,
        client_order_id=client_order_id,
        take_profit_limit_price=take_profit_limit_price,
        stop_loss_stop_price=stop_loss_stop_price,
        stop_loss_limit_price=stop_loss_limit_price,
    )

    try:
        order = _with_retry(client.submit_order, order_data)
        logger.info(f"Order submitted: {order.id} | {symbol} {side} {qty or notional} ({order_type})")
        return _serialize_order(order)
    except AlpacaClientError:
        raise
    except Exception as exc:
        logger.error(f"Alpaca submit_order failed: {exc}")
        return None


def submit_market_order(symbol: str, qty: float, side: str, time_in_force: str = "day") -> Optional[Dict[str, Any]]:
    return submit_order(symbol=symbol, qty=qty, side=side, order_type="market", time_in_force=time_in_force)


def submit_limit_order(symbol: str, qty: float, side: str, limit_price: float, time_in_force: str = "day") -> Optional[Dict[str, Any]]:
    return submit_order(symbol=symbol, qty=qty, side=side, order_type="limit", limit_price=limit_price, time_in_force=time_in_force)


def submit_stop_order(symbol: str, qty: float, side: str, stop_price: float, time_in_force: str = "day") -> Optional[Dict[str, Any]]:
    return submit_order(symbol=symbol, qty=qty, side=side, order_type="stop", stop_price=stop_price, time_in_force=time_in_force)


def submit_bracket_order(
    symbol: str, qty: float, side: str,
    take_profit_limit_price: float, stop_loss_stop_price: float,
    stop_loss_limit_price: Optional[float] = None, time_in_force: str = "day",
) -> Optional[Dict[str, Any]]:
    return submit_order(
        symbol=symbol, qty=qty, side=side, order_type="market", time_in_force=time_in_force,
        take_profit_limit_price=take_profit_limit_price,
        stop_loss_stop_price=stop_loss_stop_price,
        stop_loss_limit_price=stop_loss_limit_price,
    )


def get_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return None
    try:
        order = _with_retry(client.get_order_by_id, order_id)
        return _serialize_order(order)
    except Exception as exc:
        logger.error(f"Alpaca get_order failed: {exc}")
        return None


def list_orders(status: str = "all", limit: int = 50) -> List[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return []

    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus

    status_map = {
        "open": QueryOrderStatus.OPEN,
        "closed": QueryOrderStatus.CLOSED,
        "all": QueryOrderStatus.ALL,
    }
    request_params = GetOrdersRequest(status=status_map.get(status, QueryOrderStatus.ALL), limit=limit)

    try:
        orders = _with_retry(client.get_orders, request_params)
        return [_serialize_order(o) for o in (orders or [])]
    except Exception as exc:
        logger.error(f"Alpaca list_orders failed: {exc}")
        return []


def cancel_order_by_id(order_id: str) -> bool:
    client = _get_trading_client()
    if not client:
        return False
    try:
        _with_retry(client.cancel_order_by_id, order_id)
        logger.info(f"Order cancelled: {order_id}")
        return True
    except Exception as exc:
        logger.error(f"Alpaca cancel_order failed: {exc}")
        return False


def cancel_all_orders() -> bool:
    client = _get_trading_client()
    if not client:
        return False
    try:
        _with_retry(client.cancel_orders)
        logger.info("All orders cancelled")
        return True
    except Exception as exc:
        logger.error(f"Alpaca cancel_all_orders failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

def get_all_positions() -> List[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return []
    try:
        positions = _with_retry(client.get_all_positions)
        return [_serialize_position(p) for p in (positions or [])]
    except Exception as exc:
        logger.error(f"Alpaca get_all_positions failed: {exc}")
        return []


def get_position(symbol: str) -> Optional[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return None
    try:
        position = _with_retry(client.get_open_position, symbol.upper())
        return _serialize_position(position)
    except Exception as exc:
        logger.error(f"Alpaca get_position failed for {symbol}: {exc}")
        return None


def close_position(symbol: str, qty: Optional[float] = None) -> Optional[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return None
    from alpaca.trading.requests import ClosePositionRequest
    close_options = ClosePositionRequest(qty=str(qty)) if qty else None
    try:
        order = _with_retry(client.close_position, symbol.upper(), close_options=close_options)
        logger.info(f"Position closed: {symbol} (qty={qty or 'all'})")
        return _serialize_order(order)
    except Exception as exc:
        logger.error(f"Alpaca close_position failed for {symbol}: {exc}")
        return None


def close_all_positions() -> bool:
    client = _get_trading_client()
    if not client:
        return False
    try:
        _with_retry(client.close_all_positions, cancel_orders=True)
        logger.info("All positions closed")
        return True
    except Exception as exc:
        logger.error(f"Alpaca close_all_positions failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Portfolio History
# ---------------------------------------------------------------------------

def get_portfolio_history(period: str = "1M", timeframe: str = "1D") -> Optional[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return None
    from alpaca.trading.requests import GetPortfolioHistoryRequest
    try:
        history = _with_retry(
            client.get_portfolio_history,
            GetPortfolioHistoryRequest(period=period, timeframe=timeframe),
        )
        return {
            "timestamp": list(history.timestamp) if history.timestamp else [],
            "equity": list(history.equity) if history.equity else [],
            "profit_loss": list(history.profit_loss) if history.profit_loss else [],
            "profit_loss_pct": list(history.profit_loss_pct) if history.profit_loss_pct else [],
            "base_value": float(history.base_value) if history.base_value else 0,
            "timeframe": timeframe,
        }
    except Exception as exc:
        logger.error(f"Alpaca get_portfolio_history failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

def get_asset(symbol: str) -> Optional[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return None
    try:
        asset = _with_retry(client.get_asset, symbol.upper())
        return {
            "id": str(asset.id),
            "symbol": asset.symbol,
            "name": asset.name,
            "exchange": str(asset.exchange) if asset.exchange else None,
            "asset_class": str(asset.asset_class) if asset.asset_class else None,
            "tradable": asset.tradable,
            "fractionable": asset.fractionable,
            "shortable": asset.shortable,
            "easy_to_borrow": asset.easy_to_borrow,
            "status": str(asset.status) if asset.status else None,
        }
    except Exception as exc:
        logger.error(f"Alpaca get_asset failed for {symbol}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_time_in_force(tif: str):
    from alpaca.trading.enums import TimeInForce
    mapping = {
        "day": TimeInForce.DAY, "gtc": TimeInForce.GTC,
        "ioc": TimeInForce.IOC, "fok": TimeInForce.FOK,
        "opg": TimeInForce.OPG, "cls": TimeInForce.CLS,
    }
    return mapping.get(tif.lower(), TimeInForce.DAY)


def _build_order_request(
    symbol, qty, notional, side, order_type, time_in_force,
    limit_price, stop_price, trail_percent, trail_price,
    extended_hours, client_order_id,
    take_profit_limit_price, stop_loss_stop_price, stop_loss_limit_price,
):
    from alpaca.trading.requests import (
        MarketOrderRequest, LimitOrderRequest,
        StopOrderRequest, StopLimitOrderRequest,
        TrailingStopOrderRequest, TakeProfitRequest, StopLossRequest,
    )
    from alpaca.trading.enums import OrderClass

    order_class = None
    take_profit = None
    stop_loss = None

    if take_profit_limit_price or stop_loss_stop_price:
        if take_profit_limit_price and stop_loss_stop_price:
            order_class = OrderClass.BRACKET
        else:
            order_class = OrderClass.OTO
        if take_profit_limit_price:
            take_profit = TakeProfitRequest(limit_price=take_profit_limit_price)
        if stop_loss_stop_price:
            stop_loss = StopLossRequest(stop_price=stop_loss_stop_price, limit_price=stop_loss_limit_price)

    base: Dict[str, Any] = {"symbol": symbol, "side": side, "time_in_force": time_in_force}
    if qty is not None:
        base["qty"] = qty
    elif notional is not None:
        base["notional"] = notional
    else:
        raise AlpacaClientError(AlpacaError(code="MISSING_QTY", message="Either qty or notional must be specified"))

    if extended_hours:
        base["extended_hours"] = True
    if client_order_id:
        base["client_order_id"] = client_order_id
    if order_class:
        base["order_class"] = order_class
    if take_profit:
        base["take_profit"] = take_profit
    if stop_loss:
        base["stop_loss"] = stop_loss

    if order_type == "market":
        return MarketOrderRequest(**base)
    elif order_type == "limit":
        return LimitOrderRequest(limit_price=limit_price, **base)
    elif order_type == "stop":
        return StopOrderRequest(stop_price=stop_price, **base)
    elif order_type == "stop_limit":
        return StopLimitOrderRequest(limit_price=limit_price, stop_price=stop_price, **base)
    elif order_type == "trailing_stop":
        if trail_percent is not None:
            base["trail_percent"] = trail_percent
        elif trail_price is not None:
            base["trail_price"] = trail_price
        return TrailingStopOrderRequest(**base)
    else:
        raise AlpacaClientError(AlpacaError(code="INVALID_ORDER_TYPE", message=f"Unsupported: {order_type}"))


def _serialize_order(order) -> Dict[str, Any]:
    return {
        "order_id": str(order.id) if order.id else None,
        "client_order_id": order.client_order_id if hasattr(order, "client_order_id") else None,
        "symbol": order.symbol,
        "qty": str(order.qty) if order.qty else None,
        "notional": str(order.notional) if hasattr(order, "notional") and order.notional else None,
        "filled_qty": str(order.filled_qty) if order.filled_qty else "0",
        "side": str(order.side) if order.side else None,
        "type": str(order.type) if order.type else None,
        "order_class": str(order.order_class) if hasattr(order, "order_class") and order.order_class else None,
        "time_in_force": str(order.time_in_force) if order.time_in_force else None,
        "status": str(order.status) if order.status else None,
        "limit_price": str(order.limit_price) if order.limit_price else None,
        "stop_price": str(order.stop_price) if order.stop_price else None,
        "filled_avg_price": str(order.filled_avg_price) if order.filled_avg_price else None,
        "extended_hours": order.extended_hours if hasattr(order, "extended_hours") else False,
        "created_at": str(order.created_at) if order.created_at else None,
        "filled_at": str(order.filled_at) if order.filled_at else None,
        "canceled_at": str(order.canceled_at) if hasattr(order, "canceled_at") and order.canceled_at else None,
        "legs": [_serialize_order(leg) for leg in order.legs] if hasattr(order, "legs") and order.legs else None,
    }


def _serialize_position(position) -> Dict[str, Any]:
    return {
        "symbol": position.symbol,
        "qty": str(position.qty) if position.qty else "0",
        "side": str(position.side) if position.side else None,
        "avg_entry_price": str(position.avg_entry_price) if position.avg_entry_price else "0",
        "market_value": str(position.market_value) if position.market_value else "0",
        "cost_basis": str(position.cost_basis) if position.cost_basis else "0",
        "unrealized_pl": str(position.unrealized_pl) if position.unrealized_pl else "0",
        "unrealized_plpc": str(position.unrealized_plpc) if position.unrealized_plpc else "0",
        "current_price": str(position.current_price) if position.current_price else "0",
        "lastday_price": str(position.lastday_price) if position.lastday_price else "0",
        "change_today": str(position.change_today) if position.change_today else "0",
    }
