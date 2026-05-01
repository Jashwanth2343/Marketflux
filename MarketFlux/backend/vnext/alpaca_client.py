"""Alpaca Broker API client for MarketFlux.

Uses the Broker API (sandbox) to manage sub-accounts per MarketFlux user
and execute paper trades on their behalf.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

logger = logging.getLogger(__name__)

_broker_client = None


def _get_broker_client():
    """Lazy-initialize and return the singleton BrokerClient."""
    global _broker_client
    if _broker_client is not None:
        return _broker_client

    api_key = os.getenv("ALPACA_BROKER_API_KEY")
    secret_key = os.getenv("ALPACA_BROKER_API_SECRET")

    if not api_key or not secret_key:
        return None

    from alpaca.broker.client import BrokerClient

    _broker_client = BrokerClient(
        api_key=api_key,
        secret_key=secret_key,
        sandbox=True,
    )
    # Broker API sandbox requires Basic Auth header format
    _broker_client._use_basic_auth = True
    return _broker_client


def is_alpaca_configured() -> bool:
    return bool(os.getenv("ALPACA_BROKER_API_KEY") and os.getenv("ALPACA_BROKER_API_SECRET"))


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
    """Create an Alpaca sub-account for a MarketFlux user (paper/sandbox)."""
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

    agreement_data = [
        Agreement(
            agreement=AgreementType.MARGIN,
            signed_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            ip_address="127.0.0.1",
        ),
        Agreement(
            agreement=AgreementType.ACCOUNT,
            signed_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            ip_address="127.0.0.1",
        ),
        Agreement(
            agreement=AgreementType.CUSTOMER,
            signed_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            ip_address="127.0.0.1",
        ),
    ]

    account_data = CreateAccountRequest(
        contact=contact_data,
        identity=identity_data,
        disclosures=disclosure_data,
        agreements=agreement_data,
    )

    try:
        account = client.create_account(account_data)
        return {
            "account_id": str(account.id),
            "status": str(account.status),
            "currency": str(account.currency) if account.currency else "USD",
            "created_at": str(account.created_at) if account.created_at else None,
        }
    except Exception as exc:
        logger.error(f"Alpaca create_account failed: {exc}")
        return None


def get_account(account_id: str) -> Optional[Dict[str, Any]]:
    """Get account details including buying power, equity, cash."""
    client = _get_broker_client()
    if not client:
        return None

    try:
        account = client.get_account_by_id(account_id)
        return {
            "account_id": str(account.id),
            "status": str(account.status),
            "cash": str(account.cash) if account.cash else "0",
            "buying_power": str(account.buying_power) if account.buying_power else "0",
            "equity": str(account.equity) if account.equity else "0",
            "portfolio_value": str(account.portfolio_value) if account.portfolio_value else "0",
            "last_equity": str(account.last_equity) if account.last_equity else "0",
            "currency": str(account.currency) if account.currency else "USD",
            "created_at": str(account.created_at) if account.created_at else None,
        }
    except Exception as exc:
        logger.error(f"Alpaca get_account failed for {account_id}: {exc}")
        return None


def list_accounts() -> List[Dict[str, Any]]:
    """List all sub-accounts."""
    client = _get_broker_client()
    if not client:
        return []

    try:
        accounts = client.list_accounts()
        return [
            {
                "account_id": str(a.id),
                "status": str(a.status),
                "created_at": str(a.created_at) if a.created_at else None,
            }
            for a in accounts
        ]
    except Exception as exc:
        logger.error(f"Alpaca list_accounts failed: {exc}")
        return []


# ---------------------------------------------------------------------------
# Order Management
# ---------------------------------------------------------------------------

def submit_market_order(
    account_id: str,
    symbol: str,
    qty: float,
    side: str,
    time_in_force: str = "day",
) -> Optional[Dict[str, Any]]:
    """Submit a market order for an account."""
    client = _get_broker_client()
    if not client:
        return None

    from alpaca.broker.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
    tif = _parse_time_in_force(time_in_force)

    order_data = MarketOrderRequest(
        symbol=symbol.upper(),
        qty=qty,
        side=order_side,
        time_in_force=tif,
    )

    try:
        order = client.submit_order_for_account(
            account_id=account_id,
            order_data=order_data,
        )
        return _serialize_order(order)
    except Exception as exc:
        logger.error(f"Alpaca submit_market_order failed: {exc}")
        return None


def submit_limit_order(
    account_id: str,
    symbol: str,
    qty: float,
    side: str,
    limit_price: float,
    time_in_force: str = "day",
) -> Optional[Dict[str, Any]]:
    """Submit a limit order for an account."""
    client = _get_broker_client()
    if not client:
        return None

    from alpaca.broker.requests import LimitOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
    tif = _parse_time_in_force(time_in_force)

    order_data = LimitOrderRequest(
        symbol=symbol.upper(),
        qty=qty,
        side=order_side,
        time_in_force=tif,
        limit_price=limit_price,
    )

    try:
        order = client.submit_order_for_account(
            account_id=account_id,
            order_data=order_data,
        )
        return _serialize_order(order)
    except Exception as exc:
        logger.error(f"Alpaca submit_limit_order failed: {exc}")
        return None


def get_order(account_id: str, order_id: str) -> Optional[Dict[str, Any]]:
    """Get order status by ID."""
    client = _get_broker_client()
    if not client:
        return None

    try:
        order = client.get_order_for_account_by_id(
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
        orders = client.get_orders_for_account(
            account_id=account_id,
            filter=request_params,
        )
        return [_serialize_order(o) for o in orders]
    except Exception as exc:
        logger.error(f"Alpaca list_orders failed: {exc}")
        return []


def cancel_order(account_id: str, order_id: str) -> bool:
    """Cancel a pending order."""
    client = _get_broker_client()
    if not client:
        return False

    try:
        client.cancel_order_for_account_by_id(account_id=account_id, order_id=order_id)
        return True
    except Exception as exc:
        logger.error(f"Alpaca cancel_order failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Position Management
# ---------------------------------------------------------------------------

def get_positions(account_id: str) -> List[Dict[str, Any]]:
    """Get all open positions for an account."""
    client = _get_broker_client()
    if not client:
        return []

    try:
        positions = client.get_all_positions_for_account(account_id=account_id)
        return [_serialize_position(p) for p in positions]
    except Exception as exc:
        logger.error(f"Alpaca get_positions failed: {exc}")
        return []


def close_position(account_id: str, symbol: str) -> Optional[Dict[str, Any]]:
    """Close a position by symbol."""
    client = _get_broker_client()
    if not client:
        return None

    try:
        order = client.close_position_for_account(
            account_id=account_id,
            symbol_or_asset_id=symbol.upper(),
        )
        return _serialize_order(order)
    except Exception as exc:
        logger.error(f"Alpaca close_position failed for {symbol}: {exc}")
        return None


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
        history = client.get_portfolio_history_for_account(
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
# Helpers
# ---------------------------------------------------------------------------

def _parse_time_in_force(tif: str):
    from alpaca.trading.enums import TimeInForce

    mapping = {
        "day": TimeInForce.DAY,
        "gtc": TimeInForce.GTC,
        "ioc": TimeInForce.IOC,
        "fok": TimeInForce.FOK,
    }
    return mapping.get(tif.lower(), TimeInForce.DAY)


def _serialize_order(order) -> Dict[str, Any]:
    return {
        "order_id": str(order.id) if order.id else None,
        "symbol": order.symbol,
        "qty": str(order.qty) if order.qty else None,
        "filled_qty": str(order.filled_qty) if order.filled_qty else "0",
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
        "asset_id": str(position.asset_id) if position.asset_id else None,
    }
