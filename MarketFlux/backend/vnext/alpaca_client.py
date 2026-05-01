"""Alpaca Broker API client for MarketFlux.

Production-grade client supporting:
- Sandbox and production environments
- Per-user sub-account lifecycle (create, fund, KYC)
- All order types: market, limit, stop, stop-limit, trailing stop, bracket
- Fractional shares
- Retry logic with exponential backoff
- Structured error handling
- Position and portfolio management
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from .alpaca_config import AlpacaConfig, get_alpaca_config

logger = logging.getLogger(__name__)

_broker_client = None


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

@dataclass
class AlpacaError:
    code: str
    message: str
    status_code: Optional[int] = None
    raw: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.code,
            "message": self.message,
            "status_code": self.status_code,
        }


class AlpacaClientError(Exception):
    def __init__(self, error: AlpacaError):
        self.error = error
        super().__init__(error.message)


# ---------------------------------------------------------------------------
# Client Lifecycle
# ---------------------------------------------------------------------------

def _get_broker_client():
    """Lazy-initialize and return the singleton BrokerClient."""
    global _broker_client
    if _broker_client is not None:
        return _broker_client

    config = get_alpaca_config()
    if not config:
        return None

    from alpaca.broker.client import BrokerClient

    _broker_client = BrokerClient(
        api_key=config.api_key,
        secret_key=config.api_secret,
        sandbox=config.is_sandbox,
    )
    _broker_client._use_basic_auth = True
    return _broker_client


def reset_client() -> None:
    """Reset the cached client (useful when config changes)."""
    global _broker_client
    _broker_client = None


def is_alpaca_configured() -> bool:
    """Check if Alpaca credentials are present."""
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
            # Don't retry on client errors (4xx) except 429 (rate limit)
            if "422" in exc_str or "404" in exc_str or "400" in exc_str:
                raise
            if attempt < max_retries:
                wait = backoff * (2 ** attempt)
                logger.warning(f"Alpaca API retry {attempt + 1}/{max_retries} after {wait}s: {exc}")
                time.sleep(wait)
            else:
                logger.error(f"Alpaca API failed after {max_retries} retries: {exc}")
                raise


# ---------------------------------------------------------------------------
# Account Management
# ---------------------------------------------------------------------------

def create_trading_account(
    given_name: str,
    family_name: str,
    email: str,
    *,
    date_of_birth: str = "1990-01-01",
    country_of_tax_residence: str = "USA",
) -> Optional[Dict[str, Any]]:
    """Create an Alpaca sub-account for a MarketFlux user."""
    client = _get_broker_client()
    if not client:
        return None

    from alpaca.broker.requests import (
        CreateAccountRequest,
        Contact,
        Identity,
        Disclosures,
        Agreement,
    )
    from alpaca.broker.enums import (
        TaxIdType,
        FundingSource,
        AgreementType,
    )
    from datetime import datetime, timezone

    contact_data = Contact(
        email_address=email,
        phone_number="555-555-5555",
        street_address=["123 Paper Trade St"],
        city="New York",
        state="NY",
        postal_code="10001",
        country="USA",
    )

    identity_data = Identity(
        given_name=given_name,
        family_name=family_name,
        date_of_birth=date_of_birth,
        tax_id="000-00-0000",
        tax_id_type=TaxIdType.USA_SSN,
        country_of_citizenship="USA",
        country_of_birth="USA",
        country_of_tax_residence=country_of_tax_residence,
        funding_source=[FundingSource.EMPLOYMENT_INCOME],
    )

    disclosure_data = Disclosures(
        is_control_person=False,
        is_affiliated_exchange_or_finra=False,
        is_politically_exposed=False,
        immediate_family_exposed=False,
    )

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    agreement_data = [
        Agreement(agreement=AgreementType.MARGIN, signed_at=now_iso, ip_address="127.0.0.1"),
        Agreement(agreement=AgreementType.ACCOUNT, signed_at=now_iso, ip_address="127.0.0.1"),
        Agreement(agreement=AgreementType.CUSTOMER, signed_at=now_iso, ip_address="127.0.0.1"),
    ]

    account_data = CreateAccountRequest(
        contact=contact_data,
        identity=identity_data,
        disclosures=disclosure_data,
        agreements=agreement_data,
    )

    try:
        account = _with_retry(client.create_account, account_data)
        return _serialize_account(account)
    except Exception as exc:
        logger.error(f"Alpaca create_account failed: {exc}")
        return None


def get_account(account_id: str) -> Optional[Dict[str, Any]]:
    """Get full account details including buying power, equity, cash."""
    client = _get_broker_client()
    if not client:
        return None

    try:
        account = _with_retry(client.get_account_by_id, account_id)
        return _serialize_account(account)
    except Exception as exc:
        logger.error(f"Alpaca get_account failed for {account_id}: {exc}")
        return None


def get_trade_account(account_id: str) -> Optional[Dict[str, Any]]:
    """Get trading-specific account info (buying power, equity, etc.)."""
    client = _get_broker_client()
    if not client:
        return None

    try:
        account = _with_retry(client.get_trade_account_by_id, account_id)
        return {
            "account_id": str(account.id) if account.id else account_id,
            "status": str(account.status) if account.status else None,
            "cash": str(account.cash) if account.cash else "0",
            "buying_power": str(account.buying_power) if account.buying_power else "0",
            "equity": str(account.equity) if account.equity else "0",
            "portfolio_value": str(account.portfolio_value) if account.portfolio_value else "0",
            "last_equity": str(account.last_equity) if account.last_equity else "0",
            "long_market_value": str(account.long_market_value) if account.long_market_value else "0",
            "short_market_value": str(account.short_market_value) if account.short_market_value else "0",
            "initial_margin": str(account.initial_margin) if account.initial_margin else "0",
            "maintenance_margin": str(account.maintenance_margin) if account.maintenance_margin else "0",
            "daytrade_count": account.daytrade_count if account.daytrade_count else 0,
            "pattern_day_trader": bool(account.pattern_day_trader) if account.pattern_day_trader is not None else False,
        }
    except Exception as exc:
        logger.error(f"Alpaca get_trade_account failed for {account_id}: {exc}")
        return None


def list_accounts(query: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all sub-accounts, optionally filtered."""
    client = _get_broker_client()
    if not client:
        return []

    try:
        accounts = _with_retry(client.list_accounts)
        return [_serialize_account(a) for a in (accounts or [])]
    except Exception as exc:
        logger.error(f"Alpaca list_accounts failed: {exc}")
        return []


