"""Alpaca client for MarketFlux — dual-mode (Trading API / Broker API).

Modes (set via ALPACA_MODE env var):
  "trading" (default) — single shared paper account, TradingClient(paper=True)
  "broker"           — per-user sub-accounts via BrokerClient(sandbox=True)

Trading mode keys: APCA_API_KEY_ID + APCA_API_SECRET_KEY
Broker mode keys:  ALPACA_BROKER_API_KEY + ALPACA_BROKER_API_SECRET

All functions are synchronous; call them with asyncio.to_thread().
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_trading_client = None
_broker_client = None


def get_alpaca_mode() -> str:
    return os.getenv("ALPACA_MODE", "trading").lower()


def is_broker_mode() -> bool:
    return get_alpaca_mode() == "broker"


def _get_trading_client():
    global _trading_client
    if _trading_client is not None:
        return _trading_client

    api_key = os.getenv("APCA_API_KEY_ID")
    secret_key = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not secret_key:
        return None

    from alpaca.trading.client import TradingClient

    _trading_client = TradingClient(api_key=api_key, secret_key=secret_key, paper=True)
    return _trading_client


def _get_broker_client():
    global _broker_client
    if _broker_client is not None:
        return _broker_client

    api_key = os.getenv("ALPACA_BROKER_API_KEY")
    secret_key = os.getenv("ALPACA_BROKER_API_SECRET")

    if not api_key or not secret_key:
        return None

    from alpaca.broker.client import BrokerClient

    _broker_client = BrokerClient(api_key=api_key, secret_key=secret_key, sandbox=True)
    return _broker_client


def is_alpaca_configured() -> bool:
    if is_broker_mode():
        return bool(os.getenv("ALPACA_BROKER_API_KEY") and os.getenv("ALPACA_BROKER_API_SECRET"))
    return bool(os.getenv("APCA_API_KEY_ID") and os.getenv("APCA_API_SECRET_KEY"))


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

def get_account() -> Optional[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return None
    try:
        account = client.get_account()
        return {
            "account_id": str(account.id) if account.id else None,
            "status": str(account.status) if account.status else None,
            "cash": str(account.cash) if account.cash is not None else "0",
            "buying_power": str(account.buying_power) if account.buying_power is not None else "0",
            "equity": str(account.equity) if account.equity is not None else "0",
            "portfolio_value": str(getattr(account, "portfolio_value", None) or account.equity or 0),
            "last_equity": str(getattr(account, "last_equity", None) or 0),
            "unrealized_pl": str(getattr(account, "unrealized_intraday_pl", None) or getattr(account, "unrealized_pl", None) or 0),
            "unrealized_plpc": str(getattr(account, "unrealized_intraday_plpc", None) or getattr(account, "unrealized_plpc", None) or 0),
            "currency": str(getattr(account, "currency", "USD") or "USD"),
            "created_at": str(account.created_at) if account.created_at else None,
        }
    except Exception as exc:
        logger.error(f"Alpaca get_account failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Order Management
# ---------------------------------------------------------------------------

def submit_market_order(
    symbol: str,
    qty: float,
    side: str,
    time_in_force: str = "day",
) -> Optional[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return None

    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide

    order_data = MarketOrderRequest(
        symbol=symbol.upper(),
        qty=qty,
        side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
        time_in_force=_parse_time_in_force(time_in_force),
    )

    try:
        order = client.submit_order(order_data=order_data)
        return _serialize_order(order)
    except Exception as exc:
        logger.error(f"Alpaca submit_market_order failed: {exc}")
        return None


def submit_limit_order(
    symbol: str,
    qty: float,
    side: str,
    limit_price: float,
    time_in_force: str = "day",
) -> Optional[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return None

    from alpaca.trading.requests import LimitOrderRequest
    from alpaca.trading.enums import OrderSide

    order_data = LimitOrderRequest(
        symbol=symbol.upper(),
        qty=qty,
        side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
        time_in_force=_parse_time_in_force(time_in_force),
        limit_price=limit_price,
    )

    try:
        order = client.submit_order(order_data=order_data)
        return _serialize_order(order)
    except Exception as exc:
        logger.error(f"Alpaca submit_limit_order failed: {exc}")
        return None


def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return None
    try:
        order = client.get_order_by_id(order_id)
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

    try:
        orders = client.get_orders(
            filter=GetOrdersRequest(
                status=status_map.get(status, QueryOrderStatus.ALL),
                limit=limit,
            )
        )
        return [_serialize_order(o) for o in orders]
    except Exception as exc:
        logger.error(f"Alpaca list_orders failed: {exc}")
        return []


def cancel_order(order_id: str) -> bool:
    client = _get_trading_client()
    if not client:
        return False
    try:
        client.cancel_order_by_id(order_id)
        return True
    except Exception as exc:
        logger.error(f"Alpaca cancel_order failed: {exc}")
        return False


def cancel_all_orders() -> List[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return []
    try:
        responses = client.cancel_orders()
        return [{"id": str(r.id), "status": str(r.status)} for r in (responses or [])]
    except Exception as exc:
        logger.error(f"Alpaca cancel_all_orders failed: {exc}")
        return []


# ---------------------------------------------------------------------------
# Position Management
# ---------------------------------------------------------------------------

def get_positions() -> List[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return []
    try:
        positions = client.get_all_positions()
        return [_serialize_position(p) for p in positions]
    except Exception as exc:
        logger.error(f"Alpaca get_positions failed: {exc}")
        return []


def close_position(symbol: str, qty: Optional[float] = None) -> Optional[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return None
    try:
        if qty is not None:
            from alpaca.trading.requests import ClosePositionRequest
            order = client.close_position(
                symbol_or_asset_id=symbol.upper(),
                close_options=ClosePositionRequest(qty=str(qty)),
            )
        else:
            order = client.close_position(symbol_or_asset_id=symbol.upper())
        return _serialize_order(order)
    except Exception as exc:
        logger.error(f"Alpaca close_position failed for {symbol}: {exc}")
        return None


def close_all_positions() -> List[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return []
    try:
        orders = client.close_all_positions(cancel_orders=True)
        return [_serialize_order(o) for o in (orders or [])]
    except Exception as exc:
        logger.error(f"Alpaca close_all_positions failed: {exc}")
        return []


# ---------------------------------------------------------------------------
# Portfolio History
# ---------------------------------------------------------------------------

def get_portfolio_history(
    period: str = "1M",
    timeframe: str = "1D",
) -> Optional[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return None

    from alpaca.trading.requests import GetPortfolioHistoryRequest

    try:
        history = client.get_portfolio_history(
            history_filter=GetPortfolioHistoryRequest(period=period, timeframe=timeframe)
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
# Asset lookup
# ---------------------------------------------------------------------------

def get_asset(symbol: str) -> Optional[Dict[str, Any]]:
    client = _get_trading_client()
    if not client:
        return None
    try:
        asset = client.get_asset(symbol_or_asset_id=symbol.upper())
        return {
            "id": str(asset.id) if asset.id else None,
            "symbol": asset.symbol,
            "name": getattr(asset, "name", None),
            "tradable": bool(asset.tradable),
            "status": str(asset.status) if asset.status else None,
            "exchange": str(asset.exchange) if asset.exchange else None,
            "asset_class": str(asset.asset_class) if asset.asset_class else None,
        }
    except Exception as exc:
        logger.error(f"Alpaca get_asset failed for {symbol}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_time_in_force(tif: str):
    from alpaca.trading.enums import TimeInForce

    return {
        "day": TimeInForce.DAY,
        "gtc": TimeInForce.GTC,
        "ioc": TimeInForce.IOC,
        "fok": TimeInForce.FOK,
    }.get(tif.lower(), TimeInForce.DAY)


def _serialize_order(order) -> Dict[str, Any]:
    oid = str(order.id) if order.id else None
    return {
        "id": oid,
        "order_id": oid,
        "symbol": order.symbol,
        "qty": str(order.qty) if order.qty is not None else None,
        "filled_qty": str(order.filled_qty) if order.filled_qty is not None else "0",
        "side": str(order.side) if order.side else None,
        "type": str(order.type) if order.type else None,
        "time_in_force": str(order.time_in_force) if order.time_in_force else None,
        "status": str(order.status) if order.status else None,
        "limit_price": str(order.limit_price) if order.limit_price else None,
        "stop_price": str(order.stop_price) if order.stop_price else None,
        "filled_avg_price": str(order.filled_avg_price) if order.filled_avg_price else None,
        "created_at": str(order.created_at) if order.created_at else None,
        "updated_at": str(order.updated_at) if order.updated_at else None,
        "submitted_at": str(order.submitted_at) if order.submitted_at else None,
        "filled_at": str(order.filled_at) if order.filled_at else None,
    }


def _serialize_position(position) -> Dict[str, Any]:
    return {
        "symbol": position.symbol,
        "qty": str(position.qty) if position.qty is not None else "0",
        "side": str(position.side) if position.side else None,
        "avg_entry_price": str(position.avg_entry_price) if position.avg_entry_price is not None else "0",
        "market_value": str(position.market_value) if position.market_value is not None else "0",
        "cost_basis": str(position.cost_basis) if position.cost_basis is not None else "0",
        "unrealized_pl": str(position.unrealized_pl) if position.unrealized_pl is not None else "0",
        "unrealized_plpc": str(position.unrealized_plpc) if position.unrealized_plpc is not None else "0",
        "current_price": str(position.current_price) if position.current_price is not None else "0",
        "lastday_price": str(position.lastday_price) if position.lastday_price is not None else "0",
        "change_today": str(position.change_today) if position.change_today is not None else "0",
        "asset_id": str(position.asset_id) if position.asset_id else None,
    }


# ===========================================================================
# BROKER MODE — per-user sub-account management
# ===========================================================================

def broker_create_trading_account(
    given_name: str,
    family_name: str,
    email: str,
) -> Optional[Dict[str, Any]]:
    """Create an Alpaca sub-account for a user (broker/sandbox mode only)."""
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
    from alpaca.broker.enums import TaxIdType, FundingSource, AgreementType
    from datetime import datetime

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
        date_of_birth="1990-01-01",
        tax_id="000-00-0000",
        tax_id_type=TaxIdType.USA_SSN,
        country_of_citizenship="USA",
        country_of_birth="USA",
        country_of_tax_residence="USA",
        funding_source=[FundingSource.EMPLOYMENT_INCOME],
    )

    disclosure_data = Disclosures(
        is_control_person=False,
        is_affiliated_exchange_or_finra=False,
        is_politically_exposed=False,
        immediate_family_exposed=False,
    )

    now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    agreement_data = [
        Agreement(agreement=AgreementType.MARGIN, signed_at=now_str, ip_address="127.0.0.1"),
        Agreement(agreement=AgreementType.ACCOUNT, signed_at=now_str, ip_address="127.0.0.1"),
        Agreement(agreement=AgreementType.CUSTOMER, signed_at=now_str, ip_address="127.0.0.1"),
    ]

    try:
        account = client.create_account(
            CreateAccountRequest(
                contact=contact_data,
                identity=identity_data,
                disclosures=disclosure_data,
                agreements=agreement_data,
            )
        )
        return {
            "account_id": str(account.id),
            "status": str(account.status),
            "currency": str(account.currency) if account.currency else "USD",
            "created_at": str(account.created_at) if account.created_at else None,
        }
    except Exception as exc:
        logger.error(f"Broker create_account failed: {exc}")
        return None


def broker_get_account(account_id: str) -> Optional[Dict[str, Any]]:
    """Get sub-account details (broker mode)."""
    client = _get_broker_client()
    if not client:
        return None
    try:
        account = client.get_account_by_id(account_id)
        return {
            "account_id": str(account.id),
            "status": str(account.status),
            "cash": str(account.cash) if account.cash is not None else "0",
            "buying_power": str(account.buying_power) if account.buying_power is not None else "0",
            "equity": str(account.equity) if account.equity is not None else "0",
            "portfolio_value": str(account.portfolio_value) if account.portfolio_value is not None else "0",
            "last_equity": str(account.last_equity) if account.last_equity is not None else "0",
            "unrealized_pl": str(getattr(account, "unrealized_pl", 0) or 0),
            "unrealized_plpc": str(getattr(account, "unrealized_plpc", 0) or 0),
            "currency": str(account.currency) if account.currency else "USD",
            "created_at": str(account.created_at) if account.created_at else None,
        }
    except Exception as exc:
        logger.error(f"Broker get_account failed for {account_id}: {exc}")
        return None


def broker_submit_market_order(
    account_id: str,
    symbol: str,
    qty: float,
    side: str,
    time_in_force: str = "day",
) -> Optional[Dict[str, Any]]:
    """Submit a market order for a sub-account (broker mode)."""
    client = _get_broker_client()
    if not client:
        return None

    from alpaca.broker.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide

    order_data = MarketOrderRequest(
        symbol=symbol.upper(),
        qty=qty,
        side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
        time_in_force=_parse_time_in_force(time_in_force),
    )

    try:
        order = client.submit_order_for_account(account_id=account_id, order_data=order_data)
        return _serialize_order(order)
    except Exception as exc:
        logger.error(f"Broker submit_market_order failed: {exc}")
        return None


def broker_get_positions(account_id: str) -> List[Dict[str, Any]]:
    """Get positions for a sub-account (broker mode)."""
    client = _get_broker_client()
    if not client:
        return []
    try:
        positions = client.get_all_positions_for_account(account_id=account_id)
        return [_serialize_position(p) for p in positions]
    except Exception as exc:
        logger.error(f"Broker get_positions failed for {account_id}: {exc}")
        return []


def broker_list_orders(account_id: str, status: str = "all", limit: int = 50) -> List[Dict[str, Any]]:
    """List orders for a sub-account (broker mode)."""
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

    try:
        orders = client.get_orders_for_account(
            account_id=account_id,
            filter=GetOrdersRequest(status=status_map.get(status, QueryOrderStatus.ALL), limit=limit),
        )
        return [_serialize_order(o) for o in orders]
    except Exception as exc:
        logger.error(f"Broker list_orders failed for {account_id}: {exc}")
        return []


def broker_cancel_order(account_id: str, order_id: str) -> bool:
    """Cancel an order for a sub-account (broker mode)."""
    client = _get_broker_client()
    if not client:
        return False
    try:
        client.cancel_order_for_account_by_id(account_id=account_id, order_id=order_id)
        return True
    except Exception as exc:
        logger.error(f"Broker cancel_order failed: {exc}")
        return False


def broker_close_position(account_id: str, symbol: str) -> Optional[Dict[str, Any]]:
    """Close a position for a sub-account (broker mode)."""
    client = _get_broker_client()
    if not client:
        return None
    try:
        order = client.close_position_for_account(account_id=account_id, symbol_or_asset_id=symbol.upper())
        return _serialize_order(order)
    except Exception as exc:
        logger.error(f"Broker close_position failed for {symbol}: {exc}")
        return None


def broker_get_portfolio_history(
    account_id: str,
    period: str = "1M",
    timeframe: str = "1D",
) -> Optional[Dict[str, Any]]:
    """Get portfolio history for a sub-account (broker mode)."""
    client = _get_broker_client()
    if not client:
        return None

    from alpaca.trading.requests import GetPortfolioHistoryRequest

    try:
        history = client.get_portfolio_history_for_account(
            account_id=account_id,
            history_filter=GetPortfolioHistoryRequest(period=period, timeframe=timeframe),
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
        logger.error(f"Broker get_portfolio_history failed: {exc}")
        return None
