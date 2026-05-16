"""FastAPI router for Alpaca Trading API integration.

Uses the Trading API (paper) — single account, no sub-accounts.
All endpoints require login via get_current_user.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .alpaca_client import (
    cancel_all_orders,
    cancel_order,
    close_all_positions,
    close_position,
    get_account,
    get_asset,
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


class AlpacaClosePositionRequest(BaseModel):
    symbol: str


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def build_alpaca_router(db, get_current_user: Callable[[Request], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/alpaca", tags=["alpaca-trading"])

    async def require_user(request: Request) -> dict:
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required.")
        return user

    def _require_configured():
        if not is_alpaca_configured():
            raise HTTPException(503, "Alpaca Trading API is not configured.")

    # ------------------------------------------------------------------
    # Health / config check
    # ------------------------------------------------------------------

    @router.get("/status")
    async def alpaca_status():
        return {
            "configured": is_alpaca_configured(),
            "mode": "paper",
            "provider": "alpaca-trading-api",
        }

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    @router.get("/account")
    async def alpaca_account(request: Request):
        """Get the paper trading account summary."""
        _require_configured()
        await require_user(request)
        account_info = await asyncio.to_thread(get_account)
        if not account_info:
            raise HTTPException(502, "Unable to fetch account from Alpaca.")
        return {"item": account_info}

    @router.post("/account")
    async def alpaca_create_account(request: Request):
        """No-op for backwards compatibility — Trading API uses a single account."""
        _require_configured()
        await require_user(request)
        account_info = await asyncio.to_thread(get_account)
        if not account_info:
            raise HTTPException(502, "Unable to fetch account from Alpaca.")
        return {"item": account_info, "message": "Using shared paper trading account."}

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    @router.post("/orders")
    async def alpaca_submit_order(request: Request, payload: AlpacaOrderRequest):
        """Submit a paper trade order via Alpaca."""
        _require_configured()
        await require_user(request)

        if payload.order_type == "limit":
            if payload.limit_price is None or payload.limit_price <= 0:
                raise HTTPException(422, "limit_price is required for limit orders.")
            order = await asyncio.to_thread(
                submit_limit_order,
                symbol=payload.symbol,
                qty=payload.qty,
                side=payload.side,
                limit_price=payload.limit_price,
                time_in_force=payload.time_in_force,
            )
        else:
            order = await asyncio.to_thread(
                submit_market_order,
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
        """List orders for the paper trading account."""
        _require_configured()
        await require_user(request)
        orders = await asyncio.to_thread(list_orders, status=status, limit=min(limit, 200))
        return {"items": orders, "total": len(orders)}

    @router.get("/orders/{order_id}")
    async def alpaca_get_order(order_id: str, request: Request):
        """Get a specific order by ID."""
        _require_configured()
        await require_user(request)
        order = await asyncio.to_thread(get_order, order_id)
        if not order:
            raise HTTPException(404, "Order not found.")
        return {"item": order}

    @router.delete("/orders/{order_id}")
    async def alpaca_cancel_order(order_id: str, request: Request):
        """Cancel a pending order."""
        _require_configured()
        await require_user(request)
        success = await asyncio.to_thread(cancel_order, order_id)
        if not success:
            raise HTTPException(400, "Failed to cancel order. It may already be filled or cancelled.")
        return {"message": "Order cancelled successfully."}

    @router.delete("/orders")
    async def alpaca_cancel_all_orders(request: Request):
        """Cancel all open orders."""
        _require_configured()
        await require_user(request)
        success = await asyncio.to_thread(cancel_all_orders)
        if not success:
            raise HTTPException(502, "Failed to cancel orders.")
        return {"message": "All open orders cancelled."}

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    @router.get("/positions")
    async def alpaca_positions(request: Request):
        """Get all open positions."""
        _require_configured()
        await require_user(request)
        positions = await asyncio.to_thread(get_positions)
        return {"items": positions, "total": len(positions)}

    @router.post("/positions/close")
    async def alpaca_close_position(request: Request, payload: AlpacaClosePositionRequest):
        """Close a position by symbol."""
        _require_configured()
        await require_user(request)
        result = await asyncio.to_thread(close_position, payload.symbol)
        if not result:
            raise HTTPException(400, f"Failed to close position for {payload.symbol}.")
        return {"item": result, "message": f"Position closed for {payload.symbol}."}

    @router.post("/positions/liquidate")
    async def alpaca_liquidate_all(request: Request):
        """Close all open positions and cancel open orders."""
        _require_configured()
        await require_user(request)
        success = await asyncio.to_thread(close_all_positions)
        if not success:
            raise HTTPException(502, "Failed to liquidate positions.")
        return {"message": "All positions closed and open orders cancelled."}

    # ------------------------------------------------------------------
    # Portfolio History
    # ------------------------------------------------------------------

    @router.get("/portfolio-history")
    async def alpaca_portfolio_history(request: Request, period: str = "1M", timeframe: str = "1D"):
        """Get portfolio value history for charting."""
        _require_configured()

        valid_periods = {"1D", "1W", "1M", "3M", "6M", "1A", "all"}
        valid_timeframes = {"1Min", "5Min", "15Min", "1H", "1D"}
        if period not in valid_periods:
            raise HTTPException(422, f"Invalid period. Must be one of: {', '.join(sorted(valid_periods))}")
        if timeframe not in valid_timeframes:
            raise HTTPException(422, f"Invalid timeframe. Must be one of: {', '.join(sorted(valid_timeframes))}")

        await require_user(request)
        history = await asyncio.to_thread(get_portfolio_history, period=period, timeframe=timeframe)
        if not history:
            return {"timestamp": [], "equity": [], "profit_loss": [], "profit_loss_pct": [], "base_value": 0, "timeframe": timeframe}
        return history

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    @router.get("/assets/{symbol}")
    async def alpaca_get_asset(symbol: str, request: Request):
        """Get asset info by symbol."""
        _require_configured()
        await require_user(request)
        asset = await asyncio.to_thread(get_asset, symbol)
        if not asset:
            raise HTTPException(404, f"Asset not found: {symbol}")
        return {"item": asset}

    return router