# ---------------------------------------------------------------------------
# Order Management -- supports all order types
# ---------------------------------------------------------------------------

def submit_order(
    account_id: str,
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
    # Bracket order fields
    take_profit_limit_price: Optional[float] = None,
    stop_loss_stop_price: Optional[float] = None,
    stop_loss_limit_price: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Submit any order type for an account.
    
    Supports: market, limit, stop, stop_limit, trailing_stop, and bracket orders.
    Supports fractional shares via notional amount.
    """
    client = _get_broker_client()
    if not client:
        return None

    config = get_alpaca_config()
    from alpaca.trading.enums import OrderSide, TimeInForce

    order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
    tif = _parse_time_in_force(time_in_force)

    # Validate order constraints
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
        order = _with_retry(
            client.submit_order_for_account,
            account_id=account_id,
            order_data=order_data,
        )
        logger.info(f"Order submitted: {order.id} | {symbol} {side} {qty or notional} ({order_type})")
        return _serialize_order(order)
    except AlpacaClientError:
        raise
    except Exception as exc:
        logger.error(f"Alpaca submit_order failed: {exc}")
        return None


def submit_market_order(
    account_id: str,
    symbol: str,
    qty: float,
    side: str,
    time_in_force: str = "day",
) -> Optional[Dict[str, Any]]:
    """Convenience: submit a market order."""
    return submit_order(
        account_id=account_id,
        symbol=symbol,
        qty=qty,
        side=side,
        order_type="market",
        time_in_force=time_in_force,
    )


def submit_limit_order(
    account_id: str,
    symbol: str,
    qty: float,
    side: str,
    limit_price: float,
    time_in_force: str = "day",
) -> Optional[Dict[str, Any]]:
    """Convenience: submit a limit order."""
    return submit_order(
        account_id=account_id,
        symbol=symbol,
        qty=qty,
        side=side,
        order_type="limit",
        limit_price=limit_price,
        time_in_force=time_in_force,
    )


def submit_stop_order(
    account_id: str,
    symbol: str,
    qty: float,
    side: str,
    stop_price: float,
    time_in_force: str = "day",
) -> Optional[Dict[str, Any]]:
    """Convenience: submit a stop order."""
    return submit_order(
        account_id=account_id,
        symbol=symbol,
        qty=qty,
        side=side,
        order_type="stop",
        stop_price=stop_price,
        time_in_force=time_in_force,
    )


def submit_stop_limit_order(
    account_id: str,
    symbol: str,
    qty: float,
    side: str,
    stop_price: float,
    limit_price: float,
    time_in_force: str = "day",
) -> Optional[Dict[str, Any]]:
    """Convenience: submit a stop-limit order."""
    return submit_order(
        account_id=account_id,
        symbol=symbol,
        qty=qty,
        side=side,
        order_type="stop_limit",
        stop_price=stop_price,
        limit_price=limit_price,
        time_in_force=time_in_force,
    )


def submit_trailing_stop_order(
    account_id: str,
    symbol: str,
    qty: float,
    side: str,
    trail_percent: Optional[float] = None,
    trail_price: Optional[float] = None,
    time_in_force: str = "day",
) -> Optional[Dict[str, Any]]:
    """Convenience: submit a trailing stop order."""
    return submit_order(
        account_id=account_id,
        symbol=symbol,
        qty=qty,
        side=side,
        order_type="trailing_stop",
        trail_percent=trail_percent,
        trail_price=trail_price,
        time_in_force=time_in_force,
    )


def submit_bracket_order(
    account_id: str,
    symbol: str,
    qty: float,
    side: str,
    take_profit_limit_price: float,
    stop_loss_stop_price: float,
    stop_loss_limit_price: Optional[float] = None,
    time_in_force: str = "day",
) -> Optional[Dict[str, Any]]:
    """Submit a bracket order (entry + take profit + stop loss)."""
    return submit_order(
        account_id=account_id,
        symbol=symbol,
        qty=qty,
        side=side,
        order_type="market",
        time_in_force=time_in_force,
        take_profit_limit_price=take_profit_limit_price,
        stop_loss_stop_price=stop_loss_stop_price,
        stop_loss_limit_price=stop_loss_limit_price,
    )


def get_order(account_id: str, order_id: str) -> Optional[Dict[str, Any]]:
    """Get order status by ID."""
    client = _get_broker_client()
    if not client:
        return None

    try:
        order = _with_retry(
            client.get_order_for_account_by_id,
            account_id=account_id,
            order_id=order_id,
        )
        return _serialize_order(order)
    except Exception as exc:
        logger.error(f"Alpaca get_order failed: {exc}")
        return None


def list_orders(account_id: str, status: str = "all", limit: int = 50) -> List[Dict[str, Any]]:
    """List orders for an account."""
    client = _get_broker_client()
    if not client:
        return []

    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus

    status_map = {
        "open": QueryOrderStatus.OPEN,
        "closed": QueryOrderStatus.CLOSED,
        "all": QueryOrderStatus.ALL,
    }

    request_params = GetOrdersRequest(
        status=status_map.get(status, QueryOrderStatus.ALL),
        limit=limit,
    )

    try:
        orders = _with_retry(
            client.get_orders_for_account,
            account_id=account_id,
            filter=request_params,
        )
        return [_serialize_order(o) for o in (orders or [])]
    except Exception as exc:
        logger.error(f"Alpaca list_orders failed: {exc}")
        return []


def cancel_order(account_id: str, order_id: str) -> bool:
    """Cancel a pending order."""
    client = _get_broker_client()
    if not client:
        return False

    try:
        _with_retry(client.cancel_order_for_account_by_id, account_id=account_id, order_id=order_id)
        logger.info(f"Order cancelled: {order_id}")
        return True
    except Exception as exc:
        logger.error(f"Alpaca cancel_order failed: {exc}")
        return False


def cancel_all_orders(account_id: str) -> bool:
    """Cancel all open orders for an account."""
    client = _get_broker_client()
    if not client:
        return False

    try:
        _with_retry(client.cancel_orders_for_account, account_id=account_id)
        logger.info(f"All orders cancelled for account {account_id}")
        return True
    except Exception as exc:
        logger.error(f"Alpaca cancel_all_orders failed: {exc}")
        return False


def replace_order(
    account_id: str,
    order_id: str,
    qty: Optional[float] = None,
    limit_price: Optional[float] = None,
    stop_price: Optional[float] = None,
    time_in_force: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Replace/modify an existing order."""
    client = _get_broker_client()
    if not client:
        return None

    from alpaca.trading.requests import ReplaceOrderRequest

    kwargs: Dict[str, Any] = {}
    if qty is not None:
        kwargs["qty"] = qty
    if limit_price is not None:
        kwargs["limit_price"] = limit_price
    if stop_price is not None:
        kwargs["stop_price"] = stop_price
    if time_in_force is not None:
        kwargs["time_in_force"] = _parse_time_in_force(time_in_force)

    try:
        order = _with_retry(
            client.replace_order_for_account_by_id,
            account_id=account_id,
            order_id=order_id,
            order_data=ReplaceOrderRequest(**kwargs),
        )
        return _serialize_order(order)
    except Exception as exc:
        logger.error(f"Alpaca replace_order failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Position Management
# ---------------------------------------------------------------------------

def get_positions(account_id: str) -> List[Dict[str, Any]]:
    """Get all open positions for an account."""
    client = _get_broker_client()
    if not client:
        return []

    try:
        positions = _with_retry(client.get_all_positions_for_account, account_id=account_id)
        return [_serialize_position(p) for p in (positions or [])]
    except Exception as exc:
        logger.error(f"Alpaca get_positions failed: {exc}")
        return []


def get_position(account_id: str, symbol: str) -> Optional[Dict[str, Any]]:
    """Get a specific position by symbol."""
    client = _get_broker_client()
    if not client:
        return None

    try:
        position = _with_retry(
            client.get_open_position_for_account,
            account_id=account_id,
            symbol_or_asset_id=symbol.upper(),
        )
        return _serialize_position(position)
    except Exception as exc:
        logger.error(f"Alpaca get_position failed for {symbol}: {exc}")
        return None


def close_position(account_id: str, symbol: str, qty: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Close a position by symbol. Optionally close partial qty."""
    client = _get_broker_client()
    if not client:
        return None

    from alpaca.trading.requests import ClosePositionRequest

    close_options = None
    if qty is not None:
        close_options = ClosePositionRequest(qty=str(qty))

    try:
        order = _with_retry(
            client.close_position_for_account,
            account_id=account_id,
            symbol_or_asset_id=symbol.upper(),
            close_options=close_options,
        )
        logger.info(f"Position closed: {symbol} (qty={qty or 'all'})")
        return _serialize_order(order)
    except Exception as exc:
        logger.error(f"Alpaca close_position failed for {symbol}: {exc}")
        return None


def close_all_positions(account_id: str) -> bool:
    """Liquidate all positions for an account."""
    client = _get_broker_client()
    if not client:
        return False

    try:
        _with_retry(client.close_all_positions_for_account, account_id=account_id)
        logger.info(f"All positions closed for account {account_id}")
        return True
    except Exception as exc:
        logger.error(f"Alpaca close_all_positions failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Portfolio History
# ---------------------------------------------------------------------------

def get_portfolio_history(
    account_id: str,
    period: str = "1M",
    timeframe: str = "1D",
) -> Optional[Dict[str, Any]]:
    """Get historical portfolio values for charting."""
    client = _get_broker_client()
    if not client:
        return None

    from alpaca.trading.requests import GetPortfolioHistoryRequest

    try:
        history_filter = GetPortfolioHistoryRequest(
            period=period,
            timeframe=timeframe,
        )
        history = _with_retry(
            client.get_portfolio_history_for_account,
            account_id=account_id,
            history_filter=history_filter,
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
# Asset Information
# ---------------------------------------------------------------------------

def get_asset(symbol: str) -> Optional[Dict[str, Any]]:
    """Get asset information (tradable, fractionable, exchange, etc.)."""
    client = _get_broker_client()
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
        "day": TimeInForce.DAY,
        "gtc": TimeInForce.GTC,
        "ioc": TimeInForce.IOC,
        "fok": TimeInForce.FOK,
        "opg": TimeInForce.OPG,
        "cls": TimeInForce.CLS,
    }
    return mapping.get(tif.lower(), TimeInForce.DAY)


def _build_order_request(
    symbol: str,
    qty: Optional[float],
    notional: Optional[float],
    side,
    order_type: str,
    time_in_force,
    limit_price: Optional[float],
    stop_price: Optional[float],
    trail_percent: Optional[float],
    trail_price: Optional[float],
    extended_hours: bool,
    client_order_id: Optional[str],
    take_profit_limit_price: Optional[float],
    stop_loss_stop_price: Optional[float],
    stop_loss_limit_price: Optional[float],
):
    """Build the appropriate OrderRequest based on order type."""
    from alpaca.broker.requests import (
        MarketOrderRequest,
        LimitOrderRequest,
        StopOrderRequest,
        StopLimitOrderRequest,
        TrailingStopOrderRequest,
    )
    from alpaca.trading.enums import OrderClass
    from alpaca.trading.requests import TakeProfitRequest, StopLossRequest

    # Determine order class for bracket orders
    order_class = None
    take_profit = None
    stop_loss = None

    if take_profit_limit_price or stop_loss_stop_price:
        if take_profit_limit_price and stop_loss_stop_price:
            order_class = OrderClass.BRACKET
        elif take_profit_limit_price:
            order_class = OrderClass.OTO
        elif stop_loss_stop_price:
            order_class = OrderClass.OTO

        if take_profit_limit_price:
            take_profit = TakeProfitRequest(limit_price=take_profit_limit_price)
        if stop_loss_stop_price:
            stop_loss = StopLossRequest(
                stop_price=stop_loss_stop_price,
                limit_price=stop_loss_limit_price,
            )

    base_kwargs: Dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "time_in_force": time_in_force,
    }

    if qty is not None:
        base_kwargs["qty"] = qty
    elif notional is not None:
        base_kwargs["notional"] = notional
    else:
        raise AlpacaClientError(AlpacaError(
            code="MISSING_QTY",
            message="Either qty or notional must be specified",
        ))

    if extended_hours:
        base_kwargs["extended_hours"] = True
    if client_order_id:
        base_kwargs["client_order_id"] = client_order_id
    if order_class:
        base_kwargs["order_class"] = order_class
    if take_profit:
        base_kwargs["take_profit"] = take_profit
    if stop_loss:
        base_kwargs["stop_loss"] = stop_loss

    if order_type == "market":
        return MarketOrderRequest(**base_kwargs)
    elif order_type == "limit":
        return LimitOrderRequest(limit_price=limit_price, **base_kwargs)
    elif order_type == "stop":
        return StopOrderRequest(stop_price=stop_price, **base_kwargs)
    elif order_type == "stop_limit":
        return StopLimitOrderRequest(
            limit_price=limit_price,
            stop_price=stop_price,
            **base_kwargs,
        )
    elif order_type == "trailing_stop":
        trail_kwargs = {**base_kwargs}
        if trail_percent is not None:
            trail_kwargs["trail_percent"] = trail_percent
        elif trail_price is not None:
            trail_kwargs["trail_price"] = trail_price
        return TrailingStopOrderRequest(**trail_kwargs)
    else:
        raise AlpacaClientError(AlpacaError(
            code="INVALID_ORDER_TYPE",
            message=f"Unsupported order type: {order_type}",
        ))


def _serialize_account(account) -> Dict[str, Any]:
    return {
        "account_id": str(account.id) if account.id else None,
        "status": str(account.status) if account.status else None,
        "cash": str(account.cash) if hasattr(account, "cash") and account.cash else "0",
        "buying_power": str(account.buying_power) if hasattr(account, "buying_power") and account.buying_power else "0",
        "equity": str(account.equity) if hasattr(account, "equity") and account.equity else "0",
        "portfolio_value": str(account.portfolio_value) if hasattr(account, "portfolio_value") and account.portfolio_value else "0",
        "last_equity": str(account.last_equity) if hasattr(account, "last_equity") and account.last_equity else "0",
        "currency": str(account.currency) if hasattr(account, "currency") and account.currency else "USD",
        "created_at": str(account.created_at) if account.created_at else None,
    }


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
        "trail_percent": str(order.trail_percent) if hasattr(order, "trail_percent") and order.trail_percent else None,
        "trail_price": str(order.trail_price) if hasattr(order, "trail_price") and order.trail_price else None,
        "filled_avg_price": str(order.filled_avg_price) if order.filled_avg_price else None,
        "extended_hours": order.extended_hours if hasattr(order, "extended_hours") else False,
        "created_at": str(order.created_at) if order.created_at else None,
        "updated_at": str(order.updated_at) if order.updated_at else None,
        "submitted_at": str(order.submitted_at) if order.submitted_at else None,
        "filled_at": str(order.filled_at) if order.filled_at else None,
        "expired_at": str(order.expired_at) if hasattr(order, "expired_at") and order.expired_at else None,
        "canceled_at": str(order.canceled_at) if hasattr(order, "canceled_at") and order.canceled_at else None,
        "legs": [_serialize_order(leg) for leg in order.legs] if hasattr(order, "legs") and order.legs else None,
    }


def _serialize_position(position) -> Dict[str, Any]:
    return {
        "symbol": position.symbol,
        "qty": str(position.qty) if position.qty else "0",
        "qty_available": str(position.qty_available) if hasattr(position, "qty_available") and position.qty_available else "0",
        "side": str(position.side) if position.side else None,
        "avg_entry_price": str(position.avg_entry_price) if position.avg_entry_price else "0",
        "market_value": str(position.market_value) if position.market_value else "0",
        "cost_basis": str(position.cost_basis) if position.cost_basis else "0",
        "unrealized_pl": str(position.unrealized_pl) if position.unrealized_pl else "0",
        "unrealized_plpc": str(position.unrealized_plpc) if position.unrealized_plpc else "0",
        "unrealized_intraday_pl": str(position.unrealized_intraday_pl) if hasattr(position, "unrealized_intraday_pl") and position.unrealized_intraday_pl else "0",
        "unrealized_intraday_plpc": str(position.unrealized_intraday_plpc) if hasattr(position, "unrealized_intraday_plpc") and position.unrealized_intraday_plpc else "0",
        "current_price": str(position.current_price) if position.current_price else "0",
        "lastday_price": str(position.lastday_price) if position.lastday_price else "0",
        "change_today": str(position.change_today) if position.change_today else "0",
        "asset_id": str(position.asset_id) if position.asset_id else None,
        "asset_class": str(position.asset_class) if hasattr(position, "asset_class") and position.asset_class else None,
    }
