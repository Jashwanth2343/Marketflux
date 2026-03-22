from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from market_data import get_market_overview, get_rich_stock_data

from .adapter_helpers import build_adapter_envelope, collect_regime_inputs
from .engines import (
    build_macro_regime_view,
    build_portfolio_diagnostics,
    build_signal_feed,
    build_ticker_workspace,
    build_watchlist_board,
)


def _utcnow_zulu() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _latest_timestamp_from_mapping(payload: Dict[str, Any]) -> str:
    timestamps = []
    for value in payload.values():
        if isinstance(value, dict):
            maybe_ts = value.get("as_of")
            if maybe_ts:
                timestamps.append(maybe_ts)
    if not timestamps:
        return _utcnow_zulu()
    parsed = []
    for value in timestamps:
        try:
            parsed.append(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
        except ValueError:
            continue
    if not parsed:
        return _utcnow_zulu()
    return max(parsed).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_vnext_adapter_router(db, get_current_user: Callable[[Request], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/vnext-adapter", tags=["marketflux-vnext-adapter"])

    @router.get("/market/overview")
    async def market_overview():
        payload = await get_market_overview()
        return build_adapter_envelope(
            payload={"indices": payload},
            data_as_of=_latest_timestamp_from_mapping(payload),
        )

    @router.get("/macro/regime-inputs")
    async def regime_inputs():
        payload = await collect_regime_inputs()
        return build_adapter_envelope(payload=payload, data_as_of=payload.get("data_as_of"))

    @router.get("/market/ticker/{ticker}")
    async def market_ticker(ticker: str):
        normalized = ticker.upper().strip()
        payload = await get_rich_stock_data(normalized)
        return build_adapter_envelope(
            payload={"ticker": normalized, "snapshot": payload},
            data_as_of=payload.get("as_of") or _utcnow_zulu(),
        )

    @router.get("/research/ticker/{ticker}")
    async def research_ticker(ticker: str):
        normalized = ticker.upper().strip()
        payload = await build_ticker_workspace(normalized)
        return build_adapter_envelope(payload=payload, data_as_of=payload.get("as_of"))

    @router.get("/watchlist")
    async def watchlist(request: Request):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required to view watchlist data")
        payload = await build_watchlist_board(db, user)
        return build_adapter_envelope(payload=payload, data_as_of=payload.get("as_of"))

    @router.get("/portfolio")
    async def portfolio(request: Request):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required to view portfolio data")
        payload = await build_portfolio_diagnostics(db, user)
        return build_adapter_envelope(payload=payload, data_as_of=payload.get("as_of"))

    @router.get("/signals")
    async def signals():
        payload = await build_signal_feed(db, limit=12, persist=False)
        data_as_of = payload[0].get("freshness") if payload else _utcnow_zulu()
        return build_adapter_envelope(payload={"signals": payload}, data_as_of=data_as_of)

    @router.get("/macro/regime")
    async def regime():
        payload = await build_macro_regime_view()
        return build_adapter_envelope(payload=payload, data_as_of=payload.get("as_of"))

    return router
