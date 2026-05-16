"""FastAPI router for Alpaca Broker API integration.

Provides endpoints for managing Alpaca sub-accounts per user,
submitting/canceling orders, viewing positions, and portfolio history.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .alpaca_client import (
    cancel_order,
    close_position,
    create_trading_account,
    get_account,
    get_order,
    get_portfolio_history,
    get_positions,
    is_alpaca_configured,
    list_orders,
    submit_limit_order,
    submit_market_order,
)


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class AlpacaOrderRequest(BaseModel):
    symbol: str
    qty: float = Field(gt=0)
    side: str = Field(pattern="^(buy|sell)$")
    order_type: str = Field(default="market", pattern="^(market|limit)$")
    limit_price: Optional[float] = None
    time_in_force: str = Field(default="day", pattern="^(day|gtc|ioc|fok)$")


class AlpacaAccountCreateRequest(BaseModel):
    given_name: Optional[str] = None
    family_name: Optional[str] = None


class AlpacaClosePositionRequest(BaseModel):
    symbol: str


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def build_alpaca_router(db, get_current_user: Callable[[Request], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/alpaca", tags=["alpaca-broker"])

    async def require_user(request: Request) -> dict:
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required.")
        return user

    async def _get_or_create_alpaca_account(user: dict, db) -> str:
        """Get the user's Alpaca account_id, creating one if needed."""
        user_id = user["user_id"]

        user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        alpaca_account_id = (user_doc or {}).get("alpaca_account_id")

        if alpaca_account_id:
            return alpaca_account_id

        given_name = user.get("name", "Paper").split()[0] if user.get("name") else "Paper"
        family_name = (
            user.get("name", "Trader").split()[-1]
            if user.get("name") and len(user.get("name", "").split()) > 1
            else "Trader"
        )
        email = user.get("email", f"{user_id}@marketflux.paper")

        # create_trading_account is a blocking network call — run in thread pool
        result = await asyncio.to_thread(
            create_trading_account,
            given_name=given_name,
            family_name=family_name,
            email=email,
        )
        if not result:
            raise HTTPException(503, "Failed to create Alpaca trading account. Check Broker API credentials.")

        alpaca_account_id = result["account_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"alpaca_account_id": alpaca_account_id}},
        )
        return alpaca_account_id

    # ------------------------------------------------------------------
    # Health / config check
    # ------------------------------------------------------------------

    @router.get("/status")
    async def alpaca_status():
        return {
            "configured": is_alpaca_configured(),
            "mode": "sandbox",
            "provider": "alpaca-broker-api",
        }

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    @router.get("/account")
    async def alpaca_account(request: Request):
        """Get the user's Alpaca paper trading account summary."""
        if not is_alpaca_configured():
            raise HTTPException(503, "Alpaca Broker API is not configured.")

        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user, db)
        account_info = await asyncio.to_thread(get_account, account_id)
        if not account_info:
            raise HTTPException(502, "Unable to fetch account from Alpaca.")
        return {"item": account_info}

    @router.post("/account")
    async def alpaca_create_account(request: Request, payload: AlpacaAccountCreateRequest):
        """Explicitly provision an Alpaca sub-account for the user."""
        if not is_alpaca_configured():
            raise HTTPException(503, "Alpaca Broker API is not configured.")

        user = await require_user(request)
        user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
        if (user_doc or {}).get("alpaca_account_id"):
            account_info = await asyncio.to_thread(get_account, user_doc["alpaca_account_id"])
            return {"item": account_info, "message": "Account already exists."}

        account_id = await _get_or_create_alpaca_account(user, db)
        account_info = await asyncio.to_thread(get_account, account_id)
        return {"item": account_info, "message": "Account created successfully."}

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    @router.post("/orders")
    async def alpaca_submit_order(request: Request, payload: AlpacaOrderRequest):
        """Submit a paper trade order via Alpaca."""
        if not is_alpaca_configured():
            raise HTTPException(503, "Alpaca Broker API is not configured.")

        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user, db)

        if payload.order_type == "limit":
            if payload.limit_price is None or payload.limit_price <= 0:
                raise HTTPException(422, "limit_price is required for limit orders.")
            order = await asyncio.to_thread(
                submit_limit_order,
                account_id=account_id,
                symbol=payload.symbol,
                qty=payload.qty,
                side=payload.side,
                limit_price=payload.limit_price,
                time_in_force=payload.time_in_force,
            )
        else:
            order = await asyncio.to_thread(
                submit_market_order,
                account_id=account_id,
                symbol=payload.symbol,
                qty=payload.qty,
                side=payload.side,
                time_in_force=payload.time_in_force,
            )

        if not order:
            raise HTTPException(502, "Order submission failed. Check symbol and quantity.")
        return {"item": order}

    @router.get("/orders")
    async def alpaca_list_orders(request: Request, status: str = "all", limit: int = 50):
        """List orders for the user's Alpaca account."""
        if not is_alpaca_configured():
            raise HTTPException(503, "Alpaca Broker API is not configured.")

        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user, db)
        orders = await asyncio.to_thread(list_orders, account_id, status=status, limit=min(limit, 200))
        return {"items": orders, "total": len(orders)}

    @router.get("/orders/{order_id}")
    async def alpaca_get_order(order_id: str, request: Request):
        """Get a specific order by ID."""
        if not is_alpaca_configured():
            raise HTTPException(503, "Alpaca Broker API is not configured.")

        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user, db)
        order = await asyncio.to_thread(get_order, account_id, order_id)
        if not order:
            raise HTTPException(404, "Order not found.")
        return {"item": order}

    @router.delete("/orders/{order_id}")
    async def alpaca_cancel_order(order_id: str, request: Request):
        """Cancel a pending order."""
        if not is_alpaca_configured():
            raise HTTPException(503, "Alpaca Broker API is not configured.")

        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user, db)
        success = await asyncio.to_thread(cancel_order, account_id, order_id)
        if not success:
            raise HTTPException(400, "Failed to cancel order. It may already be filled or cancelled.")
        return {"message": "Order cancelled successfully."}

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    @router.get("/positions")
    async def alpaca_positions(request: Request):
        """Get all open positions for the user's Alpaca account."""
        if not is_alpaca_configured():
            raise HTTPException(503, "Alpaca Broker API is not configured.")

        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user, db)
        positions = await asyncio.to_thread(get_positions, account_id)
        return {"items": positions, "total": len(positions)}

    @router.post("/positions/close")
    async def alpaca_close_position(request: Request, payload: AlpacaClosePositionRequest):
        """Close a position by symbol."""
        if not is_alpaca_configured():
            raise HTTPException(503, "Alpaca Broker API is not configured.")

        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user, db)
        result = await asyncio.to_thread(close_position, account_id, payload.symbol)
        if not result:
            raise HTTPException(400, f"Failed to close position for {payload.symbol}.")
        return {"item": result, "message": f"Position closed for {payload.symbol}."}

    # ------------------------------------------------------------------
    # Portfolio History
    # ------------------------------------------------------------------

    @router.get("/portfolio-history")
    async def alpaca_portfolio_history(request: Request, period: str = "1M", timeframe: str = "1D"):
        """Get portfolio value history for charting."""
        if not is_alpaca_configured():
            raise HTTPException(503, "Alpaca Broker API is not configured.")

        valid_periods = {"1D", "1W", "1M", "3M", "6M", "1A", "all"}
        valid_timeframes = {"1Min", "5Min", "15Min", "1H", "1D"}
        if period not in valid_periods:
            raise HTTPException(422, f"Invalid period. Must be one of: {', '.join(sorted(valid_periods))}")
        if timeframe not in valid_timeframes:
            raise HTTPException(422, f"Invalid timeframe. Must be one of: {', '.join(sorted(valid_timeframes))}")

        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user, db)
        history = await asyncio.to_thread(get_portfolio_history, account_id, period=period, timeframe=timeframe)
        if not history:
            return {"timestamp": [], "equity": [], "profit_loss": [], "profit_loss_pct": [], "base_value": 0, "timeframe": timeframe}
        return history

    return router
