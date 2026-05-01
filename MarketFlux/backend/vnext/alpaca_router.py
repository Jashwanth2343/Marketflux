"""FastAPI router for Alpaca Paper Trading API.

Direct trading endpoints using the Trading API (single account).
Supports all order types, positions, portfolio history, and asset lookup.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .alpaca_client import (
    AlpacaClientError,
    cancel_all_orders,
    cancel_order_by_id,
    close_all_positions,
    close_position,
    get_account,
    get_all_positions,
    get_asset,
    get_order_by_id,
    get_portfolio_history,
    get_position,
    list_orders,
    submit_order,
)
from .alpaca_config import get_alpaca_config, is_alpaca_configured


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class OrderRequest(BaseModel):
    symbol: str
    qty: Optional[float] = Field(default=None, gt=0)
    notional: Optional[float] = Field(default=None, gt=0)
    side: str = Field(pattern="^(buy|sell)$")
    order_type: str = Field(default="market", pattern="^(market|limit|stop|stop_limit|trailing_stop)$")
    time_in_force: str = Field(default="day", pattern="^(day|gtc|ioc|fok|opg|cls)$")
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    trail_percent: Optional[float] = Field(default=None, gt=0, le=50)
    trail_price: Optional[float] = Field(default=None, gt=0)
    extended_hours: bool = False
    client_order_id: Optional[str] = None
    take_profit_limit_price: Optional[float] = None
    stop_loss_stop_price: Optional[float] = None
    stop_loss_limit_price: Optional[float] = None


class ClosePositionRequest(BaseModel):
    symbol: str
    qty: Optional[float] = Field(default=None, gt=0)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def build_alpaca_router(db, get_current_user: Callable[[Request], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/alpaca", tags=["alpaca-trading"])

    async def require_user(request: Request) -> dict:
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required.")
        return user

    def require_configured():
        if not is_alpaca_configured():
            raise HTTPException(503, "Alpaca Trading API not configured. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY.")

    # ==================================================================
    # Status
    # ==================================================================

    @router.get("/status")
    async def alpaca_status():
        config = get_alpaca_config()
        if not config:
            return {"configured": False}
        return {
            "configured": True,
            "environment": config.environment.value,
            "base_url": config.base_url,
            "features": {
                "sync_thesis_trades": config.sync_thesis_trades,
                "webhooks": config.enable_webhooks,
                "fractional_shares": config.enable_fractional_shares,
                "bracket_orders": config.enable_bracket_orders,
                "short_selling": config.enable_short_selling,
            },
        }

    # ==================================================================
    # Account
    # ==================================================================

    @router.get("/account")
    async def alpaca_account(request: Request):
        require_configured()
        await require_user(request)
        info = get_account()
        if not info:
            raise HTTPException(502, "Unable to fetch account from Alpaca.")
        return {"item": info}

    # ==================================================================
    # Orders
    # ==================================================================

    @router.post("/orders")
    async def alpaca_submit_order(request: Request, payload: OrderRequest):
        require_configured()
        user = await require_user(request)
        config = get_alpaca_config()

        if payload.notional and config and not config.enable_fractional_shares:
            raise HTTPException(422, "Fractional shares (notional orders) are disabled.")
        if (payload.take_profit_limit_price or payload.stop_loss_stop_price) and config and not config.enable_bracket_orders:
            raise HTTPException(422, "Bracket orders are disabled.")
        if payload.order_type == "limit" and not payload.limit_price:
            raise HTTPException(422, "limit_price is required for limit orders.")
        if payload.order_type == "stop" and not payload.stop_price:
            raise HTTPException(422, "stop_price is required for stop orders.")
        if payload.order_type == "stop_limit" and (not payload.stop_price or not payload.limit_price):
            raise HTTPException(422, "Both stop_price and limit_price required for stop-limit orders.")
        if payload.order_type == "trailing_stop" and not payload.trail_percent and not payload.trail_price:
            raise HTTPException(422, "trail_percent or trail_price required for trailing stop orders.")
        if not payload.qty and not payload.notional:
            raise HTTPException(422, "Either qty or notional must be specified.")

        try:
            order = submit_order(
                symbol=payload.symbol, qty=payload.qty, notional=payload.notional,
                side=payload.side, order_type=payload.order_type,
                time_in_force=payload.time_in_force, limit_price=payload.limit_price,
                stop_price=payload.stop_price, trail_percent=payload.trail_percent,
                trail_price=payload.trail_price, extended_hours=payload.extended_hours,
                client_order_id=payload.client_order_id,
                take_profit_limit_price=payload.take_profit_limit_price,
                stop_loss_stop_price=payload.stop_loss_stop_price,
                stop_loss_limit_price=payload.stop_loss_limit_price,
            )
        except AlpacaClientError as exc:
            raise HTTPException(422, detail=exc.error.to_dict())

        if not order:
            raise HTTPException(502, "Order submission failed.")
        return {"item": order}

    @router.get("/orders")
    async def alpaca_list_orders(request: Request, status: str = "all", limit: int = 50):
        require_configured()
        await require_user(request)
        orders = list_orders(status=status, limit=min(limit, 500))
        return {"items": orders, "total": len(orders)}

    @router.get("/orders/{order_id}")
    async def alpaca_get_order(order_id: str, request: Request):
        require_configured()
        await require_user(request)
        order = get_order_by_id(order_id)
        if not order:
            raise HTTPException(404, "Order not found.")
        return {"item": order}

    @router.delete("/orders/{order_id}")
    async def alpaca_cancel_order(order_id: str, request: Request):
        require_configured()
        await require_user(request)
        if not cancel_order_by_id(order_id):
            raise HTTPException(400, "Failed to cancel order.")
        return {"message": "Order cancelled."}

    @router.delete("/orders")
    async def alpaca_cancel_all(request: Request):
        require_configured()
        await require_user(request)
        if not cancel_all_orders():
            raise HTTPException(400, "Failed to cancel all orders.")
        return {"message": "All orders cancelled."}

    # ==================================================================
    # Positions
    # ==================================================================

    @router.get("/positions")
    async def alpaca_positions(request: Request):
        require_configured()
        await require_user(request)
        positions = get_all_positions()
        return {"items": positions, "total": len(positions)}

    @router.get("/positions/{symbol}")
    async def alpaca_get_position(symbol: str, request: Request):
        require_configured()
        await require_user(request)
        pos = get_position(symbol)
        if not pos:
            raise HTTPException(404, f"No open position for {symbol}.")
        return {"item": pos}

    @router.post("/positions/close")
    async def alpaca_close_position(request: Request, payload: ClosePositionRequest):
        require_configured()
        await require_user(request)
        result = close_position(payload.symbol, qty=payload.qty)
        if not result:
            raise HTTPException(400, f"Failed to close position for {payload.symbol}.")
        return {"item": result}

    @router.post("/positions/liquidate")
    async def alpaca_liquidate(request: Request):
        require_configured()
        await require_user(request)
        if not close_all_positions():
            raise HTTPException(400, "Failed to liquidate.")
        return {"message": "All positions liquidated."}

    # ==================================================================
    # Portfolio History
    # ==================================================================

    @router.get("/portfolio-history")
    async def alpaca_portfolio_history(request: Request, period: str = "1M", timeframe: str = "1D"):
        require_configured()
        await require_user(request)
        history = get_portfolio_history(period=period, timeframe=timeframe)
        if not history:
            return {"timestamp": [], "equity": [], "profit_loss": [], "profit_loss_pct": [], "base_value": 0}
        return history

    # ==================================================================
    # Assets
    # ==================================================================

    @router.get("/assets/{symbol}")
    async def alpaca_asset_info(symbol: str):
        require_configured()
        asset = get_asset(symbol)
        if not asset:
            raise HTTPException(404, f"Asset {symbol} not found.")
        return {"item": asset}

    return router
