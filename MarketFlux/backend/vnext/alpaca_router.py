"""FastAPI router for Alpaca Broker API integration.

Production-grade endpoints supporting:
- Account lifecycle (create, fund, KYC status, trading account)
- All order types (market, limit, stop, stop-limit, trailing stop, bracket)
- Fractional shares via notional amounts
- Position management (view, partial/full close, liquidate)
- Portfolio history and P&L
- Asset lookup and tradability checks
- Order replacement/modification
"""
from __future__ import annotations

from typing import Any, Callable, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .alpaca_client import (
    AlpacaClientError,
    cancel_all_orders,
    cancel_order,
    close_all_positions,
    close_position,
    create_trading_account,
    get_account,
    get_asset,
    get_order,
    get_portfolio_history,
    get_position,
    get_positions,
    get_trade_account,
    list_orders,
    replace_order,
    submit_bracket_order,
    submit_limit_order,
    submit_market_order,
    submit_order,
    submit_stop_limit_order,
    submit_stop_order,
    submit_trailing_stop_order,
)
from .alpaca_config import get_alpaca_config, is_alpaca_configured


# ---------------------------------------------------------------------------
# Request/Response models
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
    # Bracket order fields
    take_profit_limit_price: Optional[float] = None
    stop_loss_stop_price: Optional[float] = None
    stop_loss_limit_price: Optional[float] = None


class ReplaceOrderRequest(BaseModel):
    qty: Optional[float] = Field(default=None, gt=0)
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: Optional[str] = Field(default=None, pattern="^(day|gtc|ioc|fok|opg|cls)$")


class ClosePositionRequest(BaseModel):
    symbol: str
    qty: Optional[float] = Field(default=None, gt=0)


