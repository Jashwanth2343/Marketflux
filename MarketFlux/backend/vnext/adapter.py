from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request

from market_data import get_market_overview, get_rich_stock_data
from vnext.adapter_helpers import build_adapter_envelope, collect_regime_inputs
from vnext.engines import (
    build_ticker_workspace,
    build_watchlist_board,
    build_portfolio_diagnostics,
    build_signal_feed,
)

def build_adapter_router(db: Any, get_current_user: Callable[[Request], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/vnext-adapter", tags=["marketflux-adapter"])

    @router.get("/macro/regime-inputs")
    async def get_regime_inputs():
        inputs = await collect_regime_inputs()
        payload = {
            "VIX": inputs.get("vix"),
            "SP500_daily_change": inputs.get("sp500_change_percent"),
            "NASDAQ_daily_change": inputs.get("nasdaq_change_percent"),
            "TLT_daily_change": inputs.get("tlt_change_percent"),
            "unemployment_rate": inputs.get("unemployment_rate"),
            "10Y_2Y_spread": inputs.get("ten_two_spread"),
        }
        return build_adapter_envelope(
            payload=payload,
            data_as_of=inputs.get("data_as_of"),
            source="MarketFlux Retail Core"
        )

    @router.get("/market/overview")
    async def get_overview():
        data = await get_market_overview()
        return build_adapter_envelope(payload=data, source="MarketFlux Retail Core")

    @router.get("/market/ticker/{ticker}")
    async def get_ticker(ticker: str):
        try:
            data = await get_rich_stock_data(ticker.upper())
            return build_adapter_envelope(payload=data, source="MarketFlux Retail Core")
        except Exception as e:
            raise HTTPException(404, str(e))

    @router.get("/research/ticker/{ticker}")
    async def get_research_ticker(ticker: str):
        data = await build_ticker_workspace(ticker)
        return build_adapter_envelope(payload=data, source="MarketFlux Retail Core")

    @router.get("/watchlist")
    async def get_watchlist(request: Request):
        user = await get_current_user(request)
        data = await build_watchlist_board(db, user)
        return build_adapter_envelope(payload=data, source="MarketFlux Retail Core")

    @router.get("/portfolio")
    async def get_portfolio(request: Request):
        user = await get_current_user(request)
        data = await build_portfolio_diagnostics(db, user)
        return build_adapter_envelope(payload=data, source="MarketFlux Retail Core")

    @router.get("/signals")
    async def get_signals():
        data = await build_signal_feed(db)
        return build_adapter_envelope(payload=data, source="MarketFlux Retail Core")

    return router
