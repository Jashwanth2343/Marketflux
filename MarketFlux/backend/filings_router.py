"""FastAPI router exposing the SEC EDGAR full-text layer to the terminal UI.

Read-only, free public data, no auth required — same posture as the market
data endpoints. The copilot reaches these capabilities as agent tools
(sec_filings.*); these routes give the Filings panel direct access.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

import sec_filings

logger = logging.getLogger(__name__)


def build_filings_router() -> APIRouter:
    router = APIRouter(prefix="/api/filings", tags=["filings"])

    @router.get("/{symbol}")
    async def filings_list(symbol: str):
        res = await sec_filings.get_recent_filings(symbol)
        if not res.get("ok"):
            raise HTTPException(404, res.get("error", "no filings"))
        return res

    @router.get("/{symbol}/risk-diff")
    async def filings_risk_diff(symbol: str):
        res = await sec_filings.diff_risk_factors(symbol)
        if not res.get("ok"):
            raise HTTPException(404, res.get("error", "diff unavailable"))
        return res

    @router.get("/{symbol}/search")
    async def filings_search(symbol: str, q: str = Query(min_length=2, max_length=200),
                             form: str = "10-K"):
        res = await sec_filings.search_filings(symbol, q, form=form)
        if not res.get("ok"):
            raise HTTPException(404, res.get("error", "search unavailable"))
        return res

    return router
