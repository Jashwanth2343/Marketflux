"""FastAPI router for Alpaca Trading API integration.

Single shared paper account — no sub-account management.
Provides endpoints for orders, positions, portfolio history, and asset lookup.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from trading_halt import HALT_MESSAGE, is_trading_halted

logger = logging.getLogger(__name__)

from .alpaca_client import (
    cancel_all_orders,
    cancel_order,
    close_all_positions,
    close_position,
    get_account,
    get_alpaca_mode,
    get_asset,
    get_order,
    get_portfolio_history,
    get_positions,
    is_alpaca_configured,
    is_broker_mode,
    list_orders,
    submit_limit_order,
    submit_market_order,
    # Broker mode functions
    broker_cancel_all_orders,
    broker_cancel_order,
    broker_close_all_positions,
    broker_close_position,
    broker_create_trading_account,
    broker_get_account,
    broker_get_order,
    broker_get_portfolio_history,
    broker_get_positions,
    broker_list_orders,
    broker_submit_market_order,
)


# ---------------------------------------------------------------------------
# Request models
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
    qty: Optional[float] = None


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
            if is_broker_mode():
                raise HTTPException(503, "Alpaca Broker API is not configured. Set ALPACA_BROKER_API_KEY and ALPACA_BROKER_API_SECRET.")
            raise HTTPException(503, "Alpaca Trading API is not configured. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY.")

    async def _get_or_create_broker_account(user: dict) -> str:
        """Broker mode only: get or create a per-user sub-account.

        Creation is guarded by an atomic ``find_one_and_update`` claim so two
        concurrent requests for the same user cannot create duplicate
        sub-accounts (the old find-one -> create -> upsert had a TOCTOU race).
        A claim left stale for >120s (e.g. a crashed request) may be stolen.
        """
        from pymongo import ReturnDocument

        user_id = user["user_id"]

        async def _current_account_id() -> Optional[str]:
            doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "alpaca_account_id": 1})
            return (doc or {}).get("alpaca_account_id")

        account_id = await _current_account_id()
        if account_id:
            return account_id

        # Ensure the user doc exists (atomic upsert on the unique user_id).
        await db.users.update_one(
            {"user_id": user_id}, {"$setOnInsert": {"user_id": user_id}}, upsert=True
        )

        # Atomically claim the creation slot: exactly one concurrent requester
        # wins; losers wait for the winner to finish.
        claim_token = uuid.uuid4().hex
        now = time.time()
        claimed = await db.users.find_one_and_update(
            {
                "user_id": user_id,
                "alpaca_account_id": {"$exists": False},
                "$or": [
                    {"alpaca_account_creating": {"$exists": False}},
                    {"alpaca_account_creating_at": {"$lt": now - 120}},
                ],
            },
            {"$set": {"alpaca_account_creating": claim_token, "alpaca_account_creating_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if claimed is None or claimed.get("alpaca_account_creating") != claim_token:
            # Lost the race — poll for the winner's result instead of
            # creating a second sub-account.
            for _ in range(20):
                await asyncio.sleep(0.5)
                account_id = await _current_account_id()
                if account_id:
                    return account_id
            raise HTTPException(503, "Sub-account creation in progress by another request; retry shortly.")

        try:
            given_name = user.get("name", "Paper").split()[0] if user.get("name") else "Paper"
            family_name = (
                user.get("name", "Trader").split()[-1]
                if user.get("name") and len(user.get("name", "").split()) > 1
                else "Trader"
            )
            email = user.get("email", f"{user_id}@marketflux.paper")

            result = await asyncio.to_thread(
                broker_create_trading_account,
                given_name=given_name,
                family_name=family_name,
                email=email,
            )
            if not result:
                raise HTTPException(503, "Failed to create Alpaca sub-account. Check Broker API credentials.")

            account_id = result["account_id"]
            await db.users.update_one(
                {"user_id": user_id, "alpaca_account_creating": claim_token},
                {
                    "$set": {"alpaca_account_id": account_id},
                    "$unset": {"alpaca_account_creating": "", "alpaca_account_creating_at": ""},
                },
            )
            return account_id
        finally:
            # Release the claim if we failed before recording the account id,
            # so a retry isn't stuck behind our own stale claim.
            await db.users.update_one(
                {
                    "user_id": user_id,
                    "alpaca_account_creating": claim_token,
                    "alpaca_account_id": {"$exists": False},
                },
                {"$unset": {"alpaca_account_creating": "", "alpaca_account_creating_at": ""}},
            )

    # ------------------------------------------------------------------
    # Health / config check
    # ------------------------------------------------------------------

    @router.get("/status")
    async def alpaca_status():
        mode = get_alpaca_mode()
        return {
            "configured": is_alpaca_configured(),
            "mode": "paper",
            "provider": f"alpaca-{mode}-api",
            "multi_tenant": is_broker_mode(),
        }

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    @router.get("/account")
    async def alpaca_account(request: Request):
        _require_configured()
        user = await require_user(request)
        if is_broker_mode():
            account_id = await _get_or_create_broker_account(user)
            account_info = await asyncio.to_thread(broker_get_account, account_id)
        else:
            account_info = await asyncio.to_thread(get_account)
        if not account_info:
            raise HTTPException(502, "Unable to fetch account from Alpaca.")
        return {"item": account_info}

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    @router.post("/orders")
    async def alpaca_submit_order(request: Request, payload: AlpacaOrderRequest):
        _require_configured()
        if is_trading_halted():
            raise HTTPException(403, HALT_MESSAGE)
        user = await require_user(request)

        if is_broker_mode():
            account_id = await _get_or_create_broker_account(user)
            if payload.order_type == "limit":
                if payload.limit_price is None or payload.limit_price <= 0:
                    raise HTTPException(422, "limit_price is required for limit orders.")
                order = await asyncio.to_thread(
                    broker_submit_market_order,
                    account_id=account_id,
                    symbol=payload.symbol,
                    qty=payload.qty,
                    side=payload.side,
                    time_in_force=payload.time_in_force,
                    order_type="limit",
                    limit_price=payload.limit_price,
                )
            else:
                order = await asyncio.to_thread(
                    broker_submit_market_order,
                    account_id=account_id,
                    symbol=payload.symbol,
                    qty=payload.qty,
                    side=payload.side,
                    time_in_force=payload.time_in_force,
                )
        elif payload.order_type == "limit":
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
        _require_configured()
        user = await require_user(request)
        if is_broker_mode():
            account_id = await _get_or_create_broker_account(user)
            orders = await asyncio.to_thread(broker_list_orders, account_id, status=status, limit=min(limit, 200))
        else:
            orders = await asyncio.to_thread(list_orders, status=status, limit=min(limit, 200))
        return {"items": orders, "total": len(orders)}

    @router.get("/orders/{order_id}")
    async def alpaca_get_order(order_id: str, request: Request):
        _require_configured()
        user = await require_user(request)
        if is_broker_mode():
            # Scoped to the caller's sub-account: users can never see
            # another user's orders (previously used the shared account).
            account_id = await _get_or_create_broker_account(user)
            order = await asyncio.to_thread(broker_get_order, account_id, order_id)
        else:
            order = await asyncio.to_thread(get_order, order_id)
        if not order:
            raise HTTPException(404, "Order not found.")
        return {"item": order}

    @router.delete("/orders/{order_id}")
    async def alpaca_cancel_order(order_id: str, request: Request):
        _require_configured()
        if is_trading_halted():
            raise HTTPException(403, HALT_MESSAGE)
        user = await require_user(request)
        if is_broker_mode():
            account_id = await _get_or_create_broker_account(user)
            success = await asyncio.to_thread(broker_cancel_order, account_id, order_id)
        else:
            success = await asyncio.to_thread(cancel_order, order_id)
        if not success:
            raise HTTPException(400, "Failed to cancel order. It may already be filled or cancelled.")
        return {"message": "Order cancelled successfully."}

    @router.delete("/orders")
    async def alpaca_cancel_all_orders(request: Request):
        _require_configured()
        if is_trading_halted():
            raise HTTPException(403, HALT_MESSAGE)
        user = await require_user(request)
        if is_broker_mode():
            # Scoped to the caller's sub-account (previously cancelled ALL
            # users' orders via the shared account).
            account_id = await _get_or_create_broker_account(user)
            results = await asyncio.to_thread(broker_cancel_all_orders, account_id)
        else:
            results = await asyncio.to_thread(cancel_all_orders)
        return {"cancelled": results, "total": len(results)}

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    @router.get("/positions")
    async def alpaca_positions(request: Request):
        _require_configured()
        user = await require_user(request)
        if is_broker_mode():
            account_id = await _get_or_create_broker_account(user)
            positions = await asyncio.to_thread(broker_get_positions, account_id)
        else:
            positions = await asyncio.to_thread(get_positions)
        return {"items": positions, "total": len(positions)}

    @router.post("/positions/close")
    async def alpaca_close_position(request: Request, payload: AlpacaClosePositionRequest):
        _require_configured()
        if is_trading_halted():
            raise HTTPException(403, HALT_MESSAGE)
        user = await require_user(request)
        if is_broker_mode():
            account_id = await _get_or_create_broker_account(user)
            result = await asyncio.to_thread(broker_close_position, account_id, payload.symbol, payload.qty)
        else:
            result = await asyncio.to_thread(close_position, payload.symbol, payload.qty)
        if not result:
            raise HTTPException(400, f"Failed to close position for {payload.symbol}.")
        return {"item": result, "message": f"Position closed for {payload.symbol}."}

    @router.post("/positions/liquidate")
    async def alpaca_liquidate_all(request: Request):
        _require_configured()
        if is_trading_halted():
            raise HTTPException(403, HALT_MESSAGE)
        user = await require_user(request)
        if is_broker_mode():
            # Scoped to the caller's sub-account (previously liquidated the
            # shared account, closing every user's positions).
            account_id = await _get_or_create_broker_account(user)
            results = await asyncio.to_thread(broker_close_all_positions, account_id)
        else:
            results = await asyncio.to_thread(close_all_positions)
        return {"closed": results, "total": len(results)}

    # ------------------------------------------------------------------
    # Portfolio History
    # ------------------------------------------------------------------

    @router.get("/portfolio-history")
    async def alpaca_portfolio_history(request: Request, period: str = "1M", timeframe: str = "1D"):
        _require_configured()

        valid_periods = {"1D", "1W", "1M", "3M", "6M", "1A", "all"}
        valid_timeframes = {"1Min", "5Min", "15Min", "1H", "1D"}
        if period not in valid_periods:
            raise HTTPException(422, f"Invalid period. Must be one of: {', '.join(sorted(valid_periods))}")
        if timeframe not in valid_timeframes:
            raise HTTPException(422, f"Invalid timeframe. Must be one of: {', '.join(sorted(valid_timeframes))}")

        user = await require_user(request)
        if is_broker_mode():
            account_id = await _get_or_create_broker_account(user)
            history = await asyncio.to_thread(broker_get_portfolio_history, account_id, period=period, timeframe=timeframe)
        else:
            history = await asyncio.to_thread(get_portfolio_history, period=period, timeframe=timeframe)
        if not history:
            return {"timestamp": [], "equity": [], "profit_loss": [], "profit_loss_pct": [], "base_value": 0, "timeframe": timeframe}
        return history

    # ------------------------------------------------------------------
    # Asset lookup
    # ------------------------------------------------------------------

    @router.get("/assets/{symbol}")
    async def alpaca_get_asset(symbol: str, request: Request):
        _require_configured()
        await require_user(request)
        asset = await asyncio.to_thread(get_asset, symbol)
        if not asset:
            raise HTTPException(404, f"Asset {symbol} not found or not tradable.")
        return {"item": asset}

    return router