class AccountCreateRequest(BaseModel):
    given_name: Optional[str] = None
    family_name: Optional[str] = None


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

    def require_configured():
        if not is_alpaca_configured():
            raise HTTPException(503, "Alpaca Broker API is not configured. Set ALPACA_BROKER_API_KEY and ALPACA_BROKER_API_SECRET.")

    async def _get_or_create_alpaca_account(user: dict) -> str:
        """Get the user's Alpaca account_id, auto-creating if enabled."""
        user_id = user["user_id"]
        user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        alpaca_account_id = (user_doc or {}).get("alpaca_account_id")

        if alpaca_account_id:
            return alpaca_account_id

        config = get_alpaca_config()
        if not config or not config.auto_create_accounts:
            raise HTTPException(
                412,
                "No Alpaca account linked. Create one first via POST /api/alpaca/account.",
            )

        given_name = user.get("name", "Paper").split()[0] if user.get("name") else "Paper"
        family_name = (
            user.get("name", "Trader").split()[-1]
            if user.get("name") and len(user.get("name", "").split()) > 1
            else "Trader"
        )
        email = user.get("email", f"{user_id}@marketflux.paper")

        result = create_trading_account(
            given_name=given_name,
            family_name=family_name,
            email=email,
        )
        if not result:
            raise HTTPException(502, "Failed to create Alpaca trading account.")

        alpaca_account_id = result["account_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "alpaca_account_id": alpaca_account_id,
                "alpaca_account_created_at": result.get("created_at"),
            }},
        )
        return alpaca_account_id

    # ==================================================================
    # Status / Health
    # ==================================================================

    @router.get("/status")
    async def alpaca_status():
        """Check Alpaca integration status and feature flags."""
        config = get_alpaca_config()
        if not config:
            return {"configured": False}
        return {
            "configured": True,
            "environment": config.environment.value,
            "base_url": config.base_url,
            "features": {
                "auto_create_accounts": config.auto_create_accounts,
                "sync_thesis_trades": config.sync_thesis_trades,
                "webhooks": config.enable_webhooks,
                "fractional_shares": config.enable_fractional_shares,
                "bracket_orders": config.enable_bracket_orders,
                "short_selling": config.enable_short_selling,
            },
            "limits": {
                "max_order_qty": config.max_order_qty,
                "max_notional_per_order": config.max_notional_per_order,
                "rate_limit_rpm": config.rate_limit_rpm,
            },
        }

    # ==================================================================
    # Account Lifecycle
    # ==================================================================

    @router.get("/account")
    async def alpaca_account(request: Request):
        """Get the user's Alpaca paper trading account summary."""
        require_configured()
        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user)
        account_info = get_account(account_id)
        if not account_info:
            raise HTTPException(502, "Unable to fetch account from Alpaca.")
        return {"item": account_info}

    @router.get("/account/trading")
    async def alpaca_trading_account(request: Request):
        """Get detailed trading account info (margin, buying power, day trade count)."""
        require_configured()
        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user)
        trade_info = get_trade_account(account_id)
        if not trade_info:
            raise HTTPException(502, "Unable to fetch trading account from Alpaca.")
        return {"item": trade_info}

    @router.post("/account")
    async def alpaca_create_account(request: Request, payload: AccountCreateRequest):
        """Explicitly provision an Alpaca sub-account for the user."""
        require_configured()
        user = await require_user(request)

        user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
        existing_id = (user_doc or {}).get("alpaca_account_id")
        if existing_id:
            account_info = get_account(existing_id)
            return {"item": account_info, "message": "Account already exists.", "created": False}

        account_id = await _get_or_create_alpaca_account(user)
        account_info = get_account(account_id)
        return {"item": account_info, "message": "Account created.", "created": True}

    # ==================================================================
    # Orders -- Full order type support
    # ==================================================================

    @router.post("/orders")
    async def alpaca_submit_order(request: Request, payload: OrderRequest):
        """Submit any order type. Supports market, limit, stop, stop-limit, trailing stop, and bracket."""
        require_configured()
        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user)

        config = get_alpaca_config()

        # Validate feature flags
        if payload.notional and config and not config.enable_fractional_shares:
            raise HTTPException(422, "Fractional shares (notional orders) are disabled.")
        if (payload.take_profit_limit_price or payload.stop_loss_stop_price) and config and not config.enable_bracket_orders:
            raise HTTPException(422, "Bracket orders are disabled.")
        if payload.side == "sell" and config and not config.enable_short_selling:
            # Only block short sales, not selling existing positions
            positions = get_positions(account_id)
            has_position = any(p["symbol"] == payload.symbol.upper() for p in positions)
            if not has_position:
                raise HTTPException(422, "Short selling is disabled. You can only sell existing positions.")

        # Validate order type requirements
        if payload.order_type == "limit" and not payload.limit_price:
            raise HTTPException(422, "limit_price is required for limit orders.")
        if payload.order_type == "stop" and not payload.stop_price:
            raise HTTPException(422, "stop_price is required for stop orders.")
        if payload.order_type == "stop_limit" and (not payload.stop_price or not payload.limit_price):
            raise HTTPException(422, "Both stop_price and limit_price are required for stop-limit orders.")
        if payload.order_type == "trailing_stop" and not payload.trail_percent and not payload.trail_price:
            raise HTTPException(422, "Either trail_percent or trail_price is required for trailing stop orders.")
        if not payload.qty and not payload.notional:
            raise HTTPException(422, "Either qty or notional must be specified.")

        try:
            order = submit_order(
                account_id=account_id,
                symbol=payload.symbol,
                qty=payload.qty,
                notional=payload.notional,
                side=payload.side,
                order_type=payload.order_type,
                time_in_force=payload.time_in_force,
                limit_price=payload.limit_price,
                stop_price=payload.stop_price,
                trail_percent=payload.trail_percent,
                trail_price=payload.trail_price,
                extended_hours=payload.extended_hours,
                client_order_id=payload.client_order_id,
                take_profit_limit_price=payload.take_profit_limit_price,
                stop_loss_stop_price=payload.stop_loss_stop_price,
                stop_loss_limit_price=payload.stop_loss_limit_price,
            )
        except AlpacaClientError as exc:
            raise HTTPException(422, detail=exc.error.to_dict())

        if not order:
            raise HTTPException(502, "Order submission failed.")

        # Log to audit trail
        await db.alpaca_events.insert_one({
            "event_type": "order.submitted",
            "user_id": user["user_id"],
            "account_id": account_id,
            "order_id": order["order_id"],
            "symbol": payload.symbol,
            "side": payload.side,
            "qty": payload.qty,
            "notional": payload.notional,
            "order_type": payload.order_type,
            "submitted_at": order.get("submitted_at"),
        })

        return {"item": order}

    @router.get("/orders")
    async def alpaca_list_orders(request: Request, status: str = "all", limit: int = 50):
        """List orders. Filter by status: open, closed, all."""
        require_configured()
        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user)
        orders = list_orders(account_id, status=status, limit=min(limit, 500))
        return {"items": orders, "total": len(orders)}

    @router.get("/orders/{order_id}")
    async def alpaca_get_order(order_id: str, request: Request):
        """Get a specific order by ID."""
        require_configured()
        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user)
        order = get_order(account_id, order_id)
        if not order:
            raise HTTPException(404, "Order not found.")
        return {"item": order}

    @router.patch("/orders/{order_id}")
    async def alpaca_replace_order(order_id: str, request: Request, payload: ReplaceOrderRequest):
        """Modify/replace an existing pending order."""
        require_configured()
        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user)
        order = replace_order(
            account_id=account_id,
            order_id=order_id,
            qty=payload.qty,
            limit_price=payload.limit_price,
            stop_price=payload.stop_price,
            time_in_force=payload.time_in_force,
        )
        if not order:
            raise HTTPException(400, "Failed to replace order.")
        return {"item": order}

    @router.delete("/orders/{order_id}")
    async def alpaca_cancel_order(order_id: str, request: Request):
        """Cancel a pending order."""
        require_configured()
        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user)
        success = cancel_order(account_id, order_id)
        if not success:
            raise HTTPException(400, "Failed to cancel order.")
        return {"message": "Order cancelled."}

    @router.delete("/orders")
    async def alpaca_cancel_all_orders(request: Request):
        """Cancel all open orders."""
        require_configured()
        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user)
        success = cancel_all_orders(account_id)
        if not success:
            raise HTTPException(400, "Failed to cancel all orders.")
        return {"message": "All orders cancelled."}

    # ==================================================================
    # Positions
    # ==================================================================

    @router.get("/positions")
    async def alpaca_positions(request: Request):
        """Get all open positions."""
        require_configured()
        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user)
        positions = get_positions(account_id)
        return {"items": positions, "total": len(positions)}

    @router.get("/positions/{symbol}")
    async def alpaca_get_position(symbol: str, request: Request):
        """Get a specific position by symbol."""
        require_configured()
        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user)
        position = get_position(account_id, symbol)
        if not position:
            raise HTTPException(404, f"No open position for {symbol}.")
        return {"item": position}

    @router.post("/positions/close")
    async def alpaca_close_position(request: Request, payload: ClosePositionRequest):
        """Close a position (full or partial)."""
        require_configured()
        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user)
        result = close_position(account_id, payload.symbol, qty=payload.qty)
        if not result:
            raise HTTPException(400, f"Failed to close position for {payload.symbol}.")
        return {"item": result, "message": f"Position closed for {payload.symbol}."}

    @router.post("/positions/liquidate")
    async def alpaca_liquidate_all(request: Request):
        """Liquidate ALL positions (emergency use)."""
        require_configured()
        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user)
        success = close_all_positions(account_id)
        if not success:
            raise HTTPException(400, "Failed to liquidate positions.")

        await db.alpaca_events.insert_one({
            "event_type": "positions.liquidated_all",
            "user_id": user["user_id"],
            "account_id": account_id,
        })

        return {"message": "All positions liquidated."}

    # ==================================================================
    # Portfolio History
    # ==================================================================

    @router.get("/portfolio-history")
    async def alpaca_portfolio_history(request: Request, period: str = "1M", timeframe: str = "1D"):
        """Get portfolio value history for P&L charting."""
        require_configured()

        valid_periods = {"1D", "1W", "1M", "3M", "6M", "1A", "all"}
        valid_timeframes = {"1Min", "5Min", "15Min", "1H", "1D"}
        if period not in valid_periods:
            raise HTTPException(422, f"Invalid period. Use: {', '.join(sorted(valid_periods))}")
        if timeframe not in valid_timeframes:
            raise HTTPException(422, f"Invalid timeframe. Use: {', '.join(sorted(valid_timeframes))}")

        user = await require_user(request)
        account_id = await _get_or_create_alpaca_account(user)
        history = get_portfolio_history(account_id, period=period, timeframe=timeframe)
        if not history:
            return {"timestamp": [], "equity": [], "profit_loss": [], "profit_loss_pct": [], "base_value": 0, "timeframe": timeframe}
        return history

    # ==================================================================
    # Asset Information
    # ==================================================================

    @router.get("/assets/{symbol}")
    async def alpaca_asset_info(symbol: str):
        """Check if a symbol is tradable, fractionable, shortable, etc."""
        require_configured()
        asset = get_asset(symbol)
        if not asset:
            raise HTTPException(404, f"Asset {symbol} not found or not tradable.")
        return {"item": asset}

    return router
