from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Request

from .thesis_router import build_thesis_router


def build_vnext_router(db, get_current_user: Callable[[Request], Any]) -> APIRouter:
    """vnext API surface for the main MarketFlux app.

    Historically this router also exposed read-only research endpoints
    (briefing/today, signals/feed, command-center, research/ticker,
    watchlists/board, portfolio/diagnostics, compare, methodology,
    mirofish/*, terminal/strategy/stream) that were consumed exclusively by
    the standalone Next.js `quant-app` marketing/research site. That app has
    been retired, so those handlers were removed. The thesis/policy/paper-trade
    routes below remain — the main app (port 3000) depends on them.
    """
    router = APIRouter(prefix="/api/vnext", tags=["marketflux-vnext"])
    router.include_router(build_thesis_router(db, get_current_user))
    return router
